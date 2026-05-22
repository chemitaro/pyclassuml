from pathlib import Path

from pyclassuml.analyze import (
    SelectedRelation,
    SelectionResult,
    TraversalObservations,
    select_classes_and_relations,
)
from pyclassuml.analyze.selection import SelectedRelation as SelectionModuleSelectedRelation
from pyclassuml.model import (
    ClassReference,
    DependencyGraph,
    DiagnosticSeverity,
    OriginSeam,
    ParsedModule,
    Recoverability,
    SelectedRelation as ModelSelectedRelation,
)
from pyclassuml.parse import ModuleIndex


def module(path: str, classes: tuple[str, ...] = ()) -> ParsedModule:
    return ParsedModule(module_path=Path(path), classes=classes)


def reference(
    source_class_id: str,
    target_name: str,
    reference_kind: str,
    reference_owner: str,
    annotation_shape: str | None = None,
) -> ClassReference:
    return ClassReference(
        source_class_id=source_class_id,
        target_name=target_name,
        reference_kind=reference_kind,
        reference_owner=reference_owner,
        annotation_shape=annotation_shape,
    )


def module_index(
    modules: tuple[ParsedModule, ...],
    *,
    seeds: tuple[str, ...],
    import_candidate_paths: dict[str, tuple[str, ...]] | None = None,
) -> ModuleIndex:
    module_by_path = {parsed.module_path: parsed for parsed in modules}
    return ModuleIndex(
        module_by_path=module_by_path,
        project_relative_file_to_module={path: path for path in module_by_path},
        class_to_module={
            class_id: parsed.module_path
            for parsed in modules
            for class_id in parsed.classes
        },
        seed_project_relative_paths=tuple(Path(seed) for seed in seeds),
        import_candidate_paths={
            import_text: tuple(Path(path) for path in paths)
            for import_text, paths in (import_candidate_paths or {}).items()
        },
    )


def observations(*seeds: str) -> TraversalObservations:
    return TraversalObservations(seed_project_relative_paths=tuple(Path(seed) for seed in seeds))


def select(
    modules: tuple[ParsedModule, ...],
    *,
    seeds: tuple[str, ...],
    reachable: tuple[str, ...],
    edges: tuple[tuple[str, str], ...] = (),
    import_candidate_paths: dict[str, tuple[str, ...]] | None = None,
) -> SelectionResult:
    return select_classes_and_relations(
        modules,
        module_index(modules, seeds=seeds, import_candidate_paths=import_candidate_paths),
        DependencyGraph(
            reachable_files=tuple(Path(path) for path in reachable),
            edges=tuple((Path(source), Path(target)) for source, target in edges),
        ),
        observations(*seeds),
    )


def assert_typed_warning_payload(
    diagnostic,
    *,
    code: str,
    source_class_id: str,
    target_name: str,
    reference_kind: str,
    reference_owner: str,
    candidates: tuple[str, ...] = (),
) -> None:
    assert diagnostic.severity is DiagnosticSeverity.WARNING
    assert diagnostic.code == code
    assert diagnostic.origin_seam is OriginSeam.ANALYZE
    assert diagnostic.recoverability is Recoverability.RECOVERABLE
    assert diagnostic.failure_reason is None
    assert f"source_class_id={source_class_id}" in diagnostic.message
    assert f"target_name={target_name}" in diagnostic.message
    assert f"reference_kind={reference_kind}" in diagnostic.message
    assert f"reference_owner={reference_owner}" in diagnostic.message
    for candidate in candidates:
        assert candidate in diagnostic.message


def test_seed_full_display_keeps_seed_class_without_relation() -> None:
    seed = module("pkg/a.py", classes=("pkg.a.Primary", "pkg.a.Unrelated"))

    result = select((seed,), seeds=("pkg/a.py",), reachable=("pkg/a.py",))

    assert result.selected_classes.class_ids == ("pkg.a.Primary", "pkg.a.Unrelated")
    assert result.selected_relations.relations == ()
    assert result.diagnostics == ()


def test_selected_relation_compatibility_imports_use_shared_model_contract() -> None:
    assert SelectedRelation is ModelSelectedRelation
    assert SelectionModuleSelectedRelation is ModelSelectedRelation


def test_unreachable_module_class_is_excluded() -> None:
    seed = module("pkg/a.py", classes=("pkg.a.Primary",))
    unreachable = module("pkg/unreachable.py", classes=("pkg.unreachable.Hidden",))

    result = select((unreachable, seed), seeds=("pkg/a.py",), reachable=("pkg/a.py",))

    assert result.selected_classes.class_ids == ("pkg.a.Primary",)
    assert "pkg.unreachable.Hidden" not in result.selected_classes.class_ids


def test_one_class_source_target_edge_selects_relation_dependency_class() -> None:
    seed = module("pkg/a.py", classes=("pkg.a.Source",))
    dependency = module("pkg/b.py", classes=("pkg.b.Target",))

    result = select(
        (dependency, seed),
        seeds=("pkg/a.py",),
        reachable=("pkg/a.py", "pkg/b.py"),
        edges=(("pkg/a.py", "pkg/b.py"),),
    )

    assert result.selected_classes.class_ids == ("pkg.a.Source", "pkg.b.Target")
    assert result.selected_relations.relations == (
        SelectedRelation(
            source_class_id="pkg.a.Source",
            target_class_id="pkg.b.Target",
            relation_type="uses",
            evidence_kind="module_import",
        ),
    )
    assert result.diagnostics == ()


