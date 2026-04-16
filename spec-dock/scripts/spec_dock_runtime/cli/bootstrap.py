from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..application.check_deps import check_deps as application_check_deps
from ..application.close_node import close_node as application_close_node
from ..application.create_node import create_discussion_doc as application_create_discussion_doc
from ..application.create_node import create_epic as application_create_epic
from ..application.create_node import create_initiative as application_create_initiative
from ..application.create_node import create_issue as application_create_issue
from ..application.delete_node import delete_node as application_delete_node
from ..application.doctor import doctor as application_doctor
from ..application.contracts import UseCases
from ..application.import_node import import_epic as application_import_epic
from ..application.import_node import import_initiative as application_import_initiative
from ..application.import_node import import_issue as application_import_issue
from ..application.mutate_deps import mutate_deps as application_mutate_deps
from ..application.ports import Ports
from ..application.set_active import clear_active as application_clear_active
from ..application.set_active import set_active as application_set_active
from ..application.set_active import show_active as application_show_active
from ..application.sync_state import sync as application_sync
from ..application.validate_tree import validate_tree as application_validate_tree
from ..infra import active_store as infra_active_store
from ..infra import artifact_writer as infra_artifact_writer
from ..infra import clock as infra_clock
from ..infra import deps_reader as infra_deps_reader
from ..infra import derived_state_reader as infra_derived_state_reader
from ..infra import fs_repo as infra_fs_repo
from ..infra import git_cli as infra_git_cli
from ..infra import github_cli as infra_github_cli
from ..infra import json_store as infra_json_store
from ..infra import template_scaffolder as infra_template_scaffolder


@dataclass(frozen=True)
class BootstrapContext:
    use_cases: UseCases


@dataclass(frozen=True)
class _NodeReader:
    specdock_dir: Path

    def load_node_records(self):
        return infra_fs_repo.load_node_records(self.specdock_dir)


@dataclass(frozen=True)
class _NodeRepository:
    def load_node_records(self, specdock_dir: Path):
        return infra_fs_repo.load_node_records(specdock_dir)

    def write_meta(self, dest_dir: Path, record):
        infra_fs_repo.write_meta(dest_dir, record)

    def add_issue_dependency(self, meta_path: Path, to_id: str) -> None:
        infra_fs_repo.add_issue_dependency(meta_path, to_id)

    def remove_issue_dependency(self, meta_path: Path, to_id: str, *, matching_refs: list[object] | None = None) -> None:
        infra_fs_repo.remove_issue_dependency(meta_path, to_id, matching_refs=matching_refs)

    def delete_tree(self, node_path: Path) -> None:
        infra_fs_repo.delete_tree(node_path)

    def backfill_github_repo_scope(self, meta_path: Path, *, repo_owner: str, repo_name: str) -> bool:
        return infra_fs_repo.backfill_github_repo_scope(
            meta_path,
            repo_owner=repo_owner,
            repo_name=repo_name,
        )


@dataclass(frozen=True)
class _TemplateScaffolder:
    def render_text(self, text: str, replacements: dict[str, str]) -> str:
        return infra_template_scaffolder.render_text(text, replacements)

    def load_template_text(self, src_path: Path) -> str:
        return infra_template_scaffolder.load_template_text(src_path)

    def copy_scaffolded_tree(self, src_dir: Path, dest_dir: Path, replacements: dict[str, str]):
        return infra_template_scaffolder.copy_scaffolded_tree(src_dir, dest_dir, replacements)

    def write_text(self, dest_path: Path, text: str) -> None:
        infra_template_scaffolder.write_text(dest_path, text)


@dataclass(frozen=True)
class _DerivedStateReader:
    def load_cached_issue_status_by_id(self, specdock_dir: Path) -> dict[str, str]:
        return infra_derived_state_reader.load_cached_issue_status_by_id(specdock_dir)

    def load_cached_issue_last_sync_at_by_id(self, specdock_dir: Path) -> dict[str, str | None]:
        return infra_derived_state_reader.load_cached_issue_last_sync_at_by_id(specdock_dir)


@dataclass(frozen=True)
class _IssueGateway:
    def issue_index(self, repo_root: Path, *, limit: int):
        return infra_github_cli.issue_index(repo_root, limit=limit)

    def issue_create(self, repo_root: Path, title: str, body: str) -> int:
        return infra_github_cli.issue_create(repo_root, title=title, body=body)

    def issue_view_minimal(self, repo_root: Path, issue_number: int, *, repo_slug: str | None = None):
        return infra_github_cli.issue_view_minimal(
            repo_root,
            issue_number=issue_number,
            repo_slug=repo_slug,
        )

    def issue_view_snapshot(self, repo_root: Path, issue_number: int, *, repo_slug: str | None = None):
        return infra_github_cli.issue_view_snapshot(
            repo_root,
            issue_number=issue_number,
            repo_slug=repo_slug,
        )

    def issue_close(self, repo_root: Path, issue_number: int, *, repo_slug: str | None = None):
        return infra_github_cli.issue_close(
            repo_root,
            issue_number=issue_number,
            repo_slug=repo_slug,
        )


