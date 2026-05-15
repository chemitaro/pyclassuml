# Execute Initiative

Complete the relevant spec-dock initiative by decomposing it into epics, then
decomposing those epics into issues, and executing the issues through the issue
workflow.

Use the `$spec-dock-initiative-planning` skill for initiative-level planning and
epic portfolio decomposition. Use `/execute-epic` and
`$spec-dock-epic-planning` for each epic. Use `/execute-issue` and the
`$spec-dock-issue-execution` skill for each concrete issue implementation. Do
not create a new skill for this workflow, and do not substantially rewrite
existing skills as part of this prompt.

This prompt supports two operating modes:

- Standalone mode: run `/execute-initiative` by itself to complete the relevant
  active or requested initiative.
- Goal-assisted mode: first run `/goal <objective>` directly in Codex CLI, then
  run `/execute-initiative`. Treat the active goal as the higher-level objective
  for this initiative completion work.

Do not embed, simulate, or try to execute `/goal` from inside this prompt. The
`/goal` command is a built-in Codex CLI slash command that the user enters
directly. If no active goal exists, continue in standalone mode and complete the
initiative through the spec-dock workflow.

When this prompt references `/execute-epic` or `/execute-issue`, do not rely on
nested slash command expansion. It means: apply the same prompt contract as the
referenced prompt and use the corresponding spec-dock planning or execution
skill for the active scope.

Before epic decomposition starts:

1. Inspect `spec-dock/active/context-pack.md` and the current active state.
2. Confirm the relevant initiative, branch, and user objective.
3. If no suitable initiative is active, inspect existing initiatives before
   creating or importing a new initiative.
4. Inspect the active initiative `report.md` and confirm recorded Spec Authoring
   Gate evidence for fresh spec-reviewer pass on requirement, design, and plan.
   If that evidence is missing, stale, or inconsistent, rerun and fix the
   authoring gates before creating epics.
5. Use `spec-dock/docs/workflow_initiative.md` as the source of truth for
   initiative reuse, creation, authoring, epic decomposition, and initiative
   quality gates.
6. Use `spec-dock/docs/workflow_spec_authoring.md` for requirement/design/plan
   phase promotion.
7. Use `spec-dock/docs/phase_plan_initiative.md` for initiative plan structure,
   epic portfolio planning, milestone gates, metric review, and epic readiness
   contracts.

If the initiative requirement, design, or plan is missing, contradictory,
template-only, or not ready for epic decomposition, do not create epics yet.
Repair the initiative docs through the spec authoring workflow and fresh
spec-reviewer gates before decomposition.

When the initiative is ready:

- Decompose the initiative plan into an ordered epic portfolio with milestone
  gates, metric links, dependencies, readiness criteria, and final exit
  criteria.
- Create or update epics using `./spec-dock/scripts/spec-dock ...` commands and
  the rules in `spec-dock/docs/workflow_initiative.md`,
  `spec-dock/docs/rules/initiative/epics.md`,
  `spec-dock/docs/reference_github.md`, `spec-dock/docs/reference_deps.md`, and
  `spec-dock/docs/reference_sync.md`.
- For each epic, execute epic-level planning and issue decomposition using the
  `/execute-epic` contract.
- For each issue produced by those epics, run
  `./spec-dock/scripts/spec-dock issue start <issue-id>` before implementation,
  then execute the issue using the `/execute-issue` contract.
- Treat each epic as an autonomous planning and integration unit, and each issue
  as a complete TDD execution unit governed by `$spec-dock-issue-execution`.
- Record initiative-level decomposition decisions, epic handoff evidence,
  milestone / metric review evidence, skipped or blocked epic rationale, and
  final initiative completion evidence in the initiative `report.md`.

Do not report the initiative complete until all required epics and issues have
completed and the initiative final quality gates in
`spec-dock/docs/workflow_initiative.md` are satisfied. If required epic or issue
work is blocked or deferred, report the initiative as blocked or incomplete
unless the initiative and affected epic plans are amended and fresh
spec-reviewed so the deferred work is no longer required or the final exit
contract changes.
