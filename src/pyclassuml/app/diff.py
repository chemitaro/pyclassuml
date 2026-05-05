"""Diff command application wiring."""

from __future__ import annotations

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
    CommandName,
    CommandRequest,
    Diagnostic,
    ExecutionContext,
    ParsedModule,
    SelectedClasses,
    TargetSet,
)
from pyclassuml.parse import ModuleIndex, parse_target_set
from pyclassuml.render import render_uml_document
from pyclassuml.report import ReportInputs, ReportRunResult, write_report
from pyclassuml.targets import normalize_diff_targets
from pyclassuml.vcs import ChangedFileCollection, collect_diff_files


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
    class_decorations = _diff_class_decorations(
        changed_paths,
        parse_result.parsed_modules,
        parse_result.module_index,
        selection_result.selected_classes,
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


def _diff_class_decorations(
    changed_files: tuple[Path, ...],
    parsed_modules: tuple[ParsedModule, ...],
    module_index: ModuleIndex,
    selected_classes: SelectedClasses,
) -> tuple[tuple[ClassId, str], ...]:
    module_by_path = {parsed_module.module_path: parsed_module for parsed_module in parsed_modules}
    changed_module_paths = {
        module_path
        for changed_file in changed_files
        if (module_path := module_index.project_relative_file_to_module.get(changed_file)) is not None
    }
    changed_class_ids = {
        class_id
        for module_path in changed_module_paths
        if (parsed_module := module_by_path.get(module_path)) is not None
        for class_id in parsed_module.classes
    }

    decorations = []
    for class_id in sorted(selected_classes.class_ids):
        if class_id in changed_class_ids:
            decorations.append((class_id, "DiffChanged"))
            continue
        decorations.append((class_id, "DiffDependency"))
    return tuple(decorations)


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
