from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from pyclassuml.model import (
    AnalysisConfig,
    AnalysisMode,
    ClassId,
    ChangedClassInventory,
    CommandName,
    CommandOptions,
    CommandRequest,
    CommandResult,
    ClassReference,
    DependencyGraph,
    Diagnostic,
    DiagnosticSeverity,
    DiffCurrentState,
    DiffOptions,
    DiagramModel,
    ExecutionContext,
    FailureReason,
    GenerateOptions,
    OriginSeam,
    ParsedModule,
    PlantUmlText,
    Recoverability,
    RenderReadyModel,
    RunSummary,
    SelectedClasses,
    TargetObservations,
    TargetSet,
)


def warning_diagnostic() -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.WARNING,
        code="ignored_target",
        message="ignored",
        origin_seam=OriginSeam.TARGETS,
        recoverability=Recoverability.RECOVERABLE,
    )


def error_diagnostic() -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="bad_syntax",
        message="syntax error",
        origin_seam=OriginSeam.PARSE,
        recoverability=Recoverability.FATAL,
        failure_reason=FailureReason.STRICT_SYNTAX_ERROR,
    )


def valid_generate_command_options(**overrides: object) -> CommandOptions:
    kwargs: dict[str, object] = {
        "command": CommandName.GENERATE,
        "cwd": Path("."),
        "config": Path("pyproject.toml"),
        "project_root": Path("."),
        "package_root": Path("src/pyclassuml"),
        "scope_root": Path("src"),
        "output": Path("out.puml"),
        "ignore": ("tests",),
        "depth": 1,
        "strict": False,
        "target_python": "3.11",
        "generate": GenerateOptions(targets=[Path("src"), "pyclassuml.*"]),
    }
    kwargs.update(overrides)
    return CommandOptions(**kwargs)


def test_enum_value_sets_are_exact_contract_domains() -> None:
    assert {member.value for member in CommandName} == {"generate", "diff"}
    assert {member.value for member in AnalysisMode} == {"warn", "strict"}
    assert {member.value for member in DiffCurrentState} == {"working-tree", "head"}
    assert {member.value for member in DiagnosticSeverity} == {"warning", "error"}
    assert {member.value for member in Recoverability} == {
        "recoverable",
        "degraded_output",
        "fatal",
    }
    assert {member.value for member in OriginSeam} == {
        "cli",
        "config",
        "targets",
        "vcs",
        "parse",
        "analyze",
        "frameworks",
        "render",
        "report",
        "app",
    }
    assert {member.value for member in FailureReason} == {
        "cli_usage_error",
        "invalid_config_or_config_path",
        "invalid_path_or_containment",
        "strict_diff_scope_exclusion",
        "generate_scope_violation",
        "generate_zero_target_after_normalize",
        "diff_zero_target_after_scope_filter",
        "strict_resolution_failure",
        "strict_syntax_error",
        "strict_wildcard_resolution_failure",
        "traversal_limit_reached",
        "output_write_failure",
        "vcs_read_failure",
        "diagram_unbuildable_after_recovery",
    }


def test_public_import_surface_and_valid_construction() -> None:
    class_id: ClassId = "pyclassuml.model.contracts:CommandRequest"
    generate_options = GenerateOptions(targets=[Path("src"), "pyclassuml.*"])
    command_options = CommandOptions(
        command=CommandName.GENERATE,
        cwd=Path("."),
        config=Path("pyproject.toml"),
        project_root=Path("."),
        package_root=Path("src/pyclassuml"),
        scope_root=Path("src"),
        output=Path("out.puml"),
        ignore=["tests"],
        depth=1,
        strict=False,
        target_python="3.11",
        generate=generate_options,
    )

    assert CommandRequest(process_cwd=Path.cwd(), cli_options=command_options)
    assert ExecutionContext(
        execution_cwd=Path.cwd(),
        project_root=Path.cwd(),
        package_root=Path.cwd() / "src/pyclassuml",
        scope_root=Path.cwd() / "src",
    )
    assert AnalysisConfig(
        ignore=["tests"],
        output=Path("out.puml"),
        depth=0,
        mode=AnalysisMode.STRICT,
        target_python="3.12",
        diff_current_state=DiffCurrentState.HEAD,
        diff_include_untracked=True,
    )
    assert TargetSet(seed_files=[Path("src/pyclassuml/model/contracts.py")], observations=TargetObservations())
    assert ParsedModule(
        module_path=Path("src/pyclassuml/model/contracts.py"),
        imports=["pathlib.Path"],
        classes=[class_id],
        class_references=[
            ClassReference(
                source_class_id=class_id,
                target_name="Diagnostic",
                reference_kind="annotation_subscript",
                reference_owner="Mapped",
            )
        ],
        diagnostics=[warning_diagnostic()],
    )
    assert DependencyGraph(reachable_files=[Path("a.py")], edges=[(Path("a.py"), Path("b.py"))])
    assert SelectedClasses(class_ids=["a:A"])


