from __future__ import annotations

import argparse
from dataclasses import dataclass
import re

from spec_dock_runtime.application.contracts import DoctorRequest, UseCases
from spec_dock_runtime.commands.contracts import CommandArgs, CommandOutcome, CommandSpec
from spec_dock_runtime.presentation.cli_text import render_doctor_text


@dataclass(frozen=True)
class DoctorArgs(CommandArgs):
    github_repo: str | None = None
    github_pr: int | None = None
    github_head_sha: str | None = None
    github_extended: bool = False


def command_specs() -> dict[str, CommandSpec]:
    return {
        "doctor": CommandSpec(
            add_arguments=_add_doctor_arguments,
            args_factory=_doctor_args,
            run=_run_doctor,
        )
    }


def _add_doctor_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--github-repo",
        type=_github_repo_arg,
        help="GitHub repo slug for fixed capability diagnostics, e.g. owner/repo",
    )
    parser.add_argument(
        "--github-pr",
        type=_github_pr_arg,
        help="GitHub pull request number for fixed capability diagnostics",
    )
    parser.add_argument(
        "--github-head-sha",
        type=_github_head_sha_arg,
        help="GitHub PR head SHA for fixed capability diagnostics",
    )
    parser.add_argument(
        "--github-extended",
        action="store_true",
        help="Include fixed optional GitHub capability diagnostics",
    )


def _doctor_args(ns: argparse.Namespace) -> CommandArgs:
    return DoctorArgs(
        github_repo=ns.github_repo,
        github_pr=ns.github_pr,
        github_head_sha=ns.github_head_sha,
        github_extended=bool(ns.github_extended),
    )


def _run_doctor(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    doctor_args = _expect_doctor_args(args)
    result = use_cases.doctor(
        DoctorRequest(
            github_repo=doctor_args.github_repo,
            github_pr=doctor_args.github_pr,
            github_head_sha=doctor_args.github_head_sha,
            github_extended=doctor_args.github_extended,
        )
    )
    text = render_doctor_text(result)
    return CommandOutcome(exit_code=(0 if result.ok else 1), text=text)


def _expect_doctor_args(args: CommandArgs) -> DoctorArgs:
    if not isinstance(args, DoctorArgs):
        raise RuntimeError("Invalid command args for doctor")
    return args


def _github_repo_arg(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value or ""):
        return value
    raise argparse.ArgumentTypeError("--github-repo must be OWNER/REPO")


def _github_pr_arg(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("--github-pr must be a positive integer") from exc
    if parsed > 0:
        return parsed
    raise argparse.ArgumentTypeError("--github-pr must be a positive integer")


def _github_head_sha_arg(value: str) -> str:
    if re.fullmatch(r"[0-9A-Fa-f]{7,64}", value or ""):
        return value
    raise argparse.ArgumentTypeError("--github-head-sha must be a 7-64 character hex SHA")
