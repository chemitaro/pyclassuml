from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

AUTHORITY_PROPOSED = "proposed"
AUTHORITY_APPROVED = "approved"

GRANT_REVIEW_INPUT = "review_input"
GRANT_PLANNING_INPUT = "planning_input"
GRANT_DESIGN_BASELINE = "design_baseline"
GRANT_IMPLEMENTATION_START = "implementation_start"
GRANT_ISSUE_READY = "issue_ready"
GRANT_ISSUE_FINISH = "issue_finish"
GRANT_PHASE_COMPLETION = "phase_completion"

VALID_AUTHORITIES: tuple[str, ...] = (AUTHORITY_PROPOSED, AUTHORITY_APPROVED)
VALID_GRANTS: tuple[str, ...] = (
    GRANT_REVIEW_INPUT,
    GRANT_PLANNING_INPUT,
    GRANT_DESIGN_BASELINE,
    GRANT_IMPLEMENTATION_START,
    GRANT_ISSUE_READY,
    GRANT_ISSUE_FINISH,
    GRANT_PHASE_COMPLETION,
)
INVALID_WILDCARD_GRANTS: tuple[str, ...] = ("*", "grants.*", "all", "admin", "owner")
DOWNSTREAM_LIFECYCLE_GRANTS: tuple[str, ...] = (
    GRANT_IMPLEMENTATION_START,
    GRANT_ISSUE_READY,
    GRANT_ISSUE_FINISH,
    GRANT_PHASE_COMPLETION,
)
REQUIRED_DRAFT_METADATA_FIELDS: tuple[str, ...] = (
    "status",
    "authority",
    "grants",
    "owner_role",
    "draft_author_role",
    "approval",
    "source_revision",
    "approved_revision",
    "approved_hash",
    "manifest_hash",
    "permission_profile_name",
    "permission_profile_hash",
    "write_session_invocation_hash",
    "probe_run_id",
    "positive_probe_result",
)
EAL_BLOCKING_STATUSES: tuple[str, ...] = ("blocked", "stale")
PURPOSE_REQUIRED_GRANTS: dict[str, str] = {
    "artifact_metadata": GRANT_IMPLEMENTATION_START,
    "validate": GRANT_IMPLEMENTATION_START,
    "implementation": GRANT_IMPLEMENTATION_START,
    "implementation_start": GRANT_IMPLEMENTATION_START,
    "context_pack_implementation": GRANT_IMPLEMENTATION_START,
    "issue_ready": GRANT_ISSUE_READY,
    "issue_finish": GRANT_ISSUE_FINISH,
    "context_pack_finish": GRANT_ISSUE_FINISH,
    "phase_completion": GRANT_PHASE_COMPLETION,
}
DELEGATED_AUTHORITY_METADATA_READ_ERROR = "_delegated_authority_metadata_read_error"


@dataclass(frozen=True)
class AuthorityGateResult:
    ok: bool
    reason: str
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceLedgerGateResult:
    ok: bool
    reason: str
    blocking_entry_id: str | None = None
    target_artifact: str | None = None
    required_next_action: str | None = None
    details: tuple[str, ...] = ()


def approved_runtime_promotion_record(*, node_id: str) -> dict[str, str]:
    revision = f"active:{node_id}"
    return {
        "status": AUTHORITY_APPROVED,
        "authority": AUTHORITY_APPROVED,
        "source_revision": revision,
        "approved_revision": revision,
        "approved_hash": revision,
        "reviewer_target_hash": revision,
        "promotion_decision": "runtime_active_selection",
    }


def approved_runtime_grants() -> tuple[str, ...]:
    return VALID_GRANTS


def _normalize_grants(raw_grants: object) -> tuple[str, ...] | None:
    if not isinstance(raw_grants, list | tuple):
        return None
    normalized: list[str] = []
    for grant in raw_grants:
        if not isinstance(grant, str):
            return None
        stripped = grant.strip()
        if not stripped:
            return None
        normalized.append(stripped)
    return tuple(normalized)


