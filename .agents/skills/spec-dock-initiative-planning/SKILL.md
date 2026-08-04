---
name: spec-dock-initiative-planning
description: ChatGPT-first Initiative planning entrypoint for creating or refreshing Initiative requirement, design, plan, and Epic decomposition artifacts in SpecDock.
---

# Spec-Dock Initiative Planning

Use this skill for non-trivial Initiative planning. This is the primary planning route and it is ChatGPT-first.

The old local/manual planning workflow is not the normal route. Use `spec-dock-initiative-planning-manual` only as a human-approved emergency backup after the ChatGPT-first route is hard-failed and unrecoverable.

## Responsibility

This skill orchestrates Initiative planning. It does not ask Codex to hand-author the whole Initiative through many local micro-steps unless the human explicitly approves the manual backup route.

Codex owns:

- selecting or creating the correct Initiative scope;
- collecting repository, branch, artifact, ADR, and operator intent context;
- invoking `spec-dock-chatgpt-authoring` for the main planning draft;
- reviewing ChatGPT output as evidence;
- adopting or rejecting claims in `report.md`;
- rewriting canonical Initiative `requirement.md`, `design.md`, and `plan.md`;
- obtaining fresh `spec-reviewer` pass after canonical changes;
- preserving the human approval gate before Epic creation.

ChatGPT may produce:

- Initiative requirement/design/plan candidates;
- Epic decomposition proposals;
- Epic boundary and dependency notes;
- risk, open-question, and reviewer-focus notes;
- optional ZIP/tree artifacts.

ChatGPT output is evidence only. It never grants canonical adoption, reviewer pass, readiness, Issue/Epic lifecycle completion, mergeability, or PR delivery.

## Read First

- `spec-dock/docs/workflow_initiative.md`
- `spec-dock/docs/workflow_spec_authoring.md`
- `spec-dock/docs/authoring/chatgpt-pack.md`
- `spec-dock/docs/authoring/decision-routing.md`
- `spec-dock/docs/authoring/scope-layering.md`
- active Initiative docs and `report.md`, when present
- parent/product context, ADRs, artifacts, code, tests, and user-provided material relevant to the Initiative

## Operating Spine

1. Confirm the Initiative target.
   - Reuse an existing Initiative when it fits.
   - Create or import a new Initiative only when no existing Initiative fits.
   - Record new-Initiative rationale in scope-local artifacts or `report.md`.
2. Build a ChatGPT-first planning request.
   - Include repository and branch.
   - Prefer GitHub-synced context when the branch is pushed and visible.
   - Include explicit lower-authority labeling for local-context runs.
   - Include operator intent and development background as free-form context.
   - Request Initiative `requirement.md`, `design.md`, `plan.md`, and Epic decomposition context.
   - Allow `information_insufficient` when the input cannot support planning.
3. Ask `spec-dock-chatgpt-authoring` for Initiative planning evidence.
   - Wait, retry, or recover for capacity, timeout, stale sync, browser startup, or backend setup problems.
   - Do not auto-switch to manual planning.
   - Immediately after output is received, and before claim review, Evidence Adoption Ledger disposition, or canonical rewrite, invoke the shared `spec-dock-chatgpt-authoring` preservation checkpoint.
   - If its handoff is blocking, stop and propagate the block. Continue from `skipped_inline_unavailable` only when reason, decision owner, nonblocking rationale, and next action or revisit condition are all present.
   - Refer to the shared skill for branch, status, and import-result rules; do not copy that decision matrix here.
4. Review the returned evidence.
   - Check scope, non-scope, success criteria, Epic boundaries, dependencies, risks, and missing decisions.
   - Reject unsupported claims, stale repository assumptions, and any forbidden authority claims.
   - Record material adoption/rejection in `report.md`.
5. Write canonical Initiative artifacts.
   - Integrate only adopted claims into `requirement.md`, `design.md`, and `plan.md`.
   - Keep raw ChatGPT output in artifacts, not as canonical authority.
6. Run the authoring gate.
   - Obtain fresh `spec-reviewer` pass after substantive canonical changes.
   - Do not create Epic nodes until the Initiative planning gate and human approval point are satisfied.

## Manual Backup

Manual backup requires all of:

- hard / unrecoverable ChatGPT, browser, backend, provider, or account-state failure;
- reasonable wait / retry / recover attempts have failed;
- explicit human approval to use `spec-dock-initiative-planning-manual`;
- failure class, recovery attempts, approval evidence, and fallback decision recorded in `report.md`.

Queued tabs, slow responses, retryable timeouts, stale sync, missing prompt context, or fixable setup are not manual fallback reasons.

## Stop Conditions

- Initiative placement is unclear and local sources cannot resolve it.
- Repository/branch evidence required for ChatGPT-first planning is unavailable and no explicit local-context run was approved.
- ChatGPT returns `information_insufficient`; ask the human for the missing information instead of fabricating artifacts.
- ChatGPT output has not been adopted or rejected in `report.md`.
- Canonical artifacts changed after review and lack fresh `spec-reviewer` pass.
- Epic decomposition would pass unresolved Initiative decisions downstream.
- Manual fallback is requested without explicit human approval.
