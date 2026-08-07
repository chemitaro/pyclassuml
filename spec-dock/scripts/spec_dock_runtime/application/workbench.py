from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from spec_dock_runtime.application.contracts import (
    WorkbenchCopyError,
    WorkbenchCopyRequest,
    WorkbenchCopyResult,
    WorkbenchFilesystemError,
    WorktreeListRequest,
)
from spec_dock_runtime.application.worktree import worktree_list
from spec_dock_runtime.application.worktree_target import resolve_worktree_target
from spec_dock_runtime.domain.ids import parse_id

if TYPE_CHECKING:
    from spec_dock_runtime.application.ports import Ports
    from spec_dock_runtime.infra.contracts import StoredMetaRecord


def workbench_copy(req: WorkbenchCopyRequest, ports: Ports) -> WorkbenchCopyResult:
    _require_ports(ports)
    scope_id = _validate_scope_id(req.scope_id)

    inventory = worktree_list(WorktreeListRequest(), ports).worktrees
    target = resolve_worktree_target(req.target, inventory, command="copy")
    source = next((record for record in inventory if record.current), None)
    if source is None:
        raise WorkbenchCopyError(
            code="source_unavailable",
            message="workbench copy source is unavailable",
            side="source",
        )
    if target.current or "bare_worktree" in target.remove_blockers or not target.path_exists:
        raise WorkbenchCopyError(
            code="target_ineligible",
            message="workbench copy target is not eligible",
            side="target",
        )

    assert ports.repo_root is not None
    assert ports.specdock_dir is not None
    assert ports.node_repo is not None
    assert ports.filesystem_gateway is not None
    try:
        specdock_relative = ports.specdock_dir.relative_to(ports.repo_root)
    except ValueError as exc:
        raise WorkbenchCopyError(
            code="unsafe_path",
            message="workbench copy source layout is invalid",
            side="source",
        ) from exc

    source_specdock = ports.specdock_dir
    target_specdock = target.path / specdock_relative
    _guard_ancestry(ports, ports.repo_root, source_specdock, side="source")
    _guard_ancestry(ports, target.path, target_specdock, side="target")
    _guard_inventory(ports, source_specdock, side="source")
    _guard_inventory(ports, target_specdock, side="target")
    source_scope = _load_scope(ports, source_specdock, scope_id, side="source")
    target_scope = _load_scope(ports, target_specdock, scope_id, side="target")

    source_workbench = Path(source_scope.path) / ".workbench"
    target_workbench = Path(target_scope.path) / ".workbench"
    _guard_ancestry(ports, ports.repo_root, Path(source_scope.path), side="source")
    _guard_ancestry(ports, target.path, Path(target_scope.path), side="target")
    _preflight_scope_root(ports, Path(source_scope.path), side="source")
    _preflight_scope_root(ports, Path(target_scope.path), side="target")
    source_kind = _path_kind(ports, source_workbench, side="source")
    if source_kind == "missing":
        raise WorkbenchCopyError(
            code="no_source",
            message="workbench copy source does not exist",
            side="source",
        )
    if source_kind != "directory":
        raise WorkbenchCopyError(
            code="invalid_workbench_root",
            message="workbench copy source root is invalid",
            side="source",
        )
    _guard_ancestry(ports, ports.repo_root, source_workbench, side="source")
    target_kind = _path_kind(ports, target_workbench, side="target")
    if target_kind not in {"missing", "directory"}:
        raise WorkbenchCopyError(
            code="invalid_workbench_root",
            message="workbench copy target root is invalid",
            side="target",
        )
    _guard_ancestry(
        ports,
        target.path,
        target_workbench,
        side="target",
        allow_missing_leaf=target_kind == "missing",
    )
    try:
        ports.filesystem_gateway.copy_workbench(source_workbench, target_workbench)
    except WorkbenchFilesystemError as exc:
        raise WorkbenchCopyError(
            code="copy_failed",
            message="workbench copy failed",
            mutation_started=exc.mutation_started,
        ) from exc
    return WorkbenchCopyResult(
        scope_id=scope_id,
        source_worktree=source,
        target_worktree=target,
        target_workbench_path=target_workbench,
    )


def _require_ports(ports: Ports) -> None:
    if ports.repo_root is None or ports.specdock_dir is None:
        raise RuntimeError("workbench copy requires repository and spec-dock roots")
    if ports.node_repo is None:
        raise RuntimeError("workbench copy requires a node repository")
    if ports.filesystem_gateway is None:
        raise RuntimeError("workbench copy requires a filesystem gateway")


def _validate_scope_id(value: str) -> str:
    scope_id = value.strip().lower()
    try:
        prefix, is_local, _ = parse_id(scope_id)
    except RuntimeError as exc:
        raise WorkbenchCopyError(
            code="invalid_scope",
            message="workbench copy requires a full initiative, epic, or issue id",
        ) from exc
    if prefix not in {"init", "epic", "iss"} or is_local:
        raise WorkbenchCopyError(
            code="invalid_scope",
            message="workbench copy requires a full initiative, epic, or issue id",
        )
    return scope_id


def _load_scope(ports: Ports, specdock_dir: Path, scope_id: str, *, side: str) -> StoredMetaRecord:
    assert ports.node_repo is not None
    try:
        records = ports.node_repo.load_node_records(specdock_dir)
    except RuntimeError as exc:
        raise WorkbenchCopyError(
            code="invalid_scope",
            message=f"workbench copy {side} scope inventory is invalid",
            side=side,
        ) from exc
    return _resolve_scope(records, scope_id, side=side)


def _resolve_scope(records: list[StoredMetaRecord], scope_id: str, *, side: str) -> StoredMetaRecord:
    matches = [record for record in records if record.id == scope_id]
    if len(matches) != 1:
        raise WorkbenchCopyError(
            code="invalid_scope",
            message=f"workbench copy could not resolve {side} scope",
            side=side,
        )
    return matches[0]


def _preflight_scope_root(ports: Ports, path: Path, *, side: str) -> None:
    if _path_kind(ports, path, side=side) != "directory":
        raise WorkbenchCopyError(
            code="invalid_scope",
            message=f"workbench copy {side} scope root is invalid",
            side=side,
        )


def _path_kind(ports: Ports, path: Path, *, side: str) -> str:
    assert ports.filesystem_gateway is not None
    try:
        return ports.filesystem_gateway.path_kind(path)
    except RuntimeError as exc:
        raise WorkbenchCopyError(
            code="invalid_workbench_root",
            message=f"workbench copy {side} path could not be inspected",
            side=side,
        ) from exc


def _guard_ancestry(
    ports: Ports,
    root: Path,
    endpoint: Path,
    *,
    side: str,
    allow_missing_leaf: bool = False,
) -> None:
    assert ports.filesystem_gateway is not None
    try:
        ports.filesystem_gateway.guard_workbench_ancestry(
            root,
            endpoint,
            allow_missing_leaf=allow_missing_leaf,
        )
    except WorkbenchFilesystemError as exc:
        raise WorkbenchCopyError(
            code="unsafe_path",
            message=f"workbench copy {side} path is unsafe",
            side=side,
            mutation_started=exc.mutation_started,
        ) from exc


def _guard_inventory(ports: Ports, specdock_dir: Path, *, side: str) -> None:
    assert ports.filesystem_gateway is not None
    try:
        ports.filesystem_gateway.guard_workbench_inventory(specdock_dir)
    except WorkbenchFilesystemError as exc:
        raise WorkbenchCopyError(
            code="unsafe_path",
            message=f"workbench copy {side} scope inventory is unsafe",
            side=side,
            mutation_started=exc.mutation_started,
        ) from exc
