from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from spec_dock_runtime.application import create_node as app_create_node
from spec_dock_runtime.application.artifact_preflight import validate_required_artifacts_for_graph
from spec_dock_runtime.application.contracts import (
    DoctorFinding,
    DoctorRequest,
    DoctorResult,
    GitHubCapabilityDiagnostic,
    GitHubCapabilityProbeRequest,
)
from spec_dock_runtime.application.repo_context import resolve_current_repo_slug
from spec_dock_runtime.domain.deps import validate_raw_node_dependency_graph
from spec_dock_runtime.domain.models import SpecGraph, SpecNodeKind, SpecNodeSeed
from spec_dock_runtime.domain.tree import build_graph
from spec_dock_runtime.domain.validation import validate_graph_and_deps

if TYPE_CHECKING:
    from spec_dock_runtime.application.ports import Ports
    from spec_dock_runtime.infra.contracts import ActiveManifestEntry, DirectDependencyResolution, StoredMetaRecord


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


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def _raw_node_depends_on_map(
    resolutions_by_node: dict[str, list[DirectDependencyResolution]],
) -> dict[str, list[str]]:
    return {
        node_id: [resolution.resolved_node_id for resolution in resolutions]
        for node_id, resolutions in resolutions_by_node.items()
    }


def _legacy_only_workspace_finding(*, legacy_dir: Path) -> DoctorFinding:
    return DoctorFinding(
        code="legacy_only_workspace",
        message=(f"legacy workspace is present but current workspace is missing: path={legacy_dir}"),
        guidance=[
            "Do not rename '.spec-dock' to 'spec-dock' (formats are incompatible).",
            "Run `spec-dock init` to install a new `spec-dock/` workspace.",
            "Migrate required data manually and remove `.spec-dock/` manually when ready.",
        ],
    )


def _finding_from_error(error_message: str) -> DoctorFinding:
    if "Duplicate id detected" in error_message or "Duplicate numeric id detected" in error_message:
        return DoctorFinding(
            code="duplicate_id",
            message=error_message,
            guidance=[
                "重複している .meta.json の id を一意に修正してください。",
                "修正後に `spec-dock/scripts/spec-dock validate` を再実行してください。",
            ],
        )
    if (
        "Duplicate discussion sequence detected" in error_message
        or "Duplicate discussion timestamp slot detected" in error_message
        or "Duplicate discussion timestamp suffix detected" in error_message
    ):
        return DoctorFinding(
            code="duplicate_seq",
            message=error_message,
            guidance=[
                "対象 scope の discussions 配下で重複している discussion markdown を整理してください。",
                "修正後に `spec-dock/scripts/spec-dock validate` を再実行してください。",
            ],
        )
    if "Malformed discussion document filename under " in error_message:
        return DoctorFinding(
            code="malformed_discussion_doc",
            message=error_message,
            guidance=[
                "対象 scope の discussions 配下で命名規則に違反している discussion markdown を修正または整理してください。",
                "修正後に `spec-dock/scripts/spec-dock validate` を再実行してください。",
            ],
        )
    if "Create in-progress state detected" in error_message:
        return DoctorFinding(
            code="stale_create_lock",
            message=error_message,
            guidance=[
                "create 実行中であれば完了を待ってください。",
                "実行中プロセスがない場合は create lock の stale を疑い `spec-dock/scripts/spec-dock doctor` で再確認してください。",
            ],
        )
    if "Stale create-lock state detected" in error_message:
        return DoctorFinding(
            code="stale_create_lock",
            message=error_message,
            guidance=[
                "create 実行中プロセスがないことを確認してください。",
                "stale create lock を修復してから再実行してください。",
                "`spec-dock/scripts/spec-dock doctor` で再診断してください。",
            ],
        )
    if "Missing required artifact" in error_message:
        return DoctorFinding(
            code="missing_artifact",
            message=error_message,
            guidance=[
                "欠損 artifact をテンプレートまたは履歴から復元してください。",
                "復元後に `spec-dock/scripts/spec-dock validate` を再実行してください。",
            ],
        )
    if "Unsupported legacy meta.json detected" in error_message or ".meta.json" in error_message:
        return DoctorFinding(
            code="broken_meta",
            message=error_message,
            guidance=[
                "壊れた .meta.json を JSON object と required fields が揃う状態に修復してください。",
                "修復後に `spec-dock/scripts/spec-dock validate` を再実行してください。",
            ],
        )
    return DoctorFinding(
        code="validation_error",
        message=error_message,
        guidance=[
            "validate エラーの原因を解消してください。",
            "解消後に `spec-dock/scripts/spec-dock validate` を再実行してください。",
        ],
    )


