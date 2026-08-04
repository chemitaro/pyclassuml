from __future__ import annotations

from dataclasses import dataclass
import re

from spec_dock_runtime.application.contracts import TargetRef

_num_re = re.compile(r"^[0-9]+$")
_gh_issue_url_full_re = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)/issues/(?P<num>[0-9]+)(?:[/?#].*)?$",
    re.IGNORECASE,
)
_node_id_re = re.compile(r"^(?P<prefix>init|epic|iss)(?:-(?P<local>local))?-(?P<num>[0-9]+)$")
_id_in_text_re = re.compile(r"(?<![a-z0-9])(?P<id>(?:init|epic|iss)(?:-local)?-[0-9]+)(?![a-z0-9])")


@dataclass(frozen=True)
class GitHubIssueTarget:
    issue_number: int
    repo_owner: str | None
    repo_name: str | None


def _normalize_repo_scope(owner: str | None, repo: str | None) -> tuple[str, str] | None:
    normalized_owner = str(owner or "").strip().lower()
    normalized_repo = str(repo or "").strip().lower()
    if not normalized_owner or not normalized_repo:
        return None
    return (normalized_owner, normalized_repo)


def _make_github_issue_target(
    *,
    issue_number: int,
    repo_owner: str | None = None,
    repo_name: str | None = None,
) -> TargetRef:
    scope = _normalize_repo_scope(repo_owner, repo_name)
    owner = scope[0] if scope is not None else None
    repo = scope[1] if scope is not None else None
    return TargetRef(
        kind="github_issue",
        node_id=None,
        github_issue_number=int(issue_number),
        github_repo_owner=owner,
        github_repo_name=repo,
    )


def _github_target_display(*, issue_number: int, repo_owner: str | None = None, repo_name: str | None = None) -> str:
    scope = _normalize_repo_scope(repo_owner, repo_name)
    if scope is None:
        return f"github#{int(issue_number)}"
    return f"github:{scope[0]}/{scope[1]}#{int(issue_number)}"


def parse_github_issue_target(target: str) -> int:
    return parse_github_issue_target_ref(target).issue_number


def _looks_like_non_canonical_github_issue_target(raw: str) -> bool:
    lowered = raw.lower()
    return "github.com" in lowered or "issues/" in lowered or "/" in raw or ":" in raw


def parse_github_issue_target_ref(target: str) -> GitHubIssueTarget:
    raw = target.strip()
    if not raw:
        raise RuntimeError("target is required")

    full_url_match = _gh_issue_url_full_re.fullmatch(raw)
    if full_url_match:
        return GitHubIssueTarget(
            issue_number=int(full_url_match.group("num")),
            repo_owner=full_url_match.group("owner").lower(),
            repo_name=full_url_match.group("repo").lower(),
        )

    if raw.startswith("http://") or raw.startswith("https://"):
        raise RuntimeError("Invalid target. Use a GitHub issue URL like https://github.com/<owner>/<repo>/issues/123.")

    # For import targets, accept either canonical GitHub issue URLs or pure issue numbers.
    # Reject URL-like strings to avoid bypassing repo-identity validation.
    if _looks_like_non_canonical_github_issue_target(raw):
        raise RuntimeError(
            "Invalid target. Use a GitHub issue number (e.g. 123 / #123) "
            "or a canonical URL like https://github.com/<owner>/<repo>/issues/123."
        )

    if raw.startswith("#") and _num_re.fullmatch(raw[1:]):
        return GitHubIssueTarget(issue_number=int(raw[1:]), repo_owner=None, repo_name=None)

    if _num_re.fullmatch(raw):
        return GitHubIssueTarget(issue_number=int(raw), repo_owner=None, repo_name=None)

    raise RuntimeError("Invalid target. Use a GitHub issue number (e.g. 123 / #123 / URL like .../issues/123).")


def parse_active_like_target(target: str) -> tuple[TargetRef, str]:
    raw = target.strip()
    if not raw:
        raise RuntimeError("target is required")

    full_url_match = _gh_issue_url_full_re.fullmatch(raw)
    if full_url_match:
        issue_number = int(full_url_match.group("num"))
        owner = full_url_match.group("owner")
        repo = full_url_match.group("repo")
        return (
            _make_github_issue_target(
                issue_number=issue_number,
                repo_owner=owner,
                repo_name=repo,
            ),
            _github_target_display(issue_number=issue_number, repo_owner=owner, repo_name=repo),
        )

    if raw.startswith("http://") or raw.startswith("https://"):
        raise RuntimeError("Invalid target. Use a GitHub issue URL like https://github.com/<owner>/<repo>/issues/123.")

    if _looks_like_non_canonical_github_issue_target(raw):
        raise RuntimeError(
            "Invalid target. Use a GitHub issue number (e.g. 123 / #123), "
            "a node id (e.g. iss-00123), or a canonical URL like https://github.com/<owner>/<repo>/issues/123."
        )

    if raw.startswith("#") and _num_re.fullmatch(raw[1:]):
        issue_number = int(raw[1:])
        return (_make_github_issue_target(issue_number=issue_number), _github_target_display(issue_number=issue_number))

    if _num_re.fullmatch(raw):
        issue_number = int(raw)
        return (_make_github_issue_target(issue_number=issue_number), _github_target_display(issue_number=issue_number))

    lowered = raw.lower()
    matches = [item.group("id") for item in _id_in_text_re.finditer(lowered)]
    unique = sorted(set(matches))
    if len(unique) == 1:
        _assert_valid_node_id(unique[0])
        return (TargetRef(kind="node_id", node_id=unique[0], github_issue_number=None), unique[0])

    if len(unique) > 1:
        by_prefix: dict[str, list[str]] = {"iss": [], "epic": [], "init": []}
        for item in unique:
            for prefix in ("iss", "epic", "init"):
                if item.startswith(prefix + "-"):
                    by_prefix[prefix].append(item)
                    break

        for prefix in ("iss", "epic", "init"):
            values = by_prefix[prefix]
            if len(values) == 1:
                _assert_valid_node_id(values[0])
                return (TargetRef(kind="node_id", node_id=values[0], github_issue_number=None), values[0])
            if len(values) > 1:
                raise RuntimeError(f"Ambiguous target: multiple {prefix} ids found: {', '.join(sorted(values))}")

        raise RuntimeError(f"Ambiguous target: multiple ids found: {', '.join(unique)}")

    raise RuntimeError(
        "Invalid target. Use a GitHub issue number (e.g. 123 / #123 / URL) or a node id (e.g. iss-00123)."
    )


def parse_explicit_target_flags(
    *,
    positional_target: str | None,
    node_id: str | None,
    github_issue: int | None,
    command_label: str,
) -> tuple[TargetRef, str]:
    raw_target = (positional_target or "").strip()
    raw_node_id = (node_id or "").strip()
    provided = 0
    if raw_target:
        provided += 1
    if raw_node_id:
        provided += 1
    if github_issue is not None:
        provided += 1
    if provided == 0:
        raise RuntimeError(f"{command_label}: target is required. Use <target> or '--id' / '--github-issue'.")
    if provided > 1:
        raise RuntimeError(f"{command_label}: choose exactly one of <target>, '--id', '--github-issue'.")
    if raw_node_id:
        lowered = raw_node_id.lower()
        _assert_valid_node_id(lowered)
        return (TargetRef(kind="node_id", node_id=lowered, github_issue_number=None), lowered)
    if github_issue is not None:
        if int(github_issue) <= 0:
            raise RuntimeError("--github-issue must be a positive integer.")
        issue_number = int(github_issue)
        return (
            _make_github_issue_target(issue_number=issue_number),
            _github_target_display(issue_number=issue_number),
        )
    return parse_active_like_target(raw_target)


def _assert_valid_node_id(value: str) -> None:
    if _node_id_re.fullmatch(value) is None:
        raise RuntimeError(f"Invalid node id: {value}")
