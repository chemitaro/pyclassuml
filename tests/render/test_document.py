from pathlib import Path

from pyclassuml.frameworks.pydantic import PydanticEnrichmentHints
from pyclassuml.frameworks.sqlalchemy import SqlalchemyEnrichmentHints
from pyclassuml.model import (
    Diagnostic,
    DiagnosticSeverity,
    FailureReason,
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
) -> ParsedModule:
    return ParsedModule(
        module_path=Path(module_path),
        classes=classes,
        diagnostics=diagnostics,
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
            "c002 --> c001 : association",
            "c002 --> c003 : uses",
            "@enduml",
        ]
    )


def test_render_ready_model_and_plantuml_are_deterministic_for_reordered_inputs() -> None:
    first_inputs, second_inputs = determinism_inputs()

    first_ready = compose_render_ready_model(**first_inputs)
    second_ready = compose_render_ready_model(**second_inputs)
    first_result = render_uml_document(**first_inputs)
    second_result = render_uml_document(**second_inputs)

    assert first_ready == second_ready
    assert first_result.failure_signal is None
    assert second_result.failure_signal is None
    assert render_plantuml_text(build_diagram_model(first_ready)) == render_plantuml_text(
        build_diagram_model(second_ready)
    )
    assert first_result.plantuml_text == render_plantuml_text(build_diagram_model(first_ready))
    assert second_result.plantuml_text == render_plantuml_text(build_diagram_model(second_ready))
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
    relation_lines = tuple(
        line for line in result.plantuml_text.text.splitlines() if " --> " in line
    )
    assert relation_lines == (
        "c001 --> c002 : uses",
        "c001 --> c003 : uses",
        "c002 --> c003 : uses",
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
    text = render_plantuml_text(diagram)

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
