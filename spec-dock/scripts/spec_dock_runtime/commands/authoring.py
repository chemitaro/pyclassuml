from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from spec_dock_runtime.application.authoring_pack.approval_check import ApprovalCheckRequest, check_authoring_approval
from spec_dock_runtime.application.authoring_pack.backend_invoke import BackendInvokeRequest, invoke_backend
from spec_dock_runtime.application.authoring_pack.candidate_validation import (
    CandidateValidationRequest,
    validate_authoring_candidates,
)
from spec_dock_runtime.application.authoring_pack.draft_adoption_validation import (
    IssueDraftAdoptionValidationRequest,
    SelectedSkeletonFillValidationRequest,
    validate_issue_draft_adoption,
    validate_selected_skeleton_fill,
)
from spec_dock_runtime.application.authoring_pack.github_sync_preflight import (
    GitHubSyncPreflightRequest,
    run_github_sync_preflight,
)
from spec_dock_runtime.application.authoring_pack.pack_prepare import PromptPackPrepareRequest, prepare_prompt_pack
from spec_dock_runtime.application.authoring_pack.pack_review import PackReviewRequest, review_authoring_pack
from spec_dock_runtime.application.authoring_pack.pack_stage import PackStageRequest, stage_authoring_pack
from spec_dock_runtime.commands.contracts import CommandArgs, CommandOutcome, CommandSpec
from spec_dock_runtime.presentation.authoring_pack.approval_check_renderer import (
    render_approval_check_json,
    render_approval_check_text,
)
from spec_dock_runtime.presentation.authoring_pack.backend_invoke_renderer import (
    render_backend_invoke_json,
    render_backend_invoke_text,
)
from spec_dock_runtime.presentation.authoring_pack.candidate_validation_renderer import (
    render_candidate_validation_json,
    render_candidate_validation_text,
)
from spec_dock_runtime.presentation.authoring_pack.diagnostics import render_preflight_json, render_preflight_text
from spec_dock_runtime.presentation.authoring_pack.draft_adoption_renderer import (
    render_draft_adoption_json,
    render_draft_adoption_text,
)
from spec_dock_runtime.presentation.authoring_pack.pack_prepare_renderer import (
    render_pack_prepare_json,
    render_pack_prepare_text,
)
from spec_dock_runtime.presentation.authoring_pack.pack_review_renderer import (
    render_pack_review_json,
    render_pack_review_text,
)
from spec_dock_runtime.presentation.authoring_pack.pack_stage_renderer import (
    render_pack_stage_json,
    render_pack_stage_text,
)
from spec_dock_runtime.presentation.contracts import CliText

if TYPE_CHECKING:
    import argparse

    from spec_dock_runtime.application.contracts import UseCases


@dataclass(frozen=True)
class AuthoringDeferredArgs(CommandArgs):
    command: str
    next_issue: str


@dataclass(frozen=True)
class AuthoringCandidateValidationArgs(CommandArgs):
    input_path: Path
    candidate_kind: str
    output_format: str
    evidence_mode: str
    review_report: Path | None
    expected_parent_initiative: str | None
    expected_parent_epic: str | None
    expected_source_hash: str | None
    report_path: Path | None


@dataclass(frozen=True)
class AuthoringApprovalCheckArgs(CommandArgs):
    input_path: Path
    approval_path: Path | None
    candidate_kind: str
    output_format: str
    evidence_mode: str
    review_report: Path | None
    candidate_evidence: Path | None
    expected_parent_initiative: str | None
    expected_parent_epic: str | None
    expected_requested_scope: str | None
    expected_effective_scope: str | None
    expected_candidate_pack_digest: str | None
    expected_candidate_evidence_digest: str | None
    expected_source_hash: str | None
    report_path: Path | None


@dataclass(frozen=True)
class AuthoringIssueDraftAdoptionValidationArgs(CommandArgs):
    input_path: Path
    issue_dir: Path
    output_format: str
    evidence_mode: str
    review_report: Path | None
    expected_review_digest: str | None
    expected_draft_pack_digest: str | None
    expected_source_hash: str | None
    report_path: Path | None


