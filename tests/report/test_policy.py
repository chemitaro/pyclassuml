from datetime import datetime
from pathlib import Path

import pytest

from pyclassuml.model import (
    AnalysisConfig,
    ChangedClassInventory,
    CommandName,
    DependencyGraph,
    Diagnostic,
    DiagnosticSeverity,
    DiagramModel,
    ExecutionContext,
    FailureReason,
    OriginSeam,
    PlantUmlText,
    Recoverability,
    RenderFailureSignal,
    TargetObservations,
    TargetSet,
)
from pyclassuml.report import (
    ReportInputs,
    build_run_summary,
    decide_artifact_path,
    decide_exit_policy,
    write_report,
)


TIMESTAMP = datetime(2026, 5, 4, 12, 34, 56)


def context(tmp_path: Path) -> ExecutionContext:
    return ExecutionContext(
        execution_cwd=tmp_path,
        project_root=tmp_path,
        package_root=tmp_path / "src",
        scope_root=tmp_path / "src",
    )


def diagram_model() -> DiagramModel:
    return DiagramModel(
        containers=("pkg/a.py", "pkg/b.py"),
        rendered_classes=("pkg/a.py:A", "pkg/b.py:B"),
        rendered_relations=(("pkg/a.py:A", "pkg/b.py:B", "uses"),),
        aliases=(("pkg/a.py:A", "c001"), ("pkg/b.py:B", "c002")),
    )


def report_inputs(tmp_path: Path, **overrides: object) -> ReportInputs:
    kwargs: dict[str, object] = {
        "command": CommandName.GENERATE,
        "context": context(tmp_path),
        "config": AnalysisConfig(),
        "timestamp": TIMESTAMP,
        "plantuml_text": PlantUmlText("@startuml\n@enduml"),
        "diagram_model": diagram_model(),
        "target_set": TargetSet(
            seed_files=(Path("pkg/a.py"), Path("pkg/b.py")),
            observations=TargetObservations(ignored_seed_candidate_count=3, diff_scope_excluded_count=4),
        ),
        "dependency_graph": DependencyGraph(reachable_files=(Path("pkg/a.py"), Path("pkg/b.py"), Path("pkg/c.py"))),
        "changed_class_inventory": ChangedClassInventory(class_count=5),
        "scope_stop_count": 6,
    }
    kwargs.update(overrides)
    return ReportInputs(**kwargs)


def warning(code: str, recoverability: Recoverability = Recoverability.RECOVERABLE) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.WARNING,
        code=code,
        message=f"{code} warning",
        origin_seam=OriginSeam.VCS,
        recoverability=recoverability,
    )


def error(code: str, failure_reason: FailureReason, origin_seam: OriginSeam = OriginSeam.PARSE) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code=code,
        message=f"{code} error",
        origin_seam=origin_seam,
        recoverability=Recoverability.FATAL,
        failure_reason=failure_reason,
    )


def test_auto_names_generate_and_diff_with_fixed_timestamp(tmp_path: Path) -> None:
    generate = decide_artifact_path(CommandName.GENERATE, context(tmp_path), AnalysisConfig(), TIMESTAMP)
    diff = decide_artifact_path(CommandName.DIFF, context(tmp_path), AnalysisConfig(), TIMESTAMP)

    assert generate.resolved_output_path == tmp_path / "pyclassuml_20260504_123456.puml"
    assert generate.base_name == "pyclassuml_20260504_123456.puml"
    assert diff.resolved_output_path == tmp_path / "pyclassuml_diff_20260504_123456.puml"
    assert diff.base_name == "pyclassuml_diff_20260504_123456.puml"


def test_explicit_relative_and_absolute_output_resolve_with_suffix_collisions(tmp_path: Path) -> None:
    relative_base = tmp_path / "out" / "diagram.puml"
    relative_base.parent.mkdir()
    relative_base.write_text("exists", encoding="utf-8")
    (tmp_path / "out" / "diagram_2.puml").write_text("exists", encoding="utf-8")

    relative = decide_artifact_path(
        CommandName.GENERATE,
        context(tmp_path),
        AnalysisConfig(output=Path("out/diagram.puml")),
        TIMESTAMP,
    )
    absolute = decide_artifact_path(
        CommandName.GENERATE,
        context(tmp_path),
        AnalysisConfig(output=tmp_path / "absolute.puml"),
        TIMESTAMP,
    )

    assert relative.resolved_output_path == tmp_path / "out" / "diagram_3.puml"
    assert relative.collision_suffix == 3
    assert absolute.resolved_output_path == tmp_path / "absolute.puml"


