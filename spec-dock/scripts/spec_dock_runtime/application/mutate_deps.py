from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from spec_dock_runtime.application.contracts import MutateDepsError, MutateDepsRequest, MutateDepsResult
from spec_dock_runtime.application.repo_context import resolve_current_repo_slug
from spec_dock_runtime.application.sync_state import post_mutation_sync, skipped_post_mutation_sync
from spec_dock_runtime.domain.deps import ensure_node_dependency_add_would_be_valid, validate_raw_node_dependency_graph
from spec_dock_runtime.domain.models import SpecNodeKind, SpecNodeSeed
from spec_dock_runtime.domain.tree import build_graph
from spec_dock_runtime.domain.validation import ensure_current_graph_and_deps_valid

if TYPE_CHECKING:
    from spec_dock_runtime.application.ports import Ports
    from spec_dock_runtime.infra.contracts import DirectDependencyResolution, StoredMetaRecord


def _to_spec_node_seed(record: StoredMetaRecord) -> SpecNodeSeed:
    return SpecNodeSeed(
        kind=cast("SpecNodeKind", record.kind),
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


def _preflight_detail(error: RuntimeError) -> str:
    detail = str(error)
    if detail.startswith("preflight validate failed:"):
        return detail
    return f"preflight validate failed: {detail}"


def _load_direct_matching_refs(
    req: MutateDepsRequest,
    *,
    ports: Ports,
    graph,
    from_node_id: str,
    to_node_id: str,
) -> list[object]:
    load_direct_resolutions = getattr(ports.deps_topology_reader, "load_direct_dependency_resolutions", None)
    if not callable(load_direct_resolutions):
        return []

    try:
        resolutions = cast(
            "list[DirectDependencyResolution]",
            load_direct_resolutions(_resolve_specdock_dir(ports), graph, from_node_id),
        )
    except RuntimeError as error:
        _raise_mutation_error(req, code="preflight_validate_failed", detail=_preflight_detail(error))

    return [item.raw_ref for item in resolutions if item.resolved_node_id == to_node_id]


def _load_raw_node_depends_on_map(
    req: MutateDepsRequest,
    *,
    ports: Ports,
    graph,
) -> dict[str, list[str]]:
    load_node_resolutions = getattr(ports.deps_topology_reader, "load_node_dependency_resolutions", None)
    if callable(load_node_resolutions):
        try:
            resolutions_by_source = cast(
                "dict[str, list[DirectDependencyResolution]]",
                load_node_resolutions(_resolve_specdock_dir(ports), graph),
            )
        except RuntimeError as error:
            _raise_mutation_error(req, code="preflight_validate_failed", detail=_preflight_detail(error))
        return {
            source_id: [resolution.resolved_node_id for resolution in resolutions]
            for source_id, resolutions in resolutions_by_source.items()
        }

    load_direct_resolutions = getattr(ports.deps_topology_reader, "load_direct_dependency_resolutions", None)
    if not callable(load_direct_resolutions):
        return {}

    raw_map: dict[str, list[str]] = {}
    for source_id, node in graph.nodes_by_id.items():
        if node.kind not in ("initiative", "epic", "issue"):
            continue
        try:
            resolutions = cast(
                "list[DirectDependencyResolution]",
                load_direct_resolutions(_resolve_specdock_dir(ports), graph, source_id),
            )
        except RuntimeError as error:
            _raise_mutation_error(req, code="preflight_validate_failed", detail=_preflight_detail(error))
        raw_map[source_id] = [resolution.resolved_node_id for resolution in resolutions]
    return raw_map


def _build_candidate_issue_depends_on_map(
    req: MutateDepsRequest,
    *,
    ports: Ports,
    graph,
    issue_depends_on_map: dict[str, list[str]],
    from_node_id: str,
    to_node_id: str,
) -> dict[str, list[str]]:
    build_candidate = getattr(ports.deps_topology_reader, "build_candidate_issue_depends_on_map", None)
    if not callable(build_candidate):
        if graph.nodes_by_id[from_node_id].kind == "issue" and graph.nodes_by_id[to_node_id].kind == "issue":
            candidate_map: dict[str, list[str]] = {
                issue_id: list(depends_on) for issue_id, depends_on in issue_depends_on_map.items()
            }
            candidate_map.setdefault(from_node_id, [])
            candidate_map.setdefault(to_node_id, [])
            candidate_map[from_node_id].append(to_node_id)
            return candidate_map
        return dict(issue_depends_on_map)

    try:
        return cast(
            "dict[str, list[str]]",
            build_candidate(
                graph,
                issue_depends_on_map,
                from_node_id=from_node_id,
                to_node_id=to_node_id,
            ),
        )
    except RuntimeError as error:
        _raise_mutation_error(req, code="invalid_add_cycle", detail=str(error))
        raise


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
        raw_node_depends_on_map = _load_raw_node_depends_on_map(req, ports=ports, graph=graph)
        validate_raw_node_dependency_graph(graph, raw_node_depends_on_map)
        ensure_current_graph_and_deps_valid(
            graph,
            issue_depends_on_map,
            repo_root=ports.repo_root,
            current_repo_slug=resolve_current_repo_slug(ports),
            enforce_github_mandatory_linkage=False,
        )
    except RuntimeError as error:
        _raise_mutation_error(req, code="preflight_validate_failed", detail=_preflight_detail(error))

    from_node = graph.nodes_by_id.get(req.from_id)
    to_node = graph.nodes_by_id.get(req.to_id)
    if req.action == "add":
        if from_node is None:
            _raise_mutation_error(req, code="invalid_add_unresolved", detail=f"Node not found: {req.from_id}")
        if to_node is None:
            _raise_mutation_error(req, code="invalid_add_unresolved", detail=f"Node not found: {req.to_id}")
    else:
        if from_node is None or to_node is None:
            _raise_mutation_error(
                req, code="edge_not_found", detail=f"Dependency edge not found: {req.from_id} -> {req.to_id}"
            )

    assert from_node is not None
    assert to_node is not None
    direct_matching_refs = _load_direct_matching_refs(
        req,
        ports=ports,
        graph=graph,
        from_node_id=from_node.id,
        to_node_id=to_node.id,
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
                post_sync=skipped_post_mutation_sync("unchanged"),
            )

        if from_node.id == to_node.id:
            _raise_mutation_error(
                req,
                code="invalid_add_self_dependency",
                detail=f"Self dependency is not allowed: {from_node.id}",
            )

        try:
            ensure_node_dependency_add_would_be_valid(
                graph,
                raw_node_depends_on_map,
                from_node_id=from_node.id,
                to_node_id=to_node.id,
                candidate_issue_depends_on_map=_build_candidate_issue_depends_on_map(
                    req,
                    ports=ports,
                    graph=graph,
                    issue_depends_on_map=issue_depends_on_map,
                    from_node_id=from_node.id,
                    to_node_id=to_node.id,
                ),
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
        post_sync=post_mutation_sync(ports),
    )
