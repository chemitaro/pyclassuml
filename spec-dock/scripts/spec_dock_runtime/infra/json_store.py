from __future__ import annotations

import json
from pathlib import Path
from typing import Any

def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON: {path}: {e}") from e
    except UnicodeDecodeError as e:
        raise RuntimeError(f"Failed to read: {path}: {e}") from e
    except OSError as e:
        raise RuntimeError(f"Failed to read: {path}: {e}") from e


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
