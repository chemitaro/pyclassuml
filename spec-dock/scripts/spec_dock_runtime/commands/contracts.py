from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Callable

from ..application.contracts import UseCases
from ..presentation.contracts import CliText


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

