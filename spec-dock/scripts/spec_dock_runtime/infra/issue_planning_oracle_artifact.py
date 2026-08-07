"""Versioned, private Oracle 0.16.1 session artifact reader."""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Any
import zipfile

from spec_dock_runtime.domain.issue_planning_contracts import (
    OracleAuthoringZipSnapshot,
    OracleReviewJsonPayload,
)

SUPPORTED_ORACLE_VERSION = "0.16.1"
MAX_METADATA_BYTES = 1024 * 1024
MAX_ARTIFACTS = 32
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
MAX_ZIP_ENTRIES = 2048
MAX_ZIP_ENTRY_UNCOMPRESSED_BYTES = 16 * 1024 * 1024
MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_ZIP_COMPRESSION_RATIO = 200
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_TRANSPORT_ZIP_RE = re.compile(r"^(?P<stem>.+?)(?: \([1-9][0-9]*\))?\.zip$")
_ANSWER_MARKER = b"\n## Answer\n"
_SUPPORTED_ZIP_COMPRESSION = frozenset({
    zipfile.ZIP_STORED,
    zipfile.ZIP_DEFLATED,
    zipfile.ZIP_BZIP2,
    zipfile.ZIP_LZMA,
})


class OracleArtifactError(RuntimeError):
    """Content-free error for the direct Oracle adapter."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def read_session_status(
    session_root: Path,
    *,
    session_id: str,
    oracle_version: str,
) -> str:
    metadata = _read_metadata(session_root, session_id=session_id, oracle_version=oracle_version)
    status_value = metadata.get("status")
    if not isinstance(status_value, str) or not status_value:
        raise OracleArtifactError("oracle_artifact_rejected")
    return status_value


def snapshot_authoring_zip(
    session_root: Path,
    *,
    session_id: str,
    oracle_version: str,
    staging_dir: Path,
) -> OracleAuthoringZipSnapshot:
    metadata = _read_metadata(session_root, session_id=session_id, oracle_version=oracle_version)
    artifacts = _artifact_inventory(metadata)
    matches = [
        artifact
        for artifact in artifacts
        if artifact.get("kind") == "file"
        and isinstance(artifact.get("path"), str)
        and _TRANSPORT_ZIP_RE.fullmatch(Path(artifact["path"]).name)
    ]
    if not matches:
        raise OracleArtifactError("oracle_artifact_missing")
    if len(matches) != 1:
        raise OracleArtifactError("oracle_artifact_ambiguous")
    artifact = matches[0]
    payload = _snapshot_artifact(
        session_root,
        artifact=artifact,
        staging_dir=staging_dir,
    )
    observed = Path(str(artifact["path"])).name
    match = _TRANSPORT_ZIP_RE.fullmatch(observed)
    if match is None:
        raise OracleArtifactError("oracle_artifact_rejected")
    expected = f"{match.group('stem')}.zip"
    internal_root = _zip_internal_root(payload)
    try:
        return OracleAuthoringZipSnapshot(
            expected_logical_filename=expected,
            observed_transport_filename=observed,
            internal_root=internal_root,
            size_bytes=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
            zip_bytes=payload,
        )
    except ValueError:
        raise OracleArtifactError("oracle_artifact_rejected") from None


def snapshot_review_json(
    session_root: Path,
    *,
    session_id: str,
    oracle_version: str,
    staging_dir: Path,
) -> OracleReviewJsonPayload:
    metadata = _read_metadata(session_root, session_id=session_id, oracle_version=oracle_version)
    artifacts = _artifact_inventory(metadata)
    matches = [artifact for artifact in artifacts if artifact.get("kind") == "transcript"]
    if not matches:
        raise OracleArtifactError("oracle_artifact_missing")
    if len(matches) != 1:
        raise OracleArtifactError("oracle_artifact_ambiguous")
    transcript = _snapshot_artifact(
        session_root,
        artifact=matches[0],
        staging_dir=staging_dir,
    )
    marker_index = transcript.find(_ANSWER_MARKER)
    if marker_index < 0 or transcript.find(_ANSWER_MARKER, marker_index + 1) >= 0:
        raise OracleArtifactError("oracle_artifact_rejected")
    payload = transcript[marker_index + len(_ANSWER_MARKER) :].strip()
    if not payload:
        raise OracleArtifactError("oracle_artifact_rejected")
    try:
        _strict_json_object(payload)
        return OracleReviewJsonPayload(
            size_bytes=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
            json_bytes=payload,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError):
        raise OracleArtifactError("oracle_artifact_rejected") from None


def has_exact_repository_access_failure(
    session_root: Path,
    *,
    session_id: str,
    oracle_version: str,
    staging_dir: Path,
) -> bool:
    """Recognize only the exact terminal connector-failure sentinel."""
    metadata = _read_metadata(session_root, session_id=session_id, oracle_version=oracle_version)
    artifacts = _artifact_inventory(metadata)
    transcripts = [item for item in artifacts if item.get("kind") == "transcript"]
    has_file_artifact = any(item.get("kind") == "file" for item in artifacts)
    if len(transcripts) != 1:
        if transcripts and has_file_artifact:
            raise OracleArtifactError("oracle_artifact_rejected")
        return False
    transcript = _snapshot_artifact(
        session_root,
        artifact=transcripts[0],
        staging_dir=staging_dir,
    )
    marker_index = transcript.find(_ANSWER_MARKER)
    if marker_index < 0 or transcript.find(_ANSWER_MARKER, marker_index + 1) >= 0:
        if has_file_artifact:
            raise OracleArtifactError("oracle_artifact_rejected")
        return False
    answer = transcript[marker_index + len(_ANSWER_MARKER) :].strip()
    if answer == b"repository access failed":
        if has_file_artifact:
            raise OracleArtifactError("oracle_artifact_rejected")
        return True
    if b"repository access failed" in answer and has_file_artifact:
        raise OracleArtifactError("oracle_artifact_rejected")
    return False


def _read_metadata(
    session_root: Path,
    *,
    session_id: str,
    oracle_version: str,
) -> dict[str, Any]:
    if oracle_version != SUPPORTED_ORACLE_VERSION:
        raise OracleArtifactError("oracle_artifact_rejected")
    if session_root.name != session_id:
        raise OracleArtifactError("oracle_artifact_rejected")
    raw = _read_session_regular_file(
        session_root,
        relative_parts=("meta.json",),
        limit=MAX_METADATA_BYTES,
        missing_code="oracle_session_missing",
    )
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError):
        raise OracleArtifactError("oracle_artifact_rejected") from None
    if not isinstance(value, dict) or value.get("id") != session_id:
        raise OracleArtifactError("oracle_artifact_rejected")
    if value.get("mode") != "browser":
        raise OracleArtifactError("oracle_artifact_rejected")
    return value


def _artifact_inventory(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    value = metadata.get("artifacts")
    if not isinstance(value, list) or len(value) > MAX_ARTIFACTS:
        raise OracleArtifactError("oracle_artifact_rejected")
    if not all(isinstance(item, dict) for item in value):
        raise OracleArtifactError("oracle_artifact_rejected")
    return value


def _snapshot_artifact(
    session_root: Path,
    *,
    artifact: dict[str, Any],
    staging_dir: Path,
) -> bytes:
    raw_path = artifact.get("path")
    size_bytes = artifact.get("sizeBytes")
    expected_sha = artifact.get("sha256")
    validation = artifact.get("validation")
    if (
        not isinstance(raw_path, str)
        or not isinstance(size_bytes, int)
        or isinstance(size_bytes, bool)
        or size_bytes <= 0
        or size_bytes > MAX_ARTIFACT_BYTES
        or not isinstance(expected_sha, str)
        or not _SHA256_RE.fullmatch(expected_sha)
        or not isinstance(validation, dict)
        or validation.get("ok") is not True
    ):
        raise OracleArtifactError("oracle_artifact_rejected")
    relative_parts = _contained_relative_parts(session_root, raw_path)
    staging_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    staged = staging_dir / "oracle-artifact.snapshot"
    if staged.exists() or staged.is_symlink():
        raise OracleArtifactError("oracle_artifact_rejected")
    source_fd = _open_session_regular_file(
        session_root,
        relative_parts=relative_parts,
        missing_code="oracle_artifact_rejected",
    )
    try:
        before = os.fstat(source_fd)
        if before.st_size != size_bytes:
            raise OracleArtifactError("oracle_artifact_rejected")
        payload = _read_fd_bounded(source_fd, MAX_ARTIFACT_BYTES)
        after = os.fstat(source_fd)
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise OracleArtifactError("oracle_artifact_rejected")
    finally:
        os.close(source_fd)
    if len(payload) != size_bytes or hashlib.sha256(payload).hexdigest() != expected_sha:
        raise OracleArtifactError("oracle_artifact_rejected")
    staging_fd = os.open(staged, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        view = memoryview(payload)
        while view:
            written = os.write(staging_fd, view)
            if written <= 0:
                raise OracleArtifactError("oracle_artifact_rejected")
            view = view[written:]
        os.fsync(staging_fd)
    finally:
        os.close(staging_fd)
    copied = _read_bounded_regular_file(staged, MAX_ARTIFACT_BYTES)
    if len(copied) != size_bytes or hashlib.sha256(copied).hexdigest() != expected_sha:
        raise OracleArtifactError("oracle_artifact_rejected")
    return copied


def _contained_relative_parts(session_root: Path, raw_path: str) -> tuple[str, ...]:
    root = session_root.absolute()
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.absolute()
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        raise OracleArtifactError("oracle_artifact_rejected") from None
    relative_parts = PurePosixPath(relative.as_posix()).parts
    if not relative_parts or any(part in ("", ".", "..") for part in relative_parts):
        raise OracleArtifactError("oracle_artifact_rejected")
    return tuple(relative_parts)


def _directory_open_flags() -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    return flags


def _regular_open_flags() -> int:
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    return flags


def _open_absolute_directory_nofollow(path: Path, *, missing_code: str) -> int:
    if (
        os.open not in os.supports_dir_fd
        or not hasattr(os, "O_DIRECTORY")
        or not hasattr(os, "O_NOFOLLOW")
        or not hasattr(os, "O_NONBLOCK")
    ):
        raise OracleArtifactError("oracle_artifact_rejected")
    absolute = path.absolute()
    if not absolute.is_absolute():
        raise OracleArtifactError("oracle_artifact_rejected")
    descriptor: int | None = None
    try:
        descriptor = os.open("/", _directory_open_flags())
        for part in absolute.parts[1:]:
            next_descriptor = os.open(
                part,
                _directory_open_flags(),
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = next_descriptor
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            raise OracleArtifactError("oracle_artifact_rejected")
        return descriptor
    except FileNotFoundError:
        if descriptor is not None:
            os.close(descriptor)
        raise OracleArtifactError(missing_code) from None
    except OSError:
        if descriptor is not None:
            os.close(descriptor)
        raise OracleArtifactError("oracle_artifact_rejected") from None


def _open_session_regular_file(
    session_root: Path,
    *,
    relative_parts: tuple[str, ...],
    missing_code: str,
) -> int:
    if not relative_parts or any(part in ("", ".", "..") for part in relative_parts):
        raise OracleArtifactError("oracle_artifact_rejected")
    root_descriptor = _open_absolute_directory_nofollow(session_root, missing_code=missing_code)
    root_identity = _descriptor_identity(root_descriptor)
    current_descriptor = root_descriptor
    opened_directories: list[tuple[str, tuple[int, int]]] = []
    try:
        for part in relative_parts[:-1]:
            next_descriptor = os.open(
                part,
                _directory_open_flags(),
                dir_fd=current_descriptor,
            )
            if current_descriptor != root_descriptor:
                os.close(current_descriptor)
            current_descriptor = next_descriptor
            opened_directories.append((part, _descriptor_identity(current_descriptor)))
        leaf_name = relative_parts[-1]
        _before_leaf_open(current_descriptor, leaf_name)
        descriptor = os.open(
            leaf_name,
            _regular_open_flags(),
            dir_fd=current_descriptor,
        )
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise OracleArtifactError("oracle_artifact_rejected")
            if not _session_path_identity_is_current(
                session_root,
                root_identity=root_identity,
                opened_directories=opened_directories,
                missing_code=missing_code,
            ):
                raise OracleArtifactError("oracle_artifact_rejected")
        except (OSError, OracleArtifactError):
            os.close(descriptor)
            raise
        return descriptor
    except FileNotFoundError:
        raise OracleArtifactError(missing_code) from None
    except OracleArtifactError:
        raise
    except OSError:
        raise OracleArtifactError("oracle_artifact_rejected") from None
    finally:
        if current_descriptor != root_descriptor:
            os.close(current_descriptor)
        os.close(root_descriptor)


def _session_path_identity_is_current(
    session_root: Path,
    *,
    root_identity: tuple[int, int],
    opened_directories: list[tuple[str, tuple[int, int]]],
    missing_code: str,
) -> bool:
    descriptor = _open_absolute_directory_nofollow(session_root, missing_code=missing_code)
    try:
        if _descriptor_identity(descriptor) != root_identity:
            return False
        for part, expected_identity in opened_directories:
            next_descriptor = os.open(
                part,
                _directory_open_flags(),
                dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = next_descriptor
            if _descriptor_identity(descriptor) != expected_identity:
                return False
        return True
    except OSError:
        return False
    finally:
        os.close(descriptor)


def _descriptor_identity(descriptor: int) -> tuple[int, int]:
    metadata = os.fstat(descriptor)
    return metadata.st_dev, metadata.st_ino


def _before_leaf_open(_parent_fd: int, _leaf_name: str) -> None:
    """Private deterministic race hook for focused tests."""


def _read_session_regular_file(
    session_root: Path,
    *,
    relative_parts: tuple[str, ...],
    limit: int,
    missing_code: str,
) -> bytes:
    descriptor = _open_session_regular_file(
        session_root,
        relative_parts=relative_parts,
        missing_code=missing_code,
    )
    try:
        return _read_fd_bounded(descriptor, limit)
    finally:
        os.close(descriptor)


def _open_regular_nofollow(path: Path) -> int:
    try:
        descriptor = os.open(path, _regular_open_flags())
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor)
            raise OracleArtifactError("oracle_artifact_rejected")
        return descriptor
    except OSError:
        raise OracleArtifactError("oracle_artifact_rejected") from None


def _read_bounded_regular_file(path: Path, limit: int) -> bytes:
    descriptor = _open_regular_nofollow(path)
    try:
        return _read_fd_bounded(descriptor, limit)
    finally:
        os.close(descriptor)


def _read_fd_bounded(descriptor: int, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = os.read(descriptor, min(1024 * 1024, limit + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > limit:
            raise OracleArtifactError("oracle_artifact_rejected")
    return b"".join(chunks)


def _zip_internal_root(payload: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            infos = archive.infolist()
            if not infos or len(infos) > MAX_ZIP_ENTRIES:
                raise OracleArtifactError("oracle_artifact_rejected")
            roots: set[str] = set()
            total_uncompressed = 0
            for info in infos:
                path = PurePosixPath(info.filename)
                if (
                    path.is_absolute()
                    or "\\" in info.filename
                    or any(part in ("", ".", "..") for part in path.parts)
                    or any(
                        any(ord(character) < 32 or ord(character) == 127 for character in part) for part in path.parts
                    )
                ):
                    raise OracleArtifactError("oracle_artifact_rejected")
                if (
                    info.flag_bits & 0x1
                    or info.compress_type not in _SUPPORTED_ZIP_COMPRESSION
                    or info.file_size > MAX_ZIP_ENTRY_UNCOMPRESSED_BYTES
                ):
                    raise OracleArtifactError("oracle_artifact_rejected")
                total_uncompressed += info.file_size
                if total_uncompressed > MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES:
                    raise OracleArtifactError("oracle_artifact_rejected")
                if info.file_size and (
                    info.compress_size == 0 or info.file_size > info.compress_size * MAX_ZIP_COMPRESSION_RATIO
                ):
                    raise OracleArtifactError("oracle_artifact_rejected")
                roots.add(path.parts[0])
    except (
        OSError,
        RuntimeError,
        NotImplementedError,
        ValueError,
        zipfile.BadZipFile,
    ):
        raise OracleArtifactError("oracle_artifact_rejected") from None
    if len(roots) != 1:
        raise OracleArtifactError("oracle_artifact_rejected")
    return next(iter(roots))


def _strict_json_object(payload: bytes) -> dict[str, Any]:
    text = payload.decode("utf-8", errors="strict")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def reject_constant(_value: str) -> None:
        raise ValueError("non-standard JSON number")

    value = json.loads(
        text,
        object_pairs_hook=reject_duplicates,
        parse_constant=reject_constant,
    )
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value
