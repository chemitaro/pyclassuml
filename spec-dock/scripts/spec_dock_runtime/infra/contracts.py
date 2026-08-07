from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class StoredMetaRecord:
    kind: str
    id: str
    title: str
    slug: str
    path: str
    parent_id: str | None
    initiative_id: str | None
    epic_id: str | None
    github_issue_number: int | None
    meta_path: str
    github_repo_owner: str | None = None
    github_repo_name: str | None = None


@dataclass(frozen=True)
class DepsDependencyContext:
    source_node_id: str
    source_issue_id: str
    target_node_id: str
    target_node_kind: Literal["initiative", "epic", "issue"]
    target_issue_ids: tuple[str, ...]
    expansion: Literal["issue", "expanded", "empty"]


@dataclass(frozen=True)
class DepsTopologyLoadResult:
    issue_depends_on_map: dict[str, list[str]]
    warnings: list[str]
    raw_node_depends_on_map: dict[str, list[str]] = field(default_factory=dict)
    dependency_contexts_by_issue_id: dict[str, list[DepsDependencyContext]] = field(default_factory=dict)


@dataclass(frozen=True)
class DirectDependencyResolution:
    raw_ref: object
    resolved_node_id: str


@dataclass(frozen=True)
class ActiveManifestEntry:
    id: str
    path: str | None
    authority: str | None = None
    grants: tuple[str, ...] = field(default_factory=tuple)
    promotion_record: dict[str, object] | None = None


@dataclass(frozen=True)
class ActiveManifest:
    initiative: ActiveManifestEntry | None
    epic: ActiveManifestEntry | None
    issue: ActiveManifestEntry | None


@dataclass(frozen=True)
class ActiveManifestLoadResult:
    manifest: ActiveManifest | None
    source: Literal["agent.active", "legacy.work.active", "legacy.work.current", "none"]
    warnings: list[str]


@dataclass(frozen=True)
class ActiveStateSnapshot:
    manifest: ActiveManifest | None
    context_pack_text: str | None
    active_json_text: str | None
    managed_agent_state: dict[str, str | None]
