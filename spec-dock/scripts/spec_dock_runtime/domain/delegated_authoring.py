from __future__ import annotations

from dataclasses import dataclass
import re
from typing import TYPE_CHECKING

from spec_dock_runtime.domain.artifacts import parse_artifact_filename

if TYPE_CHECKING:
    from pathlib import Path

CANONICAL_DOC_NAMES: tuple[str, ...] = ("requirement.md", "design.md", "plan.md", "report.md")
FORBIDDEN_ROOT_NAMES: tuple[str, ...] = (".agents", ".codex", ".github", "src", "tests")
NON_EDITABLE_ARTIFACT_STATE_FIELDS: tuple[str, ...] = ("status", "adoption_status", "authority")
NON_EDITABLE_ARTIFACT_STATE_VALUES: tuple[str, ...] = (
    "accepted",
    "adopted",
    "partially_adopted",
    "integrated",
    "partially_integrated",
    "rejected",
    "superseded",
    "blocked",
    "stale",
)
EDITABLE_ARTIFACT_STATE_RE = re.compile(r"(?im)^\s*(?:status\s*:\s*proposed|adoption_status\s*:\s*unreviewed)\b")
REQUIRED_ARTIFACT_FRONTMATTER_FIELDS: tuple[str, ...] = (
    "created_by_role",
    "scope_id",
    "source_paths",
    "intended_targets",
    "adoption_status",
    "reflected_to",
    "diff_guard_result",
)
REQUIRED_ARTIFACT_FRONTMATTER_RE: dict[str, re.Pattern[str]] = {
    "created_by_role": re.compile(
        r"(?m)^\s*created_by_role\s*:\s*"
        r"(?:"
        r"system-architect|implementation-planner|"
        r"\"(?:system-architect|implementation-planner)\"|"
        r"'(?:system-architect|implementation-planner)'"
        r")\s*$"
    ),
    "scope_id": re.compile(r"(?m)^\s*scope_id\s*:\s*(?:\S+|\"[^\"]+\"|'[^']+')\s*$"),
    "source_paths": re.compile(r"(?m)^\s*source_paths\s*:"),
    "intended_targets": re.compile(r"(?m)^\s*intended_targets\s*:"),
    "adoption_status": re.compile(r"(?im)^\s*adoption_status\s*:\s*['\"]?unreviewed['\"]?\s*$"),
    "reflected_to": re.compile(r"(?m)^\s*reflected_to\s*:\s*\[\s*\]\s*$"),
    "diff_guard_result": re.compile(
        r"(?m)^\s*diff_guard_result\s*:\s*['\"]?(?:pending|passed|failed|not_run)['\"]?\s*$"
    ),
}
AUTHORIZED_ROLE_FRONTMATTER: dict[str, str] = {
    "system-architect": "system-architect",
    "implementation-planner": "implementation-planner",
}


@dataclass(frozen=True)
class DelegatedAuthoringResult:
    ok: bool
    status: str
    reason: str
    role: str
    scope_id: str
    target: str
    host_surface: str
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiffGuardEntry:
    status: str
    path: Path
    original_path: Path | None = None
    pre_change_text: str | None = None
    pre_change_error: str | None = None


@dataclass(frozen=True)
class DiffGuardResult:
    ok: bool
    status: str
    reason: str
    scope_id: str
    details: tuple[str, ...] = ()


def deprecated_manifest_result(
    *,
    role: str,
    scope_id: str,
    target: str,
    host_surface: str,
) -> DelegatedAuthoringResult:
    return DelegatedAuthoringResult(
        ok=False,
        status="deprecated",
        reason="deprecated_scope_local_discussion_drafts",
        role=role,
        scope_id=scope_id,
        target=target,
        host_surface=host_surface,
        details=("manifest_artifacts_disabled=true",),
    )


def evaluate_diff_guard(
    *,
    authorized_role: str | None = None,
    scope_id: str,
    repo_root: Path,
    scope_dir: Path,
    entries: tuple[DiffGuardEntry, ...],
    allow_existing_discussions: tuple[Path, ...] = (),
) -> DiffGuardResult:
    artifacts_dir = scope_dir / "artifacts"
    allowed_updates = {_normalize_repo_path(path, repo_root) for path in allow_existing_discussions}
    details: list[str] = []
    ok = True
    allowed_new_artifact_count = 0

    artifact_boundary_errors = _artifact_boundary_errors(
        repo_root=repo_root,
        artifacts_dir=artifacts_dir,
    )
    if artifact_boundary_errors:
        ok = False
        details.extend(artifact_boundary_errors)

    if not entries:
        details.append("detail=no_diff")

    for entry in entries:
        path = repo_root / _normalize_repo_path(entry.path, repo_root)
        rel_path = _display_path(path, repo_root)
        reason = _classify_entry(
            entry,
            scope_id=scope_id,
            authorized_role=authorized_role,
            repo_root=repo_root,
            scope_dir=scope_dir,
            artifacts_dir=artifacts_dir,
            allowed_updates=allowed_updates,
        )
        if reason is None:
            if _is_create_status(entry.status):
                allowed_new_artifact_count += 1
            details.append(f"allowed path={rel_path}")
        else:
            ok = False
            details.append(f"blocked path={rel_path} reason={reason}")

    if allowed_new_artifact_count != 1:
        ok = False
        details.append(
            f"blocked path={_display_path(artifacts_dir, repo_root)} "
            f"reason=expected_exactly_one_new_artifact_draft count={allowed_new_artifact_count}"
        )

    return DiffGuardResult(
        ok=ok,
        status="pass" if ok else "blocked",
        reason="ok" if ok else "forbidden_diff",
        scope_id=scope_id,
        details=tuple(details),
    )


