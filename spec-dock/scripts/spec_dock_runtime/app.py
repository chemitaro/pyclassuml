#!/usr/bin/env python3
"""
spec-dock runtime script (repo-local).

This script is installed into a repository by `uvx spec-dock init/update` as:

  `spec-dock/scripts/spec-dock`

It performs day-to-day operations without requiring `uvx` at runtime:
- Create nodes: initiative / epic / issue / adr
- Manage the active pointers (symlinks + context-pack)
- Generate derived state (`spec-dock/.agent/index.json`, `spec-dock/.agent/tree.json`)
- Validate the spec tree structure

Design goals:
- Keep dependencies minimal (stdlib only).
- Use local-only by default for `new initiative`/`new epic`.
- Keep GitHub-default behavior for `new issue` (opt out with `--no-github`).
- `sync` reads GitHub issue state by default; use `sync --no-github` only for cache/local opt-out.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cli.bootstrap import build_runtime as _cli_build_runtime
from .cli.dispatch import dispatch as _cli_dispatch
from .cli.parser import build_parser as _cli_build_parser
from .cli.registry import build_registry as _cli_build_registry
from .application.contracts import CheckDepsRequest as _CheckDepsRequest
from .application.contracts import ClearActiveRequest as _ClearActiveRequest
from .application.contracts import CreateDiscussionDocRequest as _CreateDiscussionDocRequest
from .application.contracts import CreateNodeRequest as _CreateNodeRequest
from .application.contracts import ImportNodeRequest as _ImportNodeRequest
from .application.contracts import SetActiveRequest as _SetActiveRequest
from .application.contracts import ShowActiveRequest as _ShowActiveRequest
from .application.contracts import SyncRequest as _SyncRequest
from .application.contracts import TargetRef as _TargetRef
from .application.contracts import ValidateTreeRequest as _ValidateTreeRequest
from .github import (
    _ensure_gh_available,
    _gh_issue_create,
    _gh_issue_index,
    _gh_issue_view_minimal,
)
from .infra.git_cli import origin_github_repo_slug as _origin_github_repo_slug
from .domain.models import SpecGraph, SpecNodeSeed
from .domain.tree import build_graph as _domain_build_graph
from .domain.validation import (
    validate_graph_and_deps as _domain_validate_graph_and_deps,
    validate_github_issue_numbers_unique as _domain_validate_github_issue_numbers_unique,
)
from .ids import (
    _deps_node_sort_key,
    _find_existing_id_by_num,
    _format_id,
    _normalize_local_id_input,
    _parse_id,
    _resolve_id_input,
    _resolve_input_title_and_slug,
    _slugify,
    _validate_input_slug_kebab,
)
from .io_json import _load_json, _now_iso, _try_make_readonly, _warn, _write_json
from .presentation.cli_text import render_deps_check_text as _render_deps_check_text
from .presentation.cli_text import render_active_clear_text as _render_active_clear_text
from .presentation.cli_text import render_new_doc_text as _render_new_doc_text
from .presentation.cli_text import render_new_node_text as _render_new_node_text
from .presentation.cli_text import render_import_text as _render_import_text
from .presentation.cli_text import render_active_set_text as _render_active_set_text
from .presentation.cli_text import render_active_show_text as _render_active_show_text
from .presentation.cli_text import render_sync_text as _render_sync_text
from .presentation.cli_text import render_validate_text as _render_validate_text
from .presentation.json_state import render_deps_check_json as _render_deps_check_json
from .render_md import _render_dashboard_md, _render_deps_disabled_dashboard_md
from .render_puml import (
    _deps_disabled_error_text,
    _render_deps_disabled_deps_issues_puml,
    _render_deps_disabled_tree_puml,
    _render_deps_issues_puml,
    _render_tree_ready_board_puml,
)

_SPEC_DOCK_DIRNAME = "spec-dock"

_INITIATIVES_DIRNAME = "initiatives"
_ACTIVE_DIRNAME = "active"
_AGENT_DIRNAME = ".agent"
_LEGACY_WORK_DIRNAME = ".work"
_META_FILENAME = ".meta.json"
_LEGACY_META_FILENAME = "meta.json"

_DEFAULT_ID_WIDTH = 5  # minimum width for zero-padded ids (e.g. `iss-00123`)

_ID_RE = re.compile(r"^(?P<prefix>init|epic|iss|adr)(?:-(?P<local>local))?-(?P<num>[0-9]+)$")
_NUM_RE = re.compile(r"^[0-9]+$")
_GH_ISSUE_URL_RE = re.compile(r"/issues/(?P<num>[0-9]+)\b")
_INPUT_TITLE_RE = re.compile(r"^[A-Za-z0-9]+(?: [A-Za-z0-9]+)*$")
_INPUT_SLUG_KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_BLOCKERS_TOP_LIMIT = 5
_TREE_BOARD_BLOCKERS_LABEL_LIMIT = 3
_DASHBOARD_TOP_LIMIT = 10
_DISCUSSION_DOC_TYPES = (
    "adr",
    "disc",
    "research",
    "interview",
    "scratch",
    "draft-requirement",
    "draft-design",
    "draft-plan",
    "note",
)
_DISCUSSION_DOC_FILENAME_RE = re.compile(
    r"^(?P<seq>[0-9]{3})-(?P<doc_type>adr|disc|research|interview|scratch|note)-(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)\.md$"
)

# Branch name parsing helpers (best-effort):
# - Prefer explicit ids embedded in branch names (e.g. `feature/iss-00123-foo`).
# - Fallback to GitHub issue numbers embedded in branch names (e.g. `123-foo`, `issue-123-foo`, `#123`).
_ID_IN_TEXT_RE = re.compile(r"(?<![a-z0-9])(?P<id>(?:init|epic|iss)(?:-local)?-[0-9]+)(?![a-z0-9])")
_HASH_ISSUE_IN_TEXT_RE = re.compile(r"#(?P<num>[0-9]+)\b")
_KEYWORD_ISSUE_IN_TEXT_RE = re.compile(r"(?i)(?:issue|gh)[-_]?(?P<num>[0-9]+)\b")
_LEADING_NUMBER_IN_TEXT_RE = re.compile(r"^(?P<num>[0-9]+)[-_].+")


@dataclass(frozen=True)
class _Node:
    """In-memory representation of a spec node loaded from meta JSON."""

    type: str
    id: str
    title: str
    slug: str
    path: Path
    meta_path: Path
    parent_id: str | None
    initiative_id: str | None
    epic_id: str | None
    github_issue_number: int | None


@dataclass(frozen=True)
class _BranchDecision:
    """Resolved branch naming decision for active set."""

    desired: str
    candidates: tuple[str, str]
    warnings: tuple[str, ...]


def _find_specdock_dir() -> Path:
    """Locate the `spec-dock/` directory for the current repository.

    Strategy:
    1) Prefer the invoked script location: `<repo>/spec-dock/scripts/spec-dock`
       (`sys.argv[0]`) so module relocation keeps behavior.
    2) Fallback to this module file location.
    2) Fallback to walking parents from the current working directory.
    """
    # Prefer invoked script location: <repo>/spec-dock/scripts/spec-dock
    # This stays correct even when implementation moves into a package module.
    argv0 = str(sys.argv[0]) if sys.argv else ""
    script_path = Path(argv0).resolve() if argv0 else Path(__file__).resolve()
    candidate = script_path.parent.parent
    if candidate.is_dir() and candidate.name == _SPEC_DOCK_DIRNAME:
        return candidate

    # Fallback for direct module execution:
    # <repo>/spec-dock/scripts/spec_dock_runtime/app.py -> parent.parent.parent
    module_path = Path(__file__).resolve()
    candidate_from_module = module_path.parent.parent.parent
    if candidate_from_module.is_dir() and candidate_from_module.name == _SPEC_DOCK_DIRNAME:
        return candidate_from_module

    # Fallback: search from cwd upwards.
    cur = Path.cwd().resolve()
    # Keep a hard cap to avoid pathological loops if something goes wrong.
    for _ in range(50):
        sd = cur / _SPEC_DOCK_DIRNAME
        if sd.is_dir():
            return sd
        if cur.parent == cur:
            break
        cur = cur.parent

    raise RuntimeError(f"'{_SPEC_DOCK_DIRNAME}' not found. Run 'uvx ... spec-dock init' first.")


def _find_repo_root_for_legacy_doctor() -> Path:
    """Locate a repo root that still contains only the legacy hidden workspace."""
    cur = Path.cwd().resolve()
    for _ in range(50):
        legacy_dir = cur / ".spec-dock"
        specdock_dir = cur / _SPEC_DOCK_DIRNAME
        if legacy_dir.is_dir() and not specdock_dir.exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    raise RuntimeError(f"'{_SPEC_DOCK_DIRNAME}' not found. Run 'uvx ... spec-dock init' first.")


def _initiatives_root(specdock_dir: Path) -> Path:
    """Return the spec tree root directory (`spec-dock/initiatives/`)."""
    return specdock_dir / _INITIATIVES_DIRNAME


def _meta_path(node_dir: Path) -> Path:
    """Return canonical meta path for a node directory."""
    return node_dir / _META_FILENAME


def _iter_node_meta_paths(initiatives_root: Path) -> list[Path]:
    """Collect canonical node meta paths (`.meta.json`) under initiatives root."""
    return sorted(initiatives_root.rglob(_META_FILENAME), key=lambda p: p.as_posix())


def _find_legacy_meta_paths(initiatives_root: Path) -> list[Path]:
    """Collect unsupported legacy meta paths (`meta.json`) under initiatives root."""
    return sorted(initiatives_root.rglob(_LEGACY_META_FILENAME), key=lambda p: p.as_posix())


def _ensure_no_legacy_meta_json(specdock_dir: Path) -> None:
    """Fail fast when legacy `meta.json` files are detected."""
    initiatives_root = _initiatives_root(specdock_dir)
    if not initiatives_root.exists():
        return
    legacy_paths = _find_legacy_meta_paths(initiatives_root)
    if not legacy_paths:
        return
    listed = "\n".join(f"- {p}" for p in legacy_paths)
    raise RuntimeError(
        "Unsupported legacy meta.json detected. Rename legacy files to '.meta.json' and retry:\n"
        f"{listed}"
    )


def _next_id(
    specdock_dir: Path,
    prefix: str,
    *,
    local: bool = False,
    nodes: dict[str, _Node] | None = None,
) -> str:
    """Compute the next available id for a prefix by scanning existing nodes.

    Notes:
    - When `local=True`, only ids in the `*-local-*` namespace are considered.
    - When `local=False`, only ids without `-local-` are considered.
    """
    if nodes is None:
        nodes = _scan_nodes(specdock_dir)

    max_num = 0
    for node in nodes.values():
        node_id = node.id
        try:
            parsed_prefix, is_local, num = _parse_id(node_id)
        except RuntimeError:
            continue
        if parsed_prefix != prefix:
            continue
        if is_local != local:
            continue
        max_num = max(max_num, num)

    if prefix == "adr":
        initiatives_root = _initiatives_root(specdock_dir)
        # ADRs are files, not nodes with `.meta.json`. Scan filenames as a fallback.
        for adr_path in initiatives_root.rglob("discussions/adr-*.md"):
            m = re.search(r"\b(adr(?:-local)?-[0-9]+)\b", adr_path.stem)
            if not m:
                continue
            try:
                _, is_local, num = _parse_id(m.group(1))
            except RuntimeError:
                continue
            if is_local != local:
                continue
            max_num = max(max_num, num)

    return _format_id(prefix, max_num + 1, local=local)


def _scan_nodes(specdock_dir: Path) -> dict[str, _Node]:
    """Scan node meta into an id→node map based on canonical `.meta.json` only."""
    initiatives_root = _initiatives_root(specdock_dir)
    nodes: dict[str, _Node] = {}
    if not initiatives_root.exists():
        return nodes

    for meta_path in _iter_node_meta_paths(initiatives_root):
        meta = _load_json(meta_path)
        if not isinstance(meta, dict):
            raise RuntimeError(
                f"Invalid .meta.json (expected object): {meta_path} (got {type(meta).__name__})"
            )
        node_type = str(meta.get("type", "")).strip()
        node_id = str(meta.get("id", "")).strip()
        title = str(meta.get("title", "")).strip()
        slug = str(meta.get("slug", "")).strip()
        if not node_type or not node_id:
            continue
        if node_id in nodes:
            raise RuntimeError(f"Duplicate id detected: {node_id} ({meta_path})")

        parent_id = meta.get("parent_id") or None
        initiative_id = meta.get("initiative_id") or None
        epic_id = meta.get("epic_id") or None

        github_issue_number: int | None = None
        github = meta.get("github")
        if isinstance(github, dict) and github.get("issue_number") is not None:
            try:
                github_issue_number = int(github.get("issue_number"))
            except (TypeError, ValueError) as e:
                raise RuntimeError(f"Invalid github.issue_number in {meta_path}: {github.get('issue_number')}") from e

        # Note: `path` points to the directory that contains this node's meta file.
        nodes[node_id] = _Node(
            type=node_type,
            id=node_id,
            title=title,
            slug=slug,
            path=meta_path.parent,
            meta_path=meta_path,
            parent_id=str(parent_id) if parent_id else None,
            initiative_id=str(initiative_id) if initiative_id else None,
            epic_id=str(epic_id) if epic_id else None,
            github_issue_number=github_issue_number,
        )
    return nodes

def _write_meta(
    dest_dir: Path,
    *,
    node_type: str,
    node_id: str,
    title: str,
    slug: str,
    parent_id: str | None = None,
    initiative_id: str | None = None,
    epic_id: str | None = None,
    github_issue_number: int | None = None,
) -> None:
    """Create a minimal, durable `.meta.json` for a node."""
    meta: dict[str, Any] = {
        "schema_version": 1,
        "type": node_type,
        "id": node_id,
        "title": title,
        "slug": slug,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "parent_id": parent_id,
        "initiative_id": initiative_id,
        "epic_id": epic_id,
        "_spec_dock": {
            "managed": True,
            "do_not_edit": True,
            "edit_via": "spec-dock",
        },
    }
    if github_issue_number is not None:
        meta["github"] = {"issue_number": int(github_issue_number)}
    meta_path = _meta_path(dest_dir)
    _write_json(meta_path, meta)
    readonly_ok, readonly_err = _try_make_readonly(meta_path)
    if not readonly_ok:
        reason = readonly_err or "unknown error"
        _warn(f"readonly_lock_failed: {meta_path} ({reason})")


def _unlink_any(path: Path) -> None:
    """Delete a file/symlink/directory if it exists (best-effort)."""
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
        return
    if path.is_dir():
        shutil.rmtree(path)


def _write_pathfile(active_dir: Path, name: str, target: Path) -> None:
    """Write a `.path` fallback file when symlinks are not available."""
    pathfile = active_dir / f"{name}.path"
    rel_target = os.path.relpath(target, start=active_dir)
    pathfile.write_text(rel_target + "\n", encoding="utf-8")


def _load_active_manifest(specdock_dir: Path) -> dict[str, Any] | None:
    """Load SSOT active manifest (best-effort migrate legacy `.work/*`)."""
    agent_dir = specdock_dir / _AGENT_DIRNAME
    legacy_work_dir = specdock_dir / _LEGACY_WORK_DIRNAME
    active_path = agent_dir / "active.json"
    legacy_active_path = legacy_work_dir / "active.json"
    legacy_current_path = legacy_work_dir / "current.json"

    if active_path.exists():
        current = _load_json(active_path)
        return current if isinstance(current, dict) else None

    if legacy_active_path.exists():
        current = _load_json(legacy_active_path)
        if isinstance(current, dict):
            _write_json(active_path, current)
        legacy_active_path.unlink(missing_ok=True)
        return current if isinstance(current, dict) else None

    if legacy_current_path.exists():
        current = _load_json(legacy_current_path)
        if isinstance(current, dict):
            _write_json(active_path, current)
        legacy_current_path.unlink(missing_ok=True)
        return current if isinstance(current, dict) else None

    return None


def _load_active_manifest_no_migrate(specdock_dir: Path) -> dict[str, Any] | None:
    """Load active manifest without migrating legacy `.work/*` files.

    This is used by side-effect-sensitive commands (e.g. `import`) that must not
    create/update `spec-dock/.agent/active.json` as a byproduct of reading active.
    """
    agent_dir = specdock_dir / _AGENT_DIRNAME
    legacy_work_dir = specdock_dir / _LEGACY_WORK_DIRNAME
    candidates = (
        agent_dir / "active.json",
        legacy_work_dir / "active.json",
        legacy_work_dir / "current.json",
    )
    for p in candidates:
        if not p.exists():
            continue
        current = _load_json(p)
        return current if isinstance(current, dict) else None
    return None


def _active_placeholder_dir(specdock_dir: Path, layer: str) -> Path:
    """Return the placeholder directory for `layer` (initiative/epic/issue)."""
    p = specdock_dir / "system" / "active-none" / layer
    if not p.exists():
        raise RuntimeError(f"Missing placeholder directory: {p} (run 'spec-dock update')")
    return p


def _active_entry(repo_root: Path, node: _Node | None) -> dict[str, str] | None:
    """Return an `{id,path}` entry for an active manifest, or None."""
    if node is None:
        return None
    return {"id": node.id, "path": node.path.relative_to(repo_root).as_posix()}


def _write_active_manifest(specdock_dir: Path, *, initiative: _Node | None, epic: _Node | None, issue: _Node | None) -> dict[str, Any]:
    """Write SSOT active manifest (schema v2) and prune legacy files."""
    repo_root = specdock_dir.parent
    agent_dir = specdock_dir / _AGENT_DIRNAME
    legacy_work_dir = specdock_dir / _LEGACY_WORK_DIRNAME
    agent_dir.mkdir(parents=True, exist_ok=True)

    current = {
        "schema_version": 2,
        "updated_at": _now_iso(),
        "initiative": _active_entry(repo_root, initiative),
        "epic": _active_entry(repo_root, epic),
        "issue": _active_entry(repo_root, issue),
    }
    _write_json(agent_dir / "active.json", current)

    # Prune legacy SSOT files to avoid duplicate manifests in older directories.
    (legacy_work_dir / "active.json").unlink(missing_ok=True)
    (legacy_work_dir / "current.json").unlink(missing_ok=True)
    return current


def _active_entry_id(entry: Any) -> str | None:
    if isinstance(entry, dict):
        v = entry.get("id")
        return str(v) if isinstance(v, str) and v.strip() else None
    return None


def _active_entry_path(repo_root: Path, entry: Any) -> Path | None:
    if isinstance(entry, dict):
        v = entry.get("path")
        if isinstance(v, str) and v.strip():
            p = repo_root / v
            if p.exists():
                return p
    return None


def _render_context_pack(current: dict[str, Any] | None) -> str:
    """Render `spec-dock/active/context-pack.md` based on `current`."""
    init_entry = current.get("initiative") if isinstance(current, dict) else None
    epic_entry = current.get("epic") if isinstance(current, dict) else None
    issue_entry = current.get("issue") if isinstance(current, dict) else None

    init_id = _active_entry_id(init_entry) or "(none)"
    epic_id = _active_entry_id(epic_entry) or "(none)"
    issue_id = _active_entry_id(issue_entry) or "(none)"

    has_init = isinstance(init_entry, dict)
    has_epic = isinstance(epic_entry, dict)
    has_issue = isinstance(issue_entry, dict)

    lines: list[str] = []
    lines.append("# Context Pack (generated)")
    lines.append("")
    lines.append("## Active")
    lines.append(f"- initiative: {init_id}")
    lines.append(f"- epic: {epic_id}")
    lines.append(f"- issue: {issue_id}")
    lines.append("")
    lines.append("## Generated state")
    lines.append("- entry: `spec-dock/.agent/active.json`")
    lines.append("- default working set: `spec-dock/.agent/index.json`")
    lines.append("- default dependency view: `spec-dock/.agent/deps-issues.json`")
    lines.append("- escalation only: `spec-dock/.agent/index-all.json`")
    lines.append("- human-oriented tree: `spec-dock/.agent/tree.json`")
    lines.append("")
    lines.append("## Read order")
    lines.append("- Start with `spec-dock/.agent/active.json`.")
    lines.append("- For normal work, read `spec-dock/.agent/index.json` and `spec-dock/.agent/deps-issues.json`.")
    lines.append("- Read `spec-dock/.agent/index-all.json` only when full-history context is needed.")
    lines.append(
        "- `spec-dock/active/context-pack.md` is human guidance that mirrors this contract; it is not the sole source of truth."
    )
    lines.append("- Then follow the active documents:")
    if has_init:
        lines.append("- `spec-dock/active/initiative/requirement.md`")
        lines.append("- `spec-dock/active/initiative/design.md`")
        lines.append("- `spec-dock/active/initiative/plan.md`")
    else:
        lines.append("- `spec-dock/active/initiative/README.md`")
    if has_epic:
        lines.append("- `spec-dock/active/epic/requirement.md`")
        lines.append("- `spec-dock/active/epic/design.md`")
        lines.append("- `spec-dock/active/epic/plan.md`")
    else:
        lines.append("- `spec-dock/active/epic/README.md`")
    if has_issue:
        lines.append("- `spec-dock/active/issue/requirement.md`")
        lines.append("- `spec-dock/active/issue/design.md`")
        lines.append("- `spec-dock/active/issue/plan.md`")
        lines.append("- `spec-dock/active/issue/report.md`")
    else:
        lines.append("- `spec-dock/active/issue/README.md`")
    lines.append("")
    lines.append("## Commands")
    lines.append("- state (github default): `./spec-dock/scripts/spec-dock sync`")
    lines.append("- state (cache/local opt-out): `./spec-dock/scripts/spec-dock sync --no-github`")
    lines.append("- validate: `./spec-dock/scripts/spec-dock validate`")
    lines.append("")

    return "\n".join(lines) + "\n"


def _apply_active_pointers(specdock_dir: Path, current: dict[str, Any] | None) -> None:
    """Update `spec-dock/active/*` pointers (symlink or `.path`) and context-pack."""
    repo_root = specdock_dir.parent
    active_dir = specdock_dir / _ACTIVE_DIRNAME
    active_dir.mkdir(parents=True, exist_ok=True)

    # Remove existing pointers (symlink or fallback pathfiles).
    for name in ("initiative", "epic", "issue", "context-pack.md", "initiative.path", "epic.path", "issue.path"):
        _unlink_any(active_dir / name)

    def target_dir(layer: str) -> Path:
        entry = current.get(layer) if isinstance(current, dict) else None
        return _active_entry_path(repo_root, entry) or _active_placeholder_dir(specdock_dir, layer)

    def symlink(name: str, target: Path) -> None:
        """Create an active pointer under `spec-dock/active/` (symlink or fallback)."""
        link = active_dir / name
        rel_target = os.path.relpath(target, start=active_dir)
        try:
            # Prefer symlinks: fixed entry points for both humans and agents.
            os.symlink(rel_target, link)
        except OSError:
            # Fallback: keep it readable even in environments where symlinks are restricted.
            _write_pathfile(active_dir, name, target)

    symlink("initiative", target_dir("initiative"))
    symlink("epic", target_dir("epic"))
    symlink("issue", target_dir("issue"))

    (active_dir / "context-pack.md").write_text(_render_context_pack(current), encoding="utf-8")


def _patch_agent_state_active_fields(specdock_dir: Path, current: dict[str, Any]) -> None:
    """Best-effort: patch cached derived state with the latest `active`."""
    agent_dir = specdock_dir / _AGENT_DIRNAME
    for name in ("index-all.json", "tree-all.json", "index.json", "tree.json"):
        path = agent_dir / name
        if not path.is_file():
            continue
        try:
            data = _load_json(path)
        except RuntimeError as e:
            _warn(f"active_patch_failed: failed to read {path}: {e}")
            continue
        if not isinstance(data, dict):
            _warn(f"active_patch_failed: invalid JSON shape (expected object): {path}")
            continue
        data["active"] = current
        try:
            _write_json(path, data)
        except OSError as e:
            _warn(f"active_patch_failed: failed to write {path}: {e}")


def _ensure_git_available() -> None:
    """Raise if `git` is not available in PATH."""
    if shutil.which("git") is None:
        raise RuntimeError("'git' CLI not found. Install Git, or disable git-dependent operations.")


def _require_clean_working_tree(repo_root: Path) -> None:
    """Raise if there are uncommitted/untracked changes (safety-first)."""
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


def _gh_issue_checkout(repo_root: Path, *, issue_number: int) -> None:
    """Create/switch to the branch for the given GitHub issue number via `gh`."""
    _ensure_gh_available()
    _require_clean_working_tree(repo_root)

    cmd1 = ["gh", "issue", "checkout", str(issue_number)]
    try:
        subprocess.run(cmd1, cwd=str(repo_root), capture_output=True, text=True, check=True)
        return
    except subprocess.CalledProcessError as e1:
        # Fallback: some `gh` versions support `issue develop`.
        cmd2 = ["gh", "issue", "develop", str(issue_number), "--checkout"]
        try:
            subprocess.run(cmd2, cwd=str(repo_root), capture_output=True, text=True, check=True)
            return
        except subprocess.CalledProcessError as e2:
            raise RuntimeError(
                "Failed to checkout issue branch via gh.\n"
                f"- tried: {' '.join(cmd1)}\n"
                f"  stderr: {(e1.stderr or '').strip()}\n"
                f"- tried: {' '.join(cmd2)}\n"
                f"  stderr: {(e2.stderr or '').strip()}"
            ) from e2


def _git_current_branch(repo_root: Path) -> str:
    """Return current branch name (`HEAD` when detached)."""
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
    return (p.stdout or "").strip()


def _git_local_branch_exists(repo_root: Path, *, branch: str) -> bool:
    """Return True when local branch `branch` exists."""
    _ensure_git_available()
    p = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return p.returncode == 0


def _git_checkout_branch(repo_root: Path, *, branch: str) -> None:
    """Checkout a local branch."""
    _ensure_git_available()
    cmd = ["git", "checkout", branch]
    try:
        subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"git failed: {' '.join(cmd)}\n{(e.stderr or '').strip()}") from e


def _git_check_ref_format_branch(repo_root: Path, *, branch: str) -> bool:
    """Return True when `branch` is valid for `git check-ref-format --branch`."""
    _ensure_git_available()
    p = subprocess.run(
        ["git", "check-ref-format", "--branch", branch],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return p.returncode == 0


def _resolve_active_set_branch_decision(repo_root: Path, *, node: _Node) -> _BranchDecision:
    """Resolve active-set desired branch as `id-slug`, falling back to `id` when needed."""
    candidate = f"{node.id}-{node.slug}"
    fallback = node.id
    warnings: list[str] = []

    if not candidate.isascii():
        warnings.append("id-slug is non-ascii; fallback to id")
        return _BranchDecision(desired=fallback, candidates=(candidate, fallback), warnings=tuple(warnings))
    if not _git_check_ref_format_branch(repo_root, branch=candidate):
        warnings.append("id-slug is invalid ref; fallback to id")
        return _BranchDecision(desired=fallback, candidates=(candidate, fallback), warnings=tuple(warnings))
    return _BranchDecision(desired=candidate, candidates=(candidate, fallback), warnings=tuple(warnings))


def _ensure_active_set_branch_name(repo_root: Path, *, desired: str) -> None:
    """Ensure current branch matches `desired` (create when missing)."""
    current = _git_current_branch(repo_root)
    if current == desired:
        return

    if _git_local_branch_exists(repo_root, branch=desired):
        cmd = ["git", "checkout", desired]
    else:
        cmd = ["git", "checkout", "-b", desired]
    try:
        subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"git failed: {' '.join(cmd)}\n{(e.stderr or '').strip()}") from e


def _select_active_from_node(nodes: dict[str, _Node], node: _Node) -> tuple[_Node | None, _Node | None, _Node | None]:
    """Return (initiative, epic, issue) selection derived from a node."""
    if node.type == "initiative":
        return (node, None, None)
    if node.type == "epic":
        if not node.initiative_id:
            raise RuntimeError(f"Epic meta missing initiative_id: {node.id}")
        initiative = nodes.get(node.initiative_id)
        if not initiative or initiative.type != "initiative":
            raise RuntimeError(f"Initiative not found: {node.initiative_id}")
        return (initiative, node, None)
    if node.type == "issue":
        if not node.epic_id or not node.initiative_id:
            raise RuntimeError(f"Issue meta missing epic_id/initiative_id: {node.id}")
        epic = nodes.get(node.epic_id)
        initiative = nodes.get(node.initiative_id)
        if not epic or epic.type != "epic":
            raise RuntimeError(f"Epic not found: {node.epic_id}")
        if not initiative or initiative.type != "initiative":
            raise RuntimeError(f"Initiative not found: {node.initiative_id}")
        return (initiative, epic, node)

    raise RuntimeError(f"Unsupported node type for active: {node.type} ({node.id})")


def _find_node_by_github_issue_number(nodes: dict[str, _Node], *, issue_number: int) -> _Node:
    """Find a unique node (initiative/epic/issue) by `github.issue_number`."""
    matches = [
        n
        for n in nodes.values()
        if n.github_issue_number == issue_number and n.type in ("initiative", "epic", "issue")
    ]
    if not matches:
        raise RuntimeError(f"No node found for github.issue_number={issue_number}. Create/link the node first.")
    if len(matches) > 1:
        ids = ", ".join(sorted(f"{m.type}:{m.id}" for m in matches))
        raise RuntimeError(f"Ambiguous github.issue_number={issue_number}: {ids}")
    return matches[0]


def _find_node_by_github_issue_number_or_none(nodes: dict[str, _Node], *, issue_number: int) -> _Node | None:
    """Best-effort resolver for github.issue_number; returns None when not found."""
    try:
        return _find_node_by_github_issue_number(nodes, issue_number=issue_number)
    except RuntimeError as e:
        msg = str(e)
        if msg.startswith(f"No node found for github.issue_number={issue_number}"):
            return None
        raise


def _parse_github_issue_target(target: str) -> int:
    """Parse import target into a GitHub issue number (`123` / `#123` / URL)."""
    raw = target.strip()
    if not raw:
        raise RuntimeError("target is required")

    m = _GH_ISSUE_URL_RE.search(raw)
    if m:
        return int(m.group("num"))

    if raw.startswith("#") and _NUM_RE.fullmatch(raw[1:]):
        return int(raw[1:])

    if _NUM_RE.fullmatch(raw):
        return int(raw)

    raise RuntimeError(
        "Invalid target. Use a GitHub issue number (e.g. 123 / #123 / URL like .../issues/123)."
    )


def _meta_json_path_for_output(node: _Node, *, repo_root: Path | None = None) -> str:
    """Return a stable meta path for diagnostics (repo-relative when possible)."""
    meta_path = node.meta_path
    if repo_root is not None:
        try:
            return meta_path.relative_to(repo_root).as_posix()
        except ValueError:
            pass
    return meta_path.as_posix()


def _linked_github_nodes(
    nodes: dict[str, _Node], *, issue_number: int, repo_root: Path | None = None
) -> list[_Node]:
    """Collect nodes linked to `github.issue_number`, sorted for stable diagnostics."""
    linked = [
        n for n in nodes.values() if n.github_issue_number == issue_number and n.type in ("initiative", "epic", "issue")
    ]
    return sorted(linked, key=lambda n: (n.type, n.id, _meta_json_path_for_output(n, repo_root=repo_root)))


def _format_linked_github_nodes(linked: list[_Node], *, repo_root: Path | None = None) -> str:
    """Format linked nodes for error messages (`type:id (path)` CSV)."""
    return ", ".join(
        f"{n.type}:{n.id} ({_meta_json_path_for_output(n, repo_root=repo_root)})"
        for n in linked
    )


def _ensure_github_issue_not_linked(
    nodes: dict[str, _Node],
    *,
    issue_number: int,
    repo_root: Path | None = None,
) -> None:
    """Reject link operations when github.issue_number is already linked by any node type."""
    linked = _linked_github_nodes(nodes, issue_number=issue_number, repo_root=repo_root)
    if not linked:
        return
    found = _format_linked_github_nodes(linked, repo_root=repo_root)
    raise RuntimeError(
        f"github.issue_number={issue_number} is already linked: {found}. "
        "Fix github.issue_number in one of the listed .meta.json files, "
        "or choose a different GitHub issue number (target)."
    )


def _build_graph_from_nodes(nodes: dict[str, _Node]) -> SpecGraph:
    """Map app-layer nodes into pure domain graph."""
    seeds = [
        SpecNodeSeed(
            kind=node.type,
            id=node.id,
            title=node.title,
            slug=node.slug,
            path=node.path,
            meta_path=node.meta_path,
            parent_id=node.parent_id,
            initiative_id=node.initiative_id,
            epic_id=node.epic_id,
            github_issue_number=node.github_issue_number,
        )
        for node in nodes.values()
    ]
    return _domain_build_graph(seeds)


def _validate_github_issue_numbers_unique(nodes: dict[str, _Node], *, repo_root: Path | None = None) -> None:
    """Ensure github.issue_number is unique across initiative/epic/issue nodes."""
    graph = _build_graph_from_nodes(nodes)
    _domain_validate_github_issue_numbers_unique(graph, repo_root=repo_root)


def _resolve_active_node(nodes: dict[str, _Node], *, entry: Any, expected_type: str) -> _Node | None:
    """Resolve one active manifest entry to a current node (strict type, width-agnostic id)."""
    node_id = _active_entry_id(entry)
    if not node_id:
        return None
    try:
        prefix, is_local, num = _parse_id(node_id.strip().lower())
    except RuntimeError:
        return None
    expected_prefix = {"initiative": "init", "epic": "epic", "issue": "iss"}[expected_type]
    if prefix != expected_prefix:
        return None
    resolved = _find_existing_id_by_num(nodes, prefix=prefix, num=num, local=is_local)
    if not resolved:
        return None
    node = nodes.get(resolved)
    if not node or node.type != expected_type:
        return None
    return node


def _resolve_parent_from_active(specdock_dir: Path, *, nodes: dict[str, _Node], child_type: str) -> str:
    """Resolve parent id from active manifest for `epic` or `issue` imports."""
    active = _load_active_manifest_no_migrate(specdock_dir)
    if not isinstance(active, dict):
        if child_type == "issue":
            raise RuntimeError("Cannot resolve parent epic from active selection. Pass --epic explicitly.")
        raise RuntimeError("Cannot resolve parent initiative from active selection. Pass --initiative explicitly.")

    active_init = _resolve_active_node(nodes, entry=active.get("initiative"), expected_type="initiative")
    active_epic = _resolve_active_node(nodes, entry=active.get("epic"), expected_type="epic")
    active_issue = _resolve_active_node(nodes, entry=active.get("issue"), expected_type="issue")

    if child_type == "issue":
        if active_epic:
            return active_epic.id
        if active_issue and active_issue.epic_id:
            epic = nodes.get(active_issue.epic_id)
            if epic and epic.type == "epic":
                return epic.id
        raise RuntimeError("Cannot resolve parent epic from active selection. Pass --epic explicitly.")

    if child_type == "epic":
        if active_init:
            return active_init.id
        if active_epic and active_epic.initiative_id:
            initiative = nodes.get(active_epic.initiative_id)
            if initiative and initiative.type == "initiative":
                return initiative.id
        if active_issue and active_issue.initiative_id:
            initiative = nodes.get(active_issue.initiative_id)
            if initiative and initiative.type == "initiative":
                return initiative.id
        raise RuntimeError("Cannot resolve parent initiative from active selection. Pass --initiative explicitly.")

    raise RuntimeError(f"Internal error: unsupported child type for active fallback: {child_type}")


def _git_current_branch_or_none(repo_root: Path) -> str | None:
    """Return the current branch name, or None if unavailable/detached."""
    if shutil.which("git") is None:
        return None
    try:
        p = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return None
    branch = (p.stdout or "").strip()
    if not branch or branch == "HEAD":
        return None
    return branch


@dataclass(frozen=True)
class _IssueStatusResolution:
    """Internal issue status value with an explicit source."""

    status: str
    source: str
    github_payload: dict[str, Any] | None = None


def _load_cached_issue_snapshot(
    specdock_dir: Path,
    *,
    github: bool,
) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    """Return cached issue status/github fields from prior sync artifacts."""
    if github:
        return {}, {}

    agent_dir = specdock_dir / _AGENT_DIRNAME
    state_index_all_path = agent_dir / "index-all.json"
    state_index_todo_path = agent_dir / "index.json"

    cached_index: dict[str, Any] | None = None
    for state_index_path in (state_index_all_path, state_index_todo_path):
        if not state_index_path.is_file():
            continue
        try:
            loaded = _load_json(state_index_path)
        except RuntimeError:
            continue
        if isinstance(loaded, dict):
            cached_index = loaded
            break

    if not isinstance(cached_index, dict):
        return {}, {}

    cached_issue_status_by_id: dict[str, str] = {}
    cached_github_by_id: dict[str, dict[str, Any]] = {}
    raw_nodes = cached_index.get("nodes")
    if not isinstance(raw_nodes, dict):
        return cached_issue_status_by_id, cached_github_by_id

    for node_id, item in raw_nodes.items():
        if not isinstance(node_id, str) or not isinstance(item, dict):
            continue
        raw_status = item.get("status")
        if isinstance(raw_status, str):
            status = raw_status.strip().lower()
            if status in ("done", "open", "unknown"):
                cached_issue_status_by_id[node_id] = status
        raw_github = item.get("github")
        if isinstance(raw_github, dict):
            cached_github_by_id[node_id] = raw_github

    return cached_issue_status_by_id, cached_github_by_id


def _resolve_issue_statuses(
    nodes: dict[str, _Node],
    *,
    github: bool,
    issue_index: dict[int, dict[str, Any]],
    cached_issue_status_by_id: dict[str, str],
) -> dict[str, _IssueStatusResolution]:
    """Resolve issue status values while keeping their source explicit internally."""
    resolved: dict[str, _IssueStatusResolution] = {}
    for node in nodes.values():
        if node.type != "issue":
            continue
        if github and node.github_issue_number is not None:
            gh = issue_index.get(node.github_issue_number)
            if gh:
                status = "done" if str(gh.get("state", "")).upper() == "CLOSED" else "open"
                resolved[node.id] = _IssueStatusResolution(status=status, source="github", github_payload=dict(gh))
                continue
        elif not github:
            cached_status = cached_issue_status_by_id.get(node.id)
            if cached_status is not None:
                resolved[node.id] = _IssueStatusResolution(status=cached_status, source="cache")
                continue
        resolved[node.id] = _IssueStatusResolution(status="unknown", source="unknown")
    return resolved


def _build_progress_map(
    nodes: dict[str, _Node],
    issue_statuses: dict[str, _IssueStatusResolution],
) -> dict[str, dict[str, int]]:
    """Aggregate issue status counts for initiative/epic nodes."""
    progress: dict[str, dict[str, int]] = {}
    for node in nodes.values():
        if node.type in ("initiative", "epic"):
            progress[node.id] = {"total": 0, "done": 0, "open": 0, "unknown": 0}

    for node in nodes.values():
        if node.type != "issue":
            continue
        resolution = issue_statuses.get(node.id, _IssueStatusResolution(status="unknown", source="unknown"))
        for parent in filter(None, (node.epic_id, node.initiative_id)):
            if parent not in progress:
                continue
            progress[parent]["total"] += 1
            progress[parent][resolution.status] += 1

    return progress


def _infer_active_node_from_branch(nodes: dict[str, _Node], *, branch: str) -> tuple[_Node | None, str | None]:
    """Infer a unique node from a branch name (best-effort)."""
    s = branch.strip().lower()
    if not s:
        return (None, None)

    # 1) Prefer explicit node ids embedded in the branch name.
    id_candidates: list[str] = []
    for m in _ID_IN_TEXT_RE.finditer(s):
        raw = m.group("id")
        try:
            prefix, is_local, num = _parse_id(raw)
        except RuntimeError:
            continue
        existing = _find_existing_id_by_num(nodes, prefix=prefix, num=num, local=is_local)
        if existing:
            id_candidates.append(existing)
    id_candidates = sorted(set(id_candidates))
    if len(id_candidates) == 1:
        return (nodes[id_candidates[0]], f"matched id in branch: {id_candidates[0]}")
    if len(id_candidates) > 1:
        # Practical disambiguation:
        # If the branch embeds multiple ids (init → epic → iss), prefer the most specific.
        by_prefix: dict[str, list[str]] = {"iss": [], "epic": [], "init": []}
        for item in id_candidates:
            try:
                p, _, _ = _parse_id(item)
            except RuntimeError:
                continue
            if p in by_prefix:
                by_prefix[p].append(item)

        for p in ("iss", "epic", "init"):
            if len(by_prefix[p]) == 1:
                chosen = by_prefix[p][0]
                return (nodes[chosen], f"matched id in branch: {chosen} (picked most specific)")
            if len(by_prefix[p]) > 1:
                return (None, f"ambiguous {p} ids in branch: {', '.join(sorted(by_prefix[p]))}")

        return (None, f"ambiguous ids in branch: {', '.join(id_candidates)}")

    # 2) Fallback: GitHub issue number embedded in the branch name.
    leaf = s.split("/")[-1]
    nums: set[int] = set()
    for m in _HASH_ISSUE_IN_TEXT_RE.finditer(s):
        try:
            nums.add(int(m.group("num")))
        except (TypeError, ValueError):
            continue
    for m in _KEYWORD_ISSUE_IN_TEXT_RE.finditer(s):
        try:
            nums.add(int(m.group("num")))
        except (TypeError, ValueError):
            continue
    m = _LEADING_NUMBER_IN_TEXT_RE.match(leaf)
    if m:
        try:
            nums.add(int(m.group("num")))
        except (TypeError, ValueError):
            pass

    if not nums:
        # No signal: keep active unchanged silently (common on `main`, `develop`, etc.).
        return (None, None)

    matches = [
        n
        for n in nodes.values()
        if n.github_issue_number in nums and n.type in ("initiative", "epic", "issue")
    ]
    if len(matches) == 1:
        n = matches[0]
        return (n, f"matched github.issue_number={n.github_issue_number} from branch")
    if not matches:
        return (None, f"no node matches github issue numbers {sorted(nums)}")
    ids = ", ".join(sorted(f"{m.type}:{m.id}" for m in matches))
    return (None, f"ambiguous github issue numbers {sorted(nums)}: {ids}")


def _deps_target_issue_ids(nodes: dict[str, _Node], *, target_id: str) -> list[str]:
    """Resolve a deps-check target into issue ids for canonical issue graph evaluation."""
    target = nodes.get(target_id)
    if not target:
        raise RuntimeError(f"Node not found: {target_id}")

    if target.type == "issue":
        return [target.id]
    if target.type == "epic":
        return sorted(
            [n.id for n in nodes.values() if n.type == "issue" and n.epic_id == target.id],
            key=_deps_node_sort_key,
        )
    if target.type == "initiative":
        return sorted(
            [n.id for n in nodes.values() if n.type == "issue" and n.initiative_id == target.id],
            key=_deps_node_sort_key,
        )
    raise RuntimeError(f"Unsupported node type for deps check: {target.type} ({target_id})")


def _deps_check_snapshot_issue_statuses(specdock_dir: Path) -> dict[str, str]:
    """Load issue statuses from sync snapshots (`index-all.json` preferred)."""
    out: dict[str, str] = {}
    agent_dir = specdock_dir / _AGENT_DIRNAME
    state_index: dict[str, Any] | None = None
    for state_index_path in (agent_dir / "index-all.json", agent_dir / "index.json"):
        if not state_index_path.is_file():
            continue
        try:
            loaded = _load_json(state_index_path)
        except RuntimeError:
            continue
        if isinstance(loaded, dict):
            state_index = loaded
            break

    if not isinstance(state_index, dict):
        return out

    raw_nodes = state_index.get("nodes")
    if not isinstance(raw_nodes, dict):
        return out

    for issue_id, item in raw_nodes.items():
        if not isinstance(issue_id, str) or not isinstance(item, dict):
            continue
        raw_status = item.get("status")
        if not isinstance(raw_status, str):
            continue
        status = raw_status.strip().lower()
        if status in ("done", "open", "unknown"):
            out[issue_id] = status
    return out


def _deps_check_active_issue_id(specdock_dir: Path) -> str | None:
    """Return active issue id when present."""
    current = _load_active_manifest_no_migrate(specdock_dir)
    if not isinstance(current, dict):
        return None
    return _active_entry_id(current.get("issue"))


def _deps_evaluate_v2(
    specdock_dir: Path,
    nodes: dict[str, _Node],
    *,
    target_id: str,
    github: bool,
    gh_limit: int,
) -> dict[str, Any]:
    """Evaluate deps readiness using canonical issue-only dependency graph (v2)."""
    issue_direct_depends_on, compile_warnings = _compile_issue_direct_depends_on_map(nodes)
    target_issue_ids = _deps_target_issue_ids(nodes, target_id=target_id)

    reachable_issue_ids: set[str] = set()
    stack: list[str] = list(reversed(target_issue_ids))
    while stack:
        issue_id = stack.pop()
        if issue_id in reachable_issue_ids:
            continue
        reachable_issue_ids.add(issue_id)
        for dep_id in reversed(sorted(issue_direct_depends_on.get(issue_id, []), key=_deps_node_sort_key)):
            if dep_id not in reachable_issue_ids:
                stack.append(dep_id)

    reachable_depends_on = {
        issue_id: sorted(list(issue_direct_depends_on.get(issue_id, [])), key=_deps_node_sort_key)
        for issue_id in sorted(reachable_issue_ids, key=_deps_node_sort_key)
    }
    _validate_deps_cycles(reachable_depends_on)

    warnings: list[str] = []
    for code in compile_warnings:
        if code not in warnings:
            warnings.append(code)

    repo_root = specdock_dir.parent
    issue_status_by_id: dict[str, str] = {}
    if github:
        issue_index: dict[int, dict[str, Any]] = {}
        try:
            issue_index = _gh_issue_index(repo_root, limit=gh_limit)
        except RuntimeError as e:
            if "gh_fetch_failed" not in warnings:
                warnings.append("gh_fetch_failed")
            _warn(
                "gh_fetch_failed: failed to fetch GitHub issue states; treating as unknown. "
                f"Hint: check `gh auth status`, or use --no-github for cache/local state. Details: {e}"
            )
            issue_index = {}
        else:
            linked_numbers = sorted(
                {
                    int(n.github_issue_number)
                    for n in nodes.values()
                    if n.type == "issue" and n.github_issue_number is not None
                }
            )
            missing = [n for n in linked_numbers if n not in issue_index]
            if missing:
                if "gh_index_incomplete" not in warnings:
                    warnings.append("gh_index_incomplete")
                examples = ", ".join(str(n) for n in missing[:5])
                suffix = "..." if len(missing) > 5 else ""
                _warn(
                    "gh_index_incomplete: gh issue list does not include some linked issues; treating missing as unknown. "
                    f"missing={len(missing)} examples=[{examples}{suffix}] (hint: increase --gh-limit; current: {gh_limit})"
                )

        for n in nodes.values():
            if n.type != "issue":
                continue
            status = "unknown"
            if n.github_issue_number is not None:
                gh = issue_index.get(n.github_issue_number)
                if gh:
                    status = "done" if str(gh.get("state", "")).upper() == "CLOSED" else "open"
            issue_status_by_id[n.id] = status
    else:
        snapshot_statuses = _deps_check_snapshot_issue_statuses(specdock_dir)
        for n in nodes.values():
            if n.type != "issue":
                continue
            issue_status_by_id[n.id] = snapshot_statuses.get(n.id, "unknown")

    derived_issue_deps = _derive_issue_deps_fields(issue_direct_depends_on, issue_status_by_id)

    effective_set: set[str] = set()
    for issue_id in target_issue_ids:
        deps = derived_issue_deps.get(issue_id) or {}
        for dep_id in deps.get("depends_on") or []:
            if isinstance(dep_id, str):
                effective_set.add(dep_id)

    effective_depends_on = sorted(list(effective_set), key=_deps_node_sort_key)
    blockers = list(effective_depends_on)

    target_node = nodes.get(target_id)
    if not target_node:
        raise RuntimeError(f"Node not found: {target_id}")
    if target_node.type == "issue":
        target_ready = bool((derived_issue_deps.get(target_id) or {}).get("ready", False))
    else:
        target_ready = all(bool((derived_issue_deps.get(issue_id) or {}).get("ready", False)) for issue_id in target_issue_ids)

    active_issue_id = _deps_check_active_issue_id(specdock_dir)
    out_node_ids = sorted(set(target_issue_ids) | set(reachable_issue_ids), key=_deps_node_sort_key)
    out_nodes: dict[str, Any] = {}
    for issue_id in out_node_ids:
        status = issue_status_by_id.get(issue_id, "unknown")
        info = derived_issue_deps.get(issue_id) or {"ready": False}
        ready = bool(info.get("ready", False))
        if status == "done":
            state = "done"
        elif issue_id == active_issue_id:
            state = "doing"
        elif status == "unknown":
            state = "unknown"
        elif ready:
            state = "ready"
        else:
            state = "blocked"
        out_nodes[issue_id] = {"state": state, "ready": ready}

    return {
        "target": target_id,
        "ready": target_ready,
        "effective_depends_on": effective_depends_on,
        "blockers": blockers,
        "nodes": out_nodes,
        "warnings": warnings,
    }


def _deps_evaluate(
    specdock_dir: Path,
    nodes: dict[str, _Node],
    *,
    target_id: str,
    github: bool,
    gh_limit: int,
) -> dict[str, Any]:
    """Evaluate deps readiness and node states for `target_id` (no printing; warnings may be emitted)."""
    deps_map = _build_reachable_effective_deps_map(nodes, target_id)
    _validate_deps_cycles(deps_map)
    effective_depends_on = deps_map.get(target_id, [])

    repo_root = specdock_dir.parent
    issue_index: dict[int, dict[str, Any]] = {}
    warnings: list[str] = []

    def active_leaf_id() -> str | None:
        current = _load_active_manifest_no_migrate(specdock_dir)
        if not isinstance(current, dict):
            return None
        for key in ("issue", "epic", "initiative"):
            node_id = _active_entry_id(current.get(key))
            if node_id:
                return node_id
        return None

    leaf_id = active_leaf_id()

    if github:
        try:
            issue_index = _gh_issue_index(repo_root, limit=gh_limit)
        except RuntimeError as e:
            warnings.append("gh_fetch_failed")
            _warn(
                "gh_fetch_failed: failed to fetch GitHub issue states; treating as unknown. "
                f"Hint: check `gh auth status`, or use --no-github for cache/local state. Details: {e}"
            )
            issue_index = {}
        else:
            # Warn when relevant linked issues are not included in the gh index.
            relevant_numbers: set[int] = set()
            for node_id in deps_map.keys():
                n = nodes.get(node_id)
                if not n:
                    continue
                # Only issue GitHub states affect Done/ready evaluation.
                if n.type == "issue" and n.github_issue_number is not None:
                    relevant_numbers.add(int(n.github_issue_number))
                if n.type == "initiative":
                    for iss in nodes.values():
                        if iss.type == "issue" and iss.initiative_id == n.id and iss.github_issue_number is not None:
                            relevant_numbers.add(int(iss.github_issue_number))
                if n.type == "epic":
                    for iss in nodes.values():
                        if iss.type == "issue" and iss.epic_id == n.id and iss.github_issue_number is not None:
                            relevant_numbers.add(int(iss.github_issue_number))

            missing = [n for n in sorted(relevant_numbers) if n not in issue_index]
            if missing:
                warnings.append("gh_index_incomplete")
                examples = ", ".join(str(n) for n in missing[:5])
                suffix = "..." if len(missing) > 5 else ""
                _warn(
                    "gh_index_incomplete: gh issue list does not include some linked issues; treating missing as unknown. "
                    f"missing={len(missing)} examples=[{examples}{suffix}] (hint: increase --gh-limit; current: {gh_limit})"
                )

    index_issue_status_by_id: dict[str, str] = {}
    if not github:
        agent_dir = specdock_dir / _AGENT_DIRNAME
        state_index: dict[str, Any] | None = None
        for state_index_path in (agent_dir / "index-all.json", agent_dir / "index.json"):
            if not state_index_path.is_file():
                continue
            try:
                loaded = _load_json(state_index_path)
            except RuntimeError:
                continue
            if isinstance(loaded, dict):
                state_index = loaded
                break

        if isinstance(state_index, dict):
            raw_nodes = state_index.get("nodes")
            if isinstance(raw_nodes, dict):
                for issue_id, item in raw_nodes.items():
                    if not isinstance(issue_id, str) or not isinstance(item, dict):
                        continue
                    raw_status = item.get("status")
                    if not isinstance(raw_status, str):
                        continue
                    status = raw_status.strip().lower()
                    if status in ("done", "open", "unknown"):
                        index_issue_status_by_id[issue_id] = status

    # Map issue GitHub state (OPEN/CLOSED) to a minimal done/open/unknown status.
    issue_status_by_id: dict[str, str] = {}
    for n in nodes.values():
        if n.type != "issue":
            continue
        status = "unknown"
        if github and n.github_issue_number is not None:
            gh = issue_index.get(n.github_issue_number)
            if gh:
                status = "done" if str(gh.get("state", "")).upper() == "CLOSED" else "open"
        elif not github:
            status = index_issue_status_by_id.get(n.id, "unknown")
        issue_status_by_id[n.id] = status

    # Progress for epic/initiative: derived from descendant issue statuses.
    progress: dict[str, dict[str, int]] = {}
    for n in nodes.values():
        if n.type in ("initiative", "epic"):
            progress[n.id] = {"total": 0, "done": 0, "open": 0, "unknown": 0}

    for issue_id, status in issue_status_by_id.items():
        issue = nodes.get(issue_id)
        if not issue:
            continue
        for parent in filter(None, (issue.epic_id, issue.initiative_id)):
            if parent not in progress:
                continue
            progress[parent]["total"] += 1
            progress[parent][status] += 1

    def is_done(node_id: str) -> bool:
        n = nodes.get(node_id)
        if not n:
            return False

        if n.type == "issue":
            return issue_status_by_id.get(node_id) == "done"

        if n.type in ("epic", "initiative"):
            counts = progress.get(node_id) or {"total": 0, "done": 0, "open": 0, "unknown": 0}
            return int(counts.get("open", 0)) == 0 and int(counts.get("unknown", 0)) == 0

        return False

    done_by_id: dict[str, bool] = {node_id: is_done(node_id) for node_id in deps_map.keys()}

    blockers_by_id: dict[str, list[str]] = {}
    ready_by_id: dict[str, bool] = {}
    for node_id, eff in deps_map.items():
        blockers_by_id[node_id] = [dep_id for dep_id in eff if not done_by_id.get(dep_id, False)]
        ready_by_id[node_id] = len(blockers_by_id[node_id]) == 0

    blockers = blockers_by_id.get(target_id, [])
    ready = ready_by_id.get(target_id, len(blockers) == 0)

    def base_state(node_id: str) -> str:
        n = nodes.get(node_id)
        if not n:
            return "unknown"

        if done_by_id.get(node_id, False):
            return "done"

        if n.type == "issue":
            return "todo" if issue_status_by_id.get(node_id) == "open" else "unknown"

        if n.type in ("epic", "initiative"):
            counts = progress.get(node_id) or {"total": 0, "done": 0, "open": 0, "unknown": 0}
            if int(counts.get("unknown", 0)) > 0:
                return "unknown"
            return "todo"

        return "unknown"

    def is_active_scope(node_id: str) -> bool:
        if not leaf_id:
            return False
        if leaf_id == node_id:
            return True
        active_leaf = nodes.get(leaf_id)
        node = nodes.get(node_id)
        if not active_leaf or not node:
            return False
        if node.type == "epic":
            return active_leaf.type == "issue" and active_leaf.epic_id == node.id
        if node.type == "initiative":
            return active_leaf.type in ("epic", "issue") and active_leaf.initiative_id == node.id
        return False

    def derived_state(node_id: str) -> str:
        base = base_state(node_id)
        if base == "done":
            return "done"
        if not ready_by_id.get(node_id, False):
            return "blocked"
        if is_active_scope(node_id):
            return "doing"
        if base == "todo":
            return "todo"
        return "unknown"

    out_nodes: dict[str, Any] = {}
    for node_id in sorted(deps_map.keys()):
        item: dict[str, Any] = {"state": derived_state(node_id), "ready": ready_by_id.get(node_id, False)}
        if node_id in progress:
            item["progress"] = dict(progress[node_id])
        out_nodes[node_id] = item

    return {
        "target": target_id,
        "ready": ready,
        "effective_depends_on": effective_depends_on,
        "blockers": blockers,
        "nodes": out_nodes,
        "warnings": warnings,
    }


def _build_deps_state(
    repo_root: Path,
    nodes: dict[str, _Node],
    *,
    effective_deps_map: dict[str, list[str]],
    github: bool,
    issue_index: dict[int, dict[str, Any]],
    active: dict[str, Any] | None,
    warnings: list[str],
) -> dict[str, Any]:
    """Build `.agent/deps.json` state for all nodes."""

    def sort_key(node_id: str) -> tuple[int, int, str]:
        """Deterministic sort key for ids (GitHub ids first, then local)."""
        _, is_local, num = _parse_id(node_id)
        return (1 if is_local else 0, num, node_id)

    def active_leaf_id(current: dict[str, Any] | None) -> str | None:
        if not isinstance(current, dict):
            return None
        for key in ("issue", "epic", "initiative"):
            node_id = _active_entry_id(current.get(key))
            if node_id:
                return node_id
        return None

    leaf_id = active_leaf_id(active)

    # Map issue GitHub state (OPEN/CLOSED) to a minimal done/open/unknown status.
    issue_status_by_id: dict[str, str] = {}
    for n in nodes.values():
        if n.type != "issue":
            continue
        status = "unknown"
        if github and n.github_issue_number is not None:
            gh = issue_index.get(n.github_issue_number)
            if gh:
                status = "done" if str(gh.get("state", "")).upper() == "CLOSED" else "open"
        issue_status_by_id[n.id] = status

    # Progress for epic/initiative: derived from descendant issue statuses.
    progress: dict[str, dict[str, int]] = {}
    for n in nodes.values():
        if n.type in ("initiative", "epic"):
            progress[n.id] = {"total": 0, "done": 0, "open": 0, "unknown": 0}

    for issue_id, status in issue_status_by_id.items():
        issue = nodes.get(issue_id)
        if not issue:
            continue
        for parent in filter(None, (issue.epic_id, issue.initiative_id)):
            if parent not in progress:
                continue
            progress[parent]["total"] += 1
            progress[parent][status] += 1

    def is_done(node_id: str) -> bool:
        n = nodes.get(node_id)
        if not n:
            return False

        if n.type == "issue":
            return issue_status_by_id.get(node_id) == "done"

        if n.type in ("epic", "initiative"):
            counts = progress.get(node_id) or {"total": 0, "done": 0, "open": 0, "unknown": 0}
            return int(counts.get("open", 0)) == 0 and int(counts.get("unknown", 0)) == 0

        return False

    done_by_id: dict[str, bool] = {node_id: is_done(node_id) for node_id in effective_deps_map.keys()}

    blockers_by_id: dict[str, list[str]] = {}
    ready_by_id: dict[str, bool] = {}
    for node_id, eff in effective_deps_map.items():
        blockers_by_id[node_id] = [dep_id for dep_id in eff if not done_by_id.get(dep_id, False)]
        ready_by_id[node_id] = len(blockers_by_id[node_id]) == 0

    def base_state(node_id: str) -> str:
        n = nodes.get(node_id)
        if not n:
            return "unknown"

        if done_by_id.get(node_id, False):
            return "done"

        if n.type == "issue":
            return "todo" if issue_status_by_id.get(node_id) == "open" else "unknown"

        if n.type in ("epic", "initiative"):
            counts = progress.get(node_id) or {"total": 0, "done": 0, "open": 0, "unknown": 0}
            if int(counts.get("unknown", 0)) > 0:
                return "unknown"
            return "todo"

        return "unknown"

    def is_active_scope(node_id: str) -> bool:
        if not leaf_id:
            return False
        if leaf_id == node_id:
            return True
        active_leaf = nodes.get(leaf_id)
        node = nodes.get(node_id)
        if not active_leaf or not node:
            return False
        if node.type == "epic":
            return active_leaf.type == "issue" and active_leaf.epic_id == node.id
        if node.type == "initiative":
            return active_leaf.type in ("epic", "issue") and active_leaf.initiative_id == node.id
        return False

    def derived_state(node_id: str) -> str:
        base = base_state(node_id)
        if base == "done":
            return "done"
        if not ready_by_id.get(node_id, False):
            return "blocked"
        if is_active_scope(node_id):
            return "doing"
        if base == "todo":
            return "todo"
        return "unknown"

    out_nodes: dict[str, Any] = {}
    for node_id in sorted(effective_deps_map.keys(), key=sort_key):
        n = nodes.get(node_id)
        if not n:
            continue
        out_nodes[node_id] = {
            "type": n.type,
            "id": n.id,
            "title": n.title,
            "path": n.path.relative_to(repo_root).as_posix(),
            "state": derived_state(node_id),
            "ready": ready_by_id.get(node_id, False),
            "effective_depends_on": list(effective_deps_map.get(node_id, [])),
            "blockers": list(blockers_by_id.get(node_id, [])),
        }
        if node_id in progress:
            out_nodes[node_id]["progress"] = dict(progress[node_id])

    return {
        "schema_version": 1,
        "generated_at": _now_iso(),
        "active": active,
        "warnings": list(warnings),
        "nodes": out_nodes,
    }


def _render_deps_puml(deps_state: dict[str, Any], *, todo_only: bool) -> str:
    """Render deps PlantUML (todo_only excludes done nodes/edges)."""
    nodes = deps_state.get("nodes")
    if not isinstance(nodes, dict):
        raise RuntimeError("Invalid deps_state: nodes must be an object")

    state_color = {
        "done": "#D5E8D4",
        "doing": "#DAE8FC",
        "todo": "#FFF2CC",
        "unknown": "#EEEEEE",
        "blocked": "#F8CECC",
    }

    def sort_key(node_id: str) -> tuple[int, int, str]:
        _, is_local, num = _parse_id(node_id)
        return (1 if is_local else 0, num, node_id)

    def alias(node_id: str) -> str:
        safe = re.sub(r"[^0-9A-Za-z_]", "_", node_id)
        if not safe or safe[0].isdigit():
            safe = "_" + safe
        return f"N{safe}"

    include_ids: list[str] = []
    for node_id, item in nodes.items():
        if not isinstance(item, dict):
            continue
        state = str(item.get("state") or "unknown")
        if todo_only and state == "done":
            continue
        include_ids.append(str(node_id))
    include_set = set(include_ids)
    include_ids.sort(key=sort_key)

    lines: list[str] = []
    lines.append("@startuml")
    lines.append("left to right direction")
    lines.append("skinparam shadowing false")
    lines.append("")
    lines.append("legend right")
    lines.append("|= State |= Color |")
    for state, color in (("done", "#D5E8D4"), ("doing", "#DAE8FC"), ("todo", "#FFF2CC"), ("unknown", "#EEEEEE"), ("blocked", "#F8CECC")):
        lines.append(f"| {state} |<{color}> |")
    lines.append("endlegend")
    lines.append("")

    # Nodes
    for node_id in include_ids:
        item = nodes.get(node_id)
        if not isinstance(item, dict):
            continue
        state = str(item.get("state") or "unknown")
        color = state_color.get(state, state_color["unknown"])
        label = f"{node_id}\\n{state.capitalize()}"
        if item.get("ready") is False:
            label += "\\nready=false"
        lines.append(f'rectangle "{label}" as {alias(node_id)} {color}')
    lines.append("")

    # Edges (node -> effective deps)
    edges: list[tuple[str, str]] = []
    for node_id in include_ids:
        item = nodes.get(node_id)
        if not isinstance(item, dict):
            continue
        eff = item.get("effective_depends_on") or []
        if not isinstance(eff, list):
            continue
        for dep_id in eff:
            dep = str(dep_id)
            if dep in include_set:
                edges.append((node_id, dep))
    edges.sort(key=lambda x: (sort_key(x[0]), sort_key(x[1])))
    for src, dst in edges:
        lines.append(f"{alias(src)} --> {alias(dst)} : depends_on")

    lines.append("@enduml")
    lines.append("")
    return "\n".join(lines)


def _load_deps_json(path: Path) -> dict[str, Any]:
    """Load and validate `deps.json` (missing file is treated as empty).

    Schema (MVP):
    - schema_version: 1
    - depends_on: list[str|int]
    """
    if not path.exists():
        return {"schema_version": 1, "depends_on": []}

    data = _load_json(path)
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid deps.json schema: {path}: expected a JSON object")

    schema_version = data.get("schema_version")
    if schema_version != 1:
        raise RuntimeError(f"Invalid deps.json schema: {path}: schema_version must be 1")

    depends_on = data.get("depends_on")
    if not isinstance(depends_on, list):
        raise RuntimeError(f"Invalid deps.json schema: {path}: depends_on must be a list")

    for i, ref in enumerate(depends_on):
        # Note: bool is a subclass of int in Python; reject explicitly.
        if isinstance(ref, bool):
            raise RuntimeError(f"Invalid deps.json schema: {path}: depends_on[{i}] must be a string or int")
        if isinstance(ref, (str, int)):
            continue
        raise RuntimeError(f"Invalid deps.json schema: {path}: depends_on[{i}] must be a string or int")

    # Keep unknown keys for forward-compatibility, but return a stable shape.
    return {"schema_version": 1, "depends_on": depends_on}


def _normalize_repo_slug_for_deps(owner: str | None, repo: str | None) -> str | None:
    normalized_owner = str(owner or "").strip().lower()
    normalized_repo = str(repo or "").strip().lower()
    if not normalized_owner or not normalized_repo:
        return None
    return f"{normalized_owner}/{normalized_repo}"


def _normalize_repo_slug_value_for_deps(slug: str | None) -> str | None:
    normalized = str(slug or "").strip().lower()
    if not normalized:
        return None
    owner, sep, repo = normalized.partition("/")
    if not sep or not owner or not repo:
        return None
    return f"{owner}/{repo}"


def _resolve_current_repo_slug_for_deps() -> str | None:
    try:
        specdock_dir = _find_specdock_dir()
    except RuntimeError:
        return None
    try:
        raw = _origin_github_repo_slug(specdock_dir.parent)
    except RuntimeError:
        return None
    return _normalize_repo_slug_value_for_deps(raw)


def _find_dep_node_by_github_issue_number(
    nodes: dict[str, _Node],
    *,
    issue_number: int,
    current_repo_slug: str | None = None,
) -> _Node:
    matches = [
        n
        for n in nodes.values()
        if n.github_issue_number == issue_number and n.type in ("initiative", "epic", "issue")
    ]
    if not matches:
        raise RuntimeError(f"No node found for github.issue_number={issue_number}. Create/link the node first.")

    if current_repo_slug is not None:
        current_scoped = [
            node
            for node in matches
            if (_normalize_repo_slug_for_deps(node.github_repo_owner, node.github_repo_name) or current_repo_slug)
            == current_repo_slug
        ]
        if not current_scoped:
            raise RuntimeError(
                f"No node found for github.issue_number={issue_number} in current repo scope ({current_repo_slug}). "
                "Create/link the node first."
            )
        if len(current_scoped) > 1:
            ids = ", ".join(sorted(f"{node.type}:{node.id}" for node in current_scoped))
            raise RuntimeError(f"Ambiguous github.issue_number={issue_number}: {ids}")
        return current_scoped[0]

    has_scoped = any(_normalize_repo_slug_for_deps(node.github_repo_owner, node.github_repo_name) is not None for node in matches)
    has_unscoped = any(
        _normalize_repo_slug_for_deps(node.github_repo_owner, node.github_repo_name) is None for node in matches
    )
    if has_scoped and has_unscoped:
        ids = ", ".join(
            sorted(
                f"{node.type}:{node.id}"
                f"[repo={_normalize_repo_slug_for_deps(node.github_repo_owner, node.github_repo_name) or '(current-or-unknown)'}]"
                for node in matches
            )
        )
        raise RuntimeError(
            f"Ambiguous github.issue_number={issue_number}: mixed scoped/unscoped linkage (fail-closed): {ids}. "
            "Configure current repo remote (origin) or normalize linkage scope before retrying."
        )

    if len(matches) > 1:
        ids = ", ".join(sorted(f"{m.type}:{m.id}" for m in matches))
        raise RuntimeError(f"Ambiguous github.issue_number={issue_number}: {ids}")
    return matches[0]


def _resolve_dep_ref(
    nodes: dict[str, _Node],
    ref: Any,
    *,
    src_path: Path,
    current_repo_slug: str | None = None,
) -> str:
    """Resolve a dependency reference into a canonical node id.

    Supported ref forms:
    - node id string: `init-*` / `epic-*` / `iss-*` (width variants are canonicalized)
    - GitHub issue number: int or digits-only string (must resolve to exactly one imported node)
    """
    if isinstance(ref, bool):
        # Defensive: should be rejected by schema validation already.
        raise RuntimeError(f"Unresolved dependency ref: {ref!r} (in {src_path})")

    if isinstance(ref, int):
        try:
            node = _find_dep_node_by_github_issue_number(
                nodes,
                issue_number=int(ref),
                current_repo_slug=current_repo_slug,
            )
        except RuntimeError as e:
            raise RuntimeError(f"Unresolved dependency ref: {ref!r} (in {src_path}): {e}") from e
        return node.id

    if isinstance(ref, str):
        raw = ref.strip()
        if not raw:
            raise RuntimeError(f"Unresolved dependency ref: {ref!r} (in {src_path})")
        if _NUM_RE.fullmatch(raw):
            num = int(raw)
            try:
                node = _find_dep_node_by_github_issue_number(
                    nodes,
                    issue_number=num,
                    current_repo_slug=current_repo_slug,
                )
            except RuntimeError as e:
                raise RuntimeError(f"Unresolved dependency ref: {ref!r} (in {src_path}): {e}") from e
            return node.id

        try:
            prefix, is_local, num = _parse_id(raw.lower())
        except RuntimeError as e:
            raise RuntimeError(f"Unresolved dependency ref: {ref!r} (in {src_path}): {e}") from e

        if prefix not in ("init", "epic", "iss"):
            raise RuntimeError(f"Unresolved dependency ref: {ref!r} (in {src_path}): unsupported id prefix: {prefix}")

        existing = _find_existing_id_by_num(nodes, prefix=prefix, num=num, local=is_local)
        if not existing:
            raise RuntimeError(f"Unresolved dependency ref: {ref!r} (in {src_path}): node not found")
        return existing

    raise RuntimeError(f"Unresolved dependency ref: {ref!r} (in {src_path}): unsupported type: {type(ref).__name__}")


def _resolved_direct_depends_on(
    nodes: dict[str, _Node],
    node_id: str,
    *,
    current_repo_slug: str | None = None,
) -> list[str]:
    """Return resolved direct dependencies for `node_id` (stable order)."""
    node = nodes.get(node_id)
    if not node:
        raise RuntimeError(f"Internal error: missing node: {node_id}")

    deps_path = node.path / "deps.json"
    deps = _load_deps_json(deps_path)
    direct = [
        _resolve_dep_ref(
            nodes,
            ref,
            src_path=deps_path,
            current_repo_slug=current_repo_slug,
        )
        for ref in (deps.get("depends_on") or [])
    ]

    def is_descendant(dep_id: str) -> bool:
        current_id = dep_id
        visited: set[str] = set()
        while True:
            current = nodes.get(current_id)
            if not current or not current.parent_id:
                return False
            parent_id = current.parent_id
            if parent_id == node_id:
                return True
            if parent_id in visited:
                # Broken parent chains are validated elsewhere.
                return False
            visited.add(parent_id)
            current_id = parent_id

    for dep_id in direct:
        if is_descendant(dep_id):
            raise RuntimeError(f"Invalid dependency: {node_id} cannot depend on its descendant {dep_id} (in {deps_path})")

    return sorted(set(direct))


def _effective_depends_on(
    nodes: dict[str, _Node],
    node_id: str,
    direct_map: dict[str, list[str]],
) -> list[str]:
    """Compute effective dependencies by merging parents (initiative/epic/issue rules)."""
    node = nodes.get(node_id)
    if not node:
        raise RuntimeError(f"Node not found: {node_id}")

    deps: set[str] = set(direct_map.get(node_id, []))

    if node.type == "issue":
        if not node.epic_id or not node.initiative_id:
            raise RuntimeError(f"Issue meta missing epic_id/initiative_id: {node_id}")
        deps.update(direct_map.get(node.epic_id, []))
        deps.update(direct_map.get(node.initiative_id, []))
    elif node.type == "epic":
        if not node.initiative_id:
            raise RuntimeError(f"Epic meta missing initiative_id: {node_id}")
        deps.update(direct_map.get(node.initiative_id, []))
    elif node.type == "initiative":
        # No parent merge.
        pass
    else:
        raise RuntimeError(f"Unsupported node type for deps check: {node.type} ({node_id})")

    return sorted(deps)


def _build_effective_deps_map_all(nodes: dict[str, _Node]) -> dict[str, list[str]]:
    """Build an effective dependency map for all nodes (sync=global scope)."""
    current_repo_slug = _resolve_current_repo_slug_for_deps()
    dep_node_ids = sorted(
        node_id for node_id, node in nodes.items() if node.type in ("initiative", "epic", "issue")
    )
    direct_map: dict[str, list[str]] = {}
    for node_id in dep_node_ids:
        direct_map[node_id] = _resolved_direct_depends_on(
            nodes,
            node_id,
            current_repo_slug=current_repo_slug,
        )

    effective_map: dict[str, list[str]] = {}
    for node_id in dep_node_ids:
        effective_map[node_id] = _effective_depends_on(nodes, node_id, direct_map)
    return effective_map


def _issue_ids_for_dep_node(nodes: dict[str, _Node], node_id: str) -> list[str]:
    """Expand one dependency node id into canonical issue ids."""
    node = nodes.get(node_id)
    if not node:
        raise RuntimeError(f"Node not found: {node_id}")

    if node.type == "issue":
        return [node.id]
    if node.type == "epic":
        return sorted(
            [n.id for n in nodes.values() if n.type == "issue" and n.epic_id == node.id],
            key=_deps_node_sort_key,
        )
    if node.type == "initiative":
        return sorted(
            [n.id for n in nodes.values() if n.type == "issue" and n.initiative_id == node.id],
            key=_deps_node_sort_key,
        )
    raise RuntimeError(f"Unsupported dependency node type: {node.type} ({node_id})")


def _compile_issue_direct_depends_on_map(nodes: dict[str, _Node]) -> tuple[dict[str, list[str]], list[str]]:
    """Compile deps shorthand into canonical issue->issue direct dependencies."""
    current_repo_slug = _resolve_current_repo_slug_for_deps()
    dep_node_ids = sorted(
        [node_id for node_id, node in nodes.items() if node.type in ("initiative", "epic", "issue")],
        key=_deps_node_sort_key,
    )
    issue_ids = sorted([node_id for node_id, node in nodes.items() if node.type == "issue"], key=_deps_node_sort_key)
    issue_depends_on: dict[str, set[str]] = {issue_id: set() for issue_id in issue_ids}

    warning_codes: list[str] = []
    warned_empty_refs: set[tuple[str, str]] = set()

    for src_id in dep_node_ids:
        src_node = nodes[src_id]
        src_issue_ids = _issue_ids_for_dep_node(nodes, src_id)
        if not src_issue_ids:
            continue

        deps_path = src_node.path / "deps.json"
        direct_dep_node_ids = _resolved_direct_depends_on(
            nodes,
            src_id,
            current_repo_slug=current_repo_slug,
        )

        for dep_node_id in direct_dep_node_ids:
            dep_issue_ids = _issue_ids_for_dep_node(nodes, dep_node_id)
            if not dep_issue_ids:
                key = (src_id, dep_node_id)
                if key not in warned_empty_refs:
                    warned_empty_refs.add(key)
                    if "deps_ref_expanded_to_empty" not in warning_codes:
                        warning_codes.append("deps_ref_expanded_to_empty")
                    _warn(
                        "deps_ref_expanded_to_empty: "
                        f"{src_id} depends_on={dep_node_id} expanded_to=0 (in {deps_path})"
                    )
                continue

            for src_issue_id in src_issue_ids:
                for dep_issue_id in dep_issue_ids:
                    if dep_issue_id == src_issue_id:
                        raise RuntimeError(
                            "Invalid dependency: self edge produced: "
                            f"{src_issue_id} depends_on={dep_node_id} (in {deps_path})"
                        )
                    issue_depends_on[src_issue_id].add(dep_issue_id)

    compiled = {
        issue_id: sorted(list(issue_depends_on.get(issue_id, set())), key=_deps_node_sort_key)
        for issue_id in issue_ids
    }
    return compiled, warning_codes


def _issue_depends_on_edges(issue_depends_on: dict[str, list[str]]) -> list[dict[str, str]]:
    """Render canonical issue direct dependencies into edge objects."""
    edges: list[dict[str, str]] = []
    for src_id in sorted(issue_depends_on.keys(), key=_deps_node_sort_key):
        for dst_id in sorted(issue_depends_on.get(src_id, []), key=_deps_node_sort_key):
            edges.append({"from": src_id, "to": dst_id, "kind": "depends_on"})
    return edges


def _derive_issue_deps_fields(
    issue_direct_depends_on: dict[str, list[str]],
    issue_status_by_id: dict[str, str],
    *,
    blockers_top_limit: int = _BLOCKERS_TOP_LIMIT,
) -> dict[str, dict[str, Any]]:
    """Derive per-issue deps fields for index/tree issue nodes."""

    def closure_excluding_done(start_issue_id: str) -> list[str]:
        seen: set[str] = set()
        stack = list(reversed(sorted(issue_direct_depends_on.get(start_issue_id, []), key=_deps_node_sort_key)))
        while stack:
            dep_id = stack.pop()
            if dep_id in seen:
                continue

            dep_status = issue_status_by_id.get(dep_id, "unknown")
            if dep_status == "done":
                continue

            seen.add(dep_id)
            next_ids = sorted(issue_direct_depends_on.get(dep_id, []), key=_deps_node_sort_key)
            for next_id in reversed(next_ids):
                if next_id not in seen:
                    stack.append(next_id)

        return sorted(seen, key=_deps_node_sort_key)

    derived: dict[str, dict[str, Any]] = {}
    for issue_id in sorted(issue_status_by_id.keys(), key=_deps_node_sort_key):
        status = issue_status_by_id.get(issue_id, "unknown")
        if status == "done":
            depends_on: list[str] = []
            ready = True
        else:
            depends_on = closure_excluding_done(issue_id)
            ready = False if status == "unknown" else len(depends_on) == 0

        derived[issue_id] = {
            "ready": ready,
            "depends_on": depends_on,
            "blockers_top": depends_on[:blockers_top_limit],
        }

    return derived


def _build_deps_issues_placeholder_state(*, error: str | None) -> dict[str, Any]:
    """Build placeholder `.agent/deps-issues.json` when deps are disabled."""
    err = _deps_disabled_error_text(error)
    return {
        "schema_version": 1,
        "generated_at": _now_iso(),
        "source": {"index": "spec-dock/.agent/index.json", "schema_version": 2},
        "deps": {"valid": False, "error": err},
        "nodes": {},
        "edges": [],
        "edge_direction": "depends_on (dependent -> prerequisite)",
    }


def _build_deps_issues_state(
    index_nodes: dict[str, Any],
    deps_issue_edges: list[dict[str, str]],
    *,
    active: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build todo-only issue projection for `.agent/deps-issues.json`."""
    active_issue_id = _active_entry_id(active.get("issue")) if isinstance(active, dict) else None

    issue_nodes: dict[str, Any] = {}
    for node_id in sorted(index_nodes.keys(), key=_deps_node_sort_key):
        item = index_nodes.get(node_id)
        if not isinstance(item, dict):
            continue
        if item.get("type") != "issue":
            continue

        status = str(item.get("status") or "unknown")
        if status == "done":
            continue

        deps = item.get("deps")
        ready = False
        depends_on: list[str] = []
        if isinstance(deps, dict):
            raw_ready = deps.get("ready")
            if isinstance(raw_ready, bool):
                ready = raw_ready
            raw_depends_on = deps.get("depends_on")
            if isinstance(raw_depends_on, list):
                depends_on = [str(dep_id) for dep_id in raw_depends_on if isinstance(dep_id, str)]

        if active_issue_id == node_id:
            state = "doing"
        elif status == "unknown":
            state = "unknown"
        elif ready:
            state = "ready"
        else:
            state = "blocked"

        issue_nodes[node_id] = {
            "id": node_id,
            "title": item.get("title"),
            "status": status,
            "ready": ready,
            "depends_on": depends_on,
            "state": state,
        }

    issue_id_set = set(issue_nodes.keys())
    issue_edges: list[dict[str, str]] = []
    for edge in deps_issue_edges:
        if not isinstance(edge, dict):
            continue
        from_id = edge.get("from")
        to_id = edge.get("to")
        if not isinstance(from_id, str) or not isinstance(to_id, str):
            continue
        if from_id not in issue_id_set or to_id not in issue_id_set:
            continue
        out_edge: dict[str, str] = {"from": from_id, "to": to_id}
        kind = edge.get("kind")
        if isinstance(kind, str) and kind:
            out_edge["kind"] = kind
        issue_edges.append(out_edge)

    issue_edges.sort(key=lambda x: (_deps_node_sort_key(x["from"]), _deps_node_sort_key(x["to"])))

    return {
        "schema_version": 1,
        "generated_at": _now_iso(),
        "source": {"index": "spec-dock/.agent/index.json", "schema_version": 2},
        "deps": {"valid": True, "error": None},
        "nodes": issue_nodes,
        "edges": issue_edges,
        "edge_direction": "depends_on (dependent -> prerequisite)",
    }


