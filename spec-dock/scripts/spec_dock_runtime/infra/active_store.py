from __future__ import annotations

import os
from pathlib import Path
import shutil
from typing import Any

from spec_dock_runtime.domain.authority import (
    GRANT_IMPLEMENTATION_START,
    GRANT_ISSUE_FINISH,
    evaluate_authority_gate,
    evaluate_evidence_adoption_ledger_gate,
    load_evidence_adoption_ledger_entries,
    validate_delegated_authority_artifact,
)
from spec_dock_runtime.infra.clock import now_iso
from spec_dock_runtime.infra.contracts import (
    ActiveManifest,
    ActiveManifestEntry,
    ActiveManifestLoadResult,
    ActiveStateSnapshot,
)
from spec_dock_runtime.infra.json_store import load_json, write_json

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
    raw_authority = entry.get("authority")
    authority = raw_authority.strip() if isinstance(raw_authority, str) and raw_authority.strip() else None
    raw_grants = entry.get("grants")
    grants: tuple[str, ...] = ()
    if isinstance(raw_grants, list):
        normalized_grants = [grant.strip() for grant in raw_grants if isinstance(grant, str) and grant.strip()]
        if len(normalized_grants) == len(raw_grants):
            grants = tuple(normalized_grants)
    raw_promotion_record = entry.get("promotion_record")
    promotion_record = raw_promotion_record if isinstance(raw_promotion_record, dict) else None
    return ActiveManifestEntry(
        id=raw_id.strip(),
        path=path_value,
        authority=authority,
        grants=grants,
        promotion_record=promotion_record,
    )


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
    def _entry(entry: ActiveManifestEntry | None) -> dict[str, Any] | None:
        if entry is None:
            return None
        out: dict[str, Any] = {"id": entry.id}
        if entry.path:
            out["path"] = entry.path
        if entry.authority:
            out["authority"] = entry.authority
        if entry.grants:
            out["grants"] = list(entry.grants)
        if entry.promotion_record is not None:
            out["promotion_record"] = entry.promotion_record
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


def _unlink_any(path: Path, *, allow_directory: bool = True) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
        return
    if path.is_dir():
        if not allow_directory:
            raise RuntimeError(f"Refusing to remove directory at generated file path: {path}")
        shutil.rmtree(path)


def _write_pathfile(active_dir: Path, name: str, target: Path) -> None:
    pathfile = active_dir / f"{name}.path"
    rel_target = os.path.relpath(target, start=active_dir)
    pathfile.write_text(rel_target + "\n", encoding="utf-8")


