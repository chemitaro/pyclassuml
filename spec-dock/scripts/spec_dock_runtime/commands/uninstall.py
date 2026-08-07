from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import TYPE_CHECKING

from spec_dock_runtime.commands.contracts import CommandArgs, CommandOutcome, CommandSpec
from spec_dock_runtime.presentation.contracts import CliText

if TYPE_CHECKING:
    import argparse

    from spec_dock_runtime.application.contracts import UseCases

UPSTREAM_SOURCE = "git+https://github.com/chemitaro/spec-dock"


@dataclass(frozen=True)
class UninstallArgs(CommandArgs):
    target: str
    apply: bool
    keep_specs: bool
    remove_specs: bool
    json: bool


def command_specs() -> dict[str, CommandSpec]:
    return {
        "uninstall": CommandSpec(
            add_arguments=_add_uninstall_arguments,
            args_factory=_uninstall_args,
            run=_run_uninstall,
        )
    }


def _add_uninstall_arguments(parser: argparse.ArgumentParser) -> None:
    parser.description = (
        "Uninstall SpecDock-managed repo assets by running "
        f"uvx --no-cache --from {UPSTREAM_SOURCE} spec-dock uninstall TARGET. "
        "TARGET defaults to the current working directory."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Managed repo target path to uninstall (default: current working directory)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the uninstall plan instead of showing a dry-run plan",
    )
    specs_mode = parser.add_mutually_exclusive_group()
    specs_mode.add_argument(
        "--keep-specs",
        action="store_true",
        help="Keep spec history while uninstalling managed tooling",
    )
    specs_mode.add_argument(
        "--remove-specs",
        action="store_true",
        help="Remove spec history while uninstalling managed tooling",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Forward JSON output mode to the installer CLI",
    )


def _uninstall_args(ns: argparse.Namespace) -> CommandArgs:
    return UninstallArgs(
        target=str(getattr(ns, "path", ".")),
        apply=bool(getattr(ns, "apply", False)),
        keep_specs=bool(getattr(ns, "keep_specs", False)),
        remove_specs=bool(getattr(ns, "remove_specs", False)),
        json=bool(getattr(ns, "json", False)),
    )


def _run_uninstall(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    del use_cases
    typed = _expect_uninstall_args(args)
    target = Path(typed.target).expanduser().resolve()
    command = [
        "uvx",
        "--no-cache",
        "--from",
        UPSTREAM_SOURCE,
        "spec-dock",
        "uninstall",
        str(target),
    ]
    if typed.apply:
        command.append("--apply")
    if typed.keep_specs:
        command.append("--keep-specs")
    if typed.remove_specs:
        command.append("--remove-specs")
    if typed.json:
        command.append("--json")

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return CommandOutcome(
            exit_code=127,
            text=CliText(
                stdout_lines=[],
                stderr_lines=["error: uvx could not be executed. Install uv/uvx or ensure uvx is on PATH, then retry."],
                warnings=[],
            ),
        )
    return CommandOutcome(
        exit_code=int(result.returncode),
        text=CliText(
            stdout_lines=result.stdout.splitlines(),
            stderr_lines=result.stderr.splitlines(),
            warnings=[],
        ),
    )


def _expect_uninstall_args(args: CommandArgs) -> UninstallArgs:
    if not isinstance(args, UninstallArgs):
        raise RuntimeError("Invalid command args for uninstall")
    return args
