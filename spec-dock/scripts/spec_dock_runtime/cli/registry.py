from __future__ import annotations

from ..commands import active as active_commands
from ..commands import close as close_commands
from ..commands import delete as delete_commands
from ..commands import deps as deps_commands
from ..commands import doctor as doctor_commands
from ..commands import import_cmd as import_commands
from ..commands import new as new_commands
from ..commands import sync as sync_commands
from ..commands import validate as validate_commands
from ..commands.contracts import CommandRegistry, CommandSpec


def build_registry() -> CommandRegistry:
    items: dict[str, CommandSpec] = {}
    items.update(new_commands.command_specs())
    items.update(import_commands.command_specs())
    items.update(active_commands.command_specs())
    items.update(delete_commands.command_specs())
    items.update(close_commands.command_specs())
    items.update(sync_commands.command_specs())
    items.update(deps_commands.command_specs())
    items.update(validate_commands.command_specs())
    items.update(doctor_commands.command_specs())
    return CommandRegistry(items=items)
