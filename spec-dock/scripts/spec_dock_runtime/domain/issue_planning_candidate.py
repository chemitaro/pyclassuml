from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast

from spec_dock_runtime.domain.issue_planning_contracts import IssueCandidateIdentity

if TYPE_CHECKING:
    from collections.abc import Mapping

    from spec_dock_runtime.domain.issue_planning_contracts import (
        PlanningContext,
        PlanningSourceEvidence,
    )

DOCUMENT_NAMES = ("requirement.md", "design.md", "plan.md")
CONTROL_NAMES = (
    "CHECKSUMS.sha256",
    "MANIFEST.json",
    "PLACEHOLDER-ORACLE-MAP.json",
    "SOURCE-BASELINE.json",
)
_SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_TOKEN_RE = re.compile(rb"\{\{SPECDOCK_[A-Z][A-Z0-9_]{0,63}\}\}")
_TOKEN_TEXT_RE = re.compile(r"^\{\{SPECDOCK_[A-Z][A-Z0-9_]{0,63}\}\}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_FRONT_MATTER = {
    "requirement.md": (
        ("種別", "要件定義書（Issue）"),
        ("ID", None),
        ("タイトル", None),
        ("状態", None),
        ("作成者", None),
        ("最終更新", None),
        ("親", None),
    ),
    "design.md": (
        ("種別", "設計書（Issue）"),
        ("ID", None),
        ("タイトル", None),
        ("状態", None),
        ("作成者", None),
        ("最終更新", None),
        ("依存", ("requirement.md",)),
        ("親", None),
    ),
    "plan.md": (
        ("種別", "実装計画書（Issue）"),
        ("ID", None),
        ("タイトル", None),
        ("状態", None),
        ("作成者", None),
        ("最終更新", None),
        ("依存", ("requirement.md", "design.md")),
        ("親", None),
    ),
}


@dataclass(frozen=True)
class IssueFrontMatterBaseline:
    issue_id: str
    title: str
    state: str
    author: str
    parents: tuple[str, str]


@dataclass(frozen=True)
class CandidateMaterial:
    issue_id: str
    candidate_id: str
    version: int
    logical_filename: str
    internal_root: str
    created_at_utc: str
    operation_time: datetime
    onboarding_companion_path: str
    files: Mapping[str, bytes]


@dataclass(frozen=True)
class ValidatedIssueAuthoringPayload:
    expected_logical_filename: str
    observed_transport_filename: str
    internal_root: str
    zip_sha256: str
    zip_size_bytes: int
    documents: Mapping[str, bytes]
    onboarding_companion_path: str
    onboarding_companion_bytes: bytes

    def __post_init__(self) -> None:
        _require_document_inventory(self.documents)
        validate_onboarding_companion(
            self.onboarding_companion_path,
            self.onboarding_companion_bytes,
        )
        object.__setattr__(self, "documents", MappingProxyType(dict(self.documents)))


def candidate_paths(companion_path: str) -> tuple[str, ...]:
    validate_onboarding_companion_path(companion_path)
    return tuple(
        sorted(
            (*CONTROL_NAMES, *DOCUMENT_NAMES, companion_path),
            key=lambda value: value.encode("utf-8"),
        )
    )


def checksum_paths(companion_path: str) -> tuple[str, ...]:
    return tuple(path for path in candidate_paths(companion_path) if path != "CHECKSUMS.sha256")


