from pathlib import Path

from pyclassuml.analyze import build_changed_class_inventory
from pyclassuml.model import ParsedModule
from pyclassuml.parse import ModuleIndex


def module(path: str, classes: tuple[str, ...] = ()) -> ParsedModule:
    return ParsedModule(module_path=Path(path), classes=classes)


def module_index(
    modules: tuple[ParsedModule, ...],
    *,
    project_relative_file_to_module: dict[Path, Path] | None = None,
) -> ModuleIndex:
    module_by_path = {parsed.module_path: parsed for parsed in modules}
    file_to_module = project_relative_file_to_module
    if file_to_module is None:
        file_to_module = {path: path for path in module_by_path}
    return ModuleIndex(
        module_by_path=module_by_path,
        project_relative_file_to_module=file_to_module,
        class_to_module={
            class_id: parsed.module_path
            for parsed in modules
            for class_id in parsed.classes
        },
        seed_project_relative_paths=(),
        import_candidate_paths={},
    )


def inventory(
    changed_files: tuple[str, ...],
    modules: tuple[ParsedModule, ...],
    *,
    index: ModuleIndex | None = None,
):
    if index is None:
        index = module_index(modules)
    return build_changed_class_inventory(
        tuple(Path(path) for path in changed_files),
        modules,
        index,
    )


def test_single_changed_file_with_one_class_counts_and_carries_file() -> None:
    result = inventory(
        ("pkg/a.py",),
        (module("pkg/a.py", classes=("pkg.a.A",)),),
    )

    assert result.class_count == 1
    assert result.changed_files == (Path("pkg/a.py"),)


def test_same_file_multiple_classes_count_as_multiple_changed_classes() -> None:
    result = inventory(
        ("pkg/a.py",),
        (module("pkg/a.py", classes=("pkg.a.A", "pkg.a.B")),),
    )

    assert result.class_count == 2
    assert result.changed_files == (Path("pkg/a.py"),)


def test_classless_changed_file_is_carried_without_class_count_increment() -> None:
    result = inventory(
        ("pkg/empty.py",),
        (module("pkg/empty.py"),),
    )

    assert result.class_count == 0
    assert result.changed_files == (Path("pkg/empty.py"),)


def test_unreachable_changed_class_is_counted_without_selection_inputs() -> None:
    seed = module("pkg/seed.py", classes=("pkg.seed.Seed",))
    unreachable_changed = module("pkg/unreachable.py", classes=("pkg.unreachable.Hidden",))

    result = inventory(
        ("pkg/unreachable.py",),
        (seed, unreachable_changed),
    )

    assert result.class_count == 1
    assert result.changed_files == (Path("pkg/unreachable.py"),)


def test_join_miss_or_syntax_error_equivalent_is_carried_without_class_count() -> None:
    result = inventory(
        ("pkg/broken.py",),
        (module("pkg/other.py", classes=("pkg.other.Other",)),),
    )

    assert result.class_count == 0
    assert result.changed_files == (Path("pkg/broken.py"),)


def test_changed_files_are_deduped_and_sorted_deterministically() -> None:
    result = inventory(
        ("pkg/b.py", "pkg/a.py", "pkg/b.py"),
        (
            module("pkg/b.py", classes=("pkg.b.B",)),
            module("pkg/a.py", classes=("pkg.a.A",)),
        ),
    )

    assert result.class_count == 2
    assert result.changed_files == (Path("pkg/a.py"), Path("pkg/b.py"))


def test_ignored_looking_changed_file_is_not_filtered_when_handed_off() -> None:
    result = inventory(
        ("venv/vendor.py",),
        (module("venv/vendor.py", classes=("venv.vendor.Kept",)),),
    )

    assert result.class_count == 1
    assert result.changed_files == (Path("venv/vendor.py"),)


def test_module_index_file_mapping_can_join_to_distinct_module_path() -> None:
    parsed = module("pkg/module.py", classes=("pkg.module.A",))
    index = module_index(
        (parsed,),
        project_relative_file_to_module={Path("src/pkg/module.py"): Path("pkg/module.py")},
    )

    result = inventory(
        ("src/pkg/module.py",),
        (parsed,),
        index=index,
    )

    assert result.class_count == 1
    assert result.changed_files == (Path("src/pkg/module.py"),)


def test_parsed_modules_fallback_is_used_when_index_module_by_path_misses() -> None:
    parsed = module("pkg/a.py", classes=("pkg.a.A",))
    index = ModuleIndex(
        module_by_path={},
        project_relative_file_to_module={Path("pkg/a.py"): Path("pkg/a.py")},
        class_to_module={},
        seed_project_relative_paths=(),
        import_candidate_paths={},
    )

    result = inventory(
        ("pkg/a.py",),
        (parsed,),
        index=index,
    )

    assert result.class_count == 1
    assert result.changed_files == (Path("pkg/a.py"),)
