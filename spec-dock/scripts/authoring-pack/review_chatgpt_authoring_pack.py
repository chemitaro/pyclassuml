#!/usr/bin/env python3
"""Compatibility wrapper for `spec-dock authoring pack review`."""

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

from authoring_pack_review import STATUS_EXIT_CODES, cli_summary, review_input, write_review_outputs  # noqa: E402

from spec_dock_runtime.application.authoring_pack.pack_review import (  # noqa: E402
    PackReviewRequest,
    _unsafe_report_path,
    review_authoring_pack,
)
from spec_dock_runtime.presentation.authoring_pack.pack_review_renderer import (  # noqa: E402
    render_pack_review_json,
    render_pack_review_text,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Authoring pack .zip or extracted tree.")
    parser.add_argument("--format", choices=("text", "json"), dest="output_format")
    parser.add_argument("--evidence-mode", choices=("github-synced", "local-context"), default="github-synced")
    parser.add_argument("--report-path")
    parser.add_argument("--preflight", help=argparse.SUPPRESS)
    parser.add_argument("--output-dir", help=argparse.SUPPRESS)
    parser.add_argument("--input-kind", choices=("auto", "zip", "tree"), default="auto", help=argparse.SUPPRESS)
    parser.add_argument("--extract-dir", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    legacy_mode = bool(args.preflight or args.extract_dir or args.input_kind != "auto")
    if legacy_mode and not args.preflight:
        parser.error("--preflight is required for legacy review arguments")
    if legacy_mode and not args.output_dir:
        parser.error("--output-dir is required for legacy review arguments")
    if legacy_mode:
        output_dir = Path(args.output_dir)
        legacy_result = review_input(
            Path(args.input),
            Path(args.preflight),
            input_kind=args.input_kind,
            extract_dir=Path(args.extract_dir) if args.extract_dir else None,
        )
        legacy_result = write_review_outputs(output_dir, legacy_result)
        print(json.dumps(cli_summary(legacy_result, output_dir), ensure_ascii=False, sort_keys=True))
        return STATUS_EXIT_CODES[legacy_result["status"]]
    output_format = args.output_format or ("json" if args.output_dir or args.preflight else "text")
    report_path = Path(args.report_path) if args.report_path else None
    if report_path is None and args.output_dir:
        report_path = Path(args.output_dir) / "validation-report.json"

    request_report_path = None if args.output_dir and args.report_path is None else report_path
    result = review_authoring_pack(
        PackReviewRequest(
            input_path=Path(args.input),
            output_format=output_format,
            evidence_mode=args.evidence_mode,
            report_path=request_report_path,
        )
    )
    if report_path is not None and request_report_path is None:
        unsafe_report_path = _unsafe_report_path(report_path)
        if unsafe_report_path:
            result = review_authoring_pack(
                PackReviewRequest(
                    input_path=Path(args.input),
                    output_format=output_format,
                    evidence_mode=args.evidence_mode,
                    report_path=report_path,
                )
            )
        else:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            payload = result.to_dict()
            payload["pack_digest"] = {
                "content_sha256": _legacy_pack_digest(Path(args.input)) if result.status == "pass" else None
            }
            report_path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    if output_format == "json":
        print(render_pack_review_json(result))
    else:
        for line in render_pack_review_text(result):
            print(line)
    return 0 if result.status == "pass" else 1


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


if __name__ == "__main__":
    raise SystemExit(main())
