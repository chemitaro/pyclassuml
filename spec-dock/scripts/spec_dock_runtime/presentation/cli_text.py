from __future__ import annotations

import json

from ..application.contracts import (
    ActiveClearResult,
    ActiveSetResult,
    ActiveViewResult,
    CloseNodeResult,
    DeleteNodeResult,
    CreateDiscussionDocResult,
    CreateNodeResult,
    DepsCheckResult,
    DoctorResult,
    ImportNodeResult,
    IssueFinishResult,
    IssueStartResult,
    MutateDepsError,
    MutateDepsResult,
    PostMutationSyncOutcome,
    SyncCommandResult,
    ValidationResult,
    WorktreeCreateResult,
)
from .contracts import CliText


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
    if result.ok:
        return CliText(
            stdout_lines=["spec-dock: ok (doctor) findings=0"],
            stderr_lines=[],
            warnings=warnings,
        )

    stderr_lines = [f"spec-dock: doctor: findings={len(result.findings)}"]
    for finding in result.findings:
        stderr_lines.append(f"- [{finding.code}] {finding.message}")
        for guidance in finding.guidance:
            stderr_lines.append(f"  -> {guidance}")

    return CliText(
        stdout_lines=[],
        stderr_lines=stderr_lines,
        warnings=warnings,
    )


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
        line = (
            "spec-dock: ok (new epic) "
            f"id={node.id} initiative={node.initiative_id} path={rel}{gh}"
        )
    else:
        line = (
            "spec-dock: ok (new issue) "
            f"id={node.id} epic={node.epic_id} initiative={node.initiative_id} path={rel}{gh}"
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


def render_new_doc_text(result: CreateDiscussionDocResult) -> CliText:
    rel = _rel_path_for_output(result.path.as_posix())
    line = (
        "spec-dock: ok (new doc) "
        f"type={result.doc_type} id={result.doc_id} scope={result.scope_node_id} path={rel}"
    )
    return CliText(stdout_lines=[line], stderr_lines=[], warnings=list(result.warnings))


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
        (
            f"spec-dock: ok (deps {result.action}) "
            f"from={result.from_id} to={result.to_id} result={result.result}"
        )
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
    stderr_lines = [
        (
            f"spec-dock: error (deps {error.action}) "
            f"from={error.from_id} to={error.to_id} code={error.code}"
        )
    ]
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

    all_none = (
        result.initiative.id is None
        and result.epic.id is None
        and result.issue.id is None
    )
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
        (
            "spec-dock: ok (issue start) "
            f"target={result.target_display} initiative={ini} epic={epic} issue={issue}"
        )
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
        (
            "spec-dock: ok (worktree create) "
            f"id={result.id} branch={result.branch_name} path={result.worktree_path}"
        ),
        (
            "spec-dock: worktree bootstrap "
            f"status={result.bootstrap_status} command={result.bootstrap_command or '-'}"
        ),
    ]
    return CliText(stdout_lines=stdout_lines, stderr_lines=[], warnings=list(result.warnings))


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
        stderr_lines=[
            f"spec-dock: blocked (delete) status={result.status} target={result.target_id or '(none)'}"
        ],
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
        f"{result.write_result.dashboard_md_path}"
        if result.write_result is not None
        else "spec-dock: ok (sync)"
    )
    stderr_lines: list[str] = []
    if result.state.deps_preflight_error:
        stderr_lines.append(result.state.deps_preflight_error)
    if result.active_update is not None:
        if result.active_update.applied:
            stderr_lines.append(f"spec-dock: sync: active updated ({result.active_update.reason or 'updated'})")
        else:
            stderr_lines.append(f"spec-dock: sync: active unchanged ({result.active_update.reason or 'unchanged'})")
    return CliText(stdout_lines=[line], stderr_lines=stderr_lines, warnings=list(result.state.warnings))
