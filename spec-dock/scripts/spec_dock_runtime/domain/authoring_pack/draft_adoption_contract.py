from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Literal

from spec_dock_runtime.domain.authoring_pack.authority_boundary import (
    scan_authoring_payload,
    scan_forbidden_authority_flags,
    scan_sensitive_payload,
)
from spec_dock_runtime.domain.authoring_pack.prompt_pack_contract import (
    ADOPTION_STATUS,
    AUTHORITY,
    BUNDLE_GENERATION_NOT_PROMOTION,
)
from spec_dock_runtime.domain.authoring_pack.zip_contract import MAX_ENTRY_BYTES

DraftAdoptionStatus = Literal["pass", "fail", "blocked", "stale", "rejected"]

FORBIDDEN_DRAFT_AUTHORITY_FLAG_KEYS = (
    "canonical_adoption",
    "canonical_written",
    "node_creation_performed",
    "assurance_mutation",
    "assurance_mutated",
    "authorized_profile_decision",
    "reviewer_pass",
    "reviewer_pass_claimed",
    "execution_ready",
    "pr_ready",
    "merge_ready",
    "pr_delivery",
    "pr_delivered",
)


@dataclass(frozen=True)
class DraftAdoptionResult:
    status: DraftAdoptionStatus
    input_path: str
    validation_kind: str
    authority: str = AUTHORITY
    adoption_status: str = ADOPTION_STATUS
    bundle_generation_not_promotion: bool = BUNDLE_GENERATION_NOT_PROMOTION
    evidence_mode: str = "github-synced"
    review_status: str | None = None
    review_gate_passed: bool = False
    issue_id: str | None = None
    parent_epic_id: str | None = None
    parent_initiative_id: str | None = None
    expected_review_digest: str | None = None
    observed_review_digest: str | None = None
    expected_draft_pack_digest: str | None = None
    observed_draft_pack_digest: str | None = None
    expected_source_manifest_hash: str | None = None
    observed_source_manifest_hash: str | None = None
    expected_profile: str | None = None
    observed_profile: str | None = None
    draft_count: int = 0
    valid_draft_count: int = 0
    section_count: int = 0
    valid_section_count: int = 0
    eal_disposition_required: bool = False
    canonical_targets: dict[str, str] | None = None
    node_creation_performed: bool = False
    canonical_written: bool = False
    assurance_mutated: bool = False
    reviewer_pass_claimed: bool = False
    execution_ready: bool = False
    pr_ready: bool = False
    findings: tuple[str, ...] = ()
    comparison: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "input_path": self.input_path,
            "validation_kind": self.validation_kind,
            "authority": self.authority,
            "adoption_status": self.adoption_status,
            "bundle_generation_not_promotion": self.bundle_generation_not_promotion,
            "evidence_mode": self.evidence_mode,
            "review_status": self.review_status,
            "review_gate_passed": self.review_gate_passed,
            "issue_id": self.issue_id,
            "parent_epic_id": self.parent_epic_id,
            "parent_initiative_id": self.parent_initiative_id,
            "expected_review_digest": self.expected_review_digest,
            "observed_review_digest": self.observed_review_digest,
            "expected_draft_pack_digest": self.expected_draft_pack_digest,
            "observed_draft_pack_digest": self.observed_draft_pack_digest,
            "expected_source_manifest_hash": self.expected_source_manifest_hash,
            "observed_source_manifest_hash": self.observed_source_manifest_hash,
            "expected_profile": self.expected_profile,
            "observed_profile": self.observed_profile,
            "draft_count": self.draft_count,
            "valid_draft_count": self.valid_draft_count,
            "section_count": self.section_count,
            "valid_section_count": self.valid_section_count,
            "eal_disposition_required": self.eal_disposition_required,
            "canonical_targets": self.canonical_targets,
            "node_creation_performed": self.node_creation_performed,
            "canonical_written": self.canonical_written,
            "assurance_mutated": self.assurance_mutated,
            "reviewer_pass_claimed": self.reviewer_pass_claimed,
            "execution_ready": self.execution_ready,
            "pr_ready": self.pr_ready,
            "findings": list(self.findings),
            "comparison": list(self.comparison),
        }


