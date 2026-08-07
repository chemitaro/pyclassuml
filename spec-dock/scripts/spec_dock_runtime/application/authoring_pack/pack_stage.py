from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from typing import Literal
import zipfile

from spec_dock_runtime.domain.authoring_pack.prompt_pack_contract import EXPECTED_OUTPUT_ROOT
from spec_dock_runtime.domain.authoring_pack.zip_contract import PackReviewResult, review_pack_input


@dataclass(frozen=True)
class PackStageRequest:
    input_path: Path
    stage_dir: Path
    output_format: Literal["text", "json"] = "text"
    dry_run: bool = False


@dataclass(frozen=True)
class PackStageResult:
    status: str
    input_path: str
    stage_dir: str
    review: PackReviewResult
    findings: tuple[str, ...]
    staged_files: tuple[str, ...]
    dry_run: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "input_path": self.input_path,
            "stage_dir": self.stage_dir,
            "review": self.review.to_dict(),
            "findings": list(self.findings),
            "staged_files": list(self.staged_files),
            "dry_run": self.dry_run,
        }


def stage_authoring_pack(request: PackStageRequest) -> PackStageResult:
    target_finding = _unsafe_stage_target(request.stage_dir)
    review = review_pack_input(request.input_path)
    if target_finding:
        return PackStageResult(
            status="rejected",
            input_path=str(request.input_path),
            stage_dir=str(request.stage_dir),
            review=review,
            findings=(target_finding,),
            staged_files=(),
            dry_run=request.dry_run,
        )
    if review.status != "pass":
        return PackStageResult(
            status=review.status,
            input_path=str(request.input_path),
            stage_dir=str(request.stage_dir),
            review=review,
            findings=("review_not_pass", *review.findings),
            staged_files=(),
            dry_run=request.dry_run,
        )
    if request.dry_run:
        return PackStageResult(
            status="pass",
            input_path=str(request.input_path),
            stage_dir=str(request.stage_dir),
            review=review,
            findings=(),
            staged_files=(
                "review-report.json",
                "dry-run-diff.md",
                "adoption/eal-candidates.json",
                ".specdock-stage-owner.json",
            ),
            dry_run=True,
        )
    request.stage_dir.mkdir(parents=True, exist_ok=True)
    _clean_owned_stage_dir(request.stage_dir)
    staged_files = list(_copy_pack(request.input_path, request.stage_dir))
    _write_stage_reports(request.stage_dir, review)
    staged_files.extend((
        "review-report.json",
        "dry-run-diff.md",
        "adoption/eal-candidates.json",
        ".specdock-stage-owner.json",
    ))
    return PackStageResult(
        status="pass",
        input_path=str(request.input_path),
        stage_dir=str(request.stage_dir),
        review=review,
        findings=(),
        staged_files=tuple(sorted(staged_files)),
    )


def _unsafe_stage_target(stage_dir: Path) -> str | None:
    absolute_path = stage_dir if stage_dir.is_absolute() else Path.cwd() / stage_dir
    resolved_path = absolute_path.resolve(strict=False)
    candidate_parts = (absolute_path.parts, resolved_path.parts)
    for parts in candidate_parts:
        if "spec-dock" in parts:
            spec_dock_index = parts.index("spec-dock")
            managed_parts = set(parts[spec_dock_index + 1 :])
            if managed_parts.intersection({"active", "initiatives"}):
                return "unsafe_stage_target:canonical-docs"
    if stage_dir.name == ".assurance.json" or any(".assurance.json" in parts for parts in candidate_parts):
        return "unsafe_stage_target:assurance"
    if stage_dir.exists() and not stage_dir.is_dir():
        return "unsafe_stage_target:not_directory"
    current = absolute_path
    cwd_resolved = Path.cwd().resolve()
    while current != current.parent:
        if current.exists() and current.is_symlink():
            return "unsafe_stage_target:symlink"
        if current.exists() and current.resolve() == cwd_resolved:
            break
        current = current.parent
    marker = stage_dir / ".specdock-stage-owner.json"
    if stage_dir.exists():
        for path in stage_dir.rglob("*"):
            if path.is_symlink():
                return "unsafe_stage_target:symlink_descendant"
    if (
        stage_dir.exists()
        and any(stage_dir.iterdir())
        and (not marker.exists() or not _valid_stage_owner_marker(marker))
    ):
        return "unsafe_stage_target:non_owned_existing"
    return None


