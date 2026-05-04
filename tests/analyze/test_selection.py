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
) -> ClassReference:
    return ClassReference(
        source_class_id=source_class_id,
        target_name=target_name,
        reference_kind=reference_kind,
        reference_owner=reference_owner,
    )


def module_index(modules: tuple[ParsedModule, ...], *, seeds: tuple[str, ...]) -> ModuleIndex:
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
        import_candidate_paths={},
    )


def observations(*seeds: str) -> TraversalObservations:
    return TraversalObservations(seed_project_relative_paths=tuple(Path(seed) for seed in seeds))


def select(
    modules: tuple[ParsedModule, ...],
    *,
    seeds: tuple[str, ...],
    reachable: tuple[str, ...],
    edges: tuple[tuple[str, str], ...] = (),
) -> SelectionResult:
    return select_classes_and_relations(
        modules,
        module_index(modules, seeds=seeds),
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
            reference("pkg/models.py:Order", "Customer", "field_annotation", "customer"),
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
        SelectedRelation("pkg/models.py:Order", "pkg/models.py:Customer", "association", "field_annotation"),
        SelectedRelation("pkg/models.py:Order", "pkg/models.py:Receipt", "uses", "method_return_annotation"),
    )
    assert result.diagnostics == ()


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
            reference("pkg/models.py:Source", "pkg/models.py:Exact", "field_annotation", "exact"),
            reference("pkg/models.py:Source", "pkg.models.Qualified", "field_annotation", "qualified"),
            reference("pkg/models.py:Source", "Shared", "field_annotation", "same_module"),
        ),
    )
    other_module = module("pkg/other.py", classes=("pkg/other.py:Shared",))

    result = select(
        (same_module, other_module),
        seeds=("pkg/models.py",),
        reachable=("pkg/models.py", "pkg/other.py"),
    )

    assert result.selected_relations.relations == (
        SelectedRelation("pkg/models.py:Source", "pkg/models.py:Exact", "association", "field_annotation"),
        SelectedRelation("pkg/models.py:Source", "pkg/models.py:Qualified", "association", "field_annotation"),
        SelectedRelation("pkg/models.py:Source", "pkg/models.py:Shared", "association", "field_annotation"),
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
            reference("pkg/models.py:Source", "Target", "field_annotation", "target"),
            reference("pkg/models.py:Source", "Target", "init_field_annotation", "target"),
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
