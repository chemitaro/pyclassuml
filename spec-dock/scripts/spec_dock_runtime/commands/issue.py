from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from spec_dock_runtime.application.contracts import IssueFinishRequest, IssueStartRequest, TargetRef, UseCases
from spec_dock_runtime.commands.contracts import CommandArgs, CommandOutcome, CommandSpec
from spec_dock_runtime.commands.targets import parse_explicit_target_flags
from spec_dock_runtime.presentation.cli_text import render_issue_finish_text, render_issue_start_text

if TYPE_CHECKING:
    import argparse


@dataclass(frozen=True)
class IssueStartArgs(CommandArgs):
    target_ref: TargetRef
    force: bool
    gh_limit: int


@dataclass(frozen=True)
class IssueFinishArgs(CommandArgs):
    pass


def command_specs() -> dict[str, CommandSpec]:
    return {
        "issue_start": CommandSpec(
            add_arguments=_add_issue_start_arguments,
            args_factory=_issue_start_args,
            run=_run_issue_start,
        ),
        "issue_finish": CommandSpec(
            add_arguments=_add_issue_finish_arguments,
            args_factory=_issue_finish_args,
            run=_run_issue_finish,
        ),
    }


def _add_issue_start_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "target",
        nargs="?",
        help="GitHub issue number (digits only: 123 / #123 / URL) or issue node id (e.g. iss-00123)",
    )
    parser.add_argument("--id", help="Explicit issue node id target (e.g. iss-00123)")
    parser.add_argument("--github-issue", type=int, help="Explicit GitHub issue number target (e.g. 123)")
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Bypass only the unfinished active issue guard; dependency readiness checks still apply.",
    )
    parser.add_argument("--gh-limit", type=int, default=10000, help="gh issue list limit (default: 10000)")


def _add_issue_finish_arguments(parser: argparse.ArgumentParser) -> None:
    del parser


def _issue_start_args(ns: argparse.Namespace) -> CommandArgs:
    target_ref, _target_display = parse_explicit_target_flags(
        positional_target=getattr(ns, "target", None),
        node_id=getattr(ns, "id", None),
        github_issue=getattr(ns, "github_issue", None),
        command_label="issue start",
    )
    return IssueStartArgs(
        target_ref=target_ref,
        force=bool(getattr(ns, "force", False)),
        gh_limit=int(getattr(ns, "gh_limit", 10000)),
    )


def _issue_finish_args(ns: argparse.Namespace) -> CommandArgs:
    del ns
    return IssueFinishArgs()


def _run_issue_start(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_issue_start_args(args)
    result = use_cases.issue_start(
        IssueStartRequest(
            target=typed.target_ref,
            force=typed.force,
            issue_limit=typed.gh_limit,
        )
    )
    return CommandOutcome(exit_code=0, text=render_issue_start_text(result))


def _run_issue_finish(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    _expect_issue_finish_args(args)
    result = use_cases.issue_finish(IssueFinishRequest())
    post_sync_failed = result.post_sync is not None and result.post_sync.failed
    return CommandOutcome(exit_code=1 if post_sync_failed else 0, text=render_issue_finish_text(result))


def _expect_issue_start_args(args: CommandArgs) -> IssueStartArgs:
    if not isinstance(args, IssueStartArgs):
        raise RuntimeError("Invalid command args for issue start")
    return args


def _expect_issue_finish_args(args: CommandArgs) -> IssueFinishArgs:
    if not isinstance(args, IssueFinishArgs):
        raise RuntimeError("Invalid command args for issue finish")
    return args
