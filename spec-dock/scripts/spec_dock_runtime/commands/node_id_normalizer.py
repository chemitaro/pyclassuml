from __future__ import annotations

import re

_DEFAULT_ID_WIDTH = 5
_ID_RE = re.compile(r"^(?P<prefix>init|epic|iss|adr)(?:-(?P<local>local))?-(?P<num>[0-9]+)$")


def normalize_node_id(value: str, *, field: str) -> str:
    raw = value.strip().lower()
    if not raw:
        raise RuntimeError(f"{field} is required")
    prefix, is_local, num = _parse_node_id(raw)
    return _format_node_id(prefix, num, local=is_local)


def _parse_node_id(value: str) -> tuple[str, bool, int]:
    match = _ID_RE.fullmatch(value.strip().lower())
    if match is None:
        raise RuntimeError(f"Invalid id format: {value!r} (expected: <prefix>-NNNN or <prefix>-local-NNNN)")
    prefix = match.group("prefix")
    is_local = match.group("local") == "local"
    num = int(match.group("num"))
    return prefix, is_local, num


def _format_node_id(prefix: str, num: int, *, local: bool) -> str:
    if local:
        return f"{prefix}-local-{num:0{_DEFAULT_ID_WIDTH}d}"
    return f"{prefix}-{num:0{_DEFAULT_ID_WIDTH}d}"
