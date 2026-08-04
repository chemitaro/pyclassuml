from pathlib import Path

from pyclassuml.analyze import (
    DEFAULT_TRAVERSAL_MODULE_LIMIT,
    TraversalObservations,
    TraversalResult,
    traverse_dependencies,
)
from pyclassuml.model import (
    AnalysisConfig,
    DependencyGraph,
    DiagnosticSeverity,
    ExecutionContext,
    FailureReason,
    OriginSeam,
    ParsedModule,
    Recoverability,
)
from pyclassuml.parse import ModuleIndex


def context(project_root: Path, *, package_root: Path | None = None, scope_root: Path | None = None) -> ExecutionContext:
    return ExecutionContext(
        execution_cwd=project_root.resolve(),
        project_root=project_root.resolve(),
        package_root=(package_root or project_root).resolve(),
        scope_root=(scope_root or project_root).resolve(),
    )


def module(path: str, imports: tuple[str, ...] = ()) -> ParsedModule:
    return ParsedModule(module_path=Path(path), imports=imports)


def module_index(
    modules: tuple[ParsedModule, ...],
    *,
    seeds: tuple[str, ...],
    candidates: dict[str, tuple[str, ...]] | None = None,
) -> ModuleIndex:
    module_by_path = {parsed.module_path: parsed for parsed in modules}
    return ModuleIndex(
        module_by_path=module_by_path,
        project_relative_file_to_module={path: path for path in module_by_path},
        class_to_module={},
        seed_project_relative_paths=tuple(Path(seed) for seed in seeds),
        import_candidate_paths={
            import_text: tuple(Path(candidate) for candidate in candidate_paths)
            for import_text, candidate_paths in (candidates or {}).items()
        },
    )


def test_seed_only_result_shape_seed_provenance_and_reachable_file_count(tmp_path: Path) -> None:
    seed = module("pkg/a.py")
    result = traverse_dependencies(
        (seed,),
        module_index((seed,), seeds=("pkg/a.py",)),
        context(tmp_path, package_root=tmp_path / "pkg", scope_root=tmp_path / "pkg"),
        AnalysisConfig(),
    )

    assert isinstance(result, TraversalResult)
    assert result.graph == DependencyGraph(reachable_files=(Path("pkg/a.py"),), edges=())
    assert isinstance(result.observations, TraversalObservations)
    assert result.observations.seed_project_relative_paths == (Path("pkg/a.py"),)
    assert result.observations.reachable_file_count == 1
    assert result.observations.package_stop_count == 0
    assert result.observations.scope_stop_count == 0
    assert result.observations.depth_stop_count == 0
    assert result.observations.traversal_limit_reached is False
    assert result.diagnostics == ()
    assert DEFAULT_TRAVERSAL_MODULE_LIMIT == 1000


def test_depth_zero_keeps_seed_only(tmp_path: Path) -> None:
    seed = module("pkg/a.py", imports=("pkg.b",))
    dependency = module("pkg/b.py")

    result = traverse_dependencies(
        (seed, dependency),
        module_index(
            (seed, dependency),
            seeds=("pkg/a.py",),
            candidates={"pkg.b": ("pkg/b.py",)},
        ),
        context(tmp_path, package_root=tmp_path / "pkg", scope_root=tmp_path / "pkg"),
        AnalysisConfig(depth=0),
    )

    assert result.graph.reachable_files == (Path("pkg/a.py"),)
    assert result.graph.edges == ()
    assert result.observations.depth_stop_count == 1
    assert result.observations.reachable_file_count == 1


def test_depth_one_includes_direct_import_only(tmp_path: Path) -> None:
    seed = module("pkg/a.py", imports=("pkg.b",))
    direct = module("pkg/b.py", imports=("pkg.c",))
    transitive = module("pkg/c.py")

    result = traverse_dependencies(
        (seed, direct, transitive),
        module_index(
            (seed, direct, transitive),
            seeds=("pkg/a.py",),
            candidates={"pkg.b": ("pkg/b.py",), "pkg.c": ("pkg/c.py",)},
        ),
        context(tmp_path, package_root=tmp_path / "pkg", scope_root=tmp_path / "pkg"),
        AnalysisConfig(depth=1),
    )

    assert result.graph.reachable_files == (Path("pkg/a.py"), Path("pkg/b.py"))
    assert result.graph.edges == ((Path("pkg/a.py"), Path("pkg/b.py")),)
    assert result.observations.depth_stop_count == 1
    assert result.observations.reachable_file_count == 2


