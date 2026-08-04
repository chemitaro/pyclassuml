from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING

from spec_dock_runtime.application.contracts import (
    ArtifactImportError,
    ArtifactImportRequest,
    ArtifactImportResult,
    BinaryArtifactPublishError,
    BinaryArtifactPublishRequest,
    WorkbenchSourceGuardRequest,
)
from spec_dock_runtime.application.create_artifact_doc import (
    _allocate_artifact_destination_under_create_lock,
    _format_artifact_timestamp,
    _resolve_scope_node,
)
from spec_dock_runtime.application.create_node import (
    _acquire_create_lock,
    _release_create_lock,
    _resolve_specdock_dir,
    load_graph,
)
from spec_dock_runtime.domain.ids import slugify, validate_input_slug_kebab

if TYPE_CHECKING:
    from spec_dock_runtime.application.ports import Ports


_MAX_PUBLICATION_ATTEMPTS = 100


def import_artifact(req: ArtifactImportRequest, ports: Ports) -> ArtifactImportResult:
    repo_root = _absolute_path(ports.repo_root)
    specdock_dir = _resolve_specdock_dir(ports)
    publisher = ports.binary_artifact_publisher
    source_guard = ports.workbench_source_guard
    if repo_root is None or publisher is None or source_guard is None:
        raise ArtifactImportError(code="runtime_not_configured", cleanup_state="not_created")
    if req.import_kind != "chatgpt-output":
        raise ArtifactImportError(code="unsupported_import_kind", cleanup_state="not_created")

    graph = load_graph(ports, validate=False)
    try:
        scope = _resolve_scope_node(req, graph)  # type: ignore[arg-type]
    except RuntimeError:
        raise ArtifactImportError(code="scope_invalid", cleanup_state="not_created") from None
    slug = _normalize_import_slug(req)
    source_request = WorkbenchSourceGuardRequest(
        repo_root=repo_root,
        specdock_dir=specdock_dir,
        scope_directories=tuple(
            node.path for node in graph.nodes_by_id.values() if node.kind in ("initiative", "epic", "issue")
        ),
        source_path=req.source_path,
    )
    try:
        source_guard.guard_source(source_request)
    except BinaryArtifactPublishError as error:
        raise ArtifactImportError(code=error.code, cleanup_state=error.cleanup_state) from None

    artifacts_dir = scope.path / "artifacts"
    timestamp = _format_artifact_timestamp(ports.clock.now_iso() if ports.clock is not None else None)
    try:
        lock_path, lock_token = _acquire_create_lock(specdock_dir)
    except RuntimeError:
        raise ArtifactImportError(code="create_lock_failed", cleanup_state="not_created") from None

    result: ArtifactImportResult | None = None
    body_error: ArtifactImportError | None = None
    retry_cleanup_state = "not_created"
    try:
        published = None
        destination_path = None
        artifact_id = None
        for _attempt in range(_MAX_PUBLICATION_ATTEMPTS):
            try:
                destination_path, artifact_id = _allocate_artifact_destination_under_create_lock(
                    scope=scope,
                    specdock_dir=specdock_dir,
                    artifacts_dir=artifacts_dir,
                    timestamp=timestamp,
                    artifact_type="blank",
                    slug=f"chatgpt-output-{slug}",
                )
            except RuntimeError:
                raise ArtifactImportError(
                    code="artifact_allocation_failed",
                    cleanup_state=retry_cleanup_state,
                ) from None
            try:
                published = publisher.publish(
                    BinaryArtifactPublishRequest(
                        source=source_request,
                        destination_path=destination_path,
                    )
                )
            except BinaryArtifactPublishError as error:
                retry_cleanup_state = _merge_cleanup_state(retry_cleanup_state, error.cleanup_state)
                if error.code == "destination_exists":
                    continue
                raise ArtifactImportError(
                    code=error.code,
                    cleanup_state=retry_cleanup_state,
                ) from None
            break
        else:
            raise ArtifactImportError(
                code="artifact_publication_retry_exhausted",
                cleanup_state=retry_cleanup_state,
            )

        assert published is not None
        assert destination_path is not None
        assert artifact_id is not None

        try:
            source_relative = published.source_path.relative_to(repo_root)
            destination_relative = published.destination_path.relative_to(repo_root)
        except ValueError:
            raise ArtifactImportError(code="result_path_invalid", cleanup_state=published.cleanup_state) from None
        cleanup_state = _merge_cleanup_state(retry_cleanup_state, published.cleanup_state)
        warning_codes = list(published.warning_codes)
        if cleanup_state == "retained" and "temp_cleanup_retained" not in warning_codes:
            warning_codes.append("temp_cleanup_retained")
        result = ArtifactImportResult(
            import_kind="chatgpt-output",
            storage_identity="blank",
            artifact_id=artifact_id,
            scope_id=scope.id,
            source_path=source_relative,
            destination_path=destination_relative,
            sha256=published.destination_sha256,
            byte_count=published.destination_byte_count,
            committed=published.committed,
            cleanup_state=cleanup_state,
            warning_codes=tuple(warning_codes),
        )
    except ArtifactImportError as error:
        body_error = error
    finally:
        try:
            _release_create_lock(lock_path, lock_token, specdock_dir=specdock_dir)
        except Exception as release_error:
            if body_error is None and result is not None:
                result = replace(
                    result,
                    warning_codes=(*result.warning_codes, "create_lock_release_failed"),
                )
            elif body_error is None:
                raise ArtifactImportError(code="create_lock_release_failed", cleanup_state="not_created") from None
            else:
                raise body_error from release_error
    if body_error is not None:
        raise body_error
    assert result is not None
    return result


def _normalize_import_slug(req: ArtifactImportRequest) -> str:
    title = str(req.title).strip()
    if not title:
        raise ArtifactImportError(code="title_invalid", cleanup_state="not_created")
    raw_slug = str(req.slug).strip() if req.slug is not None else slugify(title)
    if not raw_slug:
        raise ArtifactImportError(code="slug_invalid", cleanup_state="not_created")
    try:
        return validate_input_slug_kebab(raw_slug, field="--slug")
    except RuntimeError:
        raise ArtifactImportError(code="slug_invalid", cleanup_state="not_created") from None


def _absolute_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    return path if path.is_absolute() else Path.cwd() / path


def _merge_cleanup_state(first: str, second: str) -> str:
    if "retained" in (first, second):
        return "retained"
    if "removed" in (first, second):
        return "removed"
    return "not_created"