def test_multi_class_dependency_ambiguity_warns_without_relation_or_dependency_selection() -> None:
    seed = module("pkg/a.py", classes=("pkg.a.Source",))
    dependency = module("pkg/b.py", classes=("pkg.b.One", "pkg.b.Two"))

    result = select(
        (dependency, seed),
        seeds=("pkg/a.py",),
        reachable=("pkg/a.py", "pkg/b.py"),
        edges=(("pkg/a.py", "pkg/b.py"),),
    )

    assert result.selected_classes.class_ids == ("pkg.a.Source",)
    assert result.selected_relations.relations == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.severity is DiagnosticSeverity.WARNING
    assert diagnostic.code == "ambiguous_relation_endpoint"
    assert diagnostic.origin_seam is OriginSeam.ANALYZE
    assert diagnostic.recoverability is Recoverability.RECOVERABLE
    assert diagnostic.failure_reason is None


def test_multi_class_seed_source_keeps_seed_classes_without_relation_or_dependency_selection() -> None:
    seed = module("pkg/a.py", classes=("pkg.a.One", "pkg.a.Two"))
    dependency = module("pkg/b.py", classes=("pkg.b.Target",))

    result = select(
        (dependency, seed),
        seeds=("pkg/a.py",),
        reachable=("pkg/a.py", "pkg/b.py"),
        edges=(("pkg/a.py", "pkg/b.py"),),
    )

    assert result.selected_classes.class_ids == ("pkg.a.One", "pkg.a.Two")
    assert "pkg.b.Target" not in result.selected_classes.class_ids
    assert result.selected_relations.relations == ()
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.severity is DiagnosticSeverity.WARNING
    assert diagnostic.code == "ambiguous_relation_endpoint"


def test_reachable_files_gate_seed_selection_and_ignore_stale_edge_endpoints() -> None:
    reachable_seed = module("pkg/a.py", classes=("pkg.a.Source",))
    provenance_only_seed = module("pkg/b.py", classes=("pkg.b.Source",))

    result = select(
        (reachable_seed, provenance_only_seed),
        seeds=("pkg/a.py", "pkg/b.py"),
        reachable=("pkg/a.py",),
        edges=(("pkg/a.py", "pkg/b.py"), ("pkg/b.py", "pkg/a.py")),
    )

    assert result.selected_classes.class_ids == ("pkg.a.Source",)
    assert "pkg.b.Source" not in result.selected_classes.class_ids
    assert result.selected_relations.relations == ()
    assert result.diagnostics == ()
    assert result.observations.warning_diagnostics == ()


def test_zero_class_source_or_target_ambiguity_warns_without_relation() -> None:
    empty_seed = module("pkg/empty_seed.py")
    target = module("pkg/target.py", classes=("pkg.target.Target",))
    source = module("pkg/source.py", classes=("pkg.source.Source",))
    empty_target = module("pkg/empty_target.py")

    result = select(
        (target, empty_seed, empty_target, source),
        seeds=("pkg/empty_seed.py",),
        reachable=("pkg/empty_seed.py", "pkg/target.py", "pkg/source.py", "pkg/empty_target.py"),
        edges=(
            ("pkg/empty_seed.py", "pkg/target.py"),
            ("pkg/source.py", "pkg/empty_target.py"),
        ),
    )

    assert result.selected_classes.class_ids == ()
    assert result.selected_relations.relations == ()
    assert len(result.diagnostics) == 2
    assert {diagnostic.code for diagnostic in result.diagnostics} == {"ambiguous_relation_endpoint"}


def test_observations_counters_and_diagnostics_carry_result_values() -> None:
    seed = module("pkg/a.py", classes=("pkg.a.Source",))
    seed_without_relation = module("pkg/seed_without_relation.py", classes=("pkg.seed_without_relation.Kept",))
    dependency = module("pkg/b.py", classes=("pkg.b.Target",))
    ambiguous_dependency = module("pkg/c.py", classes=("pkg.c.One", "pkg.c.Two"))

    result = select(
        (ambiguous_dependency, dependency, seed_without_relation, seed),
        seeds=("pkg/a.py", "pkg/seed_without_relation.py"),
        reachable=("pkg/a.py", "pkg/b.py", "pkg/c.py", "pkg/seed_without_relation.py"),
        edges=(("pkg/a.py", "pkg/b.py"), ("pkg/a.py", "pkg/c.py")),
    )

    assert result.observations.extracted_class_count == len(result.selected_classes.class_ids)
    assert result.observations.extracted_relation_count == len(result.selected_relations.relations)
    assert result.observations.warning_diagnostics == result.diagnostics
    assert result.observations.extracted_class_count == 3
    assert result.observations.extracted_relation_count == 1
    assert len(result.observations.warning_diagnostics) == 1


def test_deterministic_ordering_for_classes_relations_and_diagnostics() -> None:
    seed_b = module("pkg/b.py", classes=("pkg.b.Source",))
    seed_without_relation = module("pkg/seed_without_relation.py", classes=("pkg.seed_without_relation.Kept",))
    dependency_b = module("pkg/d.py", classes=("pkg.d.Target",))
    seed_a = module("pkg/a.py", classes=("pkg.a.Source",))
    dependency_a = module("pkg/c.py", classes=("pkg.c.Target",))
    ambiguous_a = module("pkg/ambiguous_a.py", classes=("pkg.ambiguous_a.Z", "pkg.ambiguous_a.A"))
    ambiguous_b = module("pkg/ambiguous_b.py", classes=("pkg.ambiguous_b.Z", "pkg.ambiguous_b.A"))

    result = select(
        (ambiguous_b, dependency_b, seed_without_relation, seed_b, ambiguous_a, dependency_a, seed_a),
        seeds=("pkg/b.py", "pkg/a.py", "pkg/seed_without_relation.py"),
        reachable=(
            "pkg/b.py",
            "pkg/d.py",
            "pkg/seed_without_relation.py",
            "pkg/a.py",
            "pkg/c.py",
            "pkg/ambiguous_b.py",
            "pkg/ambiguous_a.py",
        ),
        edges=(
            ("pkg/b.py", "pkg/d.py"),
            ("pkg/a.py", "pkg/c.py"),
            ("pkg/a.py", "pkg/ambiguous_b.py"),
            ("pkg/b.py", "pkg/ambiguous_a.py"),
        ),
    )

    assert result.selected_classes.class_ids == (
        "pkg.a.Source",
        "pkg.b.Source",
        "pkg.c.Target",
        "pkg.d.Target",
        "pkg.seed_without_relation.Kept",
    )
    assert result.selected_relations.relations == (
        SelectedRelation("pkg.a.Source", "pkg.c.Target", "uses", "module_import"),
        SelectedRelation("pkg.b.Source", "pkg.d.Target", "uses", "module_import"),
    )
    assert tuple(diagnostic.message for diagnostic in result.diagnostics) == tuple(
        sorted(diagnostic.message for diagnostic in result.diagnostics)
    )


