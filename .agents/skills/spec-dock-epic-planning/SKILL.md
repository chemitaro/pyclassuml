---
name: spec-dock-epic-planning
description: Leaf skill for epic planning tasks in spec-dock.
---

# Spec-dock Epic Planning

- Use this skill for epic planning work.
- Typical fit: create/import an epic, or update epic-level requirement/design/plan docs.
- Prefer reusing/updating an existing epic first; create/import only when no existing epic fits.
- Primary workflow: `spec-dock/docs/workflow_epic.md`.
- Spec authoring workflow: `spec-dock/docs/workflow_spec_authoring.md`.
- For shared phase authoring method, use:
  - `spec-dock/docs/phase_requirement.md`
  - `spec-dock/docs/phase_design.md`
  - `spec-dock/docs/phase_plan.md`
- Keep scope-specific constraints and decisions in `workflow_epic.md`.
- In spec authoring mode, do not move from requirement to design, design to plan, or plan to Issue decomposition until a fresh `spec-reviewer` returns `review_status: pass`; fix findings and re-run a fresh reviewer until pass.
- Record each `Spec Authoring Gate` in the epic `report.md`, including investigation, user questions/answers, reviewer verdict, fixes, and promotion decision.
- Bounded depth=2 delegation is allowed only as main orchestrator -> epic planning authoring specialist -> leaf-only evidence producer.
- Depth=3 / grandchild delegation is forbidden.
- Leaf-only evidence producers must not edit canonical artifacts, perform implementation edits, claim final authority, claim reviewer pass, or claim phase promotion / issue ready / issue finish.
- Preflight reviewer output is improvement input only; final fresh reviewer pass remains independent.
- Do not default to create/import; keep new-epic rationale in `discussions/`.
- `spec-dock/docs/reference_github.md`
- `spec-dock/docs/reference_sync.md`
- `spec-dock/docs/reference_naming.md`
