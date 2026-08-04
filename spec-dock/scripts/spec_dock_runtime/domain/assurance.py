from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from typing import Literal

POLICY_VERSION = "assurance-policy-v1"
SCHEMA_VERSION = 1

FactValue = Literal["true", "false", "unknown"]


class AssuranceProfile(str, Enum):
    LITE = "lite"
    STANDARD = "standard"
    STRICT = "strict"
    CRITICAL = "critical"


class ComplexityTier(str, Enum):
    ROUTINE = "routine"
    NORMAL = "normal"
    COMPLEX = "complex"
    DEEP = "deep"


class ClassificationStage(str, Enum):
    REQUIREMENT = "requirement"


class AssuranceStatus(str, Enum):
    PROVISIONAL = "provisional"


class AssuranceMode(str, Enum):
    ADAPTIVE = "adaptive"
    STRICT_LEGACY = "strict-legacy"


@dataclass(frozen=True)
class RiskFact:
    key: str
    value: FactValue
    source: str
    reason_code: str

    def to_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "value": self.value,
            "source": self.source,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True)
class SourceArtifact:
    path: str
    role: str
    sha256: str
    display_path: str | None = None

    def to_dict(self) -> dict[str, str]:
        payload = {
            "path": self.path,
            "role": self.role,
            "sha256": self.sha256,
        }
        if self.display_path is not None:
            payload["display_path"] = self.display_path
        return payload


@dataclass(frozen=True)
class SourceBinding:
    artifacts: tuple[SourceArtifact, ...]

    def to_dict(self) -> dict[str, list[dict[str, str]]]:
        return {
            "artifacts": [
                artifact.to_dict()
                for artifact in sorted(
                    self.artifacts, key=lambda artifact: (artifact.path, artifact.role, artifact.sha256)
                )
            ],
        }


@dataclass(frozen=True)
class AssuranceClassification:
    authorized_profile: AssuranceProfile
    complexity_tier: ComplexityTier
    lite_candidate: bool
    lite_authorized: bool
    reason_codes: tuple[str, ...]
    hard_triggers: tuple[str, ...]
    unknown_facts: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "authorized_profile": self.authorized_profile.value,
            "complexity_tier": self.complexity_tier.value,
            "lite_candidate": self.lite_candidate,
            "lite_authorized": self.lite_authorized,
            "reason_codes": list(self.reason_codes),
            "hard_triggers": list(self.hard_triggers),
            "unknown_facts": list(self.unknown_facts),
        }


@dataclass(frozen=True)
class AssuranceContract:
    schema_version: int
    policy_version: str
    issue_id: str
    stage: ClassificationStage
    status: AssuranceStatus
    mode: AssuranceMode
    source_binding: SourceBinding
    classification: AssuranceClassification
    risk_facts: tuple[RiskFact, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "issue_id": self.issue_id,
            "stage": self.stage.value,
            "status": self.status.value,
            "mode": self.mode.value,
            "source_binding": self.source_binding.to_dict(),
            "classification": self.classification.to_dict(),
            "risk_facts": [fact.to_dict() for fact in self.risk_facts],
            "obligations": {
                "profile_preset": self.classification.authorized_profile.value,
                "notes": [],
            },
        }


SUPPORTED_FACT_KEYS = (
    "docs_only_change",
    "explicit_lite_opt_in",
    "lite_evidence_gate_passed",
    "migration_or_persistence_change",
    "public_contract_change",
    "rollback_difficulty_high",
    "runtime_behavior_change",
    "security_or_privacy_sensitive",
)

DEFAULT_FACT_VALUES: dict[str, FactValue] = {
    "docs_only_change": "unknown",
    "explicit_lite_opt_in": "false",
    "lite_evidence_gate_passed": "false",
    "migration_or_persistence_change": "unknown",
    "public_contract_change": "unknown",
    "rollback_difficulty_high": "unknown",
    "runtime_behavior_change": "unknown",
    "security_or_privacy_sensitive": "unknown",
}

_LITE_PREDICATE_EXPECTATIONS: dict[str, FactValue] = {
    "docs_only_change": "true",
    "migration_or_persistence_change": "false",
    "public_contract_change": "false",
    "rollback_difficulty_high": "false",
    "runtime_behavior_change": "false",
    "security_or_privacy_sensitive": "false",
}

_LITE_PREDICATE_UNKNOWN_REASON: dict[str, str] = {
    "docs_only_change": "lite_predicate_docs_only_unknown",
    "runtime_behavior_change": "lite_predicate_runtime_behavior_unknown",
}

_HARD_TRIGGER_PROFILE: dict[str, AssuranceProfile] = {
    "migration_or_persistence_change": AssuranceProfile.STRICT,
    "public_contract_change": AssuranceProfile.STRICT,
    "rollback_difficulty_high": AssuranceProfile.STRICT,
    "security_or_privacy_sensitive": AssuranceProfile.CRITICAL,
}

