#!/usr/bin/env python3
# mypy: ignore-errors
"""Validate selected-skeleton section fills from an evidence-only ChatGPT pack."""

from __future__ import annotations

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
CANDIDATE_FILL_PATH = "selected-skeleton-fill/section-fills.json"
OWNERSHIP_MARKER = "owned-by=validate_selected_skeleton_fill.py\n"
OWNERSHIP_MARKER_FILE = ".specdock-selected-skeleton-fill-validation"
MAX_FILE_SIZE = 1_000_000
HEX64 = re.compile(r"^[0-9a-f]{64}$")

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


def validate_selected_skeleton_fill(
    review_report_path: Path,
    pack_tree: Path,
    assurance_path: Path,
    selected_skeleton_path: Path,
) -> dict[str, Any]:
    generated_at = _now()
    review = _load_review_report(review_report_path, generated_at)
    if review["status"] != "pass":
        return _base_result(
            review["status"],
            generated_at,
            errors=review["errors"],
            checks=review["checks"],
            review=review.get("review_snapshot"),
        )

    root = _pack_root(pack_tree)
    if not root.exists() or not root.is_dir() or root.is_symlink():
        return _base_result(
            "blocked",
            generated_at,
            errors=["pack tree could not be observed"],
            checks=_checks("pack-tree", "blocked"),
            review=review["review_snapshot"],
        )

    digest = _pack_tree_digest(root)
    if digest["status"] != "pass":
        return _base_result(
            digest["status"],
            generated_at,
            errors=digest["errors"],
            checks=digest["checks"],
            review=review["review_snapshot"],
        )
    if digest["pack_digest"] != review["review"]["pack_digest"]:
        return _base_result(
            "stale",
            generated_at,
            errors=["pack tree digest does not match review report"],
            checks=_checks("pack-digest", "stale"),
            review=review["review_snapshot"],
        )

    assurance = _load_assurance_snapshot(assurance_path)
    if assurance["status"] != "pass":
        return _base_result(
            assurance["status"],
            generated_at,
            errors=assurance["errors"],
            checks=assurance["checks"],
            review=review["review_snapshot"],
        )

    skeleton = _load_selected_skeleton(selected_skeleton_path)
    if skeleton["status"] != "pass":
        return _base_result(
            skeleton["status"],
            generated_at,
            errors=skeleton["errors"],
            checks=skeleton["checks"],
            review=review["review_snapshot"],
            assurance_snapshot=assurance.get("snapshot"),
        )

    candidate = _load_candidate_fill_manifest(root / CANDIDATE_FILL_PATH)
    if candidate["status"] != "pass":
        return _base_result(
            candidate["status"],
            generated_at,
            errors=candidate["errors"],
            checks=candidate["checks"],
            review=review["review_snapshot"],
            assurance_snapshot=assurance["snapshot"],
            selected_skeleton=skeleton["snapshot"],
        )

    validation = _validate_candidate(assurance["snapshot"], skeleton["manifest"], candidate["payload"])
    return _base_result(
        validation["status"],
        generated_at,
        errors=validation["errors"],
        warnings=validation["warnings"],
        checks=(
            _checks("review-report", "pass")
            + _checks("pack-digest", "pass")
            + assurance["checks"]
            + skeleton["checks"]
            + candidate["checks"]
            + validation["checks"]
        ),
        review=review["review_snapshot"],
        assurance_snapshot=assurance["snapshot"],
        selected_skeleton=skeleton["snapshot"],
        candidate=validation["candidate"],
        profile_validation=validation["profile_validation"],
        skeleton_validation=validation["skeleton_validation"],
        section_inventory_validation=validation["section_inventory_validation"],
        section_results=validation["section_results"],
        adoption=validation["adoption"],
    )


def write_validation_outputs(output_dir: Path, result: dict[str, Any]) -> dict[str, Any]:
    prepared = _prepare_output_dir(output_dir)
    if prepared is not None:
        return _base_result(
            "blocked",
            result.get("generated_at", _now()),
            errors=[prepared],
            review=result.get("review"),
        )

    _write_text(output_dir / OWNERSHIP_MARKER_FILE, OWNERSHIP_MARKER)
    _write_json(output_dir / "selected-skeleton-fill-validation-report.json", result)
    _write_text(output_dir / "selected-skeleton-fill-validation-summary.md", _summary_markdown(result))
    dry_run = _section_fill_dry_run(result)
    _write_json(output_dir / "selected-skeleton-fill-dry-run.json", dry_run)
    _write_text(output_dir / "selected-skeleton-fill-dry-run.md", _dry_run_markdown(dry_run))
    return result


