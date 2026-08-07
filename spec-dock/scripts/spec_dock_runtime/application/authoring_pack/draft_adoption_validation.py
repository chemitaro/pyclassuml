from __future__ import annotations

from dataclasses import dataclass
import json
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pathlib import Path

from spec_dock_runtime.application.authoring_pack.pack_review import _unsafe_report_path
from spec_dock_runtime.application.authoring_pack.review_report_evidence import read_review_report_evidence
from spec_dock_runtime.domain.authoring_pack.authority_boundary import evidence_authority_boundary_findings
from spec_dock_runtime.domain.authoring_pack.draft_adoption_contract import (
    DraftAdoptionResult,
    blocked_result,
    failed_result,
    read_json_payload,
    validate_issue_draft_adoption_payload,
    validate_selected_skeleton_payload,
)


@dataclass(frozen=True)
class IssueDraftAdoptionValidationRequest:
    input_path: Path
    issue_dir: Path
    output_format: Literal["text", "json"] = "text"
    evidence_mode: Literal["github-synced", "local-context"] = "github-synced"
    review_report: Path | None = None
    expected_review_digest: str | None = None
    expected_draft_pack_digest: str | None = None
    expected_source_hash: str | None = None
    report_path: Path | None = None


@dataclass(frozen=True)
class SelectedSkeletonFillValidationRequest:
    input_path: Path
    issue_dir: Path
    assurance: Path
    selected_skeleton: Path
    output_format: Literal["text", "json"] = "text"
    evidence_mode: Literal["github-synced", "local-context"] = "github-synced"
    review_report: Path | None = None
    expected_review_digest: str | None = None
    expected_profile: str | None = None
    expected_source_hash: str | None = None
    report_path: Path | None = None


def validate_issue_draft_adoption(request: IssueDraftAdoptionValidationRequest) -> DraftAdoptionResult:
    payload, findings = read_json_payload(request.input_path, "issue-draft-adoption")
    if payload is None:
        result_factory = blocked_result if _missing_or_unreadable_json(findings) else failed_result
        return _write_report_if_requested(
            result_factory(
                input_path=request.input_path,
                validation_kind="issue-draft-adoption",
                evidence_mode=request.evidence_mode,
                findings=findings,
            ),
            request.report_path,
        )
    issue_gate = _issue_node_gate(request.input_path, request.issue_dir, "issue-draft-adoption", request.evidence_mode)
    if issue_gate is not None:
        return _write_report_if_requested(issue_gate, request.report_path)
    if request.review_report is None:
        return _write_report_if_requested(
            blocked_result(
                input_path=request.input_path,
                validation_kind="issue-draft-adoption",
                evidence_mode=request.evidence_mode,
                findings=("missing_review_report",),
            ),
            request.report_path,
        )
    review_report_path = request.review_report
    review_gate, review_pack_digest, review_file_digest = _review_gate(
        request.input_path, review_report_path, "issue-draft-adoption", request.evidence_mode
    )
    if review_gate.status != "pass":
        return _write_report_if_requested(review_gate, request.report_path)
    result = validate_issue_draft_adoption_payload(
        payload,
        input_path=request.input_path,
        issue_dir=request.issue_dir,
        review_status="pass",
        review_digest=review_file_digest or "",
        expected_review_digest=request.expected_review_digest,
        expected_draft_pack_digest=review_pack_digest,
        additional_expected_draft_pack_digest=request.expected_draft_pack_digest,
        expected_source_hash=request.expected_source_hash,
        evidence_mode=request.evidence_mode,
    )
    return _write_report_if_requested(result, request.report_path)


def validate_selected_skeleton_fill(request: SelectedSkeletonFillValidationRequest) -> DraftAdoptionResult:
    payload, findings = read_json_payload(request.input_path, "selected-skeleton-fill")
    if payload is None:
        result_factory = blocked_result if _missing_or_unreadable_json(findings) else failed_result
        return _write_report_if_requested(
            result_factory(
                input_path=request.input_path,
                validation_kind="selected-skeleton-fill",
                evidence_mode=request.evidence_mode,
                findings=findings,
            ),
            request.report_path,
        )
    issue_gate = _issue_node_gate(
        request.input_path, request.issue_dir, "selected-skeleton-fill", request.evidence_mode
    )
    if issue_gate is not None:
        return _write_report_if_requested(issue_gate, request.report_path)
    if request.review_report is None:
        return _write_report_if_requested(
            blocked_result(
                input_path=request.input_path,
                validation_kind="selected-skeleton-fill",
                evidence_mode=request.evidence_mode,
                findings=("missing_review_report",),
            ),
            request.report_path,
        )
    review_report_path = request.review_report
    review_gate, review_pack_digest, review_file_digest = _review_gate(
        request.input_path, review_report_path, "selected-skeleton-fill", request.evidence_mode
    )
    if review_gate.status != "pass":
        return _write_report_if_requested(review_gate, request.report_path)
    assurance, assurance_findings = read_json_payload(request.assurance, "assurance")
    if assurance is None:
        result_factory = blocked_result if _missing_or_unreadable_json(assurance_findings) else failed_result
        return _write_report_if_requested(
            result_factory(
                input_path=request.input_path,
                validation_kind="selected-skeleton-fill",
                evidence_mode=request.evidence_mode,
                findings=assurance_findings,
            ),
            request.report_path,
        )
    selected_skeleton, skeleton_findings = read_json_payload(request.selected_skeleton, "selected-skeleton")
    if selected_skeleton is None:
        result_factory = blocked_result if _missing_or_unreadable_json(skeleton_findings) else failed_result
        return _write_report_if_requested(
            result_factory(
                input_path=request.input_path,
                validation_kind="selected-skeleton-fill",
                evidence_mode=request.evidence_mode,
                findings=skeleton_findings,
            ),
            request.report_path,
        )
    result = validate_selected_skeleton_payload(
        payload,
        input_path=request.input_path,
        issue_dir=request.issue_dir,
        assurance=assurance,
        selected_skeleton=selected_skeleton,
        review_status="pass",
        review_digest=review_file_digest or "",
        expected_review_digest=request.expected_review_digest,
        expected_draft_pack_digest=review_pack_digest,
        expected_profile=request.expected_profile,
        expected_source_hash=request.expected_source_hash,
        evidence_mode=request.evidence_mode,
    )
    return _write_report_if_requested(result, request.report_path)


