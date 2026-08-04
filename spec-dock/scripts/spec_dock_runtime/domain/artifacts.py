from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import TYPE_CHECKING
import unicodedata

if TYPE_CHECKING:
    from pathlib import Path

DIRECT_ARTIFACT_TYPES = (
    "blank",
    "research",
    "interview",
    "disc",
    "decision-candidate",
    "pr-repair-batch",
    "adr",
)
ROUTING_ONLY_ARTIFACT_TYPES = ("draft-requirement", "draft-design", "draft-plan")
SUPPORTED_ARTIFACT_TYPES = (*DIRECT_ARTIFACT_TYPES, *ROUTING_ONLY_ARTIFACT_TYPES)
UNSUPPORTED_ARTIFACT_TYPES = ("scratch", "note")

_ARTIFACT_TIMESTAMP_INTENT_RE = re.compile(r"^[0-9]{8}[tT][0-9].*$")
_ARTIFACT_DOC_TYPE_PATTERN = "|".join(
    re.escape(doc_type) for doc_type in sorted(SUPPORTED_ARTIFACT_TYPES, key=len, reverse=True)
)
_TYPED_ARTIFACT_FILENAME_RE = re.compile(
    r"^(?P<ts>[0-9]{8}t[0-9]{6}z)(?:-(?P<nn>0[1-9]|[1-9][0-9]))?"
    rf"-(?P<artifact_type>{_ARTIFACT_DOC_TYPE_PATTERN})-"
    r"(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)\.md$"
)
_BLANK_ARTIFACT_FILENAME_RE = re.compile(
    r"^(?P<ts>[0-9]{8}t[0-9]{6}z)(?:-(?P<nn>0[1-9]|[1-9][0-9]))?"
    r"-(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)\.md$"
)
_GRANDFATHERED_LEGACY_ARTIFACT_FILENAME_RE = re.compile(r"^[0-9]{3}-(?:adr|disc|note)-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")


@dataclass(frozen=True)
class ArtifactFilename:
    timestamp: str
    suffix: int | None
    artifact_type: str
    slug: str
    artifact_id: str


@dataclass(frozen=True)
class GenericImportedArtifactFilename:
    timestamp: str
    suffix: int | None
    original_basename: str
    artifact_id: str


@dataclass(frozen=True)
class ArtifactSlot:
    timestamp: str
    suffix: int | None


@dataclass(frozen=True)
class ArtifactSlotLedger:
    used_slots: frozenset[ArtifactSlot]
    artifact_ids: frozenset[str]


_GENERIC_IMPORTED_ARTIFACT_FILENAME_RE = re.compile(
    r"^(?P<ts>[0-9]{8}t[0-9]{6}z)(?:-(?P<nn>0[1-9]|[1-9][0-9]))?--(?P<basename>.+)$"
)


def normalize_generic_artifact_basename(
    name: str,
    *,
    name_max_bytes: int,
    max_prefix_bytes: int,
) -> str:
    if name in ("", ".", ".."):
        raise RuntimeError("Invalid generic artifact basename")
    if name_max_bytes <= 0 or max_prefix_bytes < 0:
        raise RuntimeError("Invalid generic artifact component limit")
    budget = name_max_bytes - max_prefix_bytes
    if budget <= 0:
        raise RuntimeError("Generic artifact basename has no available byte budget")

    normalized = _replace_unsafe_basename_characters(name)
    if normalized in ("", ".", ".."):
        raise RuntimeError("Invalid generic artifact basename")
    try:
        normalized_bytes = normalized.encode("utf-8")
    except UnicodeEncodeError:
        raise RuntimeError("Invalid generic artifact basename") from None
    if len(normalized_bytes) <= budget:
        return normalized

    stem, extension_chain = _split_extension_chain(normalized)
    if extension_chain:
        extension_start = len(stem)
        while extension_start >= 0:
            retained_chain = normalized[extension_start:]
            stem_budget = budget - len(retained_chain.encode("utf-8"))
            shortened_stem = _utf8_prefix(stem, stem_budget)
            if shortened_stem:
                return shortened_stem + retained_chain
            extension_start = normalized.find(".", extension_start + 1)

    shortened = _utf8_prefix(normalized, budget)
    if shortened in ("", ".", ".."):
        raise RuntimeError("Generic artifact basename cannot fit component limit")
    return shortened