@dataclass(frozen=True)
class AuthoringSelectedSkeletonFillValidationArgs(CommandArgs):
    input_path: Path
    issue_dir: Path
    assurance: Path
    selected_skeleton: Path
    output_format: str
    evidence_mode: str
    review_report: Path | None
    expected_review_digest: str | None
    expected_profile: str | None
    expected_source_hash: str | None
    report_path: Path | None


@dataclass(frozen=True)
class AuthoringPreflightGithubSyncArgs(CommandArgs):
    evidence_mode: str
    output_format: str
    allow_default_branch_fallback: bool
    repo_root: Path | None
    ref: str | None
    source_paths: tuple[str, ...]
    expected_source_manifest: Path | None
    expected_source_hash: str | None
    provided_context_paths: tuple[str, ...]
    diff_summary: str | None
    unsynced_reason: str | None
    output_dir: Path | None


@dataclass(frozen=True)
class AuthoringPackPrepareArgs(CommandArgs):
    preflight: Path
    output_dir: Path
    output_format: str
    mode: str | None
    source_manifest: Path | None
    stale_if: Path | None


@dataclass(frozen=True)
class AuthoringPackReviewArgs(CommandArgs):
    input_path: Path
    output_format: str
    evidence_mode: str
    report_path: Path | None


@dataclass(frozen=True)
class AuthoringPackStageArgs(CommandArgs):
    input_path: Path
    stage_dir: Path
    output_format: str
    dry_run: bool


@dataclass(frozen=True)
class AuthoringBackendInvokeArgs(CommandArgs):
    prompt_pack: Path
    output_dir: Path
    output_format: str
    backend_command: str | None
    slug: str | None
    prompt: str | None
    evidence_mode: str
    timeout_seconds: float | None
    dry_run: bool


_DEFERRED_COMMANDS: dict[str, tuple[str, str]] = {}


def command_specs() -> dict[str, CommandSpec]:
    specs = {
        key: CommandSpec(
            add_arguments=_add_deferred_arguments,
            args_factory=_deferred_args_factory(command=command, next_issue=next_issue),
            run=_run_deferred,
        )
        for key, (command, next_issue) in _DEFERRED_COMMANDS.items()
    }
    specs["authoring_preflight_github_sync"] = CommandSpec(
        add_arguments=_add_preflight_github_sync_arguments,
        args_factory=_preflight_github_sync_args,
        run=_run_preflight_github_sync,
    )
    specs["authoring_pack_prepare"] = CommandSpec(
        add_arguments=_add_pack_prepare_arguments,
        args_factory=_pack_prepare_args,
        run=_run_pack_prepare,
    )
    specs["authoring_pack_review"] = CommandSpec(
        add_arguments=_add_pack_review_arguments,
        args_factory=_pack_review_args,
        run=_run_pack_review,
    )
    specs["authoring_pack_stage"] = CommandSpec(
        add_arguments=_add_pack_stage_arguments,
        args_factory=_pack_stage_args,
        run=_run_pack_stage,
    )
    specs["authoring_backend_invoke"] = CommandSpec(
        add_arguments=_add_backend_invoke_arguments,
        args_factory=_backend_invoke_args,
        run=_run_backend_invoke,
    )
    specs["authoring_approval_check"] = CommandSpec(
        add_arguments=_add_approval_check_arguments,
        args_factory=_approval_check_args,
        run=_run_approval_check,
    )
    specs["authoring_validate_initiative_epic_candidates"] = CommandSpec(
        add_arguments=_add_initiative_epic_candidate_arguments,
        args_factory=_initiative_epic_candidate_args,
        run=_run_candidate_validation,
    )
    specs["authoring_validate_epic_issue_candidates"] = CommandSpec(
        add_arguments=_add_epic_issue_candidate_arguments,
        args_factory=_epic_issue_candidate_args,
        run=_run_candidate_validation,
    )
    specs["authoring_validate_issue_draft_adoption"] = CommandSpec(
        add_arguments=_add_issue_draft_adoption_arguments,
        args_factory=_issue_draft_adoption_args,
        run=_run_issue_draft_adoption,
    )
    specs["authoring_validate_selected_skeleton_fill"] = CommandSpec(
        add_arguments=_add_selected_skeleton_fill_arguments,
        args_factory=_selected_skeleton_fill_args,
        run=_run_selected_skeleton_fill,
    )
    return specs


