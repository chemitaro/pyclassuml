---
name: spec-dock-clarification
description: First-read source-grounded grill workflow for SpecDock clarification, one-question user interviews, analysis-only clarification, and authoring handoff.
---

# Spec-Dock Clarification

Use this skill when the user asks to clarify requirements, sharpen wording, resolve ambiguity, prepare questions, align understanding before requirement / design / plan authoring, or run analysis-only clarification.

This skill owns the source-grounded grill loop. Use `spec-dock/docs/workflow_clarification.md` only for detailed artifact semantics, formal question lifecycle, and adoption evidence guidance.

Decision routing examples and detailed placement guidance live in `spec-dock/docs/authoring/decision-routing.md`. Use that doc when clarification finds a decision-only Issue, cross-issue Epic decision, cross-epic Initiative decision, ADR candidate, or missing source-of-truth gap; keep this skill limited to the stop/routing loop.

質問、調査結果、adoption target の配置判断で scope ownership が迷う場合は、Initiative / Epic / Issue の authority boundary を確認する薄い入口として `spec-dock/docs/authoring/scope-layering.md` を参照する。

## Source-Grounded Grill Loop

1. Read sources before asking: current request and attachments, `./spec-dock/scripts/spec-dock active show`, active docs, parent docs, scope-local `artifacts/`, legacy `discussions/` when present for historical context, related code/tests/templates, and ADRs.
   - For attachments, first create an inventory of filenames, paths, and high-level contents before deciding what to ask.
   - If the final target scope does not exist yet and a parent scope is known, keep attachment inventory as provisional evidence under that parent scope. If no parent scope is known, do not create durable repo artifacts yet; keep only session-local inventory in the host/session temp area outside canonical docs until placement is resolved.
   - If parent scope is required, inspect active state and nearby nodes before asking the user to choose placement.
2. Build a provisional understanding in plain language: what seems decided, what is ambiguous, what local context already answers, and what would change downstream artifacts.
3. Do gap classification:
   - source-grounded answer available: answer or proceed without asking the user.
   - low-impact uncertainty: mention the assumption and continue if safe.
   - decision-only routing gap: stop implementation/planning handoff and route to Issue-local, Epic, Initiative, ADR, or clarification using `spec-dock/docs/authoring/decision-routing.md`.
   - user-intent blocker: stop and ask the user directly.
   - durable tradeoff: prepare `disc` or ADR triage, then route adoption through canonical docs.
4. Pick one pressure-test question only when it would change scope, requirement, design, plan, ADR, template, workflow, or adoption evidence.
5. Do artifact capture before asking important questions with `new artifact` under the scope-local `artifacts/` catalog:
   - use `blank` for raw or freeform capture.
   - create unanswered `interview` for one important user question.
   - use `research` for facts, uncertainty, edge cases, and question candidates.
   - use `disc` for synthesis, options, ADR candidate triage, and adoption target.
6. After the answer, record answer adoption in the same artifact when applicable, then update canonical docs or `report.md` Evidence Adoption Ledger / Objective Alignment Ledger / Spec Authoring Gate.
7. Iterate or handoff:
   - if another high-impact question remains, create the next unanswered `interview`.
   - if enough is clear, hand off to requirement / design / plan authoring or return analysis-only output.

## User Question Boundary

- Do not ask the user about anything local sources can answer.
- Ask at most one essential question at a time through the orchestrator.
- If user-intent clarification is genuinely blocking, block the work and ask the user directly; do not use deep-consultant, specialist agents, or other proxies as a substitute for the user's answer.
- Specialist agents may return question candidates, rationale, options, and recommended wording to the orchestrator. They must not question the human directly.

## Modes

- `analysis-only`: return sources read, provisional understanding, resolved assumptions, unresolved questions, recommended next question, and suggested artifact. Do not force canonical docs.
- `draft-only`: write scope-local artifact drafts only when requested or workflow-approved. Drafts are proposed evidence until adopted.
- `canonical authoring`: route adopted clarification evidence into requirement / design / plan / ADR and record adoption in `report.md`.

## Handoff Output

Return:

- sources read
- provisional understanding
- gap classification
- unresolved questions, or `none`
- one recommended pressure-test question, if any
- suggested artifact: `blank` / `research` / `interview` / `disc`
- mode: `analysis-only` / `draft-only` / `canonical authoring`
- answer adoption / handoff target
- adoption evidence needed in `report.md`
