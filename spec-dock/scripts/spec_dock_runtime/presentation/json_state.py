from __future__ import annotations

import json
from pathlib import Path

from ..application.contracts import DepsCheckResult, SyncStateResult
from ..domain.ids import deps_node_sort_key
from ..domain.models import ActiveSelection, DepsNodeState, SpecNode
from .contracts import DepsIssuesArtifact, IndexArtifact, TreeArtifact
from .puml import (
    render_deps_disabled_deps_issues_puml,
    render_deps_disabled_tree_puml,
    render_deps_issues_puml,
    render_tree_ready_board_puml,
)

CURRENT_FUTURE_PROJECTION = "current-future"
FULL_HISTORY_PROJECTION = "full-history"
OPEN_ISSUES_DEPENDENCY_VIEW_PROJECTION = "open-issues-dependency-view"


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
        "schema_version": 1,
        "target": target_id,
        "target_status": target_status_payload,
        "ready": bool(inspection.evaluation.ready),
        "effective_depends_on": list(inspection.effective_depends_on),
        "blockers": list(inspection.evaluation.blockers),
        "nodes": {
            node_id: {
                "state": node_state.status,
                "ready": bool(node_state.ready),
                "authority": (
                    inspection.issue_statuses[node_id].authority
                    if node_id in inspection.issue_statuses
                    else "unknown"
                ),
                "effective_status": (
                    inspection.issue_statuses[node_id].effective_status
                    if node_id in inspection.issue_statuses
                    else "unknown"
                ),
                "source": (
                    inspection.issue_statuses[node_id].source
                    if node_id in inspection.issue_statuses
                    else "unknown"
                ),
                "stale": (
                    bool(inspection.issue_statuses[node_id].stale)
                    if node_id in inspection.issue_statuses
                    else True
                ),
                "last_sync_at": (
                    inspection.issue_statuses[node_id].last_sync_at
                    if node_id in inspection.issue_statuses
                    else None
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


def _active_to_json(active: ActiveSelection | None) -> dict[str, object] | None:
    if active is None:
        return None
    return {
        "initiative": {"id": active.initiative_id} if active.initiative_id else None,
        "epic": {"id": active.epic_id} if active.epic_id else None,
        "issue": {"id": active.issue_id} if active.issue_id else None,
    }


def _deps_state_by_issue_id(result: SyncStateResult) -> dict[str, DepsNodeState]:
    return {
        node_state.node_id: node_state
        for node_state in result.deps_state.nodes
    }


def _build_children(graph_nodes: dict[str, SpecNode]) -> dict[str, list[str]]:
    children: dict[str, list[str]] = {node_id: [] for node_id in graph_nodes.keys()}
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
            dep_ids = _sort_ids(
                [dep_id for dep_id in result.issue_depends_on_map.get(issue_id, []) if isinstance(dep_id, str)]
            )
            for dep_id in dep_ids:
                edges.append({"from": issue_id, "to": dep_id, "kind": "depends_on"})
        edges.sort(key=lambda item: (_sort_key(item["from"]), _sort_key(item["to"])))
        return edges

    edges: list[dict[str, str]] = []
    for issue_id in _sort_ids(list(deps_state_by_issue_id.keys())):
        node_state = deps_state_by_issue_id[issue_id]
        for dep_id in node_state.effective_depends_on:
            edges.append({"from": issue_id, "to": dep_id, "kind": "depends_on"})
    edges.sort(key=lambda item: (_sort_key(item["from"]), _sort_key(item["to"])))
    return edges


def _build_state_payloads(result: SyncStateResult) -> tuple[dict[str, object], dict[str, object]]:
    graph_nodes = result.graph.nodes_by_id
    children = _build_children(graph_nodes)
    deps_state_by_issue_id = _deps_state_by_issue_id(result)
    deps_issue_edges_all = (
        _build_issue_edges_from_deps_state(result, deps_state_by_issue_id)
        if result.deps_preflight_error is None
        else []
    )

    nodes_all: dict[str, object] = {}
    for node_id in _sort_ids(list(graph_nodes.keys())):
        node = graph_nodes[node_id]
        item: dict[str, object] = {
            "type": node.kind,
            "id": node.id,
            "title": node.title,
            "path": _to_repo_relative_specdock_path(node.path, repo_root=result.repo_root),
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
                    snapshot = result.github_snapshot_by_repo_scope_and_issue_number.get(
                        (repo_scope, int(node.github_issue_number))
                    )
            if snapshot is not None:
                github_item.update(
                    {
                        "state": snapshot.state,
                        "url": snapshot.url,
                        "updated_at": snapshot.updated_at,
                        "labels": list(snapshot.labels),
                    }
                )
            item["github"] = github_item

        if node.kind in ("initiative", "epic"):
            progress_item = result.progress.by_node_id.get(node.id)
            if isinstance(progress_item, dict):
                item["progress"] = dict(progress_item)

        nodes_all[node.id] = item

    tree_all: list[dict[str, object]] = []
    initiative_ids = _sort_ids(
        [node_id for node_id, node in graph_nodes.items() if node.kind == "initiative"]
    )
    for initiative_id in initiative_ids:
        init_base = nodes_all.get(initiative_id)
        if not isinstance(init_base, dict):
            continue
        init_item = dict(init_base)
        epics: list[dict[str, object]] = []
        for epic_id in _sort_ids(children.get(initiative_id, [])):
            epic_node = graph_nodes.get(epic_id)
            epic_base = nodes_all.get(epic_id)
            if epic_node is None or epic_node.kind != "epic" or not isinstance(epic_base, dict):
                continue
            epic_item = dict(epic_base)
            issues: list[dict[str, object]] = []
            for issue_id in _sort_ids(children.get(epic_id, [])):
                issue_node = graph_nodes.get(issue_id)
                issue_base = nodes_all.get(issue_id)
                if issue_node is None or issue_node.kind != "issue" or not isinstance(issue_base, dict):
                    continue
                issues.append(dict(issue_base))
            epic_item["issues"] = issues
            epics.append(epic_item)
        init_item["epics"] = epics
        tree_all.append(init_item)

    todo_issue_ids = _sort_ids(
        [
            node_id
            for node_id, item in nodes_all.items()
            if isinstance(item, dict)
            and item.get("type") == "issue"
            and str(item.get("status") or "unknown").lower() != "done"
        ]
    )
    todo_issue_set = set(todo_issue_ids)
    todo_epic_ids = _sort_ids(
        [
            node_id
            for node_id, node in graph_nodes.items()
            if node.kind == "epic" and any(child_id in todo_issue_set for child_id in children.get(node_id, []))
        ]
    )
    todo_epic_set = set(todo_epic_ids)
    todo_initiative_ids = _sort_ids(
        [
            node_id
            for node_id, node in graph_nodes.items()
            if node.kind == "initiative" and any(child_id in todo_epic_set for child_id in children.get(node_id, []))
        ]
    )
    todo_initiative_set = set(todo_initiative_ids)
    todo_node_ids = todo_issue_set | todo_epic_set | todo_initiative_set

    nodes_todo: dict[str, object] = {}
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
        epics: list[dict[str, object]] = []
        for epic_id in _sort_ids([child_id for child_id in children.get(initiative_id, []) if child_id in todo_epic_set]):
            epic_base = nodes_todo.get(epic_id)
            if not isinstance(epic_base, dict):
                continue
            epic_item = dict(epic_base)
            issues: list[dict[str, object]] = []
            for issue_id in _sort_ids([child_id for child_id in children.get(epic_id, []) if child_id in todo_issue_set]):
                issue_base = nodes_todo.get(issue_id)
                if isinstance(issue_base, dict):
                    issues.append(dict(issue_base))
            epic_item["issues"] = issues
            epics.append(epic_item)
        init_item["epics"] = epics
        tree_todo.append(init_item)

    deps_top_all = {
        "valid": result.deps_preflight_error is None,
        "error": result.deps_preflight_error,
        "issue_edges": list(deps_issue_edges_all),
        "edge_direction": "depends_on (dependent -> prerequisite)",
    }
    deps_issue_edges_todo = [
        edge
        for edge in deps_issue_edges_all
        if edge.get("from") in todo_issue_set and edge.get("to") in todo_issue_set
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
        "nodes": nodes_all,
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


def render_deps_issues_artifact(result: SyncStateResult) -> DepsIssuesArtifact:
    if result.deps_preflight_error is None:
        index_artifact = render_index_artifact(result)
        index_payload = json.loads(index_artifact.todo_json_text)
        deps_top = index_payload.get("deps") if isinstance(index_payload, dict) else {}
        index_nodes = index_payload.get("nodes") if isinstance(index_payload, dict) else {}
        active = index_payload.get("active") if isinstance(index_payload, dict) else None
        if not isinstance(index_nodes, dict):
            index_nodes = {}
        active_issue_id = None
        if isinstance(active, dict):
            issue_entry = active.get("issue")
            if isinstance(issue_entry, dict) and isinstance(issue_entry.get("id"), str):
                active_issue_id = issue_entry["id"]

        issue_nodes: dict[str, object] = {}
        for node_id in _sort_ids(list(index_nodes.keys())):
            item = index_nodes.get(node_id)
            if not isinstance(item, dict) or item.get("type") != "issue":
                continue
            status = str(item.get("status") or "unknown")
            deps = item.get("deps")
            ready = False
            depends_on: list[str] = []
            if isinstance(deps, dict):
                raw_ready = deps.get("ready")
                if isinstance(raw_ready, bool):
                    ready = raw_ready
                raw_depends_on = deps.get("depends_on")
                if isinstance(raw_depends_on, list):
                    depends_on = [str(dep_id) for dep_id in raw_depends_on if isinstance(dep_id, str)]
            if node_id == active_issue_id:
                state = "doing"
            elif status == "unknown":
                state = "unknown"
            elif ready:
                state = "ready"
            else:
                state = "blocked"
            issue_nodes[node_id] = {
                "id": node_id,
                "title": item.get("title"),
                "status": status,
                "ready": ready,
                "depends_on": depends_on,
                "state": state,
            }

        edge_items = deps_top.get("issue_edges") if isinstance(deps_top, dict) else []
        edges: list[dict[str, str]] = []
        issue_id_set = set(issue_nodes.keys())
        if isinstance(edge_items, list):
            for edge in edge_items:
                if not isinstance(edge, dict):
                    continue
                from_id = edge.get("from")
                to_id = edge.get("to")
                if (
                    isinstance(from_id, str)
                    and isinstance(to_id, str)
                    and from_id in issue_id_set
                    and to_id in issue_id_set
                ):
                    edges.append({"from": from_id, "to": to_id})
        edges.sort(key=lambda edge: (_sort_key(edge["from"]), _sort_key(edge["to"])))

        payload = {
            "schema_version": 1,
            "generated_at": result.generated_at,
            "projection": OPEN_ISSUES_DEPENDENCY_VIEW_PROJECTION,
            "source": {"index": "spec-dock/.agent/index.json", "schema_version": 2},
            "deps": {"valid": True, "error": None},
            "nodes": issue_nodes,
            "edges": edges,
            "edge_direction": "depends_on (dependent -> prerequisite)",
        }
        puml = render_deps_issues_puml(payload)
    else:
        payload = {
            "schema_version": 1,
            "generated_at": result.generated_at,
            "projection": OPEN_ISSUES_DEPENDENCY_VIEW_PROJECTION,
            "source": {"index": "spec-dock/.agent/index.json", "schema_version": 2},
            "deps": {"valid": False, "error": result.deps_preflight_error},
            "nodes": {},
            "edges": [],
            "edge_direction": "depends_on (dependent -> prerequisite)",
        }
        puml = render_deps_disabled_deps_issues_puml(error=result.deps_preflight_error)

    return DepsIssuesArtifact(
        json_text=json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        puml_text=puml,
    )


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
