# Execute Epic

Complete the relevant spec-dock epic by decomposing it into issues and executing
those issues through the issue workflow.

Use the `$spec-dock-epic-planning` skill for epic-level planning and
decomposition. Use `/execute-issue` and the `$spec-dock-issue-execution` skill
for each concrete issue implementation. Do not create a new skill for this
workflow, and do not substantially rewrite existing skills as part of this
prompt.

This prompt supports two operating modes:

- Standalone mode: run `/execute-epic` by itself to complete the relevant active
  or requested epic.
- Goal-assisted mode: first run `/goal <objective>` directly in Codex CLI, then
  run `/execute-epic`. Treat the active goal as the higher-level objective for
  this epic completion work.

Do not embed, simulate, or try to execute `/goal` from inside this prompt. The
`/goal` command is a built-in Codex CLI slash command that the user enters
directly. If no active goal exists, continue in standalone mode and complete the
epic through the spec-dock workflow.

When this prompt references `/execute-issue`, do not rely on nested slash command
expansion. It means: apply the same prompt contract as `/execute-issue` and use
`$spec-dock-issue-execution` for the active issue.

Before issue decomposition starts:

1. Inspect `spec-dock/active/context-pack.md` and the current active state.
2. Confirm the relevant initiative, epic, branch, and user objective.
3. If no suitable epic is active, inspect existing epics under the relevant
   initiative before creating or importing a new epic.
4. Inspect the active epic `report.md` and confirm recorded Spec Authoring Gate
   evidence for fresh spec-reviewer pass on requirement, design, and plan. If
   that evidence is missing, stale, or inconsistent, rerun and fix the authoring
   gates before creating issues.
5. Use `spec-dock/docs/workflow_epic.md` as the source of truth for epic reuse,
   creation, authoring, issue decomposition, and epic quality gates.
6. Use `spec-dock/docs/workflow_spec_authoring.md` for requirement/design/plan
   phase promotion.
7. Use `spec-dock/docs/phase_plan_epic.md` for epic plan structure and issue
   readiness contracts.

If the epic requirement, design, or plan is missing, contradictory,
template-only, or not ready for issue decomposition, do not create issues yet.
Repair the epic docs through the spec authoring workflow and fresh
spec-reviewer gates before decomposition.

When the epic is ready:

- Decompose the epic plan into concrete issues with clear scope, order,
  dependencies, readiness criteria, integration checkpoints, and acceptance
  mapping back to the epic.
- Create or update issues using `./spec-dock/scripts/spec-dock ...` commands and
  the rules in `spec-dock/docs/workflow_epic.md`,
  `spec-dock/docs/rules/epic/issues.md`, `spec-dock/docs/reference_github.md`,
  `spec-dock/docs/reference_deps.md`, and `spec-dock/docs/reference_sync.md`.
- For each issue, run `./spec-dock/scripts/spec-dock issue start <issue-id>`
  before implementation, then execute the issue using the `/execute-issue`
  contract.
- Treat each issue as a complete TDD execution unit governed by
  `$spec-dock-issue-execution`.
- Record epic-level decomposition decisions, issue handoff evidence,
  integration checkpoint evidence, skipped or blocked issue rationale, and final
  epic completion evidence in the epic `report.md`.

Do not report the epic complete until all required issues have completed and the
epic final quality gates in `spec-dock/docs/workflow_epic.md` are satisfied. If
required issue work is blocked or deferred, report the epic as blocked or
incomplete unless the epic plan is amended and fresh spec-reviewed so the
deferred work is no longer required or the final exit contract changes.
