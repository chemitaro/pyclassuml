from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
import os
from typing import TYPE_CHECKING, Literal

from spec_dock_runtime.domain.models import SpecNode  # noqa: TC001 - runtime re-export used by CLI/runtime callers.

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from spec_dock_runtime.application.issue_planning import (
        PlanningApplyRequest,
        PlanningCreateRequest,
        PlanningReviewRequest,
        PlanningReviseRequest,
    )
    from spec_dock_runtime.domain.assurance import AssuranceContract
    from spec_dock_runtime.domain.issue_planning_contracts import PlanningCommandResult
    from spec_dock_runtime.domain.models import (
        ActiveSelection,
        BranchDecision,
        DepsDependencyContext,
        DepsEvaluation,
        DepsHighLevelStatus,
        DepsState,
        IssueSnapshot,
        IssueStatusSnapshot,
        ProgressMap,
        SpecGraph,
        TargetDepsInspection,
        ValidationReport,
    )
    from spec_dock_runtime.domain.runbook import Runbook, WorkflowTarget
    from spec_dock_runtime.domain.workflow_state import WorkflowState
    from spec_dock_runtime.infra.contracts import StoredMetaRecord

POST_MUTATION_FATAL_WARNING_CODES: tuple[str, ...] = ("gh_fetch_failed",)
BootstrapStatus = Literal["skipped", "succeeded", "failed", "detection_failed"]
WorktreeClassificationReason = Literal[
    "root_valid",
    "root_missing",
    "root_blank",
    "root_invalid",
    "namespace_symlink",
]
WorktreeOrigin = Literal["spec_dock_managed", "external", "classification_unavailable"]
WORKTREE_CLASSIFICATION_REASONS: tuple[WorktreeClassificationReason, ...] = (
    "root_valid",
    "root_missing",
    "root_blank",
    "root_invalid",
    "namespace_symlink",
)
WORKTREE_ORIGINS: tuple[WorktreeOrigin, ...] = (
    "spec_dock_managed",
    "external",
    "classification_unavailable",
)


@dataclass(frozen=True)
class ValidateTreeRequest:
    pass


@dataclass(frozen=True)
class ValidationResult:
    report: ValidationReport
    checked_node_count: int


AssuranceOperation = Literal["show", "classify", "verify", "compose"]
AssuranceResultStatus = Literal["valid", "missing", "invalid", "applied", "unchanged", "dry-run"]
ComposeArtifactSelection = Literal["design", "plan", "report", "all"]


@dataclass(frozen=True)
class ShowAssuranceRequest:
    issue: str | Path | None = None


@dataclass(frozen=True)
class ClassifyAssuranceRequest:
    stage: Literal["requirement"]
    issue: str | Path | None = None
    dry_run: bool = False


@dataclass(frozen=True)
class VerifyAssuranceRequest:
    issue: str | Path | None = None


@dataclass(frozen=True)
class ComposeAssuranceRequest:
    artifact: ComposeArtifactSelection
    issue: str | Path | None = None
    dry_run: bool = False


@dataclass(frozen=True)
class AssuranceTargetView:
    issue_id: str
    repo_relative_path: str