def validate_issue_draft_adoption_payload(
    payload: dict[str, object],
    *,
    input_path: Path,
    issue_dir: Path,
    review_status: str,
    review_digest: str | None,
    expected_review_digest: str | None,
    expected_draft_pack_digest: str | None,
    additional_expected_draft_pack_digest: str | None,
    expected_source_hash: str | None,
    evidence_mode: str,
) -> DraftAdoptionResult:
    findings: list[str] = []
    comparison: list[str] = []
    if payload.get("schema_version") != "issue-draft-adoption-v1":
        findings.append("invalid_schema_version")
    _validate_authority_claims(payload, findings)

    meta = _read_json(issue_dir / ".meta.json", ".meta.json", findings)
    issue_id = _string(payload, "issue_id", findings)
    parent_epic_id = _string(payload, "parent_epic_id", findings)
    parent_initiative_id = _string(payload, "parent_initiative_id", findings)
    if isinstance(meta, dict):
        if issue_id and meta.get("id") != issue_id:
            comparison.append("issue_id_mismatch")
        if parent_epic_id and meta.get("epic_id") != parent_epic_id:
            comparison.append("parent_epic_mismatch")
        if parent_initiative_id and meta.get("initiative_id") != parent_initiative_id:
            comparison.append("parent_initiative_mismatch")

    observed_draft_pack_digest = _digest_value(payload.get("draft_pack_digest"))
    if not observed_draft_pack_digest:
        findings.append("missing_or_invalid_field:draft_pack_digest")
    if expected_draft_pack_digest and observed_draft_pack_digest != _digest_value(expected_draft_pack_digest):
        comparison.append("draft_pack_digest_mismatch")
    if additional_expected_draft_pack_digest and observed_draft_pack_digest != _digest_value(
        additional_expected_draft_pack_digest
    ):
        comparison.append("draft_pack_digest_mismatch")
    if expected_review_digest and review_digest != _digest_value(expected_review_digest):
        comparison.append("review_digest_mismatch")
    source_hash = _digest_value(payload.get("source_manifest_hash"))
    if expected_source_hash and source_hash != _digest_value(expected_source_hash):
        comparison.append("source_manifest_hash_mismatch")

    canonical_targets = payload.get("canonical_targets")
    _validate_canonical_targets(canonical_targets, findings)
    eal_disposition_required = payload.get("eal_disposition_required") is True
    if not eal_disposition_required:
        findings.append("missing_or_invalid_field:eal_disposition_required")

    drafts = payload.get("drafts")
    valid_draft_count = 0
    if not isinstance(drafts, dict):
        findings.append("missing_or_invalid_field:drafts")
        draft_count = 0
    else:
        draft_count = len(drafts)
        for key in ("requirement", "design", "plan"):
            item = drafts.get(key)
            if not isinstance(item, dict):
                findings.append(f"missing_or_invalid_field:drafts.{key}")
                continue
            if _validate_draft_item(issue_dir, item, key, findings, comparison):
                valid_draft_count += 1

    status = _status_from_findings(findings, comparison)
    return DraftAdoptionResult(
        status=status,
        input_path=str(input_path),
        validation_kind="issue-draft-adoption",
        evidence_mode=evidence_mode,
        review_status=review_status,
        review_gate_passed=review_status == "pass" and status == "pass",
        issue_id=issue_id,
        parent_epic_id=parent_epic_id,
        parent_initiative_id=parent_initiative_id,
        expected_review_digest=_digest_value(expected_review_digest),
        observed_review_digest=review_digest,
        expected_draft_pack_digest=_digest_value(expected_draft_pack_digest),
        observed_draft_pack_digest=observed_draft_pack_digest,
        expected_source_manifest_hash=_digest_value(expected_source_hash),
        observed_source_manifest_hash=source_hash,
        draft_count=draft_count,
        valid_draft_count=valid_draft_count if status == "pass" else 0,
        eal_disposition_required=eal_disposition_required,
        canonical_targets=_canonical_targets_output(canonical_targets) if status == "pass" else None,
        findings=tuple(dict.fromkeys(findings)),
        comparison=tuple(dict.fromkeys(comparison)),
    )


