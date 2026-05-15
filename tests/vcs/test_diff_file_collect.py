from pathlib import Path
import subprocess

import pytest

from pyclassuml.model import (
    AnalysisConfig,
    CommandName,
    CommandOptions,
    CommandRequest,
    DiagnosticSeverity,
    DiffCurrentState,
    DiffOptions,
    ExecutionContext,
    FailureReason,
    OriginSeam,
    Recoverability,
)
from pyclassuml.vcs import ChangedFileEntry, ChangedLineRange, VcsDiffCollection, collect_diff_files, read_base_file_text
import pyclassuml.vcs.diff_collect as diff_collect


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", "-C", str(repo), *args),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def write_file(path: Path, text: str = "content\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def init_repo(path: Path) -> Path:
    path.mkdir()
    subprocess.run(("git", "init", str(path)), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    git(path, "config", "user.name", "pyclassuml test")
    git(path, "config", "user.email", "pyclassuml@example.test")
    return path


def commit_all(repo: Path, message: str) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message)


def tag_base(repo: Path) -> str:
    git(repo, "tag", "base")
    return "base"


def request(repo: Path, *, base_ref: str = "base") -> CommandRequest:
    return CommandRequest(
        process_cwd=repo,
        cli_options=CommandOptions(
            command=CommandName.DIFF,
            diff=DiffOptions(
                base_ref=base_ref,
                current_state=DiffCurrentState.WORKING_TREE,
                include_untracked=False,
            ),
        ),
    )


def context(
    repo: Path,
    *,
    project_root: Path | None = None,
    scope_root: Path | None = None,
    vcs_root: Path | None = None,
) -> ExecutionContext:
    resolved_project_root = (project_root or repo).resolve()
    return ExecutionContext(
        execution_cwd=repo.resolve(),
        project_root=resolved_project_root,
        package_root=resolved_project_root,
        scope_root=(scope_root or resolved_project_root).resolve(),
        vcs_root=(vcs_root or resolved_project_root).resolve(),
    )


def config(
    *,
    current_state: DiffCurrentState = DiffCurrentState.WORKING_TREE,
    include_untracked: bool = False,
) -> AnalysisConfig:
    return AnalysisConfig(diff_current_state=current_state, diff_include_untracked=include_untracked)


def assert_success(result: VcsDiffCollection) -> tuple[ChangedFileEntry, ...]:
    assert result.collection is not None
    assert result.diagnostics == ()
    return result.collection.entries


def assert_error(result: VcsDiffCollection, *, code: str) -> None:
    assert result.collection is None
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == code
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.origin_seam is OriginSeam.VCS
    assert diagnostic.recoverability is Recoverability.FATAL
    assert diagnostic.failure_reason is FailureReason.VCS_READ_FAILURE


def test_working_tree_tracked_added_modified_renamed_and_delete_excluded(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "modified.py", "before\n")
    write_file(repo / "old_name.py", "rename me\n")
    write_file(repo / "deleted.py", "delete me\n")
    commit_all(repo, "base")
    tag_base(repo)

    write_file(repo / "modified.py", "after\n")
    write_file(repo / "added.py", "new\n")
    git(repo, "add", "added.py")
    git(repo, "mv", "old_name.py", "new_name.py")
    (repo / "deleted.py").unlink()

    result = collect_diff_files(request(repo), context(repo), config())

    assert assert_success(result) == (
        ChangedFileEntry("added.py", "added"),
        ChangedFileEntry("modified.py", "modified"),
        ChangedFileEntry("new_name.py", "renamed", "old_name.py"),
    )
    assert result.diagnostics == ()