def test_class_reference_contract_is_public_and_validated() -> None:
    reference = ClassReference(
        source_class_id="pkg/a.py:A",
        target_name="B",
        reference_kind="annotation_subscript",
        reference_owner="Owner",
    )

    parsed_module = ParsedModule(
        module_path=Path("pkg/a.py"),
        classes=["pkg/a.py:A"],
        class_references=[reference],
    )

    assert parsed_module.class_references == (reference,)

    for field in ("source_class_id", "target_name", "reference_kind", "reference_owner"):
        kwargs = {
            "source_class_id": "pkg/a.py:A",
            "target_name": "B",
            "reference_kind": "annotation_subscript",
            "reference_owner": "Owner",
            field: "",
        }
        with pytest.raises(ValueError):
            ClassReference(**kwargs)

    with pytest.raises(ValueError):
        ParsedModule(
            module_path=Path("pkg/a.py"),
            classes=["pkg/a.py:A"],
            class_references=["not-a-reference"],
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("depth", -1),
        ("mode", "strict"),
        ("target_python", "3"),
    ],
)
def test_analysis_config_rejects_invalid_depth_mode_target_python(field: str, value: object) -> None:
    kwargs = {field: value}

    with pytest.raises(ValueError):
        AnalysisConfig(**kwargs)


def test_counters_and_seed_files_are_validated() -> None:
    with pytest.raises(ValueError):
        TargetObservations(ignored_seed_candidate_count=-1)

    with pytest.raises(ValueError):
        TargetObservations(ignored_seed_candidate_count=True)

    with pytest.raises(ValueError):
        TargetObservations(diff_scope_excluded_count=-1)

    with pytest.raises(ValueError):
        TargetObservations(diff_scope_excluded_count=False)

    observations = TargetObservations(ignored_seed_candidate_count=2, diff_scope_excluded_count=3)
    target_set = TargetSet(seed_files=[Path("a.py")], observations=observations)
    assert target_set.observations.ignored_seed_candidate_count == 2
    assert target_set.observations.diff_scope_excluded_count == 3

    with pytest.raises(ValueError):
        TargetSet(seed_files=[Path("README.md")], observations=TargetObservations())

    with pytest.raises(ValueError):
        RunSummary(counters={"warning_count": -1})

    with pytest.raises(ValueError):
        RunSummary(counters={"warning_count": False})


