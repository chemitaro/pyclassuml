from __future__ import annotations

import contextlib
from dataclasses import dataclass, replace
from datetime import datetime
import errno
import json
import os
from pathlib import Path
import shutil
from typing import TYPE_CHECKING, Literal, cast
from uuid import uuid4

from spec_dock_runtime.application.artifact_preflight import validate_required_artifacts_for_graph
from spec_dock_runtime.application.check_deps import (
    load_cached_high_level_github_state_by_id,
    resolve_high_level_status_context,
)
from spec_dock_runtime.application.contracts import (
    ActiveUpdateOutcome,
    ArtifactWriteFailure,
    ArtifactWriteResult,
    PostMutationSyncOutcome,
    SyncCommandResult,
    SyncRequest,
    SyncStateResult,
)
from spec_dock_runtime.application.github_issue_targets import (
    collect_repo_scoped_issue_view_targets,
    normalize_repo_slug,
    snapshot_repo_issue_key,
)
from spec_dock_runtime.application.repo_context import (
    resolve_current_repo_slug,
)
from spec_dock_runtime.application.set_active import build_active_manifest, build_context_pack_text, commit_active_state
from spec_dock_runtime.application.status_context import resolve_issue_status_context
from spec_dock_runtime.domain.active import infer_active_node_from_branch
from spec_dock_runtime.domain.artifacts import parse_artifact_filename
from spec_dock_runtime.domain.deps import (
    build_deps_state,
    build_effective_deps_map,
    evaluate_readiness,
    validate_deps_cycles,
    validate_raw_node_dependency_graph,
)
from spec_dock_runtime.domain.discussion_docs import (
    DISCUSSION_DOC_TIMESTAMP_FILENAME_RE as _DISCUSSION_DOC_TIMESTAMP_FILENAME_RE,
)
from spec_dock_runtime.domain.ids import deps_node_sort_key
from spec_dock_runtime.domain.models import (
    ActiveSelection,
    DepsDependencyContext,
    DepsEvaluation,
    DepsState,
    IssueSnapshot,
    NodeId,
    SpecGraph,
    SpecNodeKind,
    SpecNodeSeed,
)
from spec_dock_runtime.domain.status import build_progress_map, resolve_issue_snapshot_by_issue_id
from spec_dock_runtime.domain.tree import build_graph, select_active_chain
from spec_dock_runtime.domain.validation import (
    find_github_repo_scope_pairing_error,
    validate_graph_and_deps,
)
from spec_dock_runtime.presentation.contracts import ArtifactBundle
from spec_dock_runtime.presentation.json_state import (
    render_deps_issues_artifact,
    render_deps_raw_artifact,
    render_index_artifact,
    render_tree_artifact,
)
from spec_dock_runtime.presentation.markdown import render_dashboard

if TYPE_CHECKING:
    from spec_dock_runtime.application.ports import Ports
    from spec_dock_runtime.infra.contracts import ActiveManifest, DirectDependencyResolution, StoredMetaRecord


class _ArtifactWriteExecutionError(RuntimeError):
    def __init__(self, *, status: Literal["failed_before_write", "failed_partial_or_stale"], reason: str):
        super().__init__(reason)
        self.status = status
        self.reason = reason


@dataclass(frozen=True)
class _AdrMirrorSource:
    scope_id: str
    source_path: Path
    basename: str
    doc_id: str


@dataclass(frozen=True)
class _AdrFrontMatter:
    doc_id: str
    parent_scope_id: str
    authority: str | None
    mirror_eligible: str | None


@dataclass(frozen=True)
class _AdrMirrorProbeLocation:
    probe_dir: Path
    remove_probe_dir_after: bool


_ADR_MIRROR_SYMLINK_UNSUPPORTED_WARNING = "adr_mirror_symlink_unsupported"


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _is_safe_unscoped_snapshot(
    snapshot: IssueSnapshot,
    *,
    current_repo_slug: str | None,
) -> bool:
    scoped_key = snapshot_repo_issue_key(snapshot)
    if scoped_key is None:
        return True
    if current_repo_slug is None:
        return False
    return scoped_key[0] == current_repo_slug


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


