from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal

from spec_dock_runtime.domain.authoring_pack.zip_contract import PackReviewResult, review_pack_input


@dataclass(frozen=True)
class PackReviewRequest:
    input_path: Path
    output_format: Literal["text", "json"] = "text"
    evidence_mode: Literal["github-synced", "local-context"] = "github-synced"
    report_path: Path | None = None


def review_authoring_pack(request: PackReviewRequest) -> PackReviewResult:
    result = review_pack_input(request.input_path)
    result = _with_evidence_mode(result, _effective_evidence_mode(result.evidence_mode, request.evidence_mode))
    if request.report_path is not None:
        unsafe_report_path = _unsafe_report_path(request.report_path)
        if unsafe_report_path:
            return PackReviewResult(
                status="rejected",
                input_path=str(request.input_path),
                input_kind=result.input_kind,
                evidence_mode=request.evidence_mode,
                findings=(unsafe_report_path,),
            )
        request.report_path.parent.mkdir(parents=True, exist_ok=True)
        request.report_path.write_text(json.dumps(result.to_dict(), sort_keys=True) + "\n", encoding="utf-8")
    return result


def _with_evidence_mode(result: PackReviewResult, evidence_mode: str) -> PackReviewResult:
    return PackReviewResult(
        status=result.status,
        input_path=result.input_path,
        input_kind=result.input_kind,
        authority=result.authority,
        adoption_status=result.adoption_status,
        bundle_generation_not_promotion=result.bundle_generation_not_promotion,
        evidence_mode=evidence_mode,
        fallback=result.fallback,
        authority_level=result.authority_level,
        missing_evidence=result.missing_evidence,
        findings=result.findings,
        reviewed_files=result.reviewed_files,
        content_sha256=result.content_sha256,
    )


def _effective_evidence_mode(observed: str | None, requested: str) -> str:
    if observed == "local-context":
        return "local-context"
    if requested == "local-context":
        return "local-context"
    return observed or requested


def _unsafe_report_path(report_path: Path) -> str | None:
    absolute_path = report_path if report_path.is_absolute() else Path.cwd() / report_path
    resolved_path = absolute_path.resolve(strict=False)
    candidate_parts = (absolute_path.parts, resolved_path.parts)
    if report_path.name == ".assurance.json" or any(".assurance.json" in parts for parts in candidate_parts):
        return "unsafe_report_path:assurance"
    for parts in candidate_parts:
        if "spec-dock" in parts:
            spec_dock_index = parts.index("spec-dock")
            managed_parts = set(parts[spec_dock_index + 1 :])
            if managed_parts.intersection({"active", "initiatives"}):
                return "unsafe_report_path:canonical-docs"
    current = absolute_path
    cwd_resolved = Path.cwd().resolve()
    while current != current.parent:
        if current.is_symlink():
            return "unsafe_report_path:symlink"
        if current.exists() and current.resolve() == cwd_resolved:
            break
        current = current.parent
    return None
