from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
from typing import TYPE_CHECKING, Literal
import unicodedata
import zipfile

from spec_dock_runtime.domain.authoring_pack.authority_boundary import (
    scan_authoring_payload,
    scan_constraint_sensitive_payload,
    scan_issue_candidate_sensitive_payload,
)
from spec_dock_runtime.domain.authoring_pack.prompt_pack_contract import (
    ADOPTION_STATUS,
    AUTHORITY,
    BUNDLE_GENERATION_NOT_PROMOTION,
    EXPECTED_OUTPUT_ROOT,
    REQUIRED_METADATA,
)
from spec_dock_runtime.domain.authoring_pack.provenance_contract import provenance_state_findings

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

PackReviewStatus = Literal["pass", "fail", "blocked", "stale", "rejected"]
PackInputKind = Literal["zip", "tree"]

SUPPORTED_TEXT_SUFFIXES = {".json", ".md", ".txt", ".yml", ".yaml"}
NESTED_ARCHIVE_SUFFIXES = {".zip", ".tar", ".tgz", ".gz", ".bz2", ".xz", ".7z"}
MAX_ENTRY_BYTES = 2_000_000
MAX_TOTAL_BYTES = 10_000_000
JSON_METADATA = tuple(path for path in REQUIRED_METADATA if path.endswith(".json"))
SECRET_PATH_PARTS = {"secret", "secrets", "token", "tokens", "credential", "credentials", "password", "passwords"}
CLAIM_SCAN_EXCLUDED_PATHS = {
    "safe-output-constraints.md",
    "chatgpt-use-prompt.md",
    "expected-output-contract.md",
}


@dataclass(frozen=True)
class PackReviewResult:
    status: PackReviewStatus
    input_path: str
    input_kind: PackInputKind
    authority: str = AUTHORITY
    adoption_status: str = ADOPTION_STATUS
    bundle_generation_not_promotion: bool = BUNDLE_GENERATION_NOT_PROMOTION
    evidence_mode: str | None = None
    fallback: bool = False
    authority_level: str = "zip_review"
    missing_evidence: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    reviewed_files: tuple[str, ...] = ()
    content_sha256: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "input_path": self.input_path,
            "input_kind": self.input_kind,
            "authority": self.authority,
            "adoption_status": self.adoption_status,
            "bundle_generation_not_promotion": self.bundle_generation_not_promotion,
            "evidence_mode": self.evidence_mode,
            "fallback": self.fallback,
            "authority_level": self.authority_level,
            "missing_evidence": list(self.missing_evidence),
            "findings": list(self.findings),
            "reviewed_files": list(self.reviewed_files),
            "pack_digest": {
                "algorithm": "sha256-tree-v1",
                "content_sha256": self.content_sha256,
            },
        }


@dataclass(frozen=True)
class ZipReviewProfile:
    name: str
    expected_root: str
    required_paths: tuple[str, ...]
    allowed_suffixes: frozenset[str]
    max_file_count: int
    max_entry_bytes: int
    max_total_bytes: int
    max_entry_compression_ratio: int
    max_total_compression_ratio: int
    cross_file_validator: Callable[[Mapping[str, bytes], str], tuple[str, ...]]


def issue_candidate_v1_profile(
    *,
    expected_root: str,
    expected_companion_path: str,
    cross_file_validator: Callable[[Mapping[str, bytes], str], tuple[str, ...]],
) -> ZipReviewProfile:
    required = tuple(
        sorted(
            (
                "CHECKSUMS.sha256",
                "MANIFEST.json",
                "PLACEHOLDER-ORACLE-MAP.json",
                "SOURCE-BASELINE.json",
                "design.md",
                "plan.md",
                "requirement.md",
                expected_companion_path,
            ),
            key=lambda value: value.encode("utf-8"),
        )
    )
    return ZipReviewProfile(
        name="issue-planning-candidate-v1",
        expected_root=expected_root,
        required_paths=required,
        allowed_suffixes=frozenset({".md", ".json", ".sha256"}),
        max_file_count=8,
        max_entry_bytes=2_000_000,
        max_total_bytes=10_000_000,
        max_entry_compression_ratio=100,
        max_total_compression_ratio=100,
        cross_file_validator=cross_file_validator,
    )


