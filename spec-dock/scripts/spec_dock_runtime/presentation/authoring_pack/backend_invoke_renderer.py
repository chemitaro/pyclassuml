from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spec_dock_runtime.domain.authoring_pack.backend_invoke_contract import BackendInvokeResult


def render_backend_invoke_json(result: BackendInvokeResult) -> str:
    return json.dumps(result.to_dict(), sort_keys=True)


def render_backend_invoke_text(result: BackendInvokeResult) -> list[str]:
    payload = result.to_dict()
    lines = ["spec-dock: authoring backend invoke"]
    for key in (
        "status",
        "authority",
        "adoption_status",
        "bundle_generation_not_promotion",
        "evidence_mode",
        "sync_state",
        "github_sync",
        "backend_source",
        "compatibility_fallback",
        "prompt_pack",
        "output_dir",
        "summary_path",
        "slug",
        "dry_run",
        "exit_code",
        "source_manifest_hash",
        "local_context_requires_eal_disposition",
    ):
        lines.append(f"{key}={_format_value(payload.get(key))}")
    for blocker in payload["blockers"]:
        lines.append(f"blocker={blocker}")
    for hint in payload["remediation"]:
        lines.append(f"remediation={hint}")
    if payload["stdout"]:
        lines.append(f"stdout={payload['stdout']}")
    if payload["stderr"]:
        lines.append(f"stderr={payload['stderr']}")
    return lines


def _format_value(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
