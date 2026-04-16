---
name: spec-driven-tdd-workflow
description: Entry skill that routes work to the correct spec-dock leaf workflow.
---

# Spec-driven TDD Workflow (Hub)

- Use this as the entry/routing skill for spec-dock work.
- Keep `spec-dock/docs/` as the source of truth; skills stay concise.
- Route once the main output is clear; leaf skills own the workflow details.

## Route to leaf skills

- `spec-dock-initiative-planning`: initiative-level requirement/design/plan planning.
- `spec-dock-epic-planning`: epic-level requirement/design/plan planning.
- `spec-dock-issue-execution`: issue-level TDD execution and report updates.
- `spec-dock-adr-facilitation`: ADR drafting/decision facilitation linked to the current workflow.

## Direct references

- `spec-dock/docs/reference_github.md`
- `spec-dock/docs/reference_deps.md`
- `spec-dock/docs/reference_sync.md`
- `spec-dock/docs/reference_naming.md`

## Quick reminders

- Do not default to create/import for initiative/epic; inspect existing nodes first.
- Keep boundary rationale in `discussions/`; docs remain the source of truth for the rule itself.
- Put interview and investigation notes under `discussions/` in the active node.
- `spec-dock/active/context-pack.md` is the execution entrypoint for active issue work.
- Discussion doc example: `./spec-dock/scripts/spec-dock new doc adr --issue iss-00123 --title "..."`
- Runtime path guardrail: use only `./spec-dock/scripts/spec-dock ...` and avoid legacy command aliases.
- For concrete dependency and completion commands, route to `spec-dock-issue-execution` and the reference docs.
