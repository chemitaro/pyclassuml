---
name: spec-dock-epic-execution
description: Coordinator skill for executing a reviewed SpecDock Epic one Issue at a time, routing each Issue to planning, execution, PR delivery, or a documented blocker.
---

# Spec-Dock Epic Execution

Use this skill after Epic planning is complete and Epic `requirement.md`, `design.md`, and `plan.md` have fresh reviewer-gated handoff evidence. This skill coordinates downstream work; it is not a semantic reviewer, Issue executor, PR preparer, or runtime command designer.

This skill is a fixed kernel / operational kernel. Keep detailed lifecycle semantics in `spec-dock/docs/workflow_epic.md`, `spec-dock/docs/workflow_issue.md`, and the routed leaf skills.

## Read First

- Current state: `./spec-dock/scripts/spec-dock active show`
- Active or requested Epic:
  - active Epic / requested-Epic resolution evidence
  - reviewer-gated `requirement.md`, `design.md`, `plan.md`
  - `report.md` as evidence ledger for unresolved blockers, decisions, handoff state, and reviewer gates
- Active Issue and GitHub freshness:
  - active Issue state
  - GitHub freshness evidence when PR state, GitHub issue state, or remote branch state can affect routing
- Downstream handoff package:
  - Issue list
  - dependency order
  - responsibility boundaries
  - draft artifact path index or skip evidence
  - expected verification
  - reviewer focus
  - delegation contract
  - PR delivery policy, including any deferred final-quality-Issue path
- Freshness checks as needed: `validate`, `sync`, `sync --github`, `git status`, `git fetch`, GitHub inspection.

## Operating Spine

1. Resolve Epic context.
   - If no active/requested reviewed Epic handoff exists, route back to Epic planning.
   - Do not treat Epic `report.md` as a reviewer-gated planning artifact; treat it as evidence ledger.
2. Respect any active Issue.
   - If an active Issue exists, do not start another Issue.
   - Continue, repair planning, evaluate finish readiness, or ask for a user decision about the active Issue.
3. Select exactly one next Issue.
   - Use the Epic plan, projections, and `./spec-dock/scripts/spec-dock deps check <issue-id>` (`deps check`).
   - If multiple Issues are ready, choose one by dependency order, priority, and risk; stop if that cannot be justified.
   - If no Issue is ready while executable work remains, record blocker evidence and stop.
   - If the Epic is intentionally no-op or has no executable Issue work, record the no-op Epic completion evidence path instead of creating Issues.
4. Start the selected Issue through lifecycle command.
   - Use `./spec-dock/scripts/spec-dock issue start <issue-id>`.
   - Treat `active set` as recovery/manual only, not normal execution.
5. Route by readiness.
   - Missing, template-only, stale, unreviewed, non-executable, or draft-only Issue docs -> `spec-dock-issue-planning`.
   - Fresh reviewer-passed canonical docs plus executable `plan.md` -> `spec-dock-issue-execution`.
   - Pre-start `draft-design` / `draft-plan` are evidence-only input for Issue planning.
   - Treat `handoff-ready` as planning transfer evidence and `execution-ready` as the Issue-level state required before implementation.
   - Never treat decision-only execution-ready claims as valid executable Issue work.
   - Record structural blocker / structural blockers when readiness, dependency, or handoff evidence cannot justify a next executable Issue.
   - Preserve reviewer finding / reviewer findings as blocker or follow-up evidence instead of self-claiming reviewer pass.
   - Do not promote raw artifact authority; only adopted canonical docs and recorded evidence may drive routing.
   - Keep user-facing summaries Japanese-first / 日本語ファースト while preserving paths, commands, identifiers, and external proper nouns.
6. Preserve PR delivery policy.
   - If the reviewed Epic plan requires per-Issue PR delivery, hand off to `github-pr-merge-preparer` after Issue final local gates.
   - If PR delivery is intentionally deferred to a final quality Issue, do not invoke PR preparation for intermediate Issues.
   - Intermediate Issues need deferred PR delivery evidence in `report.md`: final quality Issue id, dependency edge, no-per-Issue-PR rationale, no merge-prepared claim before final PR delivery, and reviewer-confirmed local completion / issue finish conditions.
7. Finish only with workflow-owned evidence.
   - This skill never claims reviewer pass, issue finish, delivery completion, merge-prepared status, PR merge readiness, GitHub closure, or Epic completion by itself.
   - Run `issue finish` only after merge-prepared evidence and workflow-owned completion gates; do not run `issue finish` from an issue-finish self-claim.
   - Use the routed workflow's completion gates and preserve blocked/stale/human-gate evidence when they occur.

## Stop Conditions

- Active Issue exists and needs continuation, planning repair, finish evaluation, or user decision.
- Reviewed Epic planning handoff is missing, stale, or contradicted by `report.md`.
- Dependency state is stale, unavailable, or cannot justify a single next Issue.
- Selected Issue cannot be started through `issue start`.
- Issue specs are template-only, draft-only, stale, unreviewed, not executable, or only handoff-ready when execution-ready is required.
- Structural blocker evidence exists in Epic or Issue docs, handoff package, reviewer gates, delegation contract, verification contract, or report ledger.
- PR preparation returns blocked, stale-head, unresolved review-thread limitation, failed checks, merge conflict, permission/auth, timeout, or human-gate evidence.
- The next action would require runtime command changes, dependency algorithm changes, PR merge/auto-merge, GitHub issue close, reviewer-pass self-claim, issue-finish self-claim, or replacing existing skills.

## Non-Goals

- Do not change runtime commands or dependency algorithms.
- Do not replace `spec-dock-epic-planning`, `spec-dock-issue-planning`, `spec-dock-issue-execution`, or `github-pr-merge-preparer`.
- Do not create unnecessary Issues for no-op/small Epics.
- Do not merge PRs, enable auto-merge, close GitHub issues, resolve review threads, or dismiss reviews.
- Do not claim reviewer pass.
