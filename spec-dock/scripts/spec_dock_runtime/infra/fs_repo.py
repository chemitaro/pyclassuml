from __future__ import annotations

import contextlib
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
import time
from typing import Any, Literal

from spec_dock_runtime.infra.clock import now_iso
from spec_dock_runtime.infra.contracts import StoredMetaRecord
from spec_dock_runtime.infra.json_store import load_json, write_json

_INITIATIVES_DIRNAME = "initiatives"
_WORKBENCH_DIRNAME = ".workbench"
_META_FILENAME = ".meta.json"
_LEGACY_META_FILENAME = "meta.json"
_NODE_DIRNAME_PATTERNS: dict[str, re.Pattern[str]] = {
    "initiative": re.compile(r"^(?P<id>init(?:-local)?-[0-9]+)-[a-z0-9]+(?:-[a-z0-9]+)*$"),
    "epic": re.compile(r"^(?P<id>epic(?:-local)?-[0-9]+)-[a-z0-9]+(?:-[a-z0-9]+)*$"),
    "issue": re.compile(r"^(?P<id>iss(?:-local)?-[0-9]+)-[a-z0-9]+(?:-[a-z0-9]+)*$"),
}
_CREATE_LOCK_RELATIVE_PATH = Path("system") / ".runtime" / "create.lock"
_ENV_CREATE_LOCK_STALE_SECONDS = "SPEC_DOCK_CREATE_LOCK_STALE_SECONDS"
_DEFAULT_CREATE_LOCK_STALE_SECONDS = 600.0


def _runtime_os_name() -> str:
    return os.name


def _try_make_readonly(path: Path) -> tuple[bool, str | None]:
    try:
        mode = path.stat().st_mode
        path.chmod(mode & ~0o222)
    except OSError as e:
        return False, str(e)

    if _runtime_os_name() == "posix":
        try:
            if path.stat().st_mode & 0o222:
                return False, "write bit still set after chmod"
        except OSError as e:
            return False, str(e)

    return True, None


def _warn(message: str) -> None:
    print(f"spec-dock: (warn) {message}", file=sys.stderr)


def _is_readonly_mode(mode: int) -> bool:
    return (mode & 0o222) == 0


def _write_failed_error(stage: str, path: Path, error: OSError | str) -> RuntimeError:
    return RuntimeError(f"write_failed[{stage}]: {path}: {error}")


def _readonly_mode_preserving_read_bits(mode: int) -> int:
    return stat.S_IMODE(mode) & ~0o222


def _write_meta_json_with_permission_contract(meta_path: Path, payload: dict[str, Any]) -> None:
    unlocked_for_write = False
    write_succeeded = False
    try:
        if meta_path.exists():
            mode = meta_path.stat().st_mode
            if _is_readonly_mode(mode):
                meta_path.chmod(mode | 0o200)
                unlocked_for_write = True
        write_json(meta_path, payload)
        write_succeeded = True
    finally:
        if write_succeeded or unlocked_for_write:
            readonly_ok, readonly_err = _try_make_readonly(meta_path)
            if not readonly_ok:
                reason = readonly_err or "unknown error"
                _warn(f"readonly_lock_failed: {meta_path} ({reason})")


def _atomic_write_json(path: Path, payload: dict[str, Any], *, readonly_mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stage = "write_temp"
    tmp_path: Path | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{path.name}.tmp-",
            dir=path.parent.as_posix(),
        )
        os.close(fd)
        tmp_path = Path(tmp_name)
        write_json(tmp_path, payload)
        stage = "lock"
        lock_mode = readonly_mode
        if lock_mode is None:
            lock_mode = _readonly_mode_preserving_read_bits(tmp_path.stat().st_mode)
        tmp_path.chmod(lock_mode)
        stage = "replace"
        Path(tmp_path).replace(path)
    except Exception as exc:
        raise RuntimeError(f"write_failed[{stage}]: {path}: {exc}") from exc
    finally:
        if tmp_path is not None and tmp_path.exists():
            with contextlib.suppress(OSError):
                tmp_path.unlink()