def test_multiple_import_candidates_share_same_hop(tmp_path: Path) -> None:
    seed = module("pkg/a.py", imports=("pkg.models",))
    module_file = module("pkg/models.py")
    package_init = module("pkg/models/__init__.py")

    result = traverse_dependencies(
        (package_init, seed, module_file),
        module_index(
            (package_init, seed, module_file),
            seeds=("pkg/a.py",),
            candidates={
                "pkg.models": ("pkg/models.py", "pkg/models/__init__.py"),
            },
        ),
        context(tmp_path, package_root=tmp_path / "pkg", scope_root=tmp_path / "pkg"),
        AnalysisConfig(depth=1),
    )

    assert result.graph.reachable_files == (
        Path("pkg/a.py"),
        Path("pkg/models/__init__.py"),
        Path("pkg/models.py"),
    )
    assert result.graph.edges == (
        (Path("pkg/a.py"), Path("pkg/models/__init__.py")),
        (Path("pkg/a.py"), Path("pkg/models.py")),
    )
    assert result.observations.depth_stop_count == 0


def test_depth_none_traverses_transitively(tmp_path: Path) -> None:
    seed = module("pkg/a.py", imports=("pkg.b",))
    direct = module("pkg/b.py", imports=("pkg.c",))
    transitive = module("pkg/c.py")

    result = traverse_dependencies(
        (seed, direct, transitive),
        module_index(
            (seed, direct, transitive),
            seeds=("pkg/a.py",),
            candidates={"pkg.b": ("pkg/b.py",), "pkg.c": ("pkg/c.py",)},
        ),
        context(tmp_path, package_root=tmp_path / "pkg", scope_root=tmp_path / "pkg"),
        AnalysisConfig(depth=None),
    )

    assert result.graph.reachable_files == (Path("pkg/a.py"), Path("pkg/b.py"), Path("pkg/c.py"))
    assert result.graph.edges == (
        (Path("pkg/a.py"), Path("pkg/b.py")),
        (Path("pkg/b.py"), Path("pkg/c.py")),
    )
    assert result.observations.depth_stop_count == 0
    assert result.observations.reachable_file_count == 3


def test_unreachable_parsed_module_is_excluded(tmp_path: Path) -> None:
    seed = module("pkg/a.py")
    unreachable = module("pkg/unreachable.py")

    result = traverse_dependencies(
        (seed, unreachable),
        module_index((seed, unreachable), seeds=("pkg/a.py",)),
        context(tmp_path, package_root=tmp_path / "pkg", scope_root=tmp_path / "pkg"),
        AnalysisConfig(),
    )

    assert result.graph.reachable_files == (Path("pkg/a.py"),)
    assert Path("pkg/unreachable.py") not in result.graph.reachable_files


def test_boundary_and_depth_stop_counts_follow_ordering(tmp_path: Path) -> None:
    seed = module(
        "pkg/app/a.py",
        imports=("depth.blocked", "outside.package", "outside.scope", "package.first"),
    )
    depth_blocked = module("pkg/app/depth_blocked.py")
    outside_scope = module("pkg/shared.py")

    result = traverse_dependencies(
        (seed, depth_blocked, outside_scope),
        module_index(
            (seed, depth_blocked, outside_scope),
            seeds=("pkg/app/a.py",),
            candidates={
                "depth.blocked": ("pkg/app/depth_blocked.py",),
                "outside.package": ("tools/helper.py",),
                "outside.scope": ("pkg/shared.py",),
                "package.first": ("other/shared.py",),
            },
        ),
        context(tmp_path, package_root=tmp_path / "pkg", scope_root=tmp_path / "pkg" / "app"),
        AnalysisConfig(depth=0),
    )

    assert result.graph.reachable_files == (Path("pkg/app/a.py"),)
    assert result.graph.edges == ()
    assert result.observations.package_stop_count == 2
    assert result.observations.scope_stop_count == 1
    assert result.observations.depth_stop_count == 1
    assert result.observations.reachable_file_count == 1


