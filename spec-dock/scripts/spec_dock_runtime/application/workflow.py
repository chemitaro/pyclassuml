from __future__ import annotations

from pathlib import Path
import re
from typing import TYPE_CHECKING, Any, Protocol

from spec_dock_runtime.application.contracts import (
    RunbookProjectionResult,
    WorkflowNextRequest,
    WorkflowResult,
    WorkflowStatusRequest,
)
from spec_dock_runtime.domain.runbook import compile_runbook
from spec_dock_runtime.domain.workflow_state import (
    STRICT_LEGACY_AUTHORITY,
    UNAVAILABLE_AUTHORITY,
    RunbookAuthority,
    WorkflowState,
    classify_requirement_text,
    evaluate_report_evidence_gate,
)

if TYPE_CHECKING:
    from spec_dock_runtime.domain.runbook import Runbook


class WorkflowAssuranceStoreLike(Protocol):
    def resolve_issue_target(self, target: None) -> Any: ...

    def read_contract(self, target: Any) -> Any: ...

    def verify_contract(self, target: Any) -> Any: ...

    def read_requirement_text(self, target: Any) -> str | None: ...


class RunbookStoreLike(Protocol):
    def write_current(self, runbook: Runbook) -> RunbookProjectionResult: ...


def workflow_status(_request: WorkflowStatusRequest, *, store: WorkflowAssuranceStoreLike) -> WorkflowResult:
    state = _resolve_state(store)
    return WorkflowResult(operation="status", state=state, runbook=None)


def workflow_next(
    request: WorkflowNextRequest,
    *,
    store: WorkflowAssuranceStoreLike,
    runbook_store: RunbookStoreLike,
) -> WorkflowResult:
    state = _resolve_state(store)
    runbook = compile_runbook(request.workflow_target, state)
    return _workflow_result_with_projection(state, runbook, runbook_store)


def _workflow_result_with_projection(
    state: WorkflowState,
    runbook: Runbook,
    runbook_store: RunbookStoreLike,
) -> WorkflowResult:
    return WorkflowResult(
        operation="next",
        state=state,
        runbook=runbook,
        projection=runbook_store.write_current(runbook),
    )


