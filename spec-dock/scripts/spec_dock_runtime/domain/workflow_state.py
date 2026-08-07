from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

WorkflowStateKind = Literal["no-active", "requirement-capture", "classification-required", "ready", "blocked"]
WorkflowArtifactReadiness = Literal["missing", "scaffold", "substantive"]
WorkflowProfile = Literal["lite", "standard", "strict", "critical", "unavailable"]
WorkflowObligationSource = Literal["authorized_profile", "unavailable"]


@dataclass(frozen=True)
class RunbookAuthority:
    authorized_profile: WorkflowProfile
    lite_candidate: bool
    obligation_source: WorkflowObligationSource


@dataclass(frozen=True)
class WorkflowState:
    kind: WorkflowStateKind
    active_issue_id: str | None
    reason_code: str
    artifact_readiness: WorkflowArtifactReadiness
    authority: RunbookAuthority
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReportEvidenceGateResult:
    status: Literal["pass", "blocked"]
    reason_code: str
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class _TableRow:
    section: str
    cells: tuple[str, ...]


STRICT_LEGACY_AUTHORITY = RunbookAuthority(
    authorized_profile="strict",
    lite_candidate=False,
    obligation_source="authorized_profile",
)

UNAVAILABLE_AUTHORITY = RunbookAuthority(
    authorized_profile="unavailable",
    lite_candidate=False,
    obligation_source="unavailable",
)


def classify_requirement_text(text: str) -> WorkflowArtifactReadiness:
    stripped = text.strip()
    if not stripped:
        return "missing"
    placeholder_markers = (
        "<ISS_ID>",
        "<ISS_TITLE>",
        "<GITHUB_ISSUE_NUMBER_OR_URL>",
        "<YOUR_NAME>",
        "YYYY-MM-DD",
        "（1〜3行）...",
        "  - ...",
        "- ...",
        "1. ...",
        "2. ...",
        "draft | approved",
        "REQ-XXX",
        "SC-XXX",
        "BH-XXX",
        "AC-XXX",
        "B-CAND-XXX",
        "CON-...",
        "TERM-XXX",
    )
    if any(marker in stripped for marker in placeholder_markers):
        return "scaffold"
    return "substantive"


def evaluate_report_evidence_gate(report_text: str | None, profile: WorkflowProfile) -> ReportEvidenceGateResult:
    if report_text is None:
        return ReportEvidenceGateResult(
            status="blocked",
            reason_code="report-evidence-missing",
            details=("report.md must record fresh review and evidence adoption before issue execution.",),
        )
    stripped = report_text.strip()
    if not stripped:
        return ReportEvidenceGateResult(
            status="blocked",
            reason_code="report-evidence-missing",
            details=("report.md is empty.",),
        )
    rows = _markdown_table_rows(stripped)
    if _report_has_scaffold_markers(stripped, rows):
        return ReportEvidenceGateResult(
            status="blocked",
            reason_code="report-evidence-scaffold",
            details=("report.md still contains scaffold placeholders.",),
        )
    missing_sections = tuple(section for section in _REQUIRED_REPORT_SECTIONS if section not in stripped)
    if missing_sections:
        return ReportEvidenceGateResult(
            status="blocked",
            reason_code="report-evidence-incomplete",
            details=tuple(f"missing report section: {section}" for section in missing_sections),
        )
    if not _has_valid_spec_authoring_gate(rows):
        return ReportEvidenceGateResult(
            status="blocked",
            reason_code="report-spec-authoring-gate-invalid",
            details=("Spec Authoring Gate must record non-blocking pass evidence for requirement/design/plan.",),
        )
    if not _has_eal_row(rows):
        return ReportEvidenceGateResult(
            status="blocked",
            reason_code="report-eal-missing",
            details=("Evidence Adoption Ledger must contain at least one EAL-* adoption row.",),
        )
    if _has_unresolved_eal_row(rows):
        return ReportEvidenceGateResult(
            status="blocked",
            reason_code="report-eal-unresolved",
            details=("Evidence Adoption Ledger contains unresolved stale/blocked evidence.",),
        )
    if not _has_delegated_draft_evidence(rows):
        return ReportEvidenceGateResult(
            status="blocked",
            reason_code="delegated-draft-evidence-missing",
            details=("Delegated Draft Evidence must record used/not used provenance before issue execution.",),
        )
    if not _has_fresh_spec_review_pass(rows):
        return ReportEvidenceGateResult(
            status="blocked",
            reason_code="report-spec-review-missing",
            details=("report.md must record a fresh spec-reviewer pass before issue execution.",),
        )
    if profile == "lite" and not _has_lite_grade_evidence(rows):
        return ReportEvidenceGateResult(
            status="blocked",
            reason_code="report-specialist-evidence-missing",
            details=("Lite issues must record not-applicable or skip-reason grade evidence before issue execution.",),
        )
    if profile in {"standard", "strict", "critical"} and not _has_specialist_or_manual_fallback_evidence(rows, profile):
        return ReportEvidenceGateResult(
            status="blocked",
            reason_code="report-specialist-evidence-missing",
            details=(
                "Standard issues require specialist evidence, a skip reason, or an explicit manual fallback. "
                "Strict/Critical issues require used specialist evidence or an explicit manual fallback with fresh review.",
            ),
        )
    return ReportEvidenceGateResult(status="pass", reason_code="report-evidence-valid")


