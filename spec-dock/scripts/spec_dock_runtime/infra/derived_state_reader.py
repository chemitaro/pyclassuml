from __future__ import annotations

from typing import TYPE_CHECKING

from spec_dock_runtime.infra.json_store import load_json

if TYPE_CHECKING:
    from pathlib import Path


def _load_cached_state_index(specdock_dir: Path) -> dict[str, object] | None:
    agent_dir = specdock_dir / ".agent"
    for state_index_path in (agent_dir / "index-all.json", agent_dir / "index.json"):
        if not state_index_path.is_file():
            continue
        try:
            loaded = load_json(state_index_path)
        except RuntimeError:
            continue
        if isinstance(loaded, dict):
            return loaded
    return None


def load_cached_issue_status_by_id(specdock_dir: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    state_index = _load_cached_state_index(specdock_dir)

    if not isinstance(state_index, dict):
        return out

    raw_nodes = state_index.get("nodes")
    if not isinstance(raw_nodes, dict):
        return out

    for issue_id, item in raw_nodes.items():
        if not isinstance(issue_id, str) or not isinstance(item, dict):
            continue
        raw_status = item.get("status")
        if not isinstance(raw_status, str):
            continue
        status = raw_status.strip().lower()
        if status in ("done", "open", "unknown"):
            out[issue_id] = status
    return out


def load_cached_issue_last_sync_at_by_id(specdock_dir: Path) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    state_index = _load_cached_state_index(specdock_dir)
    if not isinstance(state_index, dict):
        return out

    raw_nodes = state_index.get("nodes")
    if not isinstance(raw_nodes, dict):
        return out

    for issue_id, item in raw_nodes.items():
        if not isinstance(issue_id, str) or not isinstance(item, dict):
            continue
        raw_status = item.get("status")
        if not isinstance(raw_status, str):
            continue
        status = raw_status.strip().lower()
        if status in ("done", "open", "unknown"):
            raw_last_sync_at = item.get("last_sync_at")
            if isinstance(raw_last_sync_at, str):
                normalized = raw_last_sync_at.strip()
                out[issue_id] = normalized or None
            else:
                out[issue_id] = None
    return out
