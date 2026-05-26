from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from ..application.contracts import GitWorktreeRecord


def _ensure_git_available() -> None:
    if shutil.which("git") is None:
        raise RuntimeError("'git' CLI not found. Install Git, or disable git-dependent operations.")


def require_clean_working_tree(repo_root: Path) -> None:
    _ensure_git_available()
    try:
        p = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"git failed: git status --porcelain\n{(e.stderr or '').strip()}") from e

    out = (p.stdout or "").strip()
    if out:
        head = "\n".join(out.splitlines()[:20])
        more = "" if len(out.splitlines()) <= 20 else "\n..."
        raise RuntimeError(
            "Working tree is not clean; aborting checkout for safety.\n"
            "Please commit/stash your changes first.\n\n"
            f"{head}{more}"
        )


def current_branch_or_none(repo_root: Path) -> str | None:
    _ensure_git_available()
    try:
        p = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"git failed: git rev-parse --abbrev-ref HEAD\n{(e.stderr or '').strip()}") from e
    branch = (p.stdout or "").strip()
    if not branch or branch == "HEAD":
        return None
    return branch


def local_branch_exists(repo_root: Path, branch: str) -> bool:
    _ensure_git_available()
    p = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return p.returncode == 0


def checkout_branch(repo_root: Path, branch: str) -> None:
    _ensure_git_available()
    cmd = ["git", "checkout", branch]
    try:
        subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"git failed: {' '.join(cmd)}\n{(e.stderr or '').strip()}") from e


def create_and_checkout_branch(repo_root: Path, branch: str) -> None:
    _ensure_git_available()
    cmd = ["git", "checkout", "-b", branch]
    try:
        subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"git failed: {' '.join(cmd)}\n{(e.stderr or '').strip()}") from e


def check_ref_format_branch(repo_root: Path, branch: str) -> bool:
    _ensure_git_available()
    p = subprocess.run(
        ["git", "check-ref-format", "--branch", branch],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return p.returncode == 0


_HTTPS_GH_REMOTE_RE = re.compile(
    r"^https?://(?:[^@/]+@)?github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)
_SSH_GH_REMOTE_RE = re.compile(
    r"^(?:ssh://)?git@github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)


def _remote_get_url(repo_root: Path, *, push: bool) -> str:
    _ensure_git_available()
    cmd = ["git", "remote", "get-url"]
    if push:
        cmd.append("--push")
    cmd.append("origin")
    p = subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if p.returncode != 0:
        stderr = (p.stderr or "").strip()
        if "No such remote" in stderr and "origin" in stderr:
            raise RuntimeError("origin remote is missing; cannot resolve canonical GitHub repo scope.")
        raise RuntimeError(f"git failed: {' '.join(cmd)}\n{stderr}")
    raw = (p.stdout or "").strip()
    if not raw:
        raise RuntimeError("origin remote is missing; cannot resolve canonical GitHub repo scope.")
    return raw


def _parse_github_repo_slug(remote_url: str) -> str | None:
    match = _HTTPS_GH_REMOTE_RE.fullmatch(remote_url) or _SSH_GH_REMOTE_RE.fullmatch(remote_url)
    if match is None:
        return None
    owner = match.group("owner").strip().lower()
    repo = match.group("repo").strip().lower()
    if not owner or not repo:
        return None
    return f"{owner}/{repo}"


def origin_github_repo_slug(repo_root: Path) -> str | None:
    fetch_url = _remote_get_url(repo_root, push=False)
    push_url = _remote_get_url(repo_root, push=True)
    fetch_slug = _parse_github_repo_slug(fetch_url)
    push_slug = _parse_github_repo_slug(push_url)
    if fetch_slug is None or push_slug is None:
        raise RuntimeError(
            "origin remote is not a GitHub repository; cannot resolve canonical repo scope: "
            f"fetch={fetch_url} push={push_url}"
        )
    if fetch_slug != push_slug:
        raise RuntimeError(
            "origin remote fetch/push mismatch; cannot resolve canonical repo scope: "
            f"fetch={fetch_slug} push={push_slug}"
        )
    return fetch_slug


def worktree_list(repo_root: Path) -> list[GitWorktreeRecord]:
    _ensure_git_available()
    cmd = ["git", "worktree", "list", "--porcelain"]
    try:
        p = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"git failed: {' '.join(cmd)}\n{(e.stderr or '').strip()}") from e
    return _parse_worktree_porcelain(p.stdout or "")


def add_worktree_with_new_branch(repo_root: Path, *, path: Path, branch: str) -> None:
    _ensure_git_available()
    cmd = ["git", "worktree", "add", "-b", branch, str(path)]
    try:
        subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or "").strip()
        stdout = (e.stdout or "").strip()
        details = "\n".join(part for part in (stderr, stdout) if part)
        raise RuntimeError(f"git failed: {' '.join(cmd)}\n{details}") from e


def _parse_worktree_porcelain(text: str) -> list[GitWorktreeRecord]:
    records: list[GitWorktreeRecord] = []
    current: dict[str, object] = {}

    def flush() -> None:
        if "path" not in current:
            return
        branch_ref = current.get("branch")
        branch = None
        if isinstance(branch_ref, str):
            prefix = "refs/heads/"
            branch = branch_ref[len(prefix):] if branch_ref.startswith(prefix) else branch_ref
        records.append(
            GitWorktreeRecord(
                path=Path(str(current["path"])),
                head=current.get("head") if isinstance(current.get("head"), str) else None,
                branch=branch,
                detached=bool(current.get("detached", False)),
                bare=bool(current.get("bare", False)),
            )
        )

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            flush()
            current = {}
            continue
        if line.startswith("worktree "):
            flush()
            current = {"path": line[len("worktree "):]}
        elif line.startswith("HEAD "):
            current["head"] = line[len("HEAD "):]
        elif line.startswith("branch "):
            current["branch"] = line[len("branch "):]
        elif line == "detached":
            current["detached"] = True
        elif line == "bare":
            current["bare"] = True
    flush()
    return records