_REQUIRED_REPORT_SECTIONS = (
    "Evidence Adoption Ledger",
    "Spec Authoring Gate",
    "Delegated Draft Evidence",
    "Grade Specialist Evidence Gate",
    "Reviewer Gate Status",
)


def _report_has_scaffold_markers(text: str, rows: tuple[_TableRow, ...]) -> bool:
    global_markers = (
        "<ISS_ID>",
        "<ISS_TITLE>",
        "<GITHUB_ISSUE_NUMBER_OR_URL>",
        "<YOUR_NAME>",
    )
    if any(marker in text for marker in global_markers):
        return True
    row_markers = (
        "pass / fail / blocked",
        "未解決 / 解決済み / 置換済み",
        "yyyy-mm-dd",
        "ac-___",
        "ec-___",
    )
    readiness_sections = (
        "evidence adoption ledger",
        "spec authoring gate",
        "delegated draft evidence",
        "grade specialist evidence gate",
        "reviewer gate status",
    )
    for row in rows:
        if not any(section in row.section for section in readiness_sections):
            continue
        if any(marker in cell for marker in row_markers for cell in row.cells):
            return True
    return False


def _markdown_table_rows(text: str) -> tuple[_TableRow, ...]:
    rows: list[_TableRow] = []
    section = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            section = stripped.strip("# ").lower()
            continue
        if not stripped.startswith("|") or stripped.count("|") < 2:
            continue
        cells = tuple(cell.strip().strip("`").lower() for cell in stripped.strip("|").split("|"))
        if not cells or all(set(cell) <= {"-", ":", " "} for cell in cells):
            continue
        rows.append(_TableRow(section=section, cells=cells))
    return tuple(rows)


def _has_eal_row(rows: tuple[_TableRow, ...]) -> bool:
    for row in rows:
        if "evidence adoption ledger" not in row.section:
            continue
        cells = row.cells
        if cells and cells[0].startswith("eal-"):
            return True
    return False


def _has_unresolved_eal_row(rows: tuple[_TableRow, ...]) -> bool:
    for row in rows:
        if "evidence adoption ledger" not in row.section:
            continue
        cells = row.cells
        if not cells or not cells[0].startswith("eal-"):
            continue
        if len(cells) < 2:
            return True
        if _is_unresolved_eal_row(cells):
            return True
    return False


def _is_unresolved_eal_row(cells: tuple[str, ...]) -> bool:
    status = cells[1]
    if _has_eal_scaffold_marker(cells):
        return True
    if _is_unresolved_eal_status(status):
        return True
    if _has_contract_value(status, {"deferred"}):
        rationale = cells[4] if len(cells) > 4 else ""
        next_action = cells[6] if len(cells) > 6 else ""
        return not (_has_substantive_evidence(rationale) and _has_substantive_evidence(next_action))
    if _has_contract_value(status, {"adopted", "partially_adopted", "integrated", "partially_integrated"}):
        required_fields = cells[2:6]
        return len(required_fields) < 4 or any(not _has_substantive_evidence(cell) for cell in required_fields)
    if _has_contract_value(status, {"rejected"}):
        rationale = cells[4] if len(cells) > 4 else ""
        return not _has_substantive_evidence(rationale)
    return True


def _has_eal_scaffold_marker(cells: tuple[str, ...]) -> bool:
    return any(_is_scaffold_placeholder(cell) for cell in cells)


def _is_unresolved_eal_status(status: str) -> bool:
    if "stale" in status or "blocked" in status:
        return True
    allowed_statuses = {
        "adopted",
        "partially_adopted",
        "rejected",
        "deferred",
        "integrated",
        "partially_integrated",
    }
    return not _has_contract_value(status, allowed_statuses)


