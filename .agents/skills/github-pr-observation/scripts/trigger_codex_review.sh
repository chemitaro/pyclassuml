#!/usr/bin/env bash
set -euo pipefail

usage() {
  builtin printf '%s\n' \
    'usage: trigger_codex_review.sh --repo OWNER/REPO --pr NUMBER --head-sha SHA' \
    '' \
    'Posts at most one deterministic PR issue comment whose body starts with' \
    '"@codex review" after verifying that the PR head still matches --head-sha.' \
    'When script-local review instructions are valid, the comment includes' \
    'instruction metadata and text. Missing instructions fall back to a plain' \
    'deterministic review request. Invalid instructions are reported as human gate' \
    'without posting a comment. The script does not accept' \
    'caller-provided bodies, endpoints, methods, GraphQL queries, headers, jq' \
    'expressions, or raw gh arguments.' >&2
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

owner="${repo%%/*}"
name="${repo#*/}"
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

builtin printf -v python_source '%s\n' \
  'import json' \
  'import hashlib' \
  'import os' \
  'import subprocess' \
  'from datetime import datetime, timezone' \
  'from pathlib import Path' \
  '' \
  'repo = os.environ["TRIGGER_REPO"]' \
  'owner = os.environ["TRIGGER_OWNER"]' \
  'name = os.environ["TRIGGER_NAME"]' \
  'pr = os.environ["TRIGGER_PR"]' \
  'expected_head_sha = os.environ["TRIGGER_HEAD_SHA"]' \
  'endpoint = f"repos/{owner}/{name}/issues/{pr}/comments"' \
  'fixed_body = "@codex review"' \
  '# Current iss-00244 contract: use the shipped script-local instruction asset,' \
  '# not a GitHub base/head .github/codex/review-policy.md file.' \
  'instruction_path = Path(os.environ["TRIGGER_SCRIPT_DIR"]) / "codex-review-instructions.md"' \
  'instruction_display_path = ".agents/skills/github-pr-observation/scripts/codex-review-instructions.md"' \
  'instruction_max_bytes = 32768' \
  '' \
  '' \
  'def now_iso():' \
  '    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")' \
  '' \
  '' \
  'def run_gh(args):' \
  '    completed = subprocess.run(' \
  '        ["gh", *args],' \
  '        capture_output=True,' \
  '        text=True,' \
  '        check=False,' \
  '    )' \
  '    return completed.returncode, completed.stdout, completed.stderr' \
  '' \
  '' \
  'def parse_gh_paginated_stdout(text):' \
  '    decoder = json.JSONDecoder()' \
  '    index = 0' \
  '    payloads = []' \
  '    text = text or ""' \
  '    while index < len(text):' \
  '        while index < len(text) and text[index].isspace():' \
  '            index += 1' \
  '        if index >= len(text):' \
  '            break' \
  '        payload, index = decoder.raw_decode(text, index)' \
  '        payloads.append(payload)' \
  '    if not payloads:' \
  '        return []' \
  '    if len(payloads) == 1:' \
  '        return payloads[0]' \
  '    if all(isinstance(payload, list) for payload in payloads):' \
  '        merged_list = []' \
  '        for payload in payloads:' \
  '            merged_list.extend(payload)' \
  '        return merged_list' \
  '    if all(isinstance(payload, dict) for payload in payloads):' \
  '        merged = {}' \
  '        for payload in payloads:' \
  '            for key, value in payload.items():' \
  '                if isinstance(value, list):' \
  '                    merged.setdefault(key, [])' \
  '                    if isinstance(merged[key], list):' \
  '                        merged[key].extend(value)' \
  '                    else:' \
  '                        merged[key] = value' \
  '                elif isinstance(value, int) and key == "total_count":' \
  '                    merged[key] = int(merged.get(key, 0) or 0) + value' \
  '                else:' \
  '                    merged[key] = value' \
  '        return merged' \
  '    return payloads[-1]' \
  '' \
  '' \
  'def load_json(text, fallback):' \
  '    try:' \
  '        return parse_gh_paginated_stdout(text)' \
  '    except Exception:' \
  '        return fallback' \
  '' \
  '' \
  'def emit(payload):' \
  '    print(json.dumps(payload, separators=(",", ":"), sort_keys=True))' \
  '' \
  '' \
  'def limitation(code, message, **extra):' \
  '    payload = {"code": code, "message": message, "source": "trigger_codex_review.sh"}' \
  '    sanitized_extra = {}' \
  '    for key, value in extra.items():' \
  '        if key.endswith("gh_stderr") or key == "gh_stderr":' \
  '            sanitized_extra[f"{key}_sha256"] = hashlib.sha256(str(value or "").encode()).hexdigest()' \
  '        else:' \
  '            sanitized_extra[key] = value' \
  '    payload.update(sanitized_extra)' \
  '    return payload' \
  '' \
  '' \
  'def token_source():' \
  '    if os.environ.get("GH_TOKEN"):' \
  '        return "GH_TOKEN"' \
  '    if os.environ.get("GITHUB_TOKEN"):' \
  '        return "GITHUB_TOKEN"' \
  '    return "gh_saved_auth"' \
  '' \
  '' \
  'def is_permission_denied(stderr):' \
  '    lowered = (stderr or "").lower()' \
  '    return (' \
  '        "resource not accessible by personal access token" in lowered' \
  '        or "resource not accessible by integration" in lowered' \
  '        or "permission denied" in lowered' \
  '    )' \
  '' \
  '' \
  'def trigger_permission_limitation(stderr, exit_code):' \
  '    return limitation(' \
  '        "github_token_permission_denied",' \
  '        "GitHub token lacks permission to post the fixed Codex review trigger comment",' \
  '        capability="trigger_comment_write",' \
  '        api=endpoint,' \
  '        status="permission_denied",' \
  '        token_source=token_source(),' \
  '        severity="blocking",' \
  '        recommended_next_action="fix_github_token_permissions",' \
  '        secret_redacted=True,' \
  '        stderr_sha256=hashlib.sha256((stderr or "").encode()).hexdigest(),' \
  '        exit_code=exit_code,' \
  '    )' \
  '' \
  '' \
  'def head_matches(actual, expected):' \
  '    actual_lc = (actual or "").lower()' \
  '    expected_lc = (expected or "").lower()' \
  '    return bool(actual_lc and expected_lc and actual_lc.startswith(expected_lc))' \
  '' \
  '' \
  'def base_payload():' \
  '    return {' \
  '        "script": "trigger_codex_review.sh",' \
  '        "repo": repo,' \
  '        "pr": int(pr),' \
  '        "expected_head_sha": expected_head_sha,' \
  '        "current_head_sha": None,' \
  '        "final_head_sha": None,' \
  '        "head_matches_expected": False,' \
  '        "success": False,' \
  '        "overall_status": "unknown",' \
  '        "normalized_status": "unknown",' \
  '        "recommended_next_action": "unknown",' \
  '        "review_instruction": {' \
  '            "source": "script_local",' \
  '            "path": instruction_display_path,' \
  '            "hash": None,' \
  '            "bytes": 0,' \
  '            "status": "not_requested",' \
  '        },' \
  '        "trigger": {' \
  '            "action": "none",' \
  '            "body": fixed_body,' \
  '            "body_matches_expected": None,' \
  '            "comment_id": None,' \
  '            "created_at": None,' \
  '            "endpoint": endpoint,' \
  '            "mode": "post-once",' \
  '            "url": None,' \
  '        },' \
  '        "recovery": {' \
  '            "attempted": False,' \
  '            "accepted": False,' \
  '            "new_exact_comment_count": 0,' \
  '        },' \
  '        "limitations": [],' \
  '        "generated_at": now_iso(),' \
  '    }' \
  '' \
  '' \
  'payload = base_payload()' \
  '' \
  '' \
  'def block_review_instruction_gate():' \
  '    payload["success"] = False' \
  '    payload["overall_status"] = "human_gate"' \
  '    payload["normalized_status"] = "human_gate"' \
  '    payload["recommended_next_action"] = "human_gate"' \
  '    payload["trigger"]["action"] = "blocked"' \
  '    emit(payload)' \
  '    raise SystemExit(0)' \
  '' \
  'metadata_exit, metadata_stdout, metadata_stderr = run_gh(' \
  '    ["pr", "view", pr, "--repo", repo, "--json", "headRefOid,url,state,isDraft,number"]' \
  ')' \
  'metadata = load_json(metadata_stdout, {}) if metadata_exit == 0 else {}' \
  'current_head_sha = metadata.get("headRefOid") or ""' \
  'payload["current_head_sha"] = current_head_sha or None' \
  'payload["head_matches_expected"] = head_matches(current_head_sha, expected_head_sha)' \
  '' \
  'if metadata_exit != 0 or not current_head_sha:' \
  '    payload["overall_status"] = "metadata_failed"' \
  '    payload["trigger"]["action"] = "failed"' \
  '    payload["limitations"].append(' \
  '        limitation(' \
  '            "pr_metadata_collection_failed",' \
  '            "could not read PR head before posting trigger comment",' \
  '            gh_exit=metadata_exit,' \
  '            gh_stderr=metadata_stderr.strip(),' \
  '        )' \
  '    )' \
  '    emit(payload)' \
  '    raise SystemExit(0)' \
  '' \
  'if not payload["head_matches_expected"]:' \
  '    payload["overall_status"] = "stale_head"' \
  '    payload["trigger"]["action"] = "stale"' \
  '    payload["limitations"].append(' \
  '        limitation(' \
  '            "pre_trigger_head_mismatch",' \
  '            "PR head did not match expected --head-sha before trigger comment POST",' \
  '            current_head_sha=current_head_sha,' \
  '            expected_head_sha=expected_head_sha,' \
  '        )' \
  '    )' \
  '    emit(payload)' \
  '    raise SystemExit(0)' \
  '' \
  'if metadata.get("isDraft") is True:' \
  '    payload["overall_status"] = "draft_pr"' \
  '    payload["trigger"]["action"] = "skipped"' \
  '    payload["limitations"].append(' \
  '        limitation(' \
  '            "draft_pr_trigger_skipped",' \
  '            "draft PR cannot receive the deterministic Codex review trigger",' \
  '        )' \
  '    )' \
  '    emit(payload)' \
  '    raise SystemExit(0)' \
  '' \
  'pr_state = str(metadata.get("state") or "").upper()' \
  'if pr_state and pr_state != "OPEN":' \
  '    payload["overall_status"] = "non_open_pr"' \
  '    payload["trigger"]["action"] = "skipped"' \
  '    payload["limitations"].append(' \
  '        limitation(' \
  '            "non_open_pr_trigger_skipped",' \
  '            "non-open PR cannot receive the deterministic Codex review trigger",' \
  '            state=metadata.get("state"),' \
  '        )' \
  '    )' \
  '    emit(payload)' \
  '    raise SystemExit(0)' \
  '' \
  'try:' \
  '    instruction_bytes = instruction_path.read_bytes()' \
  'except FileNotFoundError:' \
  '    instruction_bytes = None' \
  '    payload["review_instruction"].update({"status": "missing_plain_fallback"})' \
  '    fixed_body = "\n".join(' \
  '        (' \
  '            "@codex review",' \
  '            "",' \
  '            "Script-local review instruction:",' \
  '            f"- source: {instruction_display_path}",' \
  '            "- instruction_status: missing_plain_fallback",' \
  '            f"- reviewed_head_sha: {expected_head_sha}",' \
  '        )' \
  '    )' \
  '    payload["trigger"]["body"] = fixed_body' \
  'except OSError as exc:' \
  '    instruction_bytes = None' \
  '    payload["review_instruction"].update({"status": "unreadable"})' \
  '    payload["limitations"].append(' \
  '        limitation(' \
  '            "review_instruction_unreadable",' \
  '            "script-local review instruction could not be read",' \
  '            path=instruction_display_path,' \
  '            error_type=type(exc).__name__,' \
  '            severity="blocking",' \
  '        )' \
  '    )' \
  '' \
  'if instruction_bytes is not None:' \
  '    payload["review_instruction"]["bytes"] = len(instruction_bytes)' \
  '    if len(instruction_bytes) > instruction_max_bytes:' \
  '        payload["review_instruction"].update({"status": "too_large"})' \
  '        payload["limitations"].append(' \
  '            limitation(' \
  '                "review_instruction_too_large",' \
  '                "script-local review instruction exceeds the maximum accepted size",' \
  '                path=instruction_display_path,' \
  '                max_bytes=instruction_max_bytes,' \
  '                severity="blocking",' \
  '            )' \
  '        )' \
  '    else:' \
  '        try:' \
  '            instruction_text = instruction_bytes.decode("utf-8")' \
  '        except UnicodeDecodeError:' \
  '            instruction_text = ""' \
  '        if instruction_text.strip():' \
  '            instruction_hash = hashlib.sha256(instruction_bytes).hexdigest()' \
  '            fixed_body = "\n".join(' \
  '                (' \
  '                    "@codex review",' \
  '                    "",' \
  '                    "Script-local review instruction:",' \
  '                    f"- source: {instruction_display_path}",' \
  '                    f"- instruction_sha256: {instruction_hash}",' \
  '                    "- instruction_status: loaded",' \
  '                    f"- reviewed_head_sha: {expected_head_sha}",' \
  '                    "",' \
  '                    instruction_text.rstrip(),' \
  '                )' \
  '            )' \
  '            payload["review_instruction"].update(' \
  '                {' \
  '                    "hash": instruction_hash,' \
  '                    "status": "loaded",' \
  '                }' \
  '            )' \
  '            payload["trigger"]["body"] = fixed_body' \
  '        else:' \
  '            payload["review_instruction"].update({"status": "invalid"})' \
  '            payload["limitations"].append(' \
  '                limitation(' \
  '                    "review_instruction_invalid",' \
  '                    "script-local review instruction must be non-empty UTF-8 text",' \
  '                    path=instruction_display_path,' \
  '                    severity="blocking",' \
  '                )' \
  '            )' \
  '' \
  'if payload["review_instruction"]["status"] in {"invalid", "too_large", "unreadable"}:' \
  '    block_review_instruction_gate()' \
  '' \
  'before_exit, before_stdout, before_stderr = run_gh(["api", endpoint, "--paginate"])' \
  'before_comments_raw = load_json(before_stdout, None) if before_exit == 0 else None' \
  'before_comments_trusted = isinstance(before_comments_raw, list)' \
  'before_comments = before_comments_raw if before_comments_trusted else []' \
  'if not before_comments_trusted:' \
  '    payload["limitations"].append(' \
  '        limitation(' \
  '            "before_comments_snapshot_untrusted",' \
  '            "could not trust before-comment snapshot; POST failure recovery will not be accepted",' \
  '            gh_exit=before_exit,' \
  '            gh_stderr=before_stderr.strip(),' \
  '        )' \
  '    )' \
  'before_ids = {comment.get("id") for comment in before_comments if isinstance(comment, dict)}' \
  '' \
  'post_exit, post_stdout, post_stderr = run_gh(' \
  '    ["api", endpoint, "--method", "POST", "--raw-field", f"body={fixed_body}"]' \
  ')' \
  'post_payload = load_json(post_stdout, {}) if post_exit == 0 else {}' \
  '' \
  'if post_exit == 0 and isinstance(post_payload, dict):' \
  '    payload["trigger"].update(' \
  '        {' \
  '            "action": "posted",' \
  '            "body_matches_expected": post_payload.get("body") == fixed_body,' \
  '            "comment_id": post_payload.get("id"),' \
  '            "created_at": post_payload.get("created_at"),' \
  '            "url": post_payload.get("html_url") or post_payload.get("url"),' \
  '        }' \
  '    )' \
  '    if payload["trigger"]["body_matches_expected"] and payload["trigger"]["comment_id"] and payload["trigger"]["created_at"]:' \
  '        payload["success"] = True' \
  '        payload["overall_status"] = "trigger_posted"' \
  '    else:' \
  '        payload["overall_status"] = "trigger_response_invalid"' \
  '        payload["limitations"].append(' \
  '            limitation(' \
  '                "trigger_response_invalid",' \
  '                "POST succeeded but response did not contain exact trigger metadata",' \
  '            )' \
  '        )' \
  'else:' \
  '    payload["trigger"]["action"] = "failed"' \
  '    payload["overall_status"] = "trigger_post_failed"' \
  '    if is_permission_denied(post_stderr):' \
  '        payload["limitations"].append(trigger_permission_limitation(post_stderr, post_exit))' \
  '    payload["limitations"].append(' \
  '        limitation(' \
  '            "trigger_post_failed",' \
  '            "fixed trigger comment POST failed; blind retry is not allowed",' \
  '            gh_exit=post_exit,' \
  '            gh_stderr=post_stderr.strip(),' \
  '        )' \
  '    )' \
  '    payload["recovery"]["attempted"] = True' \
  '    after_exit, after_stdout, after_stderr = run_gh(["api", endpoint, "--paginate"])' \
  '    after_comments_raw = load_json(after_stdout, None) if after_exit == 0 else None' \
  '    after_comments_trusted = isinstance(after_comments_raw, list)' \
  '    after_comments = after_comments_raw if after_comments_trusted else []' \
  '    if not before_comments_trusted:' \
  '        payload["limitations"].append(' \
  '            limitation(' \
  '                "trigger_recovery_unavailable",' \
  '                "POST failure recovery requires a trusted before-comment snapshot",' \
  '            )' \
  '        )' \
  '    if not after_comments_trusted:' \
  '        payload["limitations"].append(' \
  '            limitation(' \
  '                "after_comments_snapshot_untrusted",' \
  '                "POST failure recovery requires a trusted after-comment snapshot",' \
  '                gh_exit=after_exit,' \
  '                gh_stderr=after_stderr.strip(),' \
  '            )' \
  '        )' \
  '    new_exact_comments = [' \
  '        comment for comment in after_comments' \
  '        if isinstance(comment, dict)' \
  '        and comment.get("id") not in before_ids' \
  '        and comment.get("body") == fixed_body' \
  '    ]' \
  '    payload["recovery"]["new_exact_comment_count"] = len(new_exact_comments)' \
  '    if before_comments_trusted and after_comments_trusted and len(new_exact_comments) == 1:' \
  '        recovered = new_exact_comments[0]' \
  '        payload["recovery"]["accepted"] = True' \
  '        payload["trigger"].update(' \
  '            {' \
  '                "action": "recovered",' \
  '                "body_matches_expected": True,' \
  '                "comment_id": recovered.get("id"),' \
  '                "created_at": recovered.get("created_at"),' \
  '                "url": recovered.get("html_url") or recovered.get("url"),' \
  '            }' \
  '        )' \
  '        payload["success"] = bool(payload["trigger"]["comment_id"] and payload["trigger"]["created_at"])' \
  '        payload["overall_status"] = "trigger_recovered" if payload["success"] else "trigger_recovery_invalid"' \
  '    else:' \
  '        payload["limitations"].append(' \
  '            limitation(' \
  '                "trigger_recovery_ambiguous",' \
  '                "POST failure recovery requires exactly one new exact @codex review comment",' \
  '                after_gh_exit=after_exit,' \
  '                after_gh_stderr=after_stderr.strip(),' \
  '                new_exact_comment_count=len(new_exact_comments),' \
  '            )' \
  '        )' \
  '' \
  'final_exit, final_stdout, final_stderr = run_gh(' \
  '    ["pr", "view", pr, "--repo", repo, "--json", "headRefOid,url,state,isDraft,number"]' \
  ')' \
  'final_metadata = load_json(final_stdout, {}) if final_exit == 0 else {}' \
  'final_head_sha = final_metadata.get("headRefOid") or ""' \
  'payload["final_head_sha"] = final_head_sha or None' \
  '' \
  'if final_exit != 0 or not final_head_sha:' \
  '    payload["limitations"].append(' \
  '        limitation(' \
  '            "post_trigger_metadata_failed",' \
  '            "could not read PR head after trigger comment POST",' \
  '            gh_exit=final_exit,' \
  '            gh_stderr=final_stderr.strip(),' \
  '            severity="warning" if payload["success"] else "blocking",' \
  '        )' \
  '    )' \
  '    if not payload["success"]:' \
  '        payload["overall_status"] = "metadata_failed_after_trigger"' \
  'elif not head_matches(final_head_sha, expected_head_sha):' \
  '    payload["success"] = False' \
  '    payload["overall_status"] = "stale_head"' \
  '    payload["limitations"].append(' \
  '        limitation(' \
  '            "post_trigger_head_mismatch",' \
  '            "PR head changed after trigger comment POST",' \
  '            current_head_sha=final_head_sha,' \
  '            expected_head_sha=expected_head_sha,' \
  '        )' \
  '    )' \
  '' \
  'emit(payload)'

TRIGGER_REPO="$repo" \
TRIGGER_OWNER="$owner" \
TRIGGER_NAME="$name" \
TRIGGER_PR="$pr" \
TRIGGER_HEAD_SHA="$head_sha" \
TRIGGER_SCRIPT_DIR="$script_dir" \
python3 -c "$python_source"