def validate_selected_skeleton_payload(
    payload: dict[str, object],
    *,
    input_path: Path,
    issue_dir: Path,
    assurance: dict[str, object],
    selected_skeleton: dict[str, object],
    review_status: str | None,
    review_digest: str | None,
    expected_review_digest: str | None,
    expected_draft_pack_digest: str | None,
    expected_profile: str | None,
    expected_source_hash: str | None,
    evidence_mode: str,
) -> DraftAdoptionResult:
    findings: list[str] = []
    comparison: list[str] = []
    if payload.get("schema_version") != "selected-skeleton-fill-v1":
        findings.append("invalid_schema_version")
    _validate_authority_claims(payload, findings)

    meta = _read_json(issue_dir / ".meta.json", ".meta.json", findings)
    issue_id = _string(payload, "issue_id", findings)
    if isinstance(meta, dict) and issue_id and meta.get("id") != issue_id:
        comparison.append("issue_id_mismatch")

    selected_profile = _profile_from_skeleton(selected_skeleton)
    assurance_profile = _profile_from_assurance(assurance)
    observed_profile = selected_profile or assurance_profile
    if selected_profile and assurance_profile and selected_profile != assurance_profile:
        comparison.append("selected_profile_assurance_mismatch")
    if expected_profile and observed_profile != expected_profile:
        comparison.append("selected_profile_mismatch")

    source_hash = _digest_value(payload.get("source_manifest_hash"))
    if expected_source_hash and source_hash != _digest_value(expected_source_hash):
        comparison.append("source_manifest_hash_mismatch")
    if expected_review_digest and review_digest != _digest_value(expected_review_digest):
        comparison.append("review_digest_mismatch")
    observed_draft_pack_digest = _digest_value(payload.get("draft_pack_digest"))
    if not observed_draft_pack_digest:
        findings.append("missing_or_invalid_field:draft_pack_digest")
    if expected_draft_pack_digest and observed_draft_pack_digest != _digest_value(expected_draft_pack_digest):
        comparison.append("draft_pack_digest_mismatch")
    _compare_digest_field(payload, selected_skeleton, "template_hash", findings, comparison)
    _compare_digest_field(payload, selected_skeleton, "selected_skeleton_hash", findings, comparison)

    required_sections = _string_list(selected_skeleton.get("required_sections"))
    if not required_sections:
        findings.append("missing_or_invalid_field:selected_skeleton.required_sections")
    section_fills = _normalize_section_fills(payload.get("section_fills"), findings)
    valid_section_count = 0
    if section_fills is None:
        findings.append("missing_or_invalid_field:section_fills")
        section_count = 0
    else:
        section_count = len(section_fills)
        missing = sorted(set(required_sections) - set(section_fills))
        extra = sorted(set(section_fills) - set(required_sections))
        for section in missing:
            findings.append(f"missing_section_fill:{section}")
        for section in extra:
            findings.append(f"extra_section_fill:{section}")
        for section in required_sections:
            item = section_fills.get(section)
            if not isinstance(item, dict):
                continue
            if _validate_section_fill(issue_dir, item, section, findings, comparison):
                valid_section_count += 1

    status = _status_from_findings(findings, comparison)
    return DraftAdoptionResult(
        status=status,
        input_path=str(input_path),
        validation_kind="selected-skeleton-fill",
        evidence_mode=evidence_mode,
        review_status=review_status,
        review_gate_passed=review_status == "pass" and status == "pass",
        issue_id=issue_id,
        expected_review_digest=_digest_value(expected_review_digest),
        observed_review_digest=review_digest,
        expected_draft_pack_digest=_digest_value(expected_draft_pack_digest),
        observed_draft_pack_digest=observed_draft_pack_digest,
        expected_source_manifest_hash=_digest_value(expected_source_hash),
        observed_source_manifest_hash=source_hash,
        expected_profile=expected_profile,
        observed_profile=observed_profile,
        section_count=section_count,
        valid_section_count=valid_section_count if status == "pass" else 0,
        findings=tuple(dict.fromkeys(findings)),
        comparison=tuple(dict.fromkeys(comparison)),
    )


