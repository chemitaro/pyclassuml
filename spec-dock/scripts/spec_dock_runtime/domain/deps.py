from __future__ import annotations

from dataclasses import replace
from typing import TypeAlias

from spec_dock_runtime.domain.ids import deps_node_sort_key
from spec_dock_runtime.domain.models import (
    ActiveSelection,
    DepsDependencyContext,
    DepsDependencyDisposition,
    DepsDirectNodeDependency,
    DepsDispositionBasis,
    DepsEvaluation,
    DepsHighLevelStatus,
    DepsNodeBlocker,
    DepsNodeState,
    DepsState,
    IssueStatusSnapshot,
    NodeId,
    SpecGraph,
    TargetDepsInspection,
)

_BLOCKERS_TOP_LIMIT = 5
_KNOWN_ISSUE_STATUSES = {"done", "open", "closed", "unknown"}

DependencyContextInput: TypeAlias = DepsDependencyContext | dict[str, object]


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


def _issue_status_is_satisfied(status: str) -> bool:
    return status in {"closed", "done"}


def _issue_is_satisfied(issue_id: str, issue_statuses: dict[str, IssueStatusSnapshot]) -> bool:
    return _issue_status_is_satisfied(_issue_status(issue_id, issue_statuses))


def _issue_ids_for_target(graph: SpecGraph, target_id: NodeId) -> list[str]:
    target = graph.nodes_by_id.get(target_id.value)
    if target is None:
        raise RuntimeError(f"Node not found: {target_id.value}")

    if target.kind == "issue":
        return [target.id]
    if target.kind == "epic":
        return _safe_sorted_node_ids([
            node_id for node_id, node in graph.nodes_by_id.items() if node.kind == "issue" and node.epic_id == target.id
        ])
    if target.kind == "initiative":
        return _safe_sorted_node_ids([
            node_id
            for node_id, node in graph.nodes_by_id.items()
            if node.kind == "issue" and node.initiative_id == target.id
        ])
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
    issue_ids = _safe_sorted_node_ids([node_id for node_id, node in graph.nodes_by_id.items() if node.kind == "issue"])
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

            if _issue_is_satisfied(dep_id, issue_statuses):
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
        if _issue_status_is_satisfied(status):
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
    dependency_contexts_by_issue_id: dict[str, list[DependencyContextInput]] | None = None,
    high_level_statuses_by_node_id: dict[str, DepsHighLevelStatus] | None = None,
) -> DepsEvaluation:
    (
        node_blockers,
        satisfied_dependencies,
        dependency_contexts,
        suppressed_issue_roots_by_issue_id,
        unresolved_issue_roots_by_issue_id,
        direct_issue_targets_by_issue_id,
    ) = _evaluate_dependency_contexts(
        target_issue_ids=target_issue_ids,
        issue_statuses=issue_statuses,
        dependency_contexts_by_issue_id=dependency_contexts_by_issue_id,
        high_level_statuses_by_node_id=high_level_statuses_by_node_id,
    )

    issue_blockers_set: set[str] = set()
    filtered_depends_on_by_issue_id: dict[str, list[str]] = {}
    target_ready = True
    for issue_id in target_issue_ids:
        issue_info = derived_issue_deps.get(issue_id) or {"ready": False, "depends_on": []}
        status = _issue_status(issue_id, issue_statuses)
        issue_blocker_set: set[str] = set()
        suppressed_blockers = _dependency_closure(
            derived_issue_deps,
            suppressed_issue_roots_by_issue_id.get(issue_id, set()),
        )
        unresolved_blockers = _dependency_closure(
            derived_issue_deps,
            unresolved_issue_roots_by_issue_id.get(issue_id, set()),
        )
        direct_blockers = _dependency_closure(
            derived_issue_deps,
            direct_issue_targets_by_issue_id.get(issue_id, set()),
        )
        suppressed_blockers -= unresolved_blockers
        suppressed_blockers -= direct_blockers

        raw_depends_on = issue_info.get("depends_on")
        depends_on = raw_depends_on if isinstance(raw_depends_on, list) else []
        for blocker in depends_on:
            if isinstance(blocker, str):
                if blocker in suppressed_blockers:
                    continue
                issue_blocker_set.add(blocker)

        if _issue_status_is_satisfied(status):
            issue_ready = True
        else:
            issue_ready = status != "unknown" and len(issue_blocker_set) == 0
        target_ready = target_ready and issue_ready
        filtered_depends_on_by_issue_id[issue_id] = _safe_sorted_node_ids(issue_blocker_set)
        issue_blockers_set.update(issue_blocker_set)
    node_blocker_ids = [blocker.node_id for blocker in node_blockers]
    issue_blockers = _safe_sorted_node_ids(issue_blockers_set)
    blockers = _safe_sorted_node_ids(issue_blockers + node_blocker_ids)
    blockers_top = blockers[:_BLOCKERS_TOP_LIMIT]
    closure = list(blockers)
    target_ready = target_ready and len(node_blockers) == 0

    if target_ready:
        guard_reason = "ready"
    else:
        unknown_in_target = any(_issue_status(issue_id, issue_statuses) == "unknown" for issue_id in target_issue_ids)
        unknown_in_issue_blockers = any(
            _issue_status(issue_id, issue_statuses) == "unknown" for issue_id in issue_blockers
        )
        unknown_in_node_blockers = any(
            blocker.reason in {"empty_unknown", "lifecycle_unknown"} for blocker in node_blockers
        )
        guard_reason = (
            "unknown" if unknown_in_target or unknown_in_issue_blockers or unknown_in_node_blockers else "blocked"
        )

    return DepsEvaluation(
        ready=target_ready,
        guard_reason=guard_reason,
        blockers=blockers,
        blockers_top=blockers_top,
        closure=closure,
        issue_blockers=issue_blockers,
        node_blockers=node_blockers,
        satisfied_dependencies=satisfied_dependencies,
        dependency_contexts=dependency_contexts,
        debug_context={"filtered_depends_on_by_issue_id": filtered_depends_on_by_issue_id},
    )


