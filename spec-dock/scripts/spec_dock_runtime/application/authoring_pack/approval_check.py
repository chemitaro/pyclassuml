from __future__ import annotations

from dataclasses import dataclass
import json
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pathlib import Path

from spec_dock_runtime.application.authoring_pack.candidate_validation import (
    CandidateValidationRequest,
    validate_authoring_candidates,
)
from spec_dock_runtime.application.authoring_pack.pack_review import _unsafe_report_path
from spec_dock_runtime.domain.authoring_pack.candidate_contract import (
    ApprovalCheckResult,
    CandidateKind,
    tree_digest,
    validate_approval_evidence,
)
from spec_dock_runtime.domain.authoring_pack.prompt_pack_contract import EXPECTED_OUTPUT_ROOT


@dataclass(frozen=True)
class ApprovalCheckRequest:
    input_path: Path
    approval_path: Path | None
    candidate_kind: CandidateKind
    output_format: Literal["text", "json"] = "text"
    evidence_mode: Literal["github-synced", "local-context"] = "github-synced"
    review_report: Path | None = None
    candidate_evidence: Path | None = None
    expected_parent_initiative: str | None = None
    expected_parent_epic: str | None = None
    expected_requested_scope: str | None = None
    expected_effective_scope: str | None = None
    expected_candidate_pack_digest: str | None = None
    expected_candidate_evidence_digest: str | None = None
    expected_source_hash: str | None = None
    report_path: Path | None = None


def check_authoring_approval(request: ApprovalCheckRequest) -> ApprovalCheckResult:
    validation = validate_authoring_candidates(
        CandidateValidationRequest(
            input_path=request.input_path,
            candidate_kind=request.candidate_kind,
            output_format=request.output_format,
            evidence_mode=request.evidence_mode,
            review_report=request.review_report,
            expected_parent_initiative=request.expected_parent_initiative,
            expected_parent_epic=request.expected_parent_epic,
            expected_source_hash=request.expected_source_hash,
            report_path=None,
        )
    )
    if validation.status != "pass":
        return _write_report_if_requested(
            ApprovalCheckResult(
                status=validation.status,
                input_path=validation.input_path,
                candidate_kind=validation.candidate_kind,
                evidence_mode=validation.evidence_mode,
                review_status=validation.review_status,
                review_gate_passed=validation.review_gate_passed,
                approval_path=str(request.approval_path) if request.approval_path else None,
                candidate_evidence_path=str(request.candidate_evidence) if request.candidate_evidence else None,
                expected_requested_scope=_expected_requested_scope(request),
                expected_effective_scope=_expected_effective_scope(request),
                expected_candidate_pack_digest=request.expected_candidate_pack_digest,
                observed_candidate_pack_digest=tree_digest(_pack_root(request.input_path)),
                expected_candidate_evidence_digest=request.expected_candidate_evidence_digest,
                expected_source_manifest_hash=request.expected_source_hash,
                observed_source_manifest_hash=validation.observed_source_manifest_hash,
                candidate_count=validation.candidate_count,
                valid_candidate_count=validation.valid_candidate_count,
                findings=validation.findings,
                comparison=validation.comparison,
            ),
            request.report_path,
        )

    result = validate_approval_evidence(
        request.approval_path,
        input_path=request.input_path,
        candidate_kind=request.candidate_kind,
        evidence_mode=request.evidence_mode,
        review_status=validation.review_status,
        review_gate_passed=validation.review_gate_passed,
        candidate_count=validation.candidate_count,
        valid_candidate_count=validation.valid_candidate_count,
        observed_candidate_pack_digest=tree_digest(_pack_root(request.input_path)),
        expected_candidate_pack_digest=request.expected_candidate_pack_digest,
        candidate_evidence_path=request.candidate_evidence,
        expected_candidate_evidence_digest=request.expected_candidate_evidence_digest,
        expected_source_hash=request.expected_source_hash,
        observed_source_hash=validation.observed_source_manifest_hash,
        expected_requested_scope=_expected_requested_scope(request),
        expected_effective_scope=_expected_effective_scope(request),
    )
    return _write_report_if_requested(result, request.report_path)


def _expected_requested_scope(request: ApprovalCheckRequest) -> str | None:
    if request.expected_requested_scope:
        return request.expected_requested_scope
    return _parent_scope(request)


def _expected_effective_scope(request: ApprovalCheckRequest) -> str | None:
    if request.expected_effective_scope:
        return request.expected_effective_scope
    return _parent_scope(request)


def _parent_scope(request: ApprovalCheckRequest) -> str | None:
    if request.candidate_kind == "initiative-epic" and request.expected_parent_initiative:
        return f"initiative:{request.expected_parent_initiative}"
    if request.candidate_kind == "epic-issue" and request.expected_parent_epic:
        return f"epic:{request.expected_parent_epic}"
    return None


def _pack_root(input_path: Path) -> Path:
    root_name = EXPECTED_OUTPUT_ROOT.rstrip("/")
    if input_path.name == root_name:
        return input_path
    return input_path / root_name


def _write_report_if_requested(result: ApprovalCheckResult, report_path: Path | None) -> ApprovalCheckResult:
    if report_path is None:
        return result
    unsafe = _unsafe_report_path(report_path)
    if unsafe:
        return ApprovalCheckResult(
            status="rejected",
            input_path=result.input_path,
            candidate_kind=result.candidate_kind,
            evidence_mode=result.evidence_mode,
            review_status=result.review_status,
            review_gate_passed=result.review_gate_passed,
            approval_path=result.approval_path,
            candidate_evidence_path=result.candidate_evidence_path,
            expected_requested_scope=result.expected_requested_scope,
            expected_effective_scope=result.expected_effective_scope,
            expected_candidate_pack_digest=result.expected_candidate_pack_digest,
            observed_candidate_pack_digest=result.observed_candidate_pack_digest,
            expected_candidate_evidence_digest=result.expected_candidate_evidence_digest,
            candidate_evidence_file_digest=result.candidate_evidence_file_digest,
            expected_source_manifest_hash=result.expected_source_manifest_hash,
            observed_source_manifest_hash=result.observed_source_manifest_hash,
            candidate_count=result.candidate_count,
            valid_candidate_count=result.valid_candidate_count,
            findings=(unsafe,),
            comparison=result.comparison,
        )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result.to_dict(), sort_keys=True) + "\n", encoding="utf-8")
    return result