def format_generic_imported_artifact_filename(
    *,
    timestamp: str,
    original_basename: str,
    suffix: int | None = None,
    name_max_bytes: int,
) -> str:
    if suffix is not None and not 1 <= suffix <= 99:
        raise RuntimeError("Invalid generic artifact suffix")
    max_prefix_bytes = len(f"{timestamp}-99--".encode())
    normalized = normalize_generic_artifact_basename(
        original_basename,
        name_max_bytes=name_max_bytes,
        max_prefix_bytes=max_prefix_bytes,
    )
    prefix = timestamp if suffix is None else f"{timestamp}-{suffix:02d}"
    filename = f"{prefix}--{normalized}"
    if len(filename.encode("utf-8")) > name_max_bytes:
        raise RuntimeError("Generic artifact identity exceeds component limit")
    if parse_generic_imported_artifact_filename(filename) is None:
        raise RuntimeError("Invalid generic artifact identity")
    return filename


def parse_generic_imported_artifact_filename(name: str) -> GenericImportedArtifactFilename | None:
    if name == "rules.md":
        return None
    matched = _GENERIC_IMPORTED_ARTIFACT_FILENAME_RE.fullmatch(name)
    if matched is None:
        return None
    original_basename = str(matched.group("basename"))
    if original_basename in ("", ".", ".."):
        return None
    try:
        normalized = _replace_unsafe_basename_characters(original_basename)
    except RuntimeError:
        return None
    if normalized != original_basename:
        return None
    timestamp = str(matched.group("ts"))
    suffix_raw = matched.group("nn")
    suffix = int(suffix_raw) if suffix_raw is not None else None
    return GenericImportedArtifactFilename(
        timestamp=timestamp,
        suffix=suffix,
        original_basename=original_basename,
        artifact_id=name,
    )


def _replace_unsafe_basename_characters(name: str) -> str:
    separators = {separator for separator in (os.sep, os.altsep) if separator}
    windows_invalid = set('<>:"/\\|?*') if os.name == "nt" else set()
    replaced = "".join(
        "_"
        if (
            character == "\x00"
            or character in separators
            or character in windows_invalid
            or unicodedata.category(character) in ("Cc", "Cf")
        )
        else character
        for character in name
    )
    if os.name == "nt":
        stem = replaced.split(".", 1)[0].rstrip(" ").upper()
        reserved = {"CON", "PRN", "AUX", "NUL", *{f"COM{i}" for i in range(1, 10)}, *{f"LPT{i}" for i in range(1, 10)}}
        if stem in reserved:
            replaced = f"_{replaced}"
    trailing_start = len(replaced.rstrip(". "))
    if trailing_start < len(replaced):
        replaced = replaced[:trailing_start] + "".join("_" for _ in replaced[trailing_start:])
    return replaced


def _split_extension_chain(name: str) -> tuple[str, str]:
    first_dot = name.find(".", 1)
    if first_dot < 0:
        return name, ""
    return name[:first_dot], name[first_dot:]


def _utf8_prefix(value: str, byte_budget: int) -> str:
    if byte_budget <= 0:
        return ""
    used = 0
    result: list[str] = []
    for character in value:
        size = len(character.encode("utf-8"))
        if used + size > byte_budget:
            break
        result.append(character)
        used += size
    return "".join(result)


def is_supported_artifact_type(artifact_type: str) -> bool:
    return artifact_type in SUPPORTED_ARTIFACT_TYPES


def is_direct_artifact_type(artifact_type: str) -> bool:
    return artifact_type in DIRECT_ARTIFACT_TYPES


def is_routing_only_artifact_type(artifact_type: str) -> bool:
    return artifact_type in ROUTING_ONLY_ARTIFACT_TYPES


def is_ambiguous_blank_artifact_slug(slug: str) -> bool:
    return any(
        slug == artifact_type or slug.startswith(f"{artifact_type}-") for artifact_type in SUPPORTED_ARTIFACT_TYPES
    )


def is_grandfathered_legacy_artifact_filename(name: str) -> bool:
    return _GRANDFATHERED_LEGACY_ARTIFACT_FILENAME_RE.fullmatch(name) is not None


