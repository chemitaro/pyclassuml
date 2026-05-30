from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..domain import delegated_authoring as domain


@dataclass(frozen=True)
class DelegatedAuthoringManifestRequest:
    role: str
    scope_id: str
    target: str
    host_surface: str
    input_authority_file: Path
    repo_root: Path
    specdock_dir: Path


def generate_delegated_authoring_manifest(
    req: DelegatedAuthoringManifestRequest,
) -> domain.DelegatedAuthoringResult:
    return domain.deprecated_manifest_result(
        role=req.role,
        scope_id=req.scope_id,
        target=req.target,
        host_surface=req.host_surface,
    )


@dataclass(frozen=True)
class DelegatedAuthoringDiffGuardRequest:
    role: str
    scope_id: str
    repo_root: Path
    specdock_dir: Path
    baseline_status: Path | None = None
    allow_existing_discussions: tuple[Path, ...] = ()


@dataclass(frozen=True)
class DelegatedAuthoringBaselineStatusRequest:
    repo_root: Path
    output_path: Path


def run_delegated_authoring_diff_guard(
    req: DelegatedAuthoringDiffGuardRequest,
) -> domain.DiffGuardResult:
    if req.baseline_status is None:
        return domain.DiffGuardResult(
            ok=False,
            status="blocked",
            reason="missing_baseline_status",
            scope_id=req.scope_id,
            details=("baseline_status_required=true",),
        )
    scope_dir = _resolve_scope_dir(req.specdock_dir, req.scope_id)
    if scope_dir is None:
        return domain.DiffGuardResult(
            ok=False,
            status="blocked",
            reason="scope_not_found",
            scope_id=req.scope_id,
            details=(req.scope_id,),
        )
    current = _git_status_entries(req.repo_root)
    if not current.ok:
        return domain.DiffGuardResult(
            ok=False,
            status="blocked",
            reason="git_status_failed",
            scope_id=req.scope_id,
            details=current.errors,
        )
    entries = current.entries
    if req.baseline_status is not None:
        baseline_status_path = _abs_repo_path(req.baseline_status, req.repo_root)
        if _is_inside_repo(baseline_status_path, req.repo_root):
            return domain.DiffGuardResult(
                ok=False,
                status="blocked",
                reason="baseline_status_inside_repo",
                scope_id=req.scope_id,
                details=("baseline_status_must_be_outside_repo",),
            )
        baseline = _read_status_file(baseline_status_path, repo_root=req.repo_root)
        if not baseline.ok:
            return domain.DiffGuardResult(
                ok=False,
                status="blocked",
                reason="invalid_baseline_status",
                scope_id=req.scope_id,
                details=baseline.errors,
            )
        existing_create_keys = _create_entries_existing_at_baseline_keys(
            entries,
            repo_root=req.repo_root,
            baseline_entries=baseline.entries,
            baseline_file_states=_file_state_map(baseline.file_states),
        )
        entries = tuple(entry for entry in entries if _entry_key(entry) not in existing_create_keys)
        current_head = _git_head(req.repo_root)
        if baseline.head is not None:
            if current_head is None:
                return domain.DiffGuardResult(
                    ok=False,
                    status="blocked",
                    reason="git_head_failed",
                    scope_id=req.scope_id,
                    details=("current_head_unavailable",),
                )
            if current_head != baseline.head:
                return domain.DiffGuardResult(
                    ok=False,
                    status="blocked",
                    reason="committed_side_effect",
                    scope_id=req.scope_id,
                    details=(f"baseline_head={baseline.head}", f"current_head={current_head}"),
                )
        elif current_head is not None:
            return domain.DiffGuardResult(
                ok=False,
                status="blocked",
                reason="committed_side_effect",
                scope_id=req.scope_id,
                details=("baseline_head=unborn", f"current_head={current_head}"),
            )
        baseline_path = _repo_path(baseline_status_path, req.repo_root)
        baseline_errors = _dirty_discussion_baseline_errors(
            baseline.entries,
            repo_root=req.repo_root,
            scope_dir=scope_dir,
            baseline_path=baseline_path,
        )
        if baseline_errors:
            return domain.DiffGuardResult(
                ok=False,
                status="blocked",
                reason="dirty_baseline_discussion",
                scope_id=req.scope_id,
                details=tuple(baseline_errors),
            )
        baseline_keys = _ignorable_baseline_keys(
            baseline.entries,
            repo_root=req.repo_root,
            scope_id=req.scope_id,
            scope_dir=scope_dir,
            baseline_path=baseline_path,
            baseline_file_states=_file_state_map(baseline.file_states),
            allow_existing_discussions=req.allow_existing_discussions,
        )
        current_keys = {_entry_key(entry) for entry in entries}
        baseline_only_entries = tuple(
            entry
            for entry in baseline.entries
            if _entry_key(entry) not in current_keys and _repo_path(entry.path, req.repo_root) != baseline_path
            and _entry_key(entry) not in existing_create_keys
        )
        entries = tuple(
            entry
            for entry in entries
            if _entry_key(entry) not in baseline_keys and _repo_path(entry.path, req.repo_root) != baseline_path
        ) + baseline_only_entries
    entries = _attach_pre_change_text(req.repo_root, entries)
    return domain.evaluate_diff_guard(
        authorized_role=req.role,
        scope_id=req.scope_id,
        repo_root=req.repo_root,
        scope_dir=scope_dir,
        entries=entries,
        allow_existing_discussions=req.allow_existing_discussions,
    )


