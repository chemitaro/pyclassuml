from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess

repo = os.environ["OBS_REPO"]
pr = int(os.environ["OBS_PR"])
expected_head_sha = os.environ["OBS_HEAD_SHA"]
expected_head_sha_lower = expected_head_sha.lower()
TERMINAL_GREEN_JOB_EXPANSION_CAP = 1
NON_TERMINAL_JOB_EXPANSION_CAP = 1


def token_source():
    if os.environ.get("GH_TOKEN"):
        return "GH_TOKEN"
    if os.environ.get("GITHUB_TOKEN"):
        return "GITHUB_TOKEN"
    return "gh_saved_auth"


def classify_github_stderr(stderr):
    lowered = (stderr or "").lower()
    if (
        "resource not accessible by personal access token" in lowered
        or "resource not accessible by integration" in lowered
        or "permission denied" in lowered
    ):
        return "permission_denied"
    if (
        "requires authentication" in lowered
        or "authentication required" in lowered
        or "not logged into" in lowered
        or "http 401" in lowered
    ):
        return "auth_missing"
    if "rate limit" in lowered or "http 429" in lowered:
        return "rate_limited"
    if "unknown json field" in lowered:
        return "schema_unavailable"
    if (
        "http 5" in lowered
        or "timeout" in lowered
        or "timed out" in lowered
        or "temporarily unavailable" in lowered
        or "connection reset" in lowered
    ):
        return "transient_unknown"
    return "unknown"


def capability_for_api(api):
    if api.endswith("/actions/runs") or "/actions/runs?" in api:
        return "actions_read"
    if "/actions/runs/" in api and api.endswith("/jobs"):
        return "actions_read"
    return "unknown"


def is_blocking_limitation(limitation):
    return limitation.get("severity") == "blocking" or limitation.get("blocking") is True


def github_failure_limitation(*, api, source, exit_code, stderr, default_code, default_message, default_severity):
    classification = classify_github_stderr(stderr)
    stderr_sha256 = hashlib.sha256((stderr or "").encode()).hexdigest()
    if classification == "permission_denied":
        return {
            "code": "github_token_permission_denied",
            "capability": capability_for_api(api),
            "api": api,
            "source": source,
            "status": "permission_denied",
            "token_source": token_source(),
            "severity": "blocking",
            "message": "GitHub token lacks permission for fixed PR observation API",
            "recommended_next_action": "fix_github_token_permissions",
            "secret_redacted": True,
            "stderr_sha256": stderr_sha256,
            "exit_code": exit_code,
        }
    if classification == "auth_missing":
        return {
            "code": "github_auth_missing",
            "capability": capability_for_api(api),
            "api": api,
            "source": source,
            "status": "auth_missing",
            "token_source": token_source(),
            "severity": "blocking",
            "message": "GitHub authentication is unavailable for fixed PR observation API",
            "recommended_next_action": "authenticate_github_cli",
            "secret_redacted": True,
            "stderr_sha256": stderr_sha256,
            "exit_code": exit_code,
        }
    if classification == "rate_limited":
        return {
            "code": "github_rate_limited",
            "capability": capability_for_api(api),
            "api": api,
            "source": source,
            "status": "rate_limited",
            "token_source": token_source(),
            "severity": "blocking",
            "message": "GitHub rate limit blocked fixed PR observation API",
            "recommended_next_action": "wait_or_retry_later",
            "secret_redacted": True,
            "stderr_sha256": stderr_sha256,
            "exit_code": exit_code,
        }
    if classification == "schema_unavailable":
        return {
            "code": "github_api_schema_unavailable",
            "capability": capability_for_api(api),
            "api": api,
            "source": source,
            "status": "schema_unavailable",
            "token_source": token_source(),
            "severity": "blocking",
            "message": "fixed read-only GitHub API schema is unavailable",
            "recommended_next_action": "inspect_github_api_schema",
            "secret_redacted": True,
            "stderr_sha256": stderr_sha256,
            "exit_code": exit_code,
        }
    if classification == "transient_unknown":
        return {
            "code": "github_transient_unknown",
            "capability": capability_for_api(api),
            "api": api,
            "source": source,
            "status": "transient_unknown",
            "token_source": token_source(),
            "severity": "blocking",
            "message": "transient GitHub failure blocked fixed PR observation API",
            "recommended_next_action": "retry_observation",
            "secret_redacted": True,
            "stderr_sha256": stderr_sha256,
            "exit_code": exit_code,
        }
    return {
        "code": default_code,
        "capability": capability_for_api(api),
        "api": api,
        "source": source,
        "status": classification,
        "token_source": token_source(),
        "severity": default_severity,
        "message": default_message,
        "secret_redacted": True,
        "exit_code": exit_code,
        "stderr_sha256": stderr_sha256,
    }


