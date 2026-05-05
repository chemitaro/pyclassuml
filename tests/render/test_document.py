from pathlib import Path

from pyclassuml.frameworks.pydantic import PydanticEnrichmentHints
from pyclassuml.frameworks.sqlalchemy import SqlalchemyEnrichmentHints
from pyclassuml.model import (
    ClassReference,
    ClassMember,
    Diagnostic,
    DiagnosticSeverity,
    FailureReason,
    MemberParameter,
    OriginSeam,
    ParsedModule,
    Recoverability,
    SelectedClasses,
    SelectedRelation,
    SelectedRelations,
)
from pyclassuml.parse import ModuleIndex
from pyclassuml.render import (
    build_diagram_model,
    compose_render_ready_model,
    render_plantuml_text,
    render_uml_document,
)


def module_index(*class_ids: str) -> ModuleIndex:
    return ModuleIndex(
        module_by_path={},
        project_relative_file_to_module={},
        class_to_module={class_id: Path(class_id.split(":", 1)[0]) for class_id in class_ids},
        seed_project_relative_paths=(),
        import_candidate_paths={},
    )


def parsed_module(
    module_path: str,
    *classes: str,
    diagnostics: tuple[Diagnostic, ...] = (),
    members: tuple[ClassMember, ...] = (),
) -> ParsedModule:
    return ParsedModule(
        module_path=Path(module_path),
        classes=classes,
        diagnostics=diagnostics,
        members=members,
    )


def relation(
    source: str,
    target: str,
    *,
    relation_type: str = "uses",
    evidence_kind: str = "module_import",
) -> SelectedRelation:
    return SelectedRelation(
        source_class_id=source,
        target_class_id=target,
        relation_type=relation_type,
        evidence_kind=evidence_kind,
    )


def warning(code: str, *, origin_seam: OriginSeam = OriginSeam.PARSE) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.WARNING,
        code=code,
        message=f"{code} warning",
        origin_seam=origin_seam,
        recoverability=Recoverability.RECOVERABLE,
    )


def field_member(
    owner: str,
    name: str,
    *,
    visibility: str = "public",
    annotation_text: str | None = None,
    source_order: int = 0,
) -> ClassMember:
    return ClassMember(
        owner_class_id=owner,
        name=name,
        kind="field",
        visibility=visibility,
        annotation_text=annotation_text,
        source_order=source_order,
    )


def method_member(
    owner: str,
    name: str,
    *,
    visibility: str = "public",
    parameters: tuple[MemberParameter, ...] = (),
    return_annotation_text: str | None = None,
    modifiers: tuple[str, ...] = (),
    source_order: int = 0,
) -> ClassMember:
    return ClassMember(
        owner_class_id=owner,
        name=name,
        kind="method",
        visibility=visibility,
        parameters=parameters,
        return_annotation_text=return_annotation_text,
        modifiers=modifiers,
        source_order=source_order,
    )


def render_inputs() -> dict[str, object]:
    return {
        "parsed_modules": (
            parsed_module("pkg/orders.py", "pkg/orders.py:Order", "pkg/orders.py:User"),
            parsed_module("pkg/accounts.py", "pkg/accounts.py:User"),
        ),
        "module_index": module_index(
            "pkg/accounts.py:User",
            "pkg/orders.py:Order",
            "pkg/orders.py:User",
        ),
        "selected_classes": SelectedClasses(
            class_ids=(
                "pkg/orders.py:User",
                "pkg/accounts.py:User",
                "pkg/orders.py:Order",
            )
        ),
        "selected_relations": SelectedRelations(
            relations=(
                relation("pkg/orders.py:Order", "pkg/orders.py:User"),
                relation("pkg/orders.py:Order", "pkg/accounts.py:User", relation_type="association"),
            )
        ),
        "sqlalchemy_hints": SqlalchemyEnrichmentHints(),
        "pydantic_hints": PydanticEnrichmentHints(),
    }


