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
   the Issue `plan.md` authoring contract for step-local concrete test cases.

If the active issue docs are missing, contradictory, template-only, or not
implementation-ready, do not start coding. Repair the issue docs through the
spec authoring workflow and fresh spec-reviewer gates before implementation.
Missing step-local `具体テストケース一覧`, table-only concrete test cases, or
cases without `前提`, `操作`, `期待結果`, `失敗検出`, and `検証方法` fields means
the plan is not implementation-ready.

When implementation is ready:

- Follow `plan.md` step order exactly.
- Use each step's card-style nested `具体テストケース一覧`, closure ids, close
  conditions, verification commands, and evidence paths.
- Preserve the `1 implementation step = 1 code-reviewer scope = 1 commit`
  contract unless the approved issue plan is amended and re-reviewed first.
- Record implementation delegation decisions, step evidence, reviewer results,
  closure coverage, and final delivery evidence in
  `spec-dock/active/issue/report.md`.
- Run the final QA, issue-wide code-review, and spec-review gates required by
  `$spec-dock-issue-execution` before reporting the issue complete.

Do not run `./spec-dock/scripts/spec-dock issue finish` until the existing issue
execution skill's completion contract is fully satisfied.