def sha_prefix_matches(left, right):
    left_lower = str(left or "").lower()
    right_lower = str(right or "").lower()
    return bool(left_lower and right_lower) and (
        left_lower.startswith(right_lower) or right_lower.startswith(left_lower)
    )


def gh_api(path):
    command = ["gh", "api", path, "--paginate"]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return None, github_failure_limitation(
            api=path,
            source=path,
            exit_code=completed.returncode,
            stderr=completed.stderr,
            default_code="github_api_collection_failed",
            default_message="fixed read-only GitHub API collection failed",
            default_severity="blocking",
        )
    try:
        return parse_gh_paginated_stdout(completed.stdout), None
    except json.JSONDecodeError:
        return None, github_failure_limitation(
            api=path,
            source=path,
            exit_code=completed.returncode,
            stderr=completed.stderr,
            default_code="github_api_schema_unavailable",
            default_message="fixed read-only GitHub API returned non-JSON output",
            default_severity="blocking",
        )


def gh_pr_head_oid():
    command = ["gh", "pr", "view", str(pr), "--repo", repo, "--json", "headRefOid"]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return {}, github_failure_limitation(
            api="gh_pr_view.headRefOid",
            source="gh_pr_view",
            exit_code=completed.returncode,
            stderr=completed.stderr,
            default_code="pr_head_sha_resolution_failed",
            default_message="fixed read-only PR head SHA resolution failed",
            default_severity="blocking",
        )
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError:
        return {}, {
            "code": "pr_head_sha_resolution_failed",
            "source": "gh_pr_view",
            "severity": "blocking",
            "message": "fixed read-only PR head SHA resolution returned non-JSON output",
        }
    return payload if isinstance(payload, dict) else {}, None


def parse_gh_paginated_stdout(stdout):
    text = stdout or "{}"
    decoder = json.JSONDecoder()
    index = 0
    payloads = []
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        payload, index = decoder.raw_decode(text, index)
        payloads.append(payload)
    if not payloads:
        return {}
    if len(payloads) == 1:
        return payloads[0]
    return merge_paginated_payloads(payloads)


def merge_paginated_payloads(payloads):
    if all(isinstance(payload, list) for payload in payloads):
        merged_list = []
        for payload in payloads:
            merged_list.extend(payload)
        return merged_list
    if not all(isinstance(payload, dict) for payload in payloads):
        return payloads[-1]

    merged = {}
    for payload in payloads:
        for key, value in payload.items():
            if isinstance(value, list):
                merged.setdefault(key, [])
                if isinstance(merged[key], list):
                    merged[key].extend(value)
                else:
                    merged[key] = value
            elif isinstance(value, int) and key in {"total_count"}:
                merged[key] = int(merged.get(key, 0) or 0) + value
            else:
                merged[key] = value
    return merged


def as_list(payload, key):
    value = payload.get(key) if isinstance(payload, dict) else None
    return value if isinstance(value, list) else []


def normalize_actions_status(item):
    status = str(item.get("status") or "").lower()
    conclusion = str(item.get("conclusion") or "").lower()
    if status == "completed":
        if conclusion in {
            "failure",
            "error",
            "cancelled",
            "timed_out",
            "action_required",
            "startup_failure",
            "stale",
        }:
            return "failed"
        if conclusion in {"success", "skipped", "neutral"}:
            return conclusion
        return "unknown"
    if status == "in_progress":
        return "running"
    if status in {"queued", "requested", "waiting", "pending"}:
        return "pending"
    return "unknown"


FAILED_ACTION_CONCLUSIONS = {
    "failure",
    "error",
    "cancelled",
    "timed_out",
    "action_required",
    "startup_failure",
    "stale",
}