def _add_deferred_arguments(parser: argparse.ArgumentParser) -> None:
    del parser


def _add_candidate_validation_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True, dest="input_path")
    parser.add_argument("--format", choices=("text", "json"), default="text", dest="output_format")
    parser.add_argument("--evidence-mode", choices=("github-synced", "local-context"), default="github-synced")
    parser.add_argument("--review-report")
    parser.add_argument("--expected-source-manifest-hash", "--expected-source-hash", dest="expected_source_hash")
    parser.add_argument("--report-path")


def _add_initiative_epic_candidate_arguments(parser: argparse.ArgumentParser) -> None:
    _add_candidate_validation_arguments(parser)
    parser.add_argument("--expected-parent-initiative", required=True)


def _add_epic_issue_candidate_arguments(parser: argparse.ArgumentParser) -> None:
    _add_candidate_validation_arguments(parser)
    parser.add_argument("--expected-parent-epic", required=True)


def _add_approval_check_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True, dest="input_path")
    parser.add_argument("--approval", dest="approval_path")
    parser.add_argument("--candidate-kind", choices=("initiative-epic", "epic-issue"), required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text", dest="output_format")
    parser.add_argument("--evidence-mode", choices=("github-synced", "local-context"), default="github-synced")
    parser.add_argument("--review-report")
    parser.add_argument("--candidate-evidence")
    parser.add_argument("--expected-parent-initiative")
    parser.add_argument("--expected-parent-epic")
    parser.add_argument("--expected-requested-scope")
    parser.add_argument("--expected-effective-scope")
    parser.add_argument("--expected-candidate-pack-digest")
    parser.add_argument("--expected-candidate-evidence-digest")
    parser.add_argument("--expected-source-manifest-hash", "--expected-source-hash", dest="expected_source_hash")
    parser.add_argument("--report-path")


def _add_issue_draft_adoption_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True, dest="input_path")
    parser.add_argument("--issue-dir", required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text", dest="output_format")
    parser.add_argument("--evidence-mode", choices=("github-synced", "local-context"), default="github-synced")
    parser.add_argument("--review-report", required=True)
    parser.add_argument("--expected-review-digest")
    parser.add_argument("--expected-draft-pack-digest")
    parser.add_argument("--expected-source-manifest-hash", "--expected-source-hash", dest="expected_source_hash")
    parser.add_argument("--report-path")


def _add_selected_skeleton_fill_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True, dest="input_path")
    parser.add_argument("--issue-dir", required=True)
    parser.add_argument("--assurance", required=True)
    parser.add_argument("--selected-skeleton", required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text", dest="output_format")
    parser.add_argument("--evidence-mode", choices=("github-synced", "local-context"), default="github-synced")
    parser.add_argument("--review-report", required=True)
    parser.add_argument("--expected-review-digest")
    parser.add_argument("--expected-profile")
    parser.add_argument("--expected-source-manifest-hash", "--expected-source-hash", dest="expected_source_hash")
    parser.add_argument("--report-path")


def _add_preflight_github_sync_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--evidence-mode", choices=("github-synced", "local-context"), default="github-synced")
    parser.add_argument("--format", choices=("text", "json"), default="text", dest="output_format")
    parser.add_argument("--allow-default-branch-fallback", action="store_true")
    parser.add_argument("--repo-root")
    parser.add_argument("--ref")
    parser.add_argument("--source-path", action="append")
    parser.add_argument("--expected-source-manifest")
    parser.add_argument("--expected-source-hash")
    parser.add_argument("--provided-context-path", action="append")
    parser.add_argument("--diff-summary")
    parser.add_argument("--unsynced-reason")
    parser.add_argument("--output-dir")


def _add_pack_prepare_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--preflight", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text", dest="output_format")
    parser.add_argument("--mode", choices=("initiative", "epic", "issue", "selected-skeleton"))
    parser.add_argument("--source-manifest")
    parser.add_argument("--stale-if")


