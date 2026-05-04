"""Generate command application wiring."""

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
    CommandName,
    CommandRequest,
    Diagnostic,
    ExecutionContext,
)
from pyclassuml.parse import parse_target_set
from pyclassuml.render import render_uml_document
from pyclassuml.report import ReportInputs, ReportRunResult, write_report
from pyclassuml.targets import normalize_explicit_targets


def run_generate(request: CommandRequest, *, timestamp: datetime) -> ReportRunResult:
    """Run the generate pipeline and return report-owned stream/result material."""

    if request.cli_options.command is not CommandName.GENERATE:
        raise ValueError("run_generate requires a generate command request")

    config_resolution = resolve_context(request)
    diagnostics: tuple[Diagnostic, ...] = tuple(config_resolution.diagnostics)
    context = config_resolution.context
    config = config_resolution.analysis_config

    if context is None or config is None:
        return write_report(
            ReportInputs(
                command=CommandName.GENERATE,
                context=_fallback_context(request.process_cwd),
                config=AnalysisConfig(),
                timestamp=timestamp,
                diagnostics=diagnostics,
            )
        )

    target_normalization = normalize_explicit_targets(request, context, config)
    diagnostics = (*diagnostics, *target_normalization.diagnostics)
    target_set = target_normalization.target_set
    if target_set is None:
        return write_report(
            ReportInputs(
                command=CommandName.GENERATE,
                context=context,
                config=config,
                timestamp=timestamp,
                diagnostics=diagnostics,
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

    changed_class_inventory = build_changed_class_inventory(
        (),
        parse_result.parsed_modules,
        parse_result.module_index,
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
    )

    return write_report(
        ReportInputs(
            command=CommandName.GENERATE,
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


__all__ = ["run_generate"]
