#!/usr/bin/env python3
# mypy: ignore-errors
"""Validate Issue candidates from an evidence-only ChatGPT authoring pack."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
from typing import Any

STATUS_EXIT_CODES = {
    "pass": 0,
    "fail": 1,
    "blocked": 2,
    "stale": 3,
    "rejected": 4,
    "deferred": 5,
}

AUTHORITY_BOUNDARY = {
    "authority": "evidence_only",
    "adoption_status": "unreviewed",
    "bundle_generation_not_promotion": True,
}

EXPECTED_ROOT = "specdock-authoring-pack/"
ISSUE_CANDIDATE_INDEX_PATH = "candidates/issues/index.json"
OWNERSHIP_MARKER = "owned-by=validate_issue_candidates.py\n"
OWNERSHIP_MARKER_FILE = ".specdock-issue-candidates-validation"
MAX_FILE_SIZE = 1_000_000
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[a-z0-9._-]+$")

DEFAULT_FORBIDDEN_CLAIMS = (
    "spec-reviewer passed",
    "reviewer pass",
    "adoption_status: adopted",
    "adopted as canonical",
    "accepted as canonical",
    "marked as adopted",
    "approved by spec-reviewer",
    ".assurance.json updated",
    ".assurance.json modified",
    "canonical overwrite",
    "authority: canonical",
    "pull request created",
    "implementation complete",
    "qa-reviewer passed",
    "code-reviewer passed",
    "authorized_profile updated",
    "authorized profile updated",
)

PROFILE_SPECIFIC_MARKERS = (
    "selected-skeleton-fill",
    "all-profiles",
    "profiles",
)

PROFILE_SPECIFIC_KEYS = {
    "section_fills",
    "template_sha256",
    "skeleton_sha256",
    "section_inventory_sha256",
}

SECRET_PATH_MARKERS = (
    ".env",
    "secret",
    "token",
    "credential",
    "private-key",
    "private_key",
)

HOST_PATH_MARKERS = (
    "/Users/",
    "/home/",
    "/Volumes/",
    "/private/",
    ".oracle",
)

RAW_TRANSCRIPT_MARKERS = (
    "raw transcript",
    "chatgpt transcript",
    "browser transcript",
    "conversation transcript",
)

ALLOWED_PACK_SUFFIXES = {".json", ".md", ".txt"}


def validate_issue_candidates(
    review_report_path: Path,
    pack_tree: Path,
    *,
    issue_id: str,
    expected_parent_epic: str,
    expected_requirements: list[str],
    expected_acceptance: list[str],
) -> dict[str, Any]:
    generated_at = _now()
    expected_trace = {
        "issue_id": issue_id,
        "parent_epic": expected_parent_epic,
        "requirements": expected_requirements,
        "acceptance": expected_acceptance,
    }
    review = _load_review_report(review_report_path, generated_at)
    if review["status"] != "pass":
        return _base_result(
            review["status"],
            generated_at,
            expected_trace=expected_trace,
            errors=review["errors"],
            checks=review["checks"],
            review=review.get("review_snapshot"),
        )

    root = _pack_root(pack_tree)
    if not root.exists() or not root.is_dir() or root.is_symlink():
        return _base_result(
            "blocked",
            generated_at,
            expected_trace=expected_trace,
            errors=["pack tree could not be observed"],
            checks=_checks("pack-tree", "blocked"),
            review=review["review_snapshot"],
        )

    digest = _pack_tree_digest(root)
    if digest["status"] != "pass":
        return _base_result(
            digest["status"],
            generated_at,
            expected_trace=expected_trace,
            errors=digest["errors"],
            checks=digest["checks"],
            review=review["review_snapshot"],
        )
    if digest["pack_digest"] != review["review"]["pack_digest"]:
        return _base_result(
            "stale",
            generated_at,
            expected_trace=expected_trace,
            errors=["pack tree digest does not match review report"],
            checks=_checks("pack-digest", "stale"),
            review=review["review_snapshot"],
        )

    profile_path_result = _reject_profile_specific_paths(root)
    if profile_path_result is not None:
        return _base_result(
            "rejected",
            generated_at,
            expected_trace=expected_trace,
            errors=[profile_path_result],
            checks=_checks("candidate-pack-safety", "rejected"),
            review=review["review_snapshot"],
        )

    index = _load_pack_json(root / ISSUE_CANDIDATE_INDEX_PATH, "issue-candidate-index", missing_status="blocked")
    if index["status"] != "pass":
        return _base_result(
            index["status"],
            generated_at,
            expected_trace=expected_trace,
            errors=index["errors"],
            checks=index["checks"],
            review=review["review_snapshot"],
        )

    index_validation = _validate_index(index["payload"], expected_trace)
    if index_validation["status"] != "pass":
        return _base_result(
            index_validation["status"],
            generated_at,
            expected_trace=expected_trace,
            errors=index_validation["errors"],
            checks=index["checks"] + index_validation["checks"],
            review=review["review_snapshot"],
        )

    candidate_results = [
        _validate_candidate(root, raw_candidate, expected_trace) for raw_candidate in index_validation["candidate_refs"]
    ]
    comparison = _comparison_summary(candidate_results)
    status = _overall_status(candidate_results)
    errors = [error for row in candidate_results for error in row.get("errors", [])]
    warnings = [warning for row in candidate_results for warning in row.get("warnings", [])]
    warnings.extend(comparison.get("warnings", []))

    return _base_result(
        status,
        generated_at,
        expected_trace=expected_trace,
        errors=errors,
        warnings=warnings,
        checks=(
            _checks("review-report", "pass")
            + _checks("pack-digest", "pass")
            + index["checks"]
            + index_validation["checks"]
            + [check for row in candidate_results for check in row.get("checks", [])]
        ),
        review=review["review_snapshot"],
        candidates=candidate_results,
        comparison=comparison,
        adoption={
            "overall_adoption_eligible": status == "pass",
            "canonical_written": False,
            "assurance_mutated": False,
            "reviewer_pass_claimed": False,
            "next_action": "manual adoption review; rewrite canonical docs separately if accepted",
        },
    )


def write_issue_candidate_outputs(output_dir: Path, result: dict[str, Any]) -> dict[str, Any]:
    prepared = _prepare_output_dir(output_dir)
    if prepared is not None:
        return _base_result(
            "blocked",
            result.get("generated_at", _now()),
            expected_trace=result.get("trace", {}),
            errors=[prepared],
            review=result.get("inputs", {}).get("review"),
        )

    _write_text(output_dir / OWNERSHIP_MARKER_FILE, OWNERSHIP_MARKER)
    _write_json(output_dir / "issue-candidate-validation-report.json", result)
    _write_json(output_dir / "issue-candidate-comparison-summary.json", result.get("comparison", {}))
    _write_text(output_dir / "issue-candidate-comparison-summary.md", _comparison_markdown(result))
    _write_text(output_dir / "issue-candidate-validation-summary.md", _summary_markdown(result))
    return result


def cli_summary(result: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "status": result["status"],
        "output_dir": _display_path(output_dir),
    }
    adoption = result.get("adoption", {})
    if adoption:
        summary["overall_adoption_eligible"] = adoption.get("overall_adoption_eligible", False)
    comparison = result.get("comparison", {})
    if comparison:
        summary["candidate_count"] = comparison.get("candidate_count", 0)
        summary["adoption_eligible_count"] = comparison.get("adoption_eligible_count", 0)
    if result.get("errors"):
        summary["errors"] = _safe_diagnostic_value(result["errors"])
    return summary


def _validate_index(data: dict[str, Any], expected_trace: dict[str, Any]) -> dict[str, Any]:
    boundary_status, boundary_errors = _validate_boundary(data, "issue-candidate-index", missing_status="blocked")
    if boundary_status != "pass":
        return {
            "status": boundary_status,
            "errors": boundary_errors,
            "checks": _checks("issue-candidate-index-boundary", boundary_status),
        }

    errors: list[str] = []
    if data.get("schema_version") != "1":
        errors.append("issue-candidate-index.schema_version must be 1")
    trace_status, trace_errors = _validate_parent_trace(data.get("parent_trace"), expected_trace)
    if trace_status != "pass":
        return {
            "status": trace_status,
            "errors": trace_errors,
            "checks": _checks("issue-candidate-index-trace", trace_status),
        }
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        errors.append("issue-candidate-index.candidates must be a non-empty array")
        candidates = []

    refs: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, candidate in enumerate(candidates):
        label = f"issue-candidate-index.candidates[{index}]"
        if not isinstance(candidate, dict):
            errors.append(f"{label} must be an object")
            continue
        candidate_id = candidate.get("candidate_id")
        path = candidate.get("path")
        if not isinstance(candidate_id, str) or not candidate_id or not SAFE_ID.match(candidate_id):
            errors.append(f"{label}.candidate_id is invalid")
            continue
        if candidate_id in seen:
            errors.append(f"{label}.candidate_id is duplicated")
            continue
        seen.add(candidate_id)
        if not isinstance(path, str) or _safe_relative_path_error(path):
            errors.append(f"{label}.path is invalid")
            continue
        if not path.startswith("candidates/issues/") or not path.endswith("/candidate.json"):
            errors.append(f"{label}.path must point to candidates/issues/<candidate_id>/candidate.json")
            continue
        refs.append({"candidate_id": candidate_id, "path": path})

    status = "fail" if errors else "pass"
    return {
        "status": status,
        "errors": errors,
        "checks": _checks("issue-candidate-index", status),
        "candidate_refs": refs,
    }


def _validate_candidate(
    root: Path,
    candidate_ref: dict[str, str],
    expected_trace: dict[str, Any],
) -> dict[str, Any]:
    path = root / candidate_ref["path"]
    payload = _load_pack_json(path, "issue-candidate", missing_status="blocked")
    if payload["status"] != "pass":
        return _candidate_result(
            candidate_ref["candidate_id"],
            payload["status"],
            errors=payload["errors"],
            checks=payload["checks"],
        )
    data = payload["payload"]

    boundary_status, boundary_errors = _validate_boundary(data, "issue-candidate", missing_status="blocked")
    if boundary_status != "pass":
        return _candidate_result(
            candidate_ref["candidate_id"],
            boundary_status,
            errors=boundary_errors,
            checks=_checks("issue-candidate-boundary", boundary_status),
        )
    unsafe = _unsafe_candidate_metadata_error(data)
    if unsafe:
        return _candidate_result(
            candidate_ref["candidate_id"],
            "rejected",
            errors=[unsafe],
            checks=_checks("issue-candidate-safety", "rejected"),
        )
    trace_status, trace_errors = _validate_parent_trace(data.get("parent_trace"), expected_trace)
    if trace_status != "pass":
        return _candidate_result(
            candidate_ref["candidate_id"],
            trace_status,
            errors=trace_errors,
            checks=_checks("issue-candidate-trace", trace_status),
        )

    schema_errors = _candidate_schema_errors(data, candidate_ref["candidate_id"])
    if schema_errors:
        return _candidate_result(
            candidate_ref["candidate_id"],
            "fail",
            errors=schema_errors,
            checks=_checks("issue-candidate-schema", "fail"),
        )

    metadata_status, metadata_errors = _validate_boundary_metadata(data["boundary_metadata"])
    if metadata_status != "pass":
        return _candidate_result(
            candidate_ref["candidate_id"],
            metadata_status,
            errors=metadata_errors,
            checks=_checks("issue-candidate-boundary-metadata", metadata_status),
        )

    base_dir = PurePosixPath(candidate_ref["path"]).parent.as_posix()
    files_status = _validate_candidate_files(root, base_dir, data)
    if files_status["status"] != "pass":
        return _candidate_result(
            candidate_ref["candidate_id"],
            files_status["status"],
            errors=files_status["errors"],
            checks=files_status["checks"],
            candidate=data,
        )

    warnings = _candidate_warnings(data)
    return _candidate_result(
        candidate_ref["candidate_id"],
        "pass",
        warnings=warnings,
        checks=(
            _checks("issue-candidate-schema", "pass")
            + _checks("issue-candidate-boundary", "pass")
            + _checks("issue-candidate-trace", "pass")
            + _checks("issue-candidate-boundary-metadata", "pass")
            + files_status["checks"]
        ),
        candidate=data,
        profile=files_status["profile"],
    )


def _candidate_schema_errors(data: dict[str, Any], candidate_id: str) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != "1":
        errors.append("issue-candidate.schema_version must be 1")
    if data.get("candidate_id") != candidate_id:
        errors.append("issue-candidate.candidate_id does not match index")
    title = data.get("title")
    if not isinstance(title, str) or not title:
        errors.append("issue-candidate.title is required")
    for field in ("scope", "non_scope", "dependencies"):
        value = data.get(field)
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            errors.append(f"issue-candidate.{field} must be a string array")
        if field in {"scope", "non_scope"} and isinstance(value, list) and not value:
            errors.append(f"issue-candidate.{field} must not be empty")
    files = data.get("files")
    if not isinstance(files, dict):
        errors.append("issue-candidate.files must be an object")
    else:
        for field in ("requirement", "design_brief", "plan_brief", "profile"):
            value = files.get(field)
            if not isinstance(value, str) or _safe_relative_path_error(value):
                errors.append(f"issue-candidate.files.{field} is invalid")
    return errors


def _validate_boundary_metadata(value: Any) -> tuple[str, list[str]]:
    if not isinstance(value, dict):
        return "blocked", ["issue-candidate.boundary_metadata is required"]
    expected_false = (
        "canonical_written",
        "assurance_mutated",
        "review_gate_claimed",
        "selected_skeleton_fill",
        "profile_specific_template_body",
    )
    missing = [key for key in expected_false if key not in value]
    if missing:
        return "blocked", [f"issue-candidate.boundary_metadata.{key} is required" for key in missing]
    extra = sorted(set(value) - set(expected_false))
    if extra:
        return "rejected", [f"issue-candidate.boundary_metadata.{key} is not allowed" for key in extra]
    rejected = [key for key in expected_false if value.get(key) is not False]
    if rejected:
        return "rejected", [f"issue-candidate.boundary_metadata.{key} must be false" for key in rejected]
    return "pass", []


def _validate_candidate_files(root: Path, base_dir: str, data: dict[str, Any]) -> dict[str, Any]:
    files = data["files"]
    checks: list[dict[str, str]] = []
    errors: list[str] = []
    text_paths: list[str] = []
    for field in ("requirement", "design_brief", "plan_brief"):
        relative = _candidate_file_path(base_dir, files[field])
        if relative is None:
            errors.append(f"issue-candidate.files.{field} must stay under the candidate directory")
            continue
        text_paths.append(relative)
    profile_relative = _candidate_file_path(base_dir, files["profile"])
    if profile_relative is None:
        errors.append("issue-candidate.files.profile must stay under the candidate directory")
    if errors:
        return {"status": "rejected", "errors": errors, "checks": _checks("issue-candidate-files", "rejected")}

    for relative in text_paths:
        text_result = _load_pack_text(root / relative, "issue-candidate-file")
        if text_result["status"] != "pass":
            return text_result
        unsafe = _unsafe_text_error(text_result["text"])
        if unsafe:
            return {
                "status": "rejected",
                "errors": ["issue-candidate markdown contains unsafe authority or profile-specific claim"],
                "checks": _checks("issue-candidate-markdown-safety", "rejected"),
            }
        checks.extend(text_result["checks"])

    profile = _load_pack_json(root / profile_relative, "issue-candidate-profile", missing_status="blocked")
    if profile["status"] != "pass":
        return profile
    profile_status = _validate_profile(data["candidate_id"], profile["payload"])
    if profile_status["status"] != "pass":
        return profile_status
    checks.extend(profile["checks"] + profile_status["checks"])
    return {
        "status": "pass",
        "errors": [],
        "checks": checks,
        "profile": profile_status["profile"],
    }


def _candidate_file_path(base_dir: str, value: str) -> str | None:
    if _safe_relative_path_error(value):
        return None
    path = PurePosixPath(value)
    if len(path.parts) == 1:
        return f"{base_dir}/{value}"
    full = path.as_posix()
    if full.startswith(f"{base_dir}/"):
        return full
    return None


def _validate_profile(candidate_id: str, data: dict[str, Any]) -> dict[str, Any]:
    boundary_status, boundary_errors = _validate_boundary(data, "issue-candidate-profile", missing_status="blocked")
    if boundary_status != "pass":
        return {
            "status": boundary_status,
            "errors": boundary_errors,
            "checks": _checks("issue-candidate-profile-boundary", boundary_status),
        }
    unsafe = _unsafe_json_error(data, allow_null_authorized_profile=True)
    if unsafe:
        return {
            "status": "rejected",
            "errors": [unsafe],
            "checks": _checks("issue-candidate-profile-safety", "rejected"),
        }
    errors: list[str] = []
    if data.get("schema_version") != "1":
        errors.append("issue-candidate-profile.schema_version must be 1")
    if data.get("candidate_id") != candidate_id:
        errors.append("issue-candidate-profile.candidate_id does not match candidate")
    if "authorized_profile" not in data:
        return {
            "status": "blocked",
            "errors": ["issue-candidate-profile.authorized_profile is required and must be null"],
            "checks": _checks("issue-candidate-profile-authority", "blocked"),
        }
    if data.get("authorized_profile") is not None:
        return {
            "status": "rejected",
            "errors": ["issue-candidate-profile.authorized_profile must be null"],
            "checks": _checks("issue-candidate-profile-authority", "rejected"),
        }
    if data.get("profile_authority") != "local_assurance_only":
        errors.append("issue-candidate-profile.profile_authority must be local_assurance_only")
    if data.get("assurance_mutated") is not False:
        return {
            "status": "rejected",
            "errors": ["issue-candidate-profile.assurance_mutated must be false"],
            "checks": _checks("issue-candidate-profile-authority", "rejected"),
        }
    recommendation = data.get("profile_recommendation")
    if not isinstance(recommendation, dict):
        errors.append("issue-candidate-profile.profile_recommendation must be an object")
        recommendation = {}
    if recommendation.get("advisory_only") is not True or recommendation.get("ignored_for_authority") is not True:
        return {
            "status": "rejected",
            "errors": ["issue-candidate-profile.profile_recommendation must be advisory-only"],
            "checks": _checks("issue-candidate-profile-authority", "rejected"),
        }
    profile = recommendation.get("profile")
    if profile is not None and (not isinstance(profile, str) or not profile):
        errors.append("issue-candidate-profile.profile_recommendation.profile must be a string or null")
    if errors:
        return {
            "status": "fail",
            "errors": errors,
            "checks": _checks("issue-candidate-profile", "fail"),
        }
    return {
        "status": "pass",
        "errors": [],
        "checks": _checks("issue-candidate-profile", "pass"),
        "profile": {
            "profile_recommendation": _safe_diagnostic_value(profile),
            "advisory_only": True,
            "ignored_for_authority": True,
            "authorized_profile_claimed": False,
        },
    }


def _candidate_result(
    candidate_id: str,
    status: str,
    *,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
    checks: list[dict[str, str]] | None = None,
    candidate: dict[str, Any] | None = None,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate = candidate or {}
    boundary = candidate.get("boundary_metadata") if isinstance(candidate.get("boundary_metadata"), dict) else {}
    scope = candidate.get("scope") if isinstance(candidate.get("scope"), list) else []
    non_scope = candidate.get("non_scope") if isinstance(candidate.get("non_scope"), list) else []
    dependencies = candidate.get("dependencies") if isinstance(candidate.get("dependencies"), list) else []
    return {
        "candidate_id": _safe_diagnostic_value(candidate_id),
        "status": status,
        "adoption_eligible": status == "pass",
        "title": _safe_diagnostic_value(candidate.get("title")),
        "parent_trace_valid": status == "pass",
        "boundary_valid": status == "pass",
        "profile_recommendation": profile or {},
        "profile_recommendation_advisory_only": bool(profile),
        "authorized_profile_claimed": False if profile else None,
        "selected_skeleton_fill_detected": boundary.get("selected_skeleton_fill"),
        "profile_specific_template_body_detected": boundary.get("profile_specific_template_body"),
        "scope_count": len(scope),
        "non_scope_count": len(non_scope),
        "dependencies": _safe_diagnostic_value(dependencies),
        "canonical_written": False,
        "assurance_mutated": False,
        "reviewer_pass_claimed": False,
        "errors": _safe_diagnostic_value(errors or []),
        "warnings": _safe_diagnostic_value(warnings or []),
        "checks": checks or [],
        "_scope_signature": _scope_signature(scope),
    }


def _candidate_warnings(data: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if not data.get("dependencies"):
        warnings.append("issue-candidate.dependencies is empty")
    return warnings


def _comparison_summary(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    duplicate_title_groups = _duplicate_groups(candidates, "title")
    duplicate_scope_groups = _duplicate_groups(candidates, "_scope_signature")
    dependency_index: dict[str, list[str]] = defaultdict(list)
    for candidate in candidates:
        for dependency in candidate.get("dependencies", []):
            dependency_index[str(dependency)].append(str(candidate["candidate_id"]))
    warnings: list[str] = []
    if duplicate_title_groups:
        warnings.append("duplicate candidate titles detected")
    if duplicate_scope_groups:
        warnings.append("duplicate candidate scope signatures detected")
    public_candidates = [{key: value for key, value in row.items() if not key.startswith("_")} for row in candidates]
    return {
        **AUTHORITY_BOUNDARY,
        "candidate_count": len(candidates),
        "adoption_eligible_count": sum(1 for row in candidates if row.get("adoption_eligible")),
        "duplicate_title_groups": duplicate_title_groups,
        "duplicate_scope_groups": duplicate_scope_groups,
        "dependency_index": {key: sorted(value) for key, value in sorted(dependency_index.items())},
        "warnings": warnings,
        "candidates": public_candidates,
        "canonical_written": False,
        "assurance_mutated": False,
        "reviewer_pass_claimed": False,
    }


def _duplicate_groups(candidates: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for candidate in candidates:
        value = candidate.get(field)
        if isinstance(value, str) and value:
            groups[value].append(str(candidate["candidate_id"]))
    return [
        {"value": _safe_diagnostic_value(value), "candidate_ids": ids}
        for value, ids in sorted(groups.items())
        if len(ids) > 1
    ]


def _scope_signature(scope: Any) -> str | None:
    if not isinstance(scope, list) or not all(isinstance(item, str) for item in scope):
        return None
    return hashlib.sha256(json.dumps(sorted(scope), ensure_ascii=False).encode("utf-8")).hexdigest()


def _overall_status(candidates: list[dict[str, Any]]) -> str:
    if not candidates:
        return "fail"
    precedence = ("rejected", "stale", "blocked", "fail", "deferred")
    statuses = {str(candidate.get("status")) for candidate in candidates}
    for status in precedence:
        if status in statuses:
            return status
    return "pass" if statuses == {"pass"} else "fail"


def _load_review_report(review_report_path: Path, generated_at: str) -> dict[str, Any]:
    if not review_report_path.exists():
        return {
            "status": "blocked",
            "errors": ["review report missing"],
            "checks": _checks("review-report", "blocked"),
        }
    if not review_report_path.is_file() or review_report_path.is_symlink():
        return {
            "status": "fail",
            "errors": ["review report must be a file"],
            "checks": _checks("review-report", "fail"),
        }
    try:
        data = json.loads(review_report_path.read_text(encoding="utf-8"))
    except OSError:
        return {
            "status": "blocked",
            "errors": ["review report could not be read"],
            "checks": _checks("review-report", "blocked"),
        }
    except json.JSONDecodeError:
        return {
            "status": "fail",
            "errors": ["review report must be valid JSON"],
            "checks": _checks("review-report", "fail"),
        }
    if not isinstance(data, dict):
        return {
            "status": "fail",
            "errors": ["review report must be a JSON object"],
            "checks": _checks("review-report", "fail"),
        }

    errors: list[str] = []
    for key, expected in AUTHORITY_BOUNDARY.items():
        if data.get(key) != expected:
            errors.append(f"review boundary mismatch: {key}")
    status = data.get("status")
    if status not in STATUS_EXIT_CODES:
        errors.append("review report status is invalid")
    pack_digest = data.get("pack_digest")
    if status == "pass" and not _valid_pack_digest(pack_digest):
        errors.append("review report pack_digest is invalid")
    if errors:
        return {
            "status": "fail",
            "errors": errors,
            "checks": _checks("review-report", "fail"),
            "review_snapshot": _review_snapshot(data),
        }
    if status != "pass":
        return {
            "status": status,
            "errors": [f"review report status is not pass: {status}"],
            "checks": _checks("review-report", str(status)),
            "review_snapshot": _review_snapshot(data),
        }
    return {
        "status": "pass",
        "errors": [],
        "checks": _checks("review-report", "pass"),
        "review": data,
        "review_snapshot": _review_snapshot(data),
        "generated_at": generated_at,
    }


def _load_pack_json(path: Path, label: str, *, missing_status: str = "fail") -> dict[str, Any]:
    if not path.exists():
        return {
            "status": missing_status,
            "errors": [f"{label} missing"],
            "checks": _checks(label, missing_status),
        }
    if not path.is_file() or path.is_symlink():
        return {
            "status": "fail",
            "errors": [f"{label} must be a file"],
            "checks": _checks(label, "fail"),
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return {
            "status": "blocked",
            "errors": [f"{label} could not be read"],
            "checks": _checks(label, "blocked"),
        }
    except json.JSONDecodeError:
        return {
            "status": "fail",
            "errors": [f"{label} must be valid JSON"],
            "checks": _checks(label, "fail"),
        }
    if not isinstance(data, dict):
        return {
            "status": "fail",
            "errors": [f"{label} must be a JSON object"],
            "checks": _checks(label, "fail"),
        }
    return {
        "status": "pass",
        "errors": [],
        "checks": _checks(label, "pass"),
        "payload": data,
    }


def _load_pack_text(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "status": "blocked",
            "errors": [f"{label} missing"],
            "checks": _checks(label, "blocked"),
        }
    if not path.is_file() or path.is_symlink():
        return {
            "status": "fail",
            "errors": [f"{label} must be a file"],
            "checks": _checks(label, "fail"),
        }
    try:
        data = path.read_bytes()
        if len(data) > MAX_FILE_SIZE or b"\x00" in data:
            return {
                "status": "rejected",
                "errors": [f"{label} unsafe payload rejected"],
                "checks": _checks(label, "rejected"),
            }
        return {
            "status": "pass",
            "errors": [],
            "checks": _checks(label, "pass"),
            "text": data.decode("utf-8"),
        }
    except UnicodeDecodeError:
        return {
            "status": "rejected",
            "errors": [f"{label} binary payload rejected"],
            "checks": _checks(label, "rejected"),
        }
    except OSError:
        return {
            "status": "blocked",
            "errors": [f"{label} could not be read"],
            "checks": _checks(label, "blocked"),
        }


def _validate_boundary(data: dict[str, Any], label: str, *, missing_status: str) -> tuple[str, list[str]]:
    missing = [key for key in AUTHORITY_BOUNDARY if key not in data]
    if missing:
        return missing_status, [f"{label}.{key} is required" for key in missing]
    wrong = [key for key, expected in AUTHORITY_BOUNDARY.items() if data.get(key) != expected]
    if wrong:
        return "rejected", [f"{label}.{key} boundary mismatch" for key in wrong]
    return "pass", []


def _validate_parent_trace(value: Any, expected_trace: dict[str, Any]) -> tuple[str, list[str]]:
    if not isinstance(value, dict):
        return "blocked", ["parent_trace is required"]
    epic_id = value.get("epic_id") or value.get("parent_epic")
    if epic_id != expected_trace.get("parent_epic"):
        return "stale", ["parent_trace.epic_id does not match expected parent epic"]
    requirements = value.get("requirements")
    acceptance = value.get("acceptance")
    if not isinstance(requirements, list) or not all(isinstance(item, str) for item in requirements):
        return "blocked", ["parent_trace.requirements is required"]
    if not isinstance(acceptance, list) or not all(isinstance(item, str) for item in acceptance):
        return "blocked", ["parent_trace.acceptance is required"]
    missing_requirements = sorted(set(expected_trace.get("requirements", [])) - set(requirements))
    missing_acceptance = sorted(set(expected_trace.get("acceptance", [])) - set(acceptance))
    if missing_requirements:
        return "stale", ["parent_trace.requirements does not include expected requirements"]
    if missing_acceptance:
        return "stale", ["parent_trace.acceptance does not include expected acceptance"]
    return "pass", []


def _reject_profile_specific_paths(root: Path) -> str | None:
    try:
        for path in sorted(root.rglob("*")):
            if path.is_dir():
                continue
            relative = path.relative_to(root).as_posix()
            parts = tuple(part.lower() for part in PurePosixPath(relative).parts)
            if any(part in PROFILE_SPECIFIC_MARKERS for part in parts):
                return "candidate pack contains profile-specific or selected-skeleton output path"
    except OSError:
        return "candidate pack could not be read"
    return None


def _unsafe_json_error(value: Any, *, allow_null_authorized_profile: bool) -> str | None:
    if _contains_profile_specific_key(value):
        return "candidate metadata contains selected-skeleton or profile-specific template keys"
    if _authorized_profile_claimed(value, allow_null_authorized_profile=allow_null_authorized_profile):
        return "candidate metadata must not claim authorized_profile"
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if _unsafe_text_error(text):
        return "candidate metadata contains unsafe authority claim"
    return None


def _unsafe_candidate_metadata_error(value: dict[str, Any]) -> str | None:
    return _unsafe_json_error(value, allow_null_authorized_profile=False)


def _contains_profile_specific_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in PROFILE_SPECIFIC_KEYS:
                return True
            if _contains_profile_specific_key(item):
                return True
    if isinstance(value, list):
        return any(_contains_profile_specific_key(item) for item in value)
    return False


def _authorized_profile_claimed(value: Any, *, allow_null_authorized_profile: bool) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "authorized_profile" and not (allow_null_authorized_profile and item is None):
                return True
            if _authorized_profile_claimed(item, allow_null_authorized_profile=allow_null_authorized_profile):
                return True
    if isinstance(value, list):
        return any(
            _authorized_profile_claimed(item, allow_null_authorized_profile=allow_null_authorized_profile)
            for item in value
        )
    return False


def _base_result(
    status: str,
    generated_at: str,
    *,
    expected_trace: dict[str, Any],
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
    checks: list[dict[str, str]] | None = None,
    review: dict[str, Any] | None = None,
    candidates: list[dict[str, Any]] | None = None,
    comparison: dict[str, Any] | None = None,
    adoption: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        **AUTHORITY_BOUNDARY,
        "status": status,
        "generated_at": generated_at,
        "trace": expected_trace,
        "inputs": {
            "review": _safe_diagnostic_value(review or {}),
        },
        "candidates": [
            {key: value for key, value in row.items() if not key.startswith("_")} for row in (candidates or [])
        ],
        "comparison": comparison
        or {
            **AUTHORITY_BOUNDARY,
            "candidate_count": 0,
            "adoption_eligible_count": 0,
            "duplicate_title_groups": [],
            "duplicate_scope_groups": [],
            "dependency_index": {},
            "warnings": [],
            "candidates": [],
            "canonical_written": False,
            "assurance_mutated": False,
            "reviewer_pass_claimed": False,
        },
        "adoption": adoption
        or {
            "overall_adoption_eligible": False,
            "canonical_written": False,
            "assurance_mutated": False,
            "reviewer_pass_claimed": False,
            "next_action": "manual adoption review; do not treat as reviewer pass",
        },
        "checks": checks or [],
        "errors": _safe_diagnostic_value(errors or []),
        "warnings": _safe_diagnostic_value(warnings or []),
        "status_taxonomy": _status_taxonomy(),
    }


def _review_snapshot(review: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": _safe_diagnostic_value(review.get("status")),
        "input_kind": _safe_diagnostic_value(review.get("input_kind")),
        "trace": _safe_diagnostic_value(review.get("trace", {})),
        "pack_digest": _safe_diagnostic_value(review.get("pack_digest", {})),
        "source_count": len(review.get("sources", [])) if isinstance(review.get("sources"), list) else 0,
    }


def _pack_root(pack_tree: Path) -> Path:
    if pack_tree.name == EXPECTED_ROOT.rstrip("/"):
        return pack_tree
    child = pack_tree / EXPECTED_ROOT.rstrip("/")
    if child.is_dir() and not child.is_symlink():
        return child
    return pack_tree


def _pack_tree_digest(root: Path) -> dict[str, Any]:
    files: dict[str, str] = {}
    errors: list[str] = []
    try:
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                errors.append("unsafe file type rejected")
                continue
            if path.is_dir():
                continue
            mode = path.stat(follow_symlinks=False).st_mode
            if not stat.S_ISREG(mode):
                errors.append("unsafe file type rejected")
                continue
            if mode & 0o111:
                errors.append("executable tree entry rejected")
                continue
            if _safe_relative_path_error(relative):
                errors.append("unsafe pack path rejected")
                continue
            suffix = PurePosixPath(relative).suffix.lower()
            if suffix and suffix not in ALLOWED_PACK_SUFFIXES:
                errors.append("unsupported file type rejected")
                continue
            data = path.read_bytes()
            if len(data) > MAX_FILE_SIZE:
                errors.append("file size exceeds limit")
                continue
            if b"\x00" in data:
                errors.append("binary payload rejected")
                continue
            try:
                files[f"{EXPECTED_ROOT}{relative}"] = data.decode("utf-8")
            except UnicodeDecodeError:
                errors.append("binary payload rejected")
    except OSError:
        return {
            "status": "blocked",
            "errors": ["pack tree could not be read"],
            "checks": _checks("pack-digest", "blocked"),
        }
    if errors:
        return {
            "status": "rejected",
            "errors": sorted(set(errors)),
            "checks": _checks("pack-digest", "rejected"),
        }
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(files[path].encode("utf-8"))
        digest.update(b"\0")
    return {
        "status": "pass",
        "errors": [],
        "checks": _checks("pack-digest", "pass"),
        "pack_digest": {
            "algorithm": "sha256",
            "content_sha256": digest.hexdigest(),
            "file_count": len(files),
        },
    }


def _valid_pack_digest(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("algorithm") == "sha256"
        and isinstance(value.get("content_sha256"), str)
        and HEX64.match(value["content_sha256"]) is not None
        and isinstance(value.get("file_count"), int)
        and value["file_count"] > 0
    )


def _safe_relative_path_error(path_value: str) -> str | None:
    if not isinstance(path_value, str) or not path_value:
        return "path must be a non-empty string"
    if "\x00" in path_value or _has_control_char(path_value):
        return "control characters are not allowed"
    if "\\" in path_value or re.match(r"^[A-Za-z]:", path_value) or path_value.startswith("/"):
        return "absolute or host-local paths are not allowed"
    if any(marker in path_value for marker in HOST_PATH_MARKERS):
        return "host-local paths are not allowed"
    posix = PurePosixPath(path_value)
    if any(part in {"", ".."} for part in posix.parts):
        return "parent traversal is not allowed"
    lowered_parts = tuple(part.lower() for part in posix.parts)
    if any(part.startswith(".") for part in posix.parts):
        return "hidden paths are not allowed"
    if any(marker in part for marker in SECRET_PATH_MARKERS for part in lowered_parts):
        return "secret-looking paths are not allowed"
    return None


def _unsafe_text_error(value: str) -> str | None:
    normalized = _normalize_claim_text(value)
    if any(claim in normalized for claim in _forbidden_claims()):
        return "unsafe authority claim rejected"
    lowered = value.lower()
    if any(key in lowered for key in PROFILE_SPECIFIC_KEYS):
        return "profile-specific template claim rejected"
    if (
        any(marker in value for marker in HOST_PATH_MARKERS)
        or "begin private key" in lowered
        or "openssh private key" in lowered
        or "private key" in lowered
        or "secret" in lowered
        or "token" in lowered
        or "credential" in lowered
        or any(marker in lowered for marker in RAW_TRANSCRIPT_MARKERS)
    ):
        return "unsafe text rejected"
    return None


def _forbidden_claims() -> tuple[str, ...]:
    return tuple(dict.fromkeys(_normalize_claim_text(claim) for claim in DEFAULT_FORBIDDEN_CLAIMS))


def _summary_markdown(result: dict[str, Any]) -> str:
    errors = "\n".join(f"- {error}" for error in result.get("errors", [])) or "- none"
    warnings = "\n".join(f"- {warning}" for warning in result.get("warnings", [])) or "- none"
    adoption = result.get("adoption", {})
    comparison = result.get("comparison", {})
    return f"""# Issue candidate validation summary

