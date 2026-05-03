from pathlib import Path

from pyclassuml.model import (
    AnalysisConfig,
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