def test_typed_relations_classify_base_field_and_method_references() -> None:
    seed = ParsedModule(
        module_path=Path("pkg/models.py"),
        classes=(
            "pkg/models.py:Base",
            "pkg/models.py:Customer",
            "pkg/models.py:Order",
            "pkg/models.py:Receipt",
        ),
        class_references=(
            reference("pkg/models.py:Order", "Base", "class_base", "base"),
            reference("pkg/models.py:Order", "Customer", "field_annotation", "customer", "direct"),
            reference(
                "pkg/models.py:Order",
                "Receipt",
                "method_return_annotation",
                "submit",
            ),
        ),
    )

    result = select((seed,), seeds=("pkg/models.py",), reachable=("pkg/models.py",))

    assert result.selected_relations.relations == (
        SelectedRelation("pkg/models.py:Order", "pkg/models.py:Base", "inherits", "class_base"),
        SelectedRelation("pkg/models.py:Order", "pkg/models.py:Customer", "composition", "field_annotation"),
        SelectedRelation("pkg/models.py:Order", "pkg/models.py:Receipt", "uses", "method_return_annotation"),
    )
    assert result.diagnostics == ()


def test_field_annotation_shapes_classify_composition_aggregation_and_method_uses() -> None:
    seed = ParsedModule(
        module_path=Path("pkg/models.py"),
        classes=(
            "pkg/models.py:Customer",
            "pkg/models.py:Coupon",
            "pkg/models.py:Item",
            "pkg/models.py:Order",
            "pkg/models.py:OrderLine",
            "pkg/models.py:Receipt",
        ),
        class_references=(
            reference("pkg/models.py:Order", "Customer", "field_annotation", "customer", "direct"),
            reference("pkg/models.py:Order", "Coupon", "field_annotation", "coupon", "optional"),
            reference("pkg/models.py:Order", "OrderLine", "field_annotation", "lines", "collection"),
            reference("pkg/models.py:Order", "Item", "field_annotation", "items_by_key", "mapping_value"),
            reference("pkg/models.py:Order", "Receipt", "method_return_annotation", "submit"),
        ),
    )

    result = select((seed,), seeds=("pkg/models.py",), reachable=("pkg/models.py",))

    assert result.selected_relations.relations == (
        SelectedRelation("pkg/models.py:Order", "pkg/models.py:Coupon", "aggregation", "field_annotation"),
        SelectedRelation("pkg/models.py:Order", "pkg/models.py:Customer", "composition", "field_annotation"),
        SelectedRelation("pkg/models.py:Order", "pkg/models.py:Item", "aggregation", "field_annotation"),
        SelectedRelation("pkg/models.py:Order", "pkg/models.py:OrderLine", "aggregation", "field_annotation"),
        SelectedRelation("pkg/models.py:Order", "pkg/models.py:Receipt", "uses", "method_return_annotation"),
    )
    assert result.diagnostics == ()


def test_unknown_generic_field_target_falls_back_to_association_not_composition() -> None:
    seed = ParsedModule(
        module_path=Path("pkg/models.py"),
        classes=("pkg/models.py:Source", "pkg/models.py:Target"),
        class_references=(
            reference("pkg/models.py:Source", "Target", "field_annotation", "boxed"),
        ),
    )

    result = select((seed,), seeds=("pkg/models.py",), reachable=("pkg/models.py",))

    assert result.selected_relations.relations == (
        SelectedRelation("pkg/models.py:Source", "pkg/models.py:Target", "association", "field_annotation"),
    )
    assert result.diagnostics == ()


def test_pep604_non_null_union_field_creates_aggregation_for_each_selected_target() -> None:
    seed = ParsedModule(
        module_path=Path("pkg/models.py"),
        classes=(
            "pkg/models.py:Card",
            "pkg/models.py:Invoice",
            "pkg/models.py:Payment",
        ),
        class_references=(
            reference("pkg/models.py:Payment", "Card", "field_annotation", "source", "union"),
            reference("pkg/models.py:Payment", "Invoice", "field_annotation", "source", "union"),
        ),
    )

    result = select((seed,), seeds=("pkg/models.py",), reachable=("pkg/models.py",))

    assert result.selected_relations.relations == (
        SelectedRelation("pkg/models.py:Payment", "pkg/models.py:Card", "aggregation", "field_annotation"),
        SelectedRelation("pkg/models.py:Payment", "pkg/models.py:Invoice", "aggregation", "field_annotation"),
    )
    assert result.diagnostics == ()


