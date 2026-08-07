from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Literal

from spec_dock_runtime.domain.assurance import AssuranceProfile

ArtifactKind = Literal["design", "plan", "report"]
ProfileName = Literal["lite", "standard", "strict", "critical"]

_ARTIFACT_KINDS: tuple[ArtifactKind, ...] = ("design", "plan", "report")
_PROFILE_NAMES: tuple[ProfileName, ...] = ("lite", "standard", "strict", "critical")
_MARKER_PATTERN = re.compile(
    r"<!--\s*spec-dock:managed-section\s+"
    r"(?P<edge>begin|end)\s+id=\"(?P<section_id>[a-z0-9._-]+)\"\s*-->"
)
_AWAITING_ASSURANCE_COMPOSE_MARKER = "artifact_state: awaiting-assurance-compose"


@dataclass(frozen=True)
class ManagedSection:
    section_id: str
    artifact: ArtifactKind
    heading: str
    body: str


@dataclass(frozen=True)
class ProfileArtifactPreset:
    profile: ProfileName
    artifact: ArtifactKind
    section_ids: tuple[str, ...]


@dataclass(frozen=True)
class ProfileArtifactTemplate:
    profile: ProfileName
    artifact: Literal["design", "plan"]
    repo_relative_path: str
    body: str


@dataclass(frozen=True)
class ProfileSectionManifest:
    schema_version: int
    sections: dict[str, ManagedSection]
    presets: dict[tuple[ProfileName, ArtifactKind], ProfileArtifactPreset]

    def sections_for(self, profile: AssuranceProfile | str, artifact: ArtifactKind) -> tuple[ManagedSection, ...]:
        profile_name = _profile_name(profile)
        if artifact not in _ARTIFACT_KINDS:
            raise ValueError(f"Unsupported artifact kind: {artifact}")
        preset = self.presets[profile_name, artifact]
        return tuple(self.sections[section_id] for section_id in preset.section_ids)


@dataclass(frozen=True)
class MarkerConflict:
    kind: str
    section_id: str
    message: str