def write_delegated_authoring_baseline_status(
    req: DelegatedAuthoringBaselineStatusRequest,
) -> domain.DiffGuardResult:
    output_path = _abs_repo_path(req.output_path, req.repo_root)
    if _is_inside_repo(output_path, req.repo_root):
        return domain.DiffGuardResult(
            ok=False,
            status="blocked",
            reason="baseline_status_inside_repo",
            scope_id="baseline-status",
            details=("baseline_status_must_be_outside_repo",),
        )
    current = _git_status_entries(req.repo_root)
    if not current.ok:
        return domain.DiffGuardResult(
            ok=False,
            status="blocked",
            reason="git_status_failed",
            scope_id="baseline-status",
            details=current.errors,
        )
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(_render_baseline_status(req.repo_root, current.entries), encoding="utf-8")
    except OSError as error:
        return domain.DiffGuardResult(
            ok=False,
            status="blocked",
            reason="baseline_status_write_failed",
            scope_id="baseline-status",
            details=(str(error),),
        )
    return domain.DiffGuardResult(
        ok=True,
        status="pass",
        reason="baseline_status_written",
        scope_id="baseline-status",
        details=(f"baseline_status={_repo_path(output_path, req.repo_root).as_posix()}",),
    )


@dataclass(frozen=True)
class _StatusParseResult:
    ok: bool
    entries: tuple[domain.DiffGuardEntry, ...] = ()
    errors: tuple[str, ...] = ()
    file_states: tuple["_BaselineFileState", ...] = ()
    head: str | None = None


@dataclass(frozen=True)
class _BaselineFileState:
    path: Path
    mode: str
    sha256: str


_BOUNDED_IGNORED_STATUS_PATHS = (
    ".env*",
    ".env*/**",
    "manual-tests",
    "manual-tests/**",
    ".agents",
    ".agents/**",
    ".codex",
    ".codex/**",
    ".github",
    ".github/**",
    "src",
    "src/**",
    "tests",
    "tests/**",
)

_BOUNDED_IGNORED_ENV_FILE_PATHS = (
    ".env*",
    ":(glob)**/.env*",
    ".env*/**",
    ":(glob)**/.env*/**",
)


