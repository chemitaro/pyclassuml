---
name: spec-dock-hub
description: Entry/routing skill for SpecDock work; use it as the route selector for leaf workflows and the global invariant surface.
---

# SpecDock Hub

- Use this as the SpecDock Hub: the entry/routing skill, route selector, and global invariant surface for SpecDock work.
- Keep this hub focused on route selection and cross-workflow invariants; leaf skills own task-specific workflow spines.
- Use skills for the first-read workflow spine: mandatory next actions, stop conditions, reviewer gates, and handoff boundaries an agent must know before following links.
- Use `spec-dock/docs/` for detailed semantics, field meanings, lifecycle policy, hard cases, and reference material.
- Use templates as minimum authoring scaffolds and evidence slots only. Examples and detailed guidance belong in docs, not templates. Templates are not compliance authorities.
- Route to docs for detailed explanations instead of copying schema or policy into skills.
- Use `spec-dock/docs/workflow_spec_authoring.md` for detailed requirement / design / plan phase promotion semantics across Initiative, Epic, and Issue.
- Use `spec-dock-clarification` for skill-owned, source-grounded clarification when the request is to clarify ambiguous requirements, sharpen domain language, prepare one-question-at-a-time interviews, or work in analysis-only / draft-only mode before canonical authoring; use `spec-dock/docs/workflow_clarification.md` for artifact semantics and reference details.
- In spec authoring mode, each artifact must pass a fresh `spec-reviewer` (`review_status: pass`) before the next phase starts; fix findings and re-run a fresh reviewer until pass.
- A user request to use a SpecDock workflow is explicit workflow-scoped authorization to use the SpecDock-defined named sub-agents and reviewers required by that workflow.
- Do not ask for additional per-role or per-phase permission before invoking SpecDock-defined named roles within the active repo/worktree, active SpecDock scope, current session, and documented role responsibility.
- Ask the user only for scope expansion, destructive actions, external publishing, credentialed external mutation, private external systems, or roles outside the SpecDock workflow.
- ユーザーが SpecDock workflow の利用を依頼した場合、その依頼自体を、SpecDock が定義する named sub-agent / reviewer を workflow に従って利用する明示的な許可として扱う。
- active repo/worktree、active SpecDock scope、current session、documented role responsibility の範囲内では、role ごと・phase ごとの追加承認を求めない。
- scope expansion、破壊的操作、外部公開、credential を伴う外部 mutation、private external system、SpecDock workflow 外の role 利用は別途確認する。
- Missing, stale, failed, unavailable, denied, waived, or provisional reviewer results are not `review_status: pass`. Do not route to implementation or completion by treating them as degraded success.
- Canonical docs are main orchestrator-owned; sub-agent, external, and discussion outputs remain evidence until adopted into canonical docs with `report.md` evidence.
- Agents may add, remove, merge, reorder, or rewrite template sections when it improves correctness, human understanding, or agent executability for the specific project.
- Use `spec-dock/docs/phase_design.md` as the source of truth for optional diagram choices. Add useful UML / PlantUML / table sections from the catalog, or project-specific sections outside the catalog, when they clarify structure, boundaries, responsibility, flow, state, or dependency.
- Route once the main output is clear; leaf skills own the first-read spine for their workflow and docs own detailed semantics.

## Route to leaf skills

- `spec-dock-initiative-planning`: initiative-level requirement/design/plan planning.
- `spec-dock-epic-planning`: epic-level requirement/design/plan planning.
- `spec-dock-epic-execution`: epic execution coordination after Epic planning is complete; selects one ready Issue at a time, routes to Issue planning/execution, and hands PR delivery to the merge-preparer without replacing issue execution.
- `spec-dock-issue-planning`: issue-level requirement/design/plan planning, review readiness, and implementation handoff readiness.
- `spec-dock-issue-execution`: issue-level implementation / verification execution and report updates after approved / reviewer-pass planning artifacts and an executable `plan.md` are ready.
- `spec-dock-chatgpt-authoring`: shared evidence lane for ChatGPT / Oracle prompt packs, ZIP/tree outputs, and candidate reports used by planning workflows; it never owns canonical docs, reviewer gates, assurance state, execution readiness, or PR delivery.
- `spec-dock-initiative-planning-manual`, `spec-dock-epic-planning-manual`, `spec-dock-issue-planning-manual`: human-approved emergency backup planning routes only after hard / unrecoverable ChatGPT-first route failure, recovery attempts, and explicit user approval.
- `spec-dock-clarification`: first-class docs-aware clarification companion for planning, source-grounded ambiguity, one-question-at-a-time user clarification through the orchestrator, and analysis-only / authoring handoff.
- `system-architect` agent role: delegated architecture analysis and draft design evidence created through `./spec-dock/scripts/spec-dock new artifact ...` and written to the returned scope-local `artifacts/` path. Canonical docs remain main-orchestrator-only. Role behavior is encapsulated in `.codex/agents/system-architect.toml`, not in a skill.
- `implementation-planner` agent role: delegated planning analysis and draft plan evidence created through `./spec-dock/scripts/spec-dock new artifact ...` and written to the returned scope-local `artifacts/` path. Canonical docs remain main-orchestrator-only. Role behavior is encapsulated in `.codex/agents/implementation-planner.toml`, not in a skill.
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
- Keep boundary rationale in `artifacts/`; docs carry detailed rule semantics while skills expose the operational steps needed before consulting them. Existing `discussions/` remain legacy/preservation evidence.
- Route clarification work to `spec-dock-clarification`; keep detailed clarification artifact semantics in `spec-dock/docs/workflow_clarification.md`.
- Sub-agent authoring outputs may be created through the runtime `new artifact` command and then direct-written at the returned target scope `artifacts/` path, but they do not become canonical authority until the main orchestrator adopts them in canonical docs and records the adoption in `report.md`.
- Record `Spec Authoring Gate` evidence in the active node's `report.md` for each requirement / design / plan promotion.
- For issue work, route requirement/design/plan authoring and unresolved source-grounded ambiguity to `spec-dock-issue-planning` with `spec-dock-clarification` as needed before execution.
- If issue planning and execution are both requested, complete planning artifacts, fresh reviewer gates, and handoff readiness evidence before routing to `spec-dock-issue-execution`.
- `spec-dock/active/context-pack.md` is the execution entrypoint for active issue work.
- Artifact example: `./spec-dock/scripts/spec-dock new artifact adr --issue iss-00123 --title "..."`
- Runtime path guardrail: use only `./spec-dock/scripts/spec-dock ...` and avoid legacy command aliases.
- For concrete dependency and completion commands, route to `spec-dock-issue-execution` and the reference docs.