def _context_value(context: DependencyContextInput, field_name: str, default: object = None) -> object:
    if isinstance(context, dict):
        return context.get(field_name, default)
    return getattr(context, field_name, default)


def _normalize_high_level_state(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"open", "closed", "done", "unknown"}:
        return normalized
    return "unknown"


def _all_target_issues_satisfied(
    target_issue_ids: tuple[str, ...],
    issue_statuses: dict[str, IssueStatusSnapshot],
) -> bool:
    if not target_issue_ids:
        return False
    return all(_issue_is_satisfied(issue_id, issue_statuses) for issue_id in target_issue_ids)


def _any_target_issue_unknown(
    target_issue_ids: tuple[str, ...],
    issue_statuses: dict[str, IssueStatusSnapshot],
) -> bool:
    return any(_issue_status(issue_id, issue_statuses) == "unknown" for issue_id in target_issue_ids)


def _any_target_issue_open(
    target_issue_ids: tuple[str, ...],
    issue_statuses: dict[str, IssueStatusSnapshot],
) -> bool:
    return any(_issue_status(issue_id, issue_statuses) == "open" for issue_id in target_issue_ids)


def _dependency_closure(
    derived_issue_deps: dict[str, dict[str, object]],
    root_issue_ids: set[str],
) -> set[str]:
    closed: set[str] = set()
    stack = list(root_issue_ids)
    while stack:
        issue_id = stack.pop()
        if issue_id in closed:
            continue
        closed.add(issue_id)
        issue_info = derived_issue_deps.get(issue_id) or {"depends_on": []}
        raw_depends_on = issue_info.get("depends_on")
        depends_on = raw_depends_on if isinstance(raw_depends_on, list) else []
        for dep_id in depends_on:
            if isinstance(dep_id, str) and dep_id not in closed:
                stack.append(dep_id)
    return closed


def _with_disposition(
    context: DepsDependencyContext,
    *,
    lifecycle_state: str,
    lifecycle_source: str,
    dependency_disposition: DepsDependencyDisposition,
    disposition_basis: DepsDispositionBasis,
) -> DepsDependencyContext:
    return replace(
        context,
        lifecycle_state=lifecycle_state,  # type: ignore[arg-type]
        lifecycle_source=lifecycle_source,
        dependency_disposition=dependency_disposition,
        disposition_basis=disposition_basis,
    )