def test_unparsed_internal_candidate_is_not_added_and_needs_no_diagnostic(tmp_path: Path) -> None:
    seed = module("pkg/a.py", imports=("pkg.missing",))

    result = traverse_dependencies(
        (seed,),
        module_index(
            (seed,),
            seeds=("pkg/a.py",),
            candidates={"pkg.missing": ("pkg/missing.py",)},
        ),
        context(tmp_path, package_root=tmp_path / "pkg", scope_root=tmp_path / "pkg"),
        AnalysisConfig(),
    )

    assert result.graph.reachable_files == (Path("pkg/a.py"),)
    assert result.graph.edges == ()
    assert result.diagnostics == ()


def test_module_limit_returns_partial_result_and_fatal_diagnostic(tmp_path: Path) -> None:
    seed = module("pkg/a.py", imports=("pkg.b",))
    dependency = module("pkg/b.py")

    result = traverse_dependencies(
        (seed, dependency),
        module_index(
            (seed, dependency),
            seeds=("pkg/a.py",),
            candidates={"pkg.b": ("pkg/b.py",)},
        ),
        context(tmp_path, package_root=tmp_path / "pkg", scope_root=tmp_path / "pkg"),
        AnalysisConfig(),
        module_limit=1,
    )

    assert result.graph.reachable_files == (Path("pkg/a.py"),)
    assert result.graph.edges == ()
    assert result.observations.traversal_limit_reached is True
    assert result.observations.reachable_file_count == 1
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.code == "traversal_limit_reached"
    assert diagnostic.origin_seam is OriginSeam.ANALYZE
    assert diagnostic.recoverability is Recoverability.FATAL
    assert diagnostic.failure_reason is FailureReason.TRAVERSAL_LIMIT_REACHED


def test_module_limit_applies_to_initial_seed_frontier(tmp_path: Path) -> None:
    seed_a = module("pkg/a.py")
    seed_b = module("pkg/b.py")

    result = traverse_dependencies(
        (seed_b, seed_a),
        module_index((seed_b, seed_a), seeds=("pkg/a.py", "pkg/b.py")),
        context(tmp_path, package_root=tmp_path / "pkg", scope_root=tmp_path / "pkg"),
        AnalysisConfig(),
        module_limit=1,
    )

    assert result.graph.reachable_files == (Path("pkg/a.py"),)
    assert result.graph.edges == ()
    assert result.observations.seed_project_relative_paths == (Path("pkg/a.py"), Path("pkg/b.py"))
    assert result.observations.traversal_limit_reached is True
    assert result.observations.reachable_file_count == 1
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].code == "traversal_limit_reached"


def test_seed_limit_overflow_skips_already_frontiered_seed_import_side_effects(tmp_path: Path) -> None:
    seed_a = module("pkg/a.py", imports=("outside.package", "pkg.c"))
    seed_b = module("pkg/b.py")
    dependency = module("pkg/c.py")

    result = traverse_dependencies(
        (seed_b, dependency, seed_a),
        module_index(
            (seed_b, dependency, seed_a),
            seeds=("pkg/b.py", "pkg/a.py"),
            candidates={
                "outside.package": ("tools/helper.py",),
                "pkg.c": ("pkg/c.py",),
            },
        ),
        context(tmp_path, package_root=tmp_path / "pkg", scope_root=tmp_path / "pkg"),
        AnalysisConfig(),
        module_limit=1,
    )

    assert result.graph.reachable_files == (Path("pkg/a.py"),)
    assert result.graph.edges == ()
    assert result.observations.seed_project_relative_paths == (Path("pkg/a.py"), Path("pkg/b.py"))
    assert result.observations.package_stop_count == 0
    assert result.observations.scope_stop_count == 0
    assert result.observations.depth_stop_count == 0
    assert result.observations.traversal_limit_reached is True
    assert result.observations.reachable_file_count == 1
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].code == "traversal_limit_reached"


