---
name: spec-driven-tdd-workflow
description: Entry skill that routes work to the correct spec-dock leaf workflow.
---

# Spec-driven TDD Workflow (Hub)

- Use this as the entry/routing skill for spec-dock work.
- Keep `spec-dock/docs/` as the source of truth; skills stay concise.
- Keep templates as minimum authoring scaffolds, not compliance targets.
- Put spec authoring rules and workflow explanations in `spec-dock/docs/` and route through these skills.
- Use `spec-dock/docs/workflow_spec_authoring.md` as the source of truth for requirement / design / plan phase promotion across Initiative, Epic, and Issue.
- Use `spec-dock/docs/workflow_clarification.md` and `spec-dock-clarification` when the request is to clarify ambiguous requirements, sharpen domain language, prepare one-question-at-a-time interviews, or work in analysis-only / draft-only mode before canonical authoring.
- In spec authoring mode, each artifact must pass a fresh `spec-reviewer` (`review_status: pass`) before the next phase starts; fix findings and re-run a fresh reviewer until pass.
- In spec authoring or issue execution mode, honor workflow-scoped delegation consent before routing reviewer work: if the current user request or active report evidence grants issue-scoped consent, the orchestrator may invoke named reviewer / read-only specialist roles within that scope without per-phase confirmation.
- Missing, stale, failed, unavailable, denied, waived, or provisional reviewer results are not `review_status: pass`. Do not route to implementation or completion by treating them as degraded success.
- Agents may add, remove, merge, reorder, or rewrite template sections when it improves correctness, human understanding, or agent executability for the specific project.
- Use `spec-dock/docs/phase_design.md` as the source of truth for optional diagram choices. Add useful UML / PlantUML / table sections from the catalog, or project-specific sections outside the catalog, when they clarify structure, boundaries, responsibility, flow, state, or dependency.
- Route once the main output is clear; leaf skills own the workflow details.

## Route to leaf skills

- `spec-dock-initiative-planning`: initiative-level requirement/design/plan planning.
- `spec-dock-epic-planning`: epic-level requirement/design/plan planning.
- `spec-dock-issue-planning`: issue-level requirement/design/plan planning, review readiness, and implementation handoff readiness.
- `spec-dock-issue-execution`: issue-level TDD execution and report updates after approved / reviewer-pass planning artifacts and an executable `plan.md` are ready.
- `spec-dock-clarification`: first-class docs-aware clarification companion for planning, source-grounded ambiguity, one-question-at-a-time user clarification through the orchestrator, and analysis-only / authoring handoff.
- `spec-dock-system-architect`: delegated architecture analysis and draft design evidence written as scope-local flat `discussions/<ts>-<kind>-<slug>.md` Markdown. Canonical docs remain main-orchestrator-only.
- `spec-dock-implementation-planner`: delegated planning analysis and draft plan evidence written as scope-local flat `discussions/<ts>-<kind>-<slug>.md` Markdown. Canonical docs remain main-orchestrator-only.
- `spec-dock-adr-facilitation`: ADR drafting/decision facilitation linked to the current workflow.

## Direct references

- `spec-dock/docs/reference_github.md`
- `spec-dock/docs/reference_deps.md`
- `spec-dock/docs/reference_sync.md`
- `spec-dock/docs/reference_naming.md`
- `spec-dock/docs/workflow_spec_authoring.md`
- `spec-dock/docs/workflow_clarification.md`
- `spec-dock/docs/workflow_issue.md`
- `spec-dock/docs/phase_design.md`
- `spec-dock/docs/phase_plan_issue.md`

## Quick reminders

- Do not default to create/import for initiative/epic; inspect existing nodes first.
- Keep boundary rationale in `discussions/`; docs remain the source of truth for the rule itself.
- Put interview and investigation notes under `discussions/` in the active node. Important questions use unanswered `interview` first; lightweight chat questions stay one-at-a-time and return to `interview` if they become specification decisions.
- Sub-agent authoring outputs may be direct-written under the target scope `discussions/` direct child, but they do not become canonical authority until the main orchestrator adopts them in canonical docs and records the adoption in `report.md`.
- Record `Spec Authoring Gate` evidence in the active node's `report.md` for each requirement / design / plan promotion.
- For issue work, route requirement/design/plan authoring and unresolved source-grounded ambiguity to `spec-dock-issue-planning` with `spec-dock-clarification` as needed before execution.
- If issue planning and execution are both requested, complete planning artifacts, fresh reviewer gates, and handoff readiness evidence before routing to `spec-dock-issue-execution`.
- `spec-dock/active/context-pack.md` is the execution entrypoint for active issue work.
- Discussion doc example: `./spec-dock/scripts/spec-dock new doc adr --issue iss-00123 --title "..."`
- Runtime path guardrail: use only `./spec-dock/scripts/spec-dock ...` and avoid legacy command aliases.
- For concrete dependency and completion commands, route to `spec-dock-issue-execution` and the reference docs.
