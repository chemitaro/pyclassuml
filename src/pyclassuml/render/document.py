"""Pure UML document rendering from selected model contracts."""

from __future__ import annotations

from dataclasses import dataclass

from pyclassuml.frameworks.pydantic import PydanticEnrichmentHints
from pyclassuml.frameworks.sqlalchemy import SqlalchemyEnrichmentHints
from pyclassuml.model import (
    ClassMember,
    ClassId,
    Diagnostic,
    DiagnosticSeverity,
    DiagramModel,
    FailureReason,
    MemberParameter,
    OriginSeam,
    ParsedModule,
    PlantUmlText,
    Recoverability,
    RelationType,
    RenderFailureSignal,
    RenderReadyModel,
    SelectedClasses,
    SelectedRelation,
    SelectedRelations,
)
from pyclassuml.parse import ModuleIndex


@dataclass(frozen=True)
class RenderDocumentResult:
    """Seam-local discriminated result for render success or failure."""

    diagram_model: DiagramModel | None = None
    plantuml_text: PlantUmlText | None = None
    failure_signal: RenderFailureSignal | None = None

    def __post_init__(self) -> None:
        success_present = self.diagram_model is not None or self.plantuml_text is not None
        failure_present = self.failure_signal is not None
        if success_present == failure_present:
            raise ValueError("result must contain either success output or failure signal")
        if success_present and (self.diagram_model is None or self.plantuml_text is None):
            raise ValueError("success result requires diagram_model and plantuml_text")


def compose_render_ready_model(
    *,
    parsed_modules: tuple[ParsedModule, ...],
    module_index: ModuleIndex,
    selected_classes: SelectedClasses,
    selected_relations: SelectedRelations,
    sqlalchemy_hints: SqlalchemyEnrichmentHints,
    pydantic_hints: PydanticEnrichmentHints,
    class_decorations: tuple[tuple[ClassId, str], ...] = (),
) -> RenderReadyModel:
    """Merge analyze selection and framework hints into a deterministic render model."""

    parsed_class_ids = {
        class_id
        for parsed_module in parsed_modules
        for class_id in parsed_module.classes
    }
    indexed_class_ids = set(module_index.class_to_module)
    known_class_ids = parsed_class_ids & indexed_class_ids
    diagnostics = [
        diagnostic
        for parsed_module in sorted(parsed_modules, key=lambda module: module.module_path.as_posix())
        for diagnostic in parsed_module.diagnostics
    ]
    diagnostics.extend(sorted(sqlalchemy_hints.warning_diagnostics, key=_diagnostic_sort_key))
    diagnostics.extend(sorted(pydantic_hints.warning_diagnostics, key=_diagnostic_sort_key))

    valid_classes: list[ClassId] = []
    for class_id in sorted(selected_classes.class_ids):
        if class_id not in known_class_ids:
            diagnostics.append(_selected_class_missing_diagnostic(class_id))
            continue
        valid_classes.append(class_id)

    relation_by_triple: dict[tuple[ClassId, ClassId, RelationType], None] = {}
    for selected_relation in _all_relations(selected_relations, sqlalchemy_hints, pydantic_hints):
        relation_by_triple[_relation_triple(selected_relation)] = None

    relations = tuple(sorted(relation_by_triple))
    grouping_keys = tuple(sorted({_module_path_from_class_id(class_id) for class_id in valid_classes}))

    valid_class_ids = set(valid_classes)
    auto_class_decorations = tuple(
        (class_id, "Protocol")
        for class_id in valid_classes
        if _is_protocol_class(class_id, parsed_modules, module_index)
    )
    external_class_decorations = tuple(
        (class_id, decoration)
        for class_id, decoration in class_decorations
        if class_id in valid_class_ids
    )
    merged_class_decorations = tuple(sorted({*auto_class_decorations, *external_class_decorations}))
    members = tuple(
        sorted(
            (
                member
                for parsed_module in parsed_modules
                for member in parsed_module.members
                if member.owner_class_id in valid_class_ids
            ),
            key=_member_sort_key,
        )
    )

    return RenderReadyModel(
        classes=tuple(valid_classes),
        members=members,
        relations=relations,
        class_decorations=merged_class_decorations,
        grouping_keys=grouping_keys,
        diagnostics=tuple(diagnostics),
    )