def _build_reachable_effective_deps_map(nodes: dict[str, _Node], start_id: str) -> dict[str, list[str]]:
    """Build an effective dependency map for the reachable subgraph from `start_id` (deps check scope)."""
    if start_id not in nodes:
        raise RuntimeError(f"Node not found: {start_id}")

    current_repo_slug = _resolve_current_repo_slug_for_deps()
    direct_map: dict[str, list[str]] = {}
    effective_map: dict[str, list[str]] = {}

    def ensure_direct(node_id: str) -> None:
        if node_id in direct_map:
            return
        direct_map[node_id] = _resolved_direct_depends_on(
            nodes,
            node_id,
            current_repo_slug=current_repo_slug,
        )

    def get_effective(node_id: str) -> list[str]:
        cached = effective_map.get(node_id)
        if cached is not None:
            return cached

        node = nodes.get(node_id)
        if not node or node.type not in ("initiative", "epic", "issue"):
            raise RuntimeError(f"Unsupported node type for deps check: {node.type if node else '(missing)'} ({node_id})")

        ensure_direct(node_id)
        if node.type == "issue":
            if not node.epic_id or not node.initiative_id:
                raise RuntimeError(f"Issue meta missing epic_id/initiative_id: {node_id}")
            ensure_direct(node.epic_id)
            ensure_direct(node.initiative_id)
        elif node.type == "epic":
            if not node.initiative_id:
                raise RuntimeError(f"Epic meta missing initiative_id: {node_id}")
            ensure_direct(node.initiative_id)

        eff = _effective_depends_on(nodes, node_id, direct_map)
        effective_map[node_id] = eff
        return eff

    reachable: set[str] = set()
    stack: list[str] = [start_id]
    while stack:
        node_id = stack.pop()
        if node_id in reachable:
            continue
        reachable.add(node_id)
        for dep_id in get_effective(node_id):
            stack.append(dep_id)

    return {node_id: get_effective(node_id) for node_id in sorted(reachable)}


