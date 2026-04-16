from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from .clock import now_iso
from .contracts import (
    ActiveManifest,
    ActiveManifestEntry,
    ActiveManifestLoadResult,
    ActiveStateSnapshot,
)
from .json_store import load_json, write_json

_AGENT_DIRNAME = ".agent"
_LEGACY_WORK_DIRNAME = ".work"
_ACTIVE_DIRNAME = "active"


def _normalize_entry(entry: Any) -> ActiveManifestEntry | None:
    if not isinstance(entry, dict):
        return None
    raw_id = entry.get("id")
    if not isinstance(raw_id, str) or not raw_id.strip():
        return None
    raw_path = entry.get("path")
    path_value = raw_path if isinstance(raw_path, str) and raw_path.strip() else None
    return ActiveManifestEntry(id=raw_id.strip(), path=path_value)


def _normalize_manifest(current: Any) -> ActiveManifest | None:
    if not isinstance(current, dict):
        return None
    if all(key in current and current[key] is None for key in ("initiative", "epic", "issue")):
        return ActiveManifest(initiative=None, epic=None, issue=None)
    initiative = _normalize_entry(current.get("initiative"))
    epic = _normalize_entry(current.get("epic"))
    issue = _normalize_entry(current.get("issue"))
    if initiative is None and epic is None and issue is None:
        return None
    return ActiveManifest(initiative=initiative, epic=epic, issue=issue)


def _manifest_to_json_obj(manifest: ActiveManifest | None) -> dict[str, Any]:
    def _entry(entry: ActiveManifestEntry | None) -> dict[str, str] | None:
        if entry is None:
            return None
        out: dict[str, str] = {"id": entry.id}
        if entry.path:
            out["path"] = entry.path
        return out

    return {
        "schema_version": 2,
        "updated_at": now_iso(),
        "initiative": _entry(manifest.initiative if manifest is not None else None),
        "epic": _entry(manifest.epic if manifest is not None else None),
        "issue": _entry(manifest.issue if manifest is not None else None),
    }


def _active_entry_path(repo_root: Path, entry: ActiveManifestEntry | None) -> Path | None:
    if entry is None or entry.path is None:
        return None
    raw_path = entry.path.strip()
    if not raw_path:
        return None

    parsed = Path(raw_path)
    candidates: list[Path] = []

    if parsed.is_absolute():
        try:
            rel_from_repo_root = parsed.relative_to(repo_root)
            candidates.append(repo_root / rel_from_repo_root)
        except ValueError:
            pass
        parts = parsed.parts
        for specdock_index in range(len(parts) - 1, -1, -1):
            if parts[specdock_index] != "spec-dock":
                continue
            candidates.append(repo_root / Path(*parts[specdock_index:]))
    else:
        # Canonical persisted path is repo-relative (`spec-dock/...`).
        candidates.append(repo_root / parsed)

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _active_placeholder_dir(specdock_dir: Path, layer: str) -> Path:
    path = specdock_dir / "system" / "active-none" / layer
    if not path.exists():
        raise RuntimeError(f"Missing placeholder directory: {path} (run 'spec-dock update')")
    return path


