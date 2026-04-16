from __future__ import annotations

from pathlib import Path
from typing import Any

from .infra import github_cli as _infra_github_cli


def _ensure_gh_available() -> None:
    _infra_github_cli.ensure_gh_available()


def _gh_issue_index(repo_root: Path, *, limit: int) -> dict[int, dict[str, Any]]:
    return _infra_github_cli.issue_index_raw(repo_root, limit=limit)


def _gh_issue_create(repo_root: Path, *, title: str, body: str) -> int:
    return _infra_github_cli.issue_create_raw(repo_root, title=title, body=body)


def _gh_issue_view_minimal(repo_root: Path, *, issue_number: int) -> dict[str, Any]:
    return _infra_github_cli.issue_view_minimal_raw(repo_root, issue_number=issue_number)