def _valid_stage_owner_marker(marker: Path) -> bool:
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        payload.get("authority") == "evidence_only"
        and payload.get("adoption_status") == "unreviewed"
        and payload.get("bundle_generation_not_promotion") is True
        and isinstance(payload.get("created_at"), str)
        and isinstance(payload.get("input_path"), str)
        and isinstance(payload.get("input_kind"), str)
    )


def _clean_owned_stage_dir(stage_dir: Path) -> None:
    marker = stage_dir / ".specdock-stage-owner.json"
    if not marker.exists():
        return
    for child in stage_dir.iterdir():
        if child == marker:
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def _copy_pack(input_path: Path, stage_dir: Path) -> tuple[str, ...]:
    root_name = EXPECTED_OUTPUT_ROOT.rstrip("/")
    staged: list[str] = []
    if zipfile.is_zipfile(input_path):
        with zipfile.ZipFile(input_path) as archive:
            for info in archive.infolist():
                if info.is_dir() or not info.filename.startswith(f"{root_name}/"):
                    continue
                rel = info.filename[len(root_name) + 1 :]
                target = stage_dir / root_name / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(info))
                staged.append((Path(root_name) / rel).as_posix())
        return tuple(staged)
    source_root = input_path / root_name
    for source in sorted(item for item in source_root.rglob("*") if item.is_file()):
        rel = source.relative_to(source_root)
        target = stage_dir / root_name / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        staged.append((Path(root_name) / rel).as_posix())
    return tuple(staged)


def _write_stage_reports(stage_dir: Path, review: PackReviewResult) -> None:
    (stage_dir / "review-report.json").write_text(json.dumps(review.to_dict(), sort_keys=True) + "\n", encoding="utf-8")
    (stage_dir / "dry-run-diff.md").write_text(_render_dry_run_diff(stage_dir), encoding="utf-8")
    adoption_dir = stage_dir / "adoption"
    adoption_dir.mkdir(parents=True, exist_ok=True)
    (adoption_dir / "eal-candidates.json").write_text(
        json.dumps(_pack_eal_candidates(stage_dir), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (stage_dir / ".specdock-stage-owner.json").write_text(
        json.dumps(
            {
                "authority": "evidence_only",
                "adoption_status": "unreviewed",
                "bundle_generation_not_promotion": True,
                "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "input_path": review.input_path,
                "input_sha256": _input_sha256(Path(review.input_path)),
                "input_kind": review.input_kind,
                "issue_id": _active_issue_id(),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _render_dry_run_diff(stage_dir: Path) -> str:
    root = stage_dir / EXPECTED_OUTPUT_ROOT.rstrip("/")
    lines = [
        "# Dry-run diff",
        "",
        "No canonical docs were modified.",
        "",
        "## Staged authoring pack files",
        "",
    ]
    if not root.is_dir():
        lines.append("- none")
        return "\n".join(lines) + "\n"
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        rel_path = path.relative_to(root).as_posix()
        content = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        preview = " ".join(content.strip().split())[:160]
        lines.append(f"- `{rel_path}` sha256={digest}")
        if preview:
            lines.append(f"  preview: {preview}")
    return "\n".join(lines) + "\n"


def _pack_eal_candidates(stage_dir: Path) -> dict[str, object]:
    candidates_path = stage_dir / EXPECTED_OUTPUT_ROOT.rstrip("/") / "adoption" / "eal-candidates.json"
    if not candidates_path.is_file():
        return {"candidates": []}
    try:
        payload = json.loads(candidates_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"candidates": []}
    return payload if isinstance(payload, dict) else {"candidates": []}


def _input_sha256(input_path: Path) -> str | None:
    if input_path.is_file():
        return hashlib.sha256(input_path.read_bytes()).hexdigest()
    if input_path.is_dir():
        digest = hashlib.sha256()
        root = input_path / EXPECTED_OUTPUT_ROOT.rstrip("/")
        if not root.is_dir():
            return None
        for path in sorted(item for item in root.rglob("*") if item.is_file() and not item.is_symlink()):
            rel_path = path.relative_to(root).as_posix()
            digest.update(rel_path.encode("utf-8"))
            digest.update(b"\0")
            digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii"))
            digest.update(b"\0")
        return digest.hexdigest()
    return None


def _active_issue_id() -> str | None:
    meta_path = Path.cwd() / "spec-dock" / "active" / "issue" / ".meta.json"
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    issue_id = payload.get("id")
    return issue_id if isinstance(issue_id, str) and issue_id else None
