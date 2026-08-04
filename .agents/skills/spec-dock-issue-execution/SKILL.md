---
name: spec-dock-issue-execution
description: Execute an active SpecDock Issue only after reviewer-gated planning artifacts and an executable plan are ready, while recording evidence in report.md.
---

# Spec-Dock Issue Execution

Use this skill only for active Issue execution after Issue planning has produced reviewer-gated `requirement.md`, `design.md`, and executable `plan.md`. This skill executes the approved plan; it does not repair planning artifacts or invent missing requirements.

This skill is a fixed kernel / operational kernel. Keep detailed lifecycle policy in `spec-dock/docs/workflow_issue.md` and plan field semantics in `spec-dock/docs/authoring/issue-plan.md`.

state-specific generated Runbook text is runtime guidance. It is not canonical authority, must not be edited as source of truth, and must not replace canonical docs.

## Read First

- Runtime guidance: `./spec-dock/scripts/spec-dock guidance issue-execution`
  - Treat stdout as current guidance, not canonical authority.
  - Record `state`, `next_action`, `reason_code`, `authority`, `may_execute_approved_plan`, commands, and stop conditions before acting.
  - Register the returned `state`, `next_action`, `reason_code`, `authority`, commands, and stop conditions before acting.
- Canonical sources:
  - `spec-dock/docs/workflow_issue.md`
  - `spec-dock/docs/workflow_clarification.md`
  - `spec-dock/docs/phase_plan_issue.md`
  - `spec-dock/docs/authoring/issue-plan.md`
  - active Issue `requirement.md`, `design.md`, `plan.md`, and `report.md`
- Ignore generated projections such as `spec-dock/.agent/runbooks/current-runbook.*` and `spec-dock/active/current-runbook.*` as authority.
- Do not expect or derive canonical docs from `current-runbook.*`; Do not read, edit, or manage them as handoff authority.

## Operating Spine

1. Confirm execution readiness.
   - Start only when canonical requirement/design/plan are approved or reviewer-passed, current, non-template, non-contradictory, and recorded as ready.
   - Treat a non-executable `plan.md` as a planning gap.
   - If runtime guidance is malformed, unavailable, or contradicts canonical docs, stop and use the canonical docs and active artifacts.
2. Execute exactly one approved step or milestone at a time.
   - Execute exactly one current implementation step or milestone at a time.
   - Use `plan.md` for execution order, command queue, verification obligations, delegation contract, and closure criteria.
   - Do not start next-step implementation, review, or commit work until the current unit is closed.
   - Do not start implementation, review, or commit work for the next step / milestone until the current unit is closed.
3. Delegate bounded implementation work when the workflow requires it.
   - Parent agent remains responsible for orchestration, context, evidence, and closure.
   - Route runtime, CLI, infra, code, tests, scaffold behavior, shipped docs, templates, skills, and workflow text to the appropriate delegated worker per `workflow_issue.md`.
   - Parent direct implementation or direct reviewer-fail fixes require the documented exception path from `workflow_issue.md`.
4. Keep `report.md` as the evidence ledger.
   - Record observed execution evidence, verification output, reviewer verdicts, closure delta, commit/no-op evidence, and material interpretation or decision entries.
   - Use the `Spec Interpretation / Decision Ledger` for material interpretation changes, unresolved spec gap handling, and decision disposition.
   - Worker outputs are evidence until the parent orchestrator integrates, rejects, defers, supersedes, or promotes them in `report.md`.
   - Do not store private reasoning, raw transcripts, secrets, or unadopted durable decisions in canonical docs.
5. Use reviewer and completion gates.
   - Required fresh `spec-reviewer`, `code-reviewer`, and `qa-reviewer` passes are gates; unavailable/denied/skipped results are not passes.
   - After final local gates, route final PR delivery and merge-preparation evidence before `issue finish` to `github-pr-merge-preparer` when required.
   - Run `issue finish` only when `workflow_issue.md` completion gates allow it.

