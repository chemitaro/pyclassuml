from __future__ import annotations

import re

from spec_dock_runtime.domain.authoring_pack.prompt_pack_contract import (
    FORBIDDEN_AUTHORITY_CLAIMS as PROMPT_PACK_FORBIDDEN_AUTHORITY_CLAIMS,
)

LOCAL_FORBIDDEN_AUTHORITY_CLAIMS: tuple[str, ...] = (
    "canonical adoption",
    ".assurance.json mutation",
    "authorized_profile",
    "reviewer pass",
    "spec-review pass",
    "qa-review pass",
    "code-review pass",
    "execution-ready",
    "pr-ready",
    "mergeable pr",
)

FORBIDDEN_AUTHORITY_CLAIMS: tuple[str, ...] = tuple(
    dict.fromkeys((
        *(claim.lower() for claim in PROMPT_PACK_FORBIDDEN_AUTHORITY_CLAIMS),
        *LOCAL_FORBIDDEN_AUTHORITY_CLAIMS,
    ))
)

SECRET_MARKERS: tuple[str, ...] = (
    "private key",
    "api_key",
    "api key",
    "password=",
    "token=",
    "secret=",
    "credential",
)

RAW_TRANSCRIPT_MARKERS: tuple[str, ...] = (
    "raw transcript",
    "chatgpt transcript",
    "browser transcript",
)

CREDENTIAL_PATH_PARTS: tuple[str, ...] = (
    "secret",
    "secrets",
    "token",
    "tokens",
    "credential",
    "credentials",
    "password",
    "passwords",
)
PRIVATE_KEY_NAMES: tuple[str, ...] = (
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
)

_KNOWN_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}|AKIA[0-9A-Z]{16,})(?![A-Za-z0-9])",
)


