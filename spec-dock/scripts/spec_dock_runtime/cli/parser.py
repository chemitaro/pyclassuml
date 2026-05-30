from __future__ import annotations

import argparse

from ..commands.contracts import CommandRegistry, CommandSpec


class _RuntimeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # noqa: A003 - argparse API
        legacy_flags = ("--initiative", "--epic", "--issue")
        hint = ""
        if "unrecognized arguments" in message and any(flag in message for flag in legacy_flags):
            hint = (
                "\n\nHint:\n"
                "  'active set' supports explicit targets:\n"
                "  - active set <target>\n"
                "  - active set --id <node-id>\n"
                "  - active set --github-issue <number>\n"
                "\n"
                "Examples:\n"
                "  spec-dock/scripts/spec-dock active set 123\n"
                "  spec-dock/scripts/spec-dock active set --github-issue 123\n"
                "  spec-dock/scripts/spec-dock active set --id iss-00123\n"
                "  spec-dock/scripts/spec-dock active set iss-00123\n"
                "  spec-dock/scripts/spec-dock deps check --id iss-local-00001\n"
            )
        super().error(message + hint)


def build_parser(registry: CommandRegistry) -> argparse.ArgumentParser:
    parser = _RuntimeArgumentParser(prog="spec-dock/scripts/spec-dock")
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="Create a new node (initiative/epic/issue/doc)")
    new_sub = p_new.add_subparsers(dest="new_kind", required=True)
    _bind_leaf(new_sub.add_parser("initiative", help="Create a new initiative"), registry, "new_initiative")
    _bind_leaf(new_sub.add_parser("epic", help="Create a new epic under an initiative"), registry, "new_epic")
    _bind_leaf(new_sub.add_parser("issue", help="Create a new issue under an epic"), registry, "new_issue")
    _bind_leaf(
        new_sub.add_parser("doc", help="Create a discussion doc under a scope (initiative/epic/issue)"),
        registry,
        "new_doc",
    )

    p_active = sub.add_parser("active", help="Manage the active pointers")
    active_sub = p_active.add_subparsers(dest="active_cmd", required=True)
    _bind_leaf(active_sub.add_parser("set", help="Set active pointers (initiative/epic/issue)"), registry, "active_set")
    _bind_leaf(active_sub.add_parser("show", help="Show current active pointers"), registry, "active_show")
    _bind_leaf(active_sub.add_parser("clear", help="Clear active pointers"), registry, "active_clear")

    _bind_leaf(sub.add_parser("delete", help="Delete local spec nodes with safeguards"), registry, "delete")
    _bind_leaf(sub.add_parser("close", help="Close the linked GitHub issue for a node target"), registry, "close")
    _bind_leaf(
        sub.add_parser("update", help="Update a managed repo from the upstream spec-dock package"),
        registry,
        "update",
    )

    p_delegated = sub.add_parser("delegated-authoring", help="Check delegated discussion draft output")
    delegated_sub = p_delegated.add_subparsers(dest="delegated_authoring_cmd", required=True)
    _bind_leaf(
        delegated_sub.add_parser("manifest", help="Deprecated delegated authoring manifest path"),
        registry,
        "delegated_authoring_manifest",
    )
    _bind_leaf(
        delegated_sub.add_parser("baseline-status", help="Capture delegated authoring baseline status"),
        registry,
        "delegated_authoring_baseline_status",
    )
    _bind_leaf(
        delegated_sub.add_parser("diff-guard", help="Classify delegated authoring diffs"),
        registry,
        "delegated_authoring_diff_guard",
    )

    p_issue = sub.add_parser("issue", help="Run guided issue lifecycle commands")
    issue_sub = p_issue.add_subparsers(dest="issue_cmd", required=True)
    _bind_leaf(issue_sub.add_parser("start", help="Set active issue and checkout its branch"), registry, "issue_start")
    _bind_leaf(issue_sub.add_parser("finish", help="Close active issue and clear active pointers"), registry, "issue_finish")

    p_worktree = sub.add_parser("worktree", help="Manage long-lived Git worktrees")
    worktree_sub = p_worktree.add_subparsers(dest="worktree_cmd", required=True)
    _bind_leaf(
        worktree_sub.add_parser("create", help="Create a central-root Git worktree and optional make init bootstrap"),
        registry,
        "worktree_create",
    )
    _bind_leaf(worktree_sub.add_parser("list", help="List Git worktrees for this repo"), registry, "worktree_list")
    _bind_leaf(worktree_sub.add_parser("show", help="Show one Git worktree by id, path, or basename"), registry, "worktree_show")
    _bind_leaf(
        worktree_sub.add_parser("remove", help="Remove a managed Git worktree without deleting its branch"),
        registry,
        "worktree_remove",
    )

    _bind_leaf(
        sub.add_parser("sync", help="Generate index.json/tree.json (optionally enrich from GitHub)"),
        registry,
        "sync",
    )

    p_deps = sub.add_parser("deps", help="Check and visualize issue/epic/initiative dependencies")
    deps_sub = p_deps.add_subparsers(dest="deps_cmd", required=True)
    _bind_leaf(
        deps_sub.add_parser("check", help="Check whether a target is ready based on dependencies"),
        registry,
        "deps_check",
    )
    _bind_leaf(
        deps_sub.add_parser("add", help="Add an issue dependency edge"),
        registry,
        "deps_add",
    )
    _bind_leaf(
        deps_sub.add_parser("remove", help="Remove an issue dependency edge"),
        registry,
        "deps_remove",
    )

    p_import = sub.add_parser("import", help="Import an existing GitHub issue as a spec node")
    import_sub = p_import.add_subparsers(dest="import_kind", required=True)
    _bind_leaf(
        import_sub.add_parser("initiative", help="Import a GitHub issue as an initiative"),
        registry,
        "import_initiative",
    )
    _bind_leaf(
        import_sub.add_parser("epic", help="Import a GitHub issue as an epic"),
        registry,
        "import_epic",
    )
    _bind_leaf(
        import_sub.add_parser("issue", help="Import a GitHub issue as an issue"),
        registry,
        "import_issue",
    )

    _bind_leaf(sub.add_parser("validate", help="Validate the spec tree structure"), registry, "validate")
    _bind_leaf(sub.add_parser("doctor", help="Diagnose broken state and show repair guidance"), registry, "doctor")
    return parser


def _bind_leaf(parser: argparse.ArgumentParser, registry: CommandRegistry, command_key: str) -> None:
    spec = _required_spec(registry, command_key)
    spec.add_arguments(parser)
    parser.set_defaults(command_key=command_key)


def _required_spec(registry: CommandRegistry, command_key: str) -> CommandSpec:
    spec = registry.items.get(command_key)
    if spec is None:
        raise RuntimeError(f"Missing command spec in registry: {command_key}")
    return spec
