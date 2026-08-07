from __future__ import annotations

import json
import re
import shutil
import subprocess
from typing import TYPE_CHECKING, Any

from spec_dock_runtime.domain.models import IssueSnapshot

if TYPE_CHECKING:
    from pathlib import Path

_GH_ISSUE_URL_RE = re.compile(r"/issues/(?P<num>[0-9]+)\b")
_GH_ISSUE_REPO_URL_RE = re.compile(
    r"https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/issues/(?P<num>[0-9]+)\b",
    re.IGNORECASE,
)


def ensure_gh_available() -> None:
    if shutil.which("gh") is None:
        raise RuntimeError(
            "'gh' CLI not found. Install GitHub CLI (gh), or use '--no-github' for supported cache/local state commands."
        )


def issue_index_raw(repo_root: Path, *, limit: int) -> dict[int, dict[str, Any]]:
    ensure_gh_available()
    cmd = [
        "gh",
        "issue",
        "list",
        "--state",
        "all",
        "--limit",
        str(limit),
        "--json",
        "number,state,title,labels,updatedAt,url",
    ]
    try:
        p = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"gh failed: {' '.join(cmd)}\n{(e.stderr or '').strip()}") from e

    try:
        data = json.loads(p.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"gh returned invalid JSON: {' '.join(cmd)}") from e
    if not isinstance(data, list):
        raise RuntimeError(f"gh returned invalid JSON payload (expected a list): {' '.join(cmd)}")

    index: dict[int, dict[str, Any]] = {}
    for item in data:
        try:
            number = int(item.get("number"))
        except (TypeError, ValueError):
            continue
        index[number] = item
    return index


def issue_create_raw(repo_root: Path, *, title: str, body: str) -> int:
    ensure_gh_available()
    cmd = ["gh", "issue", "create", "--title", title, "--body", body]
    try:
        p = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"gh failed: {' '.join(cmd)}\n{(e.stderr or '').strip()}") from e

    out = f"{(p.stdout or '').strip()}\n{(p.stderr or '').strip()}".strip()
    m = _GH_ISSUE_URL_RE.search(out)
    if not m:
        raise RuntimeError(f"Failed to parse issue number from gh output:\n{out}")
    return int(m.group("num"))


def issue_view_minimal_raw(repo_root: Path, *, issue_number: int, repo_slug: str | None = None) -> dict[str, Any]:
    ensure_gh_available()
    cmd = ["gh", "issue", "view", str(issue_number), "--json", "number,url"]
    normalized_repo_slug = (repo_slug or "").strip()
    if normalized_repo_slug:
        cmd.extend(["--repo", normalized_repo_slug])
    try:
        p = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"gh failed: {' '.join(cmd)}\n{(e.stderr or '').strip()}") from e

    try:
        data = json.loads((p.stdout or "").strip())
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON from gh issue view for issue #{issue_number}") from e
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid gh issue view payload for issue #{issue_number}")

    raw_number = data.get("number")
    if raw_number is None:
        raise RuntimeError("Invalid gh issue view payload: number=None")
    try:
        number = int(raw_number)
    except (TypeError, ValueError) as e:
        raise RuntimeError(f"Invalid gh issue view payload: number={raw_number}") from e
    if number != issue_number:
        raise RuntimeError(f"gh issue view returned mismatched number: expected {issue_number}, got {number}")
    return data


def issue_view_snapshot_raw(repo_root: Path, *, issue_number: int, repo_slug: str | None = None) -> dict[str, Any]:
    ensure_gh_available()
    cmd = [
        "gh",
        "issue",
        "view",
        str(issue_number),
        "--json",
        "number,state,title,labels,updatedAt,url",
    ]
    normalized_repo_slug = (repo_slug or "").strip()
    if normalized_repo_slug:
        cmd.extend(["--repo", normalized_repo_slug])
    try:
        p = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"gh failed: {' '.join(cmd)}\n{(e.stderr or '').strip()}") from e

    try:
        data = json.loads((p.stdout or "").strip())
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON from gh issue view for issue #{issue_number}") from e
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid gh issue view payload for issue #{issue_number}")

    raw_number = data.get("number")
    if raw_number is None:
        raise RuntimeError("Invalid gh issue view payload: number=None")
    try:
        number = int(raw_number)
    except (TypeError, ValueError) as e:
        raise RuntimeError(f"Invalid gh issue view payload: number={raw_number}") from e
    if number != issue_number:
        raise RuntimeError(f"gh issue view returned mismatched number: expected {issue_number}, got {number}")
    return data


