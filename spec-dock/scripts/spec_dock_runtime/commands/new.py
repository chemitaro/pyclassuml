from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from spec_dock_runtime.application.contracts import (
    CreateArtifactDocRequest,
    CreateNodeRequest,
    CreateNodeResult,
    UseCases,
)
from spec_dock_runtime.commands.contracts import CommandArgs, CommandOutcome, CommandSpec
from spec_dock_runtime.presentation.cli_text import render_new_artifact_text, render_new_node_text
from spec_dock_runtime.presentation.contracts import CliText

if TYPE_CHECKING:
    import argparse

_artifact_types = (
    "blank",
    "research",
    "interview",
    "disc",
    "decision-candidate",
    "pr-repair-batch",
    "adr",
    "draft-requirement",
    "draft-design",
    "draft-plan",
)


@dataclass(frozen=True)
class NewInitiativeArgs(CommandArgs):
    title: str
    slug: str | None
    create_github_issue: bool
    github_issue_number: int | None


@dataclass(frozen=True)
class NewEpicArgs(CommandArgs):
    initiative_id: str
    title: str
    slug: str | None
    create_github_issue: bool
    github_issue_number: int | None


@dataclass(frozen=True)
class NewIssueArgs(CommandArgs):
    epic_id: str
    title: str
    slug: str | None
    create_github_issue: bool
    github_issue_number: int | None


@dataclass(frozen=True)
class NewArtifactArgs(CommandArgs):
    artifact_type: str
    scope_node_id: str
    scope_kind: Literal["initiative", "epic", "issue"]
    title: str
    slug: str | None


def command_specs() -> dict[str, CommandSpec]:
    return {
        "new_initiative": CommandSpec(
            add_arguments=_add_new_initiative_arguments,
            args_factory=_new_initiative_args,
            run=_run_new_initiative,
        ),
        "new_epic": CommandSpec(
            add_arguments=_add_new_epic_arguments,
            args_factory=_new_epic_args,
            run=_run_new_epic,
        ),
        "new_issue": CommandSpec(
            add_arguments=_add_new_issue_arguments,
            args_factory=_new_issue_args,
            run=_run_new_issue,
        ),
        "new_artifact": CommandSpec(
            add_arguments=_add_new_artifact_arguments,
            args_factory=_new_artifact_args,
            run=_run_new_artifact,
        ),
    }


def _add_new_initiative_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--title", required=True)
    parser.add_argument("--slug")
    github_group = parser.add_mutually_exclusive_group()
    github_group.add_argument(
        "--create-github-issue",
        action="store_true",
        help="Create and link a new GitHub issue (id becomes init-NNNN)",
    )
    github_group.add_argument(
        "--github-issue",
        type=int,
        help="Existing GitHub issue number to link (id becomes init-NNNN)",
    )


def _add_new_epic_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--initiative",
        required=True,
        help="Parent initiative (e.g. 123 / init-00123 / init-local-00001)",
    )
    parser.add_argument("--title", required=True)
    parser.add_argument("--slug")
    github_group = parser.add_mutually_exclusive_group()
    github_group.add_argument(
        "--create-github-issue",
        action="store_true",
        help="Create and link a new GitHub issue (id becomes epic-NNNN)",
    )
    github_group.add_argument(
        "--github-issue",
        type=int,
        help="Existing GitHub issue number to link (id becomes epic-NNNN)",
    )


def _add_new_issue_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--epic",
        required=True,
        help="Parent epic (e.g. 123 / epic-00123 / epic-local-00001)",
    )
    parser.add_argument("--title", required=True)
    parser.add_argument("--slug")
    github_group = parser.add_mutually_exclusive_group()
    github_group.add_argument(
        "--create-github-issue",
        action="store_true",
        help="Create and link a new GitHub issue (default behavior)",
    )
    github_group.add_argument(
        "--github-issue",
        type=int,
        help="Existing GitHub issue number to link (id becomes iss-NNNN)",
    )


def _add_new_artifact_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "artifact_type",
        metavar="type",
        help=(f"Artifact type: {', '.join(_artifact_types)}."),
    )
    scope_group = parser.add_mutually_exclusive_group(required=True)
    scope_group.add_argument("--initiative", help="Scope initiative (e.g. 123 / init-00123 / init-local-00001)")
    scope_group.add_argument("--epic", help="Scope epic (e.g. 123 / epic-00123 / epic-local-00001)")
    scope_group.add_argument("--issue", help="Scope issue (e.g. 123 / iss-00123 / iss-local-00001)")
    parser.add_argument("--title", required=True)
    parser.add_argument("--slug")


def _new_initiative_args(ns: argparse.Namespace) -> CommandArgs:
    return NewInitiativeArgs(
        title=str(ns.title),
        slug=getattr(ns, "slug", None),
        create_github_issue=bool(getattr(ns, "create_github_issue", False)),
        github_issue_number=getattr(ns, "github_issue", None),
    )