def file_sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def read_json_payload(path: Path, label: str) -> tuple[dict[str, object] | None, tuple[str, ...]]:
    findings: list[str] = []
    payload = _read_json(path, label, findings)
    if isinstance(payload, dict):
        return payload, tuple(findings)
    if payload is not None:
        findings.append(f"non_object_json:{label}")
    return None, tuple(findings)


def blocked_result(
    *,
    input_path: Path,
    validation_kind: str,
    evidence_mode: str,
    findings: tuple[str, ...],
    review_status: str | None = None,
) -> DraftAdoptionResult:
    return DraftAdoptionResult(
        status="blocked",
        input_path=str(input_path),
        validation_kind=validation_kind,
        evidence_mode=evidence_mode,
        review_status=review_status,
        findings=findings,
    )


def failed_result(
    *,
    input_path: Path,
    validation_kind: str,
    evidence_mode: str,
    findings: tuple[str, ...],
) -> DraftAdoptionResult:
    return DraftAdoptionResult(
        status="fail",
        input_path=str(input_path),
        validation_kind=validation_kind,
        evidence_mode=evidence_mode,
        findings=findings,
    )


def _read_json(path: Path, label: str, findings: list[str]) -> object | None:
    if path.is_symlink():
        findings.append(f"symlink_entry:{label}")
        return None
    if not path.is_file():
        findings.append(f"missing_json:{label}")
        return None
    try:
        size = path.stat().st_size
    except OSError:
        findings.append(f"unreadable_payload:{label}")
        return None
    if size > MAX_ENTRY_BYTES:
        findings.append(f"oversized_entry:{label}")
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        findings.append(f"binary_payload:{label}")
        return None
    except OSError:
        findings.append(f"unreadable_payload:{label}")
        return None
    findings.extend(scan_sensitive_payload(text))
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        findings.append(f"invalid_json:{label}")
        return None


def _validate_authority_claims(payload: dict[str, object], findings: list[str]) -> None:
    findings.extend(scan_forbidden_authority_flags(payload, FORBIDDEN_DRAFT_AUTHORITY_FLAG_KEYS))
    claims = payload.get("authority_claims")
    if not isinstance(claims, dict):
        findings.append("missing_or_invalid_field:authority_claims")
        return
    required_false = (
        "assurance_mutation",
        "authorized_profile_decision",
        "reviewer_pass",
        "execution_ready",
        "pr_ready",
    )
    optional_false = (
        "canonical_adoption",
        "canonical_written",
    )
    for key in required_false:
        if claims.get(key) is not False:
            findings.append(f"forbidden_authority_claim:{key}")
    for key in optional_false:
        if key in claims and claims.get(key) is not False:
            findings.append(f"forbidden_authority_claim:{key}")
    for key in ("merge_ready", "pr_delivery", "pr_delivered"):
        if claims.get(key):
            findings.append(f"forbidden_authority_claim:{key}")
    for key, value in claims.items():
        if (
            key
            not in {
                "canonical_adoption",
                "canonical_written",
                "assurance_mutation",
                "authorized_profile_decision",
                "reviewer_pass",
                "execution_ready",
                "pr_ready",
                "merge_ready",
                "pr_delivery",
                "pr_delivered",
            }
            and value
        ):
            findings.append(f"forbidden_authority_claim:{key}")


def _validate_canonical_targets(value: object, findings: list[str]) -> None:
    if not isinstance(value, dict):
        findings.append("missing_or_invalid_field:canonical_targets")
        return
    expected = {
        "requirement": "requirement.md",
        "design": "design.md",
        "plan": "plan.md",
        "report_evidence": "report.md",
    }
    for key, expected_path in expected.items():
        if value.get(key) != expected_path:
            findings.append(f"invalid_canonical_target:{key}")
    for key, target in value.items():
        if key not in expected:
            findings.append(f"unexpected_canonical_target:{key}")
            continue
        if not isinstance(target, str):
            findings.append(f"invalid_canonical_target:{key}")
            continue
        if target == ".assurance.json" or target.startswith("."):
            findings.append(f"forbidden_canonical_target:{key}")
        if _safe_rel(target, findings, allow_suffixes=(".md",)) is None:
            findings.append(f"invalid_canonical_target:{key}")


