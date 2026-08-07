from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from spec_dock_runtime.application.assurance import (
    classify_assurance as application_classify_assurance,
    compose_assurance as application_compose_assurance,
    show_assurance as application_show_assurance,
    verify_assurance as application_verify_assurance,
)
from spec_dock_runtime.application.check_deps import check_deps as application_check_deps
from spec_dock_runtime.application.close_node import close_node as application_close_node
from spec_dock_runtime.application.contracts import SyncRequest, UseCases, ValidateTreeRequest
from spec_dock_runtime.application.create_artifact_doc import create_artifact_doc as application_create_artifact_doc
from spec_dock_runtime.application.create_node import (
    create_epic as application_create_epic,
    create_initiative as application_create_initiative,
    create_issue as application_create_issue,
)
from spec_dock_runtime.application.delete_node import delete_node as application_delete_node
from spec_dock_runtime.application.doctor import doctor as application_doctor
from spec_dock_runtime.application.import_artifact import import_artifact as application_import_artifact
from spec_dock_runtime.application.import_file_artifact import import_file_artifact as application_import_file_artifact
from spec_dock_runtime.application.import_node import (
    import_epic as application_import_epic,
    import_initiative as application_import_initiative,
    import_issue as application_import_issue,
)
from spec_dock_runtime.application.issue_lifecycle import (
    issue_finish as application_issue_finish,
    issue_start as application_issue_start,
)
from spec_dock_runtime.application.issue_planning import (
    run_issue_planning_apply as application_run_issue_planning_apply,
    run_issue_planning_create as application_run_issue_planning_create,
    run_issue_planning_review as application_run_issue_planning_review,
    run_issue_planning_revise as application_run_issue_planning_revise,
)
from spec_dock_runtime.application.mutate_deps import mutate_deps as application_mutate_deps
from spec_dock_runtime.application.ports import (
    IssuePlanningApplyOutputRejected,
    IssuePlanningCandidateArchiveRejected,
    IssuePlanningCandidateBuildFailed,
    IssuePlanningCandidateCollision,
    IssuePlanningCandidateOutputRejected,
    IssuePlanningCandidatePublicationFailed,
    IssuePlanningDependencies,
    Ports,
)
from spec_dock_runtime.application.set_active import (
    clear_active as application_clear_active,
    set_active as application_set_active,
    show_active as application_show_active,
)
from spec_dock_runtime.application.sync_state import sync as application_sync
from spec_dock_runtime.application.validate_tree import validate_tree as application_validate_tree
from spec_dock_runtime.application.workbench import workbench_copy as application_workbench_copy
from spec_dock_runtime.application.workflow import (
    workflow_next as application_workflow_next,
    workflow_status as application_workflow_status,
)
from spec_dock_runtime.application.worktree import (
    worktree_create as application_worktree_create,
    worktree_list as application_worktree_list,
    worktree_remove as application_worktree_remove,
    worktree_show as application_worktree_show,
)
from spec_dock_runtime.domain.models import SpecNodeKind, SpecNodeSeed
from spec_dock_runtime.domain.tree import build_graph
from spec_dock_runtime.infra import (
    active_store as infra_active_store,
    artifact_store as infra_artifact_store,
    artifact_writer as infra_artifact_writer,
    assurance_store as infra_assurance_store,
    clock as infra_clock,
    deps_reader as infra_deps_reader,
    derived_state_reader as infra_derived_state_reader,
    fs_cli as infra_fs_cli,
    fs_repo as infra_fs_repo,
    git_cli as infra_git_cli,
    github_capability_cli as infra_github_capability_cli,
    github_cli as infra_github_cli,
    issue_planning_apply as infra_issue_planning_apply,
    issue_planning_candidate as infra_issue_planning_candidate,
    issue_planning_chatgpt as infra_issue_planning_chatgpt,
    issue_planning_review as infra_issue_planning_review,
    json_store as infra_json_store,
    make_cli as infra_make_cli,
    runbook_store as infra_runbook_store,
    template_scaffolder as infra_template_scaffolder,
)
from spec_dock_runtime.infra.binary_artifact_publisher import FilesystemBinaryArtifactPublisher

