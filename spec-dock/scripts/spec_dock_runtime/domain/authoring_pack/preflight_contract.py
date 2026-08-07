from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from spec_dock_runtime.domain.authoring_pack.source_manifest import SourceManifest

PreflightStatus = Literal["pass", "blocked", "stale"]
EvidenceMode = Literal["github-synced", "local-context"]
SyncState = Literal["synced", "blocked", "stale", "local_context"]
GitHubSync = Literal["verified", "not_verified", "failed"]
FETCH_POLICY_ID = "origin-fetch-v1"
MAX_FETCH_ATTEMPTS = 2
FETCH_TIMEOUT_SECONDS = 60.0
FETCH_BACKOFF_SECONDS = 0.25
DIAGNOSTIC_EXCERPT_MAX_BYTES = 1024
TerminationKind = Literal["exited", "timeout", "spawn_error", "cancelled"]
FetchFailureClass = Literal[
    "timeout",
    "transient_transport",
    "remote_throttled",
    "local_ref_lock_contention",
    "remote_access_denied_or_not_found",
    "host_identity_failure",
    "repository_configuration",
    "execution_or_filesystem_denied",
    "spawn_failure",
    "cancelled",
    "unknown",
]
ClassificationConfidence = Literal["certain", "probable", "unknown"]
PublicationStatus = Literal["not_requested", "published", "failed", "rejected"]
RemoteHeadDisposition = Literal[
    "fetched_remote_tracking_ref",
    "unverified_cache",
    "unavailable",
    "not_applicable",
]
ConcurrentChangeCheck = Literal["stable", "changed", "not_run", "not_applicable"]
RECEIPT_KIND = "spec-dock.authoring.github-sync-preflight"


def receipt_digest_value(payload: dict[str, object]) -> str:
    digest_payload = {key: value for key, value in payload.items() if key != "receipt_digest"}
    canonical = json.dumps(
        digest_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True)
class FetchClassification:
    failure_class: FetchFailureClass | None
    confidence: ClassificationConfidence
    retryable: bool
    diagnostic_code: str | None


@dataclass(frozen=True)
class GitProcessOutcome:
    return_code: int | None
    termination: TerminationKind
    stdout: bytes
    stderr: bytes
    duration_ms: int
    os_error_kind: str | None = None


@dataclass(frozen=True)
class SafeDiagnostic:
    code: str | None = None
    excerpt: str | None = None
    redacted_sha256: str | None = None
    source_byte_count: int = 0
    excerpt_byte_count: int = 0
    truncated: bool = False
    redaction_applied: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "excerpt": self.excerpt,
            "redacted_sha256": self.redacted_sha256,
            "source_byte_count": self.source_byte_count,
            "excerpt_byte_count": self.excerpt_byte_count,
            "truncated": self.truncated,
            "redaction_applied": self.redaction_applied,
        }


@dataclass(frozen=True)
class FetchAttempt:
    attempt_number: int
    duration_ms: int
    return_code: int | None
    termination: TerminationKind
    failure_class: FetchFailureClass | None
    confidence: ClassificationConfidence
    retryable: bool
    diagnostic: SafeDiagnostic = field(default_factory=SafeDiagnostic)

    def to_dict(self) -> dict[str, object]:
        return {
            "attempt_number": self.attempt_number,
            "duration_ms": self.duration_ms,
            "return_code": self.return_code,
            "termination": self.termination,
            "failure_class": self.failure_class,
            "confidence": self.confidence,
            "retryable": self.retryable,
            "diagnostic": self.diagnostic.to_dict(),
        }


@dataclass(frozen=True)
class FetchSummary:
    status: Literal["success", "failed", "cancelled", "not_started", "not_applicable"]
    policy_id: str = FETCH_POLICY_ID
    executable: str = "git"
    argv: tuple[str, ...] = ("fetch", "--prune", "origin")
    remote: str = "origin"
    timeout_seconds: float = FETCH_TIMEOUT_SECONDS
    environment_policy_id: str = "git-fetch-noninteractive-v1"
    execution_policy_context: Literal["unreported"] = "unreported"
    attempts: tuple[FetchAttempt, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "policy_id": self.policy_id,
            "executable": self.executable,
            "argv": list(self.argv),
            "remote": self.remote,
            "timeout_seconds": self.timeout_seconds,
            "environment_policy_id": self.environment_policy_id,
            "execution_policy_context": self.execution_policy_context,
            "attempts": [attempt.to_dict() for attempt in self.attempts],
        }