def failed_action_steps(job):
    steps = job.get("steps") if isinstance(job.get("steps"), list) else []
    return [
        {
            "number": step.get("number"),
            "name": step.get("name"),
            "status": step.get("status"),
            "conclusion": step.get("conclusion"),
        }
        for step in steps
        if str(step.get("conclusion") or "").lower() in FAILED_ACTION_CONCLUSIONS
    ]


def actions_failure_entry(run, job=None):
    run_id = run.get("id")
    run_attempt = (job or {}).get("run_attempt") or run.get("run_attempt") or run.get("run_number")
    job_id = (job or {}).get("id")
    dedupe_key = f"actions:{run_id}:{job_id}:{run_attempt}" if job_id is not None else f"actions:{run_id}:run"
    return {
        "kind": "github_actions_job",
        "source": "actions",
        "workflow_run_id": run_id,
        "workflow_name": run.get("name"),
        "workflow_status": run.get("status"),
        "workflow_conclusion": run.get("conclusion"),
        "workflow_run_attempt": run_attempt,
        "job_id": job_id,
        "job_name": (job or {}).get("name"),
        "job_status": (job or {}).get("status"),
        "job_conclusion": (job or {}).get("conclusion"),
        "html_url": (job or {}).get("html_url") or run.get("html_url"),
        "failed_steps": failed_action_steps(job or {}),
        "dedupe_key": dedupe_key,
    }


limitations = []
actions_failures = []
actions_failure_dedupe_keys = set()
if len(expected_head_sha_lower) < 40:
    head_payload, head_limitation = gh_pr_head_oid()
    if head_limitation:
        limitations.append(head_limitation)
    current_head_sha = str(head_payload.get("headRefOid") or "").lower()
    if (
        len(current_head_sha) == 40
        and all(char in "0123456789abcdef" for char in current_head_sha)
        and current_head_sha.startswith(expected_head_sha_lower)
    ):
        expected_head_sha = current_head_sha
        expected_head_sha_lower = current_head_sha
    else:
        limitations.append({
            "code": "pr_head_sha_resolution_failed",
            "source": "gh_pr_view",
            "severity": "blocking",
            "message": "abbreviated PR head SHA could not be resolved to the current full head SHA",
        })

actions_runs_payload, actions_limitation = gh_api(f"repos/{repo}/actions/runs?head_sha={expected_head_sha}")
actions_available = actions_limitation is None
if actions_limitation:
    limitations.append(actions_limitation)
    actions_runs_payload = {}
