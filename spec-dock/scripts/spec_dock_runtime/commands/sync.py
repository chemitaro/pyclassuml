from __future__ import annotations

import argparse
from dataclasses import dataclass

from ..application.contracts import SyncCommandResult, SyncRequest, UseCases
from ..presentation.cli_text import render_sync_text
from ..presentation.contracts import CliText
from .contracts import CommandArgs, CommandOutcome, CommandSpec


@dataclass(frozen=True)
class SyncArgs(CommandArgs):
    github: bool
    gh_limit: int
    no_update_active: bool
    force: bool


def command_specs() -> dict[str, CommandSpec]:
    return {
        "sync": CommandSpec(
            add_arguments=_add_sync_arguments,
            args_factory=_sync_args,
            run=_run_sync,
        )
    }


def _add_sync_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--github", action="store_true", help="Fetch GitHub issue states via gh CLI")
    parser.add_argument("--gh-limit", type=int, default=10000, help="gh issue list limit (default: 10000)")
    parser.add_argument(
        "--no-update-active",
        action="store_true",
        help="Do not update active pointers from current git branch (index/tree generation only)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Continue even if preflight validation fails (writes index/tree; disables active auto update)",
    )


def _sync_args(ns: argparse.Namespace) -> CommandArgs:
    return SyncArgs(
        github=bool(getattr(ns, "github", False)),
        gh_limit=int(getattr(ns, "gh_limit", 10000)),
        no_update_active=bool(getattr(ns, "no_update_active", False)),
        force=bool(getattr(ns, "force", False)),
    )


def _run_sync(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_sync_args(args)
    result = use_cases.sync(
        SyncRequest(
            force=typed.force,
            github_enabled=typed.github,
            issue_limit=typed.gh_limit,
            update_active_from_branch=(not typed.no_update_active),
        )
    )
    if result is None:
        return CommandOutcome(exit_code=0, text=CliText(stdout_lines=[], stderr_lines=[], warnings=[]))
    if isinstance(result, int):
        return CommandOutcome(exit_code=int(result), text=CliText(stdout_lines=[], stderr_lines=[], warnings=[]))
    if not isinstance(result, SyncCommandResult):
        raise RuntimeError(f"Unsupported sync result type: {type(result)}")
    exit_code = 0 if result.artifact_failure is None else 1
    return CommandOutcome(exit_code=exit_code, text=render_sync_text(result))


def _expect_sync_args(args: CommandArgs) -> SyncArgs:
    if not isinstance(args, SyncArgs):
        raise RuntimeError("Invalid command args for sync")
    return args
