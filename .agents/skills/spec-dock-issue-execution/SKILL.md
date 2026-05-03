---
name: spec-dock-issue-execution
description: Leaf skill for issue execution tasks in spec-dock.
---

# Spec-dock Issue Execution

- Use this skill for issue execution work.
- Typical fit: implement the active issue via TDD and update `report.md`.
- Start from `spec-dock/active/context-pack.md`, then follow the issue workflow.
- `spec-dock/docs/workflow_issue.md` is the source of truth for issue execution and completion.
- For shared phase authoring method, use:
  - `spec-dock/docs/phase_requirement.md`
  - `spec-dock/docs/phase_design.md`
  - `spec-dock/docs/phase_plan.md`
  - `spec-dock/docs/phase_plan_issue.md`
- Keep templates as scaffolds. Use the docs above for authoring guidance, including Issue dependency analysis, `Module Dependency Diagram`, Linux `tree` style file-change planning, and step ordering.
- Spec authoring mode: shape `requirement.md`, `design.md`, and `plan.md` for the project. Add, remove, merge, reorder, or rewrite template sections when it improves correctness, human understanding, or agent executability. Remove irrelevant placeholders.
- In spec authoring mode, use the optional diagram catalog in `spec-dock/docs/phase_design.md` as the authoritative source for diagram choices. Add catalog-listed or project-specific sections only when they clarify the issue.
- Execution mode: follow the approved issue docs. If the docs are missing required detail or contradict the implementation path, update/review the docs before implementation continues.
- Do not skip the docs impact resolution step or the final diff review quality gate.
- Issue execution is not complete unless the active issue is set and confirmed, and `spec-dock/active/issue/requirement.md`, `design.md`, `plan.md`, and `report.md` contain issue-specific content rather than template, placeholder, or effectively blank content.
- `spec-dock/active/issue/report.md` must record command evidence for required `sync`, `validate`, and review steps, including whether each required step succeeded, passed, or reached approval.
- Complete status requires the active issue to remain set and confirmed, every required step to be executed, every required `sync` / `validate` step to succeed or pass, and every required review step to reach approval or pass.
- If any required step is skipped, or executed without a successful, pass, or approved outcome, classify the issue as `blocked` or `incomplete`, record the reason and next action in `spec-dock/active/issue/report.md`, and do not report the issue as complete.
- Treat the issue as `blocked` only when an external dependency, missing permission, unavailable service, or other environment condition prevents the next required action.
- When blocked, record the reason and next action in `spec-dock/active/issue/report.md`. Include blocker type and impact when applicable.
- Keep environment blockers separate from product gaps; missing implementation, missing docs updates, or missing evidence are incomplete unless an environment blocker prevents progress.
- When incomplete, record the reason and next action in `spec-dock/active/issue/report.md`.
- Do not report the issue as complete while it is incomplete or blocked.
- Primary workflow: `spec-dock/docs/workflow_issue.md`.
- `spec-dock/docs/reference_deps.md`
- `spec-dock/docs/reference_sync.md`
- `spec-dock/docs/reference_github.md`
- `spec-dock/docs/reference_naming.md`

## Runtime command reminders

- Use runtime command path only: `./spec-dock/scripts/spec-dock ...`
- Dependency mutation is command-first:
  - `./spec-dock/scripts/spec-dock deps add --from <issue-id> --to <issue-id>`
  - `./spec-dock/scripts/spec-dock deps remove --from <issue-id> --to <issue-id>`
  - `./spec-dock/scripts/spec-dock deps check <target> --github`
- Keep report evidence aligned with workflow checks:
  - `./spec-dock/scripts/spec-dock validate`
  - `./spec-dock/scripts/spec-dock sync --github`