def validate_onboarding_companion_path(path: str) -> None:
    if not isinstance(path, str):
        raise ValueError("onboarding companion path must be a string")
    parts = path.split("/")
    if (
        len(parts) != 2
        or parts[0] != "artifacts"
        or not parts[1]
        or parts[1].startswith(".")
        or not parts[1].endswith(".md")
        or "\\" in path
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise ValueError("onboarding companion path is invalid")


def validate_onboarding_companion(path: str, payload: bytes) -> None:
    validate_onboarding_companion_path(path)
    if (
        not isinstance(payload, bytes)
        or not payload
        or payload.startswith(b"\xef\xbb\xbf")
        or b"\0" in payload
        or b"\r" in payload
        or not payload.endswith(b"\n")
    ):
        raise ValueError("onboarding companion bytes are invalid")
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ValueError("onboarding companion must be strict UTF-8") from error
    lowered = text.casefold()
    sections = _markdown_sections(text)
    required_section_concepts = (
        (("init-",), ("epic-",), ("iss-",)),
        (("purpose", "目的"), ("scope", "対象", "範囲")),
        (("system context",),),
        (("authority", "権限"), ("responsibility", "責務")),
        (("current architecture", "現行"), ("target architecture", "目標")),
        (("chatgpt first",), ("planning lifecycle", "planning workflow")),
        (("oracle",), ("reference-only", "参照専用"), ("chatgpt-use",)),
        (("candidate",), ("review",), ("human",), ("apply",)),
        (("exact current branch", "exact branch"),),
        (("s01",), ("s07",), ("s08",), ("s14",)),
        (("provider authority", "provider"), ("projection",)),
        (("failure mode", "failure", "障害"),),
        (("first-day checklist", "first day checklist", "初日"),),
    )
    if not _has_distinct_required_sections(sections, required_section_concepts):
        raise ValueError("onboarding companion required section is missing")
    if not all(name in text for name in DOCUMENT_NAMES):
        raise ValueError("onboarding companion canonical authority is incomplete")
    if not any(token in lowered for token in ("subordinate", "従属", "補助")):
        raise ValueError("onboarding companion subordinate authority is missing")
    blocks = re.findall(r"```plantuml\n(.*?)```", text, flags=re.DOTALL)
    if len(blocks) < 4:
        raise ValueError("onboarding companion requires four PlantUML blocks")
    roles = (
        ("system context",),
        ("responsibility", "authority boundary"),
        ("planning sequence", "issue planning sequence"),
        ("implementation roadmap", "remaining implementation roadmap"),
    )
    normalized_blocks = tuple(block.casefold() for block in blocks)
    if any(
        not any(any(role in block for role in alternatives) for block in normalized_blocks) for alternatives in roles
    ):
        raise ValueError("onboarding companion PlantUML role is missing")
    if any(block.count("@startuml") != 1 or block.count("@enduml") != 1 for block in blocks):
        raise ValueError("onboarding companion PlantUML framing is invalid")


def _markdown_sections(text: str) -> tuple[tuple[str, str], ...]:
    lines = text.splitlines()
    headings: list[tuple[int, int, str]] = []
    for index, line in enumerate(lines):
        match = re.fullmatch(r"(#{2,6})[ \t]+(.+?)[ \t]*#*[ \t]*", line)
        if match is not None:
            headings.append((index, len(match.group(1)), match.group(2).casefold()))
    sections: list[tuple[str, str]] = []
    for position, (line_index, level, title) in enumerate(headings):
        end = len(lines)
        for next_line, next_level, _next_title in headings[position + 1 :]:
            if next_level <= level:
                end = next_line
                break
        body = "\n".join(lines[line_index + 1 : end]).strip()
        sections.append((f"{title}\n{body.casefold()}", body))
    return tuple(sections)


def _has_distinct_required_sections(
    sections: tuple[tuple[str, str], ...],
    required_concepts: tuple[tuple[tuple[str, ...], ...], ...],
) -> bool:
    candidates = tuple(
        tuple(
            section_index
            for section_index, (section, body) in enumerate(sections)
            if body.strip() and all(any(token in section for token in alternatives) for alternatives in concepts)
        )
        for concepts in required_concepts
    )
    section_owners: dict[int, int] = {}

    def assign(concept_index: int, visited: set[int]) -> bool:
        for section_index in candidates[concept_index]:
            if section_index in visited:
                continue
            visited.add(section_index)
            owner = section_owners.get(section_index)
            if owner is None or assign(owner, visited):
                section_owners[section_index] = concept_index
                return True
        return False

    return all(assign(concept_index, set()) for concept_index in range(len(candidates)))


def validate_issue_authoring_files(
    files: Mapping[str, bytes],
    _internal_root: str,
    *,
    expected_companion_path: str,
) -> tuple[str, ...]:
    if set(files) != {*DOCUMENT_NAMES, expected_companion_path}:
        return ("inventory_mismatch",)
    try:
        for name in DOCUMENT_NAMES:
            payload = files[name]
            if (
                not payload
                or payload.startswith(b"\xef\xbb\xbf")
                or b"\0" in payload
                or b"\r" in payload
                or not payload.endswith(b"\n")
            ):
                raise ValueError("authoring document framing is invalid")
            _parse_document(name, files[name])
        validate_onboarding_companion(
            expected_companion_path,
            files[expected_companion_path],
        )
    except (KeyError, UnicodeError, ValueError):
        return ("authoring_payload_invalid",)
    return ()


def parse_current_front_matter_baseline(
    documents: Mapping[str, bytes],
) -> IssueFrontMatterBaseline:
    _require_document_inventory(documents)
    parsed = {name: _parse_document(name, documents[name])[0] for name in DOCUMENT_NAMES}
    reference = parsed["requirement.md"]
    shared = ("ID", "タイトル", "状態", "作成者", "親")
    if any(parsed[name][key] != reference[key] for name in DOCUMENT_NAMES for key in shared):
        raise ValueError("front matter baseline is inconsistent")
    parents = reference["親"]
    if not isinstance(parents, tuple) or len(parents) != 2:
        raise ValueError("front matter baseline parent identity is invalid")
    return IssueFrontMatterBaseline(
        issue_id=cast("str", reference["ID"]),
        title=cast("str", reference["タイトル"]),
        state=cast("str", reference["状態"]),
        author=cast("str", reference["作成者"]),
        parents=cast("tuple[str, str]", parents),
    )


def normalize_planner_documents(
    documents: Mapping[str, bytes],
    baseline: IssueFrontMatterBaseline,
    operation_time: datetime,
) -> Mapping[str, bytes]:
    _require_document_inventory(documents)
    utc_date = _as_utc(operation_time).date().isoformat()
    normalized: dict[str, bytes] = {}
    for name in DOCUMENT_NAMES:
        fields, body = _parse_document(name, documents[name])
        expected = {
            "ID": baseline.issue_id,
            "タイトル": baseline.title,
            "状態": baseline.state,
            "作成者": baseline.author,
            "親": baseline.parents,
        }
        if any(fields[key] != value for key, value in expected.items()):
            raise ValueError("front matter does not match the current Issue baseline")
        _validate_completeness(body, baseline)
        normalized[name] = _render_document(name, fields, body, utc_date)
    return MappingProxyType(normalized)


def canonical_control_json_bytes(value: Mapping[str, Any]) -> bytes:
    _validate_control_value(value, field_name="control")
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def parse_canonical_control_json(data: bytes) -> dict[str, Any]:
    if not data.endswith(b"\n") or data.endswith(b"\n\n") or b"\r" in data or b"\xef\xbb\xbf" in data:
        raise ValueError("canonical control JSON framing is invalid")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("canonical control JSON contains duplicate keys")
            result[key] = value
        return result

    try:
        value = json.loads(
            data[:-1].decode("utf-8", errors="strict"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"canonical control JSON number is invalid: {value}")
            ),
        )
        if not isinstance(value, dict):
            raise ValueError("canonical control JSON root must be an object")
        _validate_control_value(value, field_name="control")
        if canonical_control_json_bytes(value) != data:
            raise ValueError("canonical control JSON bytes are not canonical")
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError("canonical control JSON is invalid") from error
    return cast("dict[str, Any]", value)


