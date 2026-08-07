from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().with_name("run_pyclassuml.py")
REPOSITORY = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location("pyclassuml_repo_map_runner", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("failed to load runner module")
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)


def run_process(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("python3", str(SCRIPT), *args),
        text=True,
        capture_output=True,
        check=False,
    )


def git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", "-C", str(repo), *args),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr)
    return completed.stdout.strip()


def initialize_git_repo(repo: Path) -> None:
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "PyClassUML Skill Test")
    git(repo, "config", "user.email", "skill-test@example.invalid")


class RunnerIntegrationTests(unittest.TestCase):
    def test_child_process_receives_safety_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            output = root / "evidence"
            console_script = repo / ".venv" / "bin" / "pyclassuml"
            (repo / "src" / "pyclassuml").mkdir(parents=True)
            console_script.parent.mkdir(parents=True)
            (repo / "pyproject.toml").write_text(
                '[project]\nname = "pyclassuml"\n', encoding="utf-8"
            )
            (repo / "model.py").write_text("class Model:\n    pass\n", encoding="utf-8")
            console_script.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, pathlib, sys\n"
                "output = pathlib.Path(sys.argv[sys.argv.index('--output') + 1])\n"
                "output.write_text('@startuml\\n@enduml\\n', encoding='utf-8')\n"
                "(output.parent / 'child-env.json').write_text(json.dumps({\n"
                "    'PYTHONDONTWRITEBYTECODE': os.environ.get('PYTHONDONTWRITEBYTECODE'),\n"
                "    'PYTHONSAFEPATH': os.environ.get('PYTHONSAFEPATH'),\n"
                "}), encoding='utf-8')\n"
                "print('outcome: clean_success')\n",
                encoding="utf-8",
            )
            console_script.chmod(0o700)

            completed = run_process(
                "generate",
                "--repo",
                str(repo),
                "--tool-repo",
                str(repo),
                "--output-dir",
                str(output),
                "model.py",
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            observed = json.loads(
                (output / "child-env.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                observed,
                {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONSAFEPATH": "1"},
            )

    def test_generate_unique_class_keeps_depth_unset_and_repository_unchanged(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            output = root / "evidence"
            package = repo / "src" / "sample"
            package.mkdir(parents=True)
            (package / "service.py").write_text(
                "class OrderService:\n    pass\n", encoding="utf-8"
            )
            initialize_git_repo(repo)
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "initial")
            before = git(repo, "status", "--porcelain=v2", "--untracked-files=all")

            completed = run_process(
                "generate",
                "--repo",
                str(repo),
                "--project-root",
                ".",
                "--package-root",
                "src",
                "--scope-root",
                "src",
                "--tool-repo",
                str(REPOSITORY),
                "--output-dir",
                str(output),
                "--class-name",
                "OrderService",
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(Path(completed.stdout.strip()), output.resolve())
            self.assertEqual(
                before, git(repo, "status", "--porcelain=v2", "--untracked-files=all")
            )
            evidence = json.loads(
                (output / "run-evidence.json").read_text(encoding="utf-8")
            )
            self.assertNotIn("--depth", evidence["pyclassuml"]["argv"])
            self.assertEqual(evidence["configuration"]["source"], "synthetic_empty")
            self.assertEqual(evidence["tool"]["source"], "local_checkout")
            self.assertEqual(len(evidence["tool"]["argv_prefix"]), 1)
            self.assertTrue(
                evidence["tool"]["argv_prefix"][0].endswith("/.venv/bin/pyclassuml")
            )
            self.assertEqual(
                evidence["pyclassuml"]["environment"],
                {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONSAFEPATH": "1"},
            )
            self.assertTrue(evidence["repository"]["worktree_unchanged"])
            self.assertIn(
                str((package / "service.py").resolve()), evidence["pyclassuml"]["argv"]
            )
            self.assertTrue(
                (output / "diagram.puml")
                .read_text(encoding="utf-8")
                .startswith("@startuml")
            )
            self.assertFalse((output / ".pyclassuml-empty.toml").exists())

    def test_ambiguous_class_stops_before_child_and_writes_complete_bundle(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            output = root / "evidence"
            repo.mkdir()
            (repo / "one.py").write_text(
                "class Duplicate:\n    pass\n", encoding="utf-8"
            )
            (repo / "two.py").write_text(
                "class Duplicate:\n    pass\n", encoding="utf-8"
            )

            completed = run_process(
                "generate",
                "--repo",
                str(repo),
                "--output-dir",
                str(output),
                "--class-name",
                "Duplicate",
            )

            self.assertEqual(completed.returncode, 2)
            self.assertEqual(Path(completed.stdout.strip()), output.resolve())
            for name in (
                "diagram.puml",
                "run-evidence.json",
                "stdout.log",
                "stderr.log",
            ):
                self.assertTrue((output / name).is_file(), name)
            self.assertEqual((output / "diagram.puml").stat().st_size, 0)
            evidence = json.loads(
                (output / "run-evidence.json").read_text(encoding="utf-8")
            )
            self.assertEqual(evidence["status"], "needs_input")
            self.assertNotIn("pyclassuml", evidence)
            candidates = json.loads(
                (output / "class-candidates.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(candidates["matches"]["Duplicate"]), 2)

    def test_committed_a_to_b_uses_and_removes_clone_without_touching_dirty_target(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            output = root / "evidence"
            package = repo / "pkg"
            package.mkdir(parents=True)
            model = package / "model.py"
            model.write_text("class Model:\n    value = 1\n", encoding="utf-8")
            initialize_git_repo(repo)
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "a")
            commit_a = git(repo, "rev-parse", "HEAD")
            model.write_text("class Model:\n    value = 2\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "b")
            commit_b = git(repo, "rev-parse", "HEAD")
            (repo / "dirty.py").write_text("class Dirty:\n    pass\n", encoding="utf-8")
            before = git(repo, "status", "--porcelain=v2", "--untracked-files=all")

            completed = run_process(
                "diff",
                "--repo",
                str(repo),
                "--project-root",
                ".",
                "--package-root",
                ".",
                "--scope-root",
                ".",
                "--tool-repo",
                str(REPOSITORY),
                "--output-dir",
                str(output),
                "--base",
                commit_a,
                "--end",
                commit_b,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                before, git(repo, "status", "--porcelain=v2", "--untracked-files=all")
            )
            evidence = json.loads(
                (output / "run-evidence.json").read_text(encoding="utf-8")
            )
            self.assertEqual(evidence["comparison"]["resolved_base"], commit_a)
            self.assertEqual(evidence["comparison"]["resolved_end"], commit_b)
            self.assertTrue(evidence["comparison"]["disposable_clone_removed"])
            self.assertFalse((output / "disposable-clone").exists())
            self.assertTrue(evidence["repository"]["worktree_unchanged"])
            argv = evidence["pyclassuml"]["argv"]
            self.assertIn("--current-state", argv)
            self.assertIn("head", argv)
            self.assertIn("--no-include-untracked", argv)

    def test_repository_config_is_selected_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            output = root / "evidence"
            repo.mkdir()
            (repo / ".pyclassuml.toml").write_text("depth = 0\n", encoding="utf-8")
            (repo / "model.py").write_text("class Model:\n    pass\n", encoding="utf-8")

            completed = run_process(
                "generate",
                "--repo",
                str(repo),
                "--tool-repo",
                str(REPOSITORY),
                "--output-dir",
                str(output),
                "model.py",
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            evidence = json.loads(
                (output / "run-evidence.json").read_text(encoding="utf-8")
            )
            self.assertEqual(evidence["configuration"]["source"], "repository")
            self.assertIn(
                str((repo / ".pyclassuml.toml").resolve()),
                evidence["pyclassuml"]["argv"],
            )

    def test_symlinked_skill_resolves_owning_tool_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            output = root / "evidence"
            skill_link = root / "installed-skill"
            repo.mkdir()
            (repo / "model.py").write_text("class Model:\n    pass\n", encoding="utf-8")
            skill_link.symlink_to(SCRIPT.parents[1], target_is_directory=True)

            completed = subprocess.run(
                (
                    "python3",
                    str(skill_link / "scripts" / "run_pyclassuml.py"),
                    "generate",
                    "--repo",
                    str(repo),
                    "--output-dir",
                    str(output),
                    "model.py",
                ),
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            evidence = json.loads(
                (output / "run-evidence.json").read_text(encoding="utf-8")
            )
            self.assertEqual(evidence["tool"]["source"], "local_checkout")
            self.assertEqual(evidence["tool"]["repository"], str(REPOSITORY.resolve()))

    def test_child_failure_still_writes_complete_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            output = root / "evidence"
            repo.mkdir()
            (repo / "model.py").write_text("class Model:\n    pass\n", encoding="utf-8")
            initialize_git_repo(repo)
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "initial")

            completed = run_process(
                "diff",
                "--repo",
                str(repo),
                "--tool-repo",
                str(REPOSITORY),
                "--output-dir",
                str(output),
            )

            self.assertEqual(completed.returncode, 1)
            for name in (
                "diagram.puml",
                "run-evidence.json",
                "stdout.log",
                "stderr.log",
            ):
                self.assertTrue((output / name).is_file(), name)
            self.assertEqual((output / "diagram.puml").stat().st_size, 0)
            evidence = json.loads(
                (output / "run-evidence.json").read_text(encoding="utf-8")
            )
            self.assertEqual(evidence["status"], "failed")
            self.assertEqual(evidence["pyclassuml"]["exit_code"], 1)
            self.assertTrue(evidence["source_verification_required"])

    def test_compare_config_missing_at_endpoint_removes_clone(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            output = root / "evidence"
            repo.mkdir()
            (repo / "model.py").write_text(
                "class Model:\n    value = 1\n", encoding="utf-8"
            )
            initialize_git_repo(repo)
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "a")
            commit_a = git(repo, "rev-parse", "HEAD")
            (repo / "model.py").write_text(
                "class Model:\n    value = 2\n", encoding="utf-8"
            )
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "b")
            commit_b = git(repo, "rev-parse", "HEAD")
            (repo / ".pyclassuml.toml").write_text("depth = 1\n", encoding="utf-8")

            completed = run_process(
                "diff",
                "--repo",
                str(repo),
                "--tool-repo",
                str(REPOSITORY),
                "--output-dir",
                str(output),
                "--config",
                ".pyclassuml.toml",
                "--base",
                commit_a,
                "--end",
                commit_b,
            )

            self.assertEqual(completed.returncode, 2)
            evidence = json.loads(
                (output / "run-evidence.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                evidence["runner_error"]["code"], "config_missing_at_endpoint"
            )
            self.assertTrue(evidence["comparison"]["disposable_clone_removed"])
            self.assertFalse((output / "disposable-clone").exists())

    def test_partial_clone_is_removed_when_clone_setup_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            output = root / "evidence"
            repo.mkdir()
            (repo / "model.py").write_text(
                "class Model:\n    value = 1\n", encoding="utf-8"
            )
            initialize_git_repo(repo)
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "a")
            commit_a = git(repo, "rev-parse", "HEAD")
            (repo / "model.py").write_text(
                "class Model:\n    value = 2\n", encoding="utf-8"
            )
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "b")
            commit_b = git(repo, "rev-parse", "HEAD")

            def fail_after_clone(_repo: Path, clone: Path, _end_sha: str) -> None:
                clone.mkdir()
                (clone / "partial").write_text("partial", encoding="utf-8")
                raise RUNNER.RunnerFailure("command_failed", "checkout failed")

            stdout = io.StringIO()
            stderr = io.StringIO()
            with (
                mock.patch.object(
                    RUNNER, "_clone_for_end", side_effect=fail_after_clone
                ),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                exit_code = RUNNER.run(
                    (
                        "diff",
                        "--repo",
                        str(repo),
                        "--tool-repo",
                        str(REPOSITORY),
                        "--output-dir",
                        str(output),
                        "--base",
                        commit_a,
                        "--end",
                        commit_b,
                    )
                )

            self.assertEqual(exit_code, 2, stderr.getvalue())
            self.assertFalse((output / "disposable-clone").exists())
            evidence = json.loads(
                (output / "run-evidence.json").read_text(encoding="utf-8")
            )
            self.assertTrue(evidence["comparison"]["disposable_clone_removed"])

    def test_dirty_content_snapshot_changes_when_porcelain_classification_does_not(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            tracked = repo / "tracked.py"
            tracked.write_text("value = 1\n", encoding="utf-8")
            initialize_git_repo(repo)
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "initial")
            tracked.write_text("value = 2\n", encoding="utf-8")
            before = RUNNER._repo_snapshot(repo)
            tracked.write_text("value = 3\n", encoding="utf-8")
            after = RUNNER._repo_snapshot(repo)

            self.assertEqual(
                before["status_porcelain_v2"], after["status_porcelain_v2"]
            )
            self.assertNotEqual(
                before["dirty_content_sha256"], after["dirty_content_sha256"]
            )
            self.assertNotEqual(before["snapshot_sha256"], after["snapshot_sha256"])

    def test_diff_defaults_to_working_tree_and_includes_untracked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            output = root / "evidence"
            repo.mkdir()
            tracked = repo / "tracked.py"
            tracked.write_text("class Tracked:\n    value = 1\n", encoding="utf-8")
            initialize_git_repo(repo)
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "initial")
            tracked.write_text("class Tracked:\n    value = 2\n", encoding="utf-8")
            (repo / "untracked.py").write_text(
                "class Untracked:\n    pass\n", encoding="utf-8"
            )

            completed = run_process(
                "diff",
                "--repo",
                str(repo),
                "--tool-repo",
                str(REPOSITORY),
                "--output-dir",
                str(output),
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            evidence = json.loads(
                (output / "run-evidence.json").read_text(encoding="utf-8")
            )
            self.assertEqual(evidence["comparison"]["current_state"], "working-tree")
            self.assertTrue(evidence["comparison"]["include_untracked"])
            argv = evidence["pyclassuml"]["argv"]
            self.assertIn("working-tree", argv)
            self.assertIn("--include-untracked", argv)
            self.assertTrue(evidence["repository"]["worktree_unchanged"])

    def test_output_inside_repository_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary) / "repo"
            repo.mkdir()
            completed = run_process(
                "generate",
                "--repo",
                str(repo),
                "--output-dir",
                str(repo / "evidence"),
                str(repo),
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("output_inside_repository", completed.stderr)

    def test_dirty_worktree_is_rejected_for_head_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo = root / "repo"
            output = root / "evidence"
            repo.mkdir()
            (repo / "model.py").write_text("class Model:\n    pass\n", encoding="utf-8")
            initialize_git_repo(repo)
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "initial")
            (repo / "dirty.py").write_text("class Dirty:\n    pass\n", encoding="utf-8")

            completed = run_process(
                "diff",
                "--repo",
                str(repo),
                "--tool-repo",
                str(REPOSITORY),
                "--output-dir",
                str(output),
                "--current-state",
                "head",
            )

            self.assertEqual(completed.returncode, 2)
            evidence = json.loads(
                (output / "run-evidence.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                evidence["runner_error"]["code"], "clean_worktree_required_for_head"
            )
            self.assertNotIn("pyclassuml", evidence)


if __name__ == "__main__":
    unittest.main()
