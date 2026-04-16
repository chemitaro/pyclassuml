from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..domain.ids import deps_node_sort_key, find_existing_id_by_num, format_id, parse_id
from ..domain.models import SpecGraph
from .contracts import DirectDependencyResolution
from .contracts import DepsTopologyLoadResult
from .git_cli import origin_github_repo_slug
from .json_store import load_json

_scoped_issue_ref_re = re.compile(
    r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)#(?P<num>[0-9]+)$"
)
_gh_issue_url_full_re = re.compile(
    r"^(?:https?://)?(?:www\.)?github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)/issues/(?P<num>[0-9]+)(?:[/?#].*)?$",
    re.IGNORECASE,
)


def _load_meta_depends_on(path: Path) -> list[Any]:
    data = load_json(path)
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid .meta.json schema: {path}: expected a JSON object")

    schema_version = data.get("schema_version")
    if isinstance(schema_version, bool) or not isinstance(schema_version, int) or schema_version != 1:
        raise RuntimeError(f"Invalid .meta.json schema: {path}: schema_version must be 1")

    depends_on = data.get("depends_on", [])
    if not isinstance(depends_on, list):
        raise RuntimeError(f"Invalid .meta.json schema: {path}: depends_on must be a list")

    for i, ref in enumerate(depends_on):
        if isinstance(ref, bool):
            raise RuntimeError(f"Invalid .meta.json schema: {path}: depends_on[{i}] must be a string or int")
        if isinstance(ref, (str, int)):
            continue
        raise RuntimeError(f"Invalid .meta.json schema: {path}: depends_on[{i}] must be a string or int")

    return depends_on


def _normalize_repo_slug(owner: str | None, repo: str | None) -> str | None:
    normalized_owner = str(owner or "").strip().lower()
    normalized_repo = str(repo or "").strip().lower()
    if not normalized_owner or not normalized_repo:
        return None
    return f"{normalized_owner}/{normalized_repo}"


def _normalize_repo_slug_value(slug: str | None) -> str | None:
    normalized = str(slug or "").strip().lower()
    if not normalized:
        return None
    owner, sep, repo = normalized.partition("/")
    if not sep or not owner or not repo:
        return None
    return f"{owner}/{repo}"


def _resolve_current_repo_slug(specdock_dir: Path) -> str | None:
    repo_root = specdock_dir.parent
    try:
        raw = origin_github_repo_slug(repo_root)
    except RuntimeError:
        return None
    return _normalize_repo_slug_value(raw)


def _find_node_by_github_issue_number(
    graph: SpecGraph,
    *,
    issue_number: int,
    current_repo_slug: str | None = None,
) -> str:
    matches = [
        node
        for node in graph.nodes_by_id.values()
        if node.github_issue_number == issue_number and node.kind in ("initiative", "epic", "issue")
    ]
    if not matches:
        raise RuntimeError(f"No node found for github.issue_number={issue_number}. Create/link the node first.")

    if current_repo_slug is not None:
        current_scoped = [
            node
            for node in matches
            if (_normalize_repo_slug(node.github_repo_owner, node.github_repo_name) or current_repo_slug)
            == current_repo_slug
        ]
        if not current_scoped:
            raise RuntimeError(
                f"No node found for github.issue_number={issue_number} in current repo scope ({current_repo_slug}). "
                "Create/link the node first."
            )
        if len(current_scoped) > 1:
            ids = ", ".join(sorted(f"{node.kind}:{node.id}" for node in current_scoped))
            raise RuntimeError(f"Ambiguous github.issue_number={issue_number}: {ids}")
        return current_scoped[0].id

    has_scoped = any(_normalize_repo_slug(node.github_repo_owner, node.github_repo_name) is not None for node in matches)
    has_unscoped = any(_normalize_repo_slug(node.github_repo_owner, node.github_repo_name) is None for node in matches)
    if has_scoped and has_unscoped:
        ids = ", ".join(
            sorted(
                f"{node.kind}:{node.id}"
                f"[repo={_normalize_repo_slug(node.github_repo_owner, node.github_repo_name) or '(current-or-unknown)'}]"
                for node in matches
            )
        )
        raise RuntimeError(
            f"Ambiguous github.issue_number={issue_number}: mixed scoped/unscoped linkage (fail-closed): {ids}. "
            "Configure current repo remote (origin) or normalize linkage scope before retrying."
        )

    if len(matches) > 1:
        ids = ", ".join(sorted(f"{node.kind}:{node.id}" for node in matches))
        raise RuntimeError(f"Ambiguous github.issue_number={issue_number}: {ids}")
    return matches[0].id


