from __future__ import annotations

from dataclasses import dataclass
import json
import re
import shutil
from pathlib import Path
from typing import Any, Literal, cast

from ..domain.ids import format_id, parse_id
from ..domain.models import SpecGraph, SpecNode, SpecNodeKind, SpecNodeSeed
from ..domain.tree import build_graph
from ..infra.contracts import ActiveManifest, ActiveStateSnapshot, StoredMetaRecord
from .contracts import (
    ClearActiveRequest,
    DeleteDependencyScrubFailure,
    DeleteTerminalStatus,
    DeleteNodeRequest,
    DeleteNodeResult,
    DeleteRemoteCloseBuckets,
    DeleteValidationReason,
)
from .github_issue_targets import normalize_repo_slug
from .ports import Ports
from .sync_state import post_mutation_sync

_NUM_RE = re.compile(r"^[0-9]+$")
_SCOPED_ISSUE_REF_RE = re.compile(
    r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)#(?P<num>[0-9]+)$"
)
_GITHUB_ISSUE_URL_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)/issues/(?P<num>[0-9]+)(?:[/?#].*)?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _CanonicalRemoteIssue:
    repo_slug: str
    issue_number: int
    identifier: str


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


def _empty_remote_close() -> DeleteRemoteCloseBuckets:
    return DeleteRemoteCloseBuckets(
        closed=[],
        noop_already_closed=[],
        failed=[],
        skipped_not_attempted=[],
    )


def _result(
    *,
    status: str,
    target_id: str | None = None,
    offending_node_ids: list[str] | None = None,
    validation_code: str | None = None,
    validation_message: str | None = None,
) -> DeleteNodeResult:
    reasons: list[DeleteValidationReason] = []
    if validation_code is not None:
        reasons.append(
            DeleteValidationReason(
                node_id=target_id,
                code=validation_code,
                message=validation_message or validation_code,
            )
        )
    return DeleteNodeResult(
        status=cast(DeleteTerminalStatus, status),
        target_id=target_id,
        deleted_node_ids=[],
        remaining_node_ids=[],
        remote_close=_empty_remote_close() if status == "ok" else None,
        offending_node_ids=sorted(offending_node_ids or []),
        validation_reasons=reasons,
        active_restore_result="not_needed" if status == "ok" else None,
        recovery_guidance=[],
        dependency_scrub_failures=[],
        warnings=[],
    )


def _metadata_failure_result(
    *,
    target_id: str | None,
    offending_node_ids: list[str],
    messages_by_node_id: dict[str, str],
) -> DeleteNodeResult:
    sorted_ids = sorted(offending_node_ids)
    return DeleteNodeResult(
        status="metadata_validation_failed",
        target_id=target_id,
        deleted_node_ids=[],
        remaining_node_ids=[],
        remote_close=_empty_remote_close(),
        offending_node_ids=sorted_ids,
        validation_reasons=[
            DeleteValidationReason(
                node_id=node_id,
                code="metadata_validation_failed",
                message=messages_by_node_id.get(node_id, "metadata_validation_failed"),
            )
            for node_id in sorted_ids
        ],
        active_restore_result=None,
        recovery_guidance=[],
        dependency_scrub_failures=[],
        warnings=[],
    )


def _dependency_topology_load_failure_result(
    *,
    target_id: str,
    message: str,
) -> DeleteNodeResult:
    return DeleteNodeResult(
        status="metadata_validation_failed",
        target_id=target_id,
        deleted_node_ids=[],
        remaining_node_ids=[],
        remote_close=_empty_remote_close(),
        offending_node_ids=[],
        validation_reasons=[
            DeleteValidationReason(
                node_id=target_id,
                code="metadata_validation_failed",
                message=message,
            )
        ],
        active_restore_result=None,
        recovery_guidance=[],
        dependency_scrub_failures=[],
        warnings=[],
    )


def _remote_close_failed_result(
    *,
    target_id: str,
    remote_close: DeleteRemoteCloseBuckets,
    warnings: list[str] | None = None,
) -> DeleteNodeResult:
    return DeleteNodeResult(
        status="remote_close_failed",
        target_id=target_id,
        deleted_node_ids=[],
        remaining_node_ids=[],
        remote_close=remote_close,
        offending_node_ids=[],
        validation_reasons=[],
        active_restore_result=None,
        recovery_guidance=[],
        dependency_scrub_failures=[],
        warnings=list(warnings or []),
    )


def _local_delete_partial_failure_result(
    *,
    target_id: str,
    deleted_node_ids: list[str],
    remaining_node_ids: list[str],
    remote_close: DeleteRemoteCloseBuckets,
    active_restore_result: Literal["cleared", "restored", "restore_failed", "not_needed"],
    recovery_guidance: list[str],
    dependency_scrub_failures: list[DeleteDependencyScrubFailure] | None = None,
    warnings: list[str] | None = None,
) -> DeleteNodeResult:
    return DeleteNodeResult(
        status="local_delete_partial_failure",
        target_id=target_id,
        deleted_node_ids=list(deleted_node_ids),
        remaining_node_ids=list(remaining_node_ids),
        remote_close=remote_close,
        offending_node_ids=[],
        validation_reasons=[],
        active_restore_result=active_restore_result,
        recovery_guidance=list(recovery_guidance),
        dependency_scrub_failures=list(dependency_scrub_failures or []),
        warnings=list(warnings or []),
    )


def _build_partial_failure_recovery_guidance(
    *,
    restore_guidance: str,
    target: SpecNode,
    recursive: bool,
    force: bool,
    remaining_node_ids: list[str],
    dependency_scrub_failures: list[DeleteDependencyScrubFailure] | None = None,
) -> list[str]:
    retry_args = ["--id", target.id]
    if recursive:
        retry_args.append("--recursive")
    if force:
        retry_args.append("--force")
    retry_args.append("--yes")
    retry_command = "./spec-dock/scripts/spec-dock delete " + " ".join(retry_args)
    manual_follow_up = (
        f"resolve filesystem errors and rerun `{retry_command}`"
        if remaining_node_ids
        else (
            f"inspect `{target.path.as_posix()}` and surrounding workspace for partial-delete artifacts before continuing"
        )
    )
    guidance = [
        restore_guidance,
        "run `./spec-dock/scripts/spec-dock validate` to verify local tree and active pointers",
        "run `./spec-dock/scripts/spec-dock sync` to refresh derived issue/dependency artifacts with GitHub live state",
    ]
    if dependency_scrub_failures:
        guidance.append(
            "repair surviving initiative/epic/issue .meta.json depends_on references listed in dependency_scrub_failures before continuing"
        )
    guidance.append(manual_follow_up)
    return guidance


def _iter_managed_nodes(graph: SpecGraph) -> list[SpecNode]:
    return [node for node in graph.nodes_by_id.values() if node.kind in ("initiative", "epic", "issue")]


def _is_canonical_managed_node_dir(*, specdock_dir: Path, node_dir: Path, kind: SpecNodeKind) -> bool:
    try:
        relative_parts = node_dir.resolve().relative_to(specdock_dir.resolve()).parts
    except Exception:
        return False
    if kind == "initiative":
        return len(relative_parts) == 2 and relative_parts[0] == "initiatives"
    if kind == "epic":
        return (
            len(relative_parts) == 4
            and relative_parts[0] == "initiatives"
            and relative_parts[2] == "epics"
        )
    return (
        len(relative_parts) == 6
        and relative_parts[0] == "initiatives"
        and relative_parts[2] == "epics"
        and relative_parts[4] == "issues"
    )


def _node_kind_from_prefix(prefix: str) -> SpecNodeKind | None:
    mapping: dict[str, SpecNodeKind] = {
        "init": "initiative",
        "epic": "epic",
        "iss": "issue",
    }
    return mapping.get(prefix)


def _matching_target_directories(specdock_dir: Path, *, canonical_id: str, kind: SpecNodeKind) -> list[Path]:
    initiatives_root = specdock_dir / "initiatives"
    if not initiatives_root.exists():
        return []
    matches: list[Path] = []
    expected_prefix = f"{canonical_id}-"
    for path in initiatives_root.rglob("*"):
        if not path.is_dir():
            continue
        name = path.name.lower()
        if name != canonical_id and not name.startswith(expected_prefix):
            continue
        if not _is_canonical_managed_node_dir(specdock_dir=specdock_dir, node_dir=path, kind=kind):
            continue
        matches.append(path)
    return sorted(matches)


def _target_node_dir_from_error_message(
    *,
    message: str,
    specdock_dir: Path,
    canonical_id: str,
    kind: SpecNodeKind,
) -> Path | None:
    specdock_root = specdock_dir.resolve()
    for raw_meta_path in re.findall(r"/[^\n]*?\.meta\.json", message):
        meta_path = Path(raw_meta_path)
        try:
            node_dir = meta_path.parent.resolve()
            node_dir.relative_to(specdock_root)
        except Exception:
            continue
        name = node_dir.name.lower()
        expected_prefix = f"{canonical_id}-"
        if name != canonical_id and not name.startswith(expected_prefix):
            continue
        if not _is_canonical_managed_node_dir(specdock_dir=specdock_dir, node_dir=node_dir, kind=kind):
            continue
        return node_dir
    return None


def _target_local_metadata_failure_result(
    req: DeleteNodeRequest,
    ports: Ports,
    error: RuntimeError | None = None,
) -> DeleteNodeResult | None:
    raw_selector = str(req.node_id or req.positional_target or "").strip()
    if not raw_selector:
        return None
    try:
        prefix, is_local, num = parse_id(raw_selector.lower())
    except RuntimeError:
        return None
    kind = _node_kind_from_prefix(prefix)
    if kind is None:
        return None
    canonical_id = format_id(prefix, num, local=is_local)
    specdock_dir = _resolve_specdock_dir(ports)
    node_dir = None
    if error is not None:
        node_dir = _target_node_dir_from_error_message(
            message=str(error),
            specdock_dir=specdock_dir,
            canonical_id=canonical_id,
            kind=kind,
        )
    if node_dir is None:
        matches = _matching_target_directories(
            specdock_dir,
            canonical_id=canonical_id,
            kind=kind,
        )
        if len(matches) != 1:
            return None
        node_dir = matches[0]
    meta_path = node_dir / ".meta.json"
    try:
        loaded = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        message = f"Invalid JSON: {meta_path}: {exc}"
    except UnicodeDecodeError as exc:
        message = f"Failed to read: {meta_path}: {exc}"
    except OSError as exc:
        message = f"Failed to read: {meta_path}: {exc}"
    else:
        if isinstance(loaded, dict):
            return None
        message = f"Invalid .meta.json (expected object): {meta_path}"
    return _metadata_failure_result(
        target_id=canonical_id,
        offending_node_ids=[canonical_id],
        messages_by_node_id={canonical_id: message},
    )


def _normalize_issue_number(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str):
        raw = value.strip()
        if not raw or _NUM_RE.fullmatch(raw) is None:
            return None
        normalized = int(raw)
        return normalized if normalized > 0 else None
    return None


def _validate_node_metadata(
    node: SpecNode,
    *,
    require_meta_file: bool = True,
) -> tuple[_CanonicalRemoteIssue | None, str | None]:
    if require_meta_file and not node.meta_path.exists():
        return None, f"missing metadata file: {node.meta_path.as_posix()}"

    owner = node.github_repo_owner
    repo = node.github_repo_name
    issue_number_raw = node.github_issue_number
    has_owner = owner is not None
    has_repo = repo is not None
    has_issue = issue_number_raw is not None
    present_count = int(has_owner) + int(has_repo) + int(has_issue)
    if present_count == 0:
        return None, None
    if present_count != 3:
        return None, "partial github linkage is invalid"
    if not isinstance(owner, str) or not isinstance(repo, str):
        return None, "github repo scope must be string values"
    repo_slug = normalize_repo_slug(owner, repo)
    if repo_slug is None:
        return None, "github repo scope must be non-empty strings"
    issue_number = _normalize_issue_number(issue_number_raw)
    if issue_number is None:
        return None, "github issue number must be a positive integer"
    return _CanonicalRemoteIssue(
        repo_slug=repo_slug,
        issue_number=issue_number,
        identifier=f"{repo_slug}#{issue_number}",
    ), None


def _resolve_node_id_matches(graph: SpecGraph, raw_input: str) -> tuple[str | None, DeleteNodeResult | None]:
    raw = str(raw_input).strip().lower()
    if not raw:
        return None, _result(
            status="invalid_selector_syntax",
            validation_code="invalid_selector_syntax",
            validation_message="node id selector is required",
        )
    try:
        prefix, is_local, num = parse_id(raw)
    except RuntimeError:
        return None, _result(
            status="invalid_selector_syntax",
            validation_code="invalid_selector_syntax",
            validation_message=f"invalid node id selector: {raw_input}",
        )
    if prefix not in ("init", "epic", "iss"):
        return None, _result(
            status="invalid_selector_syntax",
            validation_code="invalid_selector_syntax",
            validation_message=f"unsupported node id prefix: {prefix}",
        )

    canonical = format_id(prefix, num, local=is_local)
    matches: list[SpecNode] = []
    for node in _iter_managed_nodes(graph):
        try:
            node_prefix, node_local, node_num = parse_id(node.id)
        except RuntimeError:
            # Ignore malformed unrelated ids during selector resolution.
            continue
        if node_prefix == prefix and node_local == is_local and node_num == num:
            matches.append(node)

    if not matches:
        return None, _result(
            status="target_not_found",
            validation_code="target_not_found",
            validation_message=f"target not found: {canonical}",
        )
    invalid_messages: dict[str, str] = {}
    for node in matches:
        _canonical_remote, validation_error = _validate_node_metadata(
            node,
            require_meta_file=node.path.exists(),
        )
        if validation_error is not None:
            invalid_messages[node.id] = validation_error
    if invalid_messages:
        sorted_invalid_ids = sorted(invalid_messages)
        resolved_target_id = sorted_invalid_ids[0] if len(sorted_invalid_ids) == 1 else None
        return None, _metadata_failure_result(
            target_id=resolved_target_id,
            offending_node_ids=sorted_invalid_ids,
            messages_by_node_id=invalid_messages,
        )

    if len(matches) > 1:
        return None, _result(
            status="ambiguous_target",
            offending_node_ids=[node.id for node in matches],
            validation_code="ambiguous_target",
            validation_message=f"ambiguous selector: {canonical}",
        )
    return matches[0].id, None


def _resolve_github_issue_matches(graph: SpecGraph, raw_input: str) -> tuple[str | None, DeleteNodeResult | None]:
    raw = str(raw_input).strip()
    if not raw or _NUM_RE.fullmatch(raw) is None:
        return None, _result(
            status="invalid_selector_syntax",
            validation_code="invalid_selector_syntax",
            validation_message=f"invalid --github-issue value: {raw_input}",
        )
    issue_number = int(raw)
    if issue_number <= 0:
        return None, _result(
            status="invalid_selector_syntax",
            validation_code="invalid_selector_syntax",
            validation_message=f"--github-issue must be a positive integer: {raw_input}",
        )
    matches: list[SpecNode] = []
    for node in _iter_managed_nodes(graph):
        normalized_issue_number = _normalize_issue_number(node.github_issue_number)
        if normalized_issue_number == issue_number:
            matches.append(node)
    if not matches:
        return None, _result(
            status="target_not_found",
            validation_code="target_not_found",
            validation_message=f"no node linked to github issue: {issue_number}",
        )
    invalid_messages: dict[str, str] = {}
    for node in matches:
        _canonical_remote, validation_error = _validate_node_metadata(
            node,
            require_meta_file=node.path.exists(),
        )
        if validation_error is not None:
            invalid_messages[node.id] = validation_error
    if invalid_messages:
        sorted_invalid_ids = sorted(invalid_messages)
        resolved_target_id = sorted_invalid_ids[0] if len(sorted_invalid_ids) == 1 else None
        return None, _metadata_failure_result(
            target_id=resolved_target_id,
            offending_node_ids=sorted_invalid_ids,
            messages_by_node_id=invalid_messages,
        )

    if len(matches) > 1:
        return None, _result(
            status="ambiguous_target",
            offending_node_ids=[node.id for node in matches],
            validation_code="ambiguous_target",
            validation_message=f"ambiguous github issue selector: {issue_number}",
        )
    return matches[0].id, None


def _resolve_target_id(req: DeleteNodeRequest, graph: SpecGraph) -> tuple[str | None, DeleteNodeResult | None]:
    selectors = 0
    has_positional = bool(str(req.positional_target or "").strip())
    has_node_id = bool(str(req.node_id or "").strip())
    has_github_issue = req.github_issue is not None and str(req.github_issue).strip() != ""
    selectors += 1 if has_positional else 0
    selectors += 1 if has_node_id else 0
    selectors += 1 if has_github_issue else 0

    if selectors == 0:
        return None, _result(
            status="invalid_selector_combination",
            validation_code="invalid_selector_combination",
            validation_message="target selector is required",
        )
    if selectors > 1:
        return None, _result(
            status="invalid_selector_combination",
            validation_code="invalid_selector_combination",
            validation_message="choose exactly one of <target>, --id, --github-issue",
        )

    if has_github_issue:
        return _resolve_github_issue_matches(graph, str(req.github_issue))
    if has_node_id:
        return _resolve_node_id_matches(graph, str(req.node_id))
    return _resolve_node_id_matches(graph, str(req.positional_target))


def _subtree_ids(target: SpecNode, graph: SpecGraph) -> set[str]:
    ids = {target.id}
    if target.kind == "initiative":
        for node in graph.nodes_by_id.values():
            if node.initiative_id == target.id:
                ids.add(node.id)
    elif target.kind == "epic":
        for node in graph.nodes_by_id.values():
            if node.epic_id == target.id:
                ids.add(node.id)
    return ids


def _subtree_issue_ids(target: SpecNode, graph: SpecGraph) -> set[str]:
    return set(_issue_ids_for_scope_node(node=target, graph=graph))


def _issue_ids_for_scope_node(*, node: SpecNode, graph: SpecGraph) -> list[str]:
    if node.kind == "issue":
        return [node.id]
    if node.kind == "epic":
        return sorted(
            [item.id for item in graph.nodes_by_id.values() if item.kind == "issue" and item.epic_id == node.id]
        )
    if node.kind == "initiative":
        return sorted(
            [item.id for item in graph.nodes_by_id.values() if item.kind == "issue" and item.initiative_id == node.id]
        )
    return []


def _collect_boundary_dependency_edges(
    *,
    dep_map: dict[str, list[str]],
    subtree_ids: set[str],
    subtree_issue_ids: set[str],
    graph: SpecGraph,
) -> tuple[set[str], dict[str, set[str]]]:
    conflict_node_ids: set[str] = set()
    surviving_issue_to_deleted_issue_ids: dict[str, set[str]] = {}

    for issue_id in sorted(subtree_issue_ids):
        for dep_id in sorted(dep_map.get(issue_id, [])):
            if dep_id in subtree_issue_ids:
                continue
            conflict_node_ids.add(issue_id)
            conflict_node_ids.add(dep_id)

    for issue_id, deps in dep_map.items():
        if issue_id in subtree_issue_ids:
            continue
        for dep_id in deps:
            if dep_id not in subtree_issue_ids:
                continue
            conflict_node_ids.add(issue_id)
            conflict_node_ids.add(dep_id)
            surviving_issue_to_deleted_issue_ids.setdefault(issue_id, set()).add(dep_id)

    surviving_node_to_deleted_issue_ids: dict[str, set[str]] = {}
    for node in _iter_managed_nodes(graph):
        if node.id in subtree_ids:
            continue
        issue_ids = _issue_ids_for_scope_node(node=node, graph=graph)
        if not issue_ids:
            continue
        edge_target_ids: set[str] = set()
        for issue_id in issue_ids:
            edge_target_ids.update(surviving_issue_to_deleted_issue_ids.get(issue_id, set()))
        if edge_target_ids:
            surviving_node_to_deleted_issue_ids[node.id] = edge_target_ids

    return conflict_node_ids, surviving_node_to_deleted_issue_ids


def _active_ids(manifest: ActiveManifest | None) -> set[str]:
    if manifest is None:
        return set()
    out: set[str] = set()
    if manifest.initiative is not None:
        out.add(manifest.initiative.id)
    if manifest.epic is not None:
        out.add(manifest.epic.id)
    if manifest.issue is not None:
        out.add(manifest.issue.id)
    return out


def _subtree_remote_close_targets(
    *,
    subtree_ids: set[str],
    graph: SpecGraph,
) -> tuple[list[_CanonicalRemoteIssue] | None, DeleteNodeResult | None]:
    invalid_messages: dict[str, str] = {}
    canonical_targets: dict[tuple[str, int], _CanonicalRemoteIssue] = {}
    for node_id in sorted(subtree_ids):
        node = graph.nodes_by_id.get(node_id)
        if node is None:
            continue
        canonical_remote, validation_error = _validate_node_metadata(node)
        if validation_error is not None:
            invalid_messages[node.id] = validation_error
            continue
        if canonical_remote is None:
            continue
        canonical_targets[(canonical_remote.repo_slug, canonical_remote.issue_number)] = canonical_remote
    if invalid_messages:
        return None, _metadata_failure_result(
            target_id=None,
            offending_node_ids=sorted(invalid_messages),
            messages_by_node_id=invalid_messages,
        )
    ordered_keys = sorted(canonical_targets.keys(), key=lambda item: (item[0], item[1]))
    ordered_targets = [canonical_targets[key] for key in ordered_keys]
    return ordered_targets, None


def _close_remote_issues_barrier(
    *,
    target_id: str,
    required_targets: list[_CanonicalRemoteIssue],
    ports: Ports,
    active_snapshot: ActiveStateSnapshot | None,
) -> tuple[DeleteRemoteCloseBuckets, DeleteNodeResult | None]:
    remote_close = _empty_remote_close()
    if not required_targets:
        return remote_close, None

    if ports.issue_gateway is None or ports.repo_root is None:
        first = required_targets[0].identifier
        remote_close.failed.append(first)
        remote_close.skipped_not_attempted.extend([item.identifier for item in required_targets[1:]])
        return remote_close, _remote_close_failed_result(
            target_id=target_id,
            remote_close=remote_close,
            warnings=["issue_gateway_unavailable_for_delete"],
        )

    for index, target in enumerate(required_targets):
        try:
            current = ports.issue_gateway.issue_view_snapshot(
                ports.repo_root,
                target.issue_number,
                repo_slug=target.repo_slug,
            )
        except RuntimeError:
            remote_close.failed.append(target.identifier)
            remote_close.skipped_not_attempted.extend([item.identifier for item in required_targets[index + 1 :]])
            warnings: list[str] = []
            if ports.active_state_store is not None and active_snapshot is not None:
                try:
                    ports.active_state_store.restore_previous_state(_resolve_specdock_dir(ports), active_snapshot)
                except Exception:
                    warnings.append("active_restore_failed")
            return remote_close, _remote_close_failed_result(
                target_id=target_id,
                remote_close=remote_close,
                warnings=warnings,
            )

        if str(current.state).strip().upper() == "CLOSED":
            remote_close.noop_already_closed.append(target.identifier)
            continue

        try:
            closed = ports.issue_gateway.issue_close(
                ports.repo_root,
                target.issue_number,
                repo_slug=target.repo_slug,
            )
        except RuntimeError:
            remote_close.failed.append(target.identifier)
            remote_close.skipped_not_attempted.extend([item.identifier for item in required_targets[index + 1 :]])
            warnings = []
            if ports.active_state_store is not None and active_snapshot is not None:
                try:
                    ports.active_state_store.restore_previous_state(_resolve_specdock_dir(ports), active_snapshot)
                except Exception:
                    warnings.append("active_restore_failed")
            return remote_close, _remote_close_failed_result(
                target_id=target_id,
                remote_close=remote_close,
                warnings=warnings,
            )

        if str(closed.state).strip().upper() == "CLOSED":
            remote_close.closed.append(target.identifier)
            continue
        remote_close.failed.append(target.identifier)
        remote_close.skipped_not_attempted.extend([item.identifier for item in required_targets[index + 1 :]])
        warnings = []
        if ports.active_state_store is not None and active_snapshot is not None:
            try:
                ports.active_state_store.restore_previous_state(_resolve_specdock_dir(ports), active_snapshot)
            except Exception:
                warnings.append("active_restore_failed")
        return remote_close, _remote_close_failed_result(
            target_id=target_id,
            remote_close=remote_close,
            warnings=warnings,
        )
    return remote_close, None


def _delete_local_node_directory(*, node: SpecNode, ports: Ports) -> None:
    if ports.node_repo is not None:
        delete_tree = getattr(ports.node_repo, "delete_tree", None)
        if callable(delete_tree):
            delete_tree(node.path)
            return
    if node.path.exists():
        shutil.rmtree(node.path)


def _subtree_delete_order(*, subtree_ids: set[str], graph: SpecGraph) -> list[SpecNode]:
    ordered_nodes = [graph.nodes_by_id[node_id] for node_id in sorted(subtree_ids) if node_id in graph.nodes_by_id]
    depth_cache: dict[str, int] = {}

    def _depth(node_id: str) -> int:
        if node_id in depth_cache:
            return depth_cache[node_id]
        node = graph.nodes_by_id.get(node_id)
        if node is None or node.parent_id is None or node.parent_id not in subtree_ids:
            depth_cache[node_id] = 0
            return 0
        depth_cache[node_id] = _depth(node.parent_id) + 1
        return depth_cache[node_id]

    ordered_nodes.sort(key=lambda node: (-_depth(node.id), node.id))
    return ordered_nodes


def _delete_subtree_locally(
    *,
    ordered_nodes: list[SpecNode],
    ports: Ports,
) -> tuple[list[str], list[str], bool]:
    deleted_node_ids: list[str] = []
    deleted_set: set[str] = set()

    for node in ordered_nodes:
        try:
            _delete_local_node_directory(node=node, ports=ports)
            deleted_node_ids.append(node.id)
            deleted_set.add(node.id)
        except Exception:
            if not node.path.exists() and node.id not in deleted_set:
                deleted_node_ids.append(node.id)
                deleted_set.add(node.id)
            remaining_node_ids = sorted(node_id for node_id in (item.id for item in ordered_nodes) if node_id not in deleted_set)
            return deleted_node_ids, remaining_node_ids, False

    return deleted_node_ids, [], True


def _load_meta_payload(path: Path, *, ports: Ports) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"Missing .meta.json: {path}")
    if ports.json_store is not None:
        payload = ports.json_store.load_json(path)
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Invalid .meta.json schema: {path}: expected object")
    depends_on = payload.get("depends_on")
    if depends_on is None:
        depends_on = []
    if not isinstance(depends_on, list):
        raise RuntimeError(f"Invalid .meta.json schema: {path}: depends_on must be a list")
    payload["depends_on"] = depends_on
    return payload


def _write_meta_payload(path: Path, payload: dict[str, Any], *, ports: Ports) -> None:
    if ports.json_store is not None:
        ports.json_store.write_json(path, payload)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _ref_matches_deleted_node(
    *,
    ref: object,
    deleted_node_ids_lower: set[str],
    deleted_issue_number_to_node_ids: dict[int, set[str]],
    deleted_scoped_refs: set[tuple[str, int]],
) -> bool:
    if isinstance(ref, str):
        raw = ref.strip()
        lowered = raw.lower()
        if lowered in deleted_node_ids_lower:
            return True
        if raw.isdigit():
            number = int(raw)
            return len(deleted_issue_number_to_node_ids.get(number, set())) == 1
        scoped_match = _SCOPED_ISSUE_REF_RE.fullmatch(raw)
        if scoped_match is not None:
            scoped_slug = normalize_repo_slug(scoped_match.group("owner"), scoped_match.group("repo"))
            if scoped_slug is None:
                return False
            return (scoped_slug, int(scoped_match.group("num"))) in deleted_scoped_refs
        url_match = _GITHUB_ISSUE_URL_RE.fullmatch(raw)
        if url_match is not None:
            scoped_slug = normalize_repo_slug(url_match.group("owner"), url_match.group("repo"))
            if scoped_slug is None:
                return False
            return (scoped_slug, int(url_match.group("num"))) in deleted_scoped_refs
        return False

    if isinstance(ref, bool):
        return False
    if isinstance(ref, int):
        return len(deleted_issue_number_to_node_ids.get(ref, set())) == 1
    return False


def _build_deleted_ref_match_context(
    *,
    deleted_node_ids: set[str],
    graph: SpecGraph,
) -> tuple[set[str], dict[str, tuple[int, str | None]]]:
    deleted_node_ids_lower: set[str] = set()
    issue_refs_by_node_id: dict[str, tuple[int, str | None]] = {}
    for node_id in sorted(deleted_node_ids):
        node = graph.nodes_by_id.get(node_id)
        if node is None:
            continue
        deleted_node_ids_lower.add(node.id.lower())
        issue_number = _normalize_issue_number(node.github_issue_number)
        if issue_number is None:
            continue
        repo_slug = normalize_repo_slug(node.github_repo_owner, node.github_repo_name)
        issue_refs_by_node_id[node.id] = (issue_number, repo_slug)
    return deleted_node_ids_lower, issue_refs_by_node_id


def _build_survivor_ref_match_context(
    *,
    edge_target_ids: set[str],
    issue_refs_by_node_id: dict[str, tuple[int, str | None]],
) -> tuple[dict[int, set[str]], set[tuple[str, int]]]:
    issue_number_to_node_ids: dict[int, set[str]] = {}
    scoped_refs: set[tuple[str, int]] = set()
    for edge_target_id in sorted(edge_target_ids):
        issue_ref = issue_refs_by_node_id.get(edge_target_id)
        if issue_ref is None:
            continue
        issue_number, repo_slug = issue_ref
        issue_number_to_node_ids.setdefault(issue_number, set()).add(edge_target_id)
        if repo_slug is not None:
            scoped_refs.add((repo_slug, issue_number))
    return issue_number_to_node_ids, scoped_refs


def _scrub_surviving_dependency_refs(
    *,
    surviving_node_to_deleted_issue_ids: dict[str, set[str]],
    deleted_subtree_node_ids: set[str],
    graph: SpecGraph,
    ports: Ports,
) -> list[DeleteDependencyScrubFailure]:
    failures: list[DeleteDependencyScrubFailure] = []
    deleted_node_ids_lower, deleted_issue_refs_by_node_id = _build_deleted_ref_match_context(
        deleted_node_ids=deleted_subtree_node_ids,
        graph=graph,
    )

    for survivor_id in sorted(surviving_node_to_deleted_issue_ids):
        edge_target_ids = set(surviving_node_to_deleted_issue_ids[survivor_id])
        deleted_issue_number_to_node_ids, deleted_scoped_refs = _build_survivor_ref_match_context(
            edge_target_ids=edge_target_ids,
            issue_refs_by_node_id=deleted_issue_refs_by_node_id,
        )
        sorted_edge_target_ids = sorted(edge_target_ids)
        survivor = graph.nodes_by_id.get(survivor_id)
        if survivor is None:
            failures.extend(
                DeleteDependencyScrubFailure(node_id=survivor_id, edge_target_id=edge_target_id)
                for edge_target_id in sorted_edge_target_ids
            )
            continue
        meta_path = survivor.path / ".meta.json"
        try:
            payload = _load_meta_payload(meta_path, ports=ports)
            depends_on = cast(list[object], payload["depends_on"])
            filtered_depends_on = [
                ref
                for ref in depends_on
                if not _ref_matches_deleted_node(
                    ref=ref,
                    deleted_node_ids_lower=deleted_node_ids_lower,
                    deleted_issue_number_to_node_ids=deleted_issue_number_to_node_ids,
                    deleted_scoped_refs=deleted_scoped_refs,
                )
            ]
            if len(filtered_depends_on) != len(depends_on):
                refs_to_remove = [
                    ref
                    for ref in depends_on
                    if _ref_matches_deleted_node(
                        ref=ref,
                        deleted_node_ids_lower=deleted_node_ids_lower,
                        deleted_issue_number_to_node_ids=deleted_issue_number_to_node_ids,
                        deleted_scoped_refs=deleted_scoped_refs,
                    )
                ]
                remove_issue_dependency = (
                    getattr(ports.node_repo, "remove_issue_dependency", None) if ports.node_repo is not None else None
                )
                if ports.node_repo is not None and not callable(remove_issue_dependency):
                    raise RuntimeError("remove_issue_dependency is not configured")
                if callable(remove_issue_dependency):
                    anchor_target_id = sorted_edge_target_ids[0] if sorted_edge_target_ids else ""
                    remove_issue_dependency(meta_path, anchor_target_id, matching_refs=refs_to_remove)
                else:
                    payload["depends_on"] = filtered_depends_on
                    _write_meta_payload(meta_path, payload, ports=ports)
        except Exception:
            failures.extend(
                DeleteDependencyScrubFailure(node_id=survivor_id, edge_target_id=edge_target_id)
                for edge_target_id in sorted_edge_target_ids
            )

    failures.sort(key=lambda item: (item.node_id, item.edge_target_id))
    return failures


def _drop_deleted_nodes_from_manifest(
    manifest: ActiveManifest | None,
    *,
    deleted_node_ids: set[str],
) -> ActiveManifest | None:
    if manifest is None:
        return None

    def _filter_entry(entry):
        if entry is None:
            return None
        if entry.id in deleted_node_ids:
            return None
        return entry

    return ActiveManifest(
        initiative=_filter_entry(manifest.initiative),
        epic=_filter_entry(manifest.epic),
        issue=_filter_entry(manifest.issue),
    )


def _manifest_has_entries(manifest: ActiveManifest | None) -> bool:
    return bool(
        manifest is not None
        and (manifest.initiative is not None or manifest.epic is not None or manifest.issue is not None)
    )


def _repair_active_after_clear_failure(
    *,
    ports: Ports,
    active_snapshot: ActiveStateSnapshot | None,
    deleted_node_ids: set[str],
) -> tuple[Literal["cleared", "restored", "restore_failed"], list[str], str]:
    warnings = ["active_clear_failed"]
    if active_snapshot is None:
        warnings.append("active_restore_failed")
        return (
            "restore_failed",
            warnings,
            "active repair failed after local delete; rerun `./spec-dock/scripts/spec-dock active clear`",
        )

    repaired_manifest = _drop_deleted_nodes_from_manifest(active_snapshot.manifest, deleted_node_ids=deleted_node_ids)
    try:
        if _manifest_has_entries(repaired_manifest):
            from .set_active import _build_context_pack_text, commit_active_state

            assert repaired_manifest is not None
            context_pack_text = _build_context_pack_text(repaired_manifest, repo_root=ports.repo_root)
            commit_active_state(
                persisted_manifest=repaired_manifest,
                patch_manifest=repaired_manifest,
                ports=ports,
                context_pack_text=context_pack_text,
            )
            return (
                "restored",
                warnings,
                "active clear failed after local delete; best-effort active repair was applied",
            )

        from .set_active import clear_active as clear_active_use_case

        clear_active_use_case(ClearActiveRequest(), ports)
        return (
            "cleared",
            warnings,
            "active clear failed once after local delete; clear fallback completed",
        )
    except Exception:
        warnings.append("active_restore_failed")
        return (
            "restore_failed",
            warnings,
            "active repair failed after local delete; rerun `./spec-dock/scripts/spec-dock active clear`",
        )


def delete_node(req: DeleteNodeRequest, ports: Ports) -> DeleteNodeResult:
    try:
        records = ports.node_reader.load_node_records()
    except RuntimeError as error:
        selector_metadata_failure = _target_local_metadata_failure_result(req, ports, error=error)
        if selector_metadata_failure is not None:
            return selector_metadata_failure
        raise
    if not records:
        return _result(
            status="target_not_found",
            validation_code="target_not_found",
            validation_message="no nodes found",
        )
    graph = build_graph([_to_spec_node_seed(record) for record in records])

    target_id, selector_failure = _resolve_target_id(req, graph)
    if selector_failure is not None:
        return selector_failure
    if target_id is None:
        return _result(
            status="target_not_found",
            validation_code="target_not_found",
            validation_message="target not found",
        )
    target = graph.nodes_by_id.get(target_id)
    if target is None:
        return _result(
            status="target_not_found",
            validation_code="target_not_found",
            validation_message=f"target not found: {target_id}",
        )
    if not target.path.exists():
        return _result(
            status="target_not_found",
            target_id=target.id,
            validation_code="target_not_found",
            validation_message=f"target path missing: {target.path.as_posix()}",
        )

    if not req.confirmed:
        return _result(
            status="confirmation_required",
            target_id=target.id,
            validation_code="confirmation_required",
            validation_message="destructive delete requires --yes",
        )
    if target.kind in ("initiative", "epic") and not req.recursive:
        return _result(
            status="recursive_required",
            target_id=target.id,
            validation_code="recursive_required",
            validation_message=f"{target.kind} delete requires --recursive",
        )

    subtree_ids = _subtree_ids(target, graph)
    active_conflicts: list[str] = []
    if ports.active_state_store is not None:
        specdock_dir = _resolve_specdock_dir(ports)
        active_manifest = ports.active_state_store.load_active_manifest(specdock_dir).manifest
        active_conflicts = sorted(_active_ids(active_manifest) & subtree_ids)
        if active_conflicts and not req.force:
            return _result(
                status="active_conflict",
                target_id=target.id,
                offending_node_ids=active_conflicts,
                validation_code="active_conflict",
                validation_message="active selection intersects delete target",
            )

    surviving_node_to_deleted_issue_ids: dict[str, set[str]] = {}
    if ports.deps_topology_reader is not None:
        specdock_dir = _resolve_specdock_dir(ports)
        try:
            topology = ports.deps_topology_reader.load_issue_depends_on_map(specdock_dir, graph)
        except Exception as exc:
            message = str(exc).strip() or "failed to load dependency topology"
            return _dependency_topology_load_failure_result(
                target_id=target.id,
                message=message,
            )
        dep_map = dict(topology.issue_depends_on_map)
        subtree_issue_ids = _subtree_issue_ids(target, graph)
        dep_conflicts, surviving_node_to_deleted_issue_ids = _collect_boundary_dependency_edges(
            dep_map=dep_map,
            subtree_ids=subtree_ids,
            subtree_issue_ids=subtree_issue_ids,
            graph=graph,
        )
        if dep_conflicts:
            if not req.force:
                return _result(
                    status="dependency_conflict",
                    target_id=target.id,
                    offending_node_ids=sorted(dep_conflicts),
                    validation_code="dependency_conflict",
                    validation_message="dependency edge crosses delete subtree boundary",
                )

    required_remote_targets, subtree_metadata_failure = _subtree_remote_close_targets(
        subtree_ids=subtree_ids,
        graph=graph,
    )
    if subtree_metadata_failure is not None:
        return DeleteNodeResult(
            status="metadata_validation_failed",
            target_id=target.id,
            deleted_node_ids=[],
            remaining_node_ids=[],
            remote_close=subtree_metadata_failure.remote_close,
            offending_node_ids=subtree_metadata_failure.offending_node_ids,
            validation_reasons=subtree_metadata_failure.validation_reasons,
            active_restore_result=None,
            recovery_guidance=[],
            dependency_scrub_failures=[],
            warnings=[],
        )
    if required_remote_targets is None:
        return _metadata_failure_result(
            target_id=target.id,
            offending_node_ids=[],
            messages_by_node_id={},
        )

    needs_active_repair = bool(req.force and active_conflicts and ports.active_state_store is not None)
    active_snapshot: ActiveStateSnapshot | None = None
    if ports.active_state_store is not None and (bool(required_remote_targets) or needs_active_repair):
        active_snapshot = ports.active_state_store.snapshot_current_state(_resolve_specdock_dir(ports))

    remote_close, remote_failure = _close_remote_issues_barrier(
        target_id=target.id,
        required_targets=required_remote_targets,
        ports=ports,
        active_snapshot=active_snapshot,
    )
    if remote_failure is not None:
        return remote_failure

    delete_order = _subtree_delete_order(subtree_ids=subtree_ids, graph=graph)
    deleted_node_ids, remaining_node_ids, local_delete_succeeded = _delete_subtree_locally(
        ordered_nodes=delete_order,
        ports=ports,
    )
    if not local_delete_succeeded:
        warnings = ["local_delete_failed"]
        active_restore_result: Literal["cleared", "restored", "restore_failed", "not_needed"] = "not_needed"
        restore_guidance = "active restore was not needed because local delete did not remove target nodes"
        if needs_active_repair and deleted_node_ids:
            active_restore_result, restore_warnings, restore_guidance = _repair_active_after_clear_failure(
                ports=ports,
                active_snapshot=active_snapshot,
                deleted_node_ids=set(deleted_node_ids),
            )
            for warning in restore_warnings:
                if warning not in warnings:
                    warnings.append(warning)
        elif deleted_node_ids:
            restore_guidance = "active restore was not needed for the partially deleted target"
        return _local_delete_partial_failure_result(
            target_id=target.id,
            deleted_node_ids=deleted_node_ids,
            remaining_node_ids=remaining_node_ids,
            remote_close=remote_close,
            active_restore_result=active_restore_result,
            recovery_guidance=_build_partial_failure_recovery_guidance(
                restore_guidance=restore_guidance,
                target=target,
                recursive=req.recursive,
                force=req.force,
                remaining_node_ids=remaining_node_ids,
            ),
            dependency_scrub_failures=[],
            warnings=warnings,
        )

    active_restore_result = "not_needed"
    warnings: list[str] = []
    restore_guidance = "active restore was not needed after local delete"
    dependency_scrub_failures: list[DeleteDependencyScrubFailure] = []
    if req.force and surviving_node_to_deleted_issue_ids:
        dependency_scrub_failures = _scrub_surviving_dependency_refs(
            surviving_node_to_deleted_issue_ids=surviving_node_to_deleted_issue_ids,
            deleted_subtree_node_ids=subtree_ids,
            graph=graph,
            ports=ports,
        )
        if dependency_scrub_failures:
            warnings.append("dependency_scrub_failed")

    if needs_active_repair:
        from .set_active import clear_active as clear_active_use_case

        try:
            clear_active_use_case(ClearActiveRequest(), ports)
            active_restore_result = "cleared"
            restore_guidance = "active clear completed after local delete"
        except Exception:
            active_restore_result, warnings, restore_guidance = _repair_active_after_clear_failure(
                ports=ports,
                active_snapshot=active_snapshot,
                deleted_node_ids=set(deleted_node_ids),
            )
            if dependency_scrub_failures and "dependency_scrub_failed" not in warnings:
                warnings.append("dependency_scrub_failed")
            return _local_delete_partial_failure_result(
                target_id=target.id,
                deleted_node_ids=deleted_node_ids,
                remaining_node_ids=[],
                remote_close=remote_close,
                active_restore_result=active_restore_result,
                recovery_guidance=_build_partial_failure_recovery_guidance(
                    restore_guidance=restore_guidance,
                    target=target,
                    recursive=req.recursive,
                    force=req.force,
                    remaining_node_ids=[],
                    dependency_scrub_failures=dependency_scrub_failures,
                ),
                dependency_scrub_failures=dependency_scrub_failures,
                warnings=warnings,
            )

    if dependency_scrub_failures:
        return _local_delete_partial_failure_result(
            target_id=target.id,
            deleted_node_ids=deleted_node_ids,
            remaining_node_ids=[],
            remote_close=remote_close,
            active_restore_result=active_restore_result,
            recovery_guidance=_build_partial_failure_recovery_guidance(
                restore_guidance=restore_guidance,
                target=target,
                recursive=req.recursive,
                force=req.force,
                remaining_node_ids=[],
                dependency_scrub_failures=dependency_scrub_failures,
            ),
            dependency_scrub_failures=dependency_scrub_failures,
            warnings=warnings,
        )

    return DeleteNodeResult(
        status="ok",
        target_id=target.id,
        deleted_node_ids=deleted_node_ids,
        remaining_node_ids=[],
        remote_close=remote_close,
        offending_node_ids=[],
        validation_reasons=[],
        active_restore_result=active_restore_result,
        recovery_guidance=[],
        dependency_scrub_failures=[],
        warnings=warnings,
        post_sync=post_mutation_sync(ports),
    )