workflow_runs = as_list(actions_runs_payload or {}, "workflow_runs")
action_run_counts = {
    "success": 0,
    "neutral": 0,
    "skipped": 0,
    "failed": 0,
    "running": 0,
    "pending": 0,
    "unknown": 0,
}
action_job_counts = {
    "success": 0,
    "neutral": 0,
    "skipped": 0,
    "failed": 0,
    "running": 0,
    "pending": 0,
    "unknown": 0,
}
sanitized_action_runs = []
sanitized_action_jobs = []
action_job_collection_successes = 0
action_job_collection_failures = 0
action_job_collection_skipped_green_runs = 0
action_job_collection_non_terminal_attempts = 0
action_job_collection_skipped_non_terminal_runs = 0
for run in workflow_runs:
    run_head_sha = str(run.get("head_sha") or "")
    if run_head_sha and not sha_prefix_matches(run_head_sha, expected_head_sha_lower):
        action_run_counts["unknown"] += 1
        continue
    run_classification = normalize_actions_status(run)
    if run_classification in action_run_counts:
        action_run_counts[run_classification] += 1
    else:
        action_run_counts["unknown"] += 1
    run_id = run.get("id")
    sanitized_action_runs.append({
        "id": run_id,
        "name": run.get("name"),
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "head_sha": run.get("head_sha"),
        "html_url": run.get("html_url"),
    })
    if run_id is None:
        action_job_collection_failures += 1
        action_job_counts["unknown"] += 1
        limitations.append({
            "code": "github_actions_jobs_unavailable",
            "source": "actions_collector",
            "capability": "actions_read",
            "severity": "blocking",
            "message": "GitHub Actions workflow run did not include an id, so jobs could not be collected",
        })
        if run_classification == "failed":
            failure = actions_failure_entry(run)
            if failure["dedupe_key"] not in actions_failure_dedupe_keys:
                actions_failure_dedupe_keys.add(failure["dedupe_key"])
                actions_failures.append(failure)
        continue
    if (
        run_classification in {"success", "neutral", "skipped"}
        and action_job_collection_successes >= TERMINAL_GREEN_JOB_EXPANSION_CAP
    ):
        action_job_collection_skipped_green_runs += 1
        continue
    if (
        run_classification in {"running", "pending"}
        and action_job_collection_non_terminal_attempts >= NON_TERMINAL_JOB_EXPANSION_CAP
    ):
        action_job_collection_skipped_non_terminal_runs += 1
        continue
    if run_classification in {"running", "pending"}:
        action_job_collection_non_terminal_attempts += 1
    jobs_payload, job_limitation = gh_api(f"repos/{repo}/actions/runs/{run_id}/jobs")
    if job_limitation:
        action_job_collection_failures += 1
        limitations.append(job_limitation)
        if run_classification == "failed":
            failure = actions_failure_entry(run)
            if failure["dedupe_key"] not in actions_failure_dedupe_keys:
                actions_failure_dedupe_keys.add(failure["dedupe_key"])
                actions_failures.append(failure)
        continue
    run_failed_jobs = []
    jobs = (jobs_payload or {}).get("jobs") if isinstance(jobs_payload, dict) else None
    if not isinstance(jobs, list):
        action_job_collection_failures += 1
        action_job_counts["unknown"] += 1
        limitations.append({
            "code": "github_actions_jobs_unavailable",
            "source": "actions_collector",
            "capability": "actions_read",
            "severity": "blocking",
            "message": "GitHub Actions jobs response did not include a jobs list",
        })
        if run_classification == "failed":
            failure = actions_failure_entry(run)
            if failure["dedupe_key"] not in actions_failure_dedupe_keys:
                actions_failure_dedupe_keys.add(failure["dedupe_key"])
                actions_failures.append(failure)
        continue
    action_job_collection_successes += 1
    for job in jobs:
        job_classification = normalize_actions_status(job)
        if job_classification in action_job_counts:
            action_job_counts[job_classification] += 1
        else:
            action_job_counts["unknown"] += 1
        sanitized_action_jobs.append({
            "id": job.get("id"),
            "run_id": job.get("run_id") or run_id,
            "name": job.get("name"),
            "status": job.get("status"),
            "conclusion": job.get("conclusion"),
            "html_url": job.get("html_url"),
        })
        if job_classification == "failed":
            run_failed_jobs.append(job)
            failure = actions_failure_entry(run, job)
            if failure["dedupe_key"] not in actions_failure_dedupe_keys:
                actions_failure_dedupe_keys.add(failure["dedupe_key"])
                actions_failures.append(failure)
    if run_classification == "failed" and not run_failed_jobs:
        failure = actions_failure_entry(run)
        if failure["dedupe_key"] not in actions_failure_dedupe_keys:
            actions_failure_dedupe_keys.add(failure["dedupe_key"])
            actions_failures.append(failure)

if actions_available and not workflow_runs:
    limitations.append({
        "code": "zero_actions_runs_non_success",
        "source": "actions_collector",
        "capability": "actions_read",
        "severity": "informational",
        "blocking": False,
        "message": "no GitHub Actions workflow runs were observed for the expected PR head SHA",
    })
    limitations.append({
        "code": "zero_checks_s03_non_success",
        "source": "ci_collector",
        "severity": "blocking",
        "message": "no GitHub Actions workflow runs were observed; S03 keeps this non-success until wait compatibility is migrated",
    })

actions_jobs_collection = {
    "successful_runs": action_job_collection_successes,
    "failed_runs": action_job_collection_failures,
}
if action_job_collection_skipped_green_runs or action_job_collection_skipped_non_terminal_runs:
    actions_jobs_collection.update({
        "mode": "bounded",
        "expanded_runs": action_job_collection_successes + action_job_collection_failures,
    })
if action_job_collection_skipped_green_runs:
    actions_jobs_collection.update({
        "skipped_green_runs": action_job_collection_skipped_green_runs,
        "cap": TERMINAL_GREEN_JOB_EXPANSION_CAP,
    })