def test_unspecified_output_auto_name_uses_next_suffix_collision(tmp_path: Path) -> None:
    base = tmp_path / "pyclassuml_20260504_123456.puml"
    base.write_text("exists", encoding="utf-8")
    (tmp_path / "pyclassuml_20260504_123456_2.puml").write_text("exists", encoding="utf-8")

    decision = decide_artifact_path(CommandName.GENERATE, context(tmp_path), AnalysisConfig(), TIMESTAMP)

    assert decision.resolved_output_path == tmp_path / "pyclassuml_20260504_123456_3.puml"
    assert decision.collision_suffix == 3


def test_missing_parent_directory_is_created_on_success_write(tmp_path: Path) -> None:
    result = write_report(
        report_inputs(tmp_path, config=AnalysisConfig(output=Path("missing/diagram.puml"))),
    )

    assert result.command_result.exit_code == 0
    assert result.command_result.artifact_path == tmp_path / "missing" / "diagram.puml"
    assert (tmp_path / "missing" / "diagram.puml").read_text(encoding="utf-8") == "@startuml\n@enduml"


def test_success_clean_write_stdout_text_and_diagram_model_counters(tmp_path: Path) -> None:
    result = write_report(report_inputs(tmp_path))

    assert result.outcome_kind == "clean_success"
    assert result.command_result.exit_code == 0
    assert result.command_result.artifact_path == tmp_path / "pyclassuml_20260504_123456.puml"
    assert result.stderr_text == ""
    assert "outcome: clean_success" in result.stdout_text
    assert "extracted_class_count: 2" in result.stdout_text
    assert "extracted_relation_count: 1" in result.stdout_text
    assert result.command_result.summary.counters == {
        "seed_file_count": 2,
        "reachable_file_count": 3,
        "extracted_class_count": 2,
        "extracted_relation_count": 1,
        "changed_class_count": 5,
        "ignored_file_count": 3,
        "warning_count": 0,
        "scope_stop_count": 6,
        "diff_scope_excluded_count": 4,
    }


def test_generate_report_uses_zero_changed_class_inventory(tmp_path: Path) -> None:
    result = write_report(
        report_inputs(
            tmp_path,
            changed_class_inventory=ChangedClassInventory(class_count=0),
        )
    )

    assert result.command_result.exit_code == 0
    assert result.command_result.summary.counters["changed_class_count"] == 0
    assert "changed_class_count: 0" in result.stdout_text


def test_diff_report_uses_nonzero_changed_class_inventory(tmp_path: Path) -> None:
    result = write_report(
        report_inputs(
            tmp_path,
            command=CommandName.DIFF,
            changed_class_inventory=ChangedClassInventory(
                class_count=2,
                changed_files=(Path("pkg/a.py"), Path("pkg/b.py")),
            ),
        )
    )

    assert result.command_result.exit_code == 0
    assert result.command_result.artifact_path == tmp_path / "pyclassuml_diff_20260504_123456.puml"
    assert result.command_result.summary.counters["changed_class_count"] == 2
    assert "changed_class_count: 2" in result.stdout_text


def test_recoverable_noop_warning_is_warning_only_success(tmp_path: Path) -> None:
    result = write_report(report_inputs(tmp_path, diagnostics=(warning("head_untracked_noop"),)))

    assert result.outcome_kind == "warning_only_success"
    assert result.command_result.exit_code == 0
    assert result.command_result.artifact_path == tmp_path / "pyclassuml_20260504_123456.puml"
    assert (tmp_path / "pyclassuml_20260504_123456.puml").read_text(encoding="utf-8") == "@startuml\n@enduml"
    assert result.stderr_text == ""
    assert result.stdout_text
    assert "warning_count: 1" in result.stdout_text
    assert "warning:head_untracked_noop: head_untracked_noop warning" in result.stdout_text


def test_degraded_output_warning_is_degraded_success(tmp_path: Path) -> None:
    result = write_report(
        report_inputs(
            tmp_path,
            diagnostics=(warning("syntax_degraded", Recoverability.DEGRADED_OUTPUT),),
        )
    )

    assert result.outcome_kind == "degraded_success"
    assert result.command_result.exit_code == 0
    assert result.command_result.artifact_path == tmp_path / "pyclassuml_20260504_123456.puml"
    assert (tmp_path / "pyclassuml_20260504_123456.puml").read_text(encoding="utf-8") == "@startuml\n@enduml"
    assert result.stderr_text == ""
    assert result.stdout_text
    assert "outcome: degraded_success" in result.stdout_text