def _resolve_state(store: WorkflowAssuranceStoreLike) -> WorkflowState:
    try:
        target = store.resolve_issue_target(None)
    except Exception as exc:
        reason = getattr(exc, "reason", "")
        if reason == "active_issue_missing":
            return WorkflowState(
                kind="no-active",
                active_issue_id=None,
                reason_code="active-issue-missing",
                artifact_readiness="missing",
                authority=STRICT_LEGACY_AUTHORITY,
            )
        return WorkflowState(
            kind="no-active",
            active_issue_id=None,
            reason_code=reason or "active-issue-unavailable",
            artifact_readiness="missing",
            authority=STRICT_LEGACY_AUTHORITY,
            details=(str(exc),),
        )

    try:
        requirement_text = store.read_requirement_text(target)
    except OSError as exc:
        return WorkflowState(
            kind="requirement-capture",
            active_issue_id=target.issue_id,
            reason_code="requirement-unreadable",
            artifact_readiness="missing",
            authority=STRICT_LEGACY_AUTHORITY,
            details=(str(exc),),
        )
    if requirement_text is None:
        return WorkflowState(
            kind="requirement-capture",
            active_issue_id=target.issue_id,
            reason_code="requirement-missing",
            artifact_readiness="missing",
            authority=STRICT_LEGACY_AUTHORITY,
        )
    assurance = store.verify_contract(target)
    authority = STRICT_LEGACY_AUTHORITY
    if assurance.status == "valid" and assurance.contract is not None:
        classification = assurance.contract.classification
        authority = RunbookAuthority(
            authorized_profile=classification.authorized_profile.value,
            lite_candidate=classification.lite_candidate,
            obligation_source="authorized_profile",
        )

    readiness = classify_requirement_text(requirement_text)
    if readiness != "substantive":
        return WorkflowState(
            kind="requirement-capture",
            active_issue_id=target.issue_id,
            reason_code="requirement-scaffold",
            artifact_readiness=readiness,
            authority=authority,
        )

    if assurance.status == "valid" and assurance.contract is not None:
        design_readiness = _classify_design_text(_read_optional_text(Path(target.issue_dir) / "design.md"))
        if design_readiness != "substantive":
            return WorkflowState(
                kind="blocked",
                active_issue_id=target.issue_id,
                reason_code="design-missing" if design_readiness == "missing" else "design-not-substantive",
                artifact_readiness="substantive",
                authority=authority,
                details=(
                    "design.md must be a substantive design artifact before issue execution.",
                    "Complete the design artifact before relying on the approved implementation plan.",
                ),
            )
        plan_readiness = _classify_plan_text(_read_optional_text(Path(target.issue_dir) / "plan.md"))
        if plan_readiness != "executable":
            return WorkflowState(
                kind="blocked",
                active_issue_id=target.issue_id,
                reason_code="plan-missing" if plan_readiness == "missing" else "plan-not-executable",
                artifact_readiness="substantive",
                authority=authority,
                details=(
                    "plan.md must be an executable workflow contract before issue execution.",
                    "Add implementation steps, verification obligations, reviewer/no-review rationale, and report evidence destinations.",
                ),
            )
        report_gate = evaluate_report_evidence_gate(
            _read_optional_text(Path(target.issue_dir) / "report.md"),
            authority.authorized_profile,
        )
        if report_gate.status != "pass":
            return WorkflowState(
                kind="blocked",
                active_issue_id=target.issue_id,
                reason_code=report_gate.reason_code,
                artifact_readiness="substantive",
                authority=authority,
                details=report_gate.details,
            )
        return WorkflowState(
            kind="ready",
            active_issue_id=target.issue_id,
            reason_code="assurance-valid",
            artifact_readiness="substantive",
            authority=authority,
        )
    if assurance.status == "invalid":
        return WorkflowState(
            kind="classification-required",
            active_issue_id=target.issue_id,
            reason_code="authority-invalid",
            artifact_readiness="substantive",
            authority=UNAVAILABLE_AUTHORITY,
            details=tuple(assurance.details),
        )
    design_readiness = _classify_design_text(_read_optional_text(Path(target.issue_dir) / "design.md"))
    if design_readiness != "substantive":
        return WorkflowState(
            kind="blocked",
            active_issue_id=target.issue_id,
            reason_code="design-missing" if design_readiness == "missing" else "design-not-substantive",
            artifact_readiness="substantive",
            authority=STRICT_LEGACY_AUTHORITY,
            details=(
                "design.md must be a substantive design artifact before strict-legacy issue execution.",
                "Complete the design artifact or create a valid assurance contract before execution.",
            ),
        )
    plan_readiness = _classify_plan_text(_read_optional_text(Path(target.issue_dir) / "plan.md"))
    if plan_readiness != "executable":
        return WorkflowState(
            kind="blocked",
            active_issue_id=target.issue_id,
            reason_code="plan-missing" if plan_readiness == "missing" else "plan-not-executable",
            artifact_readiness="substantive",
            authority=STRICT_LEGACY_AUTHORITY,
            details=(
                "plan.md must be an executable workflow contract before strict-legacy issue execution.",
                "Add implementation steps, verification obligations, reviewer/no-review rationale, and report evidence destinations.",
            ),
        )
    report_gate = evaluate_report_evidence_gate(
        _read_optional_text(Path(target.issue_dir) / "report.md"),
        STRICT_LEGACY_AUTHORITY.authorized_profile,
    )
    if report_gate.status != "pass":
        return WorkflowState(
            kind="blocked",
            active_issue_id=target.issue_id,
            reason_code=report_gate.reason_code,
            artifact_readiness="substantive",
            authority=STRICT_LEGACY_AUTHORITY,
            details=report_gate.details,
        )
    return WorkflowState(
        kind="ready",
        active_issue_id=target.issue_id,
        reason_code="strict-legacy-missing-assurance",
        artifact_readiness="substantive",
        authority=STRICT_LEGACY_AUTHORITY,
    )


def _read_optional_text(path: Path) -> str | None:
    try:
        if path.is_symlink() or not path.exists() or not path.is_file():
            return None
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _classify_plan_text(plan_text: str | None) -> str:
    if plan_text is None:
        return "missing"
    stripped = plan_text.strip()
    if not stripped:
        return "scaffold"
    lower = stripped.lower()
    frontmatter_scaffold_markers = (
        '状態: "draft',
        "状態: draft",
        "draft | proposed",
        "artifact_state: awaiting-assurance-compose",
        "todo",
        "tbd",
    )
    if _frontmatter_has_any(lower, frontmatter_scaffold_markers):
        return "scaffold"
    executable_markers = (
        "実装ステップ",
        "具体テストケース",
        "振る舞いバックログ",
        "実行中の振る舞い",
        "tdd サイクル",
        "step closure contract",
        "approved-no-op",
        "decision-only closure",
    )
    has_executable_marker = any(marker in lower for marker in executable_markers) or _has_lite_executable_plan(lower)
    scaffold_markers = (
        "no structured implementation steps",
        "no implementation steps",
        "no executable steps",
        "record red, green, and refactor evidence",
        "link each closure id to its observed verification result",
        "未記入",
        "記載してください",
    )
    if not has_executable_marker and any(marker in lower for marker in scaffold_markers):
        return "scaffold"
    if has_executable_marker and _has_placeholder_entries(stripped):
        return "scaffold"
    if has_executable_marker:
        return "executable"
    return "scaffold"