def scan_authoring_payload(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    findings: list[str] = []
    for marker in FORBIDDEN_AUTHORITY_CLAIMS:
        if marker in lowered:
            findings.append(f"forbidden_authority_claim:{marker}")
    findings.extend(scan_sensitive_payload(text))
    return tuple(dict.fromkeys(findings))


def scan_sensitive_payload(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    findings: list[str] = []
    for marker in SECRET_MARKERS:
        if marker in lowered:
            findings.append(f"secret_like_payload:{marker.strip('=')}")
    findings.extend(_scan_structured_secret_fields(lowered))
    for marker in RAW_TRANSCRIPT_MARKERS:
        if marker in lowered:
            findings.append(f"raw_transcript:{marker}")
    return tuple(dict.fromkeys(findings))


def scan_constraint_sensitive_payload(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    findings: list[str] = []
    if "private key" in lowered and ("-----begin" in lowered or "block" in lowered):
        findings.append("secret_like_payload:private key")
    findings.extend(_scan_structured_secret_fields(lowered, require_secret_like_value=True))
    findings.extend(_raw_transcript_findings(text, lowered))
    return tuple(dict.fromkeys(findings))


def scan_issue_candidate_sensitive_payload(text: str) -> tuple[str, ...]:
    findings = list(scan_constraint_sensitive_payload(text))
    private_path = private_absolute_path_finding(text)
    if private_path is not None:
        findings.append(private_path)
    if _KNOWN_TOKEN_RE.search(text) is not None:
        findings.append("secret_like_payload:token")
    return tuple(dict.fromkeys(findings))


def _raw_transcript_findings(text: str, lowered: str) -> tuple[str, ...]:
    present_markers = tuple(marker for marker in RAW_TRANSCRIPT_MARKERS if marker in lowered)
    if not present_markers:
        return ()

    colon_field = re.compile(
        r"^\s*(?:>\s*)*(?:[-*+]\s+)?(?:>\s*)*"
        r"(user|assistant|prompt|answer)\s*[:\uff1a]",
        re.IGNORECASE,
    )
    atx_heading = re.compile(
        r"^\s*#{1,6}\s+(user|assistant|prompt|answer)(?:\s+#+)?\s*$",
        re.IGNORECASE,
    )
    seen_user = False
    seen_prompt = False
    has_complete_pair = False
    for line in text.splitlines():
        match = colon_field.match(line) or atx_heading.match(line)
        if match is None:
            continue
        label = match.group(1).lower()
        if (label == "assistant" and seen_user) or (label == "answer" and seen_prompt):
            has_complete_pair = True
            break
        if label == "user":
            seen_user = True
        elif label == "prompt":
            seen_prompt = True
    if not has_complete_pair:
        return ()
    return tuple(f"raw_transcript:{marker}" for marker in present_markers)


def private_absolute_path_finding(text: str) -> str | None:
    if re.search(
        r"(^|[\s'\"=])(?:/Users/[^/\s]+/|/private/|/var/folders(?:/|$)|/tmp(?:/|$))",
        text,
    ):
        return "private_absolute_path"
    return None


def is_credential_like_path(value: str) -> bool:
    for raw_part in re.split(r"[\\/]", value.lower()):
        part = re.sub(r"^\d{3}-", "", raw_part)
        if not part:
            continue
        if part == ".env" or part.startswith(".env."):
            return True
        if part in CREDENTIAL_PATH_PARTS:
            return True
        if any(re.search(rf"(^|[-_.]){re.escape(name)}($|[-_.])", part) for name in PRIVATE_KEY_NAMES):
            return True
        if "private_key" in part or "private-key" in part:
            return True
        if "api_key" in part or "api-key" in part:
            return True
        if part.endswith((".pem", ".key")):
            return True
        if re.search(
            r"(^|[-_.])(secret|secrets|token|tokens|credential|credentials|password|passwords)($|[-_.])", part
        ):
            return True
    return False


def scan_forbidden_authority_flags(payload: object, forbidden_keys: tuple[str, ...]) -> tuple[str, ...]:
    findings: list[str] = []
    keys = frozenset(forbidden_keys)

    def visit(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in keys:
                    if child is True:
                        findings.append(f"forbidden_authority_claim:{key}")
                    elif child is not False and child is not None and not isinstance(child, (dict, list)):
                        findings.append(f"invalid_authority_flag_shape:{key}")
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(payload)
    return tuple(dict.fromkeys(findings))


def evidence_authority_boundary_findings(payload: dict[str, object], *, prefix: str) -> tuple[str, ...]:
    findings: list[str] = []
    if payload.get("authority") != "evidence_only":
        findings.append(f"{prefix}_authority_not_evidence_only")
    if payload.get("adoption_status") != "unreviewed":
        findings.append(f"{prefix}_adoption_status_not_unreviewed")
    if payload.get("bundle_generation_not_promotion") is not True:
        findings.append(f"{prefix}_bundle_generation_not_promotion_not_true")
    return tuple(findings)


def _scan_structured_secret_fields(text: str, *, require_secret_like_value: bool = False) -> tuple[str, ...]:
    if not any(keyword in text for keyword in ("api", "password", "token", "secret", "credential", "private")):
        return ()
    findings: list[str] = []
    for match in re.finditer(
        r'["\']?([a-z0-9_-]*(?:api[\s_-]?key|private[\s_-]?key|password|token|secret|credential)[a-z0-9_-]*)["\']?\s*[:=]\s*["\']?([^\s"\'{},\]]+)',
        text,
    ):
        marker = match.group(1)
        value = match.group(2)
        if require_secret_like_value and not _looks_like_secret_value(value):
            continue
        if "private" in marker:
            findings.append("secret_like_payload:private key")
        elif "token" in marker:
            findings.append("secret_like_payload:token")
        elif "secret" in marker:
            findings.append("secret_like_payload:secret")
        elif "credential" in marker:
            findings.append("secret_like_payload:credential")
        elif "password" in marker:
            findings.append("secret_like_payload:password")
        else:
            findings.append("secret_like_payload:api_key")
    return tuple(findings)


def _looks_like_secret_value(value: str) -> bool:
    lowered = value.lower()
    if len(value) >= 8:
        return True
    if any(char.isdigit() for char in value) and len(value) >= 5:
        return True
    return lowered.startswith(("sk-", "ghp_", "xoxb-", "akia"))
