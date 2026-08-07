from __future__ import annotations

from contextlib import suppress
import ctypes
from dataclasses import dataclass
import errno
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import platform
import secrets
import stat
import tempfile
from types import MappingProxyType
from typing import TYPE_CHECKING, BinaryIO
import zipfile

from spec_dock_runtime.domain.authoring_pack.zip_contract import (
    PackReviewResult,
    issue_authoring_v1_profile,
    issue_candidate_v1_profile,
    review_pack_input,
)
from spec_dock_runtime.domain.issue_planning_candidate import (
    DOCUMENT_NAMES,
    CandidateMaterial,
    ValidatedIssueAuthoringPayload,
    candidate_paths,
    derive_candidate_identity,
    parse_canonical_control_json,
    validate_issue_authoring_files,
    validate_onboarding_companion_path,
    verify_issue_candidate_files,
)
from spec_dock_runtime.domain.issue_planning_contracts import (
    IssueCandidateIdentity,
    OnboardingCompanionBindingV1,
    OracleAuthoringZipSnapshot,
    PlanningPublicationSourceStale,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from datetime import datetime


class CandidateOutputRejected(ValueError):
    pass


class CandidateCollision(FileExistsError):
    pass


class CandidateArchiveRejected(ValueError):
    def __init__(self, findings: tuple[str, ...]) -> None:
        super().__init__("Issue Candidate archive validation failed")
        self.findings = findings


class CandidateBuildFailed(OSError):
    pass


class CandidatePublicationFailed(OSError):
    pass


class CandidateSourceStale(PlanningPublicationSourceStale):
    pass


MAX_CANDIDATE_ARCHIVE_BYTES = 16_000_000


@dataclass(frozen=True)
class OutputDirectoryGuard:
    path: Path
    device: int
    inode: int


@dataclass(frozen=True)
class _OwnedEntry:
    name: str
    descriptor: int
    device: int
    inode: int


@dataclass(frozen=True)
class PublishedCandidate:
    identity: IssueCandidateIdentity
    zip_byte_count: int
    candidate_path: Path
    onboarding_companion: OnboardingCompanionBindingV1


@dataclass(frozen=True)
class VerifiedIssueCandidate:
    identity: IssueCandidateIdentity
    files: Mapping[str, bytes]
    source_baseline: Mapping[str, object]
    zip_bytes: bytes
    onboarding_companion: OnboardingCompanionBindingV1


def validate_candidate_output_directory(output_dir: Path, repo_root: Path) -> OutputDirectoryGuard:
    lexical = output_dir.absolute()
    if not lexical.exists() or not lexical.is_dir():
        raise CandidateOutputRejected("candidate output must be an existing directory")
    if _has_symlink_component(lexical):
        raise CandidateOutputRejected("candidate output path must not contain symlinks")
    try:
        output = lexical.resolve(strict=True)
        repository = repo_root.resolve(strict=True)
    except OSError as error:
        raise CandidateOutputRejected("candidate output or repository cannot be resolved") from error
    if output == repository or output.is_relative_to(repository) or repository.is_relative_to(output):
        raise CandidateOutputRejected("candidate output must be external to the repository")
    flags = os.O_RDONLY
    flags |= getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(output, flags)
    except OSError as error:
        raise CandidateOutputRejected("candidate output cannot be safely opened") from error
    try:
        opened = os.fstat(descriptor)
        current = output.stat(follow_symlinks=False)
        if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
            raise CandidateOutputRejected("candidate output identity changed")
    finally:
        os.close(descriptor)
    return OutputDirectoryGuard(path=output, device=current.st_dev, inode=current.st_ino)


def load_verified_issue_candidate(candidate_path: Path, repo_root: Path) -> VerifiedIssueCandidate:
    lexical = candidate_path.absolute()
    if not lexical.exists() or not lexical.is_file() or _has_symlink_component(lexical) or lexical.suffix != ".zip":
        raise CandidateArchiveRejected(("unsafe_candidate_path",))
    try:
        candidate = lexical.resolve(strict=True)
        repository = repo_root.resolve(strict=True)
    except OSError as error:
        raise CandidateArchiveRejected(("unsafe_candidate_path",)) from error
    if candidate == repository or candidate.is_relative_to(repository):
        raise CandidateArchiveRejected(("unsafe_candidate_path",))
    try:
        zip_bytes = _read_candidate_snapshot(candidate)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            names = tuple(info.filename for info in archive.infolist())
    except (OSError, zipfile.BadZipFile) as error:
        raise CandidateArchiveRejected(("archive_unreadable",)) from error
    roots = {name.partition("/")[0] for name in names if "/" in name and name.partition("/")[0]}
    if len(roots) != 1:
        raise CandidateArchiveRejected(("root_mismatch",))
    internal_root = next(iter(roots))
    prefix = f"{internal_root}/"
    relative_names = {name[len(prefix) :] for name in names if name.startswith(prefix) and not name.endswith("/")}
    possible_companions = relative_names - {
        "CHECKSUMS.sha256",
        "MANIFEST.json",
        "PLACEHOLDER-ORACLE-MAP.json",
        "SOURCE-BASELINE.json",
        *DOCUMENT_NAMES,
    }
    if len(possible_companions) != 1:
        raise CandidateArchiveRejected(("companion_role_mismatch",))
    companion_path = next(iter(possible_companions))
    try:
        validate_onboarding_companion_path(companion_path)
    except ValueError as error:
        raise CandidateArchiveRejected(("companion_path_mismatch",)) from error
    review = _review_candidate_snapshot(
        zip_bytes,
        repo_root=repository,
        internal_root=internal_root,
        companion_path=companion_path,
    )
    if review.status != "pass":
        raise CandidateArchiveRejected(review.findings)
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            files = {
                relative: archive.read(f"{internal_root}/{relative}") for relative in candidate_paths(companion_path)
            }
        manifest = parse_canonical_control_json(files["MANIFEST.json"])
        source = parse_canonical_control_json(files["SOURCE-BASELINE.json"])
        candidate_control = manifest["candidate"]
        if not isinstance(candidate_control, dict):
            raise ValueError("Candidate manifest identity is invalid")
        identity = IssueCandidateIdentity(
            issue_id=candidate_control["issue_id"],
            candidate_id=candidate_control["candidate_id"],
            version=candidate_control["version"],
            logical_filename=candidate_control["logical_filename"],
            observed_transport_filename=candidate.name,
            internal_root=candidate_control["internal_root"],
            source_repository=source["source_repository"],
            source_branch=source["source_branch"],
            source_head=source["source_head"],
            zip_sha256=hashlib.sha256(zip_bytes).hexdigest(),
        )
        companion = OnboardingCompanionBindingV1(
            path=companion_path,
            sha256=hashlib.sha256(files[companion_path]).hexdigest(),
        )
    except (KeyError, OSError, TypeError, ValueError, zipfile.BadZipFile) as error:
        raise CandidateArchiveRejected(("candidate_identity_mismatch",)) from error
    return VerifiedIssueCandidate(
        identity=identity,
        files=MappingProxyType(files),
        source_baseline=MappingProxyType(source),
        zip_bytes=zip_bytes,
        onboarding_companion=companion,
    )


def load_validated_issue_authoring_payload(
    snapshot: OracleAuthoringZipSnapshot,
    *,
    expected_companion_path: str,
    repo_root: Path,
) -> ValidatedIssueAuthoringPayload:
    expected_root = snapshot.expected_logical_filename.removesuffix(".zip")
    if snapshot.internal_root != expected_root:
        raise CandidateArchiveRejected(("root_mismatch",))
    try:
        validate_onboarding_companion_path(expected_companion_path)
        repository = repo_root.resolve(strict=True)
    except (OSError, ValueError) as error:
        raise CandidateArchiveRejected(("authoring_identity_mismatch",)) from error
    temporary_root = Path(tempfile.gettempdir()).resolve(strict=True)
    if temporary_root == repository or temporary_root.is_relative_to(repository):
        raise CandidateArchiveRejected(("unsafe_candidate_path",))
    with tempfile.TemporaryDirectory(
        prefix="specdock-authoring-snapshot-",
        dir=temporary_root,
    ) as raw:
        archive_path = Path(raw) / snapshot.expected_logical_filename
        with archive_path.open("xb") as stream:
            stream.write(snapshot.zip_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        review = review_pack_input(
            archive_path,
            profile=issue_authoring_v1_profile(
                expected_root=expected_root,
                expected_companion_path=expected_companion_path,
                cross_file_validator=lambda files, root: validate_issue_authoring_files(
                    files,
                    root,
                    expected_companion_path=expected_companion_path,
                ),
            ),
        )
    if review.status != "pass":
        raise CandidateArchiveRejected(review.findings)
    try:
        with zipfile.ZipFile(io.BytesIO(snapshot.zip_bytes)) as archive:
            payloads = {
                path: archive.read(f"{expected_root}/{path}") for path in (*DOCUMENT_NAMES, expected_companion_path)
            }
        return ValidatedIssueAuthoringPayload(
            expected_logical_filename=snapshot.expected_logical_filename,
            observed_transport_filename=snapshot.observed_transport_filename,
            internal_root=snapshot.internal_root,
            zip_sha256=snapshot.sha256,
            zip_size_bytes=snapshot.size_bytes,
            documents=MappingProxyType({name: payloads[name] for name in DOCUMENT_NAMES}),
            onboarding_companion_path=expected_companion_path,
            onboarding_companion_bytes=payloads[expected_companion_path],
        )
    except (KeyError, OSError, ValueError, zipfile.BadZipFile) as error:
        raise CandidateArchiveRejected(("archive_unreadable",)) from error


def _read_candidate_snapshot(candidate: Path) -> bytes:
    try:
        return read_bounded_regular_file(candidate, max_bytes=MAX_CANDIDATE_ARCHIVE_BYTES)
    except (OSError, ValueError) as error:
        raise CandidateArchiveRejected(("archive_unreadable",)) from error


def open_safe_directory_descriptor(path: Path) -> int:
    absolute = path.absolute()
    if not absolute.is_absolute() or any(part in ("", ".", "..") for part in absolute.parts[1:]):
        raise ValueError("directory traversal rejected")
    flags = os.O_RDONLY
    flags |= getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(absolute.anchor, flags)
        for part in absolute.parts[1:]:
            next_descriptor = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except OSError:
        if descriptor >= 0:
            with suppress(OSError):
                os.close(descriptor)
        raise ValueError("directory traversal rejected") from None


def read_bounded_regular_file(path: Path, *, max_bytes: int) -> bytes:
    parent_descriptor = open_safe_directory_descriptor(path.parent)
    try:
        return read_bounded_regular_file_at(
            parent_descriptor,
            path.name,
            max_bytes=max_bytes,
        )
    finally:
        os.close(parent_descriptor)


def read_bounded_regular_file_at(
    root_descriptor: int,
    relative_path: str,
    *,
    max_bytes: int,
) -> bytes:
    relative = PurePosixPath(relative_path)
    if relative.is_absolute() or any(part in ("", ".", "..") for part in relative.parts):
        raise ValueError("file traversal rejected")
    directory_descriptor = os.dup(root_descriptor)
    directory_flags = os.O_RDONLY
    directory_flags |= getattr(os, "O_DIRECTORY", 0)
    directory_flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        for part in relative.parts[:-1]:
            next_descriptor = os.open(
                part,
                directory_flags,
                dir_fd=directory_descriptor,
            )
            os.close(directory_descriptor)
            directory_descriptor = next_descriptor
        file_flags = os.O_RDONLY
        file_flags |= getattr(os, "O_NOFOLLOW", 0)
        file_flags |= getattr(os, "O_NONBLOCK", 0)
        descriptor = os.open(
            relative.parts[-1],
            file_flags,
            dir_fd=directory_descriptor,
        )
    except OSError:
        raise ValueError("file traversal rejected") from None
    finally:
        os.close(directory_descriptor)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise ValueError("file traversal rejected")
        if opened.st_size > max_bytes:
            raise ValueError("file exceeds bounded size")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise ValueError("file exceeds bounded size")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _review_candidate_snapshot(
    zip_bytes: bytes,
    *,
    repo_root: Path,
    internal_root: str,
    companion_path: str,
) -> PackReviewResult:
    temporary_root = Path(tempfile.gettempdir()).resolve(strict=True)
    if temporary_root == repo_root or temporary_root.is_relative_to(repo_root):
        raise CandidateArchiveRejected(("unsafe_candidate_path",))
    with tempfile.TemporaryDirectory(prefix="specdock-candidate-snapshot-", dir=temporary_root) as raw:
        snapshot = Path(raw) / "candidate.zip"
        with snapshot.open("xb") as stream:
            stream.write(zip_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        return review_pack_input(
            snapshot,
            profile=issue_candidate_v1_profile(
                expected_root=internal_root,
                expected_companion_path=companion_path,
                cross_file_validator=verify_issue_candidate_files,
            ),
        )


def build_deterministic_zip(
    destination: Path,
    internal_root: str,
    files: Mapping[str, bytes],
    operation_time: datetime,
) -> None:
    with destination.open("wb") as stream:
        _write_deterministic_zip(
            stream,
            internal_root,
            files,
            operation_time,
        )


def _write_deterministic_zip(
    destination: BinaryIO,
    internal_root: str,
    files: Mapping[str, bytes],
    operation_time: datetime,
) -> None:
    date_time = (
        operation_time.year,
        operation_time.month,
        operation_time.day,
        operation_time.hour,
        operation_time.minute,
        operation_time.second,
    )
    with zipfile.ZipFile(
        destination,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=True,
    ) as archive:
        archive.comment = b""
        for relative_path in sorted(files, key=lambda value: value.encode("utf-8")):
            info = zipfile.ZipInfo(f"{internal_root}/{relative_path}", date_time=date_time)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.extra = b""
            info.comment = b""
            archive.writestr(info, files[relative_path], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def atomic_publish_no_replace(source: Path, destination: Path) -> None:
    if platform.system() == "Darwin":
        _rename_exclusive_darwin(source, destination)
        return
    if platform.system() == "Linux":
        _rename_exclusive_linux(source, destination)
        return
    raise NotImplementedError("atomic no-replace publication is unsupported")


def build_and_publish_candidate(
    *,
    output_guard: OutputDirectoryGuard,
    repo_root: Path,
    material: CandidateMaterial,
    publication_guard: Callable[[], bool],
) -> PublishedCandidate:
    final_path = output_guard.path / material.logical_filename
    output_descriptor = -1
    staged: _OwnedEntry | None = None
    published_entry: _OwnedEntry | None = None
    published = False
    try:
        output_descriptor = _open_guarded_output_directory(output_guard)
        if _entry_exists_at(output_descriptor, material.logical_filename):
            raise CandidateCollision(material.logical_filename)
        staged = _create_private_staged_file(output_descriptor)
        try:
            with os.fdopen(os.dup(staged.descriptor), "w+b") as stream:
                _write_deterministic_zip(
                    stream,
                    material.internal_root,
                    material.files,
                    material.operation_time,
                )
                stream.flush()
                os.fsync(stream.fileno())
            zip_bytes = _read_regular_file_descriptor(
                staged.descriptor,
                max_bytes=MAX_CANDIDATE_ARCHIVE_BYTES,
            )
        except OSError as error:
            raise CandidateBuildFailed("Candidate ZIP construction failed") from error
        review = _review_candidate_snapshot(
            zip_bytes,
            repo_root=repo_root,
            internal_root=material.internal_root,
            companion_path=material.onboarding_companion_path,
        )
        if review.status != "pass":
            raise CandidateArchiveRejected(review.findings)
        identity = derive_candidate_identity(
            material,
            zip_bytes,
            observed_transport_filename=material.logical_filename,
        )
        if not _owned_entry_matches(
            output_descriptor,
            staged,
            expected_kind="file",
        ):
            raise CandidatePublicationFailed("Candidate publication failed")
        try:
            published_entry = _publish_verified_fd_no_replace_at(
                staged.descriptor,
                output_descriptor,
                material.logical_filename,
            )
            published_bytes = _read_regular_file_descriptor(
                published_entry.descriptor,
                max_bytes=len(zip_bytes),
            )
            if (
                len(published_bytes) != len(zip_bytes)
                or hashlib.sha256(published_bytes).hexdigest() != identity.zip_sha256
            ):
                raise OSError(errno.EIO, "Published Candidate identity mismatch")
            if _owned_entry_matches(
                output_descriptor,
                staged,
                expected_kind="file",
            ):
                os.unlink(staged.name, dir_fd=output_descriptor)
            os.fsync(output_descriptor)
            _verify_published_candidate_attachment(
                output_guard,
                output_descriptor,
                published_entry,
            )
            try:
                current = publication_guard()
            except Exception as error:
                raise CandidatePublicationFailed("Candidate publication failed") from error
            if not current:
                if _cleanup_rejected_published_candidate(output_descriptor, published_entry):
                    raise CandidateSourceStale("Candidate source changed during publication")
                raise CandidatePublicationFailed("Candidate publication failed")
        except FileExistsError as error:
            raise CandidateCollision(material.logical_filename) from error
        except (NotImplementedError, OSError) as error:
            raise CandidatePublicationFailed("Candidate publication failed") from error
        published = True
        companion = OnboardingCompanionBindingV1(
            path=material.onboarding_companion_path,
            sha256=hashlib.sha256(material.files[material.onboarding_companion_path]).hexdigest(),
        )
        return PublishedCandidate(
            identity=identity,
            zip_byte_count=len(zip_bytes),
            candidate_path=final_path,
            onboarding_companion=companion,
        )
    finally:
        if published_entry is not None:
            if not published:
                with suppress(OSError, NotImplementedError):
                    _cleanup_rejected_published_candidate(
                        output_descriptor,
                        published_entry,
                    )
            with suppress(OSError):
                os.close(published_entry.descriptor)
        if staged is not None:
            if _owned_entry_matches(
                output_descriptor,
                staged,
                expected_kind="file",
            ):
                with suppress(OSError):
                    os.unlink(staged.name, dir_fd=output_descriptor)
            with suppress(OSError):
                os.close(staged.descriptor)
        if output_descriptor >= 0:
            with suppress(OSError):
                os.close(output_descriptor)


def _open_guarded_output_directory(guard: OutputDirectoryGuard) -> int:
    try:
        descriptor = open_safe_directory_descriptor(guard.path)
    except ValueError as error:
        raise CandidateOutputRejected("candidate output cannot be safely opened") from error
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISDIR(opened.st_mode) or (opened.st_dev, opened.st_ino) != (guard.device, guard.inode):
            raise CandidateOutputRejected("candidate output identity changed")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _verify_published_candidate_attachment(
    guard: OutputDirectoryGuard,
    output_descriptor: int,
    published_entry: _OwnedEntry,
) -> None:
    try:
        captured = os.fstat(output_descriptor)
    except OSError as error:
        raise CandidateOutputRejected("candidate output cannot be safely inspected") from error
    if not stat.S_ISDIR(captured.st_mode) or (captured.st_dev, captured.st_ino) != (guard.device, guard.inode):
        raise CandidateOutputRejected("candidate output identity changed")
    visible_descriptor = _open_guarded_output_directory(guard)
    try:
        if not _owned_entry_matches(
            output_descriptor,
            published_entry,
            expected_kind="file",
        ) or not _entry_matches_identity(
            visible_descriptor,
            published_entry.name,
            device=published_entry.device,
            inode=published_entry.inode,
            expected_kind="file",
        ):
            raise CandidateOutputRejected("candidate output identity changed")
    finally:
        os.close(visible_descriptor)


def _entry_exists_at(directory_descriptor: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=directory_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError as error:
        raise CandidateOutputRejected("candidate output cannot be safely inspected") from error
    return True


def _create_private_staged_file(output_descriptor: int) -> _OwnedEntry:
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    for _attempt in range(32):
        name = f".spec-dock-issue-candidate-{secrets.token_hex(16)}.zip"
        descriptor = -1
        try:
            descriptor = os.open(
                name,
                flags,
                0o600,
                dir_fd=output_descriptor,
            )
        except FileExistsError:
            continue
        except OSError as error:
            raise CandidateBuildFailed("Candidate ZIP construction failed") from error
        try:
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode):
                raise OSError(errno.EINVAL, "Candidate staged entry is not a regular file")
            return _OwnedEntry(
                name=name,
                descriptor=descriptor,
                device=opened.st_dev,
                inode=opened.st_ino,
            )
        except OSError as error:
            if descriptor >= 0:
                with suppress(OSError):
                    os.close(descriptor)
            raise CandidateBuildFailed("Candidate ZIP construction failed") from error
    raise CandidateBuildFailed("Candidate ZIP construction failed")


def _create_private_cleanup_directory(output_descriptor: int) -> _OwnedEntry:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    output_identity = os.fstat(output_descriptor)
    for _attempt in range(32):
        name = f".spec-dock-issue-candidate-cleanup-{secrets.token_hex(16)}"
        descriptor = -1
        try:
            os.mkdir(name, 0o700, dir_fd=output_descriptor)
            descriptor = os.open(name, flags, dir_fd=output_descriptor)
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISDIR(opened.st_mode)
                or stat.S_IMODE(opened.st_mode) != 0o700
                or opened.st_uid != os.geteuid()
                or opened.st_dev != output_identity.st_dev
                or not _entry_matches_identity(
                    output_descriptor,
                    name,
                    device=opened.st_dev,
                    inode=opened.st_ino,
                    expected_kind="directory",
                )
            ):
                raise OSError(errno.EINVAL, "Candidate cleanup directory is unsafe")
            return _OwnedEntry(
                name=name,
                descriptor=descriptor,
                device=opened.st_dev,
                inode=opened.st_ino,
            )
        except FileExistsError:
            continue
        except BaseException:
            if descriptor >= 0:
                with suppress(OSError):
                    os.close(descriptor)
            with suppress(OSError):
                os.rmdir(name, dir_fd=output_descriptor)
            raise
    raise OSError(errno.EEXIST, "Candidate cleanup directory collision")


def _cleanup_rejected_published_candidate(
    output_descriptor: int,
    published_entry: _OwnedEntry,
) -> bool:
    if not _owned_entry_matches(
        output_descriptor,
        published_entry,
        expected_kind="file",
    ):
        return False
    cleanup = _create_private_cleanup_directory(output_descriptor)
    retain_cleanup = False
    try:
        try:
            _rename_exclusive_at(
                output_descriptor,
                published_entry.name,
                cleanup.descriptor,
                published_entry.name,
            )
        except (FileNotFoundError, FileExistsError, NotImplementedError, OSError):
            return False
        os.fsync(output_descriptor)
        os.fsync(cleanup.descriptor)
        if _owned_entry_matches(
            cleanup.descriptor,
            published_entry,
            expected_kind="file",
        ):
            os.unlink(published_entry.name, dir_fd=cleanup.descriptor)
            os.fsync(cleanup.descriptor)
            os.fsync(output_descriptor)
            return True
        try:
            _rename_exclusive_at(
                cleanup.descriptor,
                published_entry.name,
                output_descriptor,
                published_entry.name,
            )
            os.fsync(cleanup.descriptor)
            os.fsync(output_descriptor)
        except (FileExistsError, NotImplementedError, OSError):
            retain_cleanup = True
    finally:
        with suppress(OSError):
            os.close(cleanup.descriptor)
        if not retain_cleanup and _entry_matches_identity(
            output_descriptor,
            cleanup.name,
            device=cleanup.device,
            inode=cleanup.inode,
            expected_kind="directory",
        ):
            with suppress(OSError):
                os.rmdir(cleanup.name, dir_fd=output_descriptor)
                os.fsync(output_descriptor)
    return False


def _open_owned_regular_file(parent_descriptor: int, name: str) -> _OwnedEntry:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(name, flags, dir_fd=parent_descriptor)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise OSError(errno.EINVAL, "Published Candidate is not a regular file")
        return _OwnedEntry(
            name=name,
            descriptor=descriptor,
            device=opened.st_dev,
            inode=opened.st_ino,
        )
    except BaseException:
        os.close(descriptor)
        raise


def _owned_entry_matches(
    parent_descriptor: int,
    entry: _OwnedEntry,
    *,
    expected_kind: str,
) -> bool:
    try:
        opened = os.fstat(entry.descriptor)
    except OSError:
        return False
    if (opened.st_dev, opened.st_ino) != (entry.device, entry.inode):
        return False
    if expected_kind == "directory" and not stat.S_ISDIR(opened.st_mode):
        return False
    if expected_kind == "file" and not stat.S_ISREG(opened.st_mode):
        return False
    return _entry_matches_identity(
        parent_descriptor,
        entry.name,
        device=entry.device,
        inode=entry.inode,
        expected_kind=expected_kind,
    )


def _entry_matches_identity(
    parent_descriptor: int,
    name: str,
    *,
    device: int,
    inode: int,
    expected_kind: str,
) -> bool:
    try:
        current = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
    except OSError:
        return False
    if (current.st_dev, current.st_ino) != (device, inode):
        return False
    if expected_kind == "directory":
        return stat.S_ISDIR(current.st_mode)
    if expected_kind == "file":
        return stat.S_ISREG(current.st_mode)
    return False


def _read_regular_file_descriptor(descriptor: int, *, max_bytes: int) -> bytes:
    opened = os.fstat(descriptor)
    if not stat.S_ISREG(opened.st_mode) or opened.st_size > max_bytes:
        raise OSError(errno.EFBIG, "Candidate ZIP exceeds bounded size")
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(descriptor, min(1024 * 1024, max_bytes + 1 - total))
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        total += len(chunk)
        if total > max_bytes:
            raise OSError(errno.EFBIG, "Candidate ZIP exceeds bounded size")


def _publish_verified_fd_no_replace_at(
    staged_descriptor: int,
    destination_descriptor: int,
    destination_name: str,
) -> _OwnedEntry:
    if platform.system() == "Darwin":
        return _publish_clone_bound_darwin_at(
            staged_descriptor,
            destination_descriptor,
            destination_name,
        )
    if platform.system() == "Linux":
        bound_descriptor = os.dup(staged_descriptor)
        try:
            opened = os.fstat(bound_descriptor)
            if not stat.S_ISREG(opened.st_mode):
                raise OSError(errno.EINVAL, "Candidate staged entry is not a regular file")
            bound_entry = _OwnedEntry(
                name=destination_name,
                descriptor=bound_descriptor,
                device=opened.st_dev,
                inode=opened.st_ino,
            )
            _link_exclusive_linux_at(
                staged_descriptor,
                destination_descriptor,
                destination_name,
            )
            return bound_entry
        except BaseException:
            os.close(bound_descriptor)
            raise
    raise NotImplementedError("atomic no-replace publication is unsupported")


def _publish_clone_bound_darwin_at(
    staged_descriptor: int,
    destination_descriptor: int,
    destination_name: str,
) -> _OwnedEntry:
    for _attempt in range(32):
        capture_name = f".spec-dock-issue-candidate-capture-{secrets.token_bytes(16).hex()}.zip"
        try:
            _clone_exclusive_darwin_at(
                staged_descriptor,
                destination_descriptor,
                capture_name,
            )
        except FileExistsError:
            continue
        captured: _OwnedEntry | None = None
        try:
            captured = _open_owned_regular_file(
                destination_descriptor,
                capture_name,
            )
            bound_entry = _OwnedEntry(
                name=destination_name,
                descriptor=captured.descriptor,
                device=captured.device,
                inode=captured.inode,
            )
            _rename_exclusive_darwin_at(
                destination_descriptor,
                capture_name,
                destination_descriptor,
                destination_name,
            )
            return bound_entry
        except BaseException:
            if captured is not None:
                if _owned_entry_matches(
                    destination_descriptor,
                    captured,
                    expected_kind="file",
                ):
                    with suppress(OSError):
                        os.unlink(capture_name, dir_fd=destination_descriptor)
                        os.fsync(destination_descriptor)
                with suppress(OSError):
                    os.close(captured.descriptor)
            raise
    raise FileExistsError(errno.EEXIST, "Candidate capture name collision", destination_name)


def _rename_exclusive_at(
    source_descriptor: int,
    source_name: str,
    destination_descriptor: int,
    destination_name: str,
) -> None:
    if platform.system() == "Darwin":
        _rename_exclusive_darwin_at(
            source_descriptor,
            source_name,
            destination_descriptor,
            destination_name,
        )
        return
    if platform.system() == "Linux":
        _rename_exclusive_linux_at(
            source_descriptor,
            source_name,
            destination_descriptor,
            destination_name,
        )
        return
    raise NotImplementedError("descriptor-relative no-replace rename is unsupported")


def _has_symlink_component(path: Path) -> bool:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            return True
    return False


def _rename_exclusive_darwin(source: Path, destination: Path) -> None:
    library = ctypes.CDLL(None, use_errno=True)
    rename = getattr(library, "renamex_np", None)
    if rename is None:
        raise NotImplementedError("renamex_np is unavailable")
    rename.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    result = rename(os.fsencode(source), os.fsencode(destination), 0x00000004)
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise FileExistsError(error_number, os.strerror(error_number), destination)
    raise OSError(error_number, os.strerror(error_number), destination)


def _rename_exclusive_linux(source: Path, destination: Path) -> None:
    library = ctypes.CDLL(None, use_errno=True)
    rename = getattr(library, "renameat2", None)
    if rename is None:
        raise NotImplementedError("renameat2 is unavailable")
    rename.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    rename.restype = ctypes.c_int
    result = rename(-100, os.fsencode(source), -100, os.fsencode(destination), 0x00000001)
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise FileExistsError(error_number, os.strerror(error_number), destination)
    raise OSError(error_number, os.strerror(error_number), destination)


def _rename_exclusive_darwin_at(
    source_descriptor: int,
    source_name: str,
    destination_descriptor: int,
    destination_name: str,
) -> None:
    library = ctypes.CDLL(None, use_errno=True)
    rename = getattr(library, "renameatx_np", None)
    if rename is None:
        raise NotImplementedError("renameatx_np is unavailable")
    rename.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    rename.restype = ctypes.c_int
    result = rename(
        source_descriptor,
        os.fsencode(source_name),
        destination_descriptor,
        os.fsencode(destination_name),
        0x00000004,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise FileExistsError(error_number, os.strerror(error_number), destination_name)
    raise OSError(error_number, os.strerror(error_number), destination_name)


def _rename_exclusive_linux_at(
    source_descriptor: int,
    source_name: str,
    destination_descriptor: int,
    destination_name: str,
) -> None:
    library = ctypes.CDLL(None, use_errno=True)
    rename = getattr(library, "renameat2", None)
    if rename is None:
        raise NotImplementedError("renameat2 is unavailable")
    rename.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    rename.restype = ctypes.c_int
    result = rename(
        source_descriptor,
        os.fsencode(source_name),
        destination_descriptor,
        os.fsencode(destination_name),
        0x00000001,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise FileExistsError(error_number, os.strerror(error_number), destination_name)
    raise OSError(error_number, os.strerror(error_number), destination_name)


def _clone_exclusive_darwin_at(
    staged_descriptor: int,
    destination_descriptor: int,
    destination_name: str,
) -> None:
    library = ctypes.CDLL(None, use_errno=True)
    clone = getattr(library, "fclonefileat", None)
    if clone is None:
        raise NotImplementedError("fclonefileat is unavailable")
    clone.argtypes = (
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    clone.restype = ctypes.c_int
    result = clone(
        staged_descriptor,
        destination_descriptor,
        os.fsencode(destination_name),
        0,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise FileExistsError(error_number, os.strerror(error_number), destination_name)
    raise OSError(error_number, os.strerror(error_number), destination_name)


def _link_exclusive_linux_at(
    staged_descriptor: int,
    destination_descriptor: int,
    destination_name: str,
) -> None:
    library = ctypes.CDLL(None, use_errno=True)
    link = getattr(library, "linkat", None)
    if link is None:
        raise NotImplementedError("linkat is unavailable")
    link.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
    )
    link.restype = ctypes.c_int
    result = link(
        -100,
        os.fsencode(f"/proc/self/fd/{staged_descriptor}"),
        destination_descriptor,
        os.fsencode(destination_name),
        0x00000400,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise FileExistsError(error_number, os.strerror(error_number), destination_name)
    raise OSError(error_number, os.strerror(error_number), destination_name)
