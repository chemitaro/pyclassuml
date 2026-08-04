---
name: github-pr-creator
description: Delegate GitHub pull request work to an appropriate sub-agent and create pull requests safely from the current branch, including branch push, base branch selection, diff review, issue linkage, and `gh pr create` execution. Use when the user asks to create a pull request, push a branch for PR creation, run `gh pr create`, or draft a Japanese PR title/body from repository changes.
---

# GitHub PR Creator

## Overview

Use this skill to prefer delegation to an appropriate sub-agent, then push the current branch and create a GitHub pull request with a Japanese title and body grounded in the actual diff. PR creation is not necessarily the terminal workflow step: when post-create checks/statuses or Codex review observation is required, continue through the `github-pr-observation` skill scripts or `github-pr-merge-preparer`.

## Delegation Guidance

- Prefer handing PR creation work to an appropriate sub-agent instead of spending main-session context on branch push and `gh` execution details.
- `spark-worker` or `utility-worker` are usually good fits for this kind of bounded GitHub task. Choose whichever best matches the scope and complexity.
- When delegating, include the current branch, any explicit base branch, issue-link expectations, draft or ready intent if relevant, and the required return values: PR URL, selected base branch, issue-link outcome, or a clear blocker.
- After the PR is created or found, return the PR URL, PR number, selected base, head branch, and latest head SHA so the caller can invoke `./.agents/skills/github-pr-observation/scripts/fetch_pr_observation_snapshot.sh` or `./.agents/skills/github-pr-observation/scripts/wait_pr_observation.sh` directly when post-create observation is in scope.

## Workflow

1. Confirm the current branch, working tree, remotes, and whether a PR already exists for the branch if that matters to the request.
2. Resolve the base branch in this order: user-specified base branch, then repository default branch. Read the repository default branch from git metadata first with `git symbolic-ref refs/remotes/origin/HEAD` (strip the `origin/` prefix), or `git remote show origin` if `origin/HEAD` is unavailable. Only use `gh repo view --json defaultBranchRef` as a fallback when git metadata does not provide the answer.
3. Inspect the diff between the base branch and the current branch before writing anything. Review changed files, diff stats, and key hunks so the PR title/body reflect the actual behavior change.
4. Draft the PR title and body in Japanese from that understanding. Do not generate text from branch names or filenames alone.
5. Infer a related GitHub issue number from the current branch name when possible. Check common patterns such as `123-*`, `feature/123-*`, `fix/123-*`, `issue123`, `issue-123`, `owner/issue123`, `owner/issue-123`, or `#123-*`, then confirm if the mapping is ambiguous.
6. Add issue linkage to the PR body. Use `Closes #...` when the branch appears to complete the issue, otherwise use `Refs #...`.
7. Push the current branch before PR creation if needed. Prefer setting upstream explicitly so the branch is available to GitHub.
8. Create the PR with `gh pr create --base <base> --head <head> --title <title> --body-file <file>` or equivalent. For same-repo branches, use the branch name itself for `--head` first. Use `<owner>:<branch>` only when creating from a fork or when the owner must be specified to disambiguate the head repository.
9. Return the PR URL after creation. If a PR already exists, return that URL instead of opening a duplicate PR.
10. Return the created or existing PR details. When lightweight post-create observation is needed, call `./.agents/skills/github-pr-observation/scripts/fetch_pr_observation_snapshot.sh`; when the workflow must continue until a stable PR observation is available, proceed through `github-pr-merge-preparer` or invoke `./.agents/skills/github-pr-observation/scripts/wait_pr_observation.sh` directly.

## Safety Rules

- Do not assume a project-specific base branch such as `develop`.
- Treat `--head` as the source branch being merged from. Do not pass the base branch to `--head`.
- Determine the default branch from git metadata before consulting `gh`: prefer `git symbolic-ref refs/remotes/origin/HEAD`, then `git remote show origin`, and only then fall back to `gh repo view --json defaultBranchRef`.
- For same-repo PRs, pass `--head <current-branch>` first.
- Use `--head <owner>:<current-branch>` only for fork-based PRs or when `gh pr create` requires explicit owner disambiguation.
- When `gh pr create` says the head ref does not exist, push the branch first and retry.
- When authentication fails, check `gh auth status` first.
- When HTTPS git push fails because GitHub CLI credentials are not wired into git, run `gh auth setup-git` and retry.

## Minimal Command Pattern

```bash
git status --short
git branch --show-current
git symbolic-ref refs/remotes/origin/HEAD
git remote show origin
git diff --stat <base>...HEAD
git diff --name-only <base>...HEAD
git push -u origin <current-branch>
gh pr create --base <base> --head <current-branch> --title "<japanese-title>" --body-file /tmp/pr_body.md
# Fork or explicit owner disambiguation only:
gh pr create --base <base> --head <owner>:<current-branch> --title "<japanese-title>" --body-file /tmp/pr_body.md
```

## Response Checklist

- State which base branch was used and why.
- State how the issue number was inferred or that it could not be inferred automatically.
- Include `Closes #...` or `Refs #...` in the PR body when an issue is identified.
- Return the PR URL explicitly in the final response.
- If observation is part of the requested workflow, continue with `github-pr-observation` direct invocation or `github-pr-merge-preparer` instead of treating PR creation alone as the terminal step.