def issue_authoring_v1_profile(
    *,
    expected_root: str,
    expected_companion_path: str,
    cross_file_validator: Callable[[Mapping[str, bytes], str], tuple[str, ...]],
) -> ZipReviewProfile:
    required = tuple(
        sorted(
            (
                "design.md",
                "plan.md",
                "requirement.md",
                expected_companion_path,
            ),
            key=lambda value: value.encode("utf-8"),
        )
    )
    return ZipReviewProfile(
        name="issue-planning-authoring-v1",
        expected_root=expected_root,
        required_paths=required,
        allowed_suffixes=frozenset({".md"}),
        max_file_count=4,
        max_entry_bytes=2_000_000,
        max_total_bytes=8_000_000,
        max_entry_compression_ratio=100,
        max_total_compression_ratio=100,
        cross_file_validator=cross_file_validator,
    )


def review_pack_input(
    input_path: Path,
    *,
    profile: ZipReviewProfile | None = None,
) -> PackReviewResult:
    if profile is not None:
        return _review_profile_input(input_path, profile)
    if not input_path.exists():
        return PackReviewResult(
            status="blocked",
            input_path=str(input_path),
            input_kind="tree",
            findings=("input_missing",),
        )
    if input_path.is_symlink():
        return PackReviewResult(
            status="rejected",
            input_path=str(input_path),
            input_kind="tree",
            findings=("symlink_input_root",),
        )
    if input_path.is_dir():
        return _review_tree(input_path)
    if zipfile.is_zipfile(input_path):
        return _review_zip(input_path)
    return PackReviewResult(
        status="fail",
        input_path=str(input_path),
        input_kind="tree",
        findings=("unsupported_input_kind",),
    )


def _review_profile_input(input_path: Path, profile: ZipReviewProfile) -> PackReviewResult:
    if not input_path.exists():
        return _profile_result(input_path, "tree", ("input_missing",))
    if input_path.is_symlink():
        return _profile_result(input_path, "tree", ("symlink_input_root",))
    if input_path.is_dir() or not zipfile.is_zipfile(input_path):
        return _profile_result(input_path, "tree", ("zip_input_required",))
    return _review_profile_zip(input_path, profile)


def _review_profile_zip(input_path: Path, profile: ZipReviewProfile) -> PackReviewResult:
    findings: list[str] = []
    payloads: dict[str, bytes] = {}
    reviewed_files: list[str] = []
    total_size = 0
    total_compressed = 0
    seen: set[str] = set()
    casefolded: set[str] = set()
    normalized: set[str] = set()
    try:
        with zipfile.ZipFile(input_path) as archive:
            infos = archive.infolist()
            if len(infos) > profile.max_file_count:
                findings.append("file_count_limit")
            for info in infos:
                if info.is_dir():
                    findings.append("directory_entry")
                    continue
                rel_name = _profile_relative_name(info.filename, profile.expected_root)
                if rel_name is None:
                    findings.append("wrong_root")
                    continue
                if not _profile_safe_relative_path(rel_name):
                    findings.append("unsafe_path")
                    continue
                if rel_name in seen:
                    findings.append("duplicate_entry")
                    continue
                folded = rel_name.casefold()
                nfc = unicodedata.normalize("NFC", rel_name)
                if folded in casefolded:
                    findings.append("casefold_collision")
                    continue
                if nfc in normalized:
                    findings.append("unicode_nfc_collision")
                    continue
                seen.add(rel_name)
                casefolded.add(folded)
                normalized.add(nfc)
                reviewed_files.append(rel_name)
                total_size += info.file_size
                total_compressed += info.compress_size
                entry_findings = _profile_entry_findings(info, rel_name, profile)
                findings.extend(entry_findings)
                if entry_findings:
                    continue
                try:
                    content = archive.read(info)
                except (RuntimeError, OSError, zipfile.BadZipFile):
                    findings.append("unreadable_payload")
                    continue
                try:
                    content.decode("ascii" if rel_name == "CHECKSUMS.sha256" else "utf-8")
                except UnicodeDecodeError:
                    findings.append("binary_payload")
                    continue
                payloads[rel_name] = content
    except (OSError, zipfile.BadZipFile):
        return _profile_result(input_path, "zip", ("unreadable_archive",))

    if total_size > profile.max_total_bytes:
        findings.append("total_size_limit")
    if total_size and total_size / max(total_compressed, 1) > profile.max_total_compression_ratio:
        findings.append("total_compression_ratio_limit")
    if tuple(sorted(seen, key=lambda value: value.encode("utf-8"))) != profile.required_paths:
        findings.append("inventory_mismatch")
    if not findings:
        for content in payloads.values():
            findings.extend(_safe_profile_findings(scan_issue_candidate_sensitive_payload(content.decode("utf-8"))))
        findings.extend(_safe_profile_findings(profile.cross_file_validator(payloads, profile.expected_root)))
    unique_findings = tuple(dict.fromkeys(findings))
    return PackReviewResult(
        status="pass" if not unique_findings else "rejected",
        input_path=str(input_path),
        input_kind="zip",
        authority_level=profile.name,
        findings=unique_findings,
        reviewed_files=tuple(sorted(reviewed_files, key=lambda value: value.encode("utf-8"))),
        content_sha256=_content_digest(list(payloads.items())) if not unique_findings else None,
    )


