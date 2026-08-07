from __future__ import annotations

from spec_dock_runtime.commands import issue_planning
from spec_dock_runtime.commands.contracts import CommandRegistry


def build_registry() -> CommandRegistry:
    return CommandRegistry(items=issue_planning.command_specs())
