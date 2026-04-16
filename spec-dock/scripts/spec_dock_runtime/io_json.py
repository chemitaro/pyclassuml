from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from .infra import clock as _infra_clock
from .infra import json_store as _infra_json_store


def _now_iso() -> str:
    return _infra_clock.now_iso()


def _today() -> str:
    return _infra_clock.today()


def _load_json(path: Path) -> Any:
    return _infra_json_store.load_json(path)


def _write_json(path: Path, data: Any) -> None:
    _infra_json_store.write_json(path, data)


def _try_make_readonly(path: Path) -> tuple[bool, str | None]:
    """Try to make `path` read-only (best-effort, never raises)."""
    try:
        mode = path.stat().st_mode
        path.chmod(mode & ~0o222)
    except OSError as e:
        return False, str(e)

    if os.name == "posix":
        try:
            if path.stat().st_mode & 0o222:
                return False, "write bit still set after chmod"
        except OSError as e:
            return False, str(e)

    return True, None


def _warn(message: str) -> None:
    """Print a runtime warning using the stable CLI prefix."""
    print(f"spec-dock: (warn) {message}", file=sys.stderr)