if action_job_collection_skipped_non_terminal_runs:
    actions_jobs_collection.update({
        "skipped_non_terminal_runs": action_job_collection_skipped_non_terminal_runs,
        "non_terminal_cap": NON_TERMINAL_JOB_EXPANSION_CAP,
        "non_terminal_attempts": action_job_collection_non_terminal_attempts,
    })
actions_jobs_summary = {
    "total": len(sanitized_action_jobs),
    "counts": action_job_counts,
    "collection": actions_jobs_collection,
}
actions_summary = {
    "available": actions_available,
    "workflow_runs": {
        "total": len(sanitized_action_runs),
        "counts": action_run_counts,
    },
    "runs": sanitized_action_runs,
    "jobs": sanitized_action_jobs,
    "jobs_summary": actions_jobs_summary,
    "jobs_detail": sanitized_action_jobs,
}
actions_decisive_green = (
    actions_available
    and actions_summary["workflow_runs"]["total"] > 0
    and (
        action_job_collection_successes
        + action_job_collection_skipped_green_runs
        + action_job_collection_skipped_non_terminal_runs
        == actions_summary["workflow_runs"]["total"]
    )
    and action_job_collection_failures == 0
    and not (
        action_run_counts["failed"]
        or action_run_counts["running"]
        or action_run_counts["pending"]
        or action_run_counts["unknown"]
        or action_job_counts["failed"]
        or action_job_counts["running"]
        or action_job_counts["pending"]
        or action_job_counts["unknown"]
    )
)
actions_decisive_non_terminal = (
    actions_available
    and actions_summary["workflow_runs"]["total"] > 0
    and (
        action_job_collection_successes
        + action_job_collection_skipped_green_runs
        + action_job_collection_skipped_non_terminal_runs
        == actions_summary["workflow_runs"]["total"]
    )
    and action_job_collection_failures == 0
    and not (
        action_run_counts["failed"]
        or action_run_counts["unknown"]
        or action_job_counts["failed"]
        or action_job_counts["unknown"]
    )
    and bool(
        action_run_counts["running"]
        or action_run_counts["pending"]
        or action_job_counts["running"]
        or action_job_counts["pending"]
    )
)
actions_decisive_failed = (
    actions_available
    and actions_summary["workflow_runs"]["total"] > 0
    and (
        action_job_collection_successes + action_job_collection_skipped_green_runs
        == actions_summary["workflow_runs"]["total"]
    )
    and action_job_collection_failures == 0
    and not (action_run_counts["unknown"] or action_job_counts["unknown"])
    and bool(action_run_counts["failed"] or action_job_counts["failed"])
)
check_runs_payload = {}
statuses_payload = {}
pr_view_payload = {}
check_runs = as_list(check_runs_payload, "check_runs")
statuses = as_list(statuses_payload, "statuses")
status_check_rollup = []

check_counts = {
    "total": len(check_runs),
    "success": 0,
    "skipped": 0,
    "neutral": 0,
    "failed": 0,
    "running": 0,
    "pending": 0,
    "other": 0,
    "stale": 0,
}
status_counts = {
    "total": len(statuses),
    "aggregate_state": None,
    "success": 0,
    "failure": 0,
    "pending": 0,
    "error": 0,
    "other": 0,
}

required_check_state = {
    "available": False,
    "collection_policy": "forbidden",
    "merge_state_status": None,
    "status_check_rollup_total": len(status_check_rollup),
    "status_check_rollup_states": [],
}
for item in status_check_rollup:
    state = str(item.get("state") or item.get("status") or "").upper()
    conclusion = str(item.get("conclusion") or "").upper()
    required_check_state["status_check_rollup_states"].append({
        "name": item.get("name") or item.get("context"),
        "state": state or None,
        "conclusion": conclusion or None,
    })

failures = []
failures.extend(actions_failures)

