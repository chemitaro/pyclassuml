from __future__ import annotations

import argparse
from dataclasses import dataclass

from ..application.contracts import UseCases, WorktreeCreateRequest
from ..presentation.cli_text import render_worktree_create_text
from .contracts import CommandArgs, CommandOutcome, CommandSpec


@dataclass(frozen=True)
class WorktreeCreateArgs(CommandArgs):
    label: str | None


def command_specs() -> dict[str, CommandSpec]:
    return {
        "worktree_create": CommandSpec(
            add_arguments=_add_worktree_create_arguments,
            args_factory=_worktree_create_args,
            run=_run_worktree_create,
        ),
    }


def _add_worktree_create_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "label",
        nargs="?",
        help="Optional lowercase label for the worktree id (letters, digits, hyphens).",
    )


def _worktree_create_args(ns: argparse.Namespace) -> CommandArgs:
    return WorktreeCreateArgs(label=getattr(ns, "label", None))


def _run_worktree_create(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_worktree_create_args(args)
    result = use_cases.worktree_create(WorktreeCreateRequest(label=typed.label))
    return CommandOutcome(exit_code=0, text=render_worktree_create_text(result))


def _expect_worktree_create_args(args: CommandArgs) -> WorktreeCreateArgs:
    if not isinstance(args, WorktreeCreateArgs):
        raise RuntimeError("Invalid command args for worktree create")
    return args
