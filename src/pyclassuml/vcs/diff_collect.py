"""Collect raw changed files from Git for diff command inputs."""

from __future__ import annotations

from dataclasses import dataclass
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
class ChangedFileEntry:
    current_project_relative_path: str
    change_kind: str
    previous_project_relative_path: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.current_project_relative_path, str) or self.current_project_relative_path == "":
            raise ValueError("current_project_relative_path must be a non-empty str")
        if self.change_kind not in {"added", "modified", "renamed"}:
            raise ValueError("change_kind must be added, modified, or renamed")
        if self.previous_project_relative_path is not None and (
            not isinstance(self.previous_project_relative_path, str) or self.previous_project_relative_path == ""
        ):
            raise ValueError("previous_project_relative_path must be a non-empty str or None")


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
    return _parse_name_status(result.stdout)


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
