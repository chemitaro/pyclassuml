from __future__ import annotations

from dataclasses import dataclass
import os
import subprocess
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from spec_dock_runtime.domain.authoring_pack.preflight_contract import FETCH_TIMEOUT_SECONDS, GitProcessOutcome

_TRACE_ENVIRONMENT_KEYS = (
    "GIT_TRACE",
    "GIT_TRACE_PACKET",
    "GIT_TRACE_CURL",
    "GIT_CURL_VERBOSE",
    "GIT_TRACE2",
    "GIT_TRACE2_EVENT",
    "GIT_TRACE2_PERF",
)


@dataclass(frozen=True)
class GitFetchExecutionRequest:
    repo_root: Path
    executable: str = "git"
    argv: tuple[str, ...] = ("fetch", "--prune", "origin")
    timeout_seconds: float = FETCH_TIMEOUT_SECONDS
    environment_policy_id: str = "git-fetch-noninteractive-v1"

    @classmethod
    def for_repo(cls, repo_root: Path) -> GitFetchExecutionRequest:
        return cls(repo_root=repo_root)


def execute_git_fetch(request: GitFetchExecutionRequest) -> GitProcessOutcome:
    started = time.monotonic()
    environment = os.environ.copy()
    for key in _TRACE_ENVIRONMENT_KEYS:
        environment.pop(key, None)
    environment.update({"GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C", "LANG": "C"})
    try:
        process = subprocess.run(
            [request.executable, *request.argv],
            cwd=str(request.repo_root),
            env=environment,
            capture_output=True,
            check=False,
            shell=False,
            timeout=request.timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        return GitProcessOutcome(
            return_code=None,
            termination="timeout",
            stdout=_as_bytes(error.stdout),
            stderr=_as_bytes(error.stderr),
            duration_ms=_duration_ms(started),
        )
    except OSError as error:
        return GitProcessOutcome(
            return_code=None,
            termination="spawn_error",
            stdout=b"",
            stderr=b"",
            duration_ms=_duration_ms(started),
            os_error_kind=type(error).__name__,
        )
    return GitProcessOutcome(
        return_code=process.returncode,
        termination="exited",
        stdout=process.stdout or b"",
        stderr=process.stderr or b"",
        duration_ms=_duration_ms(started),
    )


def _duration_ms(started: float) -> int:
    return max(0, round((time.monotonic() - started) * 1000))


def _as_bytes(value: bytes | str | None) -> bytes:
    if isinstance(value, bytes):
        return value
    if value is None:
        return b""
    return value.encode("utf-8", errors="replace")
