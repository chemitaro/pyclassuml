from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from datetime import datetime
    from pathlib import Path

    from spec_dock_runtime.application.contracts import (
        ArtifactWriteResult,
        BinaryArtifactPublishRequest,
        BinaryArtifactPublishResult,
        BootstrapResult,
        ExplicitFileArtifactPublishRequest,
        ExplicitFileArtifactPublishResult,
        ExplicitFileSourcePreflightRequest,
        GitHubCapabilityDiagnostic,
        GitHubCapabilityProbeRequest,
        GitWorktreeRecord,
        GuardedExplicitFileSource,
        GuardedWorkbenchSource,
        SyncCommandResult,
        SyncRequest,
        WorkbenchSourceGuardRequest,
    )
    from spec_dock_runtime.domain.issue_planning_candidate import CandidateMaterial, ValidatedIssueAuthoringPayload
    from spec_dock_runtime.domain.issue_planning_contracts import (
        IssueCandidateIdentity,
        OnboardingCompanionBindingV1,
        ReviewedPlanningIdentity,
    )
    from spec_dock_runtime.domain.models import IssueSnapshot, SpecGraph
    from spec_dock_runtime.infra.contracts import (
        ActiveManifest,
        ActiveManifestLoadResult,
        ActiveStateSnapshot,
        DepsTopologyLoadResult,
        DirectDependencyResolution,
        StoredMetaRecord,
    )
    from spec_dock_runtime.presentation.contracts import ArtifactBundle


class ValidateNodeReader(Protocol):
    def load_node_records(self) -> list[StoredMetaRecord]: ...


class DerivedStateReader(Protocol):
    def load_cached_issue_status_by_id(self, specdock_dir: Path) -> dict[str, str]: ...


class NodeRepository(Protocol):
    def load_node_records(self, specdock_dir: Path) -> list[StoredMetaRecord]: ...

    def write_meta(self, dest_dir: Path, record: StoredMetaRecord) -> None: ...

    def add_issue_dependency(self, meta_path: Path, to_id: str) -> None: ...

    def remove_issue_dependency(
        self, meta_path: Path, to_id: str, *, matching_refs: list[object] | None = None
    ) -> None: ...

    def delete_tree(self, node_path: Path) -> None: ...


class TemplateScaffolder(Protocol):
    def render_text(self, text: str, replacements: dict[str, str]) -> str: ...

    def load_template_text(self, src_path: Path) -> str: ...

    def copy_scaffolded_tree(self, src_dir: Path, dest_dir: Path, replacements: dict[str, str]) -> list[Path]: ...

    def write_text(self, dest_path: Path, text: str) -> None: ...


class IssueGateway(Protocol):
    def issue_index(self, repo_root: Path, *, limit: int) -> list[IssueSnapshot]: ...

    def issue_create(self, repo_root: Path, title: str, body: str) -> int: ...

    def issue_view_minimal(
        self,
        repo_root: Path,
        issue_number: int,
        *,
        repo_slug: str | None = None,
    ) -> IssueSnapshot: ...

    def issue_view_snapshot(
        self,
        repo_root: Path,
        issue_number: int,
        *,
        repo_slug: str | None = None,
    ) -> IssueSnapshot: ...

    def issue_close(
        self,
        repo_root: Path,
        issue_number: int,
        *,
        repo_slug: str | None = None,
    ) -> IssueSnapshot: ...


class ActiveStateStore(Protocol):
    def load_active_manifest(self, specdock_dir: Path) -> ActiveManifestLoadResult: ...

    def load_active_manifest_no_migrate(self, specdock_dir: Path) -> ActiveManifestLoadResult: ...

    def load_active_issue_id(self, specdock_dir: Path) -> str | None: ...

    def write_active_manifest(self, specdock_dir: Path, manifest: ActiveManifest) -> ActiveManifest: ...

    def apply_active_pointers(
        self, specdock_dir: Path, manifest: ActiveManifest | None, rendered_context_pack: str
    ) -> None: ...

    def patch_agent_state_active_fields(self, specdock_dir: Path, manifest: ActiveManifest | None) -> None: ...

    def snapshot_current_state(self, specdock_dir: Path) -> ActiveStateSnapshot: ...

    def restore_previous_state(self, specdock_dir: Path, snapshot: ActiveStateSnapshot) -> None: ...


class DepsTopologyReader(Protocol):
    def load_issue_depends_on_map(self, specdock_dir: Path, graph: SpecGraph) -> DepsTopologyLoadResult: ...

    def load_direct_dependency_resolutions(
        self,
        specdock_dir: Path,
        graph: SpecGraph,
        src_id: str,
    ) -> list[DirectDependencyResolution]: ...

    def load_node_dependency_resolutions(
        self,
        specdock_dir: Path,
        graph: SpecGraph,
    ) -> dict[str, list[DirectDependencyResolution]]: ...

    def build_candidate_issue_depends_on_map(
        self,
        graph: SpecGraph,
        issue_depends_on_map: dict[str, list[str]],
        *,
        from_node_id: str,
        to_node_id: str,
    ) -> dict[str, list[str]]: ...


