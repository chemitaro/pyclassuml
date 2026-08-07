---
name: spec-dock-epic-planning
description: ChatGPT-first Epic planning entrypoint for creating or refreshing Epic requirement, design, plan, and child Issue draft handoff artifacts in SpecDock.
---

# Spec-Dock Epic Planning

Use this skill for non-trivial Epic planning. This is the primary planning route and it is ChatGPT-first.

The old local/manual planning workflow is not the normal route. Use `spec-dock-epic-planning-manual` only as a human-approved emergency backup after the ChatGPT-first route is hard-failed and unrecoverable.

## Responsibility

This skill orchestrates Epic planning and Issue slicing. It asks ChatGPT to do the heavy planning draft, then Codex reviews and adopts the result into SpecDock canonical artifacts.

Codex owns:

- confirming parent Initiative and Epic fit;
- collecting repository, branch, parent Initiative, sibling Epic, artifact, ADR, and operator intent context;
- invoking `spec-dock-chatgpt-authoring` for the main Epic planning draft;
- reviewing ChatGPT output as evidence;
- adopting or rejecting claims in `report.md`;
- rewriting canonical Epic `requirement.md`, `design.md`, and `plan.md`;
- preserving human approval before Issue node creation;
- ensuring child Issue drafts remain handoff evidence until Issue Planning formalizes them;
- obtaining fresh `spec-reviewer` pass after canonical changes.

ChatGPT may produce:

- Epic requirement/design/plan candidates;
- Issue slice proposals;
- Issue-local draft requirement/design/plan artifacts;
- dependency order and boundary notes;
- final quality / mergeable PR delivery Issue proposal or skip rationale;
- optional ZIP/tree artifacts.

ChatGPT output is evidence only. It never grants canonical adoption, reviewer pass, execution readiness, Issue creation approval, Issue finish, Epic completion, mergeability, or PR delivery.

## Read First

- `spec-dock/docs/workflow_epic.md`
- `spec-dock/docs/workflow_spec_authoring.md`
- `spec-dock/docs/phase_plan_epic.md`
- `spec-dock/docs/authoring/chatgpt-pack.md`
- `spec-dock/docs/authoring/decision-routing.md`
- `spec-dock/docs/authoring/scope-layering.md`
- active Initiative/Epic docs and `report.md`, when present
- existing sibling Epics, Issues, dependencies, ADRs, artifacts, code, tests, and user-provided material relevant to the Epic

## Operating Spine

1. Confirm the Epic target.
   - Reuse an existing Epic when it fits.
   - Create or import a new Epic only when no existing Epic fits.
   - If parent Initiative is unclear, resolve that first.
2. Build a ChatGPT-first planning request.
   - Include repository and branch.
   - Prefer GitHub-synced context when the branch is pushed and visible.
   - Include explicit lower-authority labeling for local-context runs.
   - Include operator intent and development background as free-form context.
   - Request Epic `requirement.md`, `design.md`, `plan.md`, and child Issue draft artifacts.
   - Require Issue slicing, dependency order, responsibility boundaries, and final quality Issue policy.
   - Allow `information_insufficient` when the input cannot support planning.
3. Ask `spec-dock-chatgpt-authoring` for Epic planning evidence.
   - Wait, retry, or recover for capacity, timeout, stale sync, browser startup, or backend setup problems.
   - Do not auto-switch to manual planning.
   - Immediately after output is received, and before claim review, Evidence Adoption Ledger disposition, or canonical rewrite, invoke the shared `spec-dock-chatgpt-authoring` preservation checkpoint.
   - If its handoff is blocking, stop and propagate the block. Continue from `skipped_inline_unavailable` only when reason, decision owner, nonblocking rationale, and next action or revisit condition are all present.
   - Refer to the shared skill for branch, status, and import-result rules; do not copy that decision matrix here.
4. Review the returned evidence.
   - Check Epic scope, non-scope, architecture boundary, Issue slicing, dependencies, and missing decisions.
   - Check that child Issue drafts are handoff-ready evidence, not canonical Issue docs.
   - Check that multi-Issue implementation Epics include a final quality / mergeable PR delivery Issue.
   - Allow a separate final quality Issue to be skipped only for single-Issue, docs-only, or no-op Epics with explicit skip rationale and completion evidence.
   - Reject unsupported claims, stale repository assumptions, and any forbidden authority claims.
   - Record material adoption/rejection in `report.md`.
5. Write canonical Epic artifacts and handoff evidence.
   - Integrate only adopted claims into Epic `requirement.md`, `design.md`, and `plan.md`.
   - Store Issue drafts and path indexes as Issue-local or Epic-local artifacts according to the workflow.
   - Do not finalize child Issue canonical `requirement.md`, `design.md`, or `plan.md` during Epic Planning.
6. Run the authoring gate.
   - Obtain fresh `spec-reviewer` pass after substantive canonical changes.
   - Create Issue nodes only after reviewed Epic planning and human approval of the Issue slices.

## Manual Backup

Manual backup requires all of:

- hard / unrecoverable ChatGPT, browser, backend, provider, or account-state failure;
- reasonable wait / retry / recover attempts have failed;
- explicit human approval to use `spec-dock-epic-planning-manual`;
- failure class, recovery attempts, approval evidence, and fallback decision recorded in `report.md`.

Queued tabs, slow responses, retryable timeouts, stale sync, missing prompt context, or fixable setup are not manual fallback reasons.

## Stop Conditions

- Parent Initiative or Epic placement is unclear and local sources cannot resolve it.
- Repository/branch evidence required for ChatGPT-first planning is unavailable and no explicit local-context run was approved.
- ChatGPT returns `information_insufficient`; ask the human for the missing information instead of fabricating artifacts.
- ChatGPT output has not been adopted or rejected in `report.md`.
- Canonical artifacts changed after review and lack fresh `spec-reviewer` pass.
- Issue slicing would pass unresolved Epic decisions downstream.
- Issue node creation lacks explicit human approval.
- Child Issue drafts are being treated as execution-ready or canonical Issue docs.
- Manual fallback is requested without explicit human approval.