def build_candidate_material(
    *,
    planner_documents: Mapping[str, bytes],
    onboarding_companion_path: str,
    onboarding_companion_bytes: bytes,
    baseline: IssueFrontMatterBaseline,
    context: PlanningContext,
    source_evidence: PlanningSourceEvidence,
    source_payload_sha256: str,
    source_payload_size: int,
    operation_time: datetime,
    version: int = 1,
) -> CandidateMaterial:
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ValueError("Candidate version must be a positive integer")
    _validate_source_binding(context, source_evidence, baseline)
    if context.onboarding_companion_path != onboarding_companion_path:
        raise ValueError("onboarding companion path does not match Planning context")
    validate_onboarding_companion(
        onboarding_companion_path,
        onboarding_companion_bytes,
    )
    if _SHA256_RE.fullmatch(source_payload_sha256) is None:
        raise ValueError("source payload SHA-256 is invalid")
    if isinstance(source_payload_size, bool) or not isinstance(source_payload_size, int) or source_payload_size < 0:
        raise ValueError("source payload size is invalid")
    instant = _as_utc(operation_time).replace(microsecond=0)
    normalized = normalize_planner_documents(planner_documents, baseline, instant)
    timestamp_token = instant.strftime("%Y%m%dt%H%M%Sz")
    created_at_utc = instant.strftime("%Y-%m-%dT%H:%M:%SZ")
    stem = f"{timestamp_token}-{baseline.issue_id}-issue-planning-candidate-v{version}"
    logical_filename = f"{stem}.zip"
    candidate_id = f"{baseline.issue_id}-v{version}-{timestamp_token}"

    source_baseline = canonical_control_json_bytes({
        "canonical_issue_paths": list(context.canonical_issue_paths),
        "dependency_ids": list(context.dependency_summary),
        "issue_id": baseline.issue_id,
        "parent_epic_id": context.parent_epic_id,
        "parent_initiative_id": context.parent_initiative_id,
        "planner_payload_sha256": source_payload_sha256,
        "planner_payload_size": source_payload_size,
        "relevant_paths": list(context.relevant_source_paths),
        "remote_head": source_evidence.remote_head,
        "remote_head_disposition": source_evidence.remote_head_disposition,
        "schema_version": "spec-dock.issue-candidate-source-baseline.v1",
        "snapshot_id": source_evidence.snapshot_id,
        "source_branch": source_evidence.branch,
        "source_head": source_evidence.local_head,
        "source_manifest_hash": source_evidence.source_manifest_hash,
        "source_repository": source_evidence.repository,
        "upstream": source_evidence.upstream,
    })
    placeholder_map = canonical_control_json_bytes({
        "files": [],
        "schema_version": "spec-dock.issue-candidate-placeholder-map.v1",
    })
    paths = candidate_paths(onboarding_companion_path)
    entries = [
        {
            "checksum_covered": path != "CHECKSUMS.sha256",
            "content_mode": "static",
            "path": path,
            "role": {
                "CHECKSUMS.sha256": "checksums",
                "MANIFEST.json": "manifest",
                "PLACEHOLDER-ORACLE-MAP.json": "placeholder-map",
                "SOURCE-BASELINE.json": "source-baseline",
                "design.md": "design",
                "plan.md": "plan",
                "requirement.md": "requirement",
                onboarding_companion_path: "onboarding-companion",
            }[path],
        }
        for path in paths
    ]
    manifest = canonical_control_json_bytes({
        "candidate": {
            "candidate_id": candidate_id,
            "created_at_utc": created_at_utc,
            "internal_root": stem,
            "issue_id": baseline.issue_id,
            "logical_filename": logical_filename,
            "version": version,
        },
        "checksum_algorithm": "sha256",
        "checksum_file": "CHECKSUMS.sha256",
        "entries": entries,
        "placeholder_oracle_map_sha256": hashlib.sha256(placeholder_map).hexdigest(),
        "schema_version": "spec-dock.issue-candidate-manifest.v1",
        "source_baseline_sha256": hashlib.sha256(source_baseline).hexdigest(),
    })
    covered: dict[str, bytes] = {
        "MANIFEST.json": manifest,
        "PLACEHOLDER-ORACLE-MAP.json": placeholder_map,
        "SOURCE-BASELINE.json": source_baseline,
        **normalized,
        onboarding_companion_path: onboarding_companion_bytes,
    }
    checksums = "".join(
        f"{hashlib.sha256(covered[path]).hexdigest()}  {path}\n" for path in checksum_paths(onboarding_companion_path)
    ).encode("ascii")
    files = MappingProxyType({"CHECKSUMS.sha256": checksums, **covered})
    return CandidateMaterial(
        issue_id=baseline.issue_id,
        candidate_id=candidate_id,
        version=version,
        logical_filename=logical_filename,
        internal_root=stem,
        created_at_utc=created_at_utc,
        operation_time=instant,
        onboarding_companion_path=onboarding_companion_path,
        files=files,
    )


