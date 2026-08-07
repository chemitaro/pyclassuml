from __future__ import annotations

import json
from typing import TYPE_CHECKING

from spec_dock_runtime.presentation.contracts import CliText

if TYPE_CHECKING:
    from spec_dock_runtime.application.contracts import (
        ActiveClearResult,
        ActiveSetResult,
        ActiveViewResult,
        ArtifactImportError,
        ArtifactImportResult,
        CloseNodeResult,
        CreateArtifactDocResult,
        CreateNodeResult,
        DeleteNodeResult,
        DepsCheckResult,
        DoctorResult,
        FileArtifactImportError,
        FileArtifactImportResult,
        ImportNodeResult,
        IssueFinishResult,
        IssueStartResult,
        MutateDepsError,
        MutateDepsResult,
        PostMutationSyncOutcome,
        SyncCommandResult,
        ValidationResult,
        WorkbenchCopyError,
        WorkbenchCopyResult,
        WorktreeCommandError,
        WorktreeCreateResult,
        WorktreeListResult,
        WorktreeRecordView,
        WorktreeRemoveResult,
        WorktreeShowResult,
    )


def _doctor_warning_message(code: str) -> str:
    if code == "legacy_cleanup_pending":
        return (
            "legacy '.spec-dock/' is still present. Continue with current 'spec-dock/' "
            "and remove legacy manually after migration is confirmed."
        )
    return code


def render_validate_text(result: ValidationResult) -> CliText:
    if result.report.errors:
        return CliText(
            stdout_lines=[],
            stderr_lines=[result.report.errors[0]],
            warnings=result.report.warnings,
        )
    return CliText(
        stdout_lines=[f"spec-dock: ok (validate) nodes={result.checked_node_count}"],
        stderr_lines=[],
        warnings=result.report.warnings,
    )


def render_doctor_text(result: DoctorResult) -> CliText:
    warnings = [_doctor_warning_message(warning) for warning in result.warnings]
    capability_lines = _render_github_capability_diagnostics(result)
    if result.ok:
        return CliText(
            stdout_lines=[
                "spec-dock: ok (doctor) findings=0",
                *capability_lines,
            ],
            stderr_lines=[],
            warnings=warnings,
        )

    stderr_lines = [f"spec-dock: doctor: findings={len(result.findings)}"]
    for finding in result.findings:
        stderr_lines.append(f"- [{finding.code}] {finding.message}")
        for guidance in finding.guidance:
            stderr_lines.append(f"  -> {guidance}")
    stderr_lines.extend(capability_lines)

    return CliText(
        stdout_lines=[],
        stderr_lines=stderr_lines,
        warnings=warnings,
    )


def _render_github_capability_diagnostics(result: DoctorResult) -> list[str]:
    diagnostics = list(result.github_capability_diagnostics)
    if not diagnostics:
        return []
    lines = [f"spec-dock: github capability diagnostics={len(diagnostics)}"]
    for diagnostic in diagnostics:
        stderr_hash = f" stderr_sha256={diagnostic.stderr_sha256}" if diagnostic.stderr_sha256 else ""
        lines.append(
            f"- [github:{diagnostic.group}] "
            f"code={diagnostic.code} "
            f"capability={diagnostic.capability} "
            f"status={diagnostic.status} "
            f"api={diagnostic.api} "
            f"token_source={diagnostic.token_source} "
            f"severity={diagnostic.severity} "
            f"recommended_next_action={diagnostic.recommended_next_action} "
            f"secret_redacted={str(diagnostic.secret_redacted).lower()}"
            f"{stderr_hash}"
        )
    return lines


def _rel_path_for_output(path_text: str) -> str:
    parts = path_text.replace("\\", "/").split("/")
    if "spec-dock" in parts:
        index = parts.index("spec-dock")
        return "/".join(parts[index:])
    return path_text


def _post_sync_stdout_line(outcome: PostMutationSyncOutcome | None, *, label: str) -> str | None:
    if outcome is None:
        return None
    if outcome.failed:
        return None
    if outcome.skipped_reason is not None:
        return f"spec-dock: skipped ({label} auto-sync) reason={outcome.skipped_reason}"
    return f"spec-dock: ok ({label} auto-sync)"