def _git_status_entries(repo_root: Path) -> _StatusParseResult:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            cwd=repo_root,
            capture_output=True,
            check=False,
        )
    except OSError as error:
        return _StatusParseResult(ok=False, errors=(str(error),))
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        stdout = result.stdout.decode("utf-8", errors="replace").strip()
        return _StatusParseResult(ok=False, errors=(stderr or stdout,))
    current = _parse_status_z(result.stdout, repo_root=repo_root)
    ignored = _git_ignored_forbidden_entries(repo_root)
    ignored_env_files = _git_ignored_env_file_entries(repo_root)
    if not current.ok or not ignored.ok or not ignored_env_files.ok:
        return _StatusParseResult(ok=False, errors=current.errors + ignored.errors + ignored_env_files.errors)
    entries = _dedupe_entries(current.entries + ignored.entries + ignored_env_files.entries)
    return _StatusParseResult(
        ok=True,
        entries=entries,
        file_states=_file_states_for_entries(repo_root, entries),
    )


def _git_head(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    head = result.stdout.strip()
    return head or None


def _git_ignored_forbidden_entries(repo_root: Path) -> _StatusParseResult:
    try:
        result = subprocess.run(
            [
                "git",
                "status",
                "--porcelain=v1",
                "-z",
                "--ignored=matching",
                "--untracked-files=all",
                "--",
                *_BOUNDED_IGNORED_STATUS_PATHS,
            ],
            cwd=repo_root,
            capture_output=True,
            check=False,
        )
    except OSError as error:
        return _StatusParseResult(ok=False, errors=(str(error),))
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        stdout = result.stdout.decode("utf-8", errors="replace").strip()
        return _StatusParseResult(ok=False, errors=(stderr or stdout,))
    parsed = _parse_status_z(result.stdout, repo_root=repo_root)
    if not parsed.ok:
        return parsed
    return _StatusParseResult(
        ok=True,
        entries=tuple(entry for entry in parsed.entries if entry.status == "!!"),
    )


def _git_ignored_env_file_entries(repo_root: Path) -> _StatusParseResult:
    try:
        result = subprocess.run(
            [
                "git",
                "ls-files",
                "--others",
                "--ignored",
                "--exclude-standard",
                "-z",
                "--",
                *_BOUNDED_IGNORED_ENV_FILE_PATHS,
            ],
            cwd=repo_root,
            capture_output=True,
            check=False,
        )
    except OSError as error:
        return _StatusParseResult(ok=False, errors=(str(error),))
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        stdout = result.stdout.decode("utf-8", errors="replace").strip()
        return _StatusParseResult(ok=False, errors=(stderr or stdout,))
    entries = tuple(
        domain.DiffGuardEntry(status="!!", path=_repo_path(Path(_decode_status_path_bytes(path)), repo_root))
        for path in result.stdout.split(b"\0")
        if path
    )
    return _StatusParseResult(ok=True, entries=entries)


def _create_entries_existing_at_baseline_keys(
    entries: tuple[domain.DiffGuardEntry, ...],
    *,
    repo_root: Path,
    baseline_entries: tuple[domain.DiffGuardEntry, ...],
    baseline_file_states: dict[Path, tuple[str, str]],
) -> set[tuple[str, str, str | None]]:
    baseline_create_keys = {
        _entry_key(entry) for entry in baseline_entries if entry.status in ("!!", "??")
    }
    keys: set[tuple[str, str, str | None]] = set()
    for entry in entries:
        if not (entry.status == "!!" or entry.status == "??"):
            continue
        if _entry_key(entry) not in baseline_create_keys:
            continue
        if _matches_baseline_file_state(
            entry,
            repo_root=repo_root,
            baseline_file_states=baseline_file_states,
        ):
            keys.add(_entry_key(entry))
    return keys


def _read_status_file(path: Path, *, repo_root: Path) -> _StatusParseResult:
    if not path.is_file():
        return _StatusParseResult(ok=False, errors=(f"missing_baseline_status={path}",))
    try:
        return _parse_status_text(path.read_text(encoding="utf-8"), repo_root=repo_root)
    except UnicodeDecodeError as error:
        return _StatusParseResult(ok=False, errors=(f"invalid_baseline_status_encoding={error}",))


def _parse_status_text(text: str, *, repo_root: Path) -> _StatusParseResult:
    entries: list[domain.DiffGuardEntry] = []
    file_states: list[_BaselineFileState] = []
    errors: list[str] = []
    head: str | None = None
    for raw_line in text.splitlines():
        if not raw_line:
            continue
        if raw_line.startswith("# head\t"):
            parts = raw_line.split("\t")
            if len(parts) != 2 or not parts[1]:
                errors.append(f"invalid_baseline_head={raw_line}")
                continue
            head = parts[1]
            continue
        if raw_line.startswith("# file-state-sha256\t"):
            parts = raw_line.split("\t")
            if len(parts) != 4 or not parts[1] or not parts[2] or not parts[3]:
                errors.append(f"invalid_baseline_file_state={raw_line}")
                continue
            file_states.append(
                _BaselineFileState(
                    path=_repo_path(Path(_decode_baseline_path_field(parts[1])), repo_root),
                    mode=parts[2],
                    sha256=parts[3],
                )
            )
            continue
        if raw_line.startswith("#"):
            continue
        if len(raw_line) < 4 or raw_line[2] != " ":
            errors.append(f"invalid_status_line={raw_line}")
            continue
        status = raw_line[:2]
        path_text = raw_line[3:]
        original_path = None
        rename_paths = _split_porcelain_text_rename_paths(path_text) if _is_rename_or_copy_status(status) else None
        if rename_paths is not None:
            left, right = rename_paths
            original_path = _repo_path(Path(_decode_porcelain_text_path(left)), repo_root)
            path_text = right
        if not path_text:
            errors.append(f"invalid_status_line={raw_line}")
            continue
        entries.append(
            domain.DiffGuardEntry(
                status=status,
                path=_repo_path(Path(_decode_porcelain_text_path(path_text)), repo_root),
                original_path=original_path,
            )
        )
    if errors:
        return _StatusParseResult(ok=False, errors=tuple(errors))
    return _StatusParseResult(ok=True, entries=tuple(entries), file_states=tuple(file_states), head=head)


def _parse_status_z(data: bytes, *, repo_root: Path) -> _StatusParseResult:
    entries: list[domain.DiffGuardEntry] = []
    errors: list[str] = []
    parts = data.split(b"\0")
    if parts and parts[-1] == b"":
        parts.pop()
    index = 0
    while index < len(parts):
        raw = parts[index]
        if len(raw) < 4 or raw[2:3] != b" ":
            errors.append(f"invalid_status_record={raw!r}")
            index += 1
            continue
        try:
            status = raw[:2].decode("ascii")
        except UnicodeDecodeError as error:
            errors.append(f"invalid_status_encoding={error}")
            index += 1
            continue
        path_text = _decode_status_path_bytes(raw[3:])
        original_path = None
        index += 1
        if _is_rename_or_copy_status(status):
            if index >= len(parts):
                errors.append(f"missing_original_path={path_text}")
                continue
            original_path = _repo_path(Path(_decode_status_path_bytes(parts[index])), repo_root)
            index += 1
        entries.append(
            domain.DiffGuardEntry(
                status=status,
                path=_repo_path(Path(path_text), repo_root),
                original_path=original_path,
            )
        )
    if errors:
        return _StatusParseResult(ok=False, errors=tuple(errors))
    return _StatusParseResult(ok=True, entries=tuple(entries))


def _render_baseline_status(repo_root: Path, entries: tuple[domain.DiffGuardEntry, ...]) -> str:
    lines = ["# spec-dock delegated-authoring baseline-status v1"]
    head = _git_head(repo_root)
    if head is not None:
        lines.append(f"# head\t{head}")
    for entry in entries:
        state = _file_state(repo_root / _repo_path(entry.path, repo_root))
        if state is not None:
            mode, digest = state
            lines.append(
                f"# file-state-sha256\t{_encode_baseline_path_field(_repo_path(entry.path, repo_root))}"
                f"\t{mode}\t{digest}"
            )
    for entry in entries:
        path_text = _encode_baseline_path_field(_repo_path(entry.path, repo_root))
        if entry.original_path is not None:
            path_text = f"{_encode_baseline_path_field(entry.original_path)} -> {path_text}"
        lines.append(f"{entry.status} {path_text}")
    return "\n".join(lines) + "\n"


def _file_sha256(path: Path) -> str | None:
    try:
        if path.is_symlink() or not path.is_file():
            return None
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _file_state(path: Path) -> tuple[str, str] | None:
    try:
        if path.is_symlink():
            target = os.readlink(path)
            return "symlink", hashlib.sha256(os.fsencode(target)).hexdigest()
        if path.is_dir():
            return _directory_state(path)
        if not path.is_file():
            return None
        mode = f"{path.stat().st_mode & 0o777:o}"
    except OSError:
        return None
    digest = _file_sha256(path)
    if digest is None:
        return None
    return mode, digest


def _directory_state(path: Path) -> tuple[str, str] | None:
    digest = hashlib.sha256()
    try:
        mode = f"dir:{path.stat().st_mode & 0o777:o}"
        for child in sorted(path.rglob("*"), key=lambda item: item.relative_to(path).as_posix()):
            rel = child.relative_to(path).as_posix()
            digest.update(rel.encode("utf-8", errors="surrogateescape"))
            digest.update(b"\0")
            if child.is_symlink():
                digest.update(b"symlink\0")
                digest.update(os.fsencode(os.readlink(child)))
                digest.update(b"\0")
                continue
            if child.is_dir():
                digest.update(f"dir:{child.stat().st_mode & 0o777:o}".encode("ascii"))
                digest.update(b"\0")
                continue
            if child.is_file():
                digest.update(f"file:{child.stat().st_mode & 0o777:o}".encode("ascii"))
                digest.update(b"\0")
                file_digest = _file_sha256(child)
                if file_digest is None:
                    return None
                digest.update(file_digest.encode("ascii"))
                digest.update(b"\0")
                continue
            digest.update(b"other\0")
    except OSError:
        return None
    return mode, digest.hexdigest()


def _entry_key(entry: domain.DiffGuardEntry) -> tuple[str, str, str | None]:
    return (
        entry.status,
        entry.path.as_posix(),
        entry.original_path.as_posix() if entry.original_path is not None else None,
    )


def _dedupe_entries(entries: tuple[domain.DiffGuardEntry, ...]) -> tuple[domain.DiffGuardEntry, ...]:
    deduped: dict[tuple[str, str, str | None], domain.DiffGuardEntry] = {}
    for entry in entries:
        deduped.setdefault(_entry_key(entry), entry)
    return tuple(deduped.values())


def _decode_status_path_bytes(path: bytes) -> str:
    return os.fsdecode(path)


def _is_rename_or_copy_status(status: str) -> bool:
    return len(status) == 2 and (status[0] in ("R", "C") or status[1] in ("R", "C"))


def _decode_porcelain_text_path(path_text: str) -> str:
    if len(path_text) >= 2 and path_text[0] == '"' and path_text[-1] == '"':
        return _decode_baseline_path_field(path_text)
    return path_text


def _split_porcelain_text_rename_paths(path_text: str) -> tuple[str, str] | None:
    if path_text.startswith('"'):
        left_end = _quoted_path_field_end(path_text)
        if left_end is None or path_text[left_end : left_end + 4] != " -> ":
            return None
        return path_text[:left_end], path_text[left_end + 4 :]
    if " -> " not in path_text:
        return None
    left, _sep, right = path_text.partition(" -> ")
    return left, right


def _quoted_path_field_end(path_text: str) -> int | None:
    index = 1
    while index < len(path_text):
        char = path_text[index]
        if char == "\\":
            index += 2
            continue
        if char == '"':
            return index + 1
        index += 1
    return None


def _encode_baseline_path_field(path: Path) -> str:
    return json.dumps(path.as_posix(), ensure_ascii=True)


def _decode_baseline_path_field(path_text: str) -> str:
    if len(path_text) >= 2 and path_text[0] == '"' and path_text[-1] == '"':
        try:
            return json.loads(path_text)
        except json.JSONDecodeError:
            return _decode_c_quoted_path(path_text)
    return path_text


def _decode_c_quoted_path(path_text: str) -> str:
    inner = path_text[1:-1]
    out = bytearray()
    index = 0
    while index < len(inner):
        char = inner[index]
        if char != "\\":
            out.extend(char.encode("utf-8"))
            index += 1
            continue
        index += 1
        if index >= len(inner):
            out.append(ord("\\"))
            break
        escaped = inner[index]
        if escaped in {'"', "\\"}:
            out.append(ord(escaped))
            index += 1
        elif escaped == "n":
            out.append(ord("\n"))
            index += 1
        elif escaped == "t":
            out.append(ord("\t"))
            index += 1
        elif escaped == "r":
            out.append(ord("\r"))
            index += 1
        elif escaped == "b":
            out.append(ord("\b"))
            index += 1
        elif escaped == "f":
            out.append(ord("\f"))
            index += 1
        elif escaped == "a":
            out.append(0x07)
            index += 1
        elif escaped == "v":
            out.append(0x0B)
            index += 1
        elif escaped in "01234567":
            digits = escaped
            index += 1
            while index < len(inner) and len(digits) < 3 and inner[index] in "01234567":
                digits += inner[index]
                index += 1
            out.append(int(digits, 8))
        else:
            out.extend(escaped.encode("utf-8"))
            index += 1
    return out.decode("utf-8", errors="replace")


def _attach_pre_change_text(
    repo_root: Path,
    entries: tuple[domain.DiffGuardEntry, ...],
) -> tuple[domain.DiffGuardEntry, ...]:
    enriched: list[domain.DiffGuardEntry] = []
    for entry in entries:
        text = None
        error = None
        if _is_update_status(entry.status) and entry.original_path is None:
            head_result = _git_head_text(repo_root, _repo_path(entry.path, repo_root))
            text = head_result.text
            error = head_result.error
        if text is None and error is None:
            enriched.append(entry)
        else:
            enriched.append(
                domain.DiffGuardEntry(
                    status=entry.status,
                    path=entry.path,
                    original_path=entry.original_path,
                    pre_change_text=text,
                    pre_change_error=error,
                )
            )
    return tuple(enriched)


@dataclass(frozen=True)
class _GitHeadTextResult:
    text: str | None = None
    error: str | None = None


def _git_head_text(repo_root: Path, rel_path: Path) -> _GitHeadTextResult:
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD:{rel_path.as_posix()}"],
            cwd=repo_root,
            capture_output=True,
            check=False,
        )
    except OSError:
        return _GitHeadTextResult()
    if result.returncode != 0:
        return _GitHeadTextResult()
    try:
        return _GitHeadTextResult(text=result.stdout.decode("utf-8"))
    except UnicodeDecodeError:
        return _GitHeadTextResult(error="existing_discussion_head_non_utf8")