actions_primary_unavailable = (
    any(item.get("capability") == "actions_read" and item.get("severity") == "blocking" for item in limitations)
    and not actions_available
)
head_sha_resolution_failed = any(
    item.get("code") == "pr_head_sha_resolution_failed" and item.get("severity") == "blocking" for item in limitations
)
actions_zero_runs = actions_available and actions_summary["workflow_runs"]["total"] == 0
actions_failed = bool(action_run_counts["failed"] or action_job_counts["failed"])
actions_running = bool(action_run_counts["running"] or action_job_counts["running"])
actions_pending = bool(action_run_counts["pending"] or action_job_counts["pending"])
actions_unknown = bool(action_run_counts["unknown"] or action_job_counts["unknown"])
actions_jobs_unavailable = actions_available and action_job_collection_failures > 0

if actions_primary_unavailable or head_sha_resolution_failed:
    ci_status = "unknown"
elif actions_failed:
    ci_status = "failed"
elif actions_running:
    ci_status = "running"
elif actions_pending:
    ci_status = "pending"
elif actions_unknown or actions_jobs_unavailable:
    ci_status = "unknown"
elif actions_decisive_green:
    ci_status = "passed"
elif actions_zero_runs:
    ci_status = "none"
elif limitations and any(is_blocking_limitation(item) for item in limitations):
    ci_status = "unknown"
else:
    ci_status = "unknown"

sanitized_checks = []
for check in check_runs:
    sanitized_checks.append({
        "id": check.get("id"),
        "name": check.get("name"),
        "head_sha": check.get("head_sha"),
        "status": check.get("status"),
        "conclusion": check.get("conclusion"),
        "html_url": check.get("html_url"),
        "details_url": check.get("details_url"),
        "workflow_name": check.get("workflow_name"),
        "workflow_run_id": (check.get("workflow_run") or {}).get("id")
        if isinstance(check.get("workflow_run"), dict)
        else None,
    })

sanitized_statuses = []
for status in statuses:
    sanitized_statuses.append({
        "context": status.get("context"),
        "state": status.get("state"),
        "target_url": status.get("target_url"),
        "description": status.get("description"),
    })

fingerprint_source = {
    "head_sha": expected_head_sha,
    "ci_status": ci_status,
    "source_policy": "github_actions_only",
    "actions": {
        "available": actions_summary.get("available"),
        "workflow_runs": actions_summary.get("workflow_runs"),
        "jobs_summary": actions_summary.get("jobs_summary"),
        "runs": [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "status": item.get("status"),
                "conclusion": item.get("conclusion"),
                "head_sha": item.get("head_sha"),
            }
            for item in sanitized_action_runs
        ],
        "jobs": [
            {
                "id": item.get("id"),
                "run_id": item.get("run_id"),
                "name": item.get("name"),
                "status": item.get("status"),
                "conclusion": item.get("conclusion"),
            }
            for item in sanitized_action_jobs
        ],
        "failures": [
            {
                "kind": item.get("kind"),
                "source": item.get("source"),
                "workflow_run_id": item.get("workflow_run_id"),
                "workflow_name": item.get("workflow_name"),
                "workflow_status": item.get("workflow_status"),
                "workflow_conclusion": item.get("workflow_conclusion"),
                "workflow_run_attempt": item.get("workflow_run_attempt"),
                "job_id": item.get("job_id"),
                "job_name": item.get("job_name"),
                "job_status": item.get("job_status"),
                "job_conclusion": item.get("job_conclusion"),
                "failed_steps": item.get("failed_steps"),
                "dedupe_key": item.get("dedupe_key"),
            }
            for item in actions_failures
            if item.get("source") == "actions"
        ],
    },
    "limitations": [item.get("code") for item in limitations],
}

payload = {
    "script": "fetch_pr_checks_snapshot.sh",
    "status": ci_status,
    "source_policy": "github_actions_only",
    "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "repo": repo,
    "pr": pr,
    "expected_head_sha": expected_head_sha,
    "ci": {
        "status": ci_status,
        "progress_status": ci_status,
        "source_policy": "github_actions_only",
        "check_runs": check_counts,
        "commit_statuses": status_counts,
        "actions": actions_summary,
        "checks": sanitized_checks,
        "statuses": sanitized_statuses,
        "failures": failures,
        "collector": "s03",
        "required_check_state": required_check_state,
    },
    "limitations": limitations,
    "fingerprint": hashlib.sha256(
        json.dumps(fingerprint_source, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest(),
}
print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