def _post_sync_stderr_lines(
    outcome: PostMutationSyncOutcome | None,
    *,
    label: str,
    target: str,
) -> list[str]:
    if outcome is None or not outcome.failed:
        return []
    return [f"spec-dock: failed ({label} auto-sync) {target}", *outcome.guidance]


def _post_sync_warnings(
    warnings: list[str],
    outcome: PostMutationSyncOutcome | None,
) -> list[str]:
    return [*warnings, *list(outcome.warnings if outcome else [])]


def render_new_node_text(result: CreateNodeResult) -> CliText:
    node = result.node
    rel = _rel_path_for_output(node.path.as_posix())
    gh = f" github=#{node.github_issue_number}" if node.github_issue_number is not None else ""

    if node.kind == "initiative":
        line = f"spec-dock: ok (new initiative) id={node.id} path={rel}{gh}"
    elif node.kind == "epic":
        line = f"spec-dock: ok (new epic) id={node.id} initiative={node.initiative_id} path={rel}{gh}"
    else:
        line = (
            f"spec-dock: ok (new issue) id={node.id} epic={node.epic_id} initiative={node.initiative_id} path={rel}{gh}"
        )
    stdout_lines = [line]
    post_sync_line = _post_sync_stdout_line(result.post_sync, label=f"new {node.kind}")
    if post_sync_line is not None:
        stdout_lines.append(post_sync_line)
    return CliText(
        stdout_lines=stdout_lines,
        stderr_lines=_post_sync_stderr_lines(
            result.post_sync,
            label=f"new {node.kind}",
            target=f"id={node.id}",
        ),
        warnings=_post_sync_warnings(list(result.warnings), result.post_sync),
    )


def render_new_artifact_text(result: CreateArtifactDocResult) -> CliText:
    rel = _rel_path_for_output(result.path.as_posix())
    line = (
        "spec-dock: ok (new artifact) "
        f"type={result.artifact_type} id={result.artifact_id} scope={result.scope_node_id} path={rel}"
    )
    return CliText(stdout_lines=[line], stderr_lines=[], warnings=list(result.warnings))


def render_artifact_import_text(result: ArtifactImportResult) -> CliText:
    warning_codes = ",".join(result.warning_codes) if result.warning_codes else "-"
    line = (
        "spec-dock: ok (artifact import chatgpt-output) "
        f"import_kind={result.import_kind} storage_identity={result.storage_identity} "
        f"artifact_id={result.artifact_id} scope_id={result.scope_id} "
        f"source={result.source_path.as_posix()} destination={result.destination_path.as_posix()} "
        f"sha256={result.sha256} byte_count={result.byte_count} "
        f"committed={_bool_text(result.committed)} cleanup_state={result.cleanup_state} "
        f"warning_codes={warning_codes}"
    )
    return CliText(stdout_lines=[line], stderr_lines=[], warnings=list(result.warning_codes))


def render_artifact_import_json(result: ArtifactImportResult) -> CliText:
    payload = {
        "status": "ok",
        "import_kind": result.import_kind,
        "storage_identity": result.storage_identity,
        "artifact_id": result.artifact_id,
        "scope_id": result.scope_id,
        "source": result.source_path.as_posix(),
        "destination": result.destination_path.as_posix(),
        "sha256": result.sha256,
        "byte_count": result.byte_count,
        "committed": result.committed,
        "cleanup_state": result.cleanup_state,
        "warning_codes": list(result.warning_codes),
    }
    return CliText(stdout_lines=[json.dumps(payload, ensure_ascii=False, indent=2)], stderr_lines=[], warnings=[])


def render_artifact_import_error_text(error: ArtifactImportError) -> CliText:
    return CliText(
        stdout_lines=[],
        stderr_lines=[
            "spec-dock: error (artifact import chatgpt-output) "
            f"import_kind=chatgpt-output storage_identity=blank code={error.code} "
            f"committed=false cleanup_state={error.cleanup_state}"
        ],
        warnings=[],
    )


def render_artifact_import_error_json(error: ArtifactImportError) -> CliText:
    payload = {
        "status": "error",
        "import_kind": "chatgpt-output",
        "storage_identity": "blank",
        "code": error.code,
        "committed": False,
        "cleanup_state": error.cleanup_state,
    }
    return CliText(stdout_lines=[json.dumps(payload, ensure_ascii=False, indent=2)], stderr_lines=[], warnings=[])