def _has_valid_spec_authoring_gate(rows: tuple[_TableRow, ...]) -> bool:
    required_steps = {"requirement", "design", "plan"}
    valid_steps: set[str] = set()
    for row in rows:
        if "spec authoring gate" not in row.section:
            continue
        cells = row.cells
        if not cells:
            continue
        phase = _phase_value(cells[0], required_steps)
        if phase is None:
            continue
        if not _is_valid_spec_authoring_row(cells):
            return False
        valid_steps.add(phase)
    return valid_steps == required_steps


def _is_valid_spec_authoring_row(cells: tuple[str, ...]) -> bool:
    if len(cells) < 7:
        return False
    investigated_facts = cells[1]
    open_questions = cells[2]
    adoption_decision = cells[3]
    reviewer_verdict = cells[4]
    blocking = cells[5]
    promotion_decision = cells[6]
    return (
        _has_substantive_evidence(investigated_facts)
        and _has_answer_or_explicit_none(open_questions)
        and _has_substantive_evidence(adoption_decision)
        and _has_review_pass(reviewer_verdict)
        and _is_no(blocking)
        and _has_promotion_decision(promotion_decision)
    )


def _has_answer_or_explicit_none(value: str) -> bool:
    if _is_scaffold_placeholder(value):
        return False
    if value in {"none", "なし", "該当なし", "n/a", "[]"}:
        return True
    return _has_substantive_evidence(value)


def _phase_value(value: str, allowed_values: set[str]) -> str | None:
    stripped = value.strip().strip("`")
    if stripped in allowed_values:
        return stripped
    for allowed_value in allowed_values:
        if f"({allowed_value})" in stripped or f"（{allowed_value}）" in stripped:
            return allowed_value
    return None


def _has_delegated_draft_evidence(rows: tuple[_TableRow, ...]) -> bool:
    eal_tokens = _eal_reference_tokens(rows)
    has_adopted_row = False
    has_not_used_row = False
    for row in rows:
        if "delegated draft evidence" not in row.section:
            continue
        cells = row.cells
        if not cells or "created_by_role" in cells[0]:
            continue
        adoption_status = cells[5] if len(cells) > 5 else ""
        if _has_contract_value(adoption_status, {"adopted", "partially_adopted", "integrated", "partially_integrated"}):
            has_adopted_row = True
            if not _row_has_delegated_draft_evidence(cells, eal_tokens):
                return False
            continue
        if "not used" in adoption_status and _row_has_delegated_draft_evidence(cells, eal_tokens):
            has_not_used_row = True
    return has_adopted_row or has_not_used_row


def _eal_reference_tokens(rows: tuple[_TableRow, ...]) -> tuple[str, ...]:
    tokens: list[str] = []
    adopted_statuses = {"adopted", "partially_adopted", "integrated", "partially_integrated"}
    for row in rows:
        if "evidence adoption ledger" not in row.section:
            continue
        cells = row.cells
        if not cells or not cells[0].startswith("eal-") or len(cells) < 2:
            continue
        if not _has_contract_value(cells[1], adopted_statuses):
            continue
        for cell in cells[2:6]:
            tokens.extend(_evidence_reference_tokens(cell))
    return tuple(tokens)


def _evidence_reference_tokens(value: str) -> tuple[str, ...]:
    return tuple(
        token.strip("`.;,")
        for token in value.replace(";", " ").split()
        if token.strip("`.;,").startswith((
            "artifacts/",
            "discussions/",
            "design.md",
            "plan.md",
            "requirement.md",
            "report.md",
        ))
    )


def _row_has_delegated_draft_evidence(cells: tuple[str, ...], eal_tokens: tuple[str, ...]) -> bool:
    joined_row = " ".join(cells)
    ineligible_states = ("stale", "rejected", "superseded", "blocked")
    if any(state in joined_row for state in ineligible_states):
        return False
    adoption_status = cells[5] if len(cells) > 5 else ""
    reflected_to = cells[6] if len(cells) > 6 else ""
    diff_guard = cells[7] if len(cells) > 7 else ""
    integration_result = cells[8] if len(cells) > 8 else ""
    blockers = cells[10] if len(cells) > 10 else ""
    reviewer_result = cells[11] if len(cells) > 11 else ""
    promotion_decision = cells[12] if len(cells) > 12 else ""
    if "not used" in adoption_status or (cells[0] == "該当なし" and _has_manual_authoring(integration_result)):
        return (
            _has_manual_authoring(integration_result)
            and _has_review_pass(reviewer_result)
            and _has_promotion_decision(promotion_decision)
        )
    if not _has_contract_value(adoption_status, {"adopted", "partially_adopted", "integrated", "partially_integrated"}):
        return False
    draft_path = cells[2] if len(cells) > 2 else ""
    source_paths = cells[3] if len(cells) > 3 else ""
    return (
        ("artifacts/" in draft_path or "discussions/" in draft_path)
        and _delegated_row_has_eal_reference((draft_path,), eal_tokens)
        and _has_substantive_evidence(source_paths)
        and _has_substantive_evidence(reflected_to)
        and _has_passing_diff_guard(diff_guard)
        and _has_no_unresolved_blocker(blockers)
        and _has_review_pass(reviewer_result)
        and _has_promotion_decision(promotion_decision)
    )