def test_relation_priority_prefers_composition_over_aggregation_association_and_uses() -> None:
    seed = ParsedModule(
        module_path=Path("pkg/models.py"),
        classes=("pkg/models.py:Source", "pkg/models.py:Target"),
        class_references=(
            reference("pkg/models.py:Source", "Target", "method_return_annotation", "make"),
            reference("pkg/models.py:Source", "Target", "field_annotation", "legacy"),
            reference("pkg/models.py:Source", "Target", "field_annotation", "maybe", "optional"),
            reference("pkg/models.py:Source", "Target", "field_annotation", "target", "direct"),
        ),
    )

    result = select((seed,), seeds=("pkg/models.py",), reachable=("pkg/models.py",))

    assert result.selected_relations.relations == (
        SelectedRelation("pkg/models.py:Source", "pkg/models.py:Target", "composition", "field_annotation"),
    )
    assert result.diagnostics == ()


def test_mixed_unknown_and_known_field_wrappers_keep_ownership_over_fallback() -> None:
    seed = ParsedModule(
        module_path=Path("pkg/models.py"),
        classes=("pkg/models.py:Source", "pkg/models.py:Target"),
        class_references=(
            reference("pkg/models.py:Source", "Target", "field_annotation", "union_box"),
            reference("pkg/models.py:Source", "Target", "field_annotation", "union_box", "union"),
            reference("pkg/models.py:Source", "Target", "field_annotation", "collection_box"),
            reference("pkg/models.py:Source", "Target", "field_annotation", "collection_box", "collection"),
        ),
    )

    result = select((seed,), seeds=("pkg/models.py",), reachable=("pkg/models.py",))

    assert result.selected_relations.relations == (
        SelectedRelation("pkg/models.py:Source", "pkg/models.py:Target", "aggregation", "field_annotation"),
    )
    assert result.diagnostics == ()


def test_protocol_marker_base_classifies_selected_protocol_target_as_realizes_without_external_warning() -> None:
    seed = ParsedModule(
        module_path=Path("pkg/models.py"),
        imports=("from typing import Any, Protocol",),
        classes=(
            "pkg/models.py:Repository",
            "pkg/models.py:SqlRepository",
            "pkg/models.py:AuditEvent",
        ),
        class_references=(
            reference("pkg/models.py:Repository", "Protocol", "class_base", "base"),
            reference("pkg/models.py:Repository", "AuditEvent", "method_return_annotation", "record"),
            reference("pkg/models.py:SqlRepository", "Repository", "class_base", "base"),
        ),
    )

    result = select((seed,), seeds=("pkg/models.py",), reachable=("pkg/models.py",))

    assert result.selected_relations.relations == (
        SelectedRelation("pkg/models.py:Repository", "pkg/models.py:AuditEvent", "uses", "method_return_annotation"),
        SelectedRelation("pkg/models.py:SqlRepository", "pkg/models.py:Repository", "realizes", "class_base"),
    )
    assert result.diagnostics == ()


def test_imported_bare_protocol_marker_wins_over_internal_protocol_class_in_other_module() -> None:
    contracts = ParsedModule(
        module_path=Path("pkg/contracts.py"),
        imports=("from typing import Protocol",),
        classes=(
            "pkg/contracts.py:Repository",
            "pkg/contracts.py:Impl",
        ),
        class_references=(
            reference("pkg/contracts.py:Repository", "Protocol", "class_base", "base"),
            reference("pkg/contracts.py:Impl", "Repository", "class_base", "base"),
        ),
    )
    names = ParsedModule(
        module_path=Path("pkg/names.py"),
        classes=("pkg/names.py:Protocol",),
    )

    result = select(
        (contracts, names),
        seeds=("pkg/contracts.py", "pkg/names.py"),
        reachable=("pkg/contracts.py", "pkg/names.py"),
    )

    assert result.selected_relations.relations == (
        SelectedRelation("pkg/contracts.py:Impl", "pkg/contracts.py:Repository", "realizes", "class_base"),
    )
    assert result.diagnostics == ()


def test_internal_normal_protocol_class_is_inherited_not_treated_as_marker() -> None:
    seed = ParsedModule(
        module_path=Path("pkg/models.py"),
        classes=(
            "pkg/models.py:Protocol",
            "pkg/models.py:Foo",
        ),
        class_references=(
            reference("pkg/models.py:Foo", "Protocol", "class_base", "base"),
        ),
    )

    result = select((seed,), seeds=("pkg/models.py",), reachable=("pkg/models.py",))

    assert result.selected_relations.relations == (
        SelectedRelation("pkg/models.py:Foo", "pkg/models.py:Protocol", "inherits", "class_base"),
    )
    assert result.diagnostics == ()


def test_aliased_typing_protocol_does_not_make_bare_protocol_base_a_marker() -> None:
    seed = ParsedModule(
        module_path=Path("pkg/models.py"),
        imports=("from typing import Protocol as TypingProtocol",),
        classes=(
            "pkg/models.py:Protocol",
            "pkg/models.py:Foo",
        ),
        class_references=(
            reference("pkg/models.py:Foo", "Protocol", "class_base", "base"),
        ),
    )

    result = select((seed,), seeds=("pkg/models.py",), reachable=("pkg/models.py",))

    assert result.selected_relations.relations == (
        SelectedRelation("pkg/models.py:Foo", "pkg/models.py:Protocol", "inherits", "class_base"),
    )
    assert result.diagnostics == ()


def test_method_only_like_base_is_inherited_not_realized_without_protocol_marker() -> None:
    seed = ParsedModule(
        module_path=Path("pkg/models.py"),
        classes=(
            "pkg/models.py:MethodOnly",
            "pkg/models.py:Impl",
        ),
        class_references=(
            reference("pkg/models.py:Impl", "MethodOnly", "class_base", "base"),
        ),
    )

    result = select((seed,), seeds=("pkg/models.py",), reachable=("pkg/models.py",))

    assert result.selected_relations.relations == (
        SelectedRelation("pkg/models.py:Impl", "pkg/models.py:MethodOnly", "inherits", "class_base"),
    )
    assert result.diagnostics == ()