def _profile_result(
    input_path: Path,
    input_kind: PackInputKind,
    findings: tuple[str, ...],
) -> PackReviewResult:
    return PackReviewResult(
        status="blocked" if findings == ("input_missing",) else "rejected",
        input_path=str(input_path),
        input_kind=input_kind,
        authority_level="issue-planning-candidate-v1",
        findings=findings,
    )


def _profile_relative_name(name: str, root: str) -> str | None:
    prefix = f"{root}/"
    if not name.startswith(prefix):
        return None
    return name[len(prefix) :]


def _profile_safe_relative_path(value: str) -> bool:
    if not value or "\0" in value or "\\" in value:
        return False
    if len(value) >= 2 and value[0].isalpha() and value[1] == ":":
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and path.as_posix() == value
        and all(part not in {"", ".", ".."} and not part.startswith(".") for part in path.parts)
    )


def _profile_entry_findings(
    info: zipfile.ZipInfo,
    rel_name: str,
    profile: ZipReviewProfile,
) -> tuple[str, ...]:
    findings: list[str] = []
    if info.flag_bits & 0x1:
        findings.append("encrypted_entry")
    file_type = stat.S_IFMT(info.external_attr >> 16)
    if file_type == stat.S_IFLNK:
        findings.append("symlink_entry")
    elif file_type != stat.S_IFREG:
        findings.append("special_entry")
    if (info.external_attr >> 16) & 0o111:
        findings.append("executable_entry")
    if info.file_size > profile.max_entry_bytes:
        findings.append("entry_size_limit")
    if info.file_size and info.file_size / max(info.compress_size, 1) > profile.max_entry_compression_ratio:
        findings.append("entry_compression_ratio_limit")
    suffix = PurePosixPath(rel_name).suffix.lower()
    if suffix in NESTED_ARCHIVE_SUFFIXES:
        findings.append("nested_archive")
    if suffix not in profile.allowed_suffixes:
        findings.append("unsupported_suffix")
    return tuple(findings)