def render_file_artifact_import_text(result: FileArtifactImportResult) -> CliText:
    warning_codes = ",".join(result.warning_codes) if result.warning_codes else "-"
    dynamic = {
        "target_id": result.target_id,
        "artifact_id": result.artifact_id,
        "source": result.source,
        "destination": result.destination.as_posix(),
    }
    quoted = {key: json.dumps(value, ensure_ascii=True) for key, value in dynamic.items()}
    line = (
        "spec-dock: ok (artifact import file) "
        f"import_kind={result.import_kind} storage_identity={result.storage_identity} "
        f"target_kind={result.target_kind} target_id={quoted['target_id']} "
        f"artifact_id={quoted['artifact_id']} source_visibility={result.source_visibility} "
        f"source={quoted['source']} destination={quoted['destination']} "
        f"committed={_bool_text(result.committed)} publication_state={result.publication_state} "
        f"cleanup_state={result.cleanup_state} retry_disposition={result.retry_disposition} "
        f"canonical={_bool_text(result.canonical)} warning_codes={warning_codes}"
    )
    return CliText(stdout_lines=[line], stderr_lines=[], warnings=list(result.warning_codes))


def render_file_artifact_import_json(result: FileArtifactImportResult) -> CliText:
    payload = {
        "status": "ok",
        "import_kind": result.import_kind,
        "storage_identity": result.storage_identity,
        "target_kind": result.target_kind,
        "target_id": result.target_id,
        "artifact_id": result.artifact_id,
        "source_visibility": result.source_visibility,
        "source": result.source,
        "destination": result.destination.as_posix(),
        "committed": result.committed,
        "publication_state": result.publication_state,
        "cleanup_state": result.cleanup_state,
        "warning_codes": list(result.warning_codes),
        "retry_disposition": result.retry_disposition,
        "canonical": result.canonical,
    }
    return CliText(stdout_lines=[json.dumps(payload, ensure_ascii=False, indent=2)], stderr_lines=[], warnings=[])


def render_file_artifact_import_error_text(error: FileArtifactImportError) -> CliText:
    return CliText(
        stdout_lines=[],
        stderr_lines=[
            "spec-dock: error (artifact import file) "
            f"import_kind=file storage_identity=generic code={error.code} "
            "committed=false publication_state=not_committed "
            f"cleanup_state={error.cleanup_state} retry_disposition=safe_after_remediation canonical=false"
        ],
        warnings=[],
    )


def render_file_artifact_import_error_json(error: FileArtifactImportError) -> CliText:
    payload = {
        "status": "error",
        "import_kind": "file",
        "storage_identity": "generic",
        "code": error.code,
        "committed": False,
        "publication_state": error.publication_state,
        "cleanup_state": error.cleanup_state,
        "retry_disposition": error.retry_disposition,
        "canonical": error.canonical,
    }
    return CliText(stdout_lines=[json.dumps(payload, ensure_ascii=False, indent=2)], stderr_lines=[], warnings=[])


def render_import_text(result: ImportNodeResult) -> CliText:
    node = result.node
    rel = _rel_path_for_output(node.path.as_posix())
    issue_number = int(result.imported_issue.issue_number)

    if node.kind == "initiative":
        line = f"spec-dock: ok (import initiative) id={node.id} path={rel} github=#{issue_number}"
    elif node.kind == "epic":
        line = (
            "spec-dock: ok (import epic) "
            f"id={node.id} initiative={node.initiative_id} path={rel} github=#{issue_number}"
        )
    else:
        line = (
            "spec-dock: ok (import issue) "
            f"id={node.id} epic={node.epic_id} initiative={node.initiative_id} path={rel} github=#{issue_number}"
        )

    warnings = list(result.warnings)
    for warning in result.post_import_sync.state.warnings:
        if warning not in warnings:
            warnings.append(warning)
    if result.post_import_sync.artifact_failure is not None:
        warnings.append("import_post_sync_failed")
    return CliText(stdout_lines=[line], stderr_lines=[], warnings=warnings)


