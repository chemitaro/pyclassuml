from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from spec_dock_runtime.commands.contracts import CommandOutcome, CommandRegistry
from spec_dock_runtime.presentation.contracts import CliText

if TYPE_CHECKING:
    import argparse

    from spec_dock_runtime.application.contracts import UseCases


def dispatch(ns: argparse.Namespace, registry: CommandRegistry, use_cases: UseCases) -> int:
    command_key = getattr(ns, "command_key", None)
    if not isinstance(command_key, str):
        _emit(
            CliText(
                stdout_lines=[],
                stderr_lines=["error: command key is missing"],
                warnings=[],
            )
        )
        return 1

    spec = registry.items.get(command_key)
    if spec is None:
        _emit(
            CliText(
                stdout_lines=[],
                stderr_lines=[f"error: unknown command key: {command_key}"],
                warnings=[],
            )
        )
        return 1

    try:
        args = spec.args_factory(ns)
        outcome = spec.run(args, use_cases)
    except RuntimeError as error:
        outcome = CommandOutcome(
            exit_code=1,
            text=CliText(stdout_lines=[], stderr_lines=[f"error: {error}"], warnings=[]),
        )
    except Exception as error:  # pragma: no cover - defensive fallback
        outcome = CommandOutcome(
            exit_code=1,
            text=CliText(stdout_lines=[], stderr_lines=[f"error: {error}"], warnings=[]),
        )

    _emit(outcome.text)
    return int(outcome.exit_code)


def _emit(text: CliText) -> None:
    for warning in text.warnings:
        print(f"spec-dock: (warn) {warning}", file=sys.stderr)
    for line in text.stderr_lines:
        print(line, file=sys.stderr)
    for line in text.stdout_lines:
        print(line)
