from __future__ import annotations

from collections.abc import Callable
import hashlib
import re
import time

from spec_dock_runtime.domain.authoring_pack.preflight_contract import (
    DIAGNOSTIC_EXCERPT_MAX_BYTES,
    FETCH_BACKOFF_SECONDS,
    MAX_FETCH_ATTEMPTS,
    FetchAttempt,
    FetchClassification,
    FetchFailureClass,
    FetchSummary,
    GitProcessOutcome,
    SafeDiagnostic,
)
from spec_dock_runtime.infra.authoring_pack.git_fetch import GitFetchExecutionRequest

MAX_ATTEMPTS = MAX_FETCH_ATTEMPTS
BACKOFF_SECONDS = FETCH_BACKOFF_SECONDS

FetchExecutor = Callable[[GitFetchExecutionRequest], GitProcessOutcome]
Sleeper = Callable[[float], None]

_SIGNALS: tuple[tuple[FetchFailureClass, tuple[re.Pattern[str], ...]], ...] = (
    (
        "local_ref_lock_contention",
        (
            re.compile(r"cannot lock ref .*refs/.+\.lock", re.IGNORECASE),
            re.compile(r"cannot lock ref .*\.lock exists", re.IGNORECASE),
        ),
    ),
    (
        "host_identity_failure",
        (
            re.compile(r"host key verification failed", re.IGNORECASE),
            re.compile(r"ssl certificate problem", re.IGNORECASE),
            re.compile(r"certificate verify failed", re.IGNORECASE),
            re.compile(r"unable to get local issuer certificate", re.IGNORECASE),
            re.compile(r"server certificate verification failed", re.IGNORECASE),
        ),
    ),
    (
        "remote_access_denied_or_not_found",
        (
            re.compile(r"repository not found", re.IGNORECASE),
            re.compile(r"permission denied \(publickey\)", re.IGNORECASE),
            re.compile(r"authentication failed", re.IGNORECASE),
            re.compile(r"could not read username", re.IGNORECASE),
        ),
    ),
    (
        "repository_configuration",
        (
            re.compile(r"does not appear to be a git repository", re.IGNORECASE),
            re.compile(r"no such remote", re.IGNORECASE),
            re.compile(r"couldn't find remote ref", re.IGNORECASE),
        ),
    ),
    (
        "execution_or_filesystem_denied",
        (
            re.compile(r"operation not permitted", re.IGNORECASE),
            re.compile(r"read-only file system", re.IGNORECASE),
            re.compile(r"permission denied(?! \(publickey\))", re.IGNORECASE),
        ),
    ),
    (
        "remote_throttled",
        (
            re.compile(r"(?:http\s*)?429\b", re.IGNORECASE),
            re.compile(r"too many requests", re.IGNORECASE),
            re.compile(r"rate limit(?:ed| exceeded)?", re.IGNORECASE),
        ),
    ),
    (
        "transient_transport",
        (
            re.compile(r"\bhttp(?:/[0-9.]+)?\s+5\d\d\b", re.IGNORECASE),
            re.compile(r"connection (?:reset|timed out|refused)", re.IGNORECASE),
            re.compile(r"could not resolve host", re.IGNORECASE),
            re.compile(r"network is unreachable", re.IGNORECASE),
            re.compile(r"remote end hung up unexpectedly", re.IGNORECASE),
            re.compile(r"early eof", re.IGNORECASE),
        ),
    ),
)

_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"-----BEGIN (?:OPENSSH |ENCRYPTED |RSA |DSA |EC )?PRIVATE KEY-----.*?"
            r"(?:-----END (?:OPENSSH |ENCRYPTED |RSA |DSA |EC )?PRIVATE KEY-----|\Z)",
            re.IGNORECASE | re.DOTALL,
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
    (re.compile(r"(?i)(https?://)[^\s/@:]+:[^\s/@]+@"), r"\1[REDACTED]@"),
    (re.compile(r"(?i)(authorization\s*:\s*(?:bearer|basic)\s+)[^\s]+"), r"\1[REDACTED]"),
    (
        re.compile(
            r"(?i)(?<![A-Za-z0-9_])"
            r"((?:access_token|oauth_token|id_token|refresh_token|auth_token|api_token|private_token|"
            r"api_key|api-key|apikey|client_secret|secret_key|aws_secret_access_key|credential|credentials|"
            r"token|password|passwd|secret)\s*[:=]\s*)"
            r"[^\s&#]+"
        ),
        r"\1[REDACTED]",
    ),
    (re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"), "[REDACTED_TOKEN]"),
    (re.compile(r"/(?:Users|home|private/tmp|tmp|var/folders)/[^\s]*(?:/[^\s]*)?"), "[REDACTED_PATH]"),
)


