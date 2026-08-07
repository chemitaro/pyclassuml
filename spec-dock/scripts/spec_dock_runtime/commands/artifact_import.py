from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from spec_dock_runtime.application.contracts import (
    ArtifactImportError,
    ArtifactImportRequest,
    FileArtifactImportError,
    FileArtifactImportRequest,
    UseCases,
)
from spec_dock_runtime.commands.contracts import CommandArgs, CommandOutcome, CommandSpec
from spec_dock_runtime.presentation.cli_text import (
    render_artifact_import_error_json,
    render_artifact_import_error_text,
    render_artifact_import_json,
    render_artifact_import_text,
    render_file_artifact_import_error_json,
    render_file_artifact_import_error_text,
    render_file_artifact_import_json,
    render_file_artifact_import_text,
)

if TYPE_CHECKING:
    import argparse


@dataclass(frozen=True)
class ArtifactImportChatGptOutputArgs(CommandArgs):
    scope_node_id: str
    scope_kind: Literal["initiative", "epic", "issue"]
    source_path: str
    title: str
    slug: str | None
    json: bool


@dataclass(frozen=True)
class ArtifactImportFileArgs(CommandArgs):
    target_kind: Literal["root", "initiative", "epic", "issue"]
    target_value: str | None
    source_path: str
    json: bool


def command_specs() -> dict[str, CommandSpec]:
    return {
        "artifact_import_chatgpt_output": CommandSpec(
            add_arguments=_add_arguments,
            args_factory=_args_factory,
            run=_run,
        ),
        "artifact_import_file": CommandSpec(
            add_arguments=_add_file_arguments,
            args_factory=_file_args_factory,
            run=_run_file,
        ),
    }


def _add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.description = "Import opaque Markdown bytes from an approved Workbench as a blank Artifact."
    scope_group = parser.add_mutually_exclusive_group(required=True)
    scope_group.add_argument("--initiative", help="Destination initiative scope.")
    scope_group.add_argument("--epic", help="Destination epic scope.")
    scope_group.add_argument("--issue", help="Destination issue scope.")
    parser.add_argument("--file", required=True, help="Source .md file under an approved Workbench.")
    parser.add_argument("--title", required=True, help="Title used only to derive the destination slug.")
    parser.add_argument("--slug", help="Optional explicit destination slug component.")
    parser.add_argument("--json", action="store_true", help="Emit content-free agent-oriented JSON output.")


def _args_factory(ns: argparse.Namespace) -> CommandArgs:
    for scope_kind in ("initiative", "epic", "issue"):
        value = getattr(ns, scope_kind, None)
        if value is not None:
            return ArtifactImportChatGptOutputArgs(
                scope_node_id=str(value),
                scope_kind=scope_kind,  # type: ignore[arg-type]
                source_path=str(ns.file),
                title=str(ns.title),
                slug=getattr(ns, "slug", None),
                json=bool(getattr(ns, "json", False)),
            )
    raise RuntimeError("scope is required")


def _run(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    if not isinstance(args, ArtifactImportChatGptOutputArgs):
        raise RuntimeError("Invalid command args for artifact import chatgpt-output")
    try:
        result = use_cases.import_artifact(
            ArtifactImportRequest(
                import_kind="chatgpt-output",
                scope_node_id=args.scope_node_id,
                scope_kind=args.scope_kind,
                source_path=Path(args.source_path),
                title=args.title,
                slug=args.slug,
            )
        )
    except ArtifactImportError as error:
        renderer = render_artifact_import_error_json if args.json else render_artifact_import_error_text
        return CommandOutcome(exit_code=1, text=renderer(error))
    except Exception:
        runtime_error = ArtifactImportError(code="runtime_failed", cleanup_state="not_created")
        renderer = render_artifact_import_error_json if args.json else render_artifact_import_error_text
        return CommandOutcome(exit_code=1, text=renderer(runtime_error))
    renderer = render_artifact_import_json if args.json else render_artifact_import_text
    return CommandOutcome(exit_code=0, text=renderer(result))


def _add_file_arguments(parser: argparse.ArgumentParser) -> None:
    parser.description = "Import one explicit regular file as opaque generic evidence."
    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument("--root", action="store_true", help="Destination SpecDock root.")
    target_group.add_argument("--initiative", help="Destination initiative.")
    target_group.add_argument("--epic", help="Destination epic.")
    target_group.add_argument("--issue", help="Destination issue.")
    parser.add_argument("--file", required=True, help="Explicit source file.")
    parser.add_argument("--json", action="store_true", help="Emit privacy-safe JSON output.")


def _file_args_factory(ns: argparse.Namespace) -> CommandArgs:
    if bool(getattr(ns, "root", False)):
        return ArtifactImportFileArgs(
            target_kind="root",
            target_value=None,
            source_path=str(ns.file),
            json=bool(getattr(ns, "json", False)),
        )
    for target_kind in ("initiative", "epic", "issue"):
        value = getattr(ns, target_kind, None)
        if value is not None:
            return ArtifactImportFileArgs(
                target_kind=target_kind,  # type: ignore[arg-type]
                target_value=str(value),
                source_path=str(ns.file),
                json=bool(getattr(ns, "json", False)),
            )
    raise RuntimeError("target is required")


def _run_file(args: CommandArgs, use_cases: UseCases) -> CommandOutcome:
    if not isinstance(args, ArtifactImportFileArgs):
        raise RuntimeError("Invalid command args for artifact import file")
    try:
        result = use_cases.import_file_artifact(
            FileArtifactImportRequest(
                target_kind=args.target_kind,
                target_value=args.target_value,
                source_path=Path(args.source_path),
            )
        )
    except FileArtifactImportError as error:
        renderer = render_file_artifact_import_error_json if args.json else render_file_artifact_import_error_text
        return CommandOutcome(exit_code=1, text=renderer(error))
    except Exception:
        raise RuntimeError("artifact import file runtime contract violation") from None
    renderer = render_file_artifact_import_json if args.json else render_file_artifact_import_text
    return CommandOutcome(exit_code=0, text=renderer(result))