def _promotion_value(promotion_record: Mapping[str, object], key: str) -> str | None:
    value = promotion_record.get(key)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def evaluate_authority_gate(
    *,
    authority: object,
    grants: object,
    promotion_record: object,
    required_grant: str,
    purpose: str,
    expected_revision: str | None = None,
) -> AuthorityGateResult:
    if required_grant not in VALID_GRANTS:
        return AuthorityGateResult(False, "invalid_required_grant", (f"required_grant={required_grant}",))

    if not isinstance(authority, str) or not authority.strip():
        return AuthorityGateResult(False, "missing_authority", (f"purpose={purpose}",))
    normalized_authority = authority.strip()
    if normalized_authority not in VALID_AUTHORITIES:
        return AuthorityGateResult(False, "invalid_authority", (f"authority={normalized_authority}",))
    if normalized_authority != AUTHORITY_APPROVED:
        return AuthorityGateResult(
            False,
            "authority_not_approved",
            (f"authority={normalized_authority}", f"required_grant={required_grant}", f"purpose={purpose}"),
        )

    normalized_grants = _normalize_grants(grants)
    if normalized_grants is None:
        return AuthorityGateResult(False, "missing_or_invalid_grants", (f"purpose={purpose}",))
    invalid = tuple(grant for grant in normalized_grants if grant in INVALID_WILDCARD_GRANTS or grant not in VALID_GRANTS)
    if invalid:
        return AuthorityGateResult(False, "invalid_grants", tuple(f"grant={grant}" for grant in invalid))
    if required_grant not in normalized_grants:
        return AuthorityGateResult(
            False,
            "missing_required_grant",
            (f"required_grant={required_grant}", f"purpose={purpose}"),
        )

    if not isinstance(promotion_record, Mapping):
        return AuthorityGateResult(False, "missing_promotion_record", (f"purpose={purpose}",))
    required_fields = (
        "status",
        "authority",
        "source_revision",
        "approved_revision",
        "approved_hash",
        "reviewer_target_hash",
        "promotion_decision",
    )
    missing = tuple(field for field in required_fields if _promotion_value(promotion_record, field) is None)
    if missing:
        return AuthorityGateResult(False, "incomplete_promotion_record", tuple(f"missing={field}" for field in missing))
    if _promotion_value(promotion_record, "status") != AUTHORITY_APPROVED:
        return AuthorityGateResult(False, "promotion_not_approved", (f"status={promotion_record.get('status')}",))
    if _promotion_value(promotion_record, "authority") != AUTHORITY_APPROVED:
        return AuthorityGateResult(False, "promotion_authority_not_approved", ())
    if _promotion_value(promotion_record, "approved_hash") != _promotion_value(promotion_record, "reviewer_target_hash"):
        return AuthorityGateResult(False, "stale_promotion_hash", ())
    if _promotion_value(promotion_record, "source_revision") != _promotion_value(promotion_record, "approved_revision"):
        return AuthorityGateResult(False, "stale_promotion_revision", ())
    if (
        required_grant in DOWNSTREAM_LIFECYCLE_GRANTS
        and _promotion_value(promotion_record, "promotion_decision") == "runtime_active_selection"
    ):
        return AuthorityGateResult(
            False,
            "active_synthetic_approval_not_lifecycle_approval",
            (f"required_grant={required_grant}", f"purpose={purpose}"),
        )
    if expected_revision is not None:
        normalized_expected = expected_revision.strip()
        if not normalized_expected:
            return AuthorityGateResult(False, "missing_expected_revision", ())
        if _promotion_value(promotion_record, "approved_revision") != normalized_expected:
            return AuthorityGateResult(
                False,
                "promotion_record_not_bound_to_active_entry",
                (f"expected_revision={normalized_expected}",),
            )
        if _promotion_value(promotion_record, "approved_hash") != normalized_expected:
            return AuthorityGateResult(
                False,
                "promotion_hash_not_bound_to_active_entry",
                (f"expected_revision={normalized_expected}",),
            )
    return AuthorityGateResult(True, "ok", (f"required_grant={required_grant}", f"purpose={purpose}"))


def required_grant_for_purpose(purpose: str) -> str:
    return PURPOSE_REQUIRED_GRANTS.get(purpose, GRANT_IMPLEMENTATION_START)


