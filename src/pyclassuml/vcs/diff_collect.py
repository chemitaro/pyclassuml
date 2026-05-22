"""Collect raw changed files from Git for diff command inputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import subprocess

from pyclassuml.model import (
    AnalysisConfig,
    CommandRequest,
    Diagnostic,
    DiagnosticSeverity,
    DiffBaseResolution,
    DiffCurrentState,
    ExecutionContext,
    FailureReason,
    OriginSeam,
    Recoverability,
)


@dataclass(frozen=True)
class ChangedLineRange:
    start: int
    end: int
    is_deletion_only: bool = False
    deleted_lines: tuple[str, ...] = ()
    is_before_first_line_deletion: bool = field(default=False, compare=False)

    def __post_init__(self) -> None:
        if (
            isinstance(self.start, bool)
            or isinstance(self.end, bool)
            or not isinstance(self.is_deletion_only, bool)
            or not isinstance(self.is_before_first_line_deletion, bool)
            or not isinstance(self.start, int)
            or not isinstance(self.end, int)
            or self.start < 1
            or self.end < self.start
        ):
            raise ValueError("changed line range must be a positive inclusive range")
        deleted_lines = tuple(self.deleted_lines)
        for line in deleted_lines:
            if not isinstance(line, str):
                raise ValueError("deleted_lines must contain str values")
        object.__setattr__(self, "deleted_lines", deleted_lines)


@dataclass(frozen=True)
class ChangedFileEntry:
    current_project_relative_path: str
    change_kind: str
    previous_project_relative_path: str | None = None
    current_changed_line_ranges: tuple[ChangedLineRange, ...] = field(default=(), compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.current_project_relative_path, str) or self.current_project_relative_path == "":
            raise ValueError("current_project_relative_path must be a non-empty str")
        if self.change_kind not in {"added", "modified", "renamed"}:
            raise ValueError("change_kind must be added, modified, or renamed")
        if self.previous_project_relative_path is not None and (
            not isinstance(self.previous_project_relative_path, str) or self.previous_project_relative_path == ""
        ):
            raise ValueError("previous_project_relative_path must be a non-empty str or None")
        ranges = tuple(self.current_changed_line_ranges)
        for line_range in ranges:
            if not isinstance(line_range, ChangedLineRange):
                raise ValueError("current_changed_line_ranges must contain ChangedLineRange values")
        object.__setattr__(self, "current_changed_line_ranges", ranges)


@dataclass(frozen=True)
class ChangedFileCollection:
    entries: tuple[ChangedFileEntry, ...]
    base_resolution: DiffBaseResolution

    def __post_init__(self) -> None:
        entries = tuple(self.entries)
        for entry in entries:
            if not isinstance(entry, ChangedFileEntry):
                raise ValueError("entries must contain ChangedFileEntry values")
        if not isinstance(self.base_resolution, DiffBaseResolution):
            raise ValueError("base_resolution must be DiffBaseResolution")
        object.__setattr__(self, "entries", entries)


@dataclass(frozen=True)
class VcsDiffCollection:
    collection: ChangedFileCollection | None
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        if self.collection is not None and not isinstance(self.collection, ChangedFileCollection):
            raise ValueError("collection must be ChangedFileCollection or None")
        diagnostics = tuple(self.diagnostics)
        for diagnostic in diagnostics:
            if not isinstance(diagnostic, Diagnostic):
                raise ValueError("diagnostics must contain Diagnostic values")
        object.__setattr__(self, "diagnostics", diagnostics)


class VcsDiffError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def collect_diff_files(
    request: CommandRequest,
    context: ExecutionContext,
    config: AnalysisConfig,
) -> VcsDiffCollection:
    """Collect project-root-relative changed files without scope filtering."""

    base_ref = request.cli_options.diff.base_ref if request.cli_options.diff is not None else None
    diagnostics: list[Diagnostic] = []
    vcs_root = context.vcs_root

    try:
        _ensure_git_repository(vcs_root)
        base_resolution = _resolve_base_ref(vcs_root, base_ref)
        if base_resolution.resolution_kind == "initial_commit_fallback":
            diagnostics.append(_initial_commit_fallback_diagnostic(base_resolution.resolved_base_ref))

        entries = _tracked_entries(
            vcs_root,
            context.project_root,
            base_resolution.resolved_base_ref,
            config.diff_current_state,
        )

        if config.diff_current_state is DiffCurrentState.WORKING_TREE and config.diff_include_untracked:
            entries.extend(_untracked_entries(vcs_root, context.project_root))
        elif config.diff_current_state is DiffCurrentState.HEAD and config.diff_include_untracked:
            diagnostics.append(
                Diagnostic(
                    severity=DiagnosticSeverity.WARNING,
                    code="head_untracked_noop",
                    message="include_untracked has no effect when diff current_state is head",
                    origin_seam=OriginSeam.VCS,
                    recoverability=Recoverability.RECOVERABLE,
                    failure_reason=None,
                )
            )

        return VcsDiffCollection(
            collection=ChangedFileCollection(
                entries=_dedupe_and_sort(entries),
                base_resolution=base_resolution,
            ),
            diagnostics=tuple(diagnostics),
        )
    except VcsDiffError as exc:
        return VcsDiffCollection(
            collection=None,
            diagnostics=(
                Diagnostic(
                    severity=DiagnosticSeverity.ERROR,
                    code=exc.code,
                    message=exc.message,
                    origin_seam=OriginSeam.VCS,
                    recoverability=Recoverability.FATAL,
                    failure_reason=FailureReason.VCS_READ_FAILURE,
                ),
            ),
        )


def read_base_file_text(
    vcs_root: Path,
    project_root: Path,
    base_ref: str,
    project_relative_path: str,
    *,
    missing_ok: bool = False,
) -> str | None:
    """Read a base-revision file blob without checking it out."""

    vcs_path = _git_pathspec(vcs_root, project_root / project_relative_path)
    _verify_base_ref(vcs_root, base_ref)
    result = _run_git(vcs_root, ("show", f"{base_ref}:{vcs_path}"), check=False)
    if result.returncode != 0:
        if missing_ok and _base_blob_is_absent(vcs_root, base_ref, vcs_path):
            return None
        stderr = result.stderr.decode(errors="replace")
        raise VcsDiffError(
            "git_diff_read_failure",
            f"Git base blob could not be read: {base_ref}:{vcs_path}: {stderr}",
        )
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise VcsDiffError(
            "git_diff_parse_failure",
            f"Git base blob is not valid UTF-8: {base_ref}:{vcs_path}: {exc}",
        ) from exc


def _base_blob_is_absent(vcs_root: Path, base_ref: str, vcs_path: str) -> bool:
    result = _run_git(vcs_root, ("ls-tree", "-z", base_ref, "--", vcs_path), check=False)
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace")
        raise VcsDiffError(
            "git_diff_read_failure",
            f"Git base tree could not be inspected: {base_ref}:{vcs_path}: {stderr}",
        )
    return result.stdout == b""


def _ensure_git_repository(project_root: Path) -> None:
    result = _run_git(project_root, ("rev-parse", "--is-inside-work-tree"))
    if result.stdout.strip() != b"true":
        raise VcsDiffError("git_diff_read_failure", f"project_root is not inside a Git work tree: {project_root}")


def _verify_base_ref(project_root: Path, base_ref: str) -> None:
    result = _run_git(project_root, ("rev-parse", "--verify", base_ref), check=False)
    if result.returncode != 0:
        raise VcsDiffError("invalid_base_ref", f"base ref is not a valid Git revision: {base_ref}")


def _resolve_base_ref(vcs_root: Path, requested_base_ref: str | None) -> DiffBaseResolution:
    if requested_base_ref is not None:
        _verify_base_ref(vcs_root, requested_base_ref)
        return DiffBaseResolution(
            requested_base_ref=requested_base_ref,
            resolved_base_ref=requested_base_ref,
            resolution_kind="explicit_base",
            candidate_ref=None,
        )

    _verify_head_commit(vcs_root)
    if _current_branch_is_default_branch(vcs_root):
        return _initial_commit_base_resolution(vcs_root)

    for candidate_ref in _default_branch_candidates(vcs_root):
        result = _run_git(vcs_root, ("merge-base", candidate_ref, "HEAD"), check=False)
        if result.returncode == 0:
            resolved_base = _decode_single_git_line(result.stdout, "merge-base")
            return DiffBaseResolution(
                requested_base_ref=None,
                resolved_base_ref=resolved_base,
                resolution_kind="default_branch_merge_base",
                candidate_ref=candidate_ref,
            )
    return _initial_commit_base_resolution(vcs_root)


def _verify_head_commit(vcs_root: Path) -> None:
    result = _run_git(vcs_root, ("rev-parse", "--verify", "HEAD^{commit}"), check=False)
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace")
        raise VcsDiffError("git_diff_read_failure", f"Git repository has no HEAD commit: {stderr}")


def _current_branch_is_default_branch(vcs_root: Path) -> bool:
    current_branch = _current_branch_name(vcs_root)
    if current_branch is None:
        return False

    origin_head_target = _origin_head_target(vcs_root)
    if origin_head_target is not None:
        return current_branch == _remote_default_branch_name(origin_head_target)

    return current_branch in {"main", "develop", "master"}


def _current_branch_name(vcs_root: Path) -> str | None:
    result = _run_git(vcs_root, ("symbolic-ref", "--quiet", "--short", "HEAD"), check=False)
    if result.returncode != 0:
        return None
    return _decode_single_git_line(result.stdout, "symbolic-ref HEAD")


def _origin_head_target(vcs_root: Path) -> str | None:
    result = _run_git(vcs_root, ("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"), check=False)
    if result.returncode != 0:
        return None
    return _decode_single_git_line(result.stdout, "origin/HEAD")


def _default_branch_candidates(vcs_root: Path) -> tuple[str, ...]:
    raw_candidates = []
    origin_head_target = _origin_head_target(vcs_root)
    if origin_head_target is not None:
        raw_candidates.append(_remote_candidate_ref(origin_head_target))
    raw_candidates.extend(("origin/main", "origin/develop", "origin/master", "main", "develop", "master"))

    candidates = []
    seen = set()
    for candidate in raw_candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if _ref_exists(vcs_root, candidate):
            candidates.append(candidate)
    return tuple(candidates)


def _remote_candidate_ref(origin_head_target: str) -> str:
    if origin_head_target.startswith("refs/remotes/"):
        return origin_head_target.removeprefix("refs/remotes/")
    return origin_head_target


def _remote_default_branch_name(origin_head_target: str) -> str:
    candidate = _remote_candidate_ref(origin_head_target)
    if candidate.startswith("origin/"):
        return candidate.removeprefix("origin/")
    return candidate


def _ref_exists(vcs_root: Path, ref: str) -> bool:
    result = _run_git(vcs_root, ("rev-parse", "--verify", ref), check=False)
    return result.returncode == 0


def _initial_commit_base_resolution(vcs_root: Path) -> DiffBaseResolution:
    result = _run_git(vcs_root, ("rev-list", "--max-parents=0", "HEAD"), check=False)
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace")
        raise VcsDiffError("git_diff_read_failure", f"Git initial commit could not be resolved: {stderr}")
    initial_commit = _decode_single_git_line(result.stdout, "initial commit")
    return DiffBaseResolution(
        requested_base_ref=None,
        resolved_base_ref=initial_commit,
        resolution_kind="initial_commit_fallback",
        candidate_ref=None,
    )


def _initial_commit_fallback_diagnostic(resolved_base_ref: str) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.WARNING,
        code="diff_base_initial_commit_fallback",
        message=(
            "No-base diff could not resolve a branch-start base from default branch candidates; "
            f"using initial commit object {resolved_base_ref} as the resolved base. "
            "Specify --base <ref> to choose an explicit base."
        ),
        origin_seam=OriginSeam.VCS,
        recoverability=Recoverability.DEGRADED_OUTPUT,
        failure_reason=None,
    )


def _decode_single_git_line(output: bytes, subject: str) -> str:
    lines = [line for line in output.decode("utf-8", errors="replace").splitlines() if line]
    if not lines:
        raise VcsDiffError("git_diff_read_failure", f"Git {subject} output was empty")
    return lines[0]


def _tracked_entries(
    vcs_root: Path,
    project_root: Path,
    base_ref: str,
    current_state: DiffCurrentState,
) -> list[ChangedFileEntry]:
    args = ["diff", "--relative", "--name-status", "-z", "--find-renames", base_ref]
    if current_state is DiffCurrentState.HEAD:
        args.append("HEAD")
    args.extend(("--", _git_pathspec(vcs_root, project_root)))
    result = _run_git(vcs_root, tuple(args))
    entries = _parse_name_status(result.stdout)
    return [
        _project_relative_entry(
            _entry_with_current_changed_line_ranges(vcs_root, base_ref, current_state, entry),
            vcs_root,
            project_root,
        )
        for entry in entries
        if _entry_is_under_project(entry, vcs_root, project_root)
    ]


def _untracked_entries(vcs_root: Path, project_root: Path) -> list[ChangedFileEntry]:
    result = _run_git(
        vcs_root,
        ("ls-files", "-z", "--others", "--exclude-standard", "--", _git_pathspec(vcs_root, project_root)),
    )
    return [
        ChangedFileEntry(
            current_project_relative_path=_project_relative_vcs_path(path, vcs_root, project_root),
            change_kind="added",
        )
        for path in _decode_nul_paths(result.stdout)
    ]


def _git_pathspec(vcs_root: Path, project_root: Path) -> str:
    try:
        relative = project_root.resolve().relative_to(vcs_root.resolve())
    except ValueError:
        return "."
    return "." if relative == Path(".") else relative.as_posix()


def _entry_is_under_project(entry: ChangedFileEntry, vcs_root: Path, project_root: Path) -> bool:
    return _vcs_relative_path_is_under_project(entry.current_project_relative_path, vcs_root, project_root)


def _vcs_relative_path_is_under_project(relative_path: str, vcs_root: Path, project_root: Path) -> bool:
    try:
        (vcs_root / relative_path).resolve().relative_to(project_root.resolve())
    except ValueError:
        return False
    return True


def _project_relative_vcs_path(relative_path: str, vcs_root: Path, project_root: Path) -> str:
    return (vcs_root / relative_path).resolve().relative_to(project_root.resolve()).as_posix()


def _project_relative_entry(entry: ChangedFileEntry, vcs_root: Path, project_root: Path) -> ChangedFileEntry:
    previous_path = (
        _project_relative_vcs_path(entry.previous_project_relative_path, vcs_root, project_root)
        if entry.previous_project_relative_path is not None
        else None
    )
    return ChangedFileEntry(
        current_project_relative_path=_project_relative_vcs_path(
            entry.current_project_relative_path,
            vcs_root,
            project_root,
        ),
        change_kind=entry.change_kind,
        previous_project_relative_path=previous_path,
        current_changed_line_ranges=entry.current_changed_line_ranges,
    )


def _run_git(
    project_root: Path,
    args: tuple[str, ...],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    command_parts = ("git", "-C", str(project_root), *args)
    try:
        result = subprocess.run(
            command_parts,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        command = " ".join(command_parts)
        raise VcsDiffError("git_diff_read_failure", f"Git command could not be started: {command}: {exc}") from exc
    if check and result.returncode != 0:
        command = " ".join(command_parts)
        stderr = result.stderr.decode(errors="replace")
        raise VcsDiffError("git_diff_read_failure", f"Git command failed: {command}: {stderr}")
    return result


def _parse_name_status(output: bytes) -> list[ChangedFileEntry]:
    tokens = _decode_nul_paths(output)
    entries: list[ChangedFileEntry] = []
    index = 0

    while index < len(tokens):
        status = tokens[index]
        index += 1

        if status in {"A", "M", "T"}:
            path, index = _next_token(tokens, index, status)
            entries.append(
                ChangedFileEntry(
                    current_project_relative_path=path,
                    change_kind="added" if status == "A" else "modified",
                )
            )
        elif status == "D":
            _, index = _next_token(tokens, index, status)
        elif status.startswith("R") and status[1:].isdigit():
            previous_path, index = _next_token(tokens, index, status)
            current_path, index = _next_token(tokens, index, status)
            entries.append(
                ChangedFileEntry(
                    current_project_relative_path=current_path,
                    change_kind="renamed",
                    previous_project_relative_path=previous_path,
                )
            )
        else:
            raise VcsDiffError("git_diff_parse_failure", f"unsupported Git diff name-status value: {status}")

    return entries


def _entry_with_current_changed_line_ranges(
    project_root: Path,
    base_ref: str,
    current_state: DiffCurrentState,
    entry: ChangedFileEntry,
) -> ChangedFileEntry:
    args = ["diff", "--relative", "--unified=0", "--find-renames", base_ref]
    if current_state is DiffCurrentState.HEAD:
        args.append("HEAD")
    pathspecs = [entry.current_project_relative_path]
    if entry.previous_project_relative_path is not None:
        pathspecs.insert(0, entry.previous_project_relative_path)
    args.extend(("--", *pathspecs))
    result = _run_git(project_root, tuple(args))
    return ChangedFileEntry(
        current_project_relative_path=entry.current_project_relative_path,
        change_kind=entry.change_kind,
        previous_project_relative_path=entry.previous_project_relative_path,
        current_changed_line_ranges=_parse_current_changed_line_ranges(result.stdout),
    )


def _parse_current_changed_line_ranges(output: bytes) -> tuple[ChangedLineRange, ...]:
    ranges: list[ChangedLineRange] = []
    lines = output.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.startswith(b"@@ "):
            index += 1
            continue
        header = line.decode("utf-8", errors="replace")
        plus_token = next((token for token in header.split() if token.startswith("+")), None)
        if plus_token is None:
            raise VcsDiffError("git_diff_parse_failure", f"malformed Git diff hunk header: {header}")
        deleted_lines: list[bytes] = []
        index += 1
        while index < len(lines) and not lines[index].startswith(b"@@ "):
            hunk_line = lines[index]
            if hunk_line.startswith(b"diff --git "):
                break
            if hunk_line.startswith(b"-") and not hunk_line.startswith(b"--- "):
                deleted_lines.append(hunk_line[1:])
            index += 1
        if (line_range := _parse_current_hunk_range(plus_token, header, deleted_lines)) is not None:
            ranges.append(line_range)
    return tuple(ranges)


def _parse_current_hunk_range(
    plus_token: str,
    header: str,
    deleted_lines: list[bytes],
) -> ChangedLineRange | None:
    body = plus_token[1:]
    if "," in body:
        start_text, length_text = body.split(",", 1)
    else:
        start_text, length_text = body, "1"
    try:
        start = int(start_text)
        length = int(length_text)
    except ValueError as exc:
        raise VcsDiffError("git_diff_parse_failure", f"malformed Git diff hunk header: {header}") from exc
    if start < 1 or length < 0:
        if start == 0 and length == 0 and _deleted_lines_include_decorator(deleted_lines):
            return ChangedLineRange(
                start=1,
                end=1,
                is_deletion_only=True,
                deleted_lines=tuple(line.decode("utf-8", errors="replace") for line in deleted_lines),
                is_before_first_line_deletion=True,
            )
        if start == 0 and length == 0:
            return None
        raise VcsDiffError("git_diff_parse_failure", f"malformed Git diff hunk header: {header}")
    if length == 0:
        return ChangedLineRange(
            start=start,
            end=start,
            is_deletion_only=True,
            deleted_lines=tuple(line.decode("utf-8", errors="replace") for line in deleted_lines),
        )
    return ChangedLineRange(start=start, end=start + length - 1)


def _deleted_lines_include_decorator(deleted_lines: list[bytes]) -> bool:
    return any(line.lstrip().startswith(b"@") for line in deleted_lines)


def _decode_nul_paths(output: bytes) -> list[str]:
    raw_tokens = output.split(b"\0")
    if raw_tokens and raw_tokens[-1] == b"":
        raw_tokens = raw_tokens[:-1]
    try:
        return [token.decode("utf-8") for token in raw_tokens]
    except UnicodeDecodeError as exc:
        raise VcsDiffError("git_diff_parse_failure", f"Git diff output is not valid UTF-8: {exc}") from exc


def _next_token(tokens: list[str], index: int, status: str) -> tuple[str, int]:
    if index >= len(tokens) or tokens[index] == "":
        raise VcsDiffError("git_diff_parse_failure", f"malformed Git diff name-status output near status: {status}")
    return tokens[index], index + 1


def _dedupe_and_sort(entries: list[ChangedFileEntry]) -> tuple[ChangedFileEntry, ...]:
    unique = {entry.current_project_relative_path: entry for entry in entries}
    return tuple(unique[path] for path in sorted(unique))
