from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_SPEC_DOCK_DIRNAME = "spec-dock"
_INITIATIVES_DIRNAME = "initiatives"


def _initiatives_root(specdock_dir: Path) -> Path:
    """Return initiatives root path and ensure parent exists."""
    if specdock_dir.name != _SPEC_DOCK_DIRNAME:
        raise RuntimeError(f"Not in {_SPEC_DOCK_DIRNAME}: {specdock_dir}")
    return specdock_dir / _INITIATIVES_DIRNAME