def _dependency_context_from_input(context: DependencyContextInput) -> DepsDependencyContext:
    target_issue_ids = _context_value(context, "target_issue_ids", ())
    if isinstance(target_issue_ids, list):
        target_issue_ids = tuple(target_issue_ids)
    if not isinstance(target_issue_ids, tuple):
        target_issue_ids = ()

    return DepsDependencyContext(
        source_node_id=str(_context_value(context, "source_node_id", "")),
        source_issue_id=str(_context_value(context, "source_issue_id", "")),
        target_node_id=str(_context_value(context, "target_node_id", "")),
        target_node_kind=_context_value(context, "target_node_kind", "issue"),  # type: ignore[arg-type]
        target_issue_ids=target_issue_ids,
        expansion=_context_value(context, "expansion", "issue"),  # type: ignore[arg-type]
    )


def _target_issue_ids_and_expansion(
    graph: SpecGraph,
    target_node_id: str,
) -> tuple[tuple[str, ...], str]:
    target_node = graph.nodes_by_id[target_node_id]
    if target_node.kind == "issue":
        return ((target_node.id,), "issue")
    target_issue_ids = tuple(_issue_ids_for_target(graph, NodeId(target_node_id)))
    return (target_issue_ids, "expanded" if target_issue_ids else "empty")


def _issue_lifecycle_for_direct_dependency(
    *,
    issue_id: str,
    issue_statuses: dict[str, IssueStatusSnapshot],
) -> tuple[str, str, DepsDependencyDisposition, DepsDispositionBasis]:
    snapshot = issue_statuses.get(issue_id)
    state = _issue_status(issue_id, issue_statuses)
    lifecycle_source = snapshot.source if snapshot is not None else "unknown"
    if state in {"closed", "done"}:
        return state, lifecycle_source, "satisfied", "local_done"
    if state == "open":
        return "open", lifecycle_source, "blocking", "descendant_issue_open"
    return "unknown", lifecycle_source, "indeterminate", "descendant_issue_unknown"


def _high_level_lifecycle_for_direct_dependency(
    *,
    target_node_id: str,
    target_issue_ids: tuple[str, ...],
    expansion: str,
    issue_statuses: dict[str, IssueStatusSnapshot],
    high_level_statuses_by_node_id: dict[str, DepsHighLevelStatus] | None,
) -> tuple[str, str, DepsDependencyDisposition, DepsDispositionBasis]:
    high_level_statuses = high_level_statuses_by_node_id or {}
    status = high_level_statuses.get(target_node_id)
    state = _normalize_high_level_state(status.state if status is not None else None)
    lifecycle_source = status.source if status is not None else "none"

    if state == "closed":
        return "closed", lifecycle_source, "satisfied", "lifecycle_closed"
    if state == "done":
        basis: DepsDispositionBasis = (
            "all_descendant_issues_done"
            if target_issue_ids and lifecycle_source == "descendant_aggregate"
            else "local_done"
        )
        return "done", lifecycle_source, "satisfied", basis
    if state == "unknown":
        if expansion == "empty":
            return "unknown", lifecycle_source, "indeterminate", "empty_unknown_container"
        return "unknown", lifecycle_source, "indeterminate", "descendant_issue_unknown"
    if _all_target_issues_satisfied(target_issue_ids, issue_statuses):
        return state, lifecycle_source, "satisfied", "all_descendant_issues_done"
    if target_issue_ids and _any_target_issue_unknown(target_issue_ids, issue_statuses):
        return state, lifecycle_source, "indeterminate", "descendant_issue_unknown"
    if target_issue_ids and _any_target_issue_open(target_issue_ids, issue_statuses):
        return state, lifecycle_source, "blocking", "descendant_issue_open"
    if expansion == "empty" and state == "open":
        return "open", lifecycle_source, "blocking", "empty_open_container"
    if expansion == "empty":
        return "unknown", lifecycle_source, "indeterminate", "empty_unknown_container"
    return state, lifecycle_source, "indeterminate", "descendant_issue_unknown"