def test_qualified_protocol_marker_bases_are_supported_without_abc_or_method_only_heuristics() -> None:
    seed = ParsedModule(
        module_path=Path("pkg/models.py"),
        classes=(
            "pkg/models.py:AbstractBase",
            "pkg/models.py:Concrete",
            "pkg/models.py:QualifiedProtocol",
            "pkg/models.py:QualifiedImpl",
            "pkg/models.py:ExtensionProtocol",
            "pkg/models.py:ExtensionImpl",
            "pkg/models.py:MethodOnly",
        ),
        class_references=(
            reference("pkg/models.py:AbstractBase", "ABC", "class_base", "base"),
            reference("pkg/models.py:Concrete", "AbstractBase", "class_base", "base"),
            reference("pkg/models.py:QualifiedProtocol", "typing.Protocol", "class_base", "base"),
            reference("pkg/models.py:QualifiedImpl", "QualifiedProtocol", "class_base", "base"),
            reference("pkg/models.py:ExtensionProtocol", "typing_extensions.Protocol", "class_base", "base"),
            reference("pkg/models.py:ExtensionImpl", "ExtensionProtocol", "class_base", "base"),
            reference("pkg/models.py:Concrete", "QualifiedProtocol", "method_parameter_annotation", "protocol"),
            reference("pkg/models.py:MethodOnly", "Concrete", "method_return_annotation", "make"),
        ),
    )

    result = select((seed,), seeds=("pkg/models.py",), reachable=("pkg/models.py",))

    assert result.selected_relations.relations == (
        SelectedRelation("pkg/models.py:Concrete", "pkg/models.py:AbstractBase", "inherits", "class_base"),
        SelectedRelation(
            "pkg/models.py:Concrete",
            "pkg/models.py:QualifiedProtocol",
            "uses",
            "method_parameter_annotation",
        ),
        SelectedRelation("pkg/models.py:ExtensionImpl", "pkg/models.py:ExtensionProtocol", "realizes", "class_base"),
        SelectedRelation("pkg/models.py:MethodOnly", "pkg/models.py:Concrete", "uses", "method_return_annotation"),
        SelectedRelation("pkg/models.py:QualifiedImpl", "pkg/models.py:QualifiedProtocol", "realizes", "class_base"),
    )
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["typed_relation_unresolved"]
    assert_typed_warning_payload(
        result.diagnostics[0],
        code="typed_relation_unresolved",
        source_class_id="pkg/models.py:AbstractBase",
        target_name="ABC",
        reference_kind="class_base",
        reference_owner="base",
    )


def test_class_base_unresolved_and_selection_outside_warn_without_invented_relation() -> None:
    seed = ParsedModule(
        module_path=Path("pkg/source.py"),
        classes=("pkg/source.py:Source",),
        class_references=(
            reference("pkg/source.py:Source", "MissingBase", "class_base", "base"),
            reference("pkg/source.py:Source", "OutsideBase", "class_base", "base"),
        ),
    )
    outside = module("pkg/outside.py", classes=("pkg/outside.py:OutsideBase",))

    result = select(
        (outside, seed),
        seeds=("pkg/source.py",),
        reachable=("pkg/source.py", "pkg/outside.py"),
    )

    assert result.selected_relations.relations == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "typed_relation_selection_outside",
        "typed_relation_unresolved",
    ]
    assert_typed_warning_payload(
        result.diagnostics[0],
        code="typed_relation_selection_outside",
        source_class_id="pkg/source.py:Source",
        target_name="OutsideBase",
        reference_kind="class_base",
        reference_owner="base",
        candidates=("pkg/outside.py:OutsideBase",),
    )
    assert_typed_warning_payload(
        result.diagnostics[1],
        code="typed_relation_unresolved",
        source_class_id="pkg/source.py:Source",
        target_name="MissingBase",
        reference_kind="class_base",
        reference_owner="base",
    )


def test_unselected_internal_protocol_base_warns_without_marker_or_relation() -> None:
    seed = ParsedModule(
        module_path=Path("pkg/source.py"),
        classes=("pkg/source.py:Foo",),
        class_references=(
            reference("pkg/source.py:Foo", "Protocol", "class_base", "base"),
        ),
    )
    outside = module("pkg/outside.py", classes=("pkg/outside.py:Protocol",))

    result = select(
        (outside, seed),
        seeds=("pkg/source.py",),
        reachable=("pkg/source.py", "pkg/outside.py"),
    )

    assert result.selected_relations.relations == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["typed_relation_selection_outside"]
    assert_typed_warning_payload(
        result.diagnostics[0],
        code="typed_relation_selection_outside",
        source_class_id="pkg/source.py:Foo",
        target_name="Protocol",
        reference_kind="class_base",
        reference_owner="base",
        candidates=("pkg/outside.py:Protocol",),
    )


def test_typed_relation_resolver_accepts_full_id_module_qualified_short_name_and_same_module() -> None:
    same_module = ParsedModule(
        module_path=Path("pkg/models.py"),
        classes=(
            "pkg/models.py:Source",
            "pkg/models.py:Exact",
            "pkg/models.py:Qualified",
            "pkg/models.py:Shared",
        ),
        class_references=(
            reference("pkg/models.py:Source", "pkg/models.py:Exact", "field_annotation", "exact", "direct"),
            reference("pkg/models.py:Source", "pkg.models.Qualified", "field_annotation", "qualified", "direct"),
            reference("pkg/models.py:Source", "Shared", "field_annotation", "same_module", "direct"),
        ),
    )
    other_module = module("pkg/other.py", classes=("pkg/other.py:Shared",))

    result = select(
        (same_module, other_module),
        seeds=("pkg/models.py",),
        reachable=("pkg/models.py", "pkg/other.py"),
    )

    assert result.selected_relations.relations == (
        SelectedRelation("pkg/models.py:Source", "pkg/models.py:Exact", "composition", "field_annotation"),
        SelectedRelation("pkg/models.py:Source", "pkg/models.py:Qualified", "composition", "field_annotation"),
        SelectedRelation("pkg/models.py:Source", "pkg/models.py:Shared", "composition", "field_annotation"),
    )
    assert result.diagnostics == ()