def determinism_inputs() -> tuple[dict[str, object], dict[str, object]]:
    class_ids = (
        "pkg/a.py:A",
        "pkg/b.py:B",
        "pkg/c.py:C",
    )
    selected_relation_a = relation("pkg/a.py:A", "pkg/b.py:B", relation_type="association")
    selected_relation_b = relation("pkg/b.py:B", "pkg/c.py:C")
    sqlalchemy_relations = (
        relation(
            "pkg/a.py:A",
            "pkg/c.py:C",
            evidence_kind="sqlalchemy_relationship_string",
        ),
        relation(
            "pkg/b.py:B",
            "pkg/a.py:A",
            relation_type="inherits",
            evidence_kind="sqlalchemy_mapped",
        ),
    )
    pydantic_relations = (
        relation(
            "pkg/c.py:C",
            "pkg/a.py:A",
            evidence_kind="pydantic_forward_ref",
        ),
        relation(
            "pkg/c.py:C",
            "pkg/b.py:B",
            relation_type="association",
            evidence_kind="pydantic_model_field",
        ),
    )
    sqlalchemy_warnings = (
        warning("sqlalchemy_alpha", origin_seam=OriginSeam.FRAMEWORKS),
        warning("sqlalchemy_beta", origin_seam=OriginSeam.FRAMEWORKS),
    )
    pydantic_warnings = (
        warning("pydantic_alpha", origin_seam=OriginSeam.FRAMEWORKS),
        warning("pydantic_beta", origin_seam=OriginSeam.FRAMEWORKS),
    )

    canonical = {
        "parsed_modules": (
            parsed_module("pkg/a.py", "pkg/a.py:A", diagnostics=(warning("parse_a"),)),
            parsed_module("pkg/b.py", "pkg/b.py:B"),
            parsed_module("pkg/c.py", "pkg/c.py:C", diagnostics=(warning("parse_c"),)),
        ),
        "module_index": module_index(*class_ids),
        "selected_classes": SelectedClasses(class_ids=class_ids),
        "selected_relations": SelectedRelations(relations=(selected_relation_a, selected_relation_b)),
        "sqlalchemy_hints": SqlalchemyEnrichmentHints(
            added_relations=sqlalchemy_relations,
            warning_diagnostics=sqlalchemy_warnings,
        ),
        "pydantic_hints": PydanticEnrichmentHints(
            added_relations=pydantic_relations,
            warning_diagnostics=pydantic_warnings,
        ),
    }
    reordered = {
        "parsed_modules": (
            parsed_module("pkg/c.py", "pkg/c.py:C", diagnostics=(warning("parse_c"),)),
            parsed_module("pkg/b.py", "pkg/b.py:B"),
            parsed_module("pkg/a.py", "pkg/a.py:A", diagnostics=(warning("parse_a"),)),
        ),
        "module_index": module_index(*reversed(class_ids)),
        "selected_classes": SelectedClasses(class_ids=tuple(reversed(class_ids))),
        "selected_relations": SelectedRelations(relations=(selected_relation_b, selected_relation_a)),
        "sqlalchemy_hints": SqlalchemyEnrichmentHints(
            added_relations=tuple(reversed(sqlalchemy_relations)),
            warning_diagnostics=tuple(reversed(sqlalchemy_warnings)),
        ),
        "pydantic_hints": PydanticEnrichmentHints(
            added_relations=tuple(reversed(pydantic_relations)),
            warning_diagnostics=tuple(reversed(pydantic_warnings)),
        ),
    }
    return canonical, reordered


