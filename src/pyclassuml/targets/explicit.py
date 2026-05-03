"""Normalize explicit generate inputs into target seed files."""

from __future__ import annotations

from dataclasses import dataclass
from glob import glob
from pathlib import Path

from pyclassuml.model import (
    AnalysisConfig,
    CommandName,
    CommandRequest,
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

_GLOB_META = ("*", "?", "[")


@dataclass(frozen=True)
class TargetNormalization:
    """Seam-local result for explicit target normalization."""

    target_set: TargetSet | None
    diagnostics: tuple[Diagnostic, ...] = ()


class TargetNormalizationError(Exception):
    def __init__(self, code: str, message: str, failure_reason: FailureReason) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.failure_reason = failure_reason


def normalize_explicit_targets(
    request: CommandRequest,
    context: ExecutionContext,
    config: AnalysisConfig,
) -> TargetNormalization:
    """Normalize generate explicit targets without parsing or traversing dependencies."""

    try:
        raw_targets = _generate_targets(request)
        candidates = _expand_targets(raw_targets, context)
        seed_files, ignored_count = apply_ignore(candidates, context.project_root, config.ignore)
        if not seed_files:
            raise TargetNormalizationError(
                "generate_zero_target_after_normalize",
                "generate explicit targets produced no seed Python files after normalization",
                FailureReason.GENERATE_ZERO_TARGET_AFTER_NORMALIZE,
            )
        return TargetNormalization(
            target_set=TargetSet(
                seed_files=tuple(sorted(set(seed_files))),
                observations=TargetObservations(
                    ignored_seed_candidate_count=ignored_count,
                    diff_scope_excluded_count=0,
                ),
            ),
            diagnostics=(),
        )
    except TargetNormalizationError as exc:
        return TargetNormalization(
            target_set=None,
            diagnostics=(
                Diagnostic(
                    severity=DiagnosticSeverity.ERROR,
                    code=exc.code,
                    message=exc.message,
                    origin_seam=OriginSeam.TARGETS,
                    recoverability=Recoverability.FATAL,
                    failure_reason=exc.failure_reason,
                ),
            ),
        )


def _generate_targets(request: CommandRequest) -> tuple[Path | str, ...]:
    options = request.cli_options
    if getattr(options, "command", None) is not CommandName.GENERATE:
        return ()
    generate = getattr(options, "generate", None)
    return tuple(getattr(generate, "targets", ()) if generate is not None else ())


def _expand_targets(raw_targets: tuple[Path | str, ...], context: ExecutionContext) -> list[Path]:
    candidates: list[Path] = []
    for raw_target in raw_targets:
        target = Path(raw_target)
        if _has_glob_meta(target):
            for match in _glob_matches(target, context.execution_cwd):
                resolved = _resolve_target(match)
                _ensure_in_scope(resolved, context.scope_root)
                if resolved.is_file() and resolved.suffix == ".py":
                    candidates.append(resolved)
            continue

        resolved = _resolve_target(target if target.is_absolute() else context.execution_cwd / target)
        if resolved.is_file():
            _ensure_in_scope(resolved, context.scope_root)
            if resolved.suffix == ".py":
                candidates.append(resolved)
        elif resolved.is_dir():
            _ensure_in_scope(resolved, context.scope_root)
            for python_file in resolved.glob("**/*.py"):
                resolved_python_file = _resolve_target(python_file)
                _ensure_in_scope(resolved_python_file, context.scope_root)
                candidates.append(resolved_python_file)

    return candidates


def _glob_matches(target: Path, execution_cwd: Path) -> list[Path]:
    pattern = target if target.is_absolute() else execution_cwd / target
    return [Path(match) for match in glob(str(pattern), recursive=True, include_hidden=True)]


def _resolve_target(path: Path) -> Path:
    try:
        return path.resolve()
    except (OSError, RuntimeError) as exc:
        raise TargetNormalizationError(
            "generate_scope_violation",
            f"target path could not be resolved: {path}: {exc}",
            FailureReason.GENERATE_SCOPE_VIOLATION,
        ) from exc


def _ensure_in_scope(path: Path, scope_root: Path) -> None:
    try:
        path.relative_to(scope_root)
    except ValueError as exc:
        raise TargetNormalizationError(
            "generate_scope_violation",
            f"explicit target is outside scope_root: {path}",
            FailureReason.GENERATE_SCOPE_VIOLATION,
        ) from exc


def _has_glob_meta(path: Path) -> bool:
    text = str(path)
    return any(meta in text for meta in _GLOB_META)
