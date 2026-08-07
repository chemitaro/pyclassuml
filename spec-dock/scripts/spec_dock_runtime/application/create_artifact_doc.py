from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
from typing import TYPE_CHECKING, Literal, Protocol

from spec_dock_runtime.application.contracts import CreateArtifactDocRequest, CreateArtifactDocResult
from spec_dock_runtime.application.create_node import (
    _acquire_create_lock,
    _prefix_for_kind,
    _release_create_lock,
    _replacements,
    _resolve_specdock_dir,
    _resolve_template_scaffolder,
    load_graph,
)
from spec_dock_runtime.domain.artifacts import (
    DIRECT_ARTIFACT_TYPES,
    ROUTING_ONLY_ARTIFACT_TYPES,
    SUPPORTED_ARTIFACT_TYPES,
    UNSUPPORTED_ARTIFACT_TYPES,
    allocate_artifact_filename_for_timestamp,
    artifact_id_from_path,
    is_ambiguous_blank_artifact_slug,
    scan_artifact_duplicate_state,
)
from spec_dock_runtime.domain.ids import resolve_id_input, slugify, validate_input_slug_kebab

if TYPE_CHECKING:
    from pathlib import Path

    from spec_dock_runtime.application.ports import Ports
    from spec_dock_runtime.domain.models import SpecGraph, SpecNode


@dataclass(frozen=True)
class ArtifactSetupTarget:
    path: Path
    artifacts_dir: Path
    rules_kind: str


class _AssuranceStoreLike(Protocol):
    def resolve_issue_target(self, issue: str | None = None): ...

    def verify_contract(self, target): ...


class _ArtifactStoreLike(Protocol):
    def load_profile_artifact_template_text(
        self,
        artifact: Literal["design", "plan"],
        profile: Literal["lite", "standard", "strict", "critical"],
    ) -> str: ...


_DRAFT_PROFILE_ARTIFACT_BY_TYPE: dict[str, Literal["design", "plan"]] = {
    "draft-design": "design",
    "draft-plan": "plan",
}


def create_artifact_doc(
    req: CreateArtifactDocRequest,
    ports: Ports,
    *,
    assurance_store: _AssuranceStoreLike | None = None,
    artifact_store: _ArtifactStoreLike | None = None,
) -> CreateArtifactDocResult:
    template_scaffolder = _resolve_template_scaffolder(ports)
    specdock_dir = _resolve_specdock_dir(ports)
    graph = load_graph(ports, validate=False)

    artifact_type, title, slug = _normalize_artifact_inputs(req)
    scope = _resolve_scope_node(req, graph)
    artifacts_dir = scope.path / "artifacts"
    timestamp = _format_artifact_timestamp(ports.clock.now_iso() if ports.clock is not None else None)
    template_path, template_text = _resolve_artifact_template_text(
        artifact_type=artifact_type,
        scope=scope,
        specdock_dir=specdock_dir,
        assurance_store=assurance_store,
        artifact_store=artifact_store,
    )
    del template_path

    lock_path, lock_token = _acquire_create_lock(specdock_dir)
    result: CreateArtifactDocResult | None = None
    body_error: Exception | None = None
    try:
        dest_path, artifact_id = _allocate_artifact_destination_under_create_lock(
            scope=scope,
            specdock_dir=specdock_dir,
            artifacts_dir=artifacts_dir,
            timestamp=timestamp,
            artifact_type=artifact_type,
            slug=slug,
        )
        rendered_text = template_scaffolder.render_text(
            template_text,
            _artifact_replacements(
                scope=scope,
                artifact_id=artifact_id,
                artifact_type=artifact_type,
                title=title,
            ),
        )
        template_scaffolder.write_text(dest_path, rendered_text)
        written_artifact_id = artifact_id_from_path(dest_path)
        duplicate_error, artifact_ids = scan_artifact_duplicate_state(artifacts_dir)
        if duplicate_error is not None:
            raise RuntimeError(f"post-write duplicate guard failed: {duplicate_error}")
        if written_artifact_id not in artifact_ids:
            raise RuntimeError(
                f"post-write duplicate guard failed: created artifact id not found: {written_artifact_id}"
            )
        result = CreateArtifactDocResult(
            artifact_id=written_artifact_id,
            artifact_type=artifact_type,
            scope_node_id=scope.id,
            path=dest_path,
            warnings=[],
        )
    except Exception as exc:
        body_error = exc
    finally:
        try:
            _release_create_lock(lock_path, lock_token, specdock_dir=specdock_dir)
        except Exception as release_exc:
            if body_error is None:
                raise
            raise body_error from release_exc
    if body_error is not None:
        raise body_error
    assert result is not None
    return result


