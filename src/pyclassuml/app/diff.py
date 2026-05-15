"""Diff command application wiring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pyclassuml.analyze import (
    build_changed_class_inventory,
    select_classes_and_relations,
    traverse_dependencies,
)
from pyclassuml.config import resolve_context
from pyclassuml.frameworks import (
    extract_pydantic_enrichment_hints,
    extract_sqlalchemy_enrichment_hints,
)
from pyclassuml.model import (
    AnalysisConfig,
    ClassId,
    ClassSpan,
    CommandName,
    CommandRequest,
    Diagnostic,
    DiagnosticSeverity,
    ExecutionContext,
    OriginSeam,
    ParsedModule,
    Recoverability,
    SelectedClasses,
    TargetSet,
)
from pyclassuml.parse import ModuleIndex, parse_module_source_text, parse_target_set
from pyclassuml.render import render_uml_document
from pyclassuml.report import ReportInputs, ReportRunResult, write_report
from pyclassuml.targets import normalize_diff_targets
from pyclassuml.vcs import ChangedFileCollection, ChangedFileEntry, ChangedLineRange, collect_diff_files, read_base_file_text
import pyclassuml.vcs.diff_collect as diff_collect


@dataclass(frozen=True)
class DiffClassificationSnapshot:
    parsed_modules: tuple[ParsedModule, ...]
    diagnostics: tuple[Diagnostic, ...] = ()


@dataclass(frozen=True)
class BaseClassInventory:
    class_ids_by_path: dict[Path, frozenset[ClassId] | None]
    diagnostics: tuple[Diagnostic, ...] = ()


def run_diff(request: CommandRequest, *, timestamp: datetime) -> ReportRunResult:
    """Run the diff pipeline and return report-owned stream/result material."""

    if request.cli_options.command is not CommandName.DIFF:
        raise ValueError("run_diff requires a diff command request")

    config_resolution = resolve_context(request)
    diagnostics: tuple[Diagnostic, ...] = tuple(config_resolution.diagnostics)
    context = config_resolution.context
    config = config_resolution.analysis_config

    if context is None or config is None:
        return write_report(
            ReportInputs(
                command=CommandName.DIFF,
                context=_fallback_context(request.process_cwd),
                config=AnalysisConfig(),
                timestamp=timestamp,
                diagnostics=diagnostics,
            )
        )

    vcs_collection = collect_diff_files(request, context, config)
    if vcs_collection.collection is None:
        return write_report(
            ReportInputs(
                command=CommandName.DIFF,
                context=context,
                config=config,
                timestamp=timestamp,
                diagnostics=(*diagnostics, *vcs_collection.diagnostics),
            )
        )

    target_normalization = normalize_diff_targets(
        vcs_collection.collection,
        context,
        config,
        upstream_diagnostics=tuple(vcs_collection.diagnostics),
    )
    diagnostics = (*diagnostics, *target_normalization.diagnostics)
    target_set = target_normalization.target_set
    if target_set is None:
        return write_report(
            ReportInputs(
                command=CommandName.DIFF,
                context=context,
                config=config,
                timestamp=timestamp,
                diagnostics=diagnostics,
                target_set=TargetSet(
                    seed_files=(),
                    observations=target_normalization.observations,
                ),
            )
        )

    parse_result = parse_target_set(target_set, context, config)
    diagnostics = (*diagnostics, *parse_result.diagnostics)

    traversal_result = traverse_dependencies(
        parse_result.parsed_modules,
        parse_result.module_index,
        context,
        config,
    )
    diagnostics = (*diagnostics, *traversal_result.diagnostics)

    selection_result = select_classes_and_relations(
        parse_result.parsed_modules,
        parse_result.module_index,
        traversal_result.graph,
        traversal_result.observations,
    )
    diagnostics = (*diagnostics, *selection_result.diagnostics)

    changed_paths = _project_relative_changed_paths(vcs_collection.collection)
    changed_class_inventory = build_changed_class_inventory(
        changed_paths,
        parse_result.parsed_modules,
        parse_result.module_index,
    )
    classification_entries = _classification_changed_entries(
        vcs_collection.collection.entries,
        parse_result.module_index,
    )
    current_classification_snapshot = _current_parsed_modules_for_diff_classification(
        request,
        context,
        config,
        classification_entries,
        parse_result.parsed_modules,
    )
    base_class_inventory = _base_class_ids_by_current_path(request, context, classification_entries)
    diagnostics = (*diagnostics, *current_classification_snapshot.diagnostics, *base_class_inventory.diagnostics)
    class_decorations = _diff_class_decorations(
        classification_entries,
        parse_result.parsed_modules,
        parse_result.module_index,
        selection_result.selected_classes,
        _current_file_lines_by_path_for_diff_classification(
            request,
            context,
            config,
            classification_entries,
        ),
        base_class_inventory.class_ids_by_path,
        classification_parsed_modules=current_classification_snapshot.parsed_modules,
    )

    sqlalchemy_hints = extract_sqlalchemy_enrichment_hints(
        parse_result.parsed_modules,
        parse_result.module_index,
        selection_result.selected_classes,
        selection_result.selected_relations,
    )
    diagnostics = (*diagnostics, *sqlalchemy_hints.warning_diagnostics)

    pydantic_hints = extract_pydantic_enrichment_hints(
        parse_result.parsed_modules,
        parse_result.module_index,
        selection_result.selected_classes,
        selection_result.selected_relations,
    )
    diagnostics = (*diagnostics, *pydantic_hints.warning_diagnostics)

    render_result = render_uml_document(
        parsed_modules=parse_result.parsed_modules,
        module_index=parse_result.module_index,
        selected_classes=selection_result.selected_classes,
        selected_relations=selection_result.selected_relations,
        sqlalchemy_hints=sqlalchemy_hints,
        pydantic_hints=pydantic_hints,
        class_decorations=class_decorations,
    )

    return write_report(
        ReportInputs(
            command=CommandName.DIFF,
            context=context,
            config=config,
            timestamp=timestamp,
            diagnostics=diagnostics,
            plantuml_text=render_result.plantuml_text,
            diagram_model=render_result.diagram_model,
            render_failure_signal=render_result.failure_signal,
            target_set=target_set,
            dependency_graph=traversal_result.graph,
            changed_class_inventory=changed_class_inventory,
            scope_stop_count=traversal_result.observations.scope_stop_count,
        )
    )


def _project_relative_changed_paths(collection: ChangedFileCollection) -> tuple[Path, ...]:
    return tuple(Path(entry.current_project_relative_path) for entry in collection.entries)


def _classification_changed_entries(
    changed_entries: tuple[ChangedFileEntry, ...],
    module_index: ModuleIndex,
) -> tuple[ChangedFileEntry, ...]:
    return tuple(
        entry
        for entry in changed_entries
        if Path(entry.current_project_relative_path) in module_index.project_relative_file_to_module
    )


def _diff_class_decorations(
    changed_entries: tuple[ChangedFileEntry, ...],
    parsed_modules: tuple[ParsedModule, ...],
    module_index: ModuleIndex,
    selected_classes: SelectedClasses,
    current_file_lines_by_path: dict[Path, tuple[str, ...]] | None = None,
    base_class_ids_by_path: dict[Path, frozenset[ClassId] | None] | None = None,
    *,
    classification_parsed_modules: tuple[ParsedModule, ...] | None = None,
) -> tuple[tuple[ClassId, str], ...]:
    if classification_parsed_modules is None:
        classification_parsed_modules = parsed_modules
    module_by_path = {parsed_module.module_path: parsed_module for parsed_module in classification_parsed_modules}
    selected_class_ids = set(selected_classes.class_ids)
    added_class_ids: set[ClassId] = set()
    changed_class_ids: set[ClassId] = set()
    current_file_lines_by_path = current_file_lines_by_path or {}
    base_class_ids_by_path = base_class_ids_by_path or {}

    for entry in changed_entries:
        changed_file = Path(entry.current_project_relative_path)
        module_path = module_index.project_relative_file_to_module.get(changed_file)
        if module_path is None or (parsed_module := module_by_path.get(module_path)) is None:
            continue
        base_class_ids = base_class_ids_by_path.get(changed_file)
        if base_class_ids is None and changed_file in base_class_ids_by_path:
            continue
        if entry.change_kind == "added":
            selected_spans = tuple(
                class_span for class_span in parsed_module.class_spans if class_span.class_id in selected_class_ids
            )
            added_class_ids.update(class_span.class_id for class_span in selected_spans)
            continue
        if base_class_ids is not None:
            current_only_spans = tuple(
                class_span
                for class_span in parsed_module.class_spans
                if class_span.class_id in selected_class_ids and class_span.class_id not in base_class_ids
            )
            if entry.current_changed_line_ranges:
                current_lines = current_file_lines_by_path.get(changed_file, ())
                for changed_range in entry.current_changed_line_ranges:
                    added_class_ids.update(
                        class_span.class_id
                        for class_span in _innermost_changed_class_spans(current_only_spans, changed_range, current_lines)
                    )
            else:
                added_class_ids.update(class_span.class_id for class_span in current_only_spans)
        selected_spans = tuple(
            class_span
            for class_span in parsed_module.class_spans
            if class_span.class_id in selected_class_ids and class_span.class_id not in added_class_ids
        )
        current_lines = current_file_lines_by_path.get(changed_file, ())
        for changed_range in entry.current_changed_line_ranges:
            changed_class_ids.update(
                class_span.class_id
                for class_span in _innermost_changed_class_spans(selected_spans, changed_range, current_lines)
            )

    decorations = []
    for class_id in sorted(selected_classes.class_ids):
        if class_id in added_class_ids:
            decorations.append((class_id, "DiffAdded"))
        elif class_id in changed_class_ids:
            decorations.append((class_id, "DiffChanged"))
    return tuple(decorations)


def _current_parsed_modules_for_diff_classification(
    request: CommandRequest,
    context: ExecutionContext,
    config: AnalysisConfig,
    changed_entries: tuple[ChangedFileEntry, ...],
    parsed_modules: tuple[ParsedModule, ...],
) -> DiffClassificationSnapshot:
    if config.diff_current_state.value != "head":
        return DiffClassificationSnapshot(parsed_modules=parsed_modules)
    result: list[ParsedModule] = []
    diagnostics: list[Diagnostic] = []
    parsed_by_path = {parsed_module.module_path: parsed_module for parsed_module in parsed_modules}
    for entry in changed_entries:
        current_path = Path(entry.current_project_relative_path)
        if current_path not in parsed_by_path:
            continue
        try:
            current_text = read_base_file_text(context.vcs_root, context.project_root, "HEAD", entry.current_project_relative_path)
            result.append(parse_module_source_text(current_text, current_path, filename=f"HEAD:{entry.current_project_relative_path}"))
        except diff_collect.VcsDiffError as exc:
            diagnostics.append(
                _diff_classification_diagnostic(
                    "diff_classification_current_read_unavailable",
                    f"Diff classification skipped for {entry.current_project_relative_path}: {exc.message}",
                )
            )
        except SyntaxError as exc:
            diagnostics.append(
                _diff_classification_diagnostic(
                    "diff_classification_current_parse_unavailable",
                    f"Diff classification skipped for {entry.current_project_relative_path}: {exc.msg}",
                )
            )
    return DiffClassificationSnapshot(parsed_modules=tuple(result), diagnostics=tuple(diagnostics))


def _base_class_ids_by_current_path(
    request: CommandRequest,
    context: ExecutionContext,
    changed_entries: tuple[ChangedFileEntry, ...],
) -> BaseClassInventory:
    base_ref = request.cli_options.diff.base_ref if request.cli_options.diff is not None else ""
    result: dict[Path, frozenset[ClassId] | None] = {}
    diagnostics: list[Diagnostic] = []
    for entry in changed_entries:
        current_path = Path(entry.current_project_relative_path)
        if entry.change_kind == "added":
            result[current_path] = frozenset()
            continue
        base_path = entry.previous_project_relative_path or entry.current_project_relative_path
        try:
            base_text = read_base_file_text(context.vcs_root, context.project_root, base_ref, base_path)
            parsed_module = parse_module_source_text(
                base_text,
                current_path,
                filename=f"{base_ref}:{base_path}",
            )
        except diff_collect.VcsDiffError as exc:
            diagnostics.append(
                _diff_classification_diagnostic(
                    "diff_classification_base_read_unavailable",
                    f"Diff classification skipped for {entry.current_project_relative_path}: {exc.message}",
                )
            )
            result[current_path] = None
            continue
        except SyntaxError as exc:
            diagnostics.append(
                _diff_classification_diagnostic(
                    "diff_classification_base_parse_unavailable",
                    f"Diff classification skipped for {entry.current_project_relative_path}: {exc.msg}",
                )
            )
            result[current_path] = None
            continue
        result[current_path] = frozenset(parsed_module.classes)
    return BaseClassInventory(class_ids_by_path=result, diagnostics=tuple(diagnostics))


def _diff_classification_diagnostic(code: str, message: str) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.WARNING,
        code=code,
        message=message,
        origin_seam=OriginSeam.APP,
        recoverability=Recoverability.DEGRADED_OUTPUT,
        failure_reason=None,
    )


def _current_file_lines_by_path(
    project_root: Path,
    changed_entries: tuple[ChangedFileEntry, ...],
) -> dict[Path, tuple[str, ...]]:
    lines_by_path: dict[Path, tuple[str, ...]] = {}
    for entry in changed_entries:
        changed_file = Path(entry.current_project_relative_path)
        try:
            lines_by_path[changed_file] = tuple((project_root / changed_file).read_text(encoding="utf-8").splitlines())
        except OSError:
            lines_by_path[changed_file] = ()
    return lines_by_path


def _current_file_lines_by_path_for_diff_classification(
    request: CommandRequest,
    context: ExecutionContext,
    config: AnalysisConfig,
    changed_entries: tuple[ChangedFileEntry, ...],
) -> dict[Path, tuple[str, ...]]:
    if config.diff_current_state.value != "head":
        return _current_file_lines_by_path(context.project_root, changed_entries)
    lines_by_path: dict[Path, tuple[str, ...]] = {}
    for entry in changed_entries:
        changed_file = Path(entry.current_project_relative_path)
        try:
            current_text = read_base_file_text(context.vcs_root, context.project_root, "HEAD", entry.current_project_relative_path)
            lines_by_path[changed_file] = tuple(current_text.splitlines())
        except diff_collect.VcsDiffError:
            lines_by_path[changed_file] = ()
    return lines_by_path


def _innermost_changed_class_spans(
    class_spans: tuple[ClassSpan, ...],
    changed_range: ChangedLineRange,
    current_lines: tuple[str, ...],
) -> tuple[ClassSpan, ...]:
    overlapping_spans = tuple(
        class_span
        for class_span in class_spans
        if _class_span_overlaps_changed_range(class_span, changed_range, current_lines)
    )
    return tuple(
        class_span
        for class_span in overlapping_spans
        if not any(_class_span_contains(class_span, other) for other in overlapping_spans if other is not class_span)
    )


def _class_span_contains(outer: ClassSpan, inner: ClassSpan) -> bool:
    return outer.start_line <= inner.start_line and inner.end_line <= outer.end_line


def _class_span_overlaps_changed_range(
    class_span: ClassSpan,
    changed_range: ChangedLineRange,
    current_lines: tuple[str, ...],
) -> bool:
    if not changed_range.is_deletion_only:
        return changed_range.start <= class_span.end_line and class_span.start_line <= changed_range.end
    if _deleted_lines_include_decorator(changed_range.deleted_lines):
        return _deleted_decorator_belongs_to_class(class_span, changed_range, current_lines)
    return (
        class_span.start_line <= changed_range.start <= class_span.end_line
        and _deleted_lines_look_like_class_span_change(changed_range.deleted_lines)
    )


def _deleted_lines_include_decorator(deleted_lines: tuple[str, ...]) -> bool:
    return any(line.lstrip().startswith("@") for line in deleted_lines)


def _deleted_decorator_belongs_to_class(
    class_span: ClassSpan,
    changed_range: ChangedLineRange,
    current_lines: tuple[str, ...],
) -> bool:
    if _deleted_lines_include_top_level_function_definition(changed_range.deleted_lines):
        return False
    if changed_range.is_before_first_line_deletion:
        return class_span.start_line == 1
    if changed_range.start == class_span.start_line:
        return True
    if changed_range.start != class_span.start_line - 1:
        return False
    if not current_lines:
        return True
    class_line = _line_at(current_lines, class_span.start_line)
    return _looks_like_class_definition(class_line)


def _line_at(lines: tuple[str, ...], line_number: int) -> str:
    index = line_number - 1
    if index < 0 or index >= len(lines):
        return ""
    return lines[index].lstrip()


def _looks_like_class_definition(line: str) -> bool:
    return line.startswith("class ")


def _deleted_lines_include_top_level_function_definition(deleted_lines: tuple[str, ...]) -> bool:
    return any(_looks_like_top_level_function_definition(line) for line in deleted_lines)


def _looks_like_top_level_function_definition(line: str) -> bool:
    stripped = line.lstrip()
    return line == stripped and stripped.startswith(("def ", "async def "))


def _deleted_lines_look_like_class_span_change(deleted_lines: tuple[str, ...]) -> bool:
    first_content_line = next((line for line in deleted_lines if line.strip()), "")
    return first_content_line.startswith((" ", "\t", "@"))


def _fallback_context(process_cwd: Path) -> ExecutionContext:
    try:
        resolved = process_cwd.resolve()
    except (OSError, RuntimeError):
        resolved = process_cwd
    return ExecutionContext(
        execution_cwd=resolved,
        project_root=resolved,
        package_root=resolved,
        scope_root=resolved,
    )


__all__ = ["run_diff"]
