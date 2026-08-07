"""Run PyClassUML safely and retain a repository-external evidence bundle."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
FALLBACK_COMMIT = "c669668a9e8af9ef8c1e475bf56a551121c325a6"
FALLBACK_SOURCE = f"git+https://github.com/chemitaro/pyclassuml.git@{FALLBACK_COMMIT}"
IGNORED_SCAN_DIRS = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "__pycache__",
        "site-packages",
        "node_modules",
    }
)


class RunnerFailure(RuntimeError):
    def __init__(
        self, code: str, message: str, *, details: object | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


@dataclass(frozen=True)
class Bundle:
    path: Path
    session_id: str | None
    cleanup_command: str | None


@dataclass(frozen=True)
class ToolCommand:
    source: str
    argv_prefix: tuple[str, ...]
    repository: Path | None
    pinned_commit: str | None


@dataclass(frozen=True)
class Boundaries:
    project_root: Path
    package_root: Path | None
    scope_root: Path | None
    config: Path | None


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _resolve_under(
    root: Path, value: str | Path, field: str, *, must_exist: bool = True
) -> Path:
    raw = Path(value)
    resolved = (raw if raw.is_absolute() else root / raw).resolve()
    if not _is_relative_to(resolved, root):
        raise RunnerFailure(
            "path_outside_repository",
            f"{field} must stay inside repository: {resolved}",
        )
    if must_exist and not resolved.exists():
        raise RunnerFailure("path_not_found", f"{field} does not exist: {resolved}")
    return resolved


def _run(
    argv: Sequence[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        tuple(argv),
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and completed.returncode != 0:
        message = (
            completed.stderr.strip() or completed.stdout.strip() or "command failed"
        )
        raise RunnerFailure("command_failed", f"{argv[0]} failed: {message}")
    return completed


def _git(
    repo: Path, *args: str, check: bool = True, safe_checkout: bool = False
) -> subprocess.CompletedProcess[str]:
    argv = ["git"]
    if safe_checkout:
        argv.extend(("-c", "core.hooksPath=/dev/null"))
    argv.extend(("-C", str(repo), *args))
    env = os.environ.copy()
    env.update({"GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"})
    if safe_checkout:
        env.update(
            {
                "GIT_CONFIG_GLOBAL": "/dev/null",
                "GIT_CONFIG_SYSTEM": "/dev/null",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_LFS_SKIP_SMUDGE": "1",
            }
        )
    return _run(argv, env=env, check=check)


def _git_output(repo: Path, *args: str, required: bool = False) -> str | None:
    result = _git(repo, *args, check=False)
    if result.returncode != 0:
        if required:
            message = (
                result.stderr.strip() or result.stdout.strip() or "git command failed"
            )
            raise RunnerFailure("git_read_failed", message)
        return None
    return result.stdout.strip()


def _repo_snapshot(repo: Path) -> dict[str, Any]:
    top_level = _git_output(repo, "rev-parse", "--show-toplevel")
    if top_level is None:
        return {"is_git_repository": False}
    status = (
        _git_output(
            repo,
            "status",
            "--porcelain=v2",
            "-z",
            "--untracked-files=all",
            required=True,
        )
        or ""
    )
    head = _git_output(repo, "rev-parse", "HEAD")
    branch = _git_output(repo, "branch", "--show-current") or None
    dirty_content_sha256 = _dirty_content_sha256(Path(top_level).resolve())
    digest_input = f"{head or ''}\0{status}\0{dirty_content_sha256}".encode(
        "utf-8", errors="surrogateescape"
    )
    return {
        "is_git_repository": True,
        "top_level": str(Path(top_level).resolve()),
        "head": head,
        "branch": branch,
        "status_porcelain_v2": [entry for entry in status.split("\0") if entry],
        "dirty_content_sha256": dirty_content_sha256,
        "snapshot_sha256": hashlib.sha256(digest_input).hexdigest(),
    }


def _dirty_content_sha256(vcs_root: Path) -> str:
    paths: set[str] = set()
    commands = (
        ("diff", "--name-only", "-z"),
        ("diff", "--cached", "--name-only", "-z"),
        ("ls-files", "--others", "--exclude-standard", "-z"),
    )
    for command in commands:
        output = _git_output(vcs_root, *command) or ""
        paths.update(path for path in output.split("\0") if path)

    digest = hashlib.sha256()
    for relative in sorted(paths):
        digest.update(relative.encode("utf-8", errors="surrogateescape"))
        digest.update(b"\0")
        candidate = vcs_root / relative
        try:
            if candidate.is_symlink():
                digest.update(b"symlink\0")
                digest.update(
                    os.readlink(candidate).encode("utf-8", errors="surrogateescape")
                )
            elif candidate.is_file():
                digest.update(b"file\0")
                with candidate.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
            elif candidate.exists():
                digest.update(b"other\0")
            else:
                digest.update(b"missing\0")
        except OSError as exc:
            digest.update(
                f"error:{type(exc).__name__}:{exc}".encode("utf-8", errors="replace")
            )
        digest.update(b"\0")
    return digest.hexdigest()


def _find_codex_tmp() -> Path | None:
    candidates: list[Path] = []
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        candidates.append(Path(codex_home) / "scripts" / "codex-tmp")
    candidates.append(Path.home() / ".codex" / "scripts" / "codex-tmp")
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    return None


def _create_bundle(repo: Path, output_dir: str | None) -> Bundle:
    if output_dir is not None:
        path = Path(output_dir).expanduser().resolve()
        if _is_relative_to(path, repo):
            raise RunnerFailure(
                "output_inside_repository",
                f"evidence output must be outside repository: {path}",
            )
        if path.exists() and any(path.iterdir()):
            raise RunnerFailure(
                "output_not_empty", f"evidence output directory is not empty: {path}"
            )
        path.mkdir(parents=True, exist_ok=True)
        return Bundle(path=path, session_id=None, cleanup_command=None)

    codex_tmp = _find_codex_tmp()
    if codex_tmp is not None:
        result = _run(
            (str(codex_tmp), "init-session", "pyclassuml-repo-map"), check=True
        )
        session_path = Path(result.stdout.strip()).resolve()
        path = session_path / "evidence"
        path.mkdir(mode=0o700)
        session_id = session_path.name
        cleanup = f"{codex_tmp} clean-session {session_id} --yes"
        return Bundle(path=path, session_id=session_id, cleanup_command=cleanup)

    path = Path(tempfile.mkdtemp(prefix="pyclassuml-repo-map-")).resolve()
    if _is_relative_to(path, repo):
        raise RunnerFailure(
            "output_inside_repository",
            f"temporary output resolved inside repository: {path}",
        )
    return Bundle(path=path, session_id=None, cleanup_command=None)


def _looks_like_pyclassuml_repo(path: Path) -> bool:
    pyproject = path / "pyproject.toml"
    package = path / "src" / "pyclassuml"
    if not pyproject.is_file() or not package.is_dir():
        return False
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError:
        return False
    return 'name = "pyclassuml"' in text


def _owning_tool_repo() -> Path | None:
    resolved = Path(__file__).resolve()
    for parent in resolved.parents:
        if _looks_like_pyclassuml_repo(parent):
            return parent
    return None


def _local_console_script(repository: Path) -> Path | None:
    candidates = (
        repository / ".venv" / "bin" / "pyclassuml",
        repository / ".venv" / "Scripts" / "pyclassuml.exe",
    )
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    return None


def _resolve_tool(tool_repo_arg: str | None) -> ToolCommand:
    candidates: list[Path] = []
    if tool_repo_arg:
        candidates.append(Path(tool_repo_arg).expanduser().resolve())
    env_repo = os.environ.get("PYCLASSUML_REPO")
    if env_repo:
        candidates.append(Path(env_repo).expanduser().resolve())
    owning = _owning_tool_repo()
    if owning is not None:
        candidates.append(owning)

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if not _looks_like_pyclassuml_repo(candidate):
            if (
                tool_repo_arg
                and candidate == Path(tool_repo_arg).expanduser().resolve()
            ):
                raise RunnerFailure(
                    "invalid_tool_repository", f"not a PyClassUML checkout: {candidate}"
                )
            continue
        console_script = _local_console_script(candidate)
        if console_script is None:
            continue
        return ToolCommand(
            source="local_checkout",
            argv_prefix=(str(console_script),),
            repository=candidate,
            pinned_commit=_git_output(candidate, "rev-parse", "HEAD"),
        )

    uvx = shutil.which("uvx")
    if uvx is None:
        raise RunnerFailure(
            "tool_unavailable",
            "neither a usable local PyClassUML checkout nor uvx was found",
        )
    return ToolCommand(
        source="exact_uvx_fallback",
        argv_prefix=(uvx, "--from", FALLBACK_SOURCE, "pyclassuml"),
        repository=None,
        pinned_commit=FALLBACK_COMMIT,
    )


def _resolve_boundaries(repo: Path, args: argparse.Namespace) -> Boundaries:
    project = _resolve_under(repo, args.project_root or ".", "project_root")
    if not project.is_dir():
        raise RunnerFailure(
            "invalid_project_root", f"project_root is not a directory: {project}"
        )
    package = (
        _resolve_under(repo, args.package_root, "package_root")
        if args.package_root
        else None
    )
    scope = (
        _resolve_under(repo, args.scope_root, "scope_root") if args.scope_root else None
    )
    config = _resolve_under(repo, args.config, "config") if args.config else None
    package_parent = project
    if package is not None and not _is_relative_to(package, project):
        raise RunnerFailure(
            "invalid_containment", "package_root must be inside project_root"
        )
    if package is not None:
        package_parent = package
    if scope is not None and not _is_relative_to(scope, package_parent):
        raise RunnerFailure(
            "invalid_containment",
            "scope_root must be inside package_root or project_root",
        )
    if config is not None and not config.is_file():
        raise RunnerFailure("invalid_config", f"config is not a file: {config}")
    return Boundaries(
        project_root=project, package_root=package, scope_root=scope, config=config
    )


def _map_path(path: Path | None, source: Path, destination: Path) -> Path | None:
    if path is None:
        return None
    return destination / path.relative_to(source)


def _common_pyclassuml_args(
    execution_repo: Path,
    source_repo: Path,
    boundaries: Boundaries,
    args: argparse.Namespace,
    output: Path,
    config: Path,
) -> list[str]:
    project = _map_path(boundaries.project_root, source_repo, execution_repo)
    package = _map_path(boundaries.package_root, source_repo, execution_repo)
    scope = _map_path(boundaries.scope_root, source_repo, execution_repo)
    if project is None:
        raise RunnerFailure("internal_error", "project_root mapping failed")
    argv = [
        "--cwd",
        str(execution_repo),
        "--project-root",
        str(project),
        "--output",
        str(output),
    ]
    if package is not None:
        argv.extend(("--package-root", str(package)))
    if scope is not None:
        argv.extend(("--scope-root", str(scope)))
    argv.extend(("--config", str(config)))
    for pattern in args.ignore:
        argv.extend(("--ignore", pattern))
    if args.depth is not None:
        argv.extend(("--depth", str(args.depth)))
    if args.strict:
        argv.append("--strict")
    if args.target_python:
        argv.extend(("--target-python", args.target_python))
    return argv


def _select_config(
    execution_repo: Path,
    source_repo: Path,
    boundaries: Boundaries,
    bundle: Bundle,
) -> tuple[Path, str]:
    if boundaries.config is not None:
        mapped = _map_path(boundaries.config, source_repo, execution_repo)
        if mapped is None or not mapped.is_file():
            raise RunnerFailure(
                "config_missing_at_endpoint",
                "explicit config does not exist at analysis endpoint",
            )
        return mapped, "explicit"
    project = _map_path(boundaries.project_root, source_repo, execution_repo)
    if project is None:
        raise RunnerFailure("internal_error", "project_root mapping failed")
    repository_config = project / ".pyclassuml.toml"
    if repository_config.is_file():
        return repository_config, "repository"
    synthetic = bundle.path / ".pyclassuml-empty.toml"
    synthetic.write_text("", encoding="utf-8")
    return synthetic, "synthetic_empty"


def _module_name(path: Path, base: Path) -> str:
    relative = path.relative_to(base).with_suffix("")
    parts = list(relative.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _class_candidates(
    boundaries: Boundaries,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scan_root = (
        boundaries.scope_root or boundaries.package_root or boundaries.project_root
    )
    module_base = boundaries.package_root or boundaries.project_root
    candidates: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for path in sorted(scan_root.rglob("*.py")):
        if any(part in IGNORED_SCAN_DIRS for part in path.relative_to(scan_root).parts):
            continue
        resolved_path = path.resolve()
        if not _is_relative_to(resolved_path, scan_root):
            diagnostics.append(
                {"file": str(path), "error": "symlink target escapes scan root"}
            )
            continue
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, UnicodeError, SyntaxError) as exc:
            diagnostics.append(
                {"file": str(path), "error": f"{type(exc).__name__}: {exc}"}
            )
            continue
        module = _module_name(path, module_base)

        def visit(
            body: Sequence[ast.stmt],
            parents: tuple[str, ...] = (),
            *,
            module_name: str = module,
            source_path: Path = path,
        ) -> None:
            for node in body:
                if not isinstance(node, ast.ClassDef):
                    continue
                nested = (*parents, node.name)
                class_qualname = ".".join(nested)
                qualified = (
                    f"{module_name}.{class_qualname}" if module_name else class_qualname
                )
                relative = source_path.relative_to(boundaries.project_root).as_posix()
                candidates.append(
                    {
                        "class_name": node.name,
                        "class_qualname": class_qualname,
                        "qualified_name": qualified,
                        "file": str(source_path),
                        "project_relative_file": relative,
                        "line": node.lineno,
                        "selector": f"{relative}:{class_qualname}",
                    }
                )
                visit(node.body, nested)

        visit(tree.body)
    return candidates, diagnostics


def _resolve_classes(
    queries: Sequence[str], boundaries: Boundaries
) -> tuple[list[Path], dict[str, Any], bool]:
    if not queries:
        return [], {"queries": [], "matches": {}, "scan_diagnostics": []}, False
    candidates, diagnostics = _class_candidates(boundaries)
    matches: dict[str, list[dict[str, Any]]] = {}
    selected: list[Path] = []
    needs_input = False
    for query in queries:
        found = [
            candidate
            for candidate in candidates
            if query
            in {
                candidate["class_name"],
                candidate["class_qualname"],
                candidate["qualified_name"],
                candidate["selector"],
            }
        ]
        matches[query] = found
        if len(found) != 1:
            needs_input = True
        else:
            path = Path(found[0]["file"])
            if path not in selected:
                selected.append(path)
    return (
        selected,
        {"queries": list(queries), "matches": matches, "scan_diagnostics": diagnostics},
        needs_input,
    )


def _contains_glob(value: str) -> bool:
    return any(character in value for character in "*?[")


def _generate_targets(
    repo: Path, raw_targets: Sequence[str], class_files: Sequence[Path]
) -> list[str]:
    targets: list[str] = []
    for value in raw_targets:
        if _contains_glob(value):
            targets.append(value)
            continue
        targets.append(str(_resolve_under(repo, value, "target")))
    for path in class_files:
        rendered = str(path)
        if rendered not in targets:
            targets.append(rendered)
    if not targets:
        raise RunnerFailure(
            "generate_requires_target", "generate requires a target or --class-name"
        )
    return targets


def _resolve_commit(repo: Path, ref: str, field: str) -> str:
    if ref.startswith("-") or any(character in ref for character in ("\0", "\n", "\r")):
        raise RunnerFailure("invalid_git_ref", f"unsafe {field} ref: {ref!r}")
    value = _git_output(
        repo,
        "rev-parse",
        "--verify",
        "--end-of-options",
        f"{ref}^{{commit}}",
        required=True,
    )
    if value is None:
        raise RunnerFailure(
            "invalid_git_ref", f"{field} does not resolve to a commit: {ref}"
        )
    return value


def _clone_for_end(repo: Path, clone: Path, end_sha: str) -> None:
    env = os.environ.copy()
    env.update(
        {
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_CONFIG_SYSTEM": "/dev/null",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_LFS_SKIP_SMUDGE": "1",
        }
    )
    result = _run(
        (
            "git",
            "-c",
            "core.hooksPath=/dev/null",
            "clone",
            "--no-hardlinks",
            "--no-checkout",
            "--quiet",
            str(repo),
            str(clone),
        ),
        env=env,
    )
    if result.returncode != 0:
        raise RunnerFailure(
            "clone_failed", result.stderr.strip() or "failed to create disposable clone"
        )
    _git(clone, "checkout", "--detach", "--quiet", end_sha, safe_checkout=True)


def _parse_summary(stdout: str, stderr: str) -> dict[str, Any]:
    text = stdout if stdout.strip() else stderr
    summary: dict[str, Any] = {}
    counters: dict[str, int] = {}
    in_counters = False
    diagnostics: list[str] = []
    in_diagnostics = False
    for line in text.splitlines():
        if line == "counters:":
            in_counters = True
            in_diagnostics = False
            continue
        if line == "diagnostics:":
            in_counters = False
            in_diagnostics = True
            continue
        if in_diagnostics:
            diagnostics.append(line)
            continue
        if ": " not in line:
            continue
        key, value = line.split(": ", 1)
        if in_counters:
            try:
                counters[key] = int(value)
            except ValueError:
                continue
        else:
            summary[key] = value
    if counters:
        summary["counters"] = counters
    if diagnostics:
        summary["diagnostics"] = diagnostics
    return summary


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_inventory(bundle: Bundle) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for name in ("diagram.puml", "stdout.log", "stderr.log", "class-candidates.json"):
        path = bundle.path / name
        if not path.is_file():
            continue
        artifacts.append(
            {"path": str(path), "size": path.stat().st_size, "sha256": _sha256(path)}
        )
    return artifacts


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", default=".", help="Analyzed repository root")
    parser.add_argument("--project-root")
    parser.add_argument("--package-root")
    parser.add_argument("--scope-root")
    parser.add_argument("--config")
    parser.add_argument("--output-dir")
    parser.add_argument("--tool-repo")
    parser.add_argument("--ignore", action="append", default=[])
    parser.add_argument("--depth", type=_non_negative_int)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--target-python", type=_target_python)


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return parsed


def _target_python(value: str) -> str:
    parts = value.split(".")
    if len(parts) != 2 or parts[0] != "3" or not parts[1].isdigit():
        raise argparse.ArgumentTypeError("must be a 3.<minor> string")
    return value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="run_pyclassuml.py")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate")
    _add_common_options(generate)
    generate.add_argument("--class-name", action="append", default=[])
    generate.add_argument("targets", nargs="*")
    generate.set_defaults(fetch=False)

    diff = subparsers.add_parser("diff")
    _add_common_options(diff)
    diff.add_argument("--base")
    diff.add_argument("--end")
    diff.add_argument(
        "--fetch",
        action="store_true",
        help="Explicitly refresh remote refs before analysis",
    )
    diff.add_argument(
        "--current-state", choices=("working-tree", "head"), default="working-tree"
    )
    diff.add_argument(
        "--include-untracked",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        print(
            f"repository does not exist or is not a directory: {repo}", file=sys.stderr
        )
        return 2
    try:
        bundle = _create_bundle(repo, args.output_dir)
    except RunnerFailure as exc:
        print(f"{exc.code}: {exc.message}", file=sys.stderr)
        return 2

    stdout_text = ""
    stderr_text = ""
    clone: Path | None = None
    synthetic_config: Path | None = None
    started_at = _utc_now()
    before = _repo_snapshot(repo)
    evidence: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": str(uuid.uuid4()),
        "started_at": started_at,
        "status": "failed",
        "intent": {
            "command": args.command,
            "fetch": args.fetch,
            "depth_cli": args.depth,
        },
        "bundle": {
            "path": str(bundle.path),
            "session_id": bundle.session_id,
            "cleanup_command": bundle.cleanup_command,
        },
        "repository": {"path": str(repo), "before": before},
        "source_verification_required": True,
    }
    exit_code = 2

    try:
        boundaries = _resolve_boundaries(repo, args)
        evidence["boundaries"] = {
            "project_root": str(boundaries.project_root),
            "package_root": str(boundaries.package_root)
            if boundaries.package_root
            else None,
            "scope_root": str(boundaries.scope_root) if boundaries.scope_root else None,
            "config": str(boundaries.config) if boundaries.config else None,
        }
        if args.command == "diff" and not before.get("is_git_repository"):
            raise RunnerFailure(
                "git_repository_required", "diff requires --repo to be a Git repository"
            )

        if args.fetch:
            if not before.get("is_git_repository"):
                raise RunnerFailure(
                    "git_repository_required", "--fetch requires a Git repository"
                )
            fetch = _git(repo, "fetch", "--prune", check=False)
            evidence["fetch"] = {
                "argv": ["git", "-C", str(repo), "fetch", "--prune"],
                "exit_code": fetch.returncode,
            }
            if fetch.returncode != 0:
                raise RunnerFailure(
                    "fetch_failed",
                    "git fetch failed; inspect Git authentication and remote state",
                )

        tool = _resolve_tool(args.tool_repo)
        evidence["tool"] = {
            "source": tool.source,
            "argv_prefix": list(tool.argv_prefix),
            "repository": str(tool.repository) if tool.repository else None,
            "pinned_commit": tool.pinned_commit,
        }

        class_resolution: dict[str, Any] = {
            "queries": [],
            "matches": {},
            "scan_diagnostics": [],
        }
        execution_repo = repo
        comparison: dict[str, Any] = {}
        command_args: list[str]
        if args.command == "generate":
            class_files, class_resolution, needs_input = _resolve_classes(
                args.class_name, boundaries
            )
            evidence["class_resolution"] = class_resolution
            if needs_input:
                evidence["status"] = "needs_input"
                _write_json(bundle.path / "class-candidates.json", class_resolution)
                missing = [
                    query
                    for query, matches in class_resolution["matches"].items()
                    if not matches
                ]
                ambiguous = [
                    query
                    for query, matches in class_resolution["matches"].items()
                    if len(matches) > 1
                ]
                stderr_text = f"class selection requires input; missing={missing}; ambiguous={ambiguous}\n"
                exit_code = 2
                raise RunnerFailure(
                    "class_selection_required",
                    stderr_text.strip(),
                    details=class_resolution,
                )
            targets = _generate_targets(repo, args.targets, class_files)
            config_path, config_source = _select_config(repo, repo, boundaries, bundle)
            if config_source == "synthetic_empty":
                synthetic_config = config_path
            evidence["configuration"] = {
                "source": config_source,
                "path": str(config_path),
            }
            command_args = [
                "generate",
                *_common_pyclassuml_args(
                    repo,
                    repo,
                    boundaries,
                    args,
                    bundle.path / "diagram.puml",
                    config_path,
                ),
                *targets,
            ]
        else:
            if args.end and not args.base:
                raise RunnerFailure("base_required", "--end requires --base")
            if args.end:
                base_sha = _resolve_commit(repo, args.base, "base")
                end_sha = _resolve_commit(repo, args.end, "end")
                clone = bundle.path / "disposable-clone"
                comparison = {
                    "mode": "committed_a_to_b",
                    "requested_base": args.base,
                    "requested_end": args.end,
                    "resolved_base": base_sha,
                    "resolved_end": end_sha,
                    "current_state": "head",
                    "include_untracked": False,
                    "fetch": args.fetch,
                    "disposable_clone": str(clone),
                }
                evidence["comparison"] = comparison
                _clone_for_end(repo, clone, end_sha)
                execution_repo = clone
                config_path, config_source = _select_config(
                    clone, repo, boundaries, bundle
                )
                if config_source == "synthetic_empty":
                    synthetic_config = config_path
                evidence["configuration"] = {
                    "source": config_source,
                    "path": str(config_path),
                }
                command_args = [
                    "diff",
                    *_common_pyclassuml_args(
                        clone,
                        repo,
                        boundaries,
                        args,
                        bundle.path / "diagram.puml",
                        config_path,
                    ),
                    "--base",
                    base_sha,
                    "--current-state",
                    "head",
                    "--no-include-untracked",
                ]
            else:
                if args.current_state == "head" and before.get("status_porcelain_v2"):
                    raise RunnerFailure(
                        "clean_worktree_required_for_head",
                        "--current-state head requires a clean worktree; use working-tree mode or exact --base/--end",
                    )
                resolved_base = (
                    _resolve_commit(repo, args.base, "base") if args.base else None
                )
                comparison = {
                    "mode": "target_checkout",
                    "requested_base": args.base,
                    "resolved_base": resolved_base,
                    "requested_end": None,
                    "current_state": args.current_state,
                    "include_untracked": args.include_untracked,
                    "fetch": args.fetch,
                    "disposable_clone": None,
                }
                config_path, config_source = _select_config(
                    repo, repo, boundaries, bundle
                )
                if config_source == "synthetic_empty":
                    synthetic_config = config_path
                evidence["configuration"] = {
                    "source": config_source,
                    "path": str(config_path),
                }
                command_args = [
                    "diff",
                    *_common_pyclassuml_args(
                        repo,
                        repo,
                        boundaries,
                        args,
                        bundle.path / "diagram.puml",
                        config_path,
                    ),
                ]
                if resolved_base:
                    command_args.extend(("--base", resolved_base))
                command_args.extend(("--current-state", args.current_state))
                command_args.append(
                    "--include-untracked"
                    if args.include_untracked
                    else "--no-include-untracked"
                )
            evidence["comparison"] = comparison

        full_argv = [*tool.argv_prefix, *command_args]
        child_safety_env = {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONSAFEPATH": "1",
        }
        evidence["pyclassuml"] = {
            "argv": full_argv,
            "environment": child_safety_env,
        }
        child_env = os.environ.copy()
        child_env.update(child_safety_env)
        completed = _run(full_argv, cwd=execution_repo, env=child_env)
        stdout_text = completed.stdout
        stderr_text = completed.stderr
        summary = _parse_summary(stdout_text, stderr_text)
        evidence["pyclassuml"].update(
            {"exit_code": completed.returncode, "summary": summary}
        )
        exit_code = completed.returncode
        evidence["status"] = "completed" if completed.returncode == 0 else "failed"
        outcome = summary.get("outcome")
        warning_count = summary.get("counters", {}).get("warning_count", 0)
        evidence["source_verification_required"] = bool(
            completed.returncode != 0
            or warning_count
            or outcome in {"warning_only_success", "degraded_success"}
        )
        if completed.returncode == 0 and not (bundle.path / "diagram.puml").is_file():
            raise RunnerFailure(
                "artifact_missing_after_success",
                "PyClassUML exited zero without diagram.puml",
            )
    except RunnerFailure as exc:
        if evidence.get("status") != "needs_input":
            evidence["status"] = "failed"
        evidence["runner_error"] = {
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
        }
        if not stderr_text:
            stderr_text = f"{exc.code}: {exc.message}\n"
        exit_code = 1 if "pyclassuml" in evidence else 2
    except Exception as exc:  # noqa: BLE001 - preserve evidence for unexpected runner failures
        evidence["status"] = "failed"
        evidence["runner_error"] = {
            "code": "unexpected_runner_error",
            "message": f"{type(exc).__name__}: {exc}",
        }
        stderr_text = f"unexpected_runner_error: {type(exc).__name__}: {exc}\n"
        exit_code = 2
    finally:
        if clone is not None:
            try:
                if clone.exists():
                    shutil.rmtree(clone)
                evidence.setdefault("comparison", {})["disposable_clone_removed"] = True
            except OSError as exc:
                evidence.setdefault("comparison", {})["disposable_clone_removed"] = (
                    False
                )
                evidence.setdefault("runner_warnings", []).append(
                    f"failed to remove disposable clone: {exc}"
                )
                evidence["source_verification_required"] = True

        if synthetic_config is not None and synthetic_config.exists():
            try:
                synthetic_config.unlink()
            except OSError as exc:
                evidence.setdefault("runner_warnings", []).append(
                    f"failed to remove synthetic config: {exc}"
                )

        (bundle.path / "stdout.log").write_text(stdout_text, encoding="utf-8")
        (bundle.path / "stderr.log").write_text(stderr_text, encoding="utf-8")
        diagram = bundle.path / "diagram.puml"
        if not diagram.exists():
            diagram.touch()
        after = _repo_snapshot(repo)
        evidence["repository"]["after"] = after
        evidence["repository"]["worktree_unchanged"] = before.get("head") == after.get(
            "head"
        ) and before.get("snapshot_sha256") == after.get("snapshot_sha256")
        if not evidence["repository"]["worktree_unchanged"]:
            evidence.setdefault("runner_warnings", []).append(
                "repository_changed_during_run"
            )
            evidence["source_verification_required"] = True
        evidence["artifacts"] = _artifact_inventory(bundle)
        evidence["finished_at"] = _utc_now()
        evidence["exit_code"] = exit_code
        _write_json(bundle.path / "run-evidence.json", evidence)

    print(bundle.path)
    return exit_code


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
