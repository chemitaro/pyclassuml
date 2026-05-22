from pathlib import Path

from pyclassuml.cli import CliRunResult, bind_command_request, run_cli
from pyclassuml.model import (
    CommandName,
    CommandRequest,
    CommandResult,
    DiagnosticSeverity,
    DiffCurrentState,
    FailureReason,
    OriginSeam,
    Recoverability,
    RunSummary,
)
from pyclassuml.report import ReportRunResult


def command_result(exit_code: int) -> CommandResult:
    return CommandResult(
        artifact_path=Path("diagram.puml") if exit_code == 0 else None,
        summary=RunSummary(failure_reason=None if exit_code == 0 else FailureReason.VCS_READ_FAILURE),
        diagnostics=(),
        exit_code=exit_code,
    )


def test_generate_binds_full_common_options_with_raw_relative_cwd_and_exact_process_cwd() -> None:
    process_cwd = Path("relative/process")

    request = bind_command_request(
        (
            "generate",
            "--cwd",
            "../work",
            "--config",
            "config/.pyclassuml.toml",
            "--project-root",
            ".",
            "--package-root",
            "src/pyclassuml",
            "--scope-root",
            "src",
            "--output",
            "out/diagram.puml",
            "--ignore",
            "tests/**",
            "--ignore",
            "build/**",
            "--depth",
            "3",
            "--strict",
            "--target-python",
            "3.12",
            "src/pyclassuml/model/contracts.py",
            "pyclassuml.model:CommandRequest",
        ),
        process_cwd,
    )

    assert request.process_cwd is process_cwd
    options = request.cli_options
    assert options.command is CommandName.GENERATE
    assert options.cwd == Path("../work")
    assert options.config == Path("config/.pyclassuml.toml")
    assert options.project_root == Path(".")
    assert options.package_root == Path("src/pyclassuml")
    assert options.scope_root == Path("src")
    assert options.output == Path("out/diagram.puml")
    assert options.ignore == ("tests/**", "build/**")
    assert options.depth == 3
    assert options.strict is True
    assert options.target_python == "3.12"
    assert options.generate is not None
    assert options.generate.targets == (
        "src/pyclassuml/model/contracts.py",
        "pyclassuml.model:CommandRequest",
    )
    assert options.diff is None


def test_diff_binds_default_current_state_and_include_untracked() -> None:
    request = bind_command_request(("diff",), Path("/repo"))

    options = request.cli_options
    assert options.command is CommandName.DIFF
    assert options.diff is not None
    assert options.diff.base_ref is None
    assert options.diff.current_state is DiffCurrentState.WORKING_TREE
    assert options.diff.current_state_cli_provided is False
    assert options.diff.include_untracked is True
    assert options.diff.include_untracked_cli_provided is False
    assert options.generate is None


def test_diff_binds_specified_current_state_and_include_untracked() -> None:
    request = bind_command_request(
        ("diff", "--base", "origin/main", "--current-state", "head", "--include-untracked"),
        Path("/repo"),
    )

    assert request.cli_options.diff is not None
    assert request.cli_options.diff.base_ref == "origin/main"
    assert request.cli_options.diff.current_state is DiffCurrentState.HEAD
    assert request.cli_options.diff.current_state_cli_provided is True
    assert request.cli_options.diff.include_untracked is True
    assert request.cli_options.diff.include_untracked_cli_provided is True


def test_diff_binds_explicit_base_preserving_defaults() -> None:
    request = bind_command_request(("diff", "--base", "origin/main"), Path("/repo"))

    assert request.cli_options.diff is not None
    assert request.cli_options.diff.base_ref == "origin/main"
    assert request.cli_options.diff.current_state is DiffCurrentState.WORKING_TREE
    assert request.cli_options.diff.current_state_cli_provided is False
    assert request.cli_options.diff.include_untracked is True
    assert request.cli_options.diff.include_untracked_cli_provided is False


def test_diff_binds_no_include_untracked_opt_out() -> None:
    request = bind_command_request(
        ("diff", "--base", "origin/main", "--no-include-untracked"),
        Path("/repo"),
    )

    assert request.cli_options.diff is not None
    assert request.cli_options.diff.include_untracked is False
    assert request.cli_options.diff.include_untracked_cli_provided is True


