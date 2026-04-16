from __future__ import annotations

from pathlib import Path

from ..domain.models import SpecGraph

_REQUIRED_ARTIFACTS_BY_KIND: dict[str, tuple[str, ...]] = {
    "initiative": (".meta.json", "requirement.md", "design.md", "plan.md", "report.md"),
    "epic": (".meta.json", "requirement.md", "design.md", "plan.md", "report.md"),
    "issue": (".meta.json", "requirement.md", "design.md", "plan.md", "report.md"),
}


def _path_for_output(path: Path, *, repo_root: Path | None = None) -> str:
    if repo_root is not None:
        try:
            return path.relative_to(repo_root).as_posix()
        except ValueError:
            pass
    return path.as_posix()


def validate_required_artifacts_for_graph(
    graph: SpecGraph,
    *,
    repo_root: Path | None = None,
) -> None:
    nodes = sorted(
        graph.nodes_by_id.values(),
        key=lambda node: (node.kind, node.id, node.path.as_posix()),
    )
    for node in nodes:
        required_artifacts = _REQUIRED_ARTIFACTS_BY_KIND.get(node.kind, ())
        for filename in required_artifacts:
            artifact_path = node.path / filename
            if artifact_path.is_file():
                continue
            raise RuntimeError(
                "Missing required artifact: "
                f"kind={node.kind} id={node.id} "
                f"artifact={_path_for_output(artifact_path, repo_root=repo_root)}"
            )
