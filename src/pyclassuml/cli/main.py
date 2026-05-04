"""Process entrypoint for the pyclassuml CLI."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
from typing import Sequence

from pyclassuml.app import run_diff, run_generate
from pyclassuml.cli.bind import run_cli
from pyclassuml.model import CommandName, CommandRequest
from pyclassuml.report import ReportRunResult


def main(argv: Sequence[str] | None = None) -> int:
    """Run pyclassuml from process argv and project report streams."""

    timestamp = datetime.now()

    def handler(request: CommandRequest) -> ReportRunResult:
        if request.cli_options.command is CommandName.GENERATE:
            return run_generate(request, timestamp=timestamp)
        if request.cli_options.command is CommandName.DIFF:
            return run_diff(request, timestamp=timestamp)
        raise ValueError(f"unsupported command: {request.cli_options.command}")

    result = run_cli(sys.argv[1:] if argv is None else argv, Path.cwd(), handler)
    if result.stdout_text:
        sys.stdout.write(result.stdout_text)
    if result.stderr_text:
        sys.stderr.write(result.stderr_text)
    return result.exit_code


__all__ = ["main"]