def render_deps_check_text(result: DepsCheckResult) -> CliText:
    target_id = result.inspection.target_id.value
    target_status = result.inspection.issue_statuses.get(target_id)
    authority = target_status.authority if target_status is not None else "unknown"
    effective_status = target_status.effective_status if target_status is not None else "unknown"
    source = target_status.source if target_status is not None else "unknown"
    stale = "true" if (target_status.stale if target_status is not None else True) else "false"
    last_sync_at = target_status.last_sync_at if target_status is not None else None
    last_sync_display = last_sync_at if isinstance(last_sync_at, str) and last_sync_at.strip() else "-"
    blockers = list(result.inspection.evaluation.blockers)
    if result.inspection.evaluation.ready:
        return CliText(
            stdout_lines=[
                (
                    "spec-dock: ok (deps check) "
                    f"target={target_id} "
                    f"authority={authority} effective_status={effective_status} "
                    f"source={source} stale={stale} last_sync_at={last_sync_display} "
                    "ready=true blockers=0"
                )
            ],
            stderr_lines=[],
            warnings=list(result.warnings),
        )
    return CliText(
        stdout_lines=[],
        stderr_lines=[
            (
                "spec-dock: blocked (deps check) "
                f"target={target_id} "
                f"authority={authority} effective_status={effective_status} "
                f"source={source} stale={stale} last_sync_at={last_sync_display} "
                f"ready=false blockers={len(blockers)}"
            ),
            *[f"- {blocker}" for blocker in blockers],
        ],
        warnings=list(result.warnings),
    )


def render_deps_mutation_text(result: MutateDepsResult) -> CliText:
    stdout_lines = [
        (f"spec-dock: ok (deps {result.action}) from={result.from_id} to={result.to_id} result={result.result}")
    ]
    post_sync_line = _post_sync_stdout_line(result.post_sync, label=f"deps {result.action}")
    if post_sync_line is not None:
        stdout_lines.append(post_sync_line)
    return CliText(
        stdout_lines=stdout_lines,
        stderr_lines=_post_sync_stderr_lines(
            result.post_sync,
            label=f"deps {result.action}",
            target=f"from={result.from_id} to={result.to_id}",
        ),
        warnings=_post_sync_warnings(list(result.warnings), result.post_sync),
    )


def render_deps_mutation_error_text(error: MutateDepsError) -> CliText:
    stderr_lines = [(f"spec-dock: error (deps {error.action}) from={error.from_id} to={error.to_id} code={error.code}")]
    if error.detail:
        stderr_lines.append(f"- {error.detail}")
    return CliText(
        stdout_lines=[],
        stderr_lines=stderr_lines,
        warnings=[],
    )


def render_active_show_text(result: ActiveViewResult) -> CliText:
    def _format_entry(entry_id: str | None, entry_path: str | None) -> str:
        if entry_id and entry_path:
            return f"{entry_id} ({entry_path})"
        if entry_id:
            return entry_id
        return "(none)"

    all_none = result.initiative.id is None and result.epic.id is None and result.issue.id is None
    if all_none:
        stdout_lines = [
            "spec-dock: active: (not set)",
            "fallback: spec-dock/active/{initiative,epic,issue} -> spec-dock/system/active-none/{initiative,epic,issue}",
            "next: spec-dock/scripts/spec-dock active set <target>",
        ]
    else:
        stdout_lines = [
            f"initiative: {_format_entry(result.initiative.id, result.initiative.path)}",
            f"epic: {_format_entry(result.epic.id, result.epic.path)}",
            f"issue: {_format_entry(result.issue.id, result.issue.path)}",
        ]

    return CliText(stdout_lines=stdout_lines, stderr_lines=[], warnings=list(result.warnings))


def render_active_set_text(result: ActiveSetResult, *, target_display: str) -> CliText:
    ini = result.selection.initiative_id or "(none)"
    epic = result.selection.epic_id or "(none)"
    issue = result.selection.issue_id or "(none)"
    stdout_lines = [
        f"spec-dock: ok (active set) target={target_display} initiative={ini} epic={epic} issue={issue}",
    ]
    if result.branch is not None:
        stdout_lines.append(f"spec-dock: ok (active checkout) branch={result.branch.desired}")
    return CliText(stdout_lines=stdout_lines, stderr_lines=[], warnings=list(result.warnings))


def render_active_clear_text(result: ActiveClearResult) -> CliText:
    del result
    return CliText(stdout_lines=["spec-dock: ok (active clear)"], stderr_lines=[], warnings=[])


