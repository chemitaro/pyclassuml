"""Parse target source files into AST-backed module DTOs and lookup indexes."""

from __future__ import annotations

import ast
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Iterable, Mapping

from pyclassuml.model import (
    AnalysisConfig,
    Diagnostic,
    DiagnosticSeverity,
    ExecutionContext,
    FailureReason,
    OriginSeam,
    ParsedModule,
    Recoverability,
    TargetSet,
)
from pyclassuml.targets.ignore import DEFAULT_IGNORE, is_ignored


@dataclass(frozen=True)
class ModuleIndex:
    """Seam-local lookup material built by the parse seam."""

    module_by_path: Mapping[Path, ParsedModule]
    project_relative_file_to_module: Mapping[Path, Path]
    class_to_module: Mapping[str, Path]
    seed_project_relative_paths: tuple[Path, ...]
    import_candidate_paths: Mapping[str, tuple[Path, ...]]

    def __post_init__(self) -> None:
        object.__setattr__(self, "module_by_path", MappingProxyType(dict(self.module_by_path)))
        object.__setattr__(
            self,
            "project_relative_file_to_module",
            MappingProxyType(dict(self.project_relative_file_to_module)),
        )
        object.__setattr__(self, "class_to_module", MappingProxyType(dict(self.class_to_module)))
        object.__setattr__(self, "seed_project_relative_paths", tuple(self.seed_project_relative_paths))
        object.__setattr__(
            self,
            "import_candidate_paths",
            MappingProxyType({key: tuple(value) for key, value in self.import_candidate_paths.items()}),
        )


@dataclass(frozen=True)
class ParseObservations:
    """Parse seam observations consumed by downstream reporting."""

    ignored_dependency_candidate_count: int = 0

    def __post_init__(self) -> None:
        if (
            isinstance(self.ignored_dependency_candidate_count, bool)
            or not isinstance(self.ignored_dependency_candidate_count, int)
            or self.ignored_dependency_candidate_count < 0
        ):
            raise ValueError("ignored_dependency_candidate_count must be a non-negative int")


@dataclass(frozen=True)
class ParseResult:
    """Seam-local parse result."""

    parsed_modules: tuple[ParsedModule, ...]
    module_index: ModuleIndex
    observations: ParseObservations
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "parsed_modules", tuple(self.parsed_modules))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))


@dataclass(frozen=True)
class _ImportRef:
    text: str
    module: str | None
    names: tuple[str, ...]
    level: int


def parse_target_set(
    target_set: TargetSet,
    context: ExecutionContext,
    config: AnalysisConfig,
) -> ParseResult:
    """Parse target seeds and package-local import candidates without importing code."""

    project_root = context.project_root.resolve()
    package_root = context.package_root.resolve()
    seed_files = tuple(sorted({_resolve_path(path) for path in target_set.seed_files}))
    seed_project_relative_paths = tuple(_project_relative(path, project_root) for path in seed_files)

    queue: deque[Path] = deque(seed_files)
    queued = set(seed_files)
    parsed_by_path: dict[Path, ParsedModule] = {}
    diagnostics: list[Diagnostic] = []
    ignored_count = 0
    import_candidates: dict[str, set[Path]] = {}
    failed_paths: set[Path] = set()

    while queue:
        source_path = queue.popleft()
        if source_path in parsed_by_path or source_path in failed_paths:
            continue

        try:
            tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        except SyntaxError as exc:
            diagnostics.append(_syntax_diagnostic(source_path, project_root, exc))
            failed_paths.add(source_path)
            continue

        module_path = _project_relative(source_path, project_root)
        imports = _extract_imports(tree)
        classes = _extract_classes(tree, module_path)
        parsed_module = ParsedModule(module_path=module_path, imports=imports, classes=classes, diagnostics=())
        parsed_by_path[source_path] = parsed_module

        for import_ref in _extract_import_refs(tree):
            candidates = tuple(_candidate_paths(import_ref, source_path, project_root))
            accepted: list[Path] = []
            for candidate in candidates:
                if is_ignored(candidate, project_root, (*DEFAULT_IGNORE, *config.ignore)):
                    ignored_count += 1
                    continue
                accepted.append(candidate)
                if _is_relative_to(candidate, package_root) and candidate not in queued:
                    queue.append(candidate)
                    queued.add(candidate)
            if accepted:
                import_candidates.setdefault(import_ref.text, set()).update(
                    _project_relative(candidate, project_root) for candidate in accepted
                )

    parsed_modules = tuple(parsed_by_path[path] for path in sorted(parsed_by_path))
    module_by_path = {module.module_path: module for module in parsed_modules}
    project_relative_file_to_module = {module.module_path: module.module_path for module in parsed_modules}
    class_to_module = {
        class_id: module.module_path
        for module in parsed_modules
        for class_id in module.classes
    }
    candidate_lookup = {
        key: tuple(sorted(paths))
        for key, paths in sorted(import_candidates.items(), key=lambda item: item[0])
    }

    return ParseResult(
        parsed_modules=parsed_modules,
        module_index=ModuleIndex(
            module_by_path=module_by_path,
            project_relative_file_to_module=project_relative_file_to_module,
            class_to_module=class_to_module,
            seed_project_relative_paths=seed_project_relative_paths,
            import_candidate_paths=candidate_lookup,
        ),
        observations=ParseObservations(ignored_dependency_candidate_count=ignored_count),
        diagnostics=tuple(diagnostics),
    )