def cli_summary(result: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "status": result["status"],
        "output_dir": _display_path(output_dir),
    }
    if result.get("adoption"):
        summary["overall_adoption_eligible"] = result["adoption"].get("overall_adoption_eligible", False)
    if result.get("errors"):
        summary["errors"] = _safe_diagnostic_value(result["errors"])
    return summary


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


def _load_assurance_snapshot(path: Path) -> dict[str, Any]:
    payload = _load_json_file(path, "assurance", missing_status="blocked")
    if payload["status"] != "pass":
        return payload
    data = payload["payload"]
    profile = _authorized_profile(data)
    if not profile:
        return {
            "status": "fail",
            "errors": ["assurance authorized_profile is missing"],
            "checks": _checks("assurance", "fail"),
        }
    snapshot = {
        "path": _safe_diagnostic_string(path.name),
        "sha256": _sha256_bytes(path.read_bytes()),
        "authorized_profile": profile,
        "status": data.get("status"),
    }
    return {
        "status": "pass",
        "errors": [],
        "checks": _checks("assurance", "pass"),
        "snapshot": snapshot,
    }


def _authorized_profile(data: dict[str, Any]) -> str | None:
    profile = data.get("authorized_profile")
    if isinstance(profile, str) and profile:
        return profile
    classification = data.get("classification")
    if isinstance(classification, dict):
        profile = classification.get("authorized_profile")
        if isinstance(profile, str) and profile:
            return profile
    obligations = data.get("obligations")
    if isinstance(obligations, dict):
        profile = obligations.get("profile_preset")
        if isinstance(profile, str) and profile:
            return profile
    return None


def _load_selected_skeleton(path: Path) -> dict[str, Any]:
    payload = _load_json_file(path, "selected-skeleton", missing_status="blocked")
    if payload["status"] != "pass":
        return payload
    data = payload["payload"]
    errors: list[str] = []
    if data.get("authority") not in {"local_assurance", "local-assurance"}:
        errors.append("selected-skeleton.authority must be local_assurance")
    for field in ("issue_id", "authorized_profile", "template_sha256", "skeleton_sha256", "section_inventory_sha256"):
        value = data.get(field)
        if not isinstance(value, str) or not value:
            errors.append(f"selected-skeleton.{field} is required")
    for field in ("template_sha256", "skeleton_sha256", "section_inventory_sha256"):
        value = data.get(field)
        if isinstance(value, str) and not HEX64.match(value):
            errors.append(f"selected-skeleton.{field} must be sha256 hex")
    inventory = data.get("section_inventory")
    if not isinstance(inventory, list) or not inventory:
        errors.append("selected-skeleton.section_inventory must be a non-empty array")
        inventory = []

    section_ids: list[str] = []
    required_ids: list[str] = []
    allowed_ids: list[str] = []
    for index, section in enumerate(inventory):
        if not isinstance(section, dict):
            errors.append(f"selected-skeleton.section_inventory[{index}] must be an object")
            continue
        section_id = section.get("section_id")
        if not isinstance(section_id, str) or not section_id:
            errors.append(f"selected-skeleton.section_inventory[{index}].section_id is required")
            continue
        if _safe_section_id_error(section_id):
            errors.append(f"selected-skeleton.section_inventory[{index}].section_id is invalid")
            continue
        section_ids.append(section_id)
        if section.get("required") is True:
            required_ids.append(section_id)
        if section.get("fillable", True) is True:
            allowed_ids.append(section_id)
    if len(section_ids) != len(set(section_ids)):
        errors.append("selected-skeleton.section_inventory contains duplicate section_id")

    allowed_ids = _ids_from_optional_list(data.get("allowed_section_ids"), allowed_ids, "allowed_section_ids", errors)
    required_ids = _ids_from_optional_list(
        data.get("required_section_ids"), required_ids, "required_section_ids", errors
    )
    if not set(allowed_ids).issubset(set(section_ids)):
        errors.append("selected-skeleton.allowed_section_ids must be a subset of section_inventory")
    if not set(required_ids).issubset(set(allowed_ids)):
        errors.append("selected-skeleton.required_section_ids must be a subset of allowed_section_ids")

    trace = _optional_parent_trace(data, data.get("issue_id"), errors)

    if errors:
        return {
            "status": "fail",
            "errors": errors,
            "checks": _checks("selected-skeleton", "fail"),
        }
    snapshot = {
        "issue_id": data["issue_id"],
        "authorized_profile": data["authorized_profile"],
        "template_sha256": data["template_sha256"],
        "skeleton_sha256": data["skeleton_sha256"],
        "section_inventory_sha256": data["section_inventory_sha256"],
        "section_count": len(section_ids),
        "allowed_section_ids": allowed_ids,
        "required_section_ids": required_ids,
        "trace": trace,
    }
    manifest = {
        **data,
        "_allowed_section_ids": allowed_ids,
        "_required_section_ids": required_ids,
    }
    return {
        "status": "pass",
        "errors": [],
        "checks": _checks("selected-skeleton", "pass"),
        "snapshot": snapshot,
        "manifest": manifest,
    }


