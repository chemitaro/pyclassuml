from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Literal


@dataclass(frozen=True)
class ReviewReportEvidence:
    status: Literal["pass", "missing", "unreadable", "malformed", "unsafe"]
    payload: dict[str, Any] | None = None
    content_sha256: str | None = None
    finding: str | None = None


def read_review_report_evidence(review_report: Path, *, context_path: Path) -> ReviewReportEvidence:
    repo_root = _lexical_repo_root(context_path)
    absolute = review_report if review_report.is_absolute() else Path.cwd() / review_report
    if repo_root is None:
        return ReviewReportEvidence("unsafe", finding="unsafe_review_report_path:outside-repository")
    repo_root = _normalize_system_alias(repo_root)
    absolute = _normalize_system_alias(absolute)
    if not _lexically_within(absolute, repo_root):
        resolved_root = repo_root.resolve(strict=False)
        if not _lexically_within(absolute, resolved_root):
            return ReviewReportEvidence("unsafe", finding="unsafe_review_report_path:outside-repository")
        repo_root = resolved_root
    relative = absolute.relative_to(repo_root)
    probe = repo_root
    for part in relative.parts:
        probe = probe / part
        if probe.is_symlink():
            return ReviewReportEvidence("unsafe", finding="unsafe_review_report_path:symlink")
    if not absolute.exists():
        return ReviewReportEvidence("missing", finding="missing_review_report")
    try:
        resolved = absolute.resolve(strict=True)
        resolved.relative_to(repo_root.resolve(strict=True))
    except (OSError, ValueError):
        return ReviewReportEvidence("unsafe", finding="unsafe_review_report_path:outside-repository")
    if not resolved.is_file():
        return ReviewReportEvidence("missing", finding="missing_review_report")
    try:
        content = resolved.read_bytes()
    except OSError:
        return ReviewReportEvidence("unreadable", finding="unreadable_review_report")
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ReviewReportEvidence("malformed", finding="malformed_review_report")
    if not isinstance(payload, dict):
        return ReviewReportEvidence("malformed", finding="malformed_review_report")
    return ReviewReportEvidence(
        "pass",
        payload=payload,
        content_sha256=hashlib.sha256(content).hexdigest(),
    )


def _lexical_repo_root(context_path: Path) -> Path | None:
    current = context_path if context_path.is_absolute() else Path.cwd() / context_path
    if not current.is_dir():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
        if candidate.name == ".specdock-authoring":
            return candidate.parent
        if (candidate / "spec-dock").is_dir():
            return candidate
    return None


def _lexically_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _normalize_system_alias(path: Path) -> Path:
    var_root = Path("/var")
    if _lexically_within(path, var_root):
        return Path("/private/var") / path.relative_to(var_root)
    return path
