from pathlib import Path

from pyclassuml.analyze import (
    SelectedRelation,
    SelectionResult,
    TraversalObservations,
    select_classes_and_relations,
)
from pyclassuml.analyze.selection import SelectedRelation as SelectionModuleSelectedRelation
from pyclassuml.model import (
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
