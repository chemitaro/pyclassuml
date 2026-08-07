from pathlib import Path
import os
import shutil
import subprocess

import pytest

from pyclassuml.cli.main import main


REPO_ROOT = Path(__file__).resolve().parents[2]


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", "-C", str(repo), *args),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def init_repo(path: Path) -> Path:
    path.mkdir()
    subprocess.run(("git", "init", str(path)), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    git(path, "config", "user.name", "pyclassuml test")
    git(path, "config", "user.email", "pyclassuml@example.test")
    return path


def write_file(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def commit_all(repo: Path, message: str) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message)


def tag_base(repo: Path) -> None:
    git(repo, "tag", "base")


def cleanup_console_script_generated_state(existing_paths: set[Path]) -> None:
    for path in (REPO_ROOT / "uv.lock", REPO_ROOT / ".venv", REPO_ROOT / "build"):
        if path.exists() and path not in existing_paths:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    for path in (REPO_ROOT / "src").glob("*.egg-info"):
        if path in existing_paths:
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def run_console_script(cwd: Path, tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    existing_paths = {
        path
        for path in (
            REPO_ROOT / "uv.lock",
            REPO_ROOT / ".venv",
            REPO_ROOT / "build",
            *((REPO_ROOT / "src").glob("*.egg-info")),
        )
        if path.exists()
    }
    env = {
        **os.environ,
        "PYTHONPYCACHEPREFIX": str(tmp_path / "pycache"),
        "UV_CACHE_DIR": str(tmp_path / "uv-cache"),
        "UV_LINK_MODE": "copy",
        "UV_PYTHON_DOWNLOADS": "never",
    }

    try:
        result = subprocess.run(
            (
                "uv",
                "run",
                "--quiet",
                "--no-project",
                "--isolated",
                "--with",
                str(REPO_ROOT),
                "pyclassuml",
                *args,
            ),
            cwd=cwd,
            env=env,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
        return subprocess.CompletedProcess(
            result.args,
            result.returncode,
            stdout=result.stdout,
            stderr=clean_uv_wrapper_stderr(result.stderr),
        )
    finally:
        cleanup_console_script_generated_state(existing_paths)


def clean_uv_wrapper_stderr(stderr: str) -> str:
    kept_lines = [
        line
        for line in stderr.splitlines()
        if not _is_uv_wrapper_warning(line)
    ]
    if not kept_lines:
        return ""
    return "\n".join(kept_lines) + "\n"


def _is_uv_wrapper_warning(line: str) -> bool:
    return line.startswith("WARN `--no-project` was provided") or line.startswith(
        "WARN Skipping file for setuptools:"
    )


def test_console_script_boundary_runs_via_uv_help(tmp_path: Path) -> None:
    result = run_console_script(tmp_path, tmp_path, "--help")

    assert result.returncode == 0
    assert "usage: pyclassuml" in result.stdout


def test_console_script_boundary_runs_generate_via_uv(tmp_path: Path) -> None:
    project = tmp_path / "project"
    write_file(project / "pkg" / "model.py", "class User:\n    pass\n")

    result = run_console_script(project, tmp_path, "generate", "pkg/model.py", "--output", "diagram.puml")

    artifact_text = (project / "diagram.puml").read_text(encoding="utf-8")
    assert result.returncode == 0
    assert "outcome: clean_success" in result.stdout
    assert "extracted_class_count: 1" in result.stdout
    assert result.stderr == ""
    assert 'class "User"' in artifact_text


def test_console_script_boundary_runs_diff_default_include_untracked_via_uv(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "tracked.py", "class Tracked:\n    pass\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "tracked.py", "class Tracked:\n    value = 1\n")
    write_file(repo / "pkg" / "untracked.py", "class Untracked:\n    pass\n")

    result = run_console_script(repo, tmp_path, "diff", "--base", "base", "--output", "diff.puml")

    artifact_text = (repo / "diff.puml").read_text(encoding="utf-8")
    assert result.returncode == 0
    assert "seed_file_count: 2" in result.stdout
    assert "changed_class_count: 2" in result.stdout
    assert result.stderr == ""
    assert 'class "Tracked"' in artifact_text
    assert 'class "Untracked"' in artifact_text


def test_console_script_boundary_runs_diff_no_include_untracked_via_uv(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "tracked.py", "class Tracked:\n    pass\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "tracked.py", "class Tracked:\n    value = 1\n")
    write_file(repo / "pkg" / "untracked.py", "class Untracked:\n    pass\n")

    result = run_console_script(
        repo,
        tmp_path,
        "diff",
        "--base",
        "base",
        "--no-include-untracked",
        "--output",
        "diff.puml",
    )

    artifact_text = (repo / "diff.puml").read_text(encoding="utf-8")
    assert result.returncode == 0
    assert "seed_file_count: 1" in result.stdout
    assert "changed_class_count: 1" in result.stdout
    assert result.stderr == ""
    assert 'class "Tracked"' in artifact_text
    assert 'class "Untracked"' not in artifact_text


def test_console_script_boundary_projects_invalid_base_failure_via_uv(tmp_path: Path) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "model.py", "class User:\n    pass\n")
    commit_all(repo, "base")

    result = run_console_script(repo, tmp_path, "diff", "--base", "missing-ref", "--output", "invalid.puml")

    assert result.returncode == 1
    assert result.stdout == ""
    assert "failure_reason: vcs_read_failure" in result.stderr
    assert "error:invalid_base_ref:" in result.stderr
    assert not (repo / "invalid.puml").exists()


def test_main_help_projects_argparse_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(("--help",))
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "usage: pyclassuml" in captured.out
    assert captured.err == ""


def test_diff_help_documents_implicit_base_policy(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(("diff", "--help"))
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "default branch" in captured.out
    assert "default branchのheadでは" in captured.out
    assert "HEAD~1" in captured.out
    assert captured.err == ""


def test_main_generate_writes_summary_stdout_and_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = tmp_path / "project"
    write_file(project / "pkg" / "model.py", "class User:\n    pass\n")
    monkeypatch.chdir(project)

    exit_code = main(("generate", "pkg/model.py", "--output", "diagram.puml"))
    captured = capsys.readouterr()

    artifact_text = (project / "diagram.puml").read_text(encoding="utf-8")
    assert exit_code == 0
    assert "outcome: clean_success" in captured.out
    assert "extracted_class_count: 1" in captured.out
    assert captured.err == ""
    assert 'class "User"' in artifact_text


def test_main_diff_default_includes_untracked_python(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "tracked.py", "class Tracked:\n    pass\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "tracked.py", "class Tracked:\n    value = 1\n")
    write_file(repo / "pkg" / "untracked.py", "class Untracked:\n    pass\n")
    monkeypatch.chdir(repo)

    exit_code = main(("diff", "--base", "base", "--output", "diff.puml"))
    captured = capsys.readouterr()

    artifact_text = (repo / "diff.puml").read_text(encoding="utf-8")
    assert exit_code == 0
    assert "seed_file_count: 2" in captured.out
    assert "changed_class_count: 2" in captured.out
    assert captured.err == ""
    assert 'class "Tracked"' in artifact_text
    assert 'class "Untracked"' in artifact_text


def test_main_diff_no_base_projects_resolved_base_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "model.py", "class User:\n    pass\n")
    commit_all(repo, "base")
    git(repo, "branch", "-M", "main")
    base_sha = git(repo, "rev-parse", "HEAD").stdout.strip()
    git(repo, "checkout", "-b", "feature")
    write_file(repo / "pkg" / "model.py", "class User:\n    value = 1\n")
    monkeypatch.chdir(repo)

    exit_code = main(("diff", "--output", "diff.puml"))
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "outcome: clean_success" in captured.out
    assert "base_resolution: default_branch_merge_base" in captured.out
    assert f"resolved_base: {base_sha}" in captured.out
    assert "requested_base: none" in captured.out
    assert "base_candidate: main" in captured.out
    assert captured.err == ""
    assert 'class "User"' in (repo / "diff.puml").read_text(encoding="utf-8")


def test_main_diff_no_include_untracked_opt_out_excludes_untracked_python(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "tracked.py", "class Tracked:\n    pass\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "pkg" / "tracked.py", "class Tracked:\n    value = 1\n")
    write_file(repo / "pkg" / "untracked.py", "class Untracked:\n    pass\n")
    monkeypatch.chdir(repo)

    exit_code = main(("diff", "--base", "base", "--no-include-untracked", "--output", "diff.puml"))
    captured = capsys.readouterr()

    artifact_text = (repo / "diff.puml").read_text(encoding="utf-8")
    assert exit_code == 0
    assert "seed_file_count: 1" in captured.out
    assert "changed_class_count: 1" in captured.out
    assert captured.err == ""
    assert 'class "Tracked"' in artifact_text
    assert 'class "Untracked"' not in artifact_text


def test_main_diff_head_default_include_untracked_emits_noop_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "base.py", "class Base:\n    pass\n")
    commit_all(repo, "base")
    tag_base(repo)
    write_file(repo / "head_only.py", "class HeadOnly:\n    pass\n")
    commit_all(repo, "head")
    write_file(repo / "untracked.py", "class Untracked:\n    pass\n")
    monkeypatch.chdir(repo)

    exit_code = main(("diff", "--base", "base", "--current-state", "head", "--output", "head.puml"))
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "warning:head_untracked_noop:" in captured.out
    assert captured.err == ""
    assert "untracked.py" not in (repo / "head.puml").read_text(encoding="utf-8")


def test_main_diff_invalid_base_projects_failure_to_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = init_repo(tmp_path / "repo")
    write_file(repo / "pkg" / "model.py", "class User:\n    pass\n")
    commit_all(repo, "base")
    monkeypatch.chdir(repo)

    exit_code = main(("diff", "--base", "missing-ref", "--output", "invalid.puml"))
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "failure_reason: vcs_read_failure" in captured.err
    assert "error:invalid_base_ref:" in captured.err
    assert not (repo / "invalid.puml").exists()
