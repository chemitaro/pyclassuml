from __future__ import annotations

from typing import Any

from .presentation import markdown as _presentation_markdown

_DASHBOARD_TOP_LIMIT = _presentation_markdown._DASHBOARD_TOP_LIMIT
_TREE_BOARD_BLOCKERS_LABEL_LIMIT = _presentation_markdown._TREE_BOARD_BLOCKERS_LABEL_LIMIT


def _active_entry_id(entry: Any) -> str | None:
    return _presentation_markdown._active_entry_id(entry)


def _render_dashboard_md(
    index_nodes: dict[str, Any],
    *,
    active: dict[str, Any] | None,
    top_limit: int = _DASHBOARD_TOP_LIMIT,
) -> str:
    return _presentation_markdown._render_dashboard_md(index_nodes, active=active, top_limit=top_limit)


def _render_deps_disabled_dashboard_md(*, error: str | None) -> str:
    return _presentation_markdown._render_deps_disabled_dashboard_md(error=error)
