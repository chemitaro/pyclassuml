from __future__ import annotations

import argparse
from dataclasses import dataclass

from ..application.contracts import (
    UseCases,
    WorktreeCommandError,
    WorktreeCreateRequest,
    WorktreeListRequest,
    WorktreeRemoveRequest,
    WorktreeShowRequest,
)
from ..presentation.cli_text import (
    render_worktree_create_text,
    render_worktree_error_json,
    render_worktree_error_text,
    render_worktree_list_json,
    render_worktree_list_text,
    render_worktree_remove_json,
    render_worktree_remove_text,
    render_worktree_show_json,
    render_worktree_show_text,
)
from .contracts import CommandArgs, CommandOutcome, CommandSpec


@dataclass(frozen=True)
class WorktreeCreateArgs(CommandArgs):
    label: str | None


@dataclass(frozen=True)
class WorktreeListArgs(CommandArgs):
    json: bool


@dataclass(frozen=True)
class WorktreeShowArgs(CommandArgs):
    target: str
    json: bool


@dataclass(frozen=True)
class WorktreeRemoveArgs(CommandArgs):
    target: str
    force: bool
    json: bool


def command_specs() -> dict[str, CommandSpec]:
    return {
        "worktree_create": CommandSpec(
            add_arguments=_add_worktree_create_arguments,
            args_factory=_worktree_create_args,
            run=_run_worktree_create,
        ),
        "worktree_list": CommandSpec(
            add_arguments=_add_worktree_json_arguments,
            args_factory=_worktree_list_args,
            run=_run_worktree_list,
        ),
        "worktree_show": CommandSpec(
            add_arguments=_add_worktree_show_arguments,
            args_factory=_worktree_show_args,
            run=_run_worktree_show,
        ),
        "worktree_remove": CommandSpec(
            add_arguments=_add_worktree_remove_arguments,
            args_factory=_worktree_remove_args,
            run=_run_worktree_remove,
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


def _add_worktree_json_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Emit agent-oriented JSON output.")


def _add_worktree_show_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("target", help="Worktree id, absolute path, or directory basename.")
    _add_worktree_json_arguments(parser)


def _add_worktree_remove_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("target", help="Managed worktree id, absolute path, or directory basename.")
    parser.add_argument("--force", action="store_true", help="Pass --force to git worktree remove.")
    _add_worktree_json_arguments(parser)


def _worktree_list_args(ns: argparse.Namespace) -> CommandArgs:
    return WorktreeListArgs(json=bool(getattr(ns, "json", False)))


def _worktree_show_args(ns: argparse.Namespace) -> CommandArgs:
    return WorktreeShowArgs(target=str(getattr(ns, "target")), json=bool(getattr(ns, "json", False)))


def _worktree_remove_args(ns: argparse.Namespace) -> CommandArgs:
    return WorktreeRemoveArgs(
        target=str(getattr(ns, "target")),
        force=bool(getattr(ns, "force", False)),
        json=bool(getattr(ns, "json", False)),
    )


def _run_worktree_create(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_worktree_create_args(args)
    result = use_cases.worktree_create(WorktreeCreateRequest(label=typed.label))
    return CommandOutcome(exit_code=0, text=render_worktree_create_text(result))


def _run_worktree_list(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_worktree_list_args(args)
    try:
        result = use_cases.worktree_list(WorktreeListRequest())
    except WorktreeCommandError as error:
        return _worktree_error_outcome(error, typed.json)
    renderer = render_worktree_list_json if typed.json else render_worktree_list_text
    return CommandOutcome(exit_code=0, text=renderer(result))


def _run_worktree_show(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_worktree_show_args(args)
    try:
        result = use_cases.worktree_show(WorktreeShowRequest(target=typed.target))
    except WorktreeCommandError as error:
        return _worktree_error_outcome(error, typed.json)
    renderer = render_worktree_show_json if typed.json else render_worktree_show_text
    return CommandOutcome(exit_code=0, text=renderer(result))


def _run_worktree_remove(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_worktree_remove_args(args)
    try:
        result = use_cases.worktree_remove(WorktreeRemoveRequest(target=typed.target, force=typed.force))
    except WorktreeCommandError as error:
        return _worktree_error_outcome(error, typed.json)
    renderer = render_worktree_remove_json if typed.json else render_worktree_remove_text
    return CommandOutcome(exit_code=0, text=renderer(result))


def _worktree_error_outcome(error: WorktreeCommandError, as_json: bool) -> CommandOutcome:
    renderer = render_worktree_error_json if as_json else render_worktree_error_text
    return CommandOutcome(exit_code=1, text=renderer(error))


def _expect_worktree_create_args(args: CommandArgs) -> WorktreeCreateArgs:
    if not isinstance(args, WorktreeCreateArgs):
        raise RuntimeError("Invalid command args for worktree create")
    return args


def _expect_worktree_list_args(args: CommandArgs) -> WorktreeListArgs:
    if not isinstance(args, WorktreeListArgs):
        raise RuntimeError("Invalid command args for worktree list")
    return args


def _expect_worktree_show_args(args: CommandArgs) -> WorktreeShowArgs:
    if not isinstance(args, WorktreeShowArgs):
        raise RuntimeError("Invalid command args for worktree show")
    return args


def _expect_worktree_remove_args(args: CommandArgs) -> WorktreeRemoveArgs:
    if not isinstance(args, WorktreeRemoveArgs):
        raise RuntimeError("Invalid command args for worktree remove")
    return args