def _find_node_by_scoped_github_issue_number(
    graph: SpecGraph,
    *,
    issue_number: int,
    repo_owner: str,
    repo_name: str,
    current_repo_slug: str | None = None,
) -> str:
    repo_slug = _normalize_repo_slug(repo_owner, repo_name)
    if repo_slug is None:
        raise RuntimeError("repo scope is required")
    allow_current_unscoped = current_repo_slug is not None and repo_slug == current_repo_slug
    matches = [
        node
        for node in graph.nodes_by_id.values()
        if node.github_issue_number == issue_number
        and node.kind in ("initiative", "epic", "issue")
        and (
            _normalize_repo_slug(node.github_repo_owner, node.github_repo_name) == repo_slug
            or (
                allow_current_unscoped and _normalize_repo_slug(node.github_repo_owner, node.github_repo_name) is None
            )
        )
    ]
    if not matches:
        raise RuntimeError(
            f"No node found for github.issue_number={issue_number} in repo scope ({repo_slug}). "
            "Create/link the node first."
        )
    if len(matches) > 1:
        ids = ", ".join(sorted(f"{node.kind}:{node.id}" for node in matches))
        raise RuntimeError(f"Ambiguous github.issue_number={issue_number} in repo scope ({repo_slug}): {ids}")
    return matches[0].id


def _resolve_dep_ref(
    graph: SpecGraph,
    ref: Any,
    *,
    src_path: Path,
    current_repo_slug: str | None = None,
) -> str:
    if isinstance(ref, bool):
        raise RuntimeError(f"Unresolved dependency ref: {ref!r} (in {src_path})")

    if isinstance(ref, int):
        try:
            return _find_node_by_github_issue_number(
                graph,
                issue_number=int(ref),
                current_repo_slug=current_repo_slug,
            )
        except RuntimeError as e:
            raise RuntimeError(f"Unresolved dependency ref: {ref!r} (in {src_path}): {e}") from e

    if isinstance(ref, str):
        raw = ref.strip()
        if not raw:
            raise RuntimeError(f"Unresolved dependency ref: {ref!r} (in {src_path})")
        scoped_match = _scoped_issue_ref_re.fullmatch(raw)
        if scoped_match:
            try:
                return _find_node_by_scoped_github_issue_number(
                    graph,
                    issue_number=int(scoped_match.group("num")),
                    repo_owner=scoped_match.group("owner"),
                    repo_name=scoped_match.group("repo"),
                    current_repo_slug=current_repo_slug,
                )
            except RuntimeError as e:
                raise RuntimeError(f"Unresolved dependency ref: {ref!r} (in {src_path}): {e}") from e
        full_url_match = _gh_issue_url_full_re.fullmatch(raw)
        if full_url_match:
            try:
                return _find_node_by_scoped_github_issue_number(
                    graph,
                    issue_number=int(full_url_match.group("num")),
                    repo_owner=full_url_match.group("owner"),
                    repo_name=full_url_match.group("repo"),
                    current_repo_slug=current_repo_slug,
                )
            except RuntimeError as e:
                raise RuntimeError(f"Unresolved dependency ref: {ref!r} (in {src_path}): {e}") from e
        if raw.isdigit():
            try:
                return _find_node_by_github_issue_number(
                    graph,
                    issue_number=int(raw),
                    current_repo_slug=current_repo_slug,
                )
            except RuntimeError as e:
                raise RuntimeError(f"Unresolved dependency ref: {ref!r} (in {src_path}): {e}") from e

        try:
            prefix, is_local, num = parse_id(raw.lower())
        except RuntimeError as e:
            raise RuntimeError(f"Unresolved dependency ref: {ref!r} (in {src_path}): {e}") from e
        if prefix not in ("init", "epic", "iss"):
            raise RuntimeError(
                f"Unresolved dependency ref: {ref!r} (in {src_path}): unsupported id prefix: {prefix}"
            )

        existing = find_existing_id_by_num(graph.nodes_by_id, prefix=prefix, num=num, local=is_local)
        if not existing:
            normalized = format_id(prefix, num, local=is_local)
            raise RuntimeError(f"Unresolved dependency ref: {ref!r} (in {src_path}): node not found ({normalized})")
        return existing

    raise RuntimeError(
        f"Unresolved dependency ref: {ref!r} (in {src_path}): unsupported type: {type(ref).__name__}"
    )


def _is_descendant(graph: SpecGraph, *, src_id: str, candidate_dep_id: str) -> bool:
    current_id = candidate_dep_id
    visited: set[str] = set()
    while True:
        current = graph.nodes_by_id.get(current_id)
        if current is None or not current.parent_id:
            return False
        parent_id = current.parent_id
        if parent_id == src_id:
            return True
        if parent_id in visited:
            return False
        visited.add(parent_id)
        current_id = parent_id


