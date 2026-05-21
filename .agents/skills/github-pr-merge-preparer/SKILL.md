---
name: github-pr-merge-preparer
description: Coordinate pull request creation or discovery, read-only monitoring, bounded fix delegation, re-push confirmation, and re-monitoring until a PR is merge-prepared for human judgment. Use when a workflow must continue after PR creation and report whether the PR is ready for a human merge decision without merging it.
---

# GitHub PR Merge Preparer

## Overview

Use this skill to coordinate the post-implementation PR delivery loop: create or find the PR, monitor the latest head SHA, classify monitor results, delegate bounded fixes when appropriate, confirm commit and push evidence, re-monitor, and finally report either `merge-prepared` evidence or a human gate.

This skill is a workflow coordinator. It reuses `github-pr-creator` for PR creation, `pr-monitor` for read-only checks/statuses/review monitoring, and appropriate repair workers for implementation fixes. It does not implement CI log parsing, review repair logic, or GitHub write operations beyond the delegated branch push needed after an approved fix.

## Inputs

- Current repository, branch, and working tree state.
- Optional PR URL or number.
- Optional explicit base branch.
- Active issue context and issue-link expectations when available.
- Local final gate status so draft/ready intent can be chosen safely.

## Workflow

1. Confirm the current branch, working tree, remote repository, active issue context, and whether a PR already exists for the branch.
2. Resolve the base branch:
   - Reuse an existing PR when one exists, and do not create a duplicate.
   - If an existing PR exists, use its base for monitoring. If the user requested a conflicting base, stop at a human gate before mutating the PR.
   - If no PR exists, prefer an explicit user base.
   - Otherwise respect `branch.<current>.gh-merge-base` when present.
   - If docs, config, or branch hints conflict and no existing PR resolves the conflict, stop at a human gate before creating a PR.
   - Fall back to the repository default branch only when no stronger source exists.
3. Decide draft versus ready:
   - If local final gates are known to have passed, create or keep a ready PR unless the user explicitly requested draft.
   - If local final gates are incomplete or unknown, create a draft PR or stop at a human gate; do not present it as merge-prepared.
4. Create or find the PR through `github-pr-creator`, requiring PR URL, number, open/closed state, base branch, head branch, issue linkage, and latest head SHA in the return.
5. Invoke `pr-monitor` with `repo`, `pr`, `head_sha`, and `reason: created | pushed | repushed`.
6. Treat monitor output as stale when it is not for the latest head SHA. After every push, obtain the new head SHA and re-run `pr-monitor`.
7. Classify failures with coarse labels only:
   - `check_failure:<job_or_check_name>`
   - `review_feedback:<topic>`
   - `merge_conflict`
   - `base_branch_conflict`
   - `permission_or_auth`
   - `external_or_flaky`
   - `timeout`
   - `unknown`
8. Delegate bounded fixes only for clearly actionable implementation failures or review feedback. The repair worker owns diagnosis, code changes, tests, commit, and push evidence for that bounded fix.
9. Confirm the delegated fix produced a commit and push for the PR head branch, then re-monitor the latest head SHA.
10. Stop with `merge-prepared` evidence when the predicate below is satisfied; otherwise stop at a human gate with the blocker history and recommended next action.

## Fix Loop Limits

- Default autonomous repair limit is two repair attempts for the same `failure_class`.
- Default total autonomous repair limit is four repair attempts per PR preparation invocation.
- Stop at a human gate when the same `failure_class` appears after a repair, either limit is reached, or the blocker is `permission_or_auth`, `external_or_flaky`, `base_branch_conflict`, `unknown`, a requirement expansion, a breaking change, a migration, a secret or deployment setting change, or ambiguous review intent.
- Record each loop as `iteration_index`, `head_sha`, `monitor_status`, `failure_class`, `action_taken`, and `next_action`.

## Merge-Prepared Predicate

Report `merge-prepared: yes` only when all of these are evidenced:

- PR is open.
- Monitor result is for the latest head SHA.
- No required check failure remains.
- No non-required check failure remains unless the check is known optional or the user explicitly waived it.
- Any waived non-required check failure is reported as residual risk.
- No blocking review feedback remains.
- No visible merge conflict or equivalent merge blocker remains.
- Review-thread unresolved state is known, or an unresolved-thread limitation is explicitly disclosed and waived by the user.

If unresolved review-thread state cannot be determined and is not explicitly waived, stop at a human gate. Do not hide the limitation.

## Forbidden Writes

This skill must not perform or authorize:

- PR merge.
- Auto-merge enablement.
- Branch deletion.
- GitHub issue close.
- Running `spec-dock issue finish` or otherwise closing the active issue lifecycle.
- Review comment reply.
- Review thread resolve.
- Review dismiss.
- Admin override.
- Direct modification of `pr-monitor` state or behavior.

## Human Gate Output

When stopping for a human gate, report:

- PR URL and number.
- Open/closed state.
- Base branch and head branch.
- Latest head SHA.
- Draft or ready state and why.
- Base-resolution source and any conflict.
- Monitor status and whether it matches the latest head SHA.
- Failure class history and attempted fixes.
- Non-required check waiver status, if relevant.
- Review-thread limitation status, if relevant.
- Remaining blocker and recommended next action.

## Response Checklist

- State whether a new PR was created or an existing PR was reused.
- State the selected base branch and why.
- State draft versus ready handling.
- Include PR URL, PR number, head branch, and latest head SHA.
- Summarize monitor results and fix-loop count.
- State whether the PR is `merge-prepared: yes` or `merge-prepared: no`.
- If `merge-prepared: yes`, include the evidence predicate and residual risks.
- If `merge-prepared: no`, include the human gate reason and next action.
- State explicitly that merge remains a human action.
