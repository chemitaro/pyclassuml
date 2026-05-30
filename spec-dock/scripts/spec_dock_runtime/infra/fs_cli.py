from __future__ import annotations

import shutil
from pathlib import Path


def path_exists(path: Path) -> bool:
    return path.exists()


def remove_tree(path: Path) -> None:
    try:
        shutil.rmtree(path)
    except OSError as exc:
        raise RuntimeError(f"failed to remove directory tree: path={path}\n{exc}") from exc
