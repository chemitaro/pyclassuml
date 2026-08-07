from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from spec_dock_runtime.domain.assurance import auto_lite_readiness_report
from spec_dock_runtime.presentation.contracts import CliText

if TYPE_CHECKING:
    from spec_dock_runtime.application.contracts import AssuranceResult


def render_assurance_text(result: AssuranceResult) -> CliText:
    status_text = "ok" if result.ok else "failed"
    lines = [
        f"assurance {result.operation}: {status_text}",
        f"issue: {result.target.issue_id}",
        f"mode: {result.mode}",
        f"has_contract: {_bool_text(result.has_contract)}",
    ]
    classification = _classification_payload(result)
    if classification is not None:
        lines.extend([
            f"authorized_profile: {classification['authorized_profile']}",
            f"complexity_tier: {classification['complexity_tier']}",
        ])
        if result.has_contract:
            lines.extend([
                f"lite_candidate: {_bool_text(bool(classification['lite_candidate']))}",
                f"lite_authorized: {_bool_text(bool(classification['lite_authorized']))}",
            ])
    lines.append(f"reason: {result.reason}")
    if result.details:
        lines.append("details:")
        lines.extend(f"- {detail}" for detail in result.details)
    if result.changed_paths:
        lines.append("changed_paths:")
        lines.extend(f"- {path}" for path in result.changed_paths)
    if result.warnings:
        lines.append("warnings:")
        lines.extend(f"- {warning}" for warning in result.warnings)
    if result.errors:
        lines.append("errors:")
        lines.extend(f"- {error}" for error in result.errors)
    return CliText(stdout_lines=lines, stderr_lines=[], warnings=[])


def render_assurance_json(result: AssuranceResult) -> str:
    return json.dumps(_result_payload(result), ensure_ascii=False, separators=(",", ":"))


def _result_payload(result: AssuranceResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "operation": result.operation,
        "ok": result.ok,
        "status": result.status,
        "issue_id": result.target.issue_id,
        "issue_path": result.target.repo_relative_path,
        "mode": result.mode,
        "has_contract": result.has_contract,
        "reason": result.reason,
        "details": list(result.details),
    }
    if result.dry_run:
        payload["dry_run"] = True
    if result.written_path is not None:
        payload["written_path"] = str(result.written_path)
    if result.authorized_profile is not None:
        payload["authorized_profile"] = result.authorized_profile
    if result.lite_candidate is not None:
        payload["lite_candidate"] = result.lite_candidate
    if result.changed_paths:
        payload["changed_paths"] = list(result.changed_paths)
    elif result.operation == "compose":
        payload["changed_paths"] = []
    if result.artifacts:
        payload["artifacts"] = {
            artifact.artifact: {
                "path": artifact.path,
                "changed": artifact.changed,
                "added_section_ids": list(artifact.added_section_ids),
                "preserved_section_ids": list(artifact.preserved_section_ids),
                "warnings": list(artifact.warnings),
                "errors": list(artifact.errors),
            }
            for artifact in result.artifacts
        }
    elif result.operation == "compose":
        payload["artifacts"] = {}
    if result.warnings:
        payload["warnings"] = list(result.warnings)
    elif result.operation == "compose":
        payload["warnings"] = []
    if result.errors:
        payload["errors"] = list(result.errors)
    elif result.operation == "compose":
        payload["errors"] = []
    classification = _classification_payload(result)
    if classification is not None:
        payload["classification"] = classification
    if result.contract is not None:
        payload["contract"] = result.contract.to_dict()
    return _with_auto_lite_readiness(payload, result)


def _classification_payload(result: AssuranceResult) -> dict[str, Any] | None:
    if result.contract is not None:
        return result.contract.classification.to_dict()
    if result.status == "missing" and result.mode == "strict-legacy":
        return {
            "authorized_profile": "strict",
            "complexity_tier": "complex",
            "lite_candidate": False,
            "lite_authorized": False,
            "reason_codes": ["strict_legacy_missing_assurance_contract"],
            "hard_triggers": [],
            "unknown_facts": [],
        }
    return None


def _with_auto_lite_readiness(payload: dict[str, Any], result: AssuranceResult) -> dict[str, Any]:
    readiness = _auto_lite_readiness_payload(result)
    if readiness is not None:
        payload["auto_lite_readiness"] = readiness
    return payload


def _auto_lite_readiness_payload(result: AssuranceResult) -> dict[str, object] | None:
    if result.contract is not None:
        return auto_lite_readiness_report(result.contract.classification)
    if result.status == "missing" and result.mode == "strict-legacy":
        classification = _classification_payload(result)
        if classification is None:
            return None
        return {
            "automatic_lite_default_enabled": False,
            "lite_candidate": False,
            "lite_authorized": False,
            "future_adoption_requires": [
                "accepted_adr",
                "policy_version_bump",
                "rollout_issue",
                "telemetry_gate",
            ],
            "adoption_blockers": [
                "assurance_contract_missing",
                "accepted_adr_missing",
                "policy_version_bump_missing",
                "rollout_issue_missing",
                "telemetry_gate_missing",
            ],
            "rollback_mode": "strict-legacy",
            "automation_stalled_routes_to": "human_gate",
            "required_metrics": [
                "false_positive_candidates",
                "escalation_rate",
                "p0_p1_escape",
                "post_review_blocker",
                "wall_clock_token_delta",
                "missing_metrics_summary",
            ],
            "missing_metrics_summary": {
                "present": True,
                "missing": [
                    "false_positive_candidates",
                    "escalation_rate",
                    "p0_p1_escape",
                    "post_review_blocker",
                    "wall_clock_token_delta",
                    "missing_metrics_summary",
                ],
            },
            "efficiency_baseline": {
                "profiles": {
                    "lite": {
                        "invocation_count": 1,
                        "runbook_sections": 3,
                        "review_generation_required": False,
                        "wall_clock_token_proxy": 1,
                    },
                    "standard": {
                        "invocation_count": 2,
                        "runbook_sections": 6,
                        "review_generation_required": True,
                        "wall_clock_token_proxy": 3,
                    },
                    "strict": {
                        "invocation_count": 3,
                        "runbook_sections": 9,
                        "review_generation_required": True,
                        "wall_clock_token_proxy": 5,
                    },
                },
                "comparison": {
                    "lite_vs_standard_wall_clock_token_proxy_delta": -2,
                    "standard_vs_strict_wall_clock_token_proxy_delta": -2,
                },
            },
        }
    return None


def _bool_text(value: bool) -> str:
    return "true" if value else "false"
