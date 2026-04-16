from __future__ import annotations

from pathlib import Path
from typing import cast

from ..domain.deps import ensure_issue_dependency_add_would_not_create_cycle, issue_dependency_exists
from ..domain.models import SpecNodeSeed, SpecNodeKind
from ..domain.tree import build_graph
from ..domain.validation import ensure_current_graph_and_deps_valid
from ..infra.contracts import DirectDependencyResolution
from ..infra.contracts import StoredMetaRecord
from .contracts import MutateDepsError, MutateDepsRequest, MutateDepsResult
from .ports import Ports
from .repo_context import resolve_current_repo_slug


def _to_spec_node_seed(record: StoredMetaRecord) -> SpecNodeSeed:
    return SpecNodeSeed(
        kind=cast(SpecNodeKind, record.kind),
        id=record.id,
        title=record.title,
        slug=record.slug,
        path=Path(record.path),
        meta_path=Path(record.meta_path),
        parent_id=record.parent_id,
        initiative_id=record.initiative_id,
        epic_id=record.epic_id,
        github_issue_number=record.github_issue_number,
        github_repo_owner=record.github_repo_owner,
        github_repo_name=record.github_repo_name,
    )


def _resolve_specdock_dir(ports: Ports) -> Path:
    if ports.specdock_dir is not None:
        return ports.specdock_dir
    if ports.repo_root is not None:
        return ports.repo_root / "spec-dock"
    raise RuntimeError("specdock_dir is required")


def _raise_mutation_error(
    req: MutateDepsRequest,
    *,
    code: str,
    detail: str | None = None,
) -> None:
    raise MutateDepsError(
        action=req.action,
        from_id=req.from_id,
        to_id=req.to_id,
        code=code,
        detail=detail,
    )


def _load_direct_matching_refs(
    req: MutateDepsRequest,
    *,
    ports: Ports,
    graph,
    from_issue_id: str,
    to_issue_id: str,
) -> list[object]:
    load_direct_resolutions = getattr(ports.deps_topology_reader, "load_direct_dependency_resolutions", None)
    if not callable(load_direct_resolutions):
        return []

    try:
        resolutions = cast(
            list[DirectDependencyResolution],
            load_direct_resolutions(_resolve_specdock_dir(ports), graph, from_issue_id),
        )
    except RuntimeError as error:
        _raise_mutation_error(req, code="preflight_validate_failed", detail=str(error))

    return [
        item.raw_ref
        for item in resolutions
        if item.resolved_node_id == to_issue_id
    ]


def mutate_deps(req: MutateDepsRequest, ports: Ports) -> MutateDepsResult:
    if req.action not in ("add", "remove"):
        raise RuntimeError(f"Unsupported deps mutation action: {req.action}")
    if ports.node_repo is None:
        raise RuntimeError("node_repo is required")
    if ports.deps_topology_reader is None:
        raise RuntimeError("deps_topology_reader is required")

    try:
        records = ports.node_reader.load_node_records()
        graph = build_graph([_to_spec_node_seed(record) for record in records])
        topology = ports.deps_topology_reader.load_issue_depends_on_map(_resolve_specdock_dir(ports), graph)
        issue_depends_on_map = dict(topology.issue_depends_on_map)
        ensure_current_graph_and_deps_valid(
            graph,
            issue_depends_on_map,
            repo_root=ports.repo_root,
            current_repo_slug=resolve_current_repo_slug(ports),
            enforce_github_mandatory_linkage=False,
        )
    except RuntimeError as error:
        _raise_mutation_error(req, code="preflight_validate_failed", detail=str(error))

    from_node = graph.nodes_by_id.get(req.from_id)
    to_node = graph.nodes_by_id.get(req.to_id)
    if req.action == "add":
        if from_node is None:
            _raise_mutation_error(req, code="invalid_add_unresolved", detail=f"Node not found: {req.from_id}")
        if to_node is None:
            _raise_mutation_error(req, code="invalid_add_unresolved", detail=f"Node not found: {req.to_id}")
    else:
        if from_node is None or to_node is None:
            _raise_mutation_error(req, code="edge_not_found", detail=f"Dependency edge not found: {req.from_id} -> {req.to_id}")

    assert from_node is not None
    assert to_node is not None
    if from_node.kind != "issue":
        _raise_mutation_error(
            req,
            code="unsupported_node_kind",
            detail=f"from node is not issue: {from_node.id} ({from_node.kind})",
        )
    if to_node.kind != "issue":
        _raise_mutation_error(
            req,
            code="unsupported_node_kind",
            detail=f"to node is not issue: {to_node.id} ({to_node.kind})",
        )

    direct_edge_exists = issue_dependency_exists(
        issue_depends_on_map,
        from_issue_id=from_node.id,
        to_issue_id=to_node.id,
    )
    direct_matching_refs: list[object] = []
    load_direct_resolutions = getattr(ports.deps_topology_reader, "load_direct_dependency_resolutions", None)
    if callable(load_direct_resolutions):
        direct_matching_refs = _load_direct_matching_refs(
            req,
            ports=ports,
            graph=graph,
            from_issue_id=from_node.id,
            to_issue_id=to_node.id,
        )
        direct_edge_exists = bool(direct_matching_refs)

    if req.action == "add":
        add_issue_dependency = getattr(ports.node_repo, "add_issue_dependency", None)
        if not callable(add_issue_dependency):
            raise RuntimeError("add_issue_dependency is not configured")

        if direct_edge_exists:
            return MutateDepsResult(
                action=req.action,
                from_id=from_node.id,
                to_id=to_node.id,
                result="unchanged",
                warnings=[],
            )

        if from_node.id == to_node.id:
            _raise_mutation_error(
                req,
                code="invalid_add_self_dependency",
                detail=f"Self dependency is not allowed: {from_node.id}",
            )

        try:
            ensure_issue_dependency_add_would_not_create_cycle(
                issue_depends_on_map,
                from_issue_id=from_node.id,
                to_issue_id=to_node.id,
            )
        except RuntimeError as error:
            _raise_mutation_error(req, code="invalid_add_cycle", detail=str(error))

        try:
            add_issue_dependency(from_node.meta_path, to_node.id)
        except RuntimeError as error:
            _raise_mutation_error(req, code="write_failed", detail=str(error))
    else:
        remove_issue_dependency = getattr(ports.node_repo, "remove_issue_dependency", None)
        if not callable(remove_issue_dependency):
            raise RuntimeError("remove_issue_dependency is not configured")
        if not direct_edge_exists:
            _raise_mutation_error(
                req,
                code="edge_not_found",
                detail=f"Dependency edge not found: {from_node.id} -> {to_node.id}",
            )
        try:
            remove_issue_dependency(from_node.meta_path, to_node.id, matching_refs=direct_matching_refs)
        except RuntimeError as error:
            _raise_mutation_error(req, code="write_failed", detail=str(error))

    return MutateDepsResult(
        action=req.action,
        from_id=from_node.id,
        to_id=to_node.id,
        result="updated",
        warnings=[],
    )
