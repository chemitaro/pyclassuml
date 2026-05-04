"""Class and relation selection for reachable dependency graphs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pyclassuml.analyze.traversal import TraversalObservations
from pyclassuml.model import (
    ClassId,
    DependencyGraph,
    Diagnostic,
    DiagnosticSeverity,
    OriginSeam,
    ParsedModule,
    Recoverability,
    SelectedClasses,
    SelectedRelation,
    SelectedRelations,
)
from pyclassuml.parse import ModuleIndex


@dataclass(frozen=True)
class SelectionObservations:
    """Report-facing observations for core-analysis selection output."""

    extracted_class_count: int
    extracted_relation_count: int
    warning_diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "warning_diagnostics", tuple(self.warning_diagnostics))


@dataclass(frozen=True)
class SelectionResult:
    """Selected classes, relations, observations, and diagnostics."""

    selected_classes: SelectedClasses
    selected_relations: SelectedRelations
    observations: SelectionObservations
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))


def select_classes_and_relations(
    parsed_modules: tuple[ParsedModule, ...],
    module_index: ModuleIndex,
    graph: DependencyGraph,
    traversal_observations: TraversalObservations,
) -> SelectionResult:
    """Select renderable classes and accepted module-import relations."""

    del module_index

    reachable_files = set(graph.reachable_files)
    module_by_path = {module.module_path: module for module in parsed_modules}
    selected_class_ids: set[ClassId] = set()
    relations: set[SelectedRelation] = set()
    diagnostics: list[Diagnostic] = []

    for seed_path in sorted(traversal_observations.seed_project_relative_paths):
        if seed_path not in reachable_files:
            continue
        seed_module = module_by_path.get(seed_path)
        if seed_module is None:
            continue
        selected_class_ids.update(seed_module.classes)

    for source_module_path, target_module_path in sorted(graph.edges):
        if source_module_path not in reachable_files or target_module_path not in reachable_files:
            continue

        source_classes = _classes_for_module(module_by_path, source_module_path)
        target_classes = _classes_for_module(module_by_path, target_module_path)

        if len(source_classes) != 1 or len(target_classes) != 1:
            diagnostics.append(
                _ambiguous_relation_endpoint_diagnostic(
                    source_module_path=source_module_path,
                    source_class_count=len(source_classes),
                    target_module_path=target_module_path,
                    target_class_count=len(target_classes),
                )
            )
            continue

        source_class_id = source_classes[0]
        target_class_id = target_classes[0]
        relations.add(
            SelectedRelation(
                source_class_id=source_class_id,
                target_class_id=target_class_id,
                relation_type="uses",
                evidence_kind="module_import",
            )
        )
        selected_class_ids.add(source_class_id)
        selected_class_ids.add(target_class_id)

    sorted_relations = tuple(sorted(relations, key=_relation_sort_key))
    sorted_diagnostics = tuple(sorted(diagnostics, key=_diagnostic_sort_key))
    selected_classes = SelectedClasses(class_ids=tuple(sorted(selected_class_ids)))
    selected_relations = SelectedRelations(relations=sorted_relations)
    observations = SelectionObservations(
        extracted_class_count=len(selected_classes.class_ids),
        extracted_relation_count=len(selected_relations.relations),
        warning_diagnostics=sorted_diagnostics,
    )
    return SelectionResult(
        selected_classes=selected_classes,
        selected_relations=selected_relations,
        observations=observations,
        diagnostics=sorted_diagnostics,
    )


def _classes_for_module(module_by_path: dict[Path, ParsedModule], module_path: Path) -> tuple[ClassId, ...]:
    module = module_by_path.get(module_path)
    if module is None:
        return ()
    return tuple(sorted(module.classes))


def _ambiguous_relation_endpoint_diagnostic(
    *,
    source_module_path: Path,
    source_class_count: int,
    target_module_path: Path,
    target_class_count: int,
) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.WARNING,
        code="ambiguous_relation_endpoint",
        message=(
            "module import relation endpoint is ambiguous: "
            f"{source_module_path} has {source_class_count} classes, "
            f"{target_module_path} has {target_class_count} classes"
        ),
        origin_seam=OriginSeam.ANALYZE,
        recoverability=Recoverability.RECOVERABLE,
        failure_reason=None,
    )


def _relation_sort_key(relation: SelectedRelation) -> tuple[str, str, str, str]:
    return (
        relation.source_class_id,
        relation.target_class_id,
        relation.relation_type,
        relation.evidence_kind,
    )


def _diagnostic_sort_key(diagnostic: Diagnostic) -> tuple[str, str, str, str]:
    return (
        diagnostic.code,
        diagnostic.message,
        diagnostic.severity.value,
        diagnostic.recoverability.value,
    )


__all__ = [
    "SelectedRelation",
    "SelectedRelations",
    "SelectionObservations",
    "SelectionResult",
    "select_classes_and_relations",
]