def parse_artifact_filename(name: str) -> ArtifactFilename | None:
    if name == "rules.md":
        return None
    matched = _TYPED_ARTIFACT_FILENAME_RE.fullmatch(name)
    if matched is not None:
        timestamp = str(matched.group("ts"))
        suffix_raw = matched.group("nn")
        suffix = int(suffix_raw) if suffix_raw is not None else None
        artifact_type = str(matched.group("artifact_type"))
        slug = str(matched.group("slug"))
        if artifact_type == "blank":
            return None
        artifact_id = f"{timestamp}-{artifact_type}" if suffix is None else f"{timestamp}-{suffix:02d}-{artifact_type}"
        return ArtifactFilename(
            timestamp=timestamp,
            suffix=suffix,
            artifact_type=artifact_type,
            slug=slug,
            artifact_id=artifact_id,
        )
    matched = _BLANK_ARTIFACT_FILENAME_RE.fullmatch(name)
    if matched is None:
        return None
    timestamp = str(matched.group("ts"))
    suffix_raw = matched.group("nn")
    suffix = int(suffix_raw) if suffix_raw is not None else None
    slug = str(matched.group("slug"))
    parts = slug.split("-")
    if re.fullmatch(r"[0-9]{2}", parts[0]) is not None:
        return None
    for end in range(len(parts), 0, -1):
        if "-".join(parts[:end]) in SUPPORTED_ARTIFACT_TYPES:
            return None
    artifact_id = timestamp if suffix is None else f"{timestamp}-{suffix:02d}"
    return ArtifactFilename(
        timestamp=timestamp,
        suffix=suffix,
        artifact_type="blank",
        slug=slug,
        artifact_id=artifact_id,
    )


def artifact_id_from_path(path: Path) -> str:
    parsed = parse_artifact_filename(path.name)
    if parsed is None:
        raise RuntimeError(f"Invalid artifact filename: {path.name}")
    return parsed.artifact_id


def is_malformed_artifact_candidate(path: Path) -> bool:
    if path.name == "rules.md":
        return False
    if path.suffix != ".md":
        return False
    if is_grandfathered_legacy_artifact_filename(path.name):
        return False
    if parse_generic_imported_artifact_filename(path.name) is not None:
        return False
    if parse_artifact_filename(path.name) is not None:
        return False
    stem = path.stem
    lowered = stem.lower()
    parts = lowered.split("-")
    if _ARTIFACT_TIMESTAMP_INTENT_RE.fullmatch(stem) is not None:
        return True
    for artifact_type in (*SUPPORTED_ARTIFACT_TYPES, *UNSUPPORTED_ARTIFACT_TYPES):
        if (
            lowered == artifact_type
            or lowered.startswith(f"{artifact_type}-")
            or lowered.startswith(f"{artifact_type}_")
        ):
            return True
        for start in (1, 2):
            if len(parts) <= start:
                continue
            for end in range(len(parts), start, -1):
                if "-".join(parts[start:end]) == artifact_type:
                    return True
    return False


def scan_artifact_duplicate_state(artifacts_dir: Path) -> tuple[str | None, set[str]]:
    error, ledger = scan_artifact_slot_ledger(artifacts_dir)
    return error, set(ledger.artifact_ids)


