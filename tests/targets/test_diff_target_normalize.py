from pathlib import Path

from pyclassuml.model import (
    AnalysisConfig,
    Diagnostic,
    DiagnosticSeverity,
    DiffBaseResolution,
    ExecutionContext,
    FailureReason,
    OriginSeam,
    Recoverability,
    TargetObservations,
    TargetSet,
)
from pyclassuml.targets import DiffTargetNormalization, normalize_diff_targets
from pyclassuml.vcs import ChangedFileCollection, ChangedFileEntry


def write_file(path: Path, text: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def context(project_root: Path, *, scope_root: Path | None = None) -> ExecutionContext:
    return ExecutionContext(
        execution_cwd=project_root.resolve(),
        project_root=project_root.resolve(),
        package_root=project_root.resolve(),
        scope_root=(scope_root or project_root).resolve(),
    )


def collection(*paths: str) -> ChangedFileCollection:
    return ChangedFileCollection(
        entries=tuple(ChangedFileEntry(current_project_relative_path=path, change_kind="modified") for path in paths),
        base_resolution=DiffBaseResolution(
            requested_base_ref="origin/main",
            resolved_base_ref="origin/main",
            resolution_kind="explicit_base",
            candidate_ref=None,
        ),
    )


def assert_success(result: DiffTargetNormalization) -> tuple[Path, ...]:
    assert result.target_set is not None
    return result.target_set.seed_files


def assert_zero_target_failure(result: DiffTargetNormalization) -> None:
    assert result.target_set is None
    assert result.diagnostics
    diagnostic = result.diagnostics[-1]
    assert diagnostic.code == "diff_zero_target_after_scope_filter"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.origin_seam is OriginSeam.TARGETS
    assert diagnostic.recoverability is Recoverability.FATAL
    assert diagnostic.failure_reason is FailureReason.DIFF_ZERO_TARGET_AFTER_SCOPE_FILTER


def test_diff_target_normalization_constructor_preserves_exported_positional_shapes(tmp_path: Path) -> None:
    seed = write_file(tmp_path / "project" / "pkg" / "model.py")
    target_set = TargetSet(
        seed_files=(seed.resolve(),),
        observations=TargetObservations(diff_scope_excluded_count=2),
    )
    diagnostic = Diagnostic(
        severity=DiagnosticSeverity.WARNING,
        code="head_untracked_noop",
        message="include_untracked has no effect when diff current_state is head",
        origin_seam=OriginSeam.VCS,
        recoverability=Recoverability.RECOVERABLE,
    )

    default_observations = DiffTargetNormalization(target_set)
    positional_diagnostics = DiffTargetNormalization(target_set, (diagnostic,))
    keyword_diagnostics = DiffTargetNormalization(target_set, diagnostics=(diagnostic,))

    assert default_observations.target_set is target_set
    assert default_observations.diagnostics == ()
    assert default_observations.observations == TargetObservations()
    assert positional_diagnostics.target_set is target_set
    assert positional_diagnostics.diagnostics == (diagnostic,)
    assert positional_diagnostics.observations == TargetObservations()
    assert keyword_diagnostics.target_set is target_set
    assert keyword_diagnostics.diagnostics == (diagnostic,)
    assert keyword_diagnostics.observations == TargetObservations()


def test_scope_inside_python_seed_and_scope_outside_exclusion_are_carried(tmp_path: Path) -> None:
    project = tmp_path / "project"
    scope = project / "pkg"
    inside = write_file(scope / "inside.py")
    write_file(project / "outside.py")

    result = normalize_diff_targets(
        collection("pkg/inside.py", "outside.py"),
        context(project, scope_root=scope),
        AnalysisConfig(),
    )

    assert assert_success(result) == (inside.resolve(),)
    assert result.target_set is not None
    assert result.observations == result.target_set.observations
    assert result.target_set.observations.diff_scope_excluded_count == 1
    assert result.target_set.observations.ignored_seed_candidate_count == 0
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "diff_scope_exclusion"
    assert diagnostic.severity is DiagnosticSeverity.WARNING
    assert diagnostic.origin_seam is OriginSeam.TARGETS
    assert diagnostic.recoverability is Recoverability.RECOVERABLE
    assert diagnostic.failure_reason is None


def test_project_root_relative_ignore_non_python_and_dedupe_are_deterministic(tmp_path: Path) -> None:
    project = tmp_path / "project"
    keep_a = write_file(project / "pkg" / "a.py")
    keep_z = write_file(project / "pkg" / "z.py")
    write_file(project / "pkg" / "notes.txt")
    write_file(project / "pkg" / "generated" / "skip.py")
    write_file(project / "pkg" / "__pycache__" / "cached.py")

    result = normalize_diff_targets(
        collection(
            "pkg/z.py",
            "pkg/notes.txt",
            "pkg/generated/skip.py",
            "pkg/a.py",
            "pkg/z.py",
            "pkg/__pycache__/cached.py",
        ),
        context(project),
        AnalysisConfig(ignore=("pkg/generated/**",)),
    )

    assert assert_success(result) == tuple(sorted((keep_a.resolve(), keep_z.resolve())))
    assert result.target_set is not None
    assert result.observations == result.target_set.observations
    assert result.target_set.observations.ignored_seed_candidate_count == 2
    assert result.target_set.observations.diff_scope_excluded_count == 0
    assert result.diagnostics == ()


def test_upstream_diagnostics_are_carried_before_target_diagnostics(tmp_path: Path) -> None:
    project = tmp_path / "project"
    scope = project / "pkg"
    inside = write_file(scope / "inside.py")
    write_file(project / "outside.py")
    upstream = Diagnostic(
        severity=DiagnosticSeverity.WARNING,
        code="head_untracked_noop",
        message="include_untracked has no effect when diff current_state is head",
        origin_seam=OriginSeam.VCS,
        recoverability=Recoverability.RECOVERABLE,
    )

    result = normalize_diff_targets(
        collection("pkg/inside.py", "outside.py"),
        context(project, scope_root=scope),
        AnalysisConfig(),
        upstream_diagnostics=(upstream,),
    )

    assert assert_success(result) == (inside.resolve(),)
    assert result.diagnostics[0] is upstream
    assert result.diagnostics[1].code == "diff_scope_exclusion"


def test_zero_target_after_scope_filter_returns_failure_without_empty_target_set(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_file(project / "README.md")
    write_file(project / "pkg" / "generated" / "skip.py")

    result = normalize_diff_targets(
        collection("README.md", "pkg/generated/skip.py"),
        context(project),
        AnalysisConfig(ignore=("pkg/generated/**",)),
    )

    assert_zero_target_failure(result)
    assert result.observations.ignored_seed_candidate_count == 1
    assert result.observations.diff_scope_excluded_count == 0
    assert len(result.diagnostics) == 1


def test_all_scope_outside_records_exclusion_then_zero_target_failure(tmp_path: Path) -> None:
    project = tmp_path / "project"
    scope = project / "pkg"
    write_file(project / "outside.py")

    result = normalize_diff_targets(
        collection("outside.py"),
        context(project, scope_root=scope),
        AnalysisConfig(),
    )

    assert_zero_target_failure(result)
    assert result.observations.ignored_seed_candidate_count == 0
    assert result.observations.diff_scope_excluded_count == 1
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "diff_scope_exclusion",
        "diff_zero_target_after_scope_filter",
    ]
