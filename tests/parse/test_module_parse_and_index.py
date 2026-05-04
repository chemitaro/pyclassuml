from pathlib import Path

from pyclassuml.model import (
    AnalysisConfig,
    ClassReference,
    DiagnosticSeverity,
    ExecutionContext,
    FailureReason,
    OriginSeam,
    Recoverability,
    TargetObservations,
    TargetSet,
)
from pyclassuml.parse import parse_target_set


def write_file(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path.resolve()


def context(project_root: Path, *, package_root: Path | None = None, scope_root: Path | None = None) -> ExecutionContext:
    return ExecutionContext(
        execution_cwd=project_root.resolve(),
        project_root=project_root.resolve(),
        package_root=(package_root or project_root).resolve(),
        scope_root=(scope_root or project_root).resolve(),
    )


def target_set(*seed_files: Path) -> TargetSet:
    return TargetSet(seed_files=tuple(seed_files), observations=TargetObservations())


def test_seed_file_parse_builds_parsed_module_and_index(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "import pkg.b",
                "from pkg import c",
                "class A:",
                "    class Nested:",
                "        pass",
                "def factory():",
                "    class Local:",
                "        pass",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.diagnostics == ()
    assert result.observations.ignored_dependency_candidate_count == 0
    assert result.module_index.seed_project_relative_paths == (Path("pkg/a.py"),)
    assert [module.module_path for module in result.parsed_modules] == [Path("pkg/a.py")]
    module = result.parsed_modules[0]
    assert module.imports == ("from pkg import c", "pkg.b")
    assert module.classes == ("pkg/a.py:A", "pkg/a.py:A.Nested")
    assert result.module_index.module_by_path[Path("pkg/a.py")] is module
    assert result.module_index.project_relative_file_to_module == {Path("pkg/a.py"): Path("pkg/a.py")}
    assert result.module_index.class_to_module == {
        "pkg/a.py:A": Path("pkg/a.py"),
        "pkg/a.py:A.Nested": Path("pkg/a.py"),
    }


def test_class_body_references_are_generic_and_deterministic(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "class A:",
                "    one: Owner[B]",
                "    many: Owner[list[C]]",
                "    link = link_to(\"D\")",
                "    def factory(self):",
                "        local: Owner[Local]",
                "        other = link_to(\"Local\")",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.parsed_modules[0].class_references == (
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="B",
            reference_kind="annotation_subscript",
            reference_owner="Owner",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="C",
            reference_kind="annotation_subscript",
            reference_owner="Owner",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="D",
            reference_kind="call_string_arg",
            reference_owner="link_to",
        ),
    )


def test_class_base_references_are_generic_and_deterministic(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "class A(BaseModel):",
                "    pass",
                "class B(pydantic.BaseModel):",
                "    pass",
                "class C(CustomBase):",
                "    pass",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.parsed_modules[0].class_references == (
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="BaseModel",
            reference_kind="class_base",
            reference_owner="base",
        ),
        ClassReference(
            source_class_id="pkg/a.py:B",
            target_name="pydantic.BaseModel",
            reference_kind="class_base",
            reference_owner="base",
        ),
        ClassReference(
            source_class_id="pkg/a.py:C",
            target_name="CustomBase",
            reference_kind="class_base",
            reference_owner="base",
        ),
    )


def test_generic_class_base_references_use_direct_base_name(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "class A(CustomBase[T]):",
                "    pass",
                "class B(BaseModel[T]):",
                "    pass",
                "class C(pydantic.BaseModel[T]):",
                "    pass",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.parsed_modules[0].class_references == (
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="CustomBase",
            reference_kind="class_base",
            reference_owner="base",
        ),
        ClassReference(
            source_class_id="pkg/a.py:B",
            target_name="BaseModel",
            reference_kind="class_base",
            reference_owner="base",
        ),
        ClassReference(
            source_class_id="pkg/a.py:C",
            target_name="pydantic.BaseModel",
            reference_kind="class_base",
            reference_owner="base",
        ),
    )


def test_quoted_annotation_references_are_generic_and_owner_scoped(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "class A:",
                "    direct: \"B\"",
                "    many: list[\"C\"]",
                "    optional: Optional[\"D\"]",
                "    union: Union[\"E\", \"F\"]",
                "    literal: Literal[\"Ignored\"]",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.parsed_modules[0].class_references == (
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="B",
            reference_kind="annotation_string",
            reference_owner="annotation",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="C",
            reference_kind="annotation_string",
            reference_owner="list",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="C",
            reference_kind="annotation_subscript",
            reference_owner="list",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="D",
            reference_kind="annotation_string",
            reference_owner="Optional",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="D",
            reference_kind="annotation_subscript",
            reference_owner="Optional",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="E",
            reference_kind="annotation_string",
            reference_owner="Union",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="E",
            reference_kind="annotation_subscript",
            reference_owner="Union",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="F",
            reference_kind="annotation_string",
            reference_owner="Union",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="F",
            reference_kind="annotation_subscript",
            reference_owner="Union",
        ),
    )


def test_annotated_metadata_strings_are_not_annotation_string_references(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "class A:",
                "    direct: Annotated[\"B\", \"label\"]",
                "    builtin: Annotated[int, \"label\"]",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    annotation_string_references = tuple(
        reference
        for reference in result.parsed_modules[0].class_references
        if reference.reference_kind == "annotation_string"
    )

    assert annotation_string_references == (
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="B",
            reference_kind="annotation_string",
            reference_owner="Annotated",
        ),
    )


def test_quoted_annotation_references_skip_nested_bodies(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "class A:",
                "    if True:",
                "        direct: \"B\"",
                "        def factory(self):",
                "            local: \"NestedFunction\"",
                "        async def async_factory(self):",
                "            local: \"NestedAsyncFunction\"",
                "        class Nested:",
                "            local: \"NestedClass\"",
                "        factory = lambda: list[\"LambdaBody\"]",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.parsed_modules[0].class_references == (
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="B",
            reference_kind="annotation_string",
            reference_owner="annotation",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A.Nested",
            target_name="NestedClass",
            reference_kind="annotation_string",
            reference_owner="annotation",
        ),
    )


def test_nested_class_references_use_nested_source_class_id(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "class A:",
                "    class Nested:",
                "        relation: Owner[B]",
                "        child: \"B\"",
                "        link = link_to(\"C\")",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.parsed_modules[0].class_references == (
        ClassReference(
            source_class_id="pkg/a.py:A.Nested",
            target_name="B",
            reference_kind="annotation_string",
            reference_owner="annotation",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A.Nested",
            target_name="B",
            reference_kind="annotation_subscript",
            reference_owner="Owner",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A.Nested",
            target_name="C",
            reference_kind="call_string_arg",
            reference_owner="link_to",
        ),
    )


def test_class_body_references_skip_nested_function_bodies_under_statements(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "class A:",
                "    if True:",
                "        def factory(self):",
                "            local = link_to(\"Local\")",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.parsed_modules[0].class_references == ()


def test_class_body_references_skip_lambda_bodies(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "class A:",
                "    factory = lambda: link_to(\"B\")",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.parsed_modules[0].class_references == ()


def test_class_body_references_include_annotation_under_control_statement(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "class A:",
                "    if True:",
                "        b: Owner[B]",
                "        def factory(self):",
                "            local: Owner[Local]",
                "        class Nested:",
                "            pass",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.parsed_modules[0].class_references == (
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="B",
            reference_kind="annotation_subscript",
            reference_owner="Owner",
        ),
    )


def test_mapped_annotation_references_ignore_typing_wrappers(tmp_path: Path) -> None:
    project = tmp_path / "project"
    seed = write_file(
        project / "pkg" / "a.py",
        "\n".join(
            [
                "class A:",
                "    optional: Mapped[Optional[B]]",
                "    union: Mapped[Union[B, C]]",
                "    annotated: Mapped[Annotated[B, \"primary\"]]",
                "    class_var: Mapped[ClassVar[C]]",
                "    final: Mapped[Final[B]]",
                "    literal: Mapped[Literal[\"B\"]]",
                "    required: Mapped[Required[B]]",
                "    not_required: Mapped[NotRequired[C]]",
            ]
        ),
    )

    result = parse_target_set(target_set(seed), context(project, package_root=project / "pkg"), AnalysisConfig())

    assert result.parsed_modules[0].class_references == (
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="B",
            reference_kind="annotation_subscript",
            reference_owner="Mapped",
        ),
        ClassReference(
            source_class_id="pkg/a.py:A",
            target_name="C",
            reference_kind="annotation_subscript",
            reference_owner="Mapped",
        ),
    )


def test_import_candidates_are_parsed_recursively_and_indexed_deterministically(tmp_path: Path) -> None:
    project = tmp_path / "project"
    package = project / "pkg"
    seed = write_file(package / "a.py", "from . import b\nclass A: pass\n")
    dependency_b = write_file(package / "b.py", "from pkg.sub import c\nclass B: pass\n")
    dependency_c = write_file(package / "sub" / "c.py", "class C: pass\n")

    result = parse_target_set(target_set(seed), context(project, package_root=package), AnalysisConfig())

    assert result.diagnostics == ()
    assert [module.module_path for module in result.parsed_modules] == [
        Path("pkg/a.py"),
        Path("pkg/b.py"),
        Path("pkg/sub/c.py"),
    ]
    assert result.module_index.import_candidate_paths == {
        "from . import b": (Path("pkg/b.py"),),
        "from pkg.sub import c": (Path("pkg/sub/c.py"),),
    }
    assert result.module_index.module_by_path[Path("pkg/b.py")].classes == ("pkg/b.py:B",)
    assert result.module_index.module_by_path[Path("pkg/sub/c.py")].classes == ("pkg/sub/c.py:C",)
    assert result.module_index.project_relative_file_to_module == {
        dependency_b.relative_to(project): Path("pkg/b.py"),
        dependency_c.relative_to(project): Path("pkg/sub/c.py"),
        seed.relative_to(project): Path("pkg/a.py"),
    }


def test_syntax_error_dependency_is_excluded_from_parsed_modules_and_indexes(tmp_path: Path) -> None:
    project = tmp_path / "project"
    package = project / "pkg"
    seed = write_file(package / "a.py", "from . import broken\nclass A: pass\n")
    write_file(package / "broken.py", "class Broken(:\n")

    result = parse_target_set(target_set(seed), context(project, package_root=package), AnalysisConfig())

    assert [module.module_path for module in result.parsed_modules] == [Path("pkg/a.py")]
    assert Path("pkg/broken.py") not in result.module_index.module_by_path
    assert Path("pkg/broken.py") not in result.module_index.project_relative_file_to_module
    assert result.module_index.class_to_module == {"pkg/a.py:A": Path("pkg/a.py")}
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "bad_syntax"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.origin_seam is OriginSeam.PARSE
    assert diagnostic.recoverability is Recoverability.DEGRADED_OUTPUT
    assert diagnostic.failure_reason is FailureReason.STRICT_SYNTAX_ERROR
    assert "pkg/broken.py" in diagnostic.message


def test_ignored_dependency_candidate_is_not_parsed_and_is_counted(tmp_path: Path) -> None:
    project = tmp_path / "project"
    package = project / "pkg"
    seed = write_file(package / "a.py", "from pkg.generated import skip\nclass A: pass\n")
    write_file(package / "generated" / "skip.py", "class Skip: pass\n")

    result = parse_target_set(
        target_set(seed),
        context(project, package_root=package),
        AnalysisConfig(ignore=("pkg/generated/**",)),
    )

    assert [module.module_path for module in result.parsed_modules] == [Path("pkg/a.py")]
    assert result.module_index.import_candidate_paths == {}
    assert result.observations.ignored_dependency_candidate_count == 1
    assert Path("pkg/generated/skip.py") not in result.module_index.module_by_path


def test_default_ignored_dependency_candidate_is_not_parsed_and_is_counted(tmp_path: Path) -> None:
    project = tmp_path / "project"
    package = project / "pkg"
    seed = write_file(package / "a.py", "import venv.vendor\nclass A: pass\n")
    write_file(project / "venv" / "vendor.py", "class Vendor: pass\n")

    result = parse_target_set(
        target_set(seed),
        context(project, package_root=project),
        AnalysisConfig(),
    )

    assert [module.module_path for module in result.parsed_modules] == [Path("pkg/a.py")]
    assert result.module_index.import_candidate_paths == {}
    assert result.observations.ignored_dependency_candidate_count == 1
    assert Path("venv/vendor.py") not in result.module_index.module_by_path


def test_boundary_candidates_are_lookup_material_without_package_external_parse(tmp_path: Path) -> None:
    project = tmp_path / "project"
    package = project / "pkg"
    scope = package / "app"
    seed = write_file(scope / "a.py", "from pkg import shared\nimport tools.helper\nclass A: pass\n")
    write_file(package / "shared.py", "class Shared: pass\n")
    write_file(project / "tools" / "helper.py", "class Helper: pass\n")

    result = parse_target_set(
        target_set(seed),
        context(project, package_root=package, scope_root=scope),
        AnalysisConfig(),
    )

    assert result.module_index.import_candidate_paths == {
        "from pkg import shared": (Path("pkg/shared.py"),),
        "tools.helper": (Path("tools/helper.py"),),
    }
    assert [module.module_path for module in result.parsed_modules] == [
        Path("pkg/app/a.py"),
        Path("pkg/shared.py"),
    ]
    assert Path("tools/helper.py") not in result.module_index.module_by_path