def derive_candidate_identity(
    material: CandidateMaterial,
    zip_bytes: bytes,
    *,
    observed_transport_filename: str,
) -> IssueCandidateIdentity:
    identity = IssueCandidateIdentity(
        issue_id=material.issue_id,
        candidate_id=material.candidate_id,
        version=material.version,
        logical_filename=material.logical_filename,
        observed_transport_filename=observed_transport_filename,
        internal_root=material.internal_root,
        source_repository=cast(
            "str",
            parse_canonical_control_json(material.files["SOURCE-BASELINE.json"])["source_repository"],
        ),
        source_branch=cast(
            "str",
            parse_canonical_control_json(material.files["SOURCE-BASELINE.json"])["source_branch"],
        ),
        source_head=cast(
            "str",
            parse_canonical_control_json(material.files["SOURCE-BASELINE.json"])["source_head"],
        ),
        zip_sha256=hashlib.sha256(zip_bytes).hexdigest(),
    )
    if identity.internal_root != identity.logical_filename.removesuffix(".zip"):
        raise ValueError("Candidate identity root does not match its logical filename")
    return identity


def validate_placeholder_oracle(
    documents: Mapping[str, bytes],
    placeholder_map: Mapping[str, Any],
) -> tuple[str, ...]:
    if set(placeholder_map) != {"files", "schema_version"}:
        return ("invalid_placeholder_map",)
    if placeholder_map["schema_version"] != "spec-dock.issue-candidate-placeholder-map.v1":
        return ("invalid_placeholder_map",)
    declarations = placeholder_map["files"]
    if not isinstance(declarations, list):
        return ("invalid_placeholder_map",)
    paths: list[str] = []
    findings: list[str] = []
    for declaration in declarations:
        if not isinstance(declaration, dict) or set(declaration) != {"path", "tokens"}:
            return ("invalid_placeholder_map",)
        path = declaration["path"]
        tokens = declaration["tokens"]
        if (
            path not in DOCUMENT_NAMES
            or path in paths
            or not isinstance(tokens, list)
            or any(not isinstance(token, str) or not _TOKEN_TEXT_RE.fullmatch(token) for token in tokens)
            or tokens != sorted(tokens, key=lambda value: value.encode("utf-8"))
            or len(tokens) != len(set(tokens))
        ):
            return ("invalid_placeholder_map",)
        paths.append(path)
        payload = documents.get(path)
        if payload is None:
            return ("invalid_placeholder_map",)
        declared = {token.encode() for token in tokens}
        present = set(_TOKEN_RE.findall(payload))
        if declared & present:
            findings.append("remaining_placeholder")
        if present - declared:
            findings.append("undeclared_placeholder")
    if paths != sorted(paths, key=lambda value: value.encode("utf-8")):
        return ("invalid_placeholder_map",)
    return tuple(dict.fromkeys(findings))


