from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spec_dock_runtime.domain.authoring_pack.zip_contract import PackReviewResult


def render_pack_review_json(result: PackReviewResult) -> str:
    return json.dumps(result.to_dict(), sort_keys=True)


def render_pack_review_text(result: PackReviewResult) -> list[str]:
    payload = result.to_dict()
    lines = ["spec-dock: authoring pack review"]
    for key in (
        "status",
        "input_kind",
        "authority",
        "adoption_status",
        "bundle_generation_not_promotion",
        "evidence_mode",
        "fallback",
        "authority_level",
    ):
        lines.append(f"{key}={payload[key]}")
    for item in payload["missing_evidence"]:
        lines.append(f"missing_evidence={item}")
    for item in payload["findings"]:
        lines.append(f"finding={item}")
    return lines
