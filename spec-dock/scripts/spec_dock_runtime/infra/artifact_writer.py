from __future__ import annotations

from pathlib import Path

from ..application.contracts import ArtifactWriteResult
from ..presentation.contracts import ArtifactBundle


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def cleanup_legacy_outputs(specdock_dir: Path) -> None:
    agent_dir = specdock_dir / ".agent"
    legacy_work_dir = specdock_dir / ".work"

    (agent_dir / "deps.json").unlink(missing_ok=True)
    (agent_dir / "deps.puml").unlink(missing_ok=True)
    (agent_dir / "deps.todo.puml").unlink(missing_ok=True)

    (legacy_work_dir / "state.json").unlink(missing_ok=True)
    (legacy_work_dir / "index.json").unlink(missing_ok=True)
    (legacy_work_dir / "tree.json").unlink(missing_ok=True)


def write(specdock_dir: Path, bundle: ArtifactBundle) -> ArtifactWriteResult:
    agent_dir = specdock_dir / ".agent"
    agent_dir.mkdir(parents=True, exist_ok=True)

    index_all_path = agent_dir / "index-all.json"
    index_todo_path = agent_dir / "index.json"
    tree_all_path = agent_dir / "tree-all.json"
    tree_todo_path = agent_dir / "tree.json"
    tree_all_puml_path = specdock_dir / "tree-all.puml"
    tree_todo_puml_path = specdock_dir / "tree.puml"
    deps_issues_json_path = agent_dir / "deps-issues.json"
    deps_issues_puml_path = specdock_dir / "deps-issues.puml"
    dashboard_md_path = specdock_dir / "dashboard.md"

    _write_text(index_all_path, bundle.index.all_json_text)
    _write_text(index_todo_path, bundle.index.todo_json_text)
    _write_text(tree_all_path, bundle.tree.all_json_text)
    _write_text(tree_todo_path, bundle.tree.todo_json_text)
    _write_text(tree_all_puml_path, bundle.tree.all_puml_text)
    _write_text(tree_todo_puml_path, bundle.tree.todo_puml_text)
    _write_text(deps_issues_json_path, bundle.deps_issues.json_text)
    _write_text(deps_issues_puml_path, bundle.deps_issues.puml_text)
    _write_text(dashboard_md_path, bundle.dashboard.markdown_text)
    cleanup_legacy_outputs(specdock_dir)

    repo_root = specdock_dir.parent
    return ArtifactWriteResult(
        index_all_path=index_all_path.relative_to(repo_root).as_posix(),
        index_todo_path=index_todo_path.relative_to(repo_root).as_posix(),
        tree_all_path=tree_all_path.relative_to(repo_root).as_posix(),
        tree_todo_path=tree_todo_path.relative_to(repo_root).as_posix(),
        tree_all_puml_path=tree_all_puml_path.relative_to(repo_root).as_posix(),
        tree_todo_puml_path=tree_todo_puml_path.relative_to(repo_root).as_posix(),
        deps_issues_json_path=deps_issues_json_path.relative_to(repo_root).as_posix(),
        deps_issues_puml_path=deps_issues_puml_path.relative_to(repo_root).as_posix(),
        dashboard_md_path=dashboard_md_path.relative_to(repo_root).as_posix(),
    )


class FileArtifactWriter:
    def write(self, specdock_dir: Path, bundle: ArtifactBundle) -> ArtifactWriteResult:
        return write(specdock_dir, bundle)
