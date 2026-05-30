from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from ..application.contracts import UseCases
from ..application.delegated_authoring import (
    DelegatedAuthoringBaselineStatusRequest,
    DelegatedAuthoringDiffGuardRequest,
    DelegatedAuthoringManifestRequest,
    generate_delegated_authoring_manifest,
    run_delegated_authoring_diff_guard,
    write_delegated_authoring_baseline_status,
)
from ..presentation.contracts import CliText
from .contracts import CommandArgs, CommandOutcome, CommandSpec


@dataclass(frozen=True)
class DelegatedAuthoringManifestArgs(CommandArgs):
    role: str
    scope: str
    target: str
    host_surface: str
    input_authority_file: Path


@dataclass(frozen=True)
class DelegatedAuthoringDiffGuardArgs(CommandArgs):
    role: str
    scope: str
    baseline_status: Path
    allow_existing_discussions: tuple[Path, ...]


@dataclass(frozen=True)
class DelegatedAuthoringBaselineStatusArgs(CommandArgs):
    output: Path


def command_specs() -> dict[str, CommandSpec]:
    return {
        "delegated_authoring_manifest": CommandSpec(
            add_arguments=_add_manifest_arguments,
            args_factory=_manifest_args,
            run=_run_manifest,
        ),
        "delegated_authoring_baseline_status": CommandSpec(
            add_arguments=_add_baseline_status_arguments,
            args_factory=_baseline_status_args,
            run=_run_baseline_status,
        ),
        "delegated_authoring_diff_guard": CommandSpec(
            add_arguments=_add_diff_guard_arguments,
            args_factory=_diff_guard_args,
            run=_run_diff_guard,
        ),
    }


def _add_manifest_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--role", required=True, choices=("system-architect", "implementation-planner"))
    parser.add_argument("--scope", required=True, help="Scope node id, e.g. iss-00126")
    parser.add_argument("--target", required=True, choices=("design", "plan"))
    parser.add_argument("--host-surface", required=True, choices=("cli", "desktop"))
    parser.add_argument("--input-authority-file", required=True, type=Path)


def _manifest_args(ns: argparse.Namespace) -> CommandArgs:
    return DelegatedAuthoringManifestArgs(
        role=str(ns.role),
        scope=str(ns.scope),
        target=str(ns.target),
        host_surface=str(ns.host_surface),
        input_authority_file=Path(ns.input_authority_file),
    )


def _add_diff_guard_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--role", required=True, choices=("system-architect", "implementation-planner"))
    parser.add_argument("--scope", required=True, help="Scope node id, e.g. iss-00127")
    parser.add_argument("--baseline-status", required=True, type=Path)
    parser.add_argument("--allow-existing-discussion", action="append", default=[], type=Path)


def _add_baseline_status_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output", required=True, type=Path)


def _diff_guard_args(ns: argparse.Namespace) -> CommandArgs:
    return DelegatedAuthoringDiffGuardArgs(
        role=str(ns.role),
        scope=str(ns.scope),
        baseline_status=Path(ns.baseline_status),
        allow_existing_discussions=tuple(Path(path) for path in ns.allow_existing_discussion),
    )


def _baseline_status_args(ns: argparse.Namespace) -> CommandArgs:
    return DelegatedAuthoringBaselineStatusArgs(output=Path(ns.output))


def _run_manifest(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_manifest_args(args)
    repo_root, specdock_dir = _runtime_paths(use_cases)
    result = generate_delegated_authoring_manifest(
        DelegatedAuthoringManifestRequest(
            role=typed.role,
            scope_id=typed.scope,
            target=typed.target,
            host_surface=typed.host_surface,
            input_authority_file=typed.input_authority_file,
            repo_root=repo_root,
            specdock_dir=specdock_dir,
        )
    )
    return CommandOutcome(exit_code=0 if result.ok else 1, text=_render_result(result))


def _run_baseline_status(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_baseline_status_args(args)
    repo_root, _specdock_dir = _runtime_paths(use_cases)
    result = write_delegated_authoring_baseline_status(
        DelegatedAuthoringBaselineStatusRequest(repo_root=repo_root, output_path=typed.output)
    )
    return CommandOutcome(exit_code=0 if result.ok else 1, text=_render_baseline_status_result(result))


def _run_diff_guard(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_diff_guard_args(args)
    repo_root, specdock_dir = _runtime_paths(use_cases)
    result = run_delegated_authoring_diff_guard(
        DelegatedAuthoringDiffGuardRequest(
            role=typed.role,
            scope_id=typed.scope,
            repo_root=repo_root,
            specdock_dir=specdock_dir,
            baseline_status=typed.baseline_status,
            allow_existing_discussions=typed.allow_existing_discussions,
        )
    )
    return CommandOutcome(exit_code=0 if result.ok else 1, text=_render_diff_guard_result(result))


def _expect_manifest_args(args: CommandArgs) -> DelegatedAuthoringManifestArgs:
    if not isinstance(args, DelegatedAuthoringManifestArgs):
        raise RuntimeError("Invalid command args for delegated-authoring manifest")
    return args


def _expect_baseline_status_args(args: CommandArgs) -> DelegatedAuthoringBaselineStatusArgs:
    if not isinstance(args, DelegatedAuthoringBaselineStatusArgs):
        raise RuntimeError("Invalid command args for delegated-authoring baseline-status")
    return args


def _expect_diff_guard_args(args: CommandArgs) -> DelegatedAuthoringDiffGuardArgs:
    if not isinstance(args, DelegatedAuthoringDiffGuardArgs):
        raise RuntimeError("Invalid command args for delegated-authoring diff-guard")
    return args


def _runtime_paths(use_cases: UseCases) -> tuple[Path, Path]:
    specdock_dir = use_cases.specdock_dir
    repo_root = use_cases.repo_root
    if specdock_dir is None and repo_root is not None:
        specdock_dir = repo_root / "spec-dock"
    if repo_root is None and specdock_dir is not None:
        repo_root = specdock_dir.parent
    if repo_root is None or specdock_dir is None:
        raise RuntimeError("runtime paths are not configured")
    return repo_root, specdock_dir


def _render_result(result) -> CliText:
    lines = [
        "spec-dock: ok (delegated-authoring manifest)"
        if result.ok
        else "spec-dock: blocked (delegated-authoring manifest)",
        f"status={result.status}",
        f"reason={result.reason}",
        f"role={result.role}",
        f"scope={result.scope_id}",
        f"target={result.target}",
        f"host_surface={result.host_surface}",
    ]
    for detail in result.details:
        lines.append(f"detail={detail}")
    return CliText(stdout_lines=lines, stderr_lines=[], warnings=[])


def _render_baseline_status_result(result) -> CliText:
    lines = [
        "spec-dock: ok (delegated-authoring baseline-status)"
        if result.ok
        else "spec-dock: blocked (delegated-authoring baseline-status)",
        f"status={result.status}",
        f"reason={result.reason}",
    ]
    for detail in result.details:
        lines.append(f"detail={detail}")
    return CliText(stdout_lines=lines, stderr_lines=[], warnings=[])


def _render_diff_guard_result(result) -> CliText:
    lines = [
        "spec-dock: ok (delegated-authoring diff-guard)"
        if result.ok
        else "spec-dock: blocked (delegated-authoring diff-guard)",
        f"status={result.status}",
        f"reason={result.reason}",
        f"scope={result.scope_id}",
    ]
    for detail in result.details:
        lines.append(f"detail={detail}")
    return CliText(stdout_lines=lines, stderr_lines=[], warnings=[])