@dataclass(frozen=True)
class ComposeArtifactView:
    artifact: str
    path: str
    changed: bool
    added_section_ids: tuple[str, ...] = ()
    preserved_section_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class AssuranceResult:
    operation: AssuranceOperation
    ok: bool
    status: AssuranceResultStatus
    target: AssuranceTargetView
    mode: str
    reason: str
    details: tuple[str, ...]
    contract: AssuranceContract | None
    dry_run: bool = False
    written_path: Path | None = None
    authorized_profile: str | None = None
    lite_candidate: bool | None = None
    changed_paths: tuple[str, ...] = ()
    artifacts: tuple[ComposeArtifactView, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def has_contract(self) -> bool:
        return self.contract is not None


@dataclass(frozen=True)
class WorkflowStatusRequest:
    pass


@dataclass(frozen=True)
class WorkflowNextRequest:
    workflow_target: WorkflowTarget


@dataclass(frozen=True)
class RunbookProjectionResult:
    written: bool
    paths: tuple[str, ...]
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkflowResult:
    operation: Literal["status", "next"]
    state: WorkflowState
    runbook: Runbook | None = None
    projection: RunbookProjectionResult | None = None


@dataclass(frozen=True)
class DoctorRequest:
    github_repo: str | None = None
    github_pr: int | None = None
    github_head_sha: str | None = None
    github_extended: bool = False


GitHubCapability = Literal[
    "repo_metadata_read",
    "pull_request_read",
    "check_runs_read",
    "commit_statuses_read",
    "status_check_rollup_read",
    "actions_read",
    "issue_comments_read",
    "pull_reviews_read",
    "pull_review_comments_read",
    "pull_review_threads_read",
    "trigger_comment_write",
]
GitHubCapabilityStatus = Literal[
    "ok",
    "permission_denied",
    "auth_missing",
    "rate_limited",
    "target_unavailable",
    "transient_unknown",
    "schema_unavailable",
    "skipped",
]
GitHubCapabilityTokenSource = Literal["GH_TOKEN", "GITHUB_TOKEN", "gh_saved_auth", "unknown"]
GitHubCapabilitySeverity = Literal["info", "warning", "blocking"]
GitHubCapabilityGroup = Literal["core", "extended"]
GitHubCapabilityDiagnosticCode = Literal[
    "github_capability_ok",
    "github_token_permission_denied",
    "github_auth_missing",
    "github_rate_limited",
    "github_target_unavailable",
    "github_transient_unknown",
    "github_schema_unavailable",
    "github_capability_skipped",
]


@dataclass(frozen=True)
class GitHubCapabilityProbeRequest:
    github_repo: str
    github_pr: int
    github_head_sha: str
    include_extended: bool = False


@dataclass(frozen=True)
class GitHubCapabilityDiagnostic:
    code: GitHubCapabilityDiagnosticCode
    capability: GitHubCapability
    status: GitHubCapabilityStatus
    token_source: GitHubCapabilityTokenSource
    api: str
    severity: GitHubCapabilitySeverity
    message: str
    recommended_next_action: str
    secret_redacted: bool
    stderr_sha256: str | None
    group: GitHubCapabilityGroup


@dataclass(frozen=True)
class DoctorFinding:
    code: Literal[
        "duplicate_id",
        "duplicate_seq",
        "missing_artifact",
        "broken_meta",
        "stale_active_pointer",
        "stale_create_lock",
        "legacy_only_workspace",
        "validation_error",
    ]
    message: str
    guidance: list[str]


@dataclass(frozen=True)
class DoctorResult:
    ok: bool
    findings: list[DoctorFinding]
    warnings: list[str]
    github_capability_diagnostics: list[GitHubCapabilityDiagnostic] = field(default_factory=list)


@dataclass(frozen=True)
class GitWorktreeRecord:
    path: Path
    head: str | None
    branch: str | None
    detached: bool = False
    bare: bool = False
    locked: bool = False


@dataclass(frozen=True)
class BootstrapResult:
    status: BootstrapStatus
    command: str | None
    exit_code: int | None
    warnings: list[str]


@dataclass(frozen=True)
class WorktreeCreateRequest:
    label: str | None = None


@dataclass(frozen=True)
class WorktreeCreateResult:
    id: str
    main_worktree_path: Path
    container_path: Path
    worktree_path: Path
    branch_name: str
    bootstrap_status: BootstrapStatus
    bootstrap_command: str | None
    bootstrap_exit_code: int | None
    warnings: list[str]


@dataclass(frozen=True)
class WorktreeListRequest:
    pass


@dataclass(frozen=True)
class WorktreeShowRequest:
    target: str


@dataclass(frozen=True)
class WorktreeRemoveRequest:
    target: str
    force: bool = False


@dataclass(frozen=True)
class WorktreeRecordView:
    id: str
    path: Path
    basename: str
    branch: str | None
    head: str | None
    managed: bool
    main: bool
    current: bool
    path_exists: bool
    record_exists: bool
    removable: bool
    remove_blockers: list[str]
    managed_classification_available: bool = True
    classification_reason: WorktreeClassificationReason = "root_valid"
    origin: WorktreeOrigin | str = ""

    def __post_init__(self) -> None:
        if self.classification_reason not in WORKTREE_CLASSIFICATION_REASONS:
            raise ValueError(f"unsupported worktree classification reason: {self.classification_reason}")
        origin = self.origin
        if not origin:
            if not self.managed_classification_available:
                origin = "classification_unavailable"
            else:
                origin = "spec_dock_managed" if self.managed else "external"
            object.__setattr__(self, "origin", origin)
        if origin not in WORKTREE_ORIGINS:
            raise ValueError(f"unsupported worktree origin: {origin}")


@dataclass(frozen=True)
class WorktreeListResult:
    worktrees: list[WorktreeRecordView]
    warnings: list[str]


@dataclass(frozen=True)
class WorktreeShowResult:
    target: str
    worktree: WorktreeRecordView
    warnings: list[str]


@dataclass(frozen=True)
class WorktreeRemoveResult:
    target: str
    resolved_target: WorktreeRecordView
    removed_record: bool
    removed_directory: bool
    branch_deleted: bool
    warnings: list[str]


class WorktreeCommandError(RuntimeError):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        command: str,
        target: str | None = None,
        candidates: list[WorktreeRecordView] | None = None,
        worktree: WorktreeRecordView | None = None,
        remove_blockers: list[str] | None = None,
        git_error: str | None = None,
        removed_record: bool | None = None,
        removed_directory: bool | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.command = command
        self.target = target
        self.candidates = list(candidates or [])
        self.worktree = worktree
        self.remove_blockers = list(remove_blockers or [])
        self.git_error = git_error
        self.removed_record = removed_record
        self.removed_directory = removed_directory
        self.warnings = list(warnings or [])
        super().__init__(message)


@dataclass(frozen=True)
class WorkbenchCopyRequest:
    scope_id: str
    target: str


class WorkbenchCopyError(RuntimeError):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        side: str | None = None,
        mutation_started: bool = False,
    ) -> None:
        self.code = code
        self.side = side
        self.mutation_started = mutation_started
        super().__init__(message)


