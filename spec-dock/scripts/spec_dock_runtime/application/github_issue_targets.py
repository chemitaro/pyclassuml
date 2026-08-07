from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from spec_dock_runtime.domain.models import IssueSnapshot, SpecGraph


def normalize_repo_slug(owner: str | None, repo: str | None) -> str | None:
    normalized_owner = str(owner or "").strip().lower()
    normalized_repo = str(repo or "").strip().lower()
    if not normalized_owner or not normalized_repo:
        return None
    return f"{normalized_owner}/{normalized_repo}"


def snapshot_repo_issue_key(snapshot: IssueSnapshot) -> tuple[str, int] | None:
    repo_slug = normalize_repo_slug(snapshot.repo_owner, snapshot.repo_name)
    if repo_slug is None:
        return None
    return (repo_slug, int(snapshot.issue_number))


def collect_repo_scoped_issue_view_targets(
    graph: SpecGraph,
    *,
    issue_index_snapshots: Iterable[IssueSnapshot],
    current_repo_slug: str | None = None,
) -> list[tuple[str, int]]:
    normalized_current_repo_slug = str(current_repo_slug or "").strip().lower()
    owner, sep, repo = normalized_current_repo_slug.partition("/")
    if not sep or not owner or not repo:
        normalized_current_repo_slug = ""

    indexed_keys: set[tuple[str, int]] = set()
    for snapshot in issue_index_snapshots:
        scoped_key = snapshot_repo_issue_key(snapshot)
        if scoped_key is not None:
            indexed_keys.add(scoped_key)

    targets: set[tuple[str, int]] = set()
    for node in graph.nodes_by_id.values():
        if node.kind not in ("initiative", "epic", "issue") or node.github_issue_number is None:
            continue
        repo_slug = normalize_repo_slug(node.github_repo_owner, node.github_repo_name)
        if repo_slug is None:
            # Keep fail-closed behavior for malformed partial scoped linkage.
            has_partial_scope = bool(str(node.github_repo_owner or "").strip()) or bool(
                str(node.github_repo_name or "").strip()
            )
            if has_partial_scope:
                continue
            if not normalized_current_repo_slug:
                continue
            repo_slug = normalized_current_repo_slug
        target = (repo_slug, int(node.github_issue_number))
        if target in indexed_keys:
            continue
        targets.add(target)
    return sorted(targets, key=lambda item: (item[0], item[1]))
