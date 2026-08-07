from __future__ import annotations

import contextlib
import ctypes
import errno
import hashlib
import os
from pathlib import Path
import secrets
import stat
import sys
from typing import TYPE_CHECKING

from spec_dock_runtime.application.contracts import (
    BinaryArtifactCleanupState,
    BinaryArtifactPublishError,
    BinaryArtifactPublishRequest,
    BinaryArtifactPublishResult,
    BinaryArtifactPublishWarning,
    ExplicitFileArtifactPublishRequest,
    ExplicitFileArtifactPublishResult,
    ExplicitFileSourcePreflightRequest,
    GuardedExplicitFileSource,
    GuardedWorkbenchSource,
    WorkbenchSourceGuardRequest,
)

if TYPE_CHECKING:
    from collections.abc import Callable


_UNSUPPORTED_PUBLICATION_ERRNOS = {
    errno.EACCES,
    errno.ENOENT,
    errno.ENOSYS,
    errno.EPERM,
    errno.EXDEV,
}
if hasattr(errno, "EOPNOTSUPP"):
    _UNSUPPORTED_PUBLICATION_ERRNOS.add(errno.EOPNOTSUPP)


class _PublishFailure(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class FilesystemBinaryArtifactPublisher:
    """Guard, stage, verify, and exclusively publish opaque Workbench bytes."""

    def __init__(
        self,
        *,
        chunk_size: int = 1024 * 1024,
        stage_barrier: Callable[[], None] | None = None,
        fault_injector: Callable[[str], None] | None = None,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        self._chunk_size = chunk_size
        self._stage_barrier = stage_barrier
        self._fault_injector = fault_injector

    def guard_source(self, request: WorkbenchSourceGuardRequest) -> GuardedWorkbenchSource:
        try:
            repo_root = _absolute_lexical(request.repo_root)
            specdock_dir = _absolute_lexical(request.specdock_dir)
            source_path = _absolute_lexical(request.source_path, relative_to=repo_root)
            scope_directories = tuple(_absolute_lexical(path) for path in request.scope_directories)
            if request.source_path.suffix != ".md":
                raise _PublishFailure("source_ineligible")
            _require_contained(repo_root, specdock_dir)
            approved_roots = (
                specdock_dir / ".workbench",
                *(scope / ".workbench" for scope in scope_directories),
            )
            matching_roots = [root for root in approved_roots if _is_lexically_contained(root, source_path)]
            if len(matching_roots) != 1:
                raise _PublishFailure("source_ineligible")
            workbench_root = matching_roots[0]
            _require_contained(repo_root, workbench_root)
            _guard_directory_ancestry(repo_root, source_path.parent)
            status = source_path.lstat()
            if not stat.S_ISREG(status.st_mode) or stat.S_ISLNK(status.st_mode):
                raise _PublishFailure("source_ineligible")
            return GuardedWorkbenchSource(
                source_path=source_path,
                workbench_root=workbench_root,
                device=status.st_dev,
                inode=status.st_ino,
                mode=status.st_mode,
            )
        except BinaryArtifactPublishError:
            raise
        except (_PublishFailure, FileNotFoundError, OSError, ValueError):
            raise BinaryArtifactPublishError(
                code="source_ineligible",
                cleanup_state="not_created",
            ) from None

    def guard_explicit_file_source(
        self,
        request: ExplicitFileSourcePreflightRequest,
    ) -> GuardedExplicitFileSource:
        source_fd: int | None = None
        try:
            repo_root = _absolute_lexical(request.repo_root)
            source_path = _absolute_lexical(request.source_path, relative_to=repo_root)
            path_status = source_path.lstat()
            if stat.S_ISLNK(path_status.st_mode) or not stat.S_ISREG(path_status.st_mode):
                raise _PublishFailure("source_ineligible")
            if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_NONBLOCK"):
                raise _PublishFailure("source_guard_unsupported")
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if hasattr(os, "O_CLOEXEC"):
                flags |= os.O_CLOEXEC
            source_fd = os.open(source_path, flags)
            opened_status = os.fstat(source_fd)
            path_status_after = source_path.lstat()
            expected = (path_status.st_dev, path_status.st_ino, path_status.st_mode)
            if (
                not stat.S_ISREG(opened_status.st_mode)
                or (opened_status.st_dev, opened_status.st_ino, opened_status.st_mode) != expected
                or (
                    path_status_after.st_dev,
                    path_status_after.st_ino,
                    path_status_after.st_mode,
                )
                != expected
            ):
                raise _PublishFailure("source_ineligible")
            source_visibility, source_display = _classify_explicit_source(
                repo_root,
                source_path,
                opened_status,
            )
            guarded = GuardedExplicitFileSource(
                source_path=source_path,
                descriptor=source_fd,
                initial_status=opened_status,
                source_visibility=source_visibility,
                source_display=source_display,
            )
            source_fd = None
            return guarded
        except _PublishFailure as exc:
            raise BinaryArtifactPublishError(
                code=exc.code,
                cleanup_state="not_created",
            ) from None
        except (FileNotFoundError, OSError, ValueError):
            raise BinaryArtifactPublishError(
                code="source_ineligible",
                cleanup_state="not_created",
            ) from None
        finally:
            if source_fd is not None:
                _close_descriptor_noexcept(source_fd)

    def publish(self, request: BinaryArtifactPublishRequest) -> BinaryArtifactPublishResult:
        guarded = self.guard_source(request.source)
        destination = _absolute_lexical(request.destination_path)
        repo_root = _absolute_lexical(request.source.repo_root)
        try:
            _require_contained(repo_root, destination)
        except (_PublishFailure, FileNotFoundError, OSError, ValueError):
            raise BinaryArtifactPublishError(
                code="destination_ineligible",
                cleanup_state="not_created",
            ) from None

        source_fd: int | None = None
        try:
            source_fd, initial_status = self._open_guarded_source(guarded)
            return self._stage_verify_and_publish(
                repo_root=repo_root,
                source_path=guarded.source_path,
                source_fd=source_fd,
                initial_status=initial_status,
                destination=destination,
                confirm_destination=True,
            )
        finally:
            if source_fd is not None:
                os.close(source_fd)

    def publish_explicit_file(
        self,
        request: ExplicitFileArtifactPublishRequest,
    ) -> ExplicitFileArtifactPublishResult:
        guarded = request.guarded_source
        if guarded._closed:
            raise BinaryArtifactPublishError(code="source_changed", cleanup_state="not_created")
        destination = _absolute_lexical(request.destination_path)
        repo_root = _absolute_lexical(request.repo_root)
        try:
            _require_contained(repo_root, destination)
        except (_PublishFailure, ValueError):
            raise BinaryArtifactPublishError(code="destination_ineligible", cleanup_state="not_created") from None
        try:
            os.lseek(guarded._descriptor, 0, os.SEEK_SET)
        except OSError:
            raise BinaryArtifactPublishError(code="source_changed", cleanup_state="not_created") from None
        published = self._stage_verify_and_publish(
            repo_root=repo_root,
            source_path=guarded._source_path,
            source_fd=guarded._descriptor,
            initial_status=guarded._initial_status,
            destination=destination,
            confirm_destination=False,
            probe_capability=True,
        )
        return ExplicitFileArtifactPublishResult(
            source_visibility=guarded.source_visibility,
            source_display=guarded.source_display,
            destination_path=published.destination_path,
            committed=published.committed,
            cleanup_state=published.cleanup_state,
            warning_codes=tuple(
                warning
                for warning in published.warning_codes
                if warning in ("directory_fsync_failed", "temp_cleanup_retained")
            ),
        )

    def _stage_verify_and_publish(
        self,
        *,
        repo_root: Path,
        source_path: Path,
        source_fd: int,
        initial_status: os.stat_result,
        destination: Path,
        confirm_destination: bool,
        probe_capability: bool = False,
    ) -> BinaryArtifactPublishResult:
        destination_parent_fd: int | None = None
        destination_parent_identity: tuple[int, int] | None = None
        temp_fd: int | None = None
        temp_name: str | None = None
        committed = False
        try:
            try:
                self._inject("temp_create")
            except OSError:
                raise _PublishFailure("temp_create_failed") from None
            try:
                destination_parent_fd, destination_parent_identity = _open_secure_directory(
                    repo_root,
                    destination.parent,
                )
            except (_PublishFailure, FileNotFoundError, OSError, ValueError):
                raise _PublishFailure("destination_ineligible") from None
            try:
                temp_fd, temp_name = self._create_temp(
                    destination_parent_fd,
                    anonymous=probe_capability and sys.platform.startswith("linux"),
                )
            except OSError:
                raise _PublishFailure("temp_create_failed") from None

            stream_sha256, stream_count = self._copy_source_to_temp(source_fd, temp_fd)
            try:
                self._inject("file_fsync")
                os.fsync(temp_fd)
            except OSError:
                raise _PublishFailure("file_fsync_failed") from None
            try:
                self._inject("hash")
                staged_sha256, staged_count = self._hash_descriptor(temp_fd)
            except OSError:
                raise _PublishFailure("hash_failed") from None
            if (staged_sha256, staged_count) != (stream_sha256, stream_count):
                raise _PublishFailure("hash_mismatch")
            staged_status = os.fstat(temp_fd)
            if not stat.S_ISREG(staged_status.st_mode):
                raise _PublishFailure("hash_mismatch")
            if (staged_status.st_dev, staged_status.st_ino) == (
                initial_status.st_dev,
                initial_status.st_ino,
            ):
                raise _PublishFailure("source_alias")
            if self._stage_barrier is not None:
                self._stage_barrier()
            source_sha256, source_count = self._verify_source_stability(
                source_fd,
                source_path,
                initial_status,
            )
            if (source_sha256, source_count) != (stream_sha256, stream_count):
                raise _PublishFailure("source_changed")
            self._inject("before_publication")
            if not _visible_directory_matches(
                repo_root,
                destination.parent,
                destination_parent_identity,
            ):
                raise _PublishFailure("destination_ineligible")
            if probe_capability and not sys.platform.startswith("linux"):
                if temp_name is None:
                    raise _PublishFailure("publication_unsupported")
                self._probe_no_replace_capability(
                    temp_fd,
                    destination_parent_fd,
                    temp_name,
                )
                self._publish_no_replace(
                    temp_fd,
                    destination_parent_fd,
                    destination.name,
                    inject_capability=False,
                )
            else:
                self._publish_no_replace(
                    temp_fd,
                    destination_parent_fd,
                    destination.name,
                )
            committed = True
            warning_codes: list[BinaryArtifactPublishWarning] = []
            if not self._fsync_directory(destination_parent_fd):
                warning_codes.append("directory_fsync_failed")
            destination_sha256, destination_count = staged_sha256, staged_count
            if confirm_destination:
                if not _visible_directory_matches(
                    repo_root,
                    destination.parent,
                    destination_parent_identity,
                ):
                    warning_codes.append("destination_read_failed")
                else:
                    try:
                        destination_sha256, destination_count = self._hash_published_destination(
                            destination_parent_fd,
                            destination.name,
                        )
                    except _PublishFailure as exc:
                        if exc.code != "destination_read_failed":
                            raise
                        destination_sha256, destination_count = staged_sha256, staged_count
                        warning_codes.append("destination_read_failed")
                    else:
                        if (destination_sha256, destination_count) != (staged_sha256, staged_count):
                            warning_codes.append("destination_mismatch")
            if temp_name is None:
                cleanup_state: BinaryArtifactCleanupState = "not_created"
            else:
                cleanup_state = self._cleanup_temp(temp_name, temp_fd, destination_parent_fd)
            if cleanup_state == "removed":
                temp_name = None
            elif cleanup_state == "retained":
                warning_codes.append("temp_cleanup_retained")
            return BinaryArtifactPublishResult(
                source_path=source_path,
                destination_path=destination,
                source_sha256=source_sha256,
                stream_sha256=stream_sha256,
                staged_sha256=staged_sha256,
                destination_sha256=destination_sha256,
                source_byte_count=source_count,
                stream_byte_count=stream_count,
                staged_byte_count=staged_count,
                destination_byte_count=destination_count,
                source_inode=initial_status.st_ino,
                staged_inode=staged_status.st_ino,
                cleanup_state=cleanup_state,
                warning_codes=tuple(warning_codes),
            )
        except BinaryArtifactPublishError:
            raise
        except _PublishFailure as exc:
            cleanup_state = self._cleanup_after_failure(temp_name, temp_fd, destination_parent_fd)
            raise BinaryArtifactPublishError(code=exc.code, cleanup_state=cleanup_state) from None
        except OSError:
            if committed:
                raise
            cleanup_state = self._cleanup_after_failure(temp_name, temp_fd, destination_parent_fd)
            raise BinaryArtifactPublishError(code="filesystem_failed", cleanup_state=cleanup_state) from None
        except Exception:
            if committed:
                raise
            cleanup_state = self._cleanup_after_failure(temp_name, temp_fd, destination_parent_fd)
            raise BinaryArtifactPublishError(code="runtime_failed", cleanup_state=cleanup_state) from None
        finally:
            if temp_fd is not None:
                self._close_noexcept(temp_fd, "temp_fd_close")
            if destination_parent_fd is not None:
                self._close_noexcept(destination_parent_fd, "destination_parent_fd_close")

    def _create_temp(
        self,
        destination_parent_fd: int,
        *,
        anonymous: bool = False,
    ) -> tuple[int, str | None]:
        if anonymous:
            return self._create_linux_anonymous_temp(destination_parent_fd), None
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        while True:
            temp_name = f".spec-dock-import-{secrets.token_hex(16)}.tmp"
            try:
                return os.open(temp_name, flags, 0o600, dir_fd=destination_parent_fd), temp_name
            except FileExistsError:
                continue

    def _create_linux_anonymous_temp(self, destination_parent_fd: int) -> int:
        if not hasattr(os, "O_TMPFILE"):
            raise _PublishFailure("publication_unsupported")
        flags = os.O_RDWR | os.O_TMPFILE
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        descriptor: int | None = None
        try:
            descriptor = os.open(
                ".",
                flags,
                0o600,
                dir_fd=destination_parent_fd,
            )
            descriptor_status = os.fstat(descriptor)
            if not stat.S_ISREG(descriptor_status.st_mode):
                raise _PublishFailure("publication_unsupported")
            proc_reference = Path(f"/proc/self/fd/{descriptor}")
            proc_status = proc_reference.stat()
            if not stat.S_ISREG(proc_status.st_mode) or (proc_status.st_dev, proc_status.st_ino) != (
                descriptor_status.st_dev,
                descriptor_status.st_ino,
            ):
                raise _PublishFailure("publication_unsupported")
            self._inject("linux_directory_durability")
            os.fsync(destination_parent_fd)
        except _PublishFailure:
            if descriptor is not None:
                _close_descriptor_noexcept(descriptor)
            raise
        except (OSError, TypeError):
            if descriptor is not None:
                _close_descriptor_noexcept(descriptor)
            raise _PublishFailure("publication_unsupported") from None
        return descriptor

    def _open_guarded_source(self, guarded: GuardedWorkbenchSource) -> tuple[int, os.stat_result]:
        flags = os.O_RDONLY
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        source_fd: int | None = None
        try:
            source_fd = os.open(guarded.source_path, flags)
            status = os.fstat(source_fd)
            path_status = guarded.source_path.lstat()
        except OSError:
            if source_fd is not None:
                os.close(source_fd)
            raise _PublishFailure("source_changed") from None
        expected = (guarded.device, guarded.inode, guarded.mode)
        if (
            not stat.S_ISREG(status.st_mode)
            or (
                status.st_dev,
                status.st_ino,
                status.st_mode,
            )
            != expected
            or (
                path_status.st_dev,
                path_status.st_ino,
                path_status.st_mode,
            )
            != expected
        ):
            os.close(source_fd)
            raise _PublishFailure("source_changed")
        return source_fd, status

    def _copy_source_to_temp(self, source_fd: int, temp_fd: int) -> tuple[str, int]:
        digest = hashlib.sha256()
        byte_count = 0
        try:
            self._inject("write")
            while True:
                chunk = os.read(source_fd, self._chunk_size)
                if not chunk:
                    break
                digest.update(chunk)
                byte_count += len(chunk)
                _write_all(temp_fd, chunk)
        except OSError:
            raise _PublishFailure("copy_failed") from None
        return digest.hexdigest(), byte_count

    def _hash_descriptor(self, descriptor: int) -> tuple[str, int]:
        os.lseek(descriptor, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        byte_count = 0
        while True:
            chunk = os.read(descriptor, self._chunk_size)
            if not chunk:
                return digest.hexdigest(), byte_count
            digest.update(chunk)
            byte_count += len(chunk)

    def _verify_source_stability(
        self,
        source_fd: int,
        source_path: Path,
        initial_status: os.stat_result,
    ) -> tuple[str, int]:
        try:
            source_sha256, source_count = self._hash_descriptor(source_fd)
            descriptor_status = os.fstat(source_fd)
            path_status = source_path.lstat()
        except OSError:
            raise _PublishFailure("source_changed") from None
        initial_identity = (initial_status.st_dev, initial_status.st_ino, initial_status.st_mode)
        descriptor_identity = (
            descriptor_status.st_dev,
            descriptor_status.st_ino,
            descriptor_status.st_mode,
        )
        path_identity = (path_status.st_dev, path_status.st_ino, path_status.st_mode)
        initial_metadata = (
            initial_status.st_size,
            initial_status.st_mtime_ns,
            initial_status.st_ctime_ns,
        )
        descriptor_metadata = (
            descriptor_status.st_size,
            descriptor_status.st_mtime_ns,
            descriptor_status.st_ctime_ns,
        )
        if (
            descriptor_identity != initial_identity
            or path_identity != initial_identity
            or descriptor_metadata != initial_metadata
            or not stat.S_ISREG(path_status.st_mode)
        ):
            raise _PublishFailure("source_changed")
        return source_sha256, source_count

    def _publish_no_replace(
        self,
        temp_fd: int,
        destination_parent_fd: int,
        destination_name: str,
        *,
        inject_capability: bool = True,
    ) -> None:
        if inject_capability:
            try:
                self._inject("publication_unsupported")
            except OSError:
                raise _PublishFailure("publication_unsupported") from None
        try:
            _commit_descriptor_no_replace(
                temp_fd,
                destination_parent_fd,
                destination_name,
            )
        except FileExistsError:
            raise _PublishFailure("destination_exists") from None
        except (NotImplementedError, TypeError):
            raise _PublishFailure("publication_unsupported") from None
        except OSError as exc:
            if exc.errno in _UNSUPPORTED_PUBLICATION_ERRNOS:
                raise _PublishFailure("publication_unsupported") from None
            raise _PublishFailure("publication_failed") from None

    def _probe_no_replace_capability(
        self,
        temp_fd: int,
        destination_parent_fd: int,
        existing_temp_name: str,
    ) -> None:
        try:
            self._inject("publication_unsupported")
            self._inject("capability_probe")
            _commit_descriptor_no_replace(
                temp_fd,
                destination_parent_fd,
                existing_temp_name,
            )
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise _PublishFailure("publication_unsupported") from None
        except (NotImplementedError, TypeError):
            raise _PublishFailure("publication_unsupported") from None
        else:
            raise _PublishFailure("publication_unsupported")
        try:
            self._inject("capability_probe_after_existing_check")
        except OSError as exc:
            raise _PublishFailure("publication_unsupported") from exc

    def _close_noexcept(self, descriptor: int, point: str) -> None:
        with contextlib.suppress(Exception):
            self._inject(point)
        _close_descriptor_noexcept(descriptor)

    def _hash_published_destination(
        self,
        destination_parent_fd: int,
        destination_name: str,
    ) -> tuple[str, int]:
        flags = os.O_RDONLY
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor: int | None = None
        try:
            self._inject("post_confirmation")
            descriptor = os.open(
                destination_name,
                flags,
                dir_fd=destination_parent_fd,
            )
            return self._hash_descriptor(descriptor)
        except OSError:
            raise _PublishFailure("destination_read_failed") from None
        finally:
            if descriptor is not None:
                os.close(descriptor)

    def _fsync_directory(self, destination_parent_fd: int) -> bool:
        try:
            self._inject("directory_fsync")
            os.fsync(destination_parent_fd)
        except OSError:
            return False
        return True

    def _cleanup_after_failure(
        self,
        temp_name: str | None,
        temp_fd: int | None,
        destination_parent_fd: int | None,
    ) -> BinaryArtifactCleanupState:
        if temp_name is None:
            return "not_created"
        return self._cleanup_temp(temp_name, temp_fd, destination_parent_fd)

    def _cleanup_temp(
        self,
        temp_name: str,
        temp_fd: int | None,
        destination_parent_fd: int | None,
    ) -> BinaryArtifactCleanupState:
        if temp_fd is None or destination_parent_fd is None:
            return "retained"
        observed_fd: int | None = None
        try:
            path_status = os.stat(
                temp_name,
                dir_fd=destination_parent_fd,
                follow_symlinks=False,
            )
            descriptor_status = os.fstat(temp_fd)
            if not stat.S_ISREG(path_status.st_mode) or not stat.S_ISREG(descriptor_status.st_mode):
                return "retained"
            flags = os.O_RDONLY
            if hasattr(os, "O_CLOEXEC"):
                flags |= os.O_CLOEXEC
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            if hasattr(os, "O_NONBLOCK"):
                flags |= os.O_NONBLOCK
            observed_fd = os.open(
                temp_name,
                flags,
                dir_fd=destination_parent_fd,
            )
            observed_status = os.fstat(observed_fd)
            if not stat.S_ISREG(observed_status.st_mode):
                return "retained"
            self._inject("cleanup_before_final_path_check")
            final_path_status = os.stat(
                temp_name,
                dir_fd=destination_parent_fd,
                follow_symlinks=False,
            )
        except OSError:
            return "retained"
        finally:
            if observed_fd is not None:
                _close_descriptor_noexcept(observed_fd)
        identities = {
            (path_status.st_dev, path_status.st_ino),
            (descriptor_status.st_dev, descriptor_status.st_ino),
            (observed_status.st_dev, observed_status.st_ino),
            (final_path_status.st_dev, final_path_status.st_ino),
        }
        if len(identities) != 1 or not stat.S_ISREG(final_path_status.st_mode):
            return "retained"
        try:
            self._inject("cleanup")
            os.unlink(temp_name, dir_fd=destination_parent_fd)
        except OSError:
            return "retained"
        return "removed"

    def _inject(self, point: str) -> None:
        if self._fault_injector is not None:
            self._fault_injector(point)


def _absolute_lexical(path: Path, *, relative_to: Path | None = None) -> Path:
    candidate = path
    if not candidate.is_absolute():
        if relative_to is None:
            raise ValueError("relative path has no base")
        candidate = relative_to / candidate
    return Path(os.path.normpath(candidate))


def _is_lexically_contained(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _require_contained(root: Path, path: Path) -> None:
    if not root.is_absolute() or not path.is_absolute() or not _is_lexically_contained(root, path):
        raise _PublishFailure("source_ineligible")


def _classify_explicit_source(
    repo_root: Path,
    source_path: Path,
    opened_status: os.stat_result,
) -> tuple[str, str]:
    try:
        resolved_root = repo_root.resolve(strict=True)
        resolved_source = source_path.resolve(strict=True)
        resolved_status = resolved_source.stat()
        if (
            _is_lexically_contained(resolved_root, resolved_source)
            and (
                resolved_status.st_dev,
                resolved_status.st_ino,
                resolved_status.st_mode,
            )
            == (
                opened_status.st_dev,
                opened_status.st_ino,
                opened_status.st_mode,
            )
            and _is_lexically_contained(repo_root, source_path)
        ):
            return "repo_relative", source_path.relative_to(repo_root).as_posix()
    except (FileNotFoundError, OSError, ValueError):
        pass
    return "basename_only", source_path.name


def _guard_directory_ancestry(root: Path, endpoint: Path) -> None:
    _require_contained(root, endpoint)
    relative = endpoint.relative_to(root)
    components = (
        root,
        *(root.joinpath(*relative.parts[:index]) for index in range(1, len(relative.parts) + 1)),
    )
    for component in components:
        status = component.lstat()
        if stat.S_ISLNK(status.st_mode) or not stat.S_ISDIR(status.st_mode):
            raise _PublishFailure("source_ineligible")


def _open_secure_directory(root: Path, endpoint: Path) -> tuple[int, tuple[int, int]]:
    _require_contained(root, endpoint)
    if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
        raise _PublishFailure("destination_ineligible")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC

    descriptor: int | None = None
    try:
        root_before = root.lstat()
        descriptor = os.open(root, flags)
        root_opened = os.fstat(descriptor)
        root_after = root.lstat()
        if not _matching_directory_statuses(root_before, root_opened, root_after):
            raise _PublishFailure("destination_ineligible")
        for component in endpoint.relative_to(root).parts:
            component_before = os.stat(
                component,
                dir_fd=descriptor,
                follow_symlinks=False,
            )
            next_descriptor = os.open(component, flags, dir_fd=descriptor)
            try:
                component_opened = os.fstat(next_descriptor)
                component_after = os.stat(
                    component,
                    dir_fd=descriptor,
                    follow_symlinks=False,
                )
                if not _matching_directory_statuses(
                    component_before,
                    component_opened,
                    component_after,
                ):
                    raise _PublishFailure("destination_ineligible")
            except BaseException:
                os.close(next_descriptor)
                raise
            os.close(descriptor)
            descriptor = next_descriptor
        status = os.fstat(descriptor)
        return descriptor, (status.st_dev, status.st_ino)
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
        raise


def _matching_directory_statuses(*statuses: os.stat_result) -> bool:
    identities = {(status.st_dev, status.st_ino, status.st_mode) for status in statuses}
    return len(identities) == 1 and all(stat.S_ISDIR(status.st_mode) for status in statuses)


def _visible_directory_matches(
    root: Path,
    endpoint: Path,
    expected_identity: tuple[int, int],
) -> bool:
    descriptor: int | None = None
    try:
        descriptor, identity = _open_secure_directory(root, endpoint)
        return identity == expected_identity
    except (_PublishFailure, FileNotFoundError, OSError, ValueError):
        return False
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _write_all(descriptor: int, body: bytes) -> None:
    view = memoryview(body)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise OSError("short binary write")
        view = view[written:]


def _close_descriptor_noexcept(descriptor: int) -> None:
    with contextlib.suppress(OSError):
        os.close(descriptor)


def _commit_descriptor_no_replace(
    source_fd: int,
    destination_parent_fd: int,
    destination_name: str,
) -> None:
    if sys.platform == "darwin":
        _clone_macos_descriptor(
            source_fd,
            destination_parent_fd,
            destination_name,
        )
    elif sys.platform.startswith("linux"):
        os.link(
            f"/proc/self/fd/{source_fd}",
            destination_name,
            dst_dir_fd=destination_parent_fd,
            follow_symlinks=True,
        )
    else:
        raise OSError(errno.ENOSYS, "descriptor publication unavailable")


def _clone_macos_descriptor(
    source_fd: int,
    destination_parent_fd: int,
    destination_name: str,
) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        fclonefileat = libc.fclonefileat
    except AttributeError:
        raise OSError(errno.ENOSYS, "fclonefileat unavailable") from None
    fclonefileat.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32]
    fclonefileat.restype = ctypes.c_int
    if fclonefileat(source_fd, destination_parent_fd, os.fsencode(destination_name), 0) != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number))
