from __future__ import annotations

from typing import Any

from .presentation import puml as _presentation_puml

_TREE_BOARD_BLOCKERS_LABEL_LIMIT = _presentation_puml._TREE_BOARD_BLOCKERS_LABEL_LIMIT


def _active_entry_id(entry: Any) -> str | None:
    return _presentation_puml._active_entry_id(entry)


def _issue_ready_board_state(
    issue_id: str,
    issue_item: dict[str, Any],
    *,
    active_issue_id: str | None,
) -> tuple[str, list[str]]:
    return _presentation_puml._issue_ready_board_state(
        issue_id,
        issue_item,
        active_issue_id=active_issue_id,
    )


def _render_tree_ready_board_puml(
    tree_state: dict[str, Any],
    *,
    active: dict[str, Any] | None,
    todo_only: bool,
    blockers_label_limit: int = _TREE_BOARD_BLOCKERS_LABEL_LIMIT,
) -> str:
    return _presentation_puml._render_tree_ready_board_puml(
        tree_state,
        active=active,
        todo_only=todo_only,
        blockers_label_limit=blockers_label_limit,
    )


def _deps_disabled_error_text(error: str | None) -> str:
    return _presentation_puml._deps_disabled_error_text(error)


def _render_deps_disabled_tree_puml(*, todo_only: bool, error: str | None) -> str:
    return _presentation_puml._render_deps_disabled_tree_puml(todo_only=todo_only, error=error)


def _render_deps_disabled_deps_issues_puml(*, error: str | None) -> str:
    return _presentation_puml._render_deps_disabled_deps_issues_puml(error=error)


def _render_deps_issues_puml(deps_issues_state: dict[str, Any]) -> str:
    return _presentation_puml._render_deps_issues_puml(deps_issues_state)
