from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from spec_dock_runtime.application.contracts import (
    CheckDepsRequest,
    MutateDepsError,
    MutateDepsRequest,
    TargetRef,
    UseCases,
)
from spec_dock_runtime.commands.contracts import CommandArgs, CommandOutcome, CommandSpec
from spec_dock_runtime.commands.node_id_normalizer import normalize_node_id
from spec_dock_runtime.commands.targets import parse_explicit_target_flags
from spec_dock_runtime.presentation.cli_text import (
    render_deps_check_text,
    render_deps_mutation_error_text,
    render_deps_mutation_text,
)
from spec_dock_runtime.presentation.contracts import CliText
from spec_dock_runtime.presentation.json_state import render_deps_check_json

if TYPE_CHECKING:
    import argparse


@dataclass(frozen=True)
class DepsCheckArgs(CommandArgs):
    target_ref: TargetRef
    github: bool
    no_github: bool
    gh_limit: int
    json_output: bool


@dataclass(frozen=True)
class DepsMutationArgs(CommandArgs):
    from_id: str
    to_id: str


def command_specs() -> dict[str, CommandSpec]:
    return {
        "deps_check": CommandSpec(
            add_arguments=_add_deps_check_arguments,
            args_factory=_deps_check_args,
            run=_run_deps_check,
        ),
        "deps_add": CommandSpec(
            add_arguments=_add_deps_add_arguments,
            args_factory=_deps_mutation_args,
            run=_run_deps_add,
        ),
        "deps_remove": CommandSpec(
            add_arguments=_add_deps_add_arguments,
            args_factory=_deps_mutation_args,
            run=_run_deps_remove,
        ),
    }


def _add_deps_check_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "target",
        nargs="?",
        help="GitHub issue number (123 / #123 / URL) or node id (e.g. iss-00123 / epic-local-00001)",
    )
    parser.add_argument("--id", help="Explicit node id target (e.g. iss-00123 / epic-local-00001)")
    parser.add_argument("--github-issue", type=int, help="Explicit GitHub issue number target (e.g. 123)")
    github_group = parser.add_mutually_exclusive_group()
    github_group.add_argument("--github", action="store_true", help="Fetch GitHub issue states via gh CLI")
    github_group.add_argument("--no-github", action="store_true", help="Use cached issue states without calling gh CLI")
    parser.add_argument("--gh-limit", type=int, default=10000, help="gh issue list limit (default: 10000)")
    parser.add_argument("--json", action="store_true", help="Output JSON to stdout only")


def _add_deps_add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--from",
        dest="from_id",
        required=True,
        help=(
            "Existing initiative, epic, or issue node id for dependency source "
            "(e.g. init-00123 / epic-00123 / iss-00123)"
        ),
    )
    parser.add_argument(
        "--to",
        dest="to_id",
        required=True,
        help=(
            "Existing initiative, epic, or issue node id for dependency target "
            "(e.g. init-00124 / epic-00124 / iss-00124)"
        ),
    )


def _deps_check_args(ns: argparse.Namespace) -> CommandArgs:
    target_ref, _ = parse_explicit_target_flags(
        positional_target=getattr(ns, "target", None),
        node_id=getattr(ns, "id", None),
        github_issue=getattr(ns, "github_issue", None),
        command_label="deps check",
    )
    return DepsCheckArgs(
        target_ref=target_ref,
        github=not bool(getattr(ns, "no_github", False)),
        no_github=bool(getattr(ns, "no_github", False)),
        gh_limit=int(getattr(ns, "gh_limit", 10000)),
        json_output=bool(getattr(ns, "json", False)),
    )


def _deps_mutation_args(ns: argparse.Namespace) -> CommandArgs:
    from_id = normalize_node_id(str(getattr(ns, "from_id", "")), field="--from")
    to_id = normalize_node_id(str(getattr(ns, "to_id", "")), field="--to")
    return DepsMutationArgs(from_id=from_id, to_id=to_id)


def _run_deps_check(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_deps_check_args(args)
    result = use_cases.check_deps(
        CheckDepsRequest(
            target=typed.target_ref,
            use_github=typed.github,
            issue_limit=typed.gh_limit,
        )
    )
    if typed.json_output:
        text = CliText(
            stdout_lines=[render_deps_check_json(result)],
            stderr_lines=[],
            warnings=[],
        )
    else:
        text = render_deps_check_text(result)
    exit_code = 0 if result.inspection.evaluation.ready else 3
    return CommandOutcome(exit_code=exit_code, text=text)


def _run_deps_add(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    return _run_deps_mutation(action="add", args=args, use_cases=use_cases)


def _run_deps_remove(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    return _run_deps_mutation(action="remove", args=args, use_cases=use_cases)


def _run_deps_mutation(*, action: str, args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_deps_mutation_args(args)
    try:
        result = use_cases.mutate_deps(
            MutateDepsRequest(
                action=action,
                from_id=typed.from_id,
                to_id=typed.to_id,
            )
        )
    except MutateDepsError as error:
        return CommandOutcome(exit_code=1, text=render_deps_mutation_error_text(error))
    post_sync_failed = result.post_sync is not None and result.post_sync.failed
    return CommandOutcome(exit_code=1 if post_sync_failed else 0, text=render_deps_mutation_text(result))


def _expect_deps_check_args(args: CommandArgs) -> DepsCheckArgs:
    if not isinstance(args, DepsCheckArgs):
        raise RuntimeError("Invalid command args for deps check")
    return args


def _expect_deps_mutation_args(args: CommandArgs) -> DepsMutationArgs:
    if not isinstance(args, DepsMutationArgs):
        raise RuntimeError("Invalid command args for deps mutation")
    return args
