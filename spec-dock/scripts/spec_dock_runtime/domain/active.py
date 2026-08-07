from __future__ import annotations

import contextlib
import re

from spec_dock_runtime.domain.ids import find_existing_id_by_num, parse_id
from spec_dock_runtime.domain.models import BranchDecision, SpecGraph, SpecNode

# Branch inference helpers (best-effort):
# - Prefer explicit ids embedded in branch names.
# - Fallback to GitHub issue numbers found in branch text.
_ID_IN_TEXT_RE = re.compile(r"(?<![a-z0-9])(?P<id>(?:init|epic|iss)(?:-local)?-[0-9]+)(?![a-z0-9])")
_HASH_ISSUE_IN_TEXT_RE = re.compile(r"#(?P<num>[0-9]+)\b")
_KEYWORD_ISSUE_IN_TEXT_RE = re.compile(r"(?i)(?:issue|gh)[-_]?(?P<num>[0-9]+)\b")
_LEADING_NUMBER_IN_TEXT_RE = re.compile(r"^(?P<num>[0-9]+)[-_].+")


def _normalize_repo_slug_value(slug: str | None) -> str | None:
    text = str(slug or "").strip().lower()
    if not text:
        return None
    owner, sep, repo = text.partition("/")
    if not sep or not owner or not repo:
        return None
    return f"{owner}/{repo}"


def _normalize_repo_slug(owner: str | None, repo: str | None) -> str | None:
    normalized_owner = str(owner or "").strip().lower()
    normalized_repo = str(repo or "").strip().lower()
    if not normalized_owner or not normalized_repo:
        return None
    return f"{normalized_owner}/{normalized_repo}"


def _effective_repo_slug(node: SpecNode, *, current_repo_slug: str | None) -> str | None:
    return _normalize_repo_slug(node.github_repo_owner, node.github_repo_name) or current_repo_slug


def resolve_branch_decision(node: SpecNode, *, candidate_is_valid: bool = True) -> BranchDecision:
    candidate = f"{node.id}-{node.slug}"
    fallback = node.id
    warnings: list[str] = []

    if not candidate.isascii():
        warnings.append("id-slug is non-ascii; fallback to id")
        return BranchDecision(desired=fallback, candidates=(candidate, fallback), warnings=tuple(warnings))

    if not candidate_is_valid:
        warnings.append("id-slug is invalid ref; fallback to id")
        return BranchDecision(desired=fallback, candidates=(candidate, fallback), warnings=tuple(warnings))

    return BranchDecision(desired=candidate, candidates=(candidate, fallback), warnings=tuple(warnings))


def infer_active_node_from_branch(
    graph: SpecGraph,
    *,
    branch: str,
    current_repo_slug: str | None = None,
) -> tuple[SpecNode | None, str | None]:
    s = branch.strip().lower()
    if not s:
        return (None, None)
    normalized_current_repo_slug = _normalize_repo_slug_value(current_repo_slug)

    id_candidates: list[str] = []
    for match in _ID_IN_TEXT_RE.finditer(s):
        raw = match.group("id")
        try:
            prefix, is_local, num = parse_id(raw)
        except RuntimeError:
            continue
        existing = find_existing_id_by_num(graph.nodes_by_id, prefix=prefix, num=num, local=is_local)
        if existing:
            id_candidates.append(existing)

    id_candidates = sorted(set(id_candidates))
    if len(id_candidates) == 1:
        node = graph.nodes_by_id.get(id_candidates[0])
        if node is not None and node.kind in ("initiative", "epic", "issue"):
            return (node, f"matched id in branch: {node.id}")
    if len(id_candidates) > 1:
        by_prefix: dict[str, list[str]] = {"iss": [], "epic": [], "init": []}
        for node_id in id_candidates:
            try:
                prefix, _, _ = parse_id(node_id)
            except RuntimeError:
                continue
            if prefix in by_prefix:
                by_prefix[prefix].append(node_id)

        for prefix in ("iss", "epic", "init"):
            if len(by_prefix[prefix]) == 1:
                chosen_id = by_prefix[prefix][0]
                chosen = graph.nodes_by_id.get(chosen_id)
                if chosen is not None:
                    return (chosen, f"matched id in branch: {chosen.id} (picked most specific)")
            if len(by_prefix[prefix]) > 1:
                ids = ", ".join(sorted(by_prefix[prefix]))
                return (None, f"ambiguous {prefix} ids in branch: {ids}")

        return (None, f"ambiguous ids in branch: {', '.join(id_candidates)}")

    leaf = s.split("/")[-1]
    nums: set[int] = set()

    for match in _HASH_ISSUE_IN_TEXT_RE.finditer(s):
        try:
            nums.add(int(match.group("num")))
        except (TypeError, ValueError):
            continue
    for match in _KEYWORD_ISSUE_IN_TEXT_RE.finditer(s):
        try:
            nums.add(int(match.group("num")))
        except (TypeError, ValueError):
            continue
    leading = _LEADING_NUMBER_IN_TEXT_RE.match(leaf)
    if leading:
        with contextlib.suppress(TypeError, ValueError):
            nums.add(int(leading.group("num")))

    if not nums:
        return (None, None)

    matches = [
        node
        for node in graph.nodes_by_id.values()
        if node.kind in ("initiative", "epic", "issue") and node.github_issue_number in nums
    ]
    if normalized_current_repo_slug is not None:
        current_repo_matches = [
            node
            for node in matches
            if _effective_repo_slug(node, current_repo_slug=normalized_current_repo_slug)
            == normalized_current_repo_slug
        ]
        if len(current_repo_matches) == 1:
            node = current_repo_matches[0]
            return (node, f"matched github.issue_number={node.github_issue_number} from branch")
        if len(current_repo_matches) > 1:
            ids = ", ".join(sorted(f"{node.kind}:{node.id}" for node in current_repo_matches))
            return (
                None,
                f"ambiguous github issue numbers {sorted(nums)} in current repo scope ({normalized_current_repo_slug}): {ids}",
            )
        if matches:
            ids = ", ".join(sorted(f"{node.kind}:{node.id}" for node in matches))
            return (
                None,
                (
                    "no current-repo matches for github issue numbers "
                    f"{sorted(nums)} in scope ({normalized_current_repo_slug}); refusing foreign fallback: {ids}"
                ),
            )
    if len(matches) == 1:
        node = matches[0]
        return (node, f"matched github.issue_number={node.github_issue_number} from branch")
    if not matches:
        return (None, f"no node matches github issue numbers {sorted(nums)}")
    ids = ", ".join(sorted(f"{node.kind}:{node.id}" for node in matches))
    return (None, f"ambiguous github issue numbers {sorted(nums)}: {ids}")
