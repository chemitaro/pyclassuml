from __future__ import annotations

import argparse
from dataclasses import dataclass

from ..application.contracts import (
    ClearActiveRequest,
    SetActiveRequest,
    ShowActiveRequest,
    TargetRef,
    UseCases,
)
from ..presentation.cli_text import (
    render_active_clear_text,
    render_active_set_text,
    render_active_show_text,
)
from .contracts import CommandArgs, CommandOutcome, CommandSpec
from .targets import parse_explicit_target_flags


@dataclass(frozen=True)
class ActiveSetArgs(CommandArgs):
    target_ref: TargetRef
    target_display: str
    checkout: bool
    force: bool
    github: bool
    gh_limit: int


@dataclass(frozen=True)
class ActiveShowArgs(CommandArgs):
    pass


@dataclass(frozen=True)
class ActiveClearArgs(CommandArgs):
    pass


def command_specs() -> dict[str, CommandSpec]:
    return {
        "active_set": CommandSpec(
            add_arguments=_add_active_set_arguments,
            args_factory=_active_set_args,
            run=_run_active_set,
        ),
        "active_show": CommandSpec(
            add_arguments=_add_active_show_arguments,
            args_factory=_active_show_args,
            run=_run_active_show,
        ),
        "active_clear": CommandSpec(
            add_arguments=_add_active_clear_arguments,
            args_factory=_active_clear_args,
            run=_run_active_clear,
        ),
    }


def _add_active_set_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "target",
        nargs="?",
        help="GitHub issue number (digits only: 123 / #123 / URL) or node id (e.g. iss-00123 / epic-local-00001)",
    )
    parser.add_argument("--id", help="Explicit node id target (e.g. iss-00123 / epic-local-00001)")
    parser.add_argument("--github-issue", type=int, help="Explicit GitHub issue number target (e.g. 123)")
    checkout_group = parser.add_mutually_exclusive_group()
    checkout_group.add_argument(
        "--checkout",
        action="store_true",
        help="After setting active, create/switch to the desired branch (<id>-<slug>, fallback: <id>).",
    )
    checkout_group.add_argument(
        "--no-checkout",
        dest="checkout",
        action="store_false",
        help="Set active only and skip branch operations (default).",
    )
    parser.set_defaults(checkout=False)
    parser.add_argument("--github", action="store_true", help="Fetch GitHub issue states via gh CLI (deps guard)")
    parser.add_argument("--gh-limit", type=int, default=10000, help="gh issue list limit (default: 10000)")
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Ignore deps guard and set active anyway (prints blockers as warnings)",
    )


def _add_active_show_arguments(parser: argparse.ArgumentParser) -> None:
    del parser


def _add_active_clear_arguments(parser: argparse.ArgumentParser) -> None:
    del parser


def _active_set_args(ns: argparse.Namespace) -> CommandArgs:
    target_ref, target_display = parse_explicit_target_flags(
        positional_target=getattr(ns, "target", None),
        node_id=getattr(ns, "id", None),
        github_issue=getattr(ns, "github_issue", None),
        command_label="active set",
    )
    return ActiveSetArgs(
        target_ref=target_ref,
        target_display=target_display,
        checkout=bool(getattr(ns, "checkout", False)),
        force=bool(getattr(ns, "force", False)),
        github=bool(getattr(ns, "github", False)),
        gh_limit=int(getattr(ns, "gh_limit", 10000)),
    )


def _active_show_args(ns: argparse.Namespace) -> CommandArgs:
    del ns
    return ActiveShowArgs()


def _active_clear_args(ns: argparse.Namespace) -> CommandArgs:
    del ns
    return ActiveClearArgs()


def _run_active_set(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_active_set_args(args)
    result = use_cases.set_active(
        SetActiveRequest(
            target=typed.target_ref,
            force=typed.force,
            checkout=typed.checkout,
            use_github=typed.github,
            issue_limit=typed.gh_limit,
        )
    )
    return CommandOutcome(
        exit_code=0,
        text=render_active_set_text(result, target_display=typed.target_display),
    )


def _run_active_show(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    _expect_active_show_args(args)
    result = use_cases.show_active(ShowActiveRequest())
    return CommandOutcome(exit_code=0, text=render_active_show_text(result))


def _run_active_clear(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    _expect_active_clear_args(args)
    result = use_cases.clear_active(ClearActiveRequest())
    return CommandOutcome(exit_code=0, text=render_active_clear_text(result))


def _expect_active_set_args(args: CommandArgs) -> ActiveSetArgs:
    if not isinstance(args, ActiveSetArgs):
        raise RuntimeError("Invalid command args for active set")
    return args


def _expect_active_show_args(args: CommandArgs) -> ActiveShowArgs:
    if not isinstance(args, ActiveShowArgs):
        raise RuntimeError("Invalid command args for active show")
    return args


def _expect_active_clear_args(args: CommandArgs) -> ActiveClearArgs:
    if not isinstance(args, ActiveClearArgs):
        raise RuntimeError("Invalid command args for active clear")
    return args
