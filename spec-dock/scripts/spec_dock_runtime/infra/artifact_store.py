from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from spec_dock_runtime.domain.artifact_composer import (
    ArtifactKind,
    ProfileArtifactTemplate,
    ProfileName,
    ProfileSectionManifest,
    load_profile_section_manifest,
)

if TYPE_CHECKING:
    from spec_dock_runtime.infra.assurance_store import ResolvedIssueTarget

ArtifactSelection = Literal["design", "plan", "report", "all"]

_ARTIFACT_KINDS: tuple[ArtifactKind, ...] = ("design", "plan", "report")


@dataclass(frozen=True)
class IssueArtifact:
    artifact: ArtifactKind
    path: Path
    repo_relative_path: str
    text: str


class ArtifactStore:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.specdock_dir = self.repo_root / "spec-dock"

    def artifact_kinds(self, selection: ArtifactSelection) -> tuple[ArtifactKind, ...]:
        if selection == "all":
            return _ARTIFACT_KINDS
        if selection not in _ARTIFACT_KINDS:
            raise ValueError(f"Unsupported artifact selection: {selection}")
        return (selection,)

    def read_artifact(self, target: ResolvedIssueTarget, artifact: ArtifactKind) -> IssueArtifact:
        path = target.issue_dir / f"{artifact}.md"
        if not path.is_file():
            raise FileNotFoundError(f"Planning artifact not found: {path}")
        self._validate_artifact_path(target, path)
        return IssueArtifact(
            artifact=artifact,
            path=path,
            repo_relative_path=path.relative_to(self.repo_root).as_posix(),
            text=path.read_text(encoding="utf-8"),
        )

    def write_artifact(self, artifact: IssueArtifact, text: str) -> None:
        self.ensure_artifact_writable(artifact)
        artifact.path.write_text(text, encoding="utf-8")

    def ensure_artifact_writable(self, artifact: IssueArtifact) -> None:
        if artifact.path.is_symlink():
            raise RuntimeError(f"Refusing to write symlinked planning artifact: {artifact.repo_relative_path}")
        if artifact.path.exists() and not artifact.path.is_file():
            raise RuntimeError(f"Refusing to write non-file planning artifact: {artifact.repo_relative_path}")
        resolved = artifact.path.resolve()
        if not _is_relative_to(resolved, self.repo_root):
            raise RuntimeError(f"Refusing to write artifact outside repository: {artifact.repo_relative_path}")

    def load_profile_section_manifest(self) -> ProfileSectionManifest:
        path = self.specdock_dir / "templates" / "assurance" / "profile-sections.json"
        return load_profile_section_manifest(path.read_text(encoding="utf-8"))

    def load_profile_artifact_template(
        self,
        artifact: Literal["design", "plan"],
        profile: ProfileName,
    ) -> ProfileArtifactTemplate:
        path, text = self._load_profile_artifact_template_text(artifact, profile)
        _frontmatter, body = _split_frontmatter(text)
        return ProfileArtifactTemplate(
            profile=profile,
            artifact=artifact,
            repo_relative_path=path.relative_to(self.repo_root).as_posix(),
            body=body,
        )

    def load_profile_artifact_template_text(
        self,
        artifact: Literal["design", "plan"],
        profile: ProfileName,
    ) -> str:
        _path, text = self._load_profile_artifact_template_text(artifact, profile)
        return text

    def _load_profile_artifact_template_text(
        self,
        artifact: Literal["design", "plan"],
        profile: ProfileName,
    ) -> tuple[Path, str]:
        if artifact not in ("design", "plan"):
            raise ValueError(f"Unsupported profile template artifact: {artifact}")
        if profile not in ("lite", "standard", "strict", "critical"):
            raise ValueError(f"Unsupported profile template profile: {profile}")
        path = self.specdock_dir / "templates" / "issue-profiles" / profile / f"{artifact}.md"
        if path.is_symlink():
            raise RuntimeError(f"Profile template is symlinked: {path.relative_to(self.repo_root)}")
        resolved = path.resolve()
        if not _is_relative_to(resolved, self.specdock_dir.resolve()):
            raise RuntimeError(f"Profile template is outside spec-dock workspace: {path}")
        if path.exists() and not path.is_file():
            raise RuntimeError(f"Profile template is not a file: {path.relative_to(self.repo_root)}")
        if not path.is_file():
            raise FileNotFoundError(f"Profile template not found: {path.relative_to(self.repo_root)}")
        text = path.read_text(encoding="utf-8")
        _frontmatter, body = _split_frontmatter(text)
        if not body.strip():
            raise ValueError(f"Profile template body is empty: {path.relative_to(self.repo_root)}")
        return path, text

    def _validate_artifact_path(self, target: ResolvedIssueTarget, path: Path) -> None:
        if path.is_symlink():
            raise RuntimeError(f"Refusing to use symlinked planning artifact: {path.relative_to(self.repo_root)}")
        resolved = path.resolve()
        if not _is_relative_to(resolved, target.issue_dir.resolve()):
            raise RuntimeError(f"Planning artifact is outside target issue: {path.relative_to(self.repo_root)}")
        if not _is_relative_to(resolved, self.repo_root):
            raise RuntimeError(f"Planning artifact is outside repository: {path.relative_to(self.repo_root)}")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---\n", len("---\n"))
    if end == -1:
        return "", text
    frontmatter = text[: end + len("\n---")]
    body = text[end + len("\n---\n") :]
    return frontmatter, body