def verify_issue_candidate_files(
    files: Mapping[str, bytes],
    internal_root: str,
) -> tuple[str, ...]:
    findings: list[str] = []
    if any(path not in files for path in (*CONTROL_NAMES, *DOCUMENT_NAMES)):
        findings.append("inventory_mismatch")
        return tuple(findings)
    try:
        manifest = parse_canonical_control_json(files["MANIFEST.json"])
        baseline = parse_canonical_control_json(files["SOURCE-BASELINE.json"])
        placeholder = parse_canonical_control_json(files["PLACEHOLDER-ORACLE-MAP.json"])
    except ValueError:
        return ("invalid_control_json",)
    entries = manifest.get("entries")
    companion_entries = (
        [entry for entry in entries if isinstance(entry, dict) and entry.get("role") == "onboarding-companion"]
        if isinstance(entries, list)
        else []
    )
    if len(companion_entries) != 1:
        return ("companion_role_mismatch",)
    companion_path = companion_entries[0].get("path")
    try:
        validate_onboarding_companion_path(cast("str", companion_path))
    except (TypeError, ValueError):
        return ("companion_path_mismatch",)
    expected_paths = candidate_paths(cast("str", companion_path))
    if tuple(sorted(files, key=lambda value: value.encode("utf-8"))) != expected_paths:
        return ("inventory_mismatch",)
    try:
        validate_onboarding_companion(
            cast("str", companion_path),
            files[cast("str", companion_path)],
        )
    except (KeyError, UnicodeError, ValueError):
        findings.append("companion_content_mismatch")
    candidate = manifest.get("candidate")
    if (
        set(manifest)
        != {
            "candidate",
            "checksum_algorithm",
            "checksum_file",
            "entries",
            "placeholder_oracle_map_sha256",
            "schema_version",
            "source_baseline_sha256",
        }
        or not isinstance(candidate, dict)
        or set(candidate)
        != {
            "candidate_id",
            "created_at_utc",
            "internal_root",
            "issue_id",
            "logical_filename",
            "version",
        }
    ):
        findings.append("manifest_schema_mismatch")
        candidate = {}
    if candidate.get("internal_root") != internal_root:
        findings.append("manifest_identity_mismatch")
    if manifest.get("schema_version") != "spec-dock.issue-candidate-manifest.v1":
        findings.append("manifest_schema_mismatch")
    if (
        set(baseline)
        != {
            "canonical_issue_paths",
            "dependency_ids",
            "issue_id",
            "parent_epic_id",
            "parent_initiative_id",
            "planner_payload_sha256",
            "planner_payload_size",
            "relevant_paths",
            "remote_head",
            "remote_head_disposition",
            "schema_version",
            "snapshot_id",
            "source_branch",
            "source_head",
            "source_manifest_hash",
            "source_repository",
            "upstream",
        }
        or baseline.get("schema_version") != "spec-dock.issue-candidate-source-baseline.v1"
    ):
        findings.append("source_baseline_schema_mismatch")
    if not _valid_source_baseline(baseline):
        findings.append("source_baseline_binding_mismatch")
    if (
        candidate.get("issue_id") != baseline.get("issue_id")
        or not _valid_candidate_naming(candidate, internal_root)
        or manifest.get("checksum_algorithm") != "sha256"
        or manifest.get("checksum_file") != "CHECKSUMS.sha256"
    ):
        findings.append("manifest_identity_mismatch")
    if hashlib.sha256(files["SOURCE-BASELINE.json"]).hexdigest() != manifest.get("source_baseline_sha256"):
        findings.append("source_baseline_hash_mismatch")
    if hashlib.sha256(files["PLACEHOLDER-ORACLE-MAP.json"]).hexdigest() != manifest.get(
        "placeholder_oracle_map_sha256"
    ):
        findings.append("placeholder_map_hash_mismatch")
    placeholder_findings = validate_placeholder_oracle(
        {name: files[name] for name in DOCUMENT_NAMES},
        placeholder,
    )
    placeholder_files = placeholder.get("files")
    dynamic_paths = (
        {
            declaration["path"]
            for declaration in placeholder_files
            if isinstance(declaration, dict) and isinstance(declaration.get("path"), str)
        }
        if isinstance(placeholder_files, list) and "invalid_placeholder_map" not in placeholder_findings
        else set()
    )
    expected_entries = [
        {
            "checksum_covered": path != "CHECKSUMS.sha256",
            "content_mode": "dynamic" if path in dynamic_paths else "static",
            "path": path,
            "role": {
                "CHECKSUMS.sha256": "checksums",
                "MANIFEST.json": "manifest",
                "PLACEHOLDER-ORACLE-MAP.json": "placeholder-map",
                "SOURCE-BASELINE.json": "source-baseline",
                "design.md": "design",
                "plan.md": "plan",
                "requirement.md": "requirement",
                cast("str", companion_path): "onboarding-companion",
            }[path],
        }
        for path in expected_paths
    ]
    if entries != expected_entries:
        findings.append("manifest_inventory_mismatch")
    expected_checksums = "".join(
        f"{hashlib.sha256(files[path]).hexdigest()}  {path}\n" for path in checksum_paths(cast("str", companion_path))
    ).encode("ascii")
    if files["CHECKSUMS.sha256"] != expected_checksums:
        findings.append("checksum_mismatch")
    try:
        document_baseline = parse_current_front_matter_baseline({name: files[name] for name in DOCUMENT_NAMES})
        for name in DOCUMENT_NAMES:
            _fields, body = _parse_document(name, files[name])
            _validate_completeness(body, document_baseline)
        if document_baseline.issue_id != baseline.get("issue_id") or document_baseline.parents != (
            baseline.get("parent_epic_id"),
            baseline.get("parent_initiative_id"),
        ):
            raise ValueError("canonical document identity does not match the source baseline")
    except (KeyError, UnicodeError, ValueError):
        findings.append("canonical_document_mismatch")
    findings.extend(placeholder_findings)
    return tuple(dict.fromkeys(findings))


