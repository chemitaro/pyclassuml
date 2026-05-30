from __future__ import annotations

import re
from pathlib import Path

from .contracts import (
    GitWorktreeRecord,
    WorktreeCommandError,
    WorktreeCreateRequest,
    WorktreeCreateResult,
    WorktreeListRequest,
    WorktreeListResult,
    WorktreeRecordView,
    WorktreeRemoveRequest,
    WorktreeRemoveResult,
    WorktreeShowRequest,
    WorktreeShowResult,
)
from .ports import Ports


_LABEL_RE = re.compile(r"^[a-z0-9-]+$")
_MAX_ATTEMPTS = 10000
_RETRYABLE_GIT_WORKTREE_ERRORS = (
    "already exists",
    "is already checked out",
    "a branch named",
)
_WORKTREE_ROOT_ENV = "SPEC_DOCK_WORKTREE_ROOT"
_WORKTREE_ROOT_EXAMPLE = "export SPEC_DOCK_WORKTREE_ROOT=\"$HOME/workspace/worktrees\""


def worktree_create(req: WorktreeCreateRequest, ports: Ports) -> WorktreeCreateResult:
    if ports.repo_root is None:
        raise RuntimeError("worktree create requires a repository root")
    if ports.git_gateway is None:
        raise RuntimeError("worktree create requires a Git gateway")
    if ports.bootstrap_gateway is None:
        raise RuntimeError("worktree create requires a bootstrap gateway")
    if ports.environment_gateway is None:
        raise RuntimeError("worktree create requires an environment gateway")

    label = _normalize_label(req.label)
    central_root = _resolve_worktree_root(ports)
    repo_root = ports.repo_root
    branch_prefix = ports.git_gateway.current_branch_or_none(repo_root)
    if branch_prefix is None:
        raise RuntimeError("worktree create requires a named current branch; detached HEAD is not supported")

    records = ports.git_gateway.worktree_list(repo_root)
    if not records:
        raise RuntimeError("git worktree list returned no worktrees")
    main_worktree = records[0].path
    repo_basename = main_worktree.name
    container = central_root / repo_basename
    known_paths = {_canonical_path(record.path) for record in records}
    last_attempt_id = ""
    last_reason = "no candidates attempted"

    for index in range(1, _MAX_ATTEMPTS + 1):
        worktree_id = _candidate_id(label, index)
        last_attempt_id = worktree_id
        worktree_path = container / f"{repo_basename}-{worktree_id}"
        branch_name = f"{branch_prefix}-{worktree_id}"

        collision = _preflight_collision(
            repo_root=repo_root,
            worktree_path=worktree_path,
            branch_name=branch_name,
            known_paths=known_paths,
            ports=ports,
        )
        if collision is not None:
            last_reason = collision
            continue

        try:
            container.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            state = _artifact_state(
                repo_root=repo_root,
                worktree_path=worktree_path,
                branch_name=branch_name,
                known_paths=known_paths,
                ports=ports,
                refresh_records=False,
            )
            raise RuntimeError(
                "failed to create worktree container from "
                f"{_WORKTREE_ROOT_ENV}: root={central_root} container={container} "
                f"{state}\n{exc}\nSet an absolute path, for example: {_WORKTREE_ROOT_EXAMPLE}"
            ) from exc

        try:
            ports.git_gateway.add_worktree_with_new_branch(repo_root, path=worktree_path, branch=branch_name)
        except RuntimeError as exc:
            message = str(exc)
            if _is_retryable_worktree_add_error(message):
                records = ports.git_gateway.worktree_list(repo_root)
                known_paths = {_canonical_path(record.path) for record in records}
                last_reason = f"retryable git collision: {message}"
                continue
            state = _artifact_state(
                repo_root=repo_root,
                worktree_path=worktree_path,
                branch_name=branch_name,
                known_paths=known_paths,
                ports=ports,
                refresh_records=True,
            )
            raise RuntimeError(
                "git worktree add failed for non-retryable reason: "
                f"id={worktree_id} path={worktree_path} branch={branch_name} {state}\n{message}"
            ) from exc

        bootstrap = ports.bootstrap_gateway.run_make_init_if_available(worktree_path)
        return WorktreeCreateResult(
            id=worktree_id,
            main_worktree_path=main_worktree,
            container_path=container,
            worktree_path=worktree_path,
            branch_name=branch_name,
            bootstrap_status=bootstrap.status,
            bootstrap_command=bootstrap.command,
            bootstrap_exit_code=bootstrap.exit_code,
            warnings=list(bootstrap.warnings),
        )

    mode = "label" if label is not None else "auto"
    raise RuntimeError(
        "worktree create exhausted candidate attempts: "
        f"mode={mode} last_id={last_attempt_id} container={container} reason={last_reason}"
    )


