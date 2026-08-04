from __future__ import annotations

from contextlib import suppress
import ctypes
from dataclasses import dataclass, field, replace as dataclass_replace
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import select
import shutil
import stat
import subprocess
import sys
import tempfile
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal

from spec_dock_runtime.domain.issue_planning_candidate import DOCUMENT_NAMES
from spec_dock_runtime.infra.issue_planning_candidate import (
    OutputDirectoryGuard,
    open_safe_directory_descriptor,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from spec_dock_runtime.domain.issue_planning_contracts import (
        IssueCandidateIdentity,
        ReviewedPlanningIdentity,
    )
PlanningApplyStatus = Literal[
    "ready",
    "blocked",
    "stale",
    "rejected",
    "rolled_back",
    "recovery_required",
    "publication_pending",
    "blocked_remote_diverged",
]

_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_OPERATION_SCHEMA = "spec-dock.issue-planning-apply-operation.v1"
_PROHIBITED_GIT_WORDS = {
    "--force",
    "--force-with-lease",
    "reset",
    "--amend",
    "rebase",
}
_MANAGED_SYNC_FILES = (
    "spec-dock/.agent/index-all.json",
    "spec-dock/.agent/index.json",
    "spec-dock/.agent/tree-all.json",
    "spec-dock/.agent/tree.json",
    "spec-dock/.agent/deps-issues.json",
    "spec-dock/tree-all.puml",
    "spec-dock/tree.puml",
    "spec-dock/deps-issues.puml",
    "spec-dock/deps-raw.puml",
    "spec-dock/dashboard.md",
    "spec-dock/.agent/deps.json",
    "spec-dock/.agent/deps.puml",
    "spec-dock/.agent/deps.todo.puml",
    "spec-dock/.work/state.json",
    "spec-dock/.work/index.json",
    "spec-dock/.work/tree.json",
)
_MANAGED_SYNC_TREE = "spec-dock/adrs"
_MAX_MANAGED_ENTRIES = 10_000
_MAX_MANAGED_BYTES = 32_000_000
_DURABLE_OPERATION_STATES = frozenset({
    "OPERATION_RECORDED",
    "BACKED_UP",
    "MUTATING",
    "VALIDATED",
    "SYNCED",
    "STAGED",
    "COMMITTED",
    "PUSHED",
    "REMOTE_PARITY",
    "ROLLED_BACK",
})
_TRANSACTION_RESTORE_STATES = frozenset({
    "MUTATING",
    "VALIDATED",
    "SYNCED",
    "STAGED",
})
_NO_TRANSACTION_START_STATES = frozenset({
    "OPERATION_RECORDED",
    "ROLLED_BACK",
})


class PlanningApplyOutputRejected(ValueError):
    pass


class PlanningApplyUnsafeGitCommand(ValueError):
    pass


class PlanningApplyRestoreMismatch(RuntimeError):
    pass


@dataclass
class _ApplyEvidenceHandle:
    output_fd: int
    operation_fd: int
    logical_operation_path: Path

    def close(self) -> None:
        os.close(self.operation_fd)
        os.close(self.output_fd)

    def __truediv__(self, name: str) -> Path:
        return self.logical_operation_path / name

    def stat(self) -> os.stat_result:
        return self.logical_operation_path.stat()

    def iterdir(self):
        return self.logical_operation_path.iterdir()


@dataclass(frozen=True)
class FileSnapshot:
    existed: bool
    data: bytes
    mode: int
    sha256: str


@dataclass(frozen=True)
class GitIndexSnapshot:
    path: Path
    data: bytes
    mode: int
    sha256: str


@dataclass(frozen=True)
class GitCommandResult:
    returncode: int
    stdout: bytes
    stderr: bytes


@dataclass(frozen=True)
class _PublicationAuthority:
    repository: str
    push_endpoint: str = field(repr=False)


@dataclass
class _OperationBranchLock:
    path: Path
    descriptor: int
    device: int
    inode: int
    mode: int
    destination: str
    expected_commit: str
    ref_process: subprocess.Popen[bytes]
    hook_root: Path

    def __enter__(self) -> _OperationBranchLock:
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        failure: PlanningApplyRestoreMismatch | None = None
        try:
            try:
                self.assert_held()
            except PlanningApplyRestoreMismatch as exc:
                failure = exc
                _abandon_operation_ref_transaction(self.ref_process)
            else:
                try:
                    _abort_operation_ref_transaction(self.ref_process)
                    _remove_captured_operation_head_lock(
                        self.path,
                        self.descriptor,
                        self.device,
                        self.inode,
                        self.mode,
                    )
                except PlanningApplyRestoreMismatch as exc:
                    failure = exc
        finally:
            with suppress(OSError):
                os.close(self.descriptor)
            _close_operation_ref_streams(self.ref_process)
            with suppress(OSError):
                self.hook_root.rmdir()
        if failure is not None:
            raise failure

    def assert_held(self) -> None:
        try:
            descriptor_stat = os.fstat(self.descriptor)
            current = self.path.lstat()
        except (FileNotFoundError, OSError, ValueError):
            raise PlanningApplyRestoreMismatch("operation branch HEAD lock disappeared") from None
        if (
            not stat.S_ISREG(descriptor_stat.st_mode)
            or descriptor_stat.st_uid != os.geteuid()
            or stat.S_IMODE(descriptor_stat.st_mode) != self.mode
            or not stat.S_ISREG(current.st_mode)
            or current.st_uid != os.geteuid()
            or stat.S_IMODE(current.st_mode) != self.mode
            or (descriptor_stat.st_dev, descriptor_stat.st_ino) != (self.device, self.inode)
            or (current.st_dev, current.st_ino) != (self.device, self.inode)
        ):
            raise PlanningApplyRestoreMismatch("operation branch HEAD lock was replaced")
        if self.ref_process.poll() is not None:
            raise PlanningApplyRestoreMismatch("operation branch ref transaction ended")


def _close_operation_ref_streams(process: subprocess.Popen[bytes]) -> None:
    for stream in (process.stdin, process.stdout, process.stderr):
        if stream is not None:
            with suppress(OSError, ValueError):
                stream.close()


def _abandon_operation_ref_transaction(process: subprocess.Popen[bytes]) -> None:
    failure: PlanningApplyRestoreMismatch | None = None
    try:
        if process.poll() is None:
            with suppress(OSError, ProcessLookupError):
                process.kill()
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        failure = PlanningApplyRestoreMismatch(
            "operation branch ref transaction abandonment failed",
        )
    finally:
        _close_operation_ref_streams(process)
    if failure is not None:
        raise failure


def _abort_operation_ref_transaction(process: subprocess.Popen[bytes]) -> None:
    try:
        if process.poll() is not None or process.stdin is None:
            raise PlanningApplyRestoreMismatch(
                "operation branch ref transaction abort failed",
            )
        process.stdin.write(b"abort\n")
        process.stdin.flush()
        process.stdin.close()
        returncode = process.wait(timeout=5)
    except PlanningApplyRestoreMismatch:
        _abandon_operation_ref_transaction(process)
        raise
    except (OSError, subprocess.TimeoutExpired) as exc:
        with suppress(PlanningApplyRestoreMismatch):
            _abandon_operation_ref_transaction(process)
        raise PlanningApplyRestoreMismatch(
            "operation branch ref transaction abort failed",
        ) from exc
    finally:
        _close_operation_ref_streams(process)
    if returncode != 0:
        raise PlanningApplyRestoreMismatch(
            "operation branch ref transaction abort failed",
        )


def _remove_captured_operation_head_lock(
    path: Path,
    descriptor: int,
    device: int,
    inode: int,
    mode: int,
) -> None:
    try:
        descriptor_stat = os.fstat(descriptor)
    except (OSError, ValueError) as exc:
        raise PlanningApplyRestoreMismatch(
            "operation branch HEAD lock ownership failed",
        ) from exc
    if (
        not stat.S_ISREG(descriptor_stat.st_mode)
        or descriptor_stat.st_uid != os.geteuid()
        or stat.S_IMODE(descriptor_stat.st_mode) != mode
        or (descriptor_stat.st_dev, descriptor_stat.st_ino) != (device, inode)
    ):
        raise PlanningApplyRestoreMismatch("operation branch HEAD lock was replaced")
    try:
        current = path.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise PlanningApplyRestoreMismatch(
            "operation branch HEAD lock ownership failed",
        ) from exc
    if (
        not stat.S_ISREG(current.st_mode)
        or current.st_uid != os.geteuid()
        or stat.S_IMODE(current.st_mode) != mode
        or (current.st_dev, current.st_ino) != (device, inode)
    ):
        raise PlanningApplyRestoreMismatch("operation branch HEAD lock was replaced")
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise PlanningApplyRestoreMismatch(
            "operation branch HEAD lock cleanup failed",
        ) from exc


def _read_operation_ref_ack(
    process: subprocess.Popen[bytes],
    expected: bytes,
) -> None:
    stdout = process.stdout
    if stdout is None:
        raise PlanningApplyRestoreMismatch("operation branch ref transaction acknowledgement failed")
    ready, _, _ = select.select([stdout], [], [], 5)
    if not ready or stdout.readline() != expected + b"\n":
        raise PlanningApplyRestoreMismatch("operation branch ref transaction acknowledgement failed")


def _git_ref_lock_mode_is_compatible(mode: int) -> bool:
    return (mode & ~0o666) == 0


@dataclass(frozen=True)
class ManagedStateEntry:
    kind: Literal["file", "directory", "symlink"]
    mode: int
    data: bytes = field(default=b"", repr=False)
    target: str | None = None


@dataclass(frozen=True)
class DurableTransactionBackup:
    index: GitIndexSnapshot
    files: Mapping[str, FileSnapshot]
    decision: FileSnapshot
    managed: Mapping[str, ManagedStateEntry]
    target_parent_identities: Mapping[str, tuple[int, int]]


@dataclass(frozen=True)
class _GuardedRepositoryTarget:
    relative: str
    parent_fd: int
    name: str
    parent_device: int
    parent_inode: int


@dataclass(frozen=True)
class _TargetMutation:
    relative: str
    before: FileSnapshot
    after: FileSnapshot
    phase: Literal["prepared", "published", "rollback-prepared"]
    workspace_name: str
    workspace_device: int
    workspace_inode: int
    staged_name: str
    staged_device: int
    staged_inode: int
    before_device: int | None
    before_inode: int | None
    after_device: int
    after_inode: int


@dataclass(frozen=True)
class _WorkspaceIntent:
    relative: str
    purpose: Literal["forward", "rollback-existing", "rollback-absent"]
    workspace_name: str
    workspace_device: int | None
    workspace_inode: int | None
    staged_name: str
    staged_device: int | None
    staged_inode: int | None


@dataclass(frozen=True)
class _MutationWorkspace:
    name: str
    descriptor: int
    device: int
    inode: int


class _ApplyTargetDrift(RuntimeError):
    def __init__(self, relative: str) -> None:
        super().__init__(relative)
        self.relative = relative


class _RepositoryTargetGuard:
    def __init__(self, repo_fd: int, targets: Mapping[str, _GuardedRepositoryTarget]) -> None:
        self.repo_fd = repo_fd
        self.targets = MappingProxyType(dict(targets))

    @classmethod
    def capture(
        cls,
        repo_root: Path,
        relatives: tuple[str, ...],
    ) -> _RepositoryTargetGuard:
        repo_fd = open_safe_directory_descriptor(repo_root)
        targets: dict[str, _GuardedRepositoryTarget] = {}
        try:
            for relative in relatives:
                safe = _safe_repo_relative(relative)
                parent_fd = os.dup(repo_fd)
                try:
                    for part in safe.parts[:-1]:
                        next_fd = os.open(
                            part,
                            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                            dir_fd=parent_fd,
                        )
                        opened = os.fstat(next_fd)
                        if not stat.S_ISDIR(opened.st_mode):
                            raise ValueError("repository target parent is unsafe")
                        os.close(parent_fd)
                        parent_fd = next_fd
                    parent = os.fstat(parent_fd)
                    targets[relative] = _GuardedRepositoryTarget(
                        relative=relative,
                        parent_fd=parent_fd,
                        name=safe.name,
                        parent_device=parent.st_dev,
                        parent_inode=parent.st_ino,
                    )
                    parent_fd = -1
                finally:
                    if parent_fd >= 0:
                        os.close(parent_fd)
            return cls(repo_fd, targets)
        except OSError:
            for target in targets.values():
                os.close(target.parent_fd)
            os.close(repo_fd)
            raise ValueError("directory traversal rejected") from None
        except BaseException:
            for target in targets.values():
                os.close(target.parent_fd)
            os.close(repo_fd)
            raise

    def close(self) -> None:
        for target in self.targets.values():
            os.close(target.parent_fd)
        os.close(self.repo_fd)

    @property
    def parent_identities(self) -> Mapping[str, tuple[int, int]]:
        return MappingProxyType({
            relative: (target.parent_device, target.parent_inode) for relative, target in self.targets.items()
        })

    def snapshot(self, relative: str) -> FileSnapshot:
        target = self.targets[relative]
        return _snapshot_regular_file_at(target.parent_fd, target.name)

    def read(self, relative: str) -> bytes:
        snapshot = self.snapshot(relative)
        if not snapshot.existed:
            raise FileNotFoundError(relative)
        return snapshot.data

    @staticmethod
    def _new_workspace_name() -> str:
        return f".spec-dock-apply-{os.urandom(16).hex()}"

    def _create_workspace(
        self,
        target: _GuardedRepositoryTarget,
        name: str,
    ) -> _MutationWorkspace:
        os.mkdir(name, mode=0o700, dir_fd=target.parent_fd)
        descriptor = -1
        try:
            descriptor = os.open(
                name,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=target.parent_fd,
            )
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISDIR(opened.st_mode)
                or opened.st_uid != os.geteuid()
                or stat.S_IMODE(opened.st_mode) != 0o700
            ):
                raise PlanningApplyRestoreMismatch("transaction workspace is unsafe")
            os.fsync(target.parent_fd)
            return _MutationWorkspace(
                name=name,
                descriptor=descriptor,
                device=opened.st_dev,
                inode=opened.st_ino,
            )
        except BaseException:
            if descriptor >= 0:
                os.close(descriptor)
            raise

    def _open_workspace(
        self,
        target: _GuardedRepositoryTarget,
        mutation: _TargetMutation,
    ) -> _MutationWorkspace | None:
        try:
            descriptor = os.open(
                mutation.workspace_name,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=target.parent_fd,
            )
        except FileNotFoundError:
            return None
        opened = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or opened.st_uid != os.geteuid()
            or stat.S_IMODE(opened.st_mode) != 0o700
            or (opened.st_dev, opened.st_ino) != (mutation.workspace_device, mutation.workspace_inode)
        ):
            os.close(descriptor)
            raise PlanningApplyRestoreMismatch("transaction workspace identity changed")
        return _MutationWorkspace(
            name=mutation.workspace_name,
            descriptor=descriptor,
            device=opened.st_dev,
            inode=opened.st_ino,
        )

    @staticmethod
    def _workspace_entry_identity(
        workspace: _MutationWorkspace,
        name: str,
    ) -> tuple[int, int] | None:
        try:
            opened = os.stat(name, dir_fd=workspace.descriptor, follow_symlinks=False)
        except FileNotFoundError:
            return None
        return opened.st_dev, opened.st_ino

    @staticmethod
    def _remove_workspace_if_empty(
        target: _GuardedRepositoryTarget,
        workspace: _MutationWorkspace,
    ) -> None:
        with os.scandir(workspace.descriptor) as entries:
            if next(entries, None) is not None:
                raise PlanningApplyRestoreMismatch("transaction workspace contains ambiguous entries")
        os.rmdir(workspace.name, dir_fd=target.parent_fd)
        os.close(workspace.descriptor)
        os.fsync(target.parent_fd)

    def cleanup_workspace(self, mutation: _TargetMutation) -> None:
        target = self.targets[mutation.relative]
        workspace = self._open_workspace(target, mutation)
        if workspace is None:
            return
        try:
            identity = self._workspace_entry_identity(workspace, mutation.staged_name)
            if identity is not None:
                if identity != (mutation.before_device, mutation.before_inode):
                    raise PlanningApplyRestoreMismatch("transaction workspace entry identity changed")
                if _snapshot_regular_file_at(workspace.descriptor, mutation.staged_name) != mutation.before:
                    raise PlanningApplyRestoreMismatch("transaction workspace entry bytes changed")
                os.unlink(mutation.staged_name, dir_fd=workspace.descriptor)
                os.fsync(workspace.descriptor)
            self._remove_workspace_if_empty(target, workspace)
            workspace = None
        finally:
            if workspace is not None:
                os.close(workspace.descriptor)

    def resolve_workspace_intent(
        self,
        intent: _WorkspaceIntent,
        mutations: list[_TargetMutation],
    ) -> None:
        if intent.purpose == "rollback-absent":
            self._resolve_absent_workspace_intent(intent, mutations)
            return
        matching = [
            mutation
            for mutation in mutations
            if mutation.relative == intent.relative
            and mutation.workspace_name == intent.workspace_name
            and mutation.workspace_device == intent.workspace_device
            and mutation.workspace_inode == intent.workspace_inode
            and mutation.staged_name == intent.staged_name
            and mutation.staged_device == intent.staged_device
            and mutation.staged_inode == intent.staged_inode
            and (
                (intent.purpose == "forward" and mutation.phase == "prepared")
                or (intent.purpose == "rollback-existing" and mutation.phase == "rollback-prepared")
            )
        ]
        if matching:
            if len(matching) != 1:
                raise PlanningApplyRestoreMismatch("workspace intent handoff is ambiguous")
            return

        target = self.targets[intent.relative]
        try:
            descriptor = os.open(
                intent.workspace_name,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=target.parent_fd,
            )
        except FileNotFoundError:
            if intent.staged_device is not None:
                try:
                    opened = os.stat(
                        target.name,
                        dir_fd=target.parent_fd,
                        follow_symlinks=False,
                    )
                except FileNotFoundError:
                    return
                if (opened.st_dev, opened.st_ino) == (
                    intent.staged_device,
                    intent.staged_inode,
                ):
                    raise PlanningApplyRestoreMismatch("workspace intent may have been published") from None
            return
        except OSError:
            raise PlanningApplyRestoreMismatch("workspace intent object is unsafe") from None
        workspace: _MutationWorkspace | None = None
        try:
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISDIR(opened.st_mode)
                or opened.st_uid != os.geteuid()
                or stat.S_IMODE(opened.st_mode) != 0o700
                or (
                    intent.workspace_device is not None
                    and (opened.st_dev, opened.st_ino) != (intent.workspace_device, intent.workspace_inode)
                )
            ):
                raise PlanningApplyRestoreMismatch("workspace intent identity changed")
            workspace = _MutationWorkspace(
                name=intent.workspace_name,
                descriptor=descriptor,
                device=opened.st_dev,
                inode=opened.st_ino,
            )
            descriptor = -1
            with os.scandir(workspace.descriptor) as entries:
                inventory = {entry.name for entry in entries}
            if intent.workspace_device is None:
                if inventory:
                    raise PlanningApplyRestoreMismatch("unbound workspace intent is nonempty")
            elif intent.staged_device is None:
                if inventory:
                    if inventory != {intent.staged_name}:
                        raise PlanningApplyRestoreMismatch("workspace intent contains ambiguous entries")
                    staged = os.stat(
                        intent.staged_name,
                        dir_fd=workspace.descriptor,
                        follow_symlinks=False,
                    )
                    if (
                        not stat.S_ISREG(staged.st_mode)
                        or staged.st_uid != os.geteuid()
                        or stat.S_IMODE(staged.st_mode) != 0o600
                        or staged.st_size != 0
                    ):
                        raise PlanningApplyRestoreMismatch("unbound staged intent is unsafe")
                    os.unlink(intent.staged_name, dir_fd=workspace.descriptor)
                    os.fsync(workspace.descriptor)
            elif inventory:
                if inventory != {intent.staged_name}:
                    raise PlanningApplyRestoreMismatch("workspace intent contains ambiguous entries")
                staged = os.stat(
                    intent.staged_name,
                    dir_fd=workspace.descriptor,
                    follow_symlinks=False,
                )
                if (staged.st_dev, staged.st_ino) != (
                    intent.staged_device,
                    intent.staged_inode,
                ):
                    raise PlanningApplyRestoreMismatch("workspace intent staged identity changed")
                os.unlink(intent.staged_name, dir_fd=workspace.descriptor)
                os.fsync(workspace.descriptor)
            self._remove_workspace_if_empty(target, workspace)
            workspace = None
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if workspace is not None:
                os.close(workspace.descriptor)

    def _resolve_absent_workspace_intent(
        self,
        intent: _WorkspaceIntent,
        mutations: list[_TargetMutation],
    ) -> None:
        matching = [mutation for mutation in mutations if mutation.relative == intent.relative]
        if len(matching) != 1:
            raise PlanningApplyRestoreMismatch("absent rollback intent inventory changed")
        mutation = matching[0]
        if mutation.before.existed:
            raise PlanningApplyRestoreMismatch("absent rollback intent preimage changed")
        if mutation.phase == "rollback-prepared":
            if (
                mutation.workspace_name != intent.workspace_name
                or mutation.workspace_device != intent.workspace_device
                or mutation.workspace_inode != intent.workspace_inode
                or mutation.staged_name != intent.staged_name
                or mutation.staged_device != intent.staged_device
                or mutation.staged_inode != intent.staged_inode
            ):
                raise PlanningApplyRestoreMismatch("absent rollback intent handoff changed")
            return
        if mutation.phase != "published":
            raise PlanningApplyRestoreMismatch("absent rollback intent phase changed")
        if intent.workspace_device is None:
            if intent.staged_device is not None:
                raise PlanningApplyRestoreMismatch("absent rollback intent binding changed")
        elif (intent.staged_device, intent.staged_inode) != (
            mutation.after_device,
            mutation.after_inode,
        ):
            raise PlanningApplyRestoreMismatch("absent rollback target binding changed")
        current = self.snapshot(intent.relative)
        try:
            opened_target = os.stat(
                self.targets[intent.relative].name,
                dir_fd=self.targets[intent.relative].parent_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            raise PlanningApplyRestoreMismatch("absent rollback target disappeared") from None
        if current != mutation.after or (opened_target.st_dev, opened_target.st_ino) != (
            mutation.after_device,
            mutation.after_inode,
        ):
            raise PlanningApplyRestoreMismatch("absent rollback target changed")

        target = self.targets[intent.relative]
        try:
            descriptor = os.open(
                intent.workspace_name,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=target.parent_fd,
            )
        except FileNotFoundError:
            return
        except OSError:
            raise PlanningApplyRestoreMismatch("absent rollback workspace is unsafe") from None
        workspace: _MutationWorkspace | None = None
        try:
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISDIR(opened.st_mode)
                or opened.st_uid != os.geteuid()
                or stat.S_IMODE(opened.st_mode) != 0o700
                or (
                    intent.workspace_device is not None
                    and (opened.st_dev, opened.st_ino) != (intent.workspace_device, intent.workspace_inode)
                )
            ):
                raise PlanningApplyRestoreMismatch("absent rollback workspace identity changed")
            workspace = _MutationWorkspace(
                name=intent.workspace_name,
                descriptor=descriptor,
                device=opened.st_dev,
                inode=opened.st_ino,
            )
            descriptor = -1
            with os.scandir(workspace.descriptor) as entries:
                if next(entries, None) is not None:
                    raise PlanningApplyRestoreMismatch("absent rollback workspace is nonempty")
            self._remove_workspace_if_empty(target, workspace)
            workspace = None
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if workspace is not None:
                os.close(workspace.descriptor)

    def compare_replace(
        self,
        relative: str,
        *,
        expected: FileSnapshot,
        replacement: bytes,
        mode: int,
        prepare: Callable[[_TargetMutation], None] | None = None,
        publish: Callable[[_TargetMutation], None] | None = None,
        discard: Callable[[_TargetMutation], None] | None = None,
        workspace_intent_update: Callable[[_WorkspaceIntent | None], None] | None = None,
        workspace_purpose: Literal["forward", "rollback-existing"] = "forward",
    ) -> _TargetMutation | None:
        replacement_snapshot = FileSnapshot(
            existed=True,
            data=replacement,
            mode=mode,
            sha256=hashlib.sha256(replacement).hexdigest(),
        )
        if expected == replacement_snapshot:
            if self.snapshot(relative) != expected:
                raise _ApplyTargetDrift(relative)
            return None
        target = self.targets[relative]
        workspace_name = self._new_workspace_name()
        intent = _WorkspaceIntent(
            relative=relative,
            purpose=workspace_purpose,
            workspace_name=workspace_name,
            workspace_device=None,
            workspace_inode=None,
            staged_name="staged",
            staged_device=None,
            staged_inode=None,
        )
        if workspace_intent_update is not None:
            if prepare is None:
                raise PlanningApplyRestoreMismatch("workspace intent requires mutation handoff")
            workspace_intent_update(intent)
        workspace = self._create_workspace(target, workspace_name)
        intent = dataclass_replace(
            intent,
            workspace_device=workspace.device,
            workspace_inode=workspace.inode,
        )
        if workspace_intent_update is not None:
            workspace_intent_update(intent)
        workspace_to_close: _MutationWorkspace | None = workspace
        staged_name = "staged"
        staged_fd = -1
        current_fd = -1
        prepared: _TargetMutation | None = None
        try:
            staged_fd = os.open(
                staged_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=workspace.descriptor,
            )
            os.fsync(workspace.descriptor)
            staged_identity = os.fstat(staged_fd)
            intent = dataclass_replace(
                intent,
                staged_device=staged_identity.st_dev,
                staged_inode=staged_identity.st_ino,
            )
            if workspace_intent_update is not None:
                workspace_intent_update(intent)
            os.fchmod(staged_fd, mode)
            _write_all(staged_fd, replacement)
            os.fsync(staged_fd)
            before_device: int | None = None
            before_inode: int | None = None
            if expected.existed:
                try:
                    current_fd = os.open(
                        target.name,
                        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                        dir_fd=target.parent_fd,
                    )
                except OSError as error:
                    if error.errno in {errno.ENOENT, errno.ELOOP, errno.ENOTDIR}:
                        raise _ApplyTargetDrift(relative) from None
                    raise
                current_identity = os.fstat(current_fd)
                if not stat.S_ISREG(current_identity.st_mode):
                    raise PlanningApplyRestoreMismatch("transaction exchange ownership changed")
                before_device = current_identity.st_dev
                before_inode = current_identity.st_ino
            prepared = _TargetMutation(
                relative=relative,
                before=expected,
                after=replacement_snapshot,
                phase="prepared",
                workspace_name=workspace.name,
                workspace_device=workspace.device,
                workspace_inode=workspace.inode,
                staged_name=staged_name,
                staged_device=staged_identity.st_dev,
                staged_inode=staged_identity.st_ino,
                before_device=before_device,
                before_inode=before_inode,
                after_device=staged_identity.st_dev,
                after_inode=staged_identity.st_ino,
            )
            if prepare is not None:
                prepare(prepared)
            if workspace_intent_update is not None:
                workspace_intent_update(None)
            if expected.existed:
                _exchange_entries_at(
                    workspace.descriptor,
                    staged_name,
                    target.parent_fd,
                    target.name,
                )
                displaced_identity = os.stat(
                    staged_name,
                    dir_fd=workspace.descriptor,
                    follow_symlinks=False,
                )
                displaced_snapshot = _snapshot_regular_file_at(workspace.descriptor, staged_name)
                published_identity = os.stat(
                    target.name,
                    dir_fd=target.parent_fd,
                    follow_symlinks=False,
                )
                published_snapshot = self.snapshot(relative)
                target_is_staged = (
                    published_identity.st_dev,
                    published_identity.st_ino,
                ) == (staged_identity.st_dev, staged_identity.st_ino)
                displaced_is_opened = (
                    displaced_identity.st_dev,
                    displaced_identity.st_ino,
                ) == (before_device, before_inode)
                if not target_is_staged or published_snapshot != replacement_snapshot:
                    raise PlanningApplyRestoreMismatch("transaction exchange ownership changed")
                if not displaced_is_opened or displaced_snapshot != expected:
                    current_published = os.stat(
                        target.name,
                        dir_fd=target.parent_fd,
                        follow_symlinks=False,
                    )
                    current_displaced = os.stat(
                        staged_name,
                        dir_fd=workspace.descriptor,
                        follow_symlinks=False,
                    )
                    if (
                        (current_published.st_dev, current_published.st_ino)
                        != (staged_identity.st_dev, staged_identity.st_ino)
                        or self.snapshot(relative) != replacement_snapshot
                        or (current_displaced.st_dev, current_displaced.st_ino)
                        != (displaced_identity.st_dev, displaced_identity.st_ino)
                        or _snapshot_regular_file_at(workspace.descriptor, staged_name) != displaced_snapshot
                    ):
                        raise PlanningApplyRestoreMismatch("transaction exchange continuity changed")
                    _exchange_entries_at(
                        workspace.descriptor,
                        staged_name,
                        target.parent_fd,
                        target.name,
                    )
                    os.fsync(workspace.descriptor)
                    os.fsync(target.parent_fd)
                    restored = os.stat(
                        target.name,
                        dir_fd=target.parent_fd,
                        follow_symlinks=False,
                    )
                    restored_staged = os.stat(
                        staged_name,
                        dir_fd=workspace.descriptor,
                        follow_symlinks=False,
                    )
                    if (
                        (restored.st_dev, restored.st_ino) != (displaced_identity.st_dev, displaced_identity.st_ino)
                        or self.snapshot(relative) != displaced_snapshot
                        or (restored_staged.st_dev, restored_staged.st_ino)
                        != (staged_identity.st_dev, staged_identity.st_ino)
                        or _snapshot_regular_file_at(workspace.descriptor, staged_name) != replacement_snapshot
                    ):
                        raise PlanningApplyRestoreMismatch("transaction exchange-back mismatch")
                    os.unlink(staged_name, dir_fd=workspace.descriptor)
                    os.fsync(workspace.descriptor)
                    self._remove_workspace_if_empty(target, workspace)
                    workspace_to_close = None
                    if discard is not None:
                        discard(prepared)
                    raise _ApplyTargetDrift(relative)
            else:
                try:
                    _rename_no_replace_at(
                        workspace.descriptor,
                        staged_name,
                        target.parent_fd,
                        target.name,
                    )
                except FileExistsError:
                    staged_now = self._workspace_entry_identity(workspace, staged_name)
                    if staged_now != (staged_identity.st_dev, staged_identity.st_ino):
                        raise PlanningApplyRestoreMismatch("transaction staged identity changed") from None
                    os.unlink(staged_name, dir_fd=workspace.descriptor)
                    os.fsync(workspace.descriptor)
                    self._remove_workspace_if_empty(target, workspace)
                    workspace_to_close = None
                    if discard is not None:
                        discard(prepared)
                    raise _ApplyTargetDrift(relative) from None
            observed = os.stat(
                target.name,
                dir_fd=target.parent_fd,
                follow_symlinks=False,
            )
            if (observed.st_dev, observed.st_ino) != (staged_identity.st_dev, staged_identity.st_ino) or self.snapshot(
                relative
            ) != replacement_snapshot:
                raise PlanningApplyRestoreMismatch("transaction target publication mismatch")
            published = dataclass_replace(prepared, phase="published")
            if publish is not None:
                publish(published)
            if expected.existed:
                if self._workspace_entry_identity(workspace, staged_name) != (before_device, before_inode):
                    raise PlanningApplyRestoreMismatch("transaction displaced identity changed")
                os.unlink(staged_name, dir_fd=workspace.descriptor)
                os.fsync(workspace.descriptor)
            self._remove_workspace_if_empty(target, workspace)
            workspace_to_close = None
            os.fsync(target.parent_fd)
            return published
        finally:
            if current_fd >= 0:
                os.close(current_fd)
            if staged_fd >= 0:
                os.close(staged_fd)
            if workspace_to_close is not None:
                os.close(workspace_to_close.descriptor)

    def restore(
        self,
        mutation: _TargetMutation,
        *,
        phase_update: Callable[[_TargetMutation], None] | None = None,
        workspace_intent_update: Callable[[_WorkspaceIntent | None], None] | None = None,
    ) -> None:
        target = self.targets[mutation.relative]
        if mutation.phase == "rollback-prepared":
            if mutation.before.existed:
                self._resume_existing_restore(target, mutation)
            else:
                self._resume_absent_restore(target, mutation)
            return
        current_snapshot = self.snapshot(mutation.relative)
        if current_snapshot == mutation.before:
            return
        try:
            observed = os.stat(
                target.name,
                dir_fd=target.parent_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            raise PlanningApplyRestoreMismatch("transaction-owned target disappeared") from None
        if (observed.st_dev, observed.st_ino) != (mutation.after_device, mutation.after_inode) or self.snapshot(
            mutation.relative
        ) != mutation.after:
            raise PlanningApplyRestoreMismatch("transaction-owned target changed")
        if mutation.before.existed:

            def prepare_reverse(reverse: _TargetMutation) -> None:
                rollback = dataclass_replace(
                    mutation,
                    phase="rollback-prepared",
                    workspace_name=reverse.workspace_name,
                    workspace_device=reverse.workspace_device,
                    workspace_inode=reverse.workspace_inode,
                    staged_name=reverse.staged_name,
                    staged_device=reverse.staged_device,
                    staged_inode=reverse.staged_inode,
                )
                if phase_update is not None:
                    phase_update(rollback)

            def discard_reverse(_reverse: _TargetMutation) -> None:
                if phase_update is not None:
                    phase_update(mutation)

            restored = self.compare_replace(
                mutation.relative,
                expected=mutation.after,
                replacement=mutation.before.data,
                mode=mutation.before.mode,
                prepare=prepare_reverse,
                discard=discard_reverse,
                workspace_intent_update=workspace_intent_update,
                workspace_purpose="rollback-existing",
            )
            if restored is None or self.snapshot(mutation.relative) != mutation.before:
                raise PlanningApplyRestoreMismatch("transaction target restore mismatch")
        else:
            if (phase_update is None) != (workspace_intent_update is None):
                raise PlanningApplyRestoreMismatch("absent rollback journal callbacks are incomplete")
            workspace_name = self._new_workspace_name()
            if workspace_intent_update is not None:
                workspace_intent_update(
                    _WorkspaceIntent(
                        relative=mutation.relative,
                        purpose="rollback-absent",
                        workspace_name=workspace_name,
                        workspace_device=None,
                        workspace_inode=None,
                        staged_name="quarantine",
                        staged_device=None,
                        staged_inode=None,
                    )
                )
            workspace = self._create_workspace(target, workspace_name)
            try:
                if workspace_intent_update is not None:
                    workspace_intent_update(
                        _WorkspaceIntent(
                            relative=mutation.relative,
                            purpose="rollback-absent",
                            workspace_name=workspace.name,
                            workspace_device=workspace.device,
                            workspace_inode=workspace.inode,
                            staged_name="quarantine",
                            staged_device=mutation.after_device,
                            staged_inode=mutation.after_inode,
                        )
                    )
                rollback = dataclass_replace(
                    mutation,
                    phase="rollback-prepared",
                    workspace_name=workspace.name,
                    workspace_device=workspace.device,
                    workspace_inode=workspace.inode,
                    staged_name="quarantine",
                    staged_device=mutation.after_device,
                    staged_inode=mutation.after_inode,
                )
                if phase_update is not None:
                    phase_update(rollback)
                if workspace_intent_update is not None:
                    workspace_intent_update(None)
            finally:
                os.close(workspace.descriptor)
            self._resume_absent_restore(target, rollback)

    def _resume_existing_restore(
        self,
        target: _GuardedRepositoryTarget,
        mutation: _TargetMutation,
    ) -> None:
        workspace = self._open_workspace(target, mutation)
        try:
            current = self.snapshot(mutation.relative)
            try:
                opened = os.stat(
                    target.name,
                    dir_fd=target.parent_fd,
                    follow_symlinks=False,
                )
                current_identity = (opened.st_dev, opened.st_ino)
            except FileNotFoundError:
                current_identity = None
            target_is_after = current == mutation.after and current_identity == (
                mutation.after_device,
                mutation.after_inode,
            )
            target_is_before = current == mutation.before and current_identity == (
                mutation.staged_device,
                mutation.staged_inode,
            )
            if workspace is None:
                if target_is_before:
                    return
                raise PlanningApplyRestoreMismatch("rollback workspace disappeared")
            active_workspace = workspace

            def workspace_entries() -> set[str]:
                with os.scandir(active_workspace.descriptor) as entries:
                    return {entry.name for entry in entries}

            staged_identity = self._workspace_entry_identity(workspace, mutation.staged_name)
            if target_is_after:
                if (
                    staged_identity != (mutation.staged_device, mutation.staged_inode)
                    or workspace_entries() != {mutation.staged_name}
                    or _snapshot_regular_file_at(workspace.descriptor, mutation.staged_name) != mutation.before
                ):
                    raise PlanningApplyRestoreMismatch("rollback staged preimage changed")
                _exchange_entries_at(
                    workspace.descriptor,
                    mutation.staged_name,
                    target.parent_fd,
                    target.name,
                )
                os.fsync(workspace.descriptor)
                os.fsync(target.parent_fd)
                current = self.snapshot(mutation.relative)
                try:
                    opened = os.stat(
                        target.name,
                        dir_fd=target.parent_fd,
                        follow_symlinks=False,
                    )
                except FileNotFoundError:
                    raise PlanningApplyRestoreMismatch("rollback target disappeared") from None
                target_is_before = current == mutation.before and (opened.st_dev, opened.st_ino) == (
                    mutation.staged_device,
                    mutation.staged_inode,
                )
                staged_identity = self._workspace_entry_identity(workspace, mutation.staged_name)
            if not target_is_before:
                raise PlanningApplyRestoreMismatch("rollback target state is ambiguous")
            if staged_identity is None:
                if workspace_entries():
                    raise PlanningApplyRestoreMismatch("rollback workspace contains ambiguous entries")
                self._remove_workspace_if_empty(target, workspace)
                workspace = None
                return
            if (
                staged_identity != (mutation.after_device, mutation.after_inode)
                or workspace_entries() != {mutation.staged_name}
                or _snapshot_regular_file_at(workspace.descriptor, mutation.staged_name) != mutation.after
            ):
                raise PlanningApplyRestoreMismatch("rollback displaced target changed")
            os.unlink(mutation.staged_name, dir_fd=workspace.descriptor)
            os.fsync(workspace.descriptor)
            if workspace_entries():
                raise PlanningApplyRestoreMismatch("rollback workspace contains ambiguous entries")
            self._remove_workspace_if_empty(target, workspace)
            workspace = None
        finally:
            if workspace is not None:
                os.close(workspace.descriptor)

    def resolve_prepared(self, mutation: _TargetMutation) -> _TargetMutation | None:
        if mutation.phase != "prepared":
            return mutation
        target = self.targets[mutation.relative]
        target_snapshot = self.snapshot(mutation.relative)
        workspace = self._open_workspace(target, mutation)
        try:
            staged_identity = (
                None if workspace is None else self._workspace_entry_identity(workspace, mutation.staged_name)
            )
            if target_snapshot == mutation.before:
                if workspace is None:
                    return None
                if staged_identity != (mutation.staged_device, mutation.staged_inode):
                    raise PlanningApplyRestoreMismatch("prepared mutation workspace mismatch")
                if _snapshot_regular_file_at(workspace.descriptor, mutation.staged_name) != mutation.after:
                    raise PlanningApplyRestoreMismatch("prepared mutation staged bytes changed")
                os.unlink(mutation.staged_name, dir_fd=workspace.descriptor)
                os.fsync(workspace.descriptor)
                self._remove_workspace_if_empty(target, workspace)
                workspace = None
                return None
            try:
                target_stat = os.stat(
                    target.name,
                    dir_fd=target.parent_fd,
                    follow_symlinks=False,
                )
            except FileNotFoundError:
                raise PlanningApplyRestoreMismatch("prepared mutation target disappeared") from None
            if target_snapshot == mutation.after and (target_stat.st_dev, target_stat.st_ino) == (
                mutation.staged_device,
                mutation.staged_inode,
            ):
                if not mutation.before.existed:
                    if workspace is None:
                        raise PlanningApplyRestoreMismatch("prepared mutation workspace missing")
                    if staged_identity is not None:
                        raise PlanningApplyRestoreMismatch("prepared mutation workspace slot changed")
                elif workspace is not None:
                    if staged_identity != (mutation.before_device, mutation.before_inode):
                        raise PlanningApplyRestoreMismatch("prepared mutation displaced identity changed")
                    if _snapshot_regular_file_at(workspace.descriptor, mutation.staged_name) != mutation.before:
                        raise PlanningApplyRestoreMismatch("prepared mutation displaced bytes changed")
                return dataclass_replace(mutation, phase="published")
            raise PlanningApplyRestoreMismatch("prepared mutation state is ambiguous")
        finally:
            if workspace is not None:
                os.close(workspace.descriptor)

    def _resume_absent_restore(
        self,
        target: _GuardedRepositoryTarget,
        mutation: _TargetMutation,
    ) -> None:
        workspace = self._open_workspace(target, mutation)
        if workspace is None:
            if self.snapshot(mutation.relative) == mutation.before:
                return
            raise PlanningApplyRestoreMismatch("rollback workspace disappeared")
        try:
            current = self.snapshot(mutation.relative)
            quarantined = self._workspace_entry_identity(workspace, mutation.staged_name)
            if current == mutation.before:
                if quarantined is None:
                    self._remove_workspace_if_empty(target, workspace)
                    workspace = None
                    return
                if quarantined != (mutation.after_device, mutation.after_inode):
                    raise PlanningApplyRestoreMismatch("rollback quarantine identity changed")
                if _snapshot_regular_file_at(workspace.descriptor, mutation.staged_name) != mutation.after:
                    raise PlanningApplyRestoreMismatch("rollback quarantine bytes changed")
            elif current == mutation.after:
                _rename_no_replace_at(
                    target.parent_fd,
                    target.name,
                    workspace.descriptor,
                    mutation.staged_name,
                )
                current = self.snapshot(mutation.relative)
                quarantined = self._workspace_entry_identity(workspace, mutation.staged_name)
                if current != mutation.before:
                    if quarantined == (mutation.after_device, mutation.after_inode):
                        with suppress(FileExistsError):
                            _rename_no_replace_at(
                                workspace.descriptor,
                                mutation.staged_name,
                                target.parent_fd,
                                target.name,
                            )
                    raise PlanningApplyRestoreMismatch("rollback absence was not established")
                if quarantined != (mutation.after_device, mutation.after_inode):
                    if quarantined is not None:
                        with suppress(FileExistsError):
                            _rename_no_replace_at(
                                workspace.descriptor,
                                mutation.staged_name,
                                target.parent_fd,
                                target.name,
                            )
                    raise PlanningApplyRestoreMismatch("rollback quarantine identity changed")
                if _snapshot_regular_file_at(workspace.descriptor, mutation.staged_name) != mutation.after:
                    raise PlanningApplyRestoreMismatch("rollback quarantine bytes changed")
            else:
                raise PlanningApplyRestoreMismatch("transaction-owned target changed")
            os.unlink(mutation.staged_name, dir_fd=workspace.descriptor)
            os.fsync(workspace.descriptor)
            self._remove_workspace_if_empty(target, workspace)
            workspace = None
            os.fsync(target.parent_fd)
        finally:
            if workspace is not None:
                os.close(workspace.descriptor)


@dataclass(frozen=True)
class ExpectedPlanningTargets:
    documents: Mapping[str, bytes]
    blob_oids: Mapping[str, str]


@dataclass(frozen=True)
class PlanningApplyExecution:
    status: PlanningApplyStatus
    reason: str
    operation_id: str
    decision_artifact_path: str | None = None
    local_commit: str | None = None
    local_tree: str | None = None
    remote_commit: str | None = None
    details: tuple[str, ...] = ()

    @property
    def is_ready(self) -> bool:
        return self.status == "ready" and self.reason == "adoption_published"

    def to_output(self) -> dict[str, object]:
        return {
            "operation_id": self.operation_id,
            "decision_artifact_path": self.decision_artifact_path,
            "local_commit": self.local_commit,
            "local_tree": self.local_tree,
            "remote_commit": self.remote_commit,
        }


@dataclass(frozen=True)
class PlanningApplyOperation:
    operation_id: str
    operation_core_bytes: bytes = field(repr=False)
    issue_id: str
    mode: Literal["archive-candidate", "git-bound"]
    repository: str
    branch: str
    expected_head: str
    reviewed_identity: ReviewedPlanningIdentity
    reviewed_identity_sha256: str
    review_result_sha256: str
    human_decision_sha256: str
    decision: Literal["approved", "rejected"]
    canonical_target_paths: tuple[str, str, str]
    pre_apply_target_blob_oids: Mapping[str, str]
    candidate_identity: IssueCandidateIdentity | None
    git_bound_operation_binding_sha256: str | None
    companion_target_path: str
    companion_sha256: str
    decision_artifact_path: str
    human_decision_bytes: bytes = field(repr=False)
    replacement_documents: Mapping[str, bytes] = field(repr=False)
    replacement_companion: bytes | None = field(repr=False)
    pre_apply_document_bytes: Mapping[str, bytes] = field(repr=False)

    @classmethod
    def create(
        cls,
        *,
        issue_id: str,
        mode: Literal["archive-candidate", "git-bound"],
        repository: str,
        branch: str,
        expected_head: str,
        reviewed_identity: ReviewedPlanningIdentity,
        reviewed_identity_sha256: str,
        review_result_sha256: str,
        human_decision_sha256: str,
        decision: Literal["approved", "rejected"],
        canonical_target_paths: tuple[str, str, str],
        pre_apply_target_blob_oids: Mapping[str, str],
        candidate_identity: IssueCandidateIdentity | None,
        git_bound_operation_binding_sha256: str | None,
        companion_target_path: str | None,
        companion_sha256: str | None,
        decision_artifact_path: str,
        human_decision_bytes: bytes,
        replacement_documents: Mapping[str, bytes],
        replacement_companion: bytes | None,
        pre_apply_document_bytes: Mapping[str, bytes],
    ) -> PlanningApplyOperation:
        if mode not in ("archive-candidate", "git-bound"):
            raise ValueError("invalid planning apply mode")
        if decision not in ("approved", "rejected"):
            raise ValueError("invalid planning decision")
        if _SHA40.fullmatch(expected_head) is None:
            raise ValueError("expected_head must be lowercase SHA-1")
        for digest in (
            reviewed_identity_sha256,
            review_result_sha256,
            human_decision_sha256,
        ):
            if _SHA256.fullmatch(digest) is None:
                raise ValueError("planning apply digest must be lowercase SHA-256")
        if reviewed_identity.sha256 != reviewed_identity_sha256:
            raise ValueError("reviewed identity digest mismatch")
        if candidate_identity is None:
            raise ValueError("planning apply requires Candidate identity")
        if (
            reviewed_identity.mode != mode
            or reviewed_identity.issue_id != issue_id
            or reviewed_identity.repository != repository
            or reviewed_identity.branch != branch
            or reviewed_identity.source_head != expected_head
        ):
            raise ValueError("reviewed identity does not match apply target")
        if tuple(sorted(canonical_target_paths, key=lambda value: value.encode())) != tuple(canonical_target_paths):
            raise ValueError("canonical target paths must be byte-sorted")
        for path in canonical_target_paths:
            _safe_repo_relative(path)
        if companion_target_path is None or companion_sha256 is None:
            raise ValueError("planning apply requires companion evidence")
        companion_path = _safe_repo_relative(companion_target_path).as_posix()
        issue_dir = PurePosixPath(canonical_target_paths[0]).parent
        if (
            PurePosixPath(companion_path).parent != issue_dir / "artifacts"
            or PurePosixPath(companion_path).suffix != ".md"
        ):
            raise ValueError("companion target must be beneath the Issue artifacts directory")
        if _SHA256.fullmatch(companion_sha256) is None:
            raise ValueError("companion SHA must be lowercase SHA-256")
        if mode == "git-bound":
            binding = reviewed_identity.git_bound_operation_binding
            if (
                git_bound_operation_binding_sha256 is None
                or _SHA256.fullmatch(git_bound_operation_binding_sha256) is None
                or binding is None
                or binding.binding_sha256 != git_bound_operation_binding_sha256
                or binding.candidate_identity != candidate_identity
                or binding.onboarding_companion.path != PurePosixPath(companion_path).relative_to(issue_dir).as_posix()
                or binding.onboarding_companion.sha256 != companion_sha256
                or reviewed_identity.canonical_target_paths != canonical_target_paths
            ):
                raise ValueError("git-bound operation binding mismatch")
        elif (
            git_bound_operation_binding_sha256 is not None or reviewed_identity.candidate_identity != candidate_identity
        ):
            raise ValueError("archive apply Candidate identity mismatch")
        if (
            set(pre_apply_target_blob_oids) != set(canonical_target_paths)
            or set(pre_apply_document_bytes) != set(DOCUMENT_NAMES)
            or any(_SHA40.fullmatch(value) is None for value in pre_apply_target_blob_oids.values())
            or any(
                PurePosixPath(path).name not in pre_apply_document_bytes
                or _git_blob_oid(pre_apply_document_bytes[PurePosixPath(path).name]) != pre_apply_target_blob_oids[path]
                for path in canonical_target_paths
            )
            or hashlib.sha256(human_decision_bytes).hexdigest() != human_decision_sha256
        ):
            raise ValueError("planning apply preimage evidence mismatch")
        expected_documents = set(DOCUMENT_NAMES) if decision == "approved" and mode == "archive-candidate" else set()
        if set(replacement_documents) != expected_documents:
            raise ValueError("replacement document inventory does not match apply mode")
        if (replacement_companion is not None) != (decision == "approved"):
            raise ValueError("replacement companion does not match Human decision")
        if replacement_companion is not None and hashlib.sha256(replacement_companion).hexdigest() != companion_sha256:
            raise ValueError("replacement companion SHA mismatch")
        core: dict[str, object] = {
            "schema_version": _OPERATION_SCHEMA,
            "issue_id": issue_id,
            "mode": mode,
            "repository": repository,
            "branch": branch,
            "expected_head": expected_head,
            "reviewed_identity": reviewed_identity.to_dict(),
            "reviewed_identity_sha256": reviewed_identity_sha256,
            "review_result_sha256": review_result_sha256,
            "human_decision_sha256": human_decision_sha256,
            "decision": decision,
            "canonical_target_paths": list(canonical_target_paths),
            "pre_apply_target_blob_oids": dict(
                sorted(pre_apply_target_blob_oids.items(), key=lambda item: item[0].encode())
            ),
            "candidate_identity": (None if candidate_identity is None else candidate_identity.to_dict()),
            "git_bound_operation_binding_sha256": git_bound_operation_binding_sha256,
            "companion_target_path": companion_path,
            "companion_sha256": companion_sha256,
            "replacement_companion_present": replacement_companion is not None,
        }
        core_bytes = _canonical_json_bytes(core)
        operation_id = hashlib.sha256(core_bytes).hexdigest()
        artifact = PurePosixPath(decision_artifact_path)
        _safe_repo_relative(artifact.as_posix())
        timestamp = artifact.name[:16]
        if re.fullmatch(r"[0-9]{8}t[0-9]{6}z", timestamp) is None:
            raise ValueError("decision artifact requires a UTC timestamp prefix")
        artifact_name = f"{timestamp}-planning-human-decision-{operation_id[:16]}.json"
        deterministic_artifact = artifact.with_name(artifact_name).as_posix()
        return cls(
            operation_id=operation_id,
            operation_core_bytes=core_bytes,
            issue_id=issue_id,
            mode=mode,
            repository=repository,
            branch=branch,
            expected_head=expected_head,
            reviewed_identity=reviewed_identity,
            reviewed_identity_sha256=reviewed_identity_sha256,
            review_result_sha256=review_result_sha256,
            human_decision_sha256=human_decision_sha256,
            decision=decision,
            canonical_target_paths=canonical_target_paths,
            pre_apply_target_blob_oids=MappingProxyType(dict(pre_apply_target_blob_oids)),
            candidate_identity=candidate_identity,
            git_bound_operation_binding_sha256=git_bound_operation_binding_sha256,
            companion_target_path=companion_path,
            companion_sha256=companion_sha256,
            decision_artifact_path=deterministic_artifact,
            human_decision_bytes=bytes(human_decision_bytes),
            replacement_documents=MappingProxyType(dict(replacement_documents)),
            replacement_companion=(None if replacement_companion is None else bytes(replacement_companion)),
            pre_apply_document_bytes=MappingProxyType(dict(pre_apply_document_bytes)),
        )


def _canonical_json_bytes(value: Mapping[str, object]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _safe_repo_relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError("unsafe repository-relative path")
    return path


def validate_planning_git_argv(argv: tuple[str, ...]) -> None:
    if not argv or argv[0] != "git":
        raise PlanningApplyUnsafeGitCommand("planning Git argv must start with git")
    if any(word in _PROHIBITED_GIT_WORDS or word.startswith("--force-with-lease") for word in argv[1:]):
        raise PlanningApplyUnsafeGitCommand("prohibited planning Git operation")
    if argv[1:2] == ("update-ref",):
        raise PlanningApplyUnsafeGitCommand("custom Git refs are prohibited")
    if argv[1:2] == ("push",) and any(word.startswith("+") or word.startswith(":") for word in argv[2:]):
        raise PlanningApplyUnsafeGitCommand("non-fast-forward Git push is prohibited")


def snapshot_regular_file(path: Path) -> FileSnapshot:
    try:
        opened = path.stat(follow_symlinks=False)
    except FileNotFoundError:
        return FileSnapshot(existed=False, data=b"", mode=0, sha256=hashlib.sha256(b"").hexdigest())
    if not stat.S_ISREG(opened.st_mode):
        raise ValueError("transaction target must be a regular non-symlink file")
    data = path.read_bytes()
    return FileSnapshot(
        existed=True,
        data=data,
        mode=stat.S_IMODE(opened.st_mode),
        sha256=hashlib.sha256(data).hexdigest(),
    )


def _snapshot_regular_file_at(parent_fd: int, name: str) -> FileSnapshot:
    descriptor = -1
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
    except FileNotFoundError:
        return FileSnapshot(
            existed=False,
            data=b"",
            mode=0,
            sha256=hashlib.sha256(b"").hexdigest(),
        )
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise ValueError("transaction target must be a regular non-symlink file")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        data = b"".join(chunks)
        current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
            raise ValueError("transaction target identity changed during snapshot")
        return FileSnapshot(
            existed=True,
            data=data,
            mode=stat.S_IMODE(opened.st_mode),
            sha256=hashlib.sha256(data).hexdigest(),
        )
    finally:
        os.close(descriptor)


def _exchange_entries_at(
    source_fd: int,
    first: str,
    destination_fd: int,
    second: str,
) -> None:
    if sys.platform.startswith("linux"):
        _exchange_entries_linux_at(source_fd, first, destination_fd, second)
    elif sys.platform == "darwin":
        _exchange_entries_darwin_at(source_fd, first, destination_fd, second)
    else:
        raise NotImplementedError("atomic exchange is unavailable")


def _exchange_entries_linux_at(
    source_fd: int,
    first: str,
    destination_fd: int,
    second: str,
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
        source_fd,
        os.fsencode(first),
        destination_fd,
        os.fsencode(second),
        0x00000002,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), second)


def _exchange_entries_darwin_at(
    source_fd: int,
    first: str,
    destination_fd: int,
    second: str,
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
        source_fd,
        os.fsencode(first),
        destination_fd,
        os.fsencode(second),
        0x00000002,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), second)


