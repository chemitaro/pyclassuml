from datetime import datetime
from pathlib import Path
import re
import subprocess

import pytest

import pyclassuml.app.diff as diff_app
from pyclassuml.app import run_diff
from pyclassuml.model import (
    ChangedClassInventory,
    ClassSpan,
    CommandName,
    CommandOptions,
    CommandRequest,
    DiffCurrentState,
    DiffOptions,
    FailureReason,
    GenerateOptions,
    ParsedModule,
    SelectedClasses,
)
from pyclassuml.parse import ModuleIndex
from pyclassuml.report import ReportInputs
from pyclassuml.vcs import ChangedFileEntry, ChangedLineRange


TIMESTAMP = datetime(2026, 5, 4, 12, 34, 56)


def class_alias(plantuml_text: str, class_name: str) -> str:
    match = re.search(rf'^\s*class "{re.escape(class_name)}" as (c\d+)', plantuml_text, re.MULTILINE)
    assert match is not None, f"missing alias declaration for {class_name}"
    return match.group(1)


def assert_relation(plantuml_text: str, source_name: str, arrow: str, target_name: str) -> None:
    source_alias = class_alias(plantuml_text, source_name)
    target_alias = class_alias(plantuml_text, target_name)
    assert f"{source_alias} {arrow} {target_alias}" in plantuml_text


def class_declaration(plantuml_text: str, class_name: str) -> str:
    match = re.search(rf'^\s*class "{re.escape(class_name)}" as c\d+(?: .*)?$', plantuml_text, re.MULTILINE)
    assert match is not None, f"missing class declaration for {class_name}"
    return match.group(0)


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", "-C", str(repo), *args),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def write_file(path: Path, text: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def init_repo(path: Path) -> Path:
    path.mkdir()
    subprocess.run(("git", "init", str(path)), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    git(path, "config", "user.name", "pyclassuml test")
    git(path, "config", "user.email", "pyclassuml@example.test")
    return path


def commit_all(repo: Path, message: str) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message)


def tag_base(repo: Path) -> str:
    git(repo, "tag", "base")
    return "base"


def diff_request(
    process_cwd: Path,
    *,
    base_ref: str = "base",
    current_state: DiffCurrentState = DiffCurrentState.WORKING_TREE,
    include_untracked: bool = False,
    **overrides: object,
) -> CommandRequest:
    kwargs: dict[str, object] = {
        "command": CommandName.DIFF,
        "diff": DiffOptions(
            base_ref=base_ref,
            current_state=current_state,
            include_untracked=include_untracked,
        ),
    }
    kwargs.update(overrides)
    return CommandRequest(
        process_cwd=process_cwd,
        cli_options=CommandOptions(**kwargs),
    )


def generate_request(process_cwd: Path) -> CommandRequest:
    return CommandRequest(
        process_cwd=process_cwd,
        cli_options=CommandOptions(
            command=CommandName.GENERATE,
            generate=GenerateOptions(targets=("pkg/a.py",)),
        ),
    )


def fail_if_called(stage_name: str):
    def fail(*args: object, **kwargs: object) -> object:
        raise AssertionError(f"{stage_name} should not be called")

    return fail


def test_non_diff_request_raises_value_error() -> None:
    with pytest.raises(ValueError, match="diff command request"):
        run_diff(generate_request(Path("/repo")), timestamp=TIMESTAMP)


def test_config_failure_returns_report_nonzero_without_downstream_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(diff_app, "collect_diff_files", fail_if_called("vcs"))
    monkeypatch.setattr(diff_app, "normalize_diff_targets", fail_if_called("targets"))
    monkeypatch.setattr(diff_app, "parse_target_set", fail_if_called("parse"))

    result = run_diff(
        diff_request(tmp_path, config=Path("missing.toml")),
        timestamp=TIMESTAMP,
    )
    captured = capsys.readouterr()

    assert result.outcome_kind == "hard_failure"
    assert result.command_result.exit_code == 1
    assert result.command_result.artifact_path is None
    assert result.command_result.summary.failure_reason is FailureReason.INVALID_CONFIG_OR_CONFIG_PATH
    assert result.stdout_text == ""
    assert "failure_reason: invalid_config_or_config_path" in result.stderr_text
    assert "error:invalid_config_path:" in result.stderr_text
    assert captured.out == ""
    assert captured.err == ""
    assert not list(tmp_path.glob("*.puml"))


def test_vcs_failure_returns_report_nonzero_without_target_or_common_pipeline_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(diff_app, "normalize_diff_targets", fail_if_called("targets"))
    monkeypatch.setattr(diff_app, "parse_target_set", fail_if_called("parse"))
    monkeypatch.setattr(diff_app, "render_uml_document", fail_if_called("render"))

    result = run_diff(diff_request(project), timestamp=TIMESTAMP)
    captured = capsys.readouterr()

    assert result.outcome_kind == "hard_failure"
    assert result.command_result.exit_code == 1
    assert result.command_result.artifact_path is None
    assert result.command_result.summary.failure_reason is FailureReason.VCS_READ_FAILURE
    assert result.stdout_text == ""
    assert "failure_reason: vcs_read_failure" in result.stderr_text
    assert "error:git_diff_read_failure:" in result.stderr_text
    assert captured.out == ""
    assert captured.err == ""
    assert not list(project.glob("*.puml"))


