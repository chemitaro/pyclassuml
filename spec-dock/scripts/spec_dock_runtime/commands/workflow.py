from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from spec_dock_runtime.application.contracts import UseCases, WorkflowNextRequest, WorkflowStatusRequest
from spec_dock_runtime.commands.contracts import CommandArgs, CommandOutcome, CommandSpec
from spec_dock_runtime.presentation.contracts import CliText
from spec_dock_runtime.presentation.workflow import (
    render_workflow_json,
    render_workflow_markdown,
    render_workflow_text,
)

if TYPE_CHECKING:
    import argparse

WorkflowStatusFormat = Literal["text", "json"]
WorkflowTarget = Literal["issue-planning", "issue-execution"]


@dataclass(frozen=True)
class WorkflowStatusArgs(CommandArgs):
    output_format: WorkflowStatusFormat


@dataclass(frozen=True)
class GuidanceArgs(CommandArgs):
    workflow_target: WorkflowTarget


def command_specs() -> dict[str, CommandSpec]:
    return {
        "workflow_status": CommandSpec(
            add_arguments=_add_status_arguments,
            args_factory=_status_args,
            run=_run_status,
        ),
        "guidance": CommandSpec(
            add_arguments=_add_guidance_arguments,
            args_factory=_guidance_args,
            run=_run_guidance,
        ),
    }


def _add_status_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")


def _add_guidance_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("workflow_target", choices=("issue-planning", "issue-execution"), help="Guidance target")


def _status_args(ns: argparse.Namespace) -> CommandArgs:
    output_format = getattr(ns, "format", "text")
    return WorkflowStatusArgs(output_format="json" if output_format == "json" else "text")


def _guidance_args(ns: argparse.Namespace) -> CommandArgs:
    return GuidanceArgs(workflow_target=ns.workflow_target)


def _run_status(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_status_args(args)
    result = use_cases.workflow_status(WorkflowStatusRequest())
    if typed.output_format == "json":
        text = CliText(stdout_lines=[render_workflow_json(result)], stderr_lines=[], warnings=[])
    else:
        text = render_workflow_text(result)
    return CommandOutcome(exit_code=0, text=text)


def _run_guidance(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_guidance_args(args)
    result = use_cases.workflow_next(WorkflowNextRequest(workflow_target=typed.workflow_target))
    text = render_workflow_markdown(result)
    return CommandOutcome(exit_code=0, text=text)


def _expect_status_args(args: CommandArgs) -> WorkflowStatusArgs:
    if not isinstance(args, WorkflowStatusArgs):
        raise RuntimeError("Invalid command args for workflow status")
    return args


def _expect_guidance_args(args: CommandArgs) -> GuidanceArgs:
    if not isinstance(args, GuidanceArgs):
        raise RuntimeError("Invalid command args for guidance")
    return args
