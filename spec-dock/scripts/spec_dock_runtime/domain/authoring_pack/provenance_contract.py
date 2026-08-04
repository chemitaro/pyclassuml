from __future__ import annotations

from typing import Any


def provenance_state_findings(payload: dict[str, Any]) -> tuple[str, ...]:
    findings: list[str] = []
    evidence_mode = payload.get("evidence_mode")
    sync_state = payload.get("sync_state")
    github_sync = payload.get("github_sync")
    if evidence_mode == "github-synced":
        if github_sync != "verified":
            findings.append("provenance_github_sync_not_verified")
        if sync_state != "synced":
            findings.append("provenance_sync_state_not_synced")
    elif evidence_mode == "local-context":
        if github_sync != "not_verified":
            findings.append("provenance_github_sync_not_not_verified")
        if sync_state != "local_context":
            findings.append("provenance_sync_state_not_local_context")
        if not isinstance(payload.get("unsynced_reason"), str) or not payload["unsynced_reason"].strip():
            findings.append("provenance_missing_unsynced_reason")
        provided = payload.get("provided_context_paths")
        diff_summary = payload.get("diff_summary")
        has_paths = isinstance(provided, list) and any(isinstance(item, str) and item.strip() for item in provided)
        has_diff = isinstance(diff_summary, str) and bool(diff_summary.strip())
        if not has_paths and not has_diff:
            findings.append("provenance_missing_context_provenance")
    else:
        findings.append(f"unsupported_provenance_evidence_mode:{evidence_mode}")
    return tuple(findings)
