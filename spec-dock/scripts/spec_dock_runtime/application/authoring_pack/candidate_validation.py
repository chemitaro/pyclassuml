from __future__ import annotations

from dataclasses import dataclass
import json
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pathlib import Path

from spec_dock_runtime.application.authoring_pack.pack_review import _unsafe_report_path
from spec_dock_runtime.application.authoring_pack.review_report_evidence import read_review_report_evidence
from spec_dock_runtime.domain.authoring_pack.authority_boundary import evidence_authority_boundary_findings
from spec_dock_runtime.domain.authoring_pack.candidate_contract import (
    CandidateKind,
    CandidateValidationResult,
    validate_candidate_pack,
)
from spec_dock_runtime.domain.authoring_pack.prompt_pack_contract import EXPECTED_OUTPUT_ROOT


@dataclass(frozen=True)
class CandidateValidationRequest:
    input_path: Path
    candidate_kind: CandidateKind
    output_format: Literal["text", "json"] = "text"
    evidence_mode: Literal["github-synced", "local-context"] = "github-synced"
    review_report: Path | None = None
    expected_parent_initiative: str | None = None
    expected_parent_epic: str | None = None
    expected_source_hash: str | None = None
    report_path: Path | None = None


def validate_authoring_candidates(request: CandidateValidationRequest) -> CandidateValidationResult:
    pack_root = _pack_root(request.input_path)
    review_report_path = request.review_report or _discover_review_report(request.input_path, pack_root)
    review_gate, review_digest = _review_gate(
        request.input_path, review_report_path, request.candidate_kind, request.evidence_mode
    )
    if review_gate.status != "pass":
        return _write_report_if_requested(review_gate, request.report_path)
    result = validate_candidate_pack(
        pack_root,
        input_path=request.input_path,
        candidate_kind=request.candidate_kind,
        review_status="pass",
        expected_parent_initiative=request.expected_parent_initiative,
        expected_parent_epic=request.expected_parent_epic,
        expected_source_hash=request.expected_source_hash,
        expected_review_digest=review_digest,
        evidence_mode=request.evidence_mode,
    )
    return _write_report_if_requested(result, request.report_path)


def _pack_root(input_path: Path) -> Path:
    root_name = EXPECTED_OUTPUT_ROOT.rstrip("/")
    if input_path.name == root_name:
        return input_path
    return input_path / root_name


def _discover_review_report(input_path: Path, pack_root: Path) -> Path:
    candidates = (
        input_path / "review-report.json",
        pack_root.parent / "review-report.json",
        input_path.parent / "review-report.json",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def _review_gate(
    input_path: Path, review_report: Path, candidate_kind: CandidateKind, evidence_mode: str
) -> tuple[CandidateValidationResult, str | None]:
    evidence = read_review_report_evidence(review_report, context_path=input_path)
    if evidence.status != "pass":
        failure_status = (
            "rejected" if evidence.status == "unsafe" else "fail" if evidence.status == "malformed" else "blocked"
        )
        return CandidateValidationResult(
            status=failure_status,  # type: ignore[arg-type]
            input_path=str(input_path),
            candidate_kind=candidate_kind,
            evidence_mode=evidence_mode,
            findings=(evidence.finding or "unreadable_review_report",),
        ), None
    payload = evidence.payload or {}
    status = payload.get("status")
    if status == "pass":
        authority_findings = evidence_authority_boundary_findings(payload, prefix="review_report")
        if authority_findings:
            return CandidateValidationResult(
                status="rejected",
                input_path=str(input_path),
                candidate_kind=candidate_kind,
                evidence_mode=evidence_mode,
                review_status="pass",
                review_gate_passed=False,
                findings=authority_findings,
            ), None
        pack_digest = _review_digest(payload)
        if pack_digest is None:
            return CandidateValidationResult(
                status="blocked",
                input_path=str(input_path),
                candidate_kind=candidate_kind,
                evidence_mode=evidence_mode,
                review_status="pass",
                review_gate_passed=False,
                findings=("missing_review_digest",),
            ), None
        return CandidateValidationResult(
            status="pass",
            input_path=str(input_path),
            candidate_kind=candidate_kind,
            evidence_mode=evidence_mode,
            review_status="pass",
            review_gate_passed=True,
        ), pack_digest
    if status in {"stale", "rejected", "fail", "blocked"}:
        return CandidateValidationResult(
            status=status,  # type: ignore[arg-type]
            input_path=str(input_path),
            candidate_kind=candidate_kind,
            evidence_mode=evidence_mode,
            review_status=str(status),
            review_gate_passed=False,
            findings=(f"review_not_pass:{status}",),
        ), None
    return CandidateValidationResult(
        status="blocked",
        input_path=str(input_path),
        candidate_kind=candidate_kind,
        evidence_mode=evidence_mode,
        review_status=str(status),
        review_gate_passed=False,
        findings=(f"unsupported_review_status:{status}",),
    ), None


def _review_digest(payload: dict[str, object]) -> str | None:
    pack_digest = payload.get("pack_digest")
    if isinstance(pack_digest, dict):
        value = pack_digest.get("content_sha256")
        if isinstance(value, str):
            return value
    return None


def _write_report_if_requested(
    result: CandidateValidationResult, report_path: Path | None
) -> CandidateValidationResult:
    if report_path is None:
        return result
    unsafe = _unsafe_report_path(report_path)
    if unsafe:
        return CandidateValidationResult(
            status="rejected",
            input_path=result.input_path,
            candidate_kind=result.candidate_kind,
            evidence_mode=result.evidence_mode,
            review_status=result.review_status,
            review_gate_passed=result.review_gate_passed,
            findings=(unsafe,),
        )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result.to_dict(), sort_keys=True) + "\n", encoding="utf-8")
    return result
