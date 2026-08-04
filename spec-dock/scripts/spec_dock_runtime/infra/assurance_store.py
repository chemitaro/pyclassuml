from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Literal

from spec_dock_runtime.domain.assurance import (
    AssuranceClassification,
    AssuranceContract,
    AssuranceMode,
    AssuranceProfile,
    AssuranceStatus,
    ClassificationStage,
    ComplexityTier,
    RiskFact,
    SourceArtifact,
    SourceBinding,
    canonical_json_bytes,
    validate_assurance_contract,
)
from spec_dock_runtime.infra.active_store import load_active_manifest
from spec_dock_runtime.infra.json_store import load_json

ReadStatus = Literal["valid", "missing", "invalid"]
ASSURANCE_CONTRACT_FILENAME = ".assurance.json"
LEGACY_ASSURANCE_CONTRACT_FILENAME = "assurance.json"
_PLANNING_SOURCE_ARTIFACTS: tuple[tuple[str, str], ...] = (
    ("requirement", "requirement.md"),
    ("design", "design.md"),
    ("plan", "plan.md"),
)


def _iter_issue_meta_paths(initiatives_root: Path) -> list[Path]:
    matches: list[Path] = []
    for current_root, child_dirnames, filenames in os.walk(initiatives_root, topdown=True):
        child_dirnames[:] = sorted(name for name in child_dirnames if name != ".workbench")
        if ".meta.json" in filenames:
            matches.append(Path(current_root) / ".meta.json")
    return sorted(matches, key=lambda path: path.as_posix())


@dataclass(frozen=True)
class ResolvedIssueTarget:
    issue_id: str
    issue_dir: Path
    repo_relative_path: str


@dataclass(frozen=True)
class AssuranceStoreResult:
    status: ReadStatus
    target: ResolvedIssueTarget
    contract: AssuranceContract | None
    mode: str
    reason: str
    details: tuple[str, ...] = ()


class AssuranceStoreError(RuntimeError):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