def _resolve_path(path: Path) -> Path:
    return path.resolve()


def _project_relative(path: Path, project_root: Path) -> Path:
    try:
        return path.resolve().relative_to(project_root)
    except ValueError:
        return path.resolve()


def _extract_imports(tree: ast.AST) -> tuple[str, ...]:
    return tuple(sorted(ref.text for ref in _extract_import_refs(tree)))


def _extract_import_refs(tree: ast.AST) -> tuple[_ImportRef, ...]:
    refs: list[_ImportRef] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            refs.extend(
                _ImportRef(text=alias.name, module=alias.name, names=(), level=0)
                for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            module = node.module
            names = tuple(alias.name for alias in node.names if alias.name != "*")
            import_from = f"{'.' * node.level}{module or ''}"
            text = f"from {import_from}"
            if names:
                text = f"{text} import {', '.join(names)}"
            refs.append(_ImportRef(text=text, module=module, names=names, level=node.level))
    return tuple(sorted(refs, key=lambda ref: ref.text))


def _extract_classes(tree: ast.AST, module_path: Path) -> tuple[str, ...]:
    classes: list[str] = []

    def visit(node: ast.AST, parents: tuple[str, ...]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                qualname = (*parents, child.name)
                classes.append(f"{module_path.as_posix()}:{'.'.join(qualname)}")
                visit(child, qualname)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            else:
                visit(child, parents)

    visit(tree, ())
    return tuple(sorted(classes))


def _candidate_paths(
    import_ref: _ImportRef,
    source_path: Path,
    project_root: Path,
) -> Iterable[Path]:
    bases = _import_base_parts(import_ref, source_path, project_root)
    candidate_parts: set[tuple[str, ...]] = set()
    if bases:
        candidate_parts.add(bases)
    for name in import_ref.names:
        if name:
            candidate_parts.add((*bases, *name.split(".")))

    for parts in sorted(candidate_parts):
        yield from _existing_python_candidates(project_root, parts)


def _import_base_parts(
    import_ref: _ImportRef,
    source_path: Path,
    project_root: Path,
) -> tuple[str, ...]:
    module_parts = tuple(part for part in (import_ref.module or "").split(".") if part)
    if import_ref.level == 0:
        return module_parts

    current_package = _module_parts_for_file(source_path, project_root)
    keep = max(len(current_package) - import_ref.level + 1, 0)
    return (*current_package[:keep], *module_parts)


def _module_parts_for_file(source_path: Path, project_root: Path) -> tuple[str, ...]:
    try:
        relative = source_path.relative_to(project_root)
    except ValueError:
        return ()

    if source_path.name == "__init__.py":
        return relative.parent.parts
    return relative.parent.parts


def _existing_python_candidates(project_root: Path, parts: tuple[str, ...]) -> Iterable[Path]:
    if not parts:
        return ()

    base = (project_root / Path(*parts)).resolve()
    candidates = []
    module_file = base.with_suffix(".py")
    package_init = base / "__init__.py"
    if module_file.is_file():
        candidates.append(module_file)
    if package_init.is_file():
        candidates.append(package_init)
    return tuple(sorted(candidates))


def _syntax_diagnostic(path: Path, project_root: Path, exc: SyntaxError) -> Diagnostic:
    relative = _project_relative(path, project_root).as_posix()
    location = f"{exc.lineno}:{exc.offset}" if exc.lineno is not None else "unknown"
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="bad_syntax",
        message=f"syntax error in {relative} at {location}: {exc.msg}",
        origin_seam=OriginSeam.PARSE,
        recoverability=Recoverability.DEGRADED_OUTPUT,
        failure_reason=FailureReason.STRICT_SYNTAX_ERROR,
    )


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