def worktree_list(req: WorktreeListRequest, ports: Ports) -> WorktreeListResult:
    _require_repo_and_gateways(ports, command="worktree_list")
    _ = req
    inventory = _build_inventory(ports, command="list")
    return WorktreeListResult(worktrees=inventory, warnings=[])


def worktree_show(req: WorktreeShowRequest, ports: Ports) -> WorktreeShowResult:
    _require_repo_and_gateways(ports, command="worktree_show")
    inventory = _build_inventory(ports, command="show", target=req.target)
    worktree = _resolve_target(req.target, inventory, command="show")
    return WorktreeShowResult(target=req.target, worktree=worktree, warnings=[])


def worktree_remove(req: WorktreeRemoveRequest, ports: Ports) -> WorktreeRemoveResult:
    _require_repo_and_gateways(ports, command="worktree_remove", filesystem_required=True)
    inventory = _build_inventory(ports, command="remove", target=req.target)
    worktree = _resolve_target(req.target, inventory, command="remove")
    blockers = _non_bypassable_remove_blockers(worktree)
    if blockers:
        raise WorktreeCommandError(
            code="remove_blocked",
            message="worktree remove blocked",
            command="remove",
            target=req.target,
            worktree=worktree,
            remove_blockers=blockers,
        )

    assert ports.repo_root is not None
    assert ports.git_gateway is not None
    assert ports.filesystem_gateway is not None
    records = _git_worktree_list(ports, command="remove", target=req.target)
    if not _record_still_exists(worktree, records):
        raise WorktreeCommandError(
            code="remove_blocked",
            message="worktree record is no longer present",
            command="remove",
            target=req.target,
            worktree=worktree,
            remove_blockers=["record_missing"],
        )
    _guard_remove_containment(worktree, inventory, ports.repo_root, command="remove", target=req.target)

    try:
        ports.git_gateway.remove_worktree(ports.repo_root, path=worktree.path, force=req.force)
    except RuntimeError as exc:
        raise WorktreeCommandError(
            code="git_worktree_remove_failed",
            message="git worktree remove failed",
            command="remove",
            target=req.target,
            worktree=worktree,
            git_error=str(exc),
        ) from exc

    removed_directory = True
    try:
        _guard_remove_containment(worktree, inventory, ports.repo_root, command="remove", target=req.target)
        if ports.filesystem_gateway.path_exists(worktree.path):
            ports.filesystem_gateway.remove_tree(worktree.path)
    except RuntimeError as exc:
        raise WorktreeCommandError(
            code="post_remove_cleanup_failed",
            message="post-remove directory cleanup failed",
            command="remove",
            target=req.target,
            worktree=worktree,
            git_error=str(exc),
            removed_record=True,
            removed_directory=False,
        ) from exc

    return WorktreeRemoveResult(
        target=req.target,
        resolved_target=worktree,
        removed_record=True,
        removed_directory=removed_directory,
        branch_deleted=False,
        warnings=[],
    )


def _normalize_label(label: str | None) -> str | None:
    if label is None:
        return None
    if not label:
        raise RuntimeError("invalid worktree label: use lowercase letters, digits, and hyphens only")
    if _LABEL_RE.fullmatch(label) is None:
        raise RuntimeError("invalid worktree label: use lowercase letters, digits, and hyphens only")
    return label