def build_diagram_model(render_ready_model: RenderReadyModel) -> DiagramModel:
    """Build deterministic diagram DTOs for renderable class and relation inventory."""

    rendered_classes = tuple(sorted(render_ready_model.classes))
    aliases = tuple(
        (class_id, f"c{index:03d}")
        for index, class_id in enumerate(rendered_classes, start=1)
    )
    return DiagramModel(
        containers=tuple(sorted(render_ready_model.grouping_keys)),
        rendered_classes=rendered_classes,
        rendered_relations=tuple(sorted(render_ready_model.relations)),
        aliases=aliases,
    )


def render_plantuml_text(
    render_ready_model: RenderReadyModel,
    diagram_model: DiagramModel,
) -> PlantUmlText:
    """Serialize a diagram model into deterministic PlantUML text."""

    alias_by_class_id = dict(diagram_model.aliases)
    members_by_class_id = _members_by_class_id(render_ready_model.members)
    decorations_by_class_id = _decorations_by_class_id(render_ready_model.class_decorations)
    lines = ["@startuml"]
    lines.extend(_diff_style_lines(render_ready_model.class_decorations))
    for container in diagram_model.containers:
        lines.append(f'package "{_escape_plantuml(container)}" {{')
        for class_id in diagram_model.rendered_classes:
            if _module_path_from_class_id(class_id) != container:
                continue
            label = _class_label(class_id)
            stereotype = _class_stereotype(decorations_by_class_id.get(class_id, ()))
            alias = alias_by_class_id[class_id]
            member_lines = members_by_class_id.get(class_id, ())
            if not member_lines:
                lines.append(f'  class "{_escape_plantuml(label)}" as {alias}{stereotype}')
                continue
            lines.append(f'  class "{_escape_plantuml(label)}" as {alias}{stereotype} {{')
            lines.extend(f"    {line}" for line in member_lines)
            lines.append("  }")
        lines.append("}")

    for source_class_id, target_class_id, relation_type in diagram_model.rendered_relations:
        source_alias = alias_by_class_id[source_class_id]
        target_alias = alias_by_class_id[target_class_id]
        lines.append(f"{source_alias} {_relation_arrow(relation_type)} {target_alias}")

    lines.append("@enduml")
    return PlantUmlText("\n".join(lines))


def render_uml_document(
    *,
    parsed_modules: tuple[ParsedModule, ...],
    module_index: ModuleIndex,
    selected_classes: SelectedClasses,
    selected_relations: SelectedRelations,
    sqlalchemy_hints: SqlalchemyEnrichmentHints,
    pydantic_hints: PydanticEnrichmentHints,
    class_decorations: tuple[tuple[ClassId, str], ...] = (),
) -> RenderDocumentResult:
    """Render success DTOs or a failure handoff without side effects."""

    render_ready_model = compose_render_ready_model(
        parsed_modules=parsed_modules,
        module_index=module_index,
        selected_classes=selected_classes,
        selected_relations=selected_relations,
        sqlalchemy_hints=sqlalchemy_hints,
        pydantic_hints=pydantic_hints,
        class_decorations=class_decorations,
    )
    diagnostics = list(render_ready_model.diagnostics)
    diagnostics.extend(_relation_endpoint_diagnostics(render_ready_model))
    failure = _failure_signal_if_unbuildable(render_ready_model, tuple(diagnostics))
    if failure is not None:
        return RenderDocumentResult(failure_signal=failure)

    diagram_model = build_diagram_model(render_ready_model)
    plantuml_text = render_plantuml_text(render_ready_model, diagram_model)
    return RenderDocumentResult(diagram_model=diagram_model, plantuml_text=plantuml_text)


def _all_relations(
    selected_relations: SelectedRelations,
    sqlalchemy_hints: SqlalchemyEnrichmentHints,
    pydantic_hints: PydanticEnrichmentHints,
) -> tuple[SelectedRelation, ...]:
    return (
        *selected_relations.relations,
        *sqlalchemy_hints.added_relations,
        *pydantic_hints.added_relations,
    )


def _relation_triple(relation: SelectedRelation) -> tuple[ClassId, ClassId, RelationType]:
    return (relation.source_class_id, relation.target_class_id, relation.relation_type)


def _member_sort_key(member: ClassMember) -> tuple[ClassId, int, str, str]:
    return (member.owner_class_id, member.source_order, member.kind, member.name)


