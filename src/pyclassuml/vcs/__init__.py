"""Version control diff collection seam."""

from pyclassuml.vcs.diff_collect import (
    ChangedFileCollection,
    ChangedFileEntry,
    ChangedLineRange,
    VcsDiffCollection,
    collect_diff_files,
    read_base_file_text,
)

__all__ = [
    "ChangedFileCollection",
    "ChangedFileEntry",
    "ChangedLineRange",
    "VcsDiffCollection",
    "collect_diff_files",
    "read_base_file_text",
]
