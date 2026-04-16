from __future__ import annotations

import shutil
from pathlib import Path


def render_text(text: str, replacements: dict[str, str]) -> str:
    rendered = text
    for key, value in replacements.items():
        rendered = rendered.replace(key, value)
    return rendered


def load_template_text(src_path: Path) -> str:
    if not src_path.exists() or not src_path.is_file():
        raise RuntimeError(f"Missing template file: {src_path}")
    try:
        return src_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Failed to read template: {src_path}: {exc}") from exc


def _template_files(src_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(src_dir.rglob("*"), key=lambda p: p.as_posix()):
        if path.is_file():
            files.append(path)
    return files


def _preflight_no_collision(target_paths: list[Path]) -> None:
    for path in target_paths:
        if path.exists():
            raise RuntimeError(f"Destination already exists: {path}")


def copy_scaffolded_tree(src_dir: Path, dest_dir: Path, replacements: dict[str, str]) -> list[Path]:
    if not src_dir.exists() or not src_dir.is_dir():
        raise RuntimeError(f"Missing template directory: {src_dir}")

    template_files = _template_files(src_dir)
    rel_files = [path.relative_to(src_dir) for path in template_files]
    target_paths = [dest_dir / rel for rel in rel_files]
    _preflight_no_collision(target_paths)

    created_paths: list[Path] = []
    for src_path, target_path in zip(template_files, target_paths):
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            text = src_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            shutil.copy2(src_path, target_path)
        else:
            target_path.write_text(render_text(text, replacements), encoding="utf-8")
            if text.startswith("#!"):
                try:
                    target_path.chmod(target_path.stat().st_mode | 0o111)
                except OSError:
                    pass
        created_paths.append(target_path)
    return created_paths


def write_text(dest_path: Path, text: str) -> None:
    if dest_path.exists():
        raise RuntimeError(f"Destination already exists: {dest_path}")
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(text, encoding="utf-8")
