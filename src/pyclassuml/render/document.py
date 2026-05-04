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
        class_decorations=(),
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
    lines = ["@startuml"]
    for container in diagram_model.containers:
        lines.append(f'package "{_escape_plantuml(container)}" {{')
        for class_id in diagram_model.rendered_classes:
            if _module_path_from_class_id(class_id) != container:
                continue
            label = _class_label(class_id)
            alias = alias_by_class_id[class_id]
            member_lines = members_by_class_id.get(class_id, ())
            if not member_lines:
                lines.append(f'  class "{_escape_plantuml(label)}" as {alias}')
                continue
            lines.append(f'  class "{_escape_plantuml(label)}" as {alias} {{')
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
) -> RenderDocumentResult:
    """Render success DTOs or a failure handoff without side effects."""

    render_ready_model = compose_render_ready_model(
        parsed_modules=parsed_modules,
        module_index=module_index,
        selected_classes=selected_classes,
        selected_relations=selected_relations,
        sqlalchemy_hints=sqlalchemy_hints,
        pydantic_hints=pydantic_hints,
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
        "inherits": "--|>",
        "association": "-->",
        "uses": "..>",
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
