from __future__ import annotations

from .ids import deps_node_sort_key
from .models import (
    ActiveSelection,
    DepsEvaluation,
    DepsNodeState,
    DepsState,
    IssueStatusSnapshot,
    NodeId,
    SpecGraph,
    TargetDepsInspection,
)

_BLOCKERS_TOP_LIMIT = 5
_KNOWN_ISSUE_STATUSES = {"done", "open", "unknown"}


def _safe_sorted_node_ids(node_ids: set[str] | list[str]) -> list[str]:
    try:
        return sorted(node_ids, key=deps_node_sort_key)
    except RuntimeError:
        return sorted(node_ids)


def _normalize_issue_status(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in _KNOWN_ISSUE_STATUSES:
        return normalized
    return "unknown"


def _issue_status(issue_id: str, issue_statuses: dict[str, IssueStatusSnapshot]) -> str:
    snapshot = issue_statuses.get(issue_id)
    if snapshot is None:
        return "unknown"
    return _normalize_issue_status(snapshot.effective_status)


def _issue_ids_for_target(graph: SpecGraph, target_id: NodeId) -> list[str]:
    target = graph.nodes_by_id.get(target_id.value)
    if target is None:
        raise RuntimeError(f"Node not found: {target_id.value}")

    if target.kind == "issue":
        return [target.id]
    if target.kind == "epic":
        return _safe_sorted_node_ids(
            [
                node_id
                for node_id, node in graph.nodes_by_id.items()
                if node.kind == "issue" and node.epic_id == target.id
            ]
        )
    if target.kind == "initiative":
        return _safe_sorted_node_ids(
            [
                node_id
                for node_id, node in graph.nodes_by_id.items()
                if node.kind == "issue" and node.initiative_id == target.id
            ]
        )
    raise RuntimeError(f"Unsupported node type for deps check: {target.kind} ({target.id})")


def collect_reachable_issue_ids(issue_depends_on_map: dict[str, list[str]], start_issue_ids: list[str]) -> list[str]:
    reachable: set[str] = set()
    stack = list(reversed(_safe_sorted_node_ids(start_issue_ids)))
    while stack:
        issue_id = stack.pop()
        if issue_id in reachable:
            continue
        reachable.add(issue_id)

        next_ids = _safe_sorted_node_ids(issue_depends_on_map.get(issue_id, []))
        for next_issue_id in reversed(next_ids):
            if next_issue_id not in reachable:
                stack.append(next_issue_id)

    return _safe_sorted_node_ids(reachable)


def build_effective_deps_map(graph: SpecGraph, issue_depends_on_map: dict[str, list[str]]) -> dict[str, list[str]]:
    issue_ids = _safe_sorted_node_ids(
        [node_id for node_id, node in graph.nodes_by_id.items() if node.kind == "issue"]
    )
    issue_id_set = set(issue_ids)

    out: dict[str, list[str]] = {}
    for issue_id in issue_ids:
        issue = graph.nodes_by_id[issue_id]
        deps: set[str] = set()

        for dep_id in issue_depends_on_map.get(issue_id, []):
            if dep_id in issue_id_set and dep_id != issue_id:
                deps.add(dep_id)

        if issue.epic_id:
            for dep_id in issue_depends_on_map.get(issue.epic_id, []):
                if dep_id in issue_id_set and dep_id != issue_id:
                    deps.add(dep_id)

        if issue.initiative_id:
            for dep_id in issue_depends_on_map.get(issue.initiative_id, []):
                if dep_id in issue_id_set and dep_id != issue_id:
                    deps.add(dep_id)

        out[issue_id] = _safe_sorted_node_ids(deps)

    return out


def _derive_issue_depends_on_view(
    issue_depends_on_map: dict[str, list[str]],
    issue_statuses: dict[str, IssueStatusSnapshot],
) -> dict[str, dict[str, object]]:
    def closure_excluding_done(start_issue_id: str) -> list[str]:
        seen: set[str] = set()
        stack = list(reversed(_safe_sorted_node_ids(issue_depends_on_map.get(start_issue_id, []))))
        while stack:
            dep_id = stack.pop()
            if dep_id in seen:
                continue

            if _issue_status(dep_id, issue_statuses) == "done":
                continue

            seen.add(dep_id)
            next_ids = _safe_sorted_node_ids(issue_depends_on_map.get(dep_id, []))
            for next_id in reversed(next_ids):
                if next_id not in seen:
                    stack.append(next_id)

        return _safe_sorted_node_ids(seen)

    all_issue_ids = _safe_sorted_node_ids(set(issue_depends_on_map.keys()) | set(issue_statuses.keys()))
    derived: dict[str, dict[str, object]] = {}
    for issue_id in all_issue_ids:
        status = _issue_status(issue_id, issue_statuses)
        if status == "done":
            depends_on: list[str] = []
            ready = True
        else:
            depends_on = closure_excluding_done(issue_id)
            ready = False if status == "unknown" else len(depends_on) == 0

        derived[issue_id] = {
            "ready": ready,
            "depends_on": depends_on,
            "blockers_top": depends_on[:_BLOCKERS_TOP_LIMIT],
        }

    return derived


def _build_evaluation(
    *,
    target_issue_ids: list[str],
    derived_issue_deps: dict[str, dict[str, object]],
    issue_statuses: dict[str, IssueStatusSnapshot],
) -> DepsEvaluation:
    blockers_set: set[str] = set()
    target_ready = True
    for issue_id in target_issue_ids:
        issue_info = derived_issue_deps.get(issue_id) or {"ready": False, "depends_on": []}
        target_ready = target_ready and bool(issue_info.get("ready", False))

        for blocker in issue_info.get("depends_on") or []:
            if isinstance(blocker, str):
                blockers_set.add(blocker)

    blockers = _safe_sorted_node_ids(blockers_set)
    blockers_top = blockers[:_BLOCKERS_TOP_LIMIT]
    closure = list(blockers)

    if target_ready:
        guard_reason = "ready"
    else:
        unknown_in_target = any(_issue_status(issue_id, issue_statuses) == "unknown" for issue_id in target_issue_ids)
        unknown_in_blockers = any(_issue_status(issue_id, issue_statuses) == "unknown" for issue_id in blockers)
        guard_reason = "unknown" if unknown_in_target or unknown_in_blockers else "blocked"

    return DepsEvaluation(
        ready=target_ready,
        guard_reason=guard_reason,
        blockers=blockers,
        blockers_top=blockers_top,
        closure=closure,
    )


def validate_deps_cycles(issue_depends_on_map: dict[str, list[str]]) -> None:
    visited: set[str] = set()
    in_stack: set[str] = set()
    path: list[str] = []

    for start_id in _safe_sorted_node_ids(list(issue_depends_on_map.keys())):
        if start_id in visited:
            continue

        stack: list[tuple[str, int]] = [(start_id, 0)]
        while stack:
            node_id, next_index = stack[-1]

            if node_id not in visited:
                visited.add(node_id)
                in_stack.add(node_id)
                path.append(node_id)

            deps = _safe_sorted_node_ids(issue_depends_on_map.get(node_id, []))
            if next_index >= len(deps):
                stack.pop()
                in_stack.remove(node_id)
                path.pop()
                continue

            dep_id = deps[next_index]
            stack[-1] = (node_id, next_index + 1)

            if dep_id in in_stack:
                try:
                    start_index = path.index(dep_id)
                except ValueError:
                    start_index = 0
                cycle = path[start_index:] + [dep_id]
                raise RuntimeError("Dependency cycle detected: " + " -> ".join(cycle))

            if dep_id not in visited:
                stack.append((dep_id, 0))


def issue_dependency_exists(
    issue_depends_on_map: dict[str, list[str]],
    *,
    from_issue_id: str,
    to_issue_id: str,
) -> bool:
    return to_issue_id in issue_depends_on_map.get(from_issue_id, [])


def ensure_issue_dependency_add_would_not_create_cycle(
    issue_depends_on_map: dict[str, list[str]],
    *,
    from_issue_id: str,
    to_issue_id: str,
) -> None:
    candidate_map: dict[str, list[str]] = {
        issue_id: list(depends_on)
        for issue_id, depends_on in issue_depends_on_map.items()
    }
    candidate_map.setdefault(from_issue_id, [])
    candidate_map.setdefault(to_issue_id, [])
    candidate_map[from_issue_id].append(to_issue_id)
    validate_deps_cycles(candidate_map)


def evaluate_readiness(
    graph: SpecGraph,
    issue_depends_on_map: dict[str, list[str]],
    target_id: NodeId,
    issue_statuses: dict[str, IssueStatusSnapshot],
) -> DepsEvaluation:
    effective_deps_map = build_effective_deps_map(graph, issue_depends_on_map)
    target_issue_ids = _issue_ids_for_target(graph, target_id)
    reachable_issue_ids = collect_reachable_issue_ids(effective_deps_map, target_issue_ids)
    reachable_depends_on = {
        issue_id: list(effective_deps_map.get(issue_id, []))
        for issue_id in reachable_issue_ids
    }
    validate_deps_cycles(reachable_depends_on)

    derived_issue_deps = _derive_issue_depends_on_view(reachable_depends_on, issue_statuses)
    return _build_evaluation(
        target_issue_ids=target_issue_ids,
        derived_issue_deps=derived_issue_deps,
        issue_statuses=issue_statuses,
    )


def _issue_state_for_inspection(
    *,
    issue_id: str,
    issue_statuses: dict[str, IssueStatusSnapshot],
    ready: bool,
    active_issue_id: str | None,
) -> str:
    status = _issue_status(issue_id, issue_statuses)
    if status == "done":
        return "done"
    if issue_id == active_issue_id:
        return "doing"
    if status == "unknown":
        return "unknown"
    if ready:
        return "ready"
    return "blocked"


def inspect_target_deps(
    graph: SpecGraph,
    issue_depends_on_map: dict[str, list[str]],
    target_id: NodeId,
    issue_statuses: dict[str, IssueStatusSnapshot],
    active_issue_id: str | None,
) -> TargetDepsInspection:
    effective_deps_map = build_effective_deps_map(graph, issue_depends_on_map)
    target_issue_ids = _issue_ids_for_target(graph, target_id)
    reachable_issue_ids = collect_reachable_issue_ids(effective_deps_map, target_issue_ids)
    reachable_depends_on = {
        issue_id: list(effective_deps_map.get(issue_id, []))
        for issue_id in reachable_issue_ids
    }
    validate_deps_cycles(reachable_depends_on)

    derived_issue_deps = _derive_issue_depends_on_view(reachable_depends_on, issue_statuses)
    evaluation = _build_evaluation(
        target_issue_ids=target_issue_ids,
        derived_issue_deps=derived_issue_deps,
        issue_statuses=issue_statuses,
    )

    node_states: dict[str, DepsNodeState] = {}
    inspect_issue_ids = _safe_sorted_node_ids(set(target_issue_ids) | set(reachable_issue_ids))
    for issue_id in inspect_issue_ids:
        issue_view = derived_issue_deps.get(issue_id) or {"ready": False, "depends_on": [], "blockers_top": []}
        ready = bool(issue_view.get("ready", False))
        depends_on = [dep for dep in issue_view.get("depends_on", []) if isinstance(dep, str)]
        blockers_top = [dep for dep in issue_view.get("blockers_top", []) if isinstance(dep, str)]
        node_states[issue_id] = DepsNodeState(
            node_id=issue_id,
            status=_issue_state_for_inspection(
                issue_id=issue_id,
                issue_statuses=issue_statuses,
                ready=ready,
                active_issue_id=active_issue_id,
            ),
            ready=ready,
            blockers_top=blockers_top[:_BLOCKERS_TOP_LIMIT],
            effective_depends_on=depends_on,
        )

    target_effective_set: set[str] = set()
    for issue_id in target_issue_ids:
        issue_view = derived_issue_deps.get(issue_id) or {"depends_on": []}
        for dep_id in issue_view.get("depends_on", []):
            if isinstance(dep_id, str):
                target_effective_set.add(dep_id)

    inspected_status_ids = set(inspect_issue_ids)
    inspected_status_ids.add(target_id.value)

    return TargetDepsInspection(
        target_id=target_id,
        evaluation=evaluation,
        node_states=node_states,
        effective_depends_on=_safe_sorted_node_ids(target_effective_set),
        warnings=[],
        issue_statuses={
            issue_id: issue_statuses[issue_id]
            for issue_id in _safe_sorted_node_ids(inspected_status_ids)
            if issue_id in issue_statuses
        },
    )


def _active_leaf_id(active: ActiveSelection | None) -> str | None:
    if active is None:
        return None
    if active.issue_id:
        return active.issue_id
    if active.epic_id:
        return active.epic_id
    if active.initiative_id:
        return active.initiative_id
    return None


def build_deps_state(
    graph: SpecGraph,
    effective_deps_map: dict[str, list[str]],
    issue_statuses: dict[str, IssueStatusSnapshot],
    active: ActiveSelection | None,
    warnings: list[str],
) -> DepsState:
    validate_deps_cycles(effective_deps_map)

    issue_ids = _safe_sorted_node_ids(
        [node_id for node_id, node in graph.nodes_by_id.items() if node.kind == "issue"]
    )
    active_issue_id = _active_leaf_id(active)
    nodes: list[DepsNodeState] = []

    for issue_id in issue_ids:
        status = _issue_status(issue_id, issue_statuses)
        unresolved = [
            dep_id
            for dep_id in _safe_sorted_node_ids(effective_deps_map.get(issue_id, []))
            if _issue_status(dep_id, issue_statuses) != "done"
        ]

        if status == "done":
            ready = True
            unresolved = []
            state = "done"
        else:
            ready = status != "unknown" and len(unresolved) == 0
            if issue_id == active_issue_id:
                state = "doing"
            elif status == "unknown":
                state = "unknown"
            elif ready:
                state = "ready"
            else:
                state = "blocked"

        nodes.append(
            DepsNodeState(
                node_id=issue_id,
                status=state,
                ready=ready,
                blockers_top=unresolved[:_BLOCKERS_TOP_LIMIT],
                effective_depends_on=unresolved,
            )
        )

    return DepsState(nodes=nodes, warnings=list(warnings))
