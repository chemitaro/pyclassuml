from __future__ import annotations

import os
import re
import shlex
import time
import uuid
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal
from typing import cast

from ..domain.ids import (
    find_existing_id_by_num,
    format_id,
    normalize_local_id_input,
    parse_id,
    resolve_id_input,
    resolve_input_title_and_slug,
    slugify,
    validate_input_slug_kebab,
)
from ..domain.models import SpecGraph, SpecNode, SpecNodeKind, SpecNodeSeed
from ..domain.tree import build_graph
from ..domain.validation import find_malformed_discussion_doc_filename_error, validate_graph_and_deps
from ..infra.contracts import StoredMetaRecord
from .contracts import (
    CreateDiscussionDocRequest,
    CreateDiscussionDocResult,
    CreateNodeRequest,
    CreateNodeResult,
    CreatePlan,
)
from .ports import Ports
from .repo_context import require_current_repo_slug, resolve_current_repo_slug, split_repo_slug
from .sync_state import post_mutation_sync

_META_FILENAME = ".meta.json"
_DRAFT_DISCUSSION_DOC_TYPES = ("draft-requirement", "draft-design", "draft-plan")
_CREATABLE_DISCUSSION_DOC_TYPES = ("adr", "disc", "research", "interview", "scratch", *_DRAFT_DISCUSSION_DOC_TYPES)
_RETIRED_DISCUSSION_DOC_TYPES = ("note",)
_DISCUSSION_DOC_FILENAME_RE = re.compile(
    r"^(?P<ts>[0-9]{8}t[0-9]{6}z)(?:-(?P<nn>0[1-9]|[1-9][0-9]))?"
    r"-(?P<doc_type>adr|disc|research|interview|scratch|draft-requirement|draft-design|draft-plan|note)-"
    r"(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)\.md$"
)
_DRAFT_TARGET_BY_DOC_TYPE = {
    "draft-requirement": "requirement",
    "draft-design": "design",
    "draft-plan": "plan",
}
_CREATE_LOCK_DIRNAME = ".runtime"
_CREATE_LOCK_FILENAME = "create.lock"
_ENV_CREATE_LOCK_WAIT_SECONDS = "SPEC_DOCK_CREATE_LOCK_WAIT_SECONDS"
_ENV_CREATE_LOCK_POLL_SECONDS = "SPEC_DOCK_CREATE_LOCK_POLL_SECONDS"
_ENV_CREATE_LOCK_STALE_SECONDS = "SPEC_DOCK_CREATE_LOCK_STALE_SECONDS"
_DEFAULT_CREATE_LOCK_WAIT_SECONDS = 3.0
_DEFAULT_CREATE_LOCK_POLL_SECONDS = 0.05
_DEFAULT_CREATE_LOCK_STALE_SECONDS = 600.0

CreateWritePhase = Literal["none", "scaffold_copied", "meta_written", "post_write_verified"]
_PARTIAL_LOCAL_WRITE_PHASES: tuple[CreateWritePhase, ...] = (
    "scaffold_copied",
    "meta_written",
    "post_write_verified",
)


class CreatePlanExecutionError(RuntimeError):
    def __init__(self, *, phase: CreateWritePhase, message: str):
        super().__init__(message)
        self.phase = phase


