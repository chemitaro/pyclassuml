from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, cast

from spec_dock_runtime.application.contracts import CheckDepsRequest, DepsCheckResult, TargetRef
from spec_dock_runtime.application.github_issue_targets import (
    collect_repo_scoped_issue_view_targets,
    normalize_repo_slug,
)
from spec_dock_runtime.application.repo_context import resolve_current_repo_slug
from spec_dock_runtime.application.status_context import resolve_issue_status_context
from spec_dock_runtime.domain.deps import inspect_target_deps, validate_deps_cycles, validate_raw_node_dependency_graph
from spec_dock_runtime.domain.ids import format_id, parse_id
from spec_dock_runtime.domain.models import (
    DepsHighLevelStatus,
    IssueSnapshot,
    IssueStatusSnapshot,
    NodeId,
    SpecGraph,
    SpecNodeKind,
    SpecNodeSeed,
)
from spec_dock_runtime.domain.tree import build_graph

if TYPE_CHECKING:
    from spec_dock_runtime.application.ports import Ports
    from spec_dock_runtime.infra.contracts import StoredMetaRecord


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


def _find_existing_id_by_num(graph: SpecGraph, *, prefix: str, num: int, local: bool) -> str | None:
    for node_id in graph.nodes_by_id:
        try:
            parsed_prefix, is_local, parsed_num = parse_id(str(node_id))
        except RuntimeError:
            continue
        if parsed_prefix == prefix and parsed_num == num and is_local == local:
            return str(node_id)
    return None


def _resolve_target_node_id(graph: SpecGraph, target: TargetRef, *, current_repo_slug: str | None = None) -> str:
    if target.kind == "github_issue":
        if target.github_issue_number is None:
            raise RuntimeError("TargetRef.github_issue_number is required")
        matches = [
            node
            for node in graph.nodes_by_id.values()
            if node.github_issue_number == int(target.github_issue_number)
            and node.kind in ("initiative", "epic", "issue")
        ]
        target_repo_slug = normalize_repo_slug(target.github_repo_owner, target.github_repo_name)
        if target_repo_slug is not None:
            allow_current_unscoped = current_repo_slug is not None and target_repo_slug == current_repo_slug
            scoped = [
                node
                for node in matches
                if (
                    normalize_repo_slug(node.github_repo_owner, node.github_repo_name) == target_repo_slug
                    or (
                        allow_current_unscoped
                        and normalize_repo_slug(node.github_repo_owner, node.github_repo_name) is None
                    )
                )
            ]
            if not scoped:
                raise RuntimeError(
                    "No node found for "
                    f"github.issue_number={int(target.github_issue_number)} in repo scope ({target_repo_slug}). "
                    "Create/link the node first."
                )
            if len(scoped) > 1:
                ids = ", ".join(sorted(f"{node.kind}:{node.id}" for node in scoped))
                raise RuntimeError(
                    f"Ambiguous github.issue_number={int(target.github_issue_number)} in repo scope "
                    f"({target_repo_slug}): {ids}"
                )
            return scoped[0].id
        if not matches:
            raise RuntimeError(
                f"No node found for github.issue_number={int(target.github_issue_number)}. Create/link the node first."
            )
        if len(matches) > 1:
            ids = ", ".join(sorted(f"{node.kind}:{node.id}" for node in matches))
            raise RuntimeError(f"Ambiguous github.issue_number={int(target.github_issue_number)}: {ids}")
        return matches[0].id

    if target.kind != "node_id":
        raise RuntimeError(f"Unsupported target kind: {target.kind}")

    if target.node_id is None:
        raise RuntimeError("TargetRef.node_id is required")

    raw_id = str(target.node_id).strip().lower()
    prefix, is_local, num = parse_id(raw_id)
    resolved = _find_existing_id_by_num(graph, prefix=prefix, num=num, local=is_local) or format_id(
        prefix, num, local=is_local
    )
    node = graph.nodes_by_id.get(resolved)
    if node is None or node.kind not in ("initiative", "epic", "issue"):
        raise RuntimeError(f"Node not found: {resolved}")
    return node.id


def _append_unique(warnings: list[str], code: str) -> None:
    if code not in warnings:
        warnings.append(code)


def _load_cached_issue_last_sync_at_by_id(ports: Ports, specdock_dir: Path) -> dict[str, str | None]:
    if ports.derived_state_reader is None:
        return {}
    loader = getattr(ports.derived_state_reader, "load_cached_issue_last_sync_at_by_id", None)
    if not callable(loader):
        return {}
    loaded = loader(specdock_dir)
    if not isinstance(loaded, dict):
        return {}
    out: dict[str, str | None] = {}
    for issue_id, value in loaded.items():
        if not isinstance(issue_id, str):
            continue
        if value is None:
            out[issue_id] = None
            continue
        if isinstance(value, str):
            normalized = value.strip()
            out[issue_id] = normalized or None
    return out