def _safe_profile_findings(findings: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(finding.partition(":")[0] for finding in findings)


def _review_zip(input_path: Path) -> PackReviewResult:
    findings: list[str] = []
    payloads: dict[str, str] = {}
    reviewed_files: list[str] = []
    digest_entries: list[tuple[str, bytes]] = []
    total_size = 0
    root = EXPECTED_OUTPUT_ROOT.rstrip("/")
    with zipfile.ZipFile(input_path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos if not info.is_dir()]
        seen_names: set[str] = set()
        if not names:
            findings.append("empty_zip")
        for info in infos:
            if info.is_dir():
                continue
            total_size += info.file_size
            if total_size > MAX_TOTAL_BYTES:
                findings.append("oversized_total")
                continue
            rel_name = _relative_name(info.filename, root, findings)
            if rel_name is None:
                continue
            if rel_name in seen_names:
                findings.append(f"duplicate_entry:{rel_name}")
                continue
            seen_names.add(rel_name)
            entry_findings_before = len(findings)
            _validate_entry(info, rel_name, findings)
            reviewed_files.append(rel_name)
            if len(findings) > entry_findings_before:
                continue
            try:
                content = archive.read(info)
            except (RuntimeError, zipfile.BadZipFile):
                findings.append(f"unreadable_payload:{rel_name}")
                continue
            digest_entries.append((rel_name, content))
            if _can_read_text_payload(info, rel_name):
                try:
                    payloads[rel_name] = content.decode("utf-8")
                except (RuntimeError, zipfile.BadZipFile):
                    findings.append(f"unreadable_payload:{rel_name}")
                except UnicodeDecodeError:
                    findings.append(f"binary_payload:{rel_name}")
    metadata_status = _validate_metadata(payloads, findings)
    findings.extend(_scan_payloads(payloads))
    return PackReviewResult(
        status=_status_from_findings(tuple(findings), metadata_status),
        input_path=str(input_path),
        input_kind="zip",
        evidence_mode=_payload_evidence_mode(payloads),
        findings=tuple(dict.fromkeys(findings)),
        reviewed_files=tuple(sorted(reviewed_files)),
        content_sha256=_content_digest(digest_entries)
        if _status_from_findings(tuple(findings), metadata_status) == "pass"
        else None,
    )


def _review_tree(input_path: Path) -> PackReviewResult:
    findings: list[str] = []
    payloads: dict[str, str] = {}
    reviewed_files: list[str] = []
    digest_entries: list[tuple[str, bytes]] = []
    root = input_path / EXPECTED_OUTPUT_ROOT.rstrip("/")
    if root.is_symlink():
        findings.append("symlink_entry:specdock-authoring-pack")
    elif not root.is_dir():
        findings.append("wrong_root")
    else:
        for path in sorted(root.rglob("*")):
            if path.is_dir() and not path.is_symlink():
                continue
            rel_name = path.relative_to(root).as_posix()
            _validate_relative_path(rel_name, findings)
            if path.is_symlink():
                findings.append(f"symlink_entry:{rel_name}")
                reviewed_files.append(rel_name)
                continue
            if not path.is_file():
                continue
            _validate_tree_entry(path, rel_name, findings)
            reviewed_files.append(rel_name)
            try:
                content = path.read_bytes()
            except OSError:
                findings.append(f"unreadable_payload:{rel_name}")
                continue
            digest_entries.append((rel_name, content))
            if _is_supported_text(rel_name):
                try:
                    payloads[rel_name] = content.decode("utf-8")
                except UnicodeDecodeError:
                    findings.append(f"binary_payload:{rel_name}")
        _validate_metadata(payloads, findings)
        findings.extend(_scan_payloads(payloads))
    return PackReviewResult(
        status=_status_from_findings(tuple(findings), "pass"),
        input_path=str(input_path),
        input_kind="tree",
        evidence_mode=_payload_evidence_mode(payloads),
        fallback=True,
        authority_level="lower_than_zip_review",
        missing_evidence=("zip-central-directory",),
        findings=tuple(dict.fromkeys(findings)),
        reviewed_files=tuple(sorted(reviewed_files)),
        content_sha256=_content_digest(digest_entries)
        if _status_from_findings(tuple(findings), "pass") == "pass"
        else None,
    )


def _relative_name(name: str, root: str, findings: list[str]) -> str | None:
    if not name.startswith(f"{root}/"):
        findings.append("wrong_root")
        return None
    rel_name = name[len(root) + 1 :]
    _validate_relative_path(rel_name, findings)
    return rel_name


def _validate_relative_path(rel_name: str, findings: list[str]) -> None:
    if "\\" in rel_name:
        findings.append(f"path_separator_backslash:{rel_name}")
        return
    if len(rel_name) >= 2 and rel_name[1] == ":" and rel_name[0].isalpha():
        findings.append(f"host_local_path:{rel_name}")
        return
    path = PurePosixPath(rel_name)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        findings.append(f"path_traversal:{rel_name}")
    if any(part.startswith(".") for part in path.parts):
        findings.append(f"hidden_path:{rel_name}")
    parts = tuple(part.lower() for part in path.parts)
    if parts and parts[0] in {"users", "home", "volumes", "private"}:
        findings.append(f"host_local_path:{rel_name}")
    if any(part in {".oracle", ".ssh"} for part in parts):
        findings.append(f"host_local_path:{rel_name}")
    if any(part in SECRET_PATH_PARTS or "api-key" in part or "api_key" in part for part in parts):
        findings.append(f"secret_path:{rel_name}")


def _validate_entry(info: zipfile.ZipInfo, rel_name: str, findings: list[str]) -> None:
    if info.flag_bits & 0x1:
        findings.append(f"encrypted_entry:{rel_name}")
    mode = (info.external_attr >> 16) & 0o170000
    if mode == 0o120000:
        findings.append(f"symlink_entry:{rel_name}")
    permissions = (info.external_attr >> 16) & 0o777
    if permissions & 0o111:
        findings.append(f"executable_entry:{rel_name}")
    if info.file_size > MAX_ENTRY_BYTES:
        findings.append(f"oversized_entry:{rel_name}")
    suffix = PurePosixPath(rel_name).suffix.lower()
    if suffix in NESTED_ARCHIVE_SUFFIXES:
        findings.append(f"nested_archive:{rel_name}")
    if suffix not in SUPPORTED_TEXT_SUFFIXES:
        findings.append(f"unsupported_suffix:{rel_name}")


def _validate_tree_entry(path: Path, rel_name: str, findings: list[str]) -> None:
    try:
        stat_result = path.stat()
        size = stat_result.st_size
    except OSError:
        findings.append(f"unreadable_payload:{rel_name}")
        return
    if stat_result.st_mode & 0o111:
        findings.append(f"executable_entry:{rel_name}")
    if size > MAX_ENTRY_BYTES:
        findings.append(f"oversized_entry:{rel_name}")
    suffix = PurePosixPath(rel_name).suffix.lower()
    if suffix in NESTED_ARCHIVE_SUFFIXES:
        findings.append(f"nested_archive:{rel_name}")
    if suffix not in SUPPORTED_TEXT_SUFFIXES:
        findings.append(f"unsupported_suffix:{rel_name}")


def _can_read_text_payload(info: zipfile.ZipInfo, rel_name: str) -> bool:
    if info.flag_bits & 0x1:
        return False
    mode = (info.external_attr >> 16) & 0o170000
    if mode == 0o120000:
        return False
    return _is_supported_text(rel_name) and info.file_size <= MAX_ENTRY_BYTES


def _validate_metadata(payloads: dict[str, str], findings: list[str]) -> str:
    status = "pass"
    for metadata in REQUIRED_METADATA:
        if metadata not in payloads:
            findings.append(f"missing_metadata:{metadata}")
            status = "fail"
    objects: dict[str, object] = {}
    for metadata in JSON_METADATA:
        if metadata not in payloads:
            continue
        try:
            objects[metadata] = json.loads(payloads[metadata])
        except json.JSONDecodeError:
            findings.append(f"invalid_json:{metadata}")
            status = "fail"
            continue
        if not isinstance(objects[metadata], dict):
            findings.append(f"non_object_json:{metadata}")
            status = "fail"
    source_manifest = objects.get("source-manifest.json")
    stale_if = objects.get("stale-if.json")
    for metadata, payload in objects.items():
        if isinstance(payload, dict):
            _validate_authority_metadata(metadata, payload, findings)
            _validate_required_metadata_fields(metadata, payload, findings)
    provenance = objects.get("provenance.json")
    if isinstance(provenance, dict):
        provenance_findings = provenance_state_findings(provenance)
        findings.extend(provenance_findings)
        if provenance_findings:
            status = "rejected"
    if isinstance(source_manifest, dict) and isinstance(stale_if, dict):
        expected_hash = stale_if.get("source_manifest_hash_changes", stale_if.get("source_manifest_hash"))
        if expected_hash is not None and source_manifest.get("source_manifest_hash") != expected_hash:
            findings.append("source_hash_mismatch")
            status = "stale"
    return status


def _validate_authority_metadata(metadata: str, payload: dict[str, object], findings: list[str]) -> None:
    if (metadata == "manifest.json" or "authority" in payload) and payload.get("authority") != AUTHORITY:
        findings.append("invalid_authority" if metadata == "manifest.json" else f"invalid_authority:{metadata}")
    if (metadata == "manifest.json" or "adoption_status" in payload) and payload.get(
        "adoption_status"
    ) != ADOPTION_STATUS:
        findings.append(
            "invalid_adoption_status" if metadata == "manifest.json" else f"invalid_adoption_status:{metadata}"
        )
    if (metadata == "manifest.json" or "bundle_generation_not_promotion" in payload) and payload.get(
        "bundle_generation_not_promotion"
    ) is not BUNDLE_GENERATION_NOT_PROMOTION:
        findings.append(
            "invalid_bundle_generation_not_promotion"
            if metadata == "manifest.json"
            else f"invalid_bundle_generation_not_promotion:{metadata}"
        )


def _validate_required_metadata_fields(metadata: str, payload: dict[str, object], findings: list[str]) -> None:
    if metadata == "provenance.json":
        for key in ("evidence_mode", "sync_state", "github_sync", "source_manifest_hash"):
            if not isinstance(payload.get(key), str):
                findings.append(f"missing_or_invalid_field:{metadata}.{key}")
    if metadata == "source-manifest.json":
        if not isinstance(payload.get("source_manifest_hash"), str):
            findings.append(f"missing_or_invalid_field:{metadata}.source_manifest_hash")
        if not isinstance(payload.get("source_hashes"), dict):
            findings.append(f"missing_or_invalid_field:{metadata}.source_hashes")


def _payload_evidence_mode(payloads: dict[str, str]) -> str | None:
    try:
        provenance = json.loads(payloads.get("provenance.json", "{}"))
    except json.JSONDecodeError:
        return None
    if not isinstance(provenance, dict):
        return None
    value = provenance.get("evidence_mode")
    return value if isinstance(value, str) else None


def _scan_payloads(payloads: dict[str, str]) -> tuple[str, ...]:
    findings: list[str] = []
    for rel_name, text in payloads.items():
        if rel_name in CLAIM_SCAN_EXCLUDED_PATHS:
            findings.extend(scan_constraint_sensitive_payload(text))
            continue
        findings.extend(scan_authoring_payload(_payload_for_authority_scan(rel_name, text)))
    return tuple(findings)


def _payload_for_authority_scan(rel_name: str, text: str) -> str:
    if not rel_name.endswith("/candidate.json"):
        return text
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text
    if not isinstance(payload, dict):
        return text
    profile = payload.get("profile_recommendation")
    if not isinstance(profile, dict) or profile.get("authorized_profile") is not None:
        return text
    sanitized_profile = dict(profile)
    sanitized_profile.pop("authorized_profile", None)
    sanitized_payload = dict(payload)
    sanitized_payload["profile_recommendation"] = sanitized_profile
    return json.dumps(sanitized_payload, sort_keys=True)


def _status_from_findings(findings: tuple[str, ...], metadata_status: str) -> PackReviewStatus:
    if any(finding == "wrong_root" for finding in findings):
        return "rejected"
    if (
        any(
            finding.startswith(("missing_metadata:", "invalid_json:", "non_object_json:", "missing_or_invalid_field:"))
            for finding in findings
        )
        or metadata_status == "fail"
    ):
        return "fail"
    if any(_is_rejected_finding(finding) for finding in findings):
        return "rejected"
    if any(finding.startswith("source_hash_mismatch") for finding in findings) or metadata_status == "stale":
        return "stale"
    if findings:
        return "rejected"
    return "pass"


def _is_rejected_finding(finding: str) -> bool:
    return not finding.startswith((
        "missing_metadata:",
        "invalid_json:",
        "non_object_json:",
        "missing_or_invalid_field:",
        "source_hash_mismatch",
    ))


def _is_supported_text(rel_name: str) -> bool:
    return PurePosixPath(rel_name).suffix.lower() in SUPPORTED_TEXT_SUFFIXES


def _content_digest(entries: list[tuple[str, bytes]]) -> str:
    digest = hashlib.sha256()
    for rel_name, content in sorted(entries):
        digest.update(rel_name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(content).hexdigest().encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()