def evaluate_direct_node_dependencies(
    graph: SpecGraph,
    *,
    source_node_id: str,
    raw_node_depends_on_map: dict[str, list[str]] | None,
    issue_statuses: dict[str, IssueStatusSnapshot],
    high_level_statuses_by_node_id: dict[str, DepsHighLevelStatus] | None = None,
) -> list[DepsDirectNodeDependency]:
    source_node = graph.nodes_by_id.get(source_node_id)
    if source_node is None:
        raise RuntimeError(f"Node not found: {source_node_id}")
    if source_node.kind == "issue":
        return []

    direct_target_ids = raw_node_depends_on_map.get(source_node_id, []) if raw_node_depends_on_map else []
    direct_dependencies: list[DepsDirectNodeDependency] = []
    for target_node_id in _safe_sorted_node_ids(list(direct_target_ids)):
        target_node = graph.nodes_by_id.get(target_node_id)
        if target_node is None:
            raise RuntimeError(f"Node not found: {target_node_id}")
        target_issue_ids, expansion = _target_issue_ids_and_expansion(graph, target_node_id)
        if target_node.kind == "issue":
            lifecycle_state, lifecycle_source, disposition, basis = _issue_lifecycle_for_direct_dependency(
                issue_id=target_node.id,
                issue_statuses=issue_statuses,
            )
        else:
            lifecycle_state, lifecycle_source, disposition, basis = _high_level_lifecycle_for_direct_dependency(
                target_node_id=target_node.id,
                target_issue_ids=target_issue_ids,
                expansion=expansion,
                issue_statuses=issue_statuses,
                high_level_statuses_by_node_id=high_level_statuses_by_node_id,
            )

        direct_dependencies.append(
            DepsDirectNodeDependency(
                source_node_id=source_node.id,
                source_node_kind=source_node.kind,
                target_node_id=target_node.id,
                target_node_kind=target_node.kind,
                target_issue_ids=target_issue_ids,
                expansion=expansion,  # type: ignore[arg-type]
                lifecycle_state=lifecycle_state,  # type: ignore[arg-type]
                lifecycle_source=lifecycle_source,
                dependency_disposition=disposition,
                disposition_basis=basis,
            )
        )
    return direct_dependencies


def _with_direct_node_dependencies(
    evaluation: DepsEvaluation,
    direct_node_dependencies: list[DepsDirectNodeDependency],
) -> DepsEvaluation:
    if not direct_node_dependencies:
        return evaluation

    direct_contexts = [
        DepsDependencyContext(
            source_node_id=dependency.source_node_id,
            source_issue_id=dependency.source_node_id,
            target_node_id=dependency.target_node_id,
            target_node_kind=dependency.target_node_kind,
            target_issue_ids=dependency.target_issue_ids,
            expansion=dependency.expansion,
            lifecycle_state=dependency.lifecycle_state,
            lifecycle_source=dependency.lifecycle_source,
            dependency_disposition=dependency.dependency_disposition,
            disposition_basis=dependency.disposition_basis,
        )
        for dependency in direct_node_dependencies
    ]
    satisfied_dependencies = [
        *evaluation.satisfied_dependencies,
        *[
            context
            for context in direct_contexts
            if context.dependency_disposition == "satisfied" and context not in evaluation.satisfied_dependencies
        ],
    ]
    dependency_contexts = [
        *evaluation.dependency_contexts,
        *[context for context in direct_contexts if context not in evaluation.dependency_contexts],
    ]

    unresolved = [
        dependency
        for dependency in direct_node_dependencies
        if dependency.dependency_disposition in {"blocking", "indeterminate"}
    ]
    if not unresolved:
        return replace(
            evaluation,
            satisfied_dependencies=satisfied_dependencies,
            dependency_contexts=dependency_contexts,
        )

    direct_blockers = {dependency.target_node_id for dependency in unresolved}
    blockers = _safe_sorted_node_ids(set(evaluation.blockers) | direct_blockers)
    issue_blockers = _safe_sorted_node_ids(
        set(evaluation.issue_blockers)
        | {dependency.target_node_id for dependency in unresolved if dependency.target_node_kind == "issue"}
    )
    node_blockers_by_id = {blocker.node_id: blocker for blocker in evaluation.node_blockers}
    for dependency in unresolved:
        if dependency.target_node_kind == "issue" or dependency.expansion != "empty":
            continue
        reason = "empty_open" if dependency.dependency_disposition == "blocking" else "empty_unknown"
        state = "open" if dependency.dependency_disposition == "blocking" else "unknown"
        node_blockers_by_id[dependency.target_node_id] = DepsNodeBlocker(
            node_id=dependency.target_node_id,
            reason=reason,
            state=state,
            state_source=dependency.lifecycle_source,
            source_issue_id=dependency.source_node_id,
            lifecycle_state=dependency.lifecycle_state,
            lifecycle_source=dependency.lifecycle_source,
            dependency_disposition=dependency.dependency_disposition,
            disposition_basis=dependency.disposition_basis,
        )
    guard_reason = (
        "unknown"
        if evaluation.guard_reason == "unknown"
        or any(dependency.dependency_disposition == "indeterminate" for dependency in unresolved)
        else "blocked"
    )
    return replace(
        evaluation,
        ready=False,
        guard_reason=guard_reason,
        blockers=blockers,
        blockers_top=blockers[:_BLOCKERS_TOP_LIMIT],
        closure=list(blockers),
        issue_blockers=issue_blockers,
        node_blockers=[
            node_blockers_by_id[node_id] for node_id in _safe_sorted_node_ids(list(node_blockers_by_id.keys()))
        ],
        satisfied_dependencies=satisfied_dependencies,
        dependency_contexts=dependency_contexts,
    )


