from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from spec_dock_runtime.application.issue_planning import (
    PlanningApplyRequest,
    PlanningCreateRequest,
    PlanningReviewRequest,
    PlanningReviseRequest,
)
from spec_dock_runtime.commands.contracts import CommandArgs, CommandOutcome, CommandSpec
from spec_dock_runtime.presentation.issue_planning import (
    render_planning_result_json,
    render_planning_result_text,
)

if TYPE_CHECKING:
    import argparse

    from spec_dock_runtime.application.contracts import UseCases

OutputFormat = Literal["text", "json"]
PlanningMode = Literal["archive-candidate", "git-bound"]


@dataclass(frozen=True)
class PlanningCreateArgs(CommandArgs):
    issue_id: str
    output_dir: Path
    output_format: OutputFormat
    context_manifest_path: Path | None


@dataclass(frozen=True)
class PlanningReviseArgs(CommandArgs):
    candidate_path: Path
    request_path: Path
    output_dir: Path
    output_format: OutputFormat


@dataclass(frozen=True)
class PlanningReviewArgs(CommandArgs):
    issue_id: str
    mode: PlanningMode
    output_dir: Path
    output_format: OutputFormat
    candidate_path: Path | None
    reviewed_head: str | None


@dataclass(frozen=True)
class PlanningApplyArgs(CommandArgs):
    issue_id: str
    mode: PlanningMode
    review_result_path: Path
    human_decision_path: Path
    expected_head: str
    output_dir: Path
    output_format: OutputFormat
    candidate_path: Path | None
    logical_filename: str | None
    zip_sha256: str | None
    reviewed_head: str | None


def command_specs() -> dict[str, CommandSpec]:
    return {
        "planning_create": CommandSpec(
            add_arguments=_add_create_arguments,
            args_factory=_create_args,
            run=_run_create,
        ),
        "planning_revise": CommandSpec(
            add_arguments=_add_revise_arguments,
            args_factory=_revise_args,
            run=_run_revise,
        ),
        "planning_review": CommandSpec(
            add_arguments=_add_review_arguments,
            args_factory=_review_args,
            run=_run_review,
        ),
        "planning_apply": CommandSpec(
            add_arguments=_add_apply_arguments,
            args_factory=_apply_args,
            run=_run_apply,
        ),
    }