if TYPE_CHECKING:
    from spec_dock_runtime.domain.models import SpecGraph
    from spec_dock_runtime.infra.contracts import StoredMetaRecord


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

    def remove_issue_dependency(
        self, meta_path: Path, to_id: str, *, matching_refs: list[object] | None = None
    ) -> None:
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

    def load_node_dependency_resolutions(self, specdock_dir: Path, graph):
        return infra_deps_reader.load_node_dependency_resolutions(specdock_dir, graph)

    def build_candidate_issue_depends_on_map(
        self,
        graph,
        issue_depends_on_map: dict[str, list[str]],
        *,
        from_node_id: str,
        to_node_id: str,
    ):
        return infra_deps_reader.build_candidate_issue_depends_on_map(
            graph,
            issue_depends_on_map,
            from_node_id=from_node_id,
            to_node_id=to_node_id,
        )


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

    def worktree_list(self, repo_root: Path):
        return infra_git_cli.worktree_list(repo_root)

    def add_worktree_with_new_branch(self, repo_root: Path, *, path: Path, branch: str) -> None:
        infra_git_cli.add_worktree_with_new_branch(repo_root, path=path, branch=branch)

    def remove_worktree(self, repo_root: Path, *, path: Path, force: bool) -> None:
        infra_git_cli.remove_worktree(repo_root, path=path, force=force)


@dataclass(frozen=True)
class _GitHubCapabilityGateway:
    def probe(self, request):
        return infra_github_capability_cli.GitHubCapabilityCliGateway().probe(request)


@dataclass(frozen=True)
class _BootstrapGateway:
    def run_make_init_if_available(self, worktree_path: Path):
        return infra_make_cli.run_make_init_if_available(worktree_path)


@dataclass(frozen=True)
class _FilesystemGateway:
    def path_exists(self, path: Path) -> bool:
        return infra_fs_cli.path_exists(path)

    def remove_tree(self, path: Path) -> None:
        infra_fs_cli.remove_tree(path)

    def remove_target(self, path: Path) -> None:
        infra_fs_cli.remove_target(path)

    def path_kind(self, path: Path) -> str:
        return infra_fs_cli.path_kind(path)

    def guard_workbench_ancestry(self, root: Path, endpoint: Path, *, allow_missing_leaf: bool = False) -> None:
        infra_fs_cli.guard_workbench_ancestry(root, endpoint, allow_missing_leaf=allow_missing_leaf)

    def guard_workbench_inventory(self, specdock_dir: Path) -> None:
        infra_fs_cli.guard_workbench_inventory(specdock_dir)

    def copy_workbench(self, source: Path, destination: Path) -> None:
        infra_fs_cli.copy_workbench(source, destination)


@dataclass(frozen=True)
class _EnvironmentGateway:
    def getenv(self, name: str) -> str | None:
        return os.environ.get(name)


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
class _IssuePlanningGateway:
    def validate_candidate_output_directory(self, output_dir: Path, repo_root: Path):
        try:
            return infra_issue_planning_candidate.validate_candidate_output_directory(output_dir, repo_root)
        except infra_issue_planning_candidate.CandidateOutputRejected as error:
            raise IssuePlanningCandidateOutputRejected(str(error)) from error

    def load_verified_issue_candidate(self, candidate_path: Path, repo_root: Path):
        try:
            return infra_issue_planning_candidate.load_verified_issue_candidate(candidate_path, repo_root)
        except infra_issue_planning_candidate.CandidateArchiveRejected as error:
            raise IssuePlanningCandidateArchiveRejected(error.findings) from error

    def load_validated_issue_authoring_payload(
        self,
        snapshot: object,
        *,
        expected_companion_path: str,
        repo_root: Path,
    ):
        try:
            return infra_issue_planning_candidate.load_validated_issue_authoring_payload(
                cast("Any", snapshot),
                expected_companion_path=expected_companion_path,
                repo_root=repo_root,
            )
        except infra_issue_planning_candidate.CandidateArchiveRejected as error:
            raise IssuePlanningCandidateArchiveRejected(error.findings) from error

    def build_and_publish_candidate(self, **kwargs: Any):
        try:
            return infra_issue_planning_candidate.build_and_publish_candidate(**kwargs)
        except infra_issue_planning_candidate.CandidateCollision as error:
            raise IssuePlanningCandidateCollision(str(error)) from error
        except infra_issue_planning_candidate.CandidateArchiveRejected as error:
            raise IssuePlanningCandidateArchiveRejected(error.findings) from error
        except infra_issue_planning_candidate.CandidateBuildFailed as error:
            raise IssuePlanningCandidateBuildFailed(str(error)) from error
        except infra_issue_planning_candidate.CandidatePublicationFailed as error:
            raise IssuePlanningCandidatePublicationFailed(str(error)) from error
        except infra_issue_planning_candidate.CandidateOutputRejected as error:
            raise IssuePlanningCandidateOutputRejected(str(error)) from error

    def open_safe_directory_descriptor(self, path: Path) -> int:
        try:
            return infra_issue_planning_candidate.open_safe_directory_descriptor(path)
        except infra_issue_planning_candidate.CandidateArchiveRejected as error:
            raise IssuePlanningCandidateArchiveRejected(error.findings) from error

    def read_bounded_regular_file(self, path: Path, *, max_bytes: int) -> bytes:
        return infra_issue_planning_candidate.read_bounded_regular_file(path, max_bytes=max_bytes)

    def read_bounded_regular_file_at(
        self,
        root_descriptor: int,
        relative_path: str,
        *,
        max_bytes: int,
    ) -> bytes:
        try:
            return infra_issue_planning_candidate.read_bounded_regular_file_at(
                root_descriptor,
                relative_path,
                max_bytes=max_bytes,
            )
        except infra_issue_planning_candidate.CandidateArchiveRejected as error:
            raise IssuePlanningCandidateArchiveRejected(error.findings) from error

    def read_external_review_result(self, path: Path, **kwargs: Any) -> bytes:
        return infra_issue_planning_review.read_external_review_result(path, **kwargs)

    def publish_planning_review_evidence(self, **kwargs: Any):
        try:
            return infra_issue_planning_review.publish_planning_review_evidence(**kwargs)
        except infra_issue_planning_candidate.CandidateOutputRejected as error:
            raise IssuePlanningCandidateOutputRejected(str(error)) from error

    def load_expected_planning_targets(
        self,
        repo_root: Path,
        expected_head: str,
        canonical_target_paths: tuple[str, str, str],
    ):
        return infra_issue_planning_apply.load_expected_planning_targets(
            repo_root,
            expected_head,
            canonical_target_paths,
        )

    def planning_apply_resume_available(self, operation, *, output_guard) -> bool:
        try:
            return infra_issue_planning_apply.planning_apply_resume_available(
                cast("Any", operation),
                output_guard=output_guard,
            )
        except infra_issue_planning_apply.PlanningApplyOutputRejected as error:
            raise IssuePlanningApplyOutputRejected(str(error)) from error

    def create_planning_apply_operation(self, **kwargs: Any):
        return infra_issue_planning_apply.PlanningApplyOperation.create(**kwargs)