@pytest.mark.parametrize(
    ("reason", "origin_seam"),
    (
        (FailureReason.INVALID_CONFIG_OR_CONFIG_PATH, OriginSeam.CONFIG),
        (FailureReason.INVALID_PATH_OR_CONTAINMENT, OriginSeam.TARGETS),
        (FailureReason.GENERATE_SCOPE_VIOLATION, OriginSeam.TARGETS),
        (FailureReason.GENERATE_ZERO_TARGET_AFTER_NORMALIZE, OriginSeam.TARGETS),
        (FailureReason.DIFF_ZERO_TARGET_AFTER_SCOPE_FILTER, OriginSeam.TARGETS),
        (FailureReason.TRAVERSAL_LIMIT_REACHED, OriginSeam.ANALYZE),
        (FailureReason.OUTPUT_WRITE_FAILURE, OriginSeam.REPORT),
        (FailureReason.VCS_READ_FAILURE, OriginSeam.VCS),
    ),
)
def test_hard_failure_reason_table_is_nonzero_stderr_without_artifact(
    tmp_path: Path,
    reason: FailureReason,
    origin_seam: OriginSeam,
) -> None:
    result = write_report(report_inputs(tmp_path, diagnostics=(error(reason.value, reason, origin_seam),)))

    assert result.outcome_kind == "hard_failure"
    assert result.command_result.exit_code == 1
    assert result.command_result.artifact_path is None
    assert result.command_result.summary.failure_reason is reason
    assert result.stdout_text == ""
    assert result.stderr_text
    assert f"failure_reason: {reason.value}" in result.stderr_text
    assert f"error:{reason.value}: {reason.value} error" in result.stderr_text
    assert not (tmp_path / "pyclassuml_20260504_123456.puml").exists()


def test_render_failure_signal_is_degraded_failure_with_signal_counters_and_no_write(tmp_path: Path) -> None:
    signal = RenderFailureSignal(
        failure_reason=FailureReason.DIAGRAM_UNBUILDABLE_AFTER_RECOVERY,
        diagnostics=(error("render_unbuildable", FailureReason.DIAGRAM_UNBUILDABLE_AFTER_RECOVERY, OriginSeam.RENDER),),
        class_count=7,
        relation_count=8,
        partial_diagram_present=True,
    )

    result = write_report(
        report_inputs(tmp_path, plantuml_text=None, diagram_model=None, render_failure_signal=signal)
    )

    assert result.outcome_kind == "degraded_failure"
    assert result.command_result.exit_code == 1
    assert result.command_result.artifact_path is None
    assert not (tmp_path / "pyclassuml_20260504_123456.puml").exists()
    assert result.stdout_text == ""
    assert "failure_reason: diagram_unbuildable_after_recovery" in result.stderr_text
    assert "error:render_unbuildable: render_unbuildable error" in result.stderr_text
    assert result.command_result.diagnostics == signal.diagnostics
    assert result.command_result.summary.counters["extracted_class_count"] == 7
    assert result.command_result.summary.counters["extracted_relation_count"] == 8


def test_render_failure_signal_diagnostics_are_deduped_for_summary_and_warning_count(tmp_path: Path) -> None:
    shared_warning = warning("carried_upstream_warning")
    signal = RenderFailureSignal(
        failure_reason=FailureReason.DIAGRAM_UNBUILDABLE_AFTER_RECOVERY,
        diagnostics=(
            shared_warning,
            error("render_unbuildable", FailureReason.DIAGRAM_UNBUILDABLE_AFTER_RECOVERY, OriginSeam.RENDER),
        ),
        class_count=1,
        relation_count=0,
        partial_diagram_present=True,
    )

    result = write_report(
        report_inputs(
            tmp_path,
            diagnostics=(shared_warning,),
            plantuml_text=None,
            diagram_model=None,
            render_failure_signal=signal,
        )
    )

    assert result.outcome_kind == "degraded_failure"
    assert result.command_result.summary.counters["warning_count"] == 1
    assert result.command_result.diagnostics.count(shared_warning) == 1
    assert result.stderr_text.count("warning:carried_upstream_warning: carried_upstream_warning warning") == 1
    assert "error:render_unbuildable: render_unbuildable error" in result.stderr_text