def _allocate_artifact_destination_under_create_lock(
    *,
    scope: SpecNode,
    specdock_dir: Path,
    artifacts_dir: Path,
    timestamp: str,
    artifact_type: str,
    slug: str,
) -> tuple[Path, str]:
    _ensure_artifacts_setup(scope=scope, specdock_dir=specdock_dir, artifacts_dir=artifacts_dir)
    duplicate_error, _artifact_ids = scan_artifact_duplicate_state(artifacts_dir)
    if duplicate_error is not None:
        raise RuntimeError(duplicate_error)
    dest_path, artifact_id = allocate_artifact_filename_for_timestamp(
        artifacts_dir,
        timestamp=timestamp,
        artifact_type=artifact_type,
        slug=slug,
    )
    if os.path.lexists(dest_path):
        raise RuntimeError(f"Artifact already exists: {dest_path}")
    return dest_path, artifact_id


def _normalize_artifact_inputs(req: CreateArtifactDocRequest) -> tuple[str, str, str]:
    artifact_type = str(req.artifact_type).strip().lower()
    if artifact_type in UNSUPPORTED_ARTIFACT_TYPES:
        raise RuntimeError(f"Unsupported artifact type: {artifact_type}")
    if artifact_type not in SUPPORTED_ARTIFACT_TYPES:
        allowed = ", ".join((*DIRECT_ARTIFACT_TYPES, *ROUTING_ONLY_ARTIFACT_TYPES))
        raise RuntimeError(f"Unknown artifact type: {artifact_type} (allowed: {allowed})")

    title = str(req.title).strip()
    if not title:
        raise RuntimeError("--title is required")
    slug = str(req.slug).strip() if req.slug is not None else slugify(title)
    if not slug:
        raise RuntimeError("Failed to derive slug from title. Pass --slug explicitly.")
    normalized_slug = validate_input_slug_kebab(slug, field="--slug")
    if artifact_type == "blank" and is_ambiguous_blank_artifact_slug(normalized_slug):
        raise RuntimeError(
            "Ambiguous blank artifact slug: "
            f"{normalized_slug}. "
            "Blank artifact slugs must not start with a supported artifact type prefix."
        )
    return artifact_type, title, normalized_slug


def _resolve_scope_node(req: CreateArtifactDocRequest, graph: SpecGraph) -> SpecNode:
    scope_node_id = req.scope_node_id
    if req.scope_kind is not None:
        scope_prefix = _prefix_for_kind(req.scope_kind)
        scope_node_id = resolve_id_input(
            req.scope_node_id,
            prefix=scope_prefix,
            field=f"--{req.scope_kind}",
            nodes=graph.nodes_by_id,
        )
    scope = graph.nodes_by_id.get(scope_node_id)
    if scope is None:
        raise RuntimeError(f"Scope node not found: {scope_node_id}")
    if req.scope_kind is not None and scope.kind != req.scope_kind:
        raise RuntimeError(f"Scope kind mismatch: expected {req.scope_kind}, got {scope.kind}")
    if scope.kind not in ("initiative", "epic", "issue"):
        raise RuntimeError(f"Unsupported scope kind for artifact docs: {scope.kind}")
    return scope


def _format_artifact_timestamp(now_iso: str | None = None) -> str:
    if now_iso is None:
        dt = datetime.now(timezone.utc)
    else:
        normalized = now_iso.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y%m%dt%H%M%S") + "z"


def _format_artifact_date_from_id(artifact_id: str) -> str:
    timestamp = artifact_id.split("-", 1)[0]
    return datetime.strptime(timestamp, "%Y%m%dt%H%M%Sz").date().isoformat()


def _resolve_artifact_template_text(
    *,
    artifact_type: str,
    scope: SpecNode,
    specdock_dir: Path,
    assurance_store: _AssuranceStoreLike | None,
    artifact_store: _ArtifactStoreLike | None,
) -> tuple[Path, str]:
    if artifact_type.startswith("draft-") and scope.kind != "issue":
        raise RuntimeError(f"{artifact_type} artifacts are supported only for issue scope")
    if artifact_type == "draft-requirement":
        path = specdock_dir / "templates" / "issue" / "requirement.md"
        return path, _load_required_template_text(path, label=f"issue {artifact_type}")
    profile_artifact = _DRAFT_PROFILE_ARTIFACT_BY_TYPE.get(artifact_type)
    if profile_artifact is not None:
        if assurance_store is None:
            raise RuntimeError(f"assurance_store is required for issue {artifact_type}")
        if artifact_store is None:
            raise RuntimeError(f"artifact_store is required for issue {artifact_type}")
        target = assurance_store.resolve_issue_target(scope.id)
        store_result = assurance_store.verify_contract(target)
        if store_result.status != "valid" or store_result.contract is None:
            details = "; ".join(getattr(store_result, "details", ()) or ())
            suffix = f" details={details}" if details else ""
            raise RuntimeError(
                f"Valid assurance contract is required before creating issue {artifact_type}: "
                f"reason={store_result.reason}{suffix}"
            )
        profile = store_result.contract.classification.authorized_profile.value
        text = artifact_store.load_profile_artifact_template_text(profile_artifact, profile)
        return specdock_dir / "templates" / "issue-profiles" / profile / f"{profile_artifact}.md", text
    path = specdock_dir / "templates" / "artifacts" / f"{artifact_type}.md"
    return path, _load_required_template_text(path, label=f"artifact {artifact_type}")