def _render_context_pack(manifest: ActiveManifest | None, *, repo_root: Path | None = None) -> str:
    initiative = manifest.initiative if manifest is not None else None
    epic = manifest.epic if manifest is not None else None
    issue = manifest.issue if manifest is not None else None
    init_id = initiative.id if initiative is not None else "(none)"
    epic_id = epic.id if epic is not None else "(none)"
    issue_id = issue.id if issue is not None else "(none)"

    lines: list[str] = []
    lines.append("# Context Pack (generated)")
    lines.append("")
    lines.append("## Active")
    lines.append(f"- initiative: {init_id}")
    lines.append(f"- epic: {epic_id}")
    lines.append(f"- issue: {issue_id}")
    lines.append("")
    lines.append("## Authority")
    lines.append("- source: `spec-dock/.agent/active.json`")
    lines.append(
        "- rule: proposed or missing authority cannot authorize implementation, issue ready, issue finish, or phase completion."
    )
    for label, entry in (
        ("initiative", initiative),
        ("epic", epic),
        ("issue", issue),
    ):
        if entry is None:
            lines.append(f"- {label}: authority=(none), grants=[]")
            continue
        authority = entry.authority or "missing"
        grants = ", ".join(entry.grants) if entry.grants else ""
        lines.append(f"- {label}: authority={authority}, grants=[{grants}]")
        implementation_result = evaluate_authority_gate(
            authority=entry.authority,
            grants=entry.grants,
            promotion_record=entry.promotion_record,
            required_grant=GRANT_IMPLEMENTATION_START,
            purpose="context_pack_implementation",
        )
        finish_result = evaluate_authority_gate(
            authority=entry.authority,
            grants=entry.grants,
            promotion_record=entry.promotion_record,
            required_grant=GRANT_ISSUE_FINISH,
            purpose="context_pack_finish",
        )
        downstream_blocks = _context_pack_scope_downstream_blocks(entry, repo_root=repo_root)
        if implementation_result.ok and finish_result.ok and not downstream_blocks:
            lines.append(f"- {label}: authoritative_input=implementation,finish")
        else:
            reasons = _ordered_unique(
                reason
                for reason in (implementation_result.reason, finish_result.reason, *downstream_blocks)
                if reason != "ok"
            )
            lines.append(f"- {label}: authoritative_input=none, downstream_block={','.join(reasons)}")
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
    if initiative is not None:
        lines.append("- `spec-dock/active/initiative/requirement.md`")
        lines.append("- `spec-dock/active/initiative/design.md`")
        lines.append("- `spec-dock/active/initiative/plan.md`")
    else:
        lines.append("- `spec-dock/active/initiative/README.md`")
    if epic is not None:
        lines.append("- `spec-dock/active/epic/requirement.md`")
        lines.append("- `spec-dock/active/epic/design.md`")
        lines.append("- `spec-dock/active/epic/plan.md`")
    else:
        lines.append("- `spec-dock/active/epic/README.md`")
    if issue is not None:
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


def _context_pack_scope_downstream_blocks(
    entry: ActiveManifestEntry,
    *,
    repo_root: Path | None,
) -> tuple[str, ...]:
    if repo_root is None or entry.path is None:
        return ()
    scope_dir = repo_root / entry.path
    blocks: list[str] = []
    for artifact_name in ("design.md", "plan.md"):
        artifact_path = scope_dir / artifact_name
        for purpose in ("context_pack_implementation", "context_pack_finish"):
            result = validate_delegated_authority_artifact(artifact_path, purpose=purpose)
            if result.ok:
                continue
            blocks.append(result.reason)
    ledger_result = evaluate_evidence_adoption_ledger_gate(
        load_evidence_adoption_ledger_entries(scope_dir / "report.md"),
        target_artifact="*",
        purpose="context_pack",
    )
    if not ledger_result.ok:
        blocks.append(ledger_result.reason)
        if ledger_result.blocking_entry_id is not None:
            blocks.append(f"blocking_entry_id={ledger_result.blocking_entry_id}")
    return tuple(blocks)


def _ordered_unique(values) -> list[str]:
    out: list[str] = []
    for value in values:
        if value not in out:
            out.append(value)
    return out


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

    generated_file_names = {"context-pack.md", "current-runbook.json", "current-runbook.md"}
    for name in (
        "initiative",
        "epic",
        "issue",
        "context-pack.md",
        "current-runbook.json",
        "current-runbook.md",
        "initiative.path",
        "epic.path",
        "issue.path",
    ):
        _unlink_any(active_dir / name, allow_directory=name not in generated_file_names)

    def _target_dir(layer: str) -> Path:
        if manifest is None:
            return _active_placeholder_dir(specdock_dir, layer)
        entry = getattr(manifest, layer)
        return _active_entry_path(repo_root, entry) or _active_placeholder_dir(specdock_dir, layer)

    def _symlink(name: str, target: Path) -> None:
        link = active_dir / name
        rel_target = os.path.relpath(target, start=active_dir)
        try:
            Path(link).symlink_to(rel_target)
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
        loaded = load_json(path)
        if not isinstance(loaded, dict):
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
        restored_context_pack = _render_context_pack(restored_manifest, repo_root=specdock_dir.parent)
    apply_active_pointers(specdock_dir, restored_manifest, restored_context_pack)