def _candidate_id(label: str | None, index: int) -> str:
    if label is None:
        return f"wt{index}"
    if index == 1:
        return label
    return f"{label}{index}"


def _resolve_worktree_root(ports: Ports) -> Path:
    assert ports.environment_gateway is not None
    raw_value = ports.environment_gateway.getenv(_WORKTREE_ROOT_ENV)
    if raw_value is None or not raw_value.strip():
        raise RuntimeError(
            f"{_WORKTREE_ROOT_ENV} is required for worktree create. "
            "Set it to an absolute directory for spec-dock managed worktrees, "
            f"for example: {_WORKTREE_ROOT_EXAMPLE}"
        )
    return _validate_worktree_root(raw_value)


def _resolve_worktree_root_for_command(ports: Ports, *, command: str, target: str | None = None) -> Path:
    assert ports.environment_gateway is not None
    raw_value = ports.environment_gateway.getenv(_WORKTREE_ROOT_ENV)
    if raw_value is None or not raw_value.strip():
        raise WorktreeCommandError(
            code="worktree_root_required",
            message=(
                f"{_WORKTREE_ROOT_ENV} is required for worktree {command}. "
                "Set it to an absolute directory for spec-dock managed worktrees, "
                f"for example: {_WORKTREE_ROOT_EXAMPLE}"
            ),
            command=command,
            target=target,
        )
    try:
        return _validate_worktree_root(raw_value)
    except RuntimeError as exc:
        raise WorktreeCommandError(
            code="invalid_worktree_root",
            message=str(exc),
            command=command,
            target=target,
        ) from exc


def _validate_worktree_root(raw_value: str) -> Path:
    expanded = Path(raw_value).expanduser()
    resolved = expanded.resolve(strict=False)
    if not expanded.is_absolute():
        raise RuntimeError(_invalid_worktree_root_message(raw_value, resolved, "path is relative"))
    if expanded.exists():
        if not expanded.is_dir():
            raise RuntimeError(_invalid_worktree_root_message(raw_value, resolved, "path is not a directory"))
        return expanded
    if expanded.is_symlink():
        raise RuntimeError(_invalid_worktree_root_message(raw_value, resolved, "path is a broken symlink"))
    return expanded


def _invalid_worktree_root_message(raw_value: str, resolved: Path, cause: str) -> str:
    return (
        f"invalid {_WORKTREE_ROOT_ENV}: raw={raw_value!r} resolved={resolved} cause={cause}. "
        f"Set an absolute directory, for example: {_WORKTREE_ROOT_EXAMPLE}"
    )


def _preflight_collision(
    *,
    repo_root: Path,
    worktree_path: Path,
    branch_name: str,
    known_paths: set[str],
    ports: Ports,
) -> str | None:
    assert ports.git_gateway is not None
    if _canonical_path(worktree_path) in known_paths:
        return "worktree record already exists"
    if worktree_path.exists():
        return "worktree path already exists"
    if ports.git_gateway.local_branch_exists(repo_root, branch_name):
        return "branch already exists"
    if not ports.git_gateway.check_ref_format_branch(repo_root, branch_name):
        raise RuntimeError(f"generated worktree branch is invalid: {branch_name}")
    return None


def _canonical_path(path: Path) -> str:
    return str(path.expanduser().resolve(strict=False))


def _require_repo_and_gateways(ports: Ports, *, command: str, filesystem_required: bool = False) -> None:
    if ports.repo_root is None:
        raise RuntimeError(f"{command} requires a repository root")
    if ports.git_gateway is None:
        raise RuntimeError(f"{command} requires a Git gateway")
    if ports.environment_gateway is None:
        raise RuntimeError(f"{command} requires an environment gateway")
    if filesystem_required and ports.filesystem_gateway is None:
        raise RuntimeError(f"{command} requires a filesystem gateway")