def _resolve_duration_seconds(env_name: str, default: float, *, minimum: float) -> float:
    raw = os.environ.get(env_name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError(f"Invalid {env_name}: {raw!r}") from exc
    if value < minimum:
        raise RuntimeError(f"Invalid {env_name}: {value} (must be >= {minimum})")
    return value


def _resolve_create_lock_path(specdock_dir: Path) -> Path:
    return specdock_dir / "system" / _CREATE_LOCK_DIRNAME / _CREATE_LOCK_FILENAME


def _build_create_lock_metadata(token: str) -> str:
    now_unix = time.time()
    lines = [
        f"token={token}",
        f"pid={os.getpid()}",
        f"user={os.environ.get('USER', 'unknown')}",
        f"created_unix={now_unix:.6f}",
        f"created_iso={date.today().isoformat()}",
    ]
    return "\n".join(lines) + "\n"


def _write_create_lock_payload(fd: int, payload: str) -> None:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(payload)


def _read_create_lock_metadata(lock_path: Path) -> tuple[dict[str, str], str]:
    try:
        text = lock_path.read_text(encoding="utf-8")
    except OSError as exc:
        return {}, f"unreadable={exc}"

    meta: dict[str, str] = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        if not key:
            continue
        meta[key] = value.strip()
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
        fields = [f"{k}={v}" for k, v in sorted(meta.items())]
    return meta, ", ".join(fields)


def _is_stale_lock(meta: dict[str, str], *, stale_after_seconds: float) -> bool:
    created_raw = meta.get("created_unix")
    if created_raw is None:
        return False
    try:
        created_unix = float(created_raw)
    except ValueError:
        return False
    return (time.time() - created_unix) >= stale_after_seconds


def _lock_failure_message(
    *,
    specdock_dir: Path,
    lock_path: Path,
    wait_seconds: float,
    elapsed_seconds: float,
    stale: bool,
    lock_meta_summary: str,
) -> str:
    stale_flag = "true" if stale else "false"
    return (
        "create lock acquisition failed: "
        f"wait_s={elapsed_seconds:.3f} wait_limit_s={wait_seconds:.3f} stale={stale_flag} "
        f"path={lock_path} lock_meta=[{lock_meta_summary}]. "
        f"No files were written. {_doctor_guidance_message(specdock_dir)}"
    )


def _runtime_entrypoint_path(specdock_dir: Path) -> Path:
    return (specdock_dir / "scripts" / "spec-dock").resolve()


def _specdock_dir_from_lock_path(lock_path: Path) -> Path:
    if len(lock_path.parents) >= 3:
        return lock_path.parents[2].resolve()
    return lock_path.parent.resolve()


def _doctor_guidance_message(specdock_dir: Path) -> str:
    command = " ".join(shlex.quote(part) for part in (str(_runtime_entrypoint_path(specdock_dir)), "doctor"))
    return f"Run `{command}` for guidance."


def _acquire_create_lock(specdock_dir: Path) -> tuple[Path, str]:
    lock_path = _resolve_create_lock_path(specdock_dir)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    wait_seconds = _resolve_duration_seconds(
        _ENV_CREATE_LOCK_WAIT_SECONDS,
        _DEFAULT_CREATE_LOCK_WAIT_SECONDS,
        minimum=0.0,
    )
    poll_seconds = _resolve_duration_seconds(
        _ENV_CREATE_LOCK_POLL_SECONDS,
        _DEFAULT_CREATE_LOCK_POLL_SECONDS,
        minimum=0.001,
    )
    stale_after_seconds = _resolve_duration_seconds(
        _ENV_CREATE_LOCK_STALE_SECONDS,
        _DEFAULT_CREATE_LOCK_STALE_SECONDS,
        minimum=0.0,
    )

    token = uuid.uuid4().hex
    payload = _build_create_lock_metadata(token)
    started_at = time.monotonic()
    deadline = started_at + wait_seconds

    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            meta, summary = _read_create_lock_metadata(lock_path)
            elapsed = time.monotonic() - started_at
            if _is_stale_lock(meta, stale_after_seconds=stale_after_seconds):
                raise RuntimeError(
                    _lock_failure_message(
                        specdock_dir=specdock_dir,
                        lock_path=lock_path,
                        wait_seconds=wait_seconds,
                        elapsed_seconds=elapsed,
                        stale=True,
                        lock_meta_summary=summary,
                    )
                )
            if elapsed >= wait_seconds:
                raise RuntimeError(
                    _lock_failure_message(
                        specdock_dir=specdock_dir,
                        lock_path=lock_path,
                        wait_seconds=wait_seconds,
                        elapsed_seconds=elapsed,
                        stale=False,
                        lock_meta_summary=summary,
                    )
                )
            remaining = max(0.0, deadline - time.monotonic())
            if remaining <= 0:
                continue
            time.sleep(min(poll_seconds, remaining))
            continue
        except OSError as exc:
            raise RuntimeError(
                "create lock acquisition failed: "
                f"path={lock_path} error={exc}. {_doctor_guidance_message(specdock_dir)}"
            ) from exc
        else:
            try:
                _write_create_lock_payload(fd, payload)
            except Exception as exc:
                cleanup_result = "cleanup_unlink=ok"
                try:
                    lock_path.unlink()
                except OSError as cleanup_exc:
                    cleanup_result = f"cleanup_unlink_failed={cleanup_exc}"
                raise RuntimeError(
                    "create lock metadata write failed: "
                    f"path={lock_path} error={exc} {cleanup_result}. "
                    f"No files were written. {_doctor_guidance_message(specdock_dir)}"
                ) from exc
            return lock_path, token


def _release_create_lock(lock_path: Path, token: str, *, specdock_dir: Path | None = None) -> None:
    effective_specdock_dir = specdock_dir if specdock_dir is not None else _specdock_dir_from_lock_path(lock_path)
    meta, _summary = _read_create_lock_metadata(lock_path)
    if meta.get("token") != token:
        if lock_path.exists():
            raise RuntimeError(
                "create lock release failed: "
                f"path={lock_path} reason=ownership_mismatch. "
                f"Create may have already written files. {_doctor_guidance_message(effective_specdock_dir)}"
            )
        return
    try:
        lock_path.unlink()
    except OSError as exc:
        raise RuntimeError(
            "create lock release failed: "
            f"path={lock_path} error={exc}. "
            f"Create may have already written files. {_doctor_guidance_message(effective_specdock_dir)}"
        ) from exc


def _post_write_duplicate_guard(ports: Ports, *, node_id: str) -> None:
    try:
        graph = load_graph(ports, validate=False)
    except RuntimeError as exc:
        raise RuntimeError(f"post-write duplicate guard failed: {exc}") from exc
    if node_id not in graph.nodes_by_id:
        raise RuntimeError(f"post-write duplicate guard failed: created id not found: {node_id}")


def _scan_discussion_timestamp_duplicate_state(discussions_dir: Path) -> tuple[str | None, set[str]]:
    malformed_error = find_malformed_discussion_doc_filename_error(discussions_dir)
    if malformed_error is not None:
        return malformed_error, set()
    refs = _scan_discussion_timestamp_sources(discussions_dir)
    by_standard_slot: dict[str, list[Path]] = {}
    by_suffix_slot: dict[tuple[str, int], list[Path]] = {}
    doc_ids: set[str] = set()
    for timestamp, suffix, doc_type, path in refs:
        if suffix is None:
            by_standard_slot.setdefault(timestamp, []).append(path)
            doc_ids.add(f"{timestamp}-{doc_type}")
            continue
        by_suffix_slot.setdefault((timestamp, suffix), []).append(path)
        doc_ids.add(f"{timestamp}-{suffix:02d}-{doc_type}")

    duplicate_standard_slots = sorted(slot for slot, paths in by_standard_slot.items() if len(paths) > 1)
    if duplicate_standard_slots:
        dup_slot = duplicate_standard_slots[0]
        files = ", ".join(path.name for path in sorted(by_standard_slot[dup_slot], key=lambda p: p.as_posix()))
        return (
            f"Duplicate discussion timestamp slot detected under {discussions_dir}: "
            f"slot={dup_slot} files=[{files}]",
            doc_ids,
        )

    duplicate_suffix_slots = sorted(slot for slot, paths in by_suffix_slot.items() if len(paths) > 1)
    if duplicate_suffix_slots:
        dup_timestamp, dup_suffix = duplicate_suffix_slots[0]
        files = ", ".join(
            path.name for path in sorted(by_suffix_slot[(dup_timestamp, dup_suffix)], key=lambda p: p.as_posix())
        )
        return (
            f"Duplicate discussion timestamp suffix detected under {discussions_dir}: "
            f"slot={dup_timestamp}-{dup_suffix:02d} files=[{files}]",
            doc_ids,
        )
    return None, doc_ids


def _post_write_discussion_duplicate_guard(discussions_dir: Path, *, doc_id: str) -> None:
    duplicate_error, doc_ids = _scan_discussion_timestamp_duplicate_state(discussions_dir)
    if duplicate_error is not None:
        raise RuntimeError(f"post-write duplicate guard failed: {duplicate_error}")
    if doc_id not in doc_ids:
        raise RuntimeError(f"post-write duplicate guard failed: created discussion id not found: {doc_id}")


def _preflight_discussion_duplicate_guard(
    req: CreateDiscussionDocRequest,
    ports: Ports,
    *,
    specdock_dir: Path,
) -> None:
    _normalize_discussion_doc_inputs(req)
    lock_path = _resolve_create_lock_path(specdock_dir)
    if lock_path.exists():
        return
    graph = load_graph(ports, validate=False)
    discussions_dir = _resolve_scope_node(req, graph).path / "discussions"
    duplicate_error, _doc_ids = _scan_discussion_timestamp_duplicate_state(discussions_dir)
    if duplicate_error is not None:
        raise RuntimeError(duplicate_error)


def _resolve_specdock_dir(ports: Ports) -> Path:
    if ports.specdock_dir is not None:
        return ports.specdock_dir
    if ports.repo_root is not None:
        return ports.repo_root / "spec-dock"
    raise RuntimeError("specdock_dir is required")


def _resolve_repo_root(ports: Ports) -> Path:
    if ports.repo_root is None:
        raise RuntimeError("repo_root is required")
    return ports.repo_root


def _normalize_repo_slug(owner: str | None, repo: str | None) -> str | None:
    normalized_owner = str(owner or "").strip().lower()
    normalized_repo = str(repo or "").strip().lower()
    if not normalized_owner or not normalized_repo:
        return None
    return f"{normalized_owner}/{normalized_repo}"


def _resolve_node_repo(ports: Ports):
    if ports.node_repo is not None:
        return ports.node_repo

    if ports.node_reader is None:
        raise RuntimeError("node_repo is required")

    class _NodeRepoAdapter:
        def __init__(self, reader):
            self._reader = reader

        def load_node_records(self, specdock_dir: Path):
            try:
                return self._reader.load_node_records(specdock_dir)
            except TypeError:
                return self._reader.load_node_records()

        def write_meta(self, dest_dir: Path, record: StoredMetaRecord) -> None:
            writer = getattr(self._reader, "write_meta", None)
            if writer is None:
                raise RuntimeError("node_repo.write_meta is required")
            writer(dest_dir, record)

    return _NodeRepoAdapter(ports.node_reader)


def _resolve_template_scaffolder(ports: Ports):
    if ports.template_scaffolder is None:
        raise RuntimeError("template_scaffolder is required")
    return ports.template_scaffolder


def _to_spec_node_seed(record: StoredMetaRecord) -> SpecNodeSeed:
    return SpecNodeSeed(
        kind=cast(SpecNodeKind, record.kind),
        id=record.id,
        title=record.title,
        slug=record.slug,
        path=Path(record.path),
        meta_path=Path(record.meta_path),
        parent_id=record.parent_id,
        initiative_id=record.initiative_id,
        epic_id=record.epic_id,
        github_issue_number=record.github_issue_number,
        github_repo_owner=record.github_repo_owner,
        github_repo_name=record.github_repo_name,
    )


def _to_spec_node(record: StoredMetaRecord) -> SpecNode:
    return SpecNode(
        kind=cast(SpecNodeKind, record.kind),
        id=record.id,
        title=record.title,
        slug=record.slug,
        path=Path(record.path),
        meta_path=Path(record.meta_path),
        parent_id=record.parent_id,
        initiative_id=record.initiative_id,
        epic_id=record.epic_id,
        github_issue_number=record.github_issue_number,
        github_repo_owner=record.github_repo_owner,
        github_repo_name=record.github_repo_name,
    )


def load_graph(ports: Ports, *, validate: bool) -> SpecGraph:
    specdock_dir = _resolve_specdock_dir(ports)
    node_repo = _resolve_node_repo(ports)
    records = node_repo.load_node_records(specdock_dir)
    graph = build_graph([_to_spec_node_seed(record) for record in records])
    if validate:
        repo_root = _resolve_repo_root(ports)
        current_repo_slug = resolve_current_repo_slug(ports)
        report = validate_graph_and_deps(
            graph,
            repo_root=repo_root,
            current_repo_slug=current_repo_slug,
        )
        if report.errors:
            raise RuntimeError(report.errors[0])
    return graph


def _prefix_for_kind(kind: Literal["initiative", "epic", "issue"]) -> str:
    if kind == "initiative":
        return "init"
    if kind == "epic":
        return "epic"
    return "iss"


def _resolve_github_mode(
    req: CreateNodeRequest, kind: Literal["initiative", "epic", "issue"]
) -> Literal["create", "link_existing", "local_only"]:
    if req.github_mode is None:
        return "create"
    if req.github_mode not in ("create", "link_existing", "local_only"):
        raise RuntimeError(f"Unsupported github mode: {req.github_mode}")
    if req.github_mode == "local_only":
        raise RuntimeError(f"GitHub linkage is mandatory for {kind}; local_only is not supported.")
    return req.github_mode


def _next_id(graph: SpecGraph, prefix: str, *, local: bool) -> str:
    max_num = 0
    for node_id in graph.nodes_by_id:
        try:
            parsed_prefix, is_local, num = parse_id(str(node_id))
        except RuntimeError:
            continue
        if parsed_prefix != prefix:
            continue
        if is_local != local:
            continue
        max_num = max(max_num, num)
    return format_id(prefix, max_num + 1, local=local)


def resolve_parent_for_create(
    req: CreateNodeRequest,
    graph: SpecGraph,
    *,
    kind: Literal["initiative", "epic", "issue"],
) -> str | None:
    if kind == "initiative":
        return None

    if kind == "epic":
        if req.parent_id is None:
            raise RuntimeError("--initiative is required")
        parent_id = resolve_id_input(req.parent_id, prefix="init", field="initiative", nodes=graph.nodes_by_id)
        parent = graph.nodes_by_id.get(parent_id)
        if parent is None or parent.kind != "initiative":
            raise RuntimeError(f"Initiative not found: {parent_id}")
        return parent.id

    if req.parent_id is None:
        raise RuntimeError("--epic is required")
    parent_id = resolve_id_input(req.parent_id, prefix="epic", field="epic", nodes=graph.nodes_by_id)
    parent = graph.nodes_by_id.get(parent_id)
    if parent is None or parent.kind != "epic":
        raise RuntimeError(f"Epic not found: {parent_id}")
    if not parent.initiative_id:
        raise RuntimeError(f"Epic meta missing initiative_id: {parent.id}")
    return parent.id


def _node_github_linkage_key(
    node: SpecNode,
    *,
    current_repo_slug: str | None,
) -> tuple[str | None, int] | None:
    if node.kind not in ("initiative", "epic", "issue") or node.github_issue_number is None:
        return None
    repo_slug = _normalize_repo_slug(node.github_repo_owner, node.github_repo_name) or current_repo_slug
    return (repo_slug, int(node.github_issue_number))


def _node_github_repo_slug(node: SpecNode) -> str | None:
    return _normalize_repo_slug(node.github_repo_owner, node.github_repo_name)


def _resolve_requested_repo_slug(req: CreateNodeRequest, *, current_repo_slug: str | None) -> str | None:
    owner = (req.github_repo_owner or "").strip().lower()
    repo = (req.github_repo_name or "").strip().lower()
    if owner or repo:
        if not owner or not repo:
            raise RuntimeError("github_repo_owner and github_repo_name must be provided together")
        requested_repo_slug = _normalize_repo_slug(owner, repo)
        if current_repo_slug is not None and requested_repo_slug != current_repo_slug:
            raise RuntimeError(
                "cross-repo GitHub linkage is not supported: "
                f"requested repo={requested_repo_slug} current repo={current_repo_slug}"
            )
        return requested_repo_slug
    return current_repo_slug


def guard_github_issue_uniqueness(
    graph: SpecGraph,
    github_issue_number: int | None,
    *,
    github_repo_owner: str | None = None,
    github_repo_name: str | None = None,
    current_repo_slug: str | None = None,
) -> None:
    if github_issue_number is None:
        return
    requested_repo_slug = _normalize_repo_slug(github_repo_owner, github_repo_name) or current_repo_slug
    linked_same_number = sorted(
        [
            node
            for node in graph.nodes_by_id.values()
            if node.kind in ("initiative", "epic", "issue") and node.github_issue_number == int(github_issue_number)
        ],
        key=lambda node: (node.kind, node.id, node.meta_path.as_posix()),
    )
    # Fail closed: when current repo cannot be resolved, mixing scoped and unscoped linkage
    # for the same issue number can represent the same logical GitHub issue.
    if linked_same_number:
        mixed_scope_conflict = []
        for node in linked_same_number:
            explicit_repo_slug = _node_github_repo_slug(node)
            effective_repo_slug = explicit_repo_slug or current_repo_slug
            if requested_repo_slug is None and explicit_repo_slug is not None:
                mixed_scope_conflict.append(node)
                continue
            if requested_repo_slug is not None and effective_repo_slug is None:
                mixed_scope_conflict.append(node)
                continue
        if mixed_scope_conflict:
            found = ", ".join(
                f"{node.kind}:{node.id} ({node.meta_path.as_posix()})"
                for node in mixed_scope_conflict
            )
            requested_repo_label = requested_repo_slug if requested_repo_slug is not None else "(current-or-unknown)"
            raise RuntimeError(
                "github linkage scope is ambiguous and rejected (fail-closed): "
                f"repo={requested_repo_label} github.issue_number={int(github_issue_number)} conflicts with "
                "existing linkage(s) whose repository scope cannot be resolved: "
                f"{found}. Configure current repo remote (origin) or normalize linkage scope before retrying."
            )

    linkage_key = (requested_repo_slug, int(github_issue_number))
    linked = [
        node
        for node in graph.nodes_by_id.values()
        if _node_github_linkage_key(node, current_repo_slug=current_repo_slug) == linkage_key
    ]
    if not linked:
        return
    linked = sorted(linked, key=lambda node: (node.kind, node.id, node.meta_path.as_posix()))
    found = ", ".join(f"{node.kind}:{node.id} ({node.meta_path.as_posix()})" for node in linked)
    repo_label = requested_repo_slug if requested_repo_slug is not None else "(current-or-unknown)"
    raise RuntimeError(
        f"github linkage is already linked: repo={repo_label} github.issue_number={int(github_issue_number)}: {found}. "
        "Fix github linkage in one of the listed .meta.json files, "
        "or choose a different GitHub issue number (target)."
    )


def _scaffold_file_paths(template_dir: Path, dest_dir: Path) -> list[Path]:
    if not template_dir.exists() or not template_dir.is_dir():
        raise RuntimeError(f"Missing template directory: {template_dir}")
    files: list[Path] = []
    for src_path in sorted(template_dir.rglob("*"), key=lambda p: p.as_posix()):
        if src_path.is_file():
            files.append(dest_dir / src_path.relative_to(template_dir))
    return files


def _rules_source_paths(
    *,
    kind: Literal["initiative", "epic", "issue"],
    specdock_dir: Path,
) -> list[Path]:
    docs_rules_dir = specdock_dir / "docs" / "rules"
    if kind == "initiative":
        return [
            docs_rules_dir / "initiative" / "epics.md",
            docs_rules_dir / "initiative" / "discussions.md",
        ]
    if kind == "epic":
        return [
            docs_rules_dir / "epic" / "issues.md",
            docs_rules_dir / "epic" / "discussions.md",
        ]
    return [docs_rules_dir / "issue" / "discussions.md"]


def _rules_scaffold_specs(
    *,
    kind: Literal["initiative", "epic", "issue"],
    dest_dir: Path,
    specdock_dir: Path,
) -> list[tuple[Path, Path]]:
    rules_source_paths = _rules_source_paths(kind=kind, specdock_dir=specdock_dir)
    if kind == "initiative":
        return [
            (dest_dir / "epics" / "rules.md", rules_source_paths[0]),
            (dest_dir / "discussions" / "rules.md", rules_source_paths[1]),
        ]
    if kind == "epic":
        return [
            (dest_dir / "issues" / "rules.md", rules_source_paths[0]),
            (dest_dir / "discussions" / "rules.md", rules_source_paths[1]),
        ]
    return [
        (dest_dir / "discussions" / "rules.md", rules_source_paths[0]),
    ]


def _create_relative_symlink(link_path: Path, target_path: Path) -> None:
    _validate_rules_symlink_preflight(link_path=link_path, target_path=target_path)
    link_path.parent.mkdir(parents=True, exist_ok=True)
    rel_target = os.path.relpath(target_path, start=link_path.parent)
    os.symlink(rel_target, link_path)


def _validate_parent_dir_preflight(parent_dir: Path) -> None:
    current = parent_dir
    while True:
        if os.path.lexists(current):
            if current.is_symlink():
                raise RuntimeError(f"Destination already exists: {current}")
            if not current.is_dir():
                raise RuntimeError(f"Destination already exists: {current}")
            return
        next_parent = current.parent
        if next_parent == current:
            return
        current = next_parent


def _validate_rules_symlink_preflight(*, link_path: Path, target_path: Path) -> None:
    if not target_path.exists() or not target_path.is_file():
        raise RuntimeError(f"Missing rules source: {target_path}")
    _validate_parent_dir_preflight(link_path.parent)
    if os.path.lexists(link_path):
        raise RuntimeError(f"Destination already exists: {link_path}")


def _nearest_existing_parent_dir(path: Path) -> Path:
    current = path
    while not os.path.lexists(current):
        next_parent = current.parent
        if next_parent == current:
            raise RuntimeError(f"Destination already exists: {path}")
        current = next_parent
    return current


def _preflight_symlink_creation_capability(*, link_path: Path) -> None:
    probe_dir = _nearest_existing_parent_dir(link_path.parent)
    if probe_dir.is_symlink() or not probe_dir.is_dir():
        raise RuntimeError(f"Destination already exists: {probe_dir}")
    probe_path = probe_dir / f".spec-dock-symlink-probe-{os.getpid()}-{uuid.uuid4().hex}"
    probe_target = f".spec-dock-symlink-target-{uuid.uuid4().hex}"
    try:
        os.symlink(probe_target, probe_path)
    except OSError as exc:
        raise RuntimeError(f"Symlink creation preflight failed at {link_path.parent}: {exc}") from exc
    try:
        probe_path.unlink()
    except OSError as exc:
        raise RuntimeError(f"Symlink creation preflight cleanup failed at {probe_path}: {exc}") from exc


def _preflight_rules_symlink_creation_capability(
    rules_scaffold_specs: list[tuple[Path, Path]],
) -> None:
    probed_dirs: set[Path] = set()
    for link_path, _target_path in rules_scaffold_specs:
        probe_dir = _nearest_existing_parent_dir(link_path.parent)
        if probe_dir in probed_dirs:
            continue
        _preflight_symlink_creation_capability(link_path=link_path)
        probed_dirs.add(probe_dir)


def _precheck_pre_github_create_rules_sources(
    *,
    kind: Literal["initiative", "epic", "issue"],
    specdock_dir: Path,
) -> None:
    for target_path in _rules_source_paths(kind=kind, specdock_dir=specdock_dir):
        if not target_path.exists() or not target_path.is_file():
            raise RuntimeError(f"Missing rules source: {target_path}")


def _precheck_pre_github_create_symlink_dest_dir(
    *,
    kind: Literal["initiative", "epic", "issue"],
    specdock_dir: Path,
    parent: SpecNode | None,
) -> Path:
    probe_leaf = f".spec-dock-github-create-preflight-{uuid.uuid4().hex}"
    if kind == "initiative":
        return specdock_dir / "initiatives" / probe_leaf
    if parent is None:
        raise RuntimeError("parent is required for nested GitHub create preflight")
    if kind == "epic":
        return parent.path / "epics" / probe_leaf
    return parent.path / "issues" / probe_leaf


def _precheck_pre_github_create_symlink_capability(
    *,
    kind: Literal["initiative", "epic", "issue"],
    specdock_dir: Path,
    parent: SpecNode | None,
) -> None:
    dest_dir = _precheck_pre_github_create_symlink_dest_dir(
        kind=kind,
        specdock_dir=specdock_dir,
        parent=parent,
    )
    rules_scaffold_specs = _rules_scaffold_specs(kind=kind, dest_dir=dest_dir, specdock_dir=specdock_dir)
    _preflight_rules_symlink_creation_capability(rules_scaffold_specs)


def _replacements(
    *,
    kind: Literal["initiative", "epic", "issue"],
    node_id: str,
    title: str,
    parent_id: str | None,
    initiative_id: str | None,
    github_issue_number: int | None,
    today: str,
) -> dict[str, str]:
    issue_ref = f"#{github_issue_number}" if github_issue_number is not None else ""
    common = {
        "<YOUR_NAME>": os.environ.get("USER", "<YOUR_NAME>"),
        "YYYY-MM-DD": today,
    }
    if kind == "initiative":
        return {
            "<INIT_ID>": node_id,
            "<INIT_TITLE>": title,
            "<GITHUB_ISSUE_NUMBER_OR_URL>": issue_ref,
            **common,
        }
    if kind == "epic":
        assert parent_id is not None
        return {
            "<EPIC_ID>": node_id,
            "<EPIC_TITLE>": title,
            "<INIT_ID>": parent_id,
            "<GITHUB_ISSUE_NUMBER_OR_URL>": issue_ref,
            **common,
        }
    assert parent_id is not None and initiative_id is not None
    return {
        "<ISS_ID>": node_id,
        "<ISS_TITLE>": title,
        "<FEATURE_ID>": node_id,
        "<FEATURE_NAME>": title,
        "<EPIC_ID>": parent_id,
        "<INIT_ID>": initiative_id,
        "<ISSUE_NUMBER_OR_URL>": issue_ref,
        "<GITHUB_ISSUE_NUMBER_OR_URL>": issue_ref,
        **common,
    }


def _resolve_dest_dir(
    *,
    kind: Literal["initiative", "epic", "issue"],
    node_id: str,
    slug: str,
    graph: SpecGraph,
    specdock_dir: Path,
    parent_id: str | None,
) -> tuple[Path, str | None, str | None]:
    if kind == "initiative":
        return specdock_dir / "initiatives" / f"{node_id}-{slug}", None, None

    assert parent_id is not None
    parent = graph.nodes_by_id.get(parent_id)
    if parent is None:
        raise RuntimeError(f"Parent not found: {parent_id}")

    if kind == "epic":
        return parent.path / "epics" / f"{node_id}-{slug}", parent.id, None

    if not parent.initiative_id:
        raise RuntimeError(f"Epic meta missing initiative_id: {parent.id}")
    return parent.path / "issues" / f"{node_id}-{slug}", parent.initiative_id, parent.id


def plan_node_creation(
    req: CreateNodeRequest,
    graph: SpecGraph,
    *,
    kind: Literal["initiative", "epic", "issue"],
    specdock_dir: Path,
    today: str,
    current_repo_slug: str | None = None,
) -> CreatePlan:
    title, slug = resolve_input_title_and_slug(req.title, req.slug)
    mode = _resolve_github_mode(req, kind)
    prefix = _prefix_for_kind(kind)
    requested_repo_slug = _resolve_requested_repo_slug(req, current_repo_slug=current_repo_slug)

    if mode in ("create", "link_existing"):
        if req.requested_node_id is not None:
            raise RuntimeError("Cannot combine '--id' with GitHub-backed node creation.")
        if req.github_issue_number is None:
            raise RuntimeError("github_issue_number is required for github mode")
        node_id = format_id(prefix, int(req.github_issue_number), local=False)
        guard_github_issue_uniqueness(
            graph,
            int(req.github_issue_number),
            github_repo_owner=req.github_repo_owner,
            github_repo_name=req.github_repo_name,
            current_repo_slug=current_repo_slug,
        )
    else:
        if req.github_issue_number is not None:
            raise RuntimeError("Cannot combine '--no-github' with '--github-issue'.")
        if req.requested_node_id is None:
            node_id = _next_id(graph, prefix, local=True)
        else:
            node_id = normalize_local_id_input(str(req.requested_node_id), prefix=prefix, field="id")

    parsed_prefix, is_local, num = parse_id(node_id)
    existing_id = find_existing_id_by_num(graph.nodes_by_id, prefix=parsed_prefix, num=num, local=is_local)
    if existing_id and mode in ("create", "link_existing") and req.github_issue_number is not None:
        existing = graph.nodes_by_id[existing_id]
        existing_repo_slug = _normalize_repo_slug(existing.github_repo_owner, existing.github_repo_name) or current_repo_slug
        if existing_repo_slug != requested_repo_slug:
            existing_repo_label = existing_repo_slug if existing_repo_slug is not None else "(current-or-unknown)"
            requested_repo_label = requested_repo_slug if requested_repo_slug is not None else "(current-or-unknown)"
            raise RuntimeError(
                "cross-repo GitHub linkage is not supported: "
                f"requested repo={requested_repo_label} github.issue_number={int(req.github_issue_number)} "
                f"conflicts with existing repo={existing_repo_label}: {existing_id} ({existing.meta_path})"
            )
    if existing_id:
        existing = graph.nodes_by_id[existing_id]
        raise RuntimeError(f"id already exists: {existing_id} ({existing.meta_path})")

    parent_id = resolve_parent_for_create(req, graph, kind=kind)
    dest_dir, initiative_id, epic_id = _resolve_dest_dir(
        kind=kind,
        node_id=node_id,
        slug=slug,
        graph=graph,
        specdock_dir=specdock_dir,
        parent_id=parent_id,
    )
    replacements = _replacements(
        kind=kind,
        node_id=node_id,
        title=title,
        parent_id=parent_id,
        initiative_id=initiative_id,
        github_issue_number=req.github_issue_number,
        today=today,
    )
    github_repo_owner: str | None = None
    github_repo_name: str | None = None
    if req.github_issue_number is not None:
        current_scope = split_repo_slug(requested_repo_slug)
        if current_scope is not None:
            github_repo_owner, github_repo_name = current_scope
    template_dir = specdock_dir / "templates" / kind
    planned_paths = _scaffold_file_paths(template_dir, dest_dir)
    planned_paths.extend(link_path for link_path, _target_path in _rules_scaffold_specs(kind=kind, dest_dir=dest_dir, specdock_dir=specdock_dir))
    planned_paths.append(dest_dir / _META_FILENAME)
    meta_path = dest_dir / _META_FILENAME
    return CreatePlan(
        meta=StoredMetaRecord(
            kind=kind,
            id=node_id,
            title=title,
            slug=slug,
            path=dest_dir.as_posix(),
            parent_id=parent_id,
            initiative_id=initiative_id,
            epic_id=epic_id,
            github_issue_number=req.github_issue_number,
            meta_path=meta_path.as_posix(),
            github_repo_owner=github_repo_owner,
            github_repo_name=github_repo_name,
        ),
        dest_dir=dest_dir,
        replacements=replacements,
        planned_paths=planned_paths,
    )


def _resolve_template_dir(plan: CreatePlan) -> Path:
    for parent in [plan.dest_dir, *plan.dest_dir.parents]:
        if parent.name == "spec-dock":
            return parent / "templates" / plan.meta.kind
    raise RuntimeError(f"spec-dock root not found from destination: {plan.dest_dir}")


def create_write_phase_has_local_writes(phase: CreateWritePhase) -> bool:
    return phase in _PARTIAL_LOCAL_WRITE_PHASES


def resolve_create_write_phase(error: Exception, *, default: CreateWritePhase = "none") -> CreateWritePhase:
    if isinstance(error, CreatePlanExecutionError):
        return error.phase
    return default


def execute_create_plan(plan: CreatePlan, ports: Ports) -> list[Path]:
    node_repo = _resolve_node_repo(ports)
    template_scaffolder = _resolve_template_scaffolder(ports)
    specdock_dir = _resolve_specdock_dir(ports)

    collisions = [path for path in plan.planned_paths if os.path.lexists(path)]
    if collisions:
        raise RuntimeError(f"Destination already exists: {collisions[0]}")

    template_dir = _resolve_template_dir(plan)
    rules_scaffold_specs = _rules_scaffold_specs(
        kind=plan.meta.kind,
        dest_dir=plan.dest_dir,
        specdock_dir=specdock_dir,
    )
    for link_path, target_path in rules_scaffold_specs:
        _validate_rules_symlink_preflight(link_path=link_path, target_path=target_path)
    _preflight_rules_symlink_creation_capability(rules_scaffold_specs)
    try:
        created_paths = template_scaffolder.copy_scaffolded_tree(
            src_dir=template_dir,
            dest_dir=plan.dest_dir,
            replacements=plan.replacements,
        )
    except Exception as exc:
        # copy seam failures can leave partially materialized files; fail closed as partial local write.
        raise CreatePlanExecutionError(phase="scaffold_copied", message=str(exc)) from exc

    try:
        created_rule_links: list[Path] = []
        for link_path, target_path in rules_scaffold_specs:
            _create_relative_symlink(link_path, target_path)
            created_rule_links.append(link_path)
        node_repo.write_meta(plan.dest_dir, plan.meta)
    except Exception as exc:
        raise CreatePlanExecutionError(phase="scaffold_copied", message=str(exc)) from exc
    created_non_meta_paths = sorted([*created_paths, *created_rule_links], key=lambda path: path.as_posix())
    return [*created_non_meta_paths, Path(plan.meta.meta_path)]


def _resolve_scope_node(req: CreateDiscussionDocRequest, graph: SpecGraph) -> SpecNode:
    scope_node_id = req.scope_node_id
    if req.scope_kind is not None:
        scope_prefix = _prefix_for_kind(req.scope_kind)
        scope_node_id = resolve_id_input(
            req.scope_node_id,
            prefix=scope_prefix,
            field=f"--{req.scope_kind}",
            nodes=graph.nodes_by_id,
        )

    scope = graph.nodes_by_id.get(scope_node_id)
    if scope is None:
        raise RuntimeError(f"Scope node not found: {scope_node_id}")
    if req.scope_kind is not None and scope.kind != req.scope_kind:
        raise RuntimeError(f"Scope kind mismatch: expected {req.scope_kind}, got {scope.kind}")
    if scope.kind not in ("initiative", "epic", "issue"):
        raise RuntimeError(f"Unsupported scope kind for discussion docs: {scope.kind}")
    return scope


def _normalize_discussion_doc_inputs(req: CreateDiscussionDocRequest) -> tuple[str, str, str]:
    doc_type = str(req.doc_type).strip().lower()
    if doc_type in _RETIRED_DISCUSSION_DOC_TYPES:
        raise RuntimeError(
            "Discussion doc type 'note' is retired for new documents; "
            "use 'scratch' for new raw capture docs. Existing note artifacts remain valid."
        )
    if doc_type not in _CREATABLE_DISCUSSION_DOC_TYPES:
        allowed = ", ".join(_CREATABLE_DISCUSSION_DOC_TYPES)
        raise RuntimeError(f"Unknown discussion doc type: {doc_type} (allowed: {allowed})")

    title = str(req.title).strip()
    if not title:
        raise RuntimeError("--title is required")

    slug = str(req.slug).strip() if req.slug is not None else slugify(title)
    if not slug:
        raise RuntimeError("Failed to derive slug from title. Pass --slug explicitly.")
    slug = validate_input_slug_kebab(slug, field="--slug")
    return doc_type, title, slug


def _resolve_discussion_instant_utc(now_iso: str | None = None) -> datetime:
    if now_iso is None:
        return datetime.now(timezone.utc)
    normalized = now_iso.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_discussion_timestamp(now_iso: str | None = None) -> str:
    return _resolve_discussion_instant_utc(now_iso).strftime("%Y%m%dt%H%M%S") + "z"


def _format_discussion_date(now_iso: str | None = None) -> str:
    return _resolve_discussion_instant_utc(now_iso).date().isoformat()


def _scan_discussion_timestamp_sources(
    discussions_dir: Path,
) -> list[tuple[str, int | None, str, Path]]:
    refs: list[tuple[str, int | None, str, Path]] = []
    if not discussions_dir.exists():
        return refs
    for path in sorted(discussions_dir.glob("*.md"), key=lambda p: p.as_posix()):
        matched = _DISCUSSION_DOC_FILENAME_RE.fullmatch(path.name)
        if not matched:
            continue
        suffix_raw = matched.group("nn")
        refs.append(
            (
                str(matched.group("ts")),
                int(suffix_raw) if suffix_raw is not None else None,
                str(matched.group("doc_type")),
                path,
            )
        )
    return refs


def _format_discussion_doc_identity(
    *, timestamp: str, doc_type: str, slug: str, suffix: int | None
) -> tuple[str, str]:
    stem_prefix = f"{timestamp}-{doc_type}" if suffix is None else f"{timestamp}-{suffix:02d}-{doc_type}"
    return f"{stem_prefix}-{slug}", stem_prefix


def _allocate_discussion_doc_filename(
    discussions_dir: Path,
    *,
    timestamp: str,
    doc_type: str,
    slug: str,
) -> tuple[Path, str]:
    refs = _scan_discussion_timestamp_sources(discussions_dir)
    matching = [(suffix, path) for ts, suffix, _existing_doc_type, path in refs if ts == timestamp]
    if not matching:
        stem, doc_id = _format_discussion_doc_identity(
            timestamp=timestamp,
            doc_type=doc_type,
            slug=slug,
            suffix=None,
        )
        return discussions_dir / f"{stem}.md", doc_id

    used_suffixes = {suffix for suffix, _path in matching if suffix is not None}
    for suffix in range(1, 100):
        if suffix in used_suffixes:
            continue
        stem, doc_id = _format_discussion_doc_identity(
            timestamp=timestamp,
            doc_type=doc_type,
            slug=slug,
            suffix=suffix,
        )
        return discussions_dir / f"{stem}.md", doc_id
    raise RuntimeError(
        "Discussion timestamp suffix exhaustion: "
        f"timestamp={timestamp} under {discussions_dir}. "
        "Suffix allocation is limited to 01..99 within a single-second discussion-doc family."
    )


def _resolve_specdock_root(path: Path) -> Path:
    for current in [path, *path.parents]:
        if current.name == "spec-dock":
            return current
    raise RuntimeError(f"spec-dock root not found from scope path: {path}")


def _doc_id_from_path(path: Path) -> str:
    matched = _DISCUSSION_DOC_FILENAME_RE.fullmatch(path.name)
    if matched is None:
        raise RuntimeError(f"Invalid discussion document filename: {path.name}")
    suffix_raw = matched.group("nn")
    if suffix_raw is None:
        return f"{matched.group('ts')}-{matched.group('doc_type')}"
    return f"{matched.group('ts')}-{suffix_raw}-{matched.group('doc_type')}"


def _draft_canonical_template_path(*, specdock_dir: Path, scope_kind: SpecNodeKind, doc_type: str) -> Path | None:
    target = _DRAFT_TARGET_BY_DOC_TYPE.get(doc_type)
    if target is None:
        return None
    return specdock_dir / "templates" / scope_kind / f"{target}.md"


def plan_discussion_doc(
    req: CreateDiscussionDocRequest,
    graph: SpecGraph,
    *,
    today: str | None = None,
    timestamp: str | None = None,
) -> tuple[Path, Path, dict[str, str]]:
    scope = _resolve_scope_node(req, graph)
    doc_type, title, slug = _normalize_discussion_doc_inputs(req)

    specdock_dir = _resolve_specdock_root(scope.path)
    if doc_type in _DRAFT_DISCUSSION_DOC_TYPES:
        template_path = _draft_canonical_template_path(
            specdock_dir=specdock_dir,
            scope_kind=scope.kind,
            doc_type=doc_type,
        )
        if template_path is None or not template_path.is_file():
            raise RuntimeError(f"Missing canonical template source for {scope.kind} {doc_type}: {template_path}")
    else:
        template_path = specdock_dir / "templates" / "discussions" / f"{doc_type}.md"
    discussions_dir = scope.path / "discussions"
    effective_timestamp = timestamp if timestamp is not None else _format_discussion_timestamp()
    dest_path, doc_id = _allocate_discussion_doc_filename(
        discussions_dir,
        timestamp=effective_timestamp,
        doc_type=doc_type,
        slug=slug,
    )
    if dest_path.exists():
        raise RuntimeError(f"Discussion doc already exists: {dest_path}")

    if doc_type in _DRAFT_DISCUSSION_DOC_TYPES:
        replacements = _replacements(
            kind=scope.kind,
            node_id=scope.id,
            title=scope.title,
            parent_id=scope.parent_id,
            initiative_id=scope.initiative_id,
            github_issue_number=scope.github_issue_number,
            today=today if today is not None else date.today().isoformat(),
        )
        replacements["<SCOPE_ID>"] = scope.id
    else:
        replacements = {
            "<ADR_ID>": doc_id,
            "<ADR_TITLE>": title,
            "<DISC_ID>": doc_id,
            "<DISC_TITLE>": title,
            "<RESEARCH_ID>": doc_id,
            "<RESEARCH_TITLE>": title,
            "<INTERVIEW_ID>": doc_id,
            "<INTERVIEW_TITLE>": title,
            "<SCRATCH_ID>": doc_id,
            "<SCRATCH_TITLE>": title,
            "<NOTE_ID>": doc_id,
            "<NOTE_TITLE>": title,
            "<SCOPE_ID>": scope.id,
            "<YOUR_NAME>": os.environ.get("USER", "<YOUR_NAME>"),
            "YYYY-MM-DD": today if today is not None else date.today().isoformat(),
        }
    return template_path, dest_path, replacements


def create_discussion_doc(req: CreateDiscussionDocRequest, ports: Ports) -> CreateDiscussionDocResult:
    template_scaffolder = _resolve_template_scaffolder(ports)
    specdock_dir = _resolve_specdock_dir(ports)
    _preflight_discussion_duplicate_guard(req, ports, specdock_dir=specdock_dir)
    lock_path, lock_token = _acquire_create_lock(specdock_dir)
    result: CreateDiscussionDocResult | None = None
    body_error: Exception | None = None
    try:
        graph = load_graph(ports, validate=False)
        now_iso = ports.clock.now_iso() if ports.clock is not None else None
        today = _format_discussion_date(now_iso)
        timestamp = _format_discussion_timestamp(now_iso)
        template_path, dest_path, replacements = plan_discussion_doc(req, graph, today=today, timestamp=timestamp)
        duplicate_error, _doc_ids = _scan_discussion_timestamp_duplicate_state(dest_path.parent)
        if duplicate_error is not None:
            raise RuntimeError(duplicate_error)

        template_text = template_scaffolder.load_template_text(template_path)
        rendered_text = template_scaffolder.render_text(template_text, replacements)
        template_scaffolder.write_text(dest_path, rendered_text)
        doc_id = _doc_id_from_path(dest_path)
        _post_write_discussion_duplicate_guard(dest_path.parent, doc_id=doc_id)
        doc_type, _title, _slug = _normalize_discussion_doc_inputs(req)
        result = CreateDiscussionDocResult(
            doc_id=doc_id,
            doc_type=doc_type,
            scope_node_id=replacements["<SCOPE_ID>"],
            path=dest_path,
            warnings=[],
        )
    except Exception as exc:
        body_error = exc
    finally:
        release_error: Exception | None = None
        try:
            _release_create_lock(lock_path, lock_token, specdock_dir=specdock_dir)
        except Exception as exc:
            release_error = exc

        if body_error is not None:
            if release_error is not None:
                raise RuntimeError(f"{body_error}; additionally {release_error}") from body_error
            raise body_error
        if release_error is not None:
            raise release_error

    if result is None:
        raise RuntimeError("discussion doc create failed without result")
    return result


def _github_issue_body(
    *,
    kind: Literal["initiative", "epic", "issue"],
) -> str:
    if kind == "initiative":
        return (
            "Created by spec-dock.\n\n"
            "Type: initiative\n"
            "Local specs are stored under `spec-dock/initiatives/`.\n"
        )

    if kind == "epic":
        return (
            "Created by spec-dock.\n\n"
            "Type: epic\n"
            "Local specs are stored under `spec-dock/initiatives/`.\n"
        )

    return (
        "Created by spec-dock.\n\n"
        "Type: issue\n"
        "Local specs are stored under `spec-dock/initiatives/`.\n"
    )


def _validate_pre_github_create_inputs(
    req: CreateNodeRequest,
    *,
    kind: Literal["initiative", "epic", "issue"],
    mode: Literal["create", "link_existing", "local_only"],
) -> None:
    if mode not in ("create", "link_existing"):
        return

    if req.requested_node_id is not None:
        raise RuntimeError("Cannot combine '--id' with GitHub-backed node creation.")

    if kind == "epic" and req.parent_id is None:
        raise RuntimeError("--initiative is required")

    if kind == "issue" and req.parent_id is None:
        raise RuntimeError("--epic is required")

    owner = (req.github_repo_owner or "").strip()
    repo = (req.github_repo_name or "").strip()
    if owner or repo:
        if not owner or not repo:
            raise RuntimeError("github_repo_owner and github_repo_name must be provided together")


def _precheck_pre_github_create_parent(
    req: CreateNodeRequest,
    ports: Ports,
    *,
    kind: Literal["initiative", "epic", "issue"],
) -> SpecNode | None:
    graph = load_graph(ports, validate=False)
    if kind == "initiative":
        return None
    parent_id = resolve_parent_for_create(req, graph, kind=kind)
    return graph.nodes_by_id[parent_id]


def _post_github_recovery_command(
    *,
    github_issue_number: int,
    kind: Literal["initiative", "epic", "issue"],
    req: CreateNodeRequest,
    title: str,
    specdock_dir: Path,
) -> str:
    command_args = [
        str(_runtime_entrypoint_path(specdock_dir)),
        "new",
        kind,
        "--title",
        title,
    ]
    if kind == "epic" and req.parent_id is not None:
        command_args.extend(["--initiative", req.parent_id])
    if kind == "issue" and req.parent_id is not None:
        command_args.extend(["--epic", req.parent_id])
    command_args.extend(["--github-issue", str(github_issue_number)])
    return " ".join(shlex.quote(part) for part in command_args)


def _post_github_retry_or_cleanup_guidance(
    *,
    github_issue_number: int,
    kind: Literal["initiative", "epic", "issue"],
    req: CreateNodeRequest,
    title: str,
    specdock_dir: Path,
) -> str:
    recovery_command = _post_github_recovery_command(
        github_issue_number=github_issue_number,
        kind=kind,
        req=req,
        title=title,
        specdock_dir=specdock_dir,
    )
    return (
        f"Recovery: rerun `{recovery_command}` to link the existing GitHub issue, "
        "or close/cleanup that GitHub issue before retrying."
    )


def _post_github_doctor_first_guidance(
    *,
    specdock_dir: Path,
    local_node_id: str | None,
) -> str:
    node_hint = (
        f"local node `{local_node_id}`"
        if local_node_id is not None
        else "the local node created by this request"
    )
    return (
        "Create may already have succeeded. Do not rerun blindly. "
        f"First inspect {node_hint}. {_doctor_guidance_message(specdock_dir)}"
    )


def _build_pre_github_create_failure(*, error: Exception) -> RuntimeError:
    return RuntimeError("Outcome: pre_github_fail. " f"{error}")


def _build_post_github_create_failure(
    *,
    local_error: Exception | None,
    release_error: Exception | None,
    created_github_issue_number: int | None,
    kind: Literal["initiative", "epic", "issue"],
    req: CreateNodeRequest,
    title: str,
    specdock_dir: Path,
    local_write_phase: CreateWritePhase,
    local_node_id: str | None,
    lock_acquired: bool,
) -> RuntimeError | None:
    if created_github_issue_number is None:
        return None

    if not lock_acquired:
        if local_error is None:
            return None
        guidance = _post_github_retry_or_cleanup_guidance(
            github_issue_number=created_github_issue_number,
            kind=kind,
            req=req,
            title=title,
            specdock_dir=specdock_dir,
        )
        return RuntimeError(
            "Outcome: post_github_remote_only_fail. "
            f"{local_error} "
            f"GitHub issue was created: #{created_github_issue_number}. "
            f"{guidance}"
        )

    if local_error is not None and release_error is not None:
        guidance = (
            _post_github_doctor_first_guidance(specdock_dir=specdock_dir, local_node_id=local_node_id)
            if create_write_phase_has_local_writes(local_write_phase)
            else _post_github_retry_or_cleanup_guidance(
                github_issue_number=created_github_issue_number,
                kind=kind,
                req=req,
                title=title,
                specdock_dir=specdock_dir,
            )
        )
        return RuntimeError(
            "Outcome: post_github_body_and_cleanup_fail. "
            f"Primary local failure: {local_error}. "
            f"Cleanup failure: {release_error}. "
            f"GitHub issue was created: #{created_github_issue_number}. "
            f"{guidance}"
        )

    if local_error is not None:
        guidance = (
            _post_github_doctor_first_guidance(specdock_dir=specdock_dir, local_node_id=local_node_id)
            if create_write_phase_has_local_writes(local_write_phase)
            else _post_github_retry_or_cleanup_guidance(
                github_issue_number=created_github_issue_number,
                kind=kind,
                req=req,
                title=title,
                specdock_dir=specdock_dir,
            )
        )
        return RuntimeError(
            "Outcome: post_github_local_write_fail. "
            f"{local_error} "
            f"GitHub issue was created: #{created_github_issue_number}. "
            f"{guidance}"
        )

    if release_error is not None:
        guidance = _post_github_doctor_first_guidance(specdock_dir=specdock_dir, local_node_id=local_node_id)
        return RuntimeError(
            "Outcome: post_github_local_write_success_cleanup_fail. "
            f"Cleanup failure: {release_error}. "
            f"GitHub issue was created: #{created_github_issue_number}. "
            f"{guidance}"
        )

    return None


def create_node_core(
    req: CreateNodeRequest,
    ports: Ports,
    *,
    kind: Literal["initiative", "epic", "issue"],
) -> CreateNodeResult:
    mode = _resolve_github_mode(req, kind)
    title, _slug = resolve_input_title_and_slug(req.title, req.slug)
    github_issue_number = req.github_issue_number
    created_github_issue_number: int | None = None
    current_repo_slug: str | None = None
    specdock_dir: Path | None = None

    try:
        _validate_pre_github_create_inputs(req, kind=kind, mode=mode)
        specdock_dir = _resolve_specdock_dir(ports)
        if mode in ("create", "link_existing"):
            current_repo_slug = require_current_repo_slug(ports)
            _resolve_requested_repo_slug(req, current_repo_slug=current_repo_slug)

        if mode == "link_existing" and github_issue_number is None:
            raise RuntimeError("github_issue_number is required for link_existing mode")

        if mode == "create" and github_issue_number is None:
            if ports.issue_gateway is None:
                raise RuntimeError("issue_gateway is required for github issue creation")
            parent = _precheck_pre_github_create_parent(req, ports, kind=kind)
            _precheck_pre_github_create_rules_sources(kind=kind, specdock_dir=specdock_dir)
            _precheck_pre_github_create_symlink_capability(kind=kind, specdock_dir=specdock_dir, parent=parent)
            repo_root = _resolve_repo_root(ports)
            github_issue_number = ports.issue_gateway.issue_create(
                repo_root,
                title=title,
                body=_github_issue_body(kind=kind),
            )
            created_github_issue_number = int(github_issue_number)
    except Exception as exc:
        if mode == "create" and req.github_issue_number is None and created_github_issue_number is None:
            raise _build_pre_github_create_failure(error=exc) from exc
        raise

    assert specdock_dir is not None

    try:
        lock_path, lock_token = _acquire_create_lock(specdock_dir)
    except Exception as exc:
        wrapped_error = _build_post_github_create_failure(
            local_error=exc,
            release_error=None,
            created_github_issue_number=created_github_issue_number,
            kind=kind,
            req=req,
            title=title,
            specdock_dir=specdock_dir,
            local_write_phase="none",
            local_node_id=None,
            lock_acquired=False,
        )
        if wrapped_error is not None:
            raise wrapped_error from exc
        raise

    result: CreateNodeResult | None = None
    body_error: Exception | None = None
    local_write_phase: CreateWritePhase = "none"
    local_node_id: str | None = None
    try:
        graph = load_graph(ports, validate=False)
        if current_repo_slug is None:
            current_repo_slug = resolve_current_repo_slug(ports)

        today = ports.clock.today() if ports.clock is not None else date.today().isoformat()
        plan = plan_node_creation(
            replace(
                req,
                github_mode=mode,
                github_issue_number=github_issue_number,
            ),
            graph,
            kind=kind,
            specdock_dir=specdock_dir,
            today=today,
            current_repo_slug=current_repo_slug,
        )
        local_node_id = plan.meta.id
        created_paths = execute_create_plan(plan, ports)
        local_write_phase = "meta_written"
        _post_write_duplicate_guard(ports, node_id=plan.meta.id)
        local_write_phase = "post_write_verified"
        result = CreateNodeResult(
            node=_to_spec_node(plan.meta),
            created_paths=created_paths,
            warnings=[],
        )
    except Exception as exc:
        body_error = exc
        local_write_phase = resolve_create_write_phase(exc, default=local_write_phase)
    finally:
        release_error: Exception | None = None
        try:
            _release_create_lock(lock_path, lock_token, specdock_dir=specdock_dir)
        except Exception as exc:
            release_error = exc

        wrapped_outcome_error = _build_post_github_create_failure(
            local_error=body_error,
            release_error=release_error,
            created_github_issue_number=created_github_issue_number,
            kind=kind,
            req=req,
            title=title,
            specdock_dir=specdock_dir,
            local_write_phase=local_write_phase,
            local_node_id=local_node_id if create_write_phase_has_local_writes(local_write_phase) else None,
            lock_acquired=True,
        )
        if wrapped_outcome_error is not None:
            cause = body_error if body_error is not None else release_error
            if cause is not None:
                raise wrapped_outcome_error from cause
            raise wrapped_outcome_error

        if body_error is not None:
            if release_error is not None:
                raise RuntimeError(f"{body_error}; additionally {release_error}") from body_error
            raise body_error
        if release_error is not None:
            raise release_error

    if result is None:
        raise RuntimeError("create failed without result")
    return replace(result, post_sync=post_mutation_sync(ports))


def create_initiative(req: CreateNodeRequest, ports: Ports) -> CreateNodeResult:
    return create_node_core(req, ports, kind="initiative")


def create_epic(req: CreateNodeRequest, ports: Ports) -> CreateNodeResult:
    return create_node_core(req, ports, kind="epic")


def create_issue(req: CreateNodeRequest, ports: Ports) -> CreateNodeResult:
    return create_node_core(req, ports, kind="issue")