def _evaluate_dependency_contexts(
    *,
    target_issue_ids: list[str],
    issue_statuses: dict[str, IssueStatusSnapshot],
    dependency_contexts_by_issue_id: dict[str, list[DependencyContextInput]] | None,
    high_level_statuses_by_node_id: dict[str, DepsHighLevelStatus] | None,
) -> tuple[
    list[DepsNodeBlocker],
    list[DepsDependencyContext],
    list[DepsDependencyContext],
    dict[str, set[str]],
    dict[str, set[str]],
    dict[str, set[str]],
]:
    if not dependency_contexts_by_issue_id:
        return [], [], [], {}, {}, {}

    high_level_statuses = high_level_statuses_by_node_id or {}
    node_blockers_by_id: dict[str, DepsNodeBlocker] = {}
    satisfied_by_key: dict[tuple[str, str, str], DepsDependencyContext] = {}
    dependency_contexts_by_key: dict[tuple[str, str, str], DepsDependencyContext] = {}
    suppressed_issue_roots_by_issue_id: dict[str, set[str]] = {}
    unresolved_issue_roots_by_issue_id: dict[str, set[str]] = {}
    direct_issue_targets_by_issue_id: dict[str, set[str]] = {}

    for issue_id in target_issue_ids:
        if _issue_is_satisfied(issue_id, issue_statuses):
            continue
        for raw_context in dependency_contexts_by_issue_id.get(issue_id, []):
            context = _dependency_context_from_input(raw_context)
            if context.target_node_kind == "issue":
                direct_issue_targets_by_issue_id.setdefault(issue_id, set()).update(context.target_issue_ids)
                continue

            status = high_level_statuses.get(context.target_node_id)
            state = _normalize_high_level_state(status.state if status is not None else None)
            state_source = status.source if status is not None else "none"
            key = (context.source_issue_id, context.target_node_id, context.expansion)

            if state == "closed":
                suppressed_issue_roots_by_issue_id.setdefault(issue_id, set()).update(context.target_issue_ids)
                evaluated = _with_disposition(
                    context,
                    lifecycle_state=state,
                    lifecycle_source=state_source,
                    dependency_disposition="satisfied",
                    disposition_basis="lifecycle_closed",
                )
                satisfied_by_key[key] = evaluated
                dependency_contexts_by_key[key] = evaluated
                continue

            if state == "done":
                suppressed_issue_roots_by_issue_id.setdefault(issue_id, set()).update(context.target_issue_ids)
                disposition_basis: DepsDispositionBasis = (
                    "all_descendant_issues_done"
                    if context.target_issue_ids and state_source == "descendant_aggregate"
                    else "local_done"
                )
                evaluated = _with_disposition(
                    context,
                    lifecycle_state=state,
                    lifecycle_source=state_source,
                    dependency_disposition="satisfied",
                    disposition_basis=disposition_basis,
                )
                satisfied_by_key[key] = evaluated
                dependency_contexts_by_key[key] = evaluated
                continue

            if state == "unknown":
                unresolved_issue_roots_by_issue_id.setdefault(issue_id, set()).update(context.target_issue_ids)
                if context.expansion != "empty" and not _any_target_issue_unknown(
                    context.target_issue_ids, issue_statuses
                ):
                    node_blockers_by_id[context.target_node_id] = DepsNodeBlocker(
                        node_id=context.target_node_id,
                        reason="lifecycle_unknown",
                        state="unknown",
                        state_source=state_source,
                        source_issue_id=context.source_issue_id,
                        lifecycle_state="unknown",
                        lifecycle_source=state_source,
                        dependency_disposition="indeterminate",
                        disposition_basis="descendant_issue_unknown",
                    )
                    evaluated = _with_disposition(
                        context,
                        lifecycle_state=state,
                        lifecycle_source=state_source,
                        dependency_disposition="indeterminate",
                        disposition_basis="descendant_issue_unknown",
                    )
                    dependency_contexts_by_key[key] = evaluated
                    continue

            if _all_target_issues_satisfied(context.target_issue_ids, issue_statuses):
                evaluated = _with_disposition(
                    context,
                    lifecycle_state=state,
                    lifecycle_source=state_source,
                    dependency_disposition="satisfied",
                    disposition_basis="all_descendant_issues_done",
                )
                satisfied_by_key[key] = evaluated
                dependency_contexts_by_key[key] = evaluated
                continue

            if context.target_issue_ids and _any_target_issue_unknown(context.target_issue_ids, issue_statuses):
                unresolved_issue_roots_by_issue_id.setdefault(issue_id, set()).update(context.target_issue_ids)
                evaluated = _with_disposition(
                    context,
                    lifecycle_state=state,
                    lifecycle_source=state_source,
                    dependency_disposition="indeterminate",
                    disposition_basis="descendant_issue_unknown",
                )
                dependency_contexts_by_key[key] = evaluated
                continue

            if context.target_issue_ids and _any_target_issue_open(context.target_issue_ids, issue_statuses):
                unresolved_issue_roots_by_issue_id.setdefault(issue_id, set()).update(context.target_issue_ids)
                evaluated = _with_disposition(
                    context,
                    lifecycle_state=state,
                    lifecycle_source=state_source,
                    dependency_disposition="blocking",
                    disposition_basis="descendant_issue_open",
                )
                dependency_contexts_by_key[key] = evaluated
                continue

            if context.expansion == "empty":
                if state == "open":
                    evaluated = _with_disposition(
                        context,
                        lifecycle_state="open",
                        lifecycle_source=state_source,
                        dependency_disposition="blocking",
                        disposition_basis="empty_open_container",
                    )
                    node_blockers_by_id[context.target_node_id] = DepsNodeBlocker(
                        node_id=context.target_node_id,
                        reason="empty_open",
                        state="open",
                        state_source=state_source,
                        source_issue_id=context.source_issue_id,
                        lifecycle_state="open",
                        lifecycle_source=state_source,
                        dependency_disposition="blocking",
                        disposition_basis="empty_open_container",
                    )
                    dependency_contexts_by_key[key] = evaluated
                else:
                    evaluated = _with_disposition(
                        context,
                        lifecycle_state="unknown",
                        lifecycle_source=state_source,
                        dependency_disposition="indeterminate",
                        disposition_basis="empty_unknown_container",
                    )
                    node_blockers_by_id[context.target_node_id] = DepsNodeBlocker(
                        node_id=context.target_node_id,
                        reason="empty_unknown",
                        state="unknown",
                        state_source=state_source,
                        source_issue_id=context.source_issue_id,
                        lifecycle_state="unknown",
                        lifecycle_source=state_source,
                        dependency_disposition="indeterminate",
                        disposition_basis="empty_unknown_container",
                    )
                    dependency_contexts_by_key[key] = evaluated

    return (
        [node_blockers_by_id[node_id] for node_id in _safe_sorted_node_ids(list(node_blockers_by_id.keys()))],
        [
            satisfied_by_key[key]
            for key in sorted(
                satisfied_by_key,
                key=lambda item: (deps_node_sort_key(item[0]), deps_node_sort_key(item[1]), item[2]),
            )
        ],
        [
            dependency_contexts_by_key[key]
            for key in sorted(
                dependency_contexts_by_key,
                key=lambda item: (deps_node_sort_key(item[0]), deps_node_sort_key(item[1]), item[2]),
            )
        ],
        suppressed_issue_roots_by_issue_id,
        unresolved_issue_roots_by_issue_id,
        direct_issue_targets_by_issue_id,
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
                cycle = [*path[start_index:], dep_id]
                raise RuntimeError("Dependency cycle detected: " + " -> ".join(cycle))

            if dep_id not in visited:
                stack.append((dep_id, 0))


def _require_graph_node(graph: SpecGraph, node_id: str) -> None:
    if node_id not in graph.nodes_by_id:
        raise RuntimeError(f"Node not found: {node_id}")


def _ancestor_node_ids(graph: SpecGraph, node_id: str) -> set[str]:
    _require_graph_node(graph, node_id)
    ancestors: set[str] = set()
    current_id = graph.nodes_by_id[node_id].parent_id
    while current_id:
        _require_graph_node(graph, current_id)
        if current_id in ancestors:
            raise RuntimeError("Node hierarchy cycle detected: " + current_id)
        ancestors.add(current_id)
        current_id = graph.nodes_by_id[current_id].parent_id
    return ancestors


def _descendant_node_ids(graph: SpecGraph, node_id: str) -> set[str]:
    _require_graph_node(graph, node_id)
    descendants: set[str] = set()
    stack = [child_id for child_id, child in graph.nodes_by_id.items() if child.parent_id == node_id]
    while stack:
        current_id = stack.pop()
        _require_graph_node(graph, current_id)
        if current_id in descendants:
            continue
        descendants.add(current_id)
        stack.extend(child_id for child_id, child in graph.nodes_by_id.items() if child.parent_id == current_id)
    return descendants


def validate_raw_node_dependency_graph(graph: SpecGraph, raw_node_depends_on_map: dict[str, list[str]]) -> None:
    candidate_map: dict[str, list[str]] = {}
    for node_id in _safe_sorted_node_ids(list(graph.nodes_by_id.keys())):
        node = graph.nodes_by_id[node_id]
        candidate_map.setdefault(node_id, [])
        if node.parent_id:
            _require_graph_node(graph, node.parent_id)
            candidate_map.setdefault(node.parent_id, [])
            candidate_map[node.parent_id].append(node_id)

    for source_id in _safe_sorted_node_ids(list(raw_node_depends_on_map.keys())):
        _require_graph_node(graph, source_id)
        candidate_map.setdefault(source_id, [])
        source_ancestors = _ancestor_node_ids(graph, source_id)

        for target_id in _safe_sorted_node_ids(raw_node_depends_on_map.get(source_id, [])):
            _require_graph_node(graph, target_id)
            candidate_map.setdefault(target_id, [])

            if target_id == source_id:
                raise RuntimeError(f"Raw node dependency self edge detected: {source_id}")
            if target_id in source_ancestors:
                raise RuntimeError(f"Raw node dependency targets ancestor/container: {source_id} -> {target_id}")
            if source_id in _ancestor_node_ids(graph, target_id):
                raise RuntimeError(f"Raw node dependency targets descendant: {source_id} -> {target_id}")

            candidate_map[source_id].append(target_id)
            for descendant_id in _safe_sorted_node_ids(_descendant_node_ids(graph, source_id)):
                candidate_map.setdefault(descendant_id, [])
                candidate_map[descendant_id].append(target_id)

    validate_deps_cycles(candidate_map)


def ensure_node_dependency_add_would_be_valid(
    graph: SpecGraph,
    raw_node_depends_on_map: dict[str, list[str]],
    *,
    from_node_id: str,
    to_node_id: str,
    candidate_issue_depends_on_map: dict[str, list[str]] | None = None,
) -> None:
    candidate_raw_map: dict[str, list[str]] = {
        node_id: list(depends_on) for node_id, depends_on in raw_node_depends_on_map.items()
    }
    candidate_raw_map.setdefault(from_node_id, [])
    candidate_raw_map.setdefault(to_node_id, [])
    candidate_raw_map[from_node_id].append(to_node_id)

    validate_raw_node_dependency_graph(graph, candidate_raw_map)

    if candidate_issue_depends_on_map is not None:
        validate_deps_cycles(candidate_issue_depends_on_map)


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
        issue_id: list(depends_on) for issue_id, depends_on in issue_depends_on_map.items()
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
    dependency_contexts_by_issue_id: dict[str, list[DependencyContextInput]] | None = None,
    high_level_statuses_by_node_id: dict[str, DepsHighLevelStatus] | None = None,
) -> DepsEvaluation:
    effective_deps_map = build_effective_deps_map(graph, issue_depends_on_map)
    target_issue_ids = _issue_ids_for_target(graph, target_id)
    reachable_issue_ids = collect_reachable_issue_ids(effective_deps_map, target_issue_ids)
    reachable_depends_on = {issue_id: list(effective_deps_map.get(issue_id, [])) for issue_id in reachable_issue_ids}
    validate_deps_cycles(reachable_depends_on)

    derived_issue_deps = _derive_issue_depends_on_view(reachable_depends_on, issue_statuses)
    return _build_evaluation(
        target_issue_ids=target_issue_ids,
        derived_issue_deps=derived_issue_deps,
        issue_statuses=issue_statuses,
        dependency_contexts_by_issue_id=dependency_contexts_by_issue_id,
        high_level_statuses_by_node_id=high_level_statuses_by_node_id,
    )


