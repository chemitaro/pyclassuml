#!/usr/bin/env python3
# mypy: ignore-errors
"""Prepare an evidence-only ChatGPT authoring prompt pack."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
from typing import Any

STATUS_EXIT_CODES = {
    "pass": 0,
    "fail": 1,
    "blocked": 2,
    "stale": 3,
    "rejected": 4,
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
    ".assurance.json updated",
    "pull request created",
    "implementation complete",
    "canonical overwrite",
    "authority: canonical",
)

SECRET_PATH_MARKERS = (
    ".env",
    "secret",
    "token",
    "credential",
    "private-key",
    "private_key",
)

PROMPT_PACK_FILES = (
    ".specdock-authoring-pack",
    "README.md",
    "preflight.json",
    "source-manifest.json",
    "stale-if.json",
    "validation-taxonomy.json",
    "safe-output-constraints.md",
    "chatgpt-use-prompt.md",
)

OWNERSHIP_MARKER = "owned-by=prepare_chatgpt_authoring_pack.py\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Repo-relative or absolute JSON config path.")
    parser.add_argument("--output-dir", required=True, help="Directory where prompt-pack files will be written.")
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    try:
        output_dir = output_dir.resolve()
    except (OSError, RuntimeError) as exc:
        _print_error("rejected", f"cannot resolve output directory: {exc.__class__.__name__}")
        return STATUS_EXIT_CODES["rejected"]
    if output_dir.exists() and not output_dir.is_dir():
        result = _base_result(
            "rejected",
            datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            {},
            errors=[f"output_dir must be a directory: {_display_path(output_dir)}"],
            write_diagnostics=False,
        )
        print(json.dumps(_cli_summary(result, output_dir), ensure_ascii=False, sort_keys=True))
        return STATUS_EXIT_CODES["rejected"]

    try:
        repo_root = _git_root()
    except RuntimeError as exc:
        result = _base_result(
            "blocked",
            datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            {},
            errors=[str(exc)],
        )
        result = _write_diagnostics_or_block(output_dir, result, allow_unknown=True)
        print(json.dumps(_cli_summary(result, output_dir), ensure_ascii=False, sort_keys=True))
        return STATUS_EXIT_CODES[result["status"]]

    if _is_inside(output_dir, repo_root):
        result = _base_result(
            "rejected",
            datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            {},
            errors=[f"output_dir must be outside repository: {_display_path(output_dir)}"],
            write_diagnostics=False,
        )
        print(json.dumps(_cli_summary(result, output_dir), ensure_ascii=False, sort_keys=True))
        return STATUS_EXIT_CODES["rejected"]

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = repo_root / config_path

    try:
        config = _load_json(config_path)
    except ValueError as exc:
        result = _base_result(
            "fail",
            datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            {},
            errors=[str(exc)],
        )
        result = _write_diagnostics_or_block(output_dir, result, allow_unknown=True)
        print(json.dumps(_cli_summary(result, output_dir), ensure_ascii=False, sort_keys=True))
        return STATUS_EXIT_CODES[result["status"]]

    result = _evaluate(config, repo_root)
    status = result["status"]
    if status == "pass":
        try:
            _write_prompt_pack(output_dir, result)
        except ValueError as exc:
            result = _base_result("blocked", result["generated_at"], config, errors=[str(exc)])
            result = _write_diagnostics_or_block(output_dir, result, allow_unknown=True)
            status = result["status"]
    elif result.get("write_diagnostics", True):
        try:
            _write_diagnostics(output_dir, result)
        except ValueError as exc:
            result = _base_result("blocked", result["generated_at"], config, errors=[str(exc)])
            result = _write_diagnostics_or_block(output_dir, result, allow_unknown=True)
            status = result["status"]

    print(json.dumps(_cli_summary(result, output_dir), ensure_ascii=False, sort_keys=True))
    return STATUS_EXIT_CODES[status]


def _evaluate(config: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    errors: list[str] = []
    warnings: list[str] = []

    required_fields = ("issue_id", "repository", "sources", "stale_if", "assurance_path", "safe_output_constraints")
    for field in required_fields:
        if field not in config:
            errors.append(f"missing required field: {field}")
    if "issue_id" in config and (not isinstance(config.get("issue_id"), str) or not config.get("issue_id")):
        errors.append("issue_id must be a non-empty string")
    repository = config.get("repository")
    if not isinstance(repository, dict):
        errors.append("repository must be an object")
        repository = {}
    else:
        for field in ("full_name", "requested_ref"):
            if not repository.get(field):
                errors.append(f"missing required field: repository.{field}")

    safe_output_constraints = config.get("safe_output_constraints")
    if not isinstance(safe_output_constraints, dict):
        errors.append("safe_output_constraints must be an object")
        safe_output_constraints = {}
    else:
        forbidden_claim_errors = _validate_forbidden_claims(safe_output_constraints)
        if forbidden_claim_errors:
            return _base_result("rejected", now, config, errors=forbidden_claim_errors)
        if safe_output_constraints.get("no_per_issue_pr", True) is not True:
            return _base_result(
                "rejected",
                now,
                config,
                errors=["safe_output_constraints.no_per_issue_pr must be true"],
            )
        forbidden_claims = _forbidden_claims(safe_output_constraints)
        expected_zip_root_error = _validate_zip_root(
            safe_output_constraints.get("expected_zip_root"),
            forbidden_claims,
        )
        if expected_zip_root_error:
            return _base_result("rejected", now, config, errors=[expected_zip_root_error])

    forbidden_claims = _forbidden_claims(safe_output_constraints)
    metadata_errors = _validate_prompt_metadata(config, forbidden_claims)
    if metadata_errors:
        return _base_result("rejected", now, config, errors=metadata_errors)

    stale_if = config.get("stale_if")
    if not isinstance(stale_if, list) or not stale_if:
        errors.append("stale_if must be a non-empty array")
    else:
        stale_if_errors = _validate_stale_if(stale_if, repo_root)
        if stale_if_errors:
            return _base_result("rejected", now, config, errors=stale_if_errors)

    assurance_path_value = config.get("assurance_path")
    if not isinstance(assurance_path_value, str) or not assurance_path_value:
        errors.append("assurance_path must be a non-empty string")

    if errors:
        return _base_result("fail", now, config, errors=errors)

    try:
        observed_ref = _git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root)
        observed_head = _git(["rev-parse", "HEAD"], repo_root)
    except RuntimeError as exc:
        return _base_result("blocked", now, config, errors=[str(exc)])

    observed_full_name = _observed_repo_full_name(repo_root)
    requested_full_name = str(repository.get("full_name", ""))
    if requested_full_name and not observed_full_name:
        return _base_result(
            "blocked",
            now,
            config,
            errors=["repository origin remote could not be observed"],
            observed_ref=observed_ref,
            observed_head=observed_head,
        )
    if observed_full_name and requested_full_name and observed_full_name != requested_full_name:
        return _base_result(
            "stale",
            now,
            config,
            errors=["repository.full_name does not match observed origin remote"],
            observed_ref=observed_ref,
            observed_head=observed_head,
            observed_full_name=observed_full_name,
        )

    requested_ref = str(repository.get("requested_ref", ""))
    if requested_ref not in {observed_ref, observed_head}:
        return _base_result(
            "stale",
            now,
            config,
            errors=["requested_ref does not match observed branch or HEAD"],
            observed_ref=observed_ref,
            observed_head=observed_head,
        )

    proposed_claims = _as_string_list(config.get("proposed_output_claims", []))
    unsafe_claims = _unsafe_claims(proposed_claims, forbidden_claims)
    if unsafe_claims:
        return _base_result(
            "rejected",
            now,
            config,
            errors=[f"unsafe output claim rejected: proposed_output_claims[{index}]" for index in unsafe_claims],
            observed_ref=observed_ref,
            observed_head=observed_head,
        )

    assurance_path = _resolve_repo_path(assurance_path_value, repo_root)
    if assurance_path["error"]:
        return _base_result(
            "blocked",
            now,
            config,
            errors=[f"invalid assurance_path: {assurance_path['error']}"],
            observed_ref=observed_ref,
            observed_head=observed_head,
        )
    try:
        assurance_snapshot = _assurance_snapshot(Path(assurance_path["resolved_path"]))
    except ValueError as exc:
        return _base_result(
            "blocked",
            now,
            config,
            errors=[str(exc)],
            observed_ref=observed_ref,
            observed_head=observed_head,
        )
    assurance_mismatches = _assurance_mismatches(config.get("expected_assurance"), assurance_snapshot)
    if assurance_mismatches:
        return _base_result(
            "stale",
            now,
            config,
            errors=assurance_mismatches,
            observed_ref=observed_ref,
            observed_head=observed_head,
            observed_full_name=observed_full_name,
            assurance_snapshot=assurance_snapshot,
        )

    source_result = _source_manifest(config.get("sources", []), repo_root, forbidden_claims)
    if source_result["rejected"]:
        return _base_result(
            "rejected",
            now,
            config,
            errors=source_result["rejected"],
            observed_ref=observed_ref,
            observed_head=observed_head,
            assurance_snapshot=assurance_snapshot,
        )
    if source_result["blocked"]:
        return _base_result(
            "blocked",
            now,
            config,
            errors=source_result["blocked"],
            observed_ref=observed_ref,
            observed_head=observed_head,
            assurance_snapshot=assurance_snapshot,
        )
    if source_result["missing"]:
        return _base_result(
            "fail",
            now,
            config,
            errors=source_result["missing"],
            observed_ref=observed_ref,
            observed_head=observed_head,
            assurance_snapshot=assurance_snapshot,
        )
    if source_result["stale"]:
        return _base_result(
            "stale",
            now,
            config,
            errors=source_result["stale"],
            observed_ref=observed_ref,
            observed_head=observed_head,
            assurance_snapshot=assurance_snapshot,
            sources=source_result["sources"],
        )

    return _base_result(
        "pass",
        now,
        config,
        warnings=warnings,
        observed_ref=observed_ref,
        observed_head=observed_head,
        observed_full_name=observed_full_name,
        assurance_snapshot=assurance_snapshot,
        sources=source_result["sources"],
    )


def _base_result(
    status: str,
    generated_at: str,
    config: dict[str, Any],
    *,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
    observed_ref: str | None = None,
    observed_head: str | None = None,
    observed_full_name: str | None = None,
    assurance_snapshot: dict[str, Any] | None = None,
    sources: list[dict[str, Any]] | None = None,
    write_diagnostics: bool = True,
) -> dict[str, Any]:
    repository = config.get("repository") if isinstance(config.get("repository"), dict) else {}
    result = {
        **AUTHORITY_BOUNDARY,
        "status": status,
        "generated_at": generated_at,
        "issue_id": _safe_diagnostic_value(config.get("issue_id")),
        "repository": _repository_snapshot(repository, observed_ref, observed_head, observed_full_name),
        "assurance_snapshot": assurance_snapshot,
        "sources": sources or [],
        "stale_if": _stale_if_snapshot(config.get("stale_if")),
        "safe_output_constraints": _safe_output_constraints_snapshot(config.get("safe_output_constraints")),
        "errors": errors or [],
        "warnings": warnings or [],
        "status_taxonomy": _status_taxonomy(),
    }
    if not write_diagnostics:
        result["write_diagnostics"] = False
    return result


def _cli_summary(result: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {"status": result["status"], "output_dir": _display_path(output_dir)}
    if result.get("errors"):
        summary["errors"] = result["errors"]
    return summary


def _source_manifest(raw_sources: Any, repo_root: Path, forbidden_claims: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(raw_sources, list):
        return {"sources": [], "missing": ["sources must be an array"], "stale": [], "rejected": [], "blocked": []}
    if not raw_sources:
        return {
            "sources": [],
            "missing": ["sources must be a non-empty array"],
            "stale": [],
            "rejected": [],
            "blocked": [],
        }

    sources: list[dict[str, Any]] = []
    missing: list[str] = []
    stale: list[str] = []
    rejected: list[str] = []
    blocked: list[str] = []

    for index, source in enumerate(raw_sources):
        if not isinstance(source, dict):
            missing.append(f"sources[{index}] must be an object")
            continue
        path_value = source.get("path")
        if not isinstance(path_value, str) or not path_value:
            missing.append(f"sources[{index}].path is required")
            continue
        resolved = _resolve_repo_path(path_value, repo_root)
        if resolved["error"]:
            rejected.append(f"sources[{index}].path rejected: {resolved['error']}")
            continue
        role = source.get("role", "source")
        if not isinstance(role, str) or not role:
            rejected.append(f"sources[{index}].role rejected: must be a non-empty string")
            continue
        if _unsafe_claims([role], forbidden_claims):
            rejected.append(f"sources[{index}].role rejected: forbidden authority claim is not allowed")
            continue
        if _safe_metadata_string(role) != role:
            rejected.append(f"sources[{index}].role rejected: unsafe text is not allowed")
            continue
        source_path = Path(resolved["resolved_path"])
        required = bool(source.get("required", True))
        if not source_path.exists():
            if required:
                missing.append(f"required source missing: {path_value}")
            continue
        if not source_path.is_file():
            rejected.append(f"source is not a file: {path_value}")
            continue

        try:
            digest = _sha256(source_path)
            text = source_path.read_text(encoding="utf-8", errors="replace")
            source_stat = source_path.stat()
        except OSError:
            blocked.append(f"source could not be read: {resolved['repo_relative_path']}")
            continue
        expected_sha = source.get("expected_sha256")
        if expected_sha and expected_sha != digest:
            stale.append(f"source hash mismatch: {path_value}")

        sources.append({
            "path": resolved["repo_relative_path"],
            "role": role,
            "required": required,
            "sha256": digest,
            "size_bytes": source_stat.st_size,
            "line_count": len(text.splitlines()),
            "stale_if_changed": bool(source.get("stale_if_changed", True)),
        })

    if not sources and not missing and not stale and not rejected and not blocked:
        missing.append("sources must include at least one existing source")

    return {"sources": sources, "missing": missing, "stale": stale, "rejected": rejected, "blocked": blocked}


def _resolve_repo_path(path_value: str, repo_root: Path) -> dict[str, str | None]:
    if "\x00" in path_value:
        return {"resolved_path": None, "repo_relative_path": None, "error": "NUL byte is not allowed"}
    if _has_control_char(path_value):
        return {"resolved_path": None, "repo_relative_path": None, "error": "control characters are not allowed"}
    if "\\" in path_value or re.match(r"^[A-Za-z]:", path_value):
        return {
            "resolved_path": None,
            "repo_relative_path": None,
            "error": "absolute or host-local paths are not allowed",
        }
    raw_path = Path(path_value)
    if raw_path.is_absolute():
        return {"resolved_path": None, "repo_relative_path": None, "error": "absolute paths are not allowed"}
    if any(part == ".." for part in raw_path.parts):
        return {"resolved_path": None, "repo_relative_path": None, "error": "parent traversal is not allowed"}
    lowered_parts = tuple(part.lower() for part in raw_path.parts)
    if any(marker in part for marker in SECRET_PATH_MARKERS for part in lowered_parts):
        return {"resolved_path": None, "repo_relative_path": None, "error": "secret-looking paths are not allowed"}
    try:
        resolved = (repo_root / raw_path).resolve()
        relative = resolved.relative_to(repo_root)
    except (OSError, ValueError):
        return {"resolved_path": None, "repo_relative_path": None, "error": "path must stay inside repository"}
    resolved_error = _repo_relative_path_error(relative.as_posix())
    if resolved_error:
        return {"resolved_path": None, "repo_relative_path": None, "error": resolved_error}
    return {"resolved_path": str(resolved), "repo_relative_path": relative.as_posix(), "error": None}


def _repo_relative_path_error(path_value: str) -> str | None:
    if "\x00" in path_value:
        return "NUL byte is not allowed"
    if _has_control_char(path_value):
        return "control characters are not allowed"
    raw_path = Path(path_value)
    if raw_path.is_absolute() or "\\" in path_value or re.match(r"^[A-Za-z]:", path_value):
        return "absolute or host-local paths are not allowed"
    if any(part == ".." for part in raw_path.parts):
        return "parent traversal is not allowed"
    lowered_parts = tuple(part.lower() for part in raw_path.parts)
    if any(marker in part for marker in SECRET_PATH_MARKERS for part in lowered_parts):
        return "secret-looking paths are not allowed"
    return None


def _assurance_snapshot(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"assurance file missing: {_display_path(path)}")
    if not path.is_file():
        raise ValueError(f"assurance path is not a file: {_display_path(path)}")
    try:
        data = _load_json(path)
    except ValueError as exc:
        raise ValueError(f"assurance file invalid: {exc}") from exc
    classification = data.get("classification")
    if classification is not None and not isinstance(classification, dict):
        raise ValueError("assurance classification must be an object")
    if classification is None:
        classification = {}
    return {
        "path": _repoish_path(path),
        "sha256": _sha256(path),
        "authorized_profile": classification.get("authorized_profile"),
        "complexity_tier": classification.get("complexity_tier"),
        "status": data.get("status"),
        "stage": data.get("stage"),
    }


def _write_prompt_pack(output_dir: Path, result: dict[str, Any]) -> None:
    _ensure_output_dir(output_dir)
    _prepare_output_dir(output_dir)
    _write_text(output_dir / ".specdock-authoring-pack", OWNERSHIP_MARKER)
    _write_json(output_dir / "preflight.json", result)
    _write_json(output_dir / "source-manifest.json", {"sources": result["sources"]})
    _write_json(output_dir / "stale-if.json", {"stale_if": result["stale_if"], "sources": _stale_source_index(result)})
    _write_json(output_dir / "validation-taxonomy.json", result["status_taxonomy"])
    _write_text(output_dir / "README.md", _readme(result))
    _write_text(output_dir / "safe-output-constraints.md", _safe_output_constraints(result))
    _write_text(output_dir / "chatgpt-use-prompt.md", _chatgpt_prompt(result))


def _write_diagnostics(output_dir: Path, result: dict[str, Any], *, allow_unknown: bool = False) -> None:
    _ensure_output_dir(output_dir)
    can_claim_ownership = _prepare_output_dir(output_dir, allow_unknown=allow_unknown)
    if can_claim_ownership:
        _write_text(output_dir / ".specdock-authoring-pack", OWNERSHIP_MARKER)
    elif (output_dir / "diagnostics.json").exists() or (output_dir / "diagnostics.json").is_symlink():
        return
    _write_json(output_dir / "diagnostics.json", result)


def _write_diagnostics_or_block(
    output_dir: Path,
    result: dict[str, Any],
    *,
    allow_unknown: bool = False,
) -> dict[str, Any]:
    try:
        _write_diagnostics(output_dir, result, allow_unknown=allow_unknown)
        return result
    except ValueError as exc:
        return _base_result(
            "blocked",
            result["generated_at"],
            {},
            errors=[str(exc)],
            write_diagnostics=False,
        )


def _ensure_output_dir(output_dir: Path) -> None:
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ValueError(f"cannot create output_dir: {exc.__class__.__name__}") from exc


def _clear_prompt_pack_files(output_dir: Path) -> None:
    for name in PROMPT_PACK_FILES:
        path = output_dir / name
        if path.is_file():
            path.unlink()


def _prepare_output_dir(output_dir: Path, *, allow_unknown: bool = False) -> bool:
    if _is_owned_output_dir(output_dir):
        try:
            for path in output_dir.iterdir():
                if path.is_file() or path.is_symlink():
                    path.unlink()
                elif path.is_dir():
                    shutil.rmtree(path)
        except OSError as exc:
            raise ValueError(f"cannot clean output_dir: {exc.__class__.__name__}") from exc
        return True

    try:
        unknown_paths = [path.name for path in output_dir.iterdir()]
    except OSError as exc:
        raise ValueError(f"cannot inspect output_dir: {exc.__class__.__name__}") from exc
    if unknown_paths and not allow_unknown:
        raise ValueError("output_dir contains non-pack files; choose an empty or pack-owned directory")
    return not unknown_paths


def _is_owned_output_dir(output_dir: Path) -> bool:
    marker = output_dir / ".specdock-authoring-pack"
    if marker.is_symlink() or not marker.is_file():
        return False
    try:
        return marker.read_text(encoding="utf-8") == OWNERSHIP_MARKER
    except OSError:
        return False


def _chatgpt_prompt(result: dict[str, Any]) -> str:
    constraints = result.get("safe_output_constraints") or {}
    expected_zip_root = constraints.get("expected_zip_root", "specdock-authoring-pack/")
    source_lines = "\n".join(f"- {source['path']} sha256={source['sha256']}" for source in result["sources"])
    return f"""# ChatGPT Use prompt pack

