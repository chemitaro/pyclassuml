from __future__ import annotations

import ctypes
from dataclasses import dataclass
from datetime import datetime, timezone
import errno
import hashlib
import os
from pathlib import Path
import platform
import secrets
import stat
from typing import TYPE_CHECKING

from spec_dock_runtime.domain.issue_planning_contracts import PlanningPublicationSourceStale
from spec_dock_runtime.infra.issue_planning_candidate import (
    OutputDirectoryGuard,
    read_bounded_regular_file,
    validate_candidate_output_directory,
)

if TYPE_CHECKING:
    from collections.abc import Callable

MAX_REVIEW_RESULT_BYTES = 1024 * 1024


@dataclass(frozen=True)
class PublishedPlanningReview:
    review_result_file: str
    review_summary_file: str
    review_result_sha256: str


class ReviewSourceStale(PlanningPublicationSourceStale):
    pass


@dataclass
class _OwnedReviewDirectory:
    name: str
    descriptor: int
    device: int
    inode: int
    file_identities: dict[str, tuple[int, int]]


def read_external_review_result(
    path: Path,
    *,
    repo_root: Path,
    expected_sha256: str,
) -> bytes:
    if len(expected_sha256) != 64 or any(character not in "0123456789abcdef" for character in expected_sha256):
        raise ValueError("Review result SHA-256 is invalid")
    lexical = path.absolute()
    if not lexical.exists() or not lexical.is_file() or _has_symlink_component(lexical):
        raise FileNotFoundError("Review result is unavailable")
    resolved = lexical.resolve(strict=True)
    repository = repo_root.resolve(strict=True)
    if resolved == repository or resolved.is_relative_to(repository):
        raise ValueError("Review result must be outside the repository")
    try:
        data = read_bounded_regular_file(resolved, max_bytes=MAX_REVIEW_RESULT_BYTES)
    except ValueError as error:
        reason = "bounded size" if "bounded" in str(error) else "unavailable"
        if reason == "bounded size":
            raise ValueError("Review result exceeds the bounded size") from None
        raise FileNotFoundError("Review result is unavailable") from None
    data.decode("utf-8", errors="strict")
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("Review result SHA-256 mismatch")
    return data