def _write_meta_json_atomic_with_permission_contract(meta_path: Path, payload: dict[str, Any]) -> None:
    unlocked_for_write = False
    write_failed_error: RuntimeError | None = None
    readonly_mode: int | None = None

    if meta_path.exists():
        try:
            mode = stat.S_IMODE(meta_path.stat().st_mode)
        except OSError as exc:
            raise _write_failed_error("stat", meta_path, exc) from exc
        readonly_mode = _readonly_mode_preserving_read_bits(mode)
        if _is_readonly_mode(mode):
            try:
                meta_path.chmod(mode | 0o200)
            except OSError as exc:
                raise _write_failed_error("unlock", meta_path, exc) from exc
            unlocked_for_write = True

    try:
        _atomic_write_json(meta_path, payload, readonly_mode=readonly_mode)
    except RuntimeError as exc:
        write_failed_error = exc

    if write_failed_error is not None:
        if unlocked_for_write and meta_path.exists():
            try:
                if readonly_mode is None:
                    readonly_mode = _readonly_mode_preserving_read_bits(meta_path.stat().st_mode)
                meta_path.chmod(readonly_mode)
            except OSError as exc:
                lock_error = _write_failed_error("lock", meta_path, exc)
                raise RuntimeError(f"{write_failed_error}; {lock_error}") from exc
        raise write_failed_error


def _initiatives_root(specdock_dir: Path) -> Path:
    return specdock_dir / _INITIATIVES_DIRNAME


def _iter_node_meta_paths(initiatives_root: Path) -> list[Path]:
    return _find_metadata_paths(initiatives_root, filename=_META_FILENAME)


def _find_legacy_meta_paths(initiatives_root: Path) -> list[Path]:
    return _find_metadata_paths(initiatives_root, filename=_LEGACY_META_FILENAME)


def _find_metadata_paths(root: Path, *, filename: str) -> list[Path]:
    matches: list[Path] = []
    for current_root, child_dirnames, filenames in os.walk(root, topdown=True):
        child_dirnames[:] = sorted(name for name in child_dirnames if name != _WORKBENCH_DIRNAME)
        if filename in filenames:
            matches.append(Path(current_root) / filename)
    return sorted(matches, key=lambda path: path.as_posix())


