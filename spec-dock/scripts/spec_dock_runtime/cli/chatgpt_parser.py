from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spec_dock_runtime.commands.contracts import CommandRegistry, CommandSpec


def build_parser(registry: CommandRegistry) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spec-dock/scripts/spec-dock-chatgpt")
    sub = parser.add_subparsers(dest="command", required=True)

    planning = sub.add_parser("planning", help="Create, revise, or apply Issue planning")
    planning_sub = planning.add_subparsers(dest="planning_command", required=True)
    _bind_leaf(
        planning_sub.add_parser("create", help="Create an Issue planning Candidate"),
        registry,
        "planning_create",
    )
    _bind_leaf(
        planning_sub.add_parser("revise", help="Revise an Issue planning Candidate"),
        registry,
        "planning_revise",
    )
    _bind_leaf(
        planning_sub.add_parser("apply", help="Apply reviewed Issue planning"),
        registry,
        "planning_apply",
    )

    review = sub.add_parser("review", help="Review Issue planning")
    review_sub = review.add_subparsers(dest="review_command", required=True)
    _bind_leaf(
        review_sub.add_parser("planning", help="Review Issue planning"),
        registry,
        "planning_review",
    )
    return parser


def _bind_leaf(
    parser: argparse.ArgumentParser,
    registry: CommandRegistry,
    command_key: str,
) -> None:
    spec = _required_spec(registry, command_key)
    spec.add_arguments(parser)
    parser.set_defaults(command_key=command_key)


def _required_spec(registry: CommandRegistry, command_key: str) -> CommandSpec:
    spec = registry.items.get(command_key)
    if spec is None:
        raise RuntimeError(f"Missing command spec in registry: {command_key}")
    return spec