def _git_worktree_list(ports: Ports, *, command: str, target: str | None = None) -> list[GitWorktreeRecord]:
    assert ports.repo_root is not None
    assert ports.git_gateway is not None
    try:
        return ports.git_gateway.worktree_list(ports.repo_root)
    except RuntimeError as exc:
        raise WorktreeCommandError(
            code="git_worktree_list_failed",
            message="git worktree list failed",
            command=command,
            target=target,
            git_error=str(exc),
        ) from exc


def _build_inventory(ports: Ports, *, command: str, target: str | None = None) -> list[WorktreeRecordView]:
    central_root = _resolve_worktree_root_for_command(ports, command=command, target=target)
    records = _git_worktree_list(ports, command=command, target=target)
    if not records:
        raise WorktreeCommandError(
            code="git_worktree_list_failed",
            message="git worktree list returned no worktrees",
            command=command,
            target=target,
        )
    assert ports.repo_root is not None
    main_record = records[0]
    namespace = central_root / main_record.path.name
    ordered = sorted(enumerate(records), key=lambda item: (_canonical_path(item[1].path), item[0]))
    raw_ids: list[str] = []
    for _, record in ordered:
        raw_ids.append(_raw_worktree_id(record, main_record=main_record, namespace=namespace))
    counts: dict[str, int] = {}
    views_by_index: dict[int, WorktreeRecordView] = {}
    for (original_index, record), raw_id in zip(ordered, raw_ids):
        counts[raw_id] = counts.get(raw_id, 0) + 1
        stable_id = raw_id if counts[raw_id] == 1 else f"{raw_id}~{counts[raw_id]}"
        main = _canonical_path(record.path) == _canonical_path(main_record.path)
        current = _canonical_path(record.path) == _canonical_path(ports.repo_root)
        managed = _is_managed_path(record.path, namespace)
        path_exists = record.path.exists()
        blockers = _remove_blockers(record, managed=managed, main=main, current=current, path_exists=path_exists)
        views_by_index[original_index] = WorktreeRecordView(
            id=stable_id,
            path=record.path,
            basename=record.path.name,
            branch=record.branch,
            head=record.head,
            managed=managed,
            main=main,
            current=current,
            path_exists=path_exists,
            record_exists=True,
            removable=not blockers,
            remove_blockers=blockers,
        )
    return [views_by_index[index] for index in range(len(records))]


def _raw_worktree_id(record: GitWorktreeRecord, *, main_record: GitWorktreeRecord, namespace: Path) -> str:
    if _canonical_path(record.path) == _canonical_path(main_record.path):
        return "main"
    basename = record.path.name
    repo_prefix = f"{main_record.path.name}-"
    if _is_managed_path(record.path, namespace) and basename.startswith(repo_prefix) and len(basename) > len(repo_prefix):
        return basename[len(repo_prefix):]
    return basename


def _is_managed_path(path: Path, namespace: Path) -> bool:
    if namespace.is_symlink():
        return False
    path_canonical = Path(_canonical_path(path))
    namespace_canonical = Path(_canonical_path(namespace))
    return path_canonical != namespace_canonical and _is_relative_to(path_canonical, namespace_canonical)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _remove_blockers(
    record: GitWorktreeRecord,
    *,
    managed: bool,
    main: bool,
    current: bool,
    path_exists: bool,
) -> list[str]:
    blockers: list[str] = []
    if not managed:
        blockers.append("unmanaged")
    if main:
        blockers.append("main_worktree")
    if current:
        blockers.append("current_worktree")
    if not path_exists:
        blockers.append("path_missing")
    if record.bare:
        blockers.append("bare_worktree")
    if record.locked:
        blockers.append("locked")
    return blockers


def _non_bypassable_remove_blockers(worktree: WorktreeRecordView) -> list[str]:
    return [
        blocker
        for blocker in worktree.remove_blockers
        if blocker in {"unmanaged", "main_worktree", "current_worktree", "path_missing", "record_missing", "bare_worktree"}
    ]


