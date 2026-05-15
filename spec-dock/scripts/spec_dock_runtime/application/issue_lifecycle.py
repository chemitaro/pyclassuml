from __future__ import annotations

from pathlib import Path
from typing import cast

from ..domain.active import infer_active_node_from_branch
from ..domain.ids import format_id, parse_id
from ..domain.models import SpecGraph, SpecNode, SpecNodeKind, SpecNodeSeed
from ..domain.tree import build_graph
from ..infra.contracts import ActiveManifest, StoredMetaRecord
from .close_node import close_node
from .contracts import (
    ClearActiveRequest,
    CloseNodeRequest,
    IssueFinishRequest,
    IssueFinishResult,
    IssueStartRequest,
    IssueStartResult,
    SetActiveRequest,
    TargetRef,
)
from .github_issue_targets import normalize_repo_slug
from .ports import Ports
from .repo_context import resolve_current_repo_slug
from .set_active import clear_active, set_active
from .sync_state import post_mutation_sync


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


def _resolve_specdock_dir(ports: Ports) -> Path:
    if ports.specdock_dir is not None:
        return ports.specdock_dir
    if ports.repo_root is not None:
        return ports.repo_root / "spec-dock"
    raise RuntimeError("specdock_dir is required")


def _build_graph(ports: Ports) -> SpecGraph:
    records = ports.node_reader.load_node_records()
    if not records:
        raise RuntimeError("No nodes found. Create at least one initiative/epic/issue.")
    return build_graph([_to_spec_node_seed(record) for record in records])


def _find_existing_id_by_num(graph: SpecGraph, *, prefix: str, num: int, local: bool) -> str | None:
    for node_id in graph.nodes_by_id.keys():
        try:
            parsed_prefix, is_local, parsed_num = parse_id(str(node_id))
        except RuntimeError:
            continue
        if parsed_prefix == prefix and parsed_num == num and is_local == local:
            return str(node_id)
    return None