def test_invalid_base_ref_returns_report_nonzero_without_target_or_common_pipeline_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "model.py", "class User:\n    pass\n")
    commit_all(repo, "base")
    monkeypatch.setattr(diff_app, "normalize_diff_targets", fail_if_called("targets"))
    monkeypatch.setattr(diff_app, "parse_target_set", fail_if_called("parse"))
    monkeypatch.setattr(diff_app, "traverse_dependencies", fail_if_called("traversal"))
    monkeypatch.setattr(diff_app, "render_uml_document", fail_if_called("render"))

    result = run_diff(
        diff_request(repo, base_ref="missing-ref"),
        timestamp=TIMESTAMP,
    )
    captured = capsys.readouterr()

    assert result.outcome_kind == "hard_failure"
    assert result.command_result.exit_code == 1
    assert result.command_result.artifact_path is None
    assert result.command_result.summary.failure_reason is FailureReason.VCS_READ_FAILURE
    assert result.stdout_text == ""
    assert "failure_reason: vcs_read_failure" in result.stderr_text
    assert "error:invalid_base_ref:" in result.stderr_text
    assert result.command_result.diagnostics[0].code == "invalid_base_ref"
    assert result.command_result.diagnostics[0].failure_reason is FailureReason.VCS_READ_FAILURE
    assert captured.out == ""
    assert captured.err == ""
    assert not list(repo.glob("*.puml"))


def test_zero_target_failure_returns_report_nonzero_without_common_pipeline_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "README.md", "base\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "README.md", "changed\n")
    monkeypatch.setattr(diff_app, "parse_target_set", fail_if_called("parse"))
    monkeypatch.setattr(diff_app, "traverse_dependencies", fail_if_called("traversal"))
    monkeypatch.setattr(diff_app, "render_uml_document", fail_if_called("render"))

    result = run_diff(diff_request(repo), timestamp=TIMESTAMP)
    captured = capsys.readouterr()

    assert result.outcome_kind == "hard_failure"
    assert result.command_result.exit_code == 1
    assert result.command_result.artifact_path is None
    assert result.command_result.summary.failure_reason is FailureReason.DIFF_ZERO_TARGET_AFTER_SCOPE_FILTER
    assert result.stdout_text == ""
    assert "failure_reason: diff_zero_target_after_scope_filter" in result.stderr_text
    assert "error:diff_zero_target_after_scope_filter:" in result.stderr_text
    assert captured.out == ""
    assert captured.err == ""
    assert not list(repo.glob("*.puml"))


