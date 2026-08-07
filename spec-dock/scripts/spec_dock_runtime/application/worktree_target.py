from __future__ import annotations

from pathlib import Path

from spec_dock_runtime.application.contracts import WorktreeCommandError, WorktreeRecordView


def resolve_worktree_target(
    target: str,
    inventory: list[WorktreeRecordView],
    *,
    command: str,
) -> WorktreeRecordView:
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


def _canonical_path(path: Path) -> str:
    return str(path.expanduser().resolve(strict=False))
