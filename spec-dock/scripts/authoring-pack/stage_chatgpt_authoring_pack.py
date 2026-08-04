#!/usr/bin/env python3
"""Compatibility wrapper for `spec-dock authoring pack stage`."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile

_SCRIPT_DIR = Path(__file__).resolve().parent
_SPEC_DOCK_SCRIPTS_DIR = _SCRIPT_DIR.parent
sys.path.insert(0, str(_SPEC_DOCK_SCRIPTS_DIR))

from spec_dock_runtime.application.authoring_pack.pack_stage import (  # noqa: E402
    PackStageRequest,
    stage_authoring_pack,
)
from spec_dock_runtime.domain.authoring_pack.zip_contract import review_pack_input  # noqa: E402
from spec_dock_runtime.presentation.authoring_pack.pack_stage_renderer import (  # noqa: E402
    render_pack_stage_json,
    render_pack_stage_text,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="Authoring pack .zip or extracted tree.")
    parser.add_argument("--stage-dir", help="Directory where reviewed evidence will be staged.")
    parser.add_argument("--format", choices=("text", "json"), dest="output_format")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--review-report", help=argparse.SUPPRESS)
    parser.add_argument("--pack-tree", help=argparse.SUPPRESS)
    parser.add_argument("--issue-dir", help=argparse.SUPPRESS)
    parser.add_argument("--output-dir", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    input_path = args.input or args.pack_tree
    stage_dir = args.stage_dir or args.output_dir
    if not input_path:
        parser.error("--input is required")
    if not stage_dir:
        parser.error("--stage-dir is required")

    output_format = args.output_format or (
        "json" if args.review_report or args.pack_tree or args.issue_dir or args.output_dir else "text"
    )
    if args.review_report:
        legacy_gate = _legacy_review_report_gate(Path(args.review_report), Path(input_path))
        if legacy_gate != "pass":
            result = _legacy_review_block_result(Path(input_path), Path(stage_dir), legacy_gate)
            if output_format == "json":
                print(render_pack_stage_json(result))
            else:
                for line in render_pack_stage_text(result):
                    print(line)
            return 1
    result = stage_authoring_pack(
        PackStageRequest(
            input_path=Path(input_path),
            stage_dir=Path(stage_dir),
            output_format=output_format,
            dry_run=bool(args.dry_run),
        )
    )
    if output_format == "json":
        print(render_pack_stage_json(result))
    else:
        for line in render_pack_stage_text(result):
            print(line)
    return 0 if result.status == "pass" else 1


def _legacy_review_report_gate(review_report: Path, input_path: Path) -> str:
    try:
        payload = json.loads(review_report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "blocked"
    status = payload.get("status")
    if status != "pass":
        return status if isinstance(status, str) else "blocked"
    expected_digest = _legacy_report_digest(payload)
    if expected_digest is None:
        return "blocked"
    if review_pack_input(input_path).status != "pass":
        return "stale"
    current_digest = _legacy_pack_digest(input_path)
    if current_digest != expected_digest:
        return "stale"
    return "pass"


def _legacy_report_digest(payload: dict[str, object]) -> str | None:
    pack_digest = payload.get("pack_digest")
    if isinstance(pack_digest, dict):
        value = pack_digest.get("content_sha256")
        return value if isinstance(value, str) and value else None
    return None


def _legacy_pack_digest(input_path: Path) -> str | None:
    files: dict[str, str] = {}
    root = "specdock-authoring-pack"
    if zipfile.is_zipfile(input_path):
        try:
            with zipfile.ZipFile(input_path) as archive:
                for info in archive.infolist():
                    if info.is_dir() or not info.filename.startswith(f"{root}/"):
                        continue
                    rel_path = info.filename[len(root) + 1 :]
                    files[rel_path] = archive.read(info).decode("utf-8")
        except (OSError, RuntimeError, UnicodeDecodeError, zipfile.BadZipFile):
            return None
    else:
        source_root = input_path / root
        if not source_root.is_dir() or source_root.is_symlink():
            return None
        for path in sorted(item for item in source_root.rglob("*") if item.is_file() and not item.is_symlink()):
            rel_path = path.relative_to(source_root).as_posix()
            try:
                files[rel_path] = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                return None
    digest = hashlib.sha256()
    for rel_path in sorted(files):
        digest.update(rel_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(files[rel_path].encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _legacy_review_block_result(input_path: Path, stage_dir: Path, status: str):
    from spec_dock_runtime.application.authoring_pack.pack_stage import PackStageResult
    from spec_dock_runtime.domain.authoring_pack.zip_contract import PackReviewResult

    review = PackReviewResult(
        status=status if status in {"pass", "fail", "blocked", "stale", "rejected"} else "blocked",
        input_path=str(input_path),
        input_kind="tree" if input_path.is_dir() else "zip",
        findings=("legacy_review_report_not_pass",),
    )
    return PackStageResult(
        status=review.status,
        input_path=str(input_path),
        stage_dir=str(stage_dir),
        review=review,
        findings=("legacy_review_report_not_pass",),
        staged_files=(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