def render_close_text(result: CloseNodeResult, *, target_display: str) -> CliText:
    state = str(result.issue_snapshot.state).strip().upper() or "UNKNOWN"
    stdout_lines = [
        (
            "spec-dock: ok (close) "
            f"target={target_display} node={result.node_id} kind={result.node_kind} "
            f"github=#{result.github_issue_number} state={state} already_closed={'true' if result.already_closed else 'false'}"
        )
    ]
    post_sync_line = _post_sync_stdout_line(result.post_sync, label="close")
    if post_sync_line is not None:
        stdout_lines.append(post_sync_line)
    return CliText(
        stdout_lines=stdout_lines,
        stderr_lines=_post_sync_stderr_lines(result.post_sync, label="close", target=f"target={target_display}"),
        warnings=_post_sync_warnings(list(result.warnings), result.post_sync),
    )


def render_issue_start_text(result: IssueStartResult) -> CliText:
    selection = result.active_set.selection
    ini = selection.initiative_id or "(none)"
    epic = selection.epic_id or "(none)"
    issue = selection.issue_id or "(none)"
    stdout_lines = [
        (f"spec-dock: ok (issue start) target={result.target_display} initiative={ini} epic={epic} issue={issue}")
    ]
    if result.active_set.branch is not None:
        stdout_lines.append(f"spec-dock: ok (issue checkout) branch={result.active_set.branch.desired}")
    return CliText(stdout_lines=stdout_lines, stderr_lines=[], warnings=list(result.warnings))


def render_issue_finish_text(result: IssueFinishResult) -> CliText:
    stdout_lines = [
        (
            "spec-dock: ok (issue finish) "
            f"issue={result.issue_id} github=#{result.github_issue_number} state=CLOSED "
            f"active_cleared={'true' if result.active_cleared else 'false'} "
            f"already_closed={'true' if result.already_closed else 'false'}"
        )
    ]
    post_sync_line = _post_sync_stdout_line(result.post_sync, label="issue finish")
    if post_sync_line is not None:
        stdout_lines.append(post_sync_line)
    return CliText(
        stdout_lines=stdout_lines,
        stderr_lines=_post_sync_stderr_lines(
            result.post_sync,
            label="issue finish",
            target=f"issue={result.issue_id}",
        ),
        warnings=_post_sync_warnings(list(result.warnings), result.post_sync),
    )


def render_worktree_create_text(result: WorktreeCreateResult) -> CliText:
    stdout_lines = [
        (f"spec-dock: ok (worktree create) id={result.id} branch={result.branch_name} path={result.worktree_path}"),
        (f"spec-dock: worktree bootstrap status={result.bootstrap_status} command={result.bootstrap_command or '-'}"),
    ]
    return CliText(stdout_lines=stdout_lines, stderr_lines=[], warnings=list(result.warnings))


def render_workbench_copy_text(result: WorkbenchCopyResult) -> CliText:
    return CliText(
        stdout_lines=[
            (
                "spec-dock: ok (workbench copy) "
                f"scope={result.scope_id} source={result.source_worktree.id} target={result.target_worktree.id} "
                "experimental=true canonical=false disposable=true one_shot=true sync=false"
            )
        ],
        stderr_lines=[],
        warnings=[],
    )


def render_workbench_copy_json(result: WorkbenchCopyResult) -> CliText:
    payload = {
        "status": "ok",
        "command": "copy",
        "scope": result.scope_id,
        "source_worktree": result.source_worktree.id,
        "target_worktree": result.target_worktree.id,
        "target_workbench_path": str(result.target_workbench_path),
        "experimental": result.experimental,
        "canonical": result.canonical,
        "disposable": result.disposable,
        "one_shot": result.one_shot,
        "sync": result.sync,
    }
    return CliText(stdout_lines=[json.dumps(payload, ensure_ascii=False, indent=2)], stderr_lines=[], warnings=[])


def render_workbench_copy_error_text(error: WorkbenchCopyError) -> CliText:
    side = f" side={error.side}" if error.side is not None else ""
    return CliText(
        stdout_lines=[],
        stderr_lines=[
            "spec-dock: error (workbench copy) "
            f"code={error.code}{side} mutation_started={_bool_text(error.mutation_started)} "
            "experimental=true canonical=false disposable=true one_shot=true sync=false"
        ],
        warnings=[],
    )


