from pathlib import Path
from typing import Callable

import pytest

from pyclassuml.model import (
    AnalysisConfig,
    CommandName,
    CommandOptions,
    CommandRequest,
    DiagnosticSeverity,
    ExecutionContext,
    FailureReason,
    GenerateOptions,
    OriginSeam,
    Recoverability,
)
from pyclassuml.targets import TargetNormalization, normalize_explicit_targets


def write_file(path: Path, text: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def request(targets: tuple[Path | str, ...]) -> CommandRequest:
    return CommandRequest(
        process_cwd=Path("/unused"),
        cli_options=CommandOptions(
            command=CommandName.GENERATE,
            generate=GenerateOptions(targets=targets),
        ),
    )


def context(project_root: Path, *, execution_cwd: Path | None = None, scope_root: Path | None = None) -> ExecutionContext:
    return ExecutionContext(
        execution_cwd=(execution_cwd or project_root).resolve(),
        project_root=project_root.resolve(),
        package_root=project_root.resolve(),
        scope_root=(scope_root or project_root).resolve(),
    )


def assert_success(result: TargetNormalization) -> tuple[Path, ...]:
    assert result.diagnostics == ()
    assert result.target_set is not None
    return result.target_set.seed_files


def assert_failure(result: TargetNormalization, reason: FailureReason) -> None:
    assert result.target_set is None
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.origin_seam is OriginSeam.TARGETS
    assert diagnostic.recoverability is Recoverability.FATAL
    assert diagnostic.failure_reason is reason


def test_single_relative_file_success(tmp_path: Path) -> None:
    target = write_file(tmp_path / "pkg" / "module.py")

    result = normalize_explicit_targets(request((Path("pkg/module.py"),)), context(tmp_path), AnalysisConfig())

    assert assert_success(result) == (target.resolve(),)
    assert result.target_set is not None
    assert result.target_set.observations.ignored_seed_candidate_count == 0
    assert result.target_set.observations.diff_scope_excluded_count == 0


def test_file_glob_and_dir_dedupe_order_include_init_and_only_python(tmp_path: Path) -> None:
    a = write_file(tmp_path / "pkg" / "a.py")
    init = write_file(tmp_path / "pkg" / "__init__.py")
    b = write_file(tmp_path / "pkg" / "nested" / "b.py")
    write_file(tmp_path / "pkg" / "notes.txt")

    result = normalize_explicit_targets(
        request((Path("pkg/a.py"), "pkg/**/*.py", Path("pkg"))),
        context(tmp_path),
        AnalysisConfig(),
    )

    assert assert_success(result) == tuple(sorted({a.resolve(), init.resolve(), b.resolve()}))


def test_default_and_user_ignore_are_project_root_relative_and_counted(tmp_path: Path) -> None:
    keep = write_file(tmp_path / "pkg" / "keep.py")
    write_file(tmp_path / ".venv" / "lib.py")
    write_file(tmp_path / "venv" / "lib.py")
    write_file(tmp_path / "__pycache__" / "cached.py")
    write_file(tmp_path / "pkg" / "__pycache__" / "cached.py")
    write_file(tmp_path / "site-packages" / "vendor.py")
    write_file(tmp_path / "pkg" / "generated" / "skip.py")

    result = normalize_explicit_targets(
        request(("**/*.py",)),
        context(tmp_path),
        AnalysisConfig(ignore=("pkg/generated/**",)),
    )

    assert assert_success(result) == (keep.resolve(),)
    assert result.target_set is not None
    assert result.target_set.observations.ignored_seed_candidate_count == 6


def test_user_ignore_single_star_does_not_cross_path_segments(tmp_path: Path) -> None:
    direct = write_file(tmp_path / "pkg" / "direct.py")
    nested = write_file(tmp_path / "pkg" / "nested" / "mod.py")

    result = normalize_explicit_targets(
        request(("pkg/**/*.py",)),
        context(tmp_path),
        AnalysisConfig(ignore=("pkg/*.py",)),
    )

    assert assert_success(result) == (nested.resolve(),)
    assert result.target_set is not None
    assert result.target_set.observations.ignored_seed_candidate_count == 1
    assert direct.resolve() not in result.target_set.seed_files


def test_user_ignore_double_star_can_cross_path_segments(tmp_path: Path) -> None:
    direct = write_file(tmp_path / "pkg" / "direct.py")
    nested = write_file(tmp_path / "pkg" / "nested" / "mod.py")
    keep = write_file(tmp_path / "other.py")

    result = normalize_explicit_targets(
        request(("**/*.py",)),
        context(tmp_path),
        AnalysisConfig(ignore=("pkg/**/*.py",)),
    )

    assert assert_success(result) == (keep.resolve(),)
    assert result.target_set is not None
    assert result.target_set.observations.ignored_seed_candidate_count == 2
    assert direct.resolve() not in result.target_set.seed_files
    assert nested.resolve() not in result.target_set.seed_files


def test_ignore_patterns_stay_project_root_relative_when_execution_cwd_differs(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    execution_cwd = project_root / "tools"
    execution_cwd.mkdir(parents=True)
    keep = write_file(project_root / "pkg" / "keep.py")
    write_file(project_root / "pkg" / "generated" / "skip.py")
    write_file(project_root / "__pycache__" / "root_cached.py")
    write_file(project_root / "pkg" / "__pycache__" / "nested_cached.py")

    result = normalize_explicit_targets(
        request(("../pkg/**/*.py", "../__pycache__/*.py")),
        context(project_root, execution_cwd=execution_cwd),
        AnalysisConfig(ignore=("pkg/generated/**",)),
    )

    assert assert_success(result) == (keep.resolve(),)
    assert result.target_set is not None
    assert result.target_set.observations.ignored_seed_candidate_count == 3


def test_relative_path_is_resolved_from_execution_cwd(tmp_path: Path) -> None:
    target = write_file(tmp_path / "project" / "src" / "module.py")
    execution_cwd = tmp_path / "project" / "work"
    execution_cwd.mkdir(parents=True)

    result = normalize_explicit_targets(
        request((Path("../src/module.py"),)),
        context(tmp_path / "project", execution_cwd=execution_cwd),
        AnalysisConfig(),
    )

    assert assert_success(result) == (target.resolve(),)


def test_cwd_relative_glob_target_when_execution_cwd_differs_from_project_root(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    execution_cwd = project_root / "work"
    execution_cwd.mkdir(parents=True)
    module = write_file(project_root / "src" / "module.py")
    write_file(project_root / "src" / "nested" / "nested.py")

    result = normalize_explicit_targets(
        request(("../src/*.py",)),
        context(project_root, execution_cwd=execution_cwd),
        AnalysisConfig(),
    )

    assert assert_success(result) == (module.resolve(),)


def test_cwd_relative_directory_target_when_execution_cwd_differs_from_project_root(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    execution_cwd = project_root / "work"
    execution_cwd.mkdir(parents=True)
    module = write_file(project_root / "src" / "module.py")
    nested = write_file(project_root / "src" / "nested" / "nested.py")

    result = normalize_explicit_targets(
        request((Path("../src"),)),
        context(project_root, execution_cwd=execution_cwd),
        AnalysisConfig(),
    )

    assert assert_success(result) == tuple(sorted((module.resolve(), nested.resolve())))


def test_scope_violation_fails_without_partial_success_when_valid_seed_is_present(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    valid_seed = write_file(project_root / "pkg" / "module.py")
    outside_target = write_file(tmp_path / "outside" / "outside.py")

    result = normalize_explicit_targets(
        request((valid_seed, outside_target)),
        context(project_root, scope_root=project_root),
        AnalysisConfig(),
    )

    assert_failure(result, FailureReason.GENERATE_SCOPE_VIOLATION)


@pytest.mark.parametrize(
    "target_factory",
    [
        lambda root, outside: outside / "outside.py",
        lambda root, outside: outside,
        lambda root, outside: str(outside / "*.py"),
        lambda root, outside: outside / "outside.txt",
        lambda root, outside: outside / "__pycache__" / "ignored.py",
    ],
)
def test_scope_outside_wins_before_ignore_python_and_zero_seed(
    tmp_path: Path,
    target_factory: Callable[[Path, Path], Path | str],
) -> None:
    outside = tmp_path / "outside"
    write_file(outside / "outside.py")
    write_file(outside / "outside.txt")
    write_file(outside / "__pycache__" / "ignored.py")

    raw_target = target_factory(tmp_path / "project", outside)

    result = normalize_explicit_targets(
        request((raw_target,)),
        context(tmp_path / "project", scope_root=tmp_path / "project"),
        AnalysisConfig(),
    )

    assert_failure(result, FailureReason.GENERATE_SCOPE_VIOLATION)


@pytest.mark.parametrize(
    "target_factory",
    [
        lambda root: "pkg/*.missing",
        lambda root: Path("missing.py"),
        lambda root: ".venv/ignored.py",
        lambda root: "README.md",
    ],
)
def test_zero_seed_diagnostic_for_glob_miss_missing_all_ignored_and_non_python(
    tmp_path: Path,
    target_factory: Callable[[Path], Path | str],
) -> None:
    write_file(tmp_path / ".venv" / "ignored.py")
    write_file(tmp_path / "README.md")

    result = normalize_explicit_targets(
        request((target_factory(tmp_path),)),
        context(tmp_path),
        AnalysisConfig(),
    )

    assert_failure(result, FailureReason.GENERATE_ZERO_TARGET_AFTER_NORMALIZE)
    assert result.diagnostics[0].code == "generate_zero_target_after_normalize"


def test_path_resolution_error_is_scope_violation_if_symlink_loop_is_supported(tmp_path: Path) -> None:
    loop = tmp_path / "loop"
    try:
        loop.symlink_to(loop)
    except OSError:
        pytest.skip("symlink creation is not supported")

    result = normalize_explicit_targets(request((Path("loop"),)), context(tmp_path), AnalysisConfig())

    assert_failure(result, FailureReason.GENERATE_SCOPE_VIOLATION)
    assert result.diagnostics[0].code == "generate_scope_violation"
