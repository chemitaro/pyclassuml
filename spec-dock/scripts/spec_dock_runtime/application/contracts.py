from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal

from ..domain.models import (
    ActiveSelection,
    BranchDecision,
    DepsEvaluation,
    DepsState,
    IssueSnapshot,
    IssueStatusSnapshot,
    ProgressMap,
    SpecNode,
    SpecGraph,
    TargetDepsInspection,
    ValidationReport,
)
from ..infra.contracts import StoredMetaRecord


POST_MUTATION_FATAL_WARNING_CODES: tuple[str, ...] = ("gh_fetch_failed",)
BootstrapStatus = Literal["skipped", "succeeded", "failed", "detection_failed"]


@dataclass(frozen=True)
class ValidateTreeRequest:
    pass


@dataclass(frozen=True)
class ValidationResult:
    report: ValidationReport
    checked_node_count: int


@dataclass(frozen=True)
class DoctorRequest:
    pass


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
    requested_node_id: str | None
    github_mode: Literal["create", "link_existing", "local_only"] | None
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
    github_snapshot_by_repo_and_issue_number: dict[tuple[str, int], IssueSnapshot] = field(default_factory=dict)
    github_snapshot_by_repo_scope_and_issue_number: dict[tuple[str | None, int], IssueSnapshot] = field(
        default_factory=dict
    )
    github_snapshot_by_issue_id: dict[str, IssueSnapshot] = field(default_factory=dict)


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
    create_discussion_doc: Callable[[CreateDiscussionDocRequest], CreateDiscussionDocResult]
    import_initiative: Callable[[ImportNodeRequest], ImportNodeResult]
    import_epic: Callable[[ImportNodeRequest], ImportNodeResult]
    import_issue: Callable[[ImportNodeRequest], ImportNodeResult]
    set_active: Callable[[SetActiveRequest], ActiveSetResult]
    show_active: Callable[[ShowActiveRequest], ActiveViewResult]
    clear_active: Callable[[ClearActiveRequest], ActiveClearResult]
    sync: Callable[[SyncRequest], SyncCommandResult]
    check_deps: Callable[[CheckDepsRequest], DepsCheckResult]
    validate_tree: Callable[[ValidateTreeRequest], ValidationResult]
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
    doctor: Callable[[DoctorRequest], DoctorResult] = (
        lambda _req: DoctorResult(ok=True, findings=[], warnings=[])
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
    repo_root: Path | None = None
    specdock_dir: Path | None = None
