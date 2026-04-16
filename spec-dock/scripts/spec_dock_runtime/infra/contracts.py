from __future__ import annotations

from dataclasses import dataclass
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
class DepsTopologyLoadResult:
    issue_depends_on_map: dict[str, list[str]]
    warnings: list[str]


@dataclass(frozen=True)
class DirectDependencyResolution:
    raw_ref: object
    resolved_node_id: str


@dataclass(frozen=True)
class ActiveManifestEntry:
    id: str
    path: str | None


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