def test_diff_binds_common_options_with_raw_relative_paths_and_diff_options() -> None:
    process_cwd = Path("relative/process")

    request = bind_command_request(
        (
            "diff",
            "--cwd",
            "../work",
            "--config",
            "config/.pyclassuml.toml",
            "--project-root",
            ".",
            "--package-root",
            "src/pyclassuml",
            "--scope-root",
            "src",
            "--output",
            "out/diff.puml",
            "--ignore",
            "tests/**",
            "--ignore",
            "build/**",
            "--depth",
            "2",
            "--strict",
            "--target-python",
            "3.12",
            "--base",
            "origin/main",
            "--current-state",
            "head",
            "--include-untracked",
        ),
        process_cwd,
    )

    assert request.process_cwd is process_cwd
    options = request.cli_options
    assert options.command is CommandName.DIFF
    assert options.cwd == Path("../work")
    assert options.config == Path("config/.pyclassuml.toml")
    assert options.project_root == Path(".")
    assert options.package_root == Path("src/pyclassuml")
    assert options.scope_root == Path("src")
    assert options.output == Path("out/diff.puml")
    assert options.ignore == ("tests/**", "build/**")
    assert options.depth == 2
    assert options.strict is True
    assert options.target_python == "3.12"
    assert options.diff is not None
    assert options.diff.base_ref == "origin/main"
    assert options.diff.current_state is DiffCurrentState.HEAD
    assert options.diff.current_state_cli_provided is True
    assert options.diff.include_untracked is True
    assert options.diff.include_untracked_cli_provided is True
    assert options.generate is None


def test_usage_errors_do_not_call_handler_and_return_cli_usage_error() -> None:
    calls: list[CommandRequest] = []

    def handler(request: CommandRequest) -> CommandResult:
        calls.append(request)
        return command_result(0)

    for argv in (
        ("generate", "--unknown"),
        (),
        ("diff", "--base", "main", "--depth", "-1"),
        ("diff", "--base", "main", "--target-python", "3.x"),
        ("diff", "--base", ""),
    ):
        result = run_cli(argv, Path("/repo"), handler)

        assert result.exit_code == 2
        assert result.command_result.exit_code == 2
        assert result.command_result.artifact_path is None
        assert result.command_result.summary.failure_reason is FailureReason.CLI_USAGE_ERROR
        assert len(result.command_result.diagnostics) == 1
        diagnostic = result.command_result.diagnostics[0]
        assert diagnostic.severity is DiagnosticSeverity.ERROR
        assert diagnostic.origin_seam is OriginSeam.CLI
        assert diagnostic.recoverability is Recoverability.FATAL
        assert diagnostic.failure_reason is FailureReason.CLI_USAGE_ERROR
        assert diagnostic.code == "cli_usage_error"
        assert result.stdout_text == ""
        assert "usage:" in result.stderr_text
        assert "error:" in result.stderr_text

    assert calls == []


def test_help_returns_stdout_without_calling_handler() -> None:
    calls: list[CommandRequest] = []

    def handler(request: CommandRequest) -> CommandResult:
        calls.append(request)
        return command_result(0)

    result = run_cli(("--help",), Path("/repo"), handler)

    assert result.exit_code == 0
    assert result.command_result.exit_code == 0
    assert result.command_result.diagnostics == ()
    assert result.stderr_text == ""
    assert "usage: pyclassuml" in result.stdout_text
    assert calls == []


def test_handler_exit_propagates_for_zero_and_nonzero_preserving_command_result() -> None:
    seen_requests: list[CommandRequest] = []
    expected_results = [command_result(0), command_result(7)]

    def handler(request: CommandRequest) -> CommandResult:
        seen_requests.append(request)
        return expected_results[len(seen_requests) - 1]

    success = run_cli(("generate", "pkg/module.py"), Path("/repo"), handler)
    failure = run_cli(("diff", "--base", "main"), Path("/repo"), handler)

    assert success == CliRunResult(command_result=expected_results[0], exit_code=0, stderr_text="")
    assert failure == CliRunResult(command_result=expected_results[1], exit_code=7, stderr_text="")
    assert success.command_result is expected_results[0]
    assert failure.command_result is expected_results[1]
    assert len(seen_requests) == 2


def test_report_run_result_handler_projects_stream_text_and_exit_code() -> None:
    report_result = ReportRunResult(
        command_result=command_result(7),
        outcome_kind="hard_failure",
        stdout_text="out\n",
        stderr_text="err\n",
    )

    result = run_cli(("generate", "pkg/module.py"), Path("/repo"), lambda request: report_result)

    assert result.command_result is report_result.command_result
    assert result.exit_code == 7
    assert result.stdout_text == "out\n"
    assert result.stderr_text == "err\n"
