from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CliText:
    stdout_lines: list[str]
    stderr_lines: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class IndexArtifact:
    all_json_text: str
    todo_json_text: str


@dataclass(frozen=True)
class TreeArtifact:
    all_json_text: str
    todo_json_text: str
    all_puml_text: str
    todo_puml_text: str


@dataclass(frozen=True)
class DepsIssuesArtifact:
    json_text: str
    puml_text: str


@dataclass(frozen=True)
class DepsRawArtifact:
    puml_text: str


@dataclass(frozen=True)
class DashboardArtifact:
    markdown_text: str


@dataclass(frozen=True)
class ArtifactBundle:
    index: IndexArtifact
    tree: TreeArtifact
    deps_issues: DepsIssuesArtifact
    dashboard: DashboardArtifact
    deps_raw: DepsRawArtifact