class GitGateway(Protocol):
    def require_clean_working_tree(self, repo_root: Path) -> None: ...

    def current_branch_or_none(self, repo_root: Path) -> str | None: ...

    def local_branch_exists(self, repo_root: Path, branch: str) -> bool: ...

    def checkout_branch(self, repo_root: Path, branch: str) -> None: ...

    def create_and_checkout_branch(self, repo_root: Path, branch: str) -> None: ...

    def check_ref_format_branch(self, repo_root: Path, branch: str) -> bool: ...

    def origin_github_repo_slug(self, repo_root: Path) -> str | None: ...

    def worktree_list(self, repo_root: Path) -> list[GitWorktreeRecord]: ...

    def add_worktree_with_new_branch(self, repo_root: Path, *, path: Path, branch: str) -> None: ...

    def remove_worktree(self, repo_root: Path, *, path: Path, force: bool) -> None: ...


class GitHubCapabilityGateway(Protocol):
    def probe(self, request: GitHubCapabilityProbeRequest) -> list[GitHubCapabilityDiagnostic]: ...


class BootstrapGateway(Protocol):
    def run_make_init_if_available(self, worktree_path: Path) -> BootstrapResult: ...


class FilesystemGateway(Protocol):
    def path_exists(self, path: Path) -> bool: ...

    def remove_target(self, path: Path) -> None: ...

    def path_kind(self, path: Path) -> str: ...

    def guard_workbench_ancestry(self, root: Path, endpoint: Path, *, allow_missing_leaf: bool = False) -> None: ...

    def guard_workbench_inventory(self, specdock_dir: Path) -> None: ...

    def copy_workbench(self, source: Path, destination: Path) -> None: ...


class WorkbenchSourceGuard(Protocol):
    def guard_source(self, request: WorkbenchSourceGuardRequest) -> GuardedWorkbenchSource: ...


class BinaryArtifactPublisher(Protocol):
    def publish(self, request: BinaryArtifactPublishRequest) -> BinaryArtifactPublishResult: ...


class ExplicitFileSourceGuard(Protocol):
    def guard_explicit_file_source(
        self,
        request: ExplicitFileSourcePreflightRequest,
    ) -> GuardedExplicitFileSource: ...


class ExplicitFileArtifactPublisher(Protocol):
    def publish_explicit_file(
        self,
        request: ExplicitFileArtifactPublishRequest,
    ) -> ExplicitFileArtifactPublishResult: ...


class EnvironmentGateway(Protocol):
    def getenv(self, name: str) -> str | None: ...


class ArtifactWriter(Protocol):
    def write(self, specdock_dir: Path, bundle: ArtifactBundle) -> ArtifactWriteResult: ...


class JsonStore(Protocol):
    def load_json(self, path: Path) -> object: ...

    def write_json(self, path: Path, data: object) -> None: ...


class Clock(Protocol):
    def now_iso(self) -> str: ...

    def today(self) -> str: ...


class VerifiedIssueCandidateView(Protocol):
    identity: IssueCandidateIdentity
    files: Mapping[str, bytes]
    source_baseline: Mapping[str, object]
    zip_bytes: bytes
    onboarding_companion: OnboardingCompanionBindingV1


class PublishedCandidateView(Protocol):
    identity: IssueCandidateIdentity
    zip_byte_count: int
    candidate_path: Path
    onboarding_companion: OnboardingCompanionBindingV1


class PublishedPlanningReviewView(Protocol):
    review_result_file: str
    review_summary_file: str
    review_result_sha256: str


class ExpectedPlanningTargetsView(Protocol):
    documents: Mapping[str, bytes]
    blob_oids: Mapping[str, str]


class PlanningApplyOperationView(Protocol):
    operation_id: str


class PlanningApplyExecutionView(Protocol):
    status: str
    reason: str
    details: tuple[str, ...]

    def to_output(self) -> dict[str, object]: ...


class IssuePlanningCandidateOutputGuard(Protocol):
    """Opaque token returned by the Issue Planning output guard."""


class IssuePlanningCandidateArchiveRejected(ValueError):
    def __init__(self, findings: tuple[str, ...]) -> None:
        super().__init__("Issue Candidate archive validation failed")
        self.findings = findings


class IssuePlanningCandidateBuildFailed(OSError):
    pass


class IssuePlanningCandidateCollision(FileExistsError):
    pass


class IssuePlanningCandidateOutputRejected(ValueError):
    pass


class IssuePlanningCandidatePublicationFailed(OSError):
    pass