def test_typed_relation_warnings_are_recoverable_analyze_diagnostics() -> None:
    seed = ParsedModule(
        module_path=Path("pkg/source.py"),
        classes=("pkg/source.py:Source",),
        class_references=(
            reference("pkg/source.py:Source", "Missing", "field_annotation", "missing"),
            reference("pkg/source.py:Source", "Duplicate", "field_annotation", "ambiguous"),
            reference("pkg/source.py:Source", "Outside", "field_annotation", "outside"),
        ),
    )
    duplicate_a = module("pkg/a.py", classes=("pkg/a.py:Duplicate",))
    duplicate_b = module("pkg/b.py", classes=("pkg/b.py:Duplicate",))
    outside = module("pkg/outside.py", classes=("pkg/outside.py:Outside",))

    result = select(
        (duplicate_a, duplicate_b, outside, seed),
        seeds=("pkg/source.py",),
        reachable=("pkg/source.py", "pkg/a.py", "pkg/b.py", "pkg/outside.py"),
    )

    assert result.selected_relations.relations == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "typed_relation_ambiguous",
        "typed_relation_selection_outside",
        "typed_relation_unresolved",
    ]
    assert_typed_warning_payload(
        result.diagnostics[0],
        code="typed_relation_ambiguous",
        source_class_id="pkg/source.py:Source",
        target_name="Duplicate",
        reference_kind="field_annotation",
        reference_owner="ambiguous",
        candidates=("pkg/a.py:Duplicate", "pkg/b.py:Duplicate"),
    )
    assert_typed_warning_payload(
        result.diagnostics[1],
        code="typed_relation_selection_outside",
        source_class_id="pkg/source.py:Source",
        target_name="Outside",
        reference_kind="field_annotation",
        reference_owner="outside",
        candidates=("pkg/outside.py:Outside",),
    )
    assert_typed_warning_payload(
        result.diagnostics[2],
        code="typed_relation_unresolved",
        source_class_id="pkg/source.py:Source",
        target_name="Missing",
        reference_kind="field_annotation",
        reference_owner="missing",
    )


def test_typed_relation_short_name_ambiguity_is_resolved_before_selected_set_filtering() -> None:
    source = ParsedModule(
        module_path=Path("pkg/source.py"),
        classes=("pkg/source.py:Source",),
        class_references=(
            reference("pkg/source.py:Source", "Target", "field_annotation", "target"),
        ),
    )
    selected_target = module("pkg/selected.py", classes=("pkg/selected.py:Target",))
    reachable_duplicate = module("pkg/duplicate.py", classes=("pkg/duplicate.py:Target",))

    result = select(
        (reachable_duplicate, selected_target, source),
        seeds=("pkg/source.py", "pkg/selected.py"),
        reachable=("pkg/source.py", "pkg/selected.py", "pkg/duplicate.py"),
    )

    assert result.selected_classes.class_ids == ("pkg/selected.py:Target", "pkg/source.py:Source")
    assert result.selected_relations.relations == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["typed_relation_ambiguous"]
    assert_typed_warning_payload(
        result.diagnostics[0],
        code="typed_relation_ambiguous",
        source_class_id="pkg/source.py:Source",
        target_name="Target",
        reference_kind="field_annotation",
        reference_owner="target",
        candidates=("pkg/duplicate.py:Target", "pkg/selected.py:Target"),
    )


def test_typed_relation_selected_outside_does_not_expand_selected_classes() -> None:
    seed = ParsedModule(
        module_path=Path("pkg/source.py"),
        classes=("pkg/source.py:Source",),
        class_references=(
            reference("pkg/source.py:Source", "Outside", "field_annotation", "outside"),
        ),
    )
    outside = module("pkg/outside.py", classes=("pkg/outside.py:Outside",))

    result = select(
        (outside, seed),
        seeds=("pkg/source.py",),
        reachable=("pkg/source.py", "pkg/outside.py"),
    )

    assert result.selected_classes.class_ids == ("pkg/source.py:Source",)
    assert result.selected_relations.relations == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "typed_relation_selection_outside"
    ]


def test_typed_relation_unselected_source_is_ignored_without_warning() -> None:
    unselected_source = ParsedModule(
        module_path=Path("pkg/unselected.py"),
        classes=("pkg/unselected.py:Source",),
        class_references=(
            reference("pkg/unselected.py:Source", "Target", "field_annotation", "target"),
        ),
    )
    seed = module("pkg/target.py", classes=("pkg/target.py:Target",))

    result = select(
        (seed, unselected_source),
        seeds=("pkg/target.py",),
        reachable=("pkg/target.py", "pkg/unselected.py"),
    )

    assert result.selected_classes.class_ids == ("pkg/target.py:Target",)
    assert result.selected_relations.relations == ()
    assert result.diagnostics == ()


def test_typed_relation_dedupe_prefers_canonical_relation_and_evidence_kind() -> None:
    seed = ParsedModule(
        module_path=Path("pkg/models.py"),
        classes=("pkg/models.py:Source", "pkg/models.py:Target"),
        class_references=(
            reference("pkg/models.py:Source", "Target", "method_return_annotation", "make"),
            reference("pkg/models.py:Source", "Target", "field_annotation", "target", "direct"),
            reference("pkg/models.py:Source", "Target", "init_field_annotation", "target", "direct"),
            reference("pkg/models.py:Source", "Target", "method_parameter_annotation", "use.target"),
            reference("pkg/models.py:Source", "Target", "class_base", "base"),
        ),
    )

    result = select((seed,), seeds=("pkg/models.py",), reachable=("pkg/models.py",))

    assert result.selected_relations.relations == (
        SelectedRelation("pkg/models.py:Source", "pkg/models.py:Target", "inherits", "class_base"),
    )
    assert result.diagnostics == ()


