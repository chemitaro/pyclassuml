"""Project-root-relative ignore matching for target seed candidates."""

from __future__ import annotations

from functools import lru_cache
from fnmatch import fnmatchcase
from pathlib import Path

DEFAULT_IGNORE = (".venv/**", "venv/**", "**/__pycache__/**", "site-packages/**")


def apply_ignore(candidates: list[Path], project_root: Path, user_ignore: tuple[str, ...]) -> tuple[list[Path], int]:
    patterns = (*DEFAULT_IGNORE, *user_ignore)
    seed_files: list[Path] = []
    ignored_count = 0

    for candidate in candidates:
        if is_ignored(candidate, project_root, patterns):
            ignored_count += 1
        else:
            seed_files.append(candidate)

    return seed_files, ignored_count


def is_ignored(path: Path, project_root: Path, patterns: tuple[str, ...]) -> bool:
    try:
        relative = path.relative_to(project_root).as_posix()
    except ValueError:
        relative = path.as_posix()
    return any(matches_ignore_pattern(relative, pattern) for pattern in patterns)


def matches_ignore_pattern(relative_path: str, pattern: str) -> bool:
    path_segments = tuple(segment for segment in relative_path.split("/") if segment)
    pattern_segments = tuple(segment for segment in pattern.replace("\\", "/").split("/") if segment)

    @lru_cache(maxsize=None)
    def matches(pattern_index: int, path_index: int) -> bool:
        if pattern_index == len(pattern_segments):
            return path_index == len(path_segments)

        pattern_segment = pattern_segments[pattern_index]
        if pattern_segment == "**":
            return matches(pattern_index + 1, path_index) or (
                path_index < len(path_segments) and matches(pattern_index, path_index + 1)
            )

        return (
            path_index < len(path_segments)
            and fnmatchcase(path_segments[path_index], pattern_segment)
            and matches(pattern_index + 1, path_index + 1)
        )

    return matches(0, 0)
