from __future__ import annotations

from pathlib import Path
from typing import Any


def _active_entry_id(entry: Any) -> str | None:
    """Return active entry id if shape is valid."""
    if not isinstance(entry, dict):
        return None
    value = entry.get("id")
    if isinstance(value, str) and value:
        return value
    return None


def _active_entry_path(repo_root: Path, entry: Any) -> Path | None:
    """Return active entry path under repo root if shape is valid."""
    if not isinstance(entry, dict):
        return None
    path_value = entry.get("path")
    if not isinstance(path_value, str) or not path_value:
        return None
    return (repo_root / path_value).resolve()
