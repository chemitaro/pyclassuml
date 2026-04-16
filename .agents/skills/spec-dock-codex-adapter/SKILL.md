---
name: spec-dock-codex-adapter
description: Thin Codex host adapter for spec-dock.
---

# Spec-dock Codex Adapter

- Use this as the Codex entrypoint for spec-dock work.
- Follow `spec-dock/docs/workflow_issue.md` as the canonical issue workflow.
- Route orchestration to the appropriate leaf skill; do not reimplement protocol or state logic here.
- Keep this adapter thin: wording only, no generated state, no pruning logic, no protocol interpretation.
- Adapter safety baseline follows issue-00049 host-adapter hardening scope.
- For issue work, route-only or `active set`-only is not complete.
- Do not treat the task as complete unless the active issue is set and confirmed, and `spec-dock/active/issue/requirement.md`, `design.md`, `plan.md`, and `report.md` contain issue-specific content.
- For complete status, `spec-dock/active/issue/report.md` must record command evidence showing successful required `sync` / `validate` outcomes and required review approval or pass outcomes.
- If any required step is skipped, or executed without a successful, pass, or approved outcome, record the reason and next action in `spec-dock/active/issue/report.md` and report the work as incomplete or blocked instead of complete.

## Runtime guardrails

- Use runtime command path only: `./spec-dock/scripts/spec-dock ...`
- Keep this adapter thin: use docs references for command details.
- Dependency command references:
  - `spec-dock/docs/reference_deps.md`
  - `spec-dock/docs/reference_sync.md`
- Completion workflow reference:
  - `spec-dock/docs/workflow_issue.md`
