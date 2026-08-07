from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import argparse
    from collections.abc import Callable

    from spec_dock_runtime.application.contracts import UseCases
    from spec_dock_runtime.presentation.contracts import CliText


@dataclass(frozen=True)
class CommandArgs:
    """Marker base type for command-specific typed args."""


@dataclass(frozen=True)
class CommandOutcome:
    exit_code: int
    text: CliText


@dataclass(frozen=True)
class CommandSpec:
    add_arguments: Callable[[argparse.ArgumentParser], None]
    args_factory: Callable[[argparse.Namespace], CommandArgs]
    run: Callable[[CommandArgs, UseCases], CommandOutcome]


@dataclass(frozen=True)
class CommandRegistry:
    items: dict[str, CommandSpec]
