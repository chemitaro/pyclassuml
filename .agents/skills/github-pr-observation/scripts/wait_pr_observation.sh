#!/usr/bin/env bash
set -euo pipefail

usage() {
  builtin printf '%s\n' \
    'usage: wait_pr_observation.sh --repo OWNER/REPO --pr NUMBER --head-sha SHA [options]' \
    '' \
    'Options:' \
    '  --timeout-seconds NUMBER' \
    '  --poll-interval-seconds NUMBER' \
    '  --quiet-seconds NUMBER' \
    '  --same-fingerprint-count NUMBER' \
    '  --zero-check-grace-polls NUMBER' \
    '  --trigger-mode post-once|resume' \
    '  --trigger-comment-id NUMBER' \
    '  --trigger-created-at ISO8601' \
    '  --body-mode none|trigger-window-truncated|trigger-window-full|out-only' \
    '  --progress stderr-summary|none' \
    '  --out DIR' \
    '' \
    'The script accepts only the fixed PR observation contract. It does not accept' \
    'caller-provided endpoints, methods, GraphQL queries, headers, bodies, jq' \
    'expressions, or raw gh arguments.' >&2
}

fail_usage() {
  usage
  exit 64
}

repo=""
pr=""
head_sha=""
timeout_seconds="1800"
poll_interval_seconds="30"
quiet_seconds="90"
same_fingerprint_count="2"
zero_check_grace_polls="2"
trigger_comment_id=""
trigger_created_at=""
trigger_mode="post-once"
body_mode="trigger-window-truncated"
progress="stderr-summary"
out_dir=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --repo)
      [ "$#" -ge 2 ] || fail_usage
      repo="$2"
      shift 2
      ;;
    --pr)
      [ "$#" -ge 2 ] || fail_usage
      pr="$2"
      shift 2
      ;;
    --head-sha)
      [ "$#" -ge 2 ] || fail_usage
      head_sha="$2"
      shift 2
      ;;
    --timeout-seconds)
      [ "$#" -ge 2 ] || fail_usage
      timeout_seconds="$2"
      shift 2
      ;;
    --poll-interval-seconds)
      [ "$#" -ge 2 ] || fail_usage
      poll_interval_seconds="$2"
      shift 2
      ;;
    --quiet-seconds)
      [ "$#" -ge 2 ] || fail_usage
      quiet_seconds="$2"
      shift 2
      ;;
    --same-fingerprint-count)
      [ "$#" -ge 2 ] || fail_usage
      same_fingerprint_count="$2"
      shift 2
      ;;
    --zero-check-grace-polls)
      [ "$#" -ge 2 ] || fail_usage
      zero_check_grace_polls="$2"
      shift 2
      ;;
    --trigger-mode)
      [ "$#" -ge 2 ] || fail_usage
      trigger_mode="$2"
      shift 2
      ;;
    --trigger-comment-id)
      [ "$#" -ge 2 ] || fail_usage
      trigger_comment_id="$2"
      shift 2
      ;;
    --trigger-created-at)
      [ "$#" -ge 2 ] || fail_usage
      trigger_created_at="$2"
      shift 2
      ;;
    --body-mode)
      [ "$#" -ge 2 ] || fail_usage
      body_mode="$2"
      shift 2
      ;;
    --progress)
      [ "$#" -ge 2 ] || fail_usage
      progress="$2"
      shift 2
      ;;
    --out)
      [ "$#" -ge 2 ] || fail_usage
      out_dir="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail_usage
      ;;
  esac
done

positive_int() {
  [[ "$1" =~ ^[1-9][0-9]*$ ]]
}

if ! [[ "$repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
  fail_usage
fi
if ! [[ "$pr" =~ ^[1-9][0-9]*$ ]]; then
  fail_usage
fi
if ! [[ "$head_sha" =~ ^[0-9A-Fa-f]{7,64}$ ]]; then
  fail_usage
fi
if ! positive_int "$timeout_seconds"; then
  fail_usage
fi
if ! positive_int "$poll_interval_seconds"; then
  fail_usage
fi
if ! positive_int "$quiet_seconds"; then
  fail_usage
fi
if ! positive_int "$same_fingerprint_count"; then
  fail_usage
fi
if ! positive_int "$zero_check_grace_polls"; then
  fail_usage
fi
if [ -n "$trigger_comment_id" ] && ! [[ "$trigger_comment_id" =~ ^[1-9][0-9]*$ ]]; then
  fail_usage
fi
if [ -n "$trigger_created_at" ] && ! [[ "$trigger_created_at" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(Z|[+-][0-9]{2}:[0-9]{2})?$ ]]; then
  fail_usage
fi
case "$trigger_mode" in
  post-once|resume) ;;
  *) fail_usage ;;
esac
if [ "$trigger_mode" = "post-once" ] && { [ -n "$trigger_comment_id" ] || [ -n "$trigger_created_at" ]; }; then
  fail_usage
fi
if [ "$trigger_mode" = "resume" ] && { [ -z "$trigger_comment_id" ] || [ -z "$trigger_created_at" ]; }; then
  fail_usage
fi
case "$body_mode" in
  none|trigger-window-truncated|trigger-window-full|out-only) ;;
  *) fail_usage ;;
esac
case "$progress" in
  stderr-summary|none) ;;
  *) fail_usage ;;
esac
if [ -n "$out_dir" ] && [[ "$out_dir" == -* ]]; then
  fail_usage
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
snapshot_script="$script_dir/fetch_pr_observation_snapshot.sh"
trigger_script="$script_dir/trigger_codex_review.sh"

OBS_SNAPSHOT_SCRIPT="$snapshot_script" \
OBS_TRIGGER_SCRIPT="$trigger_script" \
OBS_REPO="$repo" \
OBS_PR="$pr" \
OBS_HEAD_SHA="$head_sha" \
OBS_TIMEOUT_SECONDS="$timeout_seconds" \
OBS_POLL_INTERVAL_SECONDS="$poll_interval_seconds" \
OBS_QUIET_SECONDS="$quiet_seconds" \
OBS_SAME_FINGERPRINT_COUNT="$same_fingerprint_count" \
OBS_ZERO_CHECK_GRACE_POLLS="$zero_check_grace_polls" \
OBS_TRIGGER_MODE="$trigger_mode" \
OBS_TRIGGER_COMMENT_ID="$trigger_comment_id" \
OBS_TRIGGER_CREATED_AT="$trigger_created_at" \
OBS_BODY_MODE="$body_mode" \
OBS_PROGRESS="$progress" \
OBS_OUT_DIR="$out_dir" \
python3 "$script_dir/lib/pr_observation_wait.py"
