from __future__ import annotations

import argparse
from dataclasses import dataclass

from ..application.contracts import DoctorRequest, UseCases
from ..presentation.cli_text import render_doctor_text
from .contracts import CommandArgs, CommandOutcome, CommandSpec


@dataclass(frozen=True)
class DoctorArgs(CommandArgs):
    pass


def command_specs() -> dict[str, CommandSpec]:
    return {
        "doctor": CommandSpec(
            add_arguments=_add_doctor_arguments,
            args_factory=_doctor_args,
            run=_run_doctor,
        )
    }


def _add_doctor_arguments(parser: argparse.ArgumentParser) -> None:
    del parser


def _doctor_args(ns: argparse.Namespace) -> CommandArgs:
    del ns
    return DoctorArgs()


def _run_doctor(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    _expect_doctor_args(args)
    result = use_cases.doctor(DoctorRequest())
    text = render_doctor_text(result)
    return CommandOutcome(exit_code=(0 if result.ok else 1), text=text)


def _expect_doctor_args(args: CommandArgs) -> DoctorArgs:
    if not isinstance(args, DoctorArgs):
        raise RuntimeError("Invalid command args for doctor")
    return args