Context:
- Repository: {result["repository"]["full_name"]}
- Requested ref: {result["repository"]["requested_ref"]}
- Observed ref: {result["repository"]["observed_ref"]}
- Issue: {result["issue_id"]}

Authority boundary:
- authority: evidence_only
- adoption_status: unreviewed
- bundle_generation_not_promotion: true
- Do not claim reviewer approval.
- Do not update `.assurance.json`.
- Treat local assurance `authorized_profile` as the only profile authority.
- Do not create a Pull Request for this individual Issue.
- Expected ZIP root: {expected_zip_root}

Source manifest:
{source_lines}

Task:
- Generate an evidence-only authoring pack ZIP under the expected root.
- Include provenance, source manifest, stale conditions, and adoption map metadata.
- Treat every generated file as a draft candidate until local SpecDock adoption and fresh reviewer gates complete.
"""


def _safe_output_constraints(result: dict[str, Any]) -> str:
    constraints = result.get("safe_output_constraints") or {}
    forbidden_claims = constraints.get("forbidden_claims") or list(DEFAULT_FORBIDDEN_CLAIMS)
    forbidden = "\n".join(f"- {claim}" for claim in forbidden_claims)
    return f"""# Safe output constraints

The generated pack is evidence-only.

Forbidden claims:
{forbidden}

