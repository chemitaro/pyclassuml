from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spec_dock_runtime.domain.authoring_pack.preflight_contract import PreflightResult


def render_preflight_json(result: PreflightResult) -> str:
    return json.dumps(result.to_dict(), sort_keys=True)


def render_preflight_text(result: PreflightResult) -> list[str]:
    payload = result.to_dict()
    lines = ["spec-dock: authoring preflight github-sync"]
    for key in (
        "status",
        "evidence_mode",
        "sync_state",
        "authority",
        "github_sync",
        "requested_ref",
        "effective_ref",
        "local_head",
        "remote_head",
        "source_manifest_hash",
        "source_hash_mismatch_checked",
        "adoption_requires",
        "bundle_generation_not_promotion",
        "unsynced_reason",
        "diff_summary",
    ):
        lines.append(f"{key}={_format_value(payload.get(key))}")
    for path in payload["source_paths"]:
        lines.append(f"source_path={path}")
    for path, source_hash in sorted(payload["source_hashes"].items()):
        lines.append(f"source_hash={path}:{source_hash}")
    for path in payload["provided_context_paths"]:
        lines.append(f"provided_context_path={path}")
    for blocker in payload["blockers"]:
        lines.append(f"blocker={blocker}")
    for hint in payload["remediation"]:
        lines.append(f"remediation={hint}")
    fetch = payload["fetch"]
    lines.append(f"receipt_schema_version={_format_value(payload['schema_version'])}")
    lines.append(f"receipt_kind={_format_value(payload['receipt_kind'])}")
    lines.append(f"fetch_status={_format_value(fetch['status'])}")
    lines.append(f"fetch_attempt_count={len(fetch['attempts'])}")
    last_attempt = fetch["attempts"][-1] if fetch["attempts"] else {}
    lines.append(f"fetch_failure_class={_format_value(last_attempt.get('failure_class'))}")
    lines.append(f"fetch_classification_confidence={_format_value(last_attempt.get('confidence'))}")
    lines.append(f"fetch_timeout_seconds={_format_value(fetch['timeout_seconds'])}")
    repository = payload["repository"]
    if repository is not None:
        for key in (
            "normalized_origin",
            "branch",
            "local_head",
            "upstream",
            "effective_ref",
            "remote_head",
            "remote_head_disposition",
            "snapshot_id",
        ):
            lines.append(f"repository_{key}={_format_value(repository[key])}")
        for category in repository["worktree_state"]:
            lines.append(f"repository_worktree_state={_format_value(category)}")
    publication = payload["publication"]
    lines.append(f"publication_status={_format_value(publication['status'])}")
    lines.append(f"receipt_filename={_format_value(publication['filename'])}")
    return lines


def _format_value(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
