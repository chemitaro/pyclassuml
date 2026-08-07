from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
import subprocess

from spec_dock_runtime.application.contracts import (
    GitHubCapability,
    GitHubCapabilityDiagnostic,
    GitHubCapabilityDiagnosticCode,
    GitHubCapabilityGroup,
    GitHubCapabilityProbeRequest,
    GitHubCapabilitySeverity,
    GitHubCapabilityStatus,
    GitHubCapabilityTokenSource,
)


@dataclass(frozen=True)
class GitHubCapabilityCliGateway:
    def probe(self, request: GitHubCapabilityProbeRequest) -> list[GitHubCapabilityDiagnostic]:
        diagnostics: list[GitHubCapabilityDiagnostic] = []
        fixed_checks: list[tuple[GitHubCapability, GitHubCapabilityGroup, str, list[str]]] = [
            (
                "repo_metadata_read",
                "core",
                "gh repo view",
                ["gh", "repo", "view", request.github_repo, "--json", "nameWithOwner"],
            ),
            (
                "pull_request_read",
                "core",
                "gh pr view",
                [
                    "gh",
                    "pr",
                    "view",
                    str(request.github_pr),
                    "--repo",
                    request.github_repo,
                    "--json",
                    "number,headRefOid",
                ],
            ),
            (
                "actions_read",
                "core",
                "GET /repos/{repo}/actions/runs",
                ["gh", "api", f"repos/{request.github_repo}/actions/runs"],
            ),
            (
                "issue_comments_read",
                "core",
                "GET /repos/{repo}/issues/{pr}/comments",
                ["gh", "api", f"repos/{request.github_repo}/issues/{request.github_pr}/comments"],
            ),
            (
                "pull_reviews_read",
                "core",
                "GET /repos/{repo}/pulls/{pr}/reviews",
                ["gh", "api", f"repos/{request.github_repo}/pulls/{request.github_pr}/reviews"],
            ),
            (
                "pull_review_comments_read",
                "core",
                "GET /repos/{repo}/pulls/{pr}/comments",
                ["gh", "api", f"repos/{request.github_repo}/pulls/{request.github_pr}/comments"],
            ),
            _review_threads_graphql_check(request),
        ]
        for capability, group, api, command in fixed_checks:
            completed = _run_fixed_gh(command)
            diagnostics.append(
                _diagnostic_from_completed_process(
                    capability=capability,
                    group=group,
                    api=api,
                    completed=completed,
                )
            )
        if request.include_extended:
            for capability, group, api, command in _extended_checks():
                completed = _run_fixed_gh(command)
                diagnostics.append(
                    _diagnostic_from_completed_process(
                        capability=capability,
                        group=group,
                        api=api,
                        completed=completed,
                    )
                )
        return diagnostics


def _extended_checks() -> list[tuple[GitHubCapability, GitHubCapabilityGroup, str, list[str]]]:
    return []


def _review_threads_graphql_check(
    request: GitHubCapabilityProbeRequest,
) -> tuple[GitHubCapability, GitHubCapabilityGroup, str, list[str]]:
    owner, name = _github_repo_owner_name(request.github_repo)
    query = (
        "query($owner:String!,$name:String!,$number:Int!){"
        "repository(owner:$owner,name:$name){"
        "pullRequest(number:$number){"
        "reviewDecision "
        "reviewThreads(first:1){"
        "nodes{id isResolved} "
        "pageInfo{hasNextPage endCursor}"
        "}"
        "}"
        "}"
        "}"
    )
    return (
        "pull_review_threads_read",
        "core",
        "GraphQL PullRequest.reviewDecision/reviewThreads",
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"owner={owner}",
            "-f",
            f"name={name}",
            "-F",
            f"number={request.github_pr}",
            "-f",
            f"query={query}",
        ],
    )


def _github_repo_owner_name(github_repo: str) -> tuple[str, str]:
    owner, separator, name = github_repo.partition("/")
    if not separator:
        return owner, ""
    return owner, name