def render_workbench_copy_error_json(error: WorkbenchCopyError) -> CliText:
    payload = {
        "status": "error",
        "command": "copy",
        "code": error.code,
        "side": error.side,
        "mutation_started": error.mutation_started,
        "experimental": True,
        "canonical": False,
        "disposable": True,
        "one_shot": True,
        "sync": False,
    }
    return CliText(stdout_lines=[json.dumps(payload, ensure_ascii=False, indent=2)], stderr_lines=[], warnings=[])


def render_worktree_list_text(result: WorktreeListResult) -> CliText:
    lines = ["spec-dock: worktrees"]
    for item in result.worktrees:
        blockers = ",".join(item.remove_blockers) if item.remove_blockers else "-"
        lines.append(
            "  "
            f"id={item.id} path={item.path} branch={item.branch or '-'} "
            f"managed={_bool_text(item.managed)} main={_bool_text(item.main)} "
            f"current={_bool_text(item.current)} removable={_bool_text(item.removable)} "
            f"origin={item.origin} classification_reason={item.classification_reason} "
            f"remove_blockers={blockers}"
        )
    return CliText(stdout_lines=lines, stderr_lines=[], warnings=list(result.warnings))


def render_worktree_show_text(result: WorktreeShowResult) -> CliText:
    item = result.worktree
    blockers = ",".join(item.remove_blockers) if item.remove_blockers else "-"
    return CliText(
        stdout_lines=[
            (
                "spec-dock: worktree "
                f"id={item.id} path={item.path} branch={item.branch or '-'} "
                f"managed={_bool_text(item.managed)} main={_bool_text(item.main)} "
                f"current={_bool_text(item.current)} removable={_bool_text(item.removable)} "
                f"origin={item.origin} classification_reason={item.classification_reason} "
                f"remove_blockers={blockers}"
            )
        ],
        stderr_lines=[],
        warnings=list(result.warnings),
    )


def render_worktree_remove_text(result: WorktreeRemoveResult) -> CliText:
    blockers = ",".join(result.resolved_target.remove_blockers) if result.resolved_target.remove_blockers else "-"
    return CliText(
        stdout_lines=[
            (
                "spec-dock: ok (worktree remove) "
                f"id={result.resolved_target.id} path={result.resolved_target.path} "
                f"branch={result.resolved_target.branch or '-'} "
                f"managed={_bool_text(result.resolved_target.managed)} "
                f"origin={result.resolved_target.origin} "
                f"classification_reason={result.resolved_target.classification_reason} "
                f"remove_blockers={blockers} "
                f"removed_record={_bool_text(result.removed_record)} "
                f"removed_directory={_bool_text(result.removed_directory)} "
                f"branch_deleted={_bool_text(result.branch_deleted)}"
            )
        ],
        stderr_lines=[],
        warnings=list(result.warnings),
    )


def render_worktree_list_json(result: WorktreeListResult) -> CliText:
    payload = {
        "status": "ok",
        "command": "list",
        "warnings": list(result.warnings),
        "worktrees": [_worktree_payload(item) for item in result.worktrees],
    }
    return CliText(stdout_lines=[json.dumps(payload, ensure_ascii=False, indent=2)], stderr_lines=[], warnings=[])


def render_worktree_show_json(result: WorktreeShowResult) -> CliText:
    payload = {
        "status": "ok",
        "command": "show",
        "target": result.target,
        "warnings": list(result.warnings),
        "worktree": _worktree_payload(result.worktree),
    }
    return CliText(stdout_lines=[json.dumps(payload, ensure_ascii=False, indent=2)], stderr_lines=[], warnings=[])


def render_worktree_remove_json(result: WorktreeRemoveResult) -> CliText:
    payload = {
        "status": "ok",
        "command": "remove",
        "target": result.target,
        "warnings": list(result.warnings),
        "resolved_target": _worktree_payload(result.resolved_target),
        "removed_record": result.removed_record,
        "removed_directory": result.removed_directory,
        "branch_deleted": result.branch_deleted,
    }
    return CliText(stdout_lines=[json.dumps(payload, ensure_ascii=False, indent=2)], stderr_lines=[], warnings=[])


