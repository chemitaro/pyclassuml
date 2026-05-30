---
name: spec-dock-issue-planning
description: Leaf skill for issue requirement, design, and plan planning tasks in spec-dock.
---

# Spec-dock Issue Planning

- Use this skill for issue planning work.
- Typical fit: create or update issue-level requirement/design/plan docs, prepare review readiness, or return unresolved execution gaps to authoring.
- Primary lifecycle / execution workflow: `spec-dock/docs/workflow_issue.md`.
- Spec authoring workflow: `spec-dock/docs/workflow_spec_authoring.md`.
- Clarification workflow for unresolved ambiguity, interview evidence, and source-grounded questions: `spec-dock/docs/workflow_clarification.md`.
- Issue plan phase playbook: `spec-dock/docs/phase_plan_issue.md`.
- Issue plan field semantics and executable step schema: `spec-dock/docs/authoring/issue-plan.md`.
- Keep canonical `requirement.md` / `design.md` / `plan.md` / `report.md` main-orchestrator-owned; this skill does not grant delegated canonical write authority.
- `system-architect` and `implementation-planner` drafts are scope-local evidence only. They do not replace main orchestrator integration, fresh `spec-reviewer` pass, phase promotion, implementation readiness, or issue execution handoff.
- In spec authoring mode, do not move from requirement to design, design to plan, or plan to execution until a fresh `spec-reviewer` returns `review_status: pass`; fix findings and re-run a fresh reviewer until pass.
- If planning reveals unresolved requirement / design / plan gaps, return to `workflow_clarification.md` or the relevant authoring phase instead of absorbing the gap in execution.
- Record each `Spec Authoring Gate` in the issue `report.md`, including investigation, user questions/answers, reviewer verdict, fixes, promotion decision, and handoff readiness.
