#!/usr/bin/env python3
"""Compatibility wrapper for `spec-dock authoring backend invoke`."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import tempfile

_SCRIPT_DIR = Path(__file__).resolve().parent
_SPEC_DOCK_SCRIPTS_DIR = _SCRIPT_DIR.parent
sys.path.insert(0, str(_SPEC_DOCK_SCRIPTS_DIR))

from spec_dock_runtime.application.authoring_pack.backend_invoke import invoke_backend  # noqa: E402
from spec_dock_runtime.domain.authoring_pack.authority_boundary import is_credential_like_path  # noqa: E402
from spec_dock_runtime.domain.authoring_pack.backend_invoke_contract import BackendInvokeRequest  # noqa: E402
from spec_dock_runtime.presentation.authoring_pack.backend_invoke_renderer import (  # noqa: E402
    render_backend_invoke_json,
    render_backend_invoke_text,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt-pack")
    parser.add_argument("--output-dir")
    parser.add_argument("--format", choices=("text", "json"), default="text", dest="output_format")
    parser.add_argument("--backend-command")
    parser.add_argument("--slug")
    parser.add_argument("-p", "--prompt")
    parser.add_argument("--file", action="append", default=[])
    parser.add_argument("--evidence-mode", choices=("github-synced", "local-context"), default="github-synced")
    parser.add_argument("--timeout-seconds", type=float)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.prompt_pack:
        if not args.output_dir:
            parser.error("--output-dir is required with --prompt-pack")
        return _run_backend(
            BackendInvokeRequest(
                prompt_pack=Path(args.prompt_pack),
                output_dir=Path(args.output_dir),
                output_format=args.output_format,
                backend_command=args.backend_command,
                slug=args.slug,
                prompt=args.prompt,
                evidence_mode=args.evidence_mode,
                timeout_seconds=args.timeout_seconds,
                dry_run=bool(args.dry_run),
            ),
            args.output_format,
        )

    with tempfile.TemporaryDirectory(prefix="specdock-legacy-backend-") as tmp:
        tmp_dir = Path(tmp)
        prompt_pack = tmp_dir / "prompt-pack"
        output_dir = Path(args.output_dir) if args.output_dir else tmp_dir / "invoke-output"
        try:
            _write_legacy_prompt_pack(prompt_pack, tuple(Path(value) for value in args.file))
        except ValueError as error:
            parser.error(str(error))
        return _run_backend(
            BackendInvokeRequest(
                prompt_pack=prompt_pack,
                output_dir=output_dir,
                output_format=args.output_format,
                backend_command=args.backend_command,
                slug=args.slug,
                prompt=args.prompt,
                evidence_mode=args.evidence_mode,
                timeout_seconds=args.timeout_seconds,
                dry_run=bool(args.dry_run),
            ),
            args.output_format,
        )


def _run_backend(request: BackendInvokeRequest, output_format: str) -> int:
    result = invoke_backend(request)
    if output_format == "json":
        print(render_backend_invoke_json(result))
    else:
        for line in render_backend_invoke_text(result):
            print(line)
    return 0 if result.status == "pass" else 1


def _write_legacy_prompt_pack(prompt_pack: Path, files: tuple[Path, ...]) -> None:
    prompt_pack.mkdir(parents=True, exist_ok=True)
    (prompt_pack / ".specdock-authoring-pack").write_bytes(b"")
    resolved_files: list[Path] = []
    for path in files:
        if path.is_symlink():
            raise ValueError("legacy --file attachment must not be a symlink")
        if not path.is_file():
            raise ValueError(f"legacy --file attachment is not a readable file: {path}")
        try:
            resolved = path.resolve(strict=True)
        except (OSError, RuntimeError) as error:
            raise ValueError("legacy --file attachment could not be resolved") from error
        if is_credential_like_path(path.name) or is_credential_like_path(resolved.name):
            raise ValueError("legacy --file attachment has a forbidden credential-like path")
        repo_root = _repository_root(path.parent)
        if (
            repo_root is not None
            and _lexically_within(path, repo_root)
            and (_has_symlink_component(path, repo_root) or not resolved.is_relative_to(repo_root.resolve()))
        ):
            raise ValueError("legacy --file attachment resolves outside the repository")
        resolved_files.append(resolved)
    copy_sources = tuple(resolved_files)
    _copy_or_placeholder(
        copy_sources, prompt_pack / "chatgpt-use-prompt.md", index=0, fallback="legacy prompt attachment\n"
    )
    _copy_or_placeholder(
        copy_sources, prompt_pack / "expected-output-contract.md", index=1, fallback="legacy expected output\n"
    )
    attachment_dir = prompt_pack / "legacy-attachments"
    attachment_dir.mkdir()
    for index, (path, source) in enumerate(zip(files, copy_sources, strict=True)):
        shutil.copyfile(source, attachment_dir / f"{index:03d}-{path.name}")
    context_paths = [path.name for path in files] or ["chatgpt-use-prompt.md"]
    (prompt_pack / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_by": "spec-dock authoring-pack legacy compatibility wrapper",
                "expected_output_root": "specdock-authoring-pack/",
                "required_metadata": ["manifest.json"],
                "files": [
                    "manifest.json",
                    "provenance.json",
                    "source-manifest.json",
                    "stale-if.json",
                    "safe-output-constraints.md",
                    "chatgpt-use-prompt.md",
                    "expected-output-contract.md",
                    *[f"legacy-attachments/{index:03d}-{path.name}" for index, path in enumerate(files)],
                ],
                "authority": "evidence_only",
                "adoption_status": "unreviewed",
                "bundle_generation_not_promotion": True,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (prompt_pack / "provenance.json").write_text(
        json.dumps(
            {
                "evidence_mode": "local-context",
                "sync_state": "local_context",
                "github_sync": "not_verified",
                "source_manifest_hash": "legacy-wrapper",
                "provided_context_paths": context_paths,
                "unsynced_reason": "legacy compatibility wrapper input files",
                "adoption_requires": "explicit_eal_disposition",
                "authority": "evidence_only",
                "adoption_status": "unreviewed",
                "bundle_generation_not_promotion": True,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (prompt_pack / "source-manifest.json").write_text(
        json.dumps(
            {
                "source_paths": context_paths,
                "source_hashes": dict.fromkeys(context_paths, "legacy-wrapper"),
                "source_manifest_hash": "legacy-wrapper",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (prompt_pack / "stale-if.json").write_text("{}\n", encoding="utf-8")
    (prompt_pack / "safe-output-constraints.md").write_text(
        "Legacy compatibility prompt pack. Authority is evidence_only.\n",
        encoding="utf-8",
    )


def _copy_or_placeholder(files: tuple[Path, ...], target: Path, *, index: int, fallback: str) -> None:
    if len(files) > index and files[index].is_file():
        shutil.copyfile(files[index], target)
        return
    target.write_text(fallback, encoding="utf-8")


def _repository_root(start: Path) -> Path | None:
    current = start if start.is_absolute() else Path.cwd() / start
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _lexically_within(path: Path, root: Path) -> bool:
    absolute = path if path.is_absolute() else Path.cwd() / path
    return absolute.is_relative_to(root)


def _has_symlink_component(path: Path, root: Path) -> bool:
    absolute = path if path.is_absolute() else Path.cwd() / path
    relative = absolute.relative_to(root)
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
