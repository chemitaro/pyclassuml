from __future__ import annotations

from .ports import Ports


def normalize_repo_slug_value(slug: str | None) -> str | None:
    text = str(slug or "").strip().lower()
    if not text:
        return None
    owner, sep, repo = text.partition("/")
    if not sep or not owner or not repo:
        return None
    return f"{owner}/{repo}"


def normalize_repo_slug(owner: str | None, repo: str | None) -> str | None:
    normalized_owner = str(owner or "").strip().lower()
    normalized_repo = str(repo or "").strip().lower()
    if not normalized_owner or not normalized_repo:
        return None
    return f"{normalized_owner}/{normalized_repo}"


def split_repo_slug(slug: str | None) -> tuple[str, str] | None:
    normalized = normalize_repo_slug_value(slug)
    if normalized is None:
        return None
    owner, _sep, repo = normalized.partition("/")
    return (owner, repo)


def require_current_repo_slug(ports: Ports) -> str:
    if ports.repo_root is None:
        raise RuntimeError("repo_root is required to resolve current GitHub repo scope from origin.")
    if ports.git_gateway is None:
        raise RuntimeError("git_gateway is required to resolve current GitHub repo scope from origin.")
    resolver = getattr(ports.git_gateway, "origin_github_repo_slug", None)
    if not callable(resolver):
        raise RuntimeError("git_gateway.origin_github_repo_slug(repo_root) is required.")
    raw = resolver(ports.repo_root)
    normalized = normalize_repo_slug_value(raw)
    if normalized is None:
        raise RuntimeError("Current GitHub repo scope could not be resolved from origin.")
    return normalized


def resolve_current_repo_slug(ports: Ports) -> str | None:
    try:
        return require_current_repo_slug(ports)
    except RuntimeError:
        return None
