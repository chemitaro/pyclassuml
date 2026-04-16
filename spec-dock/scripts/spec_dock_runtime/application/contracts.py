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
    doc_type: Literal["adr", "disc", "research", "note"]
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


@dataclass(frozen=True)
class CloseNodeResult:
    node_id: str
    node_kind: str
    github_issue_number: int
    issue_snapshot: IssueSnapshot
    already_closed: bool
    warnings: list[str]


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
    doctor: Callable[[DoctorRequest], DoctorResult] = (
        lambda _req: DoctorResult(ok=True, findings=[], warnings=[])
    )
