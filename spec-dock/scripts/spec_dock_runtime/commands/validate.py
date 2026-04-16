from __future__ import annotations

import argparse
from dataclasses import dataclass

from ..application.contracts import UseCases, ValidateTreeRequest
from ..presentation.cli_text import render_validate_text
from ..presentation.contracts import CliText
from .contracts import CommandArgs, CommandOutcome, CommandSpec


@dataclass(frozen=True)
class ValidateArgs(CommandArgs):
    pass


def command_specs() -> dict[str, CommandSpec]:
    return {
        "validate": CommandSpec(
            add_arguments=_add_validate_arguments,
            args_factory=_validate_args,
            run=_run_validate,
        )
    }


def _add_validate_arguments(parser: argparse.ArgumentParser) -> None:
    del parser


def _validate_args(ns: argparse.Namespace) -> CommandArgs:
    del ns
    return ValidateArgs()


def _run_validate(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    _expect_validate_args(args)
    result = use_cases.validate_tree(ValidateTreeRequest())
    if result.checked_node_count <= 0:
        return _validate_error("No nodes found.")
    text = render_validate_text(result)
    if text.stderr_lines:
        return _validate_error(text.stderr_lines[0], warnings=list(text.warnings))
    return CommandOutcome(exit_code=0, text=text)


def _validate_error(message: str, *, warnings: list[str] | None = None) -> CommandOutcome:
    return CommandOutcome(
        exit_code=1,
        text=CliText(
            stdout_lines=[],
            stderr_lines=[f"error: {message}"],
            warnings=list(warnings) if warnings is not None else [],
        ),
    )


def _expect_validate_args(args: CommandArgs) -> ValidateArgs:
    if not isinstance(args, ValidateArgs):
        raise RuntimeError("Invalid command args for validate")
    return args