def scan_artifact_slot_ledger(artifacts_dir: Path) -> tuple[str | None, ArtifactSlotLedger]:
    empty = ArtifactSlotLedger(used_slots=frozenset(), artifact_ids=frozenset())
    if artifacts_dir.is_symlink():
        return f"Unsafe artifact directory under {artifacts_dir}: artifacts directory must not be a symlink", empty
    if os.path.lexists(artifacts_dir) and not artifacts_dir.is_dir():
        return f"Unsafe artifact directory under {artifacts_dir}: artifacts path is not a directory", empty
    slots: dict[ArtifactSlot, list[str]] = {}
    artifact_ids: set[str] = set()
    if artifacts_dir.exists():
        with os.scandir(artifacts_dir) as entries:
            direct_entries = sorted(entries, key=lambda entry: entry.name)
        for entry in direct_entries:
            if entry.name == "rules.md":
                continue
            typed = parse_artifact_filename(entry.name)
            generic = parse_generic_imported_artifact_filename(entry.name)
            parsed = typed if typed is not None else generic
            if parsed is not None:
                if not entry.is_file(follow_symlinks=False):
                    return f"Unsafe artifact file under {artifacts_dir}: {entry.name} is not a regular file", empty
                artifact_id = parsed.artifact_id
                if artifact_id in artifact_ids:
                    return f"Duplicate artifact id detected under {artifacts_dir}: id={artifact_id}", empty
                artifact_ids.add(artifact_id)
                slots.setdefault(ArtifactSlot(parsed.timestamp, parsed.suffix), []).append(artifact_id)
                continue
            path = artifacts_dir / entry.name
            if is_malformed_artifact_candidate(path):
                return f"Malformed artifact filename under {artifacts_dir}: {entry.name}", empty
    for slot, ids in sorted(slots.items(), key=lambda item: (item[0].timestamp, item[0].suffix or 0)):
        if len(ids) > 1:
            slot_display = slot.timestamp if slot.suffix is None else f"{slot.timestamp}-{slot.suffix:02d}"
            label = "timestamp slot" if slot.suffix is None else "timestamp suffix"
            return f"Duplicate artifact {label} detected under {artifacts_dir}: slot={slot_display}", empty
    return None, ArtifactSlotLedger(
        used_slots=frozenset(slots),
        artifact_ids=frozenset(artifact_ids),
    )


def allocate_artifact_filename_for_timestamp(
    artifacts_dir: Path,
    *,
    timestamp: str,
    artifact_type: str,
    slug: str,
) -> tuple[Path, str]:
    duplicate_error, ledger = scan_artifact_slot_ledger(artifacts_dir)
    if duplicate_error is not None:
        raise RuntimeError(duplicate_error)
    if ArtifactSlot(timestamp, None) not in ledger.used_slots:
        return _format_artifact_identity(
            artifacts_dir, timestamp=timestamp, suffix=None, artifact_type=artifact_type, slug=slug
        )
    for suffix in range(1, 100):
        if ArtifactSlot(timestamp, suffix) not in ledger.used_slots:
            return _format_artifact_identity(
                artifacts_dir,
                timestamp=timestamp,
                suffix=suffix,
                artifact_type=artifact_type,
                slug=slug,
            )
    raise RuntimeError(
        "Artifact timestamp suffix exhaustion: "
        f"timestamp={timestamp} under {artifacts_dir}. "
        "Suffix allocation is limited to 01..99 across all artifact families."
    )


def allocate_generic_imported_artifact_filename_for_timestamp(
    artifacts_dir: Path,
    *,
    timestamp: str,
    original_basename: str,
    name_max_bytes: int,
) -> tuple[Path, str]:
    duplicate_error, ledger = scan_artifact_slot_ledger(artifacts_dir)
    if duplicate_error is not None:
        raise RuntimeError(duplicate_error)
    suffix: int | None
    if ArtifactSlot(timestamp, None) not in ledger.used_slots:
        suffix = None
    else:
        suffix = next(
            (candidate for candidate in range(1, 100) if ArtifactSlot(timestamp, candidate) not in ledger.used_slots),
            None,
        )
        if suffix is None:
            raise RuntimeError(
                "Artifact timestamp suffix exhaustion: "
                f"timestamp={timestamp} under {artifacts_dir}. "
                "Suffix allocation is limited to 01..99 across all artifact families."
            )
    filename = format_generic_imported_artifact_filename(
        timestamp=timestamp,
        original_basename=original_basename,
        suffix=suffix,
        name_max_bytes=name_max_bytes,
    )
    return artifacts_dir / filename, filename


def _format_artifact_identity(
    artifacts_dir: Path,
    *,
    timestamp: str,
    suffix: int | None,
    artifact_type: str,
    slug: str,
) -> tuple[Path, str]:
    if artifact_type == "blank":
        stem_prefix = timestamp if suffix is None else f"{timestamp}-{suffix:02d}"
    else:
        stem_prefix = f"{timestamp}-{artifact_type}" if suffix is None else f"{timestamp}-{suffix:02d}-{artifact_type}"
    return artifacts_dir / f"{stem_prefix}-{slug}.md", stem_prefix