class AssuranceStore:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.specdock_dir = self.repo_root / "spec-dock"

    def resolve_issue_target(self, target: str | Path | None) -> ResolvedIssueTarget:
        if target is None:
            return self._resolve_active_issue_target()
        if isinstance(target, Path) or _is_path_target(str(target)):
            return self._resolve_path_target(Path(target))
        return self._resolve_ref_target(str(target))

    def build_requirement_source_binding(self, target: ResolvedIssueTarget) -> SourceBinding:
        artifacts: list[SourceArtifact] = []
        for role, filename in _PLANNING_SOURCE_ARTIFACTS:
            artifact_path = target.issue_dir / filename
            if not artifact_path.exists() or not artifact_path.is_file():
                raise AssuranceStoreError(f"{role}_missing", f"Planning source artifact not found: {artifact_path}")
            if artifact_path.is_symlink():
                raise AssuranceStoreError(
                    f"{role}_symlink",
                    f"Planning source artifact must be an issue-local regular file: {artifact_path}",
                )
            artifacts.append(
                SourceArtifact(
                    path=artifact_path.relative_to(self.repo_root).as_posix(),
                    display_path=self._active_artifact_display_path(artifact_path, role=role),
                    role=role,
                    sha256=hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
                )
            )
        return SourceBinding(artifacts=tuple(artifacts))

    def build_planning_source_binding(self, target: ResolvedIssueTarget) -> SourceBinding:
        return self.build_requirement_source_binding(target)

    def read_requirement_text(self, target: ResolvedIssueTarget) -> str | None:
        requirement_path = target.issue_dir / "requirement.md"
        if requirement_path.is_symlink() or not requirement_path.exists() or not requirement_path.is_file():
            return None
        try:
            return requirement_path.read_text(encoding="utf-8")
        except OSError:
            return None

    def read_contract(self, target: ResolvedIssueTarget) -> AssuranceStoreResult:
        path = target.issue_dir / ASSURANCE_CONTRACT_FILENAME
        legacy_path = target.issue_dir / LEGACY_ASSURANCE_CONTRACT_FILENAME
        if path.is_symlink():
            return AssuranceStoreResult(
                status="invalid",
                target=target,
                contract=None,
                mode="invalid",
                reason="contract_path_symlink",
                details=(f"path={path.relative_to(self.repo_root).as_posix()}",),
            )
        if legacy_path.exists() or legacy_path.is_symlink():
            return AssuranceStoreResult(
                status="invalid",
                target=target,
                contract=None,
                mode="invalid",
                reason="legacy_assurance_contract_path",
                details=(
                    f"legacy_path={legacy_path.relative_to(self.repo_root).as_posix()}",
                    f"canonical_path={path.relative_to(self.repo_root).as_posix()}",
                    "Rename assurance.json to .assurance.json.",
                ),
            )
        if not path.exists():
            return AssuranceStoreResult(
                status="missing",
                target=target,
                contract=None,
                mode=AssuranceMode.STRICT_LEGACY.value,
                reason="missing_assurance_contract",
            )
        if not path.is_file():
            return AssuranceStoreResult(
                status="invalid",
                target=target,
                contract=None,
                mode="invalid",
                reason="contract_path_not_file",
                details=(f"path={path.relative_to(self.repo_root).as_posix()}",),
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return AssuranceStoreResult(
                status="invalid",
                target=target,
                contract=None,
                mode="invalid",
                reason="invalid_json",
                details=(f"line={exc.lineno}", f"column={exc.colno}"),
            )
        except UnicodeDecodeError as exc:
            return AssuranceStoreResult(
                status="invalid",
                target=target,
                contract=None,
                mode="invalid",
                reason="invalid_json",
                details=(exc.__class__.__name__,),
            )
        except OSError as exc:
            return AssuranceStoreResult(
                status="invalid",
                target=target,
                contract=None,
                mode="invalid",
                reason="contract_unreadable",
                details=(exc.__class__.__name__,),
            )

        contract, errors = _contract_from_payload(payload)
        if contract is None:
            return AssuranceStoreResult(
                status="invalid",
                target=target,
                contract=None,
                mode="invalid",
                reason="invalid_schema",
                details=errors,
            )
        try:
            domain_errors = validate_assurance_contract(contract)
        except ValueError as exc:
            domain_errors = (str(exc),)
        if domain_errors:
            return AssuranceStoreResult(
                status="invalid",
                target=target,
                contract=None,
                mode="invalid",
                reason="invalid_schema",
                details=domain_errors,
            )
        target_errors = self._target_schema_errors(contract, target)
        if target_errors:
            return AssuranceStoreResult(
                status="invalid",
                target=target,
                contract=None,
                mode="invalid",
                reason="invalid_schema",
                details=target_errors,
            )
        return AssuranceStoreResult(
            status="valid",
            target=target,
            contract=contract,
            mode=contract.mode.value,
            reason="ok",
        )

    def verify_contract(self, target: ResolvedIssueTarget) -> AssuranceStoreResult:
        result = self.read_contract(target)
        if result.status != "valid" or result.contract is None:
            return result
        stale_details = self._stale_source_binding_details(result.contract)
        if stale_details:
            return AssuranceStoreResult(
                status="invalid",
                target=target,
                contract=result.contract,
                mode=result.contract.mode.value,
                reason="stale_source_binding",
                details=stale_details,
            )
        return result

    def ensure_contract_writable(self, target: ResolvedIssueTarget) -> None:
        self._contract_write_path(target)

    def write_contract(self, target: ResolvedIssueTarget, contract: AssuranceContract) -> Path:
        errors = validate_assurance_contract(contract)
        if errors:
            raise AssuranceStoreError("invalid_contract", ", ".join(errors))
        path = self._contract_write_path(target)
        path.write_bytes(canonical_json_bytes(contract))
        return path

    def _contract_write_path(self, target: ResolvedIssueTarget) -> Path:
        path = target.issue_dir / ASSURANCE_CONTRACT_FILENAME
        legacy_path = target.issue_dir / LEGACY_ASSURANCE_CONTRACT_FILENAME
        if legacy_path.exists() or legacy_path.is_symlink():
            raise AssuranceStoreError(
                "legacy_assurance_contract_path",
                f"Refusing to write assurance contract while legacy path exists: {legacy_path.relative_to(self.repo_root)}",
            )
        if path.is_symlink():
            raise AssuranceStoreError(
                "contract_path_symlink",
                f"Refusing to write symlinked assurance contract: {path.relative_to(self.repo_root)}",
            )
        resolved_parent = path.parent.resolve()
        if not _is_relative_to(resolved_parent, self.repo_root) or not _is_relative_to(
            resolved_parent, target.issue_dir
        ):
            raise AssuranceStoreError(
                "contract_path_outside_issue",
                f"Refusing to write assurance contract outside target issue: {path.relative_to(self.repo_root)}",
            )
        return path

    def _resolve_active_issue_target(self) -> ResolvedIssueTarget:
        loaded = load_active_manifest(self.specdock_dir)
        issue = loaded.manifest.issue if loaded.manifest is not None else None
        if issue is None or issue.path is None:
            raise AssuranceStoreError("active_issue_missing", "Active issue is not set")
        issue_dir = self._contained_existing_path(Path(issue.path), missing_reason="active_issue_path_missing")
        issue_meta = self._issue_meta_for_dir(issue_dir)
        if issue_meta is None:
            raise AssuranceStoreError(
                "active_issue_not_issue_dir", f"Active issue path is not an issue dir: {issue.path}"
            )
        issue_id = _meta_string(issue_meta, "id") or issue.id
        return self._target_from_issue_dir(issue_dir, issue_id=issue_id)

    def _resolve_ref_target(self, raw_target: str) -> ResolvedIssueTarget:
        target = raw_target.strip()
        if not target:
            raise AssuranceStoreError("target_empty", "Issue target is empty")
        if target.startswith("#"):
            target = target[1:]
        records = self._issue_records()
        if target.isdigit():
            number = int(target)
            matches = [record for record in records if record.github_issue_number == number]
            if not matches:
                raise AssuranceStoreError("target_not_found", f"No issue found for GitHub issue number: {raw_target}")
            if len(matches) > 1:
                raise AssuranceStoreError(
                    "target_ambiguous", f"Multiple issues found for GitHub issue number: {raw_target}"
                )
            return self._target_from_issue_dir(matches[0].issue_dir, issue_id=matches[0].issue_id)
        matches = [record for record in records if record.issue_id == target]
        if not matches:
            raise AssuranceStoreError("target_not_found", f"No issue found for issue id: {raw_target}")
        if len(matches) > 1:
            raise AssuranceStoreError("target_ambiguous", f"Multiple issues found for issue id: {raw_target}")
        return self._target_from_issue_dir(matches[0].issue_dir, issue_id=matches[0].issue_id)

    def _resolve_path_target(self, raw_path: Path) -> ResolvedIssueTarget:
        candidate = raw_path if raw_path.is_absolute() else self.repo_root / raw_path
        if not candidate.exists():
            raise AssuranceStoreError("target_path_missing", f"Target path does not exist: {raw_path}")
        resolved = candidate.resolve()
        if not _is_relative_to(resolved, self.repo_root):
            raise AssuranceStoreError("target_path_outside_repo", f"Target path is outside repository: {raw_path}")
        issue_dir = self._nearest_issue_dir(resolved)
        if issue_dir is None:
            raise AssuranceStoreError("target_not_issue_dir", f"Target path is not under an issue dir: {raw_path}")
        issue_meta = self._issue_meta_for_dir(issue_dir)
        issue_id = _meta_string(issue_meta or {}, "id")
        if issue_id is None:
            raise AssuranceStoreError("target_not_issue_dir", f"Target path is not under an issue dir: {raw_path}")
        return self._target_from_issue_dir(issue_dir, issue_id=issue_id)

    def _target_from_issue_dir(self, issue_dir: Path, *, issue_id: str) -> ResolvedIssueTarget:
        resolved_dir = issue_dir.resolve()
        if not _is_relative_to(resolved_dir, self.repo_root):
            raise AssuranceStoreError("target_path_outside_repo", f"Issue path is outside repository: {issue_dir}")
        return ResolvedIssueTarget(
            issue_id=issue_id,
            issue_dir=resolved_dir,
            repo_relative_path=resolved_dir.relative_to(self.repo_root).as_posix(),
        )

    def _contained_existing_path(self, path: Path, *, missing_reason: str) -> Path:
        candidate = path if path.is_absolute() else self.repo_root / path
        if not candidate.exists():
            raise AssuranceStoreError(missing_reason, f"Path does not exist: {path}")
        resolved = candidate.resolve()
        if not _is_relative_to(resolved, self.repo_root):
            raise AssuranceStoreError("target_path_outside_repo", f"Path is outside repository: {path}")
        return resolved

    def _active_artifact_display_path(self, artifact_path: Path, *, role: str) -> str | None:
        active_artifact = self.specdock_dir / "active" / "issue" / f"{role}.md"
        if not active_artifact.exists():
            return None
        try:
            if active_artifact.resolve() == artifact_path.resolve():
                return active_artifact.relative_to(self.repo_root).as_posix()
        except OSError:
            return None
        return None

    def _stale_source_binding_details(self, contract: AssuranceContract) -> tuple[str, ...]:
        details: list[str] = []
        for artifact in contract.source_binding.artifacts:
            artifact_path = Path(artifact.path)
            if artifact_path.is_absolute():
                details.append(f"role={artifact.role} path={artifact.path} reason=absolute_source_path")
                continue
            resolved = (self.repo_root / artifact_path).resolve()
            if not resolved.exists() or not resolved.is_file():
                details.append(
                    f"role={artifact.role} path={artifact.path} expected_sha256={artifact.sha256} actual_sha256=missing"
                )
                continue
            actual_sha256 = hashlib.sha256(resolved.read_bytes()).hexdigest()
            if actual_sha256 != artifact.sha256:
                details.append(
                    f"role={artifact.role} path={artifact.path} expected_sha256={artifact.sha256} "
                    f"actual_sha256={actual_sha256}"
                )
        return tuple(details)

    def _issue_records(self) -> list[_IssueRecord]:
        records: list[_IssueRecord] = []
        for meta_path in _iter_issue_meta_paths(self.specdock_dir / "initiatives"):
            try:
                payload = load_json(meta_path)
            except RuntimeError:
                continue
            if not isinstance(payload, dict) or payload.get("type") != "issue":
                continue
            issue_id = _meta_string(payload, "id")
            if issue_id is None:
                continue
            records.append(
                _IssueRecord(
                    issue_id=issue_id,
                    issue_dir=meta_path.parent.resolve(),
                    github_issue_number=_github_issue_number(payload),
                )
            )
        return records

    def _nearest_issue_dir(self, path: Path) -> Path | None:
        current = path if path.is_dir() else path.parent
        while _is_relative_to(current, self.repo_root):
            if self._issue_meta_for_dir(current) is not None:
                return current
            if current == self.repo_root:
                return None
            current = current.parent
        return None

    def _issue_meta_for_dir(self, issue_dir: Path) -> dict[str, Any] | None:
        meta_path = issue_dir / ".meta.json"
        if not meta_path.exists():
            return None
        try:
            payload = load_json(meta_path)
        except RuntimeError:
            return None
        if isinstance(payload, dict) and payload.get("type") == "issue":
            return payload
        return None

    def _target_schema_errors(
        self,
        contract: AssuranceContract,
        target: ResolvedIssueTarget,
    ) -> tuple[str, ...]:
        errors: list[str] = []
        if not contract.issue_id.startswith("iss-"):
            errors.append("invalid_issue_id")
        elif contract.issue_id != target.issue_id:
            errors.append("issue_id_target_mismatch")

        for artifact in contract.source_binding.artifacts:
            artifact_path = Path(artifact.path)
            if artifact_path.is_absolute():
                errors.append("source_binding_path_not_issue_local")
                continue
            resolved = (self.repo_root / artifact_path).resolve()
            if not _is_relative_to(resolved, target.issue_dir):
                errors.append("source_binding_path_not_issue_local")
                continue
            expected = target.issue_dir / f"{artifact.role}.md"
            if artifact.role in {"requirement", "design", "plan"} and resolved != expected:
                errors.append(f"source_binding_path_not_canonical:{artifact.role}")
        return tuple(errors)


@dataclass(frozen=True)
class _IssueRecord:
    issue_id: str
    issue_dir: Path
    github_issue_number: int | None


def _contract_from_payload(payload: Any) -> tuple[AssuranceContract | None, tuple[str, ...]]:
    if not isinstance(payload, dict):
        return None, ("contract_not_object",)
    required_keys = (
        "schema_version",
        "policy_version",
        "issue_id",
        "stage",
        "status",
        "mode",
        "source_binding",
        "classification",
        "risk_facts",
        "obligations",
    )
    allowed_keys = set(required_keys)
    unknown_keys = sorted(str(key) for key in payload if key not in allowed_keys)
    if unknown_keys:
        return None, tuple(f"unknown_root_field:{key}" for key in unknown_keys)
    errors = _missing_keys(
        payload,
        required_keys,
    )
    if errors:
        return None, errors
    source_binding = _source_binding_from_payload(payload.get("source_binding"))
    classification = _classification_from_payload(payload.get("classification"))
    risk_facts = _risk_facts_from_payload(payload.get("risk_facts"))
    obligations_errors = _obligations_errors(payload.get("obligations"), classification)
    errors = (
        _primitive_field_errors(payload)
        + tuple(
            detail
            for detail in (
                _enum_error("stage", payload.get("stage"), ClassificationStage),
                _enum_error("status", payload.get("status"), AssuranceStatus),
                _enum_error("mode", payload.get("mode"), AssuranceMode),
                None if source_binding is not None else "invalid_source_binding",
                None if classification is not None else "invalid_classification",
                None if risk_facts is not None else "invalid_risk_facts",
            )
            if detail is not None
        )
        + obligations_errors
    )
    if errors:
        return None, errors
    try:
        return (
            AssuranceContract(
                schema_version=payload["schema_version"],
                policy_version=payload["policy_version"],
                issue_id=payload["issue_id"],
                stage=ClassificationStage(str(payload["stage"])),
                status=AssuranceStatus(str(payload["status"])),
                mode=AssuranceMode(str(payload["mode"])),
                source_binding=source_binding,
                classification=classification,
                risk_facts=risk_facts,
            ),
            (),
        )
    except (TypeError, ValueError) as exc:
        return None, (f"invalid_contract_field:{exc.__class__.__name__}",)


def _source_binding_from_payload(payload: Any) -> SourceBinding | None:
    if not isinstance(payload, dict):
        return None
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        return None
    parsed = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            return None
        if set(artifact) - {"path", "display_path", "role", "sha256"}:
            return None
        path = artifact.get("path")
        role = artifact.get("role")
        sha256 = artifact.get("sha256")
        display_path = artifact.get("display_path")
        if not isinstance(path, str) or not isinstance(role, str) or not isinstance(sha256, str):
            return None
        if display_path is not None and not isinstance(display_path, str):
            return None
        parsed.append(SourceArtifact(path=path, display_path=display_path, role=role, sha256=sha256))
    return SourceBinding(artifacts=tuple(parsed))


def _classification_from_payload(payload: Any) -> AssuranceClassification | None:
    if not isinstance(payload, dict):
        return None
    expected = {
        "authorized_profile",
        "complexity_tier",
        "lite_candidate",
        "lite_authorized",
        "reason_codes",
        "hard_triggers",
        "unknown_facts",
    }
    if set(payload) != expected:
        return None
    if not isinstance(payload.get("lite_candidate"), bool) or not isinstance(payload.get("lite_authorized"), bool):
        return None
    reason_codes = _string_tuple(payload.get("reason_codes"))
    hard_triggers = _string_tuple(payload.get("hard_triggers"))
    unknown_facts = _string_tuple(payload.get("unknown_facts"))
    if reason_codes is None or hard_triggers is None or unknown_facts is None:
        return None
    try:
        return AssuranceClassification(
            authorized_profile=AssuranceProfile(str(payload["authorized_profile"])),
            complexity_tier=ComplexityTier(str(payload["complexity_tier"])),
            lite_candidate=payload["lite_candidate"],
            lite_authorized=payload["lite_authorized"],
            reason_codes=reason_codes,
            hard_triggers=hard_triggers,
            unknown_facts=unknown_facts,
        )
    except ValueError:
        return None


def _risk_facts_from_payload(payload: Any) -> tuple[RiskFact, ...] | None:
    if not isinstance(payload, list):
        return None
    parsed = []
    for fact in payload:
        if not isinstance(fact, dict) or set(fact) != {"key", "value", "source", "reason_code"}:
            return None
        key = fact.get("key")
        value = fact.get("value")
        source = fact.get("source")
        reason_code = fact.get("reason_code")
        if not all(isinstance(item, str) for item in (key, value, source, reason_code)):
            return None
        if value not in ("true", "false", "unknown"):
            return None
        if source != "requirement" or not reason_code:
            return None
        parsed.append(RiskFact(key=key, value=value, source=source, reason_code=reason_code))
    return tuple(parsed)


def _obligations_errors(payload: Any, classification: AssuranceClassification | None) -> tuple[str, ...]:
    if not isinstance(payload, dict):
        return ("invalid_obligations",)
    if set(payload) - {"profile_preset", "notes"}:
        return ("invalid_obligations",)
    profile_preset = payload.get("profile_preset")
    notes = payload.get("notes")
    if not isinstance(profile_preset, str):
        return ("invalid_obligations_profile_preset",)
    if not isinstance(notes, list) or not all(isinstance(note, str) for note in notes):
        return ("invalid_obligations_notes",)
    if notes:
        return ("unsupported_obligations_notes",)
    if classification is not None and profile_preset != classification.authorized_profile.value:
        return ("obligations_profile_mismatch",)
    return ()


def _is_path_target(value: str) -> bool:
    return value.startswith(("/", ".", "spec-dock/")) or "/" in value


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _missing_keys(payload: dict[str, Any], keys: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(f"missing_{key}" for key in keys if key not in payload)


def _primitive_field_errors(payload: dict[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    schema_version = payload.get("schema_version")
    if isinstance(schema_version, bool) or not isinstance(schema_version, int):
        errors.append("invalid_schema_version")
    for key in ("policy_version", "issue_id", "stage", "status", "mode"):
        if not isinstance(payload.get(key), str):
            errors.append(f"invalid_{key}")
    return tuple(errors)


def _enum_error(field: str, value: Any, enum_type: type) -> str | None:
    try:
        enum_type(str(value))
    except ValueError:
        return f"invalid_{field}"
    return None


def _string_tuple(value: Any) -> tuple[str, ...] | None:
    if not isinstance(value, list):
        return None
    if not all(isinstance(item, str) for item in value):
        return None
    return tuple(value)


def _meta_string(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _github_issue_number(payload: dict[str, Any]) -> int | None:
    github = payload.get("github")
    if not isinstance(github, dict):
        return None
    value = github.get("issue_number")
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
