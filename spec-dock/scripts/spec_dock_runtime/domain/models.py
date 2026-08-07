from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pathlib import Path

SpecNodeKind = Literal["initiative", "epic", "issue"]
DepsLifecycleState = Literal["open", "closed", "done", "unknown"]
DepsDependencyDisposition = Literal["blocking", "satisfied", "indeterminate"]
DepsDispositionBasis = Literal[
    "empty_open_container",
    "empty_unknown_container",
    "lifecycle_closed",
    "local_done",
    "all_descendant_issues_done",
    "descendant_issue_open",
    "descendant_issue_unknown",
]


@dataclass(frozen=True)
class SpecNodeSeed:
    kind: SpecNodeKind
    id: str
    title: str
    slug: str
    path: Path
    meta_path: Path
    parent_id: str | None
    initiative_id: str | None
    epic_id: str | None
    github_issue_number: int | None
    github_repo_owner: str | None = None
    github_repo_name: str | None = None


@dataclass(frozen=True)
class SpecNode:
    kind: SpecNodeKind
    id: str
    title: str
    slug: str
    path: Path
    meta_path: Path
    parent_id: str | None
    initiative_id: str | None
    epic_id: str | None
    github_issue_number: int | None
    github_repo_owner: str | None = None
    github_repo_name: str | None = None


@dataclass(frozen=True)
class SpecGraph:
    nodes_by_id: dict[str, SpecNode]


@dataclass(frozen=True)
class NodeId:
    value: str


@dataclass(frozen=True)
class BranchDecision:
    desired: str
    candidates: tuple[str, str]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class IssueSnapshot:
    issue_number: int
    state: str
    title: str
    labels: list[str]
    updated_at: str
    url: str
    repo_owner: str | None = None
    repo_name: str | None = None


@dataclass(frozen=True)
class ActiveSelection:
    initiative_id: str | None
    epic_id: str | None
    issue_id: str | None


@dataclass(frozen=True)
class IssueStatusSnapshot:
    issue_id: str
    authority: str
    effective_status: str
    source: str
    stale: bool
    last_sync_at: str | None
    github_number: int | None

    @property
    def status(self) -> str:
        # Backward-compatible alias for existing callers/tests.
        return self.effective_status


@dataclass(frozen=True)
class ProgressMap:
    by_node_id: dict[str, dict[str, int]]
    counts: dict[str, int]


@dataclass(frozen=True)
class DepsNodeState:
    node_id: str
    status: str
    ready: bool
    blockers_top: list[str]
    effective_depends_on: list[str]


@dataclass(frozen=True)
class DepsState:
    nodes: list[DepsNodeState]
    warnings: list[str]


@dataclass(frozen=True)
class DepsDependencyContext:
    source_node_id: str
    source_issue_id: str
    target_node_id: str
    target_node_kind: SpecNodeKind
    target_issue_ids: tuple[str, ...]
    expansion: Literal["issue", "expanded", "empty"]
    lifecycle_state: DepsLifecycleState | None = field(default=None, compare=False)
    lifecycle_source: str | None = field(default=None, compare=False)
    dependency_disposition: DepsDependencyDisposition | None = field(default=None, compare=False)
    disposition_basis: DepsDispositionBasis | None = field(default=None, compare=False)


@dataclass(frozen=True)
class DepsDirectNodeDependency:
    source_node_id: str
    source_node_kind: SpecNodeKind
    target_node_id: str
    target_node_kind: SpecNodeKind
    target_issue_ids: tuple[str, ...]
    expansion: Literal["issue", "expanded", "empty"]
    lifecycle_state: DepsLifecycleState
    lifecycle_source: str
    dependency_disposition: DepsDependencyDisposition
    disposition_basis: DepsDispositionBasis


@dataclass(frozen=True)
class DepsHighLevelStatus:
    node_id: str
    state: DepsLifecycleState
    source: str


@dataclass(frozen=True)
class DepsNodeBlocker:
    node_id: str
    reason: Literal["empty_open", "empty_unknown", "lifecycle_unknown"]
    state: Literal["open", "unknown"]
    state_source: str
    source_issue_id: str
    lifecycle_state: DepsLifecycleState | None = None
    lifecycle_source: str | None = None
    dependency_disposition: DepsDependencyDisposition | None = None
    disposition_basis: DepsDispositionBasis | None = None


@dataclass(frozen=True)
class DepsEvaluation:
    ready: bool
    guard_reason: Literal["ready", "blocked", "unknown"]
    blockers: list[str]
    blockers_top: list[str]
    closure: list[str]
    issue_blockers: list[str] = field(default_factory=list)
    node_blockers: list[DepsNodeBlocker] = field(default_factory=list)
    satisfied_dependencies: list[DepsDependencyContext] = field(default_factory=list)
    dependency_contexts: list[DepsDependencyContext] = field(default_factory=list)
    debug_context: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class TargetDepsInspection:
    target_id: NodeId
    evaluation: DepsEvaluation
    node_states: dict[str, DepsNodeState]
    effective_depends_on: list[str]
    warnings: list[str]
    issue_statuses: dict[str, IssueStatusSnapshot] = field(default_factory=dict)
    direct_node_dependencies: list[DepsDirectNodeDependency] = field(default_factory=list)


@dataclass(frozen=True)
class ValidationReport:
    errors: list[str]
    warnings: list[str]
