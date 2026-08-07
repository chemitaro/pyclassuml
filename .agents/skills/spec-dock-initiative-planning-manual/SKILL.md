---
name: spec-dock-initiative-planning-manual
description: Human-approved emergency backup skill for Initiative planning when the ChatGPT-first primary route is hard-failed and unrecoverable.
---

# Spec-Dock Initiative Planning Manual Backup

Use this skill only as the human-approved emergency backup for Initiative planning. The normal route remains `spec-dock-initiative-planning`, which is ChatGPT-first for non-trivial Initiative planning.

This backup route exists for hard / unrecoverable ChatGPT, browser automation, backend provider, or account-state failures that remain unresolved after wait / retry / recovery. Capacity limits, queued tabs, timeouts that can be retried, stale GitHub sync, missing prompt context, or fixable browser startup failures are not enough to use this skill.

## Required Preconditions

- The user explicitly approves using the manual route for this planning task.
- `report.md` records the failure class, recovery attempts, approval evidence, and why the primary ChatGPT-first route cannot be completed now.
- The active scope, related Initiative/Epic docs, artifacts, ADRs, and source files have been inspected directly.
- The operator accepts that this route does not grant degraded reviewer, readiness, assurance, finish, or PR-delivery claims.

## Operating Spine

1. Confirm that the primary `spec-dock-initiative-planning` route is unavailable for a hard / unrecoverable reason and that human approval exists.
2. Build source-grounded Initiative understanding from repository facts, artifacts, user answers, and accepted ADRs.
3. Author Initiative `requirement.md`, `design.md`, `plan.md`, and bounded Epic decomposition by the normal phase order.
4. Record all decisions, skipped ChatGPT evidence, fallback rationale, and promotion decisions in Initiative `report.md`.
5. Require fresh `spec-reviewer` pass before claiming phase promotion or downstream Epic creation readiness.

## Stop Conditions

- Human approval for manual route is missing.
- The failure is retryable, recoverable, capacity-related, waiting-related, or caused by missing local prompt/context setup.
- The work would bypass Evidence Adoption Ledger, canonical rewrite, or fresh reviewer gates.
- Epic candidate creation lacks explicit human approval.
- Any artifact would claim that the manual route itself grants reviewer pass, execution-ready, PR-ready, merge-ready, Issue finish, Epic completion, or PR delivery.
