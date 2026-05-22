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
    ClassMember,
    ClassReference,
    ClassSpan,
    Diagnostic,
    DiagnosticSeverity,
    ExecutionContext,
    FailureReason,
    MemberParameter,
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


@dataclass(frozen=True)
class _PositionedReference:
    reference: ClassReference
    lineno: int
    col_offset: int


@dataclass(frozen=True)
class _PositionedMember:
    member: ClassMember
    lineno: int
    col_offset: int
    sequence: int


class _AnnotationTextCache:
    def __init__(self) -> None:
        self._values: dict[int, tuple[str | None, tuple[Diagnostic, ...]]] = {}

    def text(self, annotation: ast.AST) -> tuple[str | None, tuple[Diagnostic, ...]]:
        cache_key = id(annotation)
        cached = self._values.get(cache_key)
        if cached is not None:
            return cached[0], ()
        value = _annotation_text(annotation)
        self._values[cache_key] = value
        return value


def parse_target_set(
    target_set: TargetSet,
    context: ExecutionContext,
    config: AnalysisConfig,
) -> ParseResult:
    """Parse target seeds and package-local import candidates without importing code."""

    project_root = context.project_root.resolve()
    package_root = context.package_root.resolve()
    import_roots = tuple(import_root.resolve() for import_root in context.import_roots)
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
        parsed_module = _parsed_module_from_tree(tree, module_path)
        parsed_by_path[source_path] = parsed_module

        for import_ref in _extract_import_refs(tree):
            candidates = tuple(_candidate_paths(import_ref, source_path, import_roots))
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


def parse_module_source_text(source_text: str, module_path: Path, *, filename: str | None = None) -> ParsedModule:
    """Parse one logical module from source text without importing target code."""

    tree = ast.parse(source_text, filename=filename or module_path.as_posix())
    return _parsed_module_from_tree(tree, module_path)