def test_diagnostic_failure_rules_and_enum_domains() -> None:
    with pytest.raises(ValueError):
        Diagnostic(
            severity=DiagnosticSeverity.ERROR,
            code="bad_syntax",
            message="syntax error",
            origin_seam=OriginSeam.PARSE,
            recoverability=Recoverability.FATAL,
        )

    with pytest.raises(ValueError):
        Diagnostic(
            severity=DiagnosticSeverity.WARNING,
            code="ignored_target",
            message="ignored",
            origin_seam=OriginSeam.TARGETS,
            recoverability=Recoverability.RECOVERABLE,
            failure_reason=FailureReason.CLI_USAGE_ERROR,
        )

    with pytest.raises(ValueError):
        Diagnostic(
            severity="error",
            code="bad_syntax",
            message="syntax error",
            origin_seam=OriginSeam.PARSE,
            recoverability=Recoverability.FATAL,
            failure_reason=FailureReason.STRICT_SYNTAX_ERROR,
        )

    with pytest.raises(ValueError):
        Diagnostic(
            severity=DiagnosticSeverity.ERROR,
            code="bad_syntax",
            message="syntax error",
            origin_seam="parse",
            recoverability=Recoverability.FATAL,
            failure_reason=FailureReason.STRICT_SYNTAX_ERROR,
        )

    with pytest.raises(ValueError):
        Diagnostic(
            severity=DiagnosticSeverity.ERROR,
            code="bad_syntax",
            message="syntax error",
            origin_seam=OriginSeam.PARSE,
            recoverability="fatal",
            failure_reason=FailureReason.STRICT_SYNTAX_ERROR,
        )

    with pytest.raises(ValueError):
        Diagnostic(
            severity=DiagnosticSeverity.ERROR,
            code="bad_syntax",
            message="syntax error",
            origin_seam=OriginSeam.PARSE,
            recoverability=Recoverability.FATAL,
            failure_reason="strict_syntax_error",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("depth", -1),
        ("depth", True),
        ("target_python", "3"),
        ("strict", "false"),
    ],
)
def test_command_options_rejects_invalid_scalar_invariants(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        valid_generate_command_options(**{field: value})


def test_command_option_absence_rules() -> None:
    with pytest.raises(ValueError):
        CommandOptions(command="generate", generate=GenerateOptions())

    with pytest.raises(ValueError):
        CommandOptions(command=CommandName.GENERATE)

    with pytest.raises(ValueError):
        CommandOptions(
            command=CommandName.GENERATE,
            generate=GenerateOptions(),
            diff=DiffOptions(
                base_ref="main",
                current_state=DiffCurrentState.WORKING_TREE,
                include_untracked=False,
            ),
        )

    with pytest.raises(ValueError):
        CommandOptions(command=CommandName.DIFF, generate=GenerateOptions())

    with pytest.raises(ValueError):
        CommandOptions(command=CommandName.DIFF)

    assert CommandOptions(
        command=CommandName.DIFF,
        diff=DiffOptions(
            base_ref="main",
            current_state=DiffCurrentState.WORKING_TREE,
            include_untracked=True,
        ),
    )

    with pytest.raises(ValueError):
        DiffOptions(base_ref="", current_state=DiffCurrentState.HEAD, include_untracked=False)

    with pytest.raises(ValueError):
        DiffOptions(base_ref="main", current_state="working-tree", include_untracked=False)


def test_command_options_rejects_bare_string_collections_and_non_path_options() -> None:
    with pytest.raises(ValueError):
        GenerateOptions(targets="src")

    with pytest.raises(ValueError):
        CommandOptions(command=CommandName.GENERATE, generate=GenerateOptions(), ignore="tests")

    for field in ("cwd", "config", "project_root", "package_root", "scope_root", "output"):
        with pytest.raises(ValueError):
            CommandOptions(command=CommandName.GENERATE, generate=GenerateOptions(), **{field: "."})


def test_collection_and_mapping_inputs_are_immutable_copies() -> None:
    ignore = ["tmp"]
    config = AnalysisConfig(ignore=ignore)
    ignore.append("build")
    assert config.ignore == ("tmp",)

    targets = [Path("a.py")]
    target_set = TargetSet(seed_files=targets, observations=TargetObservations())
    targets.append(Path("b.py"))
    assert target_set.seed_files == (Path("a.py"),)

    counters = {"warning_count": 1}
    summary = RunSummary(counters=counters)
    counters["warning_count"] = 9
    assert summary.counters["warning_count"] == 1
    with pytest.raises(TypeError):
        summary.counters["warning_count"] = 2
    with pytest.raises(FrozenInstanceError):
        config.depth = 3


def test_pair_and_triple_inner_inputs_are_immutable_copies() -> None:
    edge = [Path("a.py"), Path("b.py")]
    graph = DependencyGraph(edges=[edge])
    edge[1] = Path("c.py")
    assert graph.edges == ((Path("a.py"), Path("b.py")),)

    relation = ["a:A", "b:B", "uses"]
    render_ready = RenderReadyModel(relations=[relation])
    relation[2] = "inherits"
    assert render_ready.relations == (("a:A", "b:B", "uses"),)

    decoration = ["a:A", "dataclass"]
    decorated_render_ready = RenderReadyModel(class_decorations=[decoration])
    decoration[1] = "attrs"
    assert decorated_render_ready.class_decorations == (("a:A", "dataclass"),)

    rendered_relation = ["a:A", "b:B", "uses"]
    relation_diagram = DiagramModel(rendered_relations=[rendered_relation])
    rendered_relation[2] = "inherits"
    assert relation_diagram.rendered_relations == (("a:A", "b:B", "uses"),)

    alias = ["a:A", "A"]
    diagram = DiagramModel(aliases=[alias])
    alias[1] = "Renamed"
    assert diagram.aliases == (("a:A", "A"),)


def test_optional_artifact_result_and_exit_code_contract() -> None:
    result = CommandResult(
        artifact_path=None,
        summary=RunSummary(counters={"warning_count": 1}, failure_reason=FailureReason.STRICT_SYNTAX_ERROR),
        diagnostics=[error_diagnostic()],
        exit_code=1,
    )

    assert result.artifact_path is None
    assert result.exit_code == 1

    with pytest.raises(ValueError):
        CommandResult(artifact_path=Path("out.puml"), summary=RunSummary(), diagnostics=[], exit_code=-1)


def test_render_and_result_handoff_are_separate_shapes() -> None:
    render_ready = RenderReadyModel(
        classes=["a:A"],
        members=["a:A.field"],
        relations=[("a:A", "b:B", "uses")],
        class_decorations=[("a:A", "dataclass")],
        grouping_keys=["package"],
        diagnostics=[warning_diagnostic()],
    )
    diagram = DiagramModel(
        containers=["pkg"],
        rendered_classes=["a:A"],
        rendered_relations=[("a:A", "b:B", "uses")],
        aliases=[("a:A", "A")],
    )
    text = PlantUmlText("@startuml\n@enduml")
    inventory = ChangedClassInventory(class_count=1, changed_files=[Path("a.py")])
    result = CommandResult(
        artifact_path=Path("diagram.puml"),
        summary=RunSummary(counters={"class_count": inventory.class_count}),
        diagnostics=render_ready.diagnostics,
        exit_code=0,
    )

    assert render_ready.classes == ("a:A",)
    assert diagram.rendered_classes == ("a:A",)
    assert text.text.startswith("@startuml")
    assert result.artifact_path == Path("diagram.puml")