def _add_format(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", choices=("text", "json"), default="text", help="Output format")


def _add_create_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--issue", required=True, help="Existing Issue ID")
    parser.add_argument("--output", required=True, help="Existing external output directory")
    parser.add_argument(
        "--context-manifest",
        help="Optional external JSON manifest with relevant_source_paths and operator_context",
    )
    _add_format(parser)


def _add_revise_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--candidate", required=True, help="Candidate ZIP path")
    parser.add_argument(
        "--request",
        required=True,
        help="Request JSON; sibling planning-review-result.json required in same directory",
    )
    parser.add_argument("--output", required=True, help="Existing external output directory")
    _add_format(parser)


def _add_review_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--issue", required=True, help="Existing Issue ID")
    parser.add_argument("--mode", required=True, choices=("archive-candidate", "git-bound"))
    parser.add_argument(
        "--candidate",
        help="Candidate ZIP path (required by archive-candidate and git-bound modes)",
    )
    parser.add_argument("--reviewed-head", help="Reviewed Git HEAD (git-bound only)")
    parser.add_argument("--output", required=True, help="Existing external output directory")
    _add_format(parser)


def _add_apply_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--issue", required=True, help="Existing Issue ID")
    parser.add_argument("--mode", required=True, choices=("archive-candidate", "git-bound"))
    parser.add_argument("--review-result", required=True, help="PlanningReviewResult JSON path")
    parser.add_argument("--human-decision", required=True, help="PlanningHumanDecisionV1 JSON path")
    parser.add_argument("--expected-head", required=True, help="Expected current Git HEAD")
    parser.add_argument("--output", required=True, help="Existing external output directory")
    parser.add_argument(
        "--candidate",
        help="Candidate ZIP path (required by archive-candidate and git-bound modes)",
    )
    parser.add_argument("--logical-filename", help="Candidate logical filename (archive-candidate only)")
    parser.add_argument("--zip-sha256", help="Candidate ZIP SHA-256 (archive-candidate only)")
    parser.add_argument("--reviewed-head", help="Reviewed Git HEAD (git-bound only)")
    _add_format(parser)


def _output_format(ns: argparse.Namespace) -> OutputFormat:
    return "json" if getattr(ns, "format", "text") == "json" else "text"


def _create_args(ns: argparse.Namespace) -> CommandArgs:
    return PlanningCreateArgs(
        issue_id=ns.issue,
        output_dir=Path(ns.output),
        output_format=_output_format(ns),
        context_manifest_path=Path(ns.context_manifest) if ns.context_manifest is not None else None,
    )


def _revise_args(ns: argparse.Namespace) -> CommandArgs:
    return PlanningReviseArgs(
        candidate_path=Path(ns.candidate),
        request_path=Path(ns.request),
        output_dir=Path(ns.output),
        output_format=_output_format(ns),
    )


def _review_args(ns: argparse.Namespace) -> CommandArgs:
    mode: PlanningMode = ns.mode
    candidate = getattr(ns, "candidate", None)
    reviewed_head = getattr(ns, "reviewed_head", None)
    return PlanningReviewArgs(
        issue_id=ns.issue,
        mode=mode,
        output_dir=Path(ns.output),
        output_format=_output_format(ns),
        candidate_path=Path(candidate) if candidate is not None else None,
        reviewed_head=reviewed_head,
    )


def _apply_args(ns: argparse.Namespace) -> CommandArgs:
    mode: PlanningMode = ns.mode
    candidate = getattr(ns, "candidate", None)
    reviewed_head = getattr(ns, "reviewed_head", None)
    logical_filename = getattr(ns, "logical_filename", None)
    zip_sha256 = getattr(ns, "zip_sha256", None)
    return PlanningApplyArgs(
        issue_id=ns.issue,
        mode=mode,
        review_result_path=Path(ns.review_result),
        human_decision_path=Path(ns.human_decision),
        expected_head=ns.expected_head,
        output_dir=Path(ns.output),
        output_format=_output_format(ns),
        candidate_path=Path(candidate) if candidate is not None else None,
        logical_filename=logical_filename,
        zip_sha256=zip_sha256,
        reviewed_head=reviewed_head,
    )


def _run_create(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_args(args, PlanningCreateArgs, "planning create")
    result = use_cases.planning_create(
        PlanningCreateRequest(
            issue_id=typed.issue_id,
            output_dir=typed.output_dir,
            context_manifest_path=typed.context_manifest_path,
        )
    )
    return _outcome(result, typed.output_format)


def _run_revise(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_args(args, PlanningReviseArgs, "planning revise")
    result = use_cases.planning_revise(
        PlanningReviseRequest(
            candidate_path=typed.candidate_path,
            request_path=typed.request_path,
            output_dir=typed.output_dir,
        )
    )
    return _outcome(result, typed.output_format)


def _run_review(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_args(args, PlanningReviewArgs, "review planning")
    result = use_cases.planning_review(
        PlanningReviewRequest(
            issue_id=typed.issue_id,
            mode=typed.mode,
            output_dir=typed.output_dir,
            candidate_path=typed.candidate_path,
            reviewed_head=typed.reviewed_head,
        )
    )
    return _outcome(result, typed.output_format)


def _run_apply(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_args(args, PlanningApplyArgs, "planning apply")
    result = use_cases.planning_apply(
        PlanningApplyRequest(
            issue_id=typed.issue_id,
            mode=typed.mode,
            review_result_path=typed.review_result_path,
            human_decision_path=typed.human_decision_path,
            expected_head=typed.expected_head,
            output_dir=typed.output_dir,
            candidate_path=typed.candidate_path,
            logical_filename=typed.logical_filename,
            zip_sha256=typed.zip_sha256,
            reviewed_head=typed.reviewed_head,
        )
    )
    return _outcome(result, typed.output_format)


def _expect_args(args: CommandArgs, expected_type: type, command: str):
    if not isinstance(args, expected_type):
        raise RuntimeError(f"Invalid command args for {command}")
    return args


def _outcome(result, output_format: OutputFormat) -> CommandOutcome:
    text = render_planning_result_json(result) if output_format == "json" else render_planning_result_text(result)
    return CommandOutcome(exit_code=result.exit_code, text=text)
