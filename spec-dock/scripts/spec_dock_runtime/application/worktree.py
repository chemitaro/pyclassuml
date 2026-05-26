from __future__ import annotations

import re
from pathlib import Path

from .contracts import WorktreeCreateRequest, WorktreeCreateResult
from .ports import Ports


_LABEL_RE = re.compile(r"^[a-z0-9-]+$")
_MAX_ATTEMPTS = 10000
_RETRYABLE_GIT_WORKTREE_ERRORS = (
    "already exists",
    "is already checked out",
    "a branch named",
)


def worktree_create(req: WorktreeCreateRequest, ports: Ports) -> WorktreeCreateResult:
    if ports.repo_root is None:
        raise RuntimeError("worktree create requires a repository root")
    if ports.git_gateway is None:
        raise RuntimeError("worktree create requires a Git gateway")
    if ports.bootstrap_gateway is None:
        raise RuntimeError("worktree create requires a bootstrap gateway")

    label = _normalize_label(req.label)
    repo_root = ports.repo_root
    branch_prefix = ports.git_gateway.current_branch_or_none(repo_root)
    if branch_prefix is None:
        raise RuntimeError("worktree create requires a named current branch; detached HEAD is not supported")

    records = ports.git_gateway.worktree_list(repo_root)
    if not records:
        raise RuntimeError("git worktree list returned no worktrees")
    main_worktree = records[0].path
    repo_basename = main_worktree.name
    container = main_worktree.parent / f"{repo_basename}-worktrees"
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
            raise RuntimeError(f"failed to create worktree container: {container} {state}\n{exc}") from exc

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
