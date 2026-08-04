<!--
Body-section scaffold only.

For writable SpecDock scopes, create the artifact with:
`./spec-dock/scripts/spec-dock new artifact pr-repair-batch --issue <issue-id> --title "PR Repair Batch"`

The runtime-generated file owns front matter identity and the generated heading.
Do not copy front matter from this skill-local template over the generated file.
-->

## PR / Observation Metadata

- PR URL:
- PR number:
- Repository:
- Base branch:
- Head branch:
- Latest head SHA:
- Observation command:
- Observation final JSON / evidence:
- Observation status:
- Trigger comment id:
- Trigger created_at:
- Trigger boundary:
- Resume metadata:
- New trigger approved: no
- Observation limitation:
- Batch status:

## Batch Purpose

Use this batch to triage review findings, observed Actions CI failures, merge blockers, and observation limitations after PR observation and before repair delegation. The batch separates validity from need-to-fix, groups related concerns, creates repair units when needed, and records residual risk for the final merge-prepared decision. PR observation intentionally does not observe external/non-Actions checks; record GitHub UI or external CI confirmation as residual risk or a human gate when branch protection depends on them.

## Concern Catalog

| concern_id | concern | related_inventory_ids | suspected_root_cause | repair_unit | notes |
| --- | --- | --- | --- | --- | --- |

Add one row per real concern. Leave this table empty when no concern exists.

## Inventory

| ID | source_type | concern | failure_class | evidence | summary | validity | risk_class | need_to_fix | disposition | repair_unit | status | rationale | residual_risk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

Add one row per real review finding, observed Actions CI failure, merge blocker, or observation limitation. Do not keep example rows as active inventory.

## Classification Values

- `validity`: `valid` / `partially-valid` / `false-positive` / `duplicate` / `unknown`
- `failure_class`: `check_failure:<actions_job_or_workflow_name>` / `review_feedback:<topic>` / `merge_conflict` / `base_branch_conflict` / `permission_or_auth` / `external_or_flaky` / `timeout` / `unknown`
- `risk_class`: `blocking` / `material-follow-up` / `minor` / `false-positive` / `duplicate`
- `need_to_fix`: `yes` / `no` / `follow-up` / `human-decision`
- `disposition`: `fix-now` / `follow-up` / `no-action` / `covered-by` / `needs-human`
- `status`: `untriaged` / `triaged` / `unit-needed` / `unit-created` / `implemented` / `reobserved-pass` / `blocked`

## Per-Concern Analysis

### CXXX

- Covered inventory IDs:
- Validity analysis:
- Need-to-fix decision:
- Root cause:
- Options considered:
- Recommended disposition:
- Rationale:
- Residual risk:

## Root-Cause Family and Coupling Analysis

| family_id | root_cause_family | related_concerns | recurrence_class | coupling | evidence_ref | analysis_result |
| --- | --- | --- | --- | --- | --- | --- |

When a `root_cause_family` recurs, re-analyze the current evidence, root-cause
hypothesis, coupling, and prior result. Recurrence alone is not a stop reason.

## Integrated Repair Strategy

- strategy_id:
- covered_family_ids:
- prior_strategy_id:
- strategy_delta:
- bounded_scope:
- validation_plan:
- rollback_plan:
- re_observation_plan:
- residual_risk:

The strategy must be bounded, in scope, supported by current evidence, and
materially different from an ineffective prior strategy. Renaming or repeating
the same strategy is not a strategy delta.

## ChatGPT Consultation Gate

- consultation_required: yes / no
- consultation_required_reason:
- consultation_status: fresh / stale / failed / unavailable / consultation_denied / unsafe
- consultation_id:
- consulted_at:
- bound_head_sha:
- bound_observation_status:
- bound_family_ids:
- bound_strategy_context:
- input_summary_ref:
- recommendation_summary_ref:
- freshness_invalidators:
- open_risks:
- fallback_approval_status: not_requested / approved_for_invocation / fallback_approval_denied / expired
- fallback_invocation_id:
- fallback_approved_by:
- fallback_approved_at:
- fallback_invocation_scope:
- fallback_reason:
- fallback_expires_when:
- fallback_manual_analysis_ref:
- fallback_consumed_at:
- orchestrator_disposition_summary:

Use only sanitized, repository-relative evidence references.
Do not paste raw model conversation, secrets, tokens, or absolute host paths. ChatGPT output is
advisory evidence and never authorizes branch mutation or a repair strategy.

A stale consultation must be refreshed first. Only when consultation and its
defined recovery are hard-unrecoverable may an explicit human approval permit
a one-invocation, local-only fallback. Record its scope, reason, and expiry; do
not represent fallback use as consultation success. A denied, missing, expired,
out-of-scope, or reused fallback approval requires a human gate.