class WorkbenchFilesystemError(RuntimeError):
    """Content-free filesystem failure with honest mutation-boundary state."""

    def __init__(self, *, mutation_started: bool) -> None:
        self.mutation_started = mutation_started
        super().__init__("workbench filesystem operation failed")


BinaryArtifactCleanupState = Literal["not_created", "removed", "retained"]
BinaryArtifactPublishWarning = Literal[
    "create_lock_release_failed",
    "directory_fsync_failed",
    "destination_mismatch",
    "destination_read_failed",
    "temp_cleanup_retained",
]


@dataclass(frozen=True)
class WorkbenchSourceGuardRequest:
    repo_root: Path
    specdock_dir: Path
    scope_directories: tuple[Path, ...]
    source_path: Path


@dataclass(frozen=True)
class GuardedWorkbenchSource:
    source_path: Path
    workbench_root: Path
    device: int
    inode: int
    mode: int


@dataclass(frozen=True)
class BinaryArtifactPublishRequest:
    source: WorkbenchSourceGuardRequest
    destination_path: Path


@dataclass(frozen=True)
class BinaryArtifactPublishResult:
    source_path: Path
    destination_path: Path
    source_sha256: str
    stream_sha256: str
    staged_sha256: str
    destination_sha256: str
    source_byte_count: int
    stream_byte_count: int
    staged_byte_count: int
    destination_byte_count: int
    source_inode: int
    staged_inode: int
    cleanup_state: BinaryArtifactCleanupState
    warning_codes: tuple[BinaryArtifactPublishWarning, ...] = ()
    committed: bool = True


class BinaryArtifactPublishError(RuntimeError):
    """Stable content-free failure raised before formal publication."""

    def __init__(self, *, code: str, cleanup_state: BinaryArtifactCleanupState) -> None:
        self.code = code
        self.cleanup_state = cleanup_state
        self.committed = False
        super().__init__(f"binary artifact publication failed: {code}")


ArtifactImportKind = Literal["chatgpt-output"]
ArtifactStorageIdentity = Literal["blank"]


@dataclass(frozen=True)
class ArtifactImportRequest:
    import_kind: ArtifactImportKind
    scope_node_id: str
    scope_kind: Literal["initiative", "epic", "issue"]
    source_path: Path
    title: str
    slug: str | None


@dataclass(frozen=True)
class ArtifactImportResult:
    import_kind: ArtifactImportKind
    storage_identity: ArtifactStorageIdentity
    artifact_id: str
    scope_id: str
    source_path: Path
    destination_path: Path
    sha256: str
    byte_count: int
    committed: bool
    cleanup_state: BinaryArtifactCleanupState
    warning_codes: tuple[BinaryArtifactPublishWarning, ...] = ()