def _artifact_boundary_errors(*, repo_root: Path, artifacts_dir: Path) -> tuple[str, ...]:
    rel_artifacts_dir = _display_path(artifacts_dir, repo_root)
    if artifacts_dir.is_symlink():
        return (f"blocked path={rel_artifacts_dir} reason=artifacts_dir_symlink",)
    if not artifacts_dir.exists():
        return ()
    if not artifacts_dir.is_dir():
        return (f"blocked path={rel_artifacts_dir} reason=artifacts_dir_not_directory",)
    try:
        symlink_children = sorted(
            child
            for child in artifacts_dir.iterdir()
            if child.is_symlink() and parse_artifact_filename(child.name) is not None
        )
    except OSError as error:
        return (f"blocked path={rel_artifacts_dir} reason=artifacts_dir_unreadable detail={error}",)
    return tuple(
        f"blocked path={_display_path(child, repo_root)} reason=artifact_symlink" for child in symlink_children
    )


def _classify_entry(
    entry: DiffGuardEntry,
    *,
    scope_id: str,
    authorized_role: str | None,
    repo_root: Path,
    scope_dir: Path,
    artifacts_dir: Path,
    allowed_updates: set[Path],
) -> str | None:
    del allowed_updates

    rel_path = _normalize_repo_path(entry.path, repo_root)
    abs_path = repo_root / rel_path
    status = entry.status
    if len(status) != 2:
        return "invalid_status"
    if _is_unmerged_status(status):
        return "unmerged_status"
    if entry.original_path is not None or status[0] in ("R", "C") or status[1] in ("R", "C"):
        return "rename_or_copy"
    if status[0] == "D" or status[1] == "D":
        return "delete"
    if any(part.startswith(".env") for part in rel_path.parts):
        return "env_file"
    if _is_forbidden_root_path(rel_path):
        return "forbidden_root"
    if rel_path.name in CANONICAL_DOC_NAMES:
        return "canonical_doc"
    if abs_path.is_symlink():
        return "symlink"
    if _is_under(abs_path, scope_dir / "discussions"):
        return "future_noncompliant_discussion_output"
    if _is_under(abs_path, artifacts_dir) and not _is_direct_child_of(abs_path, artifacts_dir):
        return "nested_artifact_output"
    if not _is_direct_child_of(abs_path, artifacts_dir):
        return "outside_target_artifacts"
    if abs_path.suffix != ".md":
        return "non_markdown"
    if parse_artifact_filename(abs_path.name) is None:
        return "artifact_name_noncompliant"
    if _is_mixed_index_and_worktree_status(status):
        return "mixed_staged_unstaged_artifact"
    if _is_create_status(status):
        create_error = _validate_new_artifact_create(abs_path, scope_id=scope_id, authorized_role=authorized_role)
        if create_error is not None:
            return create_error
        return None
    if _is_update_status(status):
        return "existing_artifact_update_unsupported"
    return "unsupported_status"


def _is_create_status(status: str) -> bool:
    return status == "??" or status[0] == "A" or status[1] == "A"


def _is_update_status(status: str) -> bool:
    return status[0] in ("M", "T") or status[1] in ("M", "T")


def _is_unmerged_status(status: str) -> bool:
    return "U" in status or status in {"AA", "DD"}


def _is_mixed_index_and_worktree_status(status: str) -> bool:
    return status[0] not in (" ", "?") and status[1] not in (" ", "?")


def _validate_new_artifact_create(path: Path, *, scope_id: str, authorized_role: str | None) -> str | None:
    if not path.is_file():
        return "new_artifact_missing"
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return "new_artifact_non_utf8"
    metadata = _frontmatter_metadata(text)
    if _has_non_editable_artifact_state(metadata):
        return "new_artifact_claims_non_editable_state"
    if not EDITABLE_ARTIFACT_STATE_RE.search(metadata):
        return "new_artifact_missing_proposed_state"
    provenance_error = _validate_required_artifact_frontmatter(
        metadata, scope_id=scope_id, authorized_role=authorized_role
    )
    if provenance_error is not None:
        return provenance_error
    return None


