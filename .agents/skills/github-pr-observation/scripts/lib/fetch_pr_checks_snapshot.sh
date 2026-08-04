#!/usr/bin/env bash
set -euo pipefail

usage() {
  builtin printf '%s\n' \
    'usage: fetch_pr_checks_snapshot.sh --repo OWNER/REPO --pr NUMBER --head-sha SHA' \
    '' \
    'Historical compatibility entrypoint for an Actions-only CI snapshot for the' \
    'expected PR head SHA. The name is retained for compatibility and does not imply' \
    'GitHub Checks API usage. The script observes GitHub Actions workflow runs/jobs' \
    'only; it does not use GitHub Checks API, commit statuses, PR status rollup,' \
    'gh pr checks, or equivalent check-rollup surfaces. External/non-Actions checks' \
    'are intentionally unobserved and may require GitHub UI or external CI' \
    'confirmation when branch protection depends on them.' \
    '' \
    'The script accepts only this fixed read-only contract and does not accept' \
    'caller-provided gh api arguments.' >&2
}

fail_usage() {
  usage
  exit 64
}

repo=""
pr=""
head_sha=""

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
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail_usage
      ;;
  esac
done

if ! [[ "$repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
  fail_usage
fi
if ! [[ "$pr" =~ ^[1-9][0-9]*$ ]]; then
  fail_usage
fi
if ! [[ "$head_sha" =~ ^[0-9A-Fa-f]{7,64}$ ]]; then
  fail_usage
fi

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
OBS_REPO="$repo" \
OBS_PR="$pr" \
OBS_HEAD_SHA="$head_sha" \
python3 "$script_dir/pr_observation_checks.py"