def _canonical_targets_output(value: object) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    output: dict[str, str] = {}
    for key in ("requirement", "design", "plan", "report_evidence"):
        item = value.get(key)
        if isinstance(item, str):
            output[key] = item
    return output


def _validate_draft_item(
    issue_dir: Path, item: dict[str, object], key: str, findings: list[str], comparison: list[str]
) -> bool:
    rel_value = _string(item, "path", findings, label=f"drafts.{key}")
    if not rel_value:
        return False
    rel = _safe_rel(rel_value, findings, allow_suffixes=(".md",))
    if rel is None:
        return False
    if _is_canonical_doc_rel(rel):
        findings.append(f"canonical_doc_path:drafts.{key}")
        return False
    if not rel.startswith("artifacts/"):
        findings.append(f"non_artifact_draft_path:drafts.{key}")
        return False
    target = issue_dir / rel
    if _has_symlink_component(issue_dir, target):
        findings.append(f"symlink_entry:{rel}")
        return False
    if not _validate_text_file(target, rel, findings):
        return False
    expected_sha = _digest_value(item.get("sha256"))
    observed_sha = file_sha256(target)
    if not expected_sha:
        findings.append(f"missing_or_invalid_field:drafts.{key}.sha256")
        return False
    if observed_sha != expected_sha:
        comparison.append(f"draft_sha256_mismatch:{key}")
    return True


def _validate_section_fill(
    issue_dir: Path, item: dict[str, object], section: str, findings: list[str], comparison: list[str]
) -> bool:
    rel_value = _string(item, "path", findings, label=f"section_fills.{section}")
    if not rel_value:
        return False
    rel = _safe_rel(rel_value, findings, allow_suffixes=(".md", ".json"))
    if rel is None:
        return False
    if _is_canonical_doc_rel(rel):
        findings.append(f"canonical_doc_path:section_fills.{section}")
        return False
    if not rel.startswith("artifacts/"):
        findings.append(f"non_artifact_section_path:section_fills.{section}")
        return False
    target = issue_dir / rel
    if _has_symlink_component(issue_dir, target):
        findings.append(f"symlink_entry:{rel}")
        return False
    if not _validate_text_file(target, rel, findings):
        return False
    expected_sha = _digest_value(item.get("sha256"))
    observed_sha = file_sha256(target)
    if not expected_sha:
        findings.append(f"missing_or_invalid_field:section_fills.{section}.sha256")
        return False
    if observed_sha != expected_sha:
        comparison.append(f"section_sha256_mismatch:{section}")
        return False
    return True


def _normalize_section_fills(value: object, findings: list[str]) -> dict[str, dict[str, object]] | None:
    if isinstance(value, dict):
        normalized: dict[str, dict[str, object]] = {}
        for key, item in value.items():
            if isinstance(key, str) and isinstance(item, dict):
                normalized[key] = item
            else:
                findings.append("invalid_section_fill_item")
        return normalized
    if isinstance(value, list):
        normalized = {}
        for item in value:
            if not isinstance(item, dict):
                findings.append("invalid_section_fill_item")
                continue
            section_id = item.get("section_id")
            if not isinstance(section_id, str) or not section_id:
                findings.append("missing_or_invalid_field:section_fills.section_id")
                continue
            if section_id in normalized:
                findings.append(f"duplicate_section_fill:{section_id}")
                continue
            normalized[section_id] = item
        return normalized
    return None


def _validate_text_file(path: Path, label: str, findings: list[str]) -> bool:
    if path.is_symlink():
        findings.append(f"symlink_entry:{label}")
        return False
    if not path.is_file():
        findings.append(f"missing_file:{label}")
        return False
    stat_result = path.stat()
    if stat_result.st_mode & 0o111:
        findings.append(f"executable_entry:{label}")
        return False
    if stat_result.st_size > MAX_ENTRY_BYTES:
        findings.append(f"oversized_entry:{label}")
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        findings.append(f"binary_payload:{label}")
        return False
    findings.extend(scan_authoring_payload(text))
    return True