def _is_update_status(status: str) -> bool:
    return len(status) == 2 and (status[0] in ("M", "T") or status[1] in ("M", "T"))


def _dirty_discussion_baseline_errors(
    entries: tuple[domain.DiffGuardEntry, ...],
    *,
    repo_root: Path,
    scope_dir: Path,
    baseline_path: Path,
) -> list[str]:
    discussions_dir = scope_dir / "discussions"
    errors: list[str] = []
    for entry in entries:
        rel_path = _repo_path(entry.path, repo_root)
        if rel_path == baseline_path:
            continue
        try:
            (repo_root / rel_path).relative_to(discussions_dir)
        except ValueError:
            continue
        else:
            errors.append(f"blocked path={rel_path.as_posix()} reason=dirty_baseline_discussion")
    return errors


def _ignorable_baseline_keys(
    entries: tuple[domain.DiffGuardEntry, ...],
    *,
    repo_root: Path,
    scope_id: str,
    scope_dir: Path,
    baseline_path: Path,
    baseline_file_states: dict[Path, tuple[str, str]],
    allow_existing_discussions: tuple[Path, ...],
) -> set[tuple[str, str, str | None]]:
    keys: set[tuple[str, str, str | None]] = set()
    for entry in entries:
        if _repo_path(entry.path, repo_root) == baseline_path:
            keys.add(_entry_key(entry))
            continue
        if entry.status == "!!" and (
            _repo_path(entry.path, repo_root) not in baseline_file_states
            or _matches_baseline_file_state(
                entry,
                repo_root=repo_root,
                baseline_file_states=baseline_file_states,
            )
        ):
            keys.add(_entry_key(entry))
            continue
        baseline_entry = _attach_pre_change_text(repo_root, (entry,))[0]
        baseline_check = domain.evaluate_diff_guard(
            scope_id=scope_id,
            repo_root=repo_root,
            scope_dir=scope_dir,
            entries=(baseline_entry,),
            allow_existing_discussions=allow_existing_discussions,
        )
        if baseline_check.ok or (
            not _is_mixed_index_and_worktree_status(entry.status)
            and _matches_baseline_file_state(
                entry,
                repo_root=repo_root,
                baseline_file_states=baseline_file_states,
            )
        ):
            keys.add(_entry_key(entry))
    return keys