def test_modified_file_collects_current_side_changed_hunk_ranges(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(
        repo / "pkg" / "models.py",
        "\n".join(
            [
                "class Unchanged:",
                "    value = 1",
                "",
                "class Changed:",
                "    value = 1",
                "",
            ]
        ),
    )
    commit_all(repo, "base")
    tag_base(repo)
    write_file(
        repo / "pkg" / "models.py",
        "\n".join(
            [
                "class Unchanged:",
                "    value = 1",
                "",
                "class Changed:",
                "    value = 2",
                "",
            ]
        ),
    )

    (entry,) = assert_success(collect_diff_files(request(repo), context(repo), config()))

    assert entry == ChangedFileEntry("pkg/models.py", "modified")
    assert entry.current_changed_line_ranges == (ChangedLineRange(start=5, end=5),)


def test_deleted_only_hunk_uses_current_side_point_range(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "models.py", "class Model:\n    value = 1\n    removed = True\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "models.py", "class Model:\n    value = 1\n")

    (entry,) = assert_success(collect_diff_files(request(repo), context(repo), config()))

    assert entry == ChangedFileEntry("pkg/models.py", "modified")
    assert entry.current_changed_line_ranges == (
        ChangedLineRange(start=2, end=2, is_deletion_only=True, deleted_lines=("    removed = True",)),
    )


def test_deleted_only_hunk_before_first_current_line_is_not_current_side_changed_range(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "settings.py", "VALUE = 1\n\nclass Settings:\n    name = 'default'\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "settings.py", "class Settings:\n    name = 'default'\n")

    (entry,) = assert_success(collect_diff_files(request(repo), context(repo), config()))

    assert entry == ChangedFileEntry("pkg/settings.py", "modified")
    assert entry.current_changed_line_ranges == ()


def test_deleted_only_decorator_hunk_before_first_current_line_keeps_deleted_lines(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "models.py", "@entity\nclass Model:\n    value = 1\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "models.py", "class Model:\n    value = 1\n")

    (entry,) = assert_success(collect_diff_files(request(repo), context(repo), config()))

    assert entry == ChangedFileEntry("pkg/models.py", "modified")
    assert entry.current_changed_line_ranges == (
        ChangedLineRange(start=1, end=1, is_deletion_only=True, deleted_lines=("@entity",)),
    )
    assert entry.current_changed_line_ranges[0].is_before_first_line_deletion is True


def test_deleted_only_module_level_hunk_after_class_keeps_current_side_point_range(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "models.py", "class Model:\n    value = 1\n\nVALUES = [\n    1,\n]\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "models.py", "class Model:\n    value = 1\n")

    (entry,) = assert_success(collect_diff_files(request(repo), context(repo), config()))

    assert entry == ChangedFileEntry("pkg/models.py", "modified")
    assert entry.current_changed_line_ranges == (
        ChangedLineRange(
            start=2,
            end=2,
            is_deletion_only=True,
            deleted_lines=("", "VALUES = [", "    1,", "]"),
        ),
    )


def test_renamed_file_collects_current_side_changed_hunk_ranges(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "old.py", "class Model:\n    value = 1\n    keep = True\n    also_keep = True\n")
    commit_all(repo, "base")
    tag_base(repo)
    git(repo, "mv", "pkg/old.py", "pkg/new.py")
    write_file(repo / "pkg" / "new.py", "class Model:\n    value = 2\n    keep = True\n    also_keep = True\n")

    (entry,) = assert_success(collect_diff_files(request(repo), context(repo), config()))

    assert entry == ChangedFileEntry("pkg/new.py", "renamed", "pkg/old.py")
    assert entry.current_changed_line_ranges == (ChangedLineRange(start=2, end=2),)


def test_read_base_file_text_reads_project_relative_blob(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "model.py", "class Model:\n    value = 1\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "model.py", "class Model:\n    value = 2\n")

    text = read_base_file_text(repo, repo, "base", "pkg/model.py")

    assert text == "class Model:\n    value = 1\n"


def test_read_base_file_text_returns_none_for_allowed_missing_blob(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "existing.py", "class Existing:\n    pass\n")
    commit_all(repo, "base")
    tag_base(repo)

    text = read_base_file_text(repo, repo, "base", "pkg/new.py", missing_ok=True)

    assert text is None


def test_read_base_file_text_rejects_unexpected_missing_blob(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "existing.py", "class Existing:\n    pass\n")
    commit_all(repo, "base")
    tag_base(repo)

    try:
        read_base_file_text(repo, repo, "base", "pkg/new.py")
    except diff_collect.VcsDiffError as exc:
        assert exc.code == "git_diff_read_failure"
    else:
        raise AssertionError("expected VcsDiffError")


def test_read_base_file_text_missing_ok_does_not_mask_invalid_base_ref(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "existing.py", "class Existing:\n    pass\n")
    commit_all(repo, "base")

    try:
        read_base_file_text(repo, repo, "missing-ref", "pkg/new.py", missing_ok=True)
    except diff_collect.VcsDiffError as exc:
        assert exc.code == "invalid_base_ref"
    else:
        raise AssertionError("expected VcsDiffError")


def test_read_base_file_text_missing_ok_does_not_mask_base_tree_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "existing.py", "class Existing:\n    pass\n")
    commit_all(repo, "base")
    tag_base(repo)

    original_run_git = diff_collect._run_git

    def run_git_spy(
        project_root: Path,
        args: tuple[str, ...],
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[bytes]:
        if args[:2] == ("ls-tree", "-z"):
            return subprocess.CompletedProcess(("git", *args), 128, b"", b"fatal: simulated tree failure\n")
        return original_run_git(project_root, args, check=check)

    monkeypatch.setattr(diff_collect, "_run_git", run_git_spy)

    try:
        read_base_file_text(repo, repo, "base", "pkg/new.py", missing_ok=True)
    except diff_collect.VcsDiffError as exc:
        assert exc.code == "git_diff_read_failure"
    else:
        raise AssertionError("expected VcsDiffError")


def test_working_tree_untracked_included_excluded_and_empty_success(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "tracked.py")
    commit_all(repo, "base")
    tag_base(repo)

    write_file(repo / "untracked.py", "new\n")

    excluded = collect_diff_files(request(repo), context(repo), config(include_untracked=False))
    included = collect_diff_files(request(repo), context(repo), config(include_untracked=True))

    assert assert_success(excluded) == ()
    assert assert_success(included) == (ChangedFileEntry("untracked.py", "added"),)

    (repo / "untracked.py").unlink()
    empty = collect_diff_files(request(repo), context(repo), config(include_untracked=True))
    assert assert_success(empty) == ()


def test_head_diff_uses_head_not_working_tree(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "base.py", "base\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "head_only.py", "head\n")
    commit_all(repo, "head")
    write_file(repo / "work_only.py", "work\n")
    git(repo, "add", "work_only.py")

    head_result = collect_diff_files(request(repo), context(repo), config(current_state=DiffCurrentState.HEAD))
    working_result = collect_diff_files(request(repo), context(repo), config(current_state=DiffCurrentState.WORKING_TREE))

    assert assert_success(head_result) == (ChangedFileEntry("head_only.py", "added"),)
    assert assert_success(working_result) == (
        ChangedFileEntry("head_only.py", "added"),
        ChangedFileEntry("work_only.py", "added"),
    )


def test_head_include_untracked_true_warns_and_does_not_include_untracked(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "base.py", "base\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "head_only.py", "head\n")
    commit_all(repo, "head")
    write_file(repo / "untracked.py", "untracked\n")

    result = collect_diff_files(
        request(repo),
        context(repo),
        config(current_state=DiffCurrentState.HEAD, include_untracked=True),
    )

    assert result.collection is not None
    assert result.collection.entries == (ChangedFileEntry("head_only.py", "added"),)
    assert len(result.diagnostics) == 1
    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "head_untracked_noop"
    assert diagnostic.severity is DiagnosticSeverity.WARNING
    assert diagnostic.origin_seam is OriginSeam.VCS
    assert diagnostic.recoverability is Recoverability.RECOVERABLE
    assert diagnostic.failure_reason is None


def test_invalid_base_ref_returns_invalid_base_ref_error(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "tracked.py")
    commit_all(repo, "base")

    result = collect_diff_files(request(repo, base_ref="missing-ref"), context(repo), config())

    assert_error(result, code="invalid_base_ref")


def test_non_git_project_root_returns_git_diff_read_failure(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = collect_diff_files(request(project), context(project), config())

    assert_error(result, code="git_diff_read_failure")


def test_name_status_parse_failure_returns_git_diff_parse_failure(monkeypatch, tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "tracked.py")
    commit_all(repo, "base")
    tag_base(repo)

    monkeypatch.setattr(
        diff_collect,
        "_tracked_entries",
        lambda vcs_root, project_root, base_ref, current_state: diff_collect._parse_name_status(b"X\0file.py\0"),
    )

    result = collect_diff_files(request(repo), context(repo), config())

    assert_error(result, code="git_diff_parse_failure")


def test_name_status_decode_failure_returns_git_diff_parse_failure(monkeypatch, tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "tracked.py")
    commit_all(repo, "base")
    tag_base(repo)

    monkeypatch.setattr(
        diff_collect,
        "_tracked_entries",
        lambda vcs_root, project_root, base_ref, current_state: diff_collect._parse_name_status(b"A\0\xff\0"),
    )

    result = collect_diff_files(request(repo), context(repo), config())

    assert_error(result, code="git_diff_parse_failure")


def test_post_validation_git_diff_failure_returns_git_diff_read_failure(monkeypatch, tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "tracked.py")
    commit_all(repo, "base")
    tag_base(repo)
    original_run_git = diff_collect._run_git

    def run_git_with_diff_failure(
        project_root: Path,
        args: tuple[str, ...],
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[bytes]:
        if args[0] == "diff":
            raise diff_collect.VcsDiffError("git_diff_read_failure", "forced post-validation diff failure")
        return original_run_git(project_root, args, check=check)

    monkeypatch.setattr(diff_collect, "_run_git", run_git_with_diff_failure)

    result = collect_diff_files(request(repo), context(repo), config())

    assert_error(result, code="git_diff_read_failure")


def test_scope_outside_path_is_included_without_scope_filtering(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    scope = repo / "pkg"
    write_file(scope / "inside.py")
    write_file(repo / "outside_scope.py", "before\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "outside_scope.py", "after\n")

    result = collect_diff_files(request(repo), context(repo, scope_root=scope), config())

    assert assert_success(result) == (ChangedFileEntry("outside_scope.py", "modified"),)


def test_nested_project_root_working_tree_returns_project_relative_paths_only(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    project = repo / "packages" / "app"
    write_file(repo / "outside.py", "outside before\n")
    write_file(project / "inside.py", "inside before\n")
    commit_all(repo, "base")
    tag_base(repo)

    write_file(repo / "outside.py", "outside after\n")
    write_file(repo / "outside_untracked.py", "outside untracked\n")
    write_file(project / "inside.py", "inside after\n")
    write_file(project / "inside_untracked.py", "inside untracked\n")

    result = collect_diff_files(
        request(project),
        context(repo, project_root=project),
        config(include_untracked=True),
    )

    assert assert_success(result) == (
        ChangedFileEntry("inside.py", "modified"),
        ChangedFileEntry("inside_untracked.py", "added"),
    )


def test_vcs_root_can_differ_from_project_root_for_monorepo_diff(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    project = repo / "packages" / "app"
    write_file(repo / "outside.py", "outside before\n")
    write_file(project / "inside.py", "inside before\n")
    commit_all(repo, "base")
    tag_base(repo)

    write_file(repo / "outside.py", "outside after\n")
    write_file(project / "inside.py", "inside after\n")
    write_file(project / "inside_untracked.py", "inside untracked\n")

    result = collect_diff_files(
        request(repo),
        context(repo, project_root=project, vcs_root=repo),
        config(include_untracked=True),
    )

    assert assert_success(result) == (
        ChangedFileEntry("inside.py", "modified"),
        ChangedFileEntry("inside_untracked.py", "added"),
    )


def test_nested_project_root_head_returns_project_relative_paths_only(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    project = repo / "packages" / "app"
    write_file(repo / "outside.py", "outside before\n")
    write_file(project / "inside.py", "inside before\n")
    commit_all(repo, "base")
    tag_base(repo)

    write_file(repo / "outside.py", "outside after\n")
    write_file(project / "inside.py", "inside after\n")
    commit_all(repo, "head")

    result = collect_diff_files(
        request(project),
        context(repo, project_root=project),
        config(current_state=DiffCurrentState.HEAD),
    )

    assert assert_success(result) == (ChangedFileEntry("inside.py", "modified"),)


def test_entries_are_deduped_by_current_path_and_sorted(monkeypatch, tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "tracked.py")
    commit_all(repo, "base")
    tag_base(repo)

    monkeypatch.setattr(diff_collect, "_ensure_git_repository", lambda project_root: None)
    monkeypatch.setattr(diff_collect, "_verify_base_ref", lambda project_root, base_ref: None)
    monkeypatch.setattr(
        diff_collect,
        "_tracked_entries",
        lambda vcs_root, project_root, base_ref, current_state: [
            ChangedFileEntry("z.py", "modified"),
            ChangedFileEntry("a.py", "added"),
            ChangedFileEntry("z.py", "renamed", "old_z.py"),
        ],
    )

    result = collect_diff_files(request(repo), context(repo), config())

    assert assert_success(result) == (
        ChangedFileEntry("a.py", "added"),
        ChangedFileEntry("z.py", "renamed", "old_z.py"),
    )