def _valid_source_baseline(value: Mapping[str, Any]) -> bool:
    canonical_paths = value.get("canonical_issue_paths")
    dependency_ids = value.get("dependency_ids")
    relevant_paths = value.get("relevant_paths")
    branch = value.get("source_branch")
    source_head = value.get("source_head")
    return (
        isinstance(canonical_paths, list)
        and len(canonical_paths) == 3
        and all(isinstance(path, str) for path in canonical_paths)
        and [path.rsplit("/", 1)[-1] for path in canonical_paths] == ["design.md", "plan.md", "requirement.md"]
        and canonical_paths == sorted(canonical_paths, key=lambda item: item.encode("utf-8"))
        and _sorted_unique_strings(dependency_ids)
        and _sorted_unique_strings(relevant_paths)
        and isinstance(value.get("issue_id"), str)
        and isinstance(value.get("parent_epic_id"), str)
        and isinstance(value.get("parent_initiative_id"), str)
        and isinstance(value.get("planner_payload_size"), int)
        and not isinstance(value.get("planner_payload_size"), bool)
        and cast("int", value["planner_payload_size"]) >= 0
        and isinstance(value.get("planner_payload_sha256"), str)
        and _SHA256_RE.fullmatch(cast("str", value["planner_payload_sha256"])) is not None
        and isinstance(branch, str)
        and value.get("upstream") == f"origin/{branch}"
        and isinstance(source_head, str)
        and _SHA40_RE.fullmatch(source_head) is not None
        and value.get("remote_head") == source_head
        and value.get("remote_head_disposition") == "fetched_remote_tracking_ref"
        and isinstance(value.get("source_manifest_hash"), str)
        and _SHA256_RE.fullmatch(cast("str", value["source_manifest_hash"])) is not None
        and isinstance(value.get("snapshot_id"), str)
        and _SHA256_RE.fullmatch(cast("str", value["snapshot_id"])) is not None
        and isinstance(value.get("source_repository"), str)
        and cast("str", value["source_repository"]).lower() == value["source_repository"]
        and cast("str", value["source_repository"]).count("/") == 1
    )