def _is_mixed_index_and_worktree_status(status: str) -> bool:
    return len(status) == 2 and status[0] not in (" ", "?") and status[1] not in (" ", "?")


def _matches_baseline_file_state(
    entry: domain.DiffGuardEntry,
    *,
    repo_root: Path,
    baseline_file_states: dict[Path, tuple[str, str]],
) -> bool:
    rel_path = _repo_path(entry.path, repo_root)
    expected = baseline_file_states.get(rel_path)
    if expected is None:
        return False
    actual = _file_state(repo_root / rel_path)
    return actual == expected


def _file_state_map(file_states: tuple[_BaselineFileState, ...]) -> dict[Path, tuple[str, str]]:
    return {file_state.path: (file_state.mode, file_state.sha256) for file_state in file_states}


def _file_states_for_entries(repo_root: Path, entries: tuple[domain.DiffGuardEntry, ...]) -> tuple[_BaselineFileState, ...]:
    file_states: list[_BaselineFileState] = []
    for entry in entries:
        rel_path = _repo_path(entry.path, repo_root)
        state = _file_state(repo_root / rel_path)
        if state is None:
            continue
        mode, digest = state
        file_states.append(_BaselineFileState(path=rel_path, mode=mode, sha256=digest))
    return tuple(file_states)


