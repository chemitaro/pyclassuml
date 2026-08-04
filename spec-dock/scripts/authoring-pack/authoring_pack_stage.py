#!/usr/bin/env python3
# mypy: ignore-errors
"""Stage reviewed evidence-only ChatGPT authoring pack content."""

from __future__ import annotations

from datetime import datetime, timezone
import difflib
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
OWNERSHIP_MARKER = "owned-by=stage_chatgpt_authoring_pack.py\n"
OWNERSHIP_MARKER_FILE = ".specdock-authoring-pack-stage"
ALLOWED_TARGETS = {"requirement.md", "design.md", "plan.md"}
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


def stage_reviewed_pack(
    review_report_path: Path,
    pack_tree: Path,
    issue_dir: Path,
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

    if not issue_dir.exists() or not issue_dir.is_dir() or issue_dir.is_symlink():
        return _base_result(
            "blocked",
            generated_at,
            errors=["issue_dir could not be observed"],
            checks=_checks("issue-dir", "blocked"),
            review=review["review_snapshot"],
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

    adoption_map = _load_pack_json(root / "adoption/adoption-map.json", "adoption-map")
    if adoption_map["status"] != "pass":
        return _base_result(
            adoption_map["status"],
            generated_at,
            errors=adoption_map["errors"],
            checks=adoption_map["checks"],
            review=review["review_snapshot"],
        )

    validation = _validate_stage_items(adoption_map["payload"], root, issue_dir)
    if validation["status"] != "pass":
        return _base_result(
            validation["status"],
            generated_at,
            errors=validation["errors"],
            checks=validation["checks"],
            review=review["review_snapshot"],
        )

    items: list[dict[str, Any]] = []
    staged_texts: dict[str, str] = {}
    diff_texts: dict[str, str] = {}
    eal_rows: list[dict[str, Any]] = []
    diff_rows: list[dict[str, Any]] = []

    for index, item in enumerate(validation["items"], start=1):
        item_id = f"item-{index:04d}"
        staged_artifact_path = f"staged-artifacts/{item_id}.md"
        diff_path = f"diffs/{item_id}.diff"
        target_text = item["target_text"]
        candidate_text = item["candidate_text"]
        diff_text = _unified_diff(item["target_name"], item_id, target_text, candidate_text)
        diff_status = "same" if not diff_text else "changed"
        additions, deletions = _diff_stats(diff_text)

        staged_texts[staged_artifact_path] = candidate_text
        diff_texts[diff_path] = diff_text
        item_row = {
            "item_id": item_id,
            "source_path": item["source_name"],
            "target_path": item["target_name"],
            "staged_artifact_path": staged_artifact_path,
            "diff_path": diff_path,
            "candidate_sha256": _sha256_text(candidate_text),
            "target_sha256_before": _sha256_text(target_text),
            "diff_status": diff_status,
            "adoption_status": "unreviewed",
            "required_local_validation": item["required_local_validation"],
        }
        items.append(item_row)
        diff_rows.append({
            "item_id": item_id,
            "target_path": item["target_name"],
            "candidate_path": staged_artifact_path,
            "diff_path": diff_path,
            "diff_status": diff_status,
            "additions": additions,
            "deletions": deletions,
            "canonical_written": False,
        })
        eal_rows.append({
            "candidate_id": f"EAL-CAND-{index:04d}",
            "adoption_status": "unreviewed",
            "source": "ChatGPT ZIP authoring pack reviewed by review_chatgpt_authoring_pack.py",
            "source_path": item["source_name"],
            "target": item["target_name"],
            "staged_artifact": staged_artifact_path,
            "dry_run_diff": diff_path,
            "rationale": item["rationale"],
            "required_local_validation": item["required_local_validation"],
            "next_action": "manual review; if accepted, rewrite canonical doc and record final EAL row separately",
        })

    diff_report = {
        **AUTHORITY_BOUNDARY,
        "status": "pass",
        "diffs": diff_rows,
    }
    eal_candidates = {
        **AUTHORITY_BOUNDARY,
        "status": "pass",
        "rows": eal_rows,
    }
    result = _base_result(
        "pass",
        generated_at,
        checks=_checks("authoring-pack-stage", "pass"),
        review=review["review_snapshot"],
        items=items,
        outputs={
            "dry_run_diff_json": "dry-run-diff.json",
            "dry_run_diff_markdown": "dry-run-diff.md",
            "eal_candidates": "adoption/eal-candidates.json",
            "staged_artifact_count": len(items),
        },
    )
    result["_stage_payload"] = {
        "staged_texts": staged_texts,
        "diff_texts": diff_texts,
        "diff_report": diff_report,
        "eal_candidates": eal_candidates,
    }
    return result


def write_stage_outputs(output_dir: Path, result: dict[str, Any]) -> dict[str, Any]:
    prepared = _prepare_output_dir(output_dir)
    if prepared is not None:
        return _base_result(
            "blocked",
            result.get("generated_at", _now()),
            errors=[prepared],
            review=result.get("review"),
        )

    _write_text(output_dir / OWNERSHIP_MARKER_FILE, OWNERSHIP_MARKER)
    if result["status"] == "pass":
        payload = result.get("_stage_payload", {})
        for relative_path, text in payload.get("staged_texts", {}).items():
            _write_text(output_dir / relative_path, text)
        for relative_path, text in payload.get("diff_texts", {}).items():
            _write_text(output_dir / relative_path, text)
        _write_json(output_dir / "dry-run-diff.json", payload.get("diff_report", {}))
        _write_text(output_dir / "dry-run-diff.md", _diff_markdown(payload.get("diff_report", {})))
        _write_json(output_dir / "adoption/eal-candidates.json", payload.get("eal_candidates", {}))

    public_result = _public_result(result)
    _write_json(output_dir / "staging-report.json", public_result)
    _write_text(output_dir / "staging-summary.md", _summary_markdown(public_result))
    return public_result


def cli_summary(result: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "status": result["status"],
        "output_dir": _display_path(output_dir),
    }
    outputs = result.get("outputs")
    if isinstance(outputs, dict):
        summary["staged_artifact_count"] = outputs.get("staged_artifact_count", 0)
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


def _load_pack_json(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "status": "fail",
            "errors": [f"{label} missing"],
            "checks": _checks(label, "fail"),
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


def _validate_stage_items(adoption_map: dict[str, Any], pack_root: Path, issue_dir: Path) -> dict[str, Any]:
    raw_items = adoption_map.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        return {
            "status": "fail",
            "errors": ["adoption-map.items must be a non-empty array"],
            "checks": _checks("adoption-map", "fail"),
        }

    errors: list[str] = []
    rejected: list[str] = []
    blocked: list[str] = []
    items: list[dict[str, Any]] = []

    for index, raw_item in enumerate(raw_items):
        label = f"adoption-map.items[{index}]"
        if not isinstance(raw_item, dict):
            errors.append(f"{label} must be an object")
            continue
        item_text = json.dumps(raw_item, ensure_ascii=False, sort_keys=True)
        if _unsafe_text_error(item_text):
            rejected.append(f"{label} contains unsafe text")
            continue
        if raw_item.get("adoption_status") != "unreviewed":
            rejected.append(f"{label}.adoption_status must be unreviewed")
        if raw_item.get("authority") not in (None, "evidence_only"):
            rejected.append(f"{label}.authority must be evidence_only")
        write_mode = raw_item.get("write_mode")
        if write_mode not in (None, "stage", "staged", "dry_run"):
            rejected.append(f"{label}.write_mode is not allowed")

        source_name = _pack_relative_name(raw_item.get("source_path"))
        if source_name is None or _safe_relative_path_error(source_name):
            rejected.append(f"{label}.source_path is unsafe")
            continue
        if PurePosixPath(source_name).suffix.lower() != ".md":
            rejected.append(f"{label}.source_path must be markdown")
            continue
        target_name = raw_item.get("target_path", raw_item.get("target"))
        if (
            not isinstance(target_name, str)
            or _safe_relative_path_error(target_name)
            or target_name not in ALLOWED_TARGETS
        ):
            rejected.append(f"{label}.target_path is not allowed")
            continue

        required_local_validation = raw_item.get("required_local_validation")
        if not isinstance(required_local_validation, list) or not all(
            isinstance(value, str) and value for value in required_local_validation
        ):
            errors.append(f"{label}.required_local_validation must be a string array")
            continue
        if _unsafe_text_error(" ".join(required_local_validation)):
            rejected.append(f"{label}.required_local_validation contains unsafe text")
            continue

        rationale = raw_item.get("rationale", "")
        if not isinstance(rationale, str):
            errors.append(f"{label}.rationale must be a string when present")
            continue
        if _unsafe_text_error(rationale):
            rejected.append(f"{label}.rationale contains unsafe text")
            continue

        source_path = pack_root / source_name
        target_path = issue_dir / target_name
        if not source_path.exists() or not source_path.is_file() or source_path.is_symlink():
            errors.append(f"{label}.source_path could not be read")
            continue
        if not target_path.exists() or not target_path.is_file() or target_path.is_symlink():
            blocked.append(f"{label}.target_path could not be observed")
            continue
        try:
            source_text = source_path.read_text(encoding="utf-8")
            target_text = target_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            rejected.append(f"{label} contains binary text")
            continue
        except OSError:
            blocked.append(f"{label} local file could not be read")
            continue
        if len(source_text.encode("utf-8")) > MAX_FILE_SIZE:
            rejected.append(f"{label}.source_path exceeds size limit")
            continue
        content_error = _unsafe_text_error(source_text)
        if content_error:
            rejected.append(f"{label}.source_path contains unsafe text")
            continue

        items.append({
            "source_name": source_name,
            "source_path": source_path,
            "target_name": target_name,
            "target_path": target_path,
            "candidate_text": source_text,
            "target_text": target_text,
            "required_local_validation": required_local_validation,
            "rationale": rationale,
        })

    if rejected:
        return {
            "status": "rejected",
            "errors": sorted(set(rejected)),
            "checks": _checks("stage-item-safety", "rejected"),
        }
    if blocked:
        return {
            "status": "blocked",
            "errors": sorted(set(blocked)),
            "checks": _checks("stage-item-read", "blocked"),
        }
    if errors:
        return {
            "status": "fail",
            "errors": sorted(set(errors)),
            "checks": _checks("stage-item-schema", "fail"),
        }
    return {
        "status": "pass",
        "errors": [],
        "checks": _checks("stage-items", "pass"),
        "items": items,
    }


def _base_result(
    status: str,
    generated_at: str,
    *,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
    checks: list[dict[str, str]] | None = None,
    review: dict[str, Any] | None = None,
    items: list[dict[str, Any]] | None = None,
    outputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        **AUTHORITY_BOUNDARY,
        "status": status,
        "generated_at": generated_at,
        "trace": {
            "issue_id": "iss-00286",
            "parent_epic": "epic-00283",
            "requirements": ["E-RQ-006", "E-RQ-007"],
            "acceptance": ["E-AC-008", "E-AC-009"],
        },
        "review": _safe_diagnostic_value(review or {}),
        "items": items or [],
        "outputs": outputs or {},
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


def _public_result(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if not key.startswith("_")}


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


def _pack_relative_name(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if value.startswith(EXPECTED_ROOT):
        return value[len(EXPECTED_ROOT) :]
    return value


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


def _unified_diff(target_name: str, item_id: str, target_text: str, candidate_text: str) -> str:
    return "".join(
        difflib.unified_diff(
            target_text.splitlines(keepends=True),
            candidate_text.splitlines(keepends=True),
            fromfile=f"canonical/{target_name}",
            tofile=f"staged/{item_id}.md",
        )
    )


def _diff_stats(diff_text: str) -> tuple[int, int]:
    additions = 0
    deletions = 0
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            additions += 1
        elif line.startswith("-"):
            deletions += 1
    return additions, deletions


def _diff_markdown(diff_report: dict[str, Any]) -> str:
    lines = ["# Authoring pack dry-run diff", ""]
    lines.append("Authority:")
    lines.append("- authority: evidence_only")
    lines.append("- adoption_status: unreviewed")
    lines.append("- bundle_generation_not_promotion: true")
    lines.append("")
    lines.append("| item | target | diff | status | canonical_written |")
    lines.append("|---|---|---|---|---|")
    for row in diff_report.get("diffs", []):
        lines.append(
            f"| `{row['item_id']}` | `{row['target_path']}` | `{row['diff_path']}` | "
            f"`{row['diff_status']}` | `{str(row['canonical_written']).lower()}` |"
        )
    lines.append("")
    return "\n".join(lines)


def _summary_markdown(result: dict[str, Any]) -> str:
    errors = "\n".join(f"- {error}" for error in result.get("errors", [])) or "- none"
    warnings = "\n".join(f"- {warning}" for warning in result.get("warnings", [])) or "- none"
    outputs = result.get("outputs", {})
    output_lines = "\n".join(f"- {key}: `{value}`" for key, value in outputs.items()) or "- none"
    return f"""# Authoring pack staging summary

Status: `{result["status"]}`

Authority:
- authority: evidence_only
- adoption_status: unreviewed
- bundle_generation_not_promotion: true

Outputs:
{output_lines}

Errors:
{errors}

Warnings:
{warnings}
"""


def _status_taxonomy() -> dict[str, str]:
    return {
        "pass": "Staging passed; adoption remains unreviewed.",
        "fail": "Input shape or required metadata is invalid.",
        "blocked": "Required local observation or filesystem operation is unavailable.",
        "stale": "Review/source snapshot is no longer valid.",
        "rejected": "A safety boundary was violated.",
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
            return "output_dir contains non-stage files; choose an empty or stage-owned directory"
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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