def _diagnostic_sort_key(diagnostic: Diagnostic) -> tuple[str, str, str, str]:
    return (
        diagnostic.code,
        diagnostic.message,
        diagnostic.severity.value,
        diagnostic.recoverability.value,
    )


def _is_protocol_class(class_id: ClassId, parsed_modules: tuple[ParsedModule, ...], module_index: ModuleIndex) -> bool:
    module_by_path = {parsed_module.module_path: parsed_module for parsed_module in parsed_modules}
    return any(
        reference.source_class_id == class_id
        and reference.reference_kind == "class_base"
        and reference.reference_owner == "base"
        and _is_protocol_marker_base_reference(
            reference=reference,
            module_index=module_index,
            module_by_path=module_by_path,
        )
        for parsed_module in parsed_modules
        for reference in parsed_module.class_references
    )


def _is_protocol_marker_base_reference(
    *,
    reference: ClassReference,
    module_index: ModuleIndex,
    module_by_path: dict[Path, ParsedModule],
) -> bool:
    if reference.target_name in {"typing.Protocol", "typing_extensions.Protocol"}:
        return True
    if reference.target_name != "Protocol":
        return False
    if _source_module_imports_protocol_marker(reference, module_index, module_by_path):
        return True
    return False


def _source_module_imports_protocol_marker(
    reference: ClassReference,
    module_index: ModuleIndex,
    module_by_path: dict[Path, ParsedModule],
) -> bool:
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


def _failure_signal_if_unbuildable(
    render_ready_model: RenderReadyModel,
    diagnostics: tuple[Diagnostic, ...],
) -> RenderFailureSignal | None:
    failure_diagnostics = tuple(
        diagnostic
        for diagnostic in diagnostics
        if diagnostic.origin_seam is OriginSeam.RENDER
    )
    if render_ready_model.classes and not failure_diagnostics:
        return None

    if render_ready_model.classes or failure_diagnostics:
        return RenderFailureSignal(
            failure_reason=FailureReason.DIAGRAM_UNBUILDABLE_AFTER_RECOVERY,
            diagnostics=diagnostics,
            class_count=len(render_ready_model.classes),
            relation_count=len(render_ready_model.relations),
            partial_diagram_present=bool(render_ready_model.classes),
        )

    return RenderFailureSignal(
        failure_reason=FailureReason.DIAGRAM_UNBUILDABLE_AFTER_RECOVERY,
        diagnostics=diagnostics,
        class_count=0,
        relation_count=len(render_ready_model.relations),
        partial_diagram_present=False,
    )


def _relation_endpoint_diagnostics(render_ready_model: RenderReadyModel) -> tuple[Diagnostic, ...]:
    class_ids = set(render_ready_model.classes)
    diagnostics: list[Diagnostic] = []
    for source_class_id, target_class_id, relation_type in render_ready_model.relations:
        missing = tuple(
            class_id
            for class_id in (source_class_id, target_class_id)
            if class_id not in class_ids
        )
        if not missing:
            continue
        diagnostics.append(
            Diagnostic(
                severity=DiagnosticSeverity.ERROR,
                code="render_relation_endpoint_missing",
                message=(
                    "relation endpoint is missing from renderable classes: "
                    f"{source_class_id} -> {target_class_id} ({relation_type}); "
                    f"missing={', '.join(missing)}"
                ),
                origin_seam=OriginSeam.RENDER,
                recoverability=Recoverability.DEGRADED_OUTPUT,
                failure_reason=FailureReason.DIAGRAM_UNBUILDABLE_AFTER_RECOVERY,
            )
        )
    return tuple(diagnostics)


def _selected_class_missing_diagnostic(class_id: ClassId) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="render_selected_class_missing",
        message=f"selected class id is missing from parsed modules or module index: {class_id}",
        origin_seam=OriginSeam.RENDER,
        recoverability=Recoverability.DEGRADED_OUTPUT,
        failure_reason=FailureReason.DIAGRAM_UNBUILDABLE_AFTER_RECOVERY,
    )


def _module_path_from_class_id(class_id: ClassId) -> str:
    return class_id.split(":", 1)[0]


def _class_label(class_id: ClassId) -> str:
    return class_id.rsplit(":", 1)[-1].rsplit(".", 1)[-1]


