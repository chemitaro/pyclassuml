from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import TYPE_CHECKING, Any

from spec_dock_runtime.application.contracts import RunbookProjectionResult

if TYPE_CHECKING:
    from spec_dock_runtime.domain.runbook import Runbook


RUNBOOK_STATE_PATHS: tuple[str, ...] = (
    "spec-dock/.agent/runbooks/current-runbook.json",
    "spec-dock/.agent/runbooks/current-runbook.md",
)
ACTIVE_RUNBOOK_PATHS: tuple[str, ...] = tuple(f"spec-dock/active/current-runbook.{suffix}" for suffix in ("json", "md"))
CURRENT_RUNBOOK_PATHS: tuple[str, ...] = RUNBOOK_STATE_PATHS + ACTIVE_RUNBOOK_PATHS


class RunbookStore:
    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root

    def write_current(self, runbook: Runbook) -> RunbookProjectionResult:
        payload = _runbook_payload(runbook)
        json_text = json.dumps(
            {**payload, "projection": _projection_payload(runbook)},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        markdown_text = _runbook_markdown(runbook)
        writes = (
            (CURRENT_RUNBOOK_PATHS[0], json_text + "\n"),
            (CURRENT_RUNBOOK_PATHS[1], markdown_text),
            (CURRENT_RUNBOOK_PATHS[2], json_text + "\n"),
            (CURRENT_RUNBOOK_PATHS[3], markdown_text),
        )
        staged: list[tuple[Path, Path]] = []
        backups: list[tuple[Path | None, Path]] = []
        try:
            for rel_path, text in writes:
                path = _safe_projection_path(self._repo_root, rel_path)
                staged.append((_stage_text(path, text), path))
            for _tmp_path, path in staged:
                backups.append((_backup_existing_path(path), path))
            for tmp_path, path in staged:
                _replace_path(tmp_path, path)
        except OSError as exc:
            _restore_backups(backups)
            for tmp_path, _path in staged:
                tmp_path.unlink(missing_ok=True)
            for backup_path, _path in backups:
                if backup_path is not None:
                    backup_path.unlink(missing_ok=True)
            return RunbookProjectionResult(written=False, paths=(), errors=(str(exc),))
        for backup_path, _path in backups:
            if backup_path is not None:
                backup_path.unlink(missing_ok=True)
        return RunbookProjectionResult(written=True, paths=CURRENT_RUNBOOK_PATHS)


def _stage_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(text)
            tmp.flush()
            os.fsync(tmp.fileno())
        return tmp_path
    except OSError:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise


def _replace_path(src: Path, dst: Path) -> None:
    src.replace(dst)


def _safe_projection_path(repo_root: Path, rel_path: str) -> Path:
    path = repo_root / rel_path
    if path.is_symlink():
        raise OSError(f"refusing to replace symlinked runbook projection: {rel_path}")
    _reject_symlinked_ancestors(path.parent, repo_root)
    return path


def _reject_symlinked_ancestors(path: Path, root: Path) -> None:
    current = path
    while current != root:
        if current.exists() and current.is_symlink():
            raise OSError(f"refusing to write runbook projection through symlinked directory: {current}")
        if current.parent == current:
            break
        current = current.parent


def _backup_existing_path(path: Path) -> Path | None:
    if not path.exists():
        return None
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.backup-",
        suffix=".tmp",
        dir=path.parent,
    )
    os.close(fd)
    backup_path = Path(tmp_name)
    shutil.copy2(path, backup_path)
    return backup_path


def _restore_backups(backups: list[tuple[Path | None, Path]]) -> None:
    for backup_path, path in backups:
        if backup_path is None:
            path.unlink(missing_ok=True)
        elif backup_path.exists():
            backup_path.replace(path)


def _runbook_payload(runbook: Runbook) -> dict[str, Any]:
    payload = {
        "schema_version": runbook.schema_version,
        "workflow_target": runbook.workflow_target,
        "state": runbook.state,
        "next_action": runbook.next_action,
        "reason_code": runbook.reason_code,
        "active_issue_id": runbook.active_issue_id,
        "may_execute_approved_plan": runbook.may_execute_approved_plan,
        "contract_source": runbook.contract_source,
        "evidence_ledger": runbook.evidence_ledger,
        "authority": {
            "authorized_profile": runbook.authority.authorized_profile,
            "lite_candidate": runbook.authority.lite_candidate,
            "obligation_source": runbook.authority.obligation_source,
        },
        "commands": list(runbook.commands),
        "notes": list(runbook.notes),
        "stop_conditions": list(runbook.stop_conditions),
        "details": list(runbook.details),
    }
    return payload


def _runbook_markdown(runbook: Runbook) -> str:
    lines = [
        f"# Guidance Projection: {runbook.workflow_target}",
        "",
        "> Human-facing projection; not agent handoff authority. Refresh with "
        f"`./spec-dock/scripts/spec-dock guidance {runbook.workflow_target}`.",
        "",
        f"- state: {runbook.state}",
        f"- next_action: {runbook.next_action}",
        f"- reason_code: {runbook.reason_code}",
        f"- active_issue: {runbook.active_issue_id or '(none)'}",
        f"- may_execute_approved_plan: {'true' if runbook.may_execute_approved_plan else 'false'}",
        "- authority: "
        f"authorized_profile={runbook.authority.authorized_profile}, "
        f"lite_candidate={'true' if runbook.authority.lite_candidate else 'false'}, "
        f"obligation_source={runbook.authority.obligation_source}",
        "",
        "## Commands",
    ]
    lines.extend(f"- `{command}`" for command in runbook.commands)
    lines.extend(["", "## Notes"])
    lines.extend(f"- {note}" for note in runbook.notes)
    if runbook.contract_source is not None or runbook.evidence_ledger is not None:
        lines.extend(["", "## Contract"])
        if runbook.contract_source is not None:
            lines.append(f"- contract_source: {runbook.contract_source}")
        if runbook.evidence_ledger is not None:
            lines.append(f"- evidence_ledger: {runbook.evidence_ledger}")
    if runbook.details:
        lines.extend(["", "## Details"])
        lines.extend(f"- {detail}" for detail in runbook.details)
    lines.extend(["", "## Stop Conditions"])
    lines.extend(f"- {condition}" for condition in runbook.stop_conditions)
    lines.extend([
        "",
        "## Projection",
        "- Human-facing projection; not agent handoff authority.",
        "- Ignored artifact; refresh from current runtime state with "
        f"`./spec-dock/scripts/spec-dock guidance {runbook.workflow_target}`.",
    ])
    return "\n".join(lines) + "\n"


def _projection_payload(runbook: Runbook) -> dict[str, Any]:
    return {
        "written": True,
        "paths": list(CURRENT_RUNBOOK_PATHS),
        "errors": [],
        "audience": "human",
        "authority": "non-canonical",
        "refresh_command": f"./spec-dock/scripts/spec-dock guidance {runbook.workflow_target}",
    }