@dataclass(frozen=True)
class ComposeArtifactResult:
    artifact: ArtifactKind
    authorized_profile: ProfileName
    lite_candidate: bool
    output_text: str | None
    changed: bool
    added_section_ids: tuple[str, ...]
    preserved_section_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    errors: tuple[MarkerConflict, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def load_profile_section_manifest(text: str) -> ProfileSectionManifest:
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("Profile section manifest must be a JSON object.")

    schema_version = payload.get("schema_version")
    if schema_version != 1:
        raise ValueError("Profile section manifest schema_version must be 1.")

    sections_payload = payload.get("sections")
    if not isinstance(sections_payload, dict):
        raise ValueError("Profile section manifest sections must be an object.")
    sections = {
        section_id: _load_section(section_id, section_payload)
        for section_id, section_payload in sections_payload.items()
    }

    profiles_payload = payload.get("profiles")
    if not isinstance(profiles_payload, dict):
        raise ValueError("Profile section manifest profiles must be an object.")

    presets: dict[tuple[ProfileName, ArtifactKind], ProfileArtifactPreset] = {}
    for profile in _PROFILE_NAMES:
        profile_payload = profiles_payload.get(profile)
        if not isinstance(profile_payload, dict):
            raise ValueError(f"Profile section manifest missing profile: {profile}")
        for artifact in _ARTIFACT_KINDS:
            section_ids_payload = profile_payload.get(artifact)
            if not isinstance(section_ids_payload, list) or not all(
                isinstance(section_id, str) for section_id in section_ids_payload
            ):
                raise ValueError(f"Profile {profile} artifact {artifact} must list section ids.")
            section_ids = tuple(section_ids_payload)
            for section_id in section_ids:
                section = sections.get(section_id)
                if section is None:
                    raise ValueError(f"Profile {profile} references unknown section id: {section_id}")
                if section.artifact != artifact:
                    raise ValueError(f"Profile {profile} references {section_id} for wrong artifact.")
            presets[profile, artifact] = ProfileArtifactPreset(
                profile=profile,
                artifact=artifact,
                section_ids=section_ids,
            )

    return ProfileSectionManifest(schema_version=schema_version, sections=sections, presets=presets)


def compose_artifact(
    text: str,
    manifest: ProfileSectionManifest,
    artifact: ArtifactKind,
    authorized_profile: AssuranceProfile | str,
    *,
    lite_candidate: bool = False,
    profile_template: ProfileArtifactTemplate | None = None,
) -> ComposeArtifactResult:
    profile_name = _profile_name(authorized_profile)
    if profile_template is not None:
        return _compose_from_profile_template(
            text,
            artifact,
            profile_name,
            lite_candidate=lite_candidate,
            profile_template=profile_template,
        )

    scan = _scan_managed_sections(text)
    if scan.errors:
        return ComposeArtifactResult(
            artifact=artifact,
            authorized_profile=profile_name,
            lite_candidate=lite_candidate,
            output_text=None,
            changed=False,
            added_section_ids=(),
            preserved_section_ids=(),
            warnings=(),
            errors=scan.errors,
        )

    placeholder_state = _placeholder_state(text, artifact)
    if placeholder_state == "conflict":
        return ComposeArtifactResult(
            artifact=artifact,
            authorized_profile=profile_name,
            lite_candidate=lite_candidate,
            output_text=None,
            changed=False,
            added_section_ids=(),
            preserved_section_ids=(),
            warnings=(),
            errors=(
                MarkerConflict(
                    kind="substantive_content_conflict",
                    section_id="awaiting-assurance-compose",
                    message=(
                        f"{artifact}.md contains substantive content outside managed sections; "
                        "assurance compose will not overwrite it automatically."
                    ),
                ),
            ),
        )

    required_sections = manifest.sections_for(profile_name, artifact)
    added_blocks: list[str] = []
    added_section_ids: list[str] = []
    preserved_section_ids: list[str] = []
    for section in required_sections:
        if section.section_id in scan.section_ids:
            preserved_section_ids.append(section.section_id)
            continue
        added_blocks.append(_render_section(section))
        added_section_ids.append(section.section_id)

    if not added_blocks:
        return ComposeArtifactResult(
            artifact=artifact,
            authorized_profile=profile_name,
            lite_candidate=lite_candidate,
            output_text=text,
            changed=False,
            added_section_ids=(),
            preserved_section_ids=tuple(preserved_section_ids),
            warnings=(),
            errors=(),
        )

    output_text = (
        _append_blocks(_strip_placeholder_marker(text), added_blocks)
        if placeholder_state == "placeholder"
        else _append_blocks(text, added_blocks)
    )
    return ComposeArtifactResult(
        artifact=artifact,
        authorized_profile=profile_name,
        lite_candidate=lite_candidate,
        output_text=output_text,
        changed=output_text != text,
        added_section_ids=tuple(added_section_ids),
        preserved_section_ids=tuple(preserved_section_ids),
        warnings=(),
        errors=(),
    )


def _compose_from_profile_template(
    text: str,
    artifact: ArtifactKind,
    authorized_profile: ProfileName,
    *,
    lite_candidate: bool,
    profile_template: ProfileArtifactTemplate,
) -> ComposeArtifactResult:
    if artifact not in ("design", "plan"):
        raise ValueError(f"Profile Markdown templates are not supported for artifact kind: {artifact}")
    if profile_template.artifact != artifact:
        raise ValueError(f"Profile template artifact mismatch: expected {artifact}, got {profile_template.artifact}")
    if profile_template.profile != authorized_profile:
        raise ValueError(f"Profile template mismatch: expected {authorized_profile}, got {profile_template.profile}")

    template_body = _render_profile_template_body(profile_template.body, text)
    target_scan = _scan_managed_sections(text)
    template_scan = _scan_managed_sections(template_body)
    errors = (*target_scan.errors, *template_scan.errors)
    if errors:
        return ComposeArtifactResult(
            artifact=artifact,
            authorized_profile=authorized_profile,
            lite_candidate=lite_candidate,
            output_text=None,
            changed=False,
            added_section_ids=(),
            preserved_section_ids=(),
            warnings=(),
            errors=errors,
        )

    placeholder_state = _placeholder_state(text, artifact)
    if placeholder_state == "conflict":
        if _body_matches_template(text, template_body):
            return ComposeArtifactResult(
                artifact=artifact,
                authorized_profile=authorized_profile,
                lite_candidate=lite_candidate,
                output_text=text,
                changed=False,
                added_section_ids=(),
                preserved_section_ids=tuple(sorted(target_scan.section_ids)),
                warnings=(),
                errors=(),
            )
        return ComposeArtifactResult(
            artifact=artifact,
            authorized_profile=authorized_profile,
            lite_candidate=lite_candidate,
            output_text=None,
            changed=False,
            added_section_ids=(),
            preserved_section_ids=(),
            warnings=(),
            errors=(
                MarkerConflict(
                    kind="substantive_content_conflict",
                    section_id="awaiting-assurance-compose",
                    message=(
                        f"{artifact}.md contains substantive content outside managed sections; "
                        "assurance compose will not overwrite it automatically."
                    ),
                ),
            ),
        )

    if placeholder_state == "placeholder":
        output_text = _append_template_body(_strip_placeholder_marker(text), template_body)
    elif target_scan.section_ids:
        output_text = text
    else:
        output_text = _append_blocks(text, [template_body.rstrip()])
    return ComposeArtifactResult(
        artifact=artifact,
        authorized_profile=authorized_profile,
        lite_candidate=lite_candidate,
        output_text=output_text,
        changed=output_text != text,
        added_section_ids=tuple(sorted(template_scan.section_ids - target_scan.section_ids)),
        preserved_section_ids=tuple(sorted(template_scan.section_ids & target_scan.section_ids)),
        warnings=(),
        errors=(),
    )


@dataclass(frozen=True)
class _ScanResult:
    section_ids: frozenset[str]
    errors: tuple[MarkerConflict, ...]


def _load_section(section_id: str, payload: object) -> ManagedSection:
    if not isinstance(section_id, str) or not re.fullmatch(r"[a-z0-9._-]+", section_id):
        raise ValueError(f"Invalid section id: {section_id}")
    if not isinstance(payload, dict):
        raise ValueError(f"Section {section_id} must be an object.")

    artifact = payload.get("artifact")
    if artifact not in _ARTIFACT_KINDS:
        raise ValueError(f"Section {section_id} has unsupported artifact: {artifact}")
    heading = payload.get("heading")
    body = payload.get("body")
    if not isinstance(heading, str) or not heading.startswith("#"):
        raise ValueError(f"Section {section_id} heading must be a Markdown heading.")
    if not isinstance(body, str) or not body.strip():
        raise ValueError(f"Section {section_id} body must be non-empty text.")

    return ManagedSection(
        section_id=section_id,
        artifact=artifact,
        heading=heading,
        body=body,
    )


def _scan_managed_sections(text: str) -> _ScanResult:
    open_section: str | None = None
    section_ids: set[str] = set()
    errors: list[MarkerConflict] = _malformed_marker_errors(text)

    for match in _MARKER_PATTERN.finditer(text):
        edge = match.group("edge")
        section_id = match.group("section_id")
        if edge == "begin":
            if open_section is not None:
                errors.append(
                    MarkerConflict(
                        kind="mismatched_marker",
                        section_id=section_id,
                        message=f"Managed section {section_id} begins before {open_section} is closed.",
                    )
                )
                continue
            if section_id in section_ids:
                errors.append(
                    MarkerConflict(
                        kind="duplicated_marker",
                        section_id=section_id,
                        message=f"Managed section {section_id} appears more than once.",
                    )
                )
                continue
            open_section = section_id
            continue

        if open_section is None:
            errors.append(
                MarkerConflict(
                    kind="mismatched_marker",
                    section_id=section_id,
                    message=f"Managed section {section_id} ends without a matching begin marker.",
                )
            )
            continue
        if section_id != open_section:
            errors.append(
                MarkerConflict(
                    kind="mismatched_marker",
                    section_id=section_id,
                    message=f"Managed section {open_section} is closed by {section_id}.",
                )
            )
            open_section = None
            continue
        section_ids.add(section_id)
        open_section = None

    if open_section is not None:
        errors.append(
            MarkerConflict(
                kind="unclosed_marker",
                section_id=open_section,
                message=f"Managed section {open_section} has no end marker.",
            )
        )

    return _ScanResult(section_ids=frozenset(section_ids), errors=tuple(errors))


def _malformed_marker_errors(text: str) -> list[MarkerConflict]:
    errors: list[MarkerConflict] = []
    marker_token = "spec-dock:managed-section"
    search_from = 0
    while True:
        comment_start = text.find("<!--", search_from)
        if comment_start == -1:
            break
        comment_end = text.find("-->", comment_start)
        if comment_end == -1:
            marker = text[comment_start:]
            search_from = len(text)
        else:
            marker = text[comment_start : comment_end + len("-->")]
            search_from = comment_end + len("-->")
        if marker_token not in marker:
            continue
        if _MARKER_PATTERN.fullmatch(marker):
            continue
        errors.append(
            MarkerConflict(
                kind="malformed_marker",
                section_id="unknown",
                message="Managed section marker does not match the required grammar.",
            )
        )
    return errors


def _render_section(section: ManagedSection) -> str:
    body = section.body.rstrip()
    return (
        f'<!-- spec-dock:managed-section begin id="{section.section_id}" -->\n'
        f"{section.heading}\n"
        f"{body}\n"
        f'<!-- spec-dock:managed-section end id="{section.section_id}" -->'
    )


def _placeholder_state(text: str, artifact: ArtifactKind) -> Literal["none", "placeholder", "conflict"]:
    if artifact == "report":
        return "none"
    has_marker = _AWAITING_ASSURANCE_COMPOSE_MARKER in text
    has_managed_sections = _MARKER_PATTERN.search(text) is not None
    if has_marker:
        return "placeholder" if _is_unedited_placeholder(text, artifact) else "conflict"
    if has_managed_sections or not _has_substantive_body(text):
        return "none"
    return "conflict"


def _is_unedited_placeholder(text: str, artifact: ArtifactKind) -> bool:
    frontmatter, body = _split_frontmatter(text)
    if _AWAITING_ASSURANCE_COMPOSE_MARKER not in frontmatter:
        return False
    title = "設計" if artifact == "design" else "実装計画"
    noun = "設計書" if artifact == "design" else "実装計画"
    normalized_lines = [line.rstrip() for line in body.strip().splitlines()]
    if len(normalized_lines) != 8:
        return False
    return (
        normalized_lines[0].startswith("# ")
        and normalized_lines[0].endswith(f" — {title} placeholder")
        and normalized_lines[1] == ""
        and normalized_lines[2] == "このファイルはまだ合成されていません。"
        and normalized_lines[3] == ""
        and normalized_lines[4]
        == "先に `requirement.md` を具体化し、`assurance classify --stage requirement` を実行してください。"
        and normalized_lines[5]
        == f"その後、`assurance compose --artifact all` を実行して、この Issue の分類に応じた{noun}テンプレートを合成してください。"
        and normalized_lines[6] == ""
        and normalized_lines[7] == f"この状態のまま{title}本文を書き始めないでください。"
    )


def _strip_placeholder_marker(text: str) -> str:
    frontmatter, _body = _split_frontmatter(text)
    if not frontmatter:
        return text
    frontmatter_lines = []
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if stripped == _AWAITING_ASSURANCE_COMPOSE_MARKER:
            continue
        if stripped in {'状態: "draft"', "状態: draft"}:
            frontmatter_lines.append('状態: "approved"')
            continue
        frontmatter_lines.append(line)
    if frontmatter_lines == ["---", "---"]:
        return ""
    return "\n".join(frontmatter_lines).rstrip() + "\n"


def _has_substantive_body(text: str) -> bool:
    _frontmatter, body = _split_frontmatter(text)
    body = _MARKER_PATTERN.sub("", body)
    return bool(body.strip())


def _split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---\n", len("---\n"))
    if end == -1:
        return "", text
    frontmatter = text[: end + len("\n---")]
    body = text[end + len("\n---\n") :]
    return frontmatter, body


def _append_blocks(text: str, blocks: list[str]) -> str:
    base = text.rstrip()
    if not base:
        return "\n\n".join(blocks) + "\n"
    return base + "\n\n" + "\n\n".join(blocks) + "\n"


def _append_template_body(text: str, template_body: str) -> str:
    return _append_blocks(text, [template_body.rstrip()])


def _body_matches_template(text: str, template_body: str) -> bool:
    _frontmatter, body = _split_frontmatter(text)
    return body.strip() == template_body.strip()


def _render_profile_template_body(template_body: str, target_text: str) -> str:
    replacements = _profile_template_replacements(target_text)
    rendered = template_body
    for token, value in replacements.items():
        rendered = rendered.replace(token, value)
    return rendered


def _profile_template_replacements(target_text: str) -> dict[str, str]:
    frontmatter, _body = _split_frontmatter(target_text)
    if not frontmatter:
        return {}

    scalar_fields = _frontmatter_scalar_fields(frontmatter)
    parent_ids = _frontmatter_list_values(frontmatter, "親")
    github_refs = _frontmatter_list_values(frontmatter, "関連GitHub")
    issue_id = scalar_fields.get("ID")
    issue_title = scalar_fields.get("タイトル")
    replacements: dict[str, str] = {}
    if issue_id:
        replacements["<ISS_ID>"] = issue_id
        replacements["<FEATURE_ID>"] = issue_id
    if issue_title:
        replacements["<ISS_TITLE>"] = issue_title
        replacements["<FEATURE_NAME>"] = issue_title
    for parent_id in parent_ids:
        if parent_id.startswith("epic-") and "<EPIC_ID>" not in replacements:
            replacements["<EPIC_ID>"] = parent_id
        elif parent_id.startswith("init-") and "<INIT_ID>" not in replacements:
            replacements["<INIT_ID>"] = parent_id
    if github_refs:
        replacements["<GITHUB_ISSUE_NUMBER_OR_URL>"] = github_refs[0]
        replacements["<ISSUE_NUMBER_OR_URL>"] = github_refs[0]
    if scalar_fields.get("作成者"):
        replacements["<YOUR_NAME>"] = scalar_fields["作成者"]
    if scalar_fields.get("最終更新"):
        replacements["YYYY-MM-DD"] = scalar_fields["最終更新"]
    return replacements


def _frontmatter_scalar_fields(frontmatter: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in frontmatter.splitlines():
        if line.strip() == "---" or ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        value = raw_value.strip()
        if not value or value.startswith("["):
            continue
        fields[key.strip()] = value.strip('"')
    return fields


def _frontmatter_list_values(frontmatter: str, key: str) -> tuple[str, ...]:
    pattern = re.compile(rf"(?m)^{re.escape(key)}:\s*\[(?P<values>[^\]]*)\]\s*$")
    match = pattern.search(frontmatter)
    if match is None:
        return ()
    return tuple(value.strip().strip('"') for value in match.group("values").split(",") if value.strip())


def _profile_name(profile: AssuranceProfile | str) -> ProfileName:
    value = profile.value if isinstance(profile, AssuranceProfile) else profile
    if value not in _PROFILE_NAMES:
        raise ValueError(f"Unsupported authorized profile: {value}")
    return value
