"""Target normalization seam."""

from pyclassuml.targets.diff import DiffTargetNormalization, normalize_diff_targets
from pyclassuml.targets.explicit import TargetNormalization, normalize_explicit_targets

__all__ = [
    "DiffTargetNormalization",
    "TargetNormalization",
    "normalize_diff_targets",
    "normalize_explicit_targets",
]