@pytest.mark.parametrize(
    ("reason", "origin_seam"),
    (
        (FailureReason.STRICT_RESOLUTION_FAILURE, OriginSeam.PARSE),
        (FailureReason.STRICT_SYNTAX_ERROR, OriginSeam.PARSE),
        (FailureReason.STRICT_WILDCARD_RESOLUTION_FAILURE, OriginSeam.TARGETS),
        (FailureReason.STRICT_DIFF_SCOPE_EXCLUSION, OriginSeam.TARGETS),
    ),
)
def test_strict_promotable_diagnostic_is_nonzero_strict_promoted_failure_without_artifact(
    tmp_path: Path,
    reason: FailureReason,
    origin_seam: OriginSeam,
) -> None:
    diagnostic = error(reason.value, reason, origin_seam)

    decision = decide_exit_policy((diagnostic,))

    assert decision.outcome_kind == "strict_promoted_failure"
    assert decision.exit_code == 1
    assert decision.failure_reason is reason
    assert decision.strict_promoted_failure_reasons == (reason,)

    result = write_report(
        report_inputs(
            tmp_path,
            diagnostics=(diagnostic,),
        )
    )

    assert result.outcome_kind == "strict_promoted_failure"
    assert result.command_result.exit_code == 1
    assert result.command_result.artifact_path is None
    assert result.command_result.summary.failure_reason is reason
    assert not (tmp_path / "pyclassuml_20260504_123456.puml").exists()
    assert result.stdout_text == ""
    assert result.stderr_text
    assert "outcome: strict_promoted_failure" in result.stderr_text
    assert f"failure_reason: {reason.value}" in result.stderr_text
    assert f"error:{reason.value}: {reason.value} error" in result.stderr_text


def test_uncategorized_error_diagnostic_is_hard_failure_without_artifact(tmp_path: Path) -> None:
    result = write_report(
        report_inputs(
            tmp_path,
            diagnostics=(error("cli_usage_error", FailureReason.CLI_USAGE_ERROR, OriginSeam.CLI),),
        )
    )

    assert result.outcome_kind == "hard_failure"
    assert result.command_result.exit_code == 1
    assert result.command_result.artifact_path is None
    assert result.command_result.summary.failure_reason is FailureReason.CLI_USAGE_ERROR
    assert not (tmp_path / "pyclassuml_20260504_123456.puml").exists()
    assert result.stdout_text == ""
    assert "failure_reason: cli_usage_error" in result.stderr_text
    assert "error:cli_usage_error: cli_usage_error error" in result.stderr_text


def test_uncategorized_error_diagnostic_precedes_render_failure_signal(tmp_path: Path) -> None:
    signal = RenderFailureSignal(
        failure_reason=FailureReason.DIAGRAM_UNBUILDABLE_AFTER_RECOVERY,
        diagnostics=(),
        class_count=2,
        relation_count=3,
        partial_diagram_present=True,
    )

    result = write_report(
        report_inputs(
            tmp_path,
            diagnostics=(error("cli_usage_error", FailureReason.CLI_USAGE_ERROR, OriginSeam.CLI),),
            plantuml_text=None,
            diagram_model=None,
            render_failure_signal=signal,
        )
    )

    assert result.outcome_kind == "hard_failure"
    assert result.command_result.exit_code == 1
    assert result.command_result.summary.failure_reason is FailureReason.CLI_USAGE_ERROR
    assert result.command_result.artifact_path is None
    assert not (tmp_path / "pyclassuml_20260504_123456.puml").exists()
    assert result.stdout_text == ""
    assert "failure_reason: cli_usage_error" in result.stderr_text
    assert "error:cli_usage_error: cli_usage_error error" in result.stderr_text


def test_hard_failure_diagnostic_precedes_strict_and_render_failure(tmp_path: Path) -> None:
    signal = RenderFailureSignal(
        failure_reason=FailureReason.DIAGRAM_UNBUILDABLE_AFTER_RECOVERY,
        diagnostics=(),
        class_count=1,
        relation_count=1,
        partial_diagram_present=True,
    )
    diagnostics = (
        error("strict_syntax_error", FailureReason.STRICT_SYNTAX_ERROR),
        error("vcs_read_failure", FailureReason.VCS_READ_FAILURE, OriginSeam.VCS),
    )

    result = write_report(
        report_inputs(tmp_path, diagnostics=diagnostics, render_failure_signal=signal)
    )

    assert result.outcome_kind == "hard_failure"
    assert result.command_result.exit_code == 1
    assert result.command_result.summary.failure_reason is FailureReason.VCS_READ_FAILURE
    assert result.command_result.artifact_path is None