def _validate_deps_cycles(deps_map: dict[str, list[str]]) -> None:
    """Detect dependency cycles and raise with at least one `A -> B -> ... -> A` path."""
    visited: set[str] = set()
    in_stack: set[str] = set()
    path: list[str] = []

    # Iterative DFS to avoid `RecursionError` on deep dependency chains.
    for start_id in sorted(deps_map.keys()):
        if start_id in visited:
            continue

        stack: list[tuple[str, int]] = [(start_id, 0)]
        while stack:
            node_id, next_index = stack[-1]

            if node_id not in visited:
                visited.add(node_id)
                in_stack.add(node_id)
                path.append(node_id)

            deps = deps_map.get(node_id, [])
            if next_index >= len(deps):
                stack.pop()
                in_stack.remove(node_id)
                path.pop()
                continue

            dep_id = deps[next_index]
            stack[-1] = (node_id, next_index + 1)

            if dep_id in in_stack:
                try:
                    start_index = path.index(dep_id)
                except ValueError:
                    start_index = 0
                cycle = path[start_index:] + [dep_id]
                raise RuntimeError("Dependency cycle detected: " + " -> ".join(cycle))

            if dep_id not in visited:
                stack.append((dep_id, 0))


def _validate_nodes(nodes: dict[str, _Node], *, repo_root: Path | None = None) -> None:
    """Validate basic structural integrity for a pre-scanned node map.

    This is used by:
    - `validate` (full validation command)
    - `sync` preflight (to avoid generating index/tree from an invalid tree)
    """
    graph = _build_graph_from_nodes(nodes)
    report = _domain_validate_graph_and_deps(graph, repo_root=repo_root)
    if report.errors:
        raise RuntimeError(report.errors[0])


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse CLI arguments for the repo-local runtime script."""
    registry = _cli_build_registry()
    parser = _cli_build_parser(registry)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns a process exit code (0=success)."""
    parsed_argv = sys.argv[1:] if argv is None else argv
    try:
        registry = _cli_build_registry()
        parser = _cli_build_parser(registry)
        try:
            ns = parser.parse_args(parsed_argv)
        except SystemExit as error:
            code = getattr(error, "code", 1)
            return int(code) if isinstance(code, int) else 1
        try:
            specdock_dir = _find_specdock_dir()
            repo_root = specdock_dir.parent
        except RuntimeError:
            if getattr(ns, "command", None) != "doctor":
                raise
            repo_root = _find_repo_root_for_legacy_doctor()
            specdock_dir = repo_root / _SPEC_DOCK_DIRNAME
        runtime = _cli_build_runtime(specdock_dir, repo_root=repo_root)
        return _cli_dispatch(ns, registry, runtime.use_cases)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
