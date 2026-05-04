"""Changed class inventory for diff summaries."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from pyclassuml.model import ChangedClassInventory, ParsedModule
from pyclassuml.parse import ModuleIndex


def build_changed_class_inventory(
    changed_files: Iterable[Path],
    parsed_modules: Iterable[ParsedModule],
    module_index: ModuleIndex,
) -> ChangedClassInventory:
    """Count parsed class definitions in upstream handed-off changed files."""

    sorted_changed_files = tuple(sorted(set(changed_files), key=_path_sort_key))
    parsed_module_by_path = {module.module_path: module for module in parsed_modules}
    class_count = 0

    for changed_file in sorted_changed_files:
        module_path = module_index.project_relative_file_to_module.get(changed_file)
        if module_path is None:
            continue

        parsed_module = module_index.module_by_path.get(module_path)
        if parsed_module is None:
            parsed_module = parsed_module_by_path.get(module_path)
        if parsed_module is None:
            continue

        class_count += len(parsed_module.classes)

    return ChangedClassInventory(
        class_count=class_count,
        changed_files=sorted_changed_files,
    )


def _path_sort_key(path: Path) -> str:
    return path.as_posix()


__all__ = ["build_changed_class_inventory"]
