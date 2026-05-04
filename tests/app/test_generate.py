from datetime import datetime
from pathlib import Path

import pytest

import pyclassuml.app.generate as generate_app
from pyclassuml.app import run_generate
from pyclassuml.model import (
    ChangedClassInventory,
    CommandName,
    CommandOptions,
    CommandRequest,
    DiffCurrentState,
    DiffOptions,
    FailureReason,
    GenerateOptions,
)
from pyclassuml.report import ReportInputs


TIMESTAMP = datetime(2026, 5, 4, 12, 34, 56)


def write_file(path: Path, text: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def generate_request(process_cwd: Path, targets: tuple[Path | str, ...], **overrides: object) -> CommandRequest:
    kwargs: dict[str, object] = {
        "command": CommandName.GENERATE,
        "generate": GenerateOptions(targets=targets),
    }
    kwargs.update(overrides)
    return CommandRequest(
        process_cwd=process_cwd,
        cli_options=CommandOptions(**kwargs),
    )


def diff_request(process_cwd: Path) -> CommandRequest:
    return CommandRequest(
        process_cwd=process_cwd,
        cli_options=CommandOptions(
            command=CommandName.DIFF,
            diff=DiffOptions(
                base_ref="main",
                current_state=DiffCurrentState.WORKING_TREE,
                include_untracked=False,
            ),
        ),
    )


def fail_if_called(stage_name: str):
    def fail(*args: object, **kwargs: object) -> object:
        raise AssertionError(f"{stage_name} should not be called")

    return fail


def test_non_generate_request_raises_value_error() -> None:
    with pytest.raises(ValueError, match="generate command request"):
        run_generate(diff_request(Path("/repo")), timestamp=TIMESTAMP)


def test_config_failure_returns_report_nonzero_without_downstream_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(generate_app, "normalize_explicit_targets", fail_if_called("targets"))
    monkeypatch.setattr(generate_app, "parse_target_set", fail_if_called("parse"))
    monkeypatch.setattr(generate_app, "render_uml_document", fail_if_called("render"))

    result = run_generate(
        generate_request(tmp_path, ("pkg/a.py",), config=Path("missing.toml")),
        timestamp=TIMESTAMP,
    )

    assert result.outcome_kind == "hard_failure"
    assert result.command_result.exit_code == 1
    assert result.command_result.artifact_path is None
    assert result.command_result.summary.failure_reason is FailureReason.INVALID_CONFIG_OR_CONFIG_PATH
    assert result.stdout_text == ""
    assert "failure_reason: invalid_config_or_config_path" in result.stderr_text
    assert "error:invalid_config_path:" in result.stderr_text
    assert not list(tmp_path.glob("*.puml"))


def test_zero_target_failure_returns_report_nonzero_without_common_pipeline_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(generate_app, "parse_target_set", fail_if_called("parse"))
    monkeypatch.setattr(generate_app, "traverse_dependencies", fail_if_called("traversal"))
    monkeypatch.setattr(generate_app, "render_uml_document", fail_if_called("render"))

    result = run_generate(
        generate_request(tmp_path, ("missing.py",)),
        timestamp=TIMESTAMP,
    )

    assert result.outcome_kind == "hard_failure"
    assert result.command_result.exit_code == 1
    assert result.command_result.artifact_path is None
    assert result.command_result.summary.failure_reason is FailureReason.GENERATE_ZERO_TARGET_AFTER_NORMALIZE
    assert result.stdout_text == ""
    assert "failure_reason: generate_zero_target_after_normalize" in result.stderr_text
    assert "error:generate_zero_target_after_normalize:" in result.stderr_text
    assert not list(tmp_path.glob("*.puml"))


def test_happy_path_writes_artifact_summary_and_does_not_emit_streams(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_file(
        tmp_path / "pkg" / "model.py",
        "class User:\n    pass\n",
    )

    result = run_generate(
        generate_request(tmp_path, ("pkg/model.py",), output=Path("diagram.puml")),
        timestamp=TIMESTAMP,
    )
    captured = capsys.readouterr()

    assert result.outcome_kind == "clean_success"
    assert result.command_result.exit_code == 0
    assert result.command_result.artifact_path == tmp_path / "diagram.puml"
    assert (tmp_path / "diagram.puml").read_text(encoding="utf-8").startswith("@startuml\n")
    assert "outcome: clean_success" in result.stdout_text
    assert "changed_class_count: 0" in result.stdout_text
    assert result.stderr_text == ""
    assert captured.out == ""
    assert captured.err == ""


def test_zero_changed_inventory_is_built_from_empty_context_and_handed_to_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_file(tmp_path / "pkg" / "model.py", "class User:\n    pass\n")
    sentinel_inventory = ChangedClassInventory(class_count=0, changed_files=())
    calls: dict[str, object] = {}
    original_write_report = generate_app.write_report

    def build_changed_class_inventory_spy(
        changed_files: object,
        parsed_modules: object,
        module_index: object,
    ) -> ChangedClassInventory:
        calls["changed_files"] = changed_files
        calls["parsed_modules"] = parsed_modules
        calls["module_index"] = module_index
        return sentinel_inventory

    def write_report_spy(inputs: ReportInputs):
        calls["report_inputs"] = inputs
        return original_write_report(inputs)

    monkeypatch.setattr(generate_app, "build_changed_class_inventory", build_changed_class_inventory_spy)
    monkeypatch.setattr(generate_app, "write_report", write_report_spy)

    result = run_generate(
        generate_request(tmp_path, ("pkg/model.py",), output=Path("diagram.puml")),
        timestamp=TIMESTAMP,
    )

    report_inputs = calls["report_inputs"]
    assert result.outcome_kind == "clean_success"
    assert calls["changed_files"] == ()
    assert tuple(calls["parsed_modules"])
    assert calls["module_index"] is not None
    assert isinstance(report_inputs, ReportInputs)
    assert report_inputs.changed_class_inventory is sentinel_inventory


def test_scope_stop_count_from_traversal_observations_is_handed_to_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_file(
        tmp_path / "pkg" / "app" / "model.py",
        "from pkg import shared\n\nclass User:\n    pass\n",
    )
    write_file(tmp_path / "pkg" / "shared.py", "class Shared:\n    pass\n")
    calls: dict[str, object] = {}
    original_write_report = generate_app.write_report

    def write_report_spy(inputs: ReportInputs):
        calls["report_inputs"] = inputs
        return original_write_report(inputs)

    monkeypatch.setattr(generate_app, "write_report", write_report_spy)

    result = run_generate(
        generate_request(
            tmp_path,
            ("pkg/app/model.py",),
            package_root=Path("pkg"),
            scope_root=Path("pkg/app"),
            output=Path("scope-stop.puml"),
        ),
        timestamp=TIMESTAMP,
    )

    report_inputs = calls["report_inputs"]
    assert result.outcome_kind == "clean_success"
    assert isinstance(report_inputs, ReportInputs)
    assert report_inputs.scope_stop_count == 1


def test_output_unspecified_uses_caller_timestamp_for_auto_named_artifact(tmp_path: Path) -> None:
    write_file(tmp_path / "pkg" / "model.py", "class User:\n    pass\n")

    result = run_generate(
        generate_request(tmp_path, ("pkg/model.py",)),
        timestamp=TIMESTAMP,
    )

    artifact_path = tmp_path / "pyclassuml_20260504_123456.puml"
    assert result.outcome_kind == "clean_success"
    assert result.command_result.artifact_path == artifact_path
    assert artifact_path.read_text(encoding="utf-8").startswith("@startuml\n")


def test_ignored_target_observation_and_warning_diagnostic_are_reported_without_process_streams(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_file(
        tmp_path / "pkg" / "model.py",
        'class User(BaseModel):\n    friend: "Missing"\n',
    )
    write_file(tmp_path / "pkg" / "ignored.py", "class Ignored:\n    pass\n")

    result = run_generate(
        generate_request(
            tmp_path,
            ("pkg/**/*.py",),
            ignore=("pkg/ignored.py",),
            output=Path("warning.puml"),
        ),
        timestamp=TIMESTAMP,
    )
    captured = capsys.readouterr()

    assert result.outcome_kind == "degraded_success"
    assert result.command_result.exit_code == 0
    assert result.command_result.artifact_path == tmp_path / "warning.puml"
    assert result.stderr_text == ""
    assert "ignored_file_count: 1" in result.stdout_text
    assert "warning_count: 1" in result.stdout_text
    assert "warning:pydantic_forward_ref_unresolved:" in result.stdout_text
    assert captured.out == ""
    assert captured.err == ""


def test_render_failure_is_report_owned_nonzero_result_without_process_streams(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write_file(tmp_path / "pkg" / "empty.py", "VALUE = 1\n")

    result = run_generate(
        generate_request(tmp_path, ("pkg/empty.py",), output=Path("empty.puml")),
        timestamp=TIMESTAMP,
    )
    captured = capsys.readouterr()

    assert result.outcome_kind == "degraded_failure"
    assert result.command_result.exit_code == 1
    assert result.command_result.artifact_path is None
    assert result.command_result.summary.failure_reason is FailureReason.DIAGRAM_UNBUILDABLE_AFTER_RECOVERY
    assert result.stdout_text == ""
    assert "failure_reason: diagram_unbuildable_after_recovery" in result.stderr_text
    assert not (tmp_path / "empty.puml").exists()
    assert captured.out == ""
    assert captured.err == ""


def test_output_write_failure_preserves_report_owned_nonzero_result(tmp_path: Path) -> None:
    write_file(tmp_path / "pkg" / "model.py", "class User:\n    pass\n")
    write_file(tmp_path / "blocked", "not a directory\n")

    result = run_generate(
        generate_request(tmp_path, ("pkg/model.py",), output=Path("blocked/diagram.puml")),
        timestamp=TIMESTAMP,
    )

    assert result.outcome_kind == "hard_failure"
    assert result.command_result.exit_code == 1
    assert result.command_result.artifact_path is None
    assert result.command_result.summary.failure_reason is FailureReason.OUTPUT_WRITE_FAILURE
    assert result.stdout_text == ""
    assert "failure_reason: output_write_failure" in result.stderr_text
    assert "error:output_write_failure:" in result.stderr_text
