#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE' >&2
Fetch Codex review feedback from a GitHub Pull Request via REST API.

Usage:
  fetch_codex_pr_review_comments.sh --repo OWNER/REPO --pr <number> [--out <dir>]

Auth:
  Uses GH_TOKEN (preferred) or GITHUB_TOKEN.

Outputs (in --out):
  - issue_comments.json     (PR conversation comments)
  - review_comments.json    (inline review comments)
  - reviews.json            (review bodies)
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

token="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
if [[ -z "$token" ]]; then
  echo "error: GH_TOKEN or GITHUB_TOKEN is not set" >&2
  exit 1
fi

owner="${repo%%/*}"
name="${repo#*/}"
if [[ -z "$owner" || -z "$name" || "$owner" == "$name" ]]; then
  echo "error: invalid --repo (expected OWNER/REPO): $repo" >&2
  exit 2
fi

api_base="https://api.github.com"
per_page="100"

if [[ -z "$out_dir" ]]; then
  out_dir="/tmp/github-pr-${owner}-${name}-${pr_number}"
fi
mkdir -p "$out_dir"

fetch_paginated_array() {
  local url_base="$1"   # without query params
  local out_file="$2"
  local tmp_dir="$3"
  local page=1
  local page_files=()

  mkdir -p "$tmp_dir"

  while true; do
    local page_file="$tmp_dir/page_${page}.json"
    curl -fsSL \
      -H "Accept: application/vnd.github+json" \
      -H "Authorization: Bearer ${token}" \
      "${url_base}?per_page=${per_page}&page=${page}" \
      -o "$page_file"

    local length
    length="$(jq 'length' "$page_file")"
    if [[ "$length" -eq 0 ]]; then
      rm -f "$page_file"
      break
    fi

    page_files+=("$page_file")
    page="$((page + 1))"
  done

  if [[ "${#page_files[@]}" -eq 0 ]]; then
    echo '[]' >"$out_file"
    return 0
  fi

  jq -s 'add' "${page_files[@]}" >"$out_file"
}

tmp_root="$(mktemp -d)"
cleanup() { rm -rf "$tmp_root"; }
trap cleanup EXIT

issue_comments_json="${out_dir}/issue_comments.json"
review_comments_json="${out_dir}/review_comments.json"
reviews_json="${out_dir}/reviews.json"
report_md="${out_dir}/codex_report.md"

fetch_paginated_array \
  "${api_base}/repos/${owner}/${name}/issues/${pr_number}/comments" \
  "$issue_comments_json" \
  "${tmp_root}/issue_comments"

fetch_paginated_array \
  "${api_base}/repos/${owner}/${name}/pulls/${pr_number}/comments" \
  "$review_comments_json" \
  "${tmp_root}/review_comments"

fetch_paginated_array \
  "${api_base}/repos/${owner}/${name}/pulls/${pr_number}/reviews" \
  "$reviews_json" \
  "${tmp_root}/reviews"

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
echo "ok: wrote $report_md"