_HARD_TRIGGER_UNKNOWN_REASON: dict[str, str] = {
    "migration_or_persistence_change": "hard_trigger_migration_unknown",
    "public_contract_change": "hard_trigger_public_contract_unknown",
    "rollback_difficulty_high": "hard_trigger_rollback_unknown",
    "security_or_privacy_sensitive": "hard_trigger_security_unknown",
}

_PROFILE_ORDER = {
    AssuranceProfile.LITE: 0,
    AssuranceProfile.STANDARD: 1,
    AssuranceProfile.STRICT: 2,
    AssuranceProfile.CRITICAL: 3,
}


def default_risk_facts(source: str = "requirement") -> tuple[RiskFact, ...]:
    return risk_facts_from_values(DEFAULT_FACT_VALUES, source=source, reason_prefix="fact_default")


def lite_positive_values() -> dict[str, FactValue]:
    values = dict(DEFAULT_FACT_VALUES)
    values.update(_LITE_PREDICATE_EXPECTATIONS)
    return values


def risk_facts_from_values(
    values: dict[str, FactValue],
    *,
    source: str,
    reason_prefix: str,
) -> tuple[RiskFact, ...]:
    missing_keys = set(SUPPORTED_FACT_KEYS) - set(values)
    unknown_keys = set(values) - set(SUPPORTED_FACT_KEYS)
    if missing_keys:
        missing = ", ".join(sorted(missing_keys))
        raise ValueError(f"missing supported assurance facts: {missing}")
    if unknown_keys:
        unknown = ", ".join(sorted(unknown_keys))
        raise ValueError(f"unsupported assurance facts: {unknown}")

    facts = []
    for key in SUPPORTED_FACT_KEYS:
        value = values[key]
        if value not in ("true", "false", "unknown"):
            raise ValueError(f"unsupported assurance fact value for {key}: {value}")
        facts.append(RiskFact(key=key, value=value, source=source, reason_code=f"{reason_prefix}_{key}"))
    return tuple(facts)


def classify_risk_facts(risk_facts: tuple[RiskFact, ...]) -> AssuranceClassification:
    values = _fact_values_by_key(risk_facts)
    reason_codes = {fact.reason_code for fact in risk_facts}
    reason_codes.add("standard_default")

    lite_candidate = _is_lite_candidate(values)
    for key, _expected in _LITE_PREDICATE_EXPECTATIONS.items():
        if values[key] == "unknown" and key in _LITE_PREDICATE_UNKNOWN_REASON:
            reason_codes.add(_LITE_PREDICATE_UNKNOWN_REASON[key])

    hard_triggers = []
    unknown_facts = []
    authorized_profile = AssuranceProfile.STANDARD
    complexity_tier = ComplexityTier.NORMAL
    for key, trigger_profile in _HARD_TRIGGER_PROFILE.items():
        value = values[key]
        if value == "true":
            hard_triggers.append(key)
            authorized_profile = _max_profile(authorized_profile, trigger_profile)
            complexity_tier = _max_tier(
                complexity_tier,
                ComplexityTier.DEEP if trigger_profile == AssuranceProfile.CRITICAL else ComplexityTier.COMPLEX,
            )
            reason_codes.add(f"hard_trigger_{key}")
        elif value == "unknown":
            unknown_facts.append(key)
            reason_codes.add(_HARD_TRIGGER_UNKNOWN_REASON[key])

    opt_in = values["explicit_lite_opt_in"] == "true"
    evidence_gate = values["lite_evidence_gate_passed"] == "true"
    if not opt_in:
        reason_codes.add("lite_opt_in_missing_or_unknown")
    if not evidence_gate:
        reason_codes.add("lite_evidence_gate_missing_or_unknown")

    lite_authorized = lite_candidate and opt_in and evidence_gate and not hard_triggers
    if lite_authorized:
        authorized_profile = AssuranceProfile.LITE

    return AssuranceClassification(
        authorized_profile=authorized_profile,
        complexity_tier=complexity_tier,
        lite_candidate=lite_candidate,
        lite_authorized=lite_authorized,
        reason_codes=tuple(sorted(reason_codes)),
        hard_triggers=tuple(sorted(hard_triggers)),
        unknown_facts=tuple(sorted(unknown_facts)),
    )