def test_compose_render_ready_model_merges_framework_relations_and_dedupes_by_triple() -> None:
    render_ready = compose_render_ready_model(
        parsed_modules=(parsed_module("pkg/models.py", "pkg/models.py:A", "pkg/models.py:B", "pkg/models.py:C"),),
        module_index=module_index("pkg/models.py:A", "pkg/models.py:B", "pkg/models.py:C"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:B", "pkg/models.py:C")),
        selected_relations=SelectedRelations(
            relations=(relation("pkg/models.py:A", "pkg/models.py:B", evidence_kind="module_import"),)
        ),
        sqlalchemy_hints=SqlalchemyEnrichmentHints(
            added_relations=(
                relation("pkg/models.py:A", "pkg/models.py:B", evidence_kind="sqlalchemy_mapped"),
                relation("pkg/models.py:A", "pkg/models.py:C", evidence_kind="sqlalchemy_relationship_string"),
            )
        ),
        pydantic_hints=PydanticEnrichmentHints(
            added_relations=(relation("pkg/models.py:B", "pkg/models.py:C", evidence_kind="pydantic_forward_ref"),)
        ),
    )

    assert render_ready.classes == ("pkg/models.py:A", "pkg/models.py:B", "pkg/models.py:C")
    assert render_ready.relations == (
        ("pkg/models.py:A", "pkg/models.py:B", "uses"),
        ("pkg/models.py:A", "pkg/models.py:C", "uses"),
        ("pkg/models.py:B", "pkg/models.py:C", "uses"),
    )
    assert render_ready.grouping_keys == ("pkg/models.py",)
    assert render_ready.members == ()
    assert render_ready.class_decorations == ()


def test_compose_render_ready_model_carries_selected_class_members_in_stable_order() -> None:
    selected_a = "pkg/models.py:A"
    selected_b = "pkg/models.py:B"
    unselected = "pkg/models.py:C"
    late_member = field_member(selected_b, "late", source_order=20)
    early_member = method_member(selected_a, "early", source_order=10)
    ignored_member = field_member(unselected, "ignored", source_order=1)

    render_ready = compose_render_ready_model(
        parsed_modules=(
            parsed_module(
                "pkg/models.py",
                selected_b,
                selected_a,
                unselected,
                members=(late_member, ignored_member, early_member),
            ),
        ),
        module_index=module_index(selected_a, selected_b, unselected),
        selected_classes=SelectedClasses(class_ids=(selected_b, selected_a)),
        selected_relations=SelectedRelations(),
        sqlalchemy_hints=SqlalchemyEnrichmentHints(),
        pydantic_hints=PydanticEnrichmentHints(),
    )

    assert render_ready.classes == (selected_a, selected_b)
    assert render_ready.members == (early_member, late_member)


def test_compose_render_ready_model_carries_diagnostics_in_stable_source_order() -> None:
    parse_warning = warning("parse_warn")
    sqlalchemy_warning = warning("sqlalchemy_warn", origin_seam=OriginSeam.FRAMEWORKS)
    pydantic_warning = warning("pydantic_warn", origin_seam=OriginSeam.FRAMEWORKS)

    render_ready = compose_render_ready_model(
        parsed_modules=(parsed_module("pkg/models.py", "pkg/models.py:A", diagnostics=(parse_warning,)),),
        module_index=module_index("pkg/models.py:A"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A",)),
        selected_relations=SelectedRelations(),
        sqlalchemy_hints=SqlalchemyEnrichmentHints(warning_diagnostics=(sqlalchemy_warning,)),
        pydantic_hints=PydanticEnrichmentHints(warning_diagnostics=(pydantic_warning,)),
    )

    assert render_ready.diagnostics == (parse_warning, sqlalchemy_warning, pydantic_warning)


def test_render_plantuml_text_is_deterministic_and_groups_by_class_id_module_path() -> None:
    first = render_uml_document(**render_inputs())
    second = render_uml_document(**render_inputs())

    assert first.plantuml_text == second.plantuml_text
    assert first.failure_signal is None
    assert first.diagram_model is not None
    assert first.diagram_model.containers == ("pkg/accounts.py", "pkg/orders.py")
    assert first.diagram_model.aliases == (
        ("pkg/accounts.py:User", "c001"),
        ("pkg/orders.py:Order", "c002"),
        ("pkg/orders.py:User", "c003"),
    )
    assert first.plantuml_text is not None
    assert first.plantuml_text.text == "\n".join(
        [
            "@startuml",
            "package \"pkg/accounts.py\" {",
            "  class \"User\" as c001",
            "}",
            "package \"pkg/orders.py\" {",
            "  class \"Order\" as c002",
            "  class \"User\" as c003",
            "}",
            "c002 --> c001",
            "c002 ..> c003",
            "@enduml",
        ]
    )


def test_render_uml_document_outputs_diff_styles_only_when_diff_decorations_exist() -> None:
    result = render_uml_document(
        **render_inputs(),
        class_decorations=(
            ("pkg/orders.py:Order", "DiffChanged"),
            ("pkg/orders.py:User", "DiffDependency"),
        ),
    )

    assert result.failure_signal is None
    assert result.plantuml_text is not None
    assert result.plantuml_text.text.splitlines()[:7] == [
        "@startuml",
        "skinparam class {",
        "  BackgroundColor<<DiffChanged>> #fff3b0",
        "  BorderColor<<DiffChanged>> #d39e00",
        "  BackgroundColor<<DiffDependency>> #e8f4ff",
        "  BorderColor<<DiffDependency>> #5b8def",
        "}",
    ]
    assert 'class "Order" as c002 <<DiffChanged>>' in result.plantuml_text.text
    assert 'class "User" as c003 <<DiffDependency>>' in result.plantuml_text.text


def test_render_uml_document_merges_diff_and_protocol_stereotypes() -> None:
    protocol_id = "pkg/contracts.py:Repository"
    render_ready = compose_render_ready_model(
        parsed_modules=(
            ParsedModule(
                module_path=Path("pkg/contracts.py"),
                imports=("from typing import Protocol",),
                classes=(protocol_id,),
                class_references=(
                    ClassReference(
                        protocol_id,
                        "Protocol",
                        "class_base",
                        "base",
                    ),
                ),
            ),
        ),
        module_index=module_index(protocol_id),
        selected_classes=SelectedClasses(class_ids=(protocol_id,)),
        selected_relations=SelectedRelations(),
        sqlalchemy_hints=SqlalchemyEnrichmentHints(),
        pydantic_hints=PydanticEnrichmentHints(),
        class_decorations=((protocol_id, "DiffChanged"),),
    )
    text = render_plantuml_text(render_ready, build_diagram_model(render_ready))

    assert render_ready.class_decorations == (
        (protocol_id, "DiffChanged"),
        (protocol_id, "Protocol"),
    )
    assert 'class "Repository" as c001 <<DiffChanged>> <<Protocol>>' in text.text
    assert "BackgroundColor<<DiffChanged>>" in text.text


def test_render_uml_document_ignores_decorations_for_non_rendered_classes() -> None:
    result = render_uml_document(
        **render_inputs(),
        class_decorations=(("pkg/hidden.py:Hidden", "DiffChanged"),),
    )

    assert result.failure_signal is None
    assert result.plantuml_text is not None
    assert "DiffChanged" not in result.plantuml_text.text
    assert "skinparam class {" not in result.plantuml_text.text


def test_render_ready_model_and_plantuml_are_deterministic_for_reordered_inputs() -> None:
    first_inputs, second_inputs = determinism_inputs()

    first_ready = compose_render_ready_model(**first_inputs)
    second_ready = compose_render_ready_model(**second_inputs)
    first_result = render_uml_document(**first_inputs)
    second_result = render_uml_document(**second_inputs)

    assert first_ready == second_ready
    assert first_result.failure_signal is None
    assert second_result.failure_signal is None
    assert render_plantuml_text(first_ready, build_diagram_model(first_ready)) == render_plantuml_text(
        second_ready, build_diagram_model(second_ready)
    )
    assert first_result.plantuml_text == render_plantuml_text(first_ready, build_diagram_model(first_ready))
    assert second_result.plantuml_text == render_plantuml_text(second_ready, build_diagram_model(second_ready))
    assert first_result.plantuml_text == second_result.plantuml_text


def test_render_uml_document_outputs_framework_relations_after_dedupe() -> None:
    result = render_uml_document(
        parsed_modules=(
            parsed_module("pkg/models.py", "pkg/models.py:A", "pkg/models.py:B", "pkg/models.py:C"),
        ),
        module_index=module_index("pkg/models.py:A", "pkg/models.py:B", "pkg/models.py:C"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:B", "pkg/models.py:C")),
        selected_relations=SelectedRelations(
            relations=(relation("pkg/models.py:A", "pkg/models.py:B", evidence_kind="module_import"),)
        ),
        sqlalchemy_hints=SqlalchemyEnrichmentHints(
            added_relations=(
                relation("pkg/models.py:A", "pkg/models.py:B", evidence_kind="sqlalchemy_mapped"),
                relation("pkg/models.py:A", "pkg/models.py:C", evidence_kind="sqlalchemy_relationship_string"),
            )
        ),
        pydantic_hints=PydanticEnrichmentHints(
            added_relations=(relation("pkg/models.py:B", "pkg/models.py:C", evidence_kind="pydantic_forward_ref"),)
        ),
    )

    assert result.failure_signal is None
    assert result.plantuml_text is not None
    relation_lines = tuple(line for line in result.plantuml_text.text.splitlines() if line.startswith("c"))
    assert relation_lines == (
        "c001 ..> c002",
        "c001 ..> c003",
        "c002 ..> c003",
    )


def test_build_diagram_model_and_render_plantuml_text_support_class_only_document() -> None:
    render_ready = compose_render_ready_model(
        parsed_modules=(parsed_module("pkg/models.py", "pkg/models.py:A"),),
        module_index=module_index("pkg/models.py:A"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A",)),
        selected_relations=SelectedRelations(),
        sqlalchemy_hints=SqlalchemyEnrichmentHints(),
        pydantic_hints=PydanticEnrichmentHints(),
    )

    diagram = build_diagram_model(render_ready)
    text = render_plantuml_text(render_ready, diagram)

    assert diagram.rendered_relations == ()
    assert text.text == "\n".join(
        [
            "@startuml",
            "package \"pkg/models.py\" {",
            "  class \"A\" as c001",
            "}",
            "@enduml",
        ]
    )


def test_render_plantuml_text_outputs_member_body_only_for_classes_with_members() -> None:
    order_id = "pkg/models.py:Order"
    empty_id = "pkg/models.py:Empty"
    render_ready = compose_render_ready_model(
        parsed_modules=(
            parsed_module(
                "pkg/models.py",
                order_id,
                empty_id,
                members=(
                    field_member(order_id, "customer", annotation_text="Customer", source_order=1),
                    field_member(order_id, "status", source_order=2),
                    method_member(
                        order_id,
                        "submit",
                        parameters=(
                            MemberParameter(name="raw"),
                            MemberParameter(name="typed", annotation_text="Order"),
                        ),
                        return_annotation_text="Receipt",
                        source_order=3,
                    ),
                    method_member(order_id, "empty", source_order=4),
                ),
            ),
        ),
        module_index=module_index(order_id, empty_id),
        selected_classes=SelectedClasses(class_ids=(order_id, empty_id)),
        selected_relations=SelectedRelations(),
        sqlalchemy_hints=SqlalchemyEnrichmentHints(),
        pydantic_hints=PydanticEnrichmentHints(),
    )

    text = render_plantuml_text(render_ready, build_diagram_model(render_ready))

    assert text.text == "\n".join(
        [
            "@startuml",
            "package \"pkg/models.py\" {",
            "  class \"Empty\" as c001",
            "  class \"Order\" as c002 {",
            "    + customer: Customer",
            "    + status",
            "    + submit(raw, typed: Order): Receipt",
            "    + empty()",
            "  }",
            "}",
            "@enduml",
        ]
    )


def test_render_plantuml_text_outputs_field_only_and_method_only_class_bodies() -> None:
    empty_id = "pkg/models.py:Empty"
    field_only_id = "pkg/models.py:FieldOnly"
    method_only_id = "pkg/models.py:MethodOnly"
    render_ready = compose_render_ready_model(
        parsed_modules=(
            parsed_module(
                "pkg/models.py",
                empty_id,
                field_only_id,
                method_only_id,
                members=(
                    field_member(field_only_id, "customer", annotation_text="Customer", source_order=1),
                    method_member(
                        method_only_id,
                        "submit",
                        parameters=(MemberParameter(name="receipt", annotation_text="Receipt"),),
                        return_annotation_text="Receipt",
                        source_order=1,
                    ),
                ),
            ),
        ),
        module_index=module_index(empty_id, field_only_id, method_only_id),
        selected_classes=SelectedClasses(class_ids=(empty_id, field_only_id, method_only_id)),
        selected_relations=SelectedRelations(),
        sqlalchemy_hints=SqlalchemyEnrichmentHints(),
        pydantic_hints=PydanticEnrichmentHints(),
    )

    text = render_plantuml_text(render_ready, build_diagram_model(render_ready))

    assert text.text == "\n".join(
        [
            "@startuml",
            "package \"pkg/models.py\" {",
            "  class \"Empty\" as c001",
            "  class \"FieldOnly\" as c002 {",
            "    + customer: Customer",
            "  }",
            "  class \"MethodOnly\" as c003 {",
            "    + submit(receipt: Receipt): Receipt",
            "  }",
            "}",
            "@enduml",
        ]
    )


def test_render_plantuml_text_outputs_visibility_modifiers_and_member_escaping() -> None:
    class_id = "pkg/models.py:Order"
    render_ready = compose_render_ready_model(
        parsed_modules=(
            parsed_module(
                "pkg/models.py",
                class_id,
                members=(
                    field_member(
                        class_id,
                        'path"line',
                        visibility="private",
                        annotation_text='Path\\Name\nNext',
                        source_order=1,
                    ),
                    method_member(
                        class_id,
                        "load",
                        visibility="protected",
                        parameters=(MemberParameter(name='raw"arg', annotation_text="A\\B\nC"),),
                        return_annotation_text='Result"Type',
                        modifiers=("async", "unknown", "staticmethod", "async", "classmethod", "property"),
                        source_order=2,
                    ),
                ),
            ),
        ),
        module_index=module_index(class_id),
        selected_classes=SelectedClasses(class_ids=(class_id,)),
        selected_relations=SelectedRelations(),
        sqlalchemy_hints=SqlalchemyEnrichmentHints(),
        pydantic_hints=PydanticEnrichmentHints(),
    )

    text = render_plantuml_text(render_ready, build_diagram_model(render_ready))

    assert text.text == "\n".join(
        [
            "@startuml",
            "package \"pkg/models.py\" {",
            "  class \"Order\" as c001 {",
            "    - path\\\"line: Path\\\\Name Next",
            "    # {static} {class} {property} {async} load(raw\\\"arg: A\\\\B C): Result\\\"Type",
            "  }",
            "}",
            "@enduml",
        ]
    )


def test_render_plantuml_text_maps_relation_types_without_labels() -> None:
    class_ids = (
        "pkg/models.py:A",
        "pkg/models.py:B",
        "pkg/models.py:C",
        "pkg/models.py:D",
        "pkg/models.py:E",
        "pkg/models.py:F",
    )
    result = render_uml_document(
        parsed_modules=(parsed_module("pkg/models.py", *class_ids),),
        module_index=module_index(*class_ids),
        selected_classes=SelectedClasses(class_ids=class_ids),
        selected_relations=SelectedRelations(
            relations=(
                relation("pkg/models.py:A", "pkg/models.py:B", relation_type="inherits"),
                relation("pkg/models.py:B", "pkg/models.py:C", relation_type="realizes"),
                relation("pkg/models.py:C", "pkg/models.py:D", relation_type="composition"),
                relation("pkg/models.py:D", "pkg/models.py:E", relation_type="aggregation"),
                relation("pkg/models.py:E", "pkg/models.py:F", relation_type="association"),
                relation("pkg/models.py:F", "pkg/models.py:A", relation_type="uses"),
            )
        ),
        sqlalchemy_hints=SqlalchemyEnrichmentHints(),
        pydantic_hints=PydanticEnrichmentHints(),
    )

    assert result.failure_signal is None
    assert result.plantuml_text is not None
    relation_lines = tuple(line for line in result.plantuml_text.text.splitlines() if line.startswith("c"))
    assert relation_lines == (
        "c001 -up-|> c002",
        "c002 ..up|> c003",
        "c003 *-- c004",
        "c004 o-- c005",
        "c005 --> c006",
        "c006 ..> c001",
    )
    assert "*-->" not in result.plantuml_text.text
    assert "o-->" not in result.plantuml_text.text


def test_compose_and_render_protocol_class_stereotype_from_explicit_protocol_base() -> None:
    protocol_id = "pkg/models.py:Repository"
    impl_id = "pkg/models.py:SqlRepository"
    render_ready = compose_render_ready_model(
        parsed_modules=(
            ParsedModule(
                module_path=Path("pkg/models.py"),
                imports=("from typing import Protocol",),
                classes=(protocol_id, impl_id),
                class_references=(
                    ClassReference(
                        protocol_id,
                        "Protocol",
                        "class_base",
                        "base",
                    ),
                ),
            ),
        ),
        module_index=module_index(protocol_id, impl_id),
        selected_classes=SelectedClasses(class_ids=(protocol_id, impl_id)),
        selected_relations=SelectedRelations(relations=(relation(impl_id, protocol_id, relation_type="realizes"),)),
        sqlalchemy_hints=SqlalchemyEnrichmentHints(),
        pydantic_hints=PydanticEnrichmentHints(),
    )

    text = render_plantuml_text(render_ready, build_diagram_model(render_ready))

    assert render_ready.class_decorations == ((protocol_id, "Protocol"),)
    assert 'class "Repository" as c001 <<Protocol>>' in text.text
    assert "c002 ..up|> c001" in text.text


def test_compose_and_render_imported_bare_protocol_marker_with_internal_protocol_elsewhere() -> None:
    protocol_id = "pkg/contracts.py:Repository"
    impl_id = "pkg/contracts.py:SqlRepository"
    internal_protocol_id = "pkg/names.py:Protocol"
    render_ready = compose_render_ready_model(
        parsed_modules=(
            ParsedModule(
                module_path=Path("pkg/contracts.py"),
                imports=("from typing import Protocol",),
                classes=(protocol_id, impl_id),
                class_references=(
                    ClassReference(
                        protocol_id,
                        "Protocol",
                        "class_base",
                        "base",
                    ),
                ),
            ),
            ParsedModule(
                module_path=Path("pkg/names.py"),
                classes=(internal_protocol_id,),
            ),
        ),
        module_index=module_index(protocol_id, impl_id, internal_protocol_id),
        selected_classes=SelectedClasses(class_ids=(protocol_id, impl_id, internal_protocol_id)),
        selected_relations=SelectedRelations(relations=(relation(impl_id, protocol_id, relation_type="realizes"),)),
        sqlalchemy_hints=SqlalchemyEnrichmentHints(),
        pydantic_hints=PydanticEnrichmentHints(),
    )

    text = render_plantuml_text(render_ready, build_diagram_model(render_ready))

    assert render_ready.class_decorations == ((protocol_id, "Protocol"),)
    assert 'class "Repository" as c001 <<Protocol>>' in text.text
    assert 'class "Protocol" as c003 <<Protocol>>' not in text.text
    assert "c002 ..up|> c001" in text.text


def test_compose_render_ready_model_does_not_decorate_aliased_bare_protocol_base() -> None:
    protocol_id = "pkg/models.py:Protocol"
    foo_id = "pkg/models.py:Foo"
    render_ready = compose_render_ready_model(
        parsed_modules=(
            ParsedModule(
                module_path=Path("pkg/models.py"),
                imports=("from typing import Protocol as TypingProtocol",),
                classes=(protocol_id, foo_id),
                class_references=(
                    ClassReference(
                        foo_id,
                        "Protocol",
                        "class_base",
                        "base",
                    ),
                ),
            ),
        ),
        module_index=module_index(protocol_id, foo_id),
        selected_classes=SelectedClasses(class_ids=(protocol_id, foo_id)),
        selected_relations=SelectedRelations(relations=(relation(foo_id, protocol_id, relation_type="inherits"),)),
        sqlalchemy_hints=SqlalchemyEnrichmentHints(),
        pydantic_hints=PydanticEnrichmentHints(),
    )

    text = render_plantuml_text(render_ready, build_diagram_model(render_ready))

    assert render_ready.class_decorations == ()
    assert 'class "Foo" as c001 <<Protocol>>' not in text.text
    assert "<<Protocol>>" not in text.text
    assert "c001 -up-|> c002" in text.text


def test_compose_render_ready_model_decorates_qualified_protocol_bases() -> None:
    typing_protocol_id = "pkg/models.py:TypingRepository"
    extensions_protocol_id = "pkg/models.py:ExtensionsRepository"
    render_ready = compose_render_ready_model(
        parsed_modules=(
            ParsedModule(
                module_path=Path("pkg/models.py"),
                classes=(typing_protocol_id, extensions_protocol_id),
                class_references=(
                    ClassReference(
                        typing_protocol_id,
                        "typing.Protocol",
                        "class_base",
                        "base",
                    ),
                    ClassReference(
                        extensions_protocol_id,
                        "typing_extensions.Protocol",
                        "class_base",
                        "base",
                    ),
                ),
            ),
        ),
        module_index=module_index(typing_protocol_id, extensions_protocol_id),
        selected_classes=SelectedClasses(class_ids=(typing_protocol_id, extensions_protocol_id)),
        selected_relations=SelectedRelations(),
        sqlalchemy_hints=SqlalchemyEnrichmentHints(),
        pydantic_hints=PydanticEnrichmentHints(),
    )

    text = render_plantuml_text(render_ready, build_diagram_model(render_ready))

    assert render_ready.class_decorations == (
        (extensions_protocol_id, "Protocol"),
        (typing_protocol_id, "Protocol"),
    )
    assert 'class "ExtensionsRepository" as c001 <<Protocol>>' in text.text
    assert 'class "TypingRepository" as c002 <<Protocol>>' in text.text


def test_internal_normal_protocol_base_does_not_render_protocol_stereotype() -> None:
    protocol_id = "pkg/models.py:Protocol"
    foo_id = "pkg/models.py:Foo"
    render_ready = compose_render_ready_model(
        parsed_modules=(
            ParsedModule(
                module_path=Path("pkg/models.py"),
                classes=(protocol_id, foo_id),
                class_references=(
                    ClassReference(
                        foo_id,
                        "Protocol",
                        "class_base",
                        "base",
                    ),
                ),
            ),
        ),
        module_index=module_index(protocol_id, foo_id),
        selected_classes=SelectedClasses(class_ids=(protocol_id, foo_id)),
        selected_relations=SelectedRelations(relations=(relation(foo_id, protocol_id, relation_type="inherits"),)),
        sqlalchemy_hints=SqlalchemyEnrichmentHints(),
        pydantic_hints=PydanticEnrichmentHints(),
    )

    text = render_plantuml_text(render_ready, build_diagram_model(render_ready))

    assert render_ready.class_decorations == ()
    assert "<<Protocol>>" not in text.text
    assert "c001 -up-|> c002" in text.text


def test_render_uml_document_returns_failure_for_empty_selected_classes() -> None:
    result = render_uml_document(
        parsed_modules=(parsed_module("pkg/models.py", "pkg/models.py:A"),),
        module_index=module_index("pkg/models.py:A"),
        selected_classes=SelectedClasses(),
        selected_relations=SelectedRelations(),
        sqlalchemy_hints=SqlalchemyEnrichmentHints(),
        pydantic_hints=PydanticEnrichmentHints(),
    )

    assert result.diagram_model is None
    assert result.plantuml_text is None
    assert result.failure_signal is not None
    assert result.failure_signal.failure_reason is FailureReason.DIAGRAM_UNBUILDABLE_AFTER_RECOVERY
    assert result.failure_signal.class_count == 0
    assert result.failure_signal.relation_count == 0
    assert result.failure_signal.partial_diagram_present is False


def test_render_uml_document_returns_failure_for_relations_without_selected_classes() -> None:
    result = render_uml_document(
        parsed_modules=(parsed_module("pkg/models.py", "pkg/models.py:A", "pkg/models.py:B"),),
        module_index=module_index("pkg/models.py:A", "pkg/models.py:B"),
        selected_classes=SelectedClasses(),
        selected_relations=SelectedRelations(relations=(relation("pkg/models.py:A", "pkg/models.py:B"),)),
        sqlalchemy_hints=SqlalchemyEnrichmentHints(),
        pydantic_hints=PydanticEnrichmentHints(),
    )

    assert result.diagram_model is None
    assert result.plantuml_text is None
    assert result.failure_signal is not None
    assert result.failure_signal.class_count == 0
    assert result.failure_signal.relation_count == 1
    assert result.failure_signal.partial_diagram_present is False
    assert [diagnostic.code for diagnostic in result.failure_signal.diagnostics] == [
        "render_relation_endpoint_missing"
    ]


def test_render_uml_document_returns_failure_for_missing_selected_class_without_phantom_class() -> None:
    result = render_uml_document(
        parsed_modules=(parsed_module("pkg/models.py", "pkg/models.py:A"),),
        module_index=module_index("pkg/models.py:A"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/missing.py:Missing")),
        selected_relations=SelectedRelations(),
        sqlalchemy_hints=SqlalchemyEnrichmentHints(),
        pydantic_hints=PydanticEnrichmentHints(),
    )

    assert result.diagram_model is None
    assert result.plantuml_text is None
    assert result.failure_signal is not None
    assert result.failure_signal.class_count == 1
    assert result.failure_signal.partial_diagram_present is True
    assert [diagnostic.code for diagnostic in result.failure_signal.diagnostics] == [
        "render_selected_class_missing"
    ]


def test_render_uml_document_returns_failure_when_selected_class_is_missing_from_module_index() -> None:
    result = render_uml_document(
        parsed_modules=(parsed_module("pkg/models.py", "pkg/models.py:A", "pkg/models.py:B"),),
        module_index=module_index("pkg/models.py:A"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:B")),
        selected_relations=SelectedRelations(),
        sqlalchemy_hints=SqlalchemyEnrichmentHints(),
        pydantic_hints=PydanticEnrichmentHints(),
    )

    assert result.diagram_model is None
    assert result.plantuml_text is None
    assert result.failure_signal is not None
    assert result.failure_signal.class_count == 1
    assert result.failure_signal.partial_diagram_present is True
    assert [diagnostic.code for diagnostic in result.failure_signal.diagnostics] == [
        "render_selected_class_missing"
    ]


def test_render_uml_document_returns_failure_when_selected_class_is_missing_from_parsed_modules() -> None:
    result = render_uml_document(
        parsed_modules=(parsed_module("pkg/models.py", "pkg/models.py:A"),),
        module_index=module_index("pkg/models.py:A", "pkg/models.py:B"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A", "pkg/models.py:B")),
        selected_relations=SelectedRelations(),
        sqlalchemy_hints=SqlalchemyEnrichmentHints(),
        pydantic_hints=PydanticEnrichmentHints(),
    )

    assert result.diagram_model is None
    assert result.plantuml_text is None
    assert result.failure_signal is not None
    assert result.failure_signal.class_count == 1
    assert result.failure_signal.partial_diagram_present is True
    assert [diagnostic.code for diagnostic in result.failure_signal.diagnostics] == [
        "render_selected_class_missing"
    ]


def test_render_uml_document_returns_failure_for_missing_relation_endpoint_with_carried_diagnostics() -> None:
    parse_warning = warning("parse_warn")
    sqlalchemy_warning = warning("sqlalchemy_warn", origin_seam=OriginSeam.FRAMEWORKS)
    pydantic_warning = warning("pydantic_warn", origin_seam=OriginSeam.FRAMEWORKS)

    result = render_uml_document(
        parsed_modules=(parsed_module("pkg/models.py", "pkg/models.py:A", diagnostics=(parse_warning,)),),
        module_index=module_index("pkg/models.py:A"),
        selected_classes=SelectedClasses(class_ids=("pkg/models.py:A",)),
        selected_relations=SelectedRelations(relations=(relation("pkg/models.py:A", "pkg/models.py:B"),)),
        sqlalchemy_hints=SqlalchemyEnrichmentHints(
            added_relations=(relation("pkg/models.py:A", "pkg/models.py:B", evidence_kind="sqlalchemy_mapped"),),
            warning_diagnostics=(sqlalchemy_warning,),
        ),
        pydantic_hints=PydanticEnrichmentHints(warning_diagnostics=(pydantic_warning,)),
    )

    assert result.diagram_model is None
    assert result.plantuml_text is None
    assert result.failure_signal is not None
    assert result.failure_signal.class_count == 1
    assert result.failure_signal.relation_count == 1
    assert result.failure_signal.partial_diagram_present is True
    assert [diagnostic.code for diagnostic in result.failure_signal.diagnostics] == [
        "parse_warn",
        "sqlalchemy_warn",
        "pydantic_warn",
        "render_relation_endpoint_missing",
    ]