def _run_fixed_gh(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(command, 127, "", "gh executable not found")


def _diagnostic_from_completed_process(
    *,
    capability: GitHubCapability,
    group: GitHubCapabilityGroup,
    api: str,
    completed: subprocess.CompletedProcess[str],
) -> GitHubCapabilityDiagnostic:
    status = _classify_status(completed)
    code = _code_for_status(status)
    return GitHubCapabilityDiagnostic(
        code=code,
        capability=capability,
        status=status,
        token_source=_token_source(),
        api=api,
        severity=_severity_for_status(status),
        message=_message_for_status(status),
        recommended_next_action=_action_for_status(status),
        secret_redacted=True,
        stderr_sha256=_stderr_sha256(completed.stderr),
        group=group,
    )


def _token_source() -> GitHubCapabilityTokenSource:
    if os.environ.get("GH_TOKEN"):
        return "GH_TOKEN"
    if os.environ.get("GITHUB_TOKEN"):
        return "GITHUB_TOKEN"
    return "gh_saved_auth"


def _stderr_sha256(stderr: str) -> str | None:
    if not stderr:
        return None
    return hashlib.sha256(stderr.encode("utf-8")).hexdigest()


def _classify_status(completed: subprocess.CompletedProcess[str]) -> GitHubCapabilityStatus:
    if completed.returncode == 0:
        return "ok"
    stderr = completed.stderr.lower()
    if (
        "resource not accessible by personal access token" in stderr
        or "resource not accessible by integration" in stderr
        or "permission denied" in stderr
    ):
        return "permission_denied"
    if (
        "authentication" in stderr
        or "not logged into" in stderr
        or "could not resolve to a repository" in stderr
        or "gh executable not found" in stderr
    ):
        return "auth_missing"
    if "rate limit" in stderr or "api rate limit exceeded" in stderr:
        return "rate_limited"
    if "unknown json field" in stderr:
        return "schema_unavailable"
    if "field" in stderr and ("not found" in stderr or "doesn't exist" in stderr):
        return "schema_unavailable"
    if completed.returncode in (1, 2, 4):
        return "transient_unknown"
    return "transient_unknown"


def _code_for_status(status: GitHubCapabilityStatus) -> GitHubCapabilityDiagnosticCode:
    if status == "ok":
        return "github_capability_ok"
    if status == "permission_denied":
        return "github_token_permission_denied"
    if status == "auth_missing":
        return "github_auth_missing"
    if status == "rate_limited":
        return "github_rate_limited"
    if status == "schema_unavailable":
        return "github_schema_unavailable"
    if status == "skipped":
        return "github_capability_skipped"
    if status == "target_unavailable":
        return "github_target_unavailable"
    return "github_transient_unknown"


def _severity_for_status(status: GitHubCapabilityStatus) -> GitHubCapabilitySeverity:
    if status == "ok" or status == "skipped" or status == "target_unavailable":
        return "info"
    if status == "transient_unknown" or status == "rate_limited" or status == "schema_unavailable":
        return "warning"
    return "blocking"


def _message_for_status(status: GitHubCapabilityStatus) -> str:
    messages = {
        "ok": "GitHub capability probe succeeded.",
        "permission_denied": "GitHub token lacks permission for this fixed capability.",
        "auth_missing": "GitHub authentication is missing or unavailable.",
        "rate_limited": "GitHub API rate limit blocked this fixed capability probe.",
        "target_unavailable": "GitHub target context is unavailable.",
        "transient_unknown": "GitHub capability probe failed with an unclassified transient error.",
        "schema_unavailable": "GitHub response schema is unavailable for this fixed capability.",
        "skipped": "GitHub capability probe was skipped.",
    }
    return messages[status]


def _action_for_status(status: GitHubCapabilityStatus) -> str:
    actions = {
        "ok": "none",
        "permission_denied": "fix_github_token_permissions",
        "auth_missing": "authenticate_gh_or_set_token",
        "rate_limited": "retry_after_rate_limit_reset",
        "target_unavailable": "provide_github_repo_pr_and_head_sha_for_capability_probe",
        "transient_unknown": "retry_or_inspect_github",
        "schema_unavailable": "inspect_gh_version_or_api_schema",
        "skipped": "run_in_installed_runtime_with_github_capability_gateway",
    }
    return actions[status]