def publish_planning_review_evidence(
    *,
    output_dir: Path,
    repo_root: Path,
    reviewed_identity_sha256: str,
    review_result_bytes: bytes,
    summary_bytes: bytes,
    operation_time: datetime,
    publication_guard: Callable[[], bool],
) -> PublishedPlanningReview:
    guard = validate_candidate_output_directory(output_dir, repo_root)
    if len(reviewed_identity_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in reviewed_identity_sha256
    ):
        raise ValueError("reviewed identity SHA-256 is invalid")
    if len(review_result_bytes) > MAX_REVIEW_RESULT_BYTES:
        raise ValueError("Review result exceeds the bounded size")
    review_result_bytes.decode("utf-8", errors="strict")
    summary_bytes.decode("utf-8", errors="strict")
    instant = operation_time.astimezone(timezone.utc).replace(microsecond=0)
    token = instant.strftime("%Y%m%dt%H%M%Sz")
    directory_name = f"review-{token}-{reviewed_identity_sha256}"
    output_descriptor = _open_guarded_output_directory(guard)
    staged: _OwnedReviewDirectory | None = None
    published = False
    cleanup_attempted = False
    cleanup_proven = False
    failure: BaseException | None = None
    try:
        _ensure_relative_name_absent(output_descriptor, directory_name)
        _revalidate_output_guard(guard, repo_root)
        temporary_name = _create_temporary_directory_at(output_descriptor)
        temporary_descriptor = _open_directory_at(output_descriptor, temporary_name)
        opened = os.fstat(temporary_descriptor)
        staged = _OwnedReviewDirectory(
            name=temporary_name,
            descriptor=temporary_descriptor,
            device=opened.st_dev,
            inode=opened.st_ino,
            file_identities={},
        )
        _write_exact_at(
            temporary_descriptor,
            "planning-review-result.json",
            review_result_bytes,
        )
        _write_exact_at(
            temporary_descriptor,
            "planning-review-summary.md",
            summary_bytes,
        )
        os.fsync(temporary_descriptor)
        _verify_review_directory_contents(
            staged,
            {
                "planning-review-result.json": review_result_bytes,
                "planning-review-summary.md": summary_bytes,
            },
        )
        _revalidate_output_guard(guard, repo_root)
        _atomic_publish_no_replace_at(
            output_descriptor,
            staged,
            directory_name,
            expected_files={
                "planning-review-result.json": review_result_bytes,
                "planning-review-summary.md": summary_bytes,
            },
        )
        os.fsync(output_descriptor)
        _revalidate_output_guard(guard, repo_root)
        try:
            current = publication_guard()
        except Exception as error:
            raise OSError("review publication failed") from error
        if not current:
            cleanup_attempted = True
            cleanup_proven = _remove_evidence_directory_at(output_descriptor, staged)
            if cleanup_proven:
                raise ReviewSourceStale("Review source changed during publication")
            raise OSError("review publication cleanup failed")
        published = True
    except BaseException as error:
        failure = error
    finally:
        if staged is not None:
            if not published and not cleanup_attempted:
                cleanup_attempted = True
                cleanup_proven = _remove_evidence_directory_at(output_descriptor, staged)
            os.close(staged.descriptor)
        os.close(output_descriptor)
    if failure is not None:
        if staged is not None and staged.name == directory_name and cleanup_attempted and not cleanup_proven:
            raise OSError("review publication failed") from failure
        raise failure
    return PublishedPlanningReview(
        review_result_file=f"{directory_name}/planning-review-result.json",
        review_summary_file=f"{directory_name}/planning-review-summary.md",
        review_result_sha256=hashlib.sha256(review_result_bytes).hexdigest(),
    )