@dataclass(frozen=True)
class _ArtifactWriter:
    def write(self, specdock_dir: Path, bundle):
        return infra_artifact_writer.write(specdock_dir, bundle)


def _planning_node_seed(record: StoredMetaRecord) -> SpecNodeSeed:
    return SpecNodeSeed(
        kind=cast("SpecNodeKind", record.kind),
        id=record.id,
        title=record.title,
        slug=record.slug,
        path=Path(record.path),
        meta_path=Path(record.meta_path),
        parent_id=record.parent_id,
        initiative_id=record.initiative_id,
        epic_id=record.epic_id,
        github_issue_number=record.github_issue_number,
        github_repo_owner=record.github_repo_owner,
        github_repo_name=record.github_repo_name,
    )


def build_runtime(specdock_dir: Path, *, repo_root: Path | None = None) -> BootstrapContext:
    resolved_repo_root = repo_root if repo_root is not None else specdock_dir.parent
    binary_artifact_publisher = FilesystemBinaryArtifactPublisher()
    issue_planning_dependencies = IssuePlanningDependencies(
        clock=_Clock(),
        gateway=_IssuePlanningGateway(),
    )
    ports = Ports(
        node_reader=_NodeReader(specdock_dir=specdock_dir),
        repo_root=resolved_repo_root,
        specdock_dir=specdock_dir,
        node_repo=_NodeRepository(),
        template_scaffolder=_TemplateScaffolder(),
        derived_state_reader=_DerivedStateReader(),
        issue_gateway=_IssueGateway(),
        active_state_store=_ActiveStateStore(),
        deps_topology_reader=_DepsTopologyReader(),
        git_gateway=_GitGateway(),
        github_capability_gateway=_GitHubCapabilityGateway(),
        bootstrap_gateway=_BootstrapGateway(),
        environment_gateway=_EnvironmentGateway(),
        filesystem_gateway=_FilesystemGateway(),
        json_store=_JsonStore(),
        clock=issue_planning_dependencies.clock,
        artifact_writer=_ArtifactWriter(),
        workbench_source_guard=binary_artifact_publisher,
        binary_artifact_publisher=binary_artifact_publisher,
        issue_planning=issue_planning_dependencies,
        explicit_file_source_guard=binary_artifact_publisher,
        explicit_file_artifact_publisher=binary_artifact_publisher,
    )
    assurance_store = infra_assurance_store.AssuranceStore(resolved_repo_root)
    artifact_store = infra_artifact_store.ArtifactStore(resolved_repo_root)
    runbook_store = infra_runbook_store.RunbookStore(resolved_repo_root)

    def load_planning_state() -> tuple[tuple[StoredMetaRecord, ...], SpecGraph]:
        records = tuple(ports.node_reader.load_node_records())
        return records, build_graph([_planning_node_seed(record) for record in records])

    def planning_create(request):
        records, graph = load_planning_state()
        return application_run_issue_planning_create(
            request=request,
            records=records,
            repo_root=resolved_repo_root,
            dependencies=issue_planning_dependencies,
            repo_slug_resolver=infra_issue_planning_chatgpt.resolve_issue_planning_github_repository,
            backend_invoker=infra_issue_planning_chatgpt.invoke_issue_planning_chatgpt,
            dependency_loader=lambda issue_id: infra_deps_reader.load_direct_dependency_resolutions(
                specdock_dir,
                graph,
                issue_id,
            ),
        )

    def planning_review(request):
        records, _graph = load_planning_state()
        return application_run_issue_planning_review(
            request=request,
            records=records,
            repo_root=resolved_repo_root,
            dependencies=issue_planning_dependencies,
            repo_slug_resolver=infra_issue_planning_chatgpt.resolve_issue_planning_github_repository,
            backend_invoker=infra_issue_planning_chatgpt.invoke_issue_planning_chatgpt,
        )

    def planning_revise(request):
        records, _graph = load_planning_state()
        return application_run_issue_planning_revise(
            request=request,
            review_evidence=None,
            records=records,
            repo_root=resolved_repo_root,
            dependencies=issue_planning_dependencies,
            repo_slug_resolver=infra_issue_planning_chatgpt.resolve_issue_planning_github_repository,
            backend_invoker=infra_issue_planning_chatgpt.invoke_issue_planning_chatgpt,
        )

    def planning_apply(request):
        records, _graph = load_planning_state()
        return application_run_issue_planning_apply(
            request=request,
            records=records,
            repo_root=resolved_repo_root,
            dependencies=issue_planning_dependencies,
            repo_slug_resolver=infra_issue_planning_chatgpt.resolve_issue_planning_github_repository,
            validation_runner=lambda: application_validate_tree(ValidateTreeRequest(), ports),
            sync_runner=lambda: application_sync(
                SyncRequest(
                    force=False,
                    github_enabled=False,
                    issue_limit=10000,
                    update_active_from_branch=False,
                ),
                ports,
            ),
            transaction_runner=infra_issue_planning_apply.execute_planning_apply_transaction,
        )

    use_cases = UseCases(
        create_initiative=lambda req: application_create_initiative(req, ports),
        create_epic=lambda req: application_create_epic(req, ports),
        create_issue=lambda req: application_create_issue(req, ports),
        create_artifact_doc=lambda req: application_create_artifact_doc(
            req,
            ports,
            assurance_store=assurance_store,
            artifact_store=artifact_store,
        ),
        import_initiative=lambda req: application_import_initiative(req, ports),
        import_epic=lambda req: application_import_epic(req, ports),
        import_issue=lambda req: application_import_issue(req, ports),
        import_artifact=lambda req: application_import_artifact(req, ports),
        import_file_artifact=lambda req: application_import_file_artifact(req, ports),
        set_active=lambda req: application_set_active(req, ports),
        show_active=lambda req: application_show_active(req, ports),
        clear_active=lambda req: application_clear_active(req, ports),
        sync=lambda req: application_sync(req, ports),
        check_deps=lambda req: application_check_deps(req, ports),
        mutate_deps=lambda req: application_mutate_deps(req, ports),
        delete_node=lambda req: application_delete_node(req, ports),
        close_node=lambda req: application_close_node(req, ports),
        issue_start=lambda req: application_issue_start(req, ports),
        issue_finish=lambda req: application_issue_finish(req, ports),
        validate_tree=lambda req: application_validate_tree(req, ports),
        show_assurance=lambda req: application_show_assurance(req, store=assurance_store),
        classify_assurance=lambda req: application_classify_assurance(req, store=assurance_store),
        verify_assurance=lambda req: application_verify_assurance(req, store=assurance_store),
        compose_assurance=lambda req: application_compose_assurance(
            req,
            store=assurance_store,
            artifact_store=artifact_store,
        ),
        workflow_status=lambda req: application_workflow_status(req, store=assurance_store),
        workflow_next=lambda req: application_workflow_next(
            req,
            store=assurance_store,
            runbook_store=runbook_store,
        ),
        doctor=lambda req: application_doctor(req, ports),
        worktree_create=lambda req: application_worktree_create(req, ports),
        worktree_list=lambda req: application_worktree_list(req, ports),
        worktree_show=lambda req: application_worktree_show(req, ports),
        worktree_remove=lambda req: application_worktree_remove(req, ports),
        workbench_copy=lambda req: application_workbench_copy(req, ports),
        planning_create=planning_create,
        planning_revise=planning_revise,
        planning_review=planning_review,
        planning_apply=planning_apply,
        repo_root=ports.repo_root,
        specdock_dir=ports.specdock_dir,
    )
    return BootstrapContext(use_cases=use_cases)