def auto_lite_readiness_report(classification: AssuranceClassification) -> dict[str, object]:
    missing_metrics = (
        "false_positive_candidates",
        "escalation_rate",
        "p0_p1_escape",
        "post_review_blocker",
        "wall_clock_token_delta",
        "missing_metrics_summary",
    )
    adoption_blockers = (
        "accepted_adr_missing",
        "policy_version_bump_missing",
        "rollout_issue_missing",
        "telemetry_gate_missing",
    )
    return {
        "automatic_lite_default_enabled": False,
        "lite_candidate": classification.lite_candidate,
        "lite_authorized": classification.lite_authorized,
        "future_adoption_requires": [
            "accepted_adr",
            "policy_version_bump",
            "rollout_issue",
            "telemetry_gate",
        ],
        "adoption_blockers": list(adoption_blockers),
        "rollback_mode": "strict-legacy",
        "automation_stalled_routes_to": "human_gate",
        "required_metrics": list(missing_metrics),
        "missing_metrics_summary": {
            "present": True,
            "missing": list(missing_metrics),
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


def build_assurance_contract(
    *,
    issue_id: str,
    stage: ClassificationStage,
    source_binding: SourceBinding,
    risk_facts: tuple[RiskFact, ...] | None = None,
) -> AssuranceContract:
    effective_facts = (
        default_risk_facts() if risk_facts is None else tuple(sorted(risk_facts, key=lambda fact: fact.key))
    )
    classification = classify_risk_facts(effective_facts)
    return AssuranceContract(
        schema_version=SCHEMA_VERSION,
        policy_version=POLICY_VERSION,
        issue_id=issue_id,
        stage=stage,
        status=AssuranceStatus.PROVISIONAL,
        mode=AssuranceMode.ADAPTIVE,
        source_binding=source_binding,
        classification=classification,
        risk_facts=effective_facts,
    )


def canonical_json_bytes(contract: AssuranceContract) -> bytes:
    return json.dumps(contract.to_dict(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def validate_assurance_contract(contract: AssuranceContract) -> tuple[str, ...]:
    errors = []
    if contract.schema_version != SCHEMA_VERSION:
        errors.append("unsupported_schema_version")
    if contract.policy_version != POLICY_VERSION:
        errors.append("unsupported_policy_version")
    if contract.mode != AssuranceMode.ADAPTIVE:
        errors.append("unsupported_persisted_mode")
    if contract.stage != ClassificationStage.REQUIREMENT:
        errors.append("unsupported_stage")
    if not contract.source_binding.artifacts:
        errors.append("missing_source_binding_artifacts")
    expected_source_filenames = {
        "requirement": "requirement.md",
        "design": "design.md",
        "plan": "plan.md",
    }
    expected_source_roles = set(expected_source_filenames)
    actual_source_roles = {artifact.role for artifact in contract.source_binding.artifacts}
    for role in sorted(expected_source_roles - actual_source_roles):
        errors.append(f"missing_source_binding_role:{role}")
    for artifact in contract.source_binding.artifacts:
        if not artifact.path:
            errors.append("missing_source_binding_path")
        elif artifact.path.startswith("/") or artifact.path.startswith("spec-dock/active/"):
            errors.append("non_durable_source_binding_path")
        if artifact.role not in ("requirement", "design", "plan"):
            errors.append("unsupported_source_binding_role")
        elif not artifact.path.endswith(f"/{expected_source_filenames[artifact.role]}"):
            errors.append(f"source_binding_role_path_mismatch:{artifact.role}")
        if not _is_lowercase_sha256(artifact.sha256):
            errors.append("invalid_source_binding_sha256")
    expected_classification = classify_risk_facts(contract.risk_facts)
    if contract.classification != expected_classification:
        errors.append("classification_mismatch")
    return tuple(errors)


def _is_lowercase_sha256(value: str) -> bool:
    if len(value) != 64:
        return False
    return all(char in "0123456789abcdef" for char in value)


def _fact_values_by_key(risk_facts: tuple[RiskFact, ...]) -> dict[str, FactValue]:
    values: dict[str, FactValue] = {}
    duplicate_keys = []
    invalid_values = []
    for fact in risk_facts:
        if fact.key in values:
            duplicate_keys.append(fact.key)
            continue
        if fact.value not in ("true", "false", "unknown"):
            invalid_values.append((fact.key, fact.value))
        values[fact.key] = fact.value

    if duplicate_keys:
        duplicates = ", ".join(sorted(set(duplicate_keys)))
        raise ValueError(f"duplicate assurance facts: {duplicates}")
    if invalid_values:
        key, value = sorted(invalid_values)[0]
        raise ValueError(f"unsupported assurance fact value for {key}: {value}")

    missing_keys = set(SUPPORTED_FACT_KEYS) - set(values)
    unknown_keys = set(values) - set(SUPPORTED_FACT_KEYS)
    if missing_keys:
        missing = ", ".join(sorted(missing_keys))
        raise ValueError(f"missing supported assurance facts: {missing}")
    if unknown_keys:
        unknown = ", ".join(sorted(unknown_keys))
        raise ValueError(f"unsupported assurance facts: {unknown}")
    return values


def _is_lite_candidate(values: dict[str, FactValue]) -> bool:
    return all(values[key] == expected for key, expected in _LITE_PREDICATE_EXPECTATIONS.items())


def _max_profile(left: AssuranceProfile, right: AssuranceProfile) -> AssuranceProfile:
    return left if _PROFILE_ORDER[left] >= _PROFILE_ORDER[right] else right


def _max_tier(left: ComplexityTier, right: ComplexityTier) -> ComplexityTier:
    order = {
        ComplexityTier.ROUTINE: 0,
        ComplexityTier.NORMAL: 1,
        ComplexityTier.COMPLEX: 2,
        ComplexityTier.DEEP: 3,
    }
    return left if order[left] >= order[right] else right