def _rename_no_replace_at(
    source_fd: int,
    source_name: str,
    destination_fd: int,
    destination_name: str,
) -> None:
    if sys.platform.startswith("linux"):
        _rename_no_replace_linux_at(
            source_fd,
            source_name,
            destination_fd,
            destination_name,
        )
    elif sys.platform == "darwin":
        _rename_no_replace_darwin_at(
            source_fd,
            source_name,
            destination_fd,
            destination_name,
        )
    else:
        raise NotImplementedError("atomic no-replace rename is unavailable")


def _rename_no_replace_linux_at(
    source_fd: int,
    source_name: str,
    destination_fd: int,
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
        source_fd,
        os.fsencode(source_name),
        destination_fd,
        os.fsencode(destination_name),
        0x00000001,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise FileExistsError(
            error_number,
            os.strerror(error_number),
            destination_name,
        )
    raise OSError(error_number, os.strerror(error_number), destination_name)


def _rename_no_replace_darwin_at(
    source_fd: int,
    source_name: str,
    destination_fd: int,
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
        source_fd,
        os.fsencode(source_name),
        destination_fd,
        os.fsencode(destination_name),
        0x00000004,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise FileExistsError(
            error_number,
            os.strerror(error_number),
            destination_name,
        )
    raise OSError(error_number, os.strerror(error_number), destination_name)


def restore_regular_file(path: Path, snapshot: FileSnapshot) -> None:
    if snapshot.existed:
        _atomic_write_exact(path, snapshot.data, mode=snapshot.mode)
        restored = snapshot_regular_file(path)
        if restored != snapshot:
            raise PlanningApplyRestoreMismatch("file restore mismatch")
    else:
        if path.exists() or path.is_symlink():
            path.unlink()
        if path.exists() or path.is_symlink():
            raise PlanningApplyRestoreMismatch("file absence restore mismatch")


def _atomic_write_exact(path: Path, data: bytes, *, mode: int) -> None:
    parent = path.parent
    if parent.is_symlink() or not parent.is_dir():
        raise ValueError("transaction parent must be an existing safe directory")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=parent)
    temp_path = Path(temporary)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temp_path.replace(path)
        directory_descriptor = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _git_index_path(repo_root: Path) -> Path:
    result = _run_git(repo_root, ("rev-parse", "--git-path", "index"))
    if result.returncode != 0:
        raise ValueError("Git index cannot be resolved")
    value = result.stdout.decode("utf-8", errors="strict").strip()
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def snapshot_git_index(repo_root: Path) -> GitIndexSnapshot:
    path = _git_index_path(repo_root)
    snapshot = snapshot_regular_file(path)
    if not snapshot.existed:
        raise ValueError("Git index must exist before planning apply")
    return GitIndexSnapshot(
        path=path,
        data=snapshot.data,
        mode=snapshot.mode,
        sha256=snapshot.sha256,
    )


def restore_git_index(repo_root: Path, snapshot: GitIndexSnapshot) -> None:
    if _git_index_path(repo_root).resolve() != snapshot.path.resolve():
        raise PlanningApplyRestoreMismatch("Git index path changed")
    _atomic_write_exact(snapshot.path, snapshot.data, mode=snapshot.mode)
    if snapshot_git_index(repo_root) != snapshot:
        raise PlanningApplyRestoreMismatch("Git index restore mismatch")


def record_planning_apply_operation(
    operation: PlanningApplyOperation,
    *,
    output_guard: OutputDirectoryGuard | None = None,
    output_dir: Path | None = None,
    capture_hook: Callable[[str], None] | None = None,
) -> _ApplyEvidenceHandle:
    output_guard = output_guard or _guard_from_current_output(output_dir)
    output_fd = _open_guarded_output(output_guard)
    operation_name = f"planning-apply-{operation.operation_id}"
    try:
        if capture_hook is not None:
            capture_hook("after_output_capture")
        try:
            os.mkdir(operation_name, mode=0o700, dir_fd=output_fd)
            created = True
        except FileExistsError:
            created = False
        operation_fd = _open_directory_at(output_fd, operation_name)
        handle = _ApplyEvidenceHandle(
            output_fd=output_fd,
            operation_fd=operation_fd,
            logical_operation_path=output_guard.path / operation_name,
        )
        try:
            if not _owned_private_directory_at(output_fd, operation_name):
                raise PlanningApplyOutputRejected("operation identity collision")
            if created:
                _write_private_no_replace_at(handle, "operation.json", operation.operation_core_bytes)
                _mkdir_private_at(handle, "attempts")
                _set_operation_state(handle, operation, "OPERATION_RECORDED")
                return handle
            _validate_existing_operation_evidence(handle)
            if _read_private_file_at(handle, "operation.json") != operation.operation_core_bytes:
                raise PlanningApplyOutputRejected("operation identity collision")
            state_bytes = _read_private_file_at(handle, "state.json")
            try:
                state = json.loads(state_bytes)
            except (ValueError, json.JSONDecodeError):
                raise PlanningApplyOutputRejected("operation evidence is incomplete") from None
            if (
                not isinstance(state, dict)
                or set(state) != {"operation_id", "state"}
                or state.get("operation_id") != operation.operation_id
                or _canonical_json_bytes(state) != state_bytes
            ):
                raise PlanningApplyOutputRejected("operation evidence is incomplete")
            return handle
        except BaseException:
            handle.close()
            output_fd = -1
            raise
    except BaseException:
        if output_fd >= 0:
            with suppress(OSError):
                os.close(output_fd)
        raise


def _open_guarded_output(guard: OutputDirectoryGuard) -> int:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(guard.path, flags)
    opened = os.fstat(descriptor)
    if not stat.S_ISDIR(opened.st_mode) or (opened.st_dev, opened.st_ino) != (guard.device, guard.inode):
        os.close(descriptor)
        raise PlanningApplyOutputRejected("apply output identity changed")
    return descriptor


def _guard_from_current_output(output_dir: Path | None) -> OutputDirectoryGuard:
    if output_dir is None:
        raise PlanningApplyOutputRejected("apply output guard is required")
    path = output_dir.resolve(strict=True)
    opened = path.stat(follow_symlinks=False)
    if not stat.S_ISDIR(opened.st_mode) or path.is_symlink():
        raise PlanningApplyOutputRejected("apply output is unsafe")
    return OutputDirectoryGuard(path=path, device=opened.st_dev, inode=opened.st_ino)


def _open_directory_at(parent_fd: int, name: str) -> int:
    descriptor = os.open(
        name,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
        dir_fd=parent_fd,
    )
    opened = os.fstat(descriptor)
    if not stat.S_ISDIR(opened.st_mode) or opened.st_uid != os.geteuid() or stat.S_IMODE(opened.st_mode) != 0o700:
        os.close(descriptor)
        raise PlanningApplyOutputRejected("operation evidence is not private")
    return descriptor


def _parent_fd(handle: _ApplyEvidenceHandle, relative: str) -> tuple[int, str, list[int]]:
    parts = PurePosixPath(relative).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise PlanningApplyOutputRejected("operation evidence path is invalid")
    parent = handle.operation_fd
    opened: list[int] = []
    for part in parts[:-1]:
        parent = _open_directory_at(parent, part)
        opened.append(parent)
    return parent, parts[-1], opened


def _close_opened(opened: list[int]) -> None:
    for descriptor in reversed(opened):
        os.close(descriptor)


def _entry_stat_at(handle: _ApplyEvidenceHandle, relative: str) -> os.stat_result | None:
    parent, name, opened = _parent_fd(handle, relative)
    try:
        try:
            return os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return None
    finally:
        _close_opened(opened)


def _entry_exists_at(handle: _ApplyEvidenceHandle, relative: str) -> bool:
    return _entry_stat_at(handle, relative) is not None


def _read_private_file_at(handle: _ApplyEvidenceHandle, relative: str) -> bytes:
    parent, name, opened = _parent_fd(handle, relative)
    descriptor = -1
    try:
        descriptor = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent)
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) != 0o600
        ):
            raise PlanningApplyOutputRejected("operation evidence is not private")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        _close_opened(opened)


