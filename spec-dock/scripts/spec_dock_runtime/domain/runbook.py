from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from spec_dock_runtime.domain.workflow_state import RunbookAuthority, WorkflowState

WORKFLOW_RUNBOOK_SCHEMA_VERSION = "workflow-runbook-v1"
WorkflowTarget = Literal["issue-planning", "issue-execution"]


@dataclass(frozen=True)
class Runbook:
    schema_version: str
    workflow_target: WorkflowTarget
    state: str
    next_action: str
    reason_code: str
    authority: RunbookAuthority
    commands: tuple[str, ...]
    notes: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    details: tuple[str, ...]
    active_issue_id: str | None
    may_execute_approved_plan: bool = False
    contract_source: str | None = None
    evidence_ledger: str | None = None


def compile_runbook(target: WorkflowTarget, state: WorkflowState) -> Runbook:
    if state.kind == "no-active":
        return _runbook(
            target,
            state,
            next_action="issue-start-required",
            commands=("./spec-dock/scripts/spec-dock issue start <issue-id>",),
            notes=("Start an issue before continuing.",),
            stop_conditions=("No active issue is selected.",),
        )
    if state.kind == "requirement-capture":
        return _runbook(
            target,
            state,
            next_action="requirement-capture-required",
            commands=(
                "./spec-dock/scripts/spec-dock active show",
                "Edit spec-dock/active/issue/requirement.md",
            ),
            notes=("Capture substantive issue requirements and get the required review gate before continuing.",),
            stop_conditions=("Do not classify assurance or start execution from a scaffold requirement.",),
        )
    if state.kind == "classification-required":
        return _runbook(
            target,
            state,
            next_action="assurance-classification-required",
            commands=(
                "./spec-dock/scripts/spec-dock assurance classify --stage requirement",
                "./spec-dock/scripts/spec-dock assurance verify",
            ),
            notes=(
                "Assurance authority is missing or invalid; classify and verify before selecting workflow obligations.",
            ),
            stop_conditions=("Do not start implementation until assurance verification succeeds.",),
        )
    if state.kind == "blocked":
        if state.reason_code in {"plan-missing", "plan-not-executable"}:
            return _runbook(
                target,
                state,
                next_action="issue-planning-required",
                commands=(
                    "./spec-dock/scripts/spec-dock active show",
                    "Edit spec-dock/active/issue/plan.md",
                ),
                notes=("The active issue plan is not an executable workflow contract.",),
                stop_conditions=(
                    "Do not continue issue execution until plan.md contains executable step obligations.",
                ),
            )
        return _runbook(
            target,
            state,
            next_action="issue-planning-required",
            commands=(
                "./spec-dock/scripts/spec-dock active show",
                "Inspect spec-dock/active/issue/requirement.md spec-dock/active/issue/design.md spec-dock/active/issue/plan.md",
            ),
            notes=("The active issue is blocked by a workflow preflight condition.",),
            stop_conditions=("Do not continue issue execution until the blocking condition is resolved.",),
        )
    if target == "issue-execution":
        return _runbook(
            target,
            state,
            next_action="execute-approved-plan",
            commands=(
                "./spec-dock/scripts/spec-dock active show",
                "./spec-dock/scripts/spec-dock assurance verify",
            ),
            notes=(
                f"Use authorized_profile={state.authority.authorized_profile} as the obligation authority.",
                "Execute the approved plan.md in order; record observed evidence in report.md.",
                "lite_candidate is telemetry only unless authorized_profile is lite.",
            ),
            stop_conditions=(
                "Do not reduce obligations based only on lite_candidate.",
                "Do not infer the next step, worker, reviewer, verification, or context packet from runtime guidance.",
            ),
            may_execute_approved_plan=True,
            contract_source="spec-dock/active/issue/plan.md",
            evidence_ledger="spec-dock/active/issue/report.md",
        )
    return _runbook(
        target,
        state,
        next_action="planning-ready",
        commands=("./spec-dock/scripts/spec-dock active show",),
        notes=(
            f"Use authorized_profile={state.authority.authorized_profile} as the obligation authority.",
            "lite_candidate is telemetry only unless authorized_profile is lite.",
        ),
        stop_conditions=("Do not reduce obligations based only on lite_candidate.",),
    )


def _runbook(
    target: WorkflowTarget,
    state: WorkflowState,
    *,
    next_action: str,
    commands: tuple[str, ...],
    notes: tuple[str, ...],
    stop_conditions: tuple[str, ...],
    may_execute_approved_plan: bool = False,
    contract_source: str | None = None,
    evidence_ledger: str | None = None,
) -> Runbook:
    return Runbook(
        schema_version=WORKFLOW_RUNBOOK_SCHEMA_VERSION,
        workflow_target=target,
        state=state.kind,
        next_action=next_action,
        reason_code=state.reason_code,
        authority=state.authority,
        commands=commands,
        notes=notes,
        stop_conditions=stop_conditions,
        details=state.details,
        active_issue_id=state.active_issue_id,
        may_execute_approved_plan=may_execute_approved_plan,
        contract_source=contract_source,
        evidence_ledger=evidence_ledger,
    )
