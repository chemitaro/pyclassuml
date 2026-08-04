from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spec_dock_runtime.domain.authoring_pack.prompt_pack_contract import PromptPackPrepareResult


def render_pack_prepare_json(result: PromptPackPrepareResult) -> str:
    return json.dumps(result.to_dict(), sort_keys=True)


def render_pack_prepare_text(result: PromptPackPrepareResult) -> list[str]:
    payload = result.to_dict()
    lines = ["spec-dock: authoring pack prepare"]
    for key in (
        "status",
        "authority",
        "adoption_status",
        "bundle_generation_not_promotion",
        "evidence_mode",
        "sync_state",
        "github_sync",
        "mode",
        "output_dir",
        "output_root",
        "source_manifest_hash",
    ):
        lines.append(f"{key}={_format_value(payload.get(key))}")
    for path in payload["output_files"]:
        lines.append(f"output_file={path}")
    for blocker in payload["blockers"]:
        lines.append(f"blocker={blocker}")
    for hint in payload["remediation"]:
        lines.append(f"remediation={hint}")
    return lines


def _format_value(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