def _write_exact_at(directory_descriptor: int, name: str, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(name, flags, 0o600, dir_fd=directory_descriptor)
    try:
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _has_symlink_component(path: Path) -> bool:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            return True
    return False


def _revalidate_output_guard(guard: OutputDirectoryGuard, repo_root: Path) -> None:
    current = validate_candidate_output_directory(guard.path, repo_root)
    if (current.device, current.inode) != (guard.device, guard.inode):
        raise ValueError("review output directory identity changed")


def _open_guarded_output_directory(guard: OutputDirectoryGuard) -> int:
    flags = os.O_RDONLY
    flags |= getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(guard.path, flags)
    except OSError:
        raise ValueError("review output directory cannot be safely opened") from None
    opened = os.fstat(descriptor)
    if (opened.st_dev, opened.st_ino) == (guard.device, guard.inode):
        return descriptor
    os.close(descriptor)
    raise ValueError("review output directory identity changed")


def _open_directory_at(parent_descriptor: int, name: str) -> int:
    flags = os.O_RDONLY
    flags |= getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    return os.open(name, flags, dir_fd=parent_descriptor)


def _ensure_relative_name_absent(directory_descriptor: int, name: str) -> None:
    try:
        os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return
    raise FileExistsError(name)


def _create_temporary_directory_at(directory_descriptor: int) -> str:
    for _ in range(100):
        name = f".spec-dock-planning-review-{secrets.token_hex(16)}"
        try:
            os.mkdir(name, mode=0o700, dir_fd=directory_descriptor)
        except FileExistsError:
            continue
        return name
    raise FileExistsError("review staging directory collision")


def _atomic_publish_no_replace_at(
    directory_descriptor: int,
    source: _OwnedReviewDirectory,
    destination_name: str,
    *,
    expected_files: dict[str, bytes],
) -> None:
    if not _owned_review_directory_matches(directory_descriptor, source):
        raise ValueError("review staging directory identity changed")
    _verify_review_directory_contents(source, expected_files)
    _rename_no_replace_at(directory_descriptor, source.name, destination_name)
    source.name = destination_name
    if not _owned_review_directory_matches(directory_descriptor, source):
        raise ValueError("review published directory identity changed")
    _verify_review_directory_contents(source, expected_files)


def _rename_no_replace_at(
    directory_descriptor: int,
    source_name: str,
    destination_name: str,
) -> None:
    if platform.system() == "Darwin":
        library = ctypes.CDLL(None, use_errno=True)
        rename = getattr(library, "renameatx_np", None)
        if rename is None:
            raise NotImplementedError("renameatx_np is unavailable")
        flag = 0x00000004
    elif platform.system() == "Linux":
        library = ctypes.CDLL(None, use_errno=True)
        rename = getattr(library, "renameat2", None)
        if rename is None:
            raise NotImplementedError("renameat2 is unavailable")
        flag = 0x00000001
    else:
        raise NotImplementedError("atomic no-replace rename is unsupported")
    rename.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    rename.restype = ctypes.c_int
    result = rename(
        directory_descriptor,
        os.fsencode(source_name),
        directory_descriptor,
        os.fsencode(destination_name),
        flag,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number in (errno.EEXIST, errno.ENOTEMPTY):
        raise FileExistsError(error_number, os.strerror(error_number), destination_name)
    raise OSError(error_number, os.strerror(error_number), destination_name)


def _remove_evidence_directory_at(
    directory_descriptor: int,
    evidence: _OwnedReviewDirectory,
) -> bool:
    """Report that cleanup is unavailable without deleting any pathname.

    POSIX pathname removal does not provide an expected-device/inode
    precondition.  A prior identity check followed by ``unlink`` or ``rmdir``
    would therefore be a destructive TOCTOU window.  The publication caller
    treats ``False`` as an ambiguous cleanup and returns the content-free
    blocked result while preserving the published evidence for inspection.
    """

    del directory_descriptor, evidence
    return False


def _owned_review_directory_matches(
    parent_descriptor: int,
    entry: _OwnedReviewDirectory,
) -> bool:
    try:
        opened = os.fstat(entry.descriptor)
        current = os.stat(entry.name, dir_fd=parent_descriptor, follow_symlinks=False)
    except OSError:
        return False
    return (
        stat.S_ISDIR(opened.st_mode)
        and stat.S_ISDIR(current.st_mode)
        and (opened.st_dev, opened.st_ino) == (entry.device, entry.inode)
        and (current.st_dev, current.st_ino) == (entry.device, entry.inode)
    )


def _verify_review_directory_contents(
    directory: _OwnedReviewDirectory,
    expected_files: dict[str, bytes],
) -> None:
    names = tuple(sorted(os.listdir(directory.descriptor)))  # noqa: PTH208 - directory fd is the guard
    if names != tuple(sorted(expected_files)):
        raise ValueError("review staging directory contents changed")
    identities: dict[str, tuple[int, int]] = {}
    for name, expected in expected_files.items():
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory.descriptor,
        )
        try:
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode):
                raise ValueError("review staging file is unsafe")
            identities[name] = (opened.st_dev, opened.st_ino)
        finally:
            os.close(descriptor)
        actual = _read_exact_file_at(directory.descriptor, name, max_bytes=len(expected))
        if actual != expected:
            raise ValueError("review staging file contents changed")
    if directory.file_identities and directory.file_identities != identities:
        raise ValueError("review staging file identity changed")
    directory.file_identities = identities


def _read_exact_file_at(directory_descriptor: int, name: str, *, max_bytes: int) -> bytes:
    flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(name, flags, dir_fd=directory_descriptor)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or opened.st_size > max_bytes:
            raise ValueError("review staging file is unsafe")
        os.lseek(descriptor, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(64 * 1024, max_bytes + 1 - total))
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise ValueError("review staging file exceeds the bounded size")
    finally:
        os.close(descriptor)
