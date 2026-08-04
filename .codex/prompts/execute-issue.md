# Execute Issue

Complete the currently active spec-dock issue.

Use the `$spec-dock-issue-execution` skill. Do not create a new skill for this
workflow, and do not substantially rewrite the existing skill as part of this
prompt.

This prompt supports two operating modes:

- Standalone mode: run `/execute-issue` by itself to complete the active issue.
- Goal-assisted mode: first run `/goal <objective>` directly in Codex CLI, then
  run `/execute-issue`. Treat the active goal as the higher-level objective for
  this issue completion work.

Do not embed, simulate, or try to execute `/goal` from inside this prompt. The
`/goal` command is a built-in Codex CLI slash command that the user enters
directly. If no active goal exists, continue in standalone mode and complete the
active issue through the spec-dock issue workflow.

Before implementation starts:

1. Inspect `spec-dock/active/context-pack.md`.
2. Confirm the active issue and active branch.
3. Read `spec-dock/active/issue/requirement.md`,
   `spec-dock/active/issue/design.md`,
   `spec-dock/active/issue/plan.md`, and
   `spec-dock/active/issue/report.md`.
4. Treat `spec-dock/docs/workflow_issue.md` as the source of truth for issue
   execution and completion.
5. Treat `spec-dock/docs/workflow_spec_authoring.md` as the source of truth if
   requirement, design, or plan is not implementation-ready.
6. Read `spec-dock/docs/authoring/issue-plan.md` when it exists and use it as
   the Issue `plan.md` authoring contract for step-local concrete test cases
   and executable step field semantics.

If the active issue docs are missing, contradictory, template-only, or not
implementation-ready, do not start coding. Repair the issue docs through the
spec authoring workflow and fresh spec-reviewer gates before implementation.
Missing step-local `具体テストケース一覧`, table-only concrete test cases, or
cases without `前提`, `操作`, `期待結果`, `失敗検出`, and `検証方法` fields means
the plan is not implementation-ready.

When implementation is ready:

- Treat `plan.md` as the planned executable workflow contract / command queue.
  Follow step order exactly and execute each step through its behavior goal,
  planned obligation, Red or justified alternative evidence, implementation
  scope, Green verification, Refactor / cleanup guardrail, closure
  requirements, report evidence destination, and amendment trigger.
- Treat `report.md` as the observed evidence ledger. Record actual Red / Green /
  Refactor results, verification output, discovered tests, closure delta,
  delegated worker evidence, reviewer verdicts, and commit/no-op evidence there.
- Treat `report.md` as the canonical `Spec Interpretation / Decision Ledger`
  for material implementation-time interpretation, decisions, deviations,
  tradeoffs, open questions, and promotion / follow-up. If no material
  decision occurred, keep the ledger section and record
  `No material interpretation changes.` plus `No decision entries.`.
- Require each delegated worker output to include either a structured
  `Ledger Note` or
  `No material implementation decisions beyond the approved plan.`. A worker
  `proposed decision` is provisional input, not an accepted decision; the parent
  orchestrator owns report integration, disposition evidence, and promotion /
  follow-up decisions.
- Use each step's card-style nested `具体テストケース一覧`, closure ids, close
  conditions, verification commands, alternative evidence paths, and report
  evidence destinations.
- Preserve reviewable commit history through the approved plan's `commit候補`
  or approved-no-op gates. Review scope and commit scope may match, but are not
  defined as always identical.
- If implementation reveals a new specification, bug class, external contract
  risk, or closure obligation outside the approved step contract, stop for plan
  amendment and re-review instead of closing it with report evidence alone.
- Do not finish the issue with `Status=open` ledger entries, missing disposition
  evidence, report-only durable decisions, invalid no-decision claims, or ledger
  content that includes transcripts, private reasoning, or secrets.
- Record implementation delegation decisions, step evidence, reviewer results,
  closure coverage, and final delivery evidence in
  `spec-dock/active/issue/report.md`.
- Run the final QA, issue-wide code-review, and spec-review gates required by
  `$spec-dock-issue-execution` before reporting the issue complete.

Do not run `./spec-dock/scripts/spec-dock issue finish` until the existing issue
execution skill's completion contract is fully satisfied.
