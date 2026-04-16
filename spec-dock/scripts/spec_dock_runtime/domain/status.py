from __future__ import annotations

from .ids import deps_node_sort_key
from .models import IssueSnapshot, IssueStatusSnapshot, ProgressMap, SpecGraph, SpecNode

_KNOWN_ISSUE_STATUSES = {"done", "open", "unknown"}


def _normalize_issue_status(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in _KNOWN_ISSUE_STATUSES:
        return normalized
    return "unknown"


def _status_from_github_state(state: str) -> str:
    return "done" if str(state).strip().upper() == "CLOSED" else "open"


def _normalize_last_sync_at(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _safe_sorted_issue_ids(issue_ids: list[str]) -> list[str]:
    try:
        return sorted(issue_ids, key=deps_node_sort_key)
    except RuntimeError:
        return sorted(issue_ids)


def _normalize_repo_identity(
    repo_owner: str | None,
    repo_name: str | None,
) -> tuple[str, str] | None:
    owner = str(repo_owner or "").strip().lower()
    name = str(repo_name or "").strip().lower()
    if not owner or not name:
        return None
    return (owner, name)


def _normalize_repo_slug_value(repo_slug: str | None) -> tuple[str, str] | None:
    normalized = str(repo_slug or "").strip().lower()
    if not normalized:
        return None
    owner, sep, name = normalized.partition("/")
    if not sep or not owner or not name:
        return None
    return (owner, name)


def _build_issue_snapshot_indexes(
    issue_snapshots: list[IssueSnapshot] | None,
) -> tuple[dict[int, list[IssueSnapshot]], dict[tuple[str, str, int], IssueSnapshot]]:
    by_number: dict[int, list[IssueSnapshot]] = {}
    by_repo_and_number: dict[tuple[str, str, int], IssueSnapshot] = {}
    for issue_snapshot in issue_snapshots or []:
        issue_number = int(issue_snapshot.issue_number)
        by_number.setdefault(issue_number, []).append(issue_snapshot)
        identity = _normalize_repo_identity(issue_snapshot.repo_owner, issue_snapshot.repo_name)
        if identity is not None:
            by_repo_and_number[(identity[0], identity[1], issue_number)] = issue_snapshot
    return by_number, by_repo_and_number


def _resolve_issue_snapshot_for_node(
    issue_node: SpecNode,
    *,
    issue_snapshot_by_number: dict[int, list[IssueSnapshot]],
    issue_snapshot_by_repo_and_number: dict[tuple[str, str, int], IssueSnapshot],
    current_repo_identity: tuple[str, str] | None,
) -> IssueSnapshot | None:
    if issue_node.github_issue_number is None:
        return None

    issue_number = int(issue_node.github_issue_number)
    identity = _normalize_repo_identity(issue_node.github_repo_owner, issue_node.github_repo_name)
    if identity is not None:
        return issue_snapshot_by_repo_and_number.get((identity[0], identity[1], issue_number))
    if current_repo_identity is not None:
        return issue_snapshot_by_repo_and_number.get((current_repo_identity[0], current_repo_identity[1], issue_number))

    snapshots = issue_snapshot_by_number.get(issue_number, [])
    if len(snapshots) != 1:
        return None

    # Without repo identity for the node and current-repo context, fall back only to
    # snapshots that also lack repo identity to avoid cross-repo misbinding.
    snapshot = snapshots[0]
    snapshot_identity = _normalize_repo_identity(snapshot.repo_owner, snapshot.repo_name)
    if snapshot_identity is not None:
        return None
    return snapshot


def resolve_issue_statuses(
    graph: SpecGraph,
    github_enabled: bool,
    issue_snapshots: list[IssueSnapshot] | None,
    cached_issue_status_by_id: dict[str, str],
    cached_issue_last_sync_at_by_id: dict[str, str | None] | None = None,
    current_repo_slug: str | None = None,
) -> dict[str, IssueStatusSnapshot]:
    issue_snapshot_by_number, issue_snapshot_by_repo_and_number = _build_issue_snapshot_indexes(issue_snapshots)
    current_repo_identity = _normalize_repo_slug_value(current_repo_slug)

    cache_last_sync_at_by_id = dict(cached_issue_last_sync_at_by_id or {})
    resolved: dict[str, IssueStatusSnapshot] = {}
    status_target_ids = _safe_sorted_issue_ids(
        [
            node_id
            for node_id, node in graph.nodes_by_id.items()
            if node.kind in ("initiative", "epic", "issue")
        ]
    )
    for issue_id in status_target_ids:
        issue_node = graph.nodes_by_id[issue_id]

        authority = "local" if issue_node.github_issue_number is None else "github"
        effective_status = "unknown"
        source = "unknown"
        stale = authority == "github"
        last_sync_at: str | None = None

        if authority == "local":
            effective_status = "open"
            source = "local"
            stale = False
        elif github_enabled:
            issue_snapshot = _resolve_issue_snapshot_for_node(
                issue_node,
                issue_snapshot_by_number=issue_snapshot_by_number,
                issue_snapshot_by_repo_and_number=issue_snapshot_by_repo_and_number,
                current_repo_identity=current_repo_identity,
            )
            if issue_snapshot is not None:
                effective_status = _status_from_github_state(issue_snapshot.state)
                source = "github"
                stale = False
                last_sync_at = _normalize_last_sync_at(issue_snapshot.updated_at)
        else:
            source = "cache"
            cached_status = cached_issue_status_by_id.get(issue_node.id)
            if cached_status is not None:
                effective_status = _normalize_issue_status(cached_status)
                last_sync_at = _normalize_last_sync_at(cache_last_sync_at_by_id.get(issue_node.id))

        resolved[issue_id] = IssueStatusSnapshot(
            issue_id=issue_id,
            authority=authority,
            effective_status=effective_status,
            source=source,
            stale=stale,
            last_sync_at=last_sync_at,
            github_number=issue_node.github_issue_number,
        )

    return resolved


def resolve_issue_snapshot_by_issue_id(
    graph: SpecGraph,
    issue_snapshots: list[IssueSnapshot] | None,
    current_repo_slug: str | None = None,
) -> dict[str, IssueSnapshot]:
    issue_snapshot_by_number, issue_snapshot_by_repo_and_number = _build_issue_snapshot_indexes(issue_snapshots)
    current_repo_identity = _normalize_repo_slug_value(current_repo_slug)
    resolved: dict[str, IssueSnapshot] = {}
    issue_ids = _safe_sorted_issue_ids(
        [
            node_id
            for node_id, node in graph.nodes_by_id.items()
            if node.kind in ("initiative", "epic", "issue") and node.github_issue_number is not None
        ]
    )
    for issue_id in issue_ids:
        issue_node = graph.nodes_by_id[issue_id]
        issue_snapshot = _resolve_issue_snapshot_for_node(
            issue_node,
            issue_snapshot_by_number=issue_snapshot_by_number,
            issue_snapshot_by_repo_and_number=issue_snapshot_by_repo_and_number,
            current_repo_identity=current_repo_identity,
        )
        if issue_snapshot is not None:
            resolved[issue_id] = issue_snapshot
    return resolved


def build_progress_map(
    graph: SpecGraph,
    issue_statuses: dict[str, IssueStatusSnapshot],
) -> ProgressMap:
    by_node_id: dict[str, dict[str, int]] = {}
    for node_id, node in graph.nodes_by_id.items():
        if node.kind in ("initiative", "epic"):
            by_node_id[node_id] = {"total": 0, "done": 0, "open": 0, "unknown": 0}

    counts = {"total": 0, "done": 0, "open": 0, "unknown": 0}
    issue_ids = _safe_sorted_issue_ids(
        [
            node_id
            for node_id, node in graph.nodes_by_id.items()
            if node.kind == "issue"
        ]
    )
    for issue_id in issue_ids:
        issue_node = graph.nodes_by_id[issue_id]
        resolution = issue_statuses.get(
            issue_id,
            IssueStatusSnapshot(
                issue_id=issue_id,
                authority="unknown",
                effective_status="unknown",
                source="unknown",
                stale=True,
                last_sync_at=None,
                github_number=None,
            ),
        )
        issue_status = _normalize_issue_status(resolution.effective_status)

        counts["total"] += 1
        counts[issue_status] += 1

        for parent_id in filter(None, (issue_node.epic_id, issue_node.initiative_id)):
            parent_progress = by_node_id.get(parent_id)
            if parent_progress is None:
                continue
            parent_progress["total"] += 1
            parent_progress[issue_status] += 1

    return ProgressMap(by_node_id=by_node_id, counts=counts)
