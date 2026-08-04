from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spec_dock_runtime.application.authoring_pack.pack_stage import PackStageResult


def render_pack_stage_json(result: PackStageResult) -> str:
    return json.dumps(result.to_dict(), sort_keys=True)


def render_pack_stage_text(result: PackStageResult) -> list[str]:
    payload = result.to_dict()
    lines = ["spec-dock: authoring pack stage"]
    for key in ("status", "input_path", "stage_dir", "dry_run"):
        lines.append(f"{key}={payload[key]}")
    review = payload["review"]
    if isinstance(review, dict):
        for key in (
            "status",
            "authority",
            "adoption_status",
            "bundle_generation_not_promotion",
            "fallback",
            "authority_level",
        ):
            lines.append(f"review_{key}={review[key]}")
    for item in payload["findings"]:
        lines.append(f"finding={item}")
    for item in payload["staged_files"]:
        lines.append(f"staged_file={item}")
    return lines