def _ids_from_optional_list(value: Any, default: list[str], label: str, errors: list[str]) -> list[str]:
    if value is None:
        return default
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        errors.append(f"selected-skeleton.{label} must be a string array")
        return default
    invalid = [item for item in value if _safe_section_id_error(item)]
    if invalid:
        errors.append(f"selected-skeleton.{label} contains invalid section_id")
    if len(value) != len(set(value)):
        errors.append(f"selected-skeleton.{label} contains duplicate section_id")
    return list(value)


def _optional_parent_trace(data: dict[str, Any], issue_id: Any, errors: list[str]) -> dict[str, Any]:
    default_trace = _default_trace()
    if isinstance(issue_id, str) and issue_id:
        default_trace["issue_id"] = issue_id
    value = data.get("parent_trace")
    if value is None:
        value = data.get("trace")
    if value is None:
        return default_trace
    if not isinstance(value, dict):
        errors.append("selected-skeleton.parent_trace must be an object when present")
        return default_trace

    parent_epic = value.get("parent_epic", value.get("epic_id", default_trace["parent_epic"]))
    requirements = value.get("requirements", default_trace["requirements"])
    acceptance = value.get("acceptance", default_trace["acceptance"])
    trace_issue_id = value.get("issue_id", default_trace["issue_id"])
    if not isinstance(trace_issue_id, str) or not trace_issue_id:
        errors.append("selected-skeleton.parent_trace.issue_id must be a non-empty string when present")
        trace_issue_id = default_trace["issue_id"]
    elif isinstance(issue_id, str) and issue_id and trace_issue_id != issue_id:
        errors.append("selected-skeleton.parent_trace.issue_id must match selected-skeleton.issue_id")
    if not isinstance(parent_epic, str) or not parent_epic:
        errors.append("selected-skeleton.parent_trace.parent_epic must be a non-empty string when present")
        parent_epic = default_trace["parent_epic"]
    requirements = _trace_string_array(requirements, "requirements", default_trace["requirements"], errors)
    acceptance = _trace_string_array(acceptance, "acceptance", default_trace["acceptance"], errors)
    trace_text = json.dumps(
        {
            "issue_id": trace_issue_id,
            "parent_epic": parent_epic,
            "requirements": requirements,
            "acceptance": acceptance,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    if _unsafe_text_error(trace_text):
        errors.append("selected-skeleton.parent_trace contains unsafe text")
        return default_trace
    return {
        "issue_id": trace_issue_id,
        "parent_epic": parent_epic,
        "requirements": requirements,
        "acceptance": acceptance,
    }


def _trace_string_array(value: Any, label: str, default: list[str], errors: list[str]) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        errors.append(f"selected-skeleton.parent_trace.{label} must be a string array when present")
        return default
    return list(value)


def _load_candidate_fill_manifest(path: Path) -> dict[str, Any]:
    payload = _load_json_file(path, "candidate-fill", missing_status="fail")
    if payload["status"] != "pass":
        return payload
    data = payload["payload"]
    unsafe = _unsafe_metadata_error(data)
    if unsafe:
        return {
            "status": "rejected",
            "errors": [unsafe],
            "checks": _checks("candidate-fill-safety", "rejected"),
        }
    errors: list[str] = []
    for key, expected in AUTHORITY_BOUNDARY.items():
        if data.get(key) != expected:
            errors.append(f"candidate-fill boundary mismatch: {key}")
    if data.get("schema_version") != "1":
        errors.append("candidate-fill.schema_version must be 1")
    if not isinstance(data.get("issue_id"), str) or not data["issue_id"]:
        errors.append("candidate-fill.issue_id is required")
    target = data.get("target")
    if not isinstance(target, dict):
        errors.append("candidate-fill.target must be an object")
        target = {}
    else:
        for field in ("profile", "template_sha256", "skeleton_sha256", "section_inventory_sha256"):
            value = target.get(field)
            if not isinstance(value, str) or not value:
                errors.append(f"candidate-fill.target.{field} is required")
        for field in ("template_sha256", "skeleton_sha256", "section_inventory_sha256"):
            value = target.get(field)
            if isinstance(value, str) and not HEX64.match(value):
                errors.append(f"candidate-fill.target.{field} must be sha256 hex")
    fills = data.get("section_fills")
    if not isinstance(fills, list):
        errors.append("candidate-fill.section_fills must be an array")
    if errors:
        return {
            "status": "fail",
            "errors": errors,
            "checks": _checks("candidate-fill", "fail"),
        }
    return {
        "status": "pass",
        "errors": [],
        "checks": _checks("candidate-fill", "pass"),
        "payload": data,
    }


def _validate_candidate(
    assurance: dict[str, Any],
    skeleton: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    warnings: list[str] = []
    errors: list[str] = []
    checks: list[dict[str, str]] = []
    target = candidate["target"]
    local_profile = assurance["authorized_profile"]
    skeleton_profile = skeleton["authorized_profile"]
    target_profile = target["profile"]
    profile_suggestion = candidate.get("profile_suggestion")
    profile_suggestion_report = _profile_suggestion_snapshot(profile_suggestion, local_profile, warnings)

    if skeleton_profile != local_profile:
        return _candidate_result(
            "stale",
            errors=["selected skeleton authorized_profile does not match assurance authorized_profile"],
            warnings=warnings,
            checks=_checks("profile-resolution", "stale"),
            assurance=assurance,
            skeleton=skeleton,
            candidate=candidate,
            profile_suggestion=profile_suggestion_report,
        )
    if candidate.get("issue_id") != skeleton.get("issue_id"):
        return _candidate_result(
            "stale",
            errors=["candidate issue_id does not match selected skeleton issue_id"],
            warnings=warnings,
            checks=_checks("issue-binding", "stale"),
            assurance=assurance,
            skeleton=skeleton,
            candidate=candidate,
            profile_suggestion=profile_suggestion_report,
        )
    if target_profile != local_profile:
        return _candidate_result(
            "stale",
            errors=["candidate target.profile does not match local authorized_profile"],
            warnings=warnings,
            checks=_checks("profile-resolution", "stale"),
            assurance=assurance,
            skeleton=skeleton,
            candidate=candidate,
            profile_suggestion=profile_suggestion_report,
        )

    hash_mismatches = [
        field
        for field in ("template_sha256", "skeleton_sha256", "section_inventory_sha256")
        if target[field] != skeleton[field]
    ]
    if hash_mismatches:
        return _candidate_result(
            "stale",
            errors=[f"candidate target.{field} does not match selected skeleton" for field in hash_mismatches],
            warnings=warnings,
            checks=_checks("skeleton-hash", "stale"),
            assurance=assurance,
            skeleton=skeleton,
            candidate=candidate,
            profile_suggestion=profile_suggestion_report,
        )

    allowed_ids = list(skeleton["_allowed_section_ids"])
    required_ids = list(skeleton["_required_section_ids"])
    section_fills = candidate.get("section_fills", [])
    fill_errors, section_results, candidate_ids = _section_results(section_fills)
    if fill_errors:
        return _candidate_result(
            "fail",
            errors=fill_errors,
            warnings=warnings,
            checks=_checks("section-fill-schema", "fail"),
            assurance=assurance,
            skeleton=skeleton,
            candidate=candidate,
            profile_suggestion=profile_suggestion_report,
            section_results=section_results,
        )

    extra_ids = sorted(set(candidate_ids) - set(allowed_ids))
    missing_required_ids = sorted(set(required_ids) - set(candidate_ids))
    optional_ids = sorted(set(allowed_ids) - set(required_ids))
    missing_optional_ids = sorted(set(optional_ids) - set(candidate_ids))
    if missing_optional_ids:
        warnings.append("optional section fill missing")

    unsafe_results = [row for row in section_results if row["unsafe_claim_detected"]]
    if unsafe_results:
        return _candidate_result(
            "rejected",
            errors=["section fill contains unsafe authority claim"],
            warnings=warnings,
            checks=_checks("unsafe-authority-claims", "rejected"),
            assurance=assurance,
            skeleton=skeleton,
            candidate=candidate,
            profile_suggestion=profile_suggestion_report,
            section_results=section_results,
            extra_section_ids=extra_ids,
            missing_section_ids=missing_required_ids,
        )
    if extra_ids:
        return _candidate_result(
            "rejected",
            errors=["candidate contains section fill outside local selected skeleton inventory"],
            warnings=warnings,
            checks=_checks("section-map", "rejected"),
            assurance=assurance,
            skeleton=skeleton,
            candidate=candidate,
            profile_suggestion=profile_suggestion_report,
            section_results=section_results,
            extra_section_ids=extra_ids,
            missing_section_ids=missing_required_ids,
        )
    if missing_required_ids:
        return _candidate_result(
            "fail",
            errors=["candidate is missing required section fill"],
            warnings=warnings,
            checks=_checks("missing-section-report", "fail"),
            assurance=assurance,
            skeleton=skeleton,
            candidate=candidate,
            profile_suggestion=profile_suggestion_report,
            section_results=section_results,
            extra_section_ids=extra_ids,
            missing_section_ids=missing_required_ids,
        )

    eligible_ids = [section_id for section_id in candidate_ids if section_id in allowed_ids]
    checks.extend(_checks("profile-resolution", "pass"))
    checks.extend(_checks("skeleton-hash", "pass"))
    checks.extend(_checks("section-map", "pass"))
    checks.extend(_checks("unsafe-authority-claims", "pass"))
    return _candidate_result(
        "pass",
        errors=errors,
        warnings=warnings,
        checks=checks,
        assurance=assurance,
        skeleton=skeleton,
        candidate=candidate,
        profile_suggestion=profile_suggestion_report,
        section_results=section_results,
        eligible_section_ids=eligible_ids,
        missing_section_ids=[],
        missing_optional_section_ids=missing_optional_ids,
        extra_section_ids=[],
    )


def _candidate_result(
    status: str,
    *,
    errors: list[str],
    warnings: list[str],
    checks: list[dict[str, str]],
    assurance: dict[str, Any],
    skeleton: dict[str, Any],
    candidate: dict[str, Any],
    profile_suggestion: dict[str, Any],
    section_results: list[dict[str, Any]] | None = None,
    eligible_section_ids: list[str] | None = None,
    missing_section_ids: list[str] | None = None,
    missing_optional_section_ids: list[str] | None = None,
    extra_section_ids: list[str] | None = None,
) -> dict[str, Any]:
    target = candidate.get("target", {})
    allowed_ids = list(skeleton.get("_allowed_section_ids", []))
    required_ids = list(skeleton.get("_required_section_ids", []))
    section_results = section_results or []
    candidate_ids = [row["section_id"] for row in section_results]
    eligible_section_ids = eligible_section_ids or []
    missing_section_ids = missing_section_ids or []
    extra_section_ids = extra_section_ids or []
    missing_optional_section_ids = missing_optional_section_ids or []
    return {
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
        "candidate": {
            "path": CANDIDATE_FILL_PATH,
            "issue_id": _safe_diagnostic_value(candidate.get("issue_id")),
            "target_profile": _safe_diagnostic_value(target.get("profile")),
            "target_template_sha256": _safe_diagnostic_value(target.get("template_sha256")),
            "target_skeleton_sha256": _safe_diagnostic_value(target.get("skeleton_sha256")),
            "target_section_inventory_sha256": _safe_diagnostic_value(target.get("section_inventory_sha256")),
            "profile_suggestion": profile_suggestion,
            "section_fill_count": len(candidate_ids),
        },
        "profile_validation": {
            "local_authorized_profile": assurance["authorized_profile"],
            "selected_skeleton_profile": skeleton.get("authorized_profile"),
            "candidate_target_profile": _safe_diagnostic_value(target.get("profile")),
            "target_profile_matches": target.get("profile") == assurance["authorized_profile"],
            "profile_suggestion_used_for_authority": False,
        },
        "skeleton_validation": {
            "template_sha256_matches": target.get("template_sha256") == skeleton.get("template_sha256"),
            "skeleton_sha256_matches": target.get("skeleton_sha256") == skeleton.get("skeleton_sha256"),
            "section_inventory_sha256_matches": target.get("section_inventory_sha256")
            == skeleton.get("section_inventory_sha256"),
        },
        "section_inventory_validation": {
            "allowed_section_ids": allowed_ids,
            "required_section_ids": required_ids,
            "candidate_section_ids": candidate_ids,
            "eligible_section_ids": eligible_section_ids,
            "missing_section_ids": missing_section_ids,
            "missing_optional_section_ids": missing_optional_section_ids,
            "extra_section_ids": extra_section_ids,
        },
        "section_results": section_results,
        "adoption": {
            "overall_adoption_eligible": status == "pass",
            "canonical_written": False,
            "assurance_mutated": False,
            "next_action": "manual adoption review; do not treat as reviewer pass",
        },
    }


def _profile_suggestion_snapshot(value: Any, local_profile: str, warnings: list[str]) -> dict[str, Any]:
    if value is None:
        return {
            "profile": None,
            "advisory_only": True,
            "ignored_for_authority": True,
        }
    if not isinstance(value, dict):
        warnings.append("profile_suggestion ignored because it is not an object")
        return {
            "profile": None,
            "advisory_only": True,
            "ignored_for_authority": True,
        }
    suggestion = value.get("profile")
    if isinstance(suggestion, str) and suggestion and suggestion != local_profile:
        warnings.append("profile_suggestion differs from local authorized_profile and was ignored for authority")
    return {
        "profile": _safe_diagnostic_value(suggestion),
        "advisory_only": value.get("advisory_only") is True,
        "ignored_for_authority": True,
    }


def _section_results(fills: Any) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    ids: list[str] = []
    if not isinstance(fills, list):
        return ["candidate-fill.section_fills must be an array"], [], []
    seen: set[str] = set()
    for index, fill in enumerate(fills):
        label = f"candidate-fill.section_fills[{index}]"
        if not isinstance(fill, dict):
            errors.append(f"{label} must be an object")
            continue
        if "authorized_profile" in fill:
            rows.append(_section_result("<invalid>", "", unsafe=True))
            errors.append(f"{label}.authorized_profile is not allowed")
            continue
        section_id = fill.get("section_id")
        body = fill.get("body")
        if not isinstance(section_id, str) or not section_id or _safe_section_id_error(section_id):
            errors.append(f"{label}.section_id is invalid")
            continue
        if section_id in seen:
            errors.append(f"{label}.section_id is duplicated")
            continue
        seen.add(section_id)
        ids.append(section_id)
        if not isinstance(body, str):
            errors.append(f"{label}.body must be a string")
            continue
        body_hash = _sha256_text(body)
        expected_hash = fill.get("body_sha256")
        if expected_hash is not None and expected_hash != body_hash:
            errors.append(f"{label}.body_sha256 mismatch")
            continue
        rows.append(_section_result(section_id, body, unsafe=_unsafe_text_error(body) is not None))
    return errors, rows, ids


def _section_result(section_id: str, body: str, *, unsafe: bool) -> dict[str, Any]:
    return {
        "section_id": _safe_diagnostic_value(section_id),
        "status": "rejected" if unsafe else "eligible",
        "body_sha256": _sha256_text(body),
        "unsafe_claim_detected": unsafe,
    }


def _unsafe_metadata_error(value: Any) -> str | None:
    text = json.dumps(_metadata_without_section_bodies(value), ensure_ascii=False, sort_keys=True)
    if _unsafe_text_error(text):
        return "candidate fill metadata contains unsafe authority claim"
    if _contains_key(value, "authorized_profile"):
        return "candidate fill must not set authorized_profile"
    return None


def _contains_key(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False


def _metadata_without_section_bodies(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    metadata = dict(value)
    fills = metadata.get("section_fills")
    if isinstance(fills, list):
        redacted_fills: list[Any] = []
        for fill in fills:
            if isinstance(fill, dict):
                copy = dict(fill)
                if "body" in copy:
                    copy["body"] = "<section-body>"
                redacted_fills.append(copy)
            else:
                redacted_fills.append(fill)
        metadata["section_fills"] = redacted_fills
    return metadata


def _load_json_file(path: Path, label: str, *, missing_status: str) -> dict[str, Any]:
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


def _base_result(
    status: str,
    generated_at: str,
    *,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
    checks: list[dict[str, str]] | None = None,
    review: dict[str, Any] | None = None,
    assurance_snapshot: dict[str, Any] | None = None,
    selected_skeleton: dict[str, Any] | None = None,
    candidate: dict[str, Any] | None = None,
    profile_validation: dict[str, Any] | None = None,
    skeleton_validation: dict[str, Any] | None = None,
    section_inventory_validation: dict[str, Any] | None = None,
    section_results: list[dict[str, Any]] | None = None,
    adoption: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trace = _result_trace(selected_skeleton, review)
    return {
        **AUTHORITY_BOUNDARY,
        "status": status,
        "generated_at": generated_at,
        "trace": trace,
        "inputs": {
            "review": _safe_diagnostic_value(review or {}),
            "assurance_snapshot": _safe_diagnostic_value(assurance_snapshot or {}),
            "selected_skeleton": _safe_diagnostic_value(selected_skeleton or {}),
        },
        "candidate": _safe_diagnostic_value(candidate or {}),
        "profile_validation": profile_validation or {},
        "skeleton_validation": skeleton_validation or {},
        "section_inventory_validation": section_inventory_validation or {},
        "section_results": section_results or [],
        "adoption": adoption
        or {
            "overall_adoption_eligible": False,
            "canonical_written": False,
            "assurance_mutated": False,
            "next_action": "manual adoption review; do not treat as reviewer pass",
        },
        "checks": checks or [],
        "errors": _safe_diagnostic_value(errors or []),
        "warnings": _safe_diagnostic_value(warnings or []),
        "status_taxonomy": _status_taxonomy(),
    }


def _result_trace(selected_skeleton: dict[str, Any] | None, review: dict[str, Any] | None) -> dict[str, Any]:
    if selected_skeleton:
        trace = selected_skeleton.get("trace")
        if isinstance(trace, dict):
            return _safe_diagnostic_value(trace)
    if review:
        trace = review.get("trace")
        if isinstance(trace, dict) and trace:
            return _safe_diagnostic_value(trace)
    return _default_trace()


def _default_trace() -> dict[str, Any]:
    return {
        "issue_id": "iss-00287",
        "parent_epic": "epic-00283",
        "requirements": ["E-RQ-008", "E-RQ-009"],
        "acceptance": ["E-AC-005", "E-AC-006"],
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


def _safe_section_id_error(value: str) -> str | None:
    if not isinstance(value, str) or not value:
        return "section_id must be a non-empty string"
    if not re.match(r"^[a-z0-9._-]+$", value):
        return "section_id must use lowercase safe characters"
    if any(marker in value for marker in SECRET_PATH_MARKERS):
        return "section_id must not contain secret markers"
    return None


def _unsafe_text_error(value: str) -> str | None:
    normalized = _normalize_claim_text(value)
    if any(claim in normalized for claim in _forbidden_claims()):
        return "unsafe authority claim rejected"
    lowered = value.lower()
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
    return f"""# Selected skeleton fill validation summary

Status: `{result["status"]}`

Authority:
- authority: evidence_only
- adoption_status: unreviewed
- bundle_generation_not_promotion: true

Adoption:
- overall_adoption_eligible: `{str(adoption.get("overall_adoption_eligible", False)).lower()}`
- canonical_written: `{str(adoption.get("canonical_written", False)).lower()}`
- assurance_mutated: `{str(adoption.get("assurance_mutated", False)).lower()}`

Errors:
{errors}

Warnings:
{warnings}
"""


def _section_fill_dry_run(result: dict[str, Any]) -> dict[str, Any]:
    status = result["status"]
    section_inventory = result.get("section_inventory_validation", {})
    section_results = result.get("section_results", [])
    if not isinstance(section_results, list):
        section_results = []
    staged_sections = section_results if status == "pass" else []
    non_adoptable_sections = section_results if status != "pass" else []
    return {
        **AUTHORITY_BOUNDARY,
        "status": status,
        "trace": _safe_diagnostic_value(result.get("trace", _default_trace())),
        "eligible_section_ids": _safe_diagnostic_value(section_inventory.get("eligible_section_ids", [])),
        "missing_section_ids": _safe_diagnostic_value(section_inventory.get("missing_section_ids", [])),
        "missing_optional_section_ids": _safe_diagnostic_value(
            section_inventory.get("missing_optional_section_ids", [])
        ),
        "extra_section_ids": _safe_diagnostic_value(section_inventory.get("extra_section_ids", [])),
        "staged_sections": [
            {
                "section_id": _safe_diagnostic_value(section.get("section_id")),
                "status": _safe_diagnostic_value(section.get("status")),
                "body_sha256": _safe_diagnostic_value(section.get("body_sha256")),
                "canonical_written": False,
            }
            for section in staged_sections
            if isinstance(section, dict)
        ],
        "non_adoptable_sections": [
            {
                "section_id": _safe_diagnostic_value(section.get("section_id")),
                "status": _safe_diagnostic_value(section.get("status")),
                "body_sha256": _safe_diagnostic_value(section.get("body_sha256")),
                "canonical_written": False,
                "adoption_eligible": False,
            }
            for section in non_adoptable_sections
            if isinstance(section, dict)
        ],
        "adoption_status": "unreviewed",
        "canonical_written": False,
        "assurance_mutated": False,
        "next_action": "manual section adoption review; do not treat as reviewer pass",
    }


def _dry_run_markdown(dry_run: dict[str, Any]) -> str:
    staged = dry_run.get("staged_sections", [])
    non_adoptable = dry_run.get("non_adoptable_sections", [])
    rows = [
        f"| {section.get('section_id', '')} | {section.get('status', '')} | {section.get('body_sha256', '')} | false |"
        for section in staged
        if isinstance(section, dict)
    ]
    staged_rows = "\n".join(rows) or "| none | none | none | false |"
    non_adoptable_rows = [
        f"| {section.get('section_id', '')} | {section.get('status', '')} | {section.get('body_sha256', '')} | false |"
        for section in non_adoptable
        if isinstance(section, dict)
    ]
    blocked_rows = "\n".join(non_adoptable_rows) or "| none | none | none | false |"
    return f"""# Selected skeleton fill dry run

Status: `{dry_run["status"]}`

Authority:
- authority: evidence_only
- adoption_status: unreviewed
- bundle_generation_not_promotion: true

Safety:
- canonical_written: `false`
- assurance_mutated: `false`
- next_action: manual section adoption review; do not treat as reviewer pass

Section inventory:
- eligible_section_ids: `{dry_run.get("eligible_section_ids", [])}`
- missing_section_ids: `{dry_run.get("missing_section_ids", [])}`
- missing_optional_section_ids: `{dry_run.get("missing_optional_section_ids", [])}`
- extra_section_ids: `{dry_run.get("extra_section_ids", [])}`

| section_id | status | body_sha256 | canonical_written |
|---|---|---|---|
{staged_rows}

Non-adoptable sections:

| section_id | status | body_sha256 | adoption_eligible |
|---|---|---|---|
{blocked_rows}
"""


def _status_taxonomy() -> dict[str, str]:
    return {
        "pass": "Selected skeleton fill validation passed; adoption remains unreviewed.",
        "fail": "Input schema or required selected-fill data is invalid.",
        "blocked": "Required local observation or filesystem operation is unavailable.",
        "stale": "Local assurance, selected skeleton, review digest, or candidate target snapshot no longer matches.",
        "rejected": "A safety boundary, unauthorized authority claim, or extra section fill was detected.",
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


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
