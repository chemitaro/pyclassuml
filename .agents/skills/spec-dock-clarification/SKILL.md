---
name: spec-dock-clarification
description: First-class docs-aware clarification workflow for source-grounded questions, analysis-only clarification, and spec authoring handoff.
---

# Spec-Dock Clarification

Use this skill when the user asks to clarify requirements, sharpen wording, resolve ambiguity, prepare questions, or align understanding before requirement / design / plan authoring.

Keep this skill concise. `spec-dock/docs/workflow_clarification.md` is the source of truth.

## Reminders

- Read source first: active docs, parent docs, `discussions/`, related code/tests/templates, and ADRs.
- Do not ask the user about anything local context can answer.
- Traverse the decision tree and ask at most one essential question at a time through the orchestrator.
- For important decisions, create an unanswered `interview` artifact before asking; complete the same artifact after the answer.
- Sharpen domain language with existing docs/code terms, concrete scenarios, and edge cases.
- Use `research` for facts, `disc` for synthesis / ADR triage, and ADR only for durable tradeoff decisions.
- Support analysis-only / draft-only mode without forcing canonical docs.
- In authoring mode, route adoption through canonical docs and `report.md` Evidence Adoption Ledger / Objective Alignment Ledger / Spec Authoring Gate.
- Specialist agents return question candidates to the orchestrator; they do not question the human directly.

## Handoff

Return:

- sources read
- unresolved questions, or `none`
- recommended next question, if any
- suggested artifact: `scratch` / `research` / `interview` / `disc` / `adr`
- authoring mode: analysis-only / draft-only / canonical authoring
- adoption evidence needed in `report.md`
