"""Normalize diff changed files into target seed files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pyclassuml.model import (
    AnalysisConfig,
    Diagnostic,
    DiagnosticSeverity,
    ExecutionContext,
    FailureReason,
    OriginSeam,
    Recoverability,
    TargetObservations,
    TargetSet,
)
from pyclassuml.targets.ignore import apply_ignore
from pyclassuml.vcs import ChangedFileCollection


@dataclass(frozen=True)
class DiffTargetNormalization:
    """Seam-local result for diff target normalization."""

    target_set: TargetSet | None
    diagnostics: tuple[Diagnostic, ...] = ()
    observations: TargetObservations = field(default_factory=TargetObservations)


def normalize_diff_targets(
    changed_files: ChangedFileCollection,
    context: ExecutionContext,
    config: AnalysisConfig,
    upstream_diagnostics: tuple[Diagnostic, ...] = (),
) -> DiffTargetNormalization:
    """Normalize VCS changed files without re-reading Git or parsing sources."""

    diagnostics = list(upstream_diagnostics)
    candidates: list[Path] = []
    excluded_count = 0

    for entry in changed_files.entries:
        current_path = _resolve_project_relative(context.project_root, entry.current_project_relative_path)
        if not _is_in_scope(current_path, context.scope_root):
            excluded_count += 1
            continue
        if current_path.suffix == ".py":
            candidates.append(current_path)

    seed_files, ignored_count = apply_ignore(candidates, context.project_root, config.ignore)
    seed_files = sorted(set(seed_files))
    observations = TargetObservations(
        ignored_seed_candidate_count=ignored_count,
        diff_scope_excluded_count=excluded_count,
    )

    if excluded_count:
        diagnostics.append(_scope_exclusion_warning(excluded_count))

    if not seed_files:
        diagnostics.append(_zero_target_error())
        return DiffTargetNormalization(
            target_set=None,
            observations=observations,
            diagnostics=tuple(diagnostics),
        )

    return DiffTargetNormalization(
        target_set=TargetSet(
            seed_files=tuple(seed_files),
            observations=observations,
        ),
        observations=observations,
        diagnostics=tuple(diagnostics),
    )


def _resolve_project_relative(project_root: Path, relative_path: str) -> Path:
    return (project_root / relative_path).resolve()


def _is_in_scope(path: Path, scope_root: Path) -> bool:
    try:
        path.relative_to(scope_root)
    except ValueError:
        return False
    return True


def _scope_exclusion_warning(excluded_count: int) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.WARNING,
        code="diff_scope_exclusion",
        message=f"{excluded_count} changed file(s) were excluded because they are outside scope_root",
        origin_seam=OriginSeam.TARGETS,
        recoverability=Recoverability.RECOVERABLE,
        failure_reason=None,
    )


def _zero_target_error() -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="diff_zero_target_after_scope_filter",
        message="diff changed files produced no seed Python files after scope filtering",
        origin_seam=OriginSeam.TARGETS,
        recoverability=Recoverability.FATAL,
        failure_reason=FailureReason.DIFF_ZERO_TARGET_AFTER_SCOPE_FILTER,
    )