def _has_passing_diff_guard(value: str) -> bool:
    if value in {"", "not_run", "none", "該当なし"}:
        return False
    if any(marker in value for marker in ("fail", "failed", "blocked", "pending", "unresolved")):
        return False
    return any(marker in value for marker in ("pass", "passed", "success", "successful", "ok", "clean"))


def _has_no_unresolved_blocker(value: str) -> bool:
    if value in {"none", "なし", "該当なし", "[]", "no", "resolved", "解決済み"}:
        return True
    return any(marker in value for marker in ("resolved", "解決済み")) and not any(
        marker in value for marker in ("unresolved", "未解決", "blocked", "pending")
    )


def _has_review_pass(value: str) -> bool:
    if any(
        marker in value
        for marker in (
            "not pass",
            "not passed",
            "did not pass",
            "fail",
            "blocked",
            "unavailable",
            "waived",
            "provisional",
            "denied",
            "incomplete",
            "missing",
            "pending",
        )
    ):
        return False
    return _has_contract_value(value, {"pass", "passed", "合格"})


def _has_manual_authoring(value: str) -> bool:
    return (
        "manual authoring" in value
        or "manual-authored" in value
        or "手動 authoring" in value
        or "手動authoring" in value
        or "手動オーサリング" in value
    )


def _is_no(value: str) -> bool:
    return _has_contract_value(value, {"no", "いいえ"})


def _is_ready(value: str) -> bool:
    return _has_contract_value(value, {"ready"})


def _has_contract_value(value: str, allowed_values: set[str]) -> bool:
    stripped = value.strip().strip("`")
    if not stripped:
        return False
    if "/" in stripped:
        return False
    if stripped in allowed_values:
        return True
    for allowed_value in allowed_values:
        if f"({allowed_value})" in stripped or f"（{allowed_value}）" in stripped:
            return True
    return False


def _has_promotion_decision(value: str) -> bool:
    negated_markers = (
        "do not promote",
        "do not execute",
        "not promote",
        "not execute",
        "no promote",
        "no execute",
        "failed",
        "blocked",
        "pending",
    )
    if any(marker in value for marker in negated_markers):
        return False
    return (
        _has_contract_value(value, {"promote", "昇格"})
        or "execute approved plan" in value
        or "execute manual-authored canonical docs" in value
        or "manual-authored" in value
    )


def _has_fresh_spec_review_pass(rows: tuple[_TableRow, ...]) -> bool:
    found_fresh_pass = False
    for row in rows:
        if "reviewer gate status" not in row.section:
            continue
        cells = row.cells
        reviewer_role = cells[2] if len(cells) > 2 else ""
        freshness = cells[3] if len(cells) > 3 else ""
        state = cells[4] if len(cells) > 4 else ""
        risk_acceptance = cells[5] if len(cells) > 5 else ""
        promotion_decision = cells[6] if len(cells) > 6 else ""
        if reviewer_role != "spec-reviewer":
            continue
        if freshness != "fresh":
            continue
        if not (_has_review_pass(state) and _is_no(risk_acceptance) and _has_promotion_decision(promotion_decision)):
            return False
        found_fresh_pass = True
    return found_fresh_pass


def _has_specialist_or_manual_fallback_evidence(rows: tuple[_TableRow, ...], profile: WorkflowProfile) -> bool:
    for row in rows:
        if "grade specialist evidence gate" not in row.section:
            continue
        cells = row.cells
        if not cells or cells[0] != profile:
            continue
        if _row_has_grade_specialist_evidence(cells, profile):
            return True
    return False


def _has_lite_grade_evidence(rows: tuple[_TableRow, ...]) -> bool:
    for row in rows:
        if "grade specialist evidence gate" not in row.section:
            continue
        cells = row.cells
        if not cells or cells[0] != "lite":
            continue
        required_or_fallback = cells[1] if len(cells) > 1 else ""
        usage = cells[2] if len(cells) > 2 else ""
        evidence = cells[3] if len(cells) > 3 else ""
        reviewer_verdict = cells[4] if len(cells) > 4 else ""
        readiness = cells[5] if len(cells) > 5 else ""
        if (
            (
                "not applicable" in required_or_fallback
                or "not applicable" in usage
                or _has_substantive_skip_reason(evidence)
            )
            and _has_substantive_evidence(evidence)
            and _has_review_pass(reviewer_verdict)
            and _is_ready(readiness)
        ):
            return True
    return False