def _normalize_markdown_cell_value(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    while len(normalized) >= 2 and normalized.startswith("`") and normalized.endswith("`"):
        normalized = normalized[1:-1].strip()
    return normalized or None


def validate_draft_artifact_metadata(
    metadata: Mapping[str, object],
    *,
    purpose: str = "artifact_metadata",
) -> AuthorityGateResult:
    missing = tuple(field for field in REQUIRED_DRAFT_METADATA_FIELDS if field not in metadata)
    if missing:
        return AuthorityGateResult(False, "incomplete_draft_metadata", tuple(f"missing={field}" for field in missing))
    if metadata.get("authority") == AUTHORITY_PROPOSED:
        return AuthorityGateResult(False, "authority_not_approved", ("authority=proposed",))
    if metadata.get("authority") == AUTHORITY_APPROVED and metadata.get("status") != AUTHORITY_APPROVED:
        return AuthorityGateResult(False, "status_not_approved", (f"status={metadata.get('status')}",))
    if metadata.get("positive_probe_result") != "pass":
        return AuthorityGateResult(
            False,
            "positive_probe_not_passed",
            (f"positive_probe_result={metadata.get('positive_probe_result')}",),
        )
    promotion_record = metadata.get("promotion_record")
    if isinstance(promotion_record, Mapping) and _promotion_value(promotion_record, "promotion_decision") == "runtime_active_selection":
        return AuthorityGateResult(False, "active_synthetic_approval_not_artifact_approval", ())
    return evaluate_authority_gate(
        authority=metadata.get("authority"),
        grants=metadata.get("grants"),
        promotion_record=promotion_record,
        required_grant=required_grant_for_purpose(purpose),
        purpose=purpose,
    )


def delegated_authority_metadata_from_markdown(path: Path) -> Mapping[str, object] | None:
    if not path.is_file():
        return None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as error:
        return {DELEGATED_AUTHORITY_METADATA_READ_ERROR: f"unicode_decode_error={error}"}
    metadata: Mapping[str, object] | None = None
    if lines and lines[0].strip() == "---":
        try:
            closing = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
        except StopIteration:
            closing = -1
        if closing > 0:
            metadata = _parse_simple_front_matter(lines[1:closing])
    if metadata is None or not _looks_like_delegated_authority_metadata(metadata):
        metadata = _parse_delegated_draft_metadata_block(lines)
    if not _looks_like_delegated_authority_metadata(metadata):
        return None
    return metadata


def validate_delegated_authority_artifact(path: Path, *, purpose: str) -> AuthorityGateResult:
    metadata = delegated_authority_metadata_from_markdown(path)
    if metadata is None:
        return AuthorityGateResult(True, "ok", (f"purpose={purpose}", f"path={path.as_posix()}"))
    read_error = metadata.get(DELEGATED_AUTHORITY_METADATA_READ_ERROR)
    if isinstance(read_error, str):
        return AuthorityGateResult(
            False,
            "delegated_authority_artifact_non_utf8",
            (f"purpose={purpose}", f"path={path.as_posix()}", read_error),
        )
    result = validate_draft_artifact_metadata(metadata, purpose=purpose)
    if result.ok:
        return result
    return AuthorityGateResult(
        False,
        result.reason,
        (f"purpose={purpose}", f"path={path.as_posix()}", *result.details),
    )


def evaluate_evidence_adoption_ledger_gate(
    entries: object,
    *,
    target_artifact: str,
    purpose: str,
) -> EvidenceLedgerGateResult:
    if not isinstance(entries, list | tuple):
        return EvidenceLedgerGateResult(True, "ok", target_artifact=target_artifact, details=(f"purpose={purpose}",))
    for raw_entry in entries:
        if not isinstance(raw_entry, Mapping):
            continue
        status = _normalize_markdown_cell_value(_promotion_value(raw_entry, "adoption_status"))
        entry_target = _normalize_markdown_cell_value(_promotion_value(raw_entry, "target_artifact"))
        if status not in EAL_BLOCKING_STATUSES:
            continue
        if target_artifact != "*" and entry_target not in (None, target_artifact):
            continue
        entry_id = (
            _normalize_markdown_cell_value(_promotion_value(raw_entry, "id"))
            or _normalize_markdown_cell_value(_promotion_value(raw_entry, "ID"))
            or "unknown"
        )
        next_action = (
            _normalize_markdown_cell_value(_promotion_value(raw_entry, "next_action"))
            or "resolve Evidence Adoption Ledger entry"
        )
        return EvidenceLedgerGateResult(
            ok=False,
            reason=f"evidence_ledger_{status}",
            blocking_entry_id=entry_id,
            target_artifact=target_artifact,
            required_next_action=next_action,
            details=(f"purpose={purpose}", f"adoption_status={status}"),
        )
    return EvidenceLedgerGateResult(True, "ok", target_artifact=target_artifact, details=(f"purpose={purpose}",))


def load_evidence_adoption_ledger_entries(report_path: Path) -> list[dict[str, str]]:
    if not report_path.is_file():
        return []
    return parse_evidence_adoption_ledger_entries(report_path.read_text(encoding="utf-8").splitlines())


def parse_evidence_adoption_ledger_entries(lines: list[str]) -> list[dict[str, str]]:
    in_section = False
    headers: list[str] | None = None
    entries: list[dict[str, str]] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            if in_section:
                break
            in_section = "Evidence Adoption Ledger" in stripped or "証跡採用台帳" in stripped
            continue
        if not in_section or not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        if headers is None:
            headers = [_normalize_eal_header(cell) for cell in cells]
            continue
        if headers:
            entries.append({headers[index]: value for index, value in enumerate(cells) if index < len(headers)})
    return entries


def _normalize_eal_header(header: str) -> str:
    normalized = header.strip().lower().replace(" ", "_")
    for open_char, close_char in (("(", ")"), ("（", "）")):
        if open_char in normalized and close_char in normalized:
            inner = normalized.split(open_char, 1)[1].split(close_char, 1)[0].strip()
            if inner:
                normalized = inner
                break
    aliases = {
        "id": "id",
        "target": "target_artifact",
        "対象": "target_artifact",
        "adoption_status": "adoption_status",
        "採用状態": "adoption_status",
        "next_action": "next_action",
        "次アクション": "next_action",
    }
    return aliases.get(normalized, normalized)


def _parse_simple_front_matter(lines: list[str]) -> dict[str, object]:
    data: dict[str, object] = {}
    current_key: str | None = None
    for raw_line in lines:
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith((" ", "\t")) and current_key is not None:
            item = raw_line.strip()
            if item.startswith("- "):
                existing = data.setdefault(current_key, [])
                if isinstance(existing, list):
                    existing.append(item[2:].strip().strip('"'))
            continue
        if ":" not in raw_line:
            current_key = None
            continue
        key, raw_value = raw_line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        current_key = key
        if value == "":
            data[key] = []
        elif value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            data[key] = [] if not inner else [part.strip().strip('"') for part in inner.split(",")]
        else:
            data[key] = value.strip('"')
    return data


def _parse_delegated_draft_metadata_block(lines: list[str]) -> dict[str, object]:
    data: dict[str, object] = {}
    in_block = False
    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith("## "):
            if in_block:
                break
            in_block = stripped.lstrip("#").strip().lower() == "delegated draft pilot metadata"
            continue
        if not in_block or not stripped.startswith("- "):
            continue
        item = stripped[2:].strip()
        separator = "=" if "=" in item else ":" if ":" in item else None
        if separator is None:
            continue
        key, raw_value = item.split(separator, 1)
        key = key.strip()
        value = raw_value.strip().strip('"')
        if not key or not value:
            continue
        _assign_line_metadata_value(data, key, value)
    return data


def _assign_line_metadata_value(data: dict[str, object], key: str, value: str) -> None:
    parsed_value: object = [part.strip() for part in value.split(",") if part.strip()] if key == "grants" else value
    if "." not in key:
        data[key] = parsed_value
        return

    parts = [part.strip() for part in key.split(".") if part.strip()]
    if len(parts) != 2:
        data[key] = parsed_value
        return
    parent_key, child_key = parts
    existing = data.setdefault(parent_key, {})
    if not isinstance(existing, dict):
        data[key] = parsed_value
        return
    existing[child_key] = parsed_value


def _looks_like_delegated_authority_metadata(metadata: Mapping[str, object]) -> bool:
    delegated_markers = (
        "authority",
        "grants",
        "draft_author_role",
        "manifest_hash",
        "permission_profile_name",
        "write_session_invocation_hash",
        "probe_run_id",
    )
    return any(marker in metadata for marker in delegated_markers)