def _issue_state_for_inspection(
    *,
    issue_id: str,
    issue_statuses: dict[str, IssueStatusSnapshot],
    ready: bool,
    active_issue_id: str | None,
) -> str:
    status = _issue_status(issue_id, issue_statuses)
    if _issue_status_is_satisfied(status):
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
    dependency_contexts_by_issue_id: dict[str, list[DependencyContextInput]] | None = None,
    high_level_statuses_by_node_id: dict[str, DepsHighLevelStatus] | None = None,
    raw_node_depends_on_map: dict[str, list[str]] | None = None,
) -> TargetDepsInspection:
    effective_deps_map = build_effective_deps_map(graph, issue_depends_on_map)
    target_issue_ids = _issue_ids_for_target(graph, target_id)
    reachable_issue_ids = collect_reachable_issue_ids(effective_deps_map, target_issue_ids)
    reachable_depends_on = {issue_id: list(effective_deps_map.get(issue_id, [])) for issue_id in reachable_issue_ids}
    validate_deps_cycles(reachable_depends_on)

    derived_issue_deps = _derive_issue_depends_on_view(reachable_depends_on, issue_statuses)
    evaluation = _build_evaluation(
        target_issue_ids=target_issue_ids,
        derived_issue_deps=derived_issue_deps,
        issue_statuses=issue_statuses,
        dependency_contexts_by_issue_id=dependency_contexts_by_issue_id,
        high_level_statuses_by_node_id=high_level_statuses_by_node_id,
    )
    direct_node_dependencies = evaluate_direct_node_dependencies(
        graph,
        source_node_id=target_id.value,
        raw_node_depends_on_map=raw_node_depends_on_map,
        issue_statuses=issue_statuses,
        high_level_statuses_by_node_id=high_level_statuses_by_node_id,
    )
    evaluation = _with_direct_node_dependencies(evaluation, direct_node_dependencies)

    node_states: dict[str, DepsNodeState] = {}
    inspect_issue_ids = _safe_sorted_node_ids(set(target_issue_ids) | set(reachable_issue_ids))
    filtered_depends_by_issue = evaluation.debug_context.get("filtered_depends_on_by_issue_id", {})
    for issue_id in inspect_issue_ids:
        issue_view = derived_issue_deps.get(issue_id) or {"ready": False, "depends_on": [], "blockers_top": []}
        if isinstance(filtered_depends_by_issue, dict) and issue_id in filtered_depends_by_issue:
            raw_depends_on = filtered_depends_by_issue.get(issue_id, [])
            depends_on = (
                [dep for dep in raw_depends_on if isinstance(dep, str)] if isinstance(raw_depends_on, list) else []
            )
        else:
            raw_depends_on = issue_view.get("depends_on", [])
            depends_on = (
                [dep for dep in raw_depends_on if isinstance(dep, str)] if isinstance(raw_depends_on, list) else []
            )
        ready = _issue_is_satisfied(issue_id, issue_statuses) or (
            _issue_status(issue_id, issue_statuses) != "unknown" and len(depends_on) == 0
        )
        blockers_top = depends_on[:_BLOCKERS_TOP_LIMIT]
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
        if isinstance(filtered_depends_by_issue, dict) and issue_id in filtered_depends_by_issue:
            raw_depends_on = filtered_depends_by_issue.get(issue_id, [])
        else:
            issue_view = derived_issue_deps.get(issue_id) or {"depends_on": []}
            raw_depends_on = issue_view.get("depends_on", [])
        depends_on = raw_depends_on if isinstance(raw_depends_on, list) else []
        for dep_id in depends_on:
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
        direct_node_dependencies=direct_node_dependencies,
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

    issue_ids = _safe_sorted_node_ids([node_id for node_id, node in graph.nodes_by_id.items() if node.kind == "issue"])
    active_issue_id = _active_leaf_id(active)
    nodes: list[DepsNodeState] = []

    for issue_id in issue_ids:
        status = _issue_status(issue_id, issue_statuses)
        unresolved = [
            dep_id
            for dep_id in _safe_sorted_node_ids(effective_deps_map.get(issue_id, []))
            if not _issue_is_satisfied(dep_id, issue_statuses)
        ]

        if _issue_status_is_satisfied(status):
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