def _add_pack_review_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True, dest="input_path")
    parser.add_argument("--format", choices=("text", "json"), default="text", dest="output_format")
    parser.add_argument("--evidence-mode", choices=("github-synced", "local-context"), default="github-synced")
    parser.add_argument("--report-path")


def _add_pack_stage_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--input", required=True, dest="input_path")
    parser.add_argument("--stage-dir", required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text", dest="output_format")
    parser.add_argument("--dry-run", action="store_true")


def _add_backend_invoke_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--prompt-pack", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--format", choices=("text", "json"), default="text", dest="output_format")
    parser.add_argument("--backend-command")
    parser.add_argument("--slug")
    parser.add_argument("--prompt")
    parser.add_argument("--evidence-mode", choices=("github-synced", "local-context"), default="github-synced")
    parser.add_argument("--timeout-seconds", type=float)
    parser.add_argument("--dry-run", action="store_true")


def _preflight_github_sync_args(ns: argparse.Namespace) -> CommandArgs:
    return AuthoringPreflightGithubSyncArgs(
        evidence_mode=ns.evidence_mode,
        output_format=ns.output_format,
        allow_default_branch_fallback=bool(ns.allow_default_branch_fallback),
        repo_root=Path(ns.repo_root) if ns.repo_root else None,
        ref=ns.ref,
        source_paths=tuple(ns.source_path or ()),
        expected_source_manifest=Path(ns.expected_source_manifest) if ns.expected_source_manifest else None,
        expected_source_hash=ns.expected_source_hash,
        provided_context_paths=tuple(ns.provided_context_path or ()),
        diff_summary=ns.diff_summary,
        unsynced_reason=ns.unsynced_reason,
        output_dir=Path(ns.output_dir) if ns.output_dir else None,
    )


def _pack_prepare_args(ns: argparse.Namespace) -> CommandArgs:
    return AuthoringPackPrepareArgs(
        preflight=Path(ns.preflight),
        output_dir=Path(ns.output_dir),
        output_format=ns.output_format,
        mode=ns.mode,
        source_manifest=Path(ns.source_manifest) if ns.source_manifest else None,
        stale_if=Path(ns.stale_if) if ns.stale_if else None,
    )


def _pack_review_args(ns: argparse.Namespace) -> CommandArgs:
    return AuthoringPackReviewArgs(
        input_path=Path(ns.input_path),
        output_format=ns.output_format,
        evidence_mode=ns.evidence_mode,
        report_path=Path(ns.report_path) if ns.report_path else None,
    )


def _pack_stage_args(ns: argparse.Namespace) -> CommandArgs:
    return AuthoringPackStageArgs(
        input_path=Path(ns.input_path),
        stage_dir=Path(ns.stage_dir),
        output_format=ns.output_format,
        dry_run=bool(ns.dry_run),
    )


def _backend_invoke_args(ns: argparse.Namespace) -> CommandArgs:
    return AuthoringBackendInvokeArgs(
        prompt_pack=Path(ns.prompt_pack),
        output_dir=Path(ns.output_dir),
        output_format=ns.output_format,
        backend_command=ns.backend_command,
        slug=ns.slug,
        prompt=ns.prompt,
        evidence_mode=ns.evidence_mode,
        timeout_seconds=ns.timeout_seconds,
        dry_run=bool(ns.dry_run),
    )


def _initiative_epic_candidate_args(ns: argparse.Namespace) -> CommandArgs:
    return AuthoringCandidateValidationArgs(
        input_path=Path(ns.input_path),
        candidate_kind="initiative-epic",
        output_format=ns.output_format,
        evidence_mode=ns.evidence_mode,
        review_report=Path(ns.review_report) if ns.review_report else None,
        expected_parent_initiative=ns.expected_parent_initiative,
        expected_parent_epic=None,
        expected_source_hash=ns.expected_source_hash,
        report_path=Path(ns.report_path) if ns.report_path else None,
    )