class ArtifactImportError(RuntimeError):
    """Stable content-free failure for the public artifact import command."""

    def __init__(self, *, code: str, cleanup_state: BinaryArtifactCleanupState) -> None:
        self.code = code
        self.cleanup_state = cleanup_state
        self.committed = False
        super().__init__(f"artifact import failed: {code}")


FileArtifactTargetKind = Literal["root", "initiative", "epic", "issue"]
FileArtifactSourceVisibility = Literal["repo_relative", "basename_only"]
FileArtifactPublicationState = Literal["not_committed", "committed", "committed_with_warning"]
FileArtifactRetryDisposition = Literal["safe_after_remediation", "not_needed"]
FileArtifactStorageIdentity = Literal["generic"]
FileArtifactImportWarning = Literal[
    "create_lock_release_failed",
    "directory_fsync_failed",
    "temp_cleanup_retained",
]


@dataclass(frozen=True)
class FileArtifactImportRequest:
    target_kind: FileArtifactTargetKind
    target_value: str | None
    source_path: Path


@dataclass(frozen=True)
class FileArtifactImportResult:
    import_kind: Literal["file"]
    storage_identity: FileArtifactStorageIdentity
    target_kind: FileArtifactTargetKind
    target_id: str
    artifact_id: str
    source_visibility: FileArtifactSourceVisibility
    source: str
    destination: Path
    committed: bool
    publication_state: FileArtifactPublicationState
    cleanup_state: BinaryArtifactCleanupState
    warning_codes: tuple[FileArtifactImportWarning, ...]
    retry_disposition: FileArtifactRetryDisposition
    canonical: bool


class FileArtifactImportError(RuntimeError):
    """Stable content-free failure for generic explicit-file import."""

    def __init__(self, *, code: str, cleanup_state: BinaryArtifactCleanupState) -> None:
        self.code = code
        self.publication_state: FileArtifactPublicationState = "not_committed"
        self.committed = False
        self.cleanup_state = cleanup_state
        self.retry_disposition: FileArtifactRetryDisposition = "safe_after_remediation"
        self.canonical = False
        super().__init__(f"file artifact import failed: {code}")


@dataclass(frozen=True)
class ExplicitFileSourcePreflightRequest:
    repo_root: Path
    source_path: Path


class GuardedExplicitFileSource:
    """Opaque, application-owned source lease borrowed by the publisher."""

    def __init__(
        self,
        *,
        source_path: Path,
        descriptor: int,
        initial_status: object,
        source_visibility: FileArtifactSourceVisibility,
        source_display: str,
    ) -> None:
        self._source_path = source_path
        self._descriptor = descriptor
        self._initial_status = initial_status
        self.source_visibility = source_visibility
        self.source_display = source_display
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        with contextlib.suppress(OSError):
            os.close(self._descriptor)
        self._closed = True

    def __enter__(self) -> GuardedExplicitFileSource:
        if self._closed:
            raise RuntimeError("explicit file source lease is closed")
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self.close()


@dataclass(frozen=True)
class ExplicitFileArtifactPublishRequest:
    repo_root: Path
    guarded_source: GuardedExplicitFileSource
    destination_path: Path


@dataclass(frozen=True)
class ExplicitFileArtifactPublishResult:
    source_visibility: FileArtifactSourceVisibility
    source_display: str
    destination_path: Path
    committed: bool
    cleanup_state: BinaryArtifactCleanupState
    warning_codes: tuple[FileArtifactImportWarning, ...] = ()


@dataclass(frozen=True)
class WorkbenchCopyResult:
    scope_id: str
    source_worktree: WorktreeRecordView
    target_worktree: WorktreeRecordView
    target_workbench_path: Path
    experimental: bool = True
    canonical: bool = False
    disposable: bool = True
    one_shot: bool = True
    sync: bool = False


@dataclass(frozen=True)
class TargetRef:
    kind: str
    node_id: str | None
    github_issue_number: int | None
    github_repo_owner: str | None = None
    github_repo_name: str | None = None


