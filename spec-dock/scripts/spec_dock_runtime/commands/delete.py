from __future__ import annotations

import argparse
from dataclasses import dataclass

from ..application.contracts import DeleteNodeRequest, UseCases
from ..presentation.cli_text import render_delete_text
from .contracts import CommandArgs, CommandOutcome, CommandSpec


@dataclass(frozen=True)
class DeleteArgs(CommandArgs):
    positional_target: str | None
    node_id: str | None
    github_issue: str | None
    recursive: bool
    force: bool
    confirmed: bool
    json_output: bool


def command_specs() -> dict[str, CommandSpec]:
    return {
        "delete": CommandSpec(
            add_arguments=_add_delete_arguments,
            args_factory=_delete_args,
            run=_run_delete,
        )
    }


def _add_delete_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "target",
        nargs="?",
        help="Node id target (e.g. iss-00123 / epic-local-00001 / init-local-00001)",
    )
    parser.add_argument("--id", help="Explicit node id target")
    parser.add_argument("--github-issue", help="Explicit GitHub issue number target (digits only)")
    parser.add_argument("--recursive", action="store_true", help="Allow parent-scope subtree delete")
    parser.add_argument("--force", action="store_true", help="Override active/dependency conflicts only")
    parser.add_argument("--yes", action="store_true", help="Confirm destructive delete operation")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")


def _delete_args(ns: argparse.Namespace) -> CommandArgs:
    return DeleteArgs(
        positional_target=getattr(ns, "target", None),
        node_id=getattr(ns, "id", None),
        github_issue=getattr(ns, "github_issue", None),
        recursive=bool(getattr(ns, "recursive", False)),
        force=bool(getattr(ns, "force", False)),
        confirmed=bool(getattr(ns, "yes", False)),
        json_output=bool(getattr(ns, "json", False)),
    )


def _run_delete(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_delete_args(args)
    result = use_cases.delete_node(
        DeleteNodeRequest(
            positional_target=typed.positional_target,
            node_id=typed.node_id,
            github_issue=typed.github_issue,
            recursive=typed.recursive,
            force=typed.force,
            confirmed=typed.confirmed,
            json_output=typed.json_output,
        )
    )
    return CommandOutcome(
        exit_code=0 if result.status == "ok" else 1,
        text=render_delete_text(result, json_output=typed.json_output),
    )


def _expect_delete_args(args: CommandArgs) -> DeleteArgs:
    if not isinstance(args, DeleteArgs):
        raise RuntimeError("Invalid command args for delete")
    return args

