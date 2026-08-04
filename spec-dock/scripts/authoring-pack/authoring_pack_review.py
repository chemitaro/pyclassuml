#!/usr/bin/env python3
"""Review evidence-only ChatGPT authoring pack ZIPs."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
from typing import Any
from zipfile import BadZipFile, ZipFile, ZipInfo

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

ALLOWED_TEXT_SUFFIXES = {".json", ".md", ".txt"}
NESTED_ARCHIVE_SUFFIXES = (
    ".zip",
    ".tar",
    ".tgz",
    ".tar.gz",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".rar",
)
EXPECTED_ROOT = "specdock-authoring-pack/"
OWNERSHIP_MARKER = "owned-by=review_chatgpt_authoring_pack.py\n"
OWNERSHIP_MARKER_FILE = ".specdock-authoring-pack-review"
MAX_ENTRY_COUNT = 200
MAX_FILE_SIZE = 1_000_000
MAX_TOTAL_SIZE = 10_000_000
MAX_COMPRESSION_RATIO = 100
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def review_input(
    input_path: Path,
    preflight_path: Path,
    *,
    input_kind: str = "auto",
    extract_dir: Path | None = None,
) -> dict[str, Any]:
    generated_at = _now()
    preflight = _load_preflight(preflight_path, generated_at)
    if preflight["status"] != "pass":
        return _base_result(
            preflight["status"],
            generated_at,
            _detect_input_kind(input_path, input_kind),
            errors=preflight["errors"],
            checks=preflight["checks"],
            preflight=preflight.get("preflight_snapshot"),
        )

    detected_kind = _detect_input_kind(input_path, input_kind)
    if detected_kind == "zip":
        result = _review_zip(input_path, preflight["preflight"], generated_at)
    elif detected_kind == "tree":
        result = _review_tree(input_path, preflight["preflight"], generated_at)
    else:
        result = _base_result(
            "fail",
            generated_at,
            detected_kind,
            errors=["input must be a zip file or directory tree"],
            preflight=preflight["preflight_snapshot"],
        )

    if extract_dir is not None and detected_kind == "zip" and result["status"] == "pass":
        extracted = _safe_extract_zip(input_path, extract_dir, result["entries"])
        if extracted:
            result["errors"].extend(extracted)
            result["checks"].extend(_checks("safe-extraction", "blocked"))
            result["status"] = "blocked"
    return result


def write_review_outputs(output_dir: Path, result: dict[str, Any]) -> dict[str, Any]:
    prepared = _prepare_output_dir(output_dir)
    if prepared is not None:
        blocked = _base_result(
            "blocked",
            result.get("generated_at", _now()),
            result.get("input_kind", "unknown"),
            errors=[prepared],
            preflight=result.get("preflight"),
        )
        return blocked

    _write_text(output_dir / OWNERSHIP_MARKER_FILE, OWNERSHIP_MARKER)
    _write_json(output_dir / "validation-report.json", result)
    _write_text(output_dir / "validation-summary.md", _summary_markdown(result))
    return result


def cli_summary(result: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "status": result["status"],
        "output_dir": _display_path(output_dir),
    }
    if result.get("errors"):
        summary["errors"] = _safe_diagnostic_value(result["errors"])
    return summary


def _review_zip(input_path: Path, preflight: dict[str, Any], generated_at: str) -> dict[str, Any]:
    if not input_path.exists():
        return _base_result("blocked", generated_at, "zip", errors=["input zip missing"], preflight=preflight)
    if not input_path.is_file():
        return _base_result("fail", generated_at, "zip", errors=["input zip must be a file"], preflight=preflight)

    try:
        with ZipFile(input_path) as archive:
            entries, entry_errors = _inspect_zip_entries(archive, preflight)
            if entry_errors:
                return _base_result(
                    "rejected",
                    generated_at,
                    "zip",
                    errors=entry_errors,
                    checks=_checks("zip-central-directory", "rejected"),
                    preflight=preflight,
                    entries=entries,
                )
            files = _read_zip_text_files(archive, entries)
    except BadZipFile:
        return _base_result("fail", generated_at, "zip", errors=["input zip is invalid"], preflight=preflight)
    except OSError:
        return _base_result("blocked", generated_at, "zip", errors=["input zip could not be read"], preflight=preflight)

    return _validate_pack_files(files, preflight, generated_at, "zip", entries=entries)


def _review_tree(input_path: Path, preflight: dict[str, Any], generated_at: str) -> dict[str, Any]:
    if not input_path.exists():
        return _base_result("blocked", generated_at, "tree", errors=["input tree missing"], preflight=preflight)
    if not input_path.is_dir() or input_path.is_symlink():
        return _base_result(
            "fail", generated_at, "tree", errors=["input tree must be a directory"], preflight=preflight
        )

    root = _tree_root(input_path)
    files: dict[str, str] = {}
    entries: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root).as_posix()
            pack_path = f"{EXPECTED_ROOT}{relative}"
            normalized_error = _pack_path_error(pack_path, expected_root=EXPECTED_ROOT)
            if normalized_error:
                errors.append(normalized_error)
                continue
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
            suffix_error = _file_suffix_error(pack_path)
            if suffix_error:
                errors.append(suffix_error)
                continue
            data = path.read_bytes()
            text_error = _text_payload_error(pack_path, data)
            if text_error:
                errors.append(text_error)
                continue
            files[pack_path] = data.decode("utf-8")
            entries.append({"path": pack_path, "size_bytes": len(data), "mode": None})
    except OSError:
        return _base_result(
            "blocked", generated_at, "tree", errors=["input tree could not be read"], preflight=preflight
        )

    if errors:
        return _base_result(
            "rejected",
            generated_at,
            "tree",
            errors=sorted(set(errors)),
            checks=_checks("tree-safety", "rejected"),
            preflight=preflight,
            entries=entries,
        )

    result = _validate_pack_files(files, preflight, generated_at, "tree", entries=entries)
    result["deferred"].append("tree input does not provide ZIP central directory safety evidence")
    return result


def _load_preflight(preflight_path: Path, generated_at: str) -> dict[str, Any]:
    if not preflight_path.exists():
        return {
            "status": "blocked",
            "errors": ["preflight missing"],
            "checks": _checks("preflight", "blocked"),
        }
    if not preflight_path.is_file():
        return {
            "status": "fail",
            "errors": ["preflight must be a file"],
            "checks": _checks("preflight", "fail"),
        }
    try:
        raw = preflight_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except OSError:
        return {
            "status": "blocked",
            "errors": ["preflight could not be read"],
            "checks": _checks("preflight", "blocked"),
        }
    except json.JSONDecodeError:
        return {
            "status": "fail",
            "errors": ["preflight must be valid JSON"],
            "checks": _checks("preflight", "fail"),
        }
    if not isinstance(data, dict):
        return {
            "status": "fail",
            "errors": ["preflight must be a JSON object"],
            "checks": _checks("preflight", "fail"),
        }
    validation_errors = _validate_preflight_shape(data)
    if validation_errors:
        return {
            "status": "fail",
            "errors": validation_errors,
            "checks": _checks("preflight", "fail"),
            "preflight_snapshot": _preflight_snapshot(data),
        }
    status = data.get("status")
    if status != "pass":
        return {
            "status": status if status in STATUS_EXIT_CODES else "fail",
            "errors": [f"preflight status is not pass: {status}"],
            "checks": _checks("preflight", str(status)),
            "preflight_snapshot": _preflight_snapshot(data),
        }
    return {
        "status": "pass",
        "errors": [],
        "checks": _checks("preflight", "pass"),
        "preflight": data,
        "preflight_snapshot": _preflight_snapshot(data),
        "generated_at": generated_at,
    }


def _validate_preflight_shape(preflight: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key, value in AUTHORITY_BOUNDARY.items():
        if preflight.get(key) != value:
            errors.append(f"preflight boundary mismatch: {key}")
    if preflight.get("status") not in STATUS_EXIT_CODES:
        errors.append("preflight status is invalid")
    repository = preflight.get("repository")
    if not isinstance(repository, dict):
        errors.append("preflight repository must be an object")
    else:
        if not isinstance(repository.get("full_name"), str) or not repository["full_name"]:
            errors.append("preflight repository.full_name is required")
        if not isinstance(repository.get("requested_ref"), str) or not repository["requested_ref"]:
            errors.append("preflight repository.requested_ref is required")
        observed_ref = repository.get("observed_ref")
        observed_head = repository.get("observed_head")
        if not (isinstance(observed_ref, str) and observed_ref) and not (
            isinstance(observed_head, str) and observed_head
        ):
            errors.append("preflight repository observed_ref or observed_head is required")
    sources = preflight.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("preflight sources must be a non-empty array")
    else:
        for index, source in enumerate(sources):
            if not isinstance(source, dict):
                errors.append(f"preflight sources[{index}] must be an object")
                continue
            path = source.get("path")
            if not isinstance(path, str) or _repo_relative_path_error(path):
                errors.append(f"preflight sources[{index}].path is invalid")
            sha = source.get("sha256")
            if not isinstance(sha, str) or not HEX64.match(sha):
                errors.append(f"preflight sources[{index}].sha256 is invalid")
            role = source.get("role")
            if not isinstance(role, str) or not role:
                errors.append(f"preflight sources[{index}].role is invalid")
    stale_if = preflight.get("stale_if")
    errors.extend(_stale_if_schema_errors({"stale_if": stale_if}, "preflight stale_if"))
    safe_constraints = preflight.get("safe_output_constraints")
    if not isinstance(safe_constraints, dict):
        errors.append("preflight safe_output_constraints must be an object")
    elif not isinstance(safe_constraints.get("forbidden_claims"), list):
        errors.append("preflight forbidden_claims must be an array")
    errors.extend(_optional_trace_errors(preflight.get("trace")))
    return errors


def _optional_trace_errors(value: Any) -> list[str]:
    if value is None:
        return []
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["preflight trace must be an object when present"]
    for field in ("issue_id", "parent_epic"):
        if not isinstance(value.get(field), str) or not value[field]:
            errors.append(f"preflight trace.{field} is required when trace is present")
    for field in ("requirements", "acceptance"):
        items = value.get(field)
        if not isinstance(items, list) or not all(isinstance(item, str) and item for item in items):
            errors.append(f"preflight trace.{field} must be a string array when trace is present")
    trace_text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if _unsafe_text_error(trace_text):
        errors.append("preflight trace contains unsafe text")
    return errors


def _inspect_zip_entries(archive: ZipFile, preflight: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    expected_root = _expected_root(preflight)
    infos = archive.infolist()
    errors: list[str] = []
    entries: list[dict[str, Any]] = []
    normalized_paths: set[str] = set()
    total_size = 0

    if len(infos) > MAX_ENTRY_COUNT:
        errors.append("zip entry count exceeds limit")
    for info in infos:
        entry = _entry_observation(info)
        entries.append(entry)
        name = info.filename
        path_error = _pack_path_error(name, expected_root=expected_root)
        if path_error:
            errors.append(path_error)
            continue
        normalized = _normalize_pack_path(name)
        if normalized in normalized_paths:
            errors.append("duplicate normalized path rejected")
        normalized_paths.add(normalized)
        if info.is_dir():
            continue
        if info.flag_bits & 0x1:
            errors.append("encrypted zip entry rejected")
        mode = _zip_unix_mode(info)
        type_error = _zip_type_error(mode)
        if type_error:
            errors.append(type_error)
        suffix_error = _file_suffix_error(normalized)
        if suffix_error:
            errors.append(suffix_error)
        total_size += info.file_size
        if info.file_size > MAX_FILE_SIZE:
            errors.append("zip entry size exceeds limit")
        if info.compress_size > 0 and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
            errors.append("zip compression ratio exceeds limit")
    if total_size > MAX_TOTAL_SIZE:
        errors.append("zip total uncompressed size exceeds limit")
    return entries, sorted(set(errors))


def _read_zip_text_files(archive: ZipFile, entries: list[dict[str, Any]]) -> dict[str, str]:
    files: dict[str, str] = {}
    for entry in entries:
        path = entry["path"]
        if entry.get("is_dir"):
            continue
        data = archive.read(path)
        text_error = _text_payload_error(path, data)
        if text_error:
            files[path] = f"\x00{text_error}"
            continue
        files[path] = data.decode("utf-8")
    return files


def _validate_pack_files(
    files: dict[str, str],
    preflight: dict[str, Any],
    generated_at: str,
    input_kind: str,
    *,
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    errors: list[str] = []
    warnings: list[str] = []
    deferred: list[str] = []

    text_errors = [value[1:] for value in files.values() if value.startswith("\x00")]
    if text_errors:
        return _base_result(
            "rejected",
            generated_at,
            input_kind,
            errors=sorted(set(text_errors)),
            checks=_checks("text-payload", "rejected"),
            preflight=preflight,
            entries=entries,
        )

    mandatory = (
        f"{EXPECTED_ROOT}manifest.json",
        f"{EXPECTED_ROOT}provenance.json",
        f"{EXPECTED_ROOT}source-manifest.json",
        f"{EXPECTED_ROOT}stale-if.json",
        f"{EXPECTED_ROOT}adoption/adoption-map.json",
    )
    missing = [path for path in mandatory if path not in files]
    if missing:
        errors.extend(f"mandatory metadata missing: {_pack_relative(path)}" for path in missing)
        checks.extend(_checks("mandatory-metadata", "fail"))

    parsed_json: dict[str, dict[str, Any]] = {}
    for path, text in files.items():
        if path.endswith(".json"):
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                errors.append(f"json metadata invalid: {_pack_relative(path)}")
                continue
            if not isinstance(payload, dict):
                errors.append(f"json metadata must be an object: {_pack_relative(path)}")
                continue
            parsed_json[path] = payload

    safety_errors = _metadata_safety_errors(parsed_json)
    if safety_errors:
        return _base_result(
            "rejected",
            generated_at,
            input_kind,
            errors=safety_errors,
            checks=checks + _checks("metadata-safety", "rejected"),
            preflight=preflight,
            entries=entries,
        )

    errors.extend(_metadata_schema_errors(parsed_json, preflight))
    claim_errors = _unsafe_claim_errors(files, preflight)
    if claim_errors:
        return _base_result(
            "rejected",
            generated_at,
            input_kind,
            errors=claim_errors,
            checks=checks + _checks("unsafe-authority-claims", "rejected"),
            preflight=preflight,
            entries=entries,
        )

    if errors:
        return _base_result(
            "fail",
            generated_at,
            input_kind,
            errors=errors,
            checks=checks or _checks("metadata-schema", "fail"),
            preflight=preflight,
            entries=entries,
        )

    stale_status, stale_errors = _source_staleness(
        parsed_json[f"{EXPECTED_ROOT}source-manifest.json"],
        parsed_json[f"{EXPECTED_ROOT}stale-if.json"],
        preflight,
    )
    if stale_errors:
        return _base_result(
            stale_status,
            generated_at,
            input_kind,
            errors=stale_errors,
            checks=_checks("source-staleness", stale_status),
            preflight=preflight,
            entries=entries,
            sources=_source_snapshot(parsed_json[f"{EXPECTED_ROOT}source-manifest.json"]),
        )

    checks.extend(_checks("authoring-pack-review", "pass"))
    pack_digest = _pack_content_digest(files)
    return _base_result(
        "pass",
        generated_at,
        input_kind,
        warnings=warnings,
        deferred=deferred,
        checks=checks,
        preflight=preflight,
        entries=entries,
        pack_digest=pack_digest,
        sources=_source_snapshot(parsed_json[f"{EXPECTED_ROOT}source-manifest.json"]),
    )


def _metadata_schema_errors(parsed_json: dict[str, dict[str, Any]], preflight: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    manifest = parsed_json.get(f"{EXPECTED_ROOT}manifest.json")
    if manifest is not None:
        errors.extend(_boundary_errors(manifest, "manifest"))
        if not manifest.get("pack_id"):
            errors.append("manifest.pack_id is required")
        if manifest.get("expected_zip_root") != EXPECTED_ROOT:
            errors.append("manifest.expected_zip_root mismatch")
        if manifest.get("schema_version") != "1":
            errors.append("manifest.schema_version must be 1")

    provenance = parsed_json.get(f"{EXPECTED_ROOT}provenance.json")
    if provenance is not None:
        if provenance.get("authority") != "evidence_only":
            errors.append("provenance.authority must be evidence_only")
        repository = provenance.get("repository")
        if not isinstance(repository, dict) or not repository.get("full_name") or not repository.get("requested_ref"):
            errors.append("provenance.repository must include full_name and requested_ref")
        else:
            preflight_repository = preflight.get("repository", {})
            if repository.get("full_name") != preflight_repository.get("full_name") or repository.get(
                "requested_ref"
            ) != preflight_repository.get("requested_ref"):
                errors.append("provenance.repository does not match preflight repository")
        if provenance.get("source") != "chatgpt_zip_authoring_pack":
            errors.append("provenance.source mismatch")

    source_manifest = parsed_json.get(f"{EXPECTED_ROOT}source-manifest.json")
    if source_manifest is not None:
        sources = source_manifest.get("sources")
        if not isinstance(sources, list) or not sources:
            errors.append("source-manifest.sources must be a non-empty array")
        else:
            for index, source in enumerate(sources):
                if not isinstance(source, dict):
                    errors.append(f"source-manifest.sources[{index}] must be an object")
                    continue
                if _repo_relative_path_error(source.get("path", "")):
                    errors.append(f"source-manifest.sources[{index}].path is invalid")
                if not isinstance(source.get("sha256"), str) or not HEX64.match(source["sha256"]):
                    errors.append(f"source-manifest.sources[{index}].sha256 is invalid")
                if not source.get("role"):
                    errors.append(f"source-manifest.sources[{index}].role is required")

    stale_if = parsed_json.get(f"{EXPECTED_ROOT}stale-if.json")
    if stale_if is not None:
        errors.extend(_stale_if_schema_errors(stale_if, "stale-if.stale_if"))

    adoption_map = parsed_json.get(f"{EXPECTED_ROOT}adoption/adoption-map.json")
    if adoption_map is not None:
        items = adoption_map.get("items")
        if not isinstance(items, list):
            errors.append("adoption-map.items must be an array")
        else:
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    errors.append(f"adoption-map.items[{index}] must be an object")
                    continue
                if not isinstance(item.get("source_path"), str) or _pack_path_error(
                    item["source_path"],
                    expected_root="",
                    allow_without_root=True,
                ):
                    errors.append(f"adoption-map.items[{index}].source_path is invalid")
                if item.get("adoption_status") != "unreviewed":
                    errors.append(f"adoption-map.items[{index}].adoption_status must be unreviewed")
                if not isinstance(item.get("required_local_validation"), list):
                    errors.append(f"adoption-map.items[{index}].required_local_validation must be an array")

    safe_constraints = preflight.get("safe_output_constraints", {})
    expected_root = safe_constraints.get("expected_zip_root")
    if expected_root != EXPECTED_ROOT:
        errors.append("preflight expected_zip_root mismatch")
    return errors


def _metadata_safety_errors(parsed_json: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    source_manifest = parsed_json.get(f"{EXPECTED_ROOT}source-manifest.json")
    if source_manifest is not None:
        sources = source_manifest.get("sources", [])
        if not isinstance(sources, list):
            sources = []
        for index, source in enumerate(sources):
            if not isinstance(source, dict):
                continue
            path = source.get("path")
            if isinstance(path, str) and _repo_relative_path_error(path):
                errors.append(f"source-manifest.sources[{index}].path is unsafe")

    stale_if = parsed_json.get(f"{EXPECTED_ROOT}stale-if.json")
    if stale_if is not None:
        conditions = stale_if.get("stale_if", [])
        if not isinstance(conditions, list):
            conditions = []
        for condition_index, condition in enumerate(conditions):
            if not isinstance(condition, dict):
                continue
            source_paths = condition.get("source_paths", [])
            if not isinstance(source_paths, list):
                source_paths = []
            for source_index, path in enumerate(source_paths):
                if isinstance(path, str) and _repo_relative_path_error(path):
                    errors.append(f"stale-if.stale_if[{condition_index}].source_paths[{source_index}] is unsafe")
    return errors


def _stale_if_schema_errors(stale_if: dict[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    conditions = stale_if.get("stale_if")
    if not isinstance(conditions, list):
        return [f"{label} must be an array"]
    for condition_index, condition in enumerate(conditions):
        if not isinstance(condition, dict):
            errors.append(f"{label}[{condition_index}] must be an object")
            continue
        if condition.get("kind") != "source_hash_changed":
            errors.append(f"{label}[{condition_index}].kind must be source_hash_changed")
        source_paths = condition.get("source_paths")
        if not isinstance(source_paths, list) or not source_paths:
            errors.append(f"{label}[{condition_index}].source_paths must be a non-empty array")
            continue
        for source_index, path in enumerate(source_paths):
            if not isinstance(path, str) or _repo_relative_path_error(path):
                errors.append(f"{label}[{condition_index}].source_paths[{source_index}] is invalid")
    return errors


def _boundary_errors(payload: dict[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    for key, expected in AUTHORITY_BOUNDARY.items():
        if payload.get(key) != expected:
            errors.append(f"{label}.{key} boundary mismatch")
    return errors


def _source_staleness(
    source_manifest: dict[str, Any],
    pack_stale_if: dict[str, Any],
    preflight: dict[str, Any],
) -> tuple[str, list[str]]:
    errors: list[str] = []
    blocked = False
    expected_sources = {
        source["path"]: source["sha256"]
        for source in preflight.get("sources", [])
        if isinstance(source, dict) and isinstance(source.get("path"), str)
    }
    pack_sources = {
        source["path"]: source["sha256"]
        for source in source_manifest.get("sources", [])
        if isinstance(source, dict) and isinstance(source.get("path"), str)
    }
    for path, expected_sha in expected_sources.items():
        actual_sha = pack_sources.get(path)
        if actual_sha is None:
            errors.append(f"source missing from pack manifest: {path}")
        elif actual_sha != expected_sha:
            errors.append(f"source hash mismatch: {path}")

    repo_root = _git_root()
    stale_conditions = _source_hash_changed_conditions(preflight.get("stale_if", [])) + _source_hash_changed_conditions(
        pack_stale_if.get("stale_if", [])
    )
    if repo_root is None:
        if stale_conditions:
            errors.append("repo root could not be observed")
            return "blocked", errors
        return "stale", errors
    for condition in stale_conditions:
        for path in condition.get("source_paths", []):
            if not isinstance(path, str) or _repo_relative_path_error(path):
                errors.append("stale_if source path is invalid")
                continue
            source_path = repo_root / path
            try:
                current_sha = _sha256(source_path)
            except OSError:
                errors.append(f"source could not be read: {path}")
                blocked = True
                continue
            expected_sha = expected_sources.get(path)
            if expected_sha is None:
                errors.append(f"stale_if source missing from preflight snapshot: {path}")
            elif current_sha != expected_sha:
                errors.append(f"stale_if source hash changed: {path}")
    return ("blocked" if blocked else "stale"), errors


def _source_hash_changed_conditions(stale_if: Any) -> list[dict[str, Any]]:
    if not isinstance(stale_if, list):
        return []
    return [
        condition
        for condition in stale_if
        if isinstance(condition, dict) and condition.get("kind") == "source_hash_changed"
    ]


def _unsafe_claim_errors(files: dict[str, str], preflight: dict[str, Any]) -> list[str]:
    forbidden_claims = _forbidden_claims(preflight)
    errors: list[str] = []
    for path, text in files.items():
        normalized = _normalize_claim_text(text)
        if any(claim in normalized for claim in forbidden_claims):
            errors.append(f"unsafe authority claim rejected: {_pack_relative(path)}")
    return sorted(set(errors))


def _forbidden_claims(preflight: dict[str, Any]) -> tuple[str, ...]:
    raw_claims = preflight.get("safe_output_constraints", {}).get("forbidden_claims", [])
    claims = [claim for claim in raw_claims if isinstance(claim, str) and claim]
    return tuple(dict.fromkeys(_normalize_claim_text(claim) for claim in (*DEFAULT_FORBIDDEN_CLAIMS, *claims)))


def _base_result(
    status: str,
    generated_at: str,
    input_kind: str,
    *,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
    deferred: list[str] | None = None,
    checks: list[dict[str, str]] | None = None,
    preflight: dict[str, Any] | None = None,
    entries: list[dict[str, Any]] | None = None,
    pack_digest: dict[str, Any] | None = None,
    sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    trace = _result_trace(preflight)
    return {
        **AUTHORITY_BOUNDARY,
        "status": status,
        "generated_at": generated_at,
        "input_kind": input_kind,
        "trace": trace,
        "preflight": _preflight_snapshot(preflight or {}),
        "entries": entries or [],
        "pack_digest": pack_digest or {},
        "checks": checks or [],
        "errors": _safe_diagnostic_value(errors or []),
        "warnings": _safe_diagnostic_value(warnings or []),
        "deferred": _safe_diagnostic_value(deferred or []),
        "sources": sources or [],
        "status_taxonomy": _status_taxonomy(),
    }


def _result_trace(preflight: dict[str, Any] | None) -> dict[str, Any]:
    if preflight:
        trace = preflight.get("trace")
        if isinstance(trace, dict):
            return _safe_diagnostic_value(trace)
    return _default_trace()


def _default_trace() -> dict[str, Any]:
    return {
        "issue_id": "iss-00285",
        "parent_epic": "epic-00283",
        "requirements": ["E-RQ-004", "E-RQ-005"],
        "acceptance": ["E-AC-002", "E-AC-003", "E-AC-004"],
    }


def _detect_input_kind(input_path: Path, input_kind: str) -> str:
    if input_kind in {"zip", "tree"}:
        return input_kind
    if input_path.is_dir():
        return "tree"
    if input_path.suffix.lower() == ".zip":
        return "zip"
    return "unknown"


def _entry_observation(info: ZipInfo) -> dict[str, Any]:
    return {
        "path": _safe_diagnostic_string(info.filename),
        "size_bytes": info.file_size,
        "compress_size": info.compress_size,
        "is_dir": info.is_dir(),
        "mode": _zip_unix_mode(info),
    }


def _zip_unix_mode(info: ZipInfo) -> int:
    return (info.external_attr >> 16) & 0xFFFF


def _zip_type_error(mode: int) -> str | None:
    if mode == 0:
        return None
    file_type = stat.S_IFMT(mode)
    if file_type in {0, stat.S_IFREG, stat.S_IFDIR}:
        if mode & 0o111 and file_type == stat.S_IFREG:
            return "executable zip entry rejected"
        return None
    return "unsafe file type rejected"


def _pack_path_error(path_value: str, *, expected_root: str, allow_without_root: bool = False) -> str | None:
    if not isinstance(path_value, str) or not path_value:
        return "path must be a non-empty string"
    if "\x00" in path_value:
        return "NUL byte is not allowed"
    if _has_control_char(path_value):
        return "control characters are not allowed"
    if "\\" in path_value or re.match(r"^[A-Za-z]:", path_value):
        return "absolute or host-local paths are not allowed"
    if path_value.startswith("/"):
        return "absolute paths are not allowed"
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
    if not allow_without_root and expected_root and not path_value.startswith(expected_root):
        return "expected zip root mismatch"
    return None


def _normalize_pack_path(path_value: str) -> str:
    return PurePosixPath(path_value).as_posix().rstrip("/")


def _repo_relative_path_error(path_value: Any) -> str | None:
    if not isinstance(path_value, str) or not path_value:
        return "path must be a non-empty string"
    if "\x00" in path_value or _has_control_char(path_value):
        return "control characters are not allowed"
    if "\\" in path_value or re.match(r"^[A-Za-z]:", path_value) or path_value.startswith("/"):
        return "absolute or host-local paths are not allowed"
    raw_path = Path(path_value)
    if any(part == ".." for part in raw_path.parts):
        return "parent traversal is not allowed"
    lowered_parts = tuple(part.lower() for part in raw_path.parts)
    if any(marker in part for marker in SECRET_PATH_MARKERS for part in lowered_parts):
        return "secret-looking paths are not allowed"
    return None


def _file_suffix_error(path_value: str) -> str | None:
    lowered = path_value.lower()
    if lowered.endswith(NESTED_ARCHIVE_SUFFIXES):
        return "nested archive rejected"
    suffix = PurePosixPath(path_value).suffix.lower()
    if suffix and suffix not in ALLOWED_TEXT_SUFFIXES:
        return "unsupported file type rejected"
    return None


def _text_payload_error(_path_value: str, data: bytes) -> str | None:
    if len(data) > MAX_FILE_SIZE:
        return "file size exceeds limit"
    if b"\x00" in data:
        return "binary payload rejected"
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return "binary payload rejected"
    lowered = text.lower()
    if "begin private key" in lowered or "openssh private key" in lowered:
        return "secret-looking payload rejected"
    unsafe_text = _unsafe_text_error(text)
    if unsafe_text:
        return unsafe_text
    return None


def _safe_extract_zip(input_path: Path, extract_dir: Path, entries: list[dict[str, Any]]) -> list[str]:
    try:
        if extract_dir.is_symlink():
            return ["extract_dir must be a real directory; safe extraction skipped"]
        if extract_dir.exists():
            if not extract_dir.is_dir():
                return ["extract_dir must be a real directory; safe extraction skipped"]
            if any(extract_dir.iterdir()):
                return ["extract_dir is not empty; safe extraction skipped"]
        else:
            extract_dir.mkdir(parents=True)
        with ZipFile(input_path) as archive:
            for entry in entries:
                if entry.get("is_dir"):
                    continue
                target = extract_dir / entry["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(entry["path"]))
    except OSError:
        return ["safe extraction failed"]
    return []


def _prepare_output_dir(output_dir: Path) -> str | None:
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
            return "output_dir contains non-review files; choose an empty or review-owned directory"
    except OSError:
        return "output_dir could not be prepared"
    return None


def _tree_root(input_path: Path) -> Path:
    if input_path.name == EXPECTED_ROOT.rstrip("/"):
        return input_path
    child = input_path / EXPECTED_ROOT.rstrip("/")
    if child.is_dir() and not child.is_symlink():
        return child
    return input_path


def _expected_root(preflight: dict[str, Any]) -> str:
    value = preflight.get("safe_output_constraints", {}).get("expected_zip_root")
    return value if isinstance(value, str) and value else EXPECTED_ROOT


def _source_snapshot(source_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for source in source_manifest.get("sources", []):
        if not isinstance(source, dict):
            continue
        sources.append({
            "path": _safe_diagnostic_value(source.get("path")),
            "sha256": source.get("sha256"),
            "role": _safe_diagnostic_value(source.get("role")),
        })
    return sources


def _pack_content_digest(files: dict[str, str]) -> dict[str, Any]:
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(files[path].encode("utf-8"))
        digest.update(b"\0")
    return {
        "algorithm": "sha256",
        "content_sha256": digest.hexdigest(),
        "file_count": len(files),
    }


def _preflight_snapshot(preflight: dict[str, Any]) -> dict[str, Any]:
    if not preflight:
        return {}
    return {
        "status": _safe_diagnostic_value(preflight.get("status")),
        "repository": _safe_diagnostic_value(preflight.get("repository", {})),
        "trace": _trace_snapshot(preflight.get("trace")),
        "source_count": len(preflight.get("sources", [])) if isinstance(preflight.get("sources"), list) else 0,
        "safe_output_constraints": _safe_diagnostic_value(preflight.get("safe_output_constraints", {})),
    }


def _trace_snapshot(value: Any) -> dict[str, Any]:
    if value is None:
        return _default_trace()
    if not isinstance(value, dict) or _optional_trace_errors(value):
        return {"invalid": True}
    return _safe_diagnostic_value(value)


def _summary_markdown(result: dict[str, Any]) -> str:
    errors = "\n".join(f"- {error}" for error in result.get("errors", [])) or "- none"
    warnings = "\n".join(f"- {warning}" for warning in result.get("warnings", [])) or "- none"
    deferred = "\n".join(f"- {item}" for item in result.get("deferred", [])) or "- none"
    return f"""# Authoring pack validation summary

