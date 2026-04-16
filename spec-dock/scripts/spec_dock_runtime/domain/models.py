from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

SpecNodeKind = Literal["initiative", "epic", "issue"]


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
class DepsEvaluation:
    ready: bool
    guard_reason: Literal["ready", "blocked", "unknown"]
    blockers: list[str]
    blockers_top: list[str]
    closure: list[str]


@dataclass(frozen=True)
class TargetDepsInspection:
    target_id: NodeId
    evaluation: DepsEvaluation
    node_states: dict[str, DepsNodeState]
    effective_depends_on: list[str]
    warnings: list[str]
    issue_statuses: dict[str, IssueStatusSnapshot] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationReport:
    errors: list[str]
    warnings: list[str]