def _resolve_active_entry_path(
    entry: ActiveManifestEntry,
    *,
    specdock_dir: Path,
    repo_root: Path | None,
) -> Path | None:
    if entry.path is None or not entry.path.strip():
        return None
    raw = Path(entry.path.strip())
    current_repo_root = repo_root if repo_root is not None else specdock_dir.parent
    candidates: list[Path] = []

    if raw.is_absolute():
        try:
            rel_from_repo_root = raw.relative_to(current_repo_root)
            candidates.append(current_repo_root / rel_from_repo_root)
        except ValueError:
            pass
        parts = raw.parts
        for specdock_index in range(len(parts) - 1, -1, -1):
            if parts[specdock_index] != specdock_dir.name:
                continue
            candidates.append(current_repo_root / Path(*parts[specdock_index:]))
    else:
        candidates.append(current_repo_root / raw)

    resolved_specdock_dir = specdock_dir.resolve(strict=False)
    for candidate in candidates:
        try:
            candidate.resolve(strict=False).relative_to(resolved_specdock_dir)
        except ValueError:
            continue
        return candidate
    return None


def _stale_active_pointer_finding(
    ports: Ports,
    *,
    specdock_dir: Path,
    graph: SpecGraph | None,
    warnings: list[str],
) -> DoctorFinding | None:
    if ports.active_state_store is None:
        return None

    try:
        load_result = ports.active_state_store.load_active_manifest(specdock_dir)
    except RuntimeError as error:
        return DoctorFinding(
            code="stale_active_pointer",
            message=f"failed to load active manifest: {error}",
            guidance=[
                "`spec-dock/scripts/spec-dock active clear` で active pointer をクリアしてください。",
                "`spec-dock/scripts/spec-dock active set <target>` で active pointer を再設定してください。",
            ],
        )
    for warning in load_result.warnings:
        _append_unique(warnings, warning)

    manifest = load_result.manifest
    invalid_manifest_warnings = [
        warning
        for warning in load_result.warnings
        if warning.startswith("active_manifest_invalid_json:") or warning.startswith("active_manifest_invalid_shape:")
    ]
    if manifest is None:
        if invalid_manifest_warnings:
            return DoctorFinding(
                code="stale_active_pointer",
                message="; ".join(invalid_manifest_warnings),
                guidance=[
                    "`spec-dock/scripts/spec-dock active clear` で active pointer をクリアしてください。",
                    "`spec-dock/scripts/spec-dock active set <target>` で active pointer を再設定してください。",
                ],
            )
        return None

    stale_reasons: list[str] = []
    graph_ids = set(graph.nodes_by_id.keys()) if graph is not None else None
    for layer in ("initiative", "epic", "issue"):
        entry = getattr(manifest, layer)
        if entry is None:
            continue
        if graph_ids is not None and entry.id not in graph_ids:
            stale_reasons.append(f"{layer}.id={entry.id} is not found in current graph")
        resolved_path = _resolve_active_entry_path(entry, specdock_dir=specdock_dir, repo_root=ports.repo_root)
        if resolved_path is None:
            stale_reasons.append(f"{layer}.path is missing")
            continue
        if not resolved_path.exists():
            stale_reasons.append(f"{layer}.path not found: {entry.path}")
            continue
        if not resolved_path.is_dir():
            stale_reasons.append(f"{layer}.path is not a directory: {entry.path}")

    if not stale_reasons:
        return None

    return DoctorFinding(
        code="stale_active_pointer",
        message="; ".join(stale_reasons),
        guidance=[
            "`spec-dock/scripts/spec-dock active clear` で active pointer をクリアしてください。",
            "`spec-dock/scripts/spec-dock active set <target>` で active pointer を再設定してください。",
        ],
    )


