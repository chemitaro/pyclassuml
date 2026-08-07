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
    DiffBaseResolution,
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


def rev_parse(repo: Path, ref: str) -> str:
    return git(repo, "rev-parse", ref).stdout.strip()


def request(repo: Path, *, base_ref: str | None = "base") -> CommandRequest:
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
    depth: int | None = None,
    current_state: DiffCurrentState = DiffCurrentState.WORKING_TREE,
    include_untracked: bool = False,
) -> AnalysisConfig:
    return AnalysisConfig(
        depth=depth,
        diff_current_state=current_state,
        diff_include_untracked=include_untracked,
    )


def assert_success(result: VcsDiffCollection) -> tuple[ChangedFileEntry, ...]:
    assert result.collection is not None
    assert result.diagnostics == ()
    return result.collection.entries


def assert_success_with_diagnostics(result: VcsDiffCollection) -> tuple[ChangedFileEntry, ...]:
    assert result.collection is not None
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


def test_explicit_base_sets_authoritative_base_resolution(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "tracked.py", "before\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "tracked.py", "after\n")

    result = collect_diff_files(request(repo, base_ref="base"), context(repo), config())

    assert assert_success(result) == (ChangedFileEntry("tracked.py", "modified"),)
    assert result.collection is not None
    assert result.collection.base_resolution == DiffBaseResolution(
        requested_base_ref="base",
        resolved_base_ref="base",
        resolution_kind="explicit_base",
        candidate_ref=None,
    )


def test_diff_changed_files_are_invariant_to_analysis_depth(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "first.py", "before\n")
    write_file(repo / "pkg" / "second.py", "before\n")
    commit_all(repo, "base")
    git(repo, "branch", "-M", "main")
    head_sha = rev_parse(repo, "HEAD")
    write_file(repo / "pkg" / "first.py", "after\n")
    write_file(repo / "pkg" / "second.py", "after\n")

    collections = [
        collect_diff_files(request(repo, base_ref=None), context(repo), config(depth=depth))
        for depth in (0, 1, 2)
    ]

    assert [assert_success(result) for result in collections] == [
        (ChangedFileEntry("pkg/first.py", "modified"), ChangedFileEntry("pkg/second.py", "modified")),
    ] * 3
    assert [result.collection.base_resolution for result in collections if result.collection is not None] == [
        DiffBaseResolution(
            requested_base_ref=None,
            resolved_base_ref=head_sha,
            resolution_kind="default_branch_head",
            candidate_ref=None,
        ),
    ] * 3


def test_explicit_revision_expression_is_preserved_and_tree_object_is_rejected(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "tracked.py", "base\n")
    commit_all(repo, "base")
    write_file(repo / "tracked.py", "head\n")
    commit_all(repo, "head")

    result = collect_diff_files(request(repo, base_ref="HEAD~1"), context(repo), config())

    assert assert_success(result) == (ChangedFileEntry("tracked.py", "modified"),)
    assert result.collection is not None
    assert result.collection.base_resolution == DiffBaseResolution(
        requested_base_ref="HEAD~1",
        resolved_base_ref="HEAD~1",
        resolution_kind="explicit_base",
        candidate_ref=None,
    )

    tree_ref = rev_parse(repo, "HEAD^{tree}")
    invalid = collect_diff_files(request(repo, base_ref=tree_ref), context(repo), config())
    assert_error(invalid, code="invalid_base_ref")


def test_invalid_explicit_base_does_not_fallback(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "tracked.py")
    commit_all(repo, "base")

    result = collect_diff_files(request(repo, base_ref="missing-ref"), context(repo), config())

    assert_error(result, code="invalid_base_ref")
    assert all(diagnostic.code != "diff_base_initial_commit_fallback" for diagnostic in result.diagnostics)


def test_no_base_feature_branch_resolves_default_branch_merge_base(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "tracked.py", "base\n")
    commit_all(repo, "base")
    git(repo, "branch", "-m", "main")
    base_sha = rev_parse(repo, "HEAD")
    git(repo, "update-ref", "refs/remotes/origin/main", base_sha)
    git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    git(repo, "switch", "-c", "feature/default-base")
    write_file(repo / "tracked.py", "feature\n")

    result = collect_diff_files(request(repo, base_ref=None), context(repo), config())

    assert assert_success(result) == (ChangedFileEntry("tracked.py", "modified"),)
    assert result.collection is not None
    assert result.collection.base_resolution == DiffBaseResolution(
        requested_base_ref=None,
        resolved_base_ref=base_sha,
        resolution_kind="default_branch_merge_base",
        candidate_ref="origin/main",
    )


def test_no_base_detached_head_uses_valid_default_branch_merge_base(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "tracked.py", "base\n")
    commit_all(repo, "base")
    git(repo, "branch", "-M", "main")
    base_sha = rev_parse(repo, "HEAD")
    git(repo, "update-ref", "refs/remotes/origin/main", base_sha)
    git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    git(repo, "checkout", "--detach", "HEAD")
    write_file(repo / "tracked.py", "detached working tree\n")

    result = collect_diff_files(request(repo, base_ref=None), context(repo), config())

    assert assert_success(result) == (ChangedFileEntry("tracked.py", "modified"),)
    assert result.collection is not None
    assert result.collection.base_resolution == DiffBaseResolution(
        requested_base_ref=None,
        resolved_base_ref=base_sha,
        resolution_kind="default_branch_merge_base",
        candidate_ref="origin/main",
    )


def test_no_base_detached_head_without_candidates_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "tracked.py", "base\n")
    commit_all(repo, "base")
    git(repo, "checkout", "--detach", "HEAD")
    monkeypatch.setattr(diff_collect, "_default_branch_candidates", lambda vcs_root: ())

    result = collect_diff_files(request(repo, base_ref=None), context(repo), config())

    assert_error(result, code="diff_base_resolution_unavailable")