def issue_close_raw(repo_root: Path, *, issue_number: int, repo_slug: str | None = None) -> dict[str, Any]:
    ensure_gh_available()
    cmd = ["gh", "issue", "close", str(issue_number)]
    normalized_repo_slug = (repo_slug or "").strip()
    if normalized_repo_slug:
        cmd.extend(["--repo", normalized_repo_slug])
    try:
        subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"gh failed: {' '.join(cmd)}\n{(e.stderr or '').strip()}") from e
    return issue_view_snapshot_raw(repo_root, issue_number=issue_number, repo_slug=repo_slug)


def _parse_repo_identity_from_issue_url(url: str) -> tuple[str | None, str | None]:
    matched = _GH_ISSUE_REPO_URL_RE.search(str(url).strip())
    if matched is None:
        return (None, None)
    owner = str(matched.group("owner")).strip().lower()
    repo = str(matched.group("repo")).strip().lower()
    if not owner or not repo:
        return (None, None)
    return (owner, repo)


def _issue_snapshot_from_raw(item: dict[str, Any], *, repo_slug: str | None = None) -> IssueSnapshot:
    url = str(item.get("url", ""))
    owner, repo = _parse_repo_identity_from_issue_url(url)
    if owner is None or repo is None:
        normalized_repo_slug = (repo_slug or "").strip()
        if normalized_repo_slug:
            slug_owner, sep, slug_repo = normalized_repo_slug.partition("/")
            slug_owner = slug_owner.strip().lower()
            slug_repo = slug_repo.strip().lower()
            if sep and slug_owner and slug_repo:
                owner = slug_owner
                repo = slug_repo
    raw_number = item.get("number")
    if raw_number is None:
        raise RuntimeError("Invalid gh issue snapshot payload: number=None")
    try:
        issue_number = int(raw_number)
    except (TypeError, ValueError) as e:
        raise RuntimeError(f"Invalid gh issue snapshot payload: number={raw_number}") from e
    return IssueSnapshot(
        issue_number=issue_number,
        state=str(item.get("state", "")),
        title=str(item.get("title", "")),
        labels=[str(label.get("name", "")) for label in (item.get("labels") or []) if isinstance(label, dict)],
        updated_at=str(item.get("updatedAt", "")),
        url=url,
        repo_owner=owner,
        repo_name=repo,
    )


def issue_index(repo_root: Path, *, limit: int) -> list[IssueSnapshot]:
    index = issue_index_raw(repo_root, limit=limit)
    snapshots: list[IssueSnapshot] = []
    for item in index.values():
        snapshots.append(_issue_snapshot_from_raw(item))
    return snapshots


def issue_create(repo_root: Path, title: str, body: str) -> int:
    return issue_create_raw(repo_root, title=title, body=body)


def issue_view_minimal(repo_root: Path, issue_number: int, *, repo_slug: str | None = None) -> IssueSnapshot:
    raw = issue_view_minimal_raw(repo_root, issue_number=issue_number, repo_slug=repo_slug)
    return _issue_snapshot_from_raw(raw, repo_slug=repo_slug)


def issue_view_snapshot(repo_root: Path, issue_number: int, *, repo_slug: str | None = None) -> IssueSnapshot:
    raw = issue_view_snapshot_raw(repo_root, issue_number=issue_number, repo_slug=repo_slug)
    return _issue_snapshot_from_raw(raw, repo_slug=repo_slug)


def issue_close(repo_root: Path, issue_number: int, *, repo_slug: str | None = None) -> IssueSnapshot:
    raw = issue_close_raw(repo_root, issue_number=issue_number, repo_slug=repo_slug)
    return _issue_snapshot_from_raw(raw, repo_slug=repo_slug)
