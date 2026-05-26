"""Class and relation selection for reachable dependency graphs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pyclassuml.analyze.traversal import TraversalObservations
from pyclassuml.model import (
    ClassId,
    ClassReference,
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


_RELATION_TYPE_PRIORITY = {
    "inherits": 0,
    "realizes": 0,
    "composition": 1,
    "aggregation": 2,
    "association": 3,
    "dependency": 4,
    "uses": 5,
}
_EVIDENCE_KIND_PRIORITY = {
    "inherits": {
        "class_base": 0,
    },
    "realizes": {
        "class_base": 0,
    },
    "composition": {
        "field_annotation": 0,
        "init_field_annotation": 1,
    },
    "aggregation": {
        "field_annotation": 0,
        "init_field_annotation": 1,
    },
    "association": {
        "field_annotation": 0,
        "init_field_annotation": 1,
        "pydantic_forward_ref": 2,
    },
    "uses": {
        "method_parameter_annotation": 0,
        "method_return_annotation": 1,
        "module_import": 2,
        "pydantic_forward_ref": 3,
    },
    "dependency": {
        "direct_class_call": 0,
        "direct_class_member_access": 1,
        "type_check_dependency": 2,
        "cast_dependency": 3,
        "local_annotation_dependency": 4,
    },
}
_DEPENDENCY_REFERENCE_KINDS = frozenset(_EVIDENCE_KIND_PRIORITY["dependency"])


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

    reachable_files = set(graph.reachable_files)
    module_by_path = {module.module_path: module for module in parsed_modules}
    selected_class_ids: set[ClassId] = set()
    relation_candidates: list[SelectedRelation] = []
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
        relation_candidates.append(
            SelectedRelation(
                source_class_id=source_class_id,
                target_class_id=target_class_id,
                relation_type="uses",
                evidence_kind="module_import",
            )
        )
        selected_class_ids.add(source_class_id)
        selected_class_ids.add(target_class_id)

    module_by_path = {module.module_path: module for module in parsed_modules}

    for reference in _dependency_relation_references(parsed_modules):
        if reference.source_class_id not in selected_class_ids:
            continue
        resolved = _resolve_dependency_relation_target(
            reference=reference,
            module_index=module_index,
            module_by_path=module_by_path,
        )
        if isinstance(resolved, Diagnostic):
            diagnostics.append(resolved)
            continue
        target_module_path = module_index.class_to_module.get(resolved)
        if target_module_path not in reachable_files:
            diagnostics.append(
                _dependency_relation_warning_diagnostic(
                    code="dependency_relation_selection_outside",
                    reference=reference,
                    candidate_class_ids=(resolved,),
                )
            )
            continue
        selected_class_ids.add(resolved)
        relation_candidates.append(
            SelectedRelation(
                source_class_id=reference.source_class_id,
                target_class_id=resolved,
                relation_type="dependency",
                evidence_kind=reference.reference_kind,
            )
        )

    protocol_class_ids = _selected_protocol_class_ids(
        parsed_modules=parsed_modules,
        module_index=module_index,
        selected_class_ids=selected_class_ids,
    )

    for reference in _typed_relation_references(parsed_modules):
        relation_type = _relation_type_for_reference(reference)
        if relation_type is None or relation_type == "dependency":
            continue
        if reference.source_class_id not in selected_class_ids:
            continue
        if _is_qualified_protocol_marker_base_reference(reference):
            continue
        if _is_imported_bare_protocol_marker_base_reference(
            reference=reference,
            module_index=module_index,
            module_by_path=module_by_path,
        ):
            continue
        resolved = _resolve_typed_relation_target(
            reference=reference,
            module_index=module_index,
            selected_class_ids=selected_class_ids,
        )
        if isinstance(resolved, Diagnostic):
            diagnostics.append(resolved)
            continue
        relation_candidates.append(
            SelectedRelation(
                source_class_id=reference.source_class_id,
                target_class_id=resolved,
                relation_type=_realized_relation_type(relation_type, resolved, protocol_class_ids),
                evidence_kind=reference.reference_kind,
            )
        )

    sorted_relations = tuple(sorted(_normalize_relations(relation_candidates), key=_relation_sort_key))
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


def _typed_relation_references(parsed_modules: tuple[ParsedModule, ...]) -> tuple[ClassReference, ...]:
    return tuple(reference for module in parsed_modules for reference in module.class_references)


def _dependency_relation_references(parsed_modules: tuple[ParsedModule, ...]) -> tuple[ClassReference, ...]:
    return tuple(
        reference
        for module in parsed_modules
        for reference in module.class_references
        if reference.reference_kind in _DEPENDENCY_REFERENCE_KINDS
    )


def _selected_protocol_class_ids(
    *,
    parsed_modules: tuple[ParsedModule, ...],
    module_index: ModuleIndex,
    selected_class_ids: set[ClassId],
) -> frozenset[ClassId]:
    protocol_class_ids: set[ClassId] = set()
    module_by_path = {module.module_path: module for module in parsed_modules}
    for reference in _typed_relation_references(parsed_modules):
        if reference.source_class_id not in selected_class_ids:
            continue
        if _is_qualified_protocol_marker_base_reference(reference):
            protocol_class_ids.add(reference.source_class_id)
            continue
        if not _is_bare_protocol_marker_base_reference(reference):
            continue
        if _is_imported_bare_protocol_marker_base_reference(
            reference=reference,
            module_index=module_index,
            module_by_path=module_by_path,
        ):
            protocol_class_ids.add(reference.source_class_id)
            continue
    return frozenset(protocol_class_ids)


def _relation_type_for_reference(reference: ClassReference) -> str | None:
    if reference.reference_kind == "class_base" and reference.reference_owner == "base":
        return "inherits"
    if reference.reference_kind in {"field_annotation", "init_field_annotation"}:
        if reference.annotation_shape == "direct":
            return "composition"
        if reference.annotation_shape in {"optional", "union", "collection", "mapping_value"}:
            return "aggregation"
        return "association"
    if reference.reference_kind in {"method_parameter_annotation", "method_return_annotation"}:
        return "uses"
    if reference.reference_kind in _DEPENDENCY_REFERENCE_KINDS:
        return "dependency"
    return None


def _realized_relation_type(
    relation_type: str,
    target_class_id: ClassId,
    protocol_class_ids: frozenset[ClassId],
) -> str:
    if relation_type == "inherits" and target_class_id in protocol_class_ids:
        return "realizes"
    return relation_type


def _is_qualified_protocol_marker_base_reference(reference: ClassReference) -> bool:
    return (
        reference.reference_kind == "class_base"
        and reference.reference_owner == "base"
        and reference.target_name in {"typing.Protocol", "typing_extensions.Protocol"}
    )


def _is_bare_protocol_marker_base_reference(reference: ClassReference) -> bool:
    return (
        reference.reference_kind == "class_base"
        and reference.reference_owner == "base"
        and reference.target_name == "Protocol"
    )


def _is_imported_bare_protocol_marker_base_reference(
    *,
    reference: ClassReference,
    module_index: ModuleIndex,
    module_by_path: dict[Path, ParsedModule],
) -> bool:
    if not _is_bare_protocol_marker_base_reference(reference):
        return False
    source_module_path = module_index.class_to_module.get(reference.source_class_id)
    if source_module_path is None:
        return False
    source_module = module_by_path.get(source_module_path)
    if source_module is None:
        return False
    return _imports_protocol_marker(source_module.imports)


def _imports_protocol_marker(imports: tuple[str, ...]) -> bool:
    return any(
        _imports_name_from(import_text, module_name="typing", imported_name="Protocol")
        or _imports_name_from(import_text, module_name="typing_extensions", imported_name="Protocol")
        for import_text in imports
    )


def _imports_name_from(import_text: str, *, module_name: str, imported_name: str) -> bool:
    prefix = f"from {module_name} import "
    if not import_text.startswith(prefix):
        return False
    return any(
        _imports_name_as_local_name(name, imported_name)
        for name in import_text.removeprefix(prefix).split(",")
    )


def _imports_name_as_local_name(imported_text: str, expected_name: str) -> bool:
    parts = tuple(part.strip() for part in imported_text.split(" as ", maxsplit=1))
    if len(parts) == 2:
        imported_name, local_name = parts
        return imported_name == expected_name and local_name == expected_name
    return parts[0] == expected_name


def _resolve_typed_relation_target(
    *,
    reference: ClassReference,
    module_index: ModuleIndex,
    selected_class_ids: set[ClassId],
) -> ClassId | Diagnostic:
    candidates = _target_candidates(
        source_class_id=reference.source_class_id,
        target_name=reference.target_name,
        module_index=module_index,
    )
    if len(candidates) == 0:
        return _typed_relation_warning_diagnostic(
            code="typed_relation_unresolved",
            reference=reference,
        )
    if len(candidates) > 1:
        return _typed_relation_warning_diagnostic(
            code="typed_relation_ambiguous",
            reference=reference,
            candidate_class_ids=candidates,
        )

    target_class_id = candidates[0]
    if target_class_id not in selected_class_ids:
        return _typed_relation_warning_diagnostic(
            code="typed_relation_selection_outside",
            reference=reference,
            candidate_class_ids=(target_class_id,),
        )
    return target_class_id


def _resolve_dependency_relation_target(
    *,
    reference: ClassReference,
    module_index: ModuleIndex,
    module_by_path: dict[Path, ParsedModule],
) -> ClassId | Diagnostic:
    candidates = _dependency_target_candidates(
        reference=reference,
        module_index=module_index,
        module_by_path=module_by_path,
    )
    if len(candidates) == 0:
        return _dependency_relation_warning_diagnostic(
            code="dependency_relation_unresolved",
            reference=reference,
        )
    if len(candidates) > 1:
        return _dependency_relation_warning_diagnostic(
            code="dependency_relation_ambiguous",
            reference=reference,
            candidate_class_ids=candidates,
        )
    return candidates[0]


def _dependency_target_candidates(
    *,
    reference: ClassReference,
    module_index: ModuleIndex,
    module_by_path: dict[Path, ParsedModule],
) -> tuple[ClassId, ...]:
    candidates: list[ClassId] = []
    candidates.extend(
        _direct_dependency_target_candidates(
            source_class_id=reference.source_class_id,
            target_name=reference.target_name,
            module_index=module_index,
        )
    )
    source_module_path = module_index.class_to_module.get(reference.source_class_id)
    source_module = module_by_path.get(source_module_path) if source_module_path is not None else None
    if source_module is not None:
        candidates.extend(
            _from_import_dependency_target_candidates(
                target_name=reference.target_name,
                source_module=source_module,
                module_index=module_index,
                module_by_path=module_by_path,
            )
        )
        candidates.extend(
            _module_import_dependency_target_candidates(
                target_name=reference.target_name,
                source_module=source_module,
                module_index=module_index,
                module_by_path=module_by_path,
            )
        )
    return tuple(sorted(set(candidates)))


def _direct_dependency_target_candidates(
    *,
    source_class_id: ClassId,
    target_name: str,
    module_index: ModuleIndex,
) -> tuple[ClassId, ...]:
    if target_name in module_index.class_to_module:
        return (target_name,)

    source_module = module_index.class_to_module.get(source_class_id)
    if source_module is None or "." in target_name:
        return ()
    return tuple(
        class_id
        for class_id in sorted(module_index.class_to_module)
        if module_index.class_to_module.get(class_id) == source_module
        and _short_class_name(class_id) == target_name
    )


def _from_import_dependency_target_candidates(
    *,
    target_name: str,
    source_module: ParsedModule,
    module_index: ModuleIndex,
    module_by_path: dict[Path, ParsedModule],
) -> tuple[ClassId, ...]:
    if "." in target_name:
        return ()

    candidates: list[ClassId] = []
    for import_text in source_module.imports:
        imported_name = _from_import_original_name(import_text, local_name=target_name)
        if imported_name is None:
            continue
        candidates.extend(
            _class_ids_named_in_import_candidates(
                import_text=import_text,
                class_name=imported_name,
                module_index=module_index,
                module_by_path=module_by_path,
            )
        )
    return tuple(candidates)


def _module_import_dependency_target_candidates(
    *,
    target_name: str,
    source_module: ParsedModule,
    module_index: ModuleIndex,
    module_by_path: dict[Path, ParsedModule],
) -> tuple[ClassId, ...]:
    parts = tuple(part for part in target_name.split(".") if part)
    if len(parts) < 2:
        return ()

    candidates: list[ClassId] = []
    for split_at in range(1, len(parts)):
        access_prefix = ".".join(parts[:split_at])
        class_name = ".".join(parts[split_at:])
        for import_text in source_module.imports:
            module_import = _module_import_parts(import_text)
            if module_import is None:
                continue
            module_name, local_name = module_import
            if access_prefix not in {local_name, module_name}:
                continue
            candidates.extend(
                _class_ids_named_in_import_candidates(
                    import_text=import_text,
                    class_name=class_name,
                    module_index=module_index,
                    module_by_path=module_by_path,
                )
            )
    return tuple(candidates)


def _class_ids_named_in_import_candidates(
    *,
    import_text: str,
    class_name: str,
    module_index: ModuleIndex,
    module_by_path: dict[Path, ParsedModule],
) -> tuple[ClassId, ...]:
    candidates: list[ClassId] = []
    for module_path in module_index.import_candidate_paths.get(import_text, ()):
        module = module_by_path.get(module_path)
        if module is None:
            continue
        candidates.extend(class_id for class_id in module.classes if _short_class_name(class_id) == class_name)
    return tuple(candidates)


def _from_import_original_name(import_text: str, *, local_name: str) -> str | None:
    if not import_text.startswith("from ") or " import " not in import_text:
        return None
    imported_text = import_text.split(" import ", maxsplit=1)[1]
    for part in imported_text.split(","):
        imported_name, imported_local_name = _imported_name_and_local_name(part)
        if imported_local_name == local_name:
            return imported_name
    return None


def _module_import_parts(import_text: str) -> tuple[str, str] | None:
    if import_text.startswith("from ") or " import " in import_text:
        return None
    import_body = import_text.removeprefix("import ").strip()
    if not import_body:
        return None
    module_name, local_name = _imported_name_and_local_name(import_body)
    if local_name == module_name:
        local_name = module_name.split(".", maxsplit=1)[0]
    return module_name, local_name


def _imported_name_and_local_name(imported_text: str) -> tuple[str, str]:
    parts = tuple(part.strip() for part in imported_text.split(" as ", maxsplit=1))
    if len(parts) == 2:
        return parts[0], parts[1]
    return parts[0], parts[0]


def _target_candidates(
    *,
    source_class_id: ClassId,
    target_name: str,
    module_index: ModuleIndex,
) -> tuple[ClassId, ...]:
    all_class_ids = tuple(sorted(module_index.class_to_module))
    if target_name in module_index.class_to_module:
        return (target_name,)

    module_qualified_candidates = _prefer_same_module_candidate(
        candidates=tuple(
            class_id
            for class_id in all_class_ids
            if any(
                class_id == candidate or class_id.endswith(f"/{candidate}")
                for candidate in _module_qualified_target_candidates(target_name)
            )
        ),
        source_class_id=source_class_id,
        module_index=module_index,
    )
    if module_qualified_candidates:
        return module_qualified_candidates

    short_name_candidates = _prefer_same_module_candidate(
        candidates=tuple(class_id for class_id in all_class_ids if _short_class_name(class_id) == target_name),
        source_class_id=source_class_id,
        module_index=module_index,
    )
    return short_name_candidates


def _prefer_same_module_candidate(
    *,
    candidates: tuple[ClassId, ...],
    source_class_id: ClassId,
    module_index: ModuleIndex,
) -> tuple[ClassId, ...]:
    if len(candidates) <= 1:
        return candidates
    source_module = module_index.class_to_module.get(source_class_id)
    same_module_candidates = tuple(
        candidate for candidate in candidates if module_index.class_to_module.get(candidate) == source_module
    )
    if len(same_module_candidates) == 1:
        return same_module_candidates
    return candidates


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


def _typed_relation_warning_diagnostic(
    *,
    code: str,
    reference: ClassReference,
    candidate_class_ids: tuple[ClassId, ...] = (),
) -> Diagnostic:
    candidate_message = ""
    if candidate_class_ids:
        candidate_message = f"; candidates={','.join(candidate_class_ids)}"
    return Diagnostic(
        severity=DiagnosticSeverity.WARNING,
        code=code,
        message=(
            "typed relation reference could not be converted to a selected class relation: "
            f"source_class_id={reference.source_class_id}; "
            f"target_name={reference.target_name}; "
            f"reference_kind={reference.reference_kind}; "
            f"reference_owner={reference.reference_owner}"
            f"{candidate_message}"
        ),
        origin_seam=OriginSeam.ANALYZE,
        recoverability=Recoverability.RECOVERABLE,
        failure_reason=None,
    )


def _dependency_relation_warning_diagnostic(
    *,
    code: str,
    reference: ClassReference,
    candidate_class_ids: tuple[ClassId, ...] = (),
) -> Diagnostic:
    candidate_message = ""
    if candidate_class_ids:
        candidate_message = f"; candidates={','.join(candidate_class_ids)}"
    return Diagnostic(
        severity=DiagnosticSeverity.WARNING,
        code=code,
        message=(
            "dependency reference could not be converted to a selected class relation: "
            f"source_class_id={reference.source_class_id}; "
            f"target_name={reference.target_name}; "
            f"reference_kind={reference.reference_kind}; "
            f"reference_owner={reference.reference_owner}"
            f"{candidate_message}"
        ),
        origin_seam=OriginSeam.ANALYZE,
        recoverability=Recoverability.RECOVERABLE,
        failure_reason=None,
    )


def _normalize_relations(relations: list[SelectedRelation]) -> tuple[SelectedRelation, ...]:
    by_triple: dict[tuple[ClassId, ClassId, str], SelectedRelation] = {}
    for relation in relations:
        if _is_self_dashed_relation(relation):
            continue
        key = (relation.source_class_id, relation.target_class_id, relation.relation_type)
        current = by_triple.get(key)
        if current is None or _evidence_kind_rank(relation) < _evidence_kind_rank(current):
            by_triple[key] = relation

    by_endpoint: dict[tuple[ClassId, ClassId], SelectedRelation] = {}
    for relation in by_triple.values():
        key = (relation.source_class_id, relation.target_class_id)
        current = by_endpoint.get(key)
        if current is None or _relation_type_rank(relation) < _relation_type_rank(current):
            by_endpoint[key] = relation
    return tuple(by_endpoint.values())


def _is_self_dashed_relation(relation: SelectedRelation) -> bool:
    return (
        relation.relation_type in {"dependency", "uses"}
        and relation.source_class_id == relation.target_class_id
    )


def _relation_type_rank(relation: SelectedRelation) -> int:
    return _RELATION_TYPE_PRIORITY.get(relation.relation_type, len(_RELATION_TYPE_PRIORITY))


def _evidence_kind_rank(relation: SelectedRelation) -> int:
    return _EVIDENCE_KIND_PRIORITY.get(relation.relation_type, {}).get(
        relation.evidence_kind,
        len(_EVIDENCE_KIND_PRIORITY.get(relation.relation_type, {})),
    )


def _relation_sort_key(relation: SelectedRelation) -> tuple[str, str, int, int, str, str]:
    return (
        relation.source_class_id,
        relation.target_class_id,
        _relation_type_rank(relation),
        _evidence_kind_rank(relation),
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