def classify_fetch_outcome(outcome: GitProcessOutcome) -> FetchClassification:
    if outcome.termination == "cancelled":
        return FetchClassification("cancelled", "certain", False, "cancelled")
    if outcome.termination == "timeout":
        return FetchClassification("timeout", "certain", True, "timeout")
    if outcome.termination == "spawn_error":
        return FetchClassification("spawn_failure", "certain", False, "spawn_failure")
    if outcome.return_code == 0:
        return FetchClassification(None, "certain", False, None)

    diagnostic_text = _diagnostic_bytes(outcome).decode("utf-8", errors="replace")
    matches = [
        failure_class for failure_class, patterns in _SIGNALS if any(p.search(diagnostic_text) for p in patterns)
    ]
    if len(matches) != 1:
        return FetchClassification("unknown", "unknown", False, "unknown")
    failure_class = matches[0]
    retryable = failure_class in {
        "transient_transport",
        "remote_throttled",
        "local_ref_lock_contention",
    }
    return FetchClassification(failure_class, "probable", retryable, failure_class)


def safe_diagnostic(raw: bytes, *, code: str | None) -> SafeDiagnostic:
    if not raw:
        return SafeDiagnostic(code=code)
    decoded = raw.decode("utf-8", errors="replace")
    redacted = decoded
    for pattern, replacement in _REDACTIONS:
        redacted = pattern.sub(replacement, redacted)
    redacted_bytes = redacted.encode("utf-8")
    excerpt_bytes = _bounded_utf8_prefix(redacted_bytes, DIAGNOSTIC_EXCERPT_MAX_BYTES)
    return SafeDiagnostic(
        code=code,
        excerpt=excerpt_bytes.decode("utf-8"),
        redacted_sha256=hashlib.sha256(redacted_bytes).hexdigest(),
        source_byte_count=len(raw),
        excerpt_byte_count=len(excerpt_bytes),
        truncated=len(excerpt_bytes) < len(redacted_bytes),
        redaction_applied=redacted != decoded or "\ufffd" in decoded,
    )


def run_origin_fetch_policy(
    request: GitFetchExecutionRequest,
    *,
    executor: FetchExecutor,
    sleeper: Sleeper = time.sleep,
) -> FetchSummary:
    attempts: list[FetchAttempt] = []
    final_status = "failed"
    for attempt_number in range(1, MAX_ATTEMPTS + 1):
        outcome = executor(request)
        classification = classify_fetch_outcome(outcome)
        attempts.append(_fetch_attempt(outcome, classification, attempt_number))
        if classification.failure_class is None:
            final_status = "success"
            break
        if classification.failure_class == "cancelled":
            final_status = "cancelled"
            break
        if not classification.retryable or attempt_number == MAX_ATTEMPTS:
            break
        sleeper(BACKOFF_SECONDS)
    return FetchSummary(status=final_status, attempts=tuple(attempts))


def summarize_fetch_outcome(outcome: GitProcessOutcome) -> FetchSummary:
    classification = classify_fetch_outcome(outcome)
    status = (
        "success"
        if classification.failure_class is None
        else "cancelled"
        if classification.failure_class == "cancelled"
        else "failed"
    )
    return FetchSummary(status=status, attempts=(_fetch_attempt(outcome, classification, 1),))


def _fetch_attempt(
    outcome: GitProcessOutcome,
    classification: FetchClassification,
    attempt_number: int,
) -> FetchAttempt:
    return FetchAttempt(
        attempt_number=attempt_number,
        duration_ms=outcome.duration_ms,
        return_code=outcome.return_code,
        termination=outcome.termination,
        failure_class=classification.failure_class,
        confidence=classification.confidence,
        retryable=classification.retryable,
        diagnostic=safe_diagnostic(_diagnostic_bytes(outcome), code=classification.diagnostic_code),
    )


def _diagnostic_bytes(outcome: GitProcessOutcome) -> bytes:
    if outcome.termination in {"timeout", "spawn_error", "cancelled"}:
        return b""
    return outcome.stderr or outcome.stdout


def _bounded_utf8_prefix(value: bytes, maximum: int) -> bytes:
    prefix = value[:maximum]
    while prefix:
        try:
            prefix.decode("utf-8")
            return prefix
        except UnicodeDecodeError as error:
            prefix = prefix[: error.start]
    return b""