def _parsed_module_from_tree(tree: ast.AST, module_path: Path) -> ParsedModule:
    imports = _extract_imports(tree)
    class_spans = _extract_class_spans(tree, module_path)
    class_references, module_diagnostics = _extract_class_references(tree, module_path)
    members, member_diagnostics = _extract_class_members(tree, module_path)
    return ParsedModule(
        module_path=module_path,
        imports=imports,
        classes=tuple(class_span.class_id for class_span in class_spans),
        class_spans=class_spans,
        class_references=class_references,
        diagnostics=(*module_diagnostics, *member_diagnostics),
        members=members,
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
                _ImportRef(text=_format_import_alias(alias), module=alias.name, names=(), level=0)
                for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            module = node.module
            names = tuple(alias.name for alias in node.names if alias.name != "*")
            rendered_names = tuple(_format_import_from_alias(alias) for alias in node.names if alias.name != "*")
            import_from = f"{'.' * node.level}{module or ''}"
            text = f"from {import_from}"
            if rendered_names:
                text = f"{text} import {', '.join(rendered_names)}"
            refs.append(_ImportRef(text=text, module=module, names=names, level=node.level))
    return tuple(sorted(refs, key=lambda ref: ref.text))


def _format_import_alias(alias: ast.alias) -> str:
    if alias.asname is None:
        return alias.name
    return f"{alias.name} as {alias.asname}"


def _format_import_from_alias(alias: ast.alias) -> str:
    if alias.asname is None:
        return alias.name
    return f"{alias.name} as {alias.asname}"


def _extract_classes(tree: ast.AST, module_path: Path) -> tuple[str, ...]:
    return tuple(class_span.class_id for class_span in _extract_class_spans(tree, module_path))


def _extract_class_spans(tree: ast.AST, module_path: Path) -> tuple[ClassSpan, ...]:
    class_spans: list[ClassSpan] = []

    def visit(node: ast.AST, parents: tuple[str, ...]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                qualname = (*parents, child.name)
                class_id = f"{module_path.as_posix()}:{'.'.join(qualname)}"
                decorator_lines = [
                    decorator.lineno
                    for decorator in child.decorator_list
                    if isinstance(getattr(decorator, "lineno", None), int)
                ]
                start_line = min((child.lineno, *decorator_lines))
                end_line = getattr(child, "end_lineno", None)
                class_spans.append(
                    ClassSpan(
                        class_id=class_id,
                        start_line=start_line,
                        end_line=end_line if isinstance(end_line, int) else start_line,
                    )
                )
                visit(child, qualname)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            else:
                visit(child, parents)

    visit(tree, ())
    return tuple(sorted(class_spans, key=lambda class_span: class_span.class_id))


def _extract_class_members(tree: ast.AST, module_path: Path) -> tuple[tuple[ClassMember, ...], tuple[Diagnostic, ...]]:
    positioned_members: list[_PositionedMember] = []
    diagnostics: list[Diagnostic] = []
    sequence = 0

    def visit(node: ast.AST, parents: tuple[str, ...]) -> None:
        nonlocal sequence
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                qualname = (*parents, child.name)
                source_class_id = f"{module_path.as_posix()}:{'.'.join(qualname)}"
                class_members, class_diagnostics = _class_body_members(child, source_class_id)
                for class_member in class_members:
                    positioned_members.append(
                        _PositionedMember(
                            member=class_member.member,
                            lineno=class_member.lineno,
                            col_offset=class_member.col_offset,
                            sequence=sequence,
                        )
                    )
                    sequence += 1
                diagnostics.extend(class_diagnostics)
                visit(child, qualname)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            else:
                visit(child, parents)

    visit(tree, ())
    source_order_by_owner: dict[str, int] = {}
    members: list[ClassMember] = []
    for positioned_member in sorted(
        positioned_members,
        key=lambda item: (item.lineno, item.col_offset, item.sequence),
    ):
        member = positioned_member.member
        source_order = source_order_by_owner.get(member.owner_class_id, 0) + 1
        source_order_by_owner[member.owner_class_id] = source_order
        members.append(
            ClassMember(
                owner_class_id=member.owner_class_id,
                name=member.name,
                kind=member.kind,
                visibility=member.visibility,
                annotation_text=member.annotation_text,
                parameters=member.parameters,
                return_annotation_text=member.return_annotation_text,
                modifiers=member.modifiers,
                source_order=source_order,
            )
        )
    return tuple(members), tuple(diagnostics)


def _class_body_members(
    class_def: ast.ClassDef,
    source_class_id: str,
) -> tuple[tuple[_PositionedMember, ...], tuple[Diagnostic, ...]]:
    raw_members: list[_PositionedMember] = []
    diagnostics: list[Diagnostic] = []
    annotation_text_cache = _AnnotationTextCache()
    sequence = 0

    for statement in class_def.body:
        if isinstance(statement, ast.AnnAssign):
            field_names = _field_target_names(statement.target)
            annotation_text, annotation_diagnostics = annotation_text_cache.text(statement.annotation)
            diagnostics.extend(annotation_diagnostics)
            for field_name in field_names:
                raw_members.append(
                    _PositionedMember(
                        member=ClassMember(
                            owner_class_id=source_class_id,
                            name=field_name,
                            kind="field",
                            visibility=_member_visibility(field_name),
                            annotation_text=annotation_text,
                        ),
                        lineno=statement.lineno,
                        col_offset=statement.col_offset,
                        sequence=sequence,
                    )
                )
                sequence += 1
            continue

        if isinstance(statement, ast.Assign):
            for field_name in _assign_field_names(statement):
                raw_members.append(
                    _PositionedMember(
                        member=ClassMember(
                            owner_class_id=source_class_id,
                            name=field_name,
                            kind="field",
                            visibility=_member_visibility(field_name),
                        ),
                        lineno=statement.lineno,
                        col_offset=statement.col_offset,
                        sequence=sequence,
                    )
                )
                sequence += 1
            continue

        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            method_member, method_diagnostics = _method_member(statement, source_class_id, annotation_text_cache)
            diagnostics.extend(method_diagnostics)
            raw_members.append(
                _PositionedMember(
                    member=method_member,
                    lineno=statement.lineno,
                    col_offset=statement.col_offset,
                    sequence=sequence,
                )
            )
            sequence += 1
            init_members, init_diagnostics = _init_field_members(statement, source_class_id, annotation_text_cache)
            diagnostics.extend(init_diagnostics)
            for init_member in init_members:
                raw_members.append(
                    _PositionedMember(
                        member=init_member.member,
                        lineno=init_member.lineno,
                        col_offset=init_member.col_offset,
                        sequence=sequence,
                    )
                )
                sequence += 1

    return tuple(raw_members), tuple(diagnostics)


def _method_member(
    function_def: ast.FunctionDef | ast.AsyncFunctionDef,
    source_class_id: str,
    annotation_text_cache: _AnnotationTextCache,
) -> tuple[ClassMember, tuple[Diagnostic, ...]]:
    diagnostics: list[Diagnostic] = []
    parameters: list[MemberParameter] = []
    for arg in _method_arguments(function_def.args):
        annotation_text = None
        if arg.annotation is not None:
            annotation_text, annotation_diagnostics = annotation_text_cache.text(arg.annotation)
            diagnostics.extend(annotation_diagnostics)
        parameters.append(MemberParameter(name=arg.arg, annotation_text=annotation_text))

    return_annotation_text = None
    if function_def.returns is not None:
        return_annotation_text, return_diagnostics = annotation_text_cache.text(function_def.returns)
        diagnostics.extend(return_diagnostics)

    return (
        ClassMember(
            owner_class_id=source_class_id,
            name=function_def.name,
            kind="method",
            visibility=_member_visibility(function_def.name),
            parameters=tuple(parameters),
            return_annotation_text=return_annotation_text,
            modifiers=_method_modifiers(function_def),
        ),
        tuple(diagnostics),
    )


def _method_arguments(arguments: ast.arguments) -> tuple[ast.arg, ...]:
    args = (
        *arguments.posonlyargs,
        *arguments.args,
        *((arguments.vararg,) if arguments.vararg is not None else ()),
        *arguments.kwonlyargs,
        *((arguments.kwarg,) if arguments.kwarg is not None else ()),
    )
    if args and args[0].arg in {"self", "cls"}:
        return tuple(args[1:])
    return tuple(args)


def _parameter_annotation_by_name(arguments: ast.arguments) -> dict[str, ast.AST]:
    return {arg.arg: arg.annotation for arg in _method_arguments(arguments) if arg.annotation is not None}


def _method_modifiers(function_def: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    modifiers: list[str] = []
    for decorator in function_def.decorator_list:
        name = _decorator_name(decorator)
        if name in {"staticmethod", "classmethod", "property"} and name not in modifiers:
            modifiers.append(name)
    if isinstance(function_def, ast.AsyncFunctionDef):
        modifiers.append("async")
    return tuple(modifiers)


def _decorator_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return _terminal_name(node)


def _init_field_members(
    function_def: ast.FunctionDef | ast.AsyncFunctionDef,
    source_class_id: str,
    annotation_text_cache: _AnnotationTextCache,
) -> tuple[tuple[_PositionedMember, ...], tuple[Diagnostic, ...]]:
    if function_def.name != "__init__":
        return (), ()

    raw_members: list[_PositionedMember] = []
    diagnostics: list[Diagnostic] = []
    parameter_annotations = _parameter_annotation_by_name(function_def.args)
    sequence = 0

    for statement in _walk_init_direct_assignment_statements(function_def.body):
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                field_name = _self_attribute_name(target)
                if field_name is None:
                    continue
                annotation = (
                    parameter_annotations.get(statement.value.id)
                    if isinstance(statement.value, ast.Name)
                    else None
                )
                annotation_text = None
                if annotation is not None:
                    annotation_text, annotation_diagnostics = annotation_text_cache.text(annotation)
                    diagnostics.extend(annotation_diagnostics)
                raw_members.append(
                    _PositionedMember(
                        member=ClassMember(
                            owner_class_id=source_class_id,
                            name=field_name,
                            kind="field",
                            visibility=_member_visibility(field_name),
                            annotation_text=annotation_text,
                        ),
                        lineno=statement.lineno,
                        col_offset=statement.col_offset,
                        sequence=sequence,
                    )
                )
                sequence += 1
        elif isinstance(statement, ast.AnnAssign):
            field_name = _self_attribute_name(statement.target)
            if field_name is None:
                continue
            annotation_text, annotation_diagnostics = annotation_text_cache.text(statement.annotation)
            diagnostics.extend(annotation_diagnostics)
            raw_members.append(
                _PositionedMember(
                    member=ClassMember(
                        owner_class_id=source_class_id,
                        name=field_name,
                        kind="field",
                        visibility=_member_visibility(field_name),
                        annotation_text=annotation_text,
                    ),
                    lineno=statement.lineno,
                    col_offset=statement.col_offset,
                    sequence=sequence,
                )
            )
            sequence += 1
    return tuple(raw_members), tuple(diagnostics)


def _walk_init_direct_assignment_statements(statements: Iterable[ast.stmt]) -> Iterable[ast.Assign | ast.AnnAssign]:
    stack = list(reversed(tuple(statements)))
    while stack:
        statement = stack.pop()
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            yield statement
        child_statements: list[ast.stmt] = []
        for child in ast.iter_child_nodes(statement):
            if isinstance(child, ast.ExceptHandler):
                child_statements.extend(child.body)
            elif isinstance(child, ast.stmt) and not isinstance(
                child,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            ):
                child_statements.append(child)
        stack.extend(reversed(child_statements))


def _field_target_names(target: ast.AST) -> tuple[str, ...]:
    if isinstance(target, ast.Name):
        return (target.id,)
    if isinstance(target, (ast.Tuple, ast.List)):
        names: list[str] = []
        for element in target.elts:
            names.extend(_field_target_names(element))
        return tuple(names)
    return ()


def _assign_field_names(statement: ast.Assign) -> tuple[str, ...]:
    names: list[str] = []
    for target in statement.targets:
        names.extend(_field_target_names(target))
    return tuple(names)


def _self_attribute_name(target: ast.AST) -> str | None:
    if not isinstance(target, ast.Attribute):
        return None
    if not isinstance(target.value, ast.Name) or target.value.id != "self":
        return None
    return target.attr


def _annotation_text(annotation: ast.AST) -> tuple[str | None, tuple[Diagnostic, ...]]:
    try:
        return ast.unparse(annotation), ()
    except Exception:
        return None, (_annotation_text_unavailable_diagnostic(),)


def _annotation_text_unavailable_diagnostic() -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.WARNING,
        code="annotation_text_unavailable",
        message="Annotation text could not be converted to stable source text; member was retained without annotation text.",
        origin_seam=OriginSeam.PARSE,
        recoverability=Recoverability.DEGRADED_OUTPUT,
        failure_reason=None,
    )


def _member_visibility(name: str) -> str:
    if name.startswith("__") and not name.endswith("__"):
        return "private"
    if name.startswith("_") and not name.startswith("__"):
        return "protected"
    return "public"


def _extract_class_references(tree: ast.AST, module_path: Path) -> tuple[tuple[ClassReference, ...], tuple[Diagnostic, ...]]:
    references: list[_PositionedReference] = []
    diagnostics: list[Diagnostic] = []

    def visit(node: ast.AST, parents: tuple[str, ...]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                qualname = (*parents, child.name)
                source_class_id = f"{module_path.as_posix()}:{'.'.join(qualname)}"
                class_references, class_diagnostics = _class_body_references(
                    child,
                    source_class_id,
                )
                references.extend(class_references)
                diagnostics.extend(class_diagnostics)
                visit(child, qualname)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            else:
                visit(child, parents)

    visit(tree, ())
    return _ordered_class_references(references), tuple(diagnostics)


def _class_body_references(
    class_def: ast.ClassDef,
    source_class_id: str,
) -> tuple[tuple[_PositionedReference, ...], tuple[Diagnostic, ...]]:
    references: list[_PositionedReference] = []
    diagnostics: list[Diagnostic] = []
    annotation_text_cache = _AnnotationTextCache()
    references.extend(_class_base_references(class_def, source_class_id))
    for statement in class_def.body:
        if isinstance(statement, ast.ClassDef):
            continue
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            method_references, method_diagnostics = _method_annotation_references(
                statement,
                source_class_id,
                annotation_text_cache,
            )
            references.extend(method_references)
            diagnostics.extend(method_diagnostics)
            references.extend(_init_field_annotation_references(statement, source_class_id, annotation_text_cache))
            references.extend(_method_body_dependency_references(statement, source_class_id, annotation_text_cache))
            continue
        references.extend(_field_annotation_references_in_statement(statement, source_class_id, annotation_text_cache))
        references.extend(_annotation_string_references_in_statement(statement, source_class_id))
        references.extend(_annotation_subscript_references_in_statement(statement, source_class_id))
        references.extend(_call_string_arg_references(statement, source_class_id))
    return tuple(references), tuple(diagnostics)


def _class_base_references(class_def: ast.ClassDef, source_class_id: str) -> tuple[_PositionedReference, ...]:
    references: list[_PositionedReference] = []
    for base in class_def.bases:
        target_name = _dotted_name(base)
        if target_name is None:
            continue
        references.append(
            _PositionedReference(
                reference=ClassReference(
                    source_class_id=source_class_id,
                    target_name=target_name,
                    reference_kind="class_base",
                    reference_owner="base",
                ),
                lineno=base.lineno,
                col_offset=base.col_offset,
            )
        )
    return tuple(references)


def _field_annotation_references_in_statement(
    statement: ast.AST,
    source_class_id: str,
    annotation_text_cache: _AnnotationTextCache,
) -> tuple[_PositionedReference, ...]:
    references: list[_PositionedReference] = []
    for node in _walk_without_nested_definition_bodies(statement):
        if not isinstance(node, ast.AnnAssign):
            continue
        for field_name in _field_target_names(node.target):
            references.extend(
                _semantic_annotation_references(
                    node.annotation,
                    source_class_id=source_class_id,
                    reference_kind="field_annotation",
                    reference_owner=field_name,
                    lineno=node.annotation.lineno,
                    col_offset=node.annotation.col_offset,
                    annotation_text_cache=annotation_text_cache,
                )
            )
    return tuple(references)


def _method_annotation_references(
    function_def: ast.FunctionDef | ast.AsyncFunctionDef,
    source_class_id: str,
    annotation_text_cache: _AnnotationTextCache,
) -> tuple[tuple[_PositionedReference, ...], tuple[Diagnostic, ...]]:
    references: list[_PositionedReference] = []
    diagnostics: list[Diagnostic] = []
    for arg in _method_arguments(function_def.args):
        if arg.annotation is None:
            continue
        references.extend(
            _semantic_annotation_references(
                arg.annotation,
                source_class_id=source_class_id,
                reference_kind="method_parameter_annotation",
                reference_owner=f"{function_def.name}.{arg.arg}",
                lineno=arg.annotation.lineno,
                col_offset=arg.annotation.col_offset,
                annotation_text_cache=annotation_text_cache,
            )
        )
    if function_def.returns is not None:
        references.extend(
            _semantic_annotation_references(
                function_def.returns,
                source_class_id=source_class_id,
                reference_kind="method_return_annotation",
                reference_owner=function_def.name,
                lineno=function_def.returns.lineno,
                col_offset=function_def.returns.col_offset,
                annotation_text_cache=annotation_text_cache,
            )
        )
    return tuple(references), tuple(diagnostics)


def _init_field_annotation_references(
    function_def: ast.FunctionDef | ast.AsyncFunctionDef,
    source_class_id: str,
    annotation_text_cache: _AnnotationTextCache,
) -> tuple[_PositionedReference, ...]:
    if function_def.name != "__init__":
        return ()
    references: list[_PositionedReference] = []
    parameter_annotations = _parameter_annotation_by_name(function_def.args)
    for statement in _walk_init_direct_assignment_statements(function_def.body):
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                field_name = _self_attribute_name(target)
                if field_name is None or not isinstance(statement.value, ast.Name):
                    continue
                annotation = parameter_annotations.get(statement.value.id)
                if annotation is None:
                    continue
                references.extend(
                    _semantic_annotation_references(
                        annotation,
                        source_class_id=source_class_id,
                        reference_kind="init_field_annotation",
                        reference_owner=field_name,
                        lineno=statement.lineno,
                        col_offset=statement.col_offset,
                        annotation_text_cache=annotation_text_cache,
                    )
                )
        elif isinstance(statement, ast.AnnAssign):
            field_name = _self_attribute_name(statement.target)
            if field_name is None:
                continue
            references.extend(
                _semantic_annotation_references(
                    statement.annotation,
                    source_class_id=source_class_id,
                reference_kind="init_field_annotation",
                reference_owner=field_name,
                lineno=statement.lineno,
                col_offset=statement.col_offset,
                annotation_text_cache=annotation_text_cache,
            )
        )
    return tuple(references)


def _method_body_dependency_references(
    function_def: ast.FunctionDef | ast.AsyncFunctionDef,
    source_class_id: str,
    annotation_text_cache: _AnnotationTextCache,
) -> tuple[_PositionedReference, ...]:
    references: list[_PositionedReference] = []
    for statement in function_def.body:
        if isinstance(statement, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in _walk_without_nested_definition_bodies(statement):
            owner = _method_body_reference_owner(function_def, node)
            if isinstance(node, ast.AnnAssign):
                references.extend(
                    _semantic_annotation_references(
                        node.annotation,
                        source_class_id=source_class_id,
                        reference_kind="local_annotation_dependency",
                        reference_owner=owner,
                        lineno=node.annotation.lineno,
                        col_offset=node.annotation.col_offset,
                        annotation_text_cache=annotation_text_cache,
                    )
                )
                continue

            if isinstance(node, ast.Call):
                references.extend(_call_dependency_references(node, source_class_id, owner))
                continue

            if isinstance(node, ast.Attribute):
                member_target = _class_member_access_target(node)
                if member_target is None:
                    continue
                references.append(
                    _PositionedReference(
                        reference=ClassReference(
                            source_class_id=source_class_id,
                            target_name=member_target,
                            reference_kind="direct_class_member_access",
                            reference_owner=owner,
                        ),
                        lineno=node.lineno,
                        col_offset=node.col_offset,
                    )
                )
    return tuple(references)


def _method_body_reference_owner(
    function_def: ast.FunctionDef | ast.AsyncFunctionDef,
    node: ast.AST,
) -> str:
    lineno = getattr(node, "lineno", function_def.lineno)
    col_offset = getattr(node, "col_offset", function_def.col_offset)
    return f"{function_def.name}@{lineno}:{col_offset}"


def _call_dependency_references(
    call: ast.Call,
    source_class_id: str,
    reference_owner: str,
) -> tuple[_PositionedReference, ...]:
    references: list[_PositionedReference] = []

    type_check_targets = _type_check_dependency_targets(call)
    if type_check_targets:
        references.extend(
            _PositionedReference(
                reference=ClassReference(
                    source_class_id=source_class_id,
                    target_name=target_name,
                    reference_kind="type_check_dependency",
                    reference_owner=reference_owner,
                ),
                lineno=call.lineno,
                col_offset=call.col_offset,
            )
            for target_name in type_check_targets
        )
        return tuple(references)

    cast_targets = _cast_dependency_targets(call)
    if cast_targets:
        references.extend(
            _PositionedReference(
                reference=ClassReference(
                    source_class_id=source_class_id,
                    target_name=target_name,
                    reference_kind="cast_dependency",
                    reference_owner=reference_owner,
                ),
                lineno=call.lineno,
                col_offset=call.col_offset,
            )
            for target_name in cast_targets
        )
        return tuple(references)

    call_target = _direct_class_call_target(call)
    if call_target is not None:
        references.append(
            _PositionedReference(
                reference=ClassReference(
                    source_class_id=source_class_id,
                    target_name=call_target,
                    reference_kind="direct_class_call",
                    reference_owner=reference_owner,
                ),
                lineno=call.func.lineno,
                col_offset=call.func.col_offset,
            )
        )
    return tuple(references)


def _type_check_dependency_targets(call: ast.Call) -> tuple[str, ...]:
    if _terminal_name(call.func) not in {"isinstance", "issubclass"} or len(call.args) < 2:
        return ()
    return _semantic_class_like_names(call.args[1])


def _cast_dependency_targets(call: ast.Call) -> tuple[str, ...]:
    if _dotted_name(call.func) not in {"cast", "typing.cast"} or not call.args:
        return ()
    return _semantic_class_like_names(call.args[0])


def _direct_class_call_target(call: ast.Call) -> str | None:
    target_name = _dotted_name(call.func)
    if target_name is None or not _is_class_like_target(target_name):
        return None
    return target_name


def _class_member_access_target(attribute: ast.Attribute) -> str | None:
    target_name = _dotted_name(attribute.value)
    if target_name is None or not _is_class_like_target(target_name):
        return None
    return target_name


def _semantic_annotation_references(
    annotation: ast.AST,
    *,
    source_class_id: str,
    reference_kind: str,
    reference_owner: str,
    lineno: int,
    col_offset: int,
    annotation_text_cache: _AnnotationTextCache,
) -> tuple[_PositionedReference, ...]:
    annotation_text, _ = annotation_text_cache.text(annotation)
    if annotation_text is None:
        return ()
    targets = (
        _semantic_annotation_targets(annotation)
        if reference_kind in {"field_annotation", "init_field_annotation"}
        else tuple((target_name, None) for target_name in _semantic_class_like_names(annotation))
    )
    return tuple(
        _PositionedReference(
            reference=ClassReference(
                source_class_id=source_class_id,
                target_name=target_name,
                reference_kind=reference_kind,
                reference_owner=reference_owner,
                annotation_shape=shape,
            ),
            lineno=lineno,
            col_offset=col_offset,
        )
        for target_name, shape in targets
    )


def _annotation_string_references_in_statement(
    statement: ast.AST,
    source_class_id: str,
) -> tuple[_PositionedReference, ...]:
    references: list[_PositionedReference] = []
    for node in _walk_without_nested_definition_bodies(statement):
        if isinstance(node, ast.AnnAssign):
            references.extend(_annotation_string_references(node.annotation, source_class_id))
    return tuple(references)


def _annotation_string_references(annotation: ast.AST, source_class_id: str) -> tuple[_PositionedReference, ...]:
    references: list[_PositionedReference] = []
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str) and annotation.value:
        references.extend(
            _PositionedReference(
                reference=ClassReference(
                    source_class_id=source_class_id,
                    target_name=target_name,
                    reference_kind="annotation_string",
                    reference_owner=owner,
                ),
                lineno=annotation.lineno,
                col_offset=annotation.col_offset,
            )
            for owner, target_name in _annotation_string_members_from_string(annotation.value)
        )
        return tuple(references)

    for owner, target_name in _quoted_subscript_members(annotation):
        references.append(
            _PositionedReference(
                reference=ClassReference(
                    source_class_id=source_class_id,
                    target_name=target_name,
                    reference_kind="annotation_string",
                    reference_owner=owner,
                ),
                lineno=annotation.lineno,
                col_offset=annotation.col_offset,
            )
        )
    return tuple(references)


def _annotation_subscript_references_in_statement(
    statement: ast.AST,
    source_class_id: str,
) -> tuple[_PositionedReference, ...]:
    references: list[_PositionedReference] = []
    for node in _walk_without_nested_definition_bodies(statement):
        if isinstance(node, ast.AnnAssign):
            references.extend(_annotation_subscript_references(node.annotation, source_class_id))
    return tuple(references)


def _annotation_subscript_references(annotation: ast.AST, source_class_id: str) -> tuple[_PositionedReference, ...]:
    references: list[_PositionedReference] = []
    if not isinstance(annotation, ast.Subscript):
        return ()
    owner = _terminal_name(annotation.value)
    if owner is None or owner == "Literal":
        return ()
    for target_name in _class_like_names(annotation.slice):
        references.append(
            _PositionedReference(
                reference=ClassReference(
                    source_class_id=source_class_id,
                    target_name=target_name,
                    reference_kind="annotation_subscript",
                    reference_owner=owner,
                ),
                lineno=annotation.lineno,
                col_offset=annotation.col_offset,
            )
        )
    return tuple(references)


def _call_string_arg_references(statement: ast.AST, source_class_id: str) -> tuple[_PositionedReference, ...]:
    references: list[_PositionedReference] = []
    for node in _walk_without_nested_definition_bodies(statement):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        owner = _terminal_name(node.func)
        first_arg = node.args[0]
        if owner is None or not isinstance(first_arg, ast.Constant) or not isinstance(first_arg.value, str):
            continue
        if first_arg.value == "":
            continue
        references.append(
            _PositionedReference(
                reference=ClassReference(
                    source_class_id=source_class_id,
                    target_name=first_arg.value,
                    reference_kind="call_string_arg",
                    reference_owner=owner,
                ),
                lineno=first_arg.lineno,
                col_offset=first_arg.col_offset,
            )
        )
    return tuple(references)


def _walk_without_nested_definition_bodies(node: ast.AST) -> Iterable[ast.AST]:
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        if isinstance(current, ast.Lambda):
            continue
        children = tuple(
            child
            for child in ast.iter_child_nodes(current)
            if not isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        )
        stack.extend(reversed(children))


def _terminal_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Subscript):
        return _dotted_name(node.value)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        if parent is None:
            return node.attr
        return f"{parent}.{node.attr}"
    return None


def _quoted_subscript_members(node: ast.AST) -> tuple[tuple[str, str], ...]:
    members: set[tuple[str, str]] = set()

    def collect(current: ast.AST) -> None:
        if not isinstance(current, ast.Subscript):
            for child in ast.iter_child_nodes(current):
                collect(child)
            return

        owner = _terminal_name(current.value)
        if owner == "Annotated":
            first_arg = _first_subscript_arg(current.slice)
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str) and first_arg.value:
                members.add((owner, first_arg.value))
                return
            collect(first_arg)
            return
        if owner is not None and owner != "Literal":
            for target_name in _quoted_string_constants(current.slice):
                members.add((owner, target_name))
            return
        if owner == "Literal":
            return
        collect(current.slice)

    collect(node)
    return tuple(sorted(members))


def _annotation_string_members_from_string(value: str) -> tuple[tuple[str, str], ...]:
    try:
        expression = ast.parse(value, mode="eval").body
    except SyntaxError:
        return (("annotation", value),)

    members = _annotation_string_members_from_expression(expression)
    if members:
        return members
    return ()


def _annotation_string_members_from_expression(node: ast.AST) -> tuple[tuple[str, str], ...]:
    if isinstance(node, ast.Subscript):
        owner = _terminal_name(node.value)
        if owner == "Literal":
            return ()
        if owner == "Annotated":
            return tuple(
                ("Annotated", target_name)
                for target_name in _semantic_class_like_names(_first_subscript_arg(node.slice))
            )
        if owner is not None:
            return tuple((owner, target_name) for target_name in _semantic_class_like_names(node.slice))
    return tuple(("annotation", target_name) for target_name in _semantic_class_like_names(node))


def _quoted_string_constants(node: ast.AST) -> tuple[str, ...]:
    values: set[str] = set()

    def collect(current: ast.AST, *, ignored_wrapper_depth: int = 0) -> None:
        if isinstance(current, ast.Subscript):
            owner = _terminal_name(current.value)
            if owner == "Annotated":
                collect(_first_subscript_arg(current.slice), ignored_wrapper_depth=ignored_wrapper_depth)
                return
            next_ignored_wrapper_depth = ignored_wrapper_depth + 1 if owner == "Literal" else ignored_wrapper_depth
            collect(current.slice, ignored_wrapper_depth=next_ignored_wrapper_depth)
            return
        if isinstance(current, ast.Constant) and isinstance(current.value, str) and current.value:
            if ignored_wrapper_depth == 0:
                values.add(current.value)
            return
        for child in ast.iter_child_nodes(current):
            collect(child, ignored_wrapper_depth=ignored_wrapper_depth)

    collect(node)
    return tuple(sorted(values))


def _first_subscript_arg(node: ast.AST) -> ast.AST:
    if isinstance(node, ast.Tuple) and node.elts:
        return node.elts[0]
    return node


def _class_like_names(node: ast.AST) -> tuple[str, ...]:
    names: set[str] = set()

    def collect(child: ast.AST, *, in_literal: bool = False) -> None:
        if isinstance(child, ast.Subscript):
            owner = _terminal_name(child.value)
            if owner == "Literal":
                return
            if owner == "Annotated":
                collect(_first_subscript_arg(child.slice), in_literal=in_literal)
                return
            collect(child.slice, in_literal=in_literal or owner == "Literal")
            return
        if isinstance(child, ast.Constant):
            if not in_literal and isinstance(child.value, str) and child.value[:1].isupper():
                names.add(child.value)
            return
        name = _terminal_name(child)
        if name is not None:
            if name[:1].isupper() and name not in _TYPING_WRAPPER_NAMES:
                names.add(name)
            return
        for grandchild in ast.iter_child_nodes(child):
            collect(grandchild, in_literal=in_literal)

    collect(node)
    return tuple(sorted(names))


def _semantic_class_like_names(node: ast.AST) -> tuple[str, ...]:
    names: set[str] = set()

    def collect(child: ast.AST, *, in_literal: bool = False) -> None:
        if isinstance(child, ast.Subscript):
            owner = _terminal_name(child.value)
            if owner == "Literal":
                return
            if owner == "Annotated":
                collect(_first_subscript_arg(child.slice), in_literal=in_literal)
                return
            collect(child.slice, in_literal=in_literal)
            return
        if isinstance(child, ast.Constant):
            if in_literal or not isinstance(child.value, str) or not child.value:
                return
            names.update(_semantic_class_like_names_from_string(child.value))
            return
        dotted_name = _dotted_name(child)
        if dotted_name is not None:
            if _is_class_like_target(dotted_name) and _terminal_name(child) not in _TYPING_WRAPPER_NAMES:
                names.add(dotted_name)
            return
        for grandchild in ast.iter_child_nodes(child):
            collect(grandchild, in_literal=in_literal)

    collect(node)
    return tuple(sorted(names))


def _semantic_annotation_targets(node: ast.AST) -> tuple[tuple[str, str | None], ...]:
    targets: set[tuple[str, str | None]] = set()

    def collect(child: ast.AST, shape: str | None) -> None:
        parsed_string = _string_annotation_expression(child)
        if parsed_string is not None:
            collect(parsed_string, shape)
            return

        if isinstance(child, ast.BinOp) and isinstance(child.op, ast.BitOr):
            operands = _pep604_union_operands(child)
            next_shape = "optional" if any(_is_none_annotation(operand) for operand in operands) else "union"
            for operand in operands:
                if not _is_none_annotation(operand):
                    collect(operand, _annotation_shape(shape, next_shape))
            return

        if isinstance(child, ast.Subscript):
            owner = _terminal_name(child.value)
            if owner == "Literal":
                return
            if owner == "Annotated":
                collect(_first_subscript_arg(child.slice), shape)
                return
            if owner in _TRANSPARENT_TYPING_WRAPPER_NAMES:
                collect(_first_subscript_arg(child.slice), shape)
                return
            if owner in _FRAMEWORK_OWNED_ANNOTATION_WRAPPER_NAMES:
                return
            if owner == "Optional":
                collect(_first_subscript_arg(child.slice), _annotation_shape(shape, "optional"))
                return
            if owner == "Union":
                args = _subscript_args(child.slice)
                next_shape = "optional" if any(_is_none_annotation(arg) for arg in args) else "union"
                for arg in args:
                    if not _is_none_annotation(arg):
                        collect(arg, _annotation_shape(shape, next_shape))
                return
            if owner in _MAPPING_TYPING_NAMES:
                args = _subscript_args(child.slice)
                if len(args) >= 2:
                    collect(args[1], _annotation_shape(shape, "mapping_value"))
                return
            if owner in _COLLECTION_TYPING_NAMES:
                for arg in _subscript_args(child.slice):
                    if not _is_ellipsis_annotation(arg):
                        collect(arg, _annotation_shape(shape, "collection"))
                return
            collect(child.slice, None)
            return

        dotted_name = _dotted_name(child)
        if dotted_name is not None:
            if _is_class_like_target(dotted_name) and _terminal_name(child) not in _TYPING_WRAPPER_NAMES:
                targets.add((dotted_name, shape))
            return

        for grandchild in ast.iter_child_nodes(child):
            collect(grandchild, shape)

    collect(node, "direct")
    return tuple(sorted(targets, key=_semantic_annotation_target_sort_key))


_ANNOTATION_SHAPE_SORT_ORDER = {
    "direct": 0,
    "optional": 1,
    "union": 2,
    "collection": 3,
    "mapping_value": 4,
    None: 5,
}


def _semantic_annotation_target_sort_key(target: tuple[str, str | None]) -> tuple[str, int]:
    target_name, shape = target
    return (target_name, _ANNOTATION_SHAPE_SORT_ORDER[shape])


def _annotation_shape(current_shape: str | None, next_shape: str) -> str | None:
    if current_shape is None:
        return None
    return next_shape


def _string_annotation_expression(node: ast.AST) -> ast.AST | None:
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str) or not node.value:
        return None
    try:
        return ast.parse(node.value, mode="eval").body
    except SyntaxError:
        return None