Status: `{result["status"]}`

Authority:
- authority: evidence_only
- adoption_status: unreviewed
- bundle_generation_not_promotion: true

Errors:
{errors}

Warnings:
{warnings}

Deferred:
{deferred}
"""


def _status_taxonomy() -> dict[str, str]:
    return {
        "pass": "Validation passed; adoption remains unreviewed.",
        "fail": "Input shape, schema, expected root, or required metadata is invalid.",
        "blocked": "Required local observation or filesystem operation is unavailable.",
        "stale": "Preflight, source, or stale_if snapshot no longer matches.",
        "rejected": "A safety boundary was violated.",
        "deferred": "Recognized later-stage responsibility; never treated as pass.",
        "unreviewed": "Artifact adoption state, not a validator execution status.",
    }


def _checks(name: str, status: str) -> list[dict[str, str]]:
    return [{"name": name, "status": status}]


def _pack_relative(path_value: str) -> str:
    if path_value.startswith(EXPECTED_ROOT):
        return path_value[len(EXPECTED_ROOT) :]
    return path_value


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
    ):
        return "<redacted>"
    return value


def _unsafe_text_error(value: str) -> str | None:
    normalized = _normalize_claim_text(value)
    if any(claim in normalized for claim in _forbidden_claims({"safe_output_constraints": {"forbidden_claims": []}})):
        return "unsafe authority claim rejected"
    lowered = value.lower()
    if (
        any(marker in value for marker in HOST_PATH_MARKERS)
        or _looks_like_unsafe_path(value)
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


def _looks_like_unsafe_path(value: str) -> bool:
    parts = PurePosixPath(value).parts
    return any(part == ".." or part.startswith(".") for part in parts)


def _display_path(path: Path) -> str:
    return _safe_diagnostic_string(path.name or ".")


def _normalize_claim_text(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def _has_control_char(value: str) -> bool:
    return any(ord(character) < 32 for character in value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_root() -> Path | None:
    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
