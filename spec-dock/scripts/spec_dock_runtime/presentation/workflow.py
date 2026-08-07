from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from spec_dock_runtime.presentation.contracts import CliText

if TYPE_CHECKING:
    from spec_dock_runtime.application.contracts import WorkflowResult
    from spec_dock_runtime.domain.runbook import Runbook
    from spec_dock_runtime.domain.workflow_state import WorkflowState


def render_workflow_json(result: WorkflowResult) -> str:
    return json.dumps(_payload(result), ensure_ascii=False, separators=(",", ":"))


def render_workflow_text(result: WorkflowResult) -> CliText:
    state = result.state
    lines = [
        f"workflow {result.operation}: {state.kind}",
        f"active_issue: {state.active_issue_id or '(none)'}",
        f"reason_code: {state.reason_code}",
        f"artifact_readiness: {state.artifact_readiness}",
        f"authorized_profile: {state.authority.authorized_profile}",
        f"lite_candidate: {_bool_text(state.authority.lite_candidate)}",
        f"obligation_source: {state.authority.obligation_source}",
    ]
    if state.details:
        lines.append("details:")
        lines.extend(f"- {detail}" for detail in state.details)
    return CliText(stdout_lines=lines, stderr_lines=[], warnings=[])


def render_workflow_markdown(result: WorkflowResult) -> CliText:
    if result.runbook is None:
        return render_workflow_text(result)
    runbook = result.runbook
    lines = [
        f"# Guidance: {runbook.workflow_target}",
        "",
        f"- state: {runbook.state}",
        f"- next_action: {runbook.next_action}",
        f"- reason_code: {runbook.reason_code}",
        f"- active_issue: {runbook.active_issue_id or '(none)'}",
        f"- may_execute_approved_plan: {_bool_text(runbook.may_execute_approved_plan)}",
        "- authority: "
        f"authorized_profile={runbook.authority.authorized_profile}, "
        f"lite_candidate={_bool_text(runbook.authority.lite_candidate)}, "
        f"obligation_source={runbook.authority.obligation_source}",
        "",
        "## Commands",
    ]
    lines.extend(f"- `{command}`" for command in runbook.commands)
    lines.extend(["", "## Notes"])
    lines.extend(f"- {note}" for note in runbook.notes)
    if runbook.contract_source is not None or runbook.evidence_ledger is not None:
        lines.extend(["", "## Contract"])
        if runbook.contract_source is not None:
            lines.append(f"- contract_source: {runbook.contract_source}")
        if runbook.evidence_ledger is not None:
            lines.append(f"- evidence_ledger: {runbook.evidence_ledger}")
    if runbook.details:
        lines.extend(["", "## Details"])
        lines.extend(f"- {detail}" for detail in runbook.details)
    lines.extend(["", "## Stop Conditions"])
    lines.extend(f"- {condition}" for condition in runbook.stop_conditions)
    if result.projection is not None:
        lines.extend([
            "",
            "## Projection",
            "- audience: human",
            "- authority: non-canonical",
            "- note: Human-facing projection; not agent handoff authority.",
            f"- refresh_command: `./spec-dock/scripts/spec-dock guidance {runbook.workflow_target}`",
            f"- written: {_bool_text(result.projection.written)}",
        ])
        lines.extend(f"- `{path}`" for path in result.projection.paths)
        if result.projection.errors:
            lines.extend(["", "## Projection Errors"])
            lines.extend(f"- {error}" for error in result.projection.errors)
    return CliText(stdout_lines=lines, stderr_lines=[], warnings=[])


def _payload(result: WorkflowResult) -> dict[str, Any]:
    if result.runbook is not None:
        payload = _runbook_payload(result.runbook)
        if result.projection is not None:
            payload["projection"] = _projection_payload(result.projection)
        return payload
    return {
        "operation": result.operation,
        **_state_payload(result.state),
    }


def _runbook_payload(runbook: Runbook) -> dict[str, Any]:
    payload = {
        "schema_version": runbook.schema_version,
        "workflow_target": runbook.workflow_target,
        "state": runbook.state,
        "next_action": runbook.next_action,
        "reason_code": runbook.reason_code,
        "active_issue_id": runbook.active_issue_id,
        "may_execute_approved_plan": runbook.may_execute_approved_plan,
        "contract_source": runbook.contract_source,
        "evidence_ledger": runbook.evidence_ledger,
        "authority": {
            "authorized_profile": runbook.authority.authorized_profile,
            "lite_candidate": runbook.authority.lite_candidate,
            "obligation_source": runbook.authority.obligation_source,
        },
        "commands": list(runbook.commands),
        "notes": list(runbook.notes),
        "stop_conditions": list(runbook.stop_conditions),
        "details": list(runbook.details),
    }
    return payload


def _state_payload(state: WorkflowState) -> dict[str, Any]:
    return {
        "state": state.kind,
        "active_issue_id": state.active_issue_id,
        "reason_code": state.reason_code,
        "artifact_readiness": state.artifact_readiness,
        "authority": {
            "authorized_profile": state.authority.authorized_profile,
            "lite_candidate": state.authority.lite_candidate,
            "obligation_source": state.authority.obligation_source,
        },
        "details": list(state.details),
    }


def _projection_payload(projection: Any) -> dict[str, Any]:
    return {
        "written": projection.written,
        "paths": list(projection.paths),
        "errors": list(projection.errors),
        "audience": "human",
        "authority": "non-canonical",
    }


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
