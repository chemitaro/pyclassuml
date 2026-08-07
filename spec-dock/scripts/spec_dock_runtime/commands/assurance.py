from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from spec_dock_runtime.application.contracts import (
    ClassifyAssuranceRequest,
    ComposeArtifactSelection,
    ComposeAssuranceRequest,
    ShowAssuranceRequest,
    UseCases,
    VerifyAssuranceRequest,
)
from spec_dock_runtime.commands.contracts import CommandArgs, CommandOutcome, CommandSpec
from spec_dock_runtime.presentation.assurance_text import render_assurance_json, render_assurance_text
from spec_dock_runtime.presentation.contracts import CliText

if TYPE_CHECKING:
    import argparse


OutputFormat = Literal["text", "json"]


@dataclass(frozen=True)
class AssuranceShowArgs(CommandArgs):
    issue: str | None
    output_format: OutputFormat


@dataclass(frozen=True)
class AssuranceClassifyArgs(CommandArgs):
    stage: Literal["requirement"]
    issue: str | None
    output_format: OutputFormat
    dry_run: bool


@dataclass(frozen=True)
class AssuranceVerifyArgs(CommandArgs):
    issue: str | None
    output_format: OutputFormat


@dataclass(frozen=True)
class AssuranceComposeArgs(CommandArgs):
    artifact: ComposeArtifactSelection
    issue: str | None
    output_format: OutputFormat
    dry_run: bool


def command_specs() -> dict[str, CommandSpec]:
    return {
        "assurance_show": CommandSpec(
            add_arguments=_add_show_arguments,
            args_factory=_show_args,
            run=_run_show,
        ),
        "assurance_classify": CommandSpec(
            add_arguments=_add_classify_arguments,
            args_factory=_classify_args,
            run=_run_classify,
        ),
        "assurance_verify": CommandSpec(
            add_arguments=_add_verify_arguments,
            args_factory=_verify_args,
            run=_run_verify,
        ),
        "assurance_compose": CommandSpec(
            add_arguments=_add_compose_arguments,
            args_factory=_compose_args,
            run=_run_compose,
        ),
    }


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--issue", help="Issue id, GitHub issue number, or repo-contained issue path")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")


def _add_show_arguments(parser: argparse.ArgumentParser) -> None:
    _add_common_arguments(parser)


def _add_classify_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--stage", choices=("requirement",), required=True, help="Classification stage")
    _add_common_arguments(parser)
    parser.add_argument("--dry-run", action="store_true", help="Return classification without writing .assurance.json")


def _add_verify_arguments(parser: argparse.ArgumentParser) -> None:
    _add_common_arguments(parser)


def _add_compose_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--artifact",
        choices=("design", "plan", "report", "all"),
        required=True,
        help="Planning artifact to compose",
    )
    _add_common_arguments(parser)
    parser.add_argument("--dry-run", action="store_true", help="Return compose result without writing artifacts")


def _show_args(ns: argparse.Namespace) -> CommandArgs:
    return AssuranceShowArgs(
        issue=_optional_text(getattr(ns, "issue", None)),
        output_format=_output_format(ns),
    )


def _classify_args(ns: argparse.Namespace) -> CommandArgs:
    return AssuranceClassifyArgs(
        stage="requirement",
        issue=_optional_text(getattr(ns, "issue", None)),
        output_format=_output_format(ns),
        dry_run=bool(getattr(ns, "dry_run", False)),
    )


def _verify_args(ns: argparse.Namespace) -> CommandArgs:
    return AssuranceVerifyArgs(
        issue=_optional_text(getattr(ns, "issue", None)),
        output_format=_output_format(ns),
    )


def _compose_args(ns: argparse.Namespace) -> CommandArgs:
    return AssuranceComposeArgs(
        artifact=_artifact_selection(ns),
        issue=_optional_text(getattr(ns, "issue", None)),
        output_format=_output_format(ns),
        dry_run=bool(getattr(ns, "dry_run", False)),
    )


def _run_show(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_show_args(args)
    result = use_cases.show_assurance(ShowAssuranceRequest(issue=typed.issue))
    return _outcome(result=result, output_format=typed.output_format)


def _run_classify(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_classify_args(args)
    result = use_cases.classify_assurance(
        ClassifyAssuranceRequest(stage=typed.stage, issue=typed.issue, dry_run=typed.dry_run)
    )
    return _outcome(result=result, output_format=typed.output_format)


def _run_verify(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_verify_args(args)
    result = use_cases.verify_assurance(VerifyAssuranceRequest(issue=typed.issue))
    return _outcome(result=result, output_format=typed.output_format)


def _run_compose(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_compose_args(args)
    result = use_cases.compose_assurance(
        ComposeAssuranceRequest(artifact=typed.artifact, issue=typed.issue, dry_run=typed.dry_run)
    )
    return _outcome(result=result, output_format=typed.output_format)


def _outcome(*, result, output_format: OutputFormat) -> CommandOutcome:
    if output_format == "json":
        text = CliText(stdout_lines=[render_assurance_json(result)], stderr_lines=[], warnings=[])
    else:
        text = render_assurance_text(result)
    return CommandOutcome(exit_code=0 if result.ok else 1, text=text)


def _output_format(ns: argparse.Namespace) -> OutputFormat:
    value = getattr(ns, "format", "text")
    if value == "json":
        return "json"
    return "text"


def _artifact_selection(ns: argparse.Namespace) -> ComposeArtifactSelection:
    value = str(getattr(ns, "artifact", ""))
    if value in ("design", "plan", "report", "all"):
        return value
    raise RuntimeError(f"Invalid artifact selection: {value}")


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _expect_show_args(args: CommandArgs) -> AssuranceShowArgs:
    if not isinstance(args, AssuranceShowArgs):
        raise RuntimeError("Invalid command args for assurance show")
    return args


def _expect_classify_args(args: CommandArgs) -> AssuranceClassifyArgs:
    if not isinstance(args, AssuranceClassifyArgs):
        raise RuntimeError("Invalid command args for assurance classify")
    return args


def _expect_verify_args(args: CommandArgs) -> AssuranceVerifyArgs:
    if not isinstance(args, AssuranceVerifyArgs):
        raise RuntimeError("Invalid command args for assurance verify")
    return args


def _expect_compose_args(args: CommandArgs) -> AssuranceComposeArgs:
    if not isinstance(args, AssuranceComposeArgs):
        raise RuntimeError("Invalid command args for assurance compose")
    return args
