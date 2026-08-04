from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pathlib import Path

PackPrepareStatus = Literal["pass", "fail", "blocked", "stale", "rejected"]
PackMode = Literal["initiative", "epic", "issue", "selected-skeleton"]

AUTHORITY = "evidence_only"
ADOPTION_STATUS = "unreviewed"
BUNDLE_GENERATION_NOT_PROMOTION = True
EXPECTED_OUTPUT_ROOT = "specdock-authoring-pack/"

PROMPT_PACK_FILES: tuple[str, ...] = (
    ".specdock-authoring-pack",
    "manifest.json",
    "provenance.json",
    "source-manifest.json",
    "stale-if.json",
    "safe-output-constraints.md",
    "chatgpt-use-prompt.md",
    "expected-output-contract.md",
)

REQUIRED_METADATA: tuple[str, ...] = (
    "manifest.json",
    "provenance.json",
    "source-manifest.json",
    "stale-if.json",
    "safe-output-constraints.md",
    "adoption/adoption-map.json",
    "adoption/eal-candidates.json",
)

FORBIDDEN_AUTHORITY_CLAIMS: tuple[str, ...] = (
    "canonical adoption",
    ".assurance.json mutation",
    "authorized_profile decision",
    "reviewer pass",
    "execution-ready",
    "PR-ready",
    "PR delivery",
)

FORBIDDEN_PAYLOADS: tuple[str, ...] = (
    "raw transcript",
    "secret",
    "credential",
    "private key",
    "host-local absolute path",
    "path traversal",
    "hidden path",
    "nested archive",
    "binary",
    "executable",
    "symlink",
)

FORBIDDEN_ACHIEVED_CLAIM_KEYS: tuple[str, ...] = (
    "canonical_adoption",
    "assurance_mutation",
    "authorized_profile",
    "reviewer_pass",
    "execution_ready",
    "pr_ready",
    "pr_delivery",
)


@dataclass(frozen=True)
class PromptPackPrepareRequest:
    preflight_path: Path
    output_dir: Path
    output_format: Literal["text", "json"] = "text"
    mode: PackMode | None = None
    source_manifest_path: Path | None = None
    stale_if_path: Path | None = None


@dataclass(frozen=True)
class PromptPackPrepareResult:
    status: PackPrepareStatus
    authority: str
    adoption_status: str
    bundle_generation_not_promotion: bool
    evidence_mode: str | None
    sync_state: str | None
    github_sync: str | None
    output_dir: str
    output_root: str
    output_files: tuple[str, ...]
    source_manifest_hash: str | None
    blockers: tuple[str, ...]
    remediation: tuple[str, ...]
    mode: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "authority": self.authority,
            "adoption_status": self.adoption_status,
            "bundle_generation_not_promotion": self.bundle_generation_not_promotion,
            "evidence_mode": self.evidence_mode,
            "sync_state": self.sync_state,
            "github_sync": self.github_sync,
            "mode": self.mode,
            "output_dir": self.output_dir,
            "output_root": self.output_root,
            "output_files": list(self.output_files),
            "source_manifest_hash": self.source_manifest_hash,
            "blockers": list(self.blockers),
            "remediation": list(self.remediation),
        }


def authority_boundary() -> dict[str, object]:
    return {
        "authority": AUTHORITY,
        "adoption_status": ADOPTION_STATUS,
        "bundle_generation_not_promotion": BUNDLE_GENERATION_NOT_PROMOTION,
    }


def safe_output_constraints() -> dict[str, object]:
    return {
        "expected_zip_root": EXPECTED_OUTPUT_ROOT,
        "required_metadata": list(REQUIRED_METADATA),
        "authority": AUTHORITY,
        "adoption_status": ADOPTION_STATUS,
        "bundle_generation_not_promotion": BUNDLE_GENERATION_NOT_PROMOTION,
        "forbidden_authority_claims": list(FORBIDDEN_AUTHORITY_CLAIMS),
        "forbidden_payloads": list(FORBIDDEN_PAYLOADS),
    }