## Contract Anchors

- Treat `spec-dock/docs/workflow_issue.md as the source of truth` and this skill as a concise reminder for issue execution.
- parent agent responsible for orchestration; parent agent remains responsible for orchestration, evidence, and closure.
- Start execution only after `requirement.md`, `design.md`, and `plan.md` are approved / reviewer-pass.
- Treat requirement / design / plan creation or repair as planning / spec authoring work; return to planning / spec authoring for unresolved gaps.
- Use the planned executable workflow contract / command queue, 具体テストケース一覧, concrete test cases, observed evidence ledger, report evidence destination, amendment trigger, and `docs/authoring/issue-plan.md`.
- Treat a non-executable `plan.md` as an unresolved plan gap.
- Close a step only with required verification, a fresh reviewer pass, commit候補 or approved-no-op evidence, and a post-commit clean check when the workflow requires them.
- Route runtime, tests, and scaffold behavior to `dev-coder`; Route shipped docs, templates, skills, and workflow text to `doc-writer`.
- Parent direct implementation or direct reviewer-fail fixes require a documented Parent Implementation Exception; Parent direct fixes require a documented Parent Implementation Exception.
- Use bounded delegated follow-up only when the approved plan and workflow gates allow it.
- Waivers, unavailable reviewers, host conflicts, and degraded paths are not reviewer passes or normal implementation success.
- Preserve public interface / observable behavior and keep file mutation tied to the approved implementation step.
- Treat `authorized_profile` as the obligation authority; `lite_candidate` is not authority and must not reduce obligations by itself.
- `Ledger Note`: source-agent, options considered, needs orchestrator decision, No material implementation decisions beyond the approved plan., Status=open, report-only durable decision.
- Stop if execution authority, active context, reviewer gates, verification, or report-ledger disposition cannot be verified.

## Stop Conditions

- Active Issue context, allowed paths, acceptance criteria, reviewer requirements, delegation boundaries, or closure conditions cannot be verified.
- Any requirement/design/plan artifact is draft, template-only, unresolved, stale, contradictory, non-executable, or missing fresh reviewer-pass evidence.
- Execution reveals an unresolved requirement / design / plan gap; return to planning or clarification.
- Tooling is unavailable, access is denied, host conflicts exist, waiver/degraded-mode is requested, or required named roles/reviewers are unavailable without an explicit workflow-approved fallback.
- Required worker evidence, reviewer pass, verification output, report-ledger disposition, commit/no-op evidence, or post-commit clean check is missing.
- The next action would require changing runtime commands, dependency algorithms, workflow policy, or completion gates.

## Runtime Command Reminders

- Use the shipped runtime path: `./spec-dock/scripts/spec-dock ...`.
- Normal lifecycle is `issue start <target>` before execution and `issue finish` only after the workflow completion gates pass.
- `issue start -f` / `issue start --force` bypasses only the unfinished-active-issue guard.
- Mutate dependencies command-first with `deps add`, `deps remove`, and `deps check`.
  - Add dependency: `./spec-dock/scripts/spec-dock deps add --from <issue-id> --to <issue-id>`
  - Remove dependency: `./spec-dock/scripts/spec-dock deps remove --from <issue-id> --to <issue-id>`
  - Check readiness: `./spec-dock/scripts/spec-dock deps check <issue-id>` or `./spec-dock/scripts/spec-dock deps check <target>`
- Evidence commands include `validate` and `sync`; use `--no-github` only for explicit cache/local verification.
  - Validate: `./spec-dock/scripts/spec-dock validate`
  - Sync: `./spec-dock/scripts/spec-dock sync`
  - After `issue finish`, avoid `sync` on the just-finished issue branch unless the workflow explicitly requires post-finish refresh there.
- Preserve the feedback loop: reproduction, hypotheses, implementation step, verification, regression evidence, and instrumentation cleanup.
- Do not copy the full workflow here.