def _members_by_class_id(members: tuple[ClassMember, ...]) -> dict[ClassId, tuple[str, ...]]:
    grouped: dict[ClassId, list[str]] = {}
    for member in sorted(members, key=_member_sort_key):
        grouped.setdefault(member.owner_class_id, []).append(_member_line(member))
    return {class_id: tuple(lines) for class_id, lines in grouped.items()}


def _decorations_by_class_id(class_decorations: tuple[tuple[ClassId, str], ...]) -> dict[ClassId, tuple[str, ...]]:
    grouped: dict[ClassId, list[str]] = {}
    for class_id, decoration in sorted(class_decorations):
        grouped.setdefault(class_id, []).append(decoration)
    return {class_id: tuple(decorations) for class_id, decorations in grouped.items()}


def _class_stereotype(decorations: tuple[str, ...]) -> str:
    if not decorations:
        return ""
    return " " + " ".join(f"<<{_escape_plantuml(decoration)}>>" for decoration in decorations)


def _diff_style_lines(class_decorations: tuple[tuple[ClassId, str], ...]) -> list[str]:
    decorations = {decoration for _, decoration in class_decorations}
    supported_diff_decorations = ("DiffAdded", "DiffChanged")
    active_diff_decorations = tuple(
        decoration for decoration in supported_diff_decorations if decoration in decorations
    )
    if not active_diff_decorations:
        return []
    color_by_decoration = {
        "DiffAdded": ("#dff3ff", "#4b9ecf"),
        "DiffChanged": ("#dff5df", "#4f9d5d"),
    }
    lines = ["skinparam class {"]
    for decoration in active_diff_decorations:
        background_color, border_color = color_by_decoration[decoration]
        lines.append(f"  BackgroundColor<<{decoration}>> {background_color}")
        lines.append(f"  BorderColor<<{decoration}>> {border_color}")
    lines.append("}")
    return lines


def _member_line(member: ClassMember) -> str:
    if member.kind == "method":
        return _method_line(member)
    return _field_line(member)


def _field_line(member: ClassMember) -> str:
    prefix = _member_prefix(member)
    name = _escape_plantuml(_normalize_member_text(member.name))
    if member.annotation_text is None:
        return f"{prefix}{name}"
    annotation = _escape_plantuml(_normalize_member_text(member.annotation_text))
    return f"{prefix}{name}: {annotation}"


def _method_line(member: ClassMember) -> str:
    prefix = _member_prefix(member)
    name = _escape_plantuml(_normalize_member_text(member.name))
    parameters = ", ".join(_parameter_text(parameter) for parameter in member.parameters)
    signature = f"{prefix}{name}({parameters})"
    if member.return_annotation_text is None:
        return signature
    return_annotation = _escape_plantuml(_normalize_member_text(member.return_annotation_text))
    return f"{signature}: {return_annotation}"


def _parameter_text(parameter: MemberParameter) -> str:
    name = _escape_plantuml(_normalize_member_text(parameter.name))
    if parameter.annotation_text is None:
        return name
    annotation = _escape_plantuml(_normalize_member_text(parameter.annotation_text))
    return f"{name}: {annotation}"


def _member_prefix(member: ClassMember) -> str:
    visibility = {
        "public": "+",
        "protected": "#",
        "private": "-",
    }[member.visibility]
    modifiers = tuple(_modifier_prefixes(member.modifiers))
    if not modifiers:
        return f"{visibility} "
    return f"{visibility} {' '.join(modifiers)} "


def _modifier_prefixes(modifiers: tuple[str, ...]) -> tuple[str, ...]:
    supported = {
        "staticmethod": "{static}",
        "classmethod": "{class}",
        "property": "{property}",
        "async": "{async}",
    }
    order = ("staticmethod", "classmethod", "property", "async")
    seen = set(modifiers)
    return tuple(supported[modifier] for modifier in order if modifier in seen)


def _relation_arrow(relation_type: RelationType) -> str:
    return {
        "inherits": "-up-|>",
        "realizes": "..up|>",
        "composition": "*--",
        "aggregation": "o--",
        "association": "-->",
        "uses": "..>",
        "dependency": "..>",
    }[relation_type]


def _normalize_member_text(value: str) -> str:
    return value.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")


def _escape_plantuml(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


__all__ = [
    "RenderDocumentResult",
    "build_diagram_model",
    "compose_render_ready_model",
    "render_plantuml_text",
    "render_uml_document",
]