def _sorted_unique_strings(value: object) -> bool:
    return (
        isinstance(value, list)
        and all(isinstance(item, str) for item in value)
        and value == sorted(value, key=lambda item: item.encode("utf-8"))
        and len(value) == len(set(value))
    )


def _valid_candidate_naming(candidate: Mapping[str, Any], internal_root: str) -> bool:
    issue_id = candidate.get("issue_id")
    created_at = candidate.get("created_at_utc")
    if (
        not isinstance(issue_id, str)
        or not isinstance(created_at, str)
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", created_at) is None
        or isinstance(candidate.get("version"), bool)
        or not isinstance(candidate.get("version"), int)
        or cast("int", candidate.get("version")) < 1
    ):
        return False
    try:
        instant = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    token = instant.strftime("%Y%m%dt%H%M%Sz")
    version = cast("int", candidate["version"])
    expected_root = f"{token}-{issue_id}-issue-planning-candidate-v{version}"
    return (
        internal_root == expected_root
        and candidate.get("internal_root") == expected_root
        and candidate.get("logical_filename") == f"{expected_root}.zip"
        and candidate.get("candidate_id") == f"{issue_id}-v{version}-{token}"
    )


def mechanical_replacement_cost(old_text: str, new_text: str) -> int:
    if not isinstance(old_text, str) or not isinstance(new_text, str):
        raise ValueError("mechanical replacement text must be strings")
    return len(old_text.encode("utf-8")) + len(new_text.encode("utf-8"))


def apply_mechanical_revision(
    payloads: Mapping[str, bytes],
    *,
    target_file: str,
    onboarding_companion_path: str,
    old_text: str,
    new_text: str,
    diff_budget: int,
) -> Mapping[str, bytes]:
    validate_onboarding_companion_path(onboarding_companion_path)
    expected = (*DOCUMENT_NAMES, onboarding_companion_path)
    if tuple(payloads) != expected or any(not isinstance(value, bytes) for value in payloads.values()):
        raise ValueError("mechanical payload inventory is invalid")
    if target_file not in expected:
        raise ValueError("mechanical target file is not allowed")
    if (
        not old_text
        or not new_text
        or old_text == new_text
        or isinstance(diff_budget, bool)
        or not isinstance(diff_budget, int)
        or diff_budget < 1
    ):
        raise ValueError("mechanical revision request is invalid")
    if mechanical_replacement_cost(old_text, new_text) > diff_budget:
        raise ValueError("mechanical revision exceeds diff budget")
    source = payloads[target_file]
    if target_file in DOCUMENT_NAMES:
        fields, body = _parse_document(target_file, source)
        del fields
        prefix = source[: -len(body)]
    else:
        body = source
        prefix = b""
    old_bytes = old_text.encode("utf-8")
    new_bytes = new_text.encode("utf-8")
    if body.count(old_bytes) != 1:
        raise ValueError("mechanical old text must match exactly one body occurrence")
    revised = dict(payloads)
    revised[target_file] = prefix + body.replace(
        old_bytes,
        new_bytes,
        1,
    )
    if target_file in DOCUMENT_NAMES:
        _parse_document(target_file, revised[target_file])
    else:
        validate_onboarding_companion(target_file, revised[target_file])
    return MappingProxyType(revised)


def _require_document_inventory(documents: Mapping[str, bytes]) -> None:
    if tuple(documents) != DOCUMENT_NAMES or any(not isinstance(value, bytes) for value in documents.values()):
        raise ValueError("planner documents must contain exactly three canonical files in order")