`fallback_approval_denied` is an unconditional stop. An expired or consumed
fallback approval is an unconditional stop. A fallback approval is bound to
exactly one `fallback_invocation_id` and must not be reused. Record the manual
analysis in `fallback_manual_analysis_ref` and the orchestrator disposition
before any bounded worker handoff.

## Orchestrator Disposition

| recommendation_id | orchestrator_disposition | rationale | evidence_refs | scope_effect | resulting_strategy_id | residual_risk |
| --- | --- | --- | --- | --- | --- | --- |

Allowed dispositions are `use`, `partial-use`, `reject`, `defer`, and
`human-gate`. Only the orchestrator may turn dispositioned recommendations into
a bounded worker handoff.

## Repair Queue

| unit_id | source_batch | covered_ids | disposition | risk_class | repair_unit_disc | status | Implementation Plan | Re-observation Result | Residual Risk |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

Add one row per real repair unit. Leave this table empty when no repair unit is needed.

## Unit Discussion Plan

Create a repair unit `disc` for each `fix-now` item and each `needs-human` item that needs implementation analysis, design judgment, or options comparison. The worker must use the repair unit discussion, not raw findings, as the source of truth.

Required repair unit checklist:

- `source_batch`
- `unit_id`
- `covered_ids`
- `source_links`
- `failure_class`
- `risk_class`
- `disposition`
- `Validity Analysis`
- `Need-To-Fix Decision`
- `Root Cause`
- `Options Considered`
- `Recommended Design`
- `Implementation Plan`
- `Validation Plan`
- `Implementation Result`
- `Commit Evidence`
- `Re-observation Result`
- `Residual Risk / Follow-up`

## Iteration Ledger

| iteration_index | head_sha | observation_status | family_ids | recurrence_class | prior_strategy_id | proposed_strategy_id | strategy_delta | consultation_id/status | orchestrator_disposition | action_taken | fix_commit | re_observation_result | continuation_decision | stop_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

`iteration_index` is telemetry only; it does not authorize continuation or
stopping. Each row records the evidence-driven semantic decision for that
iteration.

## Semantic Stop / Human-Gate Conditions

Stop at a human gate when any condition applies:

- Any inventory item remains `untriaged`.
- Any unresolved `needs-human` item remains.
- A blocking repair unit has no bounded material `strategy_delta`, or only the
  same ineffective strategy remains.
- Observation output is not for the latest head SHA.
- Timeout or observation limitation lacks resume metadata.
- Resume would cross the recorded trigger boundary.
- A new trigger would be required but has not been approved.
- Scope expansion, requirement expansion, breaking change, migration, secret, deployment setting, permission/auth, external/flaky, or ambiguous review intent is involved.
- Current evidence is stale or incomplete and cannot be safely refreshed.
- No bounded, materially different strategy is supported by current evidence.
- The proposed strategy repeats an ineffective strategy without a material `strategy_delta`.
- Consultation is not fresh, unless a valid one-invocation, local-only fallback approval applies.
- Consultation or recovery is hard-unrecoverable and no valid fallback approval applies.
- The orchestrator cannot disposition a safe in-scope strategy.

Continue repair only when current evidence is fresh, no hard stop applies, a
bounded material `strategy_delta` exists, consultation is fresh or the explicit
fallback applies, and validation plus re-observation can be completed safely.

## Merge-Prepared Gate

Report `merge-prepared: yes` only when all conditions are true:

- PR is open.
- Latest head re-observation is complete and matches the latest head SHA.
- No observed Actions CI failure remains.
- External/non-Actions checks are not claimed as observed by this batch. If branch protection or the repository workflow depends on them, GitHub UI or external CI confirmation is recorded, or the batch stops at a human gate.
- Any waived or unconfirmed external/non-Actions check risk is recorded as residual risk.
- No blocking review feedback remains.
- No visible merge conflict or equivalent merge blocker remains.
- No `untriaged` inventory item remains.
- No unresolved `needs-human` item remains.
- No `blocking` item has an incomplete `fix-now` repair unit.
- Every `follow-up`, `no-action`, `covered-by`, `duplicate`, or `false-positive` item has rationale and residual risk where relevant.
- Observation limitation handling, resume metadata, trigger boundary, and new trigger approval status are recorded.
- Review-thread unresolved state is known, or any unresolved-thread limitation is explicitly waived and recorded as residual risk.
- `review-clean` is reported separately from `merge-prepared`; `review-clean: no` may still be `merge-prepared: yes` when all remaining items are triaged and non-blocking.