Status: `{result["status"]}`

Authority:
- authority: evidence_only
- adoption_status: unreviewed
- bundle_generation_not_promotion: true

Comparison:
- candidate_count: `{comparison.get("candidate_count", 0)}`
- adoption_eligible_count: `{comparison.get("adoption_eligible_count", 0)}`

Adoption:
- overall_adoption_eligible: `{str(adoption.get("overall_adoption_eligible", False)).lower()}`
- canonical_written: `{str(adoption.get("canonical_written", False)).lower()}`
- assurance_mutated: `{str(adoption.get("assurance_mutated", False)).lower()}`
- reviewer_pass_claimed: `{str(adoption.get("reviewer_pass_claimed", False)).lower()}`

Errors:
{errors}

Warnings:
{warnings}
"""


def _comparison_markdown(result: dict[str, Any]) -> str:
    comparison = result.get("comparison", {})
    lines = ["# Issue candidate comparison summary", ""]
    lines.append("Authority:")
    lines.append("- authority: evidence_only")
    lines.append("- adoption_status: unreviewed")
    lines.append("- bundle_generation_not_promotion: true")
    lines.append("")
    lines.append(f"- candidate_count: `{comparison.get('candidate_count', 0)}`")
    lines.append(f"- adoption_eligible_count: `{comparison.get('adoption_eligible_count', 0)}`")
    lines.append("- canonical_written: `false`")
    lines.append("- assurance_mutated: `false`")
    lines.append("")
    lines.append("| candidate | status | title | eligible | dependencies | scope | non-scope |")
    lines.append("|---|---|---|---|---|---|---|")
    for row in comparison.get("candidates", []):
        dependencies = ", ".join(f"`{item}`" for item in row.get("dependencies", [])) or "-"
        lines.append(
            f"| `{row.get('candidate_id')}` | `{row.get('status')}` | "
            f"{row.get('title') or '-'} | `{str(row.get('adoption_eligible', False)).lower()}` | "
            f"{dependencies} | `{row.get('scope_count', 0)}` | `{row.get('non_scope_count', 0)}` |"
        )
    lines.append("")
    return "\n".join(lines)


def _status_taxonomy() -> dict[str, str]:
    return {
        "pass": "Issue candidate validation passed; adoption remains unreviewed.",
        "fail": "Input schema or required candidate data is invalid.",
        "blocked": "Required local observation or candidate authority evidence is unavailable.",
        "stale": "Review digest or expected parent trace no longer matches.",
        "rejected": "A safety boundary, unauthorized authority claim, selected skeleton fill, or profile-specific output was detected.",
        "deferred": "Recognized later-stage responsibility; never treated as pass.",
        "unreviewed": "Artifact adoption state, not an execution status.",
    }


def _checks(name: str, status: str) -> list[dict[str, str]]:
    return [{"name": name, "status": status}]


def _prepare_output_dir(output_dir: Path) -> str | None:
    unsafe_output = _output_path_error(output_dir)
    if unsafe_output is not None:
        return unsafe_output
    try:
        if output_dir.exists() and (output_dir.is_symlink() or not output_dir.is_dir()):
            return "output_dir must be a directory"
        output_dir.mkdir(parents=True, exist_ok=True)
        marker = output_dir / OWNERSHIP_MARKER_FILE
        if marker.is_file() and marker.read_text(encoding="utf-8") == OWNERSHIP_MARKER:
            for path in output_dir.iterdir():
                if path.is_file() or path.is_symlink():
                    path.unlink()
                elif path.is_dir():
                    shutil.rmtree(path)
            return None
        if any(output_dir.iterdir()):
            return "output_dir contains non-validation files; choose an empty or validation-owned directory"
    except OSError:
        return "output_dir could not be prepared"
    return None


def _output_path_error(output_dir: Path) -> str | None:
    for part in output_dir.parts:
        lowered = part.lower()
        if any(marker in lowered for marker in SECRET_PATH_MARKERS):
            return "output_dir path is unsafe"
        if any(marker in lowered for marker in RAW_TRANSCRIPT_MARKERS):
            return "output_dir path is unsafe"
        if "begin private key" in lowered or "openssh private key" in lowered:
            return "output_dir path is unsafe"
        if _has_control_char(part):
            return "output_dir path is unsafe"
    return None


def _safe_diagnostic_value(value: Any) -> Any:
    if isinstance(value, str):
        return _safe_diagnostic_string(value)
    if isinstance(value, list):
        return [_safe_diagnostic_value(item) for item in value]
    if isinstance(value, dict):
        return {_safe_diagnostic_string(str(key)): _safe_diagnostic_value(item) for key, item in value.items()}
    return value


def _safe_diagnostic_string(value: str) -> str:
    lowered = value.lower()
    if (
        _has_control_char(value)
        or value.startswith("/")
        or re.match(r"^[A-Za-z]:", value)
        or _looks_like_unsafe_path(value)
        or any(marker in value for marker in HOST_PATH_MARKERS)
        or "\\" in value
        or "begin private key" in lowered
        or "openssh private key" in lowered
        or "private key" in lowered
        or "secret" in lowered
        or "token" in lowered
        or "credential" in lowered
        or any(marker in lowered for marker in RAW_TRANSCRIPT_MARKERS)
    ):
        return "<redacted>"
    return value


def _looks_like_unsafe_path(value: str) -> bool:
    parts = PurePosixPath(value).parts
    return any(part == ".." or part.startswith(".") for part in parts)


def _display_path(path: Path) -> str:
    return _safe_diagnostic_string(path.name or ".")


def _normalize_claim_text(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def _has_control_char(value: str) -> bool:
    return any(ord(character) < 32 for character in value)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