def load_cached_high_level_github_state_by_id(specdock_dir: Path) -> dict[str, str]:
    agent_dir = specdock_dir / ".agent"
    for state_index_path in (agent_dir / "index-all.json", agent_dir / "index.json"):
        if not state_index_path.is_file():
            continue
        try:
            loaded = json.loads(state_index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(loaded, dict):
            continue
        raw_nodes = loaded.get("nodes")
        if not isinstance(raw_nodes, dict):
            continue
        out: dict[str, str] = {}
        for node_id, item in raw_nodes.items():
            if not isinstance(node_id, str) or not isinstance(item, dict):
                continue
            kind = item.get("type") or item.get("kind")
            if kind not in {"initiative", "epic"}:
                continue
            github = item.get("github")
            if not isinstance(github, dict):
                continue
            raw_updated_at = github.get("updated_at")
            if not isinstance(raw_updated_at, str) or not raw_updated_at.strip():
                continue
            raw_state = github.get("state")
            if not isinstance(raw_state, str):
                continue
            normalized = raw_state.strip().lower()
            if normalized in {"open", "closed"}:
                out[node_id] = normalized
        return out
    return {}


def _normalize_issue_status(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"done", "open", "unknown"}:
        return normalized
    return "unknown"


def _status_state_from_snapshot(status: IssueStatusSnapshot) -> tuple[str, str] | None:
    effective_status = _normalize_issue_status(status.effective_status)
    if status.source == "github":
        if effective_status == "done":
            return ("closed", "github")
        if effective_status == "open":
            return ("open", "github")
        return None
    if status.source == "cache" and effective_status in {"done", "open"}:
        return (effective_status, status.source)
    return None


def _descendant_issue_ids(graph: SpecGraph, node_id: str, kind: str) -> list[str]:
    if kind == "initiative":
        return [
            issue_id
            for issue_id, issue_node in graph.nodes_by_id.items()
            if issue_node.kind == "issue" and issue_node.initiative_id == node_id
        ]
    if kind == "epic":
        return [
            issue_id
            for issue_id, issue_node in graph.nodes_by_id.items()
            if issue_node.kind == "issue" and issue_node.epic_id == node_id
        ]
    return []


def _descendant_aggregate_state(
    graph: SpecGraph,
    *,
    node_id: str,
    kind: str,
    issue_statuses: dict[str, IssueStatusSnapshot],
) -> tuple[str, str] | None:
    descendant_issue_ids = _descendant_issue_ids(graph, node_id, kind)
    if not descendant_issue_ids:
        return None
    descendant_statuses = [
        _normalize_issue_status(issue_statuses[issue_id].effective_status)
        for issue_id in descendant_issue_ids
        if issue_id in issue_statuses
    ]
    if len(descendant_statuses) != len(descendant_issue_ids):
        return ("unknown", "descendant_aggregate")
    if descendant_statuses and all(status == "done" for status in descendant_statuses):
        return ("done", "descendant_aggregate")
    if any(status == "open" for status in descendant_statuses):
        return ("open", "descendant_aggregate")
    return ("unknown", "descendant_aggregate")


def resolve_high_level_status_context(
    graph: SpecGraph,
    *,
    issue_statuses: dict[str, IssueStatusSnapshot],
    cached_high_level_github_state_by_id: dict[str, str] | None = None,
) -> dict[str, DepsHighLevelStatus]:
    statuses: dict[str, DepsHighLevelStatus] = {}
    cached_high_level_states = cached_high_level_github_state_by_id or {}
    for node_id, node in graph.nodes_by_id.items():
        if node.kind not in {"initiative", "epic"}:
            continue
        resolved = None
        status = issue_statuses.get(node_id)
        if status is not None and status.source == "github":
            resolved = _status_state_from_snapshot(status)
        if resolved is None:
            cached_state = cached_high_level_states.get(node_id)
            if cached_state in {"open", "closed"}:
                resolved = (cached_state, "cache")
        if resolved is None:
            resolved = _descendant_aggregate_state(
                graph,
                node_id=node_id,
                kind=node.kind,
                issue_statuses=issue_statuses,
            )
        if resolved is None and status is not None and status.source == "local":
            effective_status = _normalize_issue_status(status.effective_status)
            if effective_status in {"done", "open"}:
                resolved = (effective_status, "local")
        state, source = resolved if resolved is not None else ("unknown", "none")
        statuses[node_id] = DepsHighLevelStatus(
            node_id=node_id,
            state=state,  # type: ignore[arg-type]
            source=source,
        )
    return statuses


def _validate_raw_node_dependency_preflight(ports: Ports, specdock_dir: Path, graph: SpecGraph) -> None:
    load_node_resolutions = getattr(ports.deps_topology_reader, "load_node_dependency_resolutions", None)
    if not callable(load_node_resolutions):
        return

    raw_node_depends_on_map = {
        src_id: [resolution.resolved_node_id for resolution in resolutions]
        for src_id, resolutions in load_node_resolutions(specdock_dir, graph).items()
    }
    validate_raw_node_dependency_graph(graph, raw_node_depends_on_map)


def check_deps(req: CheckDepsRequest, ports: Ports) -> DepsCheckResult:
    if ports.deps_topology_reader is None:
        raise RuntimeError("deps_topology_reader is required")

    records = ports.node_reader.load_node_records()
    if not records:
        raise RuntimeError("No nodes found. Create at least one initiative/epic/issue.")
    graph = build_graph([_to_spec_node_seed(record) for record in records])
    current_repo_slug = resolve_current_repo_slug(ports)
    specdock_dir = _resolve_specdock_dir(ports)

    _validate_raw_node_dependency_preflight(ports, specdock_dir, graph)

    topology = ports.deps_topology_reader.load_issue_depends_on_map(specdock_dir, graph)
    warnings: list[str] = list(topology.warnings)
    issue_depends_on_map = dict(topology.issue_depends_on_map)
    raw_node_depends_on_map = dict(topology.raw_node_depends_on_map)
    validate_deps_cycles(issue_depends_on_map)

    issue_snapshots: list[IssueSnapshot] | None = None
    if req.use_github:
        if ports.issue_gateway is None:
            raise RuntimeError("issue_gateway is required when --github is enabled")
        if ports.repo_root is None:
            raise RuntimeError("repo_root is required when --github is enabled")
        issue_snapshots = []
        issue_index_snapshots = []
        try:
            issue_index_snapshots = ports.issue_gateway.issue_index(ports.repo_root, limit=int(req.issue_limit))
        except RuntimeError:
            _append_unique(warnings, "gh_fetch_failed")
        else:
            issue_snapshots.extend(issue_index_snapshots)
            linked_numbers = sorted({
                int(node.github_issue_number)
                for node in graph.nodes_by_id.values()
                if node.kind == "issue"
                and node.github_issue_number is not None
                and normalize_repo_slug(node.github_repo_owner, node.github_repo_name) is None
            })
            indexed = {int(snapshot.issue_number) for snapshot in issue_index_snapshots}
            missing = [n for n in linked_numbers if n not in indexed]
            if missing:
                _append_unique(warnings, "gh_index_incomplete")
        repo_scoped_targets = collect_repo_scoped_issue_view_targets(
            graph,
            issue_index_snapshots=issue_index_snapshots,
            current_repo_slug=current_repo_slug,
        )
        for repo_slug, issue_number in repo_scoped_targets:
            try:
                snapshot = ports.issue_gateway.issue_view_snapshot(
                    ports.repo_root,
                    issue_number,
                    repo_slug=repo_slug,
                )
            except RuntimeError:
                _append_unique(warnings, "gh_fetch_failed")
                continue
            issue_snapshots.append(snapshot)

    cached_issue_status_by_id: dict[str, str] = {}
    cached_issue_last_sync_at_by_id: dict[str, str | None] = {}
    cached_high_level_github_state_by_id: dict[str, str] = {}
    if ports.derived_state_reader is not None:
        cached_issue_status_by_id = ports.derived_state_reader.load_cached_issue_status_by_id(specdock_dir)
        cached_issue_last_sync_at_by_id = _load_cached_issue_last_sync_at_by_id(ports, specdock_dir)
        if not req.use_github:
            cached_high_level_github_state_by_id = load_cached_high_level_github_state_by_id(specdock_dir)

    status_context = resolve_issue_status_context(
        graph,
        github_enabled=req.use_github,
        issue_snapshots=issue_snapshots,
        cached_issue_status_by_id=cached_issue_status_by_id,
        cached_issue_last_sync_at_by_id=cached_issue_last_sync_at_by_id,
        current_repo_slug=current_repo_slug,
    )
    for warning in status_context.warnings:
        _append_unique(warnings, warning)

    target_node_id = _resolve_target_node_id(graph, req.target, current_repo_slug=current_repo_slug)
    active_issue_id = None
    if ports.active_state_store is not None:
        active_issue_id = ports.active_state_store.load_active_issue_id(specdock_dir)

    inspection = inspect_target_deps(
        graph,
        issue_depends_on_map=issue_depends_on_map,
        target_id=NodeId(target_node_id),
        issue_statuses=status_context.issue_statuses,
        dependency_contexts_by_issue_id=topology.dependency_contexts_by_issue_id,
        high_level_statuses_by_node_id=resolve_high_level_status_context(
            graph,
            issue_statuses=status_context.issue_statuses,
            cached_high_level_github_state_by_id=cached_high_level_github_state_by_id,
        ),
        raw_node_depends_on_map=raw_node_depends_on_map,
        active_issue_id=active_issue_id,
    )
    return DepsCheckResult(target=req.target, inspection=inspection, warnings=warnings)