def _epic_issue_candidate_args(ns: argparse.Namespace) -> CommandArgs:
    return AuthoringCandidateValidationArgs(
        input_path=Path(ns.input_path),
        candidate_kind="epic-issue",
        output_format=ns.output_format,
        evidence_mode=ns.evidence_mode,
        review_report=Path(ns.review_report) if ns.review_report else None,
        expected_parent_initiative=None,
        expected_parent_epic=ns.expected_parent_epic,
        expected_source_hash=ns.expected_source_hash,
        report_path=Path(ns.report_path) if ns.report_path else None,
    )


def _approval_check_args(ns: argparse.Namespace) -> CommandArgs:
    if ns.candidate_kind == "initiative-epic" and not ns.expected_parent_initiative:
        raise RuntimeError("--expected-parent-initiative is required for --candidate-kind initiative-epic")
    if ns.candidate_kind == "epic-issue" and not ns.expected_parent_epic:
        raise RuntimeError("--expected-parent-epic is required for --candidate-kind epic-issue")
    return AuthoringApprovalCheckArgs(
        input_path=Path(ns.input_path),
        approval_path=Path(ns.approval_path) if ns.approval_path else None,
        candidate_kind=ns.candidate_kind,
        output_format=ns.output_format,
        evidence_mode=ns.evidence_mode,
        review_report=Path(ns.review_report) if ns.review_report else None,
        candidate_evidence=Path(ns.candidate_evidence) if ns.candidate_evidence else None,
        expected_parent_initiative=ns.expected_parent_initiative,
        expected_parent_epic=ns.expected_parent_epic,
        expected_requested_scope=ns.expected_requested_scope,
        expected_effective_scope=ns.expected_effective_scope,
        expected_candidate_pack_digest=ns.expected_candidate_pack_digest,
        expected_candidate_evidence_digest=ns.expected_candidate_evidence_digest,
        expected_source_hash=ns.expected_source_hash,
        report_path=Path(ns.report_path) if ns.report_path else None,
    )


def _issue_draft_adoption_args(ns: argparse.Namespace) -> CommandArgs:
    return AuthoringIssueDraftAdoptionValidationArgs(
        input_path=Path(ns.input_path),
        issue_dir=Path(ns.issue_dir),
        output_format=ns.output_format,
        evidence_mode=ns.evidence_mode,
        review_report=Path(ns.review_report) if ns.review_report else None,
        expected_review_digest=ns.expected_review_digest,
        expected_draft_pack_digest=ns.expected_draft_pack_digest,
        expected_source_hash=ns.expected_source_hash,
        report_path=Path(ns.report_path) if ns.report_path else None,
    )


def _selected_skeleton_fill_args(ns: argparse.Namespace) -> CommandArgs:
    return AuthoringSelectedSkeletonFillValidationArgs(
        input_path=Path(ns.input_path),
        issue_dir=Path(ns.issue_dir),
        assurance=Path(ns.assurance),
        selected_skeleton=Path(ns.selected_skeleton),
        output_format=ns.output_format,
        evidence_mode=ns.evidence_mode,
        review_report=Path(ns.review_report) if ns.review_report else None,
        expected_review_digest=ns.expected_review_digest,
        expected_profile=ns.expected_profile,
        expected_source_hash=ns.expected_source_hash,
        report_path=Path(ns.report_path) if ns.report_path else None,
    )


def _deferred_args_factory(*, command: str, next_issue: str):
    def _deferred_args(ns: argparse.Namespace) -> CommandArgs:
        del ns
        return AuthoringDeferredArgs(command=command, next_issue=next_issue)

    return _deferred_args