def test_association_evidence_priority_without_higher_relation_type_masking() -> None:
    seed = ParsedModule(
        module_path=Path("pkg/models.py"),
        classes=("pkg/models.py:Source", "pkg/models.py:Target"),
        class_references=(
            reference("pkg/models.py:Source", "Target", "pydantic_forward_ref", "child"),
            reference("pkg/models.py:Source", "Target", "init_field_annotation", "__init__.target"),
            reference("pkg/models.py:Source", "Target", "field_annotation", "target"),
        ),
    )

    result = select((seed,), seeds=("pkg/models.py",), reachable=("pkg/models.py",))

    assert result.selected_relations.relations == (
        SelectedRelation("pkg/models.py:Source", "pkg/models.py:Target", "association", "field_annotation"),
    )
    assert result.diagnostics == ()


def test_uses_evidence_priority_without_higher_relation_type_masking() -> None:
    seed = ParsedModule(
        module_path=Path("pkg/source.py"),
        classes=("pkg/source.py:Source",),
        class_references=(
            reference("pkg/source.py:Source", "Target", "pydantic_forward_ref", "forward"),
            reference("pkg/source.py:Source", "Target", "method_return_annotation", "build"),
            reference("pkg/source.py:Source", "Target", "method_parameter_annotation", "submit.target"),
        ),
    )
    target = module("pkg/target.py", classes=("pkg/target.py:Target",))

    result = select(
        (seed, target),
        seeds=("pkg/source.py",),
        reachable=("pkg/source.py", "pkg/target.py"),
        edges=(("pkg/source.py", "pkg/target.py"),),
    )

    assert result.selected_relations.relations == (
        SelectedRelation("pkg/source.py:Source", "pkg/target.py:Target", "uses", "method_parameter_annotation"),
    )
    assert result.diagnostics == ()


def test_module_import_fallback_survives_only_without_semantic_endpoint_relation() -> None:
    source = ParsedModule(
        module_path=Path("pkg/source.py"),
        classes=("pkg/source.py:Source",),
        class_references=(
            reference("pkg/source.py:Source", "Semantic", "field_annotation", "semantic"),
        ),
    )
    semantic_target = module("pkg/semantic.py", classes=("pkg/semantic.py:Semantic",))
    fallback_target = module("pkg/fallback.py", classes=("pkg/fallback.py:Fallback",))

    result = select(
        (fallback_target, semantic_target, source),
        seeds=("pkg/source.py",),
        reachable=("pkg/source.py", "pkg/semantic.py", "pkg/fallback.py"),
        edges=(
            ("pkg/source.py", "pkg/semantic.py"),
            ("pkg/source.py", "pkg/fallback.py"),
        ),
    )

    assert result.selected_relations.relations == (
        SelectedRelation("pkg/source.py:Source", "pkg/fallback.py:Fallback", "uses", "module_import"),
        SelectedRelation("pkg/source.py:Source", "pkg/semantic.py:Semantic", "association", "field_annotation"),
    )
    assert result.diagnostics == ()


def test_s03_001_dependency_evidence_selects_same_module_target_class() -> None:
    seed = ParsedModule(
        module_path=Path("pkg/source.py"),
        classes=("pkg/source.py:A", "pkg/source.py:B"),
        class_references=(
            reference("pkg/source.py:A", "B", "direct_class_call", "make@3:15"),
            reference("pkg/source.py:A", "B", "direct_class_call", "__init__@6:17"),
        ),
    )

    result = select((seed,), seeds=("pkg/source.py",), reachable=("pkg/source.py",))

    assert result.selected_classes.class_ids == ("pkg/source.py:A", "pkg/source.py:B")
    assert result.selected_relations.relations == (
        SelectedRelation("pkg/source.py:A", "pkg/source.py:B", "dependency", "direct_class_call"),
    )
    assert result.diagnostics == ()


def test_s03_002_explicit_from_import_resolves_multi_class_target_dependency() -> None:
    source = ParsedModule(
        module_path=Path("pkg/source.py"),
        imports=("from pkg.target import B",),
        classes=("pkg/source.py:A",),
        class_references=(
            reference("pkg/source.py:A", "B", "direct_class_call", "make@4:15"),
        ),
    )
    target = module("pkg/target.py", classes=("pkg/target.py:B", "pkg/target.py:Helper"))

    result = select(
        (source, target),
        seeds=("pkg/source.py",),
        reachable=("pkg/source.py", "pkg/target.py"),
        import_candidate_paths={"from pkg.target import B": ("pkg/target.py",)},
    )

    assert result.selected_classes.class_ids == ("pkg/source.py:A", "pkg/target.py:B")
    assert result.selected_relations.relations == (
        SelectedRelation("pkg/source.py:A", "pkg/target.py:B", "dependency", "direct_class_call"),
    )
    assert "pkg/target.py:Helper" not in result.selected_classes.class_ids
    assert result.diagnostics == ()