def _unlink_any(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
        return
    if path.is_dir():
        shutil.rmtree(path)


def _write_pathfile(active_dir: Path, name: str, target: Path) -> None:
    pathfile = active_dir / f"{name}.path"
    rel_target = os.path.relpath(target, start=active_dir)
    pathfile.write_text(rel_target + "\n", encoding="utf-8")


def _render_context_pack(manifest: ActiveManifest | None) -> str:
    has_init = manifest is not None and manifest.initiative is not None
    has_epic = manifest is not None and manifest.epic is not None
    has_issue = manifest is not None and manifest.issue is not None
    init_id = manifest.initiative.id if has_init else "(none)"
    epic_id = manifest.epic.id if has_epic else "(none)"
    issue_id = manifest.issue.id if has_issue else "(none)"

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
    lines.append("- state (local): `./spec-dock/scripts/spec-dock sync`")
    lines.append("- state (github): `./spec-dock/scripts/spec-dock sync --github`")
    lines.append("- validate: `./spec-dock/scripts/spec-dock validate`")
    lines.append("")
    return "\n".join(lines) + "\n"


def load_active_manifest(specdock_dir: Path) -> ActiveManifestLoadResult:
    candidates = (
        ("agent.active", specdock_dir / ".agent" / "active.json"),
        ("legacy.work.active", specdock_dir / ".work" / "active.json"),
        ("legacy.work.current", specdock_dir / ".work" / "current.json"),
    )
    warnings: list[str] = []

    for source, path in candidates:
        if not path.exists():
            continue
        try:
            loaded = load_json(path)
        except RuntimeError:
            warnings.append(f"active_manifest_invalid_json:{source}")
            continue
        manifest = _normalize_manifest(loaded)
        if manifest is None:
            warnings.append(f"active_manifest_invalid_shape:{source}")
            continue
        return ActiveManifestLoadResult(
            manifest=manifest,
            source=source,  # type: ignore[arg-type]
            warnings=warnings,
        )

    return ActiveManifestLoadResult(manifest=None, source="none", warnings=warnings)


def load_active_manifest_no_migrate(specdock_dir: Path) -> ActiveManifestLoadResult:
    return load_active_manifest(specdock_dir)


def load_active_issue_id(specdock_dir: Path) -> str | None:
    result = load_active_manifest(specdock_dir)
    if result.manifest is None or result.manifest.issue is None:
        return None
    return result.manifest.issue.id


def write_active_manifest(specdock_dir: Path, manifest: ActiveManifest) -> ActiveManifest:
    agent_dir = specdock_dir / _AGENT_DIRNAME
    legacy_work_dir = specdock_dir / _LEGACY_WORK_DIRNAME
    agent_dir.mkdir(parents=True, exist_ok=True)
    write_json(agent_dir / "active.json", _manifest_to_json_obj(manifest))
    (legacy_work_dir / "active.json").unlink(missing_ok=True)
    (legacy_work_dir / "current.json").unlink(missing_ok=True)
    return manifest


def apply_active_pointers(specdock_dir: Path, manifest: ActiveManifest | None, rendered_context_pack: str) -> None:
    repo_root = specdock_dir.parent
    active_dir = specdock_dir / _ACTIVE_DIRNAME
    active_dir.mkdir(parents=True, exist_ok=True)

    for name in ("initiative", "epic", "issue", "context-pack.md", "initiative.path", "epic.path", "issue.path"):
        _unlink_any(active_dir / name)

    def _target_dir(layer: str) -> Path:
        if manifest is None:
            return _active_placeholder_dir(specdock_dir, layer)
        entry = getattr(manifest, layer)
        return _active_entry_path(repo_root, entry) or _active_placeholder_dir(specdock_dir, layer)

    def _symlink(name: str, target: Path) -> None:
        link = active_dir / name
        rel_target = os.path.relpath(target, start=active_dir)
        try:
            os.symlink(rel_target, link)
        except OSError:
            _write_pathfile(active_dir, name, target)

    _symlink("initiative", _target_dir("initiative"))
    _symlink("epic", _target_dir("epic"))
    _symlink("issue", _target_dir("issue"))
    (active_dir / "context-pack.md").write_text(rendered_context_pack, encoding="utf-8")


def patch_agent_state_active_fields(specdock_dir: Path, manifest: ActiveManifest | None) -> None:
    agent_dir = specdock_dir / _AGENT_DIRNAME
    active_obj = _manifest_to_json_obj(manifest)
    for name in ("index-all.json", "tree-all.json", "index.json", "tree.json"):
        path = agent_dir / name
        if not path.is_file():
            continue
        loaded = load_json(path)
        if not isinstance(loaded, dict):
            raise RuntimeError(f"invalid JSON shape (expected object): {path}")
        loaded["active"] = active_obj
        write_json(path, loaded)


def snapshot_current_state(specdock_dir: Path) -> ActiveStateSnapshot:
    agent_dir = specdock_dir / _AGENT_DIRNAME
    active_json_path = agent_dir / "active.json"
    context_pack_path = specdock_dir / _ACTIVE_DIRNAME / "context-pack.md"

    active_json_text = active_json_path.read_text(encoding="utf-8") if active_json_path.exists() else None
    context_pack_text = context_pack_path.read_text(encoding="utf-8") if context_pack_path.exists() else None
    manifest = load_active_manifest(specdock_dir).manifest

    managed_agent_state: dict[str, str | None] = {}
    for name in ("index-all.json", "tree-all.json", "index.json", "tree.json"):
        path = agent_dir / name
        if not path.exists():
            managed_agent_state[name] = None
            continue
        _loaded = load_json(path)
        if not isinstance(_loaded, dict):
            raise RuntimeError(f"invalid JSON shape (expected object): {path}")
        managed_agent_state[name] = path.read_text(encoding="utf-8")

    return ActiveStateSnapshot(
        manifest=manifest,
        context_pack_text=context_pack_text,
        active_json_text=active_json_text,
        managed_agent_state=managed_agent_state,
    )


def restore_previous_state(specdock_dir: Path, snapshot: ActiveStateSnapshot) -> None:
    agent_dir = specdock_dir / _AGENT_DIRNAME
    active_dir = specdock_dir / _ACTIVE_DIRNAME
    active_json_path = agent_dir / "active.json"
    context_pack_path = active_dir / "context-pack.md"

    if snapshot.active_json_text is None:
        active_json_path.unlink(missing_ok=True)
    else:
        active_json_path.parent.mkdir(parents=True, exist_ok=True)
        active_json_path.write_text(snapshot.active_json_text, encoding="utf-8")

    if snapshot.context_pack_text is None:
        context_pack_path.unlink(missing_ok=True)
    else:
        context_pack_path.parent.mkdir(parents=True, exist_ok=True)
        context_pack_path.write_text(snapshot.context_pack_text, encoding="utf-8")

    for name, previous_text in snapshot.managed_agent_state.items():
        path = agent_dir / name
        if previous_text is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(previous_text, encoding="utf-8")

    restored_manifest = snapshot.manifest
    restored_context_pack = snapshot.context_pack_text
    if restored_context_pack is None:
        restored_context_pack = _render_context_pack(restored_manifest)
    apply_active_pointers(specdock_dir, restored_manifest, restored_context_pack)