def _run_preflight_github_sync(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    del use_cases
    preflight_args = _expect_preflight_github_sync_args(args)
    try:
        result = run_github_sync_preflight(
            GitHubSyncPreflightRequest(
                repo_root=preflight_args.repo_root,
                evidence_mode=preflight_args.evidence_mode,  # type: ignore[arg-type]
                ref=preflight_args.ref,
                allow_default_branch_fallback=preflight_args.allow_default_branch_fallback,
                source_paths=preflight_args.source_paths,
                expected_source_manifest=preflight_args.expected_source_manifest,
                expected_source_hash=preflight_args.expected_source_hash,
                provided_context_paths=preflight_args.provided_context_paths,
                diff_summary=preflight_args.diff_summary,
                unsynced_reason=preflight_args.unsynced_reason,
                output_dir=preflight_args.output_dir,
            )
        )
    except ValueError as error:
        return CommandOutcome(
            exit_code=2,
            text=CliText(stdout_lines=[], stderr_lines=[f"error: {error}"], warnings=[]),
        )
    exit_code = 0 if result.status == "pass" else 1
    if preflight_args.output_format == "json":
        stdout_lines = [render_preflight_json(result)]
    else:
        stdout_lines = render_preflight_text(result)
    return CommandOutcome(
        exit_code=exit_code,
        text=CliText(stdout_lines=stdout_lines, stderr_lines=[], warnings=[]),
    )


def _run_pack_prepare(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    del use_cases
    pack_args = _expect_pack_prepare_args(args)
    result = prepare_prompt_pack(
        PromptPackPrepareRequest(
            preflight_path=pack_args.preflight,
            output_dir=pack_args.output_dir,
            output_format=pack_args.output_format,  # type: ignore[arg-type]
            mode=pack_args.mode,  # type: ignore[arg-type]
            source_manifest_path=pack_args.source_manifest,
            stale_if_path=pack_args.stale_if,
        )
    )
    exit_code = 0 if result.status == "pass" else 1
    if pack_args.output_format == "json":
        stdout_lines = [render_pack_prepare_json(result)]
    else:
        stdout_lines = render_pack_prepare_text(result)
    return CommandOutcome(
        exit_code=exit_code,
        text=CliText(stdout_lines=stdout_lines, stderr_lines=[], warnings=[]),
    )


def _run_pack_review(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    del use_cases
    review_args = _expect_pack_review_args(args)
    result = review_authoring_pack(
        PackReviewRequest(
            input_path=review_args.input_path,
            output_format=review_args.output_format,  # type: ignore[arg-type]
            evidence_mode=review_args.evidence_mode,  # type: ignore[arg-type]
            report_path=review_args.report_path,
        )
    )
    exit_code = 0 if result.status == "pass" else 1
    if review_args.output_format == "json":
        stdout_lines = [render_pack_review_json(result)]
    else:
        stdout_lines = render_pack_review_text(result)
    return CommandOutcome(exit_code=exit_code, text=CliText(stdout_lines=stdout_lines, stderr_lines=[], warnings=[]))


def _run_pack_stage(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    del use_cases
    stage_args = _expect_pack_stage_args(args)
    result = stage_authoring_pack(
        PackStageRequest(
            input_path=stage_args.input_path,
            stage_dir=stage_args.stage_dir,
            output_format=stage_args.output_format,  # type: ignore[arg-type]
            dry_run=stage_args.dry_run,
        )
    )
    exit_code = 0 if result.status == "pass" else 1
    if stage_args.output_format == "json":
        stdout_lines = [render_pack_stage_json(result)]
    else:
        stdout_lines = render_pack_stage_text(result)
    return CommandOutcome(exit_code=exit_code, text=CliText(stdout_lines=stdout_lines, stderr_lines=[], warnings=[]))


def _run_backend_invoke(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    del use_cases
    backend_args = _expect_backend_invoke_args(args)
    result = invoke_backend(
        BackendInvokeRequest(
            prompt_pack=backend_args.prompt_pack,
            output_dir=backend_args.output_dir,
            output_format=backend_args.output_format,  # type: ignore[arg-type]
            backend_command=backend_args.backend_command,
            slug=backend_args.slug,
            prompt=backend_args.prompt,
            evidence_mode=backend_args.evidence_mode,  # type: ignore[arg-type]
            timeout_seconds=backend_args.timeout_seconds,
            dry_run=backend_args.dry_run,
        )
    )
    exit_code = 0 if result.status == "pass" else 1
    if backend_args.output_format == "json":
        stdout_lines = [render_backend_invoke_json(result)]
    else:
        stdout_lines = render_backend_invoke_text(result)
    return CommandOutcome(
        exit_code=exit_code,
        text=CliText(stdout_lines=stdout_lines, stderr_lines=[], warnings=[]),
    )


def _run_candidate_validation(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    del use_cases
    candidate_args = _expect_candidate_validation_args(args)
    result = validate_authoring_candidates(
        CandidateValidationRequest(
            input_path=candidate_args.input_path,
            candidate_kind=candidate_args.candidate_kind,  # type: ignore[arg-type]
            output_format=candidate_args.output_format,  # type: ignore[arg-type]
            evidence_mode=candidate_args.evidence_mode,  # type: ignore[arg-type]
            review_report=candidate_args.review_report,
            expected_parent_initiative=candidate_args.expected_parent_initiative,
            expected_parent_epic=candidate_args.expected_parent_epic,
            expected_source_hash=candidate_args.expected_source_hash,
            report_path=candidate_args.report_path,
        )
    )
    exit_code = 0 if result.status == "pass" else 1
    if candidate_args.output_format == "json":
        stdout_lines = [render_candidate_validation_json(result)]
    else:
        stdout_lines = render_candidate_validation_text(result)
    return CommandOutcome(exit_code=exit_code, text=CliText(stdout_lines=stdout_lines, stderr_lines=[], warnings=[]))


def _run_approval_check(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    del use_cases
    approval_args = _expect_approval_check_args(args)
    result = check_authoring_approval(
        ApprovalCheckRequest(
            input_path=approval_args.input_path,
            approval_path=approval_args.approval_path,
            candidate_kind=approval_args.candidate_kind,  # type: ignore[arg-type]
            output_format=approval_args.output_format,  # type: ignore[arg-type]
            evidence_mode=approval_args.evidence_mode,  # type: ignore[arg-type]
            review_report=approval_args.review_report,
            candidate_evidence=approval_args.candidate_evidence,
            expected_parent_initiative=approval_args.expected_parent_initiative,
            expected_parent_epic=approval_args.expected_parent_epic,
            expected_requested_scope=approval_args.expected_requested_scope,
            expected_effective_scope=approval_args.expected_effective_scope,
            expected_candidate_pack_digest=approval_args.expected_candidate_pack_digest,
            expected_candidate_evidence_digest=approval_args.expected_candidate_evidence_digest,
            expected_source_hash=approval_args.expected_source_hash,
            report_path=approval_args.report_path,
        )
    )
    exit_code = 0 if result.status == "pass" else 1
    if approval_args.output_format == "json":
        stdout_lines = [render_approval_check_json(result)]
    else:
        stdout_lines = render_approval_check_text(result)
    return CommandOutcome(exit_code=exit_code, text=CliText(stdout_lines=stdout_lines, stderr_lines=[], warnings=[]))


def _run_issue_draft_adoption(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    del use_cases
    draft_args = _expect_issue_draft_adoption_args(args)
    result = validate_issue_draft_adoption(
        IssueDraftAdoptionValidationRequest(
            input_path=draft_args.input_path,
            issue_dir=draft_args.issue_dir,
            output_format=draft_args.output_format,  # type: ignore[arg-type]
            evidence_mode=draft_args.evidence_mode,  # type: ignore[arg-type]
            review_report=draft_args.review_report,
            expected_review_digest=draft_args.expected_review_digest,
            expected_draft_pack_digest=draft_args.expected_draft_pack_digest,
            expected_source_hash=draft_args.expected_source_hash,
            report_path=draft_args.report_path,
        )
    )
    exit_code = 0 if result.status == "pass" else 1
    if draft_args.output_format == "json":
        stdout_lines = [render_draft_adoption_json(result)]
    else:
        stdout_lines = render_draft_adoption_text(result)
    return CommandOutcome(exit_code=exit_code, text=CliText(stdout_lines=stdout_lines, stderr_lines=[], warnings=[]))


def _run_selected_skeleton_fill(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    del use_cases
    skeleton_args = _expect_selected_skeleton_fill_args(args)
    result = validate_selected_skeleton_fill(
        SelectedSkeletonFillValidationRequest(
            input_path=skeleton_args.input_path,
            issue_dir=skeleton_args.issue_dir,
            assurance=skeleton_args.assurance,
            selected_skeleton=skeleton_args.selected_skeleton,
            output_format=skeleton_args.output_format,  # type: ignore[arg-type]
            evidence_mode=skeleton_args.evidence_mode,  # type: ignore[arg-type]
            review_report=skeleton_args.review_report,
            expected_review_digest=skeleton_args.expected_review_digest,
            expected_profile=skeleton_args.expected_profile,
            expected_source_hash=skeleton_args.expected_source_hash,
            report_path=skeleton_args.report_path,
        )
    )
    exit_code = 0 if result.status == "pass" else 1
    if skeleton_args.output_format == "json":
        stdout_lines = [render_draft_adoption_json(result)]
    else:
        stdout_lines = render_draft_adoption_text(result)
    return CommandOutcome(exit_code=exit_code, text=CliText(stdout_lines=stdout_lines, stderr_lines=[], warnings=[]))


def _run_deferred(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    del use_cases
    deferred_args = _expect_deferred_args(args)
    return CommandOutcome(
        exit_code=1,
        text=CliText(
            stdout_lines=[
                f"spec-dock: deferred (authoring) command={deferred_args.command}",
                "status=deferred",
                "authority=evidence_only",
                f"next_issue={deferred_args.next_issue}",
                "reason=not_implemented_in_this_issue",
            ],
            stderr_lines=[],
            warnings=[],
        ),
    )


def _expect_deferred_args(args: CommandArgs) -> AuthoringDeferredArgs:
    if not isinstance(args, AuthoringDeferredArgs):
        raise RuntimeError("Invalid command args for authoring")
    return args


def _expect_preflight_github_sync_args(args: CommandArgs) -> AuthoringPreflightGithubSyncArgs:
    if not isinstance(args, AuthoringPreflightGithubSyncArgs):
        raise RuntimeError("Invalid command args for authoring preflight github-sync")
    return args


def _expect_pack_prepare_args(args: CommandArgs) -> AuthoringPackPrepareArgs:
    if not isinstance(args, AuthoringPackPrepareArgs):
        raise RuntimeError("Invalid command args for authoring pack prepare")
    return args


def _expect_pack_review_args(args: CommandArgs) -> AuthoringPackReviewArgs:
    if not isinstance(args, AuthoringPackReviewArgs):
        raise RuntimeError("Invalid command args for authoring pack review")
    return args


def _expect_pack_stage_args(args: CommandArgs) -> AuthoringPackStageArgs:
    if not isinstance(args, AuthoringPackStageArgs):
        raise RuntimeError("Invalid command args for authoring pack stage")
    return args


def _expect_backend_invoke_args(args: CommandArgs) -> AuthoringBackendInvokeArgs:
    if not isinstance(args, AuthoringBackendInvokeArgs):
        raise RuntimeError("Invalid command args for authoring backend invoke")
    return args


def _expect_candidate_validation_args(args: CommandArgs) -> AuthoringCandidateValidationArgs:
    if not isinstance(args, AuthoringCandidateValidationArgs):
        raise RuntimeError("Invalid command args for authoring candidate validation")
    return args


def _expect_approval_check_args(args: CommandArgs) -> AuthoringApprovalCheckArgs:
    if not isinstance(args, AuthoringApprovalCheckArgs):
        raise RuntimeError("Invalid command args for authoring approval check")
    return args


def _expect_issue_draft_adoption_args(args: CommandArgs) -> AuthoringIssueDraftAdoptionValidationArgs:
    if not isinstance(args, AuthoringIssueDraftAdoptionValidationArgs):
        raise RuntimeError("Invalid command args for authoring issue draft adoption validation")
    return args


def _expect_selected_skeleton_fill_args(args: CommandArgs) -> AuthoringSelectedSkeletonFillValidationArgs:
    if not isinstance(args, AuthoringSelectedSkeletonFillValidationArgs):
        raise RuntimeError("Invalid command args for authoring selected skeleton fill validation")
    return args