def _resolve_scope_dir(specdock_dir: Path, scope_id: str) -> Path | None:
    meta_paths = sorted(specdock_dir.glob(f"initiatives/**/{scope_id}*/.meta.json"))
    for meta_path in meta_paths:
        if _scope_meta_matches(meta_path, scope_id):
            return meta_path.parent
    active_issue = specdock_dir / "active" / "issue"
    if active_issue.exists():
        try:
            resolved = active_issue.resolve()
        except OSError:
            resolved = active_issue
        if _scope_meta_matches(resolved / ".meta.json", scope_id):
            return resolved
    return None


def _scope_meta_matches(meta_path: Path, scope_id: str) -> bool:
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return data.get("id") == scope_id


def _repo_path(path: Path, repo_root: Path) -> Path:
    if path.is_absolute():
        try:
            return path.resolve(strict=False).relative_to(repo_root.resolve(strict=False))
        except ValueError:
            return path
    return path


def _abs_repo_path(path: Path, repo_root: Path) -> Path:
    if path.is_absolute():
        return path
    return repo_root / path


def _is_inside_repo(path: Path, repo_root: Path) -> bool:
    abs_path = _abs_repo_path(path, repo_root).resolve(strict=False)
    try:
        abs_path.relative_to(repo_root.resolve(strict=False))
        return True
    except ValueError:
        return False