def test_render_failure_signal_plus_strict_diagnostic_is_strict_promoted_failure(tmp_path: Path) -> None:
    signal = RenderFailureSignal(
        failure_reason=FailureReason.DIAGRAM_UNBUILDABLE_AFTER_RECOVERY,
        diagnostics=(),
        class_count=2,
        relation_count=3,
        partial_diagram_present=True,
    )
    result = write_report(
        report_inputs(
            tmp_path,
            diagnostics=(error("strict_syntax_error", FailureReason.STRICT_SYNTAX_ERROR),),
            plantuml_text=None,
            diagram_model=None,
            render_failure_signal=signal,
        )
    )

    assert result.outcome_kind == "strict_promoted_failure"
    assert result.command_result.exit_code == 1
    assert result.command_result.summary.failure_reason is FailureReason.STRICT_SYNTAX_ERROR
    assert result.command_result.summary.counters["extracted_class_count"] == 2


def test_output_write_failure_is_hard_failure_with_diagram_model_counters(tmp_path: Path) -> None:
    def failing_write(path: Path, text: str) -> None:
        raise OSError("disk full")

    result = write_report(report_inputs(tmp_path), write_text=failing_write)

    assert result.outcome_kind == "hard_failure"
    assert result.command_result.exit_code == 1
    assert result.command_result.artifact_path is None
    assert result.command_result.summary.failure_reason is FailureReason.OUTPUT_WRITE_FAILURE
    assert result.command_result.summary.counters["extracted_class_count"] == 2
    assert result.command_result.summary.counters["extracted_relation_count"] == 1
    assert result.stdout_text == ""
    assert "error:output_write_failure:" in result.stderr_text


def test_parent_dir_creation_failure_is_output_write_failure_with_diagram_model_counters(tmp_path: Path) -> None:
    def failing_mkdir(path: Path) -> None:
        raise OSError("permission denied")

    result = write_report(
        report_inputs(tmp_path, config=AnalysisConfig(output=Path("missing/diagram.puml"))),
        make_parent_dirs=failing_mkdir,
    )

    assert result.outcome_kind == "hard_failure"
    assert result.command_result.exit_code == 1
    assert result.command_result.artifact_path is None
    assert result.command_result.summary.failure_reason is FailureReason.OUTPUT_WRITE_FAILURE
    assert result.command_result.summary.counters["extracted_class_count"] == 2
    assert result.command_result.summary.counters["extracted_relation_count"] == 1
    assert result.stdout_text == ""
    assert "failure_reason: output_write_failure" in result.stderr_text


def test_early_hard_failure_missing_producer_sources_falls_back_to_zero_counters() -> None:
    summary = build_run_summary(
        diagnostics=(error("invalid_config", FailureReason.INVALID_CONFIG_OR_CONFIG_PATH, OriginSeam.CONFIG),),
        failure_reason=FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
    )

    assert summary.counters == {
        "seed_file_count": 0,
        "reachable_file_count": 0,
        "extracted_class_count": 0,
        "extracted_relation_count": 0,
        "changed_class_count": 0,
        "ignored_file_count": 0,
        "warning_count": 0,
        "scope_stop_count": 0,
        "diff_scope_excluded_count": 0,
    }
    assert summary.failure_reason is FailureReason.INVALID_CONFIG_OR_CONFIG_PATH


def test_write_report_success_emits_nothing_to_process_streams(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    result = write_report(report_inputs(tmp_path))

    captured = capsys.readouterr()
    assert result.command_result.exit_code == 0
    assert captured.out == ""
    assert captured.err == ""


def test_write_report_failure_emits_nothing_to_process_streams(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    result = write_report(
        report_inputs(
            tmp_path,
            diagnostics=(error("invalid_config", FailureReason.INVALID_CONFIG_OR_CONFIG_PATH, OriginSeam.CONFIG),),
        )
    )

    captured = capsys.readouterr()
    assert result.command_result.exit_code == 1
    assert captured.out == ""
    assert captured.err == ""