def _semantic_class_like_names_from_string(value: str) -> tuple[str, ...]:
    try:
        expression = ast.parse(value, mode="eval").body
    except SyntaxError:
        return (value,) if _is_class_like_target(value) else ()
    return _semantic_class_like_names(expression)


def _is_class_like_target(value: str) -> bool:
    return bool(value) and value.rsplit(".", 1)[-1][:1].isupper()


def _subscript_args(node: ast.AST) -> tuple[ast.AST, ...]:
    if isinstance(node, ast.Tuple):
        return tuple(node.elts)
    return (node,)


def _pep604_union_operands(node: ast.AST) -> tuple[ast.AST, ...]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return (*_pep604_union_operands(node.left), *_pep604_union_operands(node.right))
    return (node,)


def _is_none_annotation(node: ast.AST) -> bool:
    return (
        (isinstance(node, ast.Constant) and node.value is None)
        or (isinstance(node, ast.Name) and node.id == "None")
        or (isinstance(node, ast.Constant) and node.value == "None")
    )


def _is_ellipsis_annotation(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and node.value is Ellipsis


_TRANSPARENT_TYPING_WRAPPER_NAMES = frozenset({"ClassVar", "Final", "Required", "NotRequired"})
_FRAMEWORK_OWNED_ANNOTATION_WRAPPER_NAMES = frozenset({"Mapped"})
_COLLECTION_TYPING_NAMES = frozenset(
    {
        "AbstractSet",
        "AsyncIterable",
        "AsyncIterator",
        "Collection",
        "Deque",
        "FrozenSet",
        "Iterable",
        "Iterator",
        "List",
        "MutableSequence",
        "MutableSet",
        "Sequence",
        "Set",
        "Tuple",
        "deque",
        "frozenset",
        "list",
        "set",
        "tuple",
    }
)
_MAPPING_TYPING_NAMES = frozenset({"DefaultDict", "Dict", "Mapping", "MutableMapping", "OrderedDict", "dict"})
_TYPING_WRAPPER_NAMES = frozenset(
    {
        "Annotated",
        "ClassVar",
        "Final",
        "Literal",
        "NotRequired",
        "Optional",
        "Required",
        "Union",
    }
)


def _ordered_class_references(references: Iterable[_PositionedReference]) -> tuple[ClassReference, ...]:
    positioned_by_reference: dict[ClassReference, tuple[int, int]] = {}
    for positioned in references:
        current = positioned_by_reference.get(positioned.reference)
        position = (positioned.lineno, positioned.col_offset)
        if current is None or position < current:
            positioned_by_reference[positioned.reference] = position
    return tuple(
        reference
        for reference, _ in sorted(
            positioned_by_reference.items(),
            key=lambda item: (
                item[1][0],
                item[1][1],
                item[0].source_class_id,
                item[0].reference_kind,
                item[0].reference_owner,
                item[0].target_name,
            ),
        )
    )


def _class_reference_sort_key(reference: ClassReference) -> tuple[str, str, str, str]:
    return (
        reference.source_class_id,
        reference.target_name,
        reference.reference_kind,
        reference.reference_owner,
    )


def _candidate_paths(
    import_ref: _ImportRef,
    source_path: Path,
    import_roots: tuple[Path, ...],
) -> Iterable[Path]:
    seen: set[Path] = set()
    for import_root in import_roots:
        bases = _import_base_parts(import_ref, source_path, import_root)
        candidate_parts: set[tuple[str, ...]] = set()
        if bases:
            candidate_parts.add(bases)
        for name in import_ref.names:
            if name:
                candidate_parts.add((*bases, *name.split(".")))

        for parts in sorted(candidate_parts):
            for candidate in _existing_python_candidates(import_root, parts):
                if candidate not in seen:
                    seen.add(candidate)
                    yield candidate


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
