---
name: spec-dock-issue-execution
description: Execute an active spec-dock issue while keeping spec-dock/docs/workflow_issue.md as the source of truth.
---

# Spec-Dock Issue Execution

Use `spec-dock/docs/workflow_issue.md` as the source of truth. This skill is only a concise reminder for issue execution.

- Keep the parent agent responsible for orchestration, context, acceptance evidence, and final closure. Delegates may implement bounded tasks, but they do not own the issue.
- Preserve parent invariants before, during, and after delegated work: active issue context, allowed paths, acceptance criteria, reviewer requirements, and stop conditions remain the parent agent's responsibility.
- Start execution only after `requirement.md`, `design.md`, and `plan.md` are approved / reviewer-pass and recorded as ready under the issue workflow. If any of the three artifacts is draft, template-only, unresolved, or missing reviewer-pass evidence, stop and return to planning / spec authoring instead of implementing.
- Treat requirement / design / plan creation or repair as planning / spec authoring work, not issue execution work. Use this skill only after those artifacts are ready for implementation handoff.
- Treat `plan.md` as the planned executable workflow contract / command queue. Execute each implementation step through its behavior goal, planned obligation, Red or justified alternative evidence, implementation scope, Green verification, refactor guardrail, closure requirements, report evidence destination, and amendment trigger.
- Treat a non-executable `plan.md` as an unresolved plan gap. `plan.md` must contain enough step-local scope, obligations, verification, report evidence destination, and amendment triggers for an executor to run it without inventing missing workflow decisions.
- If implementation reveals an unresolved requirement / design / plan gap, return to `spec-dock/docs/workflow_clarification.md` or the relevant authoring phase. Do not absorb the gap by inventing an execution assumption.
- Treat `report.md` as the observed evidence ledger for actual Red / Green / Refactor results, verification output, discovered tests, closure delta, reviewer verdicts, and commit/no-op evidence.
- Treat `report.md` as the canonical `Spec Interpretation / Decision Ledger` for material implementation-time interpretation, decisions, deviations, tradeoffs, open questions, and promotion / follow-up. Do not store worker raw transcripts, private reasoning, or secrets there.
- Require delegated workers to return a `Ledger Note` when they encounter material interpretation, decision, deviation, tradeoff, open question, or follow-up. The minimum fields are `source-agent`, `topic`, `trigger`, `ambiguity / constraint`, `observed facts`, `options considered`, `proposed decision`, `rationale`, `affected files`, `affected tests`, `risk if wrong`, `rollback or revisit`, `confidence`, and `needs orchestrator decision`.
- Require workers with no material decision to state `No material implementation decisions beyond the approved plan.` A worker `proposed decision` is not an accepted decision; the parent orchestrator must integrate, reject, defer, supersede, or promote it in the canonical report ledger.
- Before completion, ensure ledger entries have no `Status=open`; each resolved / superseded entry has disposition evidence, required follow-up / promotion evidence, and no report-only durable decision.
- Route step field semantics, `具体テストケース一覧`, obligation coverage, alternative evidence paths, and amendment rules to `spec-dock/docs/authoring/issue-plan.md`; keep lifecycle and completion policy in `spec-dock/docs/workflow_issue.md`.
- Route runtime, tests, and scaffold behavior to `dev-coder`.
- Route shipped docs, templates, skills, and workflow text to `doc-writer`.
- Record handoff readiness evidence in `report.md`; keep issue handoff changes limited to clarification reference, unresolved spec gap return, and readiness evidence.
- Treat unavailable tooling, denied access, host conflicts, waiver requests, and similar blockers as stop/incomplete unless explicit workflow policy evidence says they count as success.
- When review fails, perform bounded delegated follow-up and rerun review. Parent direct fixes require a documented Parent Implementation Exception.
- After final commit gates pass, use `github-pr-merge-preparer` for final PR delivery and merge-preparation evidence before `issue finish`; keep the detailed completion policy in `workflow_issue.md`.

## Runtime Command Reminders

- Use the shipped runtime path: `./spec-dock/scripts/spec-dock ...`.
- Normal lifecycle is `issue start <target>` before execution and `issue finish` only after the workflow completion gates pass.
- `issue start -f` / `issue start --force` bypasses only the unfinished-active-issue guard; it does not bypass readiness, target validation, or checkout safety.
- After `issue finish`, avoid `sync` on the just-finished issue branch when active clear must remain clear.
- Mutate dependencies command-first with `deps add`, `deps remove`, and `deps check`: `./spec-dock/scripts/spec-dock deps add --from <issue-id> --to <issue-id>`, `./spec-dock/scripts/spec-dock deps remove --from <issue-id> --to <issue-id>`, and `./spec-dock/scripts/spec-dock deps check <target>`.
- Evidence commands include `validate` and `sync`: `./spec-dock/scripts/spec-dock validate` and `./spec-dock/scripts/spec-dock sync`.
- Use `--no-github` only for explicit cache/local verification without GitHub calls.

Do not copy the full workflow here; update `workflow_issue.md` when execution policy changes.