@dataclass(frozen=True)
class CreateNodeRequest:
    title: str
    slug: str | None
    parent_id: str | None
    github_mode: Literal["create", "link_existing"] | None
    github_issue_number: int | None
    github_repo_owner: str | None = None
    github_repo_name: str | None = None


@dataclass(frozen=True)
class CreatePlan:
    meta: StoredMetaRecord
    dest_dir: Path
    replacements: dict[str, str]
    planned_paths: list[Path]


@dataclass(frozen=True)
class CreateNodeResult:
    node: SpecNode
    created_paths: list[Path]
    warnings: list[str]
    post_sync: PostMutationSyncOutcome | None = None


@dataclass(frozen=True)
class ImportNodeRequest:
    issue_number: int
    title: str
    slug: str | None
    parent_id: str | None
    target_repo_owner: str | None = None
    target_repo_name: str | None = None
    allow_foreign_url: bool = False


@dataclass(frozen=True)
class ImportNodeResult:
    node: SpecNode
    imported_issue: IssueSnapshot
    post_import_sync: SyncCommandResult
    warnings: list[str]


@dataclass(frozen=True)
class CreateDiscussionDocRequest:
    doc_type: Literal[
        "adr",
        "disc",
        "research",
        "interview",
        "scratch",
        "draft-requirement",
        "draft-design",
        "draft-plan",
        "note",
    ]
    scope_node_id: str
    title: str
    slug: str | None
    scope_kind: Literal["initiative", "epic", "issue"] | None = None


@dataclass(frozen=True)
class CreateDiscussionDocResult:
    doc_id: str
    doc_type: str
    scope_node_id: str
    path: Path
    warnings: list[str]


@dataclass(frozen=True)
class CreateArtifactDocRequest:
    artifact_type: Literal[
        "blank",
        "research",
        "interview",
        "disc",
        "decision-candidate",
        "pr-repair-batch",
        "adr",
        "draft-requirement",
        "draft-design",
        "draft-plan",
        "scratch",
        "note",
    ]
    scope_node_id: str
    title: str
    slug: str | None
    scope_kind: Literal["initiative", "epic", "issue"] | None = None


@dataclass(frozen=True)
class CreateArtifactDocResult:
    artifact_id: str
    artifact_type: str
    scope_node_id: str
    path: Path
    warnings: list[str]


@dataclass(frozen=True)
class CheckDepsRequest:
    target: TargetRef
    use_github: bool
    issue_limit: int


@dataclass(frozen=True)
class DepsCheckResult:
    target: TargetRef
    inspection: TargetDepsInspection
    warnings: list[str]


MutateDepsAction = Literal["add", "remove"]
MutateDepsResultKind = Literal["updated", "unchanged"]


@dataclass(frozen=True)
class MutateDepsRequest:
    action: MutateDepsAction
    from_id: str
    to_id: str


@dataclass(frozen=True)
class MutateDepsResult:
    action: MutateDepsAction
    from_id: str
    to_id: str
    result: MutateDepsResultKind
    warnings: list[str]
    post_sync: PostMutationSyncOutcome | None = None


class MutateDepsError(RuntimeError):
    def __init__(
        self,
        *,
        action: MutateDepsAction,
        from_id: str,
        to_id: str,
        code: str,
        detail: str | None = None,
    ) -> None:
        self.action = action
        self.from_id = from_id
        self.to_id = to_id
        self.code = code
        self.detail = detail
        super().__init__(detail or code)


@dataclass(frozen=True)
class CloseNodeRequest:
    target: TargetRef
    run_post_sync: bool = True


@dataclass(frozen=True)
class CloseNodeResult:
    node_id: str
    node_kind: str
    github_issue_number: int
    issue_snapshot: IssueSnapshot
    already_closed: bool
    warnings: list[str]
    post_sync: PostMutationSyncOutcome | None = None


@dataclass(frozen=True)
class IssueStartRequest:
    target: TargetRef
    force: bool
    issue_limit: int


@dataclass(frozen=True)
class IssueStartResult:
    target_display: str
    requested_issue_id: str
    active_set: ActiveSetResult
    forced: bool
    warnings: list[str]


@dataclass(frozen=True)
class IssueFinishRequest:
    pass


@dataclass(frozen=True)
class IssueFinishResult:
    issue_id: str
    github_issue_number: int
    already_closed: bool
    active_cleared: bool
    warnings: list[str]
    post_sync: PostMutationSyncOutcome | None = None