def _parse_document(name: str, data: bytes) -> tuple[dict[str, object], bytes]:
    if name not in _FRONT_MATTER or b"\r" in data or b"\0" in data or b"\xef\xbb\xbf" in data:
        raise ValueError("front matter document bytes are invalid")
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ValueError("front matter document must be UTF-8") from error
    if not text.startswith("---\n"):
        raise ValueError("front matter start is missing")
    separator = text.find("\n---\n", 4)
    if separator < 0:
        raise ValueError("front matter end is missing")
    raw_lines = text[4:separator].splitlines()
    schema = _FRONT_MATTER[name]
    if len(raw_lines) != len(schema):
        raise ValueError("front matter key set is invalid")
    fields: dict[str, object] = {}
    for line, (expected_key, fixed) in zip(raw_lines, schema, strict=True):
        key, delimiter, raw = line.partition(": ")
        if delimiter != ": " or key != expected_key or key in fields:
            raise ValueError("front matter key order is invalid")
        if key == "種別":
            value: object = raw
        else:
            try:
                value = json.loads(raw)
            except json.JSONDecodeError as error:
                raise ValueError("front matter value syntax is invalid") from error
        if fixed is not None and value != (list(fixed) if isinstance(fixed, tuple) else fixed):
            raise ValueError("front matter fixed value is invalid")
        if key in {"ID", "タイトル", "状態", "作成者", "最終更新"} and not isinstance(value, str):
            raise ValueError("front matter scalar type is invalid")
        if key in {"親", "依存"}:
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                raise ValueError("front matter array type is invalid")
            value = tuple(value)
        fields[key] = value
    updated = fields["最終更新"]
    if not isinstance(updated, str) or not _DATE_RE.fullmatch(updated):
        raise ValueError("front matter update date is invalid")
    try:
        date.fromisoformat(updated)
    except ValueError as error:
        raise ValueError("front matter update date is invalid") from error
    body = text[separator + 5 :].encode()
    if not body.endswith(b"\n"):
        raise ValueError("front matter document must end with LF")
    return fields, body


def _validate_completeness(body: bytes, baseline: IssueFrontMatterBaseline) -> None:
    text = body.decode("utf-8")
    lines = text.splitlines()
    nonblank = [line for line in lines if line.strip()]
    expected_h1_tokens = (baseline.issue_id, baseline.title)
    if (
        not nonblank
        or not nonblank[0].startswith("# ")
        or any(token not in nonblank[0] for token in expected_h1_tokens)
    ):
        raise ValueError("document completeness requires an identity H1")
    if sum(line.startswith("# ") for line in lines) != 1:
        raise ValueError("document completeness requires exactly one H1")
    section_indexes = [index for index, line in enumerate(lines) if line.startswith("## ")]
    if not section_indexes:
        raise ValueError("document completeness requires at least one H2")
    boundaries = [*section_indexes[1:], len(lines)]
    for start, end in zip(section_indexes, boundaries, strict=True):
        section = lines[start + 1 : end]
        if not any(_is_substantive_line(line) for line in section):
            raise ValueError("document completeness requires substantive H2 content")


def _is_substantive_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False
    if re.fullmatch(r"(?:`{3,}|~{3,})", stripped):
        return False
    return not (stripped.startswith("<!--") and stripped.endswith("-->"))


def _render_document(
    name: str,
    fields: Mapping[str, object],
    body: bytes,
    updated_date: str,
) -> bytes:
    lines = ["---"]
    for key, fixed in _FRONT_MATTER[name]:
        value = fixed if fixed is not None else fields[key]
        if key == "最終更新":
            value = updated_date
        if key == "種別":
            rendered = cast("str", value)
        else:
            rendered = json.dumps(value, ensure_ascii=False, separators=(", ", ": "))
        lines.append(f"{key}: {rendered}")
    lines.extend(("---", ""))
    normalized_body = body.rstrip(b"\n") + b"\n"
    return "\n".join(lines).encode() + b"\n" + normalized_body


def _validate_control_value(value: object, *, field_name: str) -> None:
    if isinstance(value, str) or value is None:
        if value is None:
            raise ValueError(f"{field_name} contains null")
        return
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field_name} contains a non-finite float")
        raise ValueError(f"{field_name} contains a float")
    if isinstance(value, list):
        for item in value:
            _validate_control_value(item, field_name=field_name)
        return
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError(f"{field_name} contains a non-string key")
        for item in value.values():
            _validate_control_value(item, field_name=field_name)
        return
    raise ValueError(f"{field_name} contains a non-JSON value")


def _validate_source_binding(
    context: PlanningContext,
    evidence: PlanningSourceEvidence,
    baseline: IssueFrontMatterBaseline,
) -> None:
    if (
        context.issue_id != baseline.issue_id
        or context.parent_epic_id != baseline.parents[0]
        or context.parent_initiative_id != baseline.parents[1]
        or context.repository != evidence.repository
        or context.branch != evidence.branch
        or context.source_head != evidence.local_head
        or evidence.local_head != evidence.remote_head
    ):
        raise ValueError("source evidence does not match the Candidate context")
    for values, field_name in (
        (context.canonical_issue_paths, "canonical paths"),
        (context.dependency_summary, "dependency IDs"),
        (context.relevant_source_paths, "relevant paths"),
    ):
        if tuple(values) != tuple(sorted(values, key=lambda value: value.encode("utf-8"))):
            raise ValueError(f"{field_name} must already be in UTF-8 byte order")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("operation time must be timezone-aware")
    return value.astimezone(timezone.utc)
