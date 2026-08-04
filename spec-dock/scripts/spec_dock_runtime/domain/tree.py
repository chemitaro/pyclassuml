from __future__ import annotations

from spec_dock_runtime.domain.models import ActiveSelection, NodeId, SpecGraph, SpecNode, SpecNodeSeed


def build_graph(seeds: list[SpecNodeSeed]) -> SpecGraph:
    """Build an immutable-friendly graph map from normalized node seeds."""
    nodes_by_id: dict[str, SpecNode] = {}

    for seed in seeds:
        node_id = str(seed.id).strip()
        if node_id in nodes_by_id:
            raise RuntimeError(f"Duplicate id detected: {node_id} ({seed.meta_path})")
        nodes_by_id[node_id] = SpecNode(
            kind=seed.kind,
            id=node_id,
            title=seed.title,
            slug=seed.slug,
            path=seed.path,
            meta_path=seed.meta_path,
            parent_id=seed.parent_id,
            initiative_id=seed.initiative_id,
            epic_id=seed.epic_id,
            github_issue_number=seed.github_issue_number,
            github_repo_owner=seed.github_repo_owner,
            github_repo_name=seed.github_repo_name,
        )

    return SpecGraph(nodes_by_id=nodes_by_id)


def resolve_active_node(graph: SpecGraph, entry_id: str | None, expected_kind: str) -> SpecNode | None:
    if entry_id is None:
        return None
    node = graph.nodes_by_id.get(entry_id)
    if node is None:
        return None
    if node.kind != expected_kind:
        return None
    return node


def resolve_parent_from_active(graph: SpecGraph, child_kind: str, active: ActiveSelection) -> str:
    if child_kind == "issue":
        active_epic = resolve_active_node(graph, active.epic_id, expected_kind="epic")
        if active_epic is not None:
            return active_epic.id

        active_issue = resolve_active_node(graph, active.issue_id, expected_kind="issue")
        if active_issue is not None and active_issue.epic_id:
            issue_epic = resolve_active_node(graph, active_issue.epic_id, expected_kind="epic")
            if issue_epic is not None:
                return issue_epic.id

        raise RuntimeError("Cannot resolve parent epic from active selection. Pass --epic explicitly.")

    if child_kind == "epic":
        active_initiative = resolve_active_node(graph, active.initiative_id, expected_kind="initiative")
        if active_initiative is not None:
            return active_initiative.id

        active_epic = resolve_active_node(graph, active.epic_id, expected_kind="epic")
        if active_epic is not None and active_epic.initiative_id:
            epic_initiative = resolve_active_node(graph, active_epic.initiative_id, expected_kind="initiative")
            if epic_initiative is not None:
                return epic_initiative.id

        active_issue = resolve_active_node(graph, active.issue_id, expected_kind="issue")
        if active_issue is not None and active_issue.initiative_id:
            issue_initiative = resolve_active_node(graph, active_issue.initiative_id, expected_kind="initiative")
            if issue_initiative is not None:
                return issue_initiative.id

        raise RuntimeError("Cannot resolve parent initiative from active selection. Pass --initiative explicitly.")

    raise RuntimeError(f"Internal error: unsupported child type for active fallback: {child_kind}")


def select_active_chain(graph: SpecGraph, target_id: NodeId) -> ActiveSelection:
    node = graph.nodes_by_id.get(target_id.value)
    if node is None:
        raise RuntimeError(f"Node not found: {target_id.value}")

    if node.kind == "initiative":
        return ActiveSelection(initiative_id=node.id, epic_id=None, issue_id=None)

    if node.kind == "epic":
        if not node.initiative_id:
            raise RuntimeError(f"Epic meta missing initiative_id: {node.id}")
        initiative = graph.nodes_by_id.get(node.initiative_id)
        if initiative is None or initiative.kind != "initiative":
            raise RuntimeError(f"Initiative not found: {node.initiative_id}")
        return ActiveSelection(initiative_id=initiative.id, epic_id=node.id, issue_id=None)

    if node.kind == "issue":
        if not node.epic_id or not node.initiative_id:
            raise RuntimeError(f"Issue meta missing epic_id/initiative_id: {node.id}")
        epic = graph.nodes_by_id.get(node.epic_id)
        initiative = graph.nodes_by_id.get(node.initiative_id)
        if epic is None or epic.kind != "epic":
            raise RuntimeError(f"Epic not found: {node.epic_id}")
        if initiative is None or initiative.kind != "initiative":
            raise RuntimeError(f"Initiative not found: {node.initiative_id}")
        return ActiveSelection(initiative_id=initiative.id, epic_id=epic.id, issue_id=node.id)

    raise RuntimeError(f"Unsupported node type for active: {node.kind} ({node.id})")
