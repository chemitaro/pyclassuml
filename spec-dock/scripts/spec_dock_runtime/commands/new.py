from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Literal

from ..application.contracts import (
    CreateDiscussionDocRequest,
    CreateNodeRequest,
    UseCases,
)
from ..presentation.cli_text import render_new_doc_text, render_new_node_text
from ..presentation.contracts import CliText
from .contracts import CommandArgs, CommandOutcome, CommandSpec

_discussion_doc_types = ("adr", "disc", "research", "note")


@dataclass(frozen=True)
class NewInitiativeArgs(CommandArgs):
    title: str
    slug: str | None
    node_id: str | None
    create_github_issue: bool
    github_issue_number: int | None
    no_github: bool


@dataclass(frozen=True)
class NewEpicArgs(CommandArgs):
    initiative_id: str
    title: str
    slug: str | None
    node_id: str | None
    create_github_issue: bool
    github_issue_number: int | None
    no_github: bool


@dataclass(frozen=True)
class NewIssueArgs(CommandArgs):
    epic_id: str
    title: str
    slug: str | None
    node_id: str | None
    create_github_issue: bool
    github_issue_number: int | None
    no_github: bool


@dataclass(frozen=True)
class NewDocArgs(CommandArgs):
    doc_type: str
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
        "new_doc": CommandSpec(
            add_arguments=_add_new_doc_arguments,
            args_factory=_new_doc_args,
            run=_run_new_doc,
        ),
    }


def _add_new_initiative_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--title", required=True)
    parser.add_argument("--slug")
    parser.add_argument("--id")
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
    github_group.add_argument(
        "--no-github",
        action="store_true",
        help="Rejected contract: local-only initiative creation is no longer supported",
    )


def _add_new_epic_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--initiative",
        required=True,
        help="Parent initiative (e.g. 123 / init-00123 / init-local-00001)",
    )
    parser.add_argument("--title", required=True)
    parser.add_argument("--slug")
    parser.add_argument("--id")
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
    github_group.add_argument(
        "--no-github",
        action="store_true",
        help="Rejected contract: local-only epic creation is no longer supported",
    )


def _add_new_issue_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--epic",
        required=True,
        help="Parent epic (e.g. 123 / epic-00123 / epic-local-00001)",
    )
    parser.add_argument("--title", required=True)
    parser.add_argument("--slug")
    parser.add_argument("--id")
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
    github_group.add_argument(
        "--no-github",
        action="store_true",
        help="Rejected contract: local-only issue creation is no longer supported",
    )


def _add_new_doc_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("doc_type", choices=_discussion_doc_types)
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
        node_id=getattr(ns, "id", None),
        create_github_issue=bool(getattr(ns, "create_github_issue", False)),
        github_issue_number=getattr(ns, "github_issue", None),
        no_github=bool(getattr(ns, "no_github", False)),
    )


def _new_epic_args(ns: argparse.Namespace) -> CommandArgs:
    return NewEpicArgs(
        initiative_id=str(ns.initiative),
        title=str(ns.title),
        slug=getattr(ns, "slug", None),
        node_id=getattr(ns, "id", None),
        create_github_issue=bool(getattr(ns, "create_github_issue", False)),
        github_issue_number=getattr(ns, "github_issue", None),
        no_github=bool(getattr(ns, "no_github", False)),
    )


def _new_issue_args(ns: argparse.Namespace) -> CommandArgs:
    return NewIssueArgs(
        epic_id=str(ns.epic),
        title=str(ns.title),
        slug=getattr(ns, "slug", None),
        node_id=getattr(ns, "id", None),
        create_github_issue=bool(getattr(ns, "create_github_issue", False)),
        github_issue_number=getattr(ns, "github_issue", None),
        no_github=bool(getattr(ns, "no_github", False)),
    )


def _new_doc_args(ns: argparse.Namespace) -> CommandArgs:
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
    return NewDocArgs(
        doc_type=str(ns.doc_type),
        scope_node_id=str(scope_node_id),
        scope_kind=scope_kind,
        title=str(ns.title),
        slug=getattr(ns, "slug", None),
    )


def _run_new_initiative(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_new_initiative_args(args)
    if typed.no_github:
        return _github_mandatory_error("initiative")
    use_github = True

    result = use_cases.create_initiative(
        CreateNodeRequest(
            title=typed.title,
            slug=typed.slug,
            parent_id=None,
            requested_node_id=typed.node_id,
            github_mode="link_existing" if typed.github_issue_number is not None else "create",
            github_issue_number=typed.github_issue_number,
        )
    )
    text = render_new_node_text(result)
    if use_github and typed.github_issue_number is None:
        text = _prepend_stderr(
            text,
            "spec-dock: (info) creating GitHub issue via gh",
        )
    return CommandOutcome(exit_code=0, text=text)


def _run_new_epic(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_new_epic_args(args)
    if typed.no_github:
        return _github_mandatory_error("epic")
    use_github = True

    result = use_cases.create_epic(
        CreateNodeRequest(
            title=typed.title,
            slug=typed.slug,
            parent_id=typed.initiative_id,
            requested_node_id=typed.node_id,
            github_mode="link_existing" if typed.github_issue_number is not None else "create",
            github_issue_number=typed.github_issue_number,
        )
    )
    text = render_new_node_text(result)
    if use_github and typed.github_issue_number is None:
        text = _prepend_stderr(
            text,
            "spec-dock: (info) creating GitHub issue via gh",
        )
    return CommandOutcome(exit_code=0, text=text)


def _run_new_issue(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_new_issue_args(args)
    if typed.no_github:
        return _github_mandatory_error("issue")

    result = use_cases.create_issue(
        CreateNodeRequest(
            title=typed.title,
            slug=typed.slug,
            parent_id=typed.epic_id,
            requested_node_id=typed.node_id,
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
    return CommandOutcome(exit_code=0, text=text)


def _run_new_doc(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_new_doc_args(args)
    result = use_cases.create_discussion_doc(
        CreateDiscussionDocRequest(
            doc_type=typed.doc_type,  # type: ignore[arg-type]
            scope_node_id=typed.scope_node_id,
            scope_kind=typed.scope_kind,
            title=typed.title,
            slug=typed.slug,
        )
    )
    return CommandOutcome(exit_code=0, text=render_new_doc_text(result))


def _prepend_stderr(text: CliText, line: str) -> CliText:
    return CliText(
        stdout_lines=list(text.stdout_lines),
        stderr_lines=[line, *list(text.stderr_lines)],
        warnings=list(text.warnings),
    )


def _command_error(message: str) -> CommandOutcome:
    return CommandOutcome(
        exit_code=1,
        text=CliText(stdout_lines=[], stderr_lines=[f"error: {message}"], warnings=[]),
    )


def _github_mandatory_error(kind: Literal["initiative", "epic", "issue"]) -> CommandOutcome:
    return _command_error(
        f"'--no-github' is not supported for {kind}; GitHub linkage is mandatory."
    )


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


def _expect_new_doc_args(args: CommandArgs) -> NewDocArgs:
    if not isinstance(args, NewDocArgs):
        raise RuntimeError("Invalid command args for new doc")
    return args