def _write_all(descriptor: int, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        offset += os.write(descriptor, data[offset:])
    os.fsync(descriptor)


def _write_private_no_replace_at(
    handle: _ApplyEvidenceHandle,
    relative: str,
    data: bytes,
) -> None:
    parent, name, opened = _parent_fd(handle, relative)
    descriptor = -1
    try:
        descriptor = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent,
        )
        os.fchmod(descriptor, 0o600)
        _write_all(descriptor, data)
        os.fsync(parent)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        _close_opened(opened)


def _write_private_atomic_at(
    handle: _ApplyEvidenceHandle,
    relative: str,
    data: bytes,
) -> None:
    parent, name, opened = _parent_fd(handle, relative)
    temporary = f".{name}.{os.getpid()}.{os.urandom(8).hex()}"
    descriptor = -1
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent,
        )
        os.fchmod(descriptor, 0o600)
        _write_all(descriptor, data)
        os.close(descriptor)
        descriptor = -1
        os.replace(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
        os.fsync(parent)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        with suppress(FileNotFoundError):
            os.unlink(temporary, dir_fd=parent)
        _close_opened(opened)


def _mkdir_private_at(handle: _ApplyEvidenceHandle, relative: str) -> None:
    parent, name, opened = _parent_fd(handle, relative)
    try:
        os.mkdir(name, mode=0o700, dir_fd=parent)
        if not _owned_private_directory_at(parent, name):
            raise PlanningApplyOutputRejected("operation evidence is not private")
        os.fsync(parent)
    finally:
        _close_opened(opened)


def _owned_private_directory_at(parent_fd: int, name: str) -> bool:
    try:
        opened = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError:
        return False
    return stat.S_ISDIR(opened.st_mode) and opened.st_uid == os.geteuid() and stat.S_IMODE(opened.st_mode) == 0o700


def _owned_private_subdirectory_at(handle: _ApplyEvidenceHandle, relative: str) -> bool:
    parent, name, opened = _parent_fd(handle, relative)
    try:
        return _owned_private_directory_at(parent, name)
    finally:
        _close_opened(opened)


def _owned_private_file_at(handle: _ApplyEvidenceHandle, relative: str) -> bool:
    opened = _entry_stat_at(handle, relative)
    if opened is None:
        return False
    return stat.S_ISREG(opened.st_mode) and opened.st_uid == os.geteuid() and stat.S_IMODE(opened.st_mode) == 0o600


def _owned_private_file(path: Path) -> bool:
    try:
        opened = path.stat(follow_symlinks=False)
    except OSError:
        return False
    return (
        stat.S_ISREG(opened.st_mode)
        and not path.is_symlink()
        and opened.st_uid == os.geteuid()
        and stat.S_IMODE(opened.st_mode) == 0o600
    )


def _list_directory_at(handle: _ApplyEvidenceHandle, relative: str = "") -> set[str]:
    if relative:
        parent, name, opened = _parent_fd(handle, relative)
        descriptor = _open_directory_at(parent, name)
    else:
        opened = []
        descriptor = os.dup(handle.operation_fd)
    try:
        return set(os.listdir(descriptor))  # noqa: PTH208 - descriptor-relative authority
    finally:
        os.close(descriptor)
        _close_opened(opened)


def _validate_existing_operation_evidence(handle: _ApplyEvidenceHandle) -> None:
    allowed = {
        "operation.json",
        "state.json",
        "attempts",
        "transaction",
        "commit.json",
        "publication.json",
    }
    if not _list_directory_at(handle) <= allowed:
        raise PlanningApplyOutputRejected("operation evidence contains unexpected entries")
    for required in ("operation.json", "state.json"):
        if not _owned_private_file_at(handle, required):
            raise PlanningApplyOutputRejected("operation evidence is not private")
    if not _owned_private_directory_at(handle.operation_fd, "attempts"):
        raise PlanningApplyOutputRejected("operation attempts are not private")
    for attempt in _list_directory_at(handle, "attempts"):
        if not _owned_private_file_at(handle, f"attempts/{attempt}"):
            raise PlanningApplyOutputRejected("operation attempt is not private")
    for optional in ("commit.json", "publication.json"):
        if _entry_exists_at(handle, optional) and not _owned_private_file_at(handle, optional):
            raise PlanningApplyOutputRejected("operation evidence is not private")
    if _entry_exists_at(handle, "transaction"):
        if not _owned_private_directory_at(handle.operation_fd, "transaction"):
            raise PlanningApplyOutputRejected("transaction evidence is not private")
        allowed_transaction = {
            "files",
            "managed-state",
            "git-index.bin",
            "backup-manifest.json",
            "mutation-ledger.json",
        }
        if not _list_directory_at(handle, "transaction") <= allowed_transaction:
            raise PlanningApplyOutputRejected("transaction evidence contains unexpected entries")
        transaction_fd = _open_directory_at(handle.operation_fd, "transaction")
        try:
            for directory in ("files", "managed-state"):
                if not _owned_private_directory_at(transaction_fd, directory):
                    raise PlanningApplyOutputRejected("transaction directory is not private")
                for name in _list_directory_at(handle, f"transaction/{directory}"):
                    if not _owned_private_file_at(handle, f"transaction/{directory}/{name}"):
                        raise PlanningApplyOutputRejected("transaction evidence is not private")
        finally:
            os.close(transaction_fd)
        for filename in ("git-index.bin", "backup-manifest.json", "mutation-ledger.json"):
            if not _owned_private_file_at(handle, f"transaction/{filename}"):
                raise PlanningApplyOutputRejected("transaction evidence is not private")


def _set_operation_state(
    handle: _ApplyEvidenceHandle,
    operation: PlanningApplyOperation,
    state: str,
) -> None:
    _write_private_atomic_at(
        handle,
        "state.json",
        _canonical_json_bytes({
            "operation_id": operation.operation_id,
            "state": state,
        }),
    )


def _load_operation_state(
    handle: _ApplyEvidenceHandle,
    operation: PlanningApplyOperation,
) -> str:
    try:
        state_bytes = _read_private_file_at(handle, "state.json")
        state = json.loads(state_bytes)
    except (OSError, ValueError, json.JSONDecodeError):
        raise PlanningApplyRestoreMismatch("operation state is unreadable") from None
    if (
        not isinstance(state, dict)
        or set(state) != {"operation_id", "state"}
        or state.get("operation_id") != operation.operation_id
        or not isinstance(state.get("state"), str)
        or state.get("state") not in _DURABLE_OPERATION_STATES
        or _canonical_json_bytes(state) != state_bytes
    ):
        raise PlanningApplyRestoreMismatch("operation state is invalid")
    return state["state"]


def _record_operation_attempt(
    handle: _ApplyEvidenceHandle,
    operation: PlanningApplyOperation,
) -> None:
    if not _owned_private_directory_at(handle.operation_fd, "attempts"):
        raise PlanningApplyOutputRejected("operation attempt evidence is unsafe")
    for number in range(1, 10_001):
        relative = f"attempts/{number:06d}.json"
        if _entry_exists_at(handle, relative):
            continue
        _write_private_no_replace_at(
            handle,
            relative,
            _canonical_json_bytes({
                "attempt": number,
                "operation_id": operation.operation_id,
            }),
        )
        return
    raise PlanningApplyOutputRejected("operation attempt bound exceeded")


def _run_git(
    repo_root: Path,
    argv: tuple[str, ...],
    *,
    check: bool = False,
) -> GitCommandResult:
    full_argv = ("git", "-C", repo_root.as_posix(), *argv)
    validate_planning_git_argv(("git", *argv))
    completed = subprocess.run(
        full_argv,
        check=False,
        capture_output=True,
    )
    result = GitCommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
    if check and result.returncode != 0:
        raise RuntimeError("planning Git command failed")
    return result


def _run_git_with_private_index(
    repo_root: Path,
    index_path: Path,
    argv: tuple[str, ...],
) -> GitCommandResult:
    private_root = index_path.parent.resolve()
    if not private_root.is_dir() or stat.S_IMODE(private_root.stat().st_mode) != 0o700:
        raise PlanningApplyUnsafeGitCommand("private commit workspace is unsafe")
    allowed = False
    if (len(argv) == 2 and argv[0] == "read-tree" and _SHA40.fullmatch(argv[1])) or argv == ("write-tree",):
        allowed = True
    elif argv[:3] == ("hook", "run", "--ignore-missing"):
        hook = argv[3:4]
        if hook in (("pre-commit",), ("post-commit",)) and len(argv) == 4:
            allowed = True
        elif (hook == ("prepare-commit-msg",) and len(argv) == 7 and argv[4] == "--" and argv[6] == "message") or (
            hook == ("commit-msg",) and len(argv) == 6 and argv[4] == "--"
        ):
            allowed = Path(argv[5]).parent.resolve() == private_root
    elif (
        len(argv) in (6, 7)
        and argv[0] == "commit-tree"
        and _SHA40.fullmatch(argv[1])
        and argv[2] == "-p"
        and _SHA40.fullmatch(argv[3])
        and argv[4] == "-F"
        and Path(argv[5]).parent.resolve() == private_root
        and (len(argv) == 6 or argv[6] == "-S")
    ):
        allowed = True
    if not allowed:
        raise PlanningApplyUnsafeGitCommand("private-index Git argv is outside the fixed operation seam")
    environment = os.environ.copy()
    environment["GIT_INDEX_FILE"] = index_path.resolve().as_posix()
    completed = subprocess.run(
        ("git", "-C", repo_root.as_posix(), *argv),
        check=False,
        capture_output=True,
        env=environment,
    )
    return GitCommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _git_text(repo_root: Path, *argv: str) -> str | None:
    result = _run_git(repo_root, tuple(argv))
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", errors="strict").strip()


def _operation_trailer_is_proven(
    repo_root: Path,
    *,
    message: bytes,
    operation_id: str,
) -> bool:
    try:
        message.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return False
    completed = subprocess.run(
        (
            "git",
            "-C",
            repo_root.as_posix(),
            "interpret-trailers",
            "--parse",
            "--no-divider",
        ),
        input=message,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        return False
    try:
        parsed = completed.stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return False
    target_values: list[str] = []
    for line in parsed.splitlines():
        key, separator, value = line.partition(": ")
        if not separator:
            return False
        if key == "SpecDock-Planning-Operation":
            target_values.append(value)
    return target_values == [operation_id]


def _operation_commit_is_proven(
    operation: PlanningApplyOperation,
    *,
    repo_root: Path,
    local_commit: str,
    local_tree: str,
    expected_paths: set[str],
) -> bool:
    parents = _git_text(repo_root, "rev-list", "--parents", "-n", "1", local_commit)
    commit_tree = _git_text(repo_root, "rev-parse", f"{local_commit}^{{tree}}")
    commit_paths = _git_text(
        repo_root,
        "diff-tree",
        "--no-commit-id",
        "--name-only",
        "-r",
        local_commit,
    )
    message = _run_git(repo_root, ("show", "-s", "--format=%B", local_commit))
    return (
        _SHA40.fullmatch(local_commit) is not None
        and parents == f"{local_commit} {operation.expected_head}"
        and commit_tree == local_tree
        and set(commit_paths.splitlines() if commit_paths else ()) == expected_paths
        and message.returncode == 0
        and _operation_trailer_is_proven(
            repo_root,
            message=message.stdout,
            operation_id=operation.operation_id,
        )
    )


def _create_verified_operation_commit(
    operation: PlanningApplyOperation,
    *,
    repo_root: Path,
    local_tree: str,
    expected_paths: set[str],
    subject: str,
    fault_hook: Callable[[str], None] | None,
) -> str:
    with tempfile.TemporaryDirectory(prefix="spec-dock-planning-commit-") as temporary:
        workspace = Path(temporary)
        workspace.chmod(0o700)
        index_path = workspace / "index"
        message_path = workspace / "message"
        message_path.write_bytes((f"{subject}\n\nSpecDock-Planning-Operation: {operation.operation_id}\n").encode())
        message_path.chmod(0o600)
        if _run_git_with_private_index(repo_root, index_path, ("read-tree", local_tree)).returncode != 0:
            raise _ApplyFailure("planning_commit_failed")
        private_tree = _run_git_with_private_index(repo_root, index_path, ("write-tree",))
        if private_tree.returncode != 0 or private_tree.stdout.decode("ascii", errors="strict").strip() != local_tree:
            raise _ApplyFailure("planning_commit_failed")
        for hook_argv in (
            ("hook", "run", "--ignore-missing", "pre-commit"),
            (
                "hook",
                "run",
                "--ignore-missing",
                "prepare-commit-msg",
                "--",
                message_path.as_posix(),
                "message",
            ),
            (
                "hook",
                "run",
                "--ignore-missing",
                "commit-msg",
                "--",
                message_path.as_posix(),
            ),
        ):
            if _run_git_with_private_index(repo_root, index_path, hook_argv).returncode != 0:
                raise _ApplyFailure("planning_commit_failed")
        private_tree = _run_git_with_private_index(repo_root, index_path, ("write-tree",))
        try:
            message = message_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            raise _ApplyFailure("planning_commit_failed") from None
        if (
            private_tree.returncode != 0
            or private_tree.stdout.decode("ascii", errors="strict").strip() != local_tree
            or not _operation_trailer_is_proven(
                repo_root,
                message=message.encode("utf-8"),
                operation_id=operation.operation_id,
            )
            or _git_text(repo_root, "write-tree") != local_tree
        ):
            raise _ApplyFailure("planning_commit_failed")
        if fault_hook is not None:
            fault_hook("after_final_index_proof")
        signing = _run_git(repo_root, ("config", "--type=bool", "--get", "commit.gpgsign"))
        if signing.returncode not in (0, 1):
            raise _ApplyFailure("planning_commit_failed")
        signing_value = signing.stdout.decode("ascii", errors="strict").strip()
        if signing.returncode == 0 and signing_value not in ("true", "false"):
            raise _ApplyFailure("planning_commit_failed")
        commit_argv: tuple[str, ...] = (
            "commit-tree",
            local_tree,
            "-p",
            operation.expected_head,
            "-F",
            message_path.as_posix(),
        )
        if signing_value == "true":
            commit_argv = (*commit_argv, "-S")
        created = _run_git_with_private_index(repo_root, index_path, commit_argv)
        if created.returncode != 0:
            raise _ApplyFailure("planning_commit_failed")
        local_commit = created.stdout.decode("ascii", errors="strict").strip()
        if not _operation_commit_is_proven(
            operation,
            repo_root=repo_root,
            local_commit=local_commit,
            local_tree=local_tree,
            expected_paths=expected_paths,
        ):
            raise PlanningApplyRestoreMismatch("operation commit proof failed")
        return local_commit


def _reference_transaction_payloads(
    expected_branch_update: str,
    expected_head_update: str,
) -> tuple[bytes, ...]:
    try:
        branch = expected_branch_update.encode("ascii")
        head = expected_head_update.encode("ascii")
    except UnicodeEncodeError:
        return ()
    return (
        branch + b"\n",
        head + b"\n" + branch + b"\n",
        branch + b"\n" + head + b"\n",
    )


def _reference_transaction_payload_is_expected(
    payload: bytes,
    *,
    expected_branch_update: str,
    expected_head_update: str,
) -> bool:
    return payload in _reference_transaction_payloads(expected_branch_update, expected_head_update)


def _install_operation_commit_cas(
    operation: PlanningApplyOperation,
    *,
    repo_root: Path,
    local_commit: str,
    local_tree: str,
    expected_paths: set[str],
) -> None:
    destination = f"refs/heads/{operation.branch}"
    if (
        _SHA40.fullmatch(local_commit) is None
        or _SHA40.fullmatch(local_tree) is None
        or _git_text(repo_root, "check-ref-format", "--branch", operation.branch) != operation.branch
        or not _operation_commit_is_proven(
            operation,
            repo_root=repo_root,
            local_commit=local_commit,
            local_tree=local_tree,
            expected_paths=expected_paths,
        )
    ):
        raise PlanningApplyRestoreMismatch("operation commit install proof failed")
    native_hook_text = _git_text(
        repo_root,
        "rev-parse",
        "--path-format=absolute",
        "--git-path",
        "hooks/reference-transaction",
    )
    head_path_text = _git_text(
        repo_root,
        "rev-parse",
        "--path-format=absolute",
        "--git-path",
        "HEAD",
    )
    if native_hook_text is None or head_path_text is None:
        raise PlanningApplyRestoreMismatch("operation commit install hook resolution failed")
    native_hook = Path(native_hook_text)
    head_path = Path(head_path_text)
    head_lock = head_path.with_name(f"{head_path.name}.lock")
    with tempfile.TemporaryDirectory(prefix="spec-dock-planning-ref-") as temporary:
        hook_root = Path(temporary)
        hook_root.chmod(0o700)
        hook = hook_root / "reference-transaction"
        hook.write_text(
            f"#!{sys.executable}\n"
            "import os\n"
            "from pathlib import Path\n"
            "import stat\n"
            "import subprocess\n"
            "import sys\n"
            "payload = sys.stdin.buffer.read()\n"
            "phase = sys.argv[1] if len(sys.argv) == 2 else ''\n"
            "head_path = Path(os.environ['SPECDOCK_HEAD_PATH'])\n"
            "head_lock = head_path.with_name(head_path.name + '.lock')\n"
            "def run_native():\n"
            "    native = os.environ.get('SPECDOCK_NATIVE_REFERENCE_TRANSACTION')\n"
            "    if native and Path(native).is_file() and os.access(native, os.X_OK):\n"
            "        return subprocess.run([native, phase], input=payload, check=False).returncode\n"
            "    return 0\n"
            "if phase == 'prepared':\n"
            "    try:\n"
            "        lock_metadata = head_lock.lstat()\n"
            "        if not stat.S_ISREG(lock_metadata.st_mode):\n"
            "            raise SystemExit(97)\n"
            "        observed_head = head_path.read_bytes()\n"
            "        expected_payloads = tuple(\n"
            "            bytes.fromhex(value)\n"
            "            for value in os.environ['SPECDOCK_EXPECTED_REF_PAYLOADS'].split(',')\n"
            "            if value\n"
            "        )\n"
            "        if (\n"
            "            payload not in expected_payloads\n"
            "            or observed_head != os.environ['SPECDOCK_EXPECTED_HEAD'].encode('ascii')\n"
            "        ):\n"
            "            raise SystemExit(97)\n"
            "    except (OSError, UnicodeError, ValueError):\n"
            "        raise SystemExit(97)\n"
            "    native_result = run_native()\n"
            "    raise SystemExit(native_result)\n"
            "native_result = run_native()\n"
            "raise SystemExit(native_result)\n",
            encoding="utf-8",
        )
        hook.chmod(0o700)
        environment = os.environ.copy()
        expected_branch_update = f"{operation.expected_head} {local_commit} {destination}"
        expected_head_update = f"{operation.expected_head} {local_commit} HEAD"
        expected_payloads = _reference_transaction_payloads(expected_branch_update, expected_head_update)
        environment["SPECDOCK_EXPECTED_REF_PAYLOADS"] = ",".join(payload.hex() for payload in expected_payloads)
        environment["SPECDOCK_EXPECTED_HEAD"] = f"ref: {destination}\n"
        environment["SPECDOCK_HEAD_PATH"] = head_path.as_posix()
        if native_hook.is_file() and os.access(native_hook, os.X_OK):
            environment["SPECDOCK_NATIVE_REFERENCE_TRANSACTION"] = native_hook.as_posix()
        else:
            environment.pop("SPECDOCK_NATIVE_REFERENCE_TRANSACTION", None)
        try:
            head_lock.lstat()
        except FileNotFoundError:
            pass
        else:
            raise PlanningApplyRestoreMismatch("operation commit HEAD lock failed") from None
        completed = subprocess.run(
            (
                "git",
                "-C",
                repo_root.as_posix(),
                "-c",
                f"core.hooksPath={hook_root.as_posix()}",
                "update-ref",
                "--no-deref",
                destination,
                local_commit,
                operation.expected_head,
            ),
            check=False,
            capture_output=True,
            env=environment,
        )
    if completed.returncode != 0:
        raise PlanningApplyRestoreMismatch("operation commit install CAS failed")


def _acquire_operation_branch_lock(
    repo_root: Path,
    operation: PlanningApplyOperation,
    local_commit: str,
) -> _OperationBranchLock:
    destination = f"refs/heads/{operation.branch}"
    if (
        _SHA40.fullmatch(local_commit) is None
        or not operation.branch
        or operation.branch.startswith("-")
        or any(character.isspace() for character in operation.branch)
        or _git_text(repo_root, "check-ref-format", "--branch", operation.branch) != operation.branch
    ):
        raise PlanningApplyRestoreMismatch("operation branch ref lock failed")
    head_path_text = _git_text(
        repo_root,
        "rev-parse",
        "--path-format=absolute",
        "--git-path",
        "HEAD",
    )
    if head_path_text is None:
        raise PlanningApplyRestoreMismatch("operation branch HEAD lock failed")
    head_path = Path(head_path_text)
    lock_path = head_path.with_name(f"{head_path.name}.lock")
    hook_root: Path | None = None
    ref_process: subprocess.Popen[bytes] | None = None
    descriptor: int | None = None
    captured_identity: tuple[int, int] | None = None
    captured_mode: int | None = None
    try:
        hook_root = Path(tempfile.mkdtemp(prefix="spec-dock-planning-ref-"))
        hook_root.chmod(0o700)
        ref_process = subprocess.Popen(
            (
                "git",
                "-C",
                repo_root.as_posix(),
                "-c",
                f"core.hooksPath={hook_root.as_posix()}",
                "update-ref",
                "--no-deref",
                "--stdin",
            ),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if ref_process.stdin is None:
            raise PlanningApplyRestoreMismatch("operation branch ref transaction failed")
        try:
            ref_process.stdin.write(
                f"start\nverify {destination} {local_commit}\nprepare\n".encode("ascii"),
            )
            ref_process.stdin.flush()
        except OSError:
            raise PlanningApplyRestoreMismatch("operation branch ref transaction prepare failed") from None
        _read_operation_ref_ack(ref_process, b"start: ok")
        _read_operation_ref_ack(ref_process, b"prepare: ok")
        if ref_process.poll() is not None:
            raise PlanningApplyRestoreMismatch("operation branch ref transaction prepare failed")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        try:
            descriptor = os.open(lock_path, flags)
        except OSError:
            raise PlanningApplyRestoreMismatch("operation branch HEAD lock failed") from None
        opened = os.fstat(descriptor)
        try:
            current = lock_path.lstat()
        except OSError:
            raise PlanningApplyRestoreMismatch("operation branch HEAD lock failed") from None
        opened_mode = stat.S_IMODE(opened.st_mode)
        current_mode = stat.S_IMODE(current.st_mode)
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_uid != os.geteuid()
            or not _git_ref_lock_mode_is_compatible(opened_mode)
            or not stat.S_ISREG(current.st_mode)
            or current.st_uid != os.geteuid()
            or current_mode != opened_mode
            or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
            or ref_process.poll() is not None
        ):
            raise PlanningApplyRestoreMismatch("operation branch HEAD lock is unsafe")
        os.fsync(descriptor)
        captured_identity = (opened.st_dev, opened.st_ino)
        captured_mode = opened_mode
        return _OperationBranchLock(
            path=lock_path,
            descriptor=descriptor,
            device=opened.st_dev,
            inode=opened.st_ino,
            mode=opened_mode,
            destination=destination,
            expected_commit=local_commit,
            ref_process=ref_process,
            hook_root=hook_root,
        )
    except BaseException:
        cleanup_failure: PlanningApplyRestoreMismatch | None = None
        if ref_process is not None:
            if captured_identity is None or captured_mode is None or descriptor is None:
                try:
                    _abandon_operation_ref_transaction(ref_process)
                except PlanningApplyRestoreMismatch as exc:
                    cleanup_failure = exc
            else:
                try:
                    _abort_operation_ref_transaction(ref_process)
                    _remove_captured_operation_head_lock(
                        lock_path,
                        descriptor,
                        captured_identity[0],
                        captured_identity[1],
                        captured_mode,
                    )
                except PlanningApplyRestoreMismatch as exc:
                    cleanup_failure = exc
        if hook_root is not None:
            with suppress(OSError):
                hook_root.rmdir()
        if descriptor is not None:
            with suppress(OSError):
                os.close(descriptor)
        if cleanup_failure is not None:
            raise cleanup_failure from None
        raise


def _require_operation_branch_lock(
    operation: PlanningApplyOperation,
    local_commit: str,
    branch_lock: _OperationBranchLock,
) -> None:
    destination = f"refs/heads/{operation.branch}"
    if not isinstance(branch_lock, _OperationBranchLock):
        raise PlanningApplyRestoreMismatch("operation branch ref lock is invalid")
    if branch_lock.destination != destination or branch_lock.expected_commit != local_commit:
        raise PlanningApplyRestoreMismatch("operation branch ref lock binding mismatch")
    branch_lock.assert_held()


def _operation_branch_commit_is_proven_locked(
    operation: PlanningApplyOperation,
    repo_root: Path,
    local_commit: str,
) -> bool:
    destination = f"refs/heads/{operation.branch}"
    return (
        _SHA40.fullmatch(local_commit) is not None
        and _git_text(repo_root, "symbolic-ref", "-q", "HEAD") == destination
        and _git_text(repo_root, "rev-parse", destination) == local_commit
        and _git_text(repo_root, "rev-parse", "HEAD") == local_commit
    )


def _operation_branch_commit_is_proven(
    operation: PlanningApplyOperation,
    repo_root: Path,
    local_commit: str,
    *,
    branch_lock: _OperationBranchLock | None = None,
) -> bool:
    if branch_lock is not None:
        _require_operation_branch_lock(operation, local_commit, branch_lock)
        return _operation_branch_commit_is_proven_locked(operation, repo_root, local_commit)
    with _acquire_operation_branch_lock(repo_root, operation, local_commit):
        return _operation_branch_commit_is_proven_locked(
            operation,
            repo_root,
            local_commit,
        )


def _git_blob_oid(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def _expected_staged_blob_oids(
    operation: PlanningApplyOperation,
    *,
    expected_companion_oid: str | None,
) -> Mapping[str, str | None]:
    expected: dict[str, str | None] = {}
    replace_canonical = operation.decision == "approved" and operation.mode == "archive-candidate"
    for relative in operation.canonical_target_paths:
        filename = PurePosixPath(relative).name
        if replace_canonical:
            replacement = operation.replacement_documents.get(filename)
            if replacement is None:
                raise ValueError("staged planning target cannot be proven")
            expected[relative] = _git_blob_oid(replacement)
        else:
            oid = operation.pre_apply_target_blob_oids.get(relative)
            if oid is None or _SHA40.fullmatch(oid) is None:
                raise ValueError("staged planning target cannot be proven")
            expected[relative] = oid
    if operation.replacement_companion is not None:
        expected[operation.companion_target_path] = _git_blob_oid(operation.replacement_companion)
    else:
        if expected_companion_oid is not None and _SHA40.fullmatch(expected_companion_oid) is None:
            raise ValueError("staged planning target cannot be proven")
        expected[operation.companion_target_path] = expected_companion_oid
    expected[operation.decision_artifact_path] = _git_blob_oid(operation.human_decision_bytes)
    if len(expected) != 5:
        raise ValueError("staged planning target inventory is invalid")
    return MappingProxyType(expected)


def _tree_blob_oids(
    repo_root: Path,
    tree_oid: str,
    relatives: tuple[str, ...],
) -> Mapping[str, str | None] | None:
    if _SHA40.fullmatch(tree_oid) is None or len(relatives) != len(set(relatives)):
        return None
    targets = set(relatives)
    result = _run_git(
        repo_root,
        ("ls-tree", "-r", "-z", tree_oid, "--", *sorted(relatives)),
    )
    if result.returncode != 0 or (result.stdout and not result.stdout.endswith(b"\0")):
        return None
    observed: dict[str, str] = {}
    for entry in result.stdout.split(b"\0"):
        if not entry:
            continue
        try:
            metadata, path_bytes = entry.split(b"\t", 1)
            mode, object_type, oid_bytes = metadata.split(b" ")
            path = path_bytes.decode("utf-8", errors="strict")
            oid = oid_bytes.decode("ascii", errors="strict")
        except (UnicodeDecodeError, ValueError):
            return None
        if (
            path not in targets
            or path in observed
            or mode not in {b"100644", b"100755"}
            or object_type != b"blob"
            or _SHA40.fullmatch(oid) is None
        ):
            return None
        observed[path] = oid
    return MappingProxyType({relative: observed.get(relative) for relative in relatives})


def load_expected_planning_targets(
    repo_root: Path,
    expected_head: str,
    canonical_target_paths: tuple[str, str, str],
) -> ExpectedPlanningTargets:
    if _SHA40.fullmatch(expected_head) is None:
        raise ValueError("expected planning HEAD is invalid")
    documents: dict[str, bytes] = {}
    blob_oids: dict[str, str] = {}
    for relative in canonical_target_paths:
        _safe_repo_relative(relative)
        blob_oid = _git_text(repo_root, "rev-parse", f"{expected_head}:{relative}")
        content = _run_git(repo_root, ("show", f"{expected_head}:{relative}"))
        if (
            blob_oid is None
            or _SHA40.fullmatch(blob_oid) is None
            or content.returncode != 0
            or _git_blob_oid(content.stdout) != blob_oid
        ):
            raise ValueError("expected planning target cannot be proven")
        documents[PurePosixPath(relative).name] = content.stdout
        blob_oids[relative] = blob_oid
    if set(documents) != {"design.md", "plan.md", "requirement.md"}:
        raise ValueError("expected planning target set is incomplete")
    return ExpectedPlanningTargets(
        documents=MappingProxyType(documents),
        blob_oids=MappingProxyType(blob_oids),
    )


def _load_expected_companion_preimage(
    operation: PlanningApplyOperation,
    repo_root: Path,
) -> tuple[bool, bytes, str | None]:
    relative = operation.companion_target_path
    listing = _run_git(
        repo_root,
        ("ls-tree", "-z", operation.expected_head, "--", relative),
    )
    if listing.returncode != 0:
        raise ValueError("expected companion preimage cannot be proven")
    if listing.stdout == b"":
        return False, b"", None
    try:
        metadata, observed_path = listing.stdout.removesuffix(b"\0").split(b"\t", 1)
        mode, object_type, oid_bytes = metadata.split(b" ")
        oid = oid_bytes.decode("ascii")
    except (UnicodeDecodeError, ValueError) as error:
        raise ValueError("expected companion preimage cannot be proven") from error
    if (
        mode not in (b"100644", b"100755")
        or object_type != b"blob"
        or observed_path != relative.encode("utf-8")
        or _SHA40.fullmatch(oid) is None
    ):
        raise ValueError("expected companion preimage cannot be proven")
    content = _run_git(repo_root, ("cat-file", "blob", oid))
    if content.returncode != 0 or _git_blob_oid(content.stdout) != oid:
        raise ValueError("expected companion preimage cannot be proven")
    return True, content.stdout, oid


def planning_apply_resume_available(
    operation: PlanningApplyOperation,
    *,
    output_guard: OutputDirectoryGuard | None = None,
    output_dir: Path | None = None,
) -> bool:
    output_guard = output_guard or _guard_from_current_output(output_dir)
    output_fd = _open_guarded_output(output_guard)
    try:
        try:
            existing = os.stat(
                f"planning-apply-{operation.operation_id}",
                dir_fd=output_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return False
        if not stat.S_ISDIR(existing.st_mode):
            raise PlanningApplyOutputRejected("operation identity collision")
    finally:
        os.close(output_fd)
    handle = record_planning_apply_operation(operation, output_guard=output_guard)
    try:
        return _entry_exists_at(handle, "commit.json") or _entry_exists_at(handle, "transaction")
    finally:
        handle.close()


def _capture_publication_authority(
    operation: PlanningApplyOperation,
    repo_root: Path,
) -> _PublicationAuthority:
    from spec_dock_runtime.infra.git_cli import origin_github_publication_endpoint

    try:
        repository, push_endpoint = origin_github_publication_endpoint(repo_root)
    except RuntimeError:
        raise PlanningApplyRestoreMismatch("publication authority is unavailable") from None
    expected_repository = operation.repository.strip().lower()
    if repository != expected_repository or not push_endpoint:
        raise PlanningApplyRestoreMismatch("publication authority does not match operation")
    return _PublicationAuthority(
        repository=repository,
        push_endpoint=push_endpoint,
    )


def _remote_head_observation(
    repo_root: Path,
    authority: _PublicationAuthority,
    branch: str,
) -> tuple[Literal["present", "absent", "unavailable"], str | None]:
    result = _run_git(
        repo_root,
        ("ls-remote", "--heads", authority.push_endpoint, f"refs/heads/{branch}"),
    )
    if result.returncode != 0:
        return "unavailable", None
    text = result.stdout.decode("ascii", errors="strict").strip()
    if not text:
        return "absent", None
    value = text.split()[0]
    if _SHA40.fullmatch(value) is None:
        return "unavailable", None
    return "present", value


def _remote_head(
    repo_root: Path,
    authority: _PublicationAuthority,
    branch: str,
) -> str | None:
    disposition, value = _remote_head_observation(repo_root, authority, branch)
    return value if disposition == "present" else None


def _push_operation_commit_cas(
    operation: PlanningApplyOperation,
    *,
    repo_root: Path,
    authority: _PublicationAuthority,
    expected_remote_head: str,
    local_commit: str,
    local_tree: str,
    branch_lock: _OperationBranchLock | None = None,
) -> GitCommandResult:
    if branch_lock is None:
        with _acquire_operation_branch_lock(repo_root, operation, local_commit) as acquired:
            return _push_operation_commit_cas(
                operation=operation,
                repo_root=repo_root,
                authority=authority,
                expected_remote_head=expected_remote_head,
                local_commit=local_commit,
                local_tree=local_tree,
                branch_lock=acquired,
            )
    _require_operation_branch_lock(operation, local_commit, branch_lock)
    branch = operation.branch
    if (
        _SHA40.fullmatch(expected_remote_head) is None
        or _SHA40.fullmatch(local_commit) is None
        or _SHA40.fullmatch(local_tree) is None
        or not branch
        or branch.startswith("-")
        or any(character.isspace() for character in branch)
        or authority.repository != operation.repository.strip().lower()
        or not authority.push_endpoint
        or _git_text(repo_root, "check-ref-format", "--branch", branch) != branch
        or not _operation_branch_commit_is_proven(
            operation,
            repo_root,
            local_commit,
            branch_lock=branch_lock,
        )
        or _git_text(repo_root, "rev-parse", f"{local_commit}^") != expected_remote_head
        or _git_text(repo_root, "rev-parse", f"{local_commit}^{{tree}}") != local_tree
    ):
        raise PlanningApplyUnsafeGitCommand("planning publication CAS proof failed")
    branch_lock.assert_held()
    destination = f"refs/heads/{branch}"
    lease = f"--force-with-lease={destination}:{expected_remote_head}"
    refspec = f"{local_commit}:{destination}"
    completed = subprocess.run(
        (
            "git",
            "-C",
            repo_root.as_posix(),
            "push",
            lease,
            authority.push_endpoint,
            refspec,
        ),
        check=False,
        capture_output=True,
    )
    return GitCommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _cas_failure_result(
    operation: PlanningApplyOperation,
    *,
    repo_root: Path,
    authority: _PublicationAuthority,
    local_commit: str,
    local_tree: str,
) -> PlanningApplyExecution | None:
    disposition, remote = _remote_head_observation(
        repo_root,
        authority,
        operation.branch,
    )
    if disposition == "present" and remote == local_commit:
        remote_tree = _git_text(repo_root, "rev-parse", f"{remote}^{{tree}}")
        if remote_tree == local_tree:
            return None
    if disposition == "present" and remote == operation.expected_head:
        return _operation_result(
            operation,
            status="publication_pending",
            reason="push_failed",
            local_commit=local_commit,
            local_tree=local_tree,
            remote_commit=remote,
        )
    if disposition in {"absent", "present"}:
        return _operation_result(
            operation,
            status="blocked_remote_diverged",
            reason="remote_diverged",
            local_commit=local_commit,
            local_tree=local_tree,
            remote_commit=remote,
        )
    return _operation_result(
        operation,
        status="publication_pending",
        reason="push_failed",
        local_commit=local_commit,
        local_tree=local_tree,
    )


def _changed_paths(repo_root: Path, *, cached: bool = False) -> set[str] | None:
    argv = ["diff"]
    if cached:
        argv.append("--cached")
    argv.extend(["--name-only", "-z", "--no-renames"])
    result = _run_git(repo_root, tuple(argv))
    if result.returncode != 0:
        return None
    return {item.decode("utf-8") for item in result.stdout.split(b"\0") if item}


def _operation_result(
    operation: PlanningApplyOperation,
    *,
    status: PlanningApplyStatus,
    reason: str,
    local_commit: str | None = None,
    local_tree: str | None = None,
    remote_commit: str | None = None,
) -> PlanningApplyExecution:
    return PlanningApplyExecution(
        status=status,
        reason=reason,
        operation_id=operation.operation_id,
        decision_artifact_path=operation.decision_artifact_path,
        local_commit=local_commit,
        local_tree=local_tree,
        remote_commit=remote_commit,
    )


def _apply_targets_match_snapshots(
    operation: PlanningApplyOperation,
    repo_root: Path,
    file_snapshots: Mapping[str, FileSnapshot],
    *,
    target_guard: _RepositoryTargetGuard | None = None,
) -> bool:
    if (
        _git_text(repo_root, "branch", "--show-current") != operation.branch
        or _git_text(repo_root, "rev-parse", "HEAD") != operation.expected_head
    ):
        return False
    for relative in (*operation.canonical_target_paths, operation.companion_target_path):
        expected = file_snapshots.get(relative)
        if expected is None:
            return False
        try:
            observed = (
                target_guard.snapshot(relative)
                if target_guard is not None
                else snapshot_regular_file(repo_root / relative)
            )
            if observed != expected:
                return False
        except (OSError, ValueError):
            return False
    return True


def _finalize_transaction_cleanup(
    handle: _ApplyEvidenceHandle,
    operation: PlanningApplyOperation,
    *,
    final_state: str,
) -> None:
    _remove_transaction_backup(handle)
    if _entry_exists_at(handle, "transaction"):
        raise ValueError("pre-mutation transaction backup was not removed")
    os.fsync(handle.operation_fd)
    _set_operation_state(handle, operation, final_state)


def _discard_pre_mutation_backup(
    handle: _ApplyEvidenceHandle,
    operation: PlanningApplyOperation,
    *,
    final_state: str,
) -> None:
    _finalize_transaction_cleanup(
        handle,
        operation,
        final_state=final_state,
    )


def _validate_no_transaction_state(
    handle: _ApplyEvidenceHandle,
    operation: PlanningApplyOperation,
) -> None:
    state = _load_operation_state(handle, operation)
    if state not in _NO_TRANSACTION_START_STATES or _entry_exists_at(handle, "publication.json"):
        raise PlanningApplyRestoreMismatch("operation state cannot start a transaction")


def _apply_guarded_mutation(
    target_guard: _RepositoryTargetGuard,
    handle: _ApplyEvidenceHandle,
    operation: PlanningApplyOperation,
    mutations: list[_TargetMutation],
    *,
    relative: str,
    expected: FileSnapshot,
    replacement: bytes,
    mode: int,
) -> None:
    def prepare(mutation: _TargetMutation) -> None:
        mutations.append(mutation)
        _persist_target_mutations(handle, operation, mutations)

    def publish(mutation: _TargetMutation) -> None:
        _replace_target_mutation(mutations, mutation)
        _persist_target_mutations(handle, operation, mutations)

    def discard(mutation: _TargetMutation) -> None:
        _remove_target_mutation(mutations, mutation.relative)
        _persist_target_mutations(handle, operation, mutations)

    def workspace_intent_update(intent: _WorkspaceIntent | None) -> None:
        _persist_workspace_intent(handle, operation, mutations, intent)

    mutation = target_guard.compare_replace(
        relative,
        expected=expected,
        replacement=replacement,
        mode=mode,
        prepare=prepare,
        publish=publish,
        discard=discard,
        workspace_intent_update=workspace_intent_update,
    )
    if mutation is not None:
        _replace_target_mutation(mutations, mutation)


def _replace_target_mutation(
    mutations: list[_TargetMutation],
    mutation: _TargetMutation,
) -> None:
    matches = [index for index, current in enumerate(mutations) if current.relative == mutation.relative]
    if len(matches) != 1:
        raise PlanningApplyRestoreMismatch("transaction mutation ledger inventory changed")
    mutations[matches[0]] = mutation


def _remove_target_mutation(
    mutations: list[_TargetMutation],
    relative: str,
) -> None:
    matches = [index for index, current in enumerate(mutations) if current.relative == relative]
    if len(matches) != 1:
        raise PlanningApplyRestoreMismatch("transaction mutation ledger inventory changed")
    mutations.pop(matches[0])


_WORKSPACE_INTENT_UNCHANGED = object()


def _workspace_intent_payload(intent: _WorkspaceIntent | None) -> dict[str, object] | None:
    if intent is None:
        return None
    return {
        "path": intent.relative,
        "purpose": intent.purpose,
        "workspace_name": intent.workspace_name,
        "workspace_device": intent.workspace_device,
        "workspace_inode": intent.workspace_inode,
        "staged_name": intent.staged_name,
        "staged_device": intent.staged_device,
        "staged_inode": intent.staged_inode,
    }


def _read_mutation_ledger_value(
    handle: _ApplyEvidenceHandle,
    operation: PlanningApplyOperation,
) -> dict[str, object]:
    raw = _read_private_file_at(handle, "transaction/mutation-ledger.json")
    try:
        value = json.loads(raw)
    except (ValueError, json.JSONDecodeError):
        raise PlanningApplyRestoreMismatch("transaction mutation ledger is unreadable") from None
    if (
        not isinstance(value, dict)
        or set(value) != {"operation_id", "workspace_intent", "entries"}
        or value.get("operation_id") != operation.operation_id
        or not isinstance(value.get("entries"), list)
        or _canonical_json_bytes(value) != raw
    ):
        raise PlanningApplyRestoreMismatch("transaction mutation ledger mismatch")
    return value


def _workspace_intent_from_value(
    value: object,
    operation: PlanningApplyOperation,
) -> _WorkspaceIntent | None:
    if value is None:
        return None
    allowed = {
        *operation.canonical_target_paths,
        operation.companion_target_path,
        operation.decision_artifact_path,
    }
    purpose = value.get("purpose") if isinstance(value, dict) else None
    expected_staged_name = "quarantine" if purpose == "rollback-absent" else "staged"
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "path",
            "purpose",
            "workspace_name",
            "workspace_device",
            "workspace_inode",
            "staged_name",
            "staged_device",
            "staged_inode",
        }
        or not isinstance(value.get("path"), str)
        or value["path"] not in allowed
        or purpose not in {"forward", "rollback-existing", "rollback-absent"}
        or not isinstance(value.get("workspace_name"), str)
        or re.fullmatch(r"\.spec-dock-apply-[0-9a-f]{32}", value["workspace_name"]) is None
        or value.get("staged_name") != expected_staged_name
    ):
        raise PlanningApplyRestoreMismatch("transaction workspace intent mismatch")
    workspace_device = value.get("workspace_device")
    workspace_inode = value.get("workspace_inode")
    staged_device = value.get("staged_device")
    staged_inode = value.get("staged_inode")
    workspace_bound = (
        isinstance(workspace_device, int)
        and not isinstance(workspace_device, bool)
        and isinstance(workspace_inode, int)
        and not isinstance(workspace_inode, bool)
    )
    staged_bound = (
        isinstance(staged_device, int)
        and not isinstance(staged_device, bool)
        and isinstance(staged_inode, int)
        and not isinstance(staged_inode, bool)
    )
    if (
        (workspace_device is None) != (workspace_inode is None)
        or (staged_device is None) != (staged_inode is None)
        or (workspace_device is not None and not workspace_bound)
        or (staged_device is not None and not staged_bound)
        or (staged_bound and not workspace_bound)
        or (purpose == "rollback-absent" and workspace_bound != staged_bound)
    ):
        raise PlanningApplyRestoreMismatch("transaction workspace intent mismatch")
    return _WorkspaceIntent(
        relative=value["path"],
        purpose=value["purpose"],
        workspace_name=value["workspace_name"],
        workspace_device=workspace_device,
        workspace_inode=workspace_inode,
        staged_name=value["staged_name"],
        staged_device=staged_device,
        staged_inode=staged_inode,
    )


def _load_workspace_intent(
    handle: _ApplyEvidenceHandle,
    operation: PlanningApplyOperation,
) -> _WorkspaceIntent | None:
    value = _read_mutation_ledger_value(handle, operation)
    return _workspace_intent_from_value(value["workspace_intent"], operation)


def _persist_target_mutations(
    handle: _ApplyEvidenceHandle,
    operation: PlanningApplyOperation,
    mutations: list[_TargetMutation],
    *,
    workspace_intent: _WorkspaceIntent | object | None = _WORKSPACE_INTENT_UNCHANGED,
) -> None:
    if workspace_intent is _WORKSPACE_INTENT_UNCHANGED:
        current_intent = _load_workspace_intent(handle, operation)
    else:
        assert workspace_intent is None or isinstance(workspace_intent, _WorkspaceIntent)
        current_intent = workspace_intent
    _write_private_atomic_at(
        handle,
        "transaction/mutation-ledger.json",
        _canonical_json_bytes({
            "operation_id": operation.operation_id,
            "workspace_intent": _workspace_intent_payload(current_intent),
            "entries": [
                {
                    "path": mutation.relative,
                    "phase": mutation.phase,
                    "workspace_name": mutation.workspace_name,
                    "workspace_device": mutation.workspace_device,
                    "workspace_inode": mutation.workspace_inode,
                    "staged_name": mutation.staged_name,
                    "staged_device": mutation.staged_device,
                    "staged_inode": mutation.staged_inode,
                    "before_device": mutation.before_device,
                    "before_inode": mutation.before_inode,
                    "after_device": mutation.after_device,
                    "after_inode": mutation.after_inode,
                    "after_mode": mutation.after.mode,
                    "after_sha256": mutation.after.sha256,
                }
                for mutation in mutations
            ],
        }),
    )


def _persist_workspace_intent(
    handle: _ApplyEvidenceHandle,
    operation: PlanningApplyOperation,
    mutations: list[_TargetMutation],
    intent: _WorkspaceIntent | None,
) -> None:
    _persist_target_mutations(
        handle,
        operation,
        mutations,
        workspace_intent=intent,
    )


def _load_target_mutations(
    handle: _ApplyEvidenceHandle,
    operation: PlanningApplyOperation,
    *,
    file_snapshots: Mapping[str, FileSnapshot],
    decision_snapshot: FileSnapshot,
) -> list[_TargetMutation]:
    value = _read_mutation_ledger_value(handle, operation)
    _workspace_intent_from_value(value["workspace_intent"], operation)
    allowed = {
        *operation.canonical_target_paths,
        operation.companion_target_path,
        operation.decision_artifact_path,
    }
    expected_replacements = {
        operation.decision_artifact_path: operation.human_decision_bytes,
        operation.companion_target_path: operation.replacement_companion,
        **{
            relative: operation.replacement_documents.get(PurePosixPath(relative).name)
            for relative in operation.canonical_target_paths
        },
    }
    snapshots = {
        **file_snapshots,
        operation.decision_artifact_path: decision_snapshot,
    }
    mutations: list[_TargetMutation] = []
    seen: set[str] = set()
    entries = value["entries"]
    assert isinstance(entries, list)
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or set(entry)
            != {
                "path",
                "phase",
                "workspace_name",
                "workspace_device",
                "workspace_inode",
                "staged_name",
                "staged_device",
                "staged_inode",
                "before_device",
                "before_inode",
                "after_device",
                "after_inode",
                "after_mode",
                "after_sha256",
            }
            or not isinstance(entry.get("path"), str)
            or entry["path"] not in allowed
            or entry["path"] in seen
            or entry.get("phase") not in {"prepared", "published", "rollback-prepared"}
            or not isinstance(entry.get("workspace_name"), str)
            or re.fullmatch(r"\.spec-dock-apply-[0-9a-f]{32}", entry["workspace_name"]) is None
            or entry.get("staged_name") not in {"staged", "quarantine"}
            or isinstance(entry.get("workspace_device"), bool)
            or not isinstance(entry.get("workspace_device"), int)
            or isinstance(entry.get("workspace_inode"), bool)
            or not isinstance(entry.get("workspace_inode"), int)
            or isinstance(entry.get("staged_device"), bool)
            or not isinstance(entry.get("staged_device"), int)
            or isinstance(entry.get("staged_inode"), bool)
            or not isinstance(entry.get("staged_inode"), int)
            or (
                entry.get("before_device") is not None
                and (isinstance(entry.get("before_device"), bool) or not isinstance(entry.get("before_device"), int))
            )
            or (
                entry.get("before_inode") is not None
                and (isinstance(entry.get("before_inode"), bool) or not isinstance(entry.get("before_inode"), int))
            )
            or isinstance(entry.get("after_device"), bool)
            or not isinstance(entry.get("after_device"), int)
            or isinstance(entry.get("after_inode"), bool)
            or not isinstance(entry.get("after_inode"), int)
            or isinstance(entry.get("after_mode"), bool)
            or not isinstance(entry.get("after_mode"), int)
            or not isinstance(entry.get("after_sha256"), str)
            or _SHA256.fullmatch(entry["after_sha256"]) is None
        ):
            raise PlanningApplyRestoreMismatch("transaction mutation ledger mismatch")
        replacement = expected_replacements[entry["path"]]
        if replacement is None or hashlib.sha256(replacement).hexdigest() != entry["after_sha256"]:
            raise PlanningApplyRestoreMismatch("transaction mutation ledger mismatch")
        seen.add(entry["path"])
        mutations.append(
            _TargetMutation(
                relative=entry["path"],
                before=snapshots[entry["path"]],
                after=FileSnapshot(
                    existed=True,
                    data=replacement,
                    mode=entry["after_mode"],
                    sha256=entry["after_sha256"],
                ),
                phase=entry["phase"],
                workspace_name=entry["workspace_name"],
                workspace_device=entry["workspace_device"],
                workspace_inode=entry["workspace_inode"],
                staged_name=entry["staged_name"],
                staged_device=entry["staged_device"],
                staged_inode=entry["staged_inode"],
                before_device=entry["before_device"],
                before_inode=entry["before_inode"],
                after_device=entry["after_device"],
                after_inode=entry["after_inode"],
            )
        )
    return mutations


def execute_planning_apply_transaction(
    operation: PlanningApplyOperation,
    *,
    repo_root: Path,
    output_guard: OutputDirectoryGuard | None = None,
    output_dir: Path | None = None,
    validation_runner: Callable[[], object],
    sync_runner: Callable[[], object],
    fault_hook: Callable[[str], None] | None = None,
) -> PlanningApplyExecution:
    output_guard = output_guard or _guard_from_current_output(output_dir)
    try:
        handle = record_planning_apply_operation(
            operation,
            output_guard=output_guard,
            capture_hook=fault_hook,
        )
    except (OSError, PlanningApplyOutputRejected, ValueError):
        return _operation_result(
            operation,
            status="rejected",
            reason="apply_output_rejected",
        )
    target_guard: _RepositoryTargetGuard | None = None
    try:
        try:
            target_guard = _RepositoryTargetGuard.capture(
                repo_root,
                (
                    *operation.canonical_target_paths,
                    operation.companion_target_path,
                    operation.decision_artifact_path,
                ),
            )
        except (OSError, ValueError):
            return _operation_result(
                operation,
                status=("recovery_required" if _entry_exists_at(handle, "transaction") else "rejected"),
                reason=("restore_mismatch" if _entry_exists_at(handle, "transaction") else "apply_output_rejected"),
            )
        return _execute_planning_apply_transaction(
            operation,
            repo_root=repo_root,
            handle=handle,
            target_guard=target_guard,
            validation_runner=validation_runner,
            sync_runner=sync_runner,
            fault_hook=fault_hook,
        )
    finally:
        if target_guard is not None:
            target_guard.close()
        handle.close()


def _publish_initial_operation_commit(
    operation: PlanningApplyOperation,
    *,
    repo_root: Path,
    handle: _ApplyEvidenceHandle,
    authority: _PublicationAuthority,
    local_commit: str,
    local_tree: str,
    fault_hook: Callable[[str], None] | None,
) -> PlanningApplyExecution:
    with _acquire_operation_branch_lock(repo_root, operation, local_commit) as branch_lock:
        if fault_hook is not None:
            fault_hook("before_push")
        if not _operation_branch_commit_is_proven(
            operation,
            repo_root,
            local_commit,
            branch_lock=branch_lock,
        ):
            return _operation_result(
                operation,
                status="publication_pending",
                reason="remote_parity_unconfirmed",
                local_commit=local_commit,
                local_tree=local_tree,
            )
        push = _push_operation_commit_cas(
            operation=operation,
            repo_root=repo_root,
            authority=authority,
            expected_remote_head=operation.expected_head,
            local_commit=local_commit,
            local_tree=local_tree,
            branch_lock=branch_lock,
        )
        if push.returncode != 0:
            failure = _cas_failure_result(
                operation,
                repo_root=repo_root,
                authority=authority,
                local_commit=local_commit,
                local_tree=local_tree,
            )
            if failure is not None:
                return failure
        if fault_hook is not None:
            fault_hook("after_push")
        if not _operation_branch_commit_is_proven(
            operation,
            repo_root,
            local_commit,
            branch_lock=branch_lock,
        ):
            return _operation_result(
                operation,
                status="publication_pending",
                reason="remote_parity_unconfirmed",
                local_commit=local_commit,
                local_tree=local_tree,
            )
        _set_operation_state(handle, operation, "PUSHED")
        remote = _remote_head(repo_root, authority, operation.branch)
        if fault_hook is not None:
            fault_hook("after_fetch")
        if remote != local_commit:
            return _operation_result(
                operation,
                status="publication_pending",
                reason="remote_parity_unconfirmed",
                local_commit=local_commit,
                local_tree=local_tree,
                remote_commit=remote,
            )
        remote_tree = _git_text(repo_root, "rev-parse", f"{remote}^{{tree}}")
        if remote_tree != local_tree:
            return _operation_result(
                operation,
                status="publication_pending",
                reason="remote_parity_unconfirmed",
                local_commit=local_commit,
                local_tree=local_tree,
                remote_commit=remote,
            )
        if not _operation_branch_commit_is_proven(
            operation,
            repo_root,
            local_commit,
            branch_lock=branch_lock,
        ):
            return _operation_result(
                operation,
                status="publication_pending",
                reason="remote_parity_unconfirmed",
                local_commit=local_commit,
                local_tree=local_tree,
                remote_commit=remote,
            )
        _record_publication(handle, operation, local_commit, local_tree)
        _set_operation_state(handle, operation, "REMOTE_PARITY")
        if operation.decision == "approved":
            return _operation_result(
                operation,
                status="ready",
                reason="adoption_published",
                local_commit=local_commit,
                local_tree=local_tree,
                remote_commit=remote,
            )
        return _operation_result(
            operation,
            status="rejected",
            reason="plan_rejected",
            local_commit=local_commit,
            local_tree=local_tree,
            remote_commit=remote,
        )


def _execute_planning_apply_transaction(
    operation: PlanningApplyOperation,
    *,
    repo_root: Path,
    handle: _ApplyEvidenceHandle,
    target_guard: _RepositoryTargetGuard,
    validation_runner: Callable[[], object],
    sync_runner: Callable[[], object],
    fault_hook: Callable[[str], None] | None,
) -> PlanningApplyExecution:
    has_commit = _entry_exists_at(handle, "commit.json")
    has_transaction = _entry_exists_at(handle, "transaction")
    if not has_commit and not has_transaction:
        try:
            _validate_no_transaction_state(handle, operation)
        except PlanningApplyRestoreMismatch:
            return _operation_result(
                operation,
                status="recovery_required",
                reason="restore_mismatch",
            )
    try:
        _record_operation_attempt(handle, operation)
    except (OSError, PlanningApplyOutputRejected):
        return _operation_result(
            operation,
            status="rejected",
            reason="apply_output_rejected",
        )
    try:
        publication_authority = _capture_publication_authority(operation, repo_root)
    except PlanningApplyRestoreMismatch:
        return _operation_result(
            operation,
            status=("recovery_required" if has_commit or has_transaction else "stale"),
            reason=("restore_mismatch" if has_commit or has_transaction else "apply_target_changed"),
        )
    if has_commit:
        return _resume_publication(
            operation,
            repo_root=repo_root,
            handle=handle,
            authority=publication_authority,
            fault_hook=fault_hook,
        )
    if has_transaction:
        return _recover_interrupted_transaction(
            operation,
            repo_root=repo_root,
            handle=handle,
            target_guard=target_guard,
            authority=publication_authority,
        )
    if _git_text(repo_root, "rev-parse", "HEAD") != operation.expected_head:
        return _operation_result(operation, status="stale", reason="apply_target_changed")
    if _git_text(repo_root, "branch", "--show-current") != operation.branch:
        return _operation_result(operation, status="stale", reason="apply_target_changed")
    if _git_bound_targets_are_stale(operation, repo_root):
        return _operation_result(operation, status="stale", reason="apply_target_changed")
    try:
        expected_companion = _load_expected_companion_preimage(operation, repo_root)
    except (OSError, ValueError):
        return _operation_result(
            operation,
            status="blocked",
            reason="git_preflight_blocked",
        )
    try:
        index_snapshot = snapshot_git_index(repo_root)
    except (OSError, ValueError):
        return _operation_result(operation, status="blocked", reason="git_preflight_blocked")
    try:
        managed_snapshot = snapshot_managed_sync_state(repo_root)
    except ValueError:
        return _operation_result(
            operation,
            status="blocked",
            reason="managed_state_snapshot_rejected",
        )
    except OSError:
        return _operation_result(operation, status="blocked", reason="git_preflight_blocked")
    try:
        file_snapshots = {path: target_guard.snapshot(path) for path in operation.canonical_target_paths}
        companion_snapshot = target_guard.snapshot(operation.companion_target_path)
        file_snapshots[operation.companion_target_path] = companion_snapshot
    except (OSError, ValueError):
        return _operation_result(
            operation,
            status="rejected",
            reason="apply_output_rejected",
        )
    canonical_preimages_match = all(
        snapshot.existed
        and snapshot.data == operation.pre_apply_document_bytes[PurePosixPath(path).name]
        and _git_blob_oid(snapshot.data) == operation.pre_apply_target_blob_oids[path]
        for path, snapshot in ((path, file_snapshots[path]) for path in operation.canonical_target_paths)
    )
    expected_companion_existed, expected_companion_bytes, expected_companion_oid = expected_companion
    companion_preimage_matches = (
        companion_snapshot.existed == expected_companion_existed
        and companion_snapshot.data == expected_companion_bytes
        and (
            (not companion_snapshot.existed and expected_companion_oid is None)
            or (companion_snapshot.existed and _git_blob_oid(companion_snapshot.data) == expected_companion_oid)
        )
    )
    if (
        not canonical_preimages_match
        or not companion_preimage_matches
        or (
            operation.replacement_companion is not None
            and companion_snapshot.existed
            and companion_snapshot.data != operation.replacement_companion
        )
    ):
        return _operation_result(
            operation,
            status="stale",
            reason="apply_target_changed",
        )
    try:
        decision_snapshot = target_guard.snapshot(operation.decision_artifact_path)
        if decision_snapshot.existed:
            return _operation_result(
                operation,
                status="rejected",
                reason="operation_identity_collision",
            )
        _persist_transaction_backup(
            handle,
            operation,
            index_snapshot=index_snapshot,
            file_snapshots=file_snapshots,
            decision_snapshot=decision_snapshot,
            managed_snapshot=managed_snapshot,
            target_parent_identities=target_guard.parent_identities,
        )
        _set_operation_state(handle, operation, "BACKED_UP")
    except (OSError, ValueError):
        return _operation_result(operation, status="blocked", reason="git_preflight_blocked")

    mutation_started = False
    failure_reason = "planning_commit_failed"
    target_drift = False
    preserved_drift_paths: set[str] = set()
    committed = False
    local_commit: str | None = None
    local_tree: str | None = None
    mutations: list[_TargetMutation] = []
    try:
        if fault_hook is not None:
            fault_hook("after_operation_recorded")
        if not _apply_targets_match_snapshots(
            operation,
            repo_root,
            file_snapshots,
            target_guard=target_guard,
        ):
            try:
                _discard_pre_mutation_backup(
                    handle,
                    operation,
                    final_state="OPERATION_RECORDED",
                )
            except (OSError, ValueError):
                return _operation_result(
                    operation,
                    status="recovery_required",
                    reason="restore_mismatch",
                )
            return _operation_result(
                operation,
                status="stale",
                reason="apply_target_changed",
            )
        try:
            _set_operation_state(handle, operation, "MUTATING")
        except (OSError, ValueError):
            return _operation_result(
                operation,
                status="recovery_required",
                reason="restore_mismatch",
            )
        mutation_started = True
        _apply_guarded_mutation(
            target_guard,
            handle,
            operation,
            mutations,
            relative=operation.decision_artifact_path,
            expected=decision_snapshot,
            replacement=operation.human_decision_bytes,
            mode=0o600,
        )
        if fault_hook is not None:
            fault_hook("after_decision_write")
        if operation.decision == "approved" and operation.mode == "archive-candidate":
            for filename, checkpoint in (
                ("requirement.md", "after_requirement_replace"),
                ("design.md", "after_design_replace"),
                ("plan.md", "after_plan_replace"),
            ):
                replacement = operation.replacement_documents.get(filename)
                if replacement is None:
                    raise _ApplyFailure("adoption_semantic_mutation")
                relative = _path_for_filename(operation.canonical_target_paths, filename)
                mode = file_snapshots[relative].mode
                _apply_guarded_mutation(
                    target_guard,
                    handle,
                    operation,
                    mutations,
                    relative=relative,
                    expected=file_snapshots[relative],
                    replacement=replacement,
                    mode=mode,
                )
                if fault_hook is not None:
                    fault_hook(checkpoint)
            for relative in operation.canonical_target_paths:
                filename = PurePosixPath(relative).name
                if target_guard.read(relative) != operation.replacement_documents[filename]:
                    raise _ApplyFailure("candidate_parity_failed")
        if operation.replacement_companion is not None:
            if not companion_snapshot.existed:
                _apply_guarded_mutation(
                    target_guard,
                    handle,
                    operation,
                    mutations,
                    relative=operation.companion_target_path,
                    expected=companion_snapshot,
                    replacement=operation.replacement_companion,
                    mode=0o644,
                )
            if fault_hook is not None:
                fault_hook("after_companion_write")
            if target_guard.read(operation.companion_target_path) != operation.replacement_companion:
                raise _ApplyFailure("candidate_parity_failed")
            if fault_hook is not None:
                fault_hook("after_companion_parity")
        if _git_bound_targets_are_stale(operation, repo_root):
            raise _ApplyFailure("apply_target_changed")
        if fault_hook is not None:
            fault_hook("after_canonical_proof")

        validation = validation_runner()
        errors = getattr(getattr(validation, "report", None), "errors", None)
        if errors is None or errors:
            raise _ApplyFailure("specdock_validation_failed")
        if fault_hook is not None:
            fault_hook("after_validation")
        _set_operation_state(handle, operation, "VALIDATED")

        sync = sync_runner()
        if (
            getattr(sync, "artifact_failure", None) is not None
            or getattr(getattr(sync, "state", None), "deps_preflight_error", None) is not None
        ):
            raise _ApplyFailure("specdock_sync_failed")
        if not _sync_write_result_is_scoped(sync, repo_root):
            raise _ApplyFailure("specdock_sync_failed")
        if fault_hook is not None:
            fault_hook("after_sync")
        _set_operation_state(handle, operation, "SYNCED")

        expected_paths = {operation.decision_artifact_path}
        if operation.decision == "approved" and operation.mode == "archive-candidate":
            expected_paths.update(
                relative
                for relative in operation.canonical_target_paths
                if target_guard.read(relative) != file_snapshots[relative].data
            )
        if operation.replacement_companion is not None and not companion_snapshot.existed:
            expected_paths.add(operation.companion_target_path)
        changed = _changed_paths(repo_root)
        untracked = _git_text(
            repo_root,
            "ls-files",
            "--others",
            "--exclude-standard",
            "-z",
        )
        if changed is None:
            raise _ApplyFailure("apply_diff_out_of_scope")
        actual = set(changed)
        if untracked:
            actual.update(item for item in untracked.split("\0") if item)
        if actual != expected_paths:
            raise _ApplyFailure("apply_diff_out_of_scope")
        if fault_hook is not None:
            fault_hook("after_diff_proof")

        add_result = _run_git(repo_root, ("add", "--", *sorted(expected_paths)))
        if add_result.returncode != 0 or _changed_paths(repo_root, cached=True) != expected_paths:
            raise _ApplyFailure("planning_commit_failed")
        local_tree = _git_text(repo_root, "write-tree")
        if local_tree is None:
            raise _ApplyFailure("planning_commit_failed")
        try:
            expected_staged_oids = _expected_staged_blob_oids(
                operation,
                expected_companion_oid=expected_companion_oid,
            )
        except ValueError:
            raise _ApplyFailure("planning_commit_failed") from None
        staged_oids = _tree_blob_oids(
            repo_root,
            local_tree,
            tuple(expected_staged_oids),
        )
        if staged_oids is None or staged_oids != expected_staged_oids:
            raise _ApplyFailure("planning_commit_failed")
        if fault_hook is not None:
            fault_hook("after_index_stage")
            fault_hook("before_commit")
        _set_operation_state(handle, operation, "STAGED")

        subject = (
            f"docs({operation.issue_id}): adopt reviewed planning"
            if operation.decision == "approved"
            else f"docs({operation.issue_id}): record rejected planning decision"
        )
        local_commit = _create_verified_operation_commit(
            operation,
            repo_root=repo_root,
            local_tree=local_tree,
            expected_paths=expected_paths,
            subject=subject,
            fault_hook=fault_hook,
        )
        _install_operation_commit_cas(
            operation,
            repo_root=repo_root,
            local_commit=local_commit,
            local_tree=local_tree,
            expected_paths=expected_paths,
        )
        committed = True
        _run_git(repo_root, ("hook", "run", "--ignore-missing", "post-commit"))
        _write_private_no_replace_at(
            handle,
            "commit.json",
            _canonical_json_bytes({
                "operation_id": operation.operation_id,
                "local_commit": local_commit,
                "local_tree": local_tree,
                "decision": operation.decision,
            }),
        )
        _set_operation_state(handle, operation, "COMMITTED")
        if fault_hook is not None:
            fault_hook("after_commit")
        post_commit_status = _git_text(repo_root, "status", "--porcelain=v2", "-z")
        if post_commit_status != "":
            return _operation_result(
                operation,
                status="recovery_required",
                reason="post_commit_workspace_changed",
                local_commit=local_commit,
                local_tree=local_tree,
            )
        _remove_transaction_backup(handle)
        return _publish_initial_operation_commit(
            operation,
            repo_root=repo_root,
            handle=handle,
            authority=publication_authority,
            local_commit=local_commit,
            local_tree=local_tree,
            fault_hook=fault_hook,
        )
    except _ApplyTargetDrift as error:
        failure_reason = "apply_target_changed"
        target_drift = True
        preserved_drift_paths.add(error.relative)
    except _ApplyFailure as error:
        failure_reason = error.reason
    except PlanningApplyRestoreMismatch:
        return _operation_result(
            operation,
            status="recovery_required",
            reason="restore_mismatch",
            local_commit=local_commit,
            local_tree=local_tree,
        )
    except Exception:
        if committed:
            return _operation_result(
                operation,
                status="publication_pending",
                reason="remote_parity_unconfirmed",
                local_commit=local_commit,
                local_tree=local_tree,
            )
        failure_reason = "planning_commit_failed"

    if not mutation_started:
        return _operation_result(operation, status="blocked", reason="git_preflight_blocked")
    try:
        _restore_transaction(
            operation,
            repo_root=repo_root,
            handle=handle,
            index_snapshot=index_snapshot,
            managed_snapshot=managed_snapshot,
            fault_hook=fault_hook,
            target_guard=target_guard,
            mutations=mutations,
            preserved_drift_paths=preserved_drift_paths,
        )
    except (OSError, PlanningApplyRestoreMismatch, ValueError):
        return _operation_result(
            operation,
            status="recovery_required",
            reason="restore_mismatch",
        )
    try:
        _finalize_transaction_cleanup(
            handle,
            operation,
            final_state=("OPERATION_RECORDED" if target_drift else "ROLLED_BACK"),
        )
    except (OSError, ValueError):
        return _operation_result(
            operation,
            status="recovery_required",
            reason="restore_mismatch",
        )
    if target_drift:
        return _operation_result(operation, status="stale", reason="apply_target_changed")
    return _operation_result(operation, status="rolled_back", reason=failure_reason)


def _recover_interrupted_transaction(
    operation: PlanningApplyOperation,
    *,
    repo_root: Path,
    handle: _ApplyEvidenceHandle,
    target_guard: _RepositoryTargetGuard,
    authority: _PublicationAuthority,
) -> PlanningApplyExecution:
    try:
        state = _load_operation_state(handle, operation)
    except PlanningApplyRestoreMismatch:
        return _operation_result(
            operation,
            status="recovery_required",
            reason="restore_mismatch",
        )
    if (
        state not in {"BACKED_UP", *_TRANSACTION_RESTORE_STATES}
        or _entry_exists_at(handle, "commit.json")
        or _entry_exists_at(handle, "publication.json")
    ):
        return _operation_result(
            operation,
            status="recovery_required",
            reason="restore_mismatch",
        )
    if state == "BACKED_UP":
        try:
            backup = _load_transaction_backup(
                handle,
                operation,
                repo_root=repo_root,
            )
        except (OSError, ValueError, PlanningApplyRestoreMismatch):
            return _operation_result(
                operation,
                status="recovery_required",
                reason="restore_mismatch",
            )
        if target_guard.parent_identities != backup.target_parent_identities:
            return _operation_result(
                operation,
                status="recovery_required",
                reason="restore_mismatch",
            )
        if not _apply_targets_match_snapshots(
            operation,
            repo_root,
            backup.files,
            target_guard=target_guard,
        ):
            try:
                _discard_pre_mutation_backup(
                    handle,
                    operation,
                    final_state="OPERATION_RECORDED",
                )
            except (OSError, ValueError):
                return _operation_result(
                    operation,
                    status="recovery_required",
                    reason="restore_mismatch",
                )
            return _operation_result(
                operation,
                status="stale",
                reason="apply_target_changed",
            )
        if _remote_head(repo_root, authority, operation.branch) != operation.expected_head:
            return _operation_result(
                operation,
                status="recovery_required",
                reason="restore_mismatch",
            )
        try:
            _discard_pre_mutation_backup(
                handle,
                operation,
                final_state="ROLLED_BACK",
            )
        except (OSError, ValueError):
            return _operation_result(
                operation,
                status="recovery_required",
                reason="restore_mismatch",
            )
        return _operation_result(
            operation,
            status="rolled_back",
            reason="planning_commit_failed",
        )
    if (
        _git_text(repo_root, "branch", "--show-current") != operation.branch
        or _git_text(repo_root, "rev-parse", "HEAD") != operation.expected_head
    ):
        return _operation_result(
            operation,
            status="recovery_required",
            reason="restore_mismatch",
        )
    try:
        backup = _load_transaction_backup(
            handle,
            operation,
            repo_root=repo_root,
        )
        if target_guard.parent_identities != backup.target_parent_identities:
            raise PlanningApplyRestoreMismatch("repository target parent identity changed")
        _restore_transaction(
            operation,
            repo_root=repo_root,
            handle=handle,
            index_snapshot=backup.index,
            managed_snapshot=backup.managed,
            fault_hook=None,
            target_guard=target_guard,
            mutations=_load_target_mutations(
                handle,
                operation,
                file_snapshots=backup.files,
                decision_snapshot=backup.decision,
            ),
            preserved_drift_paths=set(),
        )
        if _remote_head(repo_root, authority, operation.branch) != operation.expected_head:
            raise PlanningApplyRestoreMismatch("remote changed during recovery")
    except (OSError, ValueError, PlanningApplyRestoreMismatch):
        return _operation_result(
            operation,
            status="recovery_required",
            reason="restore_mismatch",
        )
    try:
        _finalize_transaction_cleanup(
            handle,
            operation,
            final_state="ROLLED_BACK",
        )
    except (OSError, ValueError):
        return _operation_result(
            operation,
            status="recovery_required",
            reason="restore_mismatch",
        )
    return _operation_result(
        operation,
        status="rolled_back",
        reason="planning_commit_failed",
    )


class _ApplyFailure(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _path_for_filename(paths: tuple[str, str, str], filename: str) -> str:
    matches = [path for path in paths if PurePosixPath(path).name == filename]
    if len(matches) != 1:
        raise _ApplyFailure("adoption_semantic_mutation")
    return matches[0]


def _git_bound_targets_are_stale(
    operation: PlanningApplyOperation,
    repo_root: Path,
) -> bool:
    if operation.mode != "git-bound":
        return False
    for relative in operation.canonical_target_paths:
        expected = operation.pre_apply_target_blob_oids.get(relative)
        actual = _git_text(
            repo_root,
            "hash-object",
            "--",
            relative,
        )
        reviewed = _git_text(
            repo_root,
            "rev-parse",
            f"{operation.expected_head}:{relative}",
        )
        if expected is None or actual != expected or reviewed != expected:
            return True
    return False


def _recover_workspace_intent(
    target_guard: _RepositoryTargetGuard,
    handle: _ApplyEvidenceHandle,
    operation: PlanningApplyOperation,
    mutations: list[_TargetMutation],
) -> None:
    intent = _load_workspace_intent(handle, operation)
    if intent is None:
        return
    target_guard.resolve_workspace_intent(intent, mutations)
    _persist_workspace_intent(handle, operation, mutations, None)


def _restore_transaction(
    operation: PlanningApplyOperation,
    *,
    repo_root: Path,
    handle: _ApplyEvidenceHandle,
    index_snapshot: GitIndexSnapshot,
    managed_snapshot: Mapping[str, ManagedStateEntry],
    fault_hook: Callable[[str], None] | None,
    target_guard: _RepositoryTargetGuard,
    mutations: list[_TargetMutation],
    preserved_drift_paths: set[str],
) -> None:
    if fault_hook is not None:
        fault_hook("during_restore")
    _recover_workspace_intent(
        target_guard,
        handle,
        operation,
        mutations,
    )
    restore_managed_sync_state(repo_root, managed_snapshot)
    while mutations:
        mutation = mutations[-1]
        resolved = target_guard.resolve_prepared(mutation)
        if resolved is None:
            mutations.pop()
            _persist_target_mutations(handle, operation, mutations)
            continue
        if resolved != mutation:
            mutations[-1] = resolved
            _persist_target_mutations(handle, operation, mutations)

        def phase_update(updated: _TargetMutation) -> None:
            mutations[-1] = updated
            _persist_target_mutations(handle, operation, mutations)

        def workspace_intent_update(intent: _WorkspaceIntent | None) -> None:
            _persist_workspace_intent(handle, operation, mutations, intent)

        target_guard.restore(
            resolved,
            phase_update=phase_update,
            workspace_intent_update=workspace_intent_update,
        )
        target_guard.cleanup_workspace(resolved)
        mutations.pop()
        _persist_target_mutations(handle, operation, mutations)
    restore_git_index(repo_root, index_snapshot)
    if fault_hook is not None:
        fault_hook("after_restore")
    if _git_text(repo_root, "rev-parse", "HEAD") != operation.expected_head:
        raise PlanningApplyRestoreMismatch("HEAD changed during rollback")
    status = _git_text(repo_root, "status", "--porcelain=v2", "-z")
    changed = _changed_paths(repo_root)
    untracked = _git_text(
        repo_root,
        "ls-files",
        "--others",
        "--exclude-standard",
        "-z",
    )
    actual = set() if changed is None else set(changed)
    if untracked:
        actual.update(item for item in untracked.split("\0") if item)
    if status is None or actual != preserved_drift_paths:
        raise PlanningApplyRestoreMismatch("worktree changed during rollback")
    # Some Git builds refresh index stat data during a read-only status. Restore
    # the captured bytes once more so the transaction postcondition is byte-exact.
    restore_git_index(repo_root, index_snapshot)
    if snapshot_managed_sync_state(repo_root) != managed_snapshot:
        raise PlanningApplyRestoreMismatch("managed sync state restore mismatch")


def _resume_publication(
    operation: PlanningApplyOperation,
    *,
    repo_root: Path,
    handle: _ApplyEvidenceHandle,
    authority: _PublicationAuthority,
    fault_hook: Callable[[str], None] | None,
) -> PlanningApplyExecution:
    try:
        commit_bytes = _read_private_file_at(handle, "commit.json")
        commit = json.loads(commit_bytes)
        if (
            not isinstance(commit, dict)
            or set(commit) != {"operation_id", "local_commit", "local_tree", "decision"}
            or commit.get("operation_id") != operation.operation_id
            or not isinstance(commit.get("local_commit"), str)
            or not isinstance(commit.get("local_tree"), str)
            or commit.get("decision") != operation.decision
            or _canonical_json_bytes(commit) != commit_bytes
        ):
            raise ValueError
        local_commit = commit["local_commit"]
        local_tree = commit["local_tree"]
    except (OSError, ValueError, json.JSONDecodeError):
        return _operation_result(
            operation,
            status="rejected",
            reason="operation_identity_collision",
        )
    expected_paths = _expected_operation_commit_paths(operation, repo_root)
    decision_path = repo_root / operation.decision_artifact_path
    if (
        _SHA40.fullmatch(local_commit) is None
        or _SHA40.fullmatch(local_tree) is None
        or not _operation_commit_is_proven(
            operation,
            repo_root=repo_root,
            local_commit=local_commit,
            local_tree=local_tree,
            expected_paths=expected_paths,
        )
        or not _owned_private_file(decision_path)
        or decision_path.read_bytes() != operation.human_decision_bytes
        or _git_text(repo_root, "status", "--porcelain=v2", "-z") != ""
        or not _operation_documents_match_committed_state(operation, repo_root)
    ):
        return _operation_result(
            operation,
            status="recovery_required",
            reason="restore_mismatch",
        )
    try:
        with _acquire_operation_branch_lock(repo_root, operation, local_commit) as branch_lock:
            if not _operation_branch_commit_is_proven(
                operation,
                repo_root,
                local_commit,
                branch_lock=branch_lock,
            ):
                return _operation_result(
                    operation,
                    status="recovery_required",
                    reason="restore_mismatch",
                    local_commit=local_commit,
                    local_tree=local_tree,
                )
            remote_disposition, remote = _remote_head_observation(
                repo_root,
                authority,
                operation.branch,
            )
            if remote_disposition == "absent":
                return _operation_result(
                    operation,
                    status="blocked_remote_diverged",
                    reason="remote_diverged",
                    local_commit=local_commit,
                    local_tree=local_tree,
                )
            if remote_disposition == "unavailable" or remote is None:
                return _operation_result(
                    operation,
                    status="publication_pending",
                    reason="remote_parity_unconfirmed",
                    local_commit=local_commit,
                    local_tree=local_tree,
                )
            if remote == operation.expected_head:
                if fault_hook is not None:
                    fault_hook("before_push")
                push = _push_operation_commit_cas(
                    operation=operation,
                    repo_root=repo_root,
                    authority=authority,
                    expected_remote_head=operation.expected_head,
                    local_commit=local_commit,
                    local_tree=local_tree,
                    branch_lock=branch_lock,
                )
                if push.returncode != 0:
                    failure = _cas_failure_result(
                        operation,
                        repo_root=repo_root,
                        authority=authority,
                        local_commit=local_commit,
                        local_tree=local_tree,
                    )
                    if failure is not None:
                        return failure
                remote = _remote_head(repo_root, authority, operation.branch)
            elif remote != local_commit:
                return _operation_result(
                    operation,
                    status="blocked_remote_diverged",
                    reason="remote_diverged",
                    local_commit=local_commit,
                    local_tree=local_tree,
                    remote_commit=remote,
                )
            if (
                remote != local_commit
                or _git_text(repo_root, "rev-parse", f"{remote}^{{tree}}") != local_tree
                or not _operation_branch_commit_is_proven(
                    operation,
                    repo_root,
                    local_commit,
                    branch_lock=branch_lock,
                )
            ):
                return _operation_result(
                    operation,
                    status="publication_pending",
                    reason="remote_parity_unconfirmed",
                    local_commit=local_commit,
                    local_tree=local_tree,
                    remote_commit=remote,
                )
            _record_publication(handle, operation, local_commit, local_tree)
            _set_operation_state(handle, operation, "REMOTE_PARITY")
            _remove_transaction_backup(handle)
            return _operation_result(
                operation,
                status="ready" if operation.decision == "approved" else "rejected",
                reason="adoption_published" if operation.decision == "approved" else "plan_rejected",
                local_commit=local_commit,
                local_tree=local_tree,
                remote_commit=remote,
            )
    except PlanningApplyRestoreMismatch:
        return _operation_result(
            operation,
            status="recovery_required",
            reason="restore_mismatch",
            local_commit=local_commit,
            local_tree=local_tree,
        )


def _expected_operation_commit_paths(
    operation: PlanningApplyOperation,
    repo_root: Path,
) -> set[str]:
    paths = {operation.decision_artifact_path}
    if operation.mode == "archive-candidate" and operation.decision == "approved":
        for relative in operation.canonical_target_paths:
            filename = PurePosixPath(relative).name
            if operation.replacement_documents.get(filename) != operation.pre_apply_document_bytes.get(filename):
                paths.add(relative)
    if operation.decision == "approved":
        reviewed_companion = _git_text(
            repo_root,
            "rev-parse",
            f"{operation.expected_head}:{operation.companion_target_path}",
        )
        if reviewed_companion is None:
            paths.add(operation.companion_target_path)
    return paths


def _operation_documents_match_committed_state(
    operation: PlanningApplyOperation,
    repo_root: Path,
) -> bool:
    for relative in operation.canonical_target_paths:
        filename = PurePosixPath(relative).name
        expected = operation.pre_apply_document_bytes.get(filename)
        if operation.mode == "archive-candidate" and operation.decision == "approved":
            expected = operation.replacement_documents.get(filename)
        if expected is None:
            return False
        try:
            if (repo_root / relative).read_bytes() != expected:
                return False
        except OSError:
            return False
    if operation.decision == "approved":
        try:
            companion = (repo_root / operation.companion_target_path).read_bytes()
        except OSError:
            return False
        if hashlib.sha256(companion).hexdigest() != operation.companion_sha256:
            return False
    return True


def _record_publication(
    handle: _ApplyEvidenceHandle,
    operation: PlanningApplyOperation,
    local_commit: str,
    local_tree: str,
) -> None:
    data = _canonical_json_bytes({
        "operation_id": operation.operation_id,
        "local_commit": local_commit,
        "local_tree": local_tree,
        "remote_commit": local_commit,
    })
    if _entry_exists_at(handle, "publication.json"):
        if _read_private_file_at(handle, "publication.json") != data:
            raise PlanningApplyOutputRejected("publication evidence collision")
        return
    _write_private_no_replace_at(handle, "publication.json", data)


def _persist_transaction_backup(
    handle: _ApplyEvidenceHandle,
    operation: PlanningApplyOperation,
    *,
    index_snapshot: GitIndexSnapshot,
    file_snapshots: Mapping[str, FileSnapshot],
    decision_snapshot: FileSnapshot,
    managed_snapshot: Mapping[str, ManagedStateEntry],
    target_parent_identities: Mapping[str, tuple[int, int]],
) -> None:
    _mkdir_private_at(handle, "transaction")
    _mkdir_private_at(handle, "transaction/files")
    _mkdir_private_at(handle, "transaction/managed-state")
    _write_private_no_replace_at(handle, "transaction/git-index.bin", index_snapshot.data)
    entries: list[dict[str, object]] = []
    for relative, snapshot in sorted(
        file_snapshots.items(),
        key=lambda item: item[0].encode("utf-8"),
    ):
        backup_name = f"{hashlib.sha256(relative.encode()).hexdigest()}.bin"
        _write_private_no_replace_at(handle, f"transaction/files/{backup_name}", snapshot.data)
        entries.append({
            "path": relative,
            "backup": backup_name,
            "existed": snapshot.existed,
            "mode": snapshot.mode,
            "sha256": snapshot.sha256,
        })
    manifest = {
        "operation_id": operation.operation_id,
        "index": {
            "mode": index_snapshot.mode,
            "sha256": index_snapshot.sha256,
        },
        "files": entries,
        "decision_artifact": {
            "path": operation.decision_artifact_path,
            "existed": decision_snapshot.existed,
        },
        "target_parents": [
            {
                "path": relative,
                "device": identity[0],
                "inode": identity[1],
            }
            for relative, identity in sorted(
                target_parent_identities.items(),
                key=lambda item: item[0].encode("utf-8"),
            )
        ],
        "managed_state": [],
    }
    managed_entries = manifest["managed_state"]
    assert isinstance(managed_entries, list)
    for relative, managed_entry in sorted(
        managed_snapshot.items(),
        key=lambda item: item[0].encode("utf-8"),
    ):
        backup_name = f"{hashlib.sha256(relative.encode()).hexdigest()}.bin"
        backup_data = (
            managed_entry.data if managed_entry.kind == "file" else (managed_entry.target or "").encode("utf-8")
        )
        _write_private_no_replace_at(handle, f"transaction/managed-state/{backup_name}", backup_data)
        managed_entries.append({
            "path": relative,
            "backup": backup_name,
            "kind": managed_entry.kind,
            "mode": managed_entry.mode,
            "sha256": hashlib.sha256(backup_data).hexdigest(),
        })
    _write_private_no_replace_at(
        handle,
        "transaction/backup-manifest.json",
        _canonical_json_bytes(manifest),
    )
    _write_private_no_replace_at(
        handle,
        "transaction/mutation-ledger.json",
        _canonical_json_bytes({
            "operation_id": operation.operation_id,
            "workspace_intent": None,
            "entries": [],
        }),
    )


def _load_transaction_backup(
    handle: _ApplyEvidenceHandle,
    operation: PlanningApplyOperation,
    *,
    repo_root: Path,
) -> DurableTransactionBackup:
    if not _owned_private_directory_at(handle.operation_fd, "transaction") or not _owned_private_file_at(
        handle, "transaction/backup-manifest.json"
    ):
        raise ValueError("transaction backup is unsafe")
    manifest_bytes = _read_private_file_at(handle, "transaction/backup-manifest.json")
    manifest = json.loads(manifest_bytes)
    if (
        not isinstance(manifest, dict)
        or set(manifest)
        != {
            "operation_id",
            "index",
            "files",
            "decision_artifact",
            "target_parents",
            "managed_state",
        }
        or manifest.get("operation_id") != operation.operation_id
        or _canonical_json_bytes(manifest) != manifest_bytes
    ):
        raise ValueError("transaction backup manifest mismatch")

    index_value = manifest["index"]
    if (
        not isinstance(index_value, dict)
        or set(index_value) != {"mode", "sha256"}
        or isinstance(index_value.get("mode"), bool)
        or not isinstance(index_value.get("mode"), int)
        or not isinstance(index_value.get("sha256"), str)
        or _SHA256.fullmatch(index_value["sha256"]) is None
        or not _owned_private_file_at(handle, "transaction/git-index.bin")
    ):
        raise ValueError("transaction index backup mismatch")
    index_bytes = _read_private_file_at(handle, "transaction/git-index.bin")
    if hashlib.sha256(index_bytes).hexdigest() != index_value["sha256"]:
        raise ValueError("transaction index backup mismatch")
    index_snapshot = GitIndexSnapshot(
        path=_git_index_path(repo_root),
        data=index_bytes,
        mode=index_value["mode"],
        sha256=index_value["sha256"],
    )

    file_values = manifest["files"]
    if not isinstance(file_values, list):
        raise ValueError("transaction file backup mismatch")
    file_snapshots: dict[str, FileSnapshot] = {}
    expected_file_backups: set[str] = set()
    allowed_file_paths = {
        *operation.canonical_target_paths,
        operation.companion_target_path,
    }
    for value in file_values:
        if (
            not isinstance(value, dict)
            or set(value) != {"path", "backup", "existed", "mode", "sha256"}
            or not isinstance(value.get("path"), str)
            or value["path"] not in allowed_file_paths
            or value["path"] in file_snapshots
            or not isinstance(value.get("existed"), bool)
            or (value["path"] in operation.canonical_target_paths and value["existed"] is not True)
            or isinstance(value.get("mode"), bool)
            or not isinstance(value.get("mode"), int)
            or not isinstance(value.get("sha256"), str)
            or _SHA256.fullmatch(value["sha256"]) is None
        ):
            raise ValueError("transaction file backup mismatch")
        expected_backup = f"{hashlib.sha256(value['path'].encode()).hexdigest()}.bin"
        if value.get("backup") != expected_backup:
            raise ValueError("transaction file backup mismatch")
        backup_relative = f"transaction/files/{expected_backup}"
        if not _owned_private_file_at(handle, backup_relative):
            raise ValueError("transaction file backup mismatch")
        data = _read_private_file_at(handle, backup_relative)
        if hashlib.sha256(data).hexdigest() != value["sha256"]:
            raise ValueError("transaction file backup mismatch")
        expected_file_backups.add(expected_backup)
        file_snapshots[value["path"]] = FileSnapshot(
            existed=value["existed"],
            data=data,
            mode=value["mode"],
            sha256=value["sha256"],
        )
    if (
        set(file_snapshots) != allowed_file_paths
        or not _owned_private_subdirectory_at(handle, "transaction/files")
        or _list_directory_at(handle, "transaction/files") != expected_file_backups
    ):
        raise ValueError("transaction file backup inventory mismatch")

    decision_value = manifest["decision_artifact"]
    if (
        not isinstance(decision_value, dict)
        or set(decision_value) != {"path", "existed"}
        or decision_value.get("path") != operation.decision_artifact_path
        or decision_value.get("existed") is not False
    ):
        raise ValueError("transaction decision backup mismatch")
    decision_snapshot = FileSnapshot(
        existed=False,
        data=b"",
        mode=0,
        sha256=hashlib.sha256(b"").hexdigest(),
    )

    parent_values = manifest["target_parents"]
    allowed_parent_paths = {
        *operation.canonical_target_paths,
        operation.companion_target_path,
        operation.decision_artifact_path,
    }
    if not isinstance(parent_values, list):
        raise ValueError("transaction target parent backup mismatch")
    target_parent_identities: dict[str, tuple[int, int]] = {}
    for value in parent_values:
        if (
            not isinstance(value, dict)
            or set(value) != {"path", "device", "inode"}
            or not isinstance(value.get("path"), str)
            or value["path"] not in allowed_parent_paths
            or value["path"] in target_parent_identities
            or isinstance(value.get("device"), bool)
            or not isinstance(value.get("device"), int)
            or isinstance(value.get("inode"), bool)
            or not isinstance(value.get("inode"), int)
        ):
            raise ValueError("transaction target parent backup mismatch")
        target_parent_identities[value["path"]] = (
            value["device"],
            value["inode"],
        )
    if set(target_parent_identities) != allowed_parent_paths:
        raise ValueError("transaction target parent backup mismatch")

    managed_values = manifest["managed_state"]
    if not isinstance(managed_values, list):
        raise ValueError("transaction managed backup mismatch")
    managed_snapshots: dict[str, ManagedStateEntry] = {}
    expected_managed_backups: set[str] = set()
    for value in managed_values:
        if (
            not isinstance(value, dict)
            or set(value) != {"path", "backup", "kind", "mode", "sha256"}
            or not isinstance(value.get("path"), str)
            or not _managed_path_is_allowed(value["path"])
            or value["path"] in managed_snapshots
            or value.get("kind") not in {"file", "directory", "symlink"}
            or isinstance(value.get("mode"), bool)
            or not isinstance(value.get("mode"), int)
            or not isinstance(value.get("sha256"), str)
            or _SHA256.fullmatch(value["sha256"]) is None
        ):
            raise ValueError("transaction managed backup mismatch")
        expected_backup = f"{hashlib.sha256(value['path'].encode()).hexdigest()}.bin"
        if value.get("backup") != expected_backup:
            raise ValueError("transaction managed backup mismatch")
        backup_relative = f"transaction/managed-state/{expected_backup}"
        if not _owned_private_file_at(handle, backup_relative):
            raise ValueError("transaction managed backup mismatch")
        data = _read_private_file_at(handle, backup_relative)
        if hashlib.sha256(data).hexdigest() != value["sha256"]:
            raise ValueError("transaction managed backup mismatch")
        kind = value["kind"]
        target = data.decode("utf-8", errors="strict") if kind == "symlink" else None
        managed_snapshots[value["path"]] = ManagedStateEntry(
            kind=kind,
            mode=value["mode"],
            data=data if kind == "file" else b"",
            target=target,
        )
        expected_managed_backups.add(expected_backup)
    if (
        not _owned_private_subdirectory_at(handle, "transaction/managed-state")
        or _list_directory_at(handle, "transaction/managed-state") != expected_managed_backups
    ):
        raise ValueError("transaction managed backup inventory mismatch")
    return DurableTransactionBackup(
        index=index_snapshot,
        files=MappingProxyType(file_snapshots),
        decision=decision_snapshot,
        managed=MappingProxyType(managed_snapshots),
        target_parent_identities=MappingProxyType(target_parent_identities),
    )


def _managed_path_is_allowed(value: str) -> bool:
    return value in _MANAGED_SYNC_FILES or value == _MANAGED_SYNC_TREE or value.startswith(f"{_MANAGED_SYNC_TREE}/")


def _unlink_at(handle: _ApplyEvidenceHandle, relative: str) -> None:
    parent, name, opened = _parent_fd(handle, relative)
    try:
        os.unlink(name, dir_fd=parent)
        os.fsync(parent)
    finally:
        _close_opened(opened)


def _rmdir_at(handle: _ApplyEvidenceHandle, relative: str) -> None:
    parent, name, opened = _parent_fd(handle, relative)
    try:
        os.rmdir(name, dir_fd=parent)
        os.fsync(parent)
    finally:
        _close_opened(opened)


def _remove_transaction_backup(handle: _ApplyEvidenceHandle) -> None:
    if not _entry_exists_at(handle, "transaction"):
        return
    if not _owned_private_subdirectory_at(handle, "transaction"):
        raise PlanningApplyOutputRejected("transaction evidence is unsafe")
    root_entries = _list_directory_at(handle, "transaction")
    allowed_root = {
        "files",
        "managed-state",
        "git-index.bin",
        "backup-manifest.json",
        "mutation-ledger.json",
    }
    if not root_entries <= allowed_root:
        raise PlanningApplyOutputRejected("transaction evidence contains unexpected entries")
    for directory in ("files", "managed-state"):
        relative = f"transaction/{directory}"
        if relative.split("/")[-1] in root_entries:
            if not _owned_private_subdirectory_at(handle, relative):
                raise PlanningApplyOutputRejected("transaction evidence is unsafe")
            for name in _list_directory_at(handle, relative):
                child = f"{relative}/{name}"
                if not _owned_private_file_at(handle, child):
                    raise PlanningApplyOutputRejected("transaction evidence is unsafe")
                _unlink_at(handle, child)
            _rmdir_at(handle, relative)
    for filename in ("git-index.bin", "backup-manifest.json", "mutation-ledger.json"):
        relative = f"transaction/{filename}"
        if _entry_exists_at(handle, relative):
            if not _owned_private_file_at(handle, relative):
                raise PlanningApplyOutputRejected("transaction evidence is unsafe")
            _unlink_at(handle, relative)
    _rmdir_at(handle, "transaction")


def snapshot_managed_sync_state(
    repo_root: Path,
) -> Mapping[str, ManagedStateEntry]:
    entries: dict[str, ManagedStateEntry] = {}
    total_bytes = 0

    def capture(path: Path) -> None:
        nonlocal total_bytes
        relative = path.relative_to(repo_root).as_posix()
        opened = path.lstat()
        mode = stat.S_IMODE(opened.st_mode)
        if stat.S_ISLNK(opened.st_mode):
            target = path.readlink().as_posix()
            total_bytes += len(target.encode("utf-8"))
            entries[relative] = ManagedStateEntry(
                kind="symlink",
                mode=mode,
                target=target,
            )
        elif stat.S_ISDIR(opened.st_mode):
            entries[relative] = ManagedStateEntry(kind="directory", mode=mode)
        elif stat.S_ISREG(opened.st_mode):
            data = path.read_bytes()
            total_bytes += len(data)
            entries[relative] = ManagedStateEntry(kind="file", mode=mode, data=data)
        else:
            raise ValueError("managed state contains an unsupported entry")
        if len(entries) > _MAX_MANAGED_ENTRIES or total_bytes > _MAX_MANAGED_BYTES:
            raise ValueError("managed state exceeds transaction bounds")

    for relative in _MANAGED_SYNC_FILES:
        path = repo_root / relative
        if path.exists() or path.is_symlink():
            capture(path)
    tree = repo_root / _MANAGED_SYNC_TREE
    if tree.exists() or tree.is_symlink():
        capture(tree)
        if tree.is_dir() and not tree.is_symlink():
            for path in sorted(tree.rglob("*"), key=lambda item: item.as_posix().encode()):
                capture(path)
    return MappingProxyType(entries)


def restore_managed_sync_state(
    repo_root: Path,
    snapshot: Mapping[str, ManagedStateEntry],
) -> None:
    for relative in _MANAGED_SYNC_FILES:
        _remove_any(repo_root / relative)
    _remove_any(repo_root / _MANAGED_SYNC_TREE)
    directories = [(relative, entry) for relative, entry in snapshot.items() if entry.kind == "directory"]
    for relative, entry in sorted(
        directories,
        key=lambda item: (len(PurePosixPath(item[0]).parts), item[0].encode()),
    ):
        path = repo_root / relative
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(entry.mode)
    for relative, entry in sorted(
        snapshot.items(),
        key=lambda item: item[0].encode("utf-8"),
    ):
        if entry.kind == "directory":
            continue
        path = repo_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if entry.kind == "file":
            _atomic_write_exact(path, entry.data, mode=entry.mode)
        else:
            assert entry.target is not None
            path.symlink_to(entry.target)
    if snapshot_managed_sync_state(repo_root) != snapshot:
        raise PlanningApplyRestoreMismatch("managed sync state restore mismatch")


def _remove_any(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _sync_write_result_is_scoped(sync: object, repo_root: Path) -> bool:
    active_update = getattr(sync, "active_update", None)
    if active_update is not None and getattr(active_update, "applied", False):
        return False
    write_result = getattr(sync, "write_result", None)
    if write_result is None:
        return True
    allowed = set(_MANAGED_SYNC_FILES)
    for value in vars(write_result).values():
        if not isinstance(value, str):
            return False
        path = Path(value)
        if path.is_absolute():
            try:
                relative = path.relative_to(repo_root).as_posix()
            except ValueError:
                return False
        else:
            relative = path.as_posix()
        if relative not in allowed:
            return False
    return True
