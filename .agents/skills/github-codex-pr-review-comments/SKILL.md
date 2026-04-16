---
name: github-codex-pr-review-comments
description: Fetch Codex review feedback posted to a GitHub Pull Request (inline review comments, PR conversation comments, and review bodies) via GitHub REST API using curl+jq. Use when you need all Codex review comments for a PR, especially when `gh pr view --comments` fails (e.g., GraphQL Projects classic errors) or `gh api` is restricted by policy.
---

# GitHub Codex PR Review Comments

## Quick start

1) Ensure a GitHub token is available (read-only is enough for public repos):

- Preferred: `GH_TOKEN`
- Fallback: `GITHUB_TOKEN`

2) Run the bundled script:

```bash
./scripts/fetch_codex_pr_review_comments.sh --repo OWNER/REPO --pr 13 --out /tmp/pr13
```

3) Read the report:

- `/tmp/pr13/codex_report.md` (Codex-only, human readable)
- Raw JSON snapshots (useful for auditing/parsing): `issue_comments.json`, `review_comments.json`, `reviews.json`

## What this skill fetches

- **PR conversation comments**: `GET /repos/{owner}/{repo}/issues/{pr}/comments`
- **Inline review comments** (diff lines): `GET /repos/{owner}/{repo}/pulls/{pr}/comments`
  - Replies are included and can be related via `in_reply_to_id`.
- **Review bodies** (`APPROVED`/`COMMENTED`): `GET /repos/{owner}/{repo}/pulls/{pr}/reviews`

## Why REST API (curl) instead of `gh pr view --comments`

`gh pr view --comments` can fail depending on repository settings because it uses GitHub GraphQL fields that may error (e.g., Projects classic deprecation). This skill uses the REST API endpoints above and works even when that happens.

## Script usage

```bash
./scripts/fetch_codex_pr_review_comments.sh \
  --repo OWNER/REPO \
  --pr 13 \
  --out /tmp/pr13
```

### Codex detection heuristic

The report includes comments/reviews where `user.login` contains `codex` (case-insensitive).

If your repo uses a different bot login, adjust the jq filter inside the script.

## Troubleshooting

- **`error: GH_TOKEN or GITHUB_TOKEN is not set`**: export a token env var and re-run.
- **Rate limits**: the script is read-only but still subject to GitHub rate limits; re-run later or use a token with sufficient allowance.
