from __future__ import annotations

import argparse
from dataclasses import dataclass

from ..application.contracts import CloseNodeRequest, TargetRef, UseCases
from ..presentation.cli_text import render_close_text
from .contracts import CommandArgs, CommandOutcome, CommandSpec
from .targets import parse_explicit_target_flags


@dataclass(frozen=True)
class CloseArgs(CommandArgs):
    target_ref: TargetRef
    target_display: str


def command_specs() -> dict[str, CommandSpec]:
    return {
        "close": CommandSpec(
            add_arguments=_add_close_arguments,
            args_factory=_close_args,
            run=_run_close,
        )
    }


def _add_close_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "target",
        nargs="?",
        help="GitHub issue number (123 / #123 / URL) or node id (e.g. iss-00123 / epic-local-00001)",
    )
    parser.add_argument("--id", help="Explicit node id target (e.g. iss-00123 / epic-local-00001)")
    parser.add_argument("--github-issue", type=int, help="Explicit GitHub issue number target (e.g. 123)")


def _close_args(ns: argparse.Namespace) -> CommandArgs:
    target_ref, target_display = parse_explicit_target_flags(
        positional_target=getattr(ns, "target", None),
        node_id=getattr(ns, "id", None),
        github_issue=getattr(ns, "github_issue", None),
        command_label="close",
    )
    return CloseArgs(target_ref=target_ref, target_display=target_display)


def _run_close(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_close_args(args)
    result = use_cases.close_node(CloseNodeRequest(target=typed.target_ref))
    post_sync_failed = result.post_sync is not None and result.post_sync.failed
    return CommandOutcome(
        exit_code=1 if post_sync_failed else 0,
        text=render_close_text(result, target_display=typed.target_display),
    )


def _expect_close_args(args: CommandArgs) -> CloseArgs:
    if not isinstance(args, CloseArgs):
        raise RuntimeError("Invalid command args for close")
    return args