DeleteTerminalStatus = Literal[
    "ok",
    "invalid_selector_combination",
    "invalid_selector_syntax",
    "target_not_found",
    "ambiguous_target",
    "active_conflict",
    "dependency_conflict",
    "recursive_required",
    "confirmation_required",
    "metadata_validation_failed",
    "remote_close_failed",
    "local_delete_partial_failure",
]


@dataclass(frozen=True)
class DeleteValidationReason:
    node_id: str | None
    code: str
    message: str


@dataclass(frozen=True)
class DeleteRemoteCloseBuckets:
    closed: list[str]
    noop_already_closed: list[str]
    failed: list[str]
    skipped_not_attempted: list[str]


@dataclass(frozen=True)
class DeleteDependencyScrubFailure:
    node_id: str
    edge_target_id: str


@dataclass(frozen=True)
class DeleteNodeRequest:
    positional_target: str | None
    node_id: str | None
    github_issue: str | None
    recursive: bool
    force: bool
    confirmed: bool
    json_output: bool


@dataclass(frozen=True)
class DeleteNodeResult:
    status: DeleteTerminalStatus
    target_id: str | None
    deleted_node_ids: list[str]
    remaining_node_ids: list[str]
    remote_close: DeleteRemoteCloseBuckets | None
    offending_node_ids: list[str]
    validation_reasons: list[DeleteValidationReason]
    active_restore_result: Literal["cleared", "restored", "restore_failed", "not_needed"] | None
    recovery_guidance: list[str]
    dependency_scrub_failures: list[DeleteDependencyScrubFailure]
    warnings: list[str]
    post_sync: PostMutationSyncOutcome | None = None


@dataclass(frozen=True)
class ShowActiveRequest:
    pass


@dataclass(frozen=True)
class ActiveViewEntry:
    id: str | None
    path: str | None


@dataclass(frozen=True)
class ActiveViewResult:
    initiative: ActiveViewEntry
    epic: ActiveViewEntry
    issue: ActiveViewEntry
    source: Literal["agent.active", "legacy.work.active", "legacy.work.current", "none"]
    warnings: list[str]


@dataclass(frozen=True)
class SetActiveRequest:
    target: TargetRef
    force: bool
    checkout: bool
    use_github: bool
    issue_limit: int


@dataclass(frozen=True)
class ActiveSetResult:
    selection: ActiveSelection
    branch: BranchDecision | None
    manifest_written: bool
    pointer_updated: bool
    warnings: list[str]


@dataclass(frozen=True)
class ClearActiveRequest:
    pass


@dataclass(frozen=True)
class ActiveClearResult:
    cleared: bool
    previous: ActiveSelection | None
    warnings: list[str]


@dataclass(frozen=True)
class SyncRequest:
    force: bool
    github_enabled: bool
    issue_limit: int
    update_active_from_branch: bool


@dataclass(frozen=True)
class SyncStateResult:
    graph: SpecGraph
    active: ActiveSelection | None
    issue_statuses: dict[str, IssueStatusSnapshot]
    progress: ProgressMap
    deps_state: DepsState
    deps_eval_by_id: dict[str, DepsEvaluation]
    generated_at: str
    warnings: list[str]
    deps_preflight_error: str | None
    repo_root: Path | None = None
    issue_depends_on_map: dict[str, list[str]] = field(default_factory=dict)
    raw_node_depends_on_map: dict[str, list[str]] = field(default_factory=dict)
    github_snapshot_by_repo_and_issue_number: dict[tuple[str, int], IssueSnapshot] = field(default_factory=dict)
    github_snapshot_by_repo_scope_and_issue_number: dict[tuple[str | None, int], IssueSnapshot] = field(
        default_factory=dict
    )
    github_snapshot_by_issue_id: dict[str, IssueSnapshot] = field(default_factory=dict)
    dependency_contexts_by_issue_id: dict[str, list[DepsDependencyContext]] = field(default_factory=dict)
    high_level_statuses_by_node_id: dict[str, DepsHighLevelStatus] = field(default_factory=dict)


@dataclass(frozen=True)
class ActiveUpdateOutcome:
    applied: bool
    reason: str | None