def _sorted_child_dirs(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted((p for p in path.iterdir() if p.is_dir()), key=lambda p: p.as_posix())


def _parse_node_id_from_dirname(kind: str, dirname: str) -> str | None:
    pattern = _NODE_DIRNAME_PATTERNS[kind]
    matched = pattern.fullmatch(dirname)
    if matched is None:
        return None
    return str(matched.group("id"))


def _iter_expected_node_dirs(initiatives_root: Path) -> list[tuple[str, str, Path]]:
    rows: list[tuple[str, str, Path]] = []
    for initiative_dir in _sorted_child_dirs(initiatives_root):
        initiative_id = _parse_node_id_from_dirname("initiative", initiative_dir.name)
        if initiative_id is None:
            continue
        rows.append(("initiative", initiative_id, initiative_dir))

        epics_root = initiative_dir / "epics"
        for epic_dir in _sorted_child_dirs(epics_root):
            epic_id = _parse_node_id_from_dirname("epic", epic_dir.name)
            if epic_id is None:
                continue
            rows.append(("epic", epic_id, epic_dir))

            issues_root = epic_dir / "issues"
            for issue_dir in _sorted_child_dirs(issues_root):
                issue_id = _parse_node_id_from_dirname("issue", issue_dir.name)
                if issue_id is None:
                    continue
                rows.append(("issue", issue_id, issue_dir))
    return rows


def _meta_path_for_output(meta_path: Path, *, repo_root: Path) -> str:
    try:
        return meta_path.relative_to(repo_root).as_posix()
    except ValueError:
        return meta_path.as_posix()


def _parse_create_lock_metadata_text(text: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if not sep:
            continue
        normalized_key = key.strip()
        if not normalized_key:
            continue
        meta[normalized_key] = value.strip()
    return meta


def _read_create_lock_metadata(lock_path: Path) -> tuple[dict[str, str], str]:
    try:
        text = lock_path.read_text(encoding="utf-8")
    except OSError as exc:
        return {}, f"unreadable={exc}"
    meta = _parse_create_lock_metadata_text(text)
    if not meta:
        stripped = text.strip()
        if stripped:
            return {}, f"raw={stripped}"
        return {}, "empty"
    fields = []
    for key in ("pid", "user", "created_unix", "created_iso"):
        if key in meta:
            fields.append(f"{key}={meta[key]}")
    if not fields:
        fields = [f"{key}={value}" for key, value in sorted(meta.items())]
    return meta, ", ".join(fields)


def _resolve_create_lock_stale_after_seconds() -> tuple[float, str | None]:
    raw = os.environ.get(_ENV_CREATE_LOCK_STALE_SECONDS)
    if raw is None or not raw.strip():
        return (_DEFAULT_CREATE_LOCK_STALE_SECONDS, None)
    try:
        value = float(raw)
    except ValueError:
        return (_DEFAULT_CREATE_LOCK_STALE_SECONDS, f"invalid_env={_ENV_CREATE_LOCK_STALE_SECONDS}:{raw!r}")
    if value < 0:
        return (_DEFAULT_CREATE_LOCK_STALE_SECONDS, f"invalid_env={_ENV_CREATE_LOCK_STALE_SECONDS}:{value}")
    return (value, None)


def _parse_created_unix(meta: dict[str, str]) -> float | None:
    raw = str(meta.get("created_unix", "")).strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _classify_create_lock_state(
    specdock_dir: Path,
) -> tuple[Literal["absent", "in_progress", "stale_create_lock"], str]:
    lock_path = specdock_dir / _CREATE_LOCK_RELATIVE_PATH
    if not lock_path.exists():
        return ("absent", f"path={lock_path} present=false")
    if not lock_path.is_file():
        return ("stale_create_lock", f"path={lock_path} stale=unknown reason=not_regular_file")

    meta, summary = _read_create_lock_metadata(lock_path)
    stale_after_seconds, stale_threshold_issue = _resolve_create_lock_stale_after_seconds()
    required = ("token", "pid", "user", "created_unix")
    missing = [key for key in required if not str(meta.get(key, "")).strip()]
    if missing:
        return (
            "stale_create_lock",
            f"path={lock_path} stale=unknown reason=missing_fields={','.join(missing)} lock_meta=[{summary}]",
        )
    if stale_threshold_issue is not None:
        return (
            "stale_create_lock",
            f"path={lock_path} stale=unknown reason={stale_threshold_issue} lock_meta=[{summary}]",
        )

    created_unix = _parse_created_unix(meta)
    if created_unix is None:
        return (
            "stale_create_lock",
            f"path={lock_path} stale=unknown reason=invalid_created_unix lock_meta=[{summary}]",
        )

    stale = (time.time() - created_unix) >= stale_after_seconds
    if stale:
        return ("stale_create_lock", f"path={lock_path} stale=true lock_meta=[{summary}]")
    return ("in_progress", f"path={lock_path} stale=false lock_meta=[{summary}]")


def _ensure_expected_node_meta_present(*, specdock_dir: Path, initiatives_root: Path) -> None:
    repo_root = specdock_dir.parent
    lock_state, lock_summary = _classify_create_lock_state(specdock_dir)
    for kind, node_id, node_dir in _iter_expected_node_dirs(initiatives_root):
        meta_path = node_dir / _META_FILENAME
        if meta_path.is_file():
            continue
        artifact_path = _meta_path_for_output(meta_path, repo_root=repo_root)
        if lock_state == "in_progress":
            raise RuntimeError(
                "Create in-progress state detected: "
                f"kind={kind} id={node_id} artifact={artifact_path} lock={lock_summary}. "
                "Wait for create completion or run `spec-dock/scripts/spec-dock doctor`."
            )
        if lock_state == "stale_create_lock":
            raise RuntimeError(
                "Stale create-lock state detected: "
                f"kind={kind} id={node_id} artifact={artifact_path} lock={lock_summary}. "
                "Confirm no active create process, repair lock state, then run `spec-dock/scripts/spec-dock doctor`."
            )
        raise RuntimeError(
            "Missing required artifact: "
            f"kind={kind} id={node_id} "
            f"artifact={artifact_path} "
            "(restore .meta.json for this node directory)"
        )


def ensure_no_legacy_meta_json(specdock_dir: Path) -> None:
    initiatives_root = _initiatives_root(specdock_dir)
    if not initiatives_root.exists():
        return
    legacy_paths = _find_legacy_meta_paths(initiatives_root)
    if not legacy_paths:
        return
    listed = "\n".join(f"- {p}" for p in legacy_paths)
    raise RuntimeError(
        f"Unsupported legacy meta.json detected. Rename legacy files to '.meta.json' and retry:\n{listed}"
    )


def _require_non_empty_meta_string(meta: dict[str, Any], *, field: str, meta_path: Path) -> str:
    raw_value = meta.get(field)
    if not isinstance(raw_value, str):
        raise RuntimeError(f"Invalid .meta.json (required non-empty string field={field}): {meta_path}")
    value = raw_value.strip()
    if not value:
        raise RuntimeError(f"Invalid .meta.json (required non-empty string field={field}): {meta_path}")
    return value


def load_node_records(specdock_dir: Path) -> list[StoredMetaRecord]:
    ensure_no_legacy_meta_json(specdock_dir)
    initiatives_root = _initiatives_root(specdock_dir)
    if not initiatives_root.exists():
        return []
    _ensure_expected_node_meta_present(specdock_dir=specdock_dir, initiatives_root=initiatives_root)

    records: list[StoredMetaRecord] = []
    seen_ids: set[str] = set()
    for meta_path in _iter_node_meta_paths(initiatives_root):
        meta = load_json(meta_path)
        if not isinstance(meta, dict):
            raise RuntimeError(f"Invalid .meta.json (expected object): {meta_path}")

        node_type = _require_non_empty_meta_string(meta, field="type", meta_path=meta_path)
        node_id = _require_non_empty_meta_string(meta, field="id", meta_path=meta_path)
        title = str(meta.get("title", "")).strip()
        slug = str(meta.get("slug", "")).strip()
        if node_id in seen_ids:
            raise RuntimeError(f"Duplicate id detected: {node_id} ({meta_path})")
        seen_ids.add(node_id)

        github_issue_number: int | None = None
        github_repo_owner: str | None = None
        github_repo_name: str | None = None
        github = meta.get("github")
        if isinstance(github, dict):
            raw_issue_number = github.get("issue_number")
            if raw_issue_number is not None:
                try:
                    github_issue_number = int(raw_issue_number)
                except (TypeError, ValueError) as exc:
                    raise RuntimeError(f"Invalid github.issue_number in {meta_path}: {raw_issue_number}") from exc

            owner_raw = github.get("repo_owner")
            name_raw = github.get("repo_name")
            if owner_raw is not None or name_raw is not None:
                if owner_raw is None or name_raw is None:
                    raise RuntimeError(f"Invalid github.repo_owner/repo_name in {meta_path}: both fields are required")
                if not isinstance(owner_raw, str) or not isinstance(name_raw, str):
                    raise RuntimeError(
                        f"Invalid github.repo_owner/repo_name in {meta_path}: both fields must be strings"
                    )
                owner = owner_raw.strip().lower()
                name = name_raw.strip().lower()
                if not owner or not name:
                    raise RuntimeError(
                        f"Invalid github.repo_owner/repo_name in {meta_path}: empty value is not allowed"
                    )
                if github_issue_number is None:
                    raise RuntimeError(
                        f"Invalid github.repo_owner/repo_name in {meta_path}: github.issue_number is required"
                    )
                github_repo_owner = owner
                github_repo_name = name

        records.append(
            StoredMetaRecord(
                kind=node_type,
                id=node_id,
                title=title,
                slug=slug,
                path=meta_path.parent.as_posix(),
                parent_id=meta.get("parent_id") or None,
                initiative_id=meta.get("initiative_id") or None,
                epic_id=meta.get("epic_id") or None,
                github_issue_number=github_issue_number,
                meta_path=meta_path.as_posix(),
                github_repo_owner=github_repo_owner,
                github_repo_name=github_repo_name,
            )
        )
    return records


def _build_meta_payload(record: StoredMetaRecord) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "type": record.kind,
        "id": record.id,
        "title": record.title,
        "slug": record.slug,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "parent_id": record.parent_id,
        "initiative_id": record.initiative_id,
        "epic_id": record.epic_id,
        "_spec_dock": {
            "managed": True,
            "do_not_edit": True,
            "edit_via": "spec-dock",
        },
    }
    if record.github_issue_number is not None:
        github_payload: dict[str, Any] = {"issue_number": int(record.github_issue_number)}
        owner = (record.github_repo_owner or "").strip().lower()
        name = (record.github_repo_name or "").strip().lower()
        if owner or name:
            if not owner or not name:
                raise RuntimeError("github_repo_owner and github_repo_name must be provided together")
            github_payload["repo_owner"] = owner
            github_payload["repo_name"] = name
        payload["github"] = github_payload
    return payload


def write_meta(dest_dir: Path, record: StoredMetaRecord) -> None:
    meta_path = dest_dir / _META_FILENAME
    _write_meta_json_with_permission_contract(meta_path, _build_meta_payload(record))


def add_issue_dependency(meta_path: Path, to_id: str) -> None:
    meta = load_json(meta_path)
    if not isinstance(meta, dict):
        raise RuntimeError(f"Invalid .meta.json (expected object): {meta_path}")

    depends_on_raw = meta.get("depends_on")
    if depends_on_raw is None:
        depends_on: list[Any] = []
    elif isinstance(depends_on_raw, list):
        depends_on = list(depends_on_raw)
    else:
        raise RuntimeError(f"Invalid .meta.json schema: {meta_path}: depends_on must be a list")

    depends_on.append(str(to_id))
    meta["depends_on"] = depends_on
    if "updated_at" in meta:
        meta["updated_at"] = now_iso()
    _write_meta_json_atomic_with_permission_contract(meta_path, meta)


def remove_issue_dependency(meta_path: Path, to_id: str, *, matching_refs: list[object] | None = None) -> None:
    meta = load_json(meta_path)
    if not isinstance(meta, dict):
        raise RuntimeError(f"Invalid .meta.json (expected object): {meta_path}")

    depends_on_raw = meta.get("depends_on")
    if depends_on_raw is None:
        depends_on: list[Any] = []
    elif isinstance(depends_on_raw, list):
        depends_on = list(depends_on_raw)
    else:
        raise RuntimeError(f"Invalid .meta.json schema: {meta_path}: depends_on must be a list")

    to_id_text = str(to_id)
    matching_ref_values = list(matching_refs or [])
    meta["depends_on"] = [
        dep for dep in depends_on if str(dep) != to_id_text and not any(dep == ref for ref in matching_ref_values)
    ]
    if "updated_at" in meta:
        meta["updated_at"] = now_iso()
    _write_meta_json_atomic_with_permission_contract(meta_path, meta)


def backfill_github_repo_scope(meta_path: Path, *, repo_owner: str, repo_name: str) -> bool:
    normalized_owner = str(repo_owner or "").strip().lower()
    normalized_repo = str(repo_name or "").strip().lower()
    if not normalized_owner or not normalized_repo:
        raise RuntimeError("repo_owner/repo_name are required for github scope backfill")

    meta = load_json(meta_path)
    if not isinstance(meta, dict):
        raise RuntimeError(f"Invalid .meta.json (expected object): {meta_path}")

    github = meta.get("github")
    if not isinstance(github, dict):
        raise RuntimeError(f"Invalid github payload in {meta_path}: expected object")
    if github.get("issue_number") is None:
        raise RuntimeError(f"Invalid github payload in {meta_path}: github.issue_number is required for scope backfill")

    existing_owner_raw = github.get("repo_owner")
    existing_repo_raw = github.get("repo_name")
    if existing_owner_raw is not None or existing_repo_raw is not None:
        if existing_owner_raw is None or existing_repo_raw is None:
            raise RuntimeError(f"Invalid github.repo_owner/repo_name in {meta_path}: both fields are required")
        if not isinstance(existing_owner_raw, str) or not isinstance(existing_repo_raw, str):
            raise RuntimeError(f"Invalid github.repo_owner/repo_name in {meta_path}: both fields must be strings")
        existing_owner = existing_owner_raw.strip().lower()
        existing_repo = existing_repo_raw.strip().lower()
        if not existing_owner or not existing_repo:
            raise RuntimeError(f"Invalid github.repo_owner/repo_name in {meta_path}: empty value is not allowed")
        if existing_owner == normalized_owner and existing_repo == normalized_repo:
            return False
        raise RuntimeError(
            "Refusing github scope backfill due to conflicting existing scope: "
            f"{meta_path} existing={existing_owner}/{existing_repo} requested={normalized_owner}/{normalized_repo}"
        )

    github["repo_owner"] = normalized_owner
    github["repo_name"] = normalized_repo
    meta["github"] = github

    try:
        _write_meta_json_with_permission_contract(meta_path, meta)
    except OSError as exc:
        raise RuntimeError(f"Failed to backfill github scope: {meta_path}: {exc}") from exc
    return True


def _handle_rmtree_permission_error(func, path, exc_info) -> None:
    exc = exc_info[1]
    if not isinstance(exc, PermissionError):
        raise exc
    try:
        current_mode = Path(path).stat().st_mode
        Path(path).chmod(current_mode | stat.S_IWRITE)
        func(path)
    except OSError:
        raise exc from None


def delete_tree(node_path: Path) -> None:
    target = Path(node_path)
    if not target.exists():
        return
    if not target.is_dir():
        raise RuntimeError(f"delete target is not a directory: {target.as_posix()}")
    try:
        shutil.rmtree(target, onerror=_handle_rmtree_permission_error)
    except OSError as exc:
        raise RuntimeError(f"failed to delete node directory: {target.as_posix()}: {exc}") from exc