def _validate_create_lock_metadata(meta: dict[str, str]) -> str | None:
    if not meta:
        return "empty_or_unreadable"
    required = ("token", "pid", "user", "created_unix")
    missing = [key for key in required if not str(meta.get(key, "")).strip()]
    if missing:
        return f"missing_fields={','.join(missing)}"
    try:
        float(str(meta.get("created_unix", "")).strip())
    except ValueError:
        return "invalid_created_unix"
    return None


def _stale_create_lock_finding(specdock_dir: Path) -> DoctorFinding | None:
    lock_path = app_create_node._resolve_create_lock_path(specdock_dir)
    if not lock_path.exists():
        return None
    if not lock_path.is_file():
        return DoctorFinding(
            code="stale_create_lock",
            message=f"create lock is not a regular file: path={lock_path}",
            guidance=[
                "create 実行中プロセスがないことを確認してください。",
                f"`{lock_path}` を削除してから再実行してください。",
                "`spec-dock/scripts/spec-dock doctor` で再診断してください。",
            ],
        )

    meta, summary = app_create_node._read_create_lock_metadata(lock_path)
    metadata_issue = _validate_create_lock_metadata(meta)
    stale_after_seconds: float | None = None
    try:
        stale_after_seconds = app_create_node._resolve_duration_seconds(
            app_create_node._ENV_CREATE_LOCK_STALE_SECONDS,
            app_create_node._DEFAULT_CREATE_LOCK_STALE_SECONDS,
            minimum=0.0,
        )
    except RuntimeError as error:
        metadata_issue = f"invalid_stale_threshold={error}"

    stale = False
    if stale_after_seconds is not None:
        stale = app_create_node._is_stale_lock(meta, stale_after_seconds=stale_after_seconds)
    reasons: list[str] = []
    if stale:
        reasons.append("stale=true")
    else:
        reasons.append("stale=false")
    if metadata_issue is not None:
        reasons.append(f"metadata={metadata_issue}")
    elif not stale:
        reasons.append("contention=true")

    reason_text = " ".join(reasons).strip()
    message = f"create lock detected: path={lock_path} {reason_text} lock_meta=[{summary}]".strip()
    guidance: list[str] = []
    if stale or metadata_issue is not None:
        guidance.append("create 実行中プロセスがないことを確認してください。")
        guidance.append(f"`{lock_path}` を削除してから再実行してください。")
    else:
        guidance.append("他の create 実行中であれば完了を待ってから再実行してください。")
        guidance.append(f"実行中プロセスが無い場合は `{lock_path}` を削除してから再実行してください。")
    guidance.append("`spec-dock/scripts/spec-dock doctor` で再診断してください。")
    return DoctorFinding(
        code="stale_create_lock",
        message=message,
        guidance=guidance,
    )


def _github_target_unavailable_diagnostic() -> GitHubCapabilityDiagnostic:
    return GitHubCapabilityDiagnostic(
        code="github_target_unavailable",
        capability="actions_read",
        status="target_unavailable",
        token_source="unknown",
        api="github_pr_observation_probe",
        severity="info",
        message="GitHub PR capability probe skipped because repo, PR, or head SHA was not provided.",
        recommended_next_action="provide_github_repo_pr_and_head_sha_for_capability_probe",
        secret_redacted=True,
        stderr_sha256=None,
        group="core",
    )


