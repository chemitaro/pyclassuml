from __future__ import annotations

from dataclasses import dataclass
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

DRAFT_DISCUSSION_DOC_TYPES = ("draft-requirement", "draft-design", "draft-plan")
CREATABLE_DISCUSSION_DOC_TYPES = (
    "adr",
    "disc",
    "research",
    "interview",
    "scratch",
    "pr-repair-batch",
    *DRAFT_DISCUSSION_DOC_TYPES,
)
RETIRED_DISCUSSION_DOC_TYPES = ("note",)
TIMESTAMP_DISCUSSION_DOC_TYPES = (*CREATABLE_DISCUSSION_DOC_TYPES, *RETIRED_DISCUSSION_DOC_TYPES)
LEGACY_DISCUSSION_DOC_TYPES = ("adr", "disc", "research", "note")

_DISCUSSION_DOC_TIMESTAMP_INTENT_TOKEN_RE = re.compile(
    r"^(?:[0-9]{8}|[0-9]{14}[a-zA-Z]?|[0-9]{8}[a-zA-Z][0-9]{5,7}[a-zA-Z]?|[0-9]{8}[tT][0-9]+[a-zA-Z]*)$"
)
_DISCUSSION_DOC_TIMESTAMP_INTENT_PREFIX_RE = re.compile(r"^[0-9]{8}[tT][0-9].*$")
_DISCUSSION_DOC_LEGACY_SEQUENCE_INTENT_PREFIX_RE = re.compile(r"^[0-9]{3}_.*$")


@dataclass(frozen=True)
class TimestampDiscussionDocFilename:
    timestamp: str
    suffix: int | None
    doc_type: str
    slug: str
    doc_id: str


@dataclass(frozen=True)
class LegacyDiscussionDocFilename:
    sequence: str
    doc_type: str
    slug: str


def _doc_type_pattern(doc_types: tuple[str, ...]) -> str:
    return "|".join(re.escape(doc_type) for doc_type in sorted(doc_types, key=len, reverse=True))


DISCUSSION_DOC_TIMESTAMP_FILENAME_RE = re.compile(
    r"^(?P<ts>[0-9]{8}t[0-9]{6}z)(?:-(?P<nn>0[1-9]|[1-9][0-9]))?"
    rf"-(?P<doc_type>{_doc_type_pattern(TIMESTAMP_DISCUSSION_DOC_TYPES)})-"
    r"(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)\.md$"
)
DISCUSSION_DOC_LEGACY_FILENAME_RE = re.compile(
    rf"^(?P<seq>[0-9]{{3}})-(?P<doc_type>{_doc_type_pattern(LEGACY_DISCUSSION_DOC_TYPES)})-"
    r"(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)\.md$"
)


def is_creatable_discussion_doc_type(doc_type: str) -> bool:
    return doc_type in CREATABLE_DISCUSSION_DOC_TYPES


def is_retired_discussion_doc_type(doc_type: str) -> bool:
    return doc_type in RETIRED_DISCUSSION_DOC_TYPES


def parse_timestamp_discussion_doc_filename(name: str) -> TimestampDiscussionDocFilename | None:
    matched = DISCUSSION_DOC_TIMESTAMP_FILENAME_RE.fullmatch(name)
    if matched is None:
        return None
    timestamp = str(matched.group("ts"))
    suffix_raw = matched.group("nn")
    suffix = int(suffix_raw) if suffix_raw is not None else None
    doc_type = str(matched.group("doc_type"))
    slug = str(matched.group("slug"))
    doc_id = f"{timestamp}-{doc_type}" if suffix is None else f"{timestamp}-{suffix:02d}-{doc_type}"
    return TimestampDiscussionDocFilename(
        timestamp=timestamp,
        suffix=suffix,
        doc_type=doc_type,
        slug=slug,
        doc_id=doc_id,
    )


def parse_legacy_discussion_doc_filename(name: str) -> LegacyDiscussionDocFilename | None:
    matched = DISCUSSION_DOC_LEGACY_FILENAME_RE.fullmatch(name)
    if matched is None:
        return None
    return LegacyDiscussionDocFilename(
        sequence=str(matched.group("seq")),
        doc_type=str(matched.group("doc_type")),
        slug=str(matched.group("slug")),
    )


def discussion_doc_id_from_path(path: Path) -> str:
    parsed = parse_timestamp_discussion_doc_filename(path.name)
    if parsed is None:
        raise RuntimeError(f"Invalid discussion document filename: {path.name}")
    return parsed.doc_id


def discussion_filename_expectation() -> str:
    return "Expected `<ts>-<kind>-<slug>.md`, `<ts>-<nn>-<kind>-<slug>.md`, or grandfathered `<nnn>-<kind>-<slug>.md`."


def _is_discussion_doc_type_candidate(token: str) -> bool:
    return bool(token) and token.lower() in TIMESTAMP_DISCUSSION_DOC_TYPES


def _find_discussion_doc_type_slot(parts: list[str]) -> int | None:
    for start in (1, 2):
        if len(parts) <= start:
            continue
        for end in range(len(parts), start, -1):
            candidate = "-".join(parts[start:end]).lower()
            if _is_discussion_doc_type_candidate(candidate):
                return start
    return None


def is_malformed_discussion_doc_candidate(path: Path) -> bool:
    stem = path.stem
    parts = stem.split("-")
    if not parts:
        return False
    first = parts[0]
    doc_type_slot = _find_discussion_doc_type_slot(parts)
    lowered = stem.lower()
    if _is_discussion_doc_type_candidate(lowered):
        return True
    if _is_discussion_doc_type_candidate(first):
        return True
    if doc_type_slot is not None and not first.isdigit():
        return True
    if re.fullmatch(r"[0-9]{3}", first) is not None:
        return True
    if _DISCUSSION_DOC_LEGACY_SEQUENCE_INTENT_PREFIX_RE.fullmatch(stem) is not None:
        return True
    for doc_type in TIMESTAMP_DISCUSSION_DOC_TYPES:
        if lowered.startswith(f"{doc_type}-") or lowered.startswith(f"{doc_type}_"):
            return True
    if _DISCUSSION_DOC_TIMESTAMP_INTENT_TOKEN_RE.fullmatch(first) is not None:
        return True
    return _DISCUSSION_DOC_TIMESTAMP_INTENT_PREFIX_RE.fullmatch(stem) is not None