@dataclass(frozen=True)
class ArtifactWriteResult:
    index_all_path: str
    index_todo_path: str
    tree_all_path: str
    tree_todo_path: str
    tree_all_puml_path: str
    tree_todo_puml_path: str
    deps_issues_json_path: str
    deps_issues_puml_path: str
    deps_raw_puml_path: str
    dashboard_md_path: str


@dataclass(frozen=True)
class ArtifactWriteFailure:
    status: Literal["failed_before_write", "failed_partial_or_stale"]
    reason: str


@dataclass(frozen=True)
class SyncCommandResult:
    state: SyncStateResult
    write_result: ArtifactWriteResult | None
    active_update: ActiveUpdateOutcome | None
    artifact_failure: ArtifactWriteFailure | None


@dataclass(frozen=True)
class PostMutationSyncOutcome:
    sync_result: SyncCommandResult | None
    skipped_reason: str | None = None
    exception_reason: str | None = None
    fatal_warning_codes: tuple[str, ...] = POST_MUTATION_FATAL_WARNING_CODES
    guidance: list[str] = field(default_factory=list)

    @property
    def warnings(self) -> list[str]:
        if self.sync_result is None:
            return []
        return list(self.sync_result.state.warnings)

    @property
    def fatal_warnings(self) -> list[str]:
        return [
            code
            for code in self.fatal_warning_codes
            if any(warning == code or warning.startswith(f"{code}:") for warning in self.warnings)
        ]

    @property
    def failed(self) -> bool:
        if self.exception_reason is not None:
            return True
        if self.sync_result is not None and self.sync_result.artifact_failure is not None:
            return True
        return bool(self.fatal_warnings)

    @classmethod
    def skipped(cls, reason: str) -> PostMutationSyncOutcome:
        return cls(sync_result=None, skipped_reason=reason, guidance=[])

    @classmethod
    def from_exception(cls, error: Exception) -> PostMutationSyncOutcome:
        return cls(
            sync_result=None,
            exception_reason=str(error),
            guidance=_post_mutation_sync_guidance("post-mutation sync raised an exception"),
        )

    @classmethod
    def from_sync_result(cls, sync_result: SyncCommandResult) -> PostMutationSyncOutcome:
        guidance: list[str] = []
        if sync_result.artifact_failure is not None:
            guidance = _post_mutation_sync_guidance("derived artifacts may be stale or partially written")
        else:
            fatal_warnings = [
                code
                for code in POST_MUTATION_FATAL_WARNING_CODES
                if any(warning == code or warning.startswith(f"{code}:") for warning in sync_result.state.warnings)
            ]
            if fatal_warnings:
                guidance = _post_mutation_sync_guidance(
                    "GitHub issue state fetch was incomplete: " + ", ".join(fatal_warnings)
                )
        return cls(sync_result=sync_result, guidance=guidance)


def _post_mutation_sync_guidance(reason: str) -> list[str]:
    return [
        f"mutation succeeded, but post-mutation sync failed: {reason}",
        "derived artifacts may be stale or partially written",
        "run `./spec-dock/scripts/spec-dock sync` to refresh derived artifacts with GitHub live state",
    ]


