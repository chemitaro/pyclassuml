from __future__ import annotations

from pathlib import Path
from typing import cast

from ..domain.ids import format_id, parse_id
from ..domain.models import SpecGraph, SpecNodeSeed, SpecNodeKind
from ..domain.tree import build_graph
from ..infra.contracts import StoredMetaRecord
from .contracts import CloseNodeRequest, CloseNodeResult, TargetRef
from .github_issue_targets import normalize_repo_slug
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


def _resolve_repo_root(ports: Ports) -> Path:
    if ports.repo_root is None:
        raise RuntimeError("repo_root is required")
    return ports.repo_root


def _resolve_issue_gateway(ports: Ports):
    if ports.issue_gateway is None:
        raise RuntimeError("issue_gateway is required")
    return ports.issue_gateway


def _find_existing_id_by_num(graph: SpecGraph, *, prefix: str, num: int, local: bool) -> str | None:
    for node_id in graph.nodes_by_id.keys():
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
            if node.github_issue_number == int(target.github_issue_number) and node.kind in ("initiative", "epic", "issue")
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


def close_node(req: CloseNodeRequest, ports: Ports) -> CloseNodeResult:
    issue_gateway = _resolve_issue_gateway(ports)
    repo_root = _resolve_repo_root(ports)

    records = ports.node_reader.load_node_records()
    if not records:
        raise RuntimeError("No nodes found. Create at least one initiative/epic/issue.")
    graph = build_graph([_to_spec_node_seed(record) for record in records])

    current_repo_slug = resolve_current_repo_slug(ports)
    target_id = _resolve_target_node_id(graph, req.target, current_repo_slug=current_repo_slug)
    node = graph.nodes_by_id.get(target_id)
    if node is None:
        raise RuntimeError(f"Node not found: {target_id}")
    if node.github_issue_number is None:
        raise RuntimeError(f"Node is not linked to a GitHub issue: {node.id}")

    issue_number = int(node.github_issue_number)
    repo_slug = normalize_repo_slug(node.github_repo_owner, node.github_repo_name) or current_repo_slug
    snapshot = issue_gateway.issue_view_snapshot(repo_root, issue_number, repo_slug=repo_slug)
    if str(snapshot.state).strip().upper() == "CLOSED":
        return CloseNodeResult(
            node_id=node.id,
            node_kind=node.kind,
            github_issue_number=issue_number,
            issue_snapshot=snapshot,
            already_closed=True,
            warnings=[],
        )

    try:
        closed_snapshot = issue_gateway.issue_close(repo_root, issue_number, repo_slug=repo_slug)
    except RuntimeError as error:
        try:
            post_failure_snapshot = issue_gateway.issue_view_snapshot(repo_root, issue_number, repo_slug=repo_slug)
        except RuntimeError:
            raise error
        if str(post_failure_snapshot.state).strip().upper() == "CLOSED":
            return CloseNodeResult(
                node_id=node.id,
                node_kind=node.kind,
                github_issue_number=issue_number,
                issue_snapshot=post_failure_snapshot,
                already_closed=True,
                warnings=[],
            )
        raise error

    return CloseNodeResult(
        node_id=node.id,
        node_kind=node.kind,
        github_issue_number=issue_number,
        issue_snapshot=closed_snapshot,
        already_closed=False,
        warnings=[],
    )
