from __future__ import annotations

import json
from typing import TYPE_CHECKING

from spec_dock_runtime.presentation.contracts import CliText

if TYPE_CHECKING:
    from spec_dock_runtime.domain.issue_planning_contracts import (
        PlanningCommandResult,
        PlanningReviewResult,
    )


def render_planning_result_text(result: PlanningCommandResult) -> CliText:
    payload = result.to_dict()
    lines = [
        f"status: {payload['status']}",
        f"reason: {payload['reason']}",
        f"issue_id: {payload['issue_id']}",
    ]
    if payload["output"]:
        lines.append(
            "output: "
            + json.dumps(
                payload["output"],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    if payload["details"]:
        lines.append("details:")
        lines.extend(f"- {detail}" for detail in payload["details"])
    return CliText(stdout_lines=lines, stderr_lines=[], warnings=[])


def render_planning_result_json(result: PlanningCommandResult) -> CliText:
    return CliText(
        stdout_lines=[
            json.dumps(
                result.to_dict(),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        ],
        stderr_lines=[],
        warnings=[],
    )


def render_planning_review_summary(result: PlanningReviewResult) -> str:
    lines = [
        "# Planning Review Summary",
        "",
        f"- mode: `{result.reviewed_identity.mode}`",
        f"- issue_id: `{result.reviewed_identity.issue_id}`",
        f"- reviewed_identity_sha256: `{result.reviewed_identity_sha256}`",
        f"- verdict: `{result.verdict}`",
        f"- finding_count: {len(result.findings)}",
    ]
    if result.findings:
        lines.extend(("", "## Findings", ""))
        lines.extend(
            f"- `{finding.id}`: `{finding.severity}`"
            for finding in sorted(
                result.findings,
                key=lambda item: (item.severity, item.id.encode("utf-8")),
            )
        )
    return "\n".join(lines) + "\n"
