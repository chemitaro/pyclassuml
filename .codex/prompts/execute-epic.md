# Execute Epic

Complete the relevant spec-dock epic by coordinating execution of ready Issues
from the approved Epic plan through the issue workflow.

Use `$spec-dock-epic-execution` as the first-read coordinator for Epic execution
after Epic planning is complete. It routes incomplete Epic planning back to
`$spec-dock-epic-planning`, selects one ready Issue at a time, and hands each
concrete Issue to `/execute-issue` and `$spec-dock-issue-execution` when the
Issue plan is executable. Do not substantially rewrite existing skills as part
of this prompt.

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

Before Epic execution starts:

1. Inspect `spec-dock/active/context-pack.md` and the current active state.
2. Confirm the relevant initiative, epic, branch, and user objective.
3. If no suitable epic is active or requested, stop execution and route to
   `$spec-dock-epic-planning` for Epic selection, import, creation, or authoring
   as needed.
4. Inspect the active epic `report.md` and confirm recorded Spec Authoring Gate
   evidence for fresh spec-reviewer pass on requirement, design, and plan. If
   that evidence is missing, stale, or inconsistent, stop execution and hand
   the Epic back to `$spec-dock-epic-planning`.
5. Use `spec-dock/docs/workflow_epic.md` as the source of truth for epic reuse,
   creation, authoring, issue readiness, and epic quality gates.
6. Use `spec-dock/docs/workflow_spec_authoring.md` for requirement/design/plan
   phase promotion.
7. Use `spec-dock/docs/phase_plan_epic.md` for epic plan structure and issue
   readiness contracts.
8. Treat `spec-dock/docs/rules/epic/issues.md` as an Epic planning handoff
   reference for Issue decomposition and readiness, not as execution authority
   for this prompt.

If the epic requirement, design, or plan is missing, contradictory,
template-only, or not ready for Issue execution, do not execute or create Issues
from this prompt. Hand the Epic back to `$spec-dock-epic-planning` for spec
authoring, initiative-driven decomposition, dependency, or Issue readiness repair.

When the epic is ready:

- Select the next ready Issue from the approved Epic plan, dependency state, and
  `spec-dock/docs/workflow_epic.md`. If no Issue is ready because all required
  Issues are complete or the reviewed plan explicitly has no executable Issue
  work, record no-op / completion evidence and continue to the Epic completion
  gate. If executable Issue work remains blocked or unready, record blocker
  evidence and hand the Epic back to `$spec-dock-epic-planning` or the relevant
  workflow gate instead of inventing execution work.
- For the selected Issue, run
  `./spec-dock/scripts/spec-dock issue start <issue-id>` before implementation,
  then execute that active Issue using the `/execute-issue` contract.
- Treat each issue as a complete TDD execution unit governed by
  `$spec-dock-issue-execution`.
- Record issue selection evidence, issue handoff evidence,
  integration checkpoint evidence, skipped or blocked issue rationale, and final
  epic completion evidence in the epic `report.md`.

Do not report the epic complete until all required issues have completed and the
epic final quality gates in `spec-dock/docs/workflow_epic.md` are satisfied. If
required issue work is blocked or deferred, report the epic as blocked or
incomplete unless the epic plan is amended and fresh spec-reviewed so the
deferred work is no longer required or the final exit contract changes.
