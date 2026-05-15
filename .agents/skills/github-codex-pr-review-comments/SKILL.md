---
name: github-codex-pr-review-comments
description: Fetch Codex review feedback posted to a GitHub Pull Request (inline review comments, PR conversation comments, and review bodies) via a fixed read-only `gh api --method GET` wrapper. Use when you need PR review data without allowing direct arbitrary GitHub API calls.
---

# GitHub Codex PR Review Comments

## Quick start

1) Ensure `gh` is authenticated for the target repository.

2) Run the bundled script:

```bash
./scripts/fetch_codex_pr_review_comments.sh --repo OWNER/REPO --pr 13 --out /tmp/pr13
```

3) Read the report:

- `/tmp/pr13/codex_report.md` (Codex-only, human readable)
- `/tmp/pr13/review_data.json` (normalized wrapper output)
- Raw JSON snapshots (useful for auditing/parsing): `issue_comments.json`, `review_comments.json`, `reviews.json`

## What this skill fetches

- **PR conversation comments**: `GET /repos/{owner}/{repo}/issues/{pr}/comments`
- **Inline review comments** (diff lines): `GET /repos/{owner}/{repo}/pulls/{pr}/comments`
  - Replies are included and can be related via `in_reply_to_id`.
- **Review bodies** (`APPROVED`/`COMMENTED`): `GET /repos/{owner}/{repo}/pulls/{pr}/reviews`

## Why a fixed REST GET wrapper instead of `gh pr view --comments` or direct `gh api`

`gh pr view --comments` can fail depending on repository settings because it uses GitHub GraphQL fields that may error (e.g., Projects classic deprecation). This skill uses the REST API endpoints above and works even when that happens.

Direct `gh api` is intentionally not the public interface for agents because it can perform write operations. The bundled script is the boundary: it accepts only `--repo`, `--pr`, and optional `--out`, validates those values, and internally calls only the fixed REST GET endpoints listed above with `gh api --method GET --paginate --slurp`.

Do not add passthrough flags for method, endpoint, request body, headers, jq, or GraphQL query input.

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

- **`error: gh is required`**: install or expose GitHub CLI in `PATH`.
- **GitHub authentication errors**: run `gh auth status` outside the agent or ensure the agent environment has a usable token.
- **Rate limits**: the script is read-only but still subject to GitHub rate limits; re-run later or use a token with sufficient allowance.