def _has_symlink_component(base: Path, path: Path) -> bool:
    try:
        relative = path.relative_to(base)
    except ValueError:
        return True
    current = base
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _safe_rel(value: str, findings: list[str], *, allow_suffixes: tuple[str, ...]) -> str | None:
    if "\\" in value:
        findings.append(f"path_separator_backslash:{value}")
        return None
    if len(value) >= 2 and value[1] == ":" and value[0].isalpha():
        findings.append(f"host_local_path:{value}")
        return None
    rel = PurePosixPath(value)
    if rel.is_absolute() or any(part == ".." for part in rel.parts):
        findings.append(f"path_traversal:{value}")
        return None
    if any(part.startswith(".") for part in rel.parts):
        findings.append(f"hidden_path:{value}")
        return None
    parts = tuple(part.lower() for part in rel.parts)
    if parts and parts[0] in {"users", "home", "volumes", "private"}:
        findings.append(f"host_local_path:{value}")
        return None
    if any(
        part in {"secret", "secrets", "token", "tokens", "credential", "credentials", "password", "passwords"}
        or "api-key" in part
        or "api_key" in part
        for part in parts
    ):
        findings.append(f"secret_path:{value}")
        return None
    if rel.suffix.lower() not in allow_suffixes:
        findings.append(f"unsupported_suffix:{value}")
        return None
    return rel.as_posix()


def _is_canonical_doc_rel(value: str) -> bool:
    return value in {"requirement.md", "design.md", "plan.md", "report.md", ".assurance.json"}


def _string(payload: dict[str, object], key: str, findings: list[str], *, label: str | None = None) -> str | None:
    value = payload.get(key)
    if isinstance(value, str) and value:
        return value
    findings.append(f"missing_or_invalid_field:{label or key}")
    return None


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


def _profile_from_assurance(payload: dict[str, object]) -> str | None:
    classification = payload.get("classification")
    if isinstance(classification, dict):
        value = classification.get("authorized_profile")
        if isinstance(value, str):
            return value
    value = payload.get("authorized_profile")
    return value if isinstance(value, str) else None


def _profile_from_skeleton(payload: dict[str, object]) -> str | None:
    for key in ("selected_profile", "authorized_profile", "profile"):
        value = payload.get(key)
        if isinstance(value, str):
            return value
    return None


def _compare_digest_field(
    payload: dict[str, object],
    selected_skeleton: dict[str, object],
    key: str,
    findings: list[str],
    comparison: list[str],
) -> None:
    observed = _digest_value(payload.get(key))
    expected = _digest_value(selected_skeleton.get(key))
    if not observed:
        findings.append(f"missing_or_invalid_field:{key}")
        return
    if not expected:
        findings.append(f"missing_or_invalid_field:selected_skeleton.{key}")
        return
    if observed != expected:
        comparison.append(f"{key}_mismatch")


def _digest_value(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    if value.startswith("sha256:"):
        return value.removeprefix("sha256:")
    return value


def _status_from_findings(findings: list[str], comparison: list[str]) -> DraftAdoptionStatus:
    if any(_is_rejected(finding) for finding in findings):
        return "rejected"
    if findings:
        return "fail"
    if comparison:
        return "stale"
    return "pass"


def _is_rejected(finding: str) -> bool:
    return finding.startswith((
        "path_traversal:",
        "path_separator_backslash:",
        "host_local_path:",
        "secret_path:",
        "hidden_path:",
        "unsupported_suffix:",
        "symlink_entry:",
        "executable_entry:",
        "oversized_entry:",
        "binary_payload:",
        "secret_like_payload:",
        "raw_transcript:",
        "forbidden_authority_claim:",
        "forbidden_canonical_target:",
        "unexpected_canonical_target:",
        "canonical_doc_path:",
        "non_artifact_draft_path:",
        "non_artifact_section_path:",
    ))