class IssuePlanningApplyOutputRejected(ValueError):
    pass


class IssuePlanningGateway(Protocol):
    def validate_candidate_output_directory(
        self,
        output_dir: Path,
        repo_root: Path,
    ) -> IssuePlanningCandidateOutputGuard: ...

    def load_verified_issue_candidate(
        self,
        candidate_path: Path,
        repo_root: Path,
    ) -> VerifiedIssueCandidateView: ...

    def load_validated_issue_authoring_payload(
        self,
        snapshot: object,
        *,
        expected_companion_path: str,
        repo_root: Path,
    ) -> ValidatedIssueAuthoringPayload: ...

    def build_and_publish_candidate(
        self,
        *,
        output_guard: IssuePlanningCandidateOutputGuard,
        repo_root: Path,
        material: CandidateMaterial,
        publication_guard: Callable[[], bool],
    ) -> PublishedCandidateView: ...

    def open_safe_directory_descriptor(self, path: Path) -> int: ...

    def read_bounded_regular_file(self, path: Path, *, max_bytes: int) -> bytes: ...

    def read_bounded_regular_file_at(
        self,
        root_descriptor: int,
        relative_path: str,
        *,
        max_bytes: int,
    ) -> bytes: ...

    def read_external_review_result(
        self,
        path: Path,
        *,
        repo_root: Path,
        expected_sha256: str,
    ) -> bytes: ...

    def publish_planning_review_evidence(
        self,
        *,
        output_dir: Path,
        repo_root: Path,
        reviewed_identity_sha256: str,
        review_result_bytes: bytes,
        summary_bytes: bytes,
        operation_time: datetime,
        publication_guard: Callable[[], bool],
    ) -> PublishedPlanningReviewView: ...

    def load_expected_planning_targets(
        self,
        repo_root: Path,
        expected_head: str,
        canonical_target_paths: tuple[str, str, str],
    ) -> ExpectedPlanningTargetsView: ...

    def planning_apply_resume_available(
        self,
        operation: PlanningApplyOperationView,
        *,
        output_guard: IssuePlanningCandidateOutputGuard,
    ) -> bool: ...

    def create_planning_apply_operation(
        self,
        *,
        issue_id: str,
        mode: Literal["archive-candidate", "git-bound"],
        repository: str,
        branch: str,
        expected_head: str,
        reviewed_identity: ReviewedPlanningIdentity,
        reviewed_identity_sha256: str,
        review_result_sha256: str,
        human_decision_sha256: str,
        decision: Literal["approved", "rejected"],
        canonical_target_paths: tuple[str, str, str],
        pre_apply_target_blob_oids: Mapping[str, str],
        candidate_identity: IssueCandidateIdentity | None,
        git_bound_operation_binding_sha256: str | None,
        companion_target_path: str | None,
        companion_sha256: str | None,
        decision_artifact_path: str,
        human_decision_bytes: bytes,
        replacement_documents: Mapping[str, bytes],
        replacement_companion: bytes | None,
        pre_apply_document_bytes: Mapping[str, bytes],
    ) -> PlanningApplyOperationView: ...


@dataclass(frozen=True)
class IssuePlanningDependencies:
    clock: Clock
    gateway: IssuePlanningGateway


class SyncLegacyRunner(Protocol):
    def run_sync(
        self,
        req: SyncRequest,
        *,
        active_manifest_mode: Literal["migrate", "no_migrate"] = "migrate",
    ) -> SyncCommandResult: ...


@dataclass(frozen=True)
class Ports:
    node_reader: ValidateNodeReader
    repo_root: Path | None
    specdock_dir: Path | None = None
    node_repo: NodeRepository | None = None
    template_scaffolder: TemplateScaffolder | None = None
    derived_state_reader: DerivedStateReader | None = None
    issue_gateway: IssueGateway | None = None
    active_state_store: ActiveStateStore | None = None
    deps_topology_reader: DepsTopologyReader | None = None
    git_gateway: GitGateway | None = None
    github_capability_gateway: GitHubCapabilityGateway | None = None
    json_store: JsonStore | None = None
    clock: Clock | None = None
    artifact_writer: ArtifactWriter | None = None
    sync_legacy_runner: SyncLegacyRunner | None = None
    bootstrap_gateway: BootstrapGateway | None = None
    environment_gateway: EnvironmentGateway | None = None
    filesystem_gateway: FilesystemGateway | None = None
    workbench_source_guard: WorkbenchSourceGuard | None = None
    binary_artifact_publisher: BinaryArtifactPublisher | None = None
    issue_planning: IssuePlanningDependencies | None = None
    explicit_file_source_guard: ExplicitFileSourceGuard | None = None
    explicit_file_artifact_publisher: ExplicitFileArtifactPublisher | None = None