def _has_lite_executable_plan(text: str) -> bool:
    has_change_checklist = "変更チェックリスト" in text
    has_verification = "軽量検証" in text or "lightweight verification" in text
    return has_change_checklist and has_verification


def _has_placeholder_table_rows(text: str) -> bool:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.count("|") < 3:
            continue
        cells = [cell.strip().strip("`").lower() for cell in stripped.strip("|").split("|")]
        if any(_has_generated_placeholder_token(cell) for cell in cells):
            return True
    return False


def _classify_design_text(design_text: str | None) -> str:
    if design_text is None:
        return "missing"
    stripped = design_text.strip()
    if not stripped:
        return "scaffold"
    lower = stripped.lower()
    frontmatter_scaffold_markers = (
        '状態: "draft',
        "状態: draft",
        "draft | proposed",
        "artifact_state: awaiting-assurance-compose",
        "todo",
        "tbd",
    )
    if _frontmatter_has_any(lower, frontmatter_scaffold_markers):
        return "scaffold"
    scaffold_markers = (
        "未記入",
        "記載してください",
        "設計 placeholder",
        "design placeholder",
        "placeholder design",
    )
    if any(marker in lower for marker in scaffold_markers):
        return "scaffold"
    if _has_placeholder_entries(stripped):
        return "scaffold"
    markers = (
        "設計",
        "全体像",
        "コンポーネント",
        "データモデル",
        "責務",
        "design",
        "architecture",
        "component",
        "interface",
        "contract",
    )
    if any(marker in lower for marker in markers):
        return "substantive"
    return "scaffold"


def _has_placeholder_entries(text: str) -> bool:
    return _has_placeholder_list_items(text) or _has_placeholder_table_rows(text) or _has_placeholder_code_spans(text)


def _has_placeholder_code_spans(text: str) -> bool:
    return any(_has_generated_placeholder_id_token(token) for token in re.findall(r"`([^`]+)`", text))


def _has_placeholder_list_items(text: str) -> bool:
    for line in text.splitlines():
        item_match = re.match(r"^\s*(?:[-*]|\d+[.)])\s+(.+?)\s*$", line)
        if item_match is None:
            continue
        item_text = item_match.group(1).strip().strip("`").lower()
        if _has_generated_placeholder_token(item_text) or item_text.endswith(": ...") or item_text.endswith("： ..."):
            return True
    return False


def _has_generated_placeholder_token(text: str) -> bool:
    normalized = text.strip().strip("`").lower()
    if _is_generated_placeholder_token(normalized):
        return True
    tokens = re.findall(r"[a-z][a-z0-9_-]*-(?:\.\.\.|xxx)|#\.\.\.", normalized)
    return any(_is_generated_placeholder_token(token) for token in tokens)


def _has_generated_placeholder_id_token(text: str) -> bool:
    normalized = text.strip().strip("`").lower()
    tokens = re.findall(r"[a-z][a-z0-9_-]*-(?:\.\.\.|xxx)|#\.\.\.", normalized)
    return any(_is_generated_placeholder_token(token) for token in tokens)


def _is_generated_placeholder_token(text: str) -> bool:
    return (
        text == "..."
        or "#..." in text
        or re.fullmatch(r"[a-z][a-z0-9_-]*-(?:\.\.\.|xxx)", text) is not None
        or re.fullmatch(r"[a-z][a-z0-9_]*(?:\.\.\.|xxx)", text) is not None
    )


def _frontmatter_has_any(text: str, markers: tuple[str, ...]) -> bool:
    frontmatter = _frontmatter_text(text)
    return any(marker in frontmatter for marker in markers)


def _frontmatter_text(text: str) -> str:
    if not text.startswith("---"):
        return ""
    parts = text.split("---", 2)
    if len(parts) < 3:
        return ""
    return parts[1]
