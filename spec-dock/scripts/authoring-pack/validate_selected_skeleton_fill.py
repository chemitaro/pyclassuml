#!/usr/bin/env python3
"""Compatibility wrapper for selected-skeleton fill validation.

The installed runtime command is the source of truth:

    spec-dock authoring validate selected-skeleton-fill
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def main(argv: list[str] | None = None) -> int:
    script_dir = Path(__file__).resolve().parents[1]
    spec_dock = script_dir / "spec-dock"
    return subprocess.run([
        sys.executable,
        str(spec_dock),
        "authoring",
        "validate",
        "selected-skeleton-fill",
        *(argv or sys.argv[1:]),
    ]).returncode


if __name__ == "__main__":
    raise SystemExit(main())
