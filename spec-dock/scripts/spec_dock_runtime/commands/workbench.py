from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from spec_dock_runtime.application.contracts import (
    UseCases,
    WorkbenchCopyError,
    WorkbenchCopyRequest,
    WorktreeCommandError,
)
from spec_dock_runtime.commands.contracts import CommandArgs, CommandOutcome, CommandSpec
from spec_dock_runtime.presentation.cli_text import (
    render_workbench_copy_error_json,
    render_workbench_copy_error_text,
    render_workbench_copy_json,
    render_workbench_copy_text,
)

if TYPE_CHECKING:
    import argparse


@dataclass(frozen=True)
class WorkbenchCopyArgs(CommandArgs):
    scope_id: str
    target: str
    json: bool


def command_specs() -> dict[str, CommandSpec]:
    return {
        "workbench_copy": CommandSpec(
            add_arguments=_add_workbench_copy_arguments,
            args_factory=_workbench_copy_args,
            run=_run_workbench_copy,
        )
    }


def _add_workbench_copy_arguments(parser: argparse.ArgumentParser) -> None:
    parser.description = (
        "Experimental one-shot copy of disposable, non-canonical scoped Workbench content; "
        "this command does not synchronize or copy back."
    )
    parser.add_argument("--scope", required=True, help="Full initiative, epic, or issue id.")
    parser.add_argument("--to", required=True, help="Target worktree id, absolute path, or directory basename.")
    parser.add_argument("--json", action="store_true", help="Emit content-free agent-oriented JSON output.")


def _workbench_copy_args(ns: argparse.Namespace) -> CommandArgs:
    return WorkbenchCopyArgs(
        scope_id=str(ns.scope),
        target=str(ns.to),
        json=bool(getattr(ns, "json", False)),
    )


def _run_workbench_copy(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    if not isinstance(args, WorkbenchCopyArgs):
        raise RuntimeError("Invalid command args for workbench copy")
    try:
        result = use_cases.workbench_copy(WorkbenchCopyRequest(scope_id=args.scope_id, target=args.target))
    except WorkbenchCopyError as error:
        error_renderer = render_workbench_copy_error_json if args.json else render_workbench_copy_error_text
        return CommandOutcome(exit_code=1, text=error_renderer(error))
    except WorktreeCommandError as error:
        copy_error = WorkbenchCopyError(
            code=error.code,
            message="workbench copy target selection failed",
            side="target",
        )
        error_renderer = render_workbench_copy_error_json if args.json else render_workbench_copy_error_text
        return CommandOutcome(exit_code=1, text=error_renderer(copy_error))
    renderer = render_workbench_copy_json if args.json else render_workbench_copy_text
    return CommandOutcome(exit_code=0, text=renderer(result))
