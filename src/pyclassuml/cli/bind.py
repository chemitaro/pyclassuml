"""Bind CLI argv to model request contracts."""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
import re
from typing import Callable, Sequence

from pyclassuml.model import (
    CommandName,
    CommandOptions,
    CommandRequest,
    CommandResult,
    Diagnostic,
    DiagnosticSeverity,
    DiffCurrentState,
    DiffOptions,
    FailureReason,
    GenerateOptions,
    OriginSeam,
    Recoverability,
    RunSummary,
)
from pyclassuml.report import ReportRunResult

_TARGET_PYTHON = re.compile(r"^3\.[0-9]+$")


@dataclass(frozen=True)
class CliRunResult:
    command_result: CommandResult
    exit_code: int
    stderr_text: str = ""
    stdout_text: str = ""


def bind_command_request(argv: Sequence[str], process_cwd: Path) -> CommandRequest:
    namespace = _build_parser().parse_args(tuple(argv))
    common_options = {
        "cwd": namespace.cwd,
        "config": namespace.config,
        "project_root": namespace.project_root,
        "package_root": namespace.package_root,
        "scope_root": namespace.scope_root,
        "output": namespace.output,
        "ignore": tuple(namespace.ignore),
        "depth": namespace.depth,
        "strict": namespace.strict,
        "target_python": namespace.target_python,
    }

    if namespace.command == CommandName.GENERATE.value:
        options = CommandOptions(
            command=CommandName.GENERATE,
            generate=GenerateOptions(targets=tuple(namespace.targets)),
            **common_options,
        )
    else:
        options = CommandOptions(
            command=CommandName.DIFF,
            diff=DiffOptions(
                base_ref=namespace.base_ref,
                current_state=(
                    DiffCurrentState.WORKING_TREE
                    if namespace.current_state is None
                    else DiffCurrentState(namespace.current_state)
                ),
                include_untracked=True if namespace.include_untracked is None else namespace.include_untracked,
                current_state_cli_provided=namespace.current_state is not None,
                include_untracked_cli_provided=namespace.include_untracked is not None,
            ),
            **common_options,
        )

    return CommandRequest(process_cwd=process_cwd, cli_options=options)


def run_cli(
    argv: Sequence[str],
    process_cwd: Path,
    handler: Callable[[CommandRequest], CommandResult | ReportRunResult],
) -> CliRunResult:
    stdout = StringIO()
    stderr = StringIO()
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            request = bind_command_request(argv, process_cwd)
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 2
        if exit_code == 0:
            return _help_result(stdout.getvalue())
        return _usage_error_result(stderr.getvalue(), exit_code=exit_code)

    result = handler(request)
    if isinstance(result, ReportRunResult):
        return CliRunResult(
            command_result=result.command_result,
            exit_code=result.command_result.exit_code,
            stderr_text=result.stderr_text,
            stdout_text=result.stdout_text,
        )
    return CliRunResult(command_result=result, exit_code=result.exit_code)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pyclassuml")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser(CommandName.GENERATE.value)
    _add_common_options(generate_parser)
    generate_parser.add_argument("targets", nargs="*")

    diff_parser = subparsers.add_parser(CommandName.DIFF.value)
    _add_common_options(diff_parser)
    diff_parser.add_argument("--base", dest="base_ref", required=True, type=_non_empty_string)
    diff_parser.add_argument(
        "--current-state",
        choices=[state.value for state in DiffCurrentState],
        default=None,
    )
    diff_parser.add_argument(
        "--include-untracked",
        dest="include_untracked",
        action=argparse.BooleanOptionalAction,
        default=None,
    )

    return parser


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--cwd", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--package-root", type=Path)
    parser.add_argument("--scope-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--ignore", action="append", default=[], type=_non_empty_string)
    parser.add_argument("--depth", type=_non_negative_int)
    parser.add_argument("--strict", action="store_true", default=False)
    parser.add_argument("--target-python", type=_target_python)


def _non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a non-negative integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return parsed


def _non_empty_string(value: str) -> str:
    if value == "":
        raise argparse.ArgumentTypeError("must be a non-empty string")
    return value


def _target_python(value: str) -> str:
    if not _TARGET_PYTHON.fullmatch(value):
        raise argparse.ArgumentTypeError("must be a 3.<minor> string")
    return value


def _help_result(stdout_text: str) -> CliRunResult:
    command_result = CommandResult(
        artifact_path=None,
        summary=RunSummary(),
        diagnostics=(),
        exit_code=0,
    )
    return CliRunResult(command_result=command_result, exit_code=0, stdout_text=stdout_text)


def _usage_error_result(stderr_text: str, *, exit_code: int) -> CliRunResult:
    message = _diagnostic_message(stderr_text)
    diagnostic = Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="cli_usage_error",
        message=message,
        origin_seam=OriginSeam.CLI,
        recoverability=Recoverability.FATAL,
        failure_reason=FailureReason.CLI_USAGE_ERROR,
    )
    command_result = CommandResult(
        artifact_path=None,
        summary=RunSummary(failure_reason=FailureReason.CLI_USAGE_ERROR),
        diagnostics=(diagnostic,),
        exit_code=exit_code,
    )
    return CliRunResult(command_result=command_result, exit_code=exit_code, stderr_text=stderr_text)


def _diagnostic_message(stderr_text: str) -> str:
    lines = [line.strip() for line in stderr_text.splitlines() if line.strip()]
    return lines[-1] if lines else "CLI usage error"
