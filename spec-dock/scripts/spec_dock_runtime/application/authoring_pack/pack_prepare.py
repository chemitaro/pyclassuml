from __future__ import annotations

import contextlib
import hashlib
import json
from pathlib import Path
from typing import Any

from spec_dock_runtime.domain.authoring_pack.authority_boundary import is_credential_like_path
from spec_dock_runtime.domain.authoring_pack.preflight_contract import RECEIPT_KIND, receipt_digest_value
from spec_dock_runtime.domain.authoring_pack.prompt_pack_contract import (
    ADOPTION_STATUS,
    AUTHORITY,
    BUNDLE_GENERATION_NOT_PROMOTION,
    EXPECTED_OUTPUT_ROOT,
    FORBIDDEN_ACHIEVED_CLAIM_KEYS,
    FORBIDDEN_AUTHORITY_CLAIMS,
    FORBIDDEN_PAYLOADS,
    PROMPT_PACK_FILES,
    REQUIRED_METADATA,
    PromptPackPrepareRequest,
    PromptPackPrepareResult,
    authority_boundary,
    safe_output_constraints,
)
from spec_dock_runtime.domain.authoring_pack.provenance_contract import provenance_state_findings


def prepare_prompt_pack(request: PromptPackPrepareRequest) -> PromptPackPrepareResult:
    try:
        preflight = _read_json(request.preflight_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return _result(
            request,
            status="fail",
            preflight={},
            blockers=("preflight_unreadable",),
            remediation=(f"provide a readable preflight JSON file: {error}",),
        )

    unsafe_output_dir = _unsafe_output_dir_blockers(request.output_dir)
    if unsafe_output_dir:
        return _result(
            request,
            status="rejected",
            preflight=preflight,
            blockers=tuple(unsafe_output_dir),
            remediation=("remove symlinked prompt pack output directories before preparing the pack",),
        )

    blockers = [*_preflight_receipt_blockers(preflight), *_required_preflight_blockers(preflight)]
    if blockers:
        result = _result(
            request,
            status="fail",
            preflight=preflight,
            blockers=tuple(blockers),
            remediation=("regenerate authoring preflight evidence before preparing a prompt pack",),
        )
        unsafe_diagnostics = _unsafe_diagnostics_entry_blockers(request.output_dir)
        if unsafe_diagnostics:
            return _rejected_unsafe_diagnostics_result(request, preflight, unsafe_diagnostics)
        _write_diagnostics(request.output_dir, result)
        return result

    rejected = _rejection_blockers(request, preflight)
    if rejected:
        return _result(
            request,
            status="rejected",
            preflight=preflight,
            blockers=tuple(rejected),
            remediation=("remove unsafe output targets or achieved authority claims",),
        )

    preflight_status = str(preflight["status"])
    if preflight_status != "pass":
        status = preflight_status if preflight_status in {"blocked", "stale"} else "blocked"
        result = _result(
            request,
            status=status,  # type: ignore[arg-type]
            preflight=preflight,
            blockers=_string_tuple(preflight.get("blockers")) or (f"preflight_{status}",),
            remediation=_string_tuple(preflight.get("remediation"))
            or ("rerun or reconcile authoring preflight before ChatGPT invocation",),
        )
        unsafe_diagnostics = _unsafe_diagnostics_entry_blockers(request.output_dir)
        if unsafe_diagnostics:
            return _rejected_unsafe_diagnostics_result(request, preflight, unsafe_diagnostics)
        _write_diagnostics(request.output_dir, result)
        return result

    unsafe_entries = _unsafe_output_entry_blockers(request.output_dir)
    if unsafe_entries:
        return _result(
            request,
            status="rejected",
            preflight=preflight,
            blockers=tuple(unsafe_entries),
            remediation=("remove symlink or non-regular prompt pack output entries before preparing the pack",),
        )

    output_dir = request.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        files = _pack_files(request, preflight)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        result = _result(
            request,
            status="fail",
            preflight=preflight,
            blockers=("pack_input_unreadable",),
            remediation=(f"provide readable JSON object inputs for pack prepare: {error}",),
        )
        unsafe_diagnostics = _unsafe_diagnostics_entry_blockers(request.output_dir)
        if unsafe_diagnostics:
            return _rejected_unsafe_diagnostics_result(request, preflight, unsafe_diagnostics)
        _write_diagnostics(request.output_dir, result)
        return result
    for relative_path in PROMPT_PACK_FILES:
        path = output_dir / relative_path
        content = files[relative_path]
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")

    return _result(
        request,
        status="pass",
        preflight=preflight,
        blockers=(),
        remediation=(),
    )


def _pack_files(request: PromptPackPrepareRequest, preflight: dict[str, Any]) -> dict[str, str | bytes]:
    provenance = _provenance(preflight)
    source_manifest = _source_manifest_payload(request, preflight)
    stale_if = _stale_if_payload(request, preflight)
    manifest = {
        "schema_version": 1,
        "generated_by": "spec-dock authoring pack prepare",
        "mode": request.mode,
        "expected_output_root": EXPECTED_OUTPUT_ROOT,
        "required_metadata": list(REQUIRED_METADATA),
        "files": [path for path in PROMPT_PACK_FILES if path != ".specdock-authoring-pack"],
        **authority_boundary(),
    }
    constraints = safe_output_constraints()
    return {
        ".specdock-authoring-pack": b"",
        "manifest.json": _json(manifest),
        "provenance.json": _json(provenance),
        "source-manifest.json": _json(source_manifest),
        "stale-if.json": _json(stale_if),
        "safe-output-constraints.md": _constraints_markdown(constraints),
        "chatgpt-use-prompt.md": _prompt_markdown(request, provenance, constraints),
        "expected-output-contract.md": _expected_output_contract_markdown(constraints),
    }


def _provenance(preflight: dict[str, Any]) -> dict[str, object]:
    payload: dict[str, object] = {
        "evidence_mode": preflight.get("evidence_mode"),
        "sync_state": preflight.get("sync_state"),
        "github_sync": preflight.get("github_sync"),
        "requested_ref": preflight.get("requested_ref"),
        "effective_ref": preflight.get("effective_ref"),
        "local_head": preflight.get("local_head"),
        "remote_head": preflight.get("remote_head"),
        "source_manifest_hash": preflight.get("source_manifest_hash"),
        "preflight_receipt": _preflight_receipt_binding(preflight),
        **authority_boundary(),
    }
    if preflight.get("evidence_mode") == "local-context":
        payload.update({
            "github_sync": "not_verified",
            "sync_state": "local_context",
            "provided_context_paths": list(_string_tuple(preflight.get("provided_context_paths"))),
            "diff_summary": preflight.get("diff_summary"),
            "unsynced_reason": preflight.get("unsynced_reason"),
            "adoption_requires": "explicit_eal_disposition",
        })
    return payload


def _source_manifest_payload(request: PromptPackPrepareRequest, preflight: dict[str, Any]) -> dict[str, object]:
    if request.source_manifest_path is not None:
        return _filtered_source_manifest_payload(_read_json(request.source_manifest_path))
    source_hashes = _filtered_source_hashes(dict(preflight.get("source_hashes") or {}))
    source_paths = [path for path in _string_tuple(preflight.get("source_paths")) if not _is_cache_path(path)]
    return {
        "source_paths": source_paths,
        "source_hashes": source_hashes,
        "source_manifest_hash": _manifest_hash(source_hashes),
    }


def _filtered_source_manifest_payload(payload: dict[str, Any]) -> dict[str, object]:
    source_paths = [path for path in _string_tuple(payload.get("source_paths")) if not _is_cache_path(path)]
    source_hashes = _filtered_source_hashes(dict(payload.get("source_hashes") or {}))
    return {
        "source_paths": source_paths,
        "source_hashes": source_hashes,
        "source_manifest_hash": _manifest_hash(source_hashes),
    }


def _filtered_source_hashes(source_hashes: dict[str, object]) -> dict[str, object]:
    return {path: value for path, value in source_hashes.items() if not _is_cache_path(path)}


def _is_cache_path(path: str) -> bool:
    parts = Path(path).parts
    return "__pycache__" in parts or Path(path).suffix in {".pyc", ".pyo"}


def _stale_if_payload(request: PromptPackPrepareRequest, preflight: dict[str, Any]) -> dict[str, object]:
    if request.stale_if_path is not None:
        payload: dict[str, object] = _read_json(request.stale_if_path)
    else:
        payload = {
            "local_head_changes": preflight.get("local_head"),
            "remote_head_changes": preflight.get("remote_head"),
            "source_manifest_hash_changes": preflight.get("source_manifest_hash"),
            "github_sync_changes": preflight.get("github_sync"),
            "evidence_mode_changes": preflight.get("evidence_mode"),
        }
    payload.update(_stale_if_receipt_binding(preflight))
    return payload


def _preflight_receipt_blockers(preflight: dict[str, Any]) -> list[str]:
    if "schema_version" not in preflight:
        if any(key in preflight for key in ("receipt_kind", "receipt_digest", "fetch", "freshness")):
            return ["preflight_receipt_schema_missing"]
        return []

    blockers: list[str] = []
    if type(preflight.get("schema_version")) is not int or preflight.get("schema_version") != 1:
        blockers.append("preflight_receipt_schema_unsupported")
    if preflight.get("receipt_kind") != RECEIPT_KIND:
        blockers.append("preflight_receipt_kind_mismatch")

    receipt_digest = preflight.get("receipt_digest")
    if not isinstance(receipt_digest, dict):
        blockers.append("preflight_receipt_digest_missing")
    else:
        if receipt_digest.get("algorithm") != "sha256":
            blockers.append("preflight_receipt_digest_algorithm_unsupported")
        value = receipt_digest.get("value")
        if not isinstance(value, str) or value != receipt_digest_value(preflight):
            blockers.append("preflight_receipt_digest_mismatch")

    if preflight.get("status") != "pass":
        return blockers

    receipt_blockers = preflight.get("blockers")
    if not isinstance(receipt_blockers, list):
        blockers.append("preflight_receipt_blockers_invalid")
    elif receipt_blockers:
        blockers.append("preflight_receipt_pass_has_blockers")
    evidence_mode = preflight.get("evidence_mode")
    fetch = preflight.get("fetch")
    freshness = preflight.get("freshness")
    if not isinstance(fetch, dict):
        blockers.append("preflight_receipt_fetch_missing")
        fetch = {}
    if not isinstance(freshness, dict):
        blockers.append("preflight_receipt_freshness_missing")
        freshness = {}

    if evidence_mode == "github-synced":
        if preflight.get("sync_state") != "synced":
            blockers.append("preflight_receipt_sync_state_not_synced")
        if preflight.get("github_sync") != "verified":
            blockers.append("preflight_receipt_github_sync_not_verified")
        if fetch.get("status") != "success":
            blockers.append("preflight_receipt_fetch_not_success")
        if freshness.get("remote_head_disposition") != "fetched_remote_tracking_ref":
            blockers.append("preflight_receipt_remote_head_not_fetched")
        if freshness.get("concurrent_change_check") != "stable":
            blockers.append("preflight_receipt_concurrent_change_not_stable")
        snapshot_id = freshness.get("snapshot_id")
        final_snapshot_id = freshness.get("final_guard_snapshot_id")
        if not isinstance(snapshot_id, str) or not snapshot_id:
            blockers.append("preflight_receipt_snapshot_missing")
        if final_snapshot_id != snapshot_id:
            blockers.append("preflight_receipt_final_guard_mismatch")
        if not isinstance(freshness.get("observed_at"), str) or not freshness.get("observed_at"):
            blockers.append("preflight_receipt_observed_at_missing")
    elif evidence_mode == "local-context":
        if preflight.get("sync_state") != "local_context":
            blockers.append("preflight_receipt_sync_state_not_local_context")
        if preflight.get("github_sync") != "not_verified":
            blockers.append("preflight_receipt_local_context_github_sync_invalid")
        if fetch.get("status") != "not_applicable":
            blockers.append("preflight_receipt_local_context_fetch_invalid")
        if freshness.get("remote_head_disposition") != "not_applicable":
            blockers.append("preflight_receipt_local_context_remote_disposition_invalid")
        if freshness.get("concurrent_change_check") != "not_applicable":
            blockers.append("preflight_receipt_local_context_guard_invalid")
    else:
        blockers.append("preflight_receipt_evidence_mode_unsupported")
    return blockers


def _preflight_receipt_binding(preflight: dict[str, Any]) -> dict[str, object]:
    if "schema_version" not in preflight:
        return {
            "format": "legacy_unversioned",
            "current_repository_revalidated": False,
        }

    receipt_digest = preflight.get("receipt_digest")
    freshness = preflight.get("freshness")
    payload: dict[str, object] = {
        "format": "versioned",
        "schema_version": preflight.get("schema_version"),
        "receipt_kind": preflight.get("receipt_kind"),
        "receipt_digest": dict(receipt_digest) if isinstance(receipt_digest, dict) else {},
        "current_repository_revalidated": False,
    }
    if isinstance(freshness, dict):
        for key in ("snapshot_id", "observed_at"):
            value = freshness.get(key)
            if isinstance(value, str) and value:
                payload[key] = value
    return payload


def _stale_if_receipt_binding(preflight: dict[str, Any]) -> dict[str, object]:
    binding = _preflight_receipt_binding(preflight)
    payload: dict[str, object] = {
        "preflight_receipt_format": binding["format"],
        "current_repository_revalidated": False,
    }
    if binding["format"] == "versioned":
        receipt_digest = binding.get("receipt_digest")
        if isinstance(receipt_digest, dict) and isinstance(receipt_digest.get("value"), str):
            payload["preflight_receipt_digest_changes"] = receipt_digest["value"]
        if isinstance(binding.get("snapshot_id"), str):
            payload["preflight_snapshot_id_changes"] = binding["snapshot_id"]
        if isinstance(binding.get("observed_at"), str):
            payload["preflight_observed_at"] = binding["observed_at"]
    return payload


def _required_preflight_blockers(preflight: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for key in ("status", "evidence_mode", "sync_state", "github_sync", "source_manifest_hash"):
        if key not in preflight:
            blockers.append(f"missing_{key}")
    source_hashes = preflight.get("source_hashes")
    if not isinstance(source_hashes, dict):
        blockers.append("missing_source_hashes")
    else:
        observed_hash = _manifest_hash(_filtered_source_hashes(dict(source_hashes)))
        if preflight.get("source_manifest_hash") != observed_hash:
            blockers.append("source_manifest_hash_mismatch")
    if preflight.get("status") == "pass":
        blockers.extend(provenance_state_findings(preflight))
    return blockers


def _rejection_blockers(request: PromptPackPrepareRequest, preflight: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if _is_canonical_output_target(request.output_dir):
        blockers.append("canonical_output_target")
    blockers.extend(_unsafe_input_path_blockers(preflight))
    if request.source_manifest_path is not None:
        with contextlib.suppress(OSError, ValueError, json.JSONDecodeError):
            blockers.extend(_unsafe_input_path_blockers(_read_json(request.source_manifest_path)))
    for key in FORBIDDEN_ACHIEVED_CLAIM_KEYS:
        if key in preflight:
            blockers.append(f"forbidden_achieved_claim:{key}")
    for value in _walk_values(preflight):
        if isinstance(value, str) and value.lower() in {claim.lower() for claim in FORBIDDEN_AUTHORITY_CLAIMS}:
            blockers.append(f"forbidden_achieved_claim_value:{value}")
    return blockers


def _unsafe_input_path_blockers(payload: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    paths: list[str] = []
    paths.extend(_string_tuple(payload.get("source_paths")))
    paths.extend(_string_tuple(payload.get("provided_context_paths")))
    source_hashes = payload.get("source_hashes")
    if isinstance(source_hashes, dict):
        paths.extend(path for path in source_hashes if isinstance(path, str))
    for path in paths:
        if _is_cache_path(path):
            continue
        if _is_unsafe_source_path(path):
            blockers.append(f"unsafe_source_path:{path}")
    blockers.extend(_unsafe_text_blockers(payload))
    return blockers


def _is_unsafe_source_path(path: str) -> bool:
    parsed = Path(path)
    return parsed.is_absolute() or ".." in parsed.parts or is_credential_like_path(path)


def _unsafe_text_blockers(payload: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for key in ("diff_summary", "unsynced_reason"):
        value = payload.get(key)
        if isinstance(value, str) and _contains_unsafe_text_path(value):
            blockers.append(f"unsafe_context_text:{key}")
    return blockers


def _contains_unsafe_text_path(value: str) -> bool:
    lowered = value.lower()
    markers = (
        "/users/",
        "/private/",
        "../",
        ".env",
        "secret",
        "credential",
        "credentials",
        "private key",
        "private_key",
        "id_rsa",
        ".pem",
        ".key",
        "token",
    )
    return any(marker in lowered for marker in markers)


def _manifest_hash(source_hashes: dict[str, object]) -> str:
    payload = json.dumps(source_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_canonical_output_target(path: Path) -> bool:
    joined = "/".join(path.absolute().parts)
    resolved_joined = "/".join(path.resolve().parts)
    return (
        "/spec-dock/active" in joined
        or "/spec-dock/initiatives/" in joined
        or joined.endswith("/spec-dock/initiatives")
        or "/spec-dock/active" in resolved_joined
        or "/spec-dock/initiatives/" in resolved_joined
        or resolved_joined.endswith("/spec-dock/initiatives")
        or joined.endswith("/.assurance.json")
        or resolved_joined.endswith("/.assurance.json")
    )


def _unsafe_output_entry_blockers(output_dir: Path) -> list[str]:
    blockers: list[str] = []
    resolved_output_dir = output_dir.resolve()
    for relative_path in PROMPT_PACK_FILES:
        path = output_dir / relative_path
        if path.is_symlink():
            blockers.append(f"unsafe_output_entry_symlink:{relative_path}")
            continue
        if path.exists() and not path.is_file():
            blockers.append(f"unsafe_output_entry_not_regular_file:{relative_path}")
            continue
        if path.exists() and path.resolve().parent != resolved_output_dir:
            blockers.append(f"unsafe_output_entry_outside_output_dir:{relative_path}")
    return blockers


def _unsafe_output_dir_blockers(output_dir: Path) -> list[str]:
    if _is_canonical_output_target(output_dir):
        return []
    absolute_path = output_dir if output_dir.is_absolute() else Path.cwd() / output_dir
    symlink_blocker = _output_path_symlink_blocker(absolute_path)
    if symlink_blocker is not None:
        return [symlink_blocker]
    if absolute_path.exists() and not absolute_path.is_dir():
        return ["unsafe_output_dir_not_directory"]
    return []


def _output_path_symlink_blocker(absolute_path: Path) -> str | None:
    trusted_anchor = Path.cwd()
    try:
        absolute_path.relative_to(trusted_anchor)
    except ValueError:
        trusted_anchor = Path(absolute_path.anchor)

    current = absolute_path
    while True:
        root = Path(current.anchor)
        if current.is_symlink() and current.parent != root:
            return "unsafe_output_dir_symlink" if current == absolute_path else "unsafe_output_parent_symlink"
        if current == trusted_anchor or current == current.parent:
            return None
        current = current.parent


def _unsafe_diagnostics_entry_blockers(output_dir: Path) -> list[str]:
    path = output_dir / "diagnostics.json"
    resolved_output_dir = output_dir.resolve()
    if path.is_symlink():
        return ["unsafe_output_entry_symlink:diagnostics.json"]
    if path.exists() and not path.is_file():
        return ["unsafe_output_entry_not_regular_file:diagnostics.json"]
    if path.exists() and path.resolve().parent != resolved_output_dir:
        return ["unsafe_output_entry_outside_output_dir:diagnostics.json"]
    return []


def _rejected_unsafe_diagnostics_result(
    request: PromptPackPrepareRequest,
    preflight: dict[str, Any],
    blockers: list[str],
) -> PromptPackPrepareResult:
    return _result(
        request,
        status="rejected",
        preflight=preflight,
        blockers=tuple(blockers),
        remediation=("remove symlink or non-regular diagnostics output entry before preparing the pack",),
    )


def _required_metadata(constraints: dict[str, object]) -> list[str]:
    value = constraints.get("required_metadata")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _constraints_markdown(constraints: dict[str, object]) -> str:
    lines = [
        "# Safe Output Constraints",
        "",
        f"- expected_zip_root: `{EXPECTED_OUTPUT_ROOT}`",
        f"- authority: `{AUTHORITY}`",
        f"- adoption_status: `{ADOPTION_STATUS}`",
        f"- bundle_generation_not_promotion: `{str(BUNDLE_GENERATION_NOT_PROMOTION).lower()}`",
        "",
        "## Required Metadata",
    ]
    lines.extend(f"- `{item}`" for item in _required_metadata(constraints))
    lines.extend(["", "## Forbidden Authority Claims"])
    lines.extend(f"- {item}" for item in FORBIDDEN_AUTHORITY_CLAIMS)
    lines.extend(["", "## Forbidden Payloads"])
    lines.extend(f"- {item}" for item in FORBIDDEN_PAYLOADS)
    lines.append("")
    return "\n".join(lines)


def _prompt_markdown(
    request: PromptPackPrepareRequest, provenance: dict[str, object], constraints: dict[str, object]
) -> str:
    del constraints
    mode_line = request.mode or "unspecified"
    provided_context_paths = provenance.get("provided_context_paths")
    if isinstance(provided_context_paths, list):
        provided_context_line = ", ".join(str(path) for path in provided_context_paths) or "none"
    else:
        provided_context_line = "none"
    return "\n".join([
        "# ChatGPT Use Prompt Pack",
        "",
        "Use the attached repository context and this prompt pack to produce a ZIP or tree rooted at `specdock-authoring-pack/`.",
        "Treat every generated file as evidence only. Do not claim canonical adoption, `.assurance.json` mutation, `authorized_profile` decision, reviewer pass, execution-ready, PR-ready, or PR delivery.",
        "",
        f"- mode: `{mode_line}`",
        f"- evidence_mode: `{provenance.get('evidence_mode')}`",
        f"- sync_state: `{provenance.get('sync_state')}`",
        f"- github_sync: `{provenance.get('github_sync')}`",
        f"- source_manifest_hash: `{provenance.get('source_manifest_hash')}`",
        f"- adoption_requires: `{provenance.get('adoption_requires')}`",
        f"- provided_context_paths: `{provided_context_line}`",
        f"- diff_summary: `{provenance.get('diff_summary')}`",
        f"- unsynced_reason: `{provenance.get('unsynced_reason')}`",
        f"- authority: `{AUTHORITY}`",
        f"- adoption_status: `{ADOPTION_STATUS}`",
        "",
        "## Forbidden Authority Claims",
        "",
        "- canonical adoption",
        "- `.assurance.json` mutation",
        "- `authorized_profile` decision",
        "- reviewer pass",
        "- execution-ready",
        "- PR-ready",
        "- PR delivery",
        "",
        "## Expected Output",
        "",
        "- Return a ZIP when possible.",
        "- The ZIP root must be `specdock-authoring-pack/`.",
        "- Include all required metadata named in `safe-output-constraints.md`.",
        "- Keep adoption candidates explicit and unreviewed.",
        "- Do not include raw transcripts, secrets, credentials, host-local absolute paths, nested archives, binaries, executables, symlinks, or path traversal entries.",
        "",
    ])


def _expected_output_contract_markdown(constraints: dict[str, object]) -> str:
    lines = [
        "# Expected Output Contract",
        "",
        "ChatGPT output must use this root:",
        "",
        "```text",
        EXPECTED_OUTPUT_ROOT,
        "  manifest.json",
        "  provenance.json",
        "  source-manifest.json",
        "  stale-if.json",
        "  safe-output-constraints.md",
        "  adoption/adoption-map.json",
        "  adoption/eal-candidates.json",
        "  summaries/",
        "  candidates/",
        "  drafts/",
        "  selected-skeleton-fill/section-fills.json",
        "```",
        "",
        "Required metadata:",
    ]
    lines.extend(f"- `{item}`" for item in _required_metadata(constraints))
    lines.append("")
    return "\n".join(lines)


def _write_diagnostics(output_dir: Path, result: PromptPackPrepareResult) -> None:
    if _is_canonical_output_target(output_dir):
        return
    output_dir.resolve().mkdir(parents=True, exist_ok=True)
    (output_dir / "diagnostics.json").write_text(_json(result.to_dict()), encoding="utf-8")


def _result(
    request: PromptPackPrepareRequest,
    *,
    status,
    preflight: dict[str, Any],
    blockers: tuple[str, ...],
    remediation: tuple[str, ...],
) -> PromptPackPrepareResult:
    return PromptPackPrepareResult(
        status=status,
        authority=AUTHORITY,
        adoption_status=ADOPTION_STATUS,
        bundle_generation_not_promotion=BUNDLE_GENERATION_NOT_PROMOTION,
        evidence_mode=preflight.get("evidence_mode"),
        sync_state=preflight.get("sync_state"),
        github_sync=preflight.get("github_sync"),
        output_dir=request.output_dir.as_posix(),
        output_root=EXPECTED_OUTPUT_ROOT,
        output_files=PROMPT_PACK_FILES if status == "pass" else (),
        source_manifest_hash=preflight.get("source_manifest_hash"),
        blockers=blockers,
        remediation=remediation,
        mode=request.mode,
    )


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("expected JSON object")
    return payload


def _json(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _walk_values(value: object):
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_values(child)
    else:
        yield value
