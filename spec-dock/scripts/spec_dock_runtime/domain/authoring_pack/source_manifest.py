from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from os import walk
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

DEFAULT_SOURCE_PATHS: tuple[str, ...] = (
    "src/spec_dock/assets/spec_dock/scripts/spec_dock_runtime/commands/authoring.py",
    "src/spec_dock/assets/spec_dock/scripts/spec_dock_runtime/application/authoring_pack",
    "src/spec_dock/assets/spec_dock/scripts/spec_dock_runtime/domain/authoring_pack",
    "src/spec_dock/assets/spec_dock/scripts/spec_dock_runtime/infra/authoring_pack/git_fetch.py",
    "src/spec_dock/assets/spec_dock/scripts/spec_dock_runtime/infra/authoring_pack/preflight_receipt_writer.py",
    "src/spec_dock/assets/spec_dock/scripts/spec_dock_runtime/presentation/authoring_pack",
    "spec-dock/scripts/spec_dock_runtime/commands/authoring.py",
    "spec-dock/scripts/spec_dock_runtime/application/authoring_pack",
    "spec-dock/scripts/spec_dock_runtime/domain/authoring_pack",
    "spec-dock/scripts/spec_dock_runtime/infra/authoring_pack/git_fetch.py",
    "spec-dock/scripts/spec_dock_runtime/infra/authoring_pack/preflight_receipt_writer.py",
    "spec-dock/scripts/spec_dock_runtime/presentation/authoring_pack",
)


@dataclass(frozen=True)
class SourceManifest:
    source_paths: tuple[str, ...]
    source_hashes: dict[str, str]
    source_manifest_hash: str

    def to_dict(self) -> dict[str, object]:
        return {
            "source_paths": list(self.source_paths),
            "source_hashes": dict(self.source_hashes),
            "source_manifest_hash": self.source_manifest_hash,
        }


def build_source_manifest(
    repo_root: Path,
    source_paths: tuple[str, ...],
    *,
    file_observer: Callable[[str], None] | None = None,
) -> SourceManifest:
    paths = effective_source_paths(source_paths)
    source_hashes: dict[str, str] = {}
    selected_paths: list[str] = []
    for source_path in paths:
        raw = Path(source_path)
        if _has_repo_relative_workbench_component(repo_root, raw):
            continue
        path = raw if raw.is_absolute() else repo_root / raw
        if not path.exists():
            continue
        if path.is_symlink():
            continue
        if not _is_within_repo(repo_root, path):
            continue
        selected_paths.append(_repo_relative(repo_root, path))
        if path.is_file():
            rel_path = _repo_relative(repo_root, path)
            source_hashes[rel_path] = _hash_file(path)
            if file_observer is not None:
                file_observer(rel_path)
            continue
        for child_root, child_dirnames, child_filenames in walk(path):
            child_dirnames[:] = sorted(name for name in child_dirnames if name != ".workbench")
            for child_filename in sorted(name for name in child_filenames if name != ".workbench"):
                child = Path(child_root) / child_filename
                if child.is_symlink() or not child.is_file() or _is_ignored_manifest_path(child):
                    continue
                rel_path = _repo_relative(repo_root, child)
                source_hashes[rel_path] = _hash_file(child)
                if file_observer is not None:
                    file_observer(rel_path)
    manifest_payload = json.dumps(source_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return SourceManifest(
        source_paths=tuple(selected_paths),
        source_hashes=source_hashes,
        source_manifest_hash=hashlib.sha256(manifest_payload).hexdigest(),
    )


def expected_hash_from_manifest(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    value = payload.get("source_manifest_hash")
    if not isinstance(value, str) or not value:
        raise ValueError("expected source manifest must contain source_manifest_hash")
    return value


def source_path_blockers(repo_root: Path, source_paths: tuple[str, ...]) -> tuple[str, ...]:
    blockers: list[str] = []
    root = repo_root.resolve()
    for source_path in effective_source_paths(source_paths):
        raw = Path(source_path)
        if _has_repo_relative_workbench_component(repo_root, raw):
            blockers.append(f"unsafe_source_path:workbench:{source_path}")
            continue
        if not raw.is_absolute() and ".." in raw.parts:
            blockers.append(f"unsafe_source_path:parent-traversal:{source_path}")
            continue
        path = raw if raw.is_absolute() else repo_root / raw
        if path.is_symlink():
            blockers.append(f"unsafe_source_path:symlink:{source_path}")
            continue
        if raw.is_absolute():
            try:
                path.resolve(strict=False).relative_to(root)
            except ValueError:
                blockers.append(f"unsafe_source_path:absolute-outside-repo:{source_path}")
        if not raw.is_absolute() and _has_repo_relative_symlink_component(repo_root, raw):
            blockers.append(f"unsafe_source_path:symlink:{source_path}")
            continue
        if path.is_dir():
            for child_root, child_dirnames, child_filenames in walk(path):
                retained_dirnames: list[str] = []
                for child_dirname in sorted(child_dirnames):
                    if child_dirname == ".workbench":
                        continue
                    child = Path(child_root) / child_dirname
                    if child.is_symlink():
                        blockers.append(f"unsafe_source_path:symlink:{_repo_relative_lexical(repo_root, child)}")
                        continue
                    retained_dirnames.append(child_dirname)
                child_dirnames[:] = retained_dirnames
                for child_filename in sorted(name for name in child_filenames if name != ".workbench"):
                    child = Path(child_root) / child_filename
                    if child.is_symlink():
                        blockers.append(f"unsafe_source_path:symlink:{_repo_relative_lexical(repo_root, child)}")
    return tuple(dict.fromkeys(blockers))


def effective_source_paths(source_paths: tuple[str, ...]) -> tuple[str, ...]:
    return source_paths or DEFAULT_SOURCE_PATHS


def empty_source_manifest() -> SourceManifest:
    manifest_payload = json.dumps({}, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return SourceManifest(
        source_paths=(),
        source_hashes={},
        source_manifest_hash=hashlib.sha256(manifest_payload).hexdigest(),
    )


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_ignored_manifest_path(path: Path) -> bool:
    return "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}


def _has_workbench_component(path: Path) -> bool:
    return ".workbench" in path.parts


def _has_repo_relative_workbench_component(repo_root: Path, path: Path) -> bool:
    lexical_path = path if path.is_absolute() else repo_root / path
    for root in (repo_root.absolute(), repo_root.resolve()):
        try:
            lexical_relative = lexical_path.absolute().relative_to(root)
        except ValueError:
            continue
        if _has_workbench_component(lexical_relative):
            return True
    try:
        relative = lexical_path.resolve(strict=False).relative_to(repo_root.resolve())
    except ValueError:
        return False
    return _has_workbench_component(relative)


def _has_repo_relative_symlink_component(repo_root: Path, path: Path) -> bool:
    probe = repo_root
    for part in path.parts:
        probe = probe / part
        if probe.is_symlink():
            return True
    return False


def _is_within_repo(repo_root: Path, path: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(repo_root.resolve())
    except ValueError:
        return False
    return True


def _repo_relative(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _repo_relative_lexical(repo_root: Path, path: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()