def _load_required_template_text(path: Path, *, label: str) -> str:
    if path.is_symlink():
        raise RuntimeError(f"Template is symlinked: {path}")
    if path.exists() and not path.is_file():
        raise RuntimeError(f"Template is not a file: {path}")
    if not path.is_file():
        raise RuntimeError(f"Missing template source for {label}: {path}")
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise RuntimeError(f"Template is empty: {path}")
    return text


def _preflight_artifacts_dir(artifacts_dir: Path) -> None:
    if os.path.lexists(artifacts_dir) and (artifacts_dir.is_symlink() or not artifacts_dir.is_dir()):
        raise RuntimeError(f"Destination already exists: {artifacts_dir}")
    parent = artifacts_dir.parent
    if parent.is_symlink() or not parent.is_dir():
        raise RuntimeError(f"Destination already exists: {parent}")


def _rules_source_path(*, scope: SpecNode, specdock_dir: Path) -> Path:
    return specdock_dir / "docs" / "rules" / scope.kind / "artifacts.md"


def _preflight_artifacts_rules(*, scope: SpecNode, specdock_dir: Path, artifacts_dir: Path) -> None:
    source = _rules_source_path(scope=scope, specdock_dir=specdock_dir)
    if source.is_symlink():
        raise RuntimeError(f"Missing rules source: {source}")
    if not source.is_file():
        raise RuntimeError(f"Missing rules source: {source}")
    link_path = artifacts_dir / "rules.md"
    if not os.path.lexists(link_path):
        return
    if not link_path.is_symlink():
        raise RuntimeError(f"Destination already exists: {link_path}")
    if not link_path.exists():
        raise RuntimeError(f"Broken artifact rules symlink: {link_path}")
    if link_path.resolve() != source.resolve():
        raise RuntimeError(f"Artifact rules symlink points to wrong target: {link_path}")


def _ensure_artifacts_setup(*, scope: SpecNode, specdock_dir: Path, artifacts_dir: Path) -> None:
    _ensure_artifacts_setup_for_target(
        target=ArtifactSetupTarget(
            path=scope.path,
            artifacts_dir=artifacts_dir,
            rules_kind=scope.kind,
        ),
        specdock_dir=specdock_dir,
    )


def _ensure_artifacts_setup_for_target(*, target: ArtifactSetupTarget, specdock_dir: Path) -> None:
    _preflight_artifacts_setup_for_target(target=target, specdock_dir=specdock_dir)
    source = specdock_dir / "docs" / "rules" / target.rules_kind / "artifacts.md"
    link_path = target.artifacts_dir / "rules.md"
    target.artifacts_dir.mkdir(parents=True, exist_ok=True)
    if not os.path.lexists(link_path):
        link_path.symlink_to(os.path.relpath(source, start=target.artifacts_dir))


def _preflight_artifacts_setup_for_target(*, target: ArtifactSetupTarget, specdock_dir: Path) -> None:
    _preflight_artifacts_dir(target.artifacts_dir)
    source = specdock_dir / "docs" / "rules" / target.rules_kind / "artifacts.md"
    if source.is_symlink() or not source.is_file():
        raise RuntimeError(f"Missing rules source: {source}")
    link_path = target.artifacts_dir / "rules.md"
    if os.path.lexists(link_path):
        if not link_path.is_symlink():
            raise RuntimeError(f"Destination already exists: {link_path}")
        if not link_path.exists():
            raise RuntimeError(f"Broken artifact rules symlink: {link_path}")
        if link_path.resolve() != source.resolve():
            raise RuntimeError(f"Artifact rules symlink points to wrong target: {link_path}")


def _artifact_replacements(
    *,
    scope: SpecNode,
    artifact_id: str,
    artifact_type: str,
    title: str,
) -> dict[str, str]:
    today = _format_artifact_date_from_id(artifact_id)
    replacements = _replacements(
        kind=scope.kind,
        node_id=scope.id,
        title=scope.title,
        parent_id=scope.parent_id,
        initiative_id=scope.initiative_id,
        github_issue_number=scope.github_issue_number,
        today=today,
    )
    replacements.update({
        "<ARTIFACT_ID>": artifact_id,
        "<ARTIFACT_TITLE>": title,
        "<ADR_ID>": artifact_id,
        "<ADR_TITLE>": title,
        "<DISC_ID>": artifact_id,
        "<DISC_TITLE>": title,
        "<RESEARCH_ID>": artifact_id,
        "<RESEARCH_TITLE>": title,
        "<INTERVIEW_ID>": artifact_id,
        "<INTERVIEW_TITLE>": title,
        "<DECISION_CANDIDATE_ID>": artifact_id,
        "<DECISION_CANDIDATE_TITLE>": title,
        "<PR_REPAIR_BATCH_ID>": artifact_id,
        "<PR_REPAIR_BATCH_TITLE>": title,
        "<SCOPE_ID>": scope.id,
        "<YOUR_NAME>": os.environ.get("USER", "<YOUR_NAME>"),
        "YYYY-MM-DD": today,
    })
    if artifact_type.startswith("draft-"):
        replacements["<SCOPE_ID>"] = scope.id
    return replacements