def _resolve_target_node(graph: SpecGraph, target: TargetRef, *, current_repo_slug: str | None) -> SpecNode:
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
            matches = [
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
            scope = f" in repo scope ({target_repo_slug})"
        else:
            scope = ""
        if not matches:
            raise RuntimeError(
                f"No node found for github.issue_number={int(target.github_issue_number)}{scope}. Create/link the node first."
            )
        if len(matches) > 1:
            ids = ", ".join(sorted(f"{node.kind}:{node.id}" for node in matches))
            raise RuntimeError(f"Ambiguous github.issue_number={int(target.github_issue_number)}{scope}: {ids}")
        return matches[0]

    if target.kind != "node_id":
        raise RuntimeError(f"Unsupported target kind: {target.kind}")
    if target.node_id is None:
        raise RuntimeError("TargetRef.node_id is required")

    raw_id = str(target.node_id).strip().lower()
    prefix, is_local, num = parse_id(raw_id)
    resolved = _find_existing_id_by_num(graph, prefix=prefix, num=num, local=is_local) or format_id(
        prefix,
        num,
        local=is_local,
    )
    node = graph.nodes_by_id.get(resolved)
    if node is None or node.kind not in ("initiative", "epic", "issue"):
        raise RuntimeError(f"Node not found: {resolved}")
    return node


def _active_issue_id(manifest: ActiveManifest | None) -> str | None:
    if manifest is None or manifest.issue is None:
        return None
    return manifest.issue.id


def _github_state_for_node(node: SpecNode, ports: Ports, *, current_repo_slug: str | None) -> str:
    if node.github_issue_number is None:
        return "UNKNOWN"
    if ports.issue_gateway is None:
        return "UNKNOWN"
    repo_slug = normalize_repo_slug(node.github_repo_owner, node.github_repo_name) or current_repo_slug
    try:
        snapshot = ports.issue_gateway.issue_view_snapshot(
            _resolve_repo_root(ports),
            int(node.github_issue_number),
            repo_slug=repo_slug,
        )
    except RuntimeError:
        return "UNKNOWN"
    state = str(snapshot.state).strip().upper()
    return state or "UNKNOWN"


def _format_issue_target(node: SpecNode) -> str:
    return node.id


def _finish_failure_guidance(*, active_issue_id: str, error: RuntimeError) -> str:
    return "\n".join(
        [
            f"issue finish failed while closing GitHub issue for active issue {active_issue_id}.",
            "Active selection was not cleared.",
            "Recovery:",
            "  spec-dock/scripts/spec-dock active show",
            "  spec-dock/scripts/spec-dock issue finish",
            "  gh issue view <github-issue-number>",
            str(error),
        ]
    )


def _finish_active_clear_failure_guidance(
    *,
    active_issue_id: str,
    github_issue_number: int,
    error: RuntimeError,
) -> str:
    return "\n".join(
        [
            f"issue finish failed after GitHub close/already-closed step for active issue {active_issue_id}.",
            f"GitHub issue #{github_issue_number} may have been closed successfully or may already have been closed.",
            "Active selection was not cleared.",
            "Recovery:",
            "  spec-dock/scripts/spec-dock active show",
            "  spec-dock/scripts/spec-dock issue finish",
            "  spec-dock/scripts/spec-dock active set <issue-id> --checkout",
            "Use manual active recovery if active metadata is stale or points at the wrong issue.",
            "Derived artifacts may remain stale because lifecycle auto-sync was skipped.",
            str(error),
        ]
    )


def issue_start(req: IssueStartRequest, ports: Ports) -> IssueStartResult:
    if ports.active_state_store is None:
        raise RuntimeError("active_state_store is required")
    if ports.git_gateway is None:
        raise RuntimeError("git_gateway is required")

    graph = _build_graph(ports)
    current_repo_slug = resolve_current_repo_slug(ports)
    requested = _resolve_target_node(graph, req.target, current_repo_slug=current_repo_slug)
    if requested.kind != "issue":
        raise RuntimeError(f"issue start only accepts issue nodes: target={requested.id} kind={requested.kind}")

    specdock_dir = _resolve_specdock_dir(ports)
    active_load = ports.active_state_store.load_active_manifest(specdock_dir)
    active_issue_id = _active_issue_id(active_load.manifest)
    current_branch = ports.git_gateway.current_branch_or_none(_resolve_repo_root(ports)) or "(detached)"

    if active_issue_id is not None and active_issue_id != requested.id and not req.force:
        active_node = graph.nodes_by_id.get(active_issue_id)
        branch_node, _reason = infer_active_node_from_branch(
            graph,
            branch=current_branch,
            current_repo_slug=current_repo_slug,
        )
        if active_node is not None and branch_node is not None and branch_node.id == active_issue_id:
            github_state = _github_state_for_node(active_node, ports, current_repo_slug=current_repo_slug)
            if github_state != "CLOSED":
                requested_target = _format_issue_target(requested)
                raise RuntimeError(
                    "\n".join(
                        [
                            "issue start blocked: unfinished active issue branch",
                            f"- current active issue: {active_issue_id}",
                            f"- current branch: {current_branch}",
                            f"- requested issue: {requested.id}",
                            f"- github state: {github_state}",
                            "Next commands:",
                            "  spec-dock/scripts/spec-dock issue finish",
                            f"  spec-dock/scripts/spec-dock issue start {requested_target} -f",
                            f"  spec-dock/scripts/spec-dock active set {requested_target} --checkout",
                        ]
                    )
                )

    checkout = active_issue_id != requested.id
    active_set_result = set_active(
        SetActiveRequest(
            target=req.target,
            force=False,
            checkout=checkout,
            use_github=True,
            issue_limit=req.issue_limit,
        ),
        ports,
    )
    warnings = list(active_set_result.warnings)
    if req.force:
        warnings.insert(0, f"issue start forced=true guard=unfinished_active_issue requested={requested.id}")
    return IssueStartResult(
        target_display=_format_issue_target(requested),
        requested_issue_id=requested.id,
        active_set=active_set_result,
        forced=bool(req.force),
        warnings=warnings,
    )


def issue_finish(req: IssueFinishRequest, ports: Ports) -> IssueFinishResult:
    del req
    if ports.active_state_store is None:
        raise RuntimeError("active_state_store is required")

    specdock_dir = _resolve_specdock_dir(ports)
    active_load = ports.active_state_store.load_active_manifest(specdock_dir)
    active_issue_id = _active_issue_id(active_load.manifest)
    if active_issue_id is None:
        raise RuntimeError(
            "issue finish requires an active issue. Recovery: run issue start <issue> or active set <issue> --checkout."
        )

    try:
        close_result = close_node(
            CloseNodeRequest(
                target=TargetRef(kind="node_id", node_id=active_issue_id, github_issue_number=None),
                run_post_sync=False,
            ),
            ports,
        )
    except RuntimeError as error:
        raise RuntimeError(_finish_failure_guidance(active_issue_id=active_issue_id, error=error)) from error
    try:
        clear_result = clear_active(ClearActiveRequest(), ports)
    except RuntimeError as error:
        raise RuntimeError(
            _finish_active_clear_failure_guidance(
                active_issue_id=active_issue_id,
                github_issue_number=close_result.github_issue_number,
                error=error,
            )
        ) from error
    post_sync = post_mutation_sync(ports)
    warnings = [*active_load.warnings, *close_result.warnings, *clear_result.warnings]
    return IssueFinishResult(
        issue_id=close_result.node_id,
        github_issue_number=close_result.github_issue_number,
        already_closed=close_result.already_closed,
        active_cleared=clear_result.cleared,
        warnings=warnings,
        post_sync=post_sync,
    )
