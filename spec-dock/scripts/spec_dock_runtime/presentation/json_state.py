from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, TypeAlias

from spec_dock_runtime.domain.ids import deps_node_sort_key
from spec_dock_runtime.presentation.contracts import DepsIssuesArtifact, DepsRawArtifact, IndexArtifact, TreeArtifact
from spec_dock_runtime.presentation.puml import (
    render_deps_disabled_deps_issues_puml,
    render_deps_disabled_deps_raw_puml,
    render_deps_disabled_tree_puml,
    render_deps_issues_puml,
    render_deps_raw_puml,
    render_tree_ready_board_puml,
)

if TYPE_CHECKING:
    from spec_dock_runtime.application.contracts import DepsCheckResult, SyncStateResult
    from spec_dock_runtime.domain.models import ActiveSelection, DepsNodeState, SpecNode

StatePayloads: TypeAlias = tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]

CURRENT_FUTURE_PROJECTION = "current-future"
FULL_HISTORY_PROJECTION = "full-history"
OPEN_ISSUES_DEPENDENCY_VIEW_PROJECTION = "open-issues-dependency-view"
ISSUE_READINESS_WITH_DEPENDENCY_CONTEXT_PROJECTION = "issue-readiness-with-dependency-context"


def _deps_node_blocker_payload(blocker: object) -> dict[str, object]:
    return {
        "node_id": _object_value(blocker, "node_id", ""),
        "reason": _object_value(blocker, "reason", ""),
        "state": _object_value(blocker, "state", ""),
        "state_source": _object_value(blocker, "state_source", ""),
        "source_issue_id": _object_value(blocker, "source_issue_id", ""),
        "lifecycle_state": _object_value(blocker, "lifecycle_state", None),
        "lifecycle_source": _object_value(blocker, "lifecycle_source", None),
        "dependency_disposition": _object_value(blocker, "dependency_disposition", None),
        "disposition_basis": _object_value(blocker, "disposition_basis", None),
    }


def _deps_dependency_context_payload(context: object) -> dict[str, object]:
    raw_target_issue_ids = _object_value(context, "target_issue_ids", ())
    target_issue_ids = raw_target_issue_ids if isinstance(raw_target_issue_ids, (list, tuple)) else ()
    return {
        "source_node_id": _object_value(context, "source_node_id", ""),
        "source_issue_id": _object_value(context, "source_issue_id", ""),
        "target_node_id": _object_value(context, "target_node_id", ""),
        "target_node_kind": _object_value(context, "target_node_kind", ""),
        "target_issue_ids": list(target_issue_ids),
        "expansion": _object_value(context, "expansion", ""),
        "lifecycle_state": _object_value(context, "lifecycle_state", None),
        "lifecycle_source": _object_value(context, "lifecycle_source", None),
        "dependency_disposition": _object_value(context, "dependency_disposition", None),
        "disposition_basis": _object_value(context, "disposition_basis", None),
    }


def _deps_direct_node_dependency_payload(dependency: object) -> dict[str, object]:
    raw_target_issue_ids = _object_value(dependency, "target_issue_ids", ())
    target_issue_ids = raw_target_issue_ids if isinstance(raw_target_issue_ids, (list, tuple)) else ()
    return {
        "source_node_id": _object_value(dependency, "source_node_id", ""),
        "source_node_kind": _object_value(dependency, "source_node_kind", ""),
        "target_node_id": _object_value(dependency, "target_node_id", ""),
        "target_node_kind": _object_value(dependency, "target_node_kind", ""),
        "target_issue_ids": list(target_issue_ids),
        "expansion": _object_value(dependency, "expansion", ""),
        "lifecycle_state": _object_value(dependency, "lifecycle_state", None),
        "lifecycle_source": _object_value(dependency, "lifecycle_source", None),
        "dependency_disposition": _object_value(dependency, "dependency_disposition", None),
        "disposition_basis": _object_value(dependency, "disposition_basis", None),
    }


