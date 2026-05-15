from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..application.contracts import UseCases
from ..presentation.contracts import CliText
from .contracts import CommandArgs, CommandOutcome, CommandSpec


UPSTREAM_SOURCE = "git+https://github.com/chemitaro/spec-dock"


@dataclass(frozen=True)
class UpdateArgs(CommandArgs):
    target: str


def command_specs() -> dict[str, CommandSpec]:
    return {
        "update": CommandSpec(
            add_arguments=_add_update_arguments,
            args_factory=_update_args,
            run=_run_update,
        )
    }


def _add_update_arguments(parser: argparse.ArgumentParser) -> None:
    parser.description = (
        "Update a managed repo by running "
        f"uvx --no-cache --from {UPSTREAM_SOURCE} spec-dock update TARGET. "
        "TARGET defaults to the current working directory."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Managed repo target path to update (default: current working directory)",
    )


def _update_args(ns: argparse.Namespace) -> CommandArgs:
    return UpdateArgs(target=str(getattr(ns, "path", ".")))


def _run_update(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    del use_cases
    typed = _expect_update_args(args)
    target = Path(typed.target).expanduser().resolve()
    command = [
        "uvx",
        "--no-cache",
        "--from",
        UPSTREAM_SOURCE,
        "spec-dock",
        "update",
        str(target),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return CommandOutcome(
            exit_code=127,
            text=CliText(
                stdout_lines=[],
                stderr_lines=[
                    "error: uvx could not be executed. Install uv/uvx or ensure uvx is on PATH, then retry."
                ],
                warnings=[],
            ),
        )
    return CommandOutcome(
        exit_code=int(result.returncode),
        text=CliText(
            stdout_lines=result.stdout.splitlines(),
            stderr_lines=result.stderr.splitlines(),
            warnings=[],
        ),
    )


def _expect_update_args(args: CommandArgs) -> UpdateArgs:
    if not isinstance(args, UpdateArgs):
        raise RuntimeError("Invalid command args for update")
    return args
