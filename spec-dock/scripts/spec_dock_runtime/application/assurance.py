from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any, Protocol

from spec_dock_runtime.application.contracts import (
    AssuranceOperation,
    AssuranceResult,
    AssuranceTargetView,
    ClassifyAssuranceRequest,
    ComposeArtifactView,
    ComposeAssuranceRequest,
    ShowAssuranceRequest,
    VerifyAssuranceRequest,
)
from spec_dock_runtime.domain.artifact_composer import ComposeArtifactResult, MarkerConflict, compose_artifact
from spec_dock_runtime.domain.assurance import (
    AssuranceContract,
    ClassificationStage,
    SourceBinding,
    build_assurance_contract,
)

if TYPE_CHECKING:
    from pathlib import Path


class AssuranceStoreLike(Protocol):
    def resolve_issue_target(self, target: str | Path | None) -> Any: ...

    def build_requirement_source_binding(self, target: Any) -> SourceBinding: ...

    def build_planning_source_binding(self, target: Any) -> SourceBinding: ...

    def write_contract(self, target: Any, contract: AssuranceContract) -> Path: ...

    def read_contract(self, target: Any) -> Any: ...

    def verify_contract(self, target: Any) -> Any: ...

    def ensure_contract_writable(self, target: Any) -> None: ...


class ArtifactStoreLike(Protocol):
    def artifact_kinds(self, selection: str) -> tuple[Any, ...]: ...

    def read_artifact(self, target: Any, artifact: Any) -> Any: ...

    def ensure_artifact_writable(self, artifact: Any) -> None: ...

    def write_artifact(self, artifact: Any, text: str) -> None: ...

    def load_profile_section_manifest(self) -> Any: ...

    def load_profile_artifact_template(self, artifact: Any, profile: Any) -> Any: ...


def show_assurance(request: ShowAssuranceRequest, *, store: AssuranceStoreLike) -> AssuranceResult:
    target = store.resolve_issue_target(request.issue)
    return _result_from_store_result(operation="show", store_result=store.read_contract(target))


def classify_assurance(request: ClassifyAssuranceRequest, *, store: AssuranceStoreLike) -> AssuranceResult:
    target = store.resolve_issue_target(request.issue)
    source_binding = store.build_requirement_source_binding(target)
    contract = build_assurance_contract(
        issue_id=target.issue_id,
        stage=ClassificationStage(request.stage),
        source_binding=source_binding,
    )
    written_path = None
    if not request.dry_run:
        written_path = store.write_contract(target, contract)
    return AssuranceResult(
        operation="classify",
        ok=True,
        status="valid",
        target=_target_view(target),
        mode=contract.mode.value,
        reason="ok",
        details=(),
        contract=contract,
        dry_run=request.dry_run,
        written_path=written_path,
    )


def verify_assurance(request: VerifyAssuranceRequest, *, store: AssuranceStoreLike) -> AssuranceResult:
    target = store.resolve_issue_target(request.issue)
    return _result_from_store_result(operation="verify", store_result=store.verify_contract(target))