def render_deps_check_json(result: DepsCheckResult) -> str:
    inspection = result.inspection
    target_id = inspection.target_id.value

    target_status = inspection.issue_statuses.get(target_id)
    target_status_payload = {
        "authority": target_status.authority if target_status is not None else "unknown",
        "effective_status": target_status.effective_status if target_status is not None else "unknown",
        "source": target_status.source if target_status is not None else "unknown",
        "stale": bool(target_status.stale) if target_status is not None else True,
        "last_sync_at": target_status.last_sync_at if target_status is not None else None,
    }

    payload = {
        "schema_version": 2,
        "target": target_id,
        "target_status": target_status_payload,
        "ready": bool(inspection.evaluation.ready),
        "effective_depends_on": list(inspection.effective_depends_on),
        "blockers": list(inspection.evaluation.blockers),
        "issue_blockers": list(inspection.evaluation.issue_blockers),
        "node_blockers": [_deps_node_blocker_payload(blocker) for blocker in inspection.evaluation.node_blockers],
        "satisfied_dependencies": [
            _deps_dependency_context_payload(context) for context in inspection.evaluation.satisfied_dependencies
        ],
        "dependency_contexts": [
            _deps_dependency_context_payload(context) for context in inspection.evaluation.dependency_contexts
        ],
        "direct_node_dependencies": [
            _deps_direct_node_dependency_payload(dependency) for dependency in inspection.direct_node_dependencies
        ],
        "nodes": {
            node_id: {
                "state": node_state.status,
                "ready": bool(node_state.ready),
                "authority": (
                    inspection.issue_statuses[node_id].authority if node_id in inspection.issue_statuses else "unknown"
                ),
                "effective_status": (
                    inspection.issue_statuses[node_id].effective_status
                    if node_id in inspection.issue_statuses
                    else "unknown"
                ),
                "source": (
                    inspection.issue_statuses[node_id].source if node_id in inspection.issue_statuses else "unknown"
                ),
                "stale": (
                    bool(inspection.issue_statuses[node_id].stale) if node_id in inspection.issue_statuses else True
                ),
                "last_sync_at": (
                    inspection.issue_statuses[node_id].last_sync_at if node_id in inspection.issue_statuses else None
                ),
            }
            for node_id, node_state in inspection.node_states.items()
        },
        "warnings": list(result.warnings),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _sort_ids(ids: list[str]) -> list[str]:
    try:
        return sorted(ids, key=deps_node_sort_key)
    except RuntimeError:
        return sorted(ids)


def _sort_key(node_id: str) -> tuple[int, int, str] | tuple[int, str]:
    try:
        return deps_node_sort_key(node_id)
    except RuntimeError:
        return (2, node_id)


def _normalize_repo_slug(owner: str | None, repo: str | None) -> str | None:
    normalized_owner = str(owner or "").strip().lower()
    normalized_repo = str(repo or "").strip().lower()
    if not normalized_owner or not normalized_repo:
        return None
    return f"{normalized_owner}/{normalized_repo}"


def _to_repo_relative_specdock_path(path: Path, *, repo_root: Path | None) -> str:
    if repo_root is not None:
        try:
            return path.relative_to(repo_root).as_posix()
        except ValueError:
            pass

    parts = path.parts
    if parts and parts[0] == "spec-dock":
        return path.as_posix()
    if "spec-dock" in parts:
        index = parts.index("spec-dock")
        return Path(*parts[index:]).as_posix()
    raise RuntimeError(f"Node path missing 'spec-dock' segment: {path}")


def _document_surfaces_payload(node: SpecNode, *, repo_root: Path | None) -> dict[str, object]:
    canonical_docs = []
    for kind, filename in (
        ("requirement", "requirement.md"),
        ("design", "design.md"),
        ("plan", "plan.md"),
        ("report", "report.md"),
    ):
        path = node.path / filename
        canonical_docs.append({
            "kind": kind,
            "path": _to_repo_relative_specdock_path(path, repo_root=repo_root),
            "present": path.is_file(),
        })
    artifacts_dir = node.path / "artifacts"
    discussions_dir = node.path / "discussions"
    return {
        "canonical_docs": canonical_docs,
        "future_artifacts": {
            "path": _to_repo_relative_specdock_path(artifacts_dir, repo_root=repo_root),
            "present": artifacts_dir.is_dir(),
        },
        "legacy_discussions": {
            "path": _to_repo_relative_specdock_path(discussions_dir, repo_root=repo_root),
            "present": discussions_dir.is_dir(),
        },
    }


def _active_to_json(active: ActiveSelection | None) -> dict[str, object] | None:
    if active is None:
        return None
    return {
        "initiative": {"id": active.initiative_id} if active.initiative_id else None,
        "epic": {"id": active.epic_id} if active.epic_id else None,
        "issue": {"id": active.issue_id} if active.issue_id else None,
    }


def _deps_state_by_issue_id(result: SyncStateResult) -> dict[str, DepsNodeState]:
    return {node_state.node_id: node_state for node_state in result.deps_state.nodes}


def _build_children(graph_nodes: dict[str, SpecNode]) -> dict[str, list[str]]:
    children: dict[str, list[str]] = {node_id: [] for node_id in graph_nodes}
    for node in graph_nodes.values():
        if node.parent_id and node.parent_id in children:
            children[node.parent_id].append(node.id)
    for key in list(children.keys()):
        children[key] = _sort_ids(children[key])
    return children


def _build_issue_edges_from_deps_state(
    result: SyncStateResult,
    deps_state_by_issue_id: dict[str, DepsNodeState],
) -> list[dict[str, str]]:
    if result.issue_depends_on_map:
        edges: list[dict[str, str]] = []
        issue_ids = _sort_ids(list(result.issue_depends_on_map.keys()))
        for issue_id in issue_ids:
            dep_ids = _sort_ids([
                dep_id for dep_id in result.issue_depends_on_map.get(issue_id, []) if isinstance(dep_id, str)
            ])
            for dep_id in dep_ids:
                edges.append({"from": issue_id, "to": dep_id, "kind": "depends_on"})
        edges.sort(key=lambda item: (_sort_key(item["from"]), _sort_key(item["to"])))
        return edges

    fallback_edges: list[dict[str, str]] = []
    for issue_id in _sort_ids(list(deps_state_by_issue_id.keys())):
        node_state = deps_state_by_issue_id[issue_id]
        for dep_id in node_state.effective_depends_on:
            fallback_edges.append({"from": issue_id, "to": dep_id, "kind": "depends_on"})
    fallback_edges.sort(key=lambda item: (_sort_key(item["from"]), _sort_key(item["to"])))
    return fallback_edges


def _issue_raw_state(result: SyncStateResult, issue_id: str) -> str:
    status_snapshot = result.issue_statuses.get(issue_id)
    status = status_snapshot.effective_status.lower() if status_snapshot is not None else "unknown"
    if status in ("done", "closed"):
        return "done"
    if result.active is not None and result.active.issue_id == issue_id:
        return "doing"
    if status == "unknown":
        return "unknown"
    evaluation = result.deps_eval_by_id.get(issue_id)
    if evaluation is not None and evaluation.ready:
        return "ready"
    return "blocked"


def _object_value(item: object, field_name: str, default: object = None) -> object:
    if isinstance(item, dict):
        return item.get(field_name, default)
    return getattr(item, field_name, default)


def _high_level_visual_state(result: SyncStateResult, node_id: str) -> dict[str, str] | None:
    raw_status = result.high_level_statuses_by_node_id.get(node_id)
    if raw_status is None:
        return None
    state = str(_object_value(raw_status, "state", "unknown") or "unknown").lower()
    if state not in {"open", "closed", "done", "unknown"}:
        state = "unknown"
    source = str(_object_value(raw_status, "source", "none") or "none")
    return {"state": state, "state_source": source}


def _node_is_active_raw_participant(result: SyncStateResult, node_id: str) -> bool:
    node = result.graph.nodes_by_id.get(node_id)
    if node is None:
        return False
    if node.kind == "issue":
        return not _issue_is_satisfied(result, node_id)
    descendant_issue_ids = [
        candidate.id
        for candidate in result.graph.nodes_by_id.values()
        if candidate.kind == "issue"
        and (candidate.id == node_id or candidate.epic_id == node_id or candidate.initiative_id == node_id)
    ]
    visual_state = _high_level_visual_state(result, node_id)
    if visual_state is None:
        return True
    if visual_state["state"] == "unknown":
        return True
    if descendant_issue_ids and all(_issue_is_satisfied(result, issue_id) for issue_id in descendant_issue_ids):
        return False
    return visual_state["state"] not in {"closed", "done"}


def _dependency_context_is_satisfied(context: object) -> bool:
    return _object_value(context, "dependency_disposition", None) == "satisfied"


def _raw_dependency_edge_is_satisfied(result: SyncStateResult, dependent_id: str, prerequisite_id: str) -> bool:
    contexts = list(result.dependency_contexts_by_issue_id.get(dependent_id, []))
    for issue_contexts in result.dependency_contexts_by_issue_id.values():
        for context in issue_contexts:
            if _object_value(context, "source_node_id", None) == dependent_id:
                contexts.append(context)
    evaluation = result.deps_eval_by_id.get(dependent_id)
    if evaluation is not None:
        contexts.extend(evaluation.dependency_contexts)
        contexts.extend(evaluation.satisfied_dependencies)
    for issue_evaluation in result.deps_eval_by_id.values():
        for context in issue_evaluation.dependency_contexts:
            if _object_value(context, "source_node_id", None) == dependent_id:
                contexts.append(context)
        for context in issue_evaluation.satisfied_dependencies:
            if _object_value(context, "source_node_id", None) == dependent_id:
                contexts.append(context)
    for context in contexts:
        if _object_value(context, "target_node_id", None) == prerequisite_id and _dependency_context_is_satisfied(
            context
        ):
            return True
    return False


def _raw_dependency_participant_ids(result: SyncStateResult) -> tuple[set[str], list[dict[str, str]]]:
    graph_nodes = result.graph.nodes_by_id
    participant_ids: set[str] = set()
    edges: list[dict[str, str]] = []
    seen_edges: set[tuple[str, str]] = set()

    for dependent_id in _sort_ids(list(result.raw_node_depends_on_map.keys())):
        if dependent_id not in graph_nodes:
            continue
        dep_ids = result.raw_node_depends_on_map.get(dependent_id, [])
        for prerequisite_id in _sort_ids([dep_id for dep_id in dep_ids if isinstance(dep_id, str)]):
            if prerequisite_id not in graph_nodes:
                continue
            if not _node_is_active_raw_participant(result, dependent_id):
                continue
            if not _node_is_active_raw_participant(result, prerequisite_id):
                continue
            if _raw_dependency_edge_is_satisfied(result, dependent_id, prerequisite_id):
                continue
            edge_key = (dependent_id, prerequisite_id)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            participant_ids.add(dependent_id)
            participant_ids.add(prerequisite_id)
            edges.append({"from": dependent_id, "to": prerequisite_id})

    edges.sort(key=lambda edge: (_sort_key(edge["from"]), _sort_key(edge["to"])))
    return participant_ids, edges


def _include_raw_ancestors(result: SyncStateResult, participant_ids: set[str]) -> set[str]:
    graph_nodes = result.graph.nodes_by_id
    include_ids = set(participant_ids)
    pending = list(participant_ids)
    while pending:
        node_id = pending.pop()
        node = graph_nodes.get(node_id)
        if node is None or not node.parent_id or node.parent_id in include_ids:
            continue
        include_ids.add(node.parent_id)
        pending.append(node.parent_id)
    return include_ids


def _build_deps_raw_payload(result: SyncStateResult) -> dict[str, object]:
    graph_nodes = result.graph.nodes_by_id
    participant_ids, edges = _raw_dependency_participant_ids(result)
    include_ids = _include_raw_ancestors(result, participant_ids)

    tree: list[dict[str, object]] = []
    initiative_ids = _sort_ids([
        node_id for node_id, node in graph_nodes.items() if node.kind == "initiative" and node_id in include_ids
    ])
    for initiative_id in initiative_ids:
        init_node = graph_nodes[initiative_id]
        init_item: dict[str, object] = {
            "id": init_node.id,
            "title": init_node.title,
            "participant": init_node.id in participant_ids,
            "epics": [],
        }
        init_visual_state = _high_level_visual_state(result, init_node.id)
        if init_visual_state is not None:
            init_item.update(init_visual_state)
        epic_items: list[dict[str, object]] = []
        epic_ids = _sort_ids([
            node_id
            for node_id, node in graph_nodes.items()
            if node.kind == "epic" and node.parent_id == initiative_id and node_id in include_ids
        ])
        for epic_id in epic_ids:
            epic_node = graph_nodes[epic_id]
            epic_item: dict[str, object] = {
                "id": epic_node.id,
                "title": epic_node.title,
                "participant": epic_node.id in participant_ids,
                "issues": [],
            }
            epic_visual_state = _high_level_visual_state(result, epic_node.id)
            if epic_visual_state is not None:
                epic_item.update(epic_visual_state)
            issue_items: list[dict[str, object]] = []
            issue_ids = _sort_ids([
                node_id
                for node_id, node in graph_nodes.items()
                if node.kind == "issue" and node.parent_id == epic_id and node_id in include_ids
            ])
            for issue_id in issue_ids:
                issue_node = graph_nodes[issue_id]
                issue_items.append({
                    "id": issue_node.id,
                    "title": issue_node.title,
                    "state": _issue_raw_state(result, issue_node.id),
                })
            epic_item["issues"] = issue_items
            epic_items.append(epic_item)
        init_item["epics"] = epic_items
        tree.append(init_item)

    return {
        "schema_version": 1,
        "generated_at": result.generated_at,
        "projection": "raw-direct-dependency-view",
        "deps": {"valid": True, "error": None},
        "tree": tree,
        "edges": edges,
        "edge_direction": "depends_on (dependent -> prerequisite)",
    }


def _build_state_payloads(result: SyncStateResult) -> StatePayloads:
    graph_nodes = result.graph.nodes_by_id
    children = _build_children(graph_nodes)
    deps_state_by_issue_id = _deps_state_by_issue_id(result)
    deps_issue_edges_all = (
        _build_issue_edges_from_deps_state(result, deps_state_by_issue_id)
        if result.deps_preflight_error is None
        else []
    )

    nodes_all: dict[str, dict[str, object]] = {}
    for node_id in _sort_ids(list(graph_nodes.keys())):
        node = graph_nodes[node_id]
        item: dict[str, object] = {
            "type": node.kind,
            "id": node.id,
            "title": node.title,
            "path": _to_repo_relative_specdock_path(node.path, repo_root=result.repo_root),
            "document_surfaces": _document_surfaces_payload(node, repo_root=result.repo_root),
            "parent_id": node.parent_id,
            "initiative_id": node.initiative_id,
            "epic_id": node.epic_id,
            "children": list(children.get(node.id, [])),
        }

        if node.kind == "issue":
            issue_status = result.issue_statuses.get(node.id)
            item["status"] = issue_status.effective_status if issue_status is not None else "unknown"
            item["authority"] = issue_status.authority if issue_status is not None else "unknown"
            item["effective_status"] = issue_status.effective_status if issue_status is not None else "unknown"
            item["source"] = issue_status.source if issue_status is not None else "unknown"
            item["stale"] = bool(issue_status.stale) if issue_status is not None else True
            item["last_sync_at"] = issue_status.last_sync_at if issue_status is not None else None
            if result.deps_preflight_error is None:
                evaluation = result.deps_eval_by_id.get(node.id)
                if evaluation is not None:
                    item["deps"] = {
                        "ready": bool(evaluation.ready),
                        "depends_on": list(evaluation.blockers),
                        "blockers_top": list(evaluation.blockers_top),
                    }
                else:
                    deps = deps_state_by_issue_id.get(node.id)
                    if deps is None:
                        item["deps"] = None
                    else:
                        item["deps"] = {
                            "ready": bool(deps.ready),
                            "depends_on": list(deps.effective_depends_on),
                            "blockers_top": list(deps.blockers_top),
                        }
            else:
                item["deps"] = None

        if node.github_issue_number is not None:
            github_item: dict[str, object] = {"issue_number": int(node.github_issue_number)}
            if node.github_repo_owner and node.github_repo_name:
                github_item["repo_owner"] = node.github_repo_owner
                github_item["repo_name"] = node.github_repo_name
            snapshot = result.github_snapshot_by_issue_id.get(node.id)
            if snapshot is None:
                repo_scope = _normalize_repo_slug(node.github_repo_owner, node.github_repo_name)
                fallback_allowed = True
                if repo_scope is None and node.kind == "issue":
                    issue_status = result.issue_statuses.get(node.id)
                    fallback_allowed = issue_status is not None and issue_status.source == "github"
                if fallback_allowed:
                    snapshot = result.github_snapshot_by_repo_scope_and_issue_number.get((
                        repo_scope,
                        int(node.github_issue_number),
                    ))
            if snapshot is not None:
                github_item.update({
                    "state": snapshot.state,
                    "url": snapshot.url,
                    "updated_at": snapshot.updated_at,
                    "labels": list(snapshot.labels),
                })
            elif node.kind in {"initiative", "epic"}:
                visual_state = _high_level_visual_state(result, node.id)
                if visual_state is not None and visual_state["state_source"] in {"github", "cache"}:
                    github_item.update({
                        "state": visual_state["state"].upper(),
                        "updated_at": result.generated_at,
                    })
            item["github"] = github_item

        if node.kind in ("initiative", "epic"):
            progress_item = result.progress.by_node_id.get(node.id)
            if isinstance(progress_item, dict):
                item["progress"] = dict(progress_item)

        nodes_all[node.id] = item

    tree_all: list[dict[str, object]] = []
    initiative_ids = _sort_ids([node_id for node_id, node in graph_nodes.items() if node.kind == "initiative"])
    for initiative_id in initiative_ids:
        init_base = nodes_all.get(initiative_id)
        if not isinstance(init_base, dict):
            continue
        init_item = dict(init_base)
        epics_all: list[dict[str, object]] = []
        for epic_id in _sort_ids(children.get(initiative_id, [])):
            epic_node = graph_nodes.get(epic_id)
            epic_base = nodes_all.get(epic_id)
            if epic_node is None or epic_node.kind != "epic" or not isinstance(epic_base, dict):
                continue
            epic_item = dict(epic_base)
            issues_all: list[dict[str, object]] = []
            for issue_id in _sort_ids(children.get(epic_id, [])):
                issue_node = graph_nodes.get(issue_id)
                issue_base = nodes_all.get(issue_id)
                if issue_node is None or issue_node.kind != "issue" or not isinstance(issue_base, dict):
                    continue
                issues_all.append(dict(issue_base))
            epic_item["issues"] = issues_all
            epics_all.append(epic_item)
        init_item["epics"] = epics_all
        tree_all.append(init_item)

    todo_issue_ids = _sort_ids([
        node_id
        for node_id, item in nodes_all.items()
        if isinstance(item, dict)
        and item.get("type") == "issue"
        and str(item.get("status") or "unknown").lower() != "done"
    ])
    todo_issue_set = set(todo_issue_ids)
    todo_epic_ids = _sort_ids([
        node_id
        for node_id, node in graph_nodes.items()
        if node.kind == "epic" and any(child_id in todo_issue_set for child_id in children.get(node_id, []))
    ])
    todo_epic_set = set(todo_epic_ids)
    todo_initiative_ids = _sort_ids([
        node_id
        for node_id, node in graph_nodes.items()
        if node.kind == "initiative" and any(child_id in todo_epic_set for child_id in children.get(node_id, []))
    ])
    todo_initiative_set = set(todo_initiative_ids)
    todo_node_ids = todo_issue_set | todo_epic_set | todo_initiative_set

    nodes_todo: dict[str, dict[str, object]] = {}
    for node_id in _sort_ids(list(todo_node_ids)):
        base = nodes_all.get(node_id)
        if not isinstance(base, dict):
            continue
        item = dict(base)
        item["children"] = [child_id for child_id in children.get(node_id, []) if child_id in todo_node_ids]
        nodes_todo[node_id] = item

    tree_todo: list[dict[str, object]] = []
    for initiative_id in todo_initiative_ids:
        init_base = nodes_todo.get(initiative_id)
        if not isinstance(init_base, dict):
            continue
        init_item = dict(init_base)
        epics_todo: list[dict[str, object]] = []
        for epic_id in _sort_ids([
            child_id for child_id in children.get(initiative_id, []) if child_id in todo_epic_set
        ]):
            epic_base = nodes_todo.get(epic_id)
            if not isinstance(epic_base, dict):
                continue
            epic_item = dict(epic_base)
            issues_todo: list[dict[str, object]] = []
            for issue_id in _sort_ids([
                child_id for child_id in children.get(epic_id, []) if child_id in todo_issue_set
            ]):
                issue_base = nodes_todo.get(issue_id)
                if isinstance(issue_base, dict):
                    issues_todo.append(dict(issue_base))
            epic_item["issues"] = issues_todo
            epics_todo.append(epic_item)
        init_item["epics"] = epics_todo
        tree_todo.append(init_item)

    deps_top_all = {
        "valid": result.deps_preflight_error is None,
        "error": result.deps_preflight_error,
        "issue_edges": list(deps_issue_edges_all),
        "edge_direction": "depends_on (dependent -> prerequisite)",
    }
    deps_issue_edges_todo = [
        edge for edge in deps_issue_edges_all if edge.get("from") in todo_issue_set and edge.get("to") in todo_issue_set
    ]
    deps_top_todo = {
        "valid": result.deps_preflight_error is None,
        "error": result.deps_preflight_error,
        "issue_edges": list(deps_issue_edges_todo),
        "edge_direction": "depends_on (dependent -> prerequisite)",
    }

    common = {
        "schema_version": 2,
        "generated_at": result.generated_at,
        "active": _active_to_json(result.active),
        "warnings": list(result.warnings),
        "root": "spec-dock/initiatives",
    }
    payload_all = {
        **common,
        "projection": FULL_HISTORY_PROJECTION,
        "deps": deps_top_all,
        "nodes": {
            node_id: {
                **item,
                "depends_on": list(result.raw_node_depends_on_map.get(node_id, [])),
            }
            for node_id, item in nodes_all.items()
        },
    }
    payload_todo = {
        **common,
        "projection": CURRENT_FUTURE_PROJECTION,
        "deps": deps_top_todo,
        "nodes": nodes_todo,
    }
    payload_tree_all = {
        **common,
        "deps": deps_top_all,
        "tree": tree_all,
    }
    payload_tree_todo = {
        **common,
        "deps": deps_top_todo,
        "tree": tree_todo,
    }
    return payload_all, payload_todo, payload_tree_all, payload_tree_todo


def render_index_artifact(result: SyncStateResult) -> IndexArtifact:
    payload_all, payload_todo, _, _ = _build_state_payloads(result)
    all_text = json.dumps(payload_all, ensure_ascii=False, indent=2) + "\n"
    todo_text = json.dumps(payload_todo, ensure_ascii=False, indent=2) + "\n"
    return IndexArtifact(all_json_text=all_text, todo_json_text=todo_text)


def render_tree_artifact(result: SyncStateResult) -> TreeArtifact:
    _, _, payload_all, payload_todo = _build_state_payloads(result)
    json_all_text = json.dumps(payload_all, ensure_ascii=False, indent=2) + "\n"
    json_todo_text = json.dumps(payload_todo, ensure_ascii=False, indent=2) + "\n"
    active = _active_to_json(result.active)
    if result.deps_preflight_error is None:
        all_puml = render_tree_ready_board_puml(payload_all, active=active, todo_only=False)
        todo_puml = render_tree_ready_board_puml(payload_all, active=active, todo_only=True)
    else:
        all_puml = render_deps_disabled_tree_puml(todo_only=False, error=result.deps_preflight_error)
        todo_puml = render_deps_disabled_tree_puml(todo_only=True, error=result.deps_preflight_error)
    return TreeArtifact(
        all_json_text=json_all_text,
        todo_json_text=json_todo_text,
        all_puml_text=all_puml,
        todo_puml_text=todo_puml,
    )


def _issue_status_value(result: SyncStateResult, issue_id: str) -> str:
    status = result.issue_statuses.get(issue_id)
    return status.effective_status.lower() if status is not None else "unknown"


def _issue_is_satisfied(result: SyncStateResult, issue_id: str) -> bool:
    return _issue_status_value(result, issue_id) in {"done", "closed"}


def _node_payload(result: SyncStateResult, node_id: str) -> dict[str, object] | None:
    node = result.graph.nodes_by_id.get(node_id)
    if node is None:
        return None
    item: dict[str, object] = {
        "id": node.id,
        "type": node.kind,
        "title": node.title,
        "parent_id": node.parent_id,
        "initiative_id": node.initiative_id,
        "epic_id": node.epic_id,
    }
    if node.kind == "issue":
        status = result.issue_statuses.get(node.id)
        effective_status = status.effective_status if status is not None else "unknown"
        evaluation = result.deps_eval_by_id.get(node.id)
        ready = bool(evaluation.ready) if evaluation is not None else False
        item.update({
            "status": effective_status,
            "authority": status.authority if status is not None else "unknown",
            "effective_status": effective_status,
            "source": status.source if status is not None else "unknown",
            "stale": bool(status.stale) if status is not None else True,
            "last_sync_at": status.last_sync_at if status is not None else None,
            "ready": ready,
            "depends_on": list(evaluation.blockers) if evaluation is not None else [],
            "issue_blockers": list(evaluation.issue_blockers) if evaluation is not None else [],
            "node_blockers": [
                _deps_node_blocker_payload(blocker)
                for blocker in (evaluation.node_blockers if evaluation is not None else [])
            ],
            "state": _issue_raw_state(result, node.id),
        })
    else:
        visual_state = _high_level_visual_state(result, node.id)
        state = visual_state["state"] if visual_state is not None else "unknown"
        item.update({
            "state": state,
            "state_source": visual_state["state_source"] if visual_state is not None else "none",
            "ready": state in {"closed", "done"},
        })
    return item


def _build_deps_issues_v2_payload(result: SyncStateResult) -> dict[str, object]:
    include_ids: set[str] = set()
    edges_by_key: dict[tuple[str, str, str, str], dict[str, str]] = {}
    dependency_contexts_by_key: dict[tuple[str, str, str], dict[str, object]] = {}

    def add_dependency_context(context: object) -> None:
        payload = _deps_dependency_context_payload(context)
        source_issue_id = str(payload["source_issue_id"])
        target_node_id = str(payload["target_node_id"])
        expansion = str(payload["expansion"])
        if not source_issue_id or not target_node_id:
            return
        if (
            payload["target_node_kind"] == "issue"
            and payload["dependency_disposition"] is None
            and _issue_is_satisfied(result, target_node_id)
        ):
            status = result.issue_statuses.get(target_node_id)
            payload["lifecycle_state"] = _issue_status_value(result, target_node_id)
            payload["lifecycle_source"] = status.source if status is not None else "unknown"
            payload["dependency_disposition"] = "satisfied"
            payload["disposition_basis"] = "local_done"
        key = (source_issue_id, target_node_id, expansion)
        existing = dependency_contexts_by_key.get(key)
        if existing is None:
            dependency_contexts_by_key[key] = payload
            return
        if existing.get("source_node_id") in {None, "", existing.get("source_issue_id")}:
            existing["source_node_id"] = payload["source_node_id"]
        for field in (
            "lifecycle_state",
            "lifecycle_source",
            "dependency_disposition",
            "disposition_basis",
        ):
            if payload.get(field) is not None:
                existing[field] = payload[field]

    def add_node_blocker_context(blocker: object) -> None:
        blocker_payload = _deps_node_blocker_payload(blocker)
        target_node_id = str(blocker_payload["node_id"])
        source_issue_id = str(blocker_payload["source_issue_id"])
        if not target_node_id or not source_issue_id:
            return
        target_node = result.graph.nodes_by_id.get(target_node_id)
        key = (source_issue_id, target_node_id, "empty")
        if key in dependency_contexts_by_key:
            return
        dependency_contexts_by_key[key] = {
            "source_node_id": source_issue_id,
            "source_issue_id": source_issue_id,
            "target_node_id": target_node_id,
            "target_node_kind": target_node.kind if target_node is not None else "unknown",
            "target_issue_ids": [],
            "expansion": "empty",
            "lifecycle_state": blocker_payload["lifecycle_state"],
            "lifecycle_source": blocker_payload["lifecycle_source"],
            "dependency_disposition": blocker_payload["dependency_disposition"],
            "disposition_basis": blocker_payload["disposition_basis"],
        }

    def add_edge(
        *,
        source_issue_id: str,
        target_node_id: str,
        state: str,
        relation: str,
        source: str,
    ) -> None:
        if source_issue_id not in result.graph.nodes_by_id or target_node_id not in result.graph.nodes_by_id:
            return
        include_ids.add(source_issue_id)
        include_ids.add(target_node_id)
        key = (source_issue_id, target_node_id, state, relation)
        edges_by_key[key] = {
            "from": source_issue_id,
            "to": target_node_id,
            "state": state,
            "relation": relation,
            "source": source,
        }

    for issue_id, node in result.graph.nodes_by_id.items():
        if node.kind != "issue":
            continue
        if not _issue_is_satisfied(result, issue_id):
            include_ids.add(issue_id)

    for issue_id in _sort_ids(list(result.deps_eval_by_id.keys())):
        evaluation = result.deps_eval_by_id[issue_id]
        if issue_id in include_ids:
            for blocker_id in evaluation.issue_blockers:
                add_edge(
                    source_issue_id=issue_id,
                    target_node_id=blocker_id,
                    state="blocking",
                    relation="compiled_issue",
                    source="readiness",
                )
            for blocker in evaluation.node_blockers:
                add_node_blocker_context(blocker)
                add_edge(
                    source_issue_id=issue_id,
                    target_node_id=blocker.node_id,
                    state="blocking",
                    relation="raw_direct",
                    source="readiness",
                )
            for context in evaluation.dependency_contexts:
                add_dependency_context(context)
            for context in evaluation.satisfied_dependencies:
                add_dependency_context(context)

    for issue_id in _sort_ids(list(result.deps_eval_by_id.keys())):
        evaluation = result.deps_eval_by_id[issue_id]
        for blocker in evaluation.node_blockers:
            add_node_blocker_context(blocker)
        for context in evaluation.dependency_contexts:
            add_dependency_context(context)
        for context in evaluation.satisfied_dependencies:
            add_dependency_context(context)

    for issue_id in _sort_ids(list(result.dependency_contexts_by_issue_id.keys())):
        for context in result.dependency_contexts_by_issue_id.get(issue_id, []):
            if (
                _object_value(context, "target_node_kind", None) == "issue"
                and _object_value(context, "dependency_disposition", None) is None
                and not _issue_is_satisfied(result, str(_object_value(context, "target_node_id", "")))
            ):
                continue
            add_dependency_context(context)

    nodes: dict[str, object] = {}
    for node_id in _sort_ids(list(include_ids)):
        node_payload = _node_payload(result, node_id)
        if node_payload is not None:
            nodes[node_id] = node_payload

    edges = sorted(
        edges_by_key.values(),
        key=lambda edge: (
            _sort_key(edge["from"]),
            _sort_key(edge["to"]),
            edge["state"],
            edge["relation"],
        ),
    )
    dependency_contexts = [
        dependency_contexts_by_key[key]
        for key in sorted(
            dependency_contexts_by_key,
            key=lambda item: (_sort_key(item[0]), _sort_key(item[1]), item[2]),
        )
    ]
    return {
        "schema_version": 2,
        "generated_at": result.generated_at,
        "projection": ISSUE_READINESS_WITH_DEPENDENCY_CONTEXT_PROJECTION,
        "source": {"sync_state": "readiness_evaluation", "schema_version": 2},
        "deps": {"valid": True, "error": None},
        "nodes": nodes,
        "edges": edges,
        "dependency_contexts": dependency_contexts,
        "edge_direction": "depends_on (dependent -> prerequisite)",
    }


def render_deps_issues_artifact(result: SyncStateResult) -> DepsIssuesArtifact:
    if result.deps_preflight_error is None:
        payload = _build_deps_issues_v2_payload(result)
        puml = render_deps_issues_puml(payload)
    else:
        payload = {
            "schema_version": 2,
            "generated_at": result.generated_at,
            "projection": ISSUE_READINESS_WITH_DEPENDENCY_CONTEXT_PROJECTION,
            "source": {"sync_state": "readiness_evaluation", "schema_version": 2},
            "deps": {"valid": False, "error": result.deps_preflight_error},
            "nodes": {},
            "edges": [],
            "dependency_contexts": [],
            "edge_direction": "depends_on (dependent -> prerequisite)",
        }
        puml = render_deps_disabled_deps_issues_puml(error=result.deps_preflight_error)

    return DepsIssuesArtifact(
        json_text=json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        puml_text=puml,
    )


def render_deps_raw_artifact(result: SyncStateResult) -> DepsRawArtifact:
    if result.deps_preflight_error is not None:
        return DepsRawArtifact(puml_text=render_deps_disabled_deps_raw_puml(error=result.deps_preflight_error))
    payload = _build_deps_raw_payload(result)
    return DepsRawArtifact(puml_text=render_deps_raw_puml(payload))


def render_context_pack(active_selection: ActiveSelection | None) -> str:
    initiative_id = active_selection.initiative_id if active_selection is not None else None
    epic_id = active_selection.epic_id if active_selection is not None else None
    issue_id = active_selection.issue_id if active_selection is not None else None

    lines: list[str] = []
    lines.append("# Context Pack (generated)")
    lines.append("")
    lines.append("## Active")
    lines.append(f"- initiative: {initiative_id or '(none)'}")
    lines.append(f"- epic: {epic_id or '(none)'}")
    lines.append(f"- issue: {issue_id or '(none)'}")
    lines.append("")
    lines.append("## Generated state")
    lines.append("- entry: `spec-dock/.agent/active.json`")
    lines.append("- default working set: `spec-dock/.agent/index.json`")
    lines.append("- default dependency view: `spec-dock/.agent/deps-issues.json`")
    lines.append("- escalation only: `spec-dock/.agent/index-all.json`")
    lines.append("- human-oriented tree: `spec-dock/.agent/tree.json`")
    lines.append("")
    lines.append("## Read order")
    lines.append("- Start with `spec-dock/.agent/active.json`.")
    lines.append("- For normal work, read `spec-dock/.agent/index.json` and `spec-dock/.agent/deps-issues.json`.")
    lines.append("- Read `spec-dock/.agent/index-all.json` only when full-history context is needed.")
    lines.append(
        "- `spec-dock/active/context-pack.md` is human guidance that mirrors this contract; it is not the sole source of truth."
    )
    lines.append("- Then follow the active documents:")
    if initiative_id:
        lines.append("- `spec-dock/active/initiative/requirement.md`")
        lines.append("- `spec-dock/active/initiative/design.md`")
        lines.append("- `spec-dock/active/initiative/plan.md`")
    else:
        lines.append("- `spec-dock/active/initiative/README.md`")
    if epic_id:
        lines.append("- `spec-dock/active/epic/requirement.md`")
        lines.append("- `spec-dock/active/epic/design.md`")
        lines.append("- `spec-dock/active/epic/plan.md`")
    else:
        lines.append("- `spec-dock/active/epic/README.md`")
    if issue_id:
        lines.append("- `spec-dock/active/issue/requirement.md`")
        lines.append("- `spec-dock/active/issue/design.md`")
        lines.append("- `spec-dock/active/issue/plan.md`")
        lines.append("- `spec-dock/active/issue/report.md`")
    else:
        lines.append("- `spec-dock/active/issue/README.md`")
    lines.append("")
    lines.append("## Commands")
    lines.append("- state (github default): `./spec-dock/scripts/spec-dock sync`")
    lines.append("- state (cache/local opt-out): `./spec-dock/scripts/spec-dock sync --no-github`")
    lines.append("- validate: `./spec-dock/scripts/spec-dock validate`")
    lines.append("")
    return "\n".join(lines) + "\n"
