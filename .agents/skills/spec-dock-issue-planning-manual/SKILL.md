---
name: spec-dock-issue-planning-manual
description: Human-approved emergency backup skill for Issue planning when the ChatGPT-first primary route is hard-failed and unrecoverable.
---

# Spec-Dock Issue Planning Manual Backup

Use this skill only as the human-approved emergency backup for Issue planning. The normal route remains `spec-dock-issue-planning`, which is ChatGPT-first for non-trivial Issue planning through a single workflow with `requirement-heavy`, `draft-heavy`, and `context-heavy` input framing.

This backup route exists for hard / unrecoverable ChatGPT, browser automation, backend provider, or account-state failures that remain unresolved after wait / retry / recovery. Capacity limits, queued tabs, timeouts that can be retried, stale GitHub sync, missing prompt context, or fixable browser startup failures are not enough to use this skill.

## Required Preconditions

- The user explicitly approves using the manual route for this Issue planning task.
- Issue `report.md` records the failure class, recovery attempts, approval evidence, and why the primary ChatGPT-first route cannot be completed now.
- Active Issue docs, parent Epic docs, sibling/prior Issue evidence, artifacts, ADRs, source files, and tests have been inspected directly.
- The operator accepts that this route does not grant degraded reviewer, readiness, assurance, finish, or PR-delivery claims.

## Operating Spine

1. Confirm that the primary `spec-dock-issue-planning` route is unavailable for a hard / unrecoverable reason and that human approval exists.
2. Identify the dominant input context: `requirement-heavy`, `draft-heavy`, or `context-heavy`.
3. Refresh current repository state, prior completed Issues, dependency state, unresolved ledgers, and Issue-local draft evidence.
4. Author or formalize Issue `requirement.md`, `design.md`, and `plan.md` by normal phase order.
5. Record adopted and rejected draft claims, fallback rationale, reviewer verdicts, and promotion decisions in Issue `report.md`.
6. Require fresh `spec-reviewer` pass before claiming execution handoff readiness.

## Stop Conditions

- Human approval for manual route is missing.
- The failure is retryable, recoverable, capacity-related, waiting-related, or caused by missing local prompt/context setup.
- Draft adoption evidence is stale, contradictory, missing, or not recorded in the Evidence Adoption Ledger.
- The work would bypass canonical adoption, fresh `spec-reviewer`, or execution handoff gates.
- Any artifact would claim that the manual route itself grants reviewer pass, execution-ready, PR-ready, merge-ready, Issue finish, Epic completion, or PR delivery.