def _manifest_to_active_selection(manifest: ActiveManifest | None) -> ActiveSelection | None:
    if manifest is None:
        return None
    return ActiveSelection(
        initiative_id=manifest.initiative.id if manifest.initiative is not None else None,
        epic_id=manifest.epic.id if manifest.epic is not None else None,
        issue_id=manifest.issue.id if manifest.issue is not None else None,
    )


def _now_iso_from_ports(ports: Ports) -> str:
    if ports.clock is not None and hasattr(ports.clock, "now_iso"):
        value = ports.clock.now_iso()
        return str(value)
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _require_sync_runner(ports: Ports):
    runner = ports.sync_legacy_runner
    if runner is None:
        raise RuntimeError("sync_legacy_runner is required")
    return runner


def _path_for_output(path: Path, *, repo_root: Path | None = None) -> str:
    if repo_root is not None:
        try:
            return path.relative_to(repo_root).as_posix()
        except ValueError:
            pass
    return path.as_posix()


def _parse_required_adr_front_matter(path: Path) -> _AdrFrontMatter | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    lines = text.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        return None
    try:
        closing_index = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration:
        return None
    front_matter_lines = lines[1:closing_index]
    entries: dict[str, str] = {}
    for line in front_matter_lines:
        key, separator, value = line.partition(":")
        if not separator:
            continue
        entries[key.strip()] = value.strip()
    doc_kind = entries.get("種別")
    doc_id = entries.get("ID")
    parents_raw = entries.get("親")
    if doc_kind is None or doc_id is None or parents_raw is None:
        return None
    normalized_kind = doc_kind.strip().strip('"').strip("'")
    if normalized_kind != "ADR":
        kind_suffix = normalized_kind[3:].strip() if normalized_kind.startswith("ADR") else ""
        if len(kind_suffix) <= 2 or (kind_suffix[0], kind_suffix[-1]) not in (("(", ")"), ("（", "）")):
            return None
    if not (doc_id.startswith('"') and doc_id.endswith('"')):
        return None
    try:
        parents = json.loads(parents_raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parents, list) or not parents or not isinstance(parents[0], str):
        return None
    return _AdrFrontMatter(
        doc_id=doc_id[1:-1],
        parent_scope_id=parents[0],
        authority=_front_matter_scalar(entries.get("authority")),
        mirror_eligible=_front_matter_scalar(entries.get("mirror_eligible")),
    )