def _resolved_direct_depends_on(
    graph: SpecGraph,
    src_id: str,
    *,
    current_repo_slug: str | None = None,
) -> list[str]:
    src = graph.nodes_by_id.get(src_id)
    if src is None:
        raise RuntimeError(f"Internal error: missing node: {src_id}")
    meta_path = src.path / ".meta.json"
    depends_on = _load_meta_depends_on(meta_path)
    resolved = [
        _resolve_dep_ref(
            graph,
            ref,
            src_path=meta_path,
            current_repo_slug=current_repo_slug,
        )
        for ref in depends_on
    ]
    deduped = sorted(set(resolved), key=deps_node_sort_key)
    for dep_id in deduped:
        if _is_descendant(graph, src_id=src_id, candidate_dep_id=dep_id):
            raise RuntimeError(f"Invalid dependency: {src_id} cannot depend on its descendant {dep_id} (in {meta_path})")
    return deduped


def load_direct_dependency_resolutions(
    specdock_dir: Path,
    graph: SpecGraph,
    src_id: str,
) -> list[DirectDependencyResolution]:
    src = graph.nodes_by_id.get(src_id)
    if src is None:
        raise RuntimeError(f"Node not found: {src_id}")
    meta_path = src.path / ".meta.json"
    current_repo_slug = _resolve_current_repo_slug(specdock_dir)
    depends_on = _load_meta_depends_on(meta_path)
    return [
        DirectDependencyResolution(
            raw_ref=ref,
            resolved_node_id=_resolve_dep_ref(
                graph,
                ref,
                src_path=meta_path,
                current_repo_slug=current_repo_slug,
            ),
        )
        for ref in depends_on
    ]


def _issue_ids_for_dep_node(graph: SpecGraph, node_id: str) -> list[str]:
    node = graph.nodes_by_id.get(node_id)
    if node is None:
        raise RuntimeError(f"Node not found: {node_id}")
    if node.kind == "issue":
        return [node.id]
    if node.kind == "epic":
        return sorted(
            [n.id for n in graph.nodes_by_id.values() if n.kind == "issue" and n.epic_id == node.id],
            key=deps_node_sort_key,
        )
    if node.kind == "initiative":
        return sorted(
            [n.id for n in graph.nodes_by_id.values() if n.kind == "issue" and n.initiative_id == node.id],
            key=deps_node_sort_key,
        )
    raise RuntimeError(f"Unsupported dependency node type: {node.kind} ({node_id})")


def load_issue_depends_on_map(specdock_dir: Path, graph: SpecGraph) -> DepsTopologyLoadResult:
    current_repo_slug = _resolve_current_repo_slug(specdock_dir)
    dep_node_ids = sorted(
        [node_id for node_id, node in graph.nodes_by_id.items() if node.kind in ("initiative", "epic", "issue")],
        key=deps_node_sort_key,
    )
    issue_ids = sorted(
        [node_id for node_id, node in graph.nodes_by_id.items() if node.kind == "issue"],
        key=deps_node_sort_key,
    )
    issue_depends_on: dict[str, set[str]] = {issue_id: set() for issue_id in issue_ids}

    warning_codes: list[str] = []
    warned_empty_refs: set[tuple[str, str]] = set()

    for src_id in dep_node_ids:
        src_issue_ids = _issue_ids_for_dep_node(graph, src_id)
        if not src_issue_ids:
            continue
        src_node = graph.nodes_by_id[src_id]
        meta_path = src_node.path / ".meta.json"
        direct_dep_node_ids = _resolved_direct_depends_on(
            graph,
            src_id,
            current_repo_slug=current_repo_slug,
        )

        for dep_node_id in direct_dep_node_ids:
            dep_issue_ids = _issue_ids_for_dep_node(graph, dep_node_id)
            if not dep_issue_ids:
                key = (src_id, dep_node_id)
                if key not in warned_empty_refs:
                    warned_empty_refs.add(key)
                    if "deps_ref_expanded_to_empty" not in warning_codes:
                        warning_codes.append("deps_ref_expanded_to_empty")
                continue

            for src_issue_id in src_issue_ids:
                for dep_issue_id in dep_issue_ids:
                    if dep_issue_id == src_issue_id:
                        raise RuntimeError(
                            "Invalid dependency: self edge produced: "
                            f"{src_issue_id} depends_on={dep_node_id} (in {meta_path})"
                        )
                    issue_depends_on[src_issue_id].add(dep_issue_id)

    compiled = {
        issue_id: sorted(list(issue_depends_on.get(issue_id, set())), key=deps_node_sort_key)
        for issue_id in issue_ids
    }
    return DepsTopologyLoadResult(issue_depends_on_map=compiled, warnings=warning_codes)
