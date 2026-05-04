"""Report artifact naming, summary synthesis, and exit policy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pyclassuml.model import (
    AnalysisConfig,
    ChangedClassInventory,
    CommandName,
    CommandResult,
    DependencyGraph,
    Diagnostic,
    DiagnosticSeverity,
    DiagramModel,
    ExecutionContext,
    FailureReason,
    OriginSeam,
    PlantUmlText,
    Recoverability,
    RenderFailureSignal,
    RunSummary,
    TargetSet,
)


COUNTER_KEYS = (
    "seed_file_count",
    "reachable_file_count",
    "extracted_class_count",
    "extracted_relation_count",
    "changed_class_count",
    "ignored_file_count",
    "warning_count",
    "scope_stop_count",
    "diff_scope_excluded_count",
)
SUCCESS_OUTCOMES = frozenset({"clean_success", "warning_only_success", "degraded_success"})
HARD_FAILURE_REASONS = frozenset(
    {
        FailureReason.INVALID_CONFIG_OR_CONFIG_PATH,
        FailureReason.INVALID_PATH_OR_CONTAINMENT,
        FailureReason.GENERATE_SCOPE_VIOLATION,
        FailureReason.GENERATE_ZERO_TARGET_AFTER_NORMALIZE,
        FailureReason.DIFF_ZERO_TARGET_AFTER_SCOPE_FILTER,
        FailureReason.TRAVERSAL_LIMIT_REACHED,
        FailureReason.OUTPUT_WRITE_FAILURE,
        FailureReason.VCS_READ_FAILURE,
    }
)
STRICT_PROMOTED_REASONS = frozenset(
    {
        FailureReason.STRICT_RESOLUTION_FAILURE,
        FailureReason.STRICT_SYNTAX_ERROR,
        FailureReason.STRICT_WILDCARD_RESOLUTION_FAILURE,
        FailureReason.STRICT_DIFF_SCOPE_EXCLUSION,
    }
)


@dataclass(frozen=True)
class ArtifactNamingDecision:
    base_name: str
    resolved_output_path: Path
    collision_suffix: int | None = None


@dataclass(frozen=True)
class ExitPolicyDecision:
    outcome_kind: str
    artifact_write: bool
    stream_target: str
    exit_code: int
    failure_reason: FailureReason | None = None
    strict_promoted_failure_reasons: tuple[FailureReason, ...] = ()


@dataclass(frozen=True)
class ReportRunResult:
    command_result: CommandResult
    outcome_kind: str
    stdout_text: str
    stderr_text: str


@dataclass(frozen=True)
class ReportInputs:
    command: CommandName
    context: ExecutionContext
    config: AnalysisConfig
    timestamp: datetime
    diagnostics: tuple[Diagnostic, ...] = ()
    plantuml_text: PlantUmlText | None = None
    diagram_model: DiagramModel | None = None
    render_failure_signal: RenderFailureSignal | None = None
    target_set: TargetSet | None = None
    dependency_graph: DependencyGraph | None = None
    changed_class_inventory: ChangedClassInventory | None = None
    scope_stop_count: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.command, CommandName):
            raise ValueError("command must be CommandName")
        if not isinstance(self.context, ExecutionContext):
            raise ValueError("context must be ExecutionContext")
        if not isinstance(self.config, AnalysisConfig):
            raise ValueError("config must be AnalysisConfig")
        if not isinstance(self.timestamp, datetime):
            raise ValueError("timestamp must be datetime")
        diagnostics = tuple(self.diagnostics)
        for diagnostic in diagnostics:
            if not isinstance(diagnostic, Diagnostic):
                raise ValueError("diagnostics must contain Diagnostic values")
        if self.plantuml_text is not None and not isinstance(self.plantuml_text, PlantUmlText):
            raise ValueError("plantuml_text must be PlantUmlText or None")
        if self.diagram_model is not None and not isinstance(self.diagram_model, DiagramModel):
            raise ValueError("diagram_model must be DiagramModel or None")
        if self.render_failure_signal is not None and not isinstance(self.render_failure_signal, RenderFailureSignal):
            raise ValueError("render_failure_signal must be RenderFailureSignal or None")
        if self.target_set is not None and not isinstance(self.target_set, TargetSet):
            raise ValueError("target_set must be TargetSet or None")
        if self.dependency_graph is not None and not isinstance(self.dependency_graph, DependencyGraph):
            raise ValueError("dependency_graph must be DependencyGraph or None")
        if self.changed_class_inventory is not None and not isinstance(
            self.changed_class_inventory, ChangedClassInventory
        ):
            raise ValueError("changed_class_inventory must be ChangedClassInventory or None")
        if (
            isinstance(self.scope_stop_count, bool)
            or not isinstance(self.scope_stop_count, int)
            or self.scope_stop_count < 0
        ):
            raise ValueError("scope_stop_count must be a non-negative int")
        object.__setattr__(self, "diagnostics", diagnostics)


def decide_artifact_path(
    command: CommandName,
    context: ExecutionContext,
    config: AnalysisConfig,
    timestamp: datetime,
) -> ArtifactNamingDecision:
    if not isinstance(command, CommandName):
        raise ValueError("command must be CommandName")
    if config.output is None:
        prefix = "pyclassuml_diff" if command is CommandName.DIFF else "pyclassuml"
        base_name = f"{prefix}_{timestamp:%Y%m%d_%H%M%S}.puml"
        requested_path = context.execution_cwd / base_name
    else:
        base_name = config.output.name
        requested_path = config.output if config.output.is_absolute() else context.execution_cwd / config.output

    resolved_path = requested_path
    suffix = None
    next_suffix = 2
    while resolved_path.exists():
        suffix = next_suffix
        resolved_path = requested_path.with_name(f"{requested_path.stem}_{next_suffix}{requested_path.suffix}")
        next_suffix += 1

    return ArtifactNamingDecision(
        base_name=base_name,
        resolved_output_path=resolved_path,
        collision_suffix=suffix,
    )


def decide_exit_policy(
    diagnostics: tuple[Diagnostic, ...] = (),
    render_failure_signal: RenderFailureSignal | None = None,
) -> ExitPolicyDecision:
    all_diagnostics = _combined_diagnostics(diagnostics, render_failure_signal)
    hard_reason = _first_failure_reason(all_diagnostics, HARD_FAILURE_REASONS)
    if hard_reason is not None:
        return ExitPolicyDecision(
            outcome_kind="hard_failure",
            artifact_write=False,
            stream_target="stderr",
            exit_code=1,
            failure_reason=hard_reason,
            strict_promoted_failure_reasons=_strict_reasons(all_diagnostics),
        )

    strict_reasons = _strict_reasons(all_diagnostics)
    if strict_reasons:
        return ExitPolicyDecision(
            outcome_kind="strict_promoted_failure",
            artifact_write=False,
            stream_target="stderr",
            exit_code=1,
            failure_reason=strict_reasons[0],
            strict_promoted_failure_reasons=strict_reasons,
        )

    uncategorized_error_reason = _first_error_failure_reason(tuple(diagnostics))
    if uncategorized_error_reason is not None:
        return ExitPolicyDecision(
            outcome_kind="hard_failure",
            artifact_write=False,
            stream_target="stderr",
            exit_code=1,
            failure_reason=uncategorized_error_reason,
        )

    if render_failure_signal is not None:
        return ExitPolicyDecision(
            outcome_kind="degraded_failure",
            artifact_write=False,
            stream_target="stderr",
            exit_code=1,
            failure_reason=render_failure_signal.failure_reason,
        )

    warnings = tuple(diagnostic for diagnostic in all_diagnostics if diagnostic.severity is DiagnosticSeverity.WARNING)
    if not warnings:
        outcome = "clean_success"
    elif any(diagnostic.recoverability is Recoverability.DEGRADED_OUTPUT for diagnostic in warnings):
        outcome = "degraded_success"
    else:
        outcome = "warning_only_success"

    return ExitPolicyDecision(
        outcome_kind=outcome,
        artifact_write=True,
        stream_target="stdout",
        exit_code=0,
    )


def build_run_summary(
    *,
    diagnostics: tuple[Diagnostic, ...] = (),
    failure_reason: FailureReason | None = None,
    diagram_model: DiagramModel | None = None,
    render_failure_signal: RenderFailureSignal | None = None,
    target_set: TargetSet | None = None,
    dependency_graph: DependencyGraph | None = None,
    changed_class_inventory: ChangedClassInventory | None = None,
    scope_stop_count: int = 0,
) -> RunSummary:
    class_count = 0
    relation_count = 0
    if render_failure_signal is not None:
        class_count = render_failure_signal.class_count
        relation_count = render_failure_signal.relation_count
    elif diagram_model is not None:
        class_count = len(diagram_model.rendered_classes)
        relation_count = len(diagram_model.rendered_relations)

    counters = {
        "seed_file_count": len(target_set.seed_files) if target_set is not None else 0,
        "reachable_file_count": len(dependency_graph.reachable_files) if dependency_graph is not None else 0,
        "extracted_class_count": class_count,
        "extracted_relation_count": relation_count,
        "changed_class_count": changed_class_inventory.class_count if changed_class_inventory is not None else 0,
        "ignored_file_count": target_set.observations.ignored_seed_candidate_count if target_set is not None else 0,
        "warning_count": sum(1 for diagnostic in diagnostics if diagnostic.severity is DiagnosticSeverity.WARNING),
        "scope_stop_count": scope_stop_count,
        "diff_scope_excluded_count": target_set.observations.diff_scope_excluded_count if target_set is not None else 0,
    }
    return RunSummary(counters={key: counters[key] for key in COUNTER_KEYS}, failure_reason=failure_reason)


def write_report(
    inputs: ReportInputs,
    *,
    write_text: Callable[[Path, str], None] | None = None,
    make_parent_dirs: Callable[[Path], None] | None = None,
) -> ReportRunResult:
    if write_text is None:
        write_text = _write_text
    if make_parent_dirs is None:
        make_parent_dirs = _make_parent_dirs

    naming = decide_artifact_path(inputs.command, inputs.context, inputs.config, inputs.timestamp)
    policy = decide_exit_policy(inputs.diagnostics, inputs.render_failure_signal)
    diagnostics = _combined_diagnostics(inputs.diagnostics, inputs.render_failure_signal)

    if policy.artifact_write and (inputs.plantuml_text is None or inputs.diagram_model is None):
        diagnostics = (
            *diagnostics,
            _output_write_failure_diagnostic("successful report outcome requires PlantUML text and diagram model"),
        )
        policy = decide_exit_policy(diagnostics, inputs.render_failure_signal)

    if policy.artifact_write:
        try:
            plantuml_text = inputs.plantuml_text
            if plantuml_text is None:
                raise OSError("missing PlantUML text")
            make_parent_dirs(naming.resolved_output_path.parent)
            write_text(naming.resolved_output_path, plantuml_text.text)
        except OSError as exc:
            diagnostics = (*diagnostics, _output_write_failure_diagnostic(str(exc)))
            policy = decide_exit_policy(diagnostics, inputs.render_failure_signal)

    summary_signal = inputs.render_failure_signal
    if policy.outcome_kind == "hard_failure" and policy.failure_reason is FailureReason.OUTPUT_WRITE_FAILURE:
        summary_signal = None
    summary = build_run_summary(
        diagnostics=diagnostics,
        failure_reason=policy.failure_reason,
        diagram_model=inputs.diagram_model,
        render_failure_signal=summary_signal,
        target_set=inputs.target_set,
        dependency_graph=inputs.dependency_graph,
        changed_class_inventory=inputs.changed_class_inventory,
        scope_stop_count=inputs.scope_stop_count,
    )
    artifact_path = naming.resolved_output_path if policy.artifact_write else None
    command_result = CommandResult(
        artifact_path=artifact_path,
        summary=summary,
        diagnostics=diagnostics,
        exit_code=policy.exit_code,
    )
    summary_text = _format_summary(policy.outcome_kind, summary, diagnostics)
    return ReportRunResult(
        command_result=command_result,
        outcome_kind=policy.outcome_kind,
        stdout_text=summary_text if policy.stream_target == "stdout" else "",
        stderr_text=summary_text if policy.stream_target == "stderr" else "",
    )


def _combined_diagnostics(
    diagnostics: tuple[Diagnostic, ...],
    render_failure_signal: RenderFailureSignal | None,
) -> tuple[Diagnostic, ...]:
    if render_failure_signal is None:
        return tuple(diagnostics)
    return _dedupe_diagnostics((*diagnostics, *render_failure_signal.diagnostics))


def _dedupe_diagnostics(diagnostics: tuple[Diagnostic, ...]) -> tuple[Diagnostic, ...]:
    deduped: list[Diagnostic] = []
    for diagnostic in diagnostics:
        if any(diagnostic == existing for existing in deduped):
            continue
        deduped.append(diagnostic)
    return tuple(deduped)


def _first_failure_reason(
    diagnostics: tuple[Diagnostic, ...],
    reasons: frozenset[FailureReason],
) -> FailureReason | None:
    for diagnostic in diagnostics:
        if diagnostic.failure_reason in reasons:
            return diagnostic.failure_reason
    return None


def _strict_reasons(diagnostics: tuple[Diagnostic, ...]) -> tuple[FailureReason, ...]:
    reasons: list[FailureReason] = []
    for diagnostic in diagnostics:
        if diagnostic.failure_reason in STRICT_PROMOTED_REASONS:
            reasons.append(diagnostic.failure_reason)
    return tuple(reasons)


def _first_error_failure_reason(diagnostics: tuple[Diagnostic, ...]) -> FailureReason | None:
    for diagnostic in diagnostics:
        if diagnostic.severity is DiagnosticSeverity.ERROR:
            return diagnostic.failure_reason
    return None


def _output_write_failure_diagnostic(message: str) -> Diagnostic:
    return Diagnostic(
        severity=DiagnosticSeverity.ERROR,
        code="output_write_failure",
        message=f"failed to write report artifact: {message}",
        origin_seam=OriginSeam.REPORT,
        recoverability=Recoverability.FATAL,
        failure_reason=FailureReason.OUTPUT_WRITE_FAILURE,
    )


def _format_summary(
    outcome_kind: str,
    summary: RunSummary,
    diagnostics: tuple[Diagnostic, ...],
) -> str:
    lines = [f"outcome: {outcome_kind}", f"exit_code: {0 if outcome_kind in SUCCESS_OUTCOMES else 1}"]
    if summary.failure_reason is not None:
        lines.append(f"failure_reason: {summary.failure_reason.value}")
    lines.append("counters:")
    for key in COUNTER_KEYS:
        lines.append(f"{key}: {summary.counters[key]}")
    if diagnostics:
        lines.append("diagnostics:")
        for diagnostic in diagnostics:
            lines.append(f"{diagnostic.severity.value}:{diagnostic.code}: {diagnostic.message}")
    return "\n".join(lines) + "\n"


def _make_parent_dirs(parent: Path) -> None:
    parent.mkdir(parents=True, exist_ok=True)


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


__all__ = [
    "ArtifactNamingDecision",
    "ExitPolicyDecision",
    "ReportInputs",
    "ReportRunResult",
    "build_run_summary",
    "decide_artifact_path",
    "decide_exit_policy",
    "write_report",
]