def test_module_limit_zero_returns_empty_partial_result_and_single_diagnostic(tmp_path: Path) -> None:
    seed = module("pkg/a.py")

    result = traverse_dependencies(
        (seed,),
        module_index((seed,), seeds=("pkg/a.py",)),
        context(tmp_path, package_root=tmp_path / "pkg", scope_root=tmp_path / "pkg"),
        AnalysisConfig(),
        module_limit=0,
    )

    assert result.graph.reachable_files == ()
    assert result.graph.edges == ()
    assert result.observations.traversal_limit_reached is True
    assert result.observations.reachable_file_count == 0
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].code == "traversal_limit_reached"


def test_module_limit_stops_import_processing_without_later_side_effects(tmp_path: Path) -> None:
    seed = module("pkg/a.py", imports=("a.limit", "z.outside"))
    dependency = module("pkg/b.py")

    result = traverse_dependencies(
        (seed, dependency),
        module_index(
            (seed, dependency),
            seeds=("pkg/a.py",),
            candidates={
                "a.limit": ("pkg/b.py",),
                "z.outside": ("tools/helper.py",),
            },
        ),
        context(tmp_path, package_root=tmp_path / "pkg", scope_root=tmp_path / "pkg"),
        AnalysisConfig(),
        module_limit=1,
    )

    assert result.graph.reachable_files == (Path("pkg/a.py"),)
    assert result.graph.edges == ()
    assert result.observations.package_stop_count == 0
    assert result.observations.scope_stop_count == 0
    assert result.observations.depth_stop_count == 0
    assert result.observations.traversal_limit_reached is True
    assert result.observations.reachable_file_count == 1
    assert len(result.diagnostics) == 1


def test_depth_none_terminates_deterministically_on_cyclic_imports(tmp_path: Path) -> None:
    seed = module("pkg/a.py", imports=("pkg.b",))
    dependency = module("pkg/b.py", imports=("pkg.a",))

    result = traverse_dependencies(
        (dependency, seed),
        module_index(
            (dependency, seed),
            seeds=("pkg/a.py",),
            candidates={"pkg.a": ("pkg/a.py",), "pkg.b": ("pkg/b.py",)},
        ),
        context(tmp_path, package_root=tmp_path / "pkg", scope_root=tmp_path / "pkg"),
        AnalysisConfig(depth=None),
    )

    assert result.graph.reachable_files == (Path("pkg/a.py"), Path("pkg/b.py"))
    assert result.graph.edges == (
        (Path("pkg/a.py"), Path("pkg/b.py")),
        (Path("pkg/b.py"), Path("pkg/a.py")),
    )
    assert result.observations.package_stop_count == 0
    assert result.observations.scope_stop_count == 0
    assert result.observations.depth_stop_count == 0
    assert result.observations.traversal_limit_reached is False
    assert result.observations.reachable_file_count == 2
    assert result.diagnostics == ()


def test_reachable_files_and_edges_are_deterministically_ordered(tmp_path: Path) -> None:
    seed = module("pkg/a.py", imports=("pkg.c", "pkg.b"))
    dependency_c = module("pkg/c.py")
    dependency_b = module("pkg/b.py")

    result = traverse_dependencies(
        (dependency_c, seed, dependency_b),
        module_index(
            (dependency_c, seed, dependency_b),
            seeds=("pkg/a.py",),
            candidates={"pkg.c": ("pkg/c.py",), "pkg.b": ("pkg/b.py",)},
        ),
        context(tmp_path, package_root=tmp_path / "pkg", scope_root=tmp_path / "pkg"),
        AnalysisConfig(),
    )

    assert result.graph.reachable_files == (Path("pkg/a.py"), Path("pkg/b.py"), Path("pkg/c.py"))
    assert result.graph.edges == (
        (Path("pkg/a.py"), Path("pkg/b.py")),
        (Path("pkg/a.py"), Path("pkg/c.py")),
    )