def render_worktree_error_json(error: WorktreeCommandError) -> CliText:
    payload: dict[str, object] = {
        "status": "error",
        "command": error.command,
        "warnings": list(error.warnings),
        "error": {
            "code": error.code,
            "message": error.message,
        },
    }
    if error.target is not None:
        payload["target"] = error.target
    if error.candidates:
        payload["candidates"] = [_worktree_payload(item) for item in error.candidates]
    if error.worktree is not None:
        payload["worktree"] = _worktree_payload(error.worktree)
    if error.remove_blockers:
        payload["remove_blockers"] = list(error.remove_blockers)
    if error.git_error is not None:
        payload["git_error"] = error.git_error
    if error.removed_record is not None:
        payload["removed_record"] = error.removed_record
    if error.removed_directory is not None:
        payload["removed_directory"] = error.removed_directory
    return CliText(stdout_lines=[json.dumps(payload, ensure_ascii=False, indent=2)], stderr_lines=[], warnings=[])


def render_worktree_error_text(error: WorktreeCommandError) -> CliText:
    details: list[str] = [f"error: {error.message}"]
    if error.remove_blockers:
        details.append(f"remove_blockers={','.join(error.remove_blockers)}")
    if error.candidates:
        details.append("candidates=" + ",".join(f"{item.id}:{item.path}" for item in error.candidates))
    if error.git_error:
        details.append(error.git_error)
    return CliText(stdout_lines=[], stderr_lines=details, warnings=list(error.warnings))


def _worktree_payload(item: WorktreeRecordView) -> dict[str, object]:
    return {
        "id": item.id,
        "path": str(item.path),
        "basename": item.basename,
        "branch": item.branch,
        "head": item.head,
        "managed": item.managed,
        "managed_classification_available": item.managed_classification_available,
        "classification_reason": item.classification_reason,
        "origin": item.origin,
        "main": item.main,
        "current": item.current,
        "path_exists": item.path_exists,
        "record_exists": item.record_exists,
        "removable": item.removable,
        "remove_blockers": list(item.remove_blockers),
    }


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _delete_remote_close_payload(result: DeleteNodeResult) -> dict[str, list[str]]:
    if result.remote_close is None:
        return {
            "closed": [],
            "noop_already_closed": [],
            "failed": [],
            "skipped_not_attempted": [],
        }
    return {
        "closed": list(result.remote_close.closed),
        "noop_already_closed": list(result.remote_close.noop_already_closed),
        "failed": list(result.remote_close.failed),
        "skipped_not_attempted": list(result.remote_close.skipped_not_attempted),
    }


def _delete_validation_reasons_payload(result: DeleteNodeResult) -> list[dict[str, str | None]]:
    return [
        {
            "node_id": reason.node_id,
            "code": reason.code,
            "message": reason.message,
        }
        for reason in result.validation_reasons
    ]


def _delete_post_sync_payload(result: DeleteNodeResult) -> dict[str, object] | None:
    outcome = result.post_sync
    if outcome is None:
        return None
    artifact_failure = None
    if outcome.sync_result is not None and outcome.sync_result.artifact_failure is not None:
        artifact_failure = {
            "status": outcome.sync_result.artifact_failure.status,
            "reason": outcome.sync_result.artifact_failure.reason,
        }
    if outcome.failed:
        status = "failed"
    elif outcome.skipped_reason is not None:
        status = "skipped"
    else:
        status = "success"
    return {
        "status": status,
        "failed": outcome.failed,
        "skipped_reason": outcome.skipped_reason,
        "exception_reason": outcome.exception_reason,
        "fatal_warnings": list(outcome.fatal_warnings),
        "warnings": list(outcome.warnings),
        "artifact_failure": artifact_failure,
        "recovery_guidance": list(outcome.guidance),
    }