def compose_assurance(
    request: ComposeAssuranceRequest,
    *,
    store: AssuranceStoreLike,
    artifact_store: ArtifactStoreLike,
) -> AssuranceResult:
    target = store.resolve_issue_target(request.issue)
    store_result = store.verify_contract(target)
    stale_store_result = None
    if store_result.reason == "stale_source_binding" and store_result.contract is not None:
        stale_store_result = store_result
    elif store_result.status != "valid" or store_result.contract is None:
        return _compose_invalid_result(store_result)

    contract = store_result.contract
    if stale_store_result is not None:
        return _compose_invalid_result(stale_store_result)

    manifest = artifact_store.load_profile_section_manifest()
    artifacts = [
        artifact_store.read_artifact(target, artifact) for artifact in artifact_store.artifact_kinds(request.artifact)
    ]
    composed = []
    for artifact in artifacts:
        try:
            profile_template = (
                artifact_store.load_profile_artifact_template(
                    artifact.artifact,
                    contract.classification.authorized_profile.value,
                )
                if artifact.artifact in ("design", "plan")
                else None
            )
        except (FileNotFoundError, NotADirectoryError, OSError, RuntimeError, ValueError) as exc:
            composed.append((artifact, _template_validation_error(artifact.artifact, contract, str(exc))))
            continue
        composed.append((
            artifact,
            compose_artifact(
                artifact.text,
                manifest,
                artifact.artifact,
                contract.classification.authorized_profile,
                lite_candidate=contract.classification.lite_candidate,
                profile_template=profile_template,
            ),
        ))

    if any(not result.ok for _, result in composed):
        views = tuple(_compose_artifact_view(artifact, result) for artifact, result in composed)
        reason = (
            "template_validation_failed"
            if any(error.kind == "template_validation_failed" for _, result in composed for error in result.errors)
            else "substantive_content_conflict"
            if any(error.kind == "substantive_content_conflict" for _, result in composed for error in result.errors)
            else "marker_conflict"
        )
        return AssuranceResult(
            operation="compose",
            ok=False,
            status="invalid",
            target=_target_view(target),
            mode=contract.mode.value,
            reason=reason,
            details=tuple(error for view in views for error in view.errors),
            contract=contract,
            authorized_profile=contract.classification.authorized_profile.value,
            lite_candidate=contract.classification.lite_candidate,
            artifacts=views,
            errors=tuple(error for view in views for error in view.errors),
        )

    changed = [(artifact, result) for artifact, result in composed if result.changed]
    if not request.dry_run:
        if changed:
            store.ensure_contract_writable(target)
            for artifact, _ in changed:
                artifact_store.ensure_artifact_writable(artifact)
        for artifact, result in changed:
            if result.output_text is not None:
                artifact_store.write_artifact(artifact, result.output_text)
        if changed:
            contract = replace(contract, source_binding=store.build_planning_source_binding(target))
            store.write_contract(target, contract)

    return AssuranceResult(
        operation="compose",
        ok=True,
        status="dry-run" if request.dry_run else ("applied" if changed else "unchanged"),
        target=_target_view(target),
        mode=contract.mode.value,
        reason="ok",
        details=(),
        contract=contract,
        dry_run=request.dry_run,
        authorized_profile=contract.classification.authorized_profile.value,
        lite_candidate=contract.classification.lite_candidate,
        changed_paths=tuple(artifact.repo_relative_path for artifact, _ in changed),
        artifacts=tuple(_compose_artifact_view(artifact, result) for artifact, result in composed),
        warnings=tuple(warning for _, result in composed for warning in result.warnings),
    )


def _result_from_store_result(*, operation: AssuranceOperation, store_result: Any) -> AssuranceResult:
    return AssuranceResult(
        operation=operation,
        ok=store_result.status in ("valid", "missing"),
        status=store_result.status,
        target=_target_view(store_result.target),
        mode=store_result.mode,
        reason=store_result.reason,
        details=store_result.details,
        contract=store_result.contract,
    )


def _compose_invalid_result(store_result: Any) -> AssuranceResult:
    details = store_result.details
    if store_result.status == "missing":
        details = (*details, "Run `assurance classify --stage requirement` before compose.")
    return AssuranceResult(
        operation="compose",
        ok=False,
        status="invalid",
        target=_target_view(store_result.target),
        mode=store_result.mode,
        reason=store_result.reason,
        details=details,
        contract=store_result.contract,
    )


def _template_validation_error(artifact: Any, contract: AssuranceContract, message: str) -> ComposeArtifactResult:
    return ComposeArtifactResult(
        artifact=artifact,
        authorized_profile=contract.classification.authorized_profile.value,
        lite_candidate=contract.classification.lite_candidate,
        output_text=None,
        changed=False,
        added_section_ids=(),
        preserved_section_ids=(),
        warnings=(),
        errors=(
            MarkerConflict(
                kind="template_validation_failed",
                section_id=str(artifact),
                message=message,
            ),
        ),
    )


def _compose_artifact_view(artifact: Any, result: ComposeArtifactResult) -> ComposeArtifactView:
    return ComposeArtifactView(
        artifact=result.artifact,
        path=artifact.repo_relative_path,
        changed=result.changed,
        added_section_ids=result.added_section_ids,
        preserved_section_ids=result.preserved_section_ids,
        warnings=result.warnings,
        errors=tuple(error.message for error in result.errors),
    )


def _target_view(target: Any) -> AssuranceTargetView:
    return AssuranceTargetView(issue_id=target.issue_id, repo_relative_path=target.repo_relative_path)