def _github_gateway_unavailable_diagnostic() -> GitHubCapabilityDiagnostic:
    return GitHubCapabilityDiagnostic(
        code="github_capability_skipped",
        capability="actions_read",
        status="skipped",
        token_source="unknown",
        api="github_pr_observation_probe",
        severity="info",
        message="GitHub capability gateway is unavailable.",
        recommended_next_action="run_in_installed_runtime_with_github_capability_gateway",
        secret_redacted=True,
        stderr_sha256=None,
        group="core",
    )


def _github_capability_diagnostics(req: DoctorRequest, ports: Ports) -> list[GitHubCapabilityDiagnostic]:
    if not (req.github_repo and req.github_pr is not None and req.github_head_sha):
        return [_github_target_unavailable_diagnostic()]
    if ports.github_capability_gateway is None:
        return [_github_gateway_unavailable_diagnostic()]
    probe_request = GitHubCapabilityProbeRequest(
        github_repo=req.github_repo,
        github_pr=req.github_pr,
        github_head_sha=req.github_head_sha,
        include_extended=req.github_extended,
    )
    return ports.github_capability_gateway.probe(probe_request)


def doctor(req: DoctorRequest, ports: Ports) -> DoctorResult:
    warnings: list[str] = []
    findings: list[DoctorFinding] = []
    graph: SpecGraph | None = None
    specdock_dir = _resolve_specdock_dir(ports)
    repo_root = ports.repo_root if ports.repo_root is not None else specdock_dir.parent
    legacy_dir = repo_root / ".spec-dock"
    has_current_workspace = specdock_dir.is_dir()
    has_legacy_workspace = legacy_dir.is_dir()

    if has_legacy_workspace and not has_current_workspace:
        findings.append(_legacy_only_workspace_finding(legacy_dir=legacy_dir))
        return DoctorResult(
            ok=False,
            findings=findings,
            warnings=warnings,
            github_capability_diagnostics=_github_capability_diagnostics(req, ports),
        )

    try:
        records = ports.node_reader.load_node_records()
    except RuntimeError as error:
        findings.append(_finding_from_error(str(error)))
    else:
        try:
            graph = build_graph([_to_spec_node_seed(record) for record in records])
            report = validate_graph_and_deps(
                graph,
                issue_depends_on_map=None,
                repo_root=ports.repo_root,
                current_repo_slug=resolve_current_repo_slug(ports),
            )
        except RuntimeError as error:
            findings.append(_finding_from_error(str(error)))
        else:
            if report.errors:
                findings.append(_finding_from_error(str(report.errors[0])))
            else:
                if ports.deps_topology_reader is not None:
                    load_node_dependency_resolutions = getattr(
                        ports.deps_topology_reader,
                        "load_node_dependency_resolutions",
                        None,
                    )
                    if callable(load_node_dependency_resolutions):
                        try:
                            raw_node_depends_on_map = _raw_node_depends_on_map(
                                load_node_dependency_resolutions(specdock_dir, graph)
                            )
                            validate_raw_node_dependency_graph(graph, raw_node_depends_on_map)
                        except RuntimeError as error:
                            findings.append(_finding_from_error(str(error)))
                try:
                    validate_required_artifacts_for_graph(graph, repo_root=ports.repo_root)
                except RuntimeError as error:
                    findings.append(_finding_from_error(str(error)))
            for warning in report.warnings:
                _append_unique(warnings, warning)

    stale_pointer = _stale_active_pointer_finding(
        ports,
        specdock_dir=specdock_dir,
        graph=graph,
        warnings=warnings,
    )
    if stale_pointer is not None:
        findings.append(stale_pointer)

    if not any(finding.code == "stale_create_lock" for finding in findings):
        stale_create_lock = _stale_create_lock_finding(specdock_dir)
        if stale_create_lock is not None:
            findings.append(stale_create_lock)

    if has_current_workspace and has_legacy_workspace and not findings:
        _append_unique(warnings, "legacy_cleanup_pending")

    return DoctorResult(
        ok=(len(findings) == 0),
        findings=findings,
        warnings=warnings,
        github_capability_diagnostics=_github_capability_diagnostics(req, ports),
    )
