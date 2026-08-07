#!/usr/bin/env python3
"""Compatibility wrapper for `spec-dock authoring validate epic-issue-candidates`."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

_SCRIPT_DIR = Path(__file__).resolve().parent
_SPEC_DOCK_SCRIPT = _SCRIPT_DIR.parent / "spec-dock"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    return subprocess.run([
        sys.executable,
        str(_SPEC_DOCK_SCRIPT),
        "authoring",
        "validate",
        "epic-issue-candidates",
        *args,
    ]).returncode


if __name__ == "__main__":
    raise SystemExit(main())