def _build_delete_json_payload(result: DeleteNodeResult) -> dict[str, object]:
    status = result.status
    blockers = {
        "invalid_selector_combination",
        "invalid_selector_syntax",
        "target_not_found",
        "ambiguous_target",
        "active_conflict",
        "dependency_conflict",
        "recursive_required",
        "confirmation_required",
    }
    if status in blockers:
        return {
            "status": status,
            "target_id": result.target_id,
            "offending_node_ids": list(result.offending_node_ids),
            "validation_reasons": _delete_validation_reasons_payload(result),
        }
    if status == "metadata_validation_failed":
        return {
            "status": status,
            "target_id": result.target_id,
            "offending_node_ids": list(result.offending_node_ids),
            "validation_reasons": _delete_validation_reasons_payload(result),
            "remote_close": _delete_remote_close_payload(result),
        }
    if status == "remote_close_failed":
        return {
            "status": status,
            "target_id": result.target_id,
            "remote_close": _delete_remote_close_payload(result),
            "deleted_node_ids": list(result.deleted_node_ids),
        }
    if status == "local_delete_partial_failure":
        return {
            "status": status,
            "target_id": result.target_id,
            "deleted_node_ids": list(result.deleted_node_ids),
            "remaining_node_ids": list(result.remaining_node_ids),
            "remote_close": _delete_remote_close_payload(result),
            "active_restore_result": result.active_restore_result,
            "recovery_guidance": list(result.recovery_guidance),
            "dependency_scrub_failures": [
                {
                    "node_id": failure.node_id,
                    "edge_target_id": failure.edge_target_id,
                }
                for failure in result.dependency_scrub_failures
            ],
        }
    # `ok`
    payload = {
        "status": status,
        "target_id": result.target_id,
        "deleted_node_ids": list(result.deleted_node_ids),
        "remaining_node_ids": list(result.remaining_node_ids),
        "remote_close": _delete_remote_close_payload(result),
        "active_restore_result": result.active_restore_result,
    }
    post_sync = _delete_post_sync_payload(result)
    if post_sync is not None:
        payload["post_sync"] = post_sync
    return payload


def render_delete_text(result: DeleteNodeResult, *, json_output: bool) -> CliText:
    if json_output:
        return CliText(
            stdout_lines=[json.dumps(_build_delete_json_payload(result), ensure_ascii=False, indent=2)],
            stderr_lines=[],
            warnings=[],
        )

    if result.status == "ok":
        stdout_lines = [f"spec-dock: ok (delete) target={result.target_id}"]
        post_sync_line = _post_sync_stdout_line(result.post_sync, label="delete")
        if post_sync_line is not None:
            stdout_lines.append(post_sync_line)
        return CliText(
            stdout_lines=stdout_lines,
            stderr_lines=_post_sync_stderr_lines(
                result.post_sync,
                label="delete",
                target=f"target={result.target_id}",
            ),
            warnings=_post_sync_warnings(list(result.warnings), result.post_sync),
        )
    return CliText(
        stdout_lines=[],
        stderr_lines=[f"spec-dock: blocked (delete) status={result.status} target={result.target_id or '(none)'}"],
        warnings=list(result.warnings),
    )


def render_sync_text(result: SyncCommandResult) -> CliText:
    if result.artifact_failure is not None:
        stderr_lines = [
            (
                "spec-dock: failed (sync) "
                f"status={result.artifact_failure.status} "
                f"reason={result.artifact_failure.reason}"
            )
        ]
        if result.artifact_failure.status == "failed_partial_or_stale":
            stderr_lines.append("spec-dock: sync: artifacts may be stale or partially written")
        return CliText(
            stdout_lines=[],
            stderr_lines=stderr_lines,
            warnings=list(result.state.warnings),
        )

    line = (
        "spec-dock: ok (sync) "
        f"wrote={result.write_result.index_all_path},"
        f"{result.write_result.tree_all_path},"
        f"{result.write_result.index_todo_path},"
        f"{result.write_result.tree_todo_path},"
        f"{result.write_result.tree_all_puml_path},"
        f"{result.write_result.tree_todo_puml_path},"
        f"{result.write_result.deps_issues_json_path},"
        f"{result.write_result.deps_issues_puml_path},"
        f"{result.write_result.deps_raw_puml_path},"
        f"{result.write_result.dashboard_md_path}"
        if result.write_result is not None
        else "spec-dock: ok (sync)"
    )
    sync_stderr_lines: list[str] = []
    if result.state.deps_preflight_error:
        sync_stderr_lines.append(result.state.deps_preflight_error)
    if result.active_update is not None:
        if result.active_update.applied:
            sync_stderr_lines.append(f"spec-dock: sync: active updated ({result.active_update.reason or 'updated'})")
        else:
            sync_stderr_lines.append(
                f"spec-dock: sync: active unchanged ({result.active_update.reason or 'unchanged'})"
            )
    return CliText(stdout_lines=[line], stderr_lines=sync_stderr_lines, warnings=list(result.state.warnings))