def _validate_required_artifact_frontmatter(metadata: str, *, scope_id: str, authorized_role: str | None) -> str | None:
    duplicated_key = _duplicate_artifact_frontmatter_provenance_key(metadata)
    if duplicated_key is not None:
        return f"new_artifact_duplicate_provenance:{duplicated_key}"
    missing = tuple(
        field
        for field in REQUIRED_ARTIFACT_FRONTMATTER_FIELDS
        if not REQUIRED_ARTIFACT_FRONTMATTER_RE[field].search(metadata)
    )
    if missing:
        return f"new_artifact_missing_provenance:{','.join(missing)}"
    if _frontmatter_scalar_value(metadata, "scope_id") != scope_id:
        return "new_artifact_scope_id_mismatch"
    if authorized_role is not None:
        expected_created_by_role = AUTHORIZED_ROLE_FRONTMATTER.get(authorized_role)
        if expected_created_by_role is None:
            return "new_artifact_authorized_role_unknown"
        if _frontmatter_scalar_value(metadata, "created_by_role") != expected_created_by_role:
            return "new_artifact_created_by_role_mismatch"
    if not _frontmatter_list_has_value(metadata, "source_paths"):
        return "new_artifact_empty_source_paths"
    if not _frontmatter_list_has_value(metadata, "intended_targets"):
        return "new_artifact_empty_intended_targets"
    return None


def _has_non_editable_artifact_state(metadata: str) -> bool:
    return any(
        _frontmatter_normalized_scalar_value(metadata, field) in NON_EDITABLE_ARTIFACT_STATE_VALUES
        for field in NON_EDITABLE_ARTIFACT_STATE_FIELDS
    )


def _duplicate_artifact_frontmatter_provenance_key(metadata: str) -> str | None:
    for key in REQUIRED_ARTIFACT_FRONTMATTER_FIELDS:
        key_re = re.compile(rf"^\s*{re.escape(key)}\s*:")
        if sum(1 for line in metadata.splitlines() if key_re.match(line)) > 1:
            return key
    return None


def _frontmatter_list_has_value(metadata: str, key: str) -> bool:
    lines = metadata.splitlines()
    key_re = re.compile(rf"^\s*{re.escape(key)}\s*:\s*(.*)$")
    for index, line in enumerate(lines):
        match = key_re.match(line)
        if match is None:
            continue
        inline = match.group(1).strip()
        if inline:
            inline_match = re.fullmatch(r"\[(.*)\]", inline)
            if inline_match is None:
                return False
            items = (item.strip().strip("'\"") for item in inline_match.group(1).split(","))
            return any(item for item in items)
        for child in lines[index + 1 :]:
            if child and not child[0].isspace():
                return False
            child_match = re.match(r"^\s*-\s*(.*)$", child)
            if child_match is not None and _frontmatter_list_item_has_value(child_match.group(1)):
                return True
        return False
    return False


def _frontmatter_list_item_has_value(item: str) -> bool:
    value = item.strip()
    while len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1].strip()
    return bool(value.strip("[]'\" "))


def _frontmatter_inline_list_has_value(metadata: str, key: str, value: str) -> bool:
    key_re = re.compile(rf"^\s*{re.escape(key)}\s*:\s*\[(.*?)\]\s*$")
    for line in metadata.splitlines():
        match = key_re.match(line)
        if match is None:
            continue
        items = (item.strip().strip("'\"") for item in match.group(1).split(","))
        return value in items
    return False


def _frontmatter_scalar_value(metadata: str, key: str) -> str | None:
    key_re = re.compile(rf"^\s*{re.escape(key)}\s*:\s*(.*?)\s*$")
    for line in metadata.splitlines():
        match = key_re.match(line)
        if match is None:
            continue
        raw = match.group(1).strip()
        if not raw:
            return None
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
            value = raw[1:-1]
            return value or None
        return raw
    return None


def _frontmatter_normalized_scalar_value(metadata: str, key: str) -> str | None:
    value = _frontmatter_scalar_value(metadata, key)
    if value is None:
        return None
    value = _strip_yaml_inline_comment(value).strip()
    while len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1].strip()
    return value.lower() or None


def _strip_yaml_inline_comment(value: str) -> str:
    quote: str | None = None
    for index, char in enumerate(value):
        if quote is not None:
            if char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
            continue
        if char == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index]
    return value


def _frontmatter_metadata(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    metadata_lines: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            return "\n".join(metadata_lines)
        metadata_lines.append(line)
    return ""


def _is_forbidden_root_path(rel_path: Path) -> bool:
    parts = rel_path.parts
    if not parts:
        return False
    if parts[0] in FORBIDDEN_ROOT_NAMES:
        return True
    return bool(parts[0].startswith(".env"))


def _is_direct_child_of(path: Path, parent: Path) -> bool:
    try:
        rel = path.relative_to(parent)
    except ValueError:
        return False
    return len(rel.parts) == 1


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _normalize_repo_path(path: Path, repo_root: Path) -> Path:
    if path.is_absolute():
        try:
            return path.resolve(strict=False).relative_to(repo_root.resolve(strict=False))
        except ValueError:
            return path
    return path


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()