def _issue_node_gate(
    input_path: Path, issue_dir: Path, validation_kind: str, evidence_mode: str
) -> DraftAdoptionResult | None:
    if not issue_dir.is_dir() or issue_dir.is_symlink():
        return blocked_result(
            input_path=input_path,
            validation_kind=validation_kind,
            evidence_mode=evidence_mode,
            findings=("missing_issue_node",),
        )
    meta = issue_dir / ".meta.json"
    if not meta.is_file() or meta.is_symlink():
        return blocked_result(
            input_path=input_path,
            validation_kind=validation_kind,
            evidence_mode=evidence_mode,
            findings=("missing_issue_node",),
        )
    return None


def _review_gate(
    input_path: Path, review_report: Path, validation_kind: str, evidence_mode: str
) -> tuple[DraftAdoptionResult, str | None, str | None]:
    evidence = read_review_report_evidence(review_report, context_path=input_path)
    if evidence.status != "pass":
        result_factory = failed_result if evidence.status == "malformed" else blocked_result
        result = result_factory(
            input_path=input_path,
            validation_kind=validation_kind,
            evidence_mode=evidence_mode,
            findings=(evidence.finding or "unreadable_review_report",),
        )
        if evidence.status == "unsafe":
            result = DraftAdoptionResult(
                status="rejected",
                input_path=str(input_path),
                validation_kind=validation_kind,
                evidence_mode=evidence_mode,
                review_gate_passed=False,
                findings=(evidence.finding or "unsafe_review_report_path",),
            )
        return result, None, None
    payload = evidence.payload or {}
    status = payload.get("status")
    if status == "pass":
        authority_findings = evidence_authority_boundary_findings(payload, prefix="review_report")
        if authority_findings:
            return (
                DraftAdoptionResult(
                    status="rejected",
                    input_path=str(input_path),
                    validation_kind=validation_kind,
                    evidence_mode=evidence_mode,
                    review_status="pass",
                    review_gate_passed=False,
                    findings=authority_findings,
                ),
                None,
                evidence.content_sha256,
            )
        pack_digest = _review_digest(payload)
        if pack_digest is None:
            return (
                blocked_result(
                    input_path=input_path,
                    validation_kind=validation_kind,
                    evidence_mode=evidence_mode,
                    review_status="pass",
                    findings=("missing_review_digest",),
                ),
                None,
                evidence.content_sha256,
            )
        return (
            DraftAdoptionResult(
                status="pass",
                input_path=str(input_path),
                validation_kind=validation_kind,
                evidence_mode=evidence_mode,
                review_status="pass",
                review_gate_passed=True,
            ),
            pack_digest,
            evidence.content_sha256,
        )
    if status in {"stale", "rejected", "fail", "blocked"}:
        return (
            DraftAdoptionResult(
                status=status,  # type: ignore[arg-type]
                input_path=str(input_path),
                validation_kind=validation_kind,
                evidence_mode=evidence_mode,
                review_status=str(status),
                review_gate_passed=False,
                findings=(f"review_not_pass:{status}",),
            ),
            None,
            evidence.content_sha256,
        )
    return (
        blocked_result(
            input_path=input_path,
            validation_kind=validation_kind,
            evidence_mode=evidence_mode,
            review_status=str(status),
            findings=(f"unsupported_review_status:{status}",),
        ),
        None,
        evidence.content_sha256,
    )


def _review_digest(payload: dict[str, object]) -> str | None:
    pack_digest = payload.get("pack_digest")
    if isinstance(pack_digest, dict):
        value = pack_digest.get("content_sha256")
        if isinstance(value, str):
            return value
    return None


def _write_report_if_requested(result: DraftAdoptionResult, report_path: Path | None) -> DraftAdoptionResult:
    if report_path is None:
        return result
    unsafe = _unsafe_report_path(report_path)
    if unsafe:
        return DraftAdoptionResult(
            status="rejected",
            input_path=result.input_path,
            validation_kind=result.validation_kind,
            evidence_mode=result.evidence_mode,
            findings=(unsafe,),
        )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result.to_dict(), sort_keys=True) + "\n", encoding="utf-8")
    return result


def _missing_or_unreadable_json(findings: tuple[str, ...]) -> bool:
    return any(finding.startswith(("missing_json:", "unreadable_payload:")) for finding in findings)