def _front_matter_scalar(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().strip('"').strip("'")


def _artifact_adr_mirror_eligible(front_matter: _AdrFrontMatter) -> bool:
    return front_matter.authority == "accepted" and front_matter.mirror_eligible == "true"


def _adr_doc_id_from_basename(basename: str) -> str | None:
    matched = _DISCUSSION_DOC_TIMESTAMP_FILENAME_RE.fullmatch(basename)
    if matched is None or matched.group("doc_type") != "adr":
        return None
    timestamp = str(matched.group("ts"))
    suffix_raw = matched.group("nn")
    if suffix_raw is None:
        return f"{timestamp}-adr"
    return f"{timestamp}-{int(suffix_raw):02d}-adr"


def _artifact_adr_doc_id_from_basename(basename: str) -> str | None:
    parsed = parse_artifact_filename(basename)
    if parsed is None or parsed.artifact_type != "adr":
        return None
    return parsed.artifact_id


def _ensure_collectable_artifacts_dir(artifacts_dir: Path) -> bool:
    if artifacts_dir.is_symlink():
        raise RuntimeError(f"Unsafe artifact directory: {artifacts_dir.as_posix()} is a symlink")
    if not artifacts_dir.exists():
        return False
    if not artifacts_dir.is_dir():
        raise RuntimeError(f"Unsafe artifact directory: {artifacts_dir.as_posix()} is not a directory")
    return True


def _collect_adr_mirror_sources(graph: SpecGraph) -> list[_AdrMirrorSource]:
    sources: list[_AdrMirrorSource] = []
    scope_nodes = sorted(
        (node for node in graph.nodes_by_id.values() if node.kind in ("initiative", "epic", "issue")),
        key=lambda node: (node.kind, node.id, node.path.as_posix()),
    )
    for scope in scope_nodes:
        discussions_dir = scope.path / "discussions"
        if discussions_dir.exists():
            for path in sorted(discussions_dir.glob("*.md"), key=lambda p: p.as_posix()):
                basename = path.name
                doc_id = _adr_doc_id_from_basename(basename)
                if doc_id is None:
                    continue
                front_matter = _parse_required_adr_front_matter(path)
                if front_matter is None:
                    continue
                if front_matter.doc_id != doc_id:
                    continue
                if front_matter.parent_scope_id != scope.id:
                    continue
                sources.append(
                    _AdrMirrorSource(
                        scope_id=scope.id,
                        source_path=path,
                        basename=basename,
                        doc_id=doc_id,
                    )
                )
        artifacts_dir = scope.path / "artifacts"
        if not _ensure_collectable_artifacts_dir(artifacts_dir):
            continue
        for path in sorted(artifacts_dir.glob("*.md"), key=lambda p: p.as_posix()):
            if path.name == "rules.md":
                continue
            if path.is_symlink():
                raise RuntimeError(f"Unsafe artifact file: {path.as_posix()} is a symlink")
            basename = path.name
            doc_id = _artifact_adr_doc_id_from_basename(basename)
            if doc_id is None:
                continue
            front_matter = _parse_required_adr_front_matter(path)
            if front_matter is None:
                continue
            if not _artifact_adr_mirror_eligible(front_matter):
                continue
            if front_matter.doc_id != doc_id:
                continue
            if front_matter.parent_scope_id != scope.id:
                continue
            sources.append(
                _AdrMirrorSource(
                    scope_id=scope.id,
                    source_path=path,
                    basename=basename,
                    doc_id=doc_id,
                )
            )
    return sources


def _preflight_adr_mirror_sources(result: SyncStateResult) -> list[_AdrMirrorSource]:
    sources = _collect_adr_mirror_sources(result.graph)
    sources_by_basename: dict[str, list[_AdrMirrorSource]] = {}
    for source in sources:
        sources_by_basename.setdefault(source.basename, []).append(source)
    collisions = sorted((basename, entries) for basename, entries in sources_by_basename.items() if len(entries) > 1)
    if collisions:
        basename, entries = collisions[0]
        source_list = ", ".join(
            _path_for_output(entry.source_path, repo_root=result.repo_root)
            for entry in sorted(entries, key=lambda item: item.source_path.as_posix())
        )
        raise _ArtifactWriteExecutionError(
            status="failed_before_write",
            reason=f"ADR mirror basename collision: {basename} sources=[{source_list}]",
        )
    return sources


def _unlink_any(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
        return
    if path.is_dir():
        shutil.rmtree(path)


def _ensure_empty_dir(path: Path) -> None:
    _unlink_any(path)
    path.mkdir(parents=True, exist_ok=True)


def _is_environment_symlink_unsupported(error: BaseException) -> bool:
    if not isinstance(error, OSError):
        return False
    unsupported_errnos = {
        code
        for code in (
            getattr(errno, "ENOSYS", None),
            getattr(errno, "EOPNOTSUPP", None),
            getattr(errno, "ENOTSUP", None),
        )
        if code is not None
    }
    if error.errno in unsupported_errnos:
        return True
    return getattr(error, "winerror", None) == 1314


def _resolve_adr_mirror_probe_location(specdock_dir: Path) -> _AdrMirrorProbeLocation:
    adrs_dir = specdock_dir / "adrs"
    if adrs_dir.exists() or adrs_dir.is_symlink():
        return _AdrMirrorProbeLocation(probe_dir=specdock_dir, remove_probe_dir_after=False)
    adrs_dir.mkdir(parents=True, exist_ok=True)
    return _AdrMirrorProbeLocation(probe_dir=adrs_dir, remove_probe_dir_after=True)


def _build_adr_mirror_probe_path(probe_dir: Path) -> Path:
    return probe_dir / f".spec-dock-adr-mirror-probe-{uuid4().hex}"


def _preflight_adr_mirror_symlink_support(specdock_dir: Path) -> bool:
    probe_location = _resolve_adr_mirror_probe_location(specdock_dir)
    try:
        for _ in range(16):
            probe_path = _build_adr_mirror_probe_path(probe_location.probe_dir)
            probe_created = False
            try:
                Path(probe_path).symlink_to(".spec-dock-adr-mirror-probe-target")
                probe_created = True
                return True
            except FileExistsError:
                continue
            except OSError as error:
                if _is_environment_symlink_unsupported(error):
                    return False
                raise
            finally:
                if probe_created:
                    probe_path.unlink(missing_ok=True)
        raise RuntimeError("unable to reserve ADR mirror symlink probe path")
    finally:
        if probe_location.remove_probe_dir_after:
            with contextlib.suppress(OSError):
                probe_location.probe_dir.rmdir()


def _rebuild_adr_mirror(
    specdock_dir: Path,
    sources: list[_AdrMirrorSource],
    *,
    symlink_supported: bool | None = None,
) -> bool:
    adrs_dir = specdock_dir / "adrs"
    _ensure_empty_dir(adrs_dir)
    if not sources:
        return True
    if symlink_supported is None:
        symlink_supported = _preflight_adr_mirror_symlink_support(specdock_dir)
    if not symlink_supported:
        _ensure_empty_dir(adrs_dir)
        return False
    for source in sorted(sources, key=lambda item: item.basename):
        link_path = adrs_dir / source.basename
        rel_target = os.path.relpath(source.source_path, start=adrs_dir)
        Path(link_path).symlink_to(rel_target)
    return True


def _can_collect_natively(ports: Ports) -> bool:
    return ports.deps_topology_reader is not None


def _can_sync_natively(ports: Ports) -> bool:
    return _can_collect_natively(ports) and ports.artifact_writer is not None


def _load_active_selection(
    ports: Ports,
    *,
    active_manifest_mode: Literal["migrate", "no_migrate"],
) -> tuple[ActiveSelection | None, list[str]]:
    if ports.active_state_store is None:
        return (None, [])

    specdock_dir = _resolve_specdock_dir(ports)
    if active_manifest_mode == "no_migrate":
        load_result = ports.active_state_store.load_active_manifest_no_migrate(specdock_dir)
    else:
        load_result = ports.active_state_store.load_active_manifest(specdock_dir)
    return (_manifest_to_active_selection(load_result.manifest), list(load_result.warnings))


def collect_sync_state(
    req: SyncRequest,
    ports: Ports,
    *,
    active_manifest_mode: Literal["migrate", "no_migrate"] = "migrate",
) -> SyncStateResult:
    if not _can_collect_natively(ports):
        runner = _require_sync_runner(ports)
        result = runner.run_sync(req, active_manifest_mode=active_manifest_mode)
        return result.state

    records = ports.node_reader.load_node_records()
    if not records:
        raise RuntimeError("No nodes found. Create at least one initiative/epic/issue.")
    current_repo_slug = resolve_current_repo_slug(ports)
    graph = build_graph([_to_spec_node_seed(record) for record in records])
    specdock_dir = _resolve_specdock_dir(ports)

    warnings: list[str] = []
    deps_preflight_error: str | None = None
    issue_depends_on_map: dict[str, list[str]] = {}
    raw_node_depends_on_map: dict[str, list[str]] = {}
    dependency_contexts_by_issue_id: dict[str, list[DepsDependencyContext]] = {}
    validation = validate_graph_and_deps(
        graph,
        issue_depends_on_map=None,
        repo_root=ports.repo_root,
        current_repo_slug=current_repo_slug,
        enforce_github_mandatory_linkage=False,
    )
    github_repo_scope_pairing_error = find_github_repo_scope_pairing_error(graph, repo_root=ports.repo_root)
    if validation.errors:
        validation_error = validation.errors[0]
        if github_repo_scope_pairing_error is not None:
            raise RuntimeError(f"preflight validate failed: {github_repo_scope_pairing_error}")
        if req.force:
            deps_preflight_error = f"preflight validate failed: {validation_error}"
            _append_unique(warnings, "deps_preflight_failed")
        else:
            raise RuntimeError(f"preflight validate failed: {validation_error}")
    else:
        try:
            validate_required_artifacts_for_graph(graph, repo_root=ports.repo_root)
        except RuntimeError as error:
            if req.force:
                deps_preflight_error = f"preflight validate failed: {error}"
                _append_unique(warnings, "deps_preflight_failed")
            else:
                raise RuntimeError(f"preflight validate failed: {error}") from error
        else:
            topology = ports.deps_topology_reader.load_issue_depends_on_map(specdock_dir, graph)
            issue_depends_on_map = dict(topology.issue_depends_on_map)
            dependency_contexts_by_issue_id = dict(topology.dependency_contexts_by_issue_id)
            for warning in topology.warnings:
                _append_unique(warnings, warning)
            try:
                load_node_dependency_resolutions = getattr(
                    ports.deps_topology_reader,
                    "load_node_dependency_resolutions",
                    None,
                )
                if callable(load_node_dependency_resolutions):
                    raw_node_depends_on_map = _raw_node_depends_on_map(
                        load_node_dependency_resolutions(specdock_dir, graph)
                    )
                    validate_raw_node_dependency_graph(graph, raw_node_depends_on_map)
                validate_deps_cycles(issue_depends_on_map)
                validate_graph_and_deps(
                    graph,
                    issue_depends_on_map=issue_depends_on_map,
                    repo_root=ports.repo_root,
                    current_repo_slug=current_repo_slug,
                    enforce_github_mandatory_linkage=False,
                )
                effective_deps_map = build_effective_deps_map(graph, issue_depends_on_map)
                validate_deps_cycles(effective_deps_map)
            except RuntimeError as error:
                if req.force:
                    deps_preflight_error = str(error)
                    _append_unique(warnings, "deps_preflight_failed")
                else:
                    raise

    issue_snapshots: list[IssueSnapshot] | None = None
    github_snapshot_by_repo_and_issue_number: dict[tuple[str, int], IssueSnapshot] = {}
    github_snapshot_by_repo_scope_and_issue_number: dict[tuple[str | None, int], IssueSnapshot] = {}
    github_snapshot_by_issue_id: dict[str, IssueSnapshot] = {}
    if req.github_enabled:
        if ports.issue_gateway is None:
            raise RuntimeError("issue_gateway is required when --github is enabled")
        if ports.repo_root is None:
            raise RuntimeError("repo_root is required when --github is enabled")
        issue_snapshots = []
        issue_index_snapshots: list[IssueSnapshot] = []
        foreign_issue_snapshots: list[IssueSnapshot] = []
        try:
            issue_index_snapshots = ports.issue_gateway.issue_index(ports.repo_root, limit=int(req.issue_limit))
        except RuntimeError:
            _append_unique(warnings, "gh_fetch_failed")
        else:
            linked_numbers = sorted({
                int(node.github_issue_number)
                for node in graph.nodes_by_id.values()
                if node.kind == "issue"
                and node.github_issue_number is not None
                and normalize_repo_slug(node.github_repo_owner, node.github_repo_name) is None
            })
            indexed_numbers = {int(snapshot.issue_number) for snapshot in issue_index_snapshots}
            missing = [num for num in linked_numbers if num not in indexed_numbers]
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
            foreign_issue_snapshots.append(snapshot)
        # Keep current-repo index snapshots first so unscoped lookups use the
        # current repo value when foreign repos share the same issue number.
        issue_snapshots = [*issue_index_snapshots, *foreign_issue_snapshots]
        for snapshot in issue_index_snapshots:
            if not _is_safe_unscoped_snapshot(snapshot, current_repo_slug=current_repo_slug):
                continue
            issue_number = int(snapshot.issue_number)
            unscoped_key = (None, issue_number)
            if unscoped_key not in github_snapshot_by_repo_scope_and_issue_number:
                github_snapshot_by_repo_scope_and_issue_number[unscoped_key] = snapshot

        for snapshot in issue_snapshots:
            scoped_key = snapshot_repo_issue_key(snapshot)
            if scoped_key is not None:
                if scoped_key not in github_snapshot_by_repo_and_issue_number:
                    github_snapshot_by_repo_and_issue_number[scoped_key] = snapshot
                if scoped_key not in github_snapshot_by_repo_scope_and_issue_number:
                    github_snapshot_by_repo_scope_and_issue_number[scoped_key] = snapshot

    cached_issue_status_by_id: dict[str, str] = {}
    cached_issue_last_sync_at_by_id: dict[str, str | None] = {}
    cached_high_level_github_state_by_id: dict[str, str] = {}
    if ports.derived_state_reader is not None:
        cached_issue_status_by_id = ports.derived_state_reader.load_cached_issue_status_by_id(specdock_dir)
        cached_issue_last_sync_at_by_id = _load_cached_issue_last_sync_at_by_id(ports, specdock_dir)
        if not req.github_enabled:
            cached_high_level_github_state_by_id = load_cached_high_level_github_state_by_id(specdock_dir)
    status_context = resolve_issue_status_context(
        graph,
        github_enabled=req.github_enabled,
        issue_snapshots=issue_snapshots,
        cached_issue_status_by_id=cached_issue_status_by_id,
        cached_issue_last_sync_at_by_id=cached_issue_last_sync_at_by_id,
        current_repo_slug=current_repo_slug,
    )
    if req.github_enabled:
        github_snapshot_by_issue_id = resolve_issue_snapshot_by_issue_id(
            graph,
            issue_snapshots,
            current_repo_slug=current_repo_slug,
        )
    for warning in status_context.warnings:
        _append_unique(warnings, warning)

    active_selection, active_warnings = _load_active_selection(ports, active_manifest_mode=active_manifest_mode)
    for warning in active_warnings:
        _append_unique(warnings, warning)

    deps_state: DepsState
    deps_eval_by_id: dict[str, DepsEvaluation]
    high_level_statuses_by_node_id = resolve_high_level_status_context(
        graph,
        issue_statuses=status_context.issue_statuses,
        cached_high_level_github_state_by_id=cached_high_level_github_state_by_id,
    )
    if deps_preflight_error is None:
        effective_deps_map = build_effective_deps_map(graph, issue_depends_on_map)
        deps_state = build_deps_state(
            graph,
            effective_deps_map,
            status_context.issue_statuses,
            active_selection,
            warnings=[],
        )
        deps_eval_by_id = {}
        for node_id, node in graph.nodes_by_id.items():
            if node.kind != "issue":
                continue
            deps_eval_by_id[node_id] = evaluate_readiness(
                graph,
                issue_depends_on_map,
                NodeId(node_id),
                status_context.issue_statuses,
                dependency_contexts_by_issue_id=dependency_contexts_by_issue_id,
                high_level_statuses_by_node_id=high_level_statuses_by_node_id,
            )
    else:
        deps_state = DepsState(nodes=[], warnings=[])
        deps_eval_by_id = {}

    progress = build_progress_map(graph, status_context.issue_statuses)
    return SyncStateResult(
        graph=graph,
        active=active_selection,
        issue_statuses=status_context.issue_statuses,
        progress=progress,
        deps_state=deps_state,
        deps_eval_by_id=deps_eval_by_id,
        generated_at=_now_iso_from_ports(ports),
        warnings=warnings,
        deps_preflight_error=deps_preflight_error,
        repo_root=ports.repo_root,
        issue_depends_on_map=issue_depends_on_map,
        raw_node_depends_on_map=raw_node_depends_on_map,
        github_snapshot_by_repo_and_issue_number=github_snapshot_by_repo_and_issue_number,
        github_snapshot_by_repo_scope_and_issue_number=github_snapshot_by_repo_scope_and_issue_number,
        github_snapshot_by_issue_id=github_snapshot_by_issue_id,
        dependency_contexts_by_issue_id=dependency_contexts_by_issue_id,
        high_level_statuses_by_node_id=high_level_statuses_by_node_id,
    )


def _raw_node_depends_on_map(
    resolutions_by_node: dict[str, list[DirectDependencyResolution]],
) -> dict[str, list[str]]:
    return {
        node_id: sorted(
            [resolution.resolved_node_id for resolution in resolutions],
            key=deps_node_sort_key,
        )
        for node_id, resolutions in sorted(
            resolutions_by_node.items(),
            key=lambda item: deps_node_sort_key(item[0]),
        )
        if resolutions
    }


def maybe_auto_update_from_branch(
    state: SyncStateResult,
    ports: Ports,
) -> tuple[SyncStateResult, ActiveUpdateOutcome | None]:
    if ports.repo_root is None or ports.git_gateway is None:
        return (state, None)
    if ports.active_state_store is None:
        raise RuntimeError("active_state_store is required for sync active auto-update")

    try:
        branch = ports.git_gateway.current_branch_or_none(ports.repo_root)
    except RuntimeError:
        return (state, None)
    if not branch:
        return (state, None)

    inferred_node, reason = infer_active_node_from_branch(
        state.graph,
        branch=branch,
        current_repo_slug=resolve_current_repo_slug(ports),
    )
    if inferred_node is None:
        return (state, ActiveUpdateOutcome(applied=False, reason=reason))

    selection = select_active_chain(state.graph, NodeId(inferred_node.id))
    if state.active == selection:
        return (state, ActiveUpdateOutcome(applied=False, reason=reason or "already active"))

    manifest = build_active_manifest(selection, state.graph, repo_root=ports.repo_root)
    context_pack_text = build_context_pack_text(manifest, repo_root=ports.repo_root)
    commit_active_state(
        persisted_manifest=manifest,
        patch_manifest=manifest,
        ports=ports,
        context_pack_text=context_pack_text,
    )
    return (
        replace(state, active=selection),
        ActiveUpdateOutcome(applied=True, reason=reason or f"matched branch: {inferred_node.id}"),
    )


def write_sync_artifacts(
    result: SyncStateResult,
    ports: Ports,
    *,
    adr_mirror_sources: list[_AdrMirrorSource] | None = None,
    preflight_adr_mirror_sources: bool = True,
    warning_codes: list[str] | None = None,
) -> ArtifactWriteResult:
    if ports.artifact_writer is None:
        raise RuntimeError("artifact_writer is required")
    if adr_mirror_sources is not None:
        sources = list(adr_mirror_sources)
    elif preflight_adr_mirror_sources:
        sources = _preflight_adr_mirror_sources(result)
    else:
        raise RuntimeError("adr_mirror_sources is required when preflight_adr_mirror_sources is False")
    specdock_dir = _resolve_specdock_dir(ports)
    symlink_supported: bool | None = None
    persisted_warnings = list(result.warnings)
    if sources:
        try:
            symlink_supported = _preflight_adr_mirror_symlink_support(specdock_dir)
        except Exception as error:
            raise _ArtifactWriteExecutionError(
                status="failed_before_write",
                reason=str(error),
            ) from error
        if not symlink_supported:
            _append_unique(persisted_warnings, _ADR_MIRROR_SYMLINK_UNSUPPORTED_WARNING)
            if warning_codes is not None:
                _append_unique(warning_codes, _ADR_MIRROR_SYMLINK_UNSUPPORTED_WARNING)
    persisted_result = replace(result, warnings=persisted_warnings)
    bundle = ArtifactBundle(
        index=render_index_artifact(persisted_result),
        tree=render_tree_artifact(persisted_result),
        deps_issues=render_deps_issues_artifact(persisted_result),
        dashboard=render_dashboard(persisted_result),
        deps_raw=render_deps_raw_artifact(persisted_result),
    )
    try:
        write_result = ports.artifact_writer.write(specdock_dir, bundle)
        _rebuild_adr_mirror(specdock_dir, sources, symlink_supported=symlink_supported)
        return write_result
    except Exception as error:
        # FileArtifactWriter writes sequentially and is non-atomic. Any writer exception
        # must preserve partial/stale possibility even when active_update was not applied.
        raise _ArtifactWriteExecutionError(
            status="failed_partial_or_stale",
            reason=str(error),
        ) from error


def _sync_impl(
    req: SyncRequest,
    ports: Ports,
    *,
    active_manifest_mode: Literal["migrate", "no_migrate"],
) -> SyncCommandResult:
    if not _can_sync_natively(ports):
        runner = _require_sync_runner(ports)
        return runner.run_sync(req, active_manifest_mode=active_manifest_mode)

    state = collect_sync_state(req, ports, active_manifest_mode=active_manifest_mode)
    active_update: ActiveUpdateOutcome | None = None
    final_state = state
    try:
        adr_mirror_sources = _preflight_adr_mirror_sources(state)
    except _ArtifactWriteExecutionError as error:
        return SyncCommandResult(
            state=final_state,
            write_result=None,
            active_update=active_update,
            artifact_failure=ArtifactWriteFailure(status=error.status, reason=error.reason),
        )
    if req.update_active_from_branch and not req.force:
        final_state, active_update = maybe_auto_update_from_branch(state, ports)

    sync_warnings = list(final_state.warnings)
    try:
        write_result = write_sync_artifacts(
            final_state,
            ports,
            adr_mirror_sources=adr_mirror_sources,
            preflight_adr_mirror_sources=False,
            warning_codes=sync_warnings,
        )
        final_state = replace(final_state, warnings=sync_warnings)
    except _ArtifactWriteExecutionError as error:
        final_state = replace(final_state, warnings=sync_warnings)
        artifact_status = error.status
        if active_update is not None and active_update.applied:
            artifact_status = "failed_partial_or_stale"
        return SyncCommandResult(
            state=final_state,
            write_result=None,
            active_update=active_update,
            artifact_failure=ArtifactWriteFailure(status=artifact_status, reason=error.reason),
        )
    except Exception as error:
        status: Literal["failed_before_write", "failed_partial_or_stale"]
        if active_update is not None and active_update.applied:
            status = "failed_partial_or_stale"
        else:
            status = "failed_before_write"
        final_state = replace(final_state, warnings=sync_warnings)
        return SyncCommandResult(
            state=final_state,
            write_result=None,
            active_update=active_update,
            artifact_failure=ArtifactWriteFailure(status=status, reason=str(error)),
        )

    return SyncCommandResult(
        state=final_state,
        write_result=write_result,
        active_update=active_update,
        artifact_failure=None,
    )


def sync(req: SyncRequest, ports: Ports) -> SyncCommandResult:
    return _sync_impl(req, ports, active_manifest_mode="migrate")


def sync_after_import(ports: Ports) -> SyncCommandResult:
    req = SyncRequest(
        force=False,
        github_enabled=False,
        issue_limit=10000,
        update_active_from_branch=False,
    )
    return _sync_impl(req, ports, active_manifest_mode="no_migrate")


def sync_after_mutation(ports: Ports) -> SyncCommandResult:
    req = SyncRequest(
        force=False,
        github_enabled=True,
        issue_limit=10000,
        update_active_from_branch=False,
    )
    return _sync_impl(req, ports, active_manifest_mode="no_migrate")


def post_mutation_sync(ports: Ports) -> PostMutationSyncOutcome:
    try:
        return PostMutationSyncOutcome.from_sync_result(sync_after_mutation(ports))
    except Exception as error:
        return PostMutationSyncOutcome.from_exception(error)


def skipped_post_mutation_sync(reason: str) -> PostMutationSyncOutcome:
    return PostMutationSyncOutcome.skipped(reason)
