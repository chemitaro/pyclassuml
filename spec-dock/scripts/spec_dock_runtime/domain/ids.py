from __future__ import annotations

import re
from typing import Any
import unicodedata

DEFAULT_ID_WIDTH = 5

ID_RE = re.compile(r"^(?P<prefix>init|epic|iss|adr)(?:-(?P<local>local))?-(?P<num>[0-9]+)$")
NUM_RE = re.compile(r"^[0-9]+$")
INPUT_TITLE_RE = re.compile(r"^[A-Za-z0-9]+(?: [A-Za-z0-9]+)*$")
INPUT_SLUG_KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_lowercase(value: str, *, field: str) -> str:
    """Ensure `value` is lowercase (macOS case-insensitive FS safety)."""
    if value != value.lower():
        raise RuntimeError(f"{field} must be lowercase: {value}")
    return value


def validate_slug(value: str, *, field: str = "slug") -> str:
    """Validate a slug used in filesystem paths."""
    slug = value.strip()
    if not slug:
        raise RuntimeError(f"{field} is required")

    slug = validate_lowercase(slug, field=field)
    if slug in (".", ".."):
        raise RuntimeError(f"{field} must not be '{slug}'")

    if "/" in slug or "\\" in slug:
        raise RuntimeError(f"{field} must not contain path separators: {slug}")

    for ch in slug:
        if ch.isalnum() or ch in ("-", "_", "."):
            continue
        raise RuntimeError(
            f"{field} contains unsupported character: {ch!r} (slug={slug!r}). "
            "Use only letters/digits (Unicode ok) and '-', '_', '.'."
        )

    return slug


def validate_input_title(value: str, *, field: str = "--title") -> str:
    """Validate CLI input title for new/import commands."""
    title = value.strip()
    if not title:
        raise RuntimeError(f"{field} is required")
    if INPUT_TITLE_RE.fullmatch(title):
        return title
    raise RuntimeError(
        f"{field} is invalid: {value!r}\n"
        f"expected regex: {INPUT_TITLE_RE.pattern}\n"
        "OK examples: 'Add Refresh Token', 'JWT Auth 2'\n"
        "NG examples: 'Add-Token', 'Add  Token', 'Add_0Token', '日本語'"
    )


def validate_input_slug_kebab(value: str, *, field: str = "--slug") -> str:
    """Validate CLI input slug for new/import commands (kebab-case only)."""
    slug = value.strip()
    if not slug:
        raise RuntimeError(f"{field} is required")
    if INPUT_SLUG_KEBAB_RE.fullmatch(slug):
        return slug
    raise RuntimeError(
        f"{field} is invalid: {value!r}\n"
        f"expected regex: {INPUT_SLUG_KEBAB_RE.pattern}\n"
        "OK examples: 'add-refresh-token', 'jwt-auth-2'\n"
        "NG examples: 'Add-token', 'add_token', 'add..token', '日本語'"
    )


def derive_input_slug_from_title(title: str) -> str:
    """Derive deterministic kebab-case slug from an already validated title."""
    return title.lower().replace(" ", "-")


def resolve_input_title_and_slug(title: str, slug: str | None) -> tuple[str, str]:
    """Normalize+validate title/slug for new/import before any side effects."""
    normalized_title = validate_input_title(title, field="--title")
    if slug is None:
        derived_slug = derive_input_slug_from_title(normalized_title)
        return normalized_title, validate_input_slug_kebab(derived_slug, field="--slug")
    return normalized_title, validate_input_slug_kebab(slug, field="--slug")


def normalize_id_input(value: str, *, prefix: str, field: str) -> str:
    """Normalize an id argument into the canonical `<prefix>-NNNN` form."""
    raw = value.strip()
    if not raw:
        raise RuntimeError(f"{field} is required")

    raw = raw.lower()

    if NUM_RE.fullmatch(raw):
        return format_id(prefix, int(raw), local=False)

    parsed_prefix, is_local, num = parse_id(raw)
    if parsed_prefix != prefix:
        raise RuntimeError(f"{field} must be '{prefix}-NNNN' or 'NNNN': {value}")
    return format_id(prefix, num, local=is_local)


def find_existing_id_by_num(nodes: dict[str, Any], *, prefix: str, num: int, local: bool) -> str | None:
    """Find an existing node id by `(prefix, num, local)` in `nodes`."""
    for node_id in nodes:
        try:
            p, is_local, n = parse_id(str(node_id))
        except RuntimeError:
            continue
        if p == prefix and n == num and is_local == local:
            return str(node_id)
    return None


def resolve_id_input(value: str, *, prefix: str, field: str, nodes: dict[str, Any] | None = None) -> str:
    """Resolve an id argument with ambiguity checks when `nodes` is provided."""
    raw = value.strip().lower()
    if not raw:
        raise RuntimeError(f"{field} is required")

    if NUM_RE.fullmatch(raw):
        num = int(raw)
        normal = format_id(prefix, num, local=False)
        if not nodes:
            return normal
        existing_normal = find_existing_id_by_num(nodes, prefix=prefix, num=num, local=False)
        existing_local = find_existing_id_by_num(nodes, prefix=prefix, num=num, local=True)
        if existing_normal and existing_local:
            raise RuntimeError(
                f"{field} is ambiguous: {value} could mean {existing_normal} or {existing_local}. Use full id."
            )
        if existing_normal:
            return existing_normal
        if existing_local:
            return existing_local
        return normal

    parsed_prefix, is_local, num = parse_id(raw)
    if parsed_prefix != prefix:
        raise RuntimeError(f"{field} must be '{prefix}-NNNN', '{prefix}-local-NNNN' or 'NNNN': {value}")
    if nodes:
        existing = find_existing_id_by_num(nodes, prefix=prefix, num=num, local=is_local)
        if existing:
            return existing
    return format_id(prefix, num, local=is_local)


def slugify(title: str) -> str:
    """Conservative Unicode-aware slugifier for filenames."""
    s = unicodedata.normalize("NFKC", title).strip().lower()
    s = re.sub(r"\s+", "-", s)

    out: list[str] = []
    for ch in s:
        if ch.isalnum() or ch in ("-", "_", "."):
            out.append(ch)
        else:
            out.append("-")

    slug = "".join(out)
    slug = re.sub(r"-{2,}", "-", slug).strip("-._")
    return slug or "item"


def parse_id(value: str) -> tuple[str, bool, int]:
    """Parse a node id (`<prefix>-<num>` or `<prefix>-local-<num>`)."""
    m = ID_RE.fullmatch(value.strip().lower())
    if not m:
        raise RuntimeError(f"Invalid id format: {value!r} (expected: <prefix>-NNNN or <prefix>-local-NNNN)")
    prefix = m.group("prefix")
    is_local = m.group("local") == "local"
    num = int(m.group("num"))
    return prefix, is_local, num


def format_id(prefix: str, num: int, *, width: int = DEFAULT_ID_WIDTH, local: bool = False) -> str:
    """Format an id with zero-padding."""
    if local:
        return f"{prefix}-local-{num:0{width}d}"
    return f"{prefix}-{num:0{width}d}"


def deps_node_sort_key(node_id: str) -> tuple[int, int, str]:
    """Deterministic sort key for dependency-related outputs."""
    _, is_local, num = parse_id(node_id)
    return (1 if is_local else 0, num, node_id)