def test_no_base_default_branch_working_tree_uses_start_head_sha_without_history_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "tracked.py", "initial\n")
    commit_all(repo, "initial")
    git(repo, "branch", "-M", "main")
    write_file(repo / "tracked.py", "historical\n")
    commit_all(repo, "historical")
    head_sha = rev_parse(repo, "HEAD")
    git(repo, "update-ref", "refs/remotes/origin/main", rev_parse(repo, "HEAD~1"))
    git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    write_file(repo / "tracked.py", "working tree\n")

    original_run_git = diff_collect._run_git
    seen_args: list[tuple[str, ...]] = []

    def run_git_spy(
        project_root: Path,
        args: tuple[str, ...],
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[bytes]:
        seen_args.append(args)
        return original_run_git(project_root, args, check=check)

    monkeypatch.setattr(diff_collect, "_run_git", run_git_spy)

    result = collect_diff_files(request(repo, base_ref=None), context(repo), config())

    assert assert_success(result) == (ChangedFileEntry("tracked.py", "modified"),)
    assert result.collection is not None
    assert result.collection.base_resolution == DiffBaseResolution(
        requested_base_ref=None,
        resolved_base_ref=head_sha,
        resolution_kind="default_branch_head",
        candidate_ref=None,
    )
    assert sum(args == ("rev-parse", "--verify", "HEAD^{commit}") for args in seen_args) == 1
    assert not any(args[:2] == ("rev-list", "--max-parents=0") for args in seen_args)


def test_no_base_default_branch_head_requires_explicit_base_before_diff(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "tracked.py", "initial\n")
    commit_all(repo, "initial")
    git(repo, "branch", "-M", "main")
    seen_args: list[tuple[str, ...]] = []
    original_run_git = diff_collect._run_git

    def run_git_spy(
        project_root: Path,
        args: tuple[str, ...],
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[bytes]:
        seen_args.append(args)
        return original_run_git(project_root, args, check=check)

    monkeypatch.setattr(diff_collect, "_run_git", run_git_spy)

    result = collect_diff_files(
        request(repo, base_ref=None),
        context(repo),
        config(current_state=DiffCurrentState.HEAD),
    )

    assert_error(result, code="diff_default_branch_head_requires_base")
    assert "HEAD~1" in result.diagnostics[0].message
    assert "origin/<default-branch>" in result.diagnostics[0].message
    assert not any(args[:1] == ("diff",) for args in seen_args)


def test_origin_head_identity_takes_precedence_over_conventional_branch_name(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "tracked.py", "base\n")
    commit_all(repo, "base")
    git(repo, "branch", "-M", "main")
    base_sha = rev_parse(repo, "HEAD")
    write_file(repo / "tracked.py", "main history\n")
    commit_all(repo, "main history")
    git(repo, "branch", "release/main", base_sha)
    git(repo, "update-ref", "refs/remotes/origin/release/main", base_sha)
    git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/release/main")
    write_file(repo / "tracked.py", "working tree\n")

    result = collect_diff_files(request(repo, base_ref=None), context(repo), config())

    assert result.collection is not None
    assert result.collection.base_resolution == DiffBaseResolution(
        requested_base_ref=None,
        resolved_base_ref=base_sha,
        resolution_kind="default_branch_merge_base",
        candidate_ref="origin/release/main",
    )


def test_configured_current_state_is_authoritative_over_raw_cli_state(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "tracked.py", "base\n")
    commit_all(repo, "base")
    git(repo, "branch", "-M", "main")
    write_file(repo / "tracked.py", "working tree\n")

    request_head = request(repo, base_ref=None)
    request_head = CommandRequest(
        process_cwd=request_head.process_cwd,
        cli_options=CommandOptions(
            command=CommandName.DIFF,
            diff=DiffOptions(
                base_ref=None,
                current_state=DiffCurrentState.HEAD,
                include_untracked=False,
            ),
        ),
    )
    working_tree_result = collect_diff_files(request_head, context(repo), config())
    assert assert_success(working_tree_result) == (ChangedFileEntry("tracked.py", "modified"),)

    request_working_tree = request(repo, base_ref=None)
    head_result = collect_diff_files(
        request_working_tree,
        context(repo),
        config(current_state=DiffCurrentState.HEAD),
    )
    assert_error(head_result, code="diff_default_branch_head_requires_base")


def test_no_base_without_usable_candidate_fails_without_initial_commit_fallback(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "tracked.py", "initial\n")
    commit_all(repo, "initial")
    git(repo, "branch", "-M", "feature/no-candidate")
    write_file(repo / "tracked.py", "head\n")
    commit_all(repo, "head")

    assert git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "feature/no-candidate"
    for ref in (
        "refs/remotes/origin/HEAD",
        "refs/remotes/origin/main",
        "refs/remotes/origin/develop",
        "refs/remotes/origin/master",
        "refs/heads/main",
        "refs/heads/develop",
        "refs/heads/master",
    ):
        ref_probe = subprocess.run(
            ("git", "-C", str(repo), "show-ref", "--verify", "--quiet", ref),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert ref_probe.returncode != 0

    result = collect_diff_files(request(repo, base_ref=None), context(repo), config())

    assert_error(result, code="diff_base_resolution_unavailable")
    assert all(diagnostic.code != "diff_base_initial_commit_fallback" for diagnostic in result.diagnostics)


def test_no_base_candidate_exhaustion_does_not_call_rev_list(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "tracked.py", "base\n")
    commit_all(repo, "base")
    git(repo, "branch", "-M", "main")
    base_sha = rev_parse(repo, "HEAD")
    git(repo, "update-ref", "refs/remotes/origin/main", base_sha)
    git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    git(repo, "switch", "-c", "feature/no-merge-base")
    write_file(repo / "tracked.py", "feature\n")

    original_run_git = diff_collect._run_git
    attempted_rev_list = False

    def run_git_spy(
        project_root: Path,
        args: tuple[str, ...],
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[bytes]:
        nonlocal attempted_rev_list
        if args[:1] == ("merge-base",):
            return subprocess.CompletedProcess(("git", *args), 1, b"", b"no merge base\n")
        if args[:1] == ("rev-list",):
            attempted_rev_list = True
        return original_run_git(project_root, args, check=check)

    monkeypatch.setattr(diff_collect, "_run_git", run_git_spy)

    result = collect_diff_files(request(repo, base_ref=None), context(repo), config())

    assert_error(result, code="diff_base_resolution_unavailable")
    assert attempted_rev_list is False


def test_no_base_current_slashful_default_branch_working_tree_uses_head(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "tracked.py", "initial\n")
    commit_all(repo, "initial")
    git(repo, "branch", "-m", "release/main")
    initial_sha = rev_parse(repo, "HEAD")
    git(repo, "update-ref", "refs/remotes/origin/release/main", initial_sha)
    git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/release/main")
    write_file(repo / "tracked.py", "head\n")
    commit_all(repo, "head")
    git(repo, "update-ref", "refs/remotes/origin/release/main", rev_parse(repo, "HEAD"))
    git(repo, "branch", "main", initial_sha)

    result = collect_diff_files(request(repo, base_ref=None), context(repo), config())

    assert assert_success_with_diagnostics(result) == ()
    assert result.collection is not None
    assert result.collection.base_resolution == DiffBaseResolution(
        requested_base_ref=None,
        resolved_base_ref=rev_parse(repo, "HEAD"),
        resolution_kind="default_branch_head",
        candidate_ref=None,
    )


def test_no_base_no_commit_repository_fails_fast(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")

    result = collect_diff_files(request(repo, base_ref=None), context(repo), config())

    assert_error(result, code="git_diff_read_failure")


def test_no_base_preserves_untracked_and_project_boundaries(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    project = repo / "packages" / "app"
    write_file(repo / "outside.py", "outside before\n")
    write_file(project / "inside.py", "inside before\n")
    commit_all(repo, "initial")
    write_file(repo / "outside.py", "outside after\n")
    write_file(project / "inside.py", "inside after\n")
    write_file(project / "inside_untracked.py", "inside untracked\n")

    excluded = collect_diff_files(
        request(project, base_ref=None),
        context(repo, project_root=project),
        config(include_untracked=False),
    )
    included = collect_diff_files(
        request(project, base_ref=None),
        context(repo, project_root=project),
        config(include_untracked=True),
    )
    scope_boundary = collect_diff_files(
        request(repo, base_ref=None),
        context(repo, scope_root=project),
        config(include_untracked=False),
    )

    assert assert_success_with_diagnostics(excluded) == (ChangedFileEntry("inside.py", "modified"),)
    assert assert_success_with_diagnostics(included) == (
        ChangedFileEntry("inside.py", "modified"),
        ChangedFileEntry("inside_untracked.py", "added"),
    )
    assert assert_success_with_diagnostics(scope_boundary) == (
        ChangedFileEntry("outside.py", "modified"),
        ChangedFileEntry("packages/app/inside.py", "modified"),
    )


def test_no_base_candidate_order_skips_missing_duplicates_and_merge_base_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "tracked.py", "base\n")
    commit_all(repo, "base")
    git(repo, "branch", "-m", "main")
    base_sha = rev_parse(repo, "HEAD")
    git(repo, "update-ref", "refs/remotes/origin/main", base_sha)
    git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    git(repo, "branch", "develop", base_sha)
    git(repo, "switch", "-c", "feature/precedence")
    git(repo, "branch", "-D", "main")
    write_file(repo / "tracked.py", "feature\n")

    original_run_git = diff_collect._run_git
    attempted_merge_bases: list[str] = []
    attempted_merge_base_heads: list[str] = []
    attempted_rev_list = False

    def run_git_spy(
        project_root: Path,
        args: tuple[str, ...],
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[bytes]:
        if args[:1] == ("merge-base",):
            attempted_merge_bases.append(args[1])
            attempted_merge_base_heads.append(args[2])
            if args[1] == "origin/main":
                return subprocess.CompletedProcess(("git", *args), 1, b"", b"no merge base\n")
        nonlocal attempted_rev_list
        if args[:1] == ("rev-list",):
            attempted_rev_list = True
        return original_run_git(project_root, args, check=check)

    monkeypatch.setattr(diff_collect, "_run_git", run_git_spy)

    result = collect_diff_files(request(repo, base_ref=None), context(repo), config())

    assert assert_success(result) == (ChangedFileEntry("tracked.py", "modified"),)
    assert attempted_merge_bases == ["origin/main", "develop"]
    assert attempted_merge_base_heads == [base_sha, base_sha]
    assert attempted_rev_list is False
    assert result.collection is not None
    assert result.collection.base_resolution == DiffBaseResolution(
        requested_base_ref=None,
        resolved_base_ref=base_sha,
        resolution_kind="default_branch_merge_base",
        candidate_ref="develop",
    )


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


def test_git_diff_collection_disables_lazy_fetch_external_diff_and_textconv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "model.py", "class Model:\n    value = 1\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "model.py", "class Model:\n    value = 2\n")

    original_run = diff_collect.subprocess.run
    calls: list[tuple[tuple[str, ...], dict[str, object]]] = []

    def run_spy(command: tuple[str, ...], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        calls.append((command, kwargs))
        return original_run(command, **kwargs)

    monkeypatch.setattr(diff_collect.subprocess, "run", run_spy)

    result = collect_diff_files(request(repo), context(repo), config())

    assert assert_success(result) == (ChangedFileEntry("pkg/model.py", "modified"),)
    assert calls
    assert all(call_kwargs["env"]["GIT_NO_LAZY_FETCH"] == "1" for _, call_kwargs in calls)
    diff_commands = [command for command, _ in calls if "diff" in command]
    assert diff_commands
    for command in diff_commands:
        assert "--no-ext-diff" in command
        assert "--no-textconv" in command
        assert "--no-color" in command


def test_git_diff_collection_does_not_invoke_external_diff_or_textconv_sentinels(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    marker = tmp_path / "sentinel-called"
    external_diff = tmp_path / "external-diff.sh"
    textconv = tmp_path / "textconv.sh"
    write_file(external_diff, f"#!/bin/sh\ntouch '{marker}'\nexit 97\n")
    write_file(textconv, f"#!/bin/sh\ntouch '{marker}'\ncat \"$1\"\n")
    external_diff.chmod(0o755)
    textconv.chmod(0o755)
    write_file(repo / ".gitattributes", "pkg/model.py diff=sentinel\n")
    write_file(repo / "pkg" / "model.py", "class Model:\n    value = 1\n")
    commit_all(repo, "base")
    tag_base(repo)
    git(repo, "config", "diff.external", str(external_diff))
    git(repo, "config", "diff.sentinel.textconv", str(textconv))
    write_file(repo / "pkg" / "model.py", "class Model:\n    value = 2\n")

    result = collect_diff_files(request(repo), context(repo), config())

    assert assert_success(result) == (ChangedFileEntry("pkg/model.py", "modified"),)
    assert not marker.exists()


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


def test_implicit_changed_path_limit_is_inclusive_and_explicit_base_bypasses() -> None:
    implicit_resolution = DiffBaseResolution(
        requested_base_ref=None,
        resolved_base_ref="abc123",
        resolution_kind="default_branch_head",
        candidate_ref=None,
    )
    entries = [diff_collect._RawChangedFileEntry(f"pkg/{index}.py", "modified") for index in range(1000)]

    diff_collect._ensure_implicit_changed_path_limit(implicit_resolution, entries)

    with pytest.raises(diff_collect.VcsDiffError, match="1001") as error_info:
        diff_collect._ensure_implicit_changed_path_limit(
            implicit_resolution,
            [*entries, diff_collect._RawChangedFileEntry("pkg/1000.py", "modified")],
        )
    assert error_info.value.code == "diff_implicit_range_too_broad"

    explicit_resolution = DiffBaseResolution(
        requested_base_ref="base",
        resolved_base_ref="base",
        resolution_kind="explicit_base",
        candidate_ref=None,
    )
    diff_collect._ensure_implicit_changed_path_limit(explicit_resolution, entries + entries[:1])


def test_implicit_range_guard_stops_before_hunk_and_explicit_base_bypasses_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "one.py", "class One:\n    pass\n")
    write_file(repo / "two.py", "class Two:\n    pass\n")
    commit_all(repo, "base")
    tag_base(repo)
    git(repo, "branch", "-M", "main")
    write_file(repo / "one.py", "class One:\n    value = 1\n")
    write_file(repo / "two.py", "class Two:\n    value = 2\n")
    head_sha = rev_parse(repo, "HEAD")
    monkeypatch.setattr(diff_collect, "MAX_IMPLICIT_DIFF_CHANGED_PATHS", 1)
    original_hunk = diff_collect._entry_with_current_changed_line_ranges
    hunk_calls = 0

    def hunk_spy(*args: object, **kwargs: object) -> diff_collect._RawChangedFileEntry:
        nonlocal hunk_calls
        hunk_calls += 1
        return original_hunk(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(diff_collect, "_entry_with_current_changed_line_ranges", hunk_spy)

    implicit = collect_diff_files(request(repo, base_ref=None), context(repo), config())
    assert_error(implicit, code="diff_implicit_range_too_broad")
    assert f"base {head_sha}" in implicit.diagnostics[0].message
    assert "2 changed paths" in implicit.diagnostics[0].message
    assert f"--base {head_sha}" in implicit.diagnostics[0].message
    assert hunk_calls == 0

    explicit = collect_diff_files(request(repo, base_ref="base"), context(repo), config())
    assert assert_success(explicit) == (
        ChangedFileEntry("one.py", "modified"),
        ChangedFileEntry("two.py", "modified"),
    )
    assert hunk_calls == 2


def test_implicit_range_guard_counts_included_untracked_before_target_filter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "tracked.py", "before\n")
    commit_all(repo, "base")
    git(repo, "branch", "-M", "main")
    write_file(repo / "tracked.py", "after\n")
    write_file(repo / "notes.txt", "untracked non-Python\n")
    monkeypatch.setattr(diff_collect, "MAX_IMPLICIT_DIFF_CHANGED_PATHS", 1)

    result = collect_diff_files(
        request(repo, base_ref=None),
        context(repo),
        config(include_untracked=True),
    )

    assert_error(result, code="diff_implicit_range_too_broad")
    assert "2 changed paths" in result.diagnostics[0].message


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


def test_nested_project_rename_uses_vcs_paths_for_hunk_and_project_paths_for_dto(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    project = repo / "packages" / "app"
    write_file(project / "old.py", "class Model:\n    value = 1\n    keep = True\n    stable = True\n")
    commit_all(repo, "base")
    tag_base(repo)
    git(repo, "mv", "packages/app/old.py", "packages/app/new.py")
    write_file(project / "new.py", "class Model:\n    value = 2\n    keep = True\n    stable = True\n")

    result = collect_diff_files(
        request(project),
        context(repo, project_root=project),
        config(),
    )

    (entry,) = assert_success(result)
    assert entry.current_project_relative_path == "new.py"
    assert entry.previous_project_relative_path == "old.py"
    assert entry.current_changed_line_ranges == (ChangedLineRange(start=2, end=2),)


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
            diff_collect._RawChangedFileEntry("z.py", "modified"),
            diff_collect._RawChangedFileEntry("a.py", "added"),
            diff_collect._RawChangedFileEntry("z.py", "renamed", "old_z.py"),
        ],
    )

    result = collect_diff_files(request(repo), context(repo), config())

    assert assert_success(result) == (
        ChangedFileEntry("a.py", "added"),
        ChangedFileEntry("z.py", "renamed", "old_z.py"),
    )
