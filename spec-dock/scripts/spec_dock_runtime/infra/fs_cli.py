from __future__ import annotations

import os
import shutil
import stat
from typing import TYPE_CHECKING

from spec_dock_runtime.application.contracts import WorkbenchFilesystemError

if TYPE_CHECKING:
    from pathlib import Path


DirectoryIdentity = tuple[int, int, int]
PathIdentity = tuple[int, int, int]
_WORKBENCH_DIR_FD_SUPPORTED = all(
    function in os.supports_dir_fd for function in (os.open, os.stat, os.mkdir, os.unlink, os.readlink, os.symlink)
)
_WORKBENCH_FD_INSPECTION_SUPPORTED = os.stat in os.supports_follow_symlinks and os.scandir in os.supports_fd


def path_exists(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise RuntimeError(f"failed to inspect target path: path={path}\n{exc}") from exc
    return True


def remove_tree(path: Path) -> None:
    try:
        shutil.rmtree(path)
    except OSError as exc:
        raise RuntimeError(f"failed to remove directory tree: path={path}\n{exc}") from exc


def remove_target(path: Path) -> None:
    try:
        mode = path.lstat().st_mode
    except OSError as exc:
        raise RuntimeError(f"failed to inspect target path: path={path}\n{exc}") from exc

    if stat.S_ISLNK(mode) or stat.S_ISREG(mode):
        try:
            path.unlink()
        except OSError as exc:
            raise RuntimeError(f"failed to remove target path: path={path}\n{exc}") from exc
        return

    if stat.S_ISDIR(mode):
        remove_tree(path)
        return

    raise RuntimeError(f"unsupported target path type: path={path}")


def path_kind(path: Path) -> str:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return "missing"
    except OSError as exc:
        raise RuntimeError("failed to inspect workbench path") from exc
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISREG(mode):
        return "file"
    return "other"


def guard_workbench_ancestry(root: Path, endpoint: Path, *, allow_missing_leaf: bool = False) -> None:
    """Reject lexical escapes and symlinks without resolving their targets."""
    try:
        if not root.is_absolute() or not endpoint.is_absolute():
            raise WorkbenchFilesystemError(mutation_started=False)
        if ".." in root.parts or ".." in endpoint.parts:
            raise WorkbenchFilesystemError(mutation_started=False)
        try:
            relative = endpoint.relative_to(root)
        except ValueError as exc:
            raise WorkbenchFilesystemError(mutation_started=False) from exc

        components = (
            root,
            *(root.joinpath(*relative.parts[:index]) for index in range(1, len(relative.parts) + 1)),
        )
        for index, component in enumerate(components):
            is_endpoint = index == len(components) - 1
            try:
                mode = component.lstat().st_mode
            except FileNotFoundError:
                if allow_missing_leaf and is_endpoint:
                    return
                raise WorkbenchFilesystemError(mutation_started=False) from None
            if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
                raise WorkbenchFilesystemError(mutation_started=False)
    except WorkbenchFilesystemError:
        raise
    except OSError as exc:
        raise WorkbenchFilesystemError(mutation_started=False) from exc


def guard_workbench_inventory(specdock_dir: Path) -> None:
    """Guard the complete recursive metadata discovery surface before loading."""
    try:
        initiatives_root = specdock_dir / "initiatives"
        if not _optional_directory(initiatives_root):
            return
        pending = [initiatives_root]
        while pending:
            current = pending.pop()
            children: list[Path] = []
            for child in current.iterdir():
                if child.name == ".workbench":
                    continue
                mode = child.lstat().st_mode
                if child.name == ".meta.json":
                    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
                        raise WorkbenchFilesystemError(mutation_started=False)
                    continue
                if stat.S_ISLNK(mode):
                    if child.is_dir():
                        raise WorkbenchFilesystemError(mutation_started=False)
                    continue
                if stat.S_ISDIR(mode):
                    children.append(child)
            pending.extend(sorted(children, key=lambda path: path.name, reverse=True))
    except WorkbenchFilesystemError:
        raise
    except OSError as exc:
        raise WorkbenchFilesystemError(mutation_started=False) from exc


def _optional_directory(path: Path) -> bool:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return False
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise WorkbenchFilesystemError(mutation_started=False)
    return True


def _capture_directory_identity(path: Path) -> DirectoryIdentity:
    status = path.lstat()
    if not stat.S_ISDIR(status.st_mode):
        raise RuntimeError("workbench copy path is not a directory")
    return status.st_dev, status.st_ino, status.st_mode


def _inspect_path(path: Path) -> tuple[str, PathIdentity | None]:
    try:
        status = path.lstat()
    except FileNotFoundError:
        return "missing", None
    identity = status.st_dev, status.st_ino, status.st_mode
    if stat.S_ISDIR(status.st_mode):
        return "directory", identity
    if stat.S_ISREG(status.st_mode):
        return "file", identity
    if stat.S_ISLNK(status.st_mode):
        return "symlink", identity
    return "other", identity


def _descriptor_identity(status: os.stat_result) -> PathIdentity:
    return status.st_dev, status.st_ino, status.st_mode


def _require_workbench_descriptor_support() -> None:
    if not _WORKBENCH_DIR_FD_SUPPORTED:
        raise OSError("required descriptor-relative operation is unavailable")
    if not _WORKBENCH_FD_INSPECTION_SUPPORTED:
        raise OSError("required descriptor inspection is unavailable")
    if getattr(os, "O_NOFOLLOW", None) is None or getattr(os, "O_DIRECTORY", None) is None:
        raise OSError("required directory open flags are unavailable")


def _open_verified_regular_source_at(parent_fd: int, name: str, expected: PathIdentity) -> int:
    no_follow = getattr(os, "O_NOFOLLOW", None)
    if no_follow is None:
        raise OSError("required no-follow open is unavailable")
    flags = os.O_RDONLY | no_follow | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(name, flags, dir_fd=parent_fd)
    try:
        status = os.fstat(descriptor)
        if not stat.S_ISREG(status.st_mode) or _descriptor_identity(status) != expected:
            raise RuntimeError("workbench copy source identity changed")
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def _open_verified_directory(path: Path, expected: DirectoryIdentity) -> int:
    no_follow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if no_follow is None or directory is None:
        raise OSError("required directory open flags are unavailable")
    flags = os.O_RDONLY | directory | no_follow | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(path, flags)
    try:
        if _descriptor_identity(os.fstat(descriptor)) != expected:
            raise RuntimeError("workbench copy directory identity changed")
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def _inspect_entry_at(parent_fd: int, name: str) -> tuple[str, PathIdentity | None]:
    try:
        status = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return "missing", None
    identity = _descriptor_identity(status)
    if stat.S_ISDIR(status.st_mode):
        return "directory", identity
    if stat.S_ISREG(status.st_mode):
        return "file", identity
    if stat.S_ISLNK(status.st_mode):
        return "symlink", identity
    return "other", identity


def _open_verified_directory_at(parent_fd: int, name: str, expected: DirectoryIdentity) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(name, flags, dir_fd=parent_fd)
    try:
        status = os.fstat(descriptor)
        if not stat.S_ISDIR(status.st_mode) or _descriptor_identity(status) != expected:
            raise RuntimeError("workbench copy directory identity changed")
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def _create_and_open_directory_at(
    parent_fd: int,
    name: str,
    mutation_started: list[bool],
) -> int:
    _assert_fd_path_missing(parent_fd, name)
    os.mkdir(name, 0o777, dir_fd=parent_fd)
    mutation_started[0] = True
    kind, identity = _inspect_entry_at(parent_fd, name)
    if kind != "directory" or identity is None:
        raise RuntimeError("workbench copy created directory identity changed")
    return _open_verified_directory_at(parent_fd, name, identity)


def _assert_fd_path_missing(parent_fd: int, name: str) -> None:
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    raise RuntimeError("workbench copy destination path appeared")


def _open_exclusive_regular_file(parent_fd: int, name: str) -> int:
    no_follow = getattr(os, "O_NOFOLLOW", None)
    if no_follow is None:
        raise OSError("required no-follow open is unavailable")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | no_follow | getattr(os, "O_CLOEXEC", 0)
    return os.open(name, flags, 0o600, dir_fd=parent_fd)


def _copy_descriptor_bytes(source_fd: int, destination_fd: int) -> None:
    while chunk := os.read(source_fd, 1024 * 1024):
        pending = memoryview(chunk)
        while pending:
            written = os.write(destination_fd, pending)
            if written == 0:
                raise OSError("workbench copy descriptor write made no progress")
            pending = pending[written:]


def _copy_regular_file(
    source_parent_fd: int,
    destination_parent_fd: int,
    name: str,
    source_identity: PathIdentity,
    destination_identity: PathIdentity | None,
    mutation_started: list[bool],
) -> None:
    source_fd = _open_verified_regular_source_at(source_parent_fd, name, source_identity)
    try:
        source_status = os.fstat(source_fd)
        if destination_identity is not None:
            _unlink_verified_entry_at(destination_parent_fd, name, destination_identity)
            mutation_started[0] = True
        _assert_fd_path_missing(destination_parent_fd, name)
        destination_fd = _open_exclusive_regular_file(destination_parent_fd, name)
        mutation_started[0] = True
        try:
            _copy_descriptor_bytes(source_fd, destination_fd)
            os.fchmod(destination_fd, stat.S_IMODE(source_status.st_mode))
            os.utime(
                destination_fd,
                ns=(source_status.st_atime_ns, source_status.st_mtime_ns),
            )
        finally:
            os.close(destination_fd)
    finally:
        os.close(source_fd)


def _unlink_verified_entry_at(parent_fd: int, name: str, expected: PathIdentity) -> None:
    _, actual = _inspect_entry_at(parent_fd, name)
    if actual != expected:
        raise RuntimeError("workbench copy path identity changed")
    os.unlink(name, dir_fd=parent_fd)


def _read_verified_symlink_at(parent_fd: int, name: str, expected: PathIdentity) -> str:
    kind, before = _inspect_entry_at(parent_fd, name)
    if kind != "symlink" or before != expected:
        raise RuntimeError("workbench copy source identity changed")
    target = os.readlink(name, dir_fd=parent_fd)
    kind, after = _inspect_entry_at(parent_fd, name)
    if kind != "symlink" or after != expected:
        raise RuntimeError("workbench copy source identity changed")
    return target


def copy_workbench(source: Path, destination: Path) -> None:
    """Merge an opaque Workbench tree without following symlinks."""
    mutation_started = [False]
    try:
        _require_workbench_descriptor_support()
        source_identity = _capture_directory_identity(source)
        source_fd = _open_verified_directory(source, source_identity)
        destination_fd: int | None = None
        try:
            destination_kind, destination_identity = _inspect_path(destination)
            if destination_kind == "missing":
                destination_parent_identity = _capture_directory_identity(destination.parent)
                destination_parent_fd = _open_verified_directory(
                    destination.parent,
                    destination_parent_identity,
                )
                try:
                    destination_fd = _create_and_open_directory_at(
                        destination_parent_fd,
                        destination.name,
                        mutation_started,
                    )
                finally:
                    os.close(destination_parent_fd)
            elif destination_kind == "directory":
                if destination_identity is None:
                    raise RuntimeError("workbench copy destination identity is missing")
                destination_fd = _open_verified_directory(destination, destination_identity)
            else:
                raise RuntimeError("workbench copy destination is not a directory")
            _merge_workbench_directory(source_fd, destination_fd, mutation_started)
        finally:
            if destination_fd is not None:
                os.close(destination_fd)
            os.close(source_fd)
    except WorkbenchFilesystemError:
        raise
    except (OSError, RuntimeError) as exc:
        raise WorkbenchFilesystemError(mutation_started=mutation_started[0]) from exc


def _merge_workbench_directory(
    source_fd: int,
    destination_fd: int,
    mutation_started: list[bool],
) -> None:
    with os.scandir(source_fd) as entries:
        source_names = sorted(entry.name for entry in entries)
    for name in source_names:
        _merge_workbench_entry(source_fd, destination_fd, name, mutation_started)


def _merge_workbench_entry(
    source_parent_fd: int,
    destination_parent_fd: int,
    name: str,
    mutation_started: list[bool],
) -> None:
    source_kind, source_identity = _inspect_entry_at(source_parent_fd, name)
    destination_kind, destination_identity = _inspect_entry_at(destination_parent_fd, name)

    if source_kind == "directory":
        if source_identity is None:
            raise RuntimeError("workbench copy source identity is missing")
        source_child_fd = _open_verified_directory_at(source_parent_fd, name, source_identity)
        try:
            if destination_kind == "missing":
                destination_child_fd = _create_and_open_directory_at(
                    destination_parent_fd,
                    name,
                    mutation_started,
                )
            elif destination_kind == "directory":
                if destination_identity is None:
                    raise RuntimeError("workbench copy destination identity is missing")
                destination_child_fd = _open_verified_directory_at(
                    destination_parent_fd,
                    name,
                    destination_identity,
                )
            else:
                raise RuntimeError("workbench copy entry type collision")
            try:
                _merge_workbench_directory(source_child_fd, destination_child_fd, mutation_started)
            finally:
                os.close(destination_child_fd)
        finally:
            os.close(source_child_fd)
        return

    if source_kind not in {"file", "symlink"}:
        raise RuntimeError("workbench copy source entry type is unsupported")
    if source_identity is None:
        raise RuntimeError("workbench copy source identity is missing")
    if destination_kind == "directory" or destination_kind == "other":
        raise RuntimeError("workbench copy entry type collision")
    if source_kind == "file":
        _copy_regular_file(
            source_parent_fd,
            destination_parent_fd,
            name,
            source_identity,
            destination_identity,
            mutation_started,
        )
        return
    link_target = _read_verified_symlink_at(source_parent_fd, name, source_identity)
    if destination_kind in {"file", "symlink"}:
        if destination_identity is None:
            raise RuntimeError("workbench copy destination identity is missing")
        _unlink_verified_entry_at(destination_parent_fd, name, destination_identity)
        mutation_started[0] = True
    _assert_fd_path_missing(destination_parent_fd, name)
    os.symlink(link_target, name, dir_fd=destination_parent_fd)
    mutation_started[0] = True
