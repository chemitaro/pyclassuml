from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..application.contracts import BootstrapResult


_MISSING_INIT_TARGET_FRAGMENTS = (
    "no rule to make target 'init'",
    "no rule to make target `init'",
    "no rule to make target init",
    "no targets specified and no makefile found",
    "no makefile found",
)


def run_make_init_if_available(worktree_path: Path) -> BootstrapResult:
    if shutil.which("make") is None:
        return BootstrapResult(
            status="detection_failed",
            command="make -n init",
            exit_code=None,
            warnings=["make init detection failed: make command not found"],
        )

    dry_run = subprocess.run(
        ["make", "-n", "init"],
        cwd=str(worktree_path),
        capture_output=True,
        text=True,
        check=False,
    )
    if dry_run.returncode != 0:
        stderr = (dry_run.stderr or "").strip()
        if _is_missing_init_target(stderr):
            return BootstrapResult(status="skipped", command=None, exit_code=None, warnings=[])
        return BootstrapResult(
            status="detection_failed",
            command="make -n init",
            exit_code=dry_run.returncode,
            warnings=[f"make init detection failed: {stderr or 'unknown error'}"],
        )

    run = subprocess.run(
        ["make", "init"],
        cwd=str(worktree_path),
        capture_output=True,
        text=True,
        check=False,
    )
    if run.returncode == 0:
        return BootstrapResult(status="succeeded", command="make init", exit_code=0, warnings=[])
    stderr = (run.stderr or "").strip()
    stdout = (run.stdout or "").strip()
    detail = stderr or stdout or "unknown error"
    return BootstrapResult(
        status="failed",
        command="make init",
        exit_code=run.returncode,
        warnings=[f"make init failed: {detail}"],
    )


def _is_missing_init_target(stderr: str) -> bool:
    lowered = stderr.lower()
    return any(fragment in lowered for fragment in _MISSING_INIT_TARGET_FRAGMENTS)
