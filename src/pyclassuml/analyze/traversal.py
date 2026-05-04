"""Dependency traversal for parsed Python modules."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path

from pyclassuml.model import (
    AnalysisConfig,
    DependencyGraph,
    Diagnostic,
    DiagnosticSeverity,
    ExecutionContext,
    FailureReason,
    OriginSeam,
    ParsedModule,
    Recoverability,
)
from pyclassuml.parse import ModuleIndex


DEFAULT_TRAVERSAL_MODULE_LIMIT = 1000


@dataclass(frozen=True)
class TraversalObservations:
    """Seam-local traversal observations for downstream summary material."""

    seed_project_relative_paths: tuple[Path, ...]
    package_stop_count: int = 0
    scope_stop_count: int = 0
    depth_stop_count: int = 0
    traversal_limit_reached: bool = False
    reachable_file_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "seed_project_relative_paths", tuple(self.seed_project_relative_paths))


@dataclass(frozen=True)
class TraversalResult:
    """Seam-local traversal result wrapper."""

    graph: DependencyGraph
    observations: TraversalObservations
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))


def traverse_dependencies(
    parsed_modules: tuple[ParsedModule, ...],
    module_index: ModuleIndex,
    context: ExecutionContext,
    config: AnalysisConfig,
    *,
    module_limit: int = DEFAULT_TRAVERSAL_MODULE_LIMIT,
) -> TraversalResult:
    """Build a deterministic reachable dependency graph from parsed module metadata."""

    parsed_module_paths = {module.module_path for module in parsed_modules}
    module_by_path = {
        module_path: module
        for module_path, module in module_index.module_by_path.items()
        if module_path in parsed_module_paths
    }
    seed_paths = tuple(sorted(module_index.seed_project_relative_paths))
    reachable: set[Path] = set()
    edges: set[tuple[Path, Path]] = set()
    frontier: deque[tuple[Path, int]] = deque()

    package_stop_count = 0
    scope_stop_count = 0
    depth_stop_count = 0
    traversal_limit_reached = False
    diagnostics: list[Diagnostic] = []

    for seed_path in seed_paths:
        if seed_path not in module_by_path or seed_path in reachable:
            continue
        if len(reachable) + 1 > module_limit:
            traversal_limit_reached = True
            diagnostics.append(_traversal_limit_diagnostic(module_limit))
            break
        reachable.add(seed_path)
        frontier.append((seed_path, 0))

    while frontier and not traversal_limit_reached:
        module_path, hop = frontier.popleft()
        module = module_by_path[module_path]

        for import_text in sorted(module.imports):
            for candidate_path in sorted(module_index.import_candidate_paths.get(import_text, ())):
                next_hop = hop + 1

                stop_reason = _stop_reason(candidate_path, next_hop, context, config)
                if stop_reason == "package":
                    package_stop_count += 1
                    continue
                if stop_reason == "scope":
                    scope_stop_count += 1
                    continue
                if stop_reason == "depth":
                    depth_stop_count += 1
                    continue

                if candidate_path not in module_by_path:
                    continue

                if candidate_path in reachable:
                    edges.add((module_path, candidate_path))
                    continue

                if len(reachable) + 1 > module_limit:
                    traversal_limit_reached = True
                    diagnostics.append(_traversal_limit_diagnostic(module_limit))
                    break

                reachable.add(candidate_path)
                edges.add((module_path, candidate_path))
                frontier.append((candidate_path, next_hop))
            if traversal_limit_reached:
                break

    graph = DependencyGraph(
        reachable_files=tuple(sorted(reachable)),
        edges=tuple(sorted(edges)),
    )
    observations = TraversalObservations(
        seed_project_relative_paths=seed_paths,
        package_stop_count=package_stop_count,
        scope_stop_count=scope_stop_count,
        depth_stop_count=depth_stop_count,
        traversal_limit_reached=traversal_limit_reached,
        reachable_file_count=len(graph.reachable_files),
    )
    return TraversalResult(graph=graph, observations=observations, diagnostics=tuple(diagnostics))


def _stop_reason(
    candidate_path: Path,
    hop: int,
    context: ExecutionContext,
    config: AnalysisConfig,
) -> str | None:
    absolute_candidate = _absolute_candidate_path(candidate_path, context.project_root)
    if not _is_relative_to(absolute_candidate, context.package_root.resolve()):
        return "package"
    if not _is_relative_to(absolute_candidate, context.scope_root.resolve()):
        return "scope"
    if config.depth is not None and hop > config.depth:
        return "depth"
    return None


def _absolute_candidate_path(candidate_path: Path, project_root: Path) -> Path:
    if candidate_path.is_absolute():
        return candidate_path.resolve()
    return (project_root / candidate_path).resolve()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _traversal_limit_diagnostic(module_limit: int) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="traversal_limit_reached",
        message=f"dependency traversal reached module limit {module_limit}",
        origin_seam=OriginSeam.ANALYZE,
        recoverability=Recoverability.FATAL,
        failure_reason=FailureReason.TRAVERSAL_LIMIT_REACHED,
    )


__all__ = [
    "DEFAULT_TRAVERSAL_MODULE_LIMIT",
    "TraversalObservations",
    "TraversalResult",
    "traverse_dependencies",
]