def _new_epic_args(ns: argparse.Namespace) -> CommandArgs:
    return NewEpicArgs(
        initiative_id=str(ns.initiative),
        title=str(ns.title),
        slug=getattr(ns, "slug", None),
        create_github_issue=bool(getattr(ns, "create_github_issue", False)),
        github_issue_number=getattr(ns, "github_issue", None),
    )


def _new_issue_args(ns: argparse.Namespace) -> CommandArgs:
    return NewIssueArgs(
        epic_id=str(ns.epic),
        title=str(ns.title),
        slug=getattr(ns, "slug", None),
        create_github_issue=bool(getattr(ns, "create_github_issue", False)),
        github_issue_number=getattr(ns, "github_issue", None),
    )


def _new_artifact_args(ns: argparse.Namespace) -> CommandArgs:
    initiative = getattr(ns, "initiative", None)
    epic = getattr(ns, "epic", None)
    issue = getattr(ns, "issue", None)
    if initiative is not None:
        scope_kind: Literal["initiative", "epic", "issue"] = "initiative"
        scope_node_id = initiative
    elif epic is not None:
        scope_kind = "epic"
        scope_node_id = epic
    elif issue is not None:
        scope_kind = "issue"
        scope_node_id = issue
    else:
        raise RuntimeError("scope is required")
    return NewArtifactArgs(
        artifact_type=str(ns.artifact_type),
        scope_node_id=str(scope_node_id),
        scope_kind=scope_kind,
        title=str(ns.title),
        slug=getattr(ns, "slug", None),
    )


def _run_new_initiative(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_new_initiative_args(args)

    result = use_cases.create_initiative(
        CreateNodeRequest(
            title=typed.title,
            slug=typed.slug,
            parent_id=None,
            github_mode="link_existing" if typed.github_issue_number is not None else "create",
            github_issue_number=typed.github_issue_number,
        )
    )
    text = render_new_node_text(result)
    if typed.github_issue_number is None:
        text = _prepend_stderr(
            text,
            "spec-dock: (info) creating GitHub issue via gh",
        )
    return CommandOutcome(exit_code=_post_sync_exit_code(result), text=text)


def _run_new_epic(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_new_epic_args(args)

    result = use_cases.create_epic(
        CreateNodeRequest(
            title=typed.title,
            slug=typed.slug,
            parent_id=typed.initiative_id,
            github_mode="link_existing" if typed.github_issue_number is not None else "create",
            github_issue_number=typed.github_issue_number,
        )
    )
    text = render_new_node_text(result)
    if typed.github_issue_number is None:
        text = _prepend_stderr(
            text,
            "spec-dock: (info) creating GitHub issue via gh",
        )
    return CommandOutcome(exit_code=_post_sync_exit_code(result), text=text)


def _run_new_issue(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_new_issue_args(args)

    result = use_cases.create_issue(
        CreateNodeRequest(
            title=typed.title,
            slug=typed.slug,
            parent_id=typed.epic_id,
            github_mode="link_existing" if typed.github_issue_number is not None else "create",
            github_issue_number=typed.github_issue_number,
        )
    )
    text = render_new_node_text(result)
    if typed.github_issue_number is None:
        text = _prepend_stderr(
            text,
            "spec-dock: (info) creating GitHub issue via gh",
        )
    return CommandOutcome(exit_code=_post_sync_exit_code(result), text=text)


def _run_new_artifact(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_new_artifact_args(args)
    result = use_cases.create_artifact_doc(
        CreateArtifactDocRequest(
            artifact_type=typed.artifact_type,  # type: ignore[arg-type]
            scope_node_id=typed.scope_node_id,
            scope_kind=typed.scope_kind,
            title=typed.title,
            slug=typed.slug,
        )
    )
    return CommandOutcome(exit_code=0, text=render_new_artifact_text(result))


def _prepend_stderr(text: CliText, line: str) -> CliText:
    return CliText(
        stdout_lines=list(text.stdout_lines),
        stderr_lines=[line, *list(text.stderr_lines)],
        warnings=list(text.warnings),
    )


def _post_sync_exit_code(result: CreateNodeResult) -> int:
    return 1 if result.post_sync is not None and result.post_sync.failed else 0


def _expect_new_initiative_args(args: CommandArgs) -> NewInitiativeArgs:
    if not isinstance(args, NewInitiativeArgs):
        raise RuntimeError("Invalid command args for new initiative")
    return args


def _expect_new_epic_args(args: CommandArgs) -> NewEpicArgs:
    if not isinstance(args, NewEpicArgs):
        raise RuntimeError("Invalid command args for new epic")
    return args


def _expect_new_issue_args(args: CommandArgs) -> NewIssueArgs:
    if not isinstance(args, NewIssueArgs):
        raise RuntimeError("Invalid command args for new issue")
    return args


def _expect_new_artifact_args(args: CommandArgs) -> NewArtifactArgs:
    if not isinstance(args, NewArtifactArgs):
        raise RuntimeError("Invalid command args for new artifact")
    return args
