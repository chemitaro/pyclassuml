import contextlib
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
from typing import NoReturn

NEXT_SNAPSHOT_BUDGET_FLOOR_SECONDS = 0.25
NEXT_SNAPSHOT_BUDGET_SLACK_SECONDS = 0.25
USAGE_LINE = "usage: wait_pr_observation.sh --repo OWNER/REPO --pr NUMBER --head-sha SHA [options]"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fail_usage() -> NoReturn:
    print(USAGE_LINE, file=sys.stderr)
    raise SystemExit(64)


def validate_environment() -> None:
    required_names = (
        "OBS_SNAPSHOT_SCRIPT",
        "OBS_TRIGGER_SCRIPT",
        "OBS_REPO",
        "OBS_PR",
        "OBS_HEAD_SHA",
        "OBS_TIMEOUT_SECONDS",
        "OBS_POLL_INTERVAL_SECONDS",
        "OBS_QUIET_SECONDS",
        "OBS_SAME_FINGERPRINT_COUNT",
        "OBS_ZERO_CHECK_GRACE_POLLS",
        "OBS_TRIGGER_MODE",
        "OBS_TRIGGER_COMMENT_ID",
        "OBS_TRIGGER_CREATED_AT",
        "OBS_BODY_MODE",
        "OBS_PROGRESS",
        "OBS_OUT_DIR",
    )
    if any(name not in os.environ for name in required_names):
        fail_usage()

    values = {name: os.environ[name] for name in required_names}
    if not values["OBS_SNAPSHOT_SCRIPT"] or not values["OBS_TRIGGER_SCRIPT"]:
        fail_usage()
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", values["OBS_REPO"]) is None:
        fail_usage()
    if re.fullmatch(r"[1-9][0-9]*", values["OBS_PR"]) is None:
        fail_usage()
    if re.fullmatch(r"[0-9A-Fa-f]{7,64}", values["OBS_HEAD_SHA"]) is None:
        fail_usage()

    positive_integer_names = (
        "OBS_TIMEOUT_SECONDS",
        "OBS_POLL_INTERVAL_SECONDS",
        "OBS_QUIET_SECONDS",
        "OBS_SAME_FINGERPRINT_COUNT",
        "OBS_ZERO_CHECK_GRACE_POLLS",
    )
    if any(re.fullmatch(r"[1-9][0-9]*", values[name]) is None for name in positive_integer_names):
        fail_usage()

    trigger_mode = values["OBS_TRIGGER_MODE"]
    trigger_comment_id = values["OBS_TRIGGER_COMMENT_ID"]
    trigger_created_at = values["OBS_TRIGGER_CREATED_AT"]
    if trigger_mode not in {"post-once", "resume"}:
        fail_usage()
    if trigger_comment_id and re.fullmatch(r"[1-9][0-9]*", trigger_comment_id) is None:
        fail_usage()
    if trigger_created_at and (
        re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(Z|[+-][0-9]{2}:[0-9]{2})?",
            trigger_created_at,
        )
        is None
    ):
        fail_usage()
    if trigger_mode == "post-once" and (trigger_comment_id or trigger_created_at):
        fail_usage()
    if trigger_mode == "resume" and (not trigger_comment_id or not trigger_created_at):
        fail_usage()

    if values["OBS_BODY_MODE"] not in {
        "none",
        "trigger-window-truncated",
        "trigger-window-full",
        "out-only",
    }:
        fail_usage()
    if values["OBS_PROGRESS"] not in {"stderr-summary", "none"}:
        fail_usage()
    if values["OBS_OUT_DIR"].startswith("-"):
        fail_usage()


def parse_utc_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def age_seconds_from_timestamp(value: object, *, now: datetime | None = None) -> int:
    parsed = parse_utc_timestamp(value)
    if parsed is None:
        return 0
    now = now or datetime.now(timezone.utc)
    return int(max(0, (now - parsed).total_seconds()))


def utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def numeric_age_seconds(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(max(0, value))
    if isinstance(value, str):
        try:
            return int(max(0, float(value)))
        except ValueError:
            return None
    return None


def sha256_json(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def limitation_codes(payload: dict) -> list[str]:
    return [
        str(item.get("code")) for item in payload.get("limitations", []) if isinstance(item, dict) and item.get("code")
    ]


def has_blocking_limitation(payload: dict, ignored_codes: set[str] | None = None) -> bool:
    ignored_codes = ignored_codes or set()
    return any(
        isinstance(item, dict) and item.get("severity") == "blocking" and item.get("code") not in ignored_codes
        for item in payload.get("limitations", [])
    )


def ci_source_policy(payload: dict) -> str | None:
    ci = payload.get("ci") if isinstance(payload.get("ci"), dict) else {}
    source_policy = payload.get("source_policy") or ci.get("source_policy")
    return source_policy if isinstance(source_policy, str) else None


def has_zero_actions_limitation(payload: dict) -> bool:
    limitations = payload.get("limitations", [])
    has_zero_actions = any(
        isinstance(item, dict) and item.get("code") == "zero_actions_runs_non_success" for item in limitations
    )
    if has_zero_actions:
        return True
    if ci_source_policy(payload) == "github_actions_only":
        return False
    return any(isinstance(item, dict) and item.get("code") == "zero_checks_s03_non_success" for item in limitations)


def has_permission_limitation(payload: dict) -> bool:
    return any(
        isinstance(item, dict)
        and item.get("code") == "github_token_permission_denied"
        and item.get("severity") == "blocking"
        for item in payload.get("limitations", [])
    )


def has_permission_signal(payload: dict) -> bool:
    return any(
        isinstance(item, dict) and item.get("code") == "github_token_permission_denied"
        for item in payload.get("limitations", [])
    )


def has_waitable_required_actions_context_limitation(payload: dict) -> bool:
    return any(
        isinstance(item, dict)
        and item.get("code") == "required_actions_context_pending"
        and item.get("recommended_next_action") == "wait"
        for item in payload.get("limitations", [])
    )


def sanitized_review_signals(payload: dict) -> list:
    review = payload.get("review")
    if not isinstance(review, dict):
        return []
    safe_keys = (
        "kind",
        "id",
        "review_id",
        "author",
        "codex_authored",
        "created_at",
        "submitted_at",
        "updated_at",
        "activity_at",
        "state",
        "commit_id",
        "original_commit_id",
        "stale",
        "trigger_command",
        "path",
        "line",
        "thread_id",
        "thread_state",
        "current_status_signal",
        "body_sha256",
        "body_truncated",
        "body_original_length",
        "omitted_reason",
    )
    signals = review.get("signals")
    if not isinstance(signals, list):
        return []
    return [{key: item.get(key) for key in safe_keys} for item in signals if isinstance(item, dict)]


def review_progress_signal_is_current(item: dict) -> bool:
    if item.get("current_status_signal") is not None:
        return item.get("current_status_signal") is True
    if item.get("stale") is True:
        return False
    return item.get("omitted_reason") not in {
        "outside_trigger_window",
        "trigger_unknown",
        "timestamp-unavailable",
    }


def review_semantic_signal_items(payload: dict) -> list:
    signal_kinds = {"pull_review", "pull_review_comment", "issue_comment"}
    return [
        item
        for item in sanitized_review_signals(payload)
        if item.get("trigger_command") is not True
        and review_progress_signal_is_current(item)
        and item.get("kind") in signal_kinds
    ]


def review_progress_signal_items(payload: dict) -> list:
    progress_kinds = {"pull_review", "pull_review_comment", "issue_comment"}
    omitted_progress_reasons = {None, "body_mode_none", "body_mode_out_only", "item_count_cap", "total_body_char_cap"}
    return [
        item
        for item in sanitized_review_signals(payload)
        if item.get("trigger_command") is not True
        and review_progress_signal_is_current(item)
        and item.get("omitted_reason") in omitted_progress_reasons
        and item.get("codex_authored") is True
        and item.get("kind") in progress_kinds
    ]


def int_count(source: dict, key: str) -> int:
    value = source.get(key)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(value))
    return 0


def ci_progress_counts(payload: dict) -> dict:
    ci = payload.get("ci") if isinstance(payload.get("ci"), dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    actions = ci.get("actions") if isinstance(ci.get("actions"), dict) else {}
    workflow_runs = actions.get("workflow_runs") if isinstance(actions.get("workflow_runs"), dict) else {}
    workflow_counts = workflow_runs.get("counts") if isinstance(workflow_runs.get("counts"), dict) else {}
    jobs_summary = actions.get("jobs_summary") if isinstance(actions.get("jobs_summary"), dict) else {}
    job_counts = jobs_summary.get("counts") if isinstance(jobs_summary.get("counts"), dict) else {}
    job_total = int_count(jobs_summary, "total")
    workflow_total = int_count(workflow_runs, "total")
    use_jobs = bool(jobs_summary) and bool(job_counts)
    if use_jobs and job_total == 0 and workflow_total > 0:
        use_jobs = False
    counts = job_counts if use_jobs else workflow_counts
    total = job_total if use_jobs else workflow_total
    if not counts and total == 0 and ci_source_policy(payload) != "github_actions_only":
        counts = ci.get("check_runs") if isinstance(ci.get("check_runs"), dict) else {}
        total = int_count(counts, "total")
    ok = int_count(counts, "success") + int_count(counts, "skipped") + int_count(counts, "neutral")
    fail = int_count(counts, "failed")
    other = int_count(counts, "other")
    run = int_count(counts, "running")
    pend = int_count(counts, "pending")
    stale = int_count(counts, "stale")
    done = ok + fail + other
    return {
        "status": ci.get("status") or summary.get("ci") or "unknown",
        "done": done,
        "total": total,
        "ok": ok,
        "run": run,
        "pend": pend,
        "fail": fail,
        "other": other,
        "stale": stale,
    }


def review_progress_counts(payload: dict) -> dict:
    review = payload.get("review") if isinstance(payload.get("review"), dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    signals = review.get("signals") if isinstance(review.get("signals"), list) else []
    decision = decision_payload(payload)
    current = review.get("current") if isinstance(review.get("current"), dict) else {}
    codex_review = payload.get("codex_review")
    if not isinstance(codex_review, dict):
        nested_codex_review = review.get("codex_review")
        codex_review = nested_codex_review if isinstance(nested_codex_review, dict) else {}
    selected_review_comments = codex_review.get("selected_review_comments")
    selected_reviews = codex_review.get("selected_reviews")
    comments = len(review_progress_signal_items(payload)) if signals else 0
    decision_comment_count = (
        len(decision.get("selected_review_comment_ids", []))
        if isinstance(decision.get("selected_review_comment_ids"), list)
        else 0
    )
    decision_review_count = (
        len(decision.get("selected_review_ids", [])) if isinstance(decision.get("selected_review_ids"), list) else 0
    )
    current_comment_count = (
        len(current.get("selected_review_comments", []))
        if isinstance(current.get("selected_review_comments"), list)
        else 0
    )
    current_review_count = (
        len(current.get("selected_reviews", [])) if isinstance(current.get("selected_reviews"), list) else 0
    )
    current_signal_count = len(current.get("signals", [])) if isinstance(current.get("signals"), list) else 0
    comments = max(
        comments,
        decision_comment_count + decision_review_count,
        current_comment_count + current_review_count,
        current_signal_count,
    )
    if isinstance(selected_review_comments, list):
        comments = max(comments, len(selected_review_comments))
    if isinstance(selected_reviews, list):
        comments = max(comments, len(selected_reviews))
    review_requests = review.get("review_requests")
    requested = len(review_requests) if isinstance(review_requests, list) else 0
    selected_thread_ids = decision.get("selected_review_thread_ids")
    if not isinstance(selected_thread_ids, list):
        selected_thread_ids = current.get("selected_thread_ids")
    selected_unresolved_ids = decision.get("selected_unresolved_thread_ids")
    if not isinstance(selected_unresolved_ids, list):
        selected_unresolved_ids = current.get("selected_unresolved_thread_ids")
    selected_unresolved_count = int_count(decision, "selected_unresolved_count")
    if selected_unresolved_count == 0 and isinstance(selected_unresolved_ids, list):
        selected_unresolved_count = len(selected_unresolved_ids)
    if not decision and not current:
        threads = review.get("threads") if isinstance(review.get("threads"), dict) else {}
        thread_count = int_count(threads, "total")
        unresolved_count = int_count(threads, "unresolved")
    else:
        thread_count = len(selected_thread_ids) if isinstance(selected_thread_ids, list) else 0
        unresolved_count = selected_unresolved_count
    return {
        "status": review.get("status") or summary.get("review") or "unknown",
        "comments": comments,
        "threads": thread_count,
        "unresolved": unresolved_count,
        "requested": requested,
        "limits": len(payload.get("limitations")) if isinstance(payload.get("limitations"), list) else 0,
    }


def decision_payload(payload: dict) -> dict:
    decision = payload.get("decision")
    return decision if isinstance(decision, dict) else {}


def decision_fingerprint(payload: dict) -> str | None:
    value = payload.get("decision_fingerprint")
    if isinstance(value, str) and value:
        return value
    decision = decision_payload(payload)
    value = decision.get("fingerprint")
    if isinstance(value, str) and value:
        return value
    return None


def align_decision_observation_complete(payload: dict, observation_complete: bool) -> None:
    decision = decision_payload(payload)
    if not decision:
        return
    if decision.get("status") == "passed":
        return
    if decision.get("observation_complete") is observation_complete:
        return
    decision["observation_complete"] = observation_complete
    fingerprint_source = dict(decision)
    fingerprint_source.pop("fingerprint", None)
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_source, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    decision["fingerprint"] = fingerprint
    payload["decision_fingerprint"] = fingerprint


def refresh_decision_fingerprint(payload: dict) -> None:
    decision = decision_payload(payload)
    if not decision:
        return
    fingerprint_source = dict(decision)
    fingerprint_source.pop("fingerprint", None)
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_source, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    decision["fingerprint"] = fingerprint
    payload["decision_fingerprint"] = fingerprint


def decision_int(decision: dict, key: str, default: int = 0) -> int:
    value = decision.get(key)
    return value if isinstance(value, int) else default


def decision_list(decision: dict, key: str) -> list:
    value = decision.get(key)
    return value if isinstance(value, list) else []


def has_explicit_actionable_unresolved_fields(decision: dict) -> bool:
    return "actionable_unresolved_count" in decision or "actionable_unresolved_thread_ids" in decision


def current_selected_actionable_reason(payload: dict) -> str | None:
    decision = decision_payload(payload)
    selected_unresolved_thread_ids = decision_list(decision, "selected_unresolved_thread_ids")
    selected_unresolved_count = decision_int(
        decision,
        "selected_unresolved_count",
        len(selected_unresolved_thread_ids),
    )
    current_selected_unresolved_count = decision_int(
        decision,
        "current_selected_unresolved_count",
        selected_unresolved_count,
    )
    actionable_unresolved_count = decision_int(decision, "actionable_unresolved_count")
    actionable_unresolved_thread_ids = decision_list(decision, "actionable_unresolved_thread_ids")
    if (
        has_explicit_actionable_unresolved_fields(decision)
        and actionable_unresolved_count == 0
        and not actionable_unresolved_thread_ids
    ):
        selected_unresolved_count = 0
        current_selected_unresolved_count = 0
    selected_changes_requested_evidence = decision_list(decision, "selected_changes_requested_evidence")
    decision_reason = decision.get("status_reason")
    if (
        decision_reason == "current_selected_unresolved_thread"
        or selected_unresolved_count > 0
        or current_selected_unresolved_count > 0
    ):
        return "current_selected_unresolved_thread"
    if decision_reason == "current_selected_changes_requested" or selected_changes_requested_evidence:
        return "current_selected_changes_requested"
    return None


def carryover_inventory_reason(payload: dict) -> str | None:
    decision = decision_payload(payload)
    carryover_unresolved_count = decision_int(decision, "carryover_unresolved_count")
    carryover_unresolved_thread_ids = decision_list(decision, "carryover_unresolved_thread_ids")
    decision_reason = decision.get("status_reason")
    if (
        decision_reason == "carryover_non_outdated_unresolved_thread"
        or carryover_unresolved_count > 0
        or bool(carryover_unresolved_thread_ids)
    ):
        return "carryover_non_outdated_unresolved_thread"
    return None


def explicit_actionable_unresolved_reason(payload: dict) -> str | None:
    decision = decision_payload(payload)
    actionable_unresolved_count = decision_int(decision, "actionable_unresolved_count")
    actionable_unresolved_thread_ids = decision_list(decision, "actionable_unresolved_thread_ids")
    if actionable_unresolved_count > 0 or actionable_unresolved_thread_ids:
        return "actionable_unresolved_thread"
    return None


def trusted_completion_actionable_reason(payload: dict) -> str | None:
    current_reason = current_selected_actionable_reason(payload)
    if current_reason:
        return current_reason
    decision = decision_payload(payload)
    lifecycle = codex_review_lifecycle(payload)
    completion_signal = decision.get("completion_signal") or lifecycle.get("completion_signal")
    fallback_pass_candidate = decision.get("fallback_pass_candidate")
    if (
        completion_signal == "fallback_issue_comment"
        and isinstance(fallback_pass_candidate, dict)
        and fallback_pass_candidate.get("promotes_top_level_status") is True
    ):
        return explicit_actionable_unresolved_reason(payload)
    if completion_signal == "submitted_pull_request_review":
        carryover_reason = carryover_inventory_reason(payload)
        if carryover_reason:
            return carryover_reason
        return explicit_actionable_unresolved_reason(payload)
    return None


def mark_decision_actionable_unresolved(payload: dict, reason: str) -> None:
    decision = decision_payload(payload)
    if not decision:
        return
    decision["status"] = "human_gate"
    decision["status_reason"] = reason
    decision["recommended_next_action"] = "address_review_feedback"
    decision["observation_complete"] = False
    fingerprint_source = dict(decision)
    fingerprint_source.pop("fingerprint", None)
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_source, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    decision["fingerprint"] = fingerprint
    payload["decision_fingerprint"] = fingerprint


def align_actionable_review_summary(payload: dict, reason: str | None) -> None:
    if reason not in {"current_selected_unresolved_thread", "carryover_non_outdated_unresolved_thread"}:
        return
    summary = payload.get("summary")
    if isinstance(summary, dict):
        summary["review"] = "unresolved"


def mark_decision_timeout(payload: dict) -> None:
    decision = decision_payload(payload)
    if not decision:
        return
    decision["status"] = "timeout"
    decision["status_reason"] = "wait_timeout"
    decision["recommended_next_action"] = "wait_or_resume"
    decision["observation_complete"] = False
    fingerprint_source = dict(decision)
    fingerprint_source.pop("fingerprint", None)
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_source, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    decision["fingerprint"] = fingerprint
    payload["decision_fingerprint"] = fingerprint


def mark_decision_fallback_pass(payload: dict) -> None:
    decision = decision_payload(payload)
    if not decision:
        return
    decision["status"] = "passed"
    decision["status_reason"] = "fallback_issue_comment_no_major_issues"
    decision["recommended_next_action"] = "merge_prepared"
    decision["observation_complete"] = True
    fingerprint_source = dict(decision)
    fingerprint_source.pop("fingerprint", None)
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_source, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    decision["fingerprint"] = fingerprint
    payload["decision_fingerprint"] = fingerprint


def codex_review_payload(payload: dict) -> dict:
    codex_review = payload.get("codex_review")
    if isinstance(codex_review, dict):
        return codex_review
    review = payload.get("review") if isinstance(payload.get("review"), dict) else {}
    nested_codex_review = review.get("codex_review")
    return nested_codex_review if isinstance(nested_codex_review, dict) else {}


def codex_review_lifecycle(payload: dict) -> dict:
    lifecycle = codex_review_payload(payload).get("lifecycle")
    return lifecycle if isinstance(lifecycle, dict) else {}


def ci_status(payload: dict) -> str:
    ci = payload.get("ci") if isinstance(payload.get("ci"), dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    return str(ci.get("status") or summary.get("ci") or "unknown")


def trigger_created_at_for_latency(payload: dict, fallback_created_at: str) -> object:
    trigger = payload.get("trigger") if isinstance(payload.get("trigger"), dict) else {}
    return trigger.get("created_at") or fallback_created_at


def previous_wait_ci_passed_since(
    out_dir: Path | None,
    *,
    repo: str,
    pr: str,
    head_sha: str,
    trigger_comment_id: str,
    trigger_created_at: str,
) -> datetime | None:
    if out_dir is None:
        return None
    result_path = out_dir / "result.json"
    if not result_path.is_file():
        return None
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None

    resume = payload.get("resume") if isinstance(payload.get("resume"), dict) else {}
    trigger = payload.get("trigger") if isinstance(payload.get("trigger"), dict) else {}
    wait = payload.get("wait") if isinstance(payload.get("wait"), dict) else {}
    if not wait:
        return None

    previous_repo = resume.get("repo") or payload.get("repo")
    previous_pr = resume.get("pr") or payload.get("pr")
    previous_head_sha = resume.get("head_sha") or payload.get("expected_head_sha")
    previous_trigger_comment_id = resume.get("trigger_comment_id") or trigger.get("comment_id")
    previous_trigger_created_at = resume.get("trigger_created_at") or trigger.get("created_at")

    if previous_repo and str(previous_repo) != repo:
        return None
    if previous_pr and str(previous_pr) != str(pr):
        return None
    if previous_head_sha and str(previous_head_sha) != head_sha:
        return None
    if previous_trigger_comment_id and str(previous_trigger_comment_id) != str(trigger_comment_id):
        return None
    if previous_trigger_created_at and str(previous_trigger_created_at) != str(trigger_created_at):
        return None

    ci_passed_since = parse_utc_timestamp(wait.get("ci_passed_since"))
    if ci_passed_since is not None:
        return ci_passed_since

    observed_at = parse_utc_timestamp(payload.get("observed_at"))
    ci_passed_age_seconds = numeric_age_seconds(wait.get("ci_passed_age_seconds"))
    if observed_at is None or ci_passed_age_seconds is None:
        return None
    return observed_at - timedelta(seconds=ci_passed_age_seconds)


def semantic_fingerprint(payload: dict) -> str:
    authoritative_fingerprint = decision_fingerprint(payload)
    if authoritative_fingerprint:
        return authoritative_fingerprint
    ci_progress = ci_progress_counts(payload)
    review_progress = review_progress_counts(payload)
    lifecycle = codex_review_lifecycle(payload)
    decision = decision_payload(payload)
    source = {
        "repo": payload.get("repo"),
        "pr": payload.get("pr"),
        "expected_head_sha": payload.get("expected_head_sha"),
        "current_head_sha": payload.get("current_head_sha"),
        "head_matches_expected": payload.get("head_matches_expected"),
        "normalized_status": payload.get("normalized_status"),
        "limitations": limitation_codes(payload),
        "ci": {
            "status": payload.get("ci", {}).get("status") if isinstance(payload.get("ci"), dict) else None,
            "failures": payload.get("ci", {}).get("failures") if isinstance(payload.get("ci"), dict) else None,
            "progress": ci_progress,
        },
        "review": {
            "status": payload.get("review", {}).get("status") if isinstance(payload.get("review"), dict) else None,
            **(
                {}
                if decision
                else {
                    "signals": review_semantic_signal_items(payload),
                    "review_requests": payload.get("review", {}).get("review_requests")
                    if isinstance(payload.get("review"), dict)
                    else None,
                    "threads": payload.get("review", {}).get("threads")
                    if isinstance(payload.get("review"), dict)
                    else None,
                }
            ),
            "body_mode": payload.get("review", {}).get("body_mode")
            if isinstance(payload.get("review"), dict)
            else None,
            "progress": review_progress,
        },
        "decision": decision,
        "codex_review": {
            "lifecycle": {
                "status": lifecycle.get("status"),
                "completion_signal": lifecycle.get("completion_signal"),
                "selected_review_ids": lifecycle.get("selected_review_ids"),
                "selected_review_comment_ids": lifecycle.get("selected_review_comment_ids"),
                "selected_review_thread_ids": lifecycle.get("selected_review_thread_ids"),
            },
            "collection_summary": codex_review_payload(payload).get("collection_summary"),
        },
        "trigger": payload.get("trigger"),
    }
    return sha256_json(source)


def blocker_fingerprints(payload: dict) -> list[str]:
    decision = decision_payload(payload)
    blocker_policy = decision.get("blocker_policy")
    if not isinstance(blocker_policy, dict):
        return []
    values = blocker_policy.get("blocker_fingerprints")
    if not isinstance(values, list):
        return []
    return [value for value in values if isinstance(value, str) and value]


def mark_automation_stalled(payload: dict, *, same_count: int, same_required: int) -> bool:
    fingerprints = blocker_fingerprints(payload)
    if not fingerprints or same_count < same_required:
        return False
    decision = decision_payload(payload)
    if decision.get("status") != "human_gate":
        return False
    if decision.get("recommended_next_action") == "merge_prepared":
        return False
    stalled = {
        "present": True,
        "reason": "same_blocker_fingerprint_repeated",
        "blocker_fingerprints": fingerprints,
        "same_fingerprint_observed": same_count,
        "same_fingerprint_required": same_required,
        "recommended_next_action": "human_gate",
    }
    payload["automation_stalled"] = stalled
    decision["automation_stalled"] = stalled
    decision["recommended_next_action"] = "human_gate"
    decision["status_reason"] = "automation_stalled"
    refresh_decision_fingerprint(payload)
    return True


def fallback_snapshot(snapshot_exit: int, stdout_text: str, stderr_text: str) -> dict:
    limitations = []
    if snapshot_exit != 0:
        limitations.append({
            "code": "snapshot_script_failed",
            "source": "fetch_pr_observation_snapshot.sh",
            "severity": "blocking",
            "message": "snapshot script failed before final wait classification",
            "exit_code": snapshot_exit,
            "stderr_sha256": hashlib.sha256(stderr_text.encode()).hexdigest(),
            "stdout_sha256": hashlib.sha256(stdout_text.encode()).hexdigest(),
        })
    else:
        limitations.append({
            "code": "snapshot_json_unavailable",
            "source": "fetch_pr_observation_snapshot.sh",
            "severity": "blocking",
            "message": "snapshot script did not return parseable JSON",
            "stdout_sha256": hashlib.sha256(stdout_text.encode()).hexdigest(),
        })
    return {
        "script": "fetch_pr_observation_snapshot.sh",
        "status": "unknown",
        "overall_status": "unknown",
        "normalized_status": "unknown",
        "observation_complete": False,
        "observed_at": utc_now(),
        "repo": os.environ["OBS_REPO"],
        "pr": int(os.environ["OBS_PR"]),
        "expected_head_sha": os.environ["OBS_HEAD_SHA"],
        "current_head_sha": None,
        "head_matches_expected": None,
        "summary": {"ci": "unknown", "review": "unknown", "head": "unknown"},
        "limitations": limitations,
        "recommended_next_action": "human_gate",
        "ci": {"status": "unknown", "checks": [], "failures": []},
        "review": {"status": "unknown", "signals": [], "codex_authored": []},
        "trigger": {"source": "none", "comment_id": None, "created_at": None},
        "artifacts": {},
    }


def timeout_snapshot(timeout_seconds: float, stdout_text: object, stderr_text: object) -> dict:
    if isinstance(stdout_text, bytes):
        stdout_text = stdout_text.decode(errors="replace")
    if isinstance(stderr_text, bytes):
        stderr_text = stderr_text.decode(errors="replace")
    stdout_text = "" if stdout_text is None else str(stdout_text)
    stderr_text = "" if stderr_text is None else str(stderr_text)
    return {
        "script": "fetch_pr_observation_snapshot.sh",
        "status": "timeout",
        "overall_status": "timeout",
        "normalized_status": "timeout",
        "observation_complete": False,
        "observed_at": utc_now(),
        "repo": os.environ["OBS_REPO"],
        "pr": int(os.environ["OBS_PR"]),
        "expected_head_sha": os.environ["OBS_HEAD_SHA"],
        "current_head_sha": None,
        "head_matches_expected": None,
        "summary": {"ci": "unknown", "review": "unknown", "head": "unknown"},
        "limitations": [
            {
                "code": "snapshot_poll_timeout",
                "source": "fetch_pr_observation_snapshot.sh",
                "severity": "blocking",
                "message": "snapshot poll exceeded the remaining wait deadline",
                "timeout_seconds": timeout_seconds,
                "stdout_sha256": hashlib.sha256(stdout_text.encode()).hexdigest(),
                "stderr_sha256": hashlib.sha256(stderr_text.encode()).hexdigest(),
            }
        ],
        "recommended_next_action": "wait_or_resume",
        "ci": {"status": "unknown", "checks": [], "failures": []},
        "review": {"status": "unknown", "signals": [], "codex_authored": []},
        "trigger": {},
        "artifacts": {},
    }


def append_snapshot_poll_timeout_limitation(
    payload: dict,
    timeout_seconds: float,
    stdout_text: object,
    stderr_text: object,
    *,
    source: str = "fetch_pr_observation_snapshot.sh",
    severity: str = "blocking",
    message: str = "snapshot poll exceeded the remaining wait deadline",
    deadline_reached: bool | None = None,
) -> None:
    if isinstance(stdout_text, bytes):
        stdout_text = stdout_text.decode(errors="replace")
    if isinstance(stderr_text, bytes):
        stderr_text = stderr_text.decode(errors="replace")
    stdout_text = "" if stdout_text is None else str(stdout_text)
    stderr_text = "" if stderr_text is None else str(stderr_text)
    limitations = payload.setdefault("limitations", [])
    if any(isinstance(item, dict) and item.get("code") == "snapshot_poll_timeout" for item in limitations):
        return
    limitations.append({
        "code": "snapshot_poll_timeout",
        "source": source,
        "severity": severity,
        "message": message,
        "timeout_seconds": timeout_seconds,
        "stdout_sha256": hashlib.sha256(stdout_text.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr_text.encode()).hexdigest(),
        **({} if deadline_reached is None else {"deadline_reached": deadline_reached}),
    })


def terminate_process_group(proc: subprocess.Popen[str]) -> None:
    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        return
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=1)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(pgid, signal.SIGKILL)
        proc.wait()


def run_snapshot(
    args: list[str],
    timeout_seconds: float,
    env_overrides: dict[str, str] | None = None,
) -> tuple[int, str, str, bool]:
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=({**os.environ, **env_overrides} if env_overrides else None),
        start_new_session=True,
    )
    try:
        stdout_text, stderr_text = proc.communicate(timeout=timeout_seconds)
        return proc.returncode, stdout_text, stderr_text, False
    except subprocess.TimeoutExpired as exc:
        terminate_process_group(proc)
        stdout_text, stderr_text = proc.communicate()
        if exc.stdout:
            stdout_text = (exc.stdout if isinstance(exc.stdout, str) else exc.stdout.decode(errors="replace")) + (
                stdout_text or ""
            )
        if exc.stderr:
            stderr_text = (exc.stderr if isinstance(exc.stderr, str) else exc.stderr.decode(errors="replace")) + (
                stderr_text or ""
            )
        return (
            proc.returncode if proc.returncode is not None else -signal.SIGKILL,
            stdout_text or "",
            stderr_text or "",
            True,
        )


def trigger_failure_result(trigger_payload: dict, trigger_stdout: str, trigger_stderr: str) -> dict:
    trigger = trigger_payload.get("trigger") if isinstance(trigger_payload.get("trigger"), dict) else {}
    normalized_status = trigger_payload.get("overall_status") or trigger_payload.get("status") or "unknown"
    if normalized_status == "trigger_posted":
        normalized_status = "unknown"
    if has_permission_signal(trigger_payload):
        normalized_status = "human_gate"
        next_action = "fix_github_token_permissions"
    elif normalized_status == "stale_head":
        next_action = "rerun_for_current_head"
    elif normalized_status == "draft_pr":
        normalized_status = "human_gate"
        next_action = "mark_pr_ready_for_review"
    elif normalized_status == "non_open_pr":
        normalized_status = "human_gate"
        next_action = "reopen_or_use_open_pr"
    else:
        next_action = "human_gate"
    return {
        **trigger_payload,
        "script": "wait_pr_observation.sh",
        "status": normalized_status,
        "overall_status": normalized_status,
        "normalized_status": normalized_status,
        "observation_complete": False,
        "observed_at": utc_now(),
        "recommended_next_action": next_action,
        "trigger": {
            **trigger,
            "mode": "post-once",
            "helper_success": False,
            "helper_stdout_sha256": hashlib.sha256(trigger_stdout.encode()).hexdigest(),
            "helper_stderr_sha256": hashlib.sha256(trigger_stderr.encode()).hexdigest(),
        },
        "wait": {
            "polls": 0,
            "contract_phase": "s02_trigger_post_once",
        },
    }


def write_final_artifacts(
    *,
    out_dir: Path,
    result_text: str,
    latest_snapshot_text: str = "{}\n",
    latest_delta: dict | None = None,
    events: list[dict] | None = None,
    latest_snapshot_out_dir: Path | None = None,
) -> None:
    if latest_snapshot_out_dir:
        copy_tree_contents(latest_snapshot_out_dir / "raw", out_dir / "raw")
    (out_dir / "result.json").write_text(result_text, encoding="utf-8")
    (out_dir / "latest.json").write_text(
        latest_snapshot_text if latest_snapshot_text.endswith("\n") else latest_snapshot_text + "\n",
        encoding="utf-8",
    )
    (out_dir / "latest_delta.json").write_text(
        json.dumps(latest_delta or {}, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    (out_dir / "events.ndjson").write_text(
        "".join(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n" for event in (events or [])),
        encoding="utf-8",
    )


def run_trigger(
    *,
    trigger_script: str,
    repo: str,
    pr: str,
    head_sha: str,
    timeout_seconds: float,
) -> dict:
    exit_code, stdout_text, stderr_text, timed_out = run_snapshot(
        [trigger_script, "--repo", repo, "--pr", pr, "--head-sha", head_sha],
        max(0.1, timeout_seconds),
    )
    if timed_out:
        return {
            "script": "trigger_codex_review.sh",
            "success": False,
            "overall_status": "trigger_timeout",
            "limitations": [
                {
                    "code": "trigger_timeout",
                    "source": "trigger_codex_review.sh",
                    "severity": "blocking",
                    "message": "trigger helper exceeded the remaining wait deadline",
                    "timeout_seconds": timeout_seconds,
                    "stdout_sha256": hashlib.sha256(stdout_text.encode()).hexdigest(),
                    "stderr_sha256": hashlib.sha256(stderr_text.encode()).hexdigest(),
                }
            ],
            "trigger": {"mode": "post-once", "action": "failed"},
            "_helper_stdout": stdout_text,
            "_helper_stderr": stderr_text,
        }
    try:
        payload = json.loads(stdout_text)
    except Exception:
        payload = {
            "script": "trigger_codex_review.sh",
            "success": False,
            "overall_status": "trigger_json_unavailable",
            "limitations": [
                {
                    "code": "trigger_json_unavailable",
                    "source": "trigger_codex_review.sh",
                    "severity": "blocking",
                    "message": "trigger helper did not return parseable JSON",
                    "exit_code": exit_code,
                    "stdout_sha256": hashlib.sha256(stdout_text.encode()).hexdigest(),
                    "stderr_sha256": hashlib.sha256(stderr_text.encode()).hexdigest(),
                }
            ],
            "trigger": {"mode": "post-once", "action": "failed"},
        }
    if exit_code != 0:
        payload.setdefault("limitations", []).append({
            "code": "trigger_helper_failed",
            "source": "trigger_codex_review.sh",
            "severity": "blocking",
            "message": "trigger helper exited non-zero",
            "exit_code": exit_code,
            "stderr_sha256": hashlib.sha256(stderr_text.encode()).hexdigest(),
        })
        payload["success"] = False
        payload.setdefault("overall_status", "trigger_helper_failed")
    payload["_helper_stdout"] = stdout_text
    payload["_helper_stderr"] = stderr_text
    return payload


def copy_tree_contents(source: Path, destination: Path) -> None:
    if not source.is_dir():
        return
    destination.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        target = destination / child.name
        if child.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(child, target)
        else:
            shutil.copy2(child, target)


def clear_managed_out_artifacts(out_dir: Path) -> None:
    managed_names = [
        "result.json",
        "latest.json",
        "events.ndjson",
        "latest_delta.json",
        "raw",
        "snapshots",
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in managed_names:
        target = out_dir / name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists() or target.is_symlink():
            target.unlink()
    (out_dir / "snapshots").mkdir(parents=True, exist_ok=True)
    (out_dir / "raw").mkdir(parents=True, exist_ok=True)


def classify(payload: dict, poll: int, zero_check_grace_polls: int) -> tuple[str, str, str, bool, bool]:
    ci = payload.get("ci") if isinstance(payload.get("ci"), dict) else {}
    review = payload.get("review") if isinstance(payload.get("review"), dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    ci_status = ci.get("status") or summary.get("ci") or "unknown"
    summary_review_status = summary.get("review")
    review_status = review.get("status") or summary_review_status or "unknown"
    decision = decision_payload(payload)
    decision_status = decision.get("status")
    decision_reason = decision.get("status_reason")
    decision_next_action = decision.get("recommended_next_action")
    lifecycle = codex_review_lifecycle(payload)
    lifecycle_status = lifecycle.get("status")
    completion_signal = decision.get("completion_signal") or lifecycle.get("completion_signal")
    top_level_status = payload.get("normalized_status")
    top_level_next_action = payload.get("recommended_next_action")

    if payload.get("head_matches_expected") is False or top_level_status == "stale_head":
        return "stale_head", "stale_head", "rerun_for_current_head", False, True
    if top_level_status == "human_gate" and top_level_next_action in {
        "mark_pr_ready_for_review",
        "reopen_or_use_open_pr",
    }:
        return "human_gate", "human_gate", top_level_next_action, False, True
    if ci_status == "none" and has_zero_actions_limitation(payload):
        zero_ignored_codes = {
            "zero_actions_runs_non_success",
            "zero_checks_s03_non_success",
        }
        if has_blocking_limitation(payload, ignored_codes=zero_ignored_codes):
            if has_permission_limitation(payload):
                return "unknown", "unknown", "fix_github_token_permissions", False, True
            return "unknown", "unknown", "human_gate", False, True
        if poll < zero_check_grace_polls:
            return "none", "none", "wait", False, False
        return "unknown", "unknown", "human_gate", False, True
    if ci_status == "failed":
        return "failed", "failed", "fix_ci", False, True
    if ci_status in {"pending", "running", "none"}:
        if has_blocking_limitation(payload, ignored_codes={"required_checks_missing_or_pending"}):
            if has_permission_limitation(payload):
                return "unknown", "unknown", "fix_github_token_permissions", False, True
            return "unknown", "unknown", "human_gate", False, True
        return ci_status, ci_status, "wait", False, False
    if (
        ci_status == "unknown"
        and top_level_status == "pending"
        and top_level_next_action == "wait"
        and has_waitable_required_actions_context_limitation(payload)
    ):
        if has_blocking_limitation(payload, ignored_codes={"required_actions_context_pending"}):
            if has_permission_limitation(payload):
                return "unknown", "unknown", "fix_github_token_permissions", False, True
            return "unknown", "unknown", "human_gate", False, True
        return "pending", "pending", "wait", False, False
    actionable_reason = trusted_completion_actionable_reason(payload)
    if ci_status == "passed" and actionable_reason:
        return "human_gate", "human_gate", "address_review_feedback", False, True
    if has_permission_limitation(payload):
        return "unknown", "unknown", "fix_github_token_permissions", False, True
    if has_blocking_limitation(payload):
        return "unknown", "unknown", "human_gate", False, True
    if ci_status != "passed":
        return "unknown", "unknown", "human_gate", False, True
    if decision:
        if decision_reason in {"current_selected_unresolved_thread", "current_selected_changes_requested"}:
            return "human_gate", "human_gate", "address_review_feedback", False, True
        fallback_pass_candidate = decision.get("fallback_pass_candidate")
        if (
            completion_signal == "fallback_issue_comment"
            and isinstance(fallback_pass_candidate, dict)
            and fallback_pass_candidate.get("promotes_top_level_status") is True
            and review_status not in {"changes_requested", "requested", "pending", "unknown", "unresolved"}
        ):
            mark_decision_fallback_pass(payload)
            return "passed", "passed", "merge_prepared", True, False
        if completion_signal == "fallback_issue_comment" or decision_reason == "fallback_issue_comment_low_confidence":
            return "human_gate", "human_gate", "manual_review_required_non_retryable", False, True
        if decision_reason == "missing_current_completion_signal":
            return "pending", "pending", "wait_or_resume", False, False
        if (
            completion_signal == "codex_no_findings_issue_comment"
            and decision_status == "passed"
            and top_level_status == "passed"
            and top_level_next_action == "merge_prepared"
        ):
            return "passed", "passed", "merge_prepared", True, False
        if decision_status == "passed" and decision_next_action == "merge_prepared":
            return "passed", "passed", "merge_prepared", True, False
        if decision_status == "human_gate":
            return "human_gate", "human_gate", decision_next_action or "human_gate", False, True
        if decision_status in {"pending", "none"}:
            return "pending", "pending", decision_next_action or "wait_or_resume", False, False
        return "unknown", "unknown", decision_next_action or "human_gate", False, True
    if completion_signal == "fallback_issue_comment":
        return "human_gate", "human_gate", "manual_review_required_non_retryable", False, True
    if summary_review_status in {"requested", "commented", "changes_requested", "unresolved"}:
        return "human_gate", "human_gate", "address_review_feedback", True, False
    if review_status in {"requested", "commented", "changes_requested", "unresolved"}:
        return "human_gate", "human_gate", "address_review_feedback", True, False
    if review_status in {"none", "pending"} and lifecycle_status in {"pending", "unknown"}:
        return "pending", "pending", "wait", False, False
    if review_status in {"none", "pending"} and lifecycle_status == "none" and completion_signal == "none":
        return "pending", "pending", "wait", False, False
    if completion_signal != "submitted_pull_request_review":
        return "pending", "pending", "wait", False, False
    if review_status == "approved":
        return "passed", "passed", "merge_prepared", True, False
    if review_status == "none":
        return "passed", "passed", "merge_prepared", True, False
    return "unknown", "unknown", "human_gate", False, True


def resume_command_hint(payload: dict) -> str | None:
    trigger = payload.get("trigger") if isinstance(payload.get("trigger"), dict) else {}
    comment_id = (
        trigger.get("comment_id") or globals().get("trigger_comment_id") or os.environ.get("OBS_TRIGGER_COMMENT_ID")
    )
    created_at = (
        trigger.get("created_at") or globals().get("trigger_created_at") or os.environ.get("OBS_TRIGGER_CREATED_AT")
    )
    if not comment_id or not created_at:
        return None
    return (
        "./.agents/skills/github-pr-observation/scripts/wait_pr_observation.sh"
        f" --repo {os.environ['OBS_REPO']}"
        f" --pr {os.environ['OBS_PR']}"
        f" --head-sha {os.environ['OBS_HEAD_SHA']}"
        " --trigger-mode resume"
        f" --trigger-comment-id {comment_id}"
        f" --trigger-created-at {created_at}"
    )


def attach_resume_metadata(payload: dict) -> None:
    trigger = payload.get("trigger") if isinstance(payload.get("trigger"), dict) else {}
    comment_id = (
        trigger.get("comment_id")
        or globals().get("trigger_comment_id")
        or os.environ.get("OBS_TRIGGER_COMMENT_ID")
        or None
    )
    created_at = (
        trigger.get("created_at")
        or globals().get("trigger_created_at")
        or os.environ.get("OBS_TRIGGER_CREATED_AT")
        or None
    )
    command_hint = resume_command_hint(payload)
    comment_id_value = int(comment_id) if isinstance(comment_id, str) and comment_id.isdigit() else comment_id
    payload["resume"] = {
        "available": bool(command_hint) and bool(comment_id) and bool(created_at),
        "trigger_mode": "resume",
        "trigger_comment_id": comment_id_value,
        "trigger_created_at": created_at,
        "repo": os.environ["OBS_REPO"],
        "pr": int(os.environ["OBS_PR"]),
        "head_sha": os.environ["OBS_HEAD_SHA"],
        "command_hint": command_hint,
    }


def progress_line(
    *,
    poll: int,
    elapsed: int,
    remain: int,
    phase: str,
    payload: dict,
    quiet_elapsed: int,
    quiet_required: int,
    same_count: int,
    same_required: int,
    observation_complete: bool,
) -> str:
    ci_counts = ci_progress_counts(payload)
    review_counts = review_progress_counts(payload)
    ci_status = ci_counts["status"]
    review_status = review_counts["status"]
    render_review = review_status
    if (
        phase == "wait"
        and not observation_complete
        and review_status in {"none", "pending", "unknown", "approved", "passed"}
    ):
        lifecycle = codex_review_lifecycle(payload)
        decision = decision_payload(payload)
        completion_signal = decision.get("completion_signal") or lifecycle.get("completion_signal")
        lifecycle_status = lifecycle.get("status")
        has_actionable_feedback = any(
            int(review_counts.get(key, 0) or 0) > 0 for key in ("comments", "threads", "unresolved", "requested")
        )
        if (
            not has_actionable_feedback
            and completion_signal in {None, "", "none"}
            and lifecycle_status in {None, "", "none", "pending", "unknown"}
        ):
            render_review = "pending_signal"

    fields: list[tuple[str, str, bool]] = [
        ("poll", str(poll), False),
        ("elapsed", str(elapsed), False),
        ("remain", str(remain), False),
        ("phase", phase, False),
        ("ci", str(ci_status), False),
    ]
    ci_detailed = phase == "wait" and ci_status in {"running", "pending", "none", "unknown"}
    if ci_detailed:
        fields.extend([
            ("checks", f"{ci_counts['done']}/{ci_counts['total']}", False),
            ("ok", str(ci_counts["ok"]), False),
            ("run", str(ci_counts["run"]), True),
            ("pend", str(ci_counts["pend"]), True),
            ("fail", str(ci_counts["fail"]), False),
            ("other", str(ci_counts["other"]), True),
        ])
    elif ci_status == "failed":
        fields.append(("fail", str(ci_counts["fail"]), False))

    fields.append(("review", str(render_review), False))
    review_human_gate = review_status in {"unresolved", "changes_requested", "commented"}
    review_detailed = phase == "wait" and not observation_complete
    if review_detailed or review_human_gate:
        fields.append(("comments", str(review_counts["comments"]), False))
    if review_detailed or review_status in {"unresolved", "changes_requested"}:
        fields.extend([
            ("threads", str(review_counts["threads"]), True),
            ("unresolved", str(review_counts["unresolved"]), True),
            ("requested", str(review_counts["requested"]), True),
        ])
    fields.extend([
        ("quiet", f"{quiet_elapsed}/{quiet_required}", False),
        ("stable", f"{same_count}/{same_required}", True),
    ])

    drop_order = ["other", "requested", "threads", "unresolved", "stable", "pend", "run"]
    active = list(fields)

    def build(parts: list[tuple[str, str, bool]], limit_value: str) -> str:
        rendered = ["pr_obs"] + [f"{key}={value}" for key, value, _optional in parts]
        rendered.extend([f"limit={limit_value}", "final=stdout_json"])
        return " ".join(rendered)

    line = build(active, "none")
    if len(line) <= 240:
        return line
    for key in drop_order:
        candidate = [item for item in active if not (item[0] == key and item[2])]
        if len(candidate) == len(active):
            continue
        active = candidate
        line = build(active, "truncated")
        if len(line) <= 240:
            return line
    return build(active, "truncated")[:240]


def mark_latest_timeout(
    payload: dict,
    latest_change_monotonic: float,
    same_count: int,
    quiet_elapsed: int | None = None,
) -> None:
    if quiet_elapsed is None:
        quiet_elapsed = int(max(0, time.monotonic() - latest_change_monotonic))
    append_snapshot_poll_timeout_limitation(
        payload,
        0,
        "",
        "",
        source="wait_pr_observation.sh",
        message="wait deadline expired before quiet/stability completed",
        deadline_reached=True,
    )
    payload["status"] = "timeout"
    payload["overall_status"] = "timeout"
    payload["normalized_status"] = "timeout"
    payload["observation_complete"] = False
    payload["recommended_next_action"] = "wait_or_resume"
    payload["observed_at"] = utc_now()
    payload.setdefault("wait", {})["deadline_reached"] = True
    payload["wait"]["quiet_seconds_observed"] = quiet_elapsed
    payload["wait"]["same_fingerprint_observed"] = same_count
    mark_decision_timeout(payload)
    payload["fingerprint"] = semantic_fingerprint(payload)
    attach_resume_metadata(payload)


validate_environment()

snapshot_script = os.environ["OBS_SNAPSHOT_SCRIPT"]
trigger_script = os.environ["OBS_TRIGGER_SCRIPT"]
repo = os.environ["OBS_REPO"]
pr = os.environ["OBS_PR"]
head_sha = os.environ["OBS_HEAD_SHA"]
timeout_seconds = int(os.environ["OBS_TIMEOUT_SECONDS"])
poll_interval_seconds = int(os.environ["OBS_POLL_INTERVAL_SECONDS"])
quiet_seconds = int(os.environ["OBS_QUIET_SECONDS"])
same_fingerprint_count = int(os.environ["OBS_SAME_FINGERPRINT_COUNT"])
zero_check_grace_polls = int(os.environ["OBS_ZERO_CHECK_GRACE_POLLS"])
trigger_mode = os.environ["OBS_TRIGGER_MODE"]
trigger_comment_id = os.environ["OBS_TRIGGER_COMMENT_ID"]
trigger_created_at = os.environ["OBS_TRIGGER_CREATED_AT"]
body_mode = os.environ["OBS_BODY_MODE"]
progress = os.environ["OBS_PROGRESS"]
out_dir_text = os.environ["OBS_OUT_DIR"]
out_dir = Path(out_dir_text) if out_dir_text else None
start_monotonic = time.monotonic()
deadline = start_monotonic + timeout_seconds
trigger_helper_metadata: dict = {}
previous_ci_passed_since = previous_wait_ci_passed_since(
    out_dir,
    repo=repo,
    pr=pr,
    head_sha=head_sha,
    trigger_comment_id=trigger_comment_id,
    trigger_created_at=trigger_created_at,
)

if out_dir:
    clear_managed_out_artifacts(out_dir)

if trigger_mode == "post-once":
    trigger_payload = run_trigger(
        trigger_script=trigger_script,
        repo=repo,
        pr=pr,
        head_sha=head_sha,
        timeout_seconds=max(0.1, deadline - time.monotonic()),
    )
    trigger_stdout = str(trigger_payload.pop("_helper_stdout", ""))
    trigger_stderr = str(trigger_payload.pop("_helper_stderr", ""))
    trigger = trigger_payload.get("trigger") if isinstance(trigger_payload.get("trigger"), dict) else {}
    trigger_comment_id = str(trigger.get("comment_id") or "")
    trigger_created_at = str(trigger.get("created_at") or "")
    trigger_helper_metadata = {
        **trigger,
        "helper_success": trigger_payload.get("success") is True,
    }
    if trigger_payload.get("success") is not True or not trigger_comment_id or not trigger_created_at:
        failure_payload = trigger_failure_result(trigger_payload, trigger_stdout, trigger_stderr)
        failure_payload.setdefault("artifacts", {})
        failure_payload["artifacts"].update({
            "result_json": str(out_dir / "result.json") if out_dir else None,
            "latest_json": str(out_dir / "latest.json") if out_dir else None,
            "events_ndjson": str(out_dir / "events.ndjson") if out_dir else None,
            "latest_delta_json": str(out_dir / "latest_delta.json") if out_dir else None,
            "snapshots_dir": str(out_dir / "snapshots") if out_dir else None,
        })
        result_text = (
            json.dumps(
                failure_payload,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )
        if out_dir:
            write_final_artifacts(out_dir=out_dir, result_text=result_text)
        print(
            result_text,
            end="",
        )
        raise SystemExit(0)

snapshot_args = [
    snapshot_script,
    "--repo",
    repo,
    "--pr",
    pr,
    "--head-sha",
    head_sha,
    "--body-mode",
    body_mode,
]
if trigger_comment_id:
    snapshot_args.extend(["--trigger-comment-id", trigger_comment_id])
if trigger_created_at:
    snapshot_args.extend(["--trigger-created-at", trigger_created_at])

previous_fingerprint = None
latest_change_monotonic = start_monotonic
same_count = 0
poll = 0
events: list[dict] = []
latest_payload: dict | None = None
latest_snapshot_text = "{}\n"
latest_delta: dict = {}
latest_snapshot_out_dir: Path | None = None
final_phase = "timeout"
ci_passed_first_monotonic: float | None = None
recent_snapshot_elapsed_seconds = NEXT_SNAPSHOT_BUDGET_FLOOR_SECONDS
next_poll_min_budget_seconds = recent_snapshot_elapsed_seconds + NEXT_SNAPSHOT_BUDGET_SLACK_SECONDS
final_poll_skipped_reason: str | None = None
under_budget_poll_exception_used = False
under_budget_poll_exception_kind: str | None = None

while True:
    if latest_payload is not None and time.monotonic() >= deadline:
        final_phase = "timeout"
        mark_latest_timeout(latest_payload, latest_change_monotonic, same_count)
        latest_payload.setdefault("wait", {})["next_poll_min_budget_seconds"] = round(
            next_poll_min_budget_seconds,
            3,
        )
        break

    remaining_before_poll = deadline - time.monotonic()
    under_budget_before_poll = latest_payload is not None and remaining_before_poll < next_poll_min_budget_seconds
    if under_budget_before_poll:
        quiet_deadline = latest_change_monotonic + quiet_seconds
        quiet_can_be_evaluated = deadline >= quiet_deadline
        stability_can_be_evaluated = same_count >= same_fingerprint_count or (same_count + 1 >= same_fingerprint_count)
        (
            _,
            _,
            _,
            can_complete_when_stable_before_poll,
            terminal_before_poll,
        ) = classify(
            latest_payload,
            poll,
            zero_check_grace_polls,
        )
        if terminal_before_poll:
            final_phase = "terminal"
            break
        zero_ignored_codes = {
            "zero_actions_runs_non_success",
            "zero_checks_s03_non_success",
        }
        zero_check_grace_can_be_evaluated = (
            not (under_budget_poll_exception_used and under_budget_poll_exception_kind == "zero_check_grace")
            and has_zero_actions_limitation(latest_payload)
            and poll < zero_check_grace_polls
            and not has_blocking_limitation(
                latest_payload,
                ignored_codes=zero_ignored_codes,
            )
        )
        under_budget_poll_exception_candidate_kind = None
        if can_complete_when_stable_before_poll and quiet_can_be_evaluated and stability_can_be_evaluated:
            under_budget_poll_exception_candidate_kind = "stable_completion"
        elif zero_check_grace_can_be_evaluated:
            under_budget_poll_exception_candidate_kind = "zero_check_grace"
        under_budget_poll_allowed = (
            not (under_budget_poll_exception_used and under_budget_poll_exception_candidate_kind == "zero_check_grace")
            and under_budget_poll_exception_candidate_kind is not None
        )
        if not under_budget_poll_allowed:
            final_poll_skipped_reason = "insufficient_next_snapshot_budget"
            final_phase = "timeout"
            mark_latest_timeout(latest_payload, latest_change_monotonic, same_count)
            latest_payload.setdefault("wait", {})["next_poll_min_budget_seconds"] = round(
                next_poll_min_budget_seconds,
                3,
            )
            latest_payload["wait"]["final_poll_skipped_reason"] = final_poll_skipped_reason
            latest_payload["wait"]["remaining_seconds_before_final_poll"] = round(
                max(0, remaining_before_poll),
                3,
            )
            break
        under_budget_poll_exception_used = True
        under_budget_poll_exception_kind = under_budget_poll_exception_candidate_kind
    else:
        under_budget_poll_exception_used = False
        under_budget_poll_exception_kind = None

    poll += 1
    now_before = time.monotonic()
    snapshot_timeout = max(0.001, deadline - time.monotonic())
    snapshot_poll_timed_out = False
    poll_snapshot_args = list(snapshot_args)
    poll_out_dir = None
    if out_dir:
        poll_out_dir = out_dir / "snapshots" / f"poll-{poll:04d}-artifacts"
        poll_snapshot_args.extend(["--out", str(poll_out_dir)])
    current_snapshot_out_dir = poll_out_dir
    snapshot_exit, snapshot_stdout, snapshot_stderr, snapshot_poll_timed_out = run_snapshot(
        poll_snapshot_args,
        snapshot_timeout,
    )
    recent_snapshot_elapsed_seconds = max(0, time.monotonic() - now_before)
    next_poll_min_budget_seconds = (
        max(
            NEXT_SNAPSHOT_BUDGET_FLOOR_SECONDS,
            recent_snapshot_elapsed_seconds,
        )
        + NEXT_SNAPSHOT_BUDGET_SLACK_SECONDS
    )
    snapshot_timeout_preserved_latest_state = False
    if snapshot_poll_timed_out and latest_payload is not None:
        payload = latest_payload
        (
            _,
            _,
            _,
            can_complete_when_stable_at_timeout,
            terminal_at_timeout,
        ) = classify(
            payload,
            poll,
            zero_check_grace_polls,
        )
        quiet_deadline = latest_change_monotonic + quiet_seconds
        stable_at_timeout = same_count >= same_fingerprint_count and time.monotonic() >= quiet_deadline
        snapshot_timeout_preserved_latest_state = bool(
            terminal_at_timeout or (can_complete_when_stable_at_timeout and stable_at_timeout)
        )
        if not snapshot_timeout_preserved_latest_state:
            append_snapshot_poll_timeout_limitation(
                payload,
                snapshot_timeout,
                snapshot_stdout,
                snapshot_stderr,
                severity="blocking",
            )
            mark_latest_timeout(payload, latest_change_monotonic, same_count)
        snapshot_text = latest_snapshot_text
    elif snapshot_poll_timed_out:
        payload = timeout_snapshot(snapshot_timeout, snapshot_stdout, snapshot_stderr)
        attach_resume_metadata(payload)
        snapshot_text = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    else:
        snapshot_text = snapshot_stdout if snapshot_stdout else "{}\n"
        try:
            payload = json.loads(snapshot_text)
            if not isinstance(payload, dict):
                payload = fallback_snapshot(snapshot_exit, snapshot_text, snapshot_stderr)
                snapshot_text = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
        except Exception:
            payload = fallback_snapshot(snapshot_exit, snapshot_text, snapshot_stderr)
            snapshot_text = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"

    fingerprint = semantic_fingerprint(payload)
    observed_monotonic = time.monotonic()
    if fingerprint == previous_fingerprint:
        same_count += 1
        changed = False
    else:
        latest_change_monotonic = observed_monotonic
        latest_delta = {
            "previous_fingerprint": previous_fingerprint,
            "current_fingerprint": fingerprint,
            "changed": previous_fingerprint is not None,
            "poll": poll,
        }
        same_count = 1
        previous_fingerprint = fingerprint
        changed = True

    quiet_elapsed = int(max(0, time.monotonic() - latest_change_monotonic))
    if ci_status(payload) == "passed":
        if ci_passed_first_monotonic is None:
            observed_age = age_seconds_from_timestamp(payload.get("observed_at"))
            ci_passed_first_monotonic = time.monotonic() - observed_age
            if previous_ci_passed_since is not None:
                previous_age = int(max(0, (datetime.now(timezone.utc) - previous_ci_passed_since).total_seconds()))
                ci_passed_first_monotonic = min(
                    ci_passed_first_monotonic,
                    time.monotonic() - previous_age,
                )
    else:
        ci_passed_first_monotonic = None
        previous_ci_passed_since = None
    normalized_status, overall_status, next_action, can_complete_when_stable, terminal_now = classify(
        payload,
        poll,
        zero_check_grace_polls,
    )
    event_normalized_status = normalized_status
    stable = same_count >= same_fingerprint_count and quiet_elapsed >= quiet_seconds
    review_trigger_age_seconds = age_seconds_from_timestamp(trigger_created_at_for_latency(payload, trigger_created_at))
    ci_passed_age_seconds = (
        int(max(0, time.monotonic() - ci_passed_first_monotonic)) if ci_passed_first_monotonic is not None else 0
    )
    ci_passed_since = (
        utc_text(datetime.now(timezone.utc) - timedelta(seconds=ci_passed_age_seconds))
        if ci_passed_first_monotonic is not None
        else None
    )
    observation_complete = bool(can_complete_when_stable and stable)
    elapsed = int(max(0, time.monotonic() - start_monotonic))
    remain = int(max(0, deadline - time.monotonic()))
    if observation_complete:
        final_phase = "terminal"
    elif snapshot_poll_timed_out and not snapshot_timeout_preserved_latest_state:
        final_phase = "timeout"
        normalized_status = "timeout"
        overall_status = "timeout"
        next_action = "wait_or_resume"
        mark_decision_timeout(payload)
    elif terminal_now:
        final_phase = "terminal"
    elif time.monotonic() >= deadline:
        final_phase = "timeout"
        mark_latest_timeout(payload, latest_change_monotonic, same_count, quiet_elapsed)
        normalized_status = "timeout"
        overall_status = "timeout"
        next_action = "wait_or_resume"
        mark_decision_timeout(payload)
    else:
        final_phase = "wait"

    final_actionable_reason = trusted_completion_actionable_reason(payload)
    if final_phase == "terminal" and final_actionable_reason:
        normalized_status = "human_gate"
        overall_status = "human_gate"
        next_action = "address_review_feedback"
        observation_complete = False
        mark_decision_actionable_unresolved(payload, final_actionable_reason)
        align_actionable_review_summary(payload, final_actionable_reason)

    if normalized_status == "human_gate" and mark_automation_stalled(
        payload, same_count=same_count, same_required=same_fingerprint_count
    ):
        normalized_status = "human_gate"
        overall_status = "human_gate"
        next_action = "human_gate"
        observation_complete = False
        terminal_now = True
    elif normalized_status == "human_gate" and blocker_fingerprints(payload) and same_count < same_fingerprint_count:
        terminal_now = False
    if normalized_status == "human_gate" and has_permission_signal(payload):
        next_action = "fix_github_token_permissions"

    payload["script"] = "wait_pr_observation.sh"
    payload["status"] = normalized_status
    payload["overall_status"] = overall_status
    payload["normalized_status"] = normalized_status
    payload["observation_complete"] = observation_complete
    payload["recommended_next_action"] = next_action
    if payload.get("normalized_status") == "timeout":
        mark_decision_timeout(payload)
    align_decision_observation_complete(payload, observation_complete)
    fingerprint = semantic_fingerprint(payload)
    payload["fingerprint"] = fingerprint
    payload["observed_at"] = utc_now()
    payload["wait"] = {
        "polls": poll,
        "timeout_seconds": timeout_seconds,
        "poll_interval_seconds": poll_interval_seconds,
        "next_poll_min_budget_seconds": round(next_poll_min_budget_seconds, 3),
        "quiet_seconds_required": quiet_seconds,
        "quiet_seconds_observed": quiet_elapsed,
        "same_fingerprint_required": same_fingerprint_count,
        "same_fingerprint_observed": same_count,
        "review_trigger_age_seconds": review_trigger_age_seconds,
        "ci_passed_age_seconds": ci_passed_age_seconds,
        "ci_passed_since": ci_passed_since,
        "zero_check_grace_polls": zero_check_grace_polls,
        "latest_change_poll": latest_delta.get("poll", poll),
        "deadline_reached": final_phase == "timeout" or time.monotonic() >= deadline,
        "contract_phase": "s05_stable_wait_loop",
    }
    if final_poll_skipped_reason:
        payload["wait"]["final_poll_skipped_reason"] = final_poll_skipped_reason
    payload.setdefault("artifacts", {})
    payload["artifacts"].update({
        "result_json": str(out_dir / "result.json") if out_dir else None,
        "latest_json": str(out_dir / "latest.json") if out_dir else None,
        "events_ndjson": str(out_dir / "events.ndjson") if out_dir else None,
        "latest_delta_json": str(out_dir / "latest_delta.json") if out_dir else None,
        "snapshots_dir": str(out_dir / "snapshots") if out_dir else None,
    })
    if trigger_helper_metadata:
        snapshot_trigger = payload.get("trigger") if isinstance(payload.get("trigger"), dict) else {}
        payload["trigger"] = {
            **trigger_helper_metadata,
            **snapshot_trigger,
        }
    if next_action == "wait_or_resume":
        attach_resume_metadata(payload)

    latest_payload = payload
    latest_snapshot_text = snapshot_text
    latest_snapshot_out_dir = current_snapshot_out_dir
    event = {
        "event": "poll",
        "poll": poll,
        "fingerprint": fingerprint,
        "changed": changed,
        "normalized_status": event_normalized_status,
        "observation_complete": observation_complete,
        "ci": payload.get("summary", {}).get("ci"),
        "review": payload.get("summary", {}).get("review"),
        "quiet_seconds_observed": quiet_elapsed,
        "same_fingerprint_observed": same_count,
    }
    events.append(event)

    if out_dir:
        (out_dir / "snapshots" / f"poll-{poll:04d}.json").write_text(
            latest_snapshot_text if latest_snapshot_text.endswith("\n") else latest_snapshot_text + "\n",
            encoding="utf-8",
        )

    if progress == "stderr-summary":
        print(
            progress_line(
                poll=poll,
                elapsed=elapsed,
                remain=remain,
                phase=final_phase,
                payload=payload,
                quiet_elapsed=quiet_elapsed,
                quiet_required=quiet_seconds,
                same_count=same_count,
                same_required=same_fingerprint_count,
                observation_complete=observation_complete,
            ),
            file=sys.stderr,
        )

    if observation_complete or terminal_now or final_phase == "timeout":
        break

    remaining_after_poll = max(0, deadline - time.monotonic())
    sleep_budget = max(0, remaining_after_poll - next_poll_min_budget_seconds)
    sleep_seconds = min(poll_interval_seconds, sleep_budget)
    if sleep_seconds <= 0:
        continue
    if under_budget_poll_exception_kind != "zero_check_grace":
        under_budget_poll_exception_used = False
        under_budget_poll_exception_kind = None
    time.sleep(sleep_seconds)

assert latest_payload is not None
result_text = json.dumps(latest_payload, sort_keys=True, separators=(",", ":")) + "\n"
if out_dir:
    if latest_snapshot_out_dir:
        copy_tree_contents(latest_snapshot_out_dir / "raw", out_dir / "raw")
    (out_dir / "result.json").write_text(result_text, encoding="utf-8")
    (out_dir / "latest.json").write_text(
        latest_snapshot_text if latest_snapshot_text.endswith("\n") else latest_snapshot_text + "\n",
        encoding="utf-8",
    )
    (out_dir / "latest_delta.json").write_text(
        json.dumps(latest_delta or {}, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    (out_dir / "events.ndjson").write_text(
        "".join(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n" for event in events),
        encoding="utf-8",
    )

print(result_text, end="")