def _resolve_target(target: str, inventory: list[WorktreeRecordView], *, command: str) -> WorktreeRecordView:
    target_path = Path(target).expanduser()
    target_canonical = _canonical_path(target_path) if target_path.is_absolute() else None
    id_matches = [worktree for worktree in inventory if worktree.id == target]
    if len(id_matches) == 1:
        return id_matches[0]
    matches: list[WorktreeRecordView] = []
    for worktree in inventory:
        forms = {worktree.basename}
        if target_canonical is not None and _canonical_path(worktree.path) == target_canonical:
            forms.add(target)
        if target in forms:
            matches.append(worktree)
    unique = {_canonical_path(item.path): item for item in matches}
    matches = list(unique.values())
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise WorktreeCommandError(
            code="ambiguous_target",
            message=f"ambiguous worktree target: {target}",
            command=command,
            target=target,
            candidates=matches,
        )
    if any(record.branch == target for record in inventory):
        raise WorktreeCommandError(
            code="unsupported_branch_target",
            message=f"worktree target must be id, absolute path, or basename, not branch: {target}",
            command=command,
            target=target,
        )
    raise WorktreeCommandError(
        code="target_not_found",
        message=f"worktree target not found: {target}",
        command=command,
        target=target,
    )


def _record_still_exists(worktree: WorktreeRecordView, records: list[GitWorktreeRecord]) -> bool:
    target = _canonical_path(worktree.path)
    return any(_canonical_path(record.path) == target for record in records)


def _guard_remove_containment(
    worktree: WorktreeRecordView,
    inventory: list[WorktreeRecordView],
    repo_root: Path,
    *,
    command: str,
    target: str,
) -> None:
    main = next((item for item in inventory if item.main), None)
    if main is None:
        raise RuntimeError("main worktree record is missing")
    namespace = worktree.path.parent
    target_path = Path(_canonical_path(worktree.path))
    namespace_path = Path(_canonical_path(namespace))
    blocked: list[str] = []
    if namespace.is_symlink():
        blocked.append("outside_managed_namespace")
    if not _is_relative_to(target_path, namespace_path) or target_path == namespace_path:
        blocked.append("outside_managed_namespace")
    if target_path == Path(_canonical_path(repo_root)):
        blocked.append("current_worktree")
    if target_path == Path(_canonical_path(main.path)):
        blocked.append("main_worktree")
    if not worktree.managed:
        blocked.append("unmanaged")
    if worktree.main:
        blocked.append("main_worktree")
    if worktree.current:
        blocked.append("current_worktree")
    if blocked:
        deduped = list(dict.fromkeys(blocked))
        raise WorktreeCommandError(
            code="remove_blocked",
            message="worktree remove blocked by containment guard",
            command=command,
            target=target,
            worktree=worktree,
            remove_blockers=deduped,
        )


def _is_retryable_worktree_add_error(message: str) -> bool:
    lowered = message.lower()
    return any(fragment in lowered for fragment in _RETRYABLE_GIT_WORKTREE_ERRORS)


def _artifact_state(
    *,
    repo_root: Path,
    worktree_path: Path,
    branch_name: str,
    known_paths: set[str],
    ports: Ports,
    refresh_records: bool,
) -> str:
    assert ports.git_gateway is not None
    record_paths = known_paths
    if refresh_records:
        try:
            record_paths = {_canonical_path(record.path) for record in ports.git_gateway.worktree_list(repo_root)}
        except RuntimeError:
            record_paths = known_paths
    try:
        branch_exists = ports.git_gateway.local_branch_exists(repo_root, branch_name)
    except RuntimeError:
        branch_exists = "unknown"
    path_exists = worktree_path.exists()
    record_exists = _canonical_path(worktree_path) in record_paths
    return (
        "artifact_state="
        f"path_exists:{path_exists},"
        f"branch_exists:{branch_exists},"
        f"record_exists:{record_exists}"
    )
