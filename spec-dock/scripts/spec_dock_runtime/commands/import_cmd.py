from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from spec_dock_runtime.application.contracts import ImportNodeRequest, ImportNodeResult, UseCases
from spec_dock_runtime.commands.contracts import CommandArgs, CommandOutcome, CommandSpec
from spec_dock_runtime.commands.targets import parse_github_issue_target_ref
from spec_dock_runtime.presentation.cli_text import render_import_text

if TYPE_CHECKING:
    import argparse


@dataclass(frozen=True)
class ImportInitiativeArgs(CommandArgs):
    issue_number: int
    title: str
    slug: str | None
    target_repo_owner: str | None
    target_repo_name: str | None
    allow_foreign_url: bool


@dataclass(frozen=True)
class ImportEpicArgs(CommandArgs):
    issue_number: int
    title: str
    slug: str | None
    target_repo_owner: str | None
    target_repo_name: str | None
    allow_foreign_url: bool
    initiative_id: str | None


@dataclass(frozen=True)
class ImportIssueArgs(CommandArgs):
    issue_number: int
    title: str
    slug: str | None
    target_repo_owner: str | None
    target_repo_name: str | None
    allow_foreign_url: bool
    epic_id: str | None


def command_specs() -> dict[str, CommandSpec]:
    return {
        "import_initiative": CommandSpec(
            add_arguments=_add_import_initiative_arguments,
            args_factory=_import_initiative_args,
            run=_run_import_initiative,
        ),
        "import_epic": CommandSpec(
            add_arguments=_add_import_epic_arguments,
            args_factory=_import_epic_args,
            run=_run_import_epic,
        ),
        "import_issue": CommandSpec(
            add_arguments=_add_import_issue_arguments,
            args_factory=_import_issue_args,
            run=_run_import_issue,
        ),
    }


def _add_import_initiative_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "target",
        help="GitHub issue number (123 / #123) or GitHub issue URL (https://github.com/<owner>/<repo>/issues/123)",
    )
    parser.add_argument(
        "--allow-foreign-url",
        action="store_true",
        help=(
            "Retained for compatibility; foreign GitHub issue URLs are still rejected for "
            "initiative/epic/issue node identity import."
        ),
    )
    parser.add_argument("--title", required=True, help="spec-dock title to store (GitHub title is not imported)")
    parser.add_argument("--slug")


def _add_import_epic_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "target",
        help="GitHub issue number (123 / #123) or GitHub issue URL (https://github.com/<owner>/<repo>/issues/123)",
    )
    parser.add_argument(
        "--allow-foreign-url",
        action="store_true",
        help=(
            "Retained for compatibility; foreign GitHub issue URLs are still rejected for "
            "initiative/epic/issue node identity import."
        ),
    )
    parser.add_argument("--title", required=True, help="spec-dock title to store (GitHub title is not imported)")
    parser.add_argument("--slug")
    parser.add_argument(
        "--initiative",
        help="Parent initiative (e.g. 123 / init-00123 / init-local-00001). Omit to resolve from active.",
    )


def _add_import_issue_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "target",
        help="GitHub issue number (123 / #123) or GitHub issue URL (https://github.com/<owner>/<repo>/issues/123)",
    )
    parser.add_argument(
        "--allow-foreign-url",
        action="store_true",
        help=(
            "Retained for compatibility; foreign GitHub issue URLs are still rejected for "
            "initiative/epic/issue node identity import."
        ),
    )
    parser.add_argument("--title", required=True, help="spec-dock title to store (GitHub title is not imported)")
    parser.add_argument("--slug")
    parser.add_argument(
        "--epic",
        help="Parent epic (e.g. 123 / epic-00123 / epic-local-00001). Omit to resolve from active.",
    )


def _import_initiative_args(ns: argparse.Namespace) -> CommandArgs:
    target = parse_github_issue_target_ref(str(ns.target))
    return ImportInitiativeArgs(
        issue_number=target.issue_number,
        title=str(ns.title),
        slug=getattr(ns, "slug", None),
        target_repo_owner=target.repo_owner,
        target_repo_name=target.repo_name,
        allow_foreign_url=bool(getattr(ns, "allow_foreign_url", False)),
    )


def _import_epic_args(ns: argparse.Namespace) -> CommandArgs:
    target = parse_github_issue_target_ref(str(ns.target))
    return ImportEpicArgs(
        issue_number=target.issue_number,
        title=str(ns.title),
        slug=getattr(ns, "slug", None),
        target_repo_owner=target.repo_owner,
        target_repo_name=target.repo_name,
        allow_foreign_url=bool(getattr(ns, "allow_foreign_url", False)),
        initiative_id=getattr(ns, "initiative", None),
    )


def _import_issue_args(ns: argparse.Namespace) -> CommandArgs:
    target = parse_github_issue_target_ref(str(ns.target))
    return ImportIssueArgs(
        issue_number=target.issue_number,
        title=str(ns.title),
        slug=getattr(ns, "slug", None),
        target_repo_owner=target.repo_owner,
        target_repo_name=target.repo_name,
        allow_foreign_url=bool(getattr(ns, "allow_foreign_url", False)),
        epic_id=getattr(ns, "epic", None),
    )


def _run_import_initiative(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_import_initiative_args(args)
    result = use_cases.import_initiative(
        ImportNodeRequest(
            issue_number=typed.issue_number,
            title=typed.title,
            slug=typed.slug,
            parent_id=None,
            target_repo_owner=typed.target_repo_owner,
            target_repo_name=typed.target_repo_name,
            allow_foreign_url=typed.allow_foreign_url,
        )
    )
    return _import_outcome(result)


def _run_import_epic(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_import_epic_args(args)
    result = use_cases.import_epic(
        ImportNodeRequest(
            issue_number=typed.issue_number,
            title=typed.title,
            slug=typed.slug,
            parent_id=typed.initiative_id,
            target_repo_owner=typed.target_repo_owner,
            target_repo_name=typed.target_repo_name,
            allow_foreign_url=typed.allow_foreign_url,
        )
    )
    return _import_outcome(result)


def _run_import_issue(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    typed = _expect_import_issue_args(args)
    result = use_cases.import_issue(
        ImportNodeRequest(
            issue_number=typed.issue_number,
            title=typed.title,
            slug=typed.slug,
            parent_id=typed.epic_id,
            target_repo_owner=typed.target_repo_owner,
            target_repo_name=typed.target_repo_name,
            allow_foreign_url=typed.allow_foreign_url,
        )
    )
    return _import_outcome(result)


def _import_outcome(result: ImportNodeResult) -> CommandOutcome:
    exit_code = 0 if result.post_import_sync.artifact_failure is None else 1
    return CommandOutcome(exit_code=exit_code, text=render_import_text(result))


def _expect_import_initiative_args(args: CommandArgs) -> ImportInitiativeArgs:
    if not isinstance(args, ImportInitiativeArgs):
        raise RuntimeError("Invalid command args for import initiative")
    return args


def _expect_import_epic_args(args: CommandArgs) -> ImportEpicArgs:
    if not isinstance(args, ImportEpicArgs):
        raise RuntimeError("Invalid command args for import epic")
    return args


def _expect_import_issue_args(args: CommandArgs) -> ImportIssueArgs:
    if not isinstance(args, ImportIssueArgs):
        raise RuntimeError("Invalid command args for import issue")
    return args
