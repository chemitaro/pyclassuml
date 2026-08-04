from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Literal

PRIMARY_BACKEND_ENV = "SPECDOCK_CHATGPT_COMMAND"
FALLBACK_BACKEND_ENV = "ORACLE_CHATGPT_COMMAND"

BackendInvokeStatus = Literal["pass", "blocked", "rejected"]
BackendCommandSource = Literal["cli", "env:SPECDOCK_CHATGPT_COMMAND", "env:ORACLE_CHATGPT_COMMAND", "unset"]
EvidenceMode = Literal["github-synced", "local-context"]

DEFAULT_BACKEND_PROMPT = "Use the attached prompt pack files as the task brief. Produce the requested authoring output."

BACKEND_PROMPT_PACK_FILES: tuple[str, ...] = (
    "chatgpt-use-prompt.md",
    "expected-output-contract.md",
    "manifest.json",
    "provenance.json",
    "source-manifest.json",
    "stale-if.json",
    "safe-output-constraints.md",
)

REQUIRED_PROMPT_PACK_FILES: tuple[str, ...] = (
    ".specdock-authoring-pack",
    "manifest.json",
    "provenance.json",
    "source-manifest.json",
    "stale-if.json",
    "safe-output-constraints.md",
    "chatgpt-use-prompt.md",
    "expected-output-contract.md",
)

REQUIRED_MANIFEST_FIELDS: tuple[str, ...] = (
    "schema_version",
    "generated_by",
    "expected_output_root",
    "required_metadata",
    "files",
    "authority",
    "adoption_status",
    "bundle_generation_not_promotion",
)

REQUIRED_PROVENANCE_FIELDS: tuple[str, ...] = (
    "evidence_mode",
    "sync_state",
    "github_sync",
    "source_manifest_hash",
    "authority",
    "adoption_status",
    "bundle_generation_not_promotion",
)

REQUIRED_SOURCE_MANIFEST_FIELDS: tuple[str, ...] = (
    "source_paths",
    "source_hashes",
    "source_manifest_hash",
)


@dataclass(frozen=True)
class BackendCommandResolution:
    status: BackendInvokeStatus
    source: BackendCommandSource
    argv: tuple[str, ...]
    compatibility_fallback: bool
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class PromptPackValidation:
    status: BackendInvokeStatus
    prompt_pack: Path
    blockers: tuple[str, ...]
    evidence_mode: str | None
    source_manifest_hash: str | None
    github_sync: str | None
    sync_state: str | None


@dataclass(frozen=True)
class BackendInvokeRequest:
    prompt_pack: Path
    output_dir: Path
    output_format: Literal["text", "json"] = "text"
    backend_command: str | None = None
    slug: str | None = None
    prompt: str | None = None
    evidence_mode: EvidenceMode = "github-synced"
    timeout_seconds: float | None = None
    dry_run: bool = False
    working_dir: Path | None = None


@dataclass(frozen=True)
class BackendStreamCapture:
    stdout: bytes = field(default=b"", repr=False)
    stderr: bytes = field(default=b"", repr=False)


@dataclass(frozen=True)
class BackendInvokeResult:
    status: BackendInvokeStatus
    authority: str
    adoption_status: str
    bundle_generation_not_promotion: bool
    evidence_mode: str | None
    sync_state: str | None
    github_sync: str | None
    backend_source: str
    compatibility_fallback: bool
    prompt_pack: str
    output_dir: str
    summary_path: str | None
    slug: str | None
    dry_run: bool
    backend_argv: tuple[str, ...]
    invocation_argv: tuple[str, ...]
    exit_code: int | None
    stdout: str
    stderr: str
    stdout_bytes: int
    stderr_bytes: int
    stream_output_disposition: str
    source_manifest_hash: str | None
    blockers: tuple[str, ...]
    remediation: tuple[str, ...]
    local_context_requires_eal_disposition: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "authority": self.authority,
            "adoption_status": self.adoption_status,
            "bundle_generation_not_promotion": self.bundle_generation_not_promotion,
            "evidence_mode": self.evidence_mode,
            "sync_state": self.sync_state,
            "github_sync": self.github_sync,
            "backend_source": self.backend_source,
            "compatibility_fallback": self.compatibility_fallback,
            "prompt_pack": _redact_summary_value(self.prompt_pack),
            "output_dir": _redact_summary_value(self.output_dir),
            "summary_path": _redact_summary_value(self.summary_path) if self.summary_path is not None else None,
            "slug": self.slug,
            "dry_run": self.dry_run,
            "backend_argv": _redact_argv_values(self.backend_argv),
            "invocation_argv": _redact_argv_values(self.invocation_argv),
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "stdout_bytes": self.stdout_bytes,
            "stderr_bytes": self.stderr_bytes,
            "stream_output_disposition": self.stream_output_disposition,
            "source_manifest_hash": self.source_manifest_hash,
            "blockers": [_redact_summary_value(value) for value in self.blockers],
            "remediation": [_redact_summary_value(value) for value in self.remediation],
            "local_context_requires_eal_disposition": self.local_context_requires_eal_disposition,
        }


def _redact_summary_value(value: str) -> str:
    lowered = value.lower()
    if _looks_like_secret(value) or _looks_like_host_path(value):
        return "[redacted]"
    if re.search(r"\b[a-z0-9_-]*(api[_-]?key|password|token|secret|credential|key)[a-z0-9_-]*=", lowered):
        return "[redacted]"
    return value


def _redact_argv_values(values: tuple[str, ...]) -> list[str]:
    redacted: list[str] = []
    previous_was_secret_option = False
    for value in values:
        if previous_was_secret_option:
            redacted.append("[redacted]")
            previous_was_secret_option = False
            continue
        redacted_value = _redact_summary_value(value)
        redacted.append(redacted_value)
        previous_was_secret_option = _is_secret_option_name(value)
    return redacted


def _is_secret_option_name(value: str) -> bool:
    stripped = value.lstrip("-").lower()
    return bool(stripped and re.search(r"^(api[_-]?key|password|token|secret|credential|key)$", stripped))


def _looks_like_secret(value: str) -> bool:
    lowered = value.lower()
    return (
        value.startswith("sk-")
        or re.search(r"gh[pousr]_[a-z0-9_]{8,}", lowered) is not None
        or re.search(r"xox[baprs]-[a-z0-9-]{8,}", lowered) is not None
        or re.search(r"akia[0-9a-z]{16}", lowered) is not None
        or lowered.startswith((
            "token=",
            "--token",
            "secret=",
            "--secret",
            "credential=",
            "--credential",
            "password=",
            "--password",
            "key=",
            "--key",
        ))
        or re.search(r"\b[a-z0-9_-]*(api[_-]?key|password|token|secret|credential|key)[a-z0-9_-]*=", lowered)
        is not None
    )


def _looks_like_host_path(value: str) -> bool:
    if Path(value).is_absolute():
        return True
    return re.search(r"(^|[=\s'\"])(/Users/|/private/|/var/folders(?:/|$)|/tmp(?:/|$))[^\s'\"]*", value) is not None