Required boundary:
- authority: evidence_only
- adoption_status: unreviewed
- bundle_generation_not_promotion: true
- expected_zip_root: {constraints.get("expected_zip_root", "specdock-authoring-pack/")}
"""


def _readme(result: dict[str, Any]) -> str:
    return f"""# Prompt pack

Status: `{result["status"]}`

This directory was generated by `prepare_chatgpt_authoring_pack.py`.

The files are evidence-only inputs for ChatGPT Use. They are not canonical SpecDock documents, reviewer pass evidence, or Pull Request delivery evidence.
"""


def _status_taxonomy() -> dict[str, str]:
    return {
        "pass": "Preflight passed and prompt-pack files were generated.",
        "fail": "Inputs are invalid or required sources are missing.",
        "blocked": "Required local observations are unavailable.",
        "stale": "A source or assurance observation no longer matches the expected snapshot.",
        "rejected": "A safety boundary was violated.",
        "deferred": "The case belongs to a later workflow stage.",
        "unreviewed": "Adoption state for generated artifacts, not a preflight status.",
    }


def _stale_source_index(result: dict[str, Any]) -> list[dict[str, str]]:
    return [{"path": source["path"], "sha256": source["sha256"]} for source in result["sources"]]


def _unsafe_claims(claims: list[str], forbidden_claims: tuple[str, ...]) -> list[int]:
    forbidden = tuple(_normalize_claim_text(claim) for claim in forbidden_claims)
    unsafe: list[int] = []
    for index, claim in enumerate(claims):
        normalized = _normalize_claim_text(claim)
        if any(forbidden_claim in normalized for forbidden_claim in forbidden):
            unsafe.append(index)
    return unsafe


def _normalize_claim_text(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def _contains_default_forbidden_claim(value: str) -> bool:
    normalized = _normalize_claim_text(value)
    return any(_normalize_claim_text(claim) in normalized for claim in DEFAULT_FORBIDDEN_CLAIMS)


def _repository_snapshot(
    repository: dict[str, Any],
    observed_ref: str | None,
    observed_head: str | None,
    observed_full_name: str | None,
) -> dict[str, Any]:
    return {
        "full_name": _safe_diagnostic_value(repository.get("full_name")),
        "observed_full_name": _safe_diagnostic_value(observed_full_name),
        "requested_ref": _safe_diagnostic_value(repository.get("requested_ref")),
        "observed_ref": _safe_diagnostic_value(observed_ref),
        "observed_head": observed_head,
    }


def _forbidden_claims(safe_output_constraints: dict[str, Any]) -> tuple[str, ...]:
    custom_claims = [
        claim
        for claim in _as_string_list(safe_output_constraints.get("forbidden_claims", []))
        if _safe_diagnostic_string(claim, redact_default_claims=False) == claim
    ]
    return tuple(
        dict.fromkeys((
            *DEFAULT_FORBIDDEN_CLAIMS,
            *custom_claims,
        ))
    )


def _validate_forbidden_claims(safe_output_constraints: dict[str, Any]) -> list[str]:
    raw_claims = safe_output_constraints.get("forbidden_claims")
    if raw_claims is None:
        return []
    if not isinstance(raw_claims, list):
        return ["safe_output_constraints.forbidden_claims must be an array"]

    errors: list[str] = []
    for index, claim in enumerate(raw_claims):
        if not isinstance(claim, str) or not claim:
            errors.append(f"safe_output_constraints.forbidden_claims[{index}] must be a non-empty string")
            continue
        if _safe_diagnostic_string(claim, redact_default_claims=False) != claim:
            errors.append(f"safe_output_constraints.forbidden_claims[{index}] rejected: unsafe text is not allowed")
    return errors


def _validate_prompt_metadata(config: dict[str, Any], forbidden_claims: tuple[str, ...]) -> list[str]:
    errors: list[str] = []
    repository = config.get("repository") if isinstance(config.get("repository"), dict) else {}
    prompt_metadata = (
        ("issue_id", config.get("issue_id")),
        ("repository.full_name", repository.get("full_name")),
        ("repository.requested_ref", repository.get("requested_ref")),
    )

    for location, value in prompt_metadata:
        if not isinstance(value, str) or not value:
            continue
        if "\x00" in value:
            errors.append(f"{location} rejected: NUL byte is not allowed")
        elif _has_control_char(value):
            errors.append(f"{location} rejected: control characters are not allowed")
        elif _safe_metadata_string(value) != value:
            errors.append(f"{location} rejected: unsafe text is not allowed")
        elif _unsafe_claims([value], forbidden_claims):
            errors.append(f"{location} rejected: forbidden authority claim is not allowed")

    return errors


def _safe_output_constraints_snapshot(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    snapshot: dict[str, Any] = {
        "forbidden_claims": list(_forbidden_claims(value)),
    }
    expected_zip_root = value.get("expected_zip_root")
    if _validate_zip_root(expected_zip_root, _forbidden_claims(value)) is None:
        snapshot["expected_zip_root"] = expected_zip_root
    snapshot["no_per_issue_pr"] = value.get("no_per_issue_pr", True)
    return snapshot


def _stale_if_snapshot(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []

    snapshot: list[Any] = []
    for condition in value:
        if not isinstance(condition, dict):
            snapshot.append("<invalid-condition>")
            continue
        sanitized: dict[str, Any] = {}
        for key, raw_value in condition.items():
            safe_key = _safe_diagnostic_string(str(key))
            if key in {"source_paths", "paths"} and isinstance(raw_value, list):
                sanitized[safe_key] = [_safe_diagnostic_path(item) for item in raw_value]
            else:
                sanitized[safe_key] = _safe_diagnostic_value(raw_value)
        snapshot.append(sanitized)
    return snapshot


def _safe_diagnostic_value(value: Any) -> Any:
    if isinstance(value, str):
        return _safe_diagnostic_string(value)
    if isinstance(value, list):
        return [_safe_diagnostic_value(item) for item in value]
    if isinstance(value, dict):
        return {_safe_diagnostic_string(str(key)): _safe_diagnostic_value(item) for key, item in value.items()}
    return value


def _safe_diagnostic_path(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return "<invalid-path>"
    raw_path = Path(value)
    lowered = value.lower()
    lowered_parts = tuple(part.lower() for part in raw_path.parts)
    if (
        _has_control_char(value)
        or raw_path.is_absolute()
        or "\\" in value
        or re.match(r"^[A-Za-z]:", value)
        or any(part == ".." for part in raw_path.parts)
        or any(marker in part for marker in SECRET_PATH_MARKERS for part in lowered_parts)
        or any(marker in value for marker in ("/Users/", "/home/", "/Volumes/", "/private/", ".oracle"))
    ):
        return "<redacted-path>"
    if (
        any(marker in lowered for marker in SECRET_PATH_MARKERS)
        or "secret" in lowered
        or "token" in lowered
        or "credential" in lowered
        or "private key" in lowered
    ):
        return "<redacted-path>"
    return value


def _safe_diagnostic_string(value: str, *, redact_default_claims: bool = True) -> str:
    lowered = value.lower()
    if (
        _has_control_char(value)
        or any(marker in value for marker in ("/Users/", "/home/", "/Volumes/", "/private/", ".oracle"))
        or "\\" in value
        or "begin private key" in lowered
        or "private key" in lowered
        or "secret" in lowered
        or "token" in lowered
        or "credential" in lowered
        or (redact_default_claims and _contains_default_forbidden_claim(value))
    ):
        return "<redacted>"
    return value


def _safe_metadata_string(value: str) -> str:
    lowered = value.lower()
    lowered_parts = tuple(part.lower() for part in Path(value).parts)
    if _safe_diagnostic_string(value) != value or any(
        marker in part for marker in SECRET_PATH_MARKERS for part in lowered_parts
    ):
        return "<redacted>"
    if any(marker in lowered for marker in SECRET_PATH_MARKERS):
        return "<redacted>"
    return value


def _assurance_mismatches(expected: Any, actual: dict[str, Any]) -> list[str]:
    if expected is None:
        return []
    if not isinstance(expected, dict):
        return ["expected_assurance must be an object"]

    comparable_fields = ("sha256", "authorized_profile", "complexity_tier", "status", "stage")
    mismatches: list[str] = []
    for field in comparable_fields:
        expected_value = expected.get(field)
        if expected_value is not None and expected_value != actual.get(field):
            mismatches.append(f"assurance snapshot mismatch: {field}")
    return mismatches


def _validate_zip_root(value: Any, forbidden_claims: tuple[str, ...]) -> str | None:
    if not isinstance(value, str) or not value:
        return "safe_output_constraints.expected_zip_root must be a non-empty string"
    if "\x00" in value:
        return "safe_output_constraints.expected_zip_root rejected: NUL byte is not allowed"
    if _has_control_char(value):
        return "safe_output_constraints.expected_zip_root rejected: control characters are not allowed"
    if _unsafe_claims([value], forbidden_claims):
        return "safe_output_constraints.expected_zip_root rejected: forbidden authority claim is not allowed"
    lowered = value.lower()
    if (
        "begin private key" in lowered
        or "private key" in lowered
        or "secret" in lowered
        or "token" in lowered
        or "credential" in lowered
    ):
        return "safe_output_constraints.expected_zip_root rejected: unsafe text is not allowed"
    if any(character.isspace() for character in value):
        return "safe_output_constraints.expected_zip_root rejected: whitespace is not allowed"
    if value.startswith(("/", "\\")) or "\\" in value or ":" in value:
        return "safe_output_constraints.expected_zip_root rejected: absolute or host-local paths are not allowed"
    if any(marker in value for marker in ("/Users/", "/home/", "/Volumes/", ".oracle")):
        return "safe_output_constraints.expected_zip_root rejected: host-local paths are not allowed"
    root = PurePosixPath(value)
    if any(part == ".." for part in root.parts):
        return "safe_output_constraints.expected_zip_root rejected: parent traversal is not allowed"
    lowered_parts = tuple(part.lower() for part in root.parts)
    if any(marker in part for marker in SECRET_PATH_MARKERS for part in lowered_parts):
        return "safe_output_constraints.expected_zip_root rejected: secret-looking paths are not allowed"
    if _safe_diagnostic_string(value) != value:
        return "safe_output_constraints.expected_zip_root rejected: unsafe text is not allowed"
    return None


def _validate_stale_if(stale_if: list[Any], repo_root: Path) -> list[str]:
    errors: list[str] = []
    for index, condition in enumerate(stale_if):
        if not isinstance(condition, dict):
            errors.append(f"stale_if[{index}] must be an object")
            continue
        for field in ("source_paths", "paths"):
            value = condition.get(field)
            if value is None:
                continue
            if not isinstance(value, list):
                errors.append(f"stale_if[{index}].{field} must be an array")
                continue
            for path_index, path_value in enumerate(value):
                if not isinstance(path_value, str) or not path_value:
                    errors.append(f"stale_if[{index}].{field}[{path_index}] must be a non-empty string")
                    continue
                resolved = _resolve_repo_path(path_value, repo_root)
                if resolved["error"]:
                    errors.append(f"stale_if[{index}].{field}[{path_index}] rejected: {resolved['error']}")
        for key, value in condition.items():
            if _safe_diagnostic_string(str(key)) != str(key):
                errors.append(f"stale_if[{index}] key rejected: unsafe text is not allowed")
            if key not in {"source_paths", "paths"}:
                errors.extend(_unsafe_metadata_errors(value, f"stale_if[{index}].{key}"))
    return errors


def _unsafe_metadata_errors(value: Any, location: str) -> list[str]:
    if isinstance(value, str):
        if _safe_diagnostic_string(value) != value:
            return [f"{location} rejected: unsafe text is not allowed"]
        return []
    if isinstance(value, list):
        errors: list[str] = []
        for index, item in enumerate(value):
            errors.extend(_unsafe_metadata_errors(item, f"{location}[{index}]"))
        return errors
    if isinstance(value, dict):
        errors: list[str] = []
        for key, item in value.items():
            safe_key = _safe_diagnostic_string(str(key))
            if safe_key != str(key):
                errors.append(f"{location} key rejected: unsafe text is not allowed")
            errors.extend(_unsafe_metadata_errors(item, f"{location}.{safe_key}"))
        return errors
    return []


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        reason = getattr(exc, "strerror", None) or exc.__class__.__name__
        raise ValueError(f"cannot read JSON: {_display_path(path)}: {reason}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"cannot parse JSON: {_display_path(path)}: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {_display_path(path)}")
    return data


def _write_json(path: Path, data: Any) -> None:
    _write_text(path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_text(path: Path, text: str) -> None:
    try:
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"cannot write output file: {path.name}: {exc.__class__.__name__}") from exc


def _has_control_char(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_root() -> Path:
    return Path(_git(["rev-parse", "--show-toplevel"], Path.cwd())).resolve()


def _git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def _observed_repo_full_name(repo_root: Path) -> str | None:
    try:
        remote_url = _git(["remote", "get-url", "origin"], repo_root)
    except RuntimeError:
        return None
    return _parse_github_full_name(remote_url)


def _parse_github_full_name(remote_url: str) -> str | None:
    patterns = (
        r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?$",
        r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$",
    )
    for pattern in patterns:
        match = re.search(pattern, remote_url)
        if match:
            return f"{match.group('owner')}/{match.group('repo')}"
    return None


def _is_inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _repoish_path(path: Path) -> str:
    try:
        repo_root = _git_root()
        return path.resolve().relative_to(repo_root).as_posix()
    except (RuntimeError, ValueError):
        return path.name


def _display_path(path: Path) -> str:
    try:
        display_path = _repoish_path(path)
    except RuntimeError:
        display_path = path.name
    return _safe_diagnostic_path(display_path)


def _print_error(status: str, message: str) -> None:
    print(json.dumps({"status": status, "errors": [message]}, ensure_ascii=False, sort_keys=True), file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