@dataclass(frozen=True)
class _ActiveStateStore:
    def load_active_manifest(self, specdock_dir: Path):
        return infra_active_store.load_active_manifest(specdock_dir)

    def load_active_manifest_no_migrate(self, specdock_dir: Path):
        return infra_active_store.load_active_manifest_no_migrate(specdock_dir)

    def load_active_issue_id(self, specdock_dir: Path):
        return infra_active_store.load_active_issue_id(specdock_dir)

    def write_active_manifest(self, specdock_dir: Path, manifest):
        return infra_active_store.write_active_manifest(specdock_dir, manifest)

    def apply_active_pointers(self, specdock_dir: Path, manifest, rendered_context_pack: str) -> None:
        infra_active_store.apply_active_pointers(specdock_dir, manifest, rendered_context_pack)

    def patch_agent_state_active_fields(self, specdock_dir: Path, manifest) -> None:
        infra_active_store.patch_agent_state_active_fields(specdock_dir, manifest)

    def snapshot_current_state(self, specdock_dir: Path):
        return infra_active_store.snapshot_current_state(specdock_dir)

    def restore_previous_state(self, specdock_dir: Path, snapshot) -> None:
        infra_active_store.restore_previous_state(specdock_dir, snapshot)


@dataclass(frozen=True)
class _DepsTopologyReader:
    def load_issue_depends_on_map(self, specdock_dir: Path, graph):
        return infra_deps_reader.load_issue_depends_on_map(specdock_dir, graph)

    def load_direct_dependency_resolutions(self, specdock_dir: Path, graph, src_id: str):
        return infra_deps_reader.load_direct_dependency_resolutions(specdock_dir, graph, src_id)


@dataclass(frozen=True)
class _GitGateway:
    def require_clean_working_tree(self, repo_root: Path) -> None:
        infra_git_cli.require_clean_working_tree(repo_root)

    def current_branch_or_none(self, repo_root: Path):
        return infra_git_cli.current_branch_or_none(repo_root)

    def local_branch_exists(self, repo_root: Path, branch: str) -> bool:
        return infra_git_cli.local_branch_exists(repo_root, branch)

    def checkout_branch(self, repo_root: Path, branch: str) -> None:
        infra_git_cli.checkout_branch(repo_root, branch)

    def create_and_checkout_branch(self, repo_root: Path, branch: str) -> None:
        infra_git_cli.create_and_checkout_branch(repo_root, branch)

    def check_ref_format_branch(self, repo_root: Path, branch: str) -> bool:
        return infra_git_cli.check_ref_format_branch(repo_root, branch)

    def origin_github_repo_slug(self, repo_root: Path) -> str | None:
        return infra_git_cli.origin_github_repo_slug(repo_root)


@dataclass(frozen=True)
class _JsonStore:
    def load_json(self, path: Path):
        return infra_json_store.load_json(path)

    def write_json(self, path: Path, data: object) -> None:
        infra_json_store.write_json(path, data)


@dataclass(frozen=True)
class _Clock:
    def now_iso(self) -> str:
        return infra_clock.now_iso()

    def today(self) -> str:
        return infra_clock.today()


@dataclass(frozen=True)
class _ArtifactWriter:
    def write(self, specdock_dir: Path, bundle):
        return infra_artifact_writer.write(specdock_dir, bundle)


def build_runtime(specdock_dir: Path, *, repo_root: Path | None = None) -> BootstrapContext:
    ports = Ports(
        node_reader=_NodeReader(specdock_dir=specdock_dir),
        repo_root=repo_root if repo_root is not None else specdock_dir.parent,
        specdock_dir=specdock_dir,
        node_repo=_NodeRepository(),
        template_scaffolder=_TemplateScaffolder(),
        derived_state_reader=_DerivedStateReader(),
        issue_gateway=_IssueGateway(),
        active_state_store=_ActiveStateStore(),
        deps_topology_reader=_DepsTopologyReader(),
        git_gateway=_GitGateway(),
        json_store=_JsonStore(),
        clock=_Clock(),
        artifact_writer=_ArtifactWriter(),
    )
    use_cases = UseCases(
        create_initiative=lambda req: application_create_initiative(req, ports),
        create_epic=lambda req: application_create_epic(req, ports),
        create_issue=lambda req: application_create_issue(req, ports),
        create_discussion_doc=lambda req: application_create_discussion_doc(req, ports),
        import_initiative=lambda req: application_import_initiative(req, ports),
        import_epic=lambda req: application_import_epic(req, ports),
        import_issue=lambda req: application_import_issue(req, ports),
        set_active=lambda req: application_set_active(req, ports),
        show_active=lambda req: application_show_active(req, ports),
        clear_active=lambda req: application_clear_active(req, ports),
        sync=lambda req: application_sync(req, ports),
        check_deps=lambda req: application_check_deps(req, ports),
        mutate_deps=lambda req: application_mutate_deps(req, ports),
        delete_node=lambda req: application_delete_node(req, ports),
        close_node=lambda req: application_close_node(req, ports),
        validate_tree=lambda req: application_validate_tree(req, ports),
        doctor=lambda req: application_doctor(req, ports),
    )
    return BootstrapContext(use_cases=use_cases)
