---
name: spec-dock-epic-planning-manual
description: Human-approved emergency backup skill for Epic planning when the ChatGPT-first primary route is hard-failed and unrecoverable.
---

# Spec-Dock Epic Planning Manual Backup

Use this skill only as the human-approved emergency backup for Epic planning. The normal route remains `spec-dock-epic-planning`, which is ChatGPT-first for non-trivial Epic planning, Issue slicing, and Issue draft handoff.

This backup route exists for hard / unrecoverable ChatGPT, browser automation, backend provider, or account-state failures that remain unresolved after wait / retry / recovery. Capacity limits, queued tabs, timeouts that can be retried, stale GitHub sync, missing prompt context, or fixable browser startup failures are not enough to use this skill.

## Required Preconditions

- The user explicitly approves using the manual route for this Epic planning task.
- Epic `report.md` records the failure class, recovery attempts, approval evidence, and why the primary ChatGPT-first route cannot be completed now.
- Parent Initiative, sibling Epics, active Epic docs, artifacts, ADRs, source files, and tests have been inspected directly.
- The operator accepts that this route does not grant degraded reviewer, readiness, assurance, finish, or PR-delivery claims.

## Operating Spine

1. Confirm that the primary `spec-dock-epic-planning` route is unavailable for a hard / unrecoverable reason and that human approval exists.
2. Build source-grounded Epic understanding from repository facts, artifacts, user answers, and accepted ADRs.
3. Author Epic `requirement.md`, `design.md`, and `plan.md` by normal phase order.
4. Prepare Issue slices, Issue-local draft requirement/design/plan artifacts, dependency order, and final quality Issue required/skipped rationale.
5. Record all decisions, skipped ChatGPT evidence, fallback rationale, Issue draft paths, and promotion decisions in Epic `report.md`.
6. Require fresh `spec-reviewer` pass before claiming Epic planning promotion or Issue node creation readiness.

## Stop Conditions

- Human approval for manual route is missing.
- The failure is retryable, recoverable, capacity-related, waiting-related, or caused by missing local prompt/context setup.
- Issue node creation lacks explicit human approval.
- The work would finalize canonical child Issue docs during Epic planning instead of leaving them for Issue planning.
- Any artifact would claim that the manual route itself grants reviewer pass, execution-ready, PR-ready, merge-ready, Issue finish, Epic completion, or PR delivery.
