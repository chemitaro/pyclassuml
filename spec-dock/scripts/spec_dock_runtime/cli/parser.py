from __future__ import annotations

import argparse
from typing import TYPE_CHECKING, NoReturn

if TYPE_CHECKING:
    from spec_dock_runtime.commands.contracts import CommandRegistry, CommandSpec


class _RuntimeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
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

    p_new = sub.add_parser("new", help="Create a new node or artifact (initiative/epic/issue/artifact)")
    new_sub = p_new.add_subparsers(dest="new_kind", required=True)
    _bind_leaf(new_sub.add_parser("initiative", help="Create a new initiative"), registry, "new_initiative")
    _bind_leaf(new_sub.add_parser("epic", help="Create a new epic under an initiative"), registry, "new_epic")
    _bind_leaf(new_sub.add_parser("issue", help="Create a new issue under an epic"), registry, "new_issue")
    _bind_leaf(
        new_sub.add_parser("artifact", help="Create an artifact under a scope (initiative/epic/issue)"),
        registry,
        "new_artifact",
    )

    p_artifact = sub.add_parser("artifact", help="Manage scope-local artifacts")
    artifact_sub = p_artifact.add_subparsers(dest="artifact_cmd", required=True)
    artifact_import = artifact_sub.add_parser("import", help="Import an existing file as an artifact")
    artifact_import_sub = artifact_import.add_subparsers(dest="artifact_import_kind", required=True)
    _bind_leaf(
        artifact_import_sub.add_parser(
            "chatgpt-output",
            help="Import opaque Markdown bytes from an approved Workbench",
        ),
        registry,
        "artifact_import_chatgpt_output",
    )
    _bind_leaf(
        artifact_import_sub.add_parser(
            "file",
            help="Import one explicit file as an opaque generic Artifact",
        ),
        registry,
        "artifact_import_file",
    )

    p_active = sub.add_parser("active", help="Manage the active pointers")
    active_sub = p_active.add_subparsers(dest="active_cmd", required=True)
    _bind_leaf(active_sub.add_parser("set", help="Set active pointers (initiative/epic/issue)"), registry, "active_set")
    _bind_leaf(active_sub.add_parser("show", help="Show current active pointers"), registry, "active_show")
    _bind_leaf(active_sub.add_parser("clear", help="Clear active pointers"), registry, "active_clear")

    p_assurance = sub.add_parser("assurance", help="Show, classify, and verify issue assurance contracts")
    assurance_sub = p_assurance.add_subparsers(dest="assurance_cmd", required=True)
    _bind_leaf(
        assurance_sub.add_parser("show", help="Show the target issue assurance contract"), registry, "assurance_show"
    )
    _bind_leaf(
        assurance_sub.add_parser("classify", help="Classify the target issue and write .assurance.json"),
        registry,
        "assurance_classify",
    )
    _bind_leaf(
        assurance_sub.add_parser("verify", help="Verify the target issue assurance contract"),
        registry,
        "assurance_verify",
    )
    _bind_leaf(
        assurance_sub.add_parser("compose", help="Compose profile-aware planning artifact sections"),
        registry,
        "assurance_compose",
    )

    p_authoring = sub.add_parser(
        "authoring",
        help="Run ChatGPT authoring helper commands",
        description="Run ChatGPT authoring helper commands.",
        epilog=(
            "Authoring commands:\n"
            "  authoring preflight github-sync\n"
            "  authoring pack prepare\n"
            "  authoring backend invoke\n"
            "  authoring pack review\n"
            "  authoring pack stage\n"
            "  authoring validate initiative-epic-candidates\n"
            "  authoring validate epic-issue-candidates\n"
            "  authoring validate issue-draft-adoption\n"
            "  authoring validate selected-skeleton-fill\n"
            "  authoring approval check"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    authoring_sub = p_authoring.add_subparsers(dest="authoring_cmd", required=True)

    authoring_preflight = authoring_sub.add_parser("preflight", help="Run authoring preflight checks")
    authoring_preflight_sub = authoring_preflight.add_subparsers(dest="authoring_preflight_cmd", required=True)
    _bind_leaf(
        authoring_preflight_sub.add_parser("github-sync", help="Check GitHub sync before repo-aware authoring"),
        registry,
        "authoring_preflight_github_sync",
    )

    authoring_pack = authoring_sub.add_parser("pack", help="Authoring pack helpers")
    authoring_pack_sub = authoring_pack.add_subparsers(dest="authoring_pack_cmd", required=True)
    _bind_leaf(
        authoring_pack_sub.add_parser("prepare", help="Prepare a ChatGPT prompt pack from preflight evidence"),
        registry,
        "authoring_pack_prepare",
    )
    _bind_leaf(
        authoring_pack_sub.add_parser("review", help="Review ChatGPT authoring pack ZIP/tree output"),
        registry,
        "authoring_pack_review",
    )
    _bind_leaf(
        authoring_pack_sub.add_parser("stage", help="Stage reviewed ChatGPT authoring pack evidence"),
        registry,
        "authoring_pack_stage",
    )

    authoring_backend = authoring_sub.add_parser("backend", help="ChatGPT backend helpers")
    authoring_backend_sub = authoring_backend.add_subparsers(dest="authoring_backend_cmd", required=True)
    _bind_leaf(
        authoring_backend_sub.add_parser("invoke", help="Invoke a configured ChatGPT backend with a prompt pack"),
        registry,
        "authoring_backend_invoke",
    )

    authoring_validate = authoring_sub.add_parser("validate", help="Validate evidence-only authoring outputs")
    authoring_validate_sub = authoring_validate.add_subparsers(dest="authoring_validate_cmd", required=True)
    _bind_leaf(
        authoring_validate_sub.add_parser(
            "initiative-epic-candidates",
            help="Validate evidence-only Initiative-to-Epic candidates",
        ),
        registry,
        "authoring_validate_initiative_epic_candidates",
    )
    _bind_leaf(
        authoring_validate_sub.add_parser(
            "epic-issue-candidates",
            help="Validate evidence-only Epic-to-Issue candidates",
        ),
        registry,
        "authoring_validate_epic_issue_candidates",
    )
    _bind_leaf(
        authoring_validate_sub.add_parser(
            "issue-draft-adoption",
            help="Validate evidence-only Issue draft adoption",
        ),
        registry,
        "authoring_validate_issue_draft_adoption",
    )
    _bind_leaf(
        authoring_validate_sub.add_parser(
            "selected-skeleton-fill",
            help="Validate evidence-only selected skeleton fill",
        ),
        registry,
        "authoring_validate_selected_skeleton_fill",
    )

    authoring_approval = authoring_sub.add_parser("approval", help="Check authoring approval evidence")
    authoring_approval_sub = authoring_approval.add_subparsers(dest="authoring_approval_cmd", required=True)
    _bind_leaf(
        authoring_approval_sub.add_parser("check", help="Check human approval evidence before node creation"),
        registry,
        "authoring_approval_check",
    )

    _bind_leaf(sub.add_parser("guidance", help="Render state-aware issue guidance"), registry, "guidance")

    p_workflow = sub.add_parser("workflow", help="Show state-aware workflow status")
    workflow_sub = p_workflow.add_subparsers(dest="workflow_cmd", required=True)
    _bind_leaf(workflow_sub.add_parser("status", help="Show resolved workflow state"), registry, "workflow_status")

    _bind_leaf(sub.add_parser("delete", help="Delete local spec nodes with safeguards"), registry, "delete")
    _bind_leaf(sub.add_parser("close", help="Close the linked GitHub issue for a node target"), registry, "close")
    _bind_leaf(
        sub.add_parser("update", help="Update a managed repo from the upstream spec-dock package"),
        registry,
        "update",
    )
    _bind_leaf(
        sub.add_parser("uninstall", help="Uninstall SpecDock-managed repo assets via the upstream spec-dock package"),
        registry,
        "uninstall",
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
    _bind_leaf(
        issue_sub.add_parser("finish", help="Close active issue and clear active pointers"), registry, "issue_finish"
    )

    p_worktree = sub.add_parser("worktree", help="Manage long-lived Git worktrees")
    worktree_sub = p_worktree.add_subparsers(dest="worktree_cmd", required=True)
    _bind_leaf(
        worktree_sub.add_parser("create", help="Create a central-root Git worktree and optional make init bootstrap"),
        registry,
        "worktree_create",
    )
    _bind_leaf(worktree_sub.add_parser("list", help="List Git worktrees for this repo"), registry, "worktree_list")
    _bind_leaf(
        worktree_sub.add_parser("show", help="Show one Git worktree by id, path, or basename"),
        registry,
        "worktree_show",
    )
    _bind_leaf(
        worktree_sub.add_parser("remove", help="Remove a Git worktree without deleting its branch"),
        registry,
        "worktree_remove",
    )

    p_workbench = sub.add_parser(
        "workbench",
        help="Run explicit experimental operations on non-canonical Workbench content",
    )
    workbench_sub = p_workbench.add_subparsers(dest="workbench_cmd", required=True)
    _bind_leaf(
        workbench_sub.add_parser(
            "copy",
            help=(
                "Experimental one-shot copy of disposable, non-canonical scoped Workbench content "
                "to another worktree without synchronization"
            ),
        ),
        registry,
        "workbench_copy",
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
