from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

from spec_dock_runtime.application.artifact_preflight import validate_required_artifacts_for_graph
from spec_dock_runtime.application.contracts import ValidateTreeRequest, ValidationResult
from spec_dock_runtime.application.repo_context import resolve_current_repo_slug
from spec_dock_runtime.domain.authority import (
    evaluate_evidence_adoption_ledger_gate,
    load_evidence_adoption_ledger_entries,
    validate_delegated_authority_artifact,
)
from spec_dock_runtime.domain.deps import validate_raw_node_dependency_graph
from spec_dock_runtime.domain.models import SpecNodeKind, SpecNodeSeed, ValidationReport
from spec_dock_runtime.domain.tree import build_graph
from spec_dock_runtime.domain.validation import validate_graph_and_deps

if TYPE_CHECKING:
    from spec_dock_runtime.application.ports import Ports
    from spec_dock_runtime.infra.contracts import DirectDependencyResolution, StoredMetaRecord


def _to_spec_node_seed(record: StoredMetaRecord) -> SpecNodeSeed:
    return SpecNodeSeed(
        kind=cast("SpecNodeKind", record.kind),
        id=record.id,
        title=record.title,
        slug=record.slug,
        path=Path(record.path),
        meta_path=Path(record.meta_path),
        parent_id=record.parent_id,
        initiative_id=record.initiative_id,
        epic_id=record.epic_id,
        github_issue_number=record.github_issue_number,
        github_repo_owner=record.github_repo_owner,
        github_repo_name=record.github_repo_name,
    )


def validate_tree(req: ValidateTreeRequest, ports: Ports) -> ValidationResult:
    del req
    records = ports.node_reader.load_node_records()
    graph = build_graph([_to_spec_node_seed(record) for record in records])
    report = validate_graph_and_deps(
        graph,
        issue_depends_on_map=None,
        repo_root=ports.repo_root,
        current_repo_slug=resolve_current_repo_slug(ports),
    )
    if report.errors:
        return ValidationResult(report=report, checked_node_count=len(records))

    if ports.deps_topology_reader is not None:
        if ports.specdock_dir is not None:
            specdock_dir = ports.specdock_dir
        elif ports.repo_root is not None:
            specdock_dir = ports.repo_root / "spec-dock"
        else:
            raise RuntimeError("specdock_dir is required when deps_topology_reader is configured")
        topology = ports.deps_topology_reader.load_issue_depends_on_map(specdock_dir, graph)
        report = validate_graph_and_deps(
            graph,
            issue_depends_on_map=dict(topology.issue_depends_on_map),
            repo_root=ports.repo_root,
            current_repo_slug=resolve_current_repo_slug(ports),
        )
        if report.errors:
            return ValidationResult(report=report, checked_node_count=len(records))

        load_node_dependency_resolutions = getattr(
            ports.deps_topology_reader,
            "load_node_dependency_resolutions",
            None,
        )
        if callable(load_node_dependency_resolutions):
            raw_node_depends_on_map = _raw_node_depends_on_map(load_node_dependency_resolutions(specdock_dir, graph))
            try:
                validate_raw_node_dependency_graph(graph, raw_node_depends_on_map)
            except RuntimeError as error:
                return ValidationResult(
                    report=ValidationReport(errors=[str(error)], warnings=[]),
                    checked_node_count=len(records),
                )

    if not report.errors:
        try:
            validate_required_artifacts_for_graph(graph, repo_root=ports.repo_root)
        except RuntimeError as error:
            report = ValidationReport(errors=[str(error)], warnings=list(report.warnings))
    if not report.errors and ports.repo_root is not None:
        authority_errors = _validate_delegated_authority_artifacts(graph, repo_root=ports.repo_root)
        if authority_errors:
            report = ValidationReport(errors=authority_errors, warnings=list(report.warnings))
    if not report.errors and ports.repo_root is not None:
        ledger_errors = _validate_evidence_adoption_ledgers(graph, repo_root=ports.repo_root)
        if ledger_errors:
            report = ValidationReport(errors=ledger_errors, warnings=list(report.warnings))
    return ValidationResult(report=report, checked_node_count=len(records))


def _raw_node_depends_on_map(
    resolutions_by_node: dict[str, list[DirectDependencyResolution]],
) -> dict[str, list[str]]:
    return {
        node_id: [resolution.resolved_node_id for resolution in resolutions]
        for node_id, resolutions in resolutions_by_node.items()
    }


def _validate_delegated_authority_artifacts(graph, *, repo_root: Path) -> list[str]:
    errors: list[str] = []
    for node in graph.nodes_by_id.values():
        for artifact_name in ("design.md", "plan.md"):
            artifact_path = repo_root / node.path / artifact_name
            result = validate_delegated_authority_artifact(artifact_path, purpose="validate")
            if result.ok:
                continue
            detail = " ".join(result.details)
            errors.append(
                "Delegated draft authority incomplete/blocked: "
                f"path={artifact_path.as_posix()} reason={result.reason}" + (f" details={detail}" if detail else "")
            )
    return errors


def _validate_evidence_adoption_ledgers(graph, *, repo_root: Path) -> list[str]:
    errors: list[str] = []
    for node in graph.nodes_by_id.values():
        report_path = repo_root / node.path / "report.md"
        entries = load_evidence_adoption_ledger_entries(report_path)
        result = evaluate_evidence_adoption_ledger_gate(entries, target_artifact="*", purpose="validate")
        if result.ok:
            continue
        detail = " ".join(result.details)
        errors.append(
            "Evidence Adoption Ledger incomplete/blocked: "
            f"path={report_path.as_posix()} reason={result.reason} "
            f"blocking_entry_id={result.blocking_entry_id}" + (f" details={detail}" if detail else "")
        )
    return errors
