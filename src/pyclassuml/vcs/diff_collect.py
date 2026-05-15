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

    def __post_init__(self) -> None:
        entries = tuple(self.entries)
        for entry in entries:
            if not isinstance(entry, ChangedFileEntry):
                raise ValueError("entries must contain ChangedFileEntry values")
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

    base_ref = request.cli_options.diff.base_ref if request.cli_options.diff is not None else ""
    diagnostics: list[Diagnostic] = []

    try:
        _ensure_git_repository(context.project_root)
        _verify_base_ref(context.project_root, base_ref)
        entries = _tracked_entries(context.project_root, base_ref, config.diff_current_state)

        if config.diff_current_state is DiffCurrentState.WORKING_TREE and config.diff_include_untracked:
            entries.extend(_untracked_entries(context.project_root))
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
            collection=ChangedFileCollection(entries=_dedupe_and_sort(entries)),
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


def _ensure_git_repository(project_root: Path) -> None:
    result = _run_git(project_root, ("rev-parse", "--is-inside-work-tree"))
    if result.stdout.strip() != b"true":
        raise VcsDiffError("git_diff_read_failure", f"project_root is not inside a Git work tree: {project_root}")


def _verify_base_ref(project_root: Path, base_ref: str) -> None:
    result = _run_git(project_root, ("rev-parse", "--verify", base_ref), check=False)
    if result.returncode != 0:
        raise VcsDiffError("invalid_base_ref", f"base ref is not a valid Git revision: {base_ref}")


def _tracked_entries(project_root: Path, base_ref: str, current_state: DiffCurrentState) -> list[ChangedFileEntry]:
    args = ["diff", "--relative", "--name-status", "-z", "--find-renames", base_ref]
    if current_state is DiffCurrentState.HEAD:
        args.append("HEAD")
    args.extend(("--", "."))
    result = _run_git(project_root, tuple(args))
    entries = _parse_name_status(result.stdout)
    return [
        _entry_with_current_changed_line_ranges(project_root, base_ref, current_state, entry)
        for entry in entries
    ]


def _untracked_entries(project_root: Path) -> list[ChangedFileEntry]:
    result = _run_git(project_root, ("ls-files", "-z", "--others", "--exclude-standard", "--", "."))
    return [
        ChangedFileEntry(current_project_relative_path=path, change_kind="added")
        for path in _decode_nul_paths(result.stdout)
    ]


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
    if entry.change_kind == "added":
        return entry

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