def test_s03_002_dependency_direct_use_wins_over_single_class_import_fallback() -> None:
    source = ParsedModule(
        module_path=Path("pkg/source.py"),
        imports=("from pkg.target import B",),
        classes=("pkg/source.py:A",),
        class_references=(
            reference("pkg/source.py:A", "B", "direct_class_call", "make@4:15"),
        ),
    )
    target = module("pkg/target.py", classes=("pkg/target.py:B",))

    result = select(
        (source, target),
        seeds=("pkg/source.py",),
        reachable=("pkg/source.py", "pkg/target.py"),
        edges=(("pkg/source.py", "pkg/target.py"),),
        import_candidate_paths={"from pkg.target import B": ("pkg/target.py",)},
    )

    assert result.selected_relations.relations == (
        SelectedRelation("pkg/source.py:A", "pkg/target.py:B", "dependency", "direct_class_call"),
    )
    assert result.diagnostics == ()


def test_s03_003_alias_relative_and_module_qualified_imports_resolve_dependency_targets() -> None:
    alias_source = ParsedModule(
        module_path=Path("pkg/alias_source.py"),
        imports=("from pkg.target import B as AliasB",),
        classes=("pkg/alias_source.py:A",),
        class_references=(
            reference("pkg/alias_source.py:A", "AliasB", "direct_class_call", "make@4:15"),
        ),
    )
    relative_source = ParsedModule(
        module_path=Path("pkg/relative_source.py"),
        imports=("from .target import B",),
        classes=("pkg/relative_source.py:A",),
        class_references=(
            reference("pkg/relative_source.py:A", "B", "direct_class_call", "make@4:15"),
        ),
    )
    qualified_source = ParsedModule(
        module_path=Path("pkg/qualified_source.py"),
        imports=("pkg.target",),
        classes=("pkg/qualified_source.py:A",),
        class_references=(
            reference(
                "pkg/qualified_source.py:A",
                "pkg.target.B",
                "direct_class_member_access",
                "make@4:15",
            ),
        ),
    )
    target = module("pkg/target.py", classes=("pkg/target.py:B", "pkg/target.py:Helper"))

    result = select(
        (alias_source, qualified_source, relative_source, target),
        seeds=("pkg/alias_source.py", "pkg/relative_source.py", "pkg/qualified_source.py"),
        reachable=("pkg/alias_source.py", "pkg/relative_source.py", "pkg/qualified_source.py", "pkg/target.py"),
        import_candidate_paths={
            "from pkg.target import B as AliasB": ("pkg/target.py",),
            "from .target import B": ("pkg/target.py",),
            "pkg.target": ("pkg/target.py",),
        },
    )

    assert result.selected_classes.class_ids == (
        "pkg/alias_source.py:A",
        "pkg/qualified_source.py:A",
        "pkg/relative_source.py:A",
        "pkg/target.py:B",
    )
    assert result.selected_relations.relations == (
        SelectedRelation("pkg/alias_source.py:A", "pkg/target.py:B", "dependency", "direct_class_call"),
        SelectedRelation(
            "pkg/qualified_source.py:A",
            "pkg/target.py:B",
            "dependency",
            "direct_class_member_access",
        ),
        SelectedRelation("pkg/relative_source.py:A", "pkg/target.py:B", "dependency", "direct_class_call"),
    )
    assert "pkg/target.py:Helper" not in result.selected_classes.class_ids
    assert result.diagnostics == ()


def test_s03_004_dependency_ambiguity_import_only_and_priority_guards() -> None:
    source = ParsedModule(
        module_path=Path("pkg/source.py"),
        imports=(
            "from pkg.imported import ImportedOnly",
            "from pkg.owned import Owned",
            "from pkg.one import Duplicate",
            "from pkg.outside import Outside",
            "from pkg.two import Duplicate",
        ),
        classes=("pkg/source.py:A", "pkg/source.py:Structural"),
        class_references=(
            reference("pkg/source.py:A", "Duplicate", "direct_class_call", "ambiguous@4:15"),
            reference("pkg/source.py:A", "target.B", "direct_class_member_access", "not_imported@5:15"),
            reference("pkg/source.py:A", "Outside", "direct_class_call", "outside@6:15"),
            reference("pkg/source.py:Structural", "Owned", "field_annotation", "owned", "direct"),
            reference("pkg/source.py:Structural", "Owned", "direct_class_call", "make@7:15"),
        ),
    )
    duplicate_a = module("pkg/one.py", classes=("pkg/one.py:Duplicate",))
    duplicate_b = module("pkg/two.py", classes=("pkg/two.py:Duplicate",))
    imported_only = module("pkg/imported.py", classes=("pkg/imported.py:ImportedOnly",))
    owned = module("pkg/owned.py", classes=("pkg/owned.py:Owned",))
    outside = module("pkg/outside.py", classes=("pkg/outside.py:Outside",))
    not_imported_target = module("pkg/target.py", classes=("pkg/target.py:B",))

    result = select(
        (duplicate_a, duplicate_b, imported_only, not_imported_target, outside, owned, source),
        seeds=("pkg/source.py",),
        reachable=("pkg/source.py", "pkg/one.py", "pkg/two.py", "pkg/imported.py", "pkg/owned.py", "pkg/target.py"),
        edges=(("pkg/source.py", "pkg/imported.py"),),
        import_candidate_paths={
            "from pkg.imported import ImportedOnly": ("pkg/imported.py",),
            "from pkg.owned import Owned": ("pkg/owned.py",),
            "from pkg.one import Duplicate": ("pkg/one.py",),
            "from pkg.outside import Outside": ("pkg/outside.py",),
            "from pkg.two import Duplicate": ("pkg/two.py",),
        },
    )

    assert result.selected_classes.class_ids == (
        "pkg/owned.py:Owned",
        "pkg/source.py:A",
        "pkg/source.py:Structural",
    )
    assert result.selected_relations.relations == (
        SelectedRelation("pkg/source.py:Structural", "pkg/owned.py:Owned", "composition", "field_annotation"),
    )
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "ambiguous_relation_endpoint",
        "dependency_relation_ambiguous",
        "dependency_relation_selection_outside",
        "dependency_relation_unresolved",
    ]