@dataclass(frozen=True)
class PublicationEvidence:
    requested: bool = False
    status: PublicationStatus = "not_requested"
    filename: str | None = None
    blocker: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "requested": self.requested,
            "status": self.status,
            "filename": self.filename,
            "blocker": self.blocker,
        }


@dataclass(frozen=True)
class RepositorySnapshot:
    normalized_origin: str | None
    branch: str | None
    local_head: str | None
    upstream: str | None
    effective_ref: str | None
    remote_head: str | None
    remote_head_disposition: RemoteHeadDisposition
    worktree_state: tuple[str, ...]
    source_manifest: SourceManifest
    snapshot_id: str

    def to_dict(self) -> dict[str, object]:
        return {
            "normalized_origin": self.normalized_origin,
            "branch": self.branch,
            "local_head": self.local_head,
            "upstream": self.upstream,
            "effective_ref": self.effective_ref,
            "remote_head": self.remote_head,
            "remote_head_disposition": self.remote_head_disposition,
            "worktree_state": list(self.worktree_state),
            "source_manifest": self.source_manifest.to_dict(),
            "snapshot_id": self.snapshot_id,
        }


@dataclass(frozen=True)
class FreshnessEvidence:
    observed_at: str | None = None
    snapshot_id: str | None = None
    final_guard_snapshot_id: str | None = None
    concurrent_change_check: ConcurrentChangeCheck = "not_applicable"
    remote_head_disposition: RemoteHeadDisposition = "not_applicable"

    def to_dict(self) -> dict[str, object]:
        return {
            "observed_at": self.observed_at,
            "snapshot_id": self.snapshot_id,
            "final_guard_snapshot_id": self.final_guard_snapshot_id,
            "concurrent_change_check": self.concurrent_change_check,
            "remote_head_disposition": self.remote_head_disposition,
        }


@dataclass(frozen=True)
class PreflightResult:
    status: PreflightStatus
    evidence_mode: EvidenceMode
    sync_state: SyncState
    github_sync: GitHubSync
    requested_ref: str | None
    effective_ref: str | None
    local_head: str | None
    remote_head: str | None
    source_manifest: SourceManifest
    source_hash_mismatch_checked: bool
    blockers: tuple[str, ...] = ()
    remediation: tuple[str, ...] = ()
    expected_source_hash: str | None = None
    current_source_hash: str | None = None
    provided_context_paths: tuple[str, ...] = ()
    diff_summary: str | None = None
    unsynced_reason: str | None = None
    authority: str = "evidence_only"
    adoption_requires: str = "explicit_eal_disposition"
    bundle_generation_not_promotion: bool = True
    fetch: FetchSummary = field(default_factory=lambda: FetchSummary(status="not_applicable"))
    freshness: FreshnessEvidence = field(default_factory=FreshnessEvidence)
    publication: PublicationEvidence = field(default_factory=PublicationEvidence)
    repository: RepositorySnapshot | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": 1,
            "receipt_kind": RECEIPT_KIND,
            "status": self.status,
            "evidence_mode": self.evidence_mode,
            "sync_state": self.sync_state,
            "authority": self.authority,
            "requested_ref": self.requested_ref,
            "effective_ref": self.effective_ref,
            "local_head": self.local_head,
            "remote_head": self.remote_head,
            "source_hash_mismatch_checked": self.source_hash_mismatch_checked,
            "github_sync": self.github_sync,
            "provided_context_paths": list(self.provided_context_paths),
            "diff_summary": self.diff_summary,
            "unsynced_reason": self.unsynced_reason,
            "blockers": list(self.blockers),
            "remediation": list(self.remediation),
            "adoption_requires": self.adoption_requires,
            "bundle_generation_not_promotion": self.bundle_generation_not_promotion,
            "expected_source_hash": self.expected_source_hash,
            "current_source_hash": self.current_source_hash,
            "fetch": self.fetch.to_dict(),
            "freshness": self.freshness.to_dict(),
            "publication": self.publication.to_dict(),
            "repository": None if self.repository is None else self.repository.to_dict(),
        }
        payload.update(self.source_manifest.to_dict())
        payload["receipt_digest"] = {
            "algorithm": "sha256",
            "value": receipt_digest_value(payload),
        }
        return payload


@dataclass(frozen=True)
class GitVisibleRef:
    state: Literal[
        "resolved",
        "branch_missing",
        "connector_unavailable",
        "default_branch_unknown",
        "origin_mismatch",
    ]
    requested_ref: str | None
    effective_ref: str | None
    remote_head: str | None
    blockers: tuple[str, ...] = field(default_factory=tuple)
    remediation: tuple[str, ...] = field(default_factory=tuple)