@dataclass(frozen=True)
class UseCases:
    create_initiative: Callable[[CreateNodeRequest], CreateNodeResult]
    create_epic: Callable[[CreateNodeRequest], CreateNodeResult]
    create_issue: Callable[[CreateNodeRequest], CreateNodeResult]
    create_artifact_doc: Callable[[CreateArtifactDocRequest], CreateArtifactDocResult]
    import_initiative: Callable[[ImportNodeRequest], ImportNodeResult]
    import_epic: Callable[[ImportNodeRequest], ImportNodeResult]
    import_issue: Callable[[ImportNodeRequest], ImportNodeResult]
    set_active: Callable[[SetActiveRequest], ActiveSetResult]
    show_active: Callable[[ShowActiveRequest], ActiveViewResult]
    clear_active: Callable[[ClearActiveRequest], ActiveClearResult]
    sync: Callable[[SyncRequest], SyncCommandResult]
    check_deps: Callable[[CheckDepsRequest], DepsCheckResult]
    validate_tree: Callable[[ValidateTreeRequest], ValidationResult]
    import_artifact: Callable[[ArtifactImportRequest], ArtifactImportResult] = lambda _req: (_ for _ in ()).throw(
        RuntimeError("import_artifact is not configured")
    )
    import_file_artifact: Callable[[FileArtifactImportRequest], FileArtifactImportResult] = lambda _req: (
        _ for _ in ()
    ).throw(RuntimeError("import_file_artifact is not configured"))
    show_assurance: Callable[[ShowAssuranceRequest], AssuranceResult] = lambda _req: (_ for _ in ()).throw(
        RuntimeError("show_assurance is not configured")
    )
    classify_assurance: Callable[[ClassifyAssuranceRequest], AssuranceResult] = lambda _req: (_ for _ in ()).throw(
        RuntimeError("classify_assurance is not configured")
    )
    verify_assurance: Callable[[VerifyAssuranceRequest], AssuranceResult] = lambda _req: (_ for _ in ()).throw(
        RuntimeError("verify_assurance is not configured")
    )
    compose_assurance: Callable[[ComposeAssuranceRequest], AssuranceResult] = lambda _req: (_ for _ in ()).throw(
        RuntimeError("compose_assurance is not configured")
    )
    workflow_status: Callable[[WorkflowStatusRequest], WorkflowResult] = lambda _req: (_ for _ in ()).throw(
        RuntimeError("workflow_status is not configured")
    )
    workflow_next: Callable[[WorkflowNextRequest], WorkflowResult] = lambda _req: (_ for _ in ()).throw(
        RuntimeError("workflow_next is not configured")
    )
    mutate_deps: Callable[[MutateDepsRequest], MutateDepsResult] = lambda _req: (_ for _ in ()).throw(
        RuntimeError("mutate_deps is not configured")
    )
    delete_node: Callable[[DeleteNodeRequest], DeleteNodeResult] = lambda _req: (_ for _ in ()).throw(
        RuntimeError("delete_node is not configured")
    )
    close_node: Callable[[CloseNodeRequest], CloseNodeResult] = lambda _req: (_ for _ in ()).throw(
        RuntimeError("close_node is not configured")
    )
    issue_start: Callable[[IssueStartRequest], IssueStartResult] = lambda _req: (_ for _ in ()).throw(
        RuntimeError("issue_start is not configured")
    )
    issue_finish: Callable[[IssueFinishRequest], IssueFinishResult] = lambda _req: (_ for _ in ()).throw(
        RuntimeError("issue_finish is not configured")
    )
    doctor: Callable[[DoctorRequest], DoctorResult] = lambda _req: DoctorResult(
        ok=True, findings=[], warnings=[], github_capability_diagnostics=[]
    )
    worktree_create: Callable[[WorktreeCreateRequest], WorktreeCreateResult] = lambda _req: (_ for _ in ()).throw(
        RuntimeError("worktree_create is not configured")
    )
    worktree_list: Callable[[WorktreeListRequest], WorktreeListResult] = lambda _req: (_ for _ in ()).throw(
        RuntimeError("worktree_list is not configured")
    )
    worktree_show: Callable[[WorktreeShowRequest], WorktreeShowResult] = lambda _req: (_ for _ in ()).throw(
        RuntimeError("worktree_show is not configured")
    )
    worktree_remove: Callable[[WorktreeRemoveRequest], WorktreeRemoveResult] = lambda _req: (_ for _ in ()).throw(
        RuntimeError("worktree_remove is not configured")
    )
    workbench_copy: Callable[[WorkbenchCopyRequest], WorkbenchCopyResult] = lambda _req: (_ for _ in ()).throw(
        RuntimeError("workbench_copy is not configured")
    )
    planning_create: Callable[[PlanningCreateRequest], PlanningCommandResult] = lambda _req: (_ for _ in ()).throw(
        RuntimeError("planning_create is not configured")
    )
    planning_revise: Callable[[PlanningReviseRequest], PlanningCommandResult] = lambda _req: (_ for _ in ()).throw(
        RuntimeError("planning_revise is not configured")
    )
    planning_review: Callable[[PlanningReviewRequest], PlanningCommandResult] = lambda _req: (_ for _ in ()).throw(
        RuntimeError("planning_review is not configured")
    )
    planning_apply: Callable[[PlanningApplyRequest], PlanningCommandResult] = lambda _req: (_ for _ in ()).throw(
        RuntimeError("planning_apply is not configured")
    )
    repo_root: Path | None = None
    specdock_dir: Path | None = None