def _row_has_grade_specialist_evidence(cells: tuple[str, ...], profile: WorkflowProfile) -> bool:
    joined_row = " ".join(cells)
    required_or_fallback = cells[1] if len(cells) > 1 else ""
    usage = cells[2] if len(cells) > 2 else ""
    evidence = cells[3] if len(cells) > 3 else ""
    reviewer_verdict = cells[4] if len(cells) > 4 else ""
    readiness = cells[5] if len(cells) > 5 else ""
    fallback_and_evidence = f"{required_or_fallback} {evidence}".strip()
    usage_and_evidence = f"{usage} {evidence}".strip() or joined_row
    has_specialist = (
        ("system-architect" in required_or_fallback or "implementation-planner" in required_or_fallback)
        and usage == "used"
        and _has_substantive_evidence(evidence)
    )
    has_skip_reason = _has_substantive_skip_reason(usage_and_evidence)
    has_fallback = _has_substantive_evidence(evidence) and (
        "manual authoring fallback" in fallback_and_evidence
        or "manual-authored canonical docs" in fallback_and_evidence
        or "manual fallback" in fallback_and_evidence
        or ("manual fallback" in required_or_fallback and "manual evidence" in evidence)
    )
    if profile == "critical" and has_fallback:
        has_fallback = _has_critical_fallback_approval(fallback_and_evidence)
    if profile in {"strict", "critical"}:
        has_skip_reason = False
    if not (has_specialist or has_skip_reason or has_fallback):
        return False
    has_fresh_review = _has_review_pass(reviewer_verdict)
    has_readiness = _is_ready(readiness) or "execute approved plan" in readiness
    return has_fresh_review and has_readiness


def _has_substantive_evidence(value: str) -> bool:
    if value in {"", "none", "該当なし", "n/a", "[]"}:
        return False
    if "not applicable" in value:
        return False
    return not _is_scaffold_placeholder(value)


def _has_substantive_skip_reason(value: str) -> bool:
    for marker in ("skip reason:", "未使用理由"):
        if marker not in value:
            continue
        tail = value.split(marker, 1)[1].strip(" :：-")
        return _has_substantive_evidence(tail)
    return False


def _is_scaffold_placeholder(value: str) -> bool:
    placeholder_values = {
        "...",
        "xxx",
        "path / command / reviewer finding",
        "path / command",
        "path",
        "command",
        "コマンド",
        "reviewer finding",
        "レビュアー指摘",
        "lite not applicable reason",
        "ライト該当なし理由（lite not applicable reason）",
        "manual evidence",
        "manual fallback evidence",
        "explicit approval and risk acceptance",
        "yyyy-mm-dd",
        "ac-___",
        "ec-___",
    }
    if value in placeholder_values:
        return True
    if "..." in value:
        return True
    if _is_scaffold_choice_list(value):
        return True
    if value.endswith(": ...") or value.endswith("： ..."):
        return True
    if "yyyy-mm-dd" in value or "ac-___" in value or "ec-___" in value:
        return True
    if "<" in value and ">" in value:
        return True
    if value.startswith("skip reason:"):
        tail = value.split("skip reason:", 1)[1].strip(" :：-")
        return not tail or _is_scaffold_placeholder(tail)
    return False


def _is_scaffold_choice_list(value: str) -> bool:
    known_choice_groups = (
        ("sub-agent", "reviewer", "discussion", "command", "research"),
        ("artifact", "issue", "follow-up"),
        ("used", "skipped", "unavailable", "denied"),
        ("ready", "blocked"),
    )
    return any(" / " in value and all(choice in value for choice in group) for group in known_choice_groups)


def _has_critical_fallback_approval(value: str) -> bool:
    negated_approval_markers = ("no explicit approval", "no approval", "without approval", "approval denied")
    if any(marker in value for marker in negated_approval_markers):
        return False
    has_approval = (
        "explicit approval" in value
        or "fallback approval" in value
        or "approved fallback" in value
        or "明示承認" in value
    )
    has_risk_acceptance = "risk acceptance" in value or "risk accepted" in value or "リスク受容" in value
    return has_approval and has_risk_acceptance


def _delegated_row_has_eal_reference(values: tuple[str, ...], eal_tokens: tuple[str, ...]) -> bool:
    for value in values:
        for token in _evidence_reference_tokens(value):
            if token in eal_tokens:
                return True
    return False
