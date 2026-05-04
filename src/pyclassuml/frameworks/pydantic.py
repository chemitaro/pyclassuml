"""Pydantic-specific relation enrichment from framework-neutral parse evidence."""

from __future__ import annotations

from dataclasses import dataclass

from pyclassuml.analyze.selection import SelectedRelation, SelectedRelations
from pyclassuml.model import (
    ClassId,
    Diagnostic,
    DiagnosticSeverity,
    OriginSeam,
    ParsedModule,
    Recoverability,
    SelectedClasses,
)
from pyclassuml.parse import ModuleIndex


@dataclass(frozen=True)
class PydanticEnrichmentHints:
    """Seam-local additions produced by the Pydantic framework support."""

    added_relations: tuple[SelectedRelation, ...] = ()
    warning_diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "added_relations", tuple(self.added_relations))
        object.__setattr__(self, "warning_diagnostics", tuple(self.warning_diagnostics))


def extract_pydantic_enrichment_hints(
    parsed_modules: tuple[ParsedModule, ...],
    module_index: ModuleIndex,
    selected_classes: SelectedClasses,
    selected_relations: SelectedRelations,
) -> PydanticEnrichmentHints:
    """Extract Pydantic forward-reference hints without mutating core selection."""

    selected_class_ids = set(selected_classes.class_ids)
    eligible_source_class_ids = _pydantic_eligible_source_class_ids(parsed_modules)
    seen_relation_triples = {
        (relation.source_class_id, relation.target_class_id, relation.relation_type)
        for relation in selected_relations.relations
    }
    added_relations: set[SelectedRelation] = set()
    warning_diagnostics: set[Diagnostic] = set()

    for reference in sorted(
        (reference for module in parsed_modules for reference in module.class_references),
        key=lambda item: (
            item.source_class_id,
            item.target_name,
            item.reference_kind,
            item.reference_owner,
        ),
    ):
        if reference.reference_kind != "annotation_string":
            continue
        if reference.reference_owner == "ClassVar":
            continue
        if reference.source_class_id not in eligible_source_class_ids:
            continue
        if reference.source_class_id not in selected_class_ids:
            continue

        target_class_id, diagnostic_code = _resolve_target(
            target_name=reference.target_name,
            module_index=module_index,
            selected_class_ids=selected_class_ids,
        )
        if diagnostic_code is not None:
            warning_diagnostics.add(
                _warning_diagnostic(
                    code=diagnostic_code,
                    source_class_id=reference.source_class_id,
                    target_name=reference.target_name,
                    reference_owner=reference.reference_owner,
                )
            )
            continue

        if target_class_id is None:
            continue
        relation = SelectedRelation(
            source_class_id=reference.source_class_id,
            target_class_id=target_class_id,
            relation_type="uses",
            evidence_kind="pydantic_forward_ref",
        )
        relation_triple = (relation.source_class_id, relation.target_class_id, relation.relation_type)
        if relation_triple not in seen_relation_triples:
            added_relations.add(relation)
            seen_relation_triples.add(relation_triple)

    return PydanticEnrichmentHints(
        added_relations=tuple(sorted(added_relations, key=_relation_sort_key)),
        warning_diagnostics=tuple(sorted(warning_diagnostics, key=_diagnostic_sort_key)),
    )


def _pydantic_eligible_source_class_ids(parsed_modules: tuple[ParsedModule, ...]) -> set[ClassId]:
    return {
        reference.source_class_id
        for module in parsed_modules
        for reference in module.class_references
        if (
            reference.reference_kind == "class_base"
            and reference.reference_owner == "base"
            and reference.target_name in {"BaseModel", "pydantic.BaseModel"}
        )
    }


def _resolve_target(
    *,
    target_name: str,
    module_index: ModuleIndex,
    selected_class_ids: set[ClassId],
) -> tuple[ClassId | None, str | None]:
    candidates = tuple(
        sorted(
            class_id
            for class_id in module_index.class_to_module
            if _matches_target_name(class_id=class_id, target_name=target_name)
        )
    )
    if len(candidates) == 0:
        return None, "pydantic_forward_ref_unresolved"
    if len(candidates) > 1:
        return None, "pydantic_forward_ref_ambiguous"

    target_class_id = candidates[0]
    if target_class_id not in selected_class_ids:
        return None, "pydantic_forward_ref_selection_outside"
    return target_class_id, None


def _matches_target_name(*, class_id: ClassId, target_name: str) -> bool:
    if class_id == target_name:
        return True
    if any(
        class_id == candidate or class_id.endswith(f"/{candidate}")
        for candidate in _module_qualified_target_candidates(target_name)
    ):
        return True
    if class_id.endswith(f":{target_name}") or class_id.endswith(f".{target_name}"):
        return True
    return _short_class_name(class_id) == target_name


def _module_qualified_target_candidates(target_name: str) -> tuple[str, ...]:
    parts = tuple(part for part in target_name.split(".") if part)
    if len(parts) < 2:
        return ()
    candidates = {
        f"{'/'.join(parts[:split_at])}.py:{'.'.join(parts[split_at:])}"
        for split_at in range(1, len(parts))
    }
    return tuple(sorted(candidates))


def _short_class_name(class_id: ClassId) -> str:
    return class_id.rsplit(":", 1)[-1].rsplit(".", 1)[-1]


def _warning_diagnostic(
    *,
    code: str,
    source_class_id: ClassId,
    target_name: str,
    reference_owner: str,
) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.WARNING,
        code=code,
        message=(
            "Pydantic forward reference could not be converted to a selected class relation: "
            f"{source_class_id} -> {target_name} via {reference_owner}"
        ),
        origin_seam=OriginSeam.FRAMEWORKS,
        recoverability=Recoverability.DEGRADED_OUTPUT,
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
    "PydanticEnrichmentHints",
    "extract_pydantic_enrichment_hints",
]
