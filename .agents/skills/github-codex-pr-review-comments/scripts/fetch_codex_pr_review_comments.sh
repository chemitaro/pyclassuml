#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE' >&2
Fetch Codex review feedback from a GitHub Pull Request via REST API.

Usage:
  fetch_codex_pr_review_comments.sh --repo OWNER/REPO --pr <number> [--out <dir>]

Auth:
  Uses the authenticated GitHub CLI (`gh api`).

Outputs (in --out):
  - issue_comments.json     (PR conversation comments)
  - review_comments.json    (inline review comments)
  - reviews.json            (review bodies)
  - review_data.json        (normalized wrapper output)
  - codex_report.md         (Codex-only summary)
USAGE
}

repo=""
pr_number=""
out_dir=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      repo="${2:-}"
      shift 2
      ;;
    --pr)
      pr_number="${2:-}"
      shift 2
      ;;
    --out)
      out_dir="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown arg: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$repo" || -z "$pr_number" ]]; then
  echo "error: --repo and --pr are required" >&2
  usage
  exit 2
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "error: gh is required" >&2
  exit 1
fi

owner="${repo%%/*}"
name="${repo#*/}"
if [[ "$repo" != */* || "$repo" == */*/* || -z "$owner" || -z "$name" ]]; then
  echo "error: invalid --repo (expected OWNER/REPO): $repo" >&2
  exit 2
fi

if [[ ! "$owner" =~ ^[A-Za-z0-9][A-Za-z0-9-]{0,38}$ ]]; then
  echo "error: invalid --repo owner: $owner" >&2
  exit 2
fi

if [[ ! "$name" =~ ^[A-Za-z0-9._-]+$ || "$name" == .* || "$name" == *..* ]]; then
  echo "error: invalid --repo name: $name" >&2
  exit 2
fi

if [[ ! "$pr_number" =~ ^[1-9][0-9]*$ ]]; then
  echo "error: invalid --pr (expected positive integer): $pr_number" >&2
  exit 2
fi

if [[ -z "$out_dir" ]]; then
  out_dir="/tmp/github-pr-${owner}-${name}-${pr_number}"
fi
mkdir -p "$out_dir"

fetch_rest_array() {
  local endpoint="$1"
  local out_file="$2"

  # This wrapper intentionally does not accept method, endpoint, body, jq, or
  # GraphQL input from callers. `gh api` is constrained to fixed REST GET calls.
  gh api \
    --method GET \
    --paginate \
    --slurp \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "$endpoint" \
    --jq 'add' \
    >"$out_file"
}

issue_comments_json="${out_dir}/issue_comments.json"
review_comments_json="${out_dir}/review_comments.json"
reviews_json="${out_dir}/reviews.json"
review_data_json="${out_dir}/review_data.json"
report_md="${out_dir}/codex_report.md"

issue_comments_endpoint="repos/${owner}/${name}/issues/${pr_number}/comments?per_page=100"
review_comments_endpoint="repos/${owner}/${name}/pulls/${pr_number}/comments?per_page=100"
reviews_endpoint="repos/${owner}/${name}/pulls/${pr_number}/reviews?per_page=100"

fetch_rest_array "$issue_comments_endpoint" "$issue_comments_json"
fetch_rest_array "$review_comments_endpoint" "$review_comments_json"
fetch_rest_array "$reviews_endpoint" "$reviews_json"

codex_filter_jq='
def is_codex:
  (.user.login // "" | test("codex"; "i"));

def md_comment($src):
  "### " + $src + " #" + ((.id|tostring)) + "\n"
  + "- user: " + (.user.login // "") + "\n"
  + "- created_at: " + (.created_at // .submitted_at // "") + "\n"
  + (if (.path // "") != "" then "- path: " + .path + "\n" else "" end)
  + (if (.line // null) != null then "- line: " + (.line|tostring) + "\n" else "" end)
  + (if (.in_reply_to_id // null) != null then "- in_reply_to_id: " + (.in_reply_to_id|tostring) + "\n" else "" end)
  + "\n"
  + (.body // "") + "\n";

{
  inline:  ($review_comments | map(select(is_codex))),
  convo:   ($issue_comments | map(select(is_codex))),
  reviews: ($reviews | map(select(is_codex)))
}
| "# Codex review report\n\n"
  + "- repo: " + $repo + "\n"
  + "- pr: #" + ($pr|tostring) + "\n\n"
  + "## Summary\n\n"
  + "- inline review comments: " + (.inline|length|tostring) + "\n"
  + "- PR conversation comments: " + (.convo|length|tostring) + "\n"
  + "- review bodies: " + (.reviews|length|tostring) + "\n\n"
  + "## Inline review comments (diff)\n\n"
  + (if (.inline|length) == 0 then "_(none)_\n"
     else (.inline | map(md_comment("inline")) | join("\n")) end)
  + "\n\n## PR conversation comments\n\n"
  + (if (.convo|length) == 0 then "_(none)_\n"
     else (.convo | map(md_comment("convo")) | join("\n")) end)
  + "\n\n## Review bodies\n\n"
  + (if (.reviews|length) == 0 then "_(none)_\n"
     else (.reviews | map(md_comment("review")) | join("\n")) end)
'

jq -n \
  -r \
  --arg repo "$repo" \
  --argjson pr "$pr_number" \
  --arg issue_comments_endpoint "$issue_comments_endpoint" \
  --arg review_comments_endpoint "$review_comments_endpoint" \
  --arg reviews_endpoint "$reviews_endpoint" \
  --slurpfile issue_comments "$issue_comments_json" \
  --slurpfile review_comments "$review_comments_json" \
  --slurpfile reviews "$reviews_json" \
  '
  # slurpfile yields [<array>] so unwrap.
  ($issue_comments[0] // []) as $issue_comments
  | ($review_comments[0] // []) as $review_comments
  | ($reviews[0] // []) as $reviews
  | {
      meta: {
        repo: $repo,
        pr: $pr,
        endpoints: {
          issue_comments: $issue_comments_endpoint,
          review_comments: $review_comments_endpoint,
          reviews: $reviews_endpoint
        },
        transport: "gh api --method GET",
        generated_at: (now | todateiso8601)
      },
      issue_comments: $issue_comments,
      review_comments: $review_comments,
      reviews: $reviews,
      codex: {
        issue_comments: ($issue_comments | map(select((.user.login // "") | test("codex"; "i")))),
        review_comments: ($review_comments | map(select((.user.login // "") | test("codex"; "i")))),
        reviews: ($reviews | map(select((.user.login // "") | test("codex"; "i"))))
      }
    }
  ' >"$review_data_json"

jq -n \
  -r \
  --arg repo "$repo" \
  --argjson pr "$pr_number" \
  --slurpfile issue_comments "$issue_comments_json" \
  --slurpfile review_comments "$review_comments_json" \
  --slurpfile reviews "$reviews_json" \
  '
  # slurpfile yields [<array>] so unwrap.
  ($issue_comments[0] // []) as $issue_comments
  | ($review_comments[0] // []) as $review_comments
  | ($reviews[0] // []) as $reviews
  | '"$codex_filter_jq"'
  ' >"$report_md"

echo "ok: wrote $issue_comments_json"
echo "ok: wrote $review_comments_json"
echo "ok: wrote $reviews_json"
echo "ok: wrote $review_data_json"
echo "ok: wrote $report_md"