def test_diff_post_target_stage_invocation_order_is_canonical(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "model.py", "class User:\n    pass\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "model.py", "class User:\n    value = 1\n")
    calls: list[str] = []
    original_parse = diff_app.parse_target_set
    original_traversal = diff_app.traverse_dependencies
    original_selection = diff_app.select_classes_and_relations
    original_inventory = diff_app.build_changed_class_inventory
    original_sqlalchemy = diff_app.extract_sqlalchemy_enrichment_hints
    original_pydantic = diff_app.extract_pydantic_enrichment_hints
    original_render = diff_app.render_uml_document
    original_report = diff_app.write_report

    def parse_spy(*args: object, **kwargs: object):
        calls.append("parse")
        return original_parse(*args, **kwargs)

    def traversal_spy(*args: object, **kwargs: object):
        calls.append("traversal")
        return original_traversal(*args, **kwargs)

    def selection_spy(*args: object, **kwargs: object):
        calls.append("selection")
        return original_selection(*args, **kwargs)

    def inventory_spy(*args: object, **kwargs: object):
        calls.append("changed_inventory")
        return original_inventory(*args, **kwargs)

    def sqlalchemy_spy(*args: object, **kwargs: object):
        calls.append("sqlalchemy")
        return original_sqlalchemy(*args, **kwargs)

    def pydantic_spy(*args: object, **kwargs: object):
        calls.append("pydantic")
        return original_pydantic(*args, **kwargs)

    def render_spy(*args: object, **kwargs: object):
        calls.append("render")
        return original_render(*args, **kwargs)

    def report_spy(*args: object, **kwargs: object):
        calls.append("report")
        return original_report(*args, **kwargs)

    monkeypatch.setattr(diff_app, "parse_target_set", parse_spy)
    monkeypatch.setattr(diff_app, "traverse_dependencies", traversal_spy)
    monkeypatch.setattr(diff_app, "select_classes_and_relations", selection_spy)
    monkeypatch.setattr(diff_app, "build_changed_class_inventory", inventory_spy)
    monkeypatch.setattr(diff_app, "extract_sqlalchemy_enrichment_hints", sqlalchemy_spy)
    monkeypatch.setattr(diff_app, "extract_pydantic_enrichment_hints", pydantic_spy)
    monkeypatch.setattr(diff_app, "render_uml_document", render_spy)
    monkeypatch.setattr(diff_app, "write_report", report_spy)

    result = run_diff(
        diff_request(repo, output=Path("order.puml")),
        timestamp=TIMESTAMP,
    )

    assert result.outcome_kind == "clean_success"
    assert calls == [
        "parse",
        "traversal",
        "selection",
        "changed_inventory",
        "sqlalchemy",
        "pydantic",
        "render",
        "report",
    ]


def test_happy_path_writes_artifact_summary_and_does_not_emit_process_streams(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "model.py", "class User:\n    pass\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "model.py", "class User:\n    value = 1\n")

    result = run_diff(
        diff_request(repo, output=Path("diagram.puml")),
        timestamp=TIMESTAMP,
    )
    captured = capsys.readouterr()

    assert result.outcome_kind == "clean_success"
    assert result.command_result.exit_code == 0
    assert result.command_result.artifact_path == repo / "diagram.puml"
    assert (repo / "diagram.puml").read_text(encoding="utf-8").startswith("@startuml\n")
    assert "outcome: clean_success" in result.stdout_text
    assert "seed_file_count: 1" in result.stdout_text
    assert "changed_class_count: 1" in result.stdout_text
    assert result.stderr_text == ""
    assert captured.out == ""
    assert captured.err == ""


def test_diff_member_rendering_e2e_covers_changed_class_body_and_alias_relations(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(
        repo / "pkg" / "checkout.py",
        "\n".join(
            [
                "class CheckoutSnapshot:",
                "    request_id: str",
            ]
        ),
    )
    commit_all(repo, "base")
    tag_base(repo)
    write_file(
        repo / "pkg" / "checkout.py",
        "\n".join(
            [
                "class CheckoutSnapshot:",
                "    request_id: str",
                '    order: "Order"',
                "",
                '    def submit(self, order: "Order") -> "Receipt":',
                "        return Receipt()",
                "",
                "class Order:",
                "    order_id: str",
                "",
                "class Receipt:",
                "    receipt_id: str",
            ]
        ),
    )

    result = run_diff(
        diff_request(repo, output=Path("member-diff.puml")),
        timestamp=TIMESTAMP,
    )

    output = (repo / "member-diff.puml").read_text(encoding="utf-8")
    assert result.outcome_kind == "clean_success"
    assert result.command_result.exit_code == 0
    assert 'class "CheckoutSnapshot" as ' in output
    assert 'class "Order" as ' in output
    assert 'class "Receipt" as ' in output
    assert "+ request_id: str" in output
    assert "+ order: 'Order'" in output
    assert "+ submit(order: 'Order'): 'Receipt'" in output
    assert_relation(output, "CheckoutSnapshot", "*--", "Order")
    assert_relation(output, "CheckoutSnapshot", "..>", "Receipt")
    assert "seed_file_count: 1" in result.stdout_text
    assert "changed_class_count: 3" in result.stdout_text


def test_diff_e2e_marks_changed_class_and_dependency_only_class(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "__init__.py")
    write_file(repo / "pkg" / "customer.py", "class Customer:\n    customer_id: str\n")
    write_file(
        repo / "pkg" / "order.py",
        "\n".join(
            [
                "from pkg.customer import Customer",
                "",
                "class Order:",
                "    customer: Customer",
            ]
        ),
    )
    commit_all(repo, "base")
    tag_base(repo)
    write_file(
        repo / "pkg" / "order.py",
        "\n".join(
            [
                "from pkg.customer import Customer",
                "",
                "class Order:",
                "    customer: Customer",
                "    status: str",
            ]
        ),
    )

    result = run_diff(
        diff_request(repo, output=Path("colorized.puml")),
        timestamp=TIMESTAMP,
    )

    output = (repo / "colorized.puml").read_text(encoding="utf-8")
    assert result.outcome_kind == "clean_success"
    assert result.command_result.summary.counters["changed_class_count"] == 1
    assert "skinparam class {" in output
    assert "<<DiffChanged>>" in class_declaration(output, "Order")
    assert "DiffDependency" not in output
    assert "DiffChanged" not in class_declaration(output, "Customer")
    assert_relation(output, "Order", "*--", "Customer")


def test_diff_colorization_coexists_with_relation_notation_regression_fixture(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(
        repo / "pkg" / "model.py",
        "\n".join(
            [
                "from typing import Protocol",
                "",
                "class Base:",
                "    pass",
                "",
                "class Address:",
                "    pass",
                "",
                "class Line:",
                "    pass",
                "",
                "class Receipt:",
                "    pass",
                "",
                "class Gateway(Protocol):",
                "    def authorize(self, request: 'Checkout') -> Receipt:",
                "        ...",
                "",
                "class SqlGateway(Gateway):",
                "    pass",
                "",
                "class Checkout(Base):",
                "    address: Address",
                "    lines: list[Line]",
                "    def submit(self) -> Receipt:",
                "        return Receipt()",
            ]
        ),
    )
    commit_all(repo, "base")
    tag_base(repo)
    write_file(
        repo / "pkg" / "model.py",
        (repo / "pkg" / "model.py").read_text(encoding="utf-8").replace(
            "        ...",
            "        return Receipt()",
        ),
    )

    result = run_diff(
        diff_request(repo, output=Path("relations.puml")),
        timestamp=TIMESTAMP,
    )

    output = (repo / "relations.puml").read_text(encoding="utf-8")
    assert result.outcome_kind == "clean_success"
    assert "<<DiffChanged>>" in output
    assert "<<DiffChanged>> <<Protocol>>" in class_declaration(output, "Gateway")
    assert_relation(output, "Checkout", "-up-|>", "Base")
    assert_relation(output, "Checkout", "*--", "Address")
    assert_relation(output, "Checkout", "o--", "Line")
    assert_relation(output, "Checkout", "..>", "Receipt")
    assert_relation(output, "Gateway", "..>", "Checkout")
    assert_relation(output, "Gateway", "..>", "Receipt")
    assert_relation(output, "SqlGateway", "..up|>", "Gateway")
    assert "*-->" not in output
    assert "o-->" not in output


def test_diff_colorized_output_is_deterministic(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "__init__.py")
    write_file(repo / "pkg" / "dependency.py", "class Dependency:\n    pass\n")
    write_file(repo / "pkg" / "changed.py", "from pkg.dependency import Dependency\n\nclass Changed:\n    item: Dependency\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(
        repo / "pkg" / "changed.py",
        "from pkg.dependency import Dependency\n\nclass Changed:\n    item: Dependency\n    flag: bool\n",
    )

    first = run_diff(diff_request(repo, output=Path("first.puml")), timestamp=TIMESTAMP)
    second = run_diff(diff_request(repo, output=Path("second.puml")), timestamp=TIMESTAMP)

    assert first.outcome_kind == "clean_success"
    assert second.outcome_kind == "clean_success"
    assert (repo / "first.puml").read_text(encoding="utf-8") == (repo / "second.puml").read_text(encoding="utf-8")


def test_diff_e2e_marks_only_class_whose_body_overlaps_changed_hunk(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "__init__.py")
    write_file(
        repo / "pkg" / "models.py",
        "\n".join(
            [
                "class Unchanged:",
                "    value = 1",
                "",
                "class Changed:",
                "    value = 1",
                "",
            ]
        ),
    )
    commit_all(repo, "base")
    tag_base(repo)
    write_file(
        repo / "pkg" / "models.py",
        "\n".join(
            [
                "class Unchanged:",
                "    value = 1",
                "",
                "class Changed:",
                "    value = 2",
                "",
            ]
        ),
    )

    result = run_diff(diff_request(repo, output=Path("models.puml")), timestamp=TIMESTAMP)

    output = (repo / "models.puml").read_text(encoding="utf-8")
    assert result.outcome_kind == "clean_success"
    assert result.command_result.summary.counters["changed_class_count"] == 2
    assert "<<DiffChanged>>" in class_declaration(output, "Changed")
    assert "DiffChanged" not in class_declaration(output, "Unchanged")


def test_diff_e2e_marks_nested_inner_body_change_without_outer_highlight(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "__init__.py")
    write_file(
        repo / "pkg" / "models.py",
        "\n".join(
            [
                "class Outer:",
                "    outer_value = 1",
                "",
                "    class Inner:",
                "        value = 1",
                "",
            ]
        ),
    )
    commit_all(repo, "base")
    tag_base(repo)
    write_file(
        repo / "pkg" / "models.py",
        "\n".join(
            [
                "class Outer:",
                "    outer_value = 1",
                "",
                "    class Inner:",
                "        value = 2",
                "",
            ]
        ),
    )

    result = run_diff(diff_request(repo, output=Path("nested.puml")), timestamp=TIMESTAMP)

    output = (repo / "nested.puml").read_text(encoding="utf-8")
    assert result.outcome_kind == "clean_success"
    assert "<<DiffChanged>>" in class_declaration(output, "Inner")
    assert "DiffChanged" not in class_declaration(output, "Outer")


def test_diff_e2e_marks_class_body_deletion_only_hunk_as_changed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "__init__.py")
    write_file(repo / "pkg" / "models.py", "class Model:\n    value = 1\n    removed = True\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "models.py", "class Model:\n    value = 1\n")

    result = run_diff(diff_request(repo, output=Path("body-deletion.puml")), timestamp=TIMESTAMP)

    output = (repo / "body-deletion.puml").read_text(encoding="utf-8")
    assert result.outcome_kind == "clean_success"
    assert result.command_result.summary.counters["changed_class_count"] == 1
    assert "skinparam class {" in output
    assert "<<DiffChanged>>" in class_declaration(output, "Model")


def test_diff_e2e_module_level_only_change_does_not_emit_diff_changed_style(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "__init__.py")
    write_file(
        repo / "pkg" / "settings.py",
        "\n".join(
            [
                "VALUE = 1",
                "",
                "class Settings:",
                "    name = 'default'",
                "",
            ]
        ),
    )
    commit_all(repo, "base")
    tag_base(repo)
    write_file(
        repo / "pkg" / "settings.py",
        "\n".join(
            [
                "VALUE = 2",
                "",
                "class Settings:",
                "    name = 'default'",
                "",
            ]
        ),
    )

    result = run_diff(diff_request(repo, output=Path("settings.puml")), timestamp=TIMESTAMP)

    output = (repo / "settings.puml").read_text(encoding="utf-8")
    assert result.outcome_kind == "clean_success"
    assert result.command_result.summary.counters["changed_class_count"] == 1
    assert "DiffChanged" not in class_declaration(output, "Settings")
    assert "skinparam class" not in output


def test_diff_e2e_module_level_deletion_only_hunk_does_not_emit_diff_changed_style(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "__init__.py")
    write_file(
        repo / "pkg" / "settings.py",
        "\n".join(
            [
                "VALUE = 1",
                "",
                "class Settings:",
                "    name = 'default'",
                "",
            ]
        ),
    )
    commit_all(repo, "base")
    tag_base(repo)
    write_file(
        repo / "pkg" / "settings.py",
        "\n".join(
            [
                "class Settings:",
                "    name = 'default'",
                "",
            ]
        ),
    )

    result = run_diff(diff_request(repo, output=Path("settings-deletion.puml")), timestamp=TIMESTAMP)

    output = (repo / "settings-deletion.puml").read_text(encoding="utf-8")
    assert result.outcome_kind == "clean_success"
    assert result.command_result.summary.counters["changed_class_count"] == 1
    assert "DiffChanged" not in class_declaration(output, "Settings")
    assert "skinparam class" not in output


def test_diff_e2e_indented_module_level_deletion_after_class_does_not_emit_diff_changed_style(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "__init__.py")
    write_file(repo / "pkg" / "models.py", "class Model:\n    value = 1\n\nVALUES = [\n    1,\n]\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "models.py", "class Model:\n    value = 1\n")

    result = run_diff(diff_request(repo, output=Path("module-deletion-after-class.puml")), timestamp=TIMESTAMP)

    output = (repo / "module-deletion-after-class.puml").read_text(encoding="utf-8")
    assert result.outcome_kind == "clean_success"
    assert result.command_result.summary.counters["changed_class_count"] == 1
    assert "DiffChanged" not in class_declaration(output, "Model")
    assert "skinparam class" not in output


def test_diff_e2e_marks_decorator_only_class_change_as_diff_changed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "__init__.py")
    write_file(repo / "pkg" / "models.py", "class Model:\n    value = 1\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "models.py", "@entity\nclass Model:\n    value = 1\n")

    result = run_diff(diff_request(repo, output=Path("decorator-change.puml")), timestamp=TIMESTAMP)

    output = (repo / "decorator-change.puml").read_text(encoding="utf-8")
    assert result.outcome_kind == "clean_success"
    assert result.command_result.summary.counters["changed_class_count"] == 1
    assert "<<DiffChanged>>" in class_declaration(output, "Model")


def test_diff_e2e_marks_decorator_only_class_removal_as_diff_changed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "__init__.py")
    write_file(repo / "pkg" / "models.py", "@entity\nclass Model:\n    value = 1\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "models.py", "class Model:\n    value = 1\n")

    result = run_diff(diff_request(repo, output=Path("decorator-removal.puml")), timestamp=TIMESTAMP)

    output = (repo / "decorator-removal.puml").read_text(encoding="utf-8")
    assert result.outcome_kind == "clean_success"
    assert result.command_result.summary.counters["changed_class_count"] == 1
    assert "<<DiffChanged>>" in class_declaration(output, "Model")


def test_diff_e2e_does_not_attach_function_decorator_removal_to_following_class(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "__init__.py")
    write_file(
        repo / "pkg" / "models.py",
        "\n".join(
            [
                "@trace",
                "def helper(): return 1",
                "class Model:",
                "    value = 1",
                "",
            ]
        ),
    )
    commit_all(repo, "base")
    tag_base(repo)
    write_file(
        repo / "pkg" / "models.py",
        "\n".join(
            [
                "def helper(): return 1",
                "class Model:",
                "    value = 1",
                "",
            ]
        ),
    )

    result = run_diff(diff_request(repo, output=Path("function-decorator-removal.puml")), timestamp=TIMESTAMP)

    output = (repo / "function-decorator-removal.puml").read_text(encoding="utf-8")
    assert result.outcome_kind == "clean_success"
    assert "DiffChanged" not in class_declaration(output, "Model")
    assert "skinparam class" not in output


def test_diff_e2e_does_not_attach_deleted_decorated_helper_to_class_moved_to_file_start(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "__init__.py")
    write_file(
        repo / "pkg" / "models.py",
        "\n".join(
            [
                "@trace",
                "def helper():",
                "    return 1",
                "",
                "class Model:",
                "    value = 1",
                "",
            ]
        ),
    )
    commit_all(repo, "base")
    tag_base(repo)
    write_file(
        repo / "pkg" / "models.py",
        "\n".join(
            [
                "class Model:",
                "    value = 1",
                "",
            ]
        ),
    )

    result = run_diff(diff_request(repo, output=Path("deleted-helper.puml")), timestamp=TIMESTAMP)

    output = (repo / "deleted-helper.puml").read_text(encoding="utf-8")
    assert result.outcome_kind == "clean_success"
    assert "DiffChanged" not in class_declaration(output, "Model")
    assert "skinparam class" not in output


def test_diff_class_decorations_excludes_unselected_changed_classes() -> None:
    selected_id = "pkg/selected.py:Selected"
    hidden_id = "pkg/hidden.py:Hidden"
    decorations = diff_app._diff_class_decorations(
        (ChangedFileEntry("pkg/hidden.py", "added"),),
        (
            ParsedModule(Path("pkg/selected.py"), classes=(selected_id,)),
            ParsedModule(Path("pkg/hidden.py"), classes=(hidden_id,)),
        ),
        ModuleIndex(
            module_by_path={},
            project_relative_file_to_module={
                Path("pkg/selected.py"): Path("pkg/selected.py"),
                Path("pkg/hidden.py"): Path("pkg/hidden.py"),
            },
            class_to_module={
                selected_id: Path("pkg/selected.py"),
                hidden_id: Path("pkg/hidden.py"),
            },
            seed_project_relative_paths=(),
            import_candidate_paths={},
        ),
        SelectedClasses(class_ids=(selected_id,)),
    )

    assert decorations == ()


def test_diff_class_decorations_marks_only_selected_class_with_overlapping_changed_range() -> None:
    changed_id = "pkg/models.py:Changed"
    unchanged_id = "pkg/models.py:Unchanged"
    decorations = diff_app._diff_class_decorations(
        (
            ChangedFileEntry(
                "pkg/models.py",
                "modified",
                current_changed_line_ranges=(ChangedLineRange(start=6, end=6),),
            ),
        ),
        (
            ParsedModule(
                Path("pkg/models.py"),
                classes=(changed_id, unchanged_id),
                class_spans=(
                    ClassSpan(unchanged_id, start_line=1, end_line=2),
                    ClassSpan(changed_id, start_line=4, end_line=6),
                ),
            ),
        ),
        ModuleIndex(
            module_by_path={},
            project_relative_file_to_module={Path("pkg/models.py"): Path("pkg/models.py")},
            class_to_module={
                changed_id: Path("pkg/models.py"),
                unchanged_id: Path("pkg/models.py"),
            },
            seed_project_relative_paths=(),
            import_candidate_paths={},
        ),
        SelectedClasses(class_ids=(changed_id, unchanged_id)),
    )

    assert decorations == ((changed_id, "DiffChanged"),)


def test_diff_class_decorations_prefers_innermost_nested_class_for_changed_range() -> None:
    outer_id = "pkg/models.py:Outer"
    inner_id = "pkg/models.py:Outer.Inner"
    decorations = diff_app._diff_class_decorations(
        (
            ChangedFileEntry(
                "pkg/models.py",
                "modified",
                current_changed_line_ranges=(ChangedLineRange(start=5, end=5),),
            ),
        ),
        (
            ParsedModule(
                Path("pkg/models.py"),
                classes=(outer_id, inner_id),
                class_spans=(
                    ClassSpan(outer_id, start_line=1, end_line=5),
                    ClassSpan(inner_id, start_line=4, end_line=5),
                ),
            ),
        ),
        ModuleIndex(
            module_by_path={},
            project_relative_file_to_module={Path("pkg/models.py"): Path("pkg/models.py")},
            class_to_module={
                outer_id: Path("pkg/models.py"),
                inner_id: Path("pkg/models.py"),
            },
            seed_project_relative_paths=(),
            import_candidate_paths={},
        ),
        SelectedClasses(class_ids=(outer_id, inner_id)),
    )

    assert decorations == ((inner_id, "DiffChanged"),)


def test_diff_class_decorations_does_not_attach_function_decorator_deletion_to_following_class() -> None:
    model_id = "pkg/models.py:Model"
    decorations = diff_app._diff_class_decorations(
        (
            ChangedFileEntry(
                "pkg/models.py",
                "modified",
                current_changed_line_ranges=(
                    ChangedLineRange(
                        start=1,
                        end=1,
                        is_deletion_only=True,
                        deleted_lines=("@trace",),
                        is_before_first_line_deletion=True,
                    ),
                ),
            ),
        ),
        (
            ParsedModule(
                Path("pkg/models.py"),
                classes=(model_id,),
                class_spans=(ClassSpan(model_id, start_line=2, end_line=3),),
            ),
        ),
        ModuleIndex(
            module_by_path={},
            project_relative_file_to_module={Path("pkg/models.py"): Path("pkg/models.py")},
            class_to_module={model_id: Path("pkg/models.py")},
            seed_project_relative_paths=(),
            import_candidate_paths={},
        ),
        SelectedClasses(class_ids=(model_id,)),
        {Path("pkg/models.py"): ("def helper(): return 1", "class Model:", "    value = 1")},
    )

    assert decorations == ()


def test_diff_class_decorations_keeps_class_decorator_deletion_after_function() -> None:
    model_id = "pkg/models.py:Model"
    decorations = diff_app._diff_class_decorations(
        (
            ChangedFileEntry(
                "pkg/models.py",
                "modified",
                current_changed_line_ranges=(
                    ChangedLineRange(start=1, end=1, is_deletion_only=True, deleted_lines=("@entity",)),
                ),
            ),
        ),
        (
            ParsedModule(
                Path("pkg/models.py"),
                classes=(model_id,),
                class_spans=(ClassSpan(model_id, start_line=2, end_line=3),),
            ),
        ),
        ModuleIndex(
            module_by_path={},
            project_relative_file_to_module={Path("pkg/models.py"): Path("pkg/models.py")},
            class_to_module={model_id: Path("pkg/models.py")},
            seed_project_relative_paths=(),
            import_candidate_paths={},
        ),
        SelectedClasses(class_ids=(model_id,)),
        {Path("pkg/models.py"): ("def helper(): return 1", "class Model:", "    value = 1")},
    )

    assert decorations == ((model_id, "DiffChanged"),)


def test_diff_class_decorations_do_not_fabricate_changed_class_on_join_miss() -> None:
    selected_id = "pkg/other.py:Other"
    decorations = diff_app._diff_class_decorations(
        (ChangedFileEntry("pkg/broken.py", "modified", current_changed_line_ranges=(ChangedLineRange(1, 1),)),),
        (ParsedModule(Path("pkg/other.py"), classes=(selected_id,)),),
        ModuleIndex(
            module_by_path={},
            project_relative_file_to_module={Path("pkg/other.py"): Path("pkg/other.py")},
            class_to_module={selected_id: Path("pkg/other.py")},
            seed_project_relative_paths=(),
            import_candidate_paths={},
        ),
        SelectedClasses(class_ids=(selected_id,)),
    )

    assert decorations == ()


def test_diff_syntax_error_preserves_diagnostics_and_emits_no_fabricated_diff_changed(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "broken.py", "class Broken:\n    pass\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "broken.py", "class Broken(:\n")

    result = run_diff(
        diff_request(repo, output=Path("broken.puml")),
        timestamp=TIMESTAMP,
    )

    assert result.outcome_kind == "strict_promoted_failure"
    assert result.command_result.summary.counters["changed_class_count"] == 0
    assert "error:bad_syntax:" in result.stderr_text
    assert "error:render_selected_class_missing:" not in result.stderr_text
    assert not (repo / "broken.puml").exists()


def test_diff_changed_python_file_without_classes_preserves_failure_and_emits_no_diff_style(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "constants.py", "VALUE = 1\n\ndef helper() -> int:\n    return VALUE\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "constants.py", "VALUE = 2\n\ndef helper() -> int:\n    return VALUE\n")
    calls: dict[str, object] = {}
    original_render = diff_app.render_uml_document

    def render_spy(*args: object, **kwargs: object):
        calls["class_decorations"] = kwargs.get("class_decorations")
        return original_render(*args, **kwargs)

    monkeypatch.setattr(diff_app, "render_uml_document", render_spy)

    result = run_diff(
        diff_request(repo, output=Path("constants.puml")),
        timestamp=TIMESTAMP,
    )

    assert result.outcome_kind == "degraded_failure"
    assert result.command_result.exit_code == 1
    assert result.command_result.artifact_path is None
    assert result.command_result.summary.failure_reason is FailureReason.DIAGRAM_UNBUILDABLE_AFTER_RECOVERY
    assert result.command_result.summary.counters["seed_file_count"] == 1
    assert result.command_result.summary.counters["changed_class_count"] == 0
    assert result.command_result.diagnostics == ()
    assert calls["class_decorations"] == ()
    assert result.stdout_text == ""
    assert "failure_reason: diagram_unbuildable_after_recovery" in result.stderr_text
    assert "DiffChanged" not in result.stderr_text
    assert "skinparam class" not in result.stderr_text
    assert not (repo / "constants.puml").exists()


def test_working_tree_include_untracked_includes_untracked_python_in_seed_changed_and_report(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "tracked.py", "class Tracked:\n    pass\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "tracked.py", "class Tracked:\n    value = 1\n")
    write_file(repo / "pkg" / "untracked.py", "class Untracked:\n    pass\n")

    result = run_diff(
        diff_request(
            repo,
            include_untracked=True,
            output=Path("untracked.puml"),
        ),
        timestamp=TIMESTAMP,
    )
    captured = capsys.readouterr()

    artifact_text = (repo / "untracked.puml").read_text(encoding="utf-8")
    assert result.outcome_kind == "clean_success"
    assert result.command_result.exit_code == 0
    assert result.command_result.summary.counters["seed_file_count"] == 2
    assert result.command_result.summary.counters["changed_class_count"] == 2
    assert "seed_file_count: 2" in result.stdout_text
    assert "changed_class_count: 2" in result.stdout_text
    assert 'class "Tracked"' in artifact_text
    assert 'class "Untracked"' in artifact_text
    assert "skinparam class {" in artifact_text
    assert "<<DiffChanged>>" in class_declaration(artifact_text, "Tracked")
    assert "<<DiffChanged>>" in class_declaration(artifact_text, "Untracked")
    assert "<<DiffDependency>>" not in class_declaration(artifact_text, "Untracked")
    assert result.stderr_text == ""
    assert captured.out == ""
    assert captured.err == ""


def test_head_current_state_colors_head_changed_class_and_dependency_only_without_untracked(
    tmp_path: Path,
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "__init__.py")
    write_file(repo / "pkg" / "dependency.py", "class Dependency:\n    dependency_id: str\n")
    write_file(
        repo / "pkg" / "service.py",
        "\n".join(
            [
                "from pkg.dependency import Dependency",
                "",
                "class Service:",
                "    dependency: Dependency",
            ]
        ),
    )
    commit_all(repo, "base")
    tag_base(repo)
    write_file(
        repo / "pkg" / "service.py",
        "\n".join(
            [
                "from pkg.dependency import Dependency",
                "",
                "class Service:",
                "    dependency: Dependency",
                "    version: str",
            ]
        ),
    )
    commit_all(repo, "head")
    write_file(repo / "pkg" / "untracked.py", "class Untracked:\n    pass\n")

    result = run_diff(
        diff_request(
            repo,
            current_state=DiffCurrentState.HEAD,
            include_untracked=True,
            output=Path("head-colorized.puml"),
        ),
        timestamp=TIMESTAMP,
    )

    output = (repo / "head-colorized.puml").read_text(encoding="utf-8")
    service_declaration = class_declaration(output, "Service")
    dependency_declaration = class_declaration(output, "Dependency")
    assert result.outcome_kind == "warning_only_success"
    assert result.command_result.summary.counters["seed_file_count"] == 1
    assert result.command_result.summary.counters["changed_class_count"] == 1
    assert "warning:head_untracked_noop:" in result.stdout_text
    assert "skinparam class {" in output
    assert "<<DiffChanged>>" in service_declaration
    assert "<<DiffDependency>>" not in service_declaration
    assert "<<DiffDependency>>" not in dependency_declaration
    assert "<<DiffChanged>>" not in dependency_declaration
    assert 'class "Untracked"' not in output
    assert_relation(output, "Service", "*--", "Dependency")


def test_working_tree_default_excludes_untracked_python_from_seed_changed_and_report(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "tracked.py", "class Tracked:\n    pass\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "tracked.py", "class Tracked:\n    value = 1\n")
    write_file(repo / "pkg" / "untracked.py", "class Untracked:\n    pass\n")

    result = run_diff(
        diff_request(
            repo,
            output=Path("tracked-only.puml"),
        ),
        timestamp=TIMESTAMP,
    )
    captured = capsys.readouterr()

    artifact_text = (repo / "tracked-only.puml").read_text(encoding="utf-8")
    assert result.outcome_kind == "clean_success"
    assert result.command_result.exit_code == 0
    assert result.command_result.summary.counters["seed_file_count"] == 1
    assert result.command_result.summary.counters["changed_class_count"] == 1
    assert "seed_file_count: 1" in result.stdout_text
    assert "changed_class_count: 1" in result.stdout_text
    assert 'class "Tracked"' in artifact_text
    assert 'class "Untracked"' not in artifact_text
    assert result.stderr_text == ""
    assert captured.out == ""
    assert captured.err == ""


def test_output_unspecified_uses_diff_prefix_and_caller_timestamp(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "model.py", "class User:\n    pass\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "model.py", "class User:\n    value = 1\n")

    result = run_diff(diff_request(repo), timestamp=TIMESTAMP)

    artifact_path = repo / "pyclassuml_diff_20260504_123456.puml"
    assert result.outcome_kind == "clean_success"
    assert result.command_result.artifact_path == artifact_path
    assert artifact_path.read_text(encoding="utf-8").startswith("@startuml\n")


def test_project_root_relative_changed_files_are_used_for_inventory_and_handed_to_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "model.py", "class User:\n    pass\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "model.py", "class User:\n    value = 1\n")
    sentinel_inventory = ChangedClassInventory(class_count=1, changed_files=(Path("pkg/model.py"),))
    calls: dict[str, object] = {}
    original_write_report = diff_app.write_report

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

    monkeypatch.setattr(diff_app, "build_changed_class_inventory", build_changed_class_inventory_spy)
    monkeypatch.setattr(diff_app, "write_report", write_report_spy)

    result = run_diff(
        diff_request(repo, output=Path("diagram.puml")),
        timestamp=TIMESTAMP,
    )

    report_inputs = calls["report_inputs"]
    assert result.outcome_kind == "clean_success"
    assert calls["changed_files"] == (Path("pkg/model.py"),)
    assert tuple(calls["parsed_modules"])
    assert calls["module_index"] is not None
    assert isinstance(report_inputs, ReportInputs)
    assert report_inputs.changed_class_inventory is sentinel_inventory


def test_scope_stop_count_from_traversal_observations_is_handed_to_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(
        repo / "pkg" / "app" / "model.py",
        "from pkg import shared\n\nclass User:\n    pass\n",
    )
    write_file(repo / "pkg" / "shared.py", "class Shared:\n    pass\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(
        repo / "pkg" / "app" / "model.py",
        "from pkg import shared\n\nclass User:\n    value = 1\n",
    )
    calls: dict[str, object] = {}
    original_write_report = diff_app.write_report

    def write_report_spy(inputs: ReportInputs):
        calls["report_inputs"] = inputs
        return original_write_report(inputs)

    monkeypatch.setattr(diff_app, "write_report", write_report_spy)

    result = run_diff(
        diff_request(
            repo,
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


def test_head_include_untracked_noop_warning_is_preserved(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "base.py", "class Base:\n    pass\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "head_only.py", "class HeadOnly:\n    pass\n")
    commit_all(repo, "head")
    write_file(repo / "untracked.py", "class Untracked:\n    pass\n")

    result = run_diff(
        diff_request(
            repo,
            current_state=DiffCurrentState.HEAD,
            include_untracked=True,
            output=Path("head.puml"),
        ),
        timestamp=TIMESTAMP,
    )

    assert result.outcome_kind == "warning_only_success"
    assert result.command_result.exit_code == 0
    assert result.command_result.summary.counters["warning_count"] == 1
    assert "warning:head_untracked_noop:" in result.stdout_text
    assert "untracked.py" not in (repo / "head.puml").read_text(encoding="utf-8")


def test_diff_scope_excluded_count_is_preserved(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "inside.py", "class Inside:\n    pass\n")
    write_file(repo / "outside.py", "class Outside:\n    pass\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "inside.py", "class Inside:\n    value = 1\n")
    write_file(repo / "outside.py", "class Outside:\n    value = 1\n")

    result = run_diff(
        diff_request(
            repo,
            package_root=Path("pkg"),
            scope_root=Path("pkg"),
            output=Path("scope.puml"),
        ),
        timestamp=TIMESTAMP,
    )

    assert result.outcome_kind == "warning_only_success"
    assert result.command_result.exit_code == 0
    assert result.command_result.summary.counters["diff_scope_excluded_count"] == 1
    assert result.command_result.summary.counters["changed_class_count"] == 1
    assert "diff_scope_excluded_count: 1" in result.stdout_text
    assert "warning:diff_scope_exclusion:" in result.stdout_text


def test_zero_target_all_scope_outside_preserves_diff_scope_excluded_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = init_repo(tmp_path / "repo")
    (repo / "pkg").mkdir()
    write_file(repo / "outside.py", "class Outside:\n    pass\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "outside.py", "class Outside:\n    value = 1\n")
    monkeypatch.setattr(diff_app, "parse_target_set", fail_if_called("parse"))
    monkeypatch.setattr(diff_app, "traverse_dependencies", fail_if_called("traversal"))
    monkeypatch.setattr(diff_app, "render_uml_document", fail_if_called("render"))

    result = run_diff(
        diff_request(
            repo,
            package_root=Path("."),
            scope_root=Path("pkg"),
        ),
        timestamp=TIMESTAMP,
    )
    captured = capsys.readouterr()

    assert result.outcome_kind == "hard_failure"
    assert result.command_result.exit_code == 1
    assert result.command_result.summary.failure_reason is FailureReason.DIFF_ZERO_TARGET_AFTER_SCOPE_FILTER
    assert result.command_result.summary.counters["seed_file_count"] == 0
    assert result.command_result.summary.counters["diff_scope_excluded_count"] == 1
    assert "diff_scope_excluded_count: 1" in result.stderr_text
    assert "warning:diff_scope_exclusion:" in result.stderr_text
    assert "error:diff_zero_target_after_scope_filter:" in result.stderr_text
    assert captured.out == ""
    assert captured.err == ""


def test_output_write_failure_preserves_report_owned_nonzero_result(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "model.py", "class User:\n    pass\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "model.py", "class User:\n    value = 1\n")
    write_file(repo / "blocked", "not a directory\n")

    result = run_diff(
        diff_request(repo, output=Path("blocked/diagram.puml")),
        timestamp=TIMESTAMP,
    )

    assert result.outcome_kind == "hard_failure"
    assert result.command_result.exit_code == 1
    assert result.command_result.artifact_path is None
    assert result.command_result.summary.failure_reason is FailureReason.OUTPUT_WRITE_FAILURE
    assert result.stdout_text == ""
    assert "failure_reason: output_write_failure" in result.stderr_text
    assert "error:output_write_failure:" in result.stderr_text


def test_output_write_failure_does_not_emit_process_streams(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "model.py", "class User:\n    pass\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "model.py", "class User:\n    value = 1\n")
    write_file(repo / "blocked", "not a directory\n")

    result = run_diff(
        diff_request(repo, output=Path("blocked/diagram.puml")),
        timestamp=TIMESTAMP,
    )
    captured = capsys.readouterr()

    assert result.outcome_kind == "hard_failure"
    assert result.stdout_text == ""
    assert captured.out == ""
    assert captured.err == ""


def test_render_failure_is_report_owned_nonzero_result_without_process_streams(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "empty.py", "VALUE = 1\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "empty.py", "VALUE = 2\n")

    result = run_diff(
        diff_request(repo, output=Path("empty.puml")),
        timestamp=TIMESTAMP,
    )
    captured = capsys.readouterr()

    assert result.outcome_kind == "degraded_failure"
    assert result.command_result.exit_code == 1
    assert result.command_result.artifact_path is None
    assert result.command_result.summary.failure_reason is FailureReason.DIAGRAM_UNBUILDABLE_AFTER_RECOVERY
    assert result.stdout_text == ""
    assert "failure_reason: diagram_unbuildable_after_recovery" in result.stderr_text
    assert not (repo / "empty.puml").exists()
    assert captured.out == ""
    assert captured.err == ""
