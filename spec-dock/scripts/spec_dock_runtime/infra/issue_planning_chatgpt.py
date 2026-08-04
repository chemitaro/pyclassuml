"""Provider-owned direct Oracle transport for Issue Planning."""

from __future__ import annotations

from contextlib import suppress
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat
import subprocess
from tempfile import TemporaryDirectory
import time
from typing import TYPE_CHECKING, Literal
from urllib.parse import urlsplit

from spec_dock_runtime.domain.issue_planning_contracts import (
    OracleAuthoringZipSnapshot,
    OracleReviewJsonPayload,
    PlanningInvocationResult,
    PlanningSourceEvidence,
)
from spec_dock_runtime.infra.git_cli import origin_github_repo_slug
from spec_dock_runtime.infra.issue_planning_oracle_artifact import (
    SUPPORTED_ORACLE_VERSION,
    OracleArtifactError,
    has_exact_repository_access_failure,
    read_session_status,
    snapshot_authoring_zip,
    snapshot_review_json,
)

if TYPE_CHECKING:
    from spec_dock_runtime.application.issue_planning_prompt import (
        PlanningOutputExpectation,
        SynthesizedPlanningPrompt,
    )

_PREFLIGHT_TIMEOUT_SECONDS = 10.0
_MAX_CDP_VERSION_BYTES = 64 * 1024
_DEFAULT_RUN_TIMEOUT_SECONDS = 2 * 60 * 60
_DEFAULT_RECOVERY_TIMEOUT_SECONDS = 2 * 60
_RECOVERY_POLL_INTERVAL_SECONDS = 0.25
_TERMINAL_STATUSES = frozenset({"completed"})
_SessionState = Literal["terminal", "nonterminal", "missing", "invalid"]
_ROOT_CAPABILITIES = (
    b"--engine",
    b"--file",
    b"--slug",
    b"--wait",
    b"--prompt",
    b"--browser-attachments",
    b"--model",
    b"--browser-model-strategy",
    b"--remote-chrome",
)
_SESSION_CAPABILITIES = (b"--harvest", b"--no-recover")
_SAFE_ENVIRONMENT_KEYS = frozenset({
    "HOME",
    "LANG",
    "ORACLE_HOME_DIR",
    "PATH",
    "TMPDIR",
    "TZ",
})
_SESSION_ROLE_SLUGS = {
    "planner": "planner",
    "semantic_revision": "semantic-revision",
    "reviewer": "reviewer",
}


def resolve_issue_planning_github_repository(repo_root: Path) -> str | None:
    return origin_github_repo_slug(repo_root)


def invoke_issue_planning_chatgpt(
    *,
    repo_root: Path,
    role: Literal["planner", "semantic_revision", "reviewer"],
    source_evidence: PlanningSourceEvidence,
    synthesized: SynthesizedPlanningPrompt,
    timeout_seconds: float | None = None,
) -> PlanningInvocationResult:
    expectation = synthesized.output_expectation
    if not _invocation_contract_is_valid(role, synthesized, expectation):
        return _result("rejected", "planning_context_rejected", source_evidence, None)
    managed_chrome = _parse_managed_chrome_endpoint(os.environ.get("SPECDOCK_ORACLE_REMOTE_CHROME"))
    if managed_chrome is None:
        return _result("blocked", "oracle_unavailable", source_evidence, None)
    executable = _resolve_oracle_executable()
    if executable is None:
        return _result("blocked", "oracle_unavailable", source_evidence, None)
    executable_identity = _executable_identity(executable)
    if executable_identity is None:
        return _result("blocked", "oracle_unavailable", source_evidence, None)
    child_env = _sanitized_child_environment()
    if not _preflight_supported_oracle(executable, child_env=child_env, cwd=repo_root):
        return _result(
            "blocked",
            "oracle_capability_unsupported",
            source_evidence,
            None,
        )
    if not _preflight_managed_chrome(managed_chrome):
        return _result("blocked", "oracle_unavailable", source_evidence, None)

    with TemporaryDirectory(prefix="specdock-issue-planning-") as raw_temp:
        temp_root = Path(raw_temp)
        pack = temp_root / "prompt-pack"
        staging = temp_root / "staging"
        _write_transport_pack(pack, synthesized, source_evidence)
        session_id = _new_session_id(role, source_evidence)
        session_root = _oracle_home(child_env) / "sessions" / session_id
        if session_root.exists() or session_root.is_symlink():
            return _result(
                "blocked",
                "oracle_session_recovery_required",
                source_evidence,
                None,
            )
        final_executable = _resolve_oracle_executable()
        if (
            final_executable is None
            or final_executable != executable
            or _executable_identity(final_executable) != executable_identity
        ):
            return _result("blocked", "oracle_unavailable", source_evidence, None)
        argv = [
            str(final_executable),
            "--engine",
            "browser",
            "--model",
            "Pro",
            "--browser-model-strategy",
            "select",
            "--remote-chrome",
            f"{managed_chrome[0]}:{managed_chrome[1]}",
            "--browser-no-cookie-sync",
            "--wait",
            "--browser-attachments",
            "always",
            "--slug",
            session_id,
            "--prompt",
            synthesized.prompt,
            "--file",
            str(pack),
        ]
        run_timeout = (
            timeout_seconds if timeout_seconds is not None and timeout_seconds > 0 else _DEFAULT_RUN_TIMEOUT_SECONDS
        )
        exit_code: int | None = None
        needs_recovery = False
        try:
            completed = _run_oracle(
                argv,
                child_env=child_env,
                cwd=repo_root,
                timeout=run_timeout,
            )
            exit_code = completed.returncode
            needs_recovery = completed.returncode != 0
        except (subprocess.TimeoutExpired, OSError):
            needs_recovery = True

        session_state = _session_state(session_root, session_id=session_id)
        if session_state == "invalid":
            return _result(
                "rejected",
                "oracle_artifact_rejected",
                source_evidence,
                exit_code,
            )
        if needs_recovery or session_state != "terminal":
            recovered_state = _recover_same_session(
                executable=final_executable,
                executable_identity=executable_identity,
                session_id=session_id,
                session_root=session_root,
                child_env=child_env,
                cwd=repo_root,
                timeout=min(run_timeout, _DEFAULT_RECOVERY_TIMEOUT_SECONDS),
            )
            if recovered_state == "invalid":
                return _result(
                    "rejected",
                    "oracle_artifact_rejected",
                    source_evidence,
                    exit_code,
                )
            if recovered_state != "terminal":
                return _result(
                    "blocked",
                    "oracle_session_recovery_required",
                    source_evidence,
                    exit_code,
                )
        return _collect_typed_result(
            role=role,
            expectation=expectation,
            session_root=session_root,
            session_id=session_id,
            staging=staging,
            source_evidence=source_evidence,
            exit_code=exit_code,
        )


def _parse_managed_chrome_endpoint(value: str | None) -> tuple[str, int] | None:
    if value is None:
        return None
    match = re.fullmatch(r"(127\.0\.0\.1|localhost):([0-9]{1,5})", value)
    if match is None:
        return None
    port = int(match.group(2))
    if not 1 <= port <= 65535:
        return None
    return "127.0.0.1", port


def _preflight_managed_chrome(endpoint: tuple[str, int]) -> bool:
    host, port = endpoint
    connection = http.client.HTTPConnection(
        host,
        port,
        timeout=_PREFLIGHT_TIMEOUT_SECONDS,
    )
    try:
        connection.request(
            "GET",
            "/json/version",
            headers={"Connection": "close"},
        )
        response = connection.getresponse()
        if response.status != 200:
            return False
        payload = response.read(_MAX_CDP_VERSION_BYTES + 1)
        if len(payload) > _MAX_CDP_VERSION_BYTES:
            return False
        parsed_payload = json.loads(payload)
        if not isinstance(parsed_payload, dict):
            return False
        debugger_url = parsed_payload.get("webSocketDebuggerUrl")
        if not isinstance(debugger_url, str) or not debugger_url:
            return False
        parsed_url = urlsplit(debugger_url)
        if (
            parsed_url.scheme not in {"ws", "wss"}
            or parsed_url.username is not None
            or parsed_url.password is not None
            or parsed_url.hostname not in {"127.0.0.1", "localhost"}
            or parsed_url.port != port
        ):
            return False
    except (OSError, ValueError, json.JSONDecodeError, http.client.HTTPException):
        return False
    finally:
        connection.close()
    return True


def _resolve_oracle_executable() -> Path | None:
    candidate_text = shutil.which("oracle")
    if not candidate_text:
        return None
    candidate = Path(candidate_text)
    try:
        resolved = candidate.resolve(strict=True)
        mode = resolved.stat().st_mode
    except (OSError, RuntimeError):
        return None
    if not stat.S_ISREG(mode) or not os.access(resolved, os.X_OK):
        return None
    return resolved


def _executable_identity(path: Path) -> tuple[int, int, int, int] | None:
    try:
        metadata = path.stat()
    except OSError:
        return None
    if not stat.S_ISREG(metadata.st_mode) or not os.access(path, os.X_OK):
        return None
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_size,
        metadata.st_mtime_ns,
    )


def _preflight_supported_oracle(
    executable: Path,
    *,
    child_env: dict[str, str],
    cwd: Path,
) -> bool:
    try:
        version = _run_oracle(
            [str(executable), "--version"],
            child_env=child_env,
            cwd=cwd,
            timeout=_PREFLIGHT_TIMEOUT_SECONDS,
        )
        if version.returncode != 0 or version.stdout.decode("utf-8", errors="replace").strip() != (
            SUPPORTED_ORACLE_VERSION
        ):
            return False
        root_help = _run_oracle(
            [str(executable), "--help"],
            child_env=child_env,
            cwd=cwd,
            timeout=_PREFLIGHT_TIMEOUT_SECONDS,
        )
        session_help = _run_oracle(
            [str(executable), "session", "--help"],
            child_env=child_env,
            cwd=cwd,
            timeout=_PREFLIGHT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return (
        root_help.returncode == 0
        and session_help.returncode == 0
        and all(flag in root_help.stdout for flag in _ROOT_CAPABILITIES)
        and all(flag in session_help.stdout for flag in _SESSION_CAPABILITIES)
    )


def _run_oracle(
    argv: list[str],
    *,
    child_env: dict[str, str],
    cwd: Path,
    timeout: float,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        argv,
        cwd=cwd,
        env=child_env,
        shell=False,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def _recover_same_session(
    *,
    executable: Path,
    executable_identity: tuple[int, int, int, int],
    session_id: str,
    session_root: Path,
    child_env: dict[str, str],
    cwd: Path,
    timeout: float,
) -> _SessionState:
    deadline = time.monotonic() + timeout
    initial_state = _session_state(session_root, session_id=session_id)
    if initial_state in {"terminal", "invalid"}:
        return initial_state
    recovery_executable = _resolve_oracle_executable()
    if (
        recovery_executable is None
        or recovery_executable != executable
        or _executable_identity(recovery_executable) != executable_identity
    ):
        return "nonterminal"
    pre_harvest_state = _session_state(session_root, session_id=session_id)
    if pre_harvest_state in {"terminal", "invalid"}:
        return pre_harvest_state
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return pre_harvest_state
    with suppress(OSError, subprocess.TimeoutExpired):
        _run_oracle(
            [
                str(recovery_executable),
                "session",
                session_id,
                "--harvest",
                "--no-recover",
            ],
            child_env=child_env,
            cwd=cwd,
            timeout=remaining,
        )
    return _poll_same_session_state(
        session_root,
        session_id=session_id,
        deadline=deadline,
    )


def _poll_same_session_state(
    session_root: Path,
    *,
    session_id: str,
    deadline: float,
) -> _SessionState:
    while True:
        state = _session_state(session_root, session_id=session_id)
        if state in {"terminal", "invalid"}:
            return state
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return state
        time.sleep(min(_RECOVERY_POLL_INTERVAL_SECONDS, remaining))


def _session_state(session_root: Path, *, session_id: str) -> _SessionState:
    try:
        status_value = read_session_status(
            session_root,
            session_id=session_id,
            oracle_version=SUPPORTED_ORACLE_VERSION,
        )
    except OracleArtifactError as error:
        return "missing" if error.code == "oracle_session_missing" else "invalid"
    return "terminal" if status_value in _TERMINAL_STATUSES else "nonterminal"


def _collect_typed_result(
    *,
    role: Literal["planner", "semantic_revision", "reviewer"],
    expectation: PlanningOutputExpectation,
    session_root: Path,
    session_id: str,
    staging: Path,
    source_evidence: PlanningSourceEvidence,
    exit_code: int | None,
) -> PlanningInvocationResult:
    try:
        if has_exact_repository_access_failure(
            session_root,
            session_id=session_id,
            oracle_version=SUPPORTED_ORACLE_VERSION,
            staging_dir=staging / "branch-gate",
        ):
            return _result(
                "blocked",
                "github_exact_branch_unavailable",
                source_evidence,
                exit_code,
            )
        if role in {"planner", "semantic_revision"}:
            authoring_zip = snapshot_authoring_zip(
                session_root,
                session_id=session_id,
                oracle_version=SUPPORTED_ORACLE_VERSION,
                staging_dir=staging,
            )
            if (
                authoring_zip.expected_logical_filename != expectation.logical_filename
                or authoring_zip.internal_root != expectation.internal_root
            ):
                raise OracleArtifactError("oracle_artifact_rejected")
            return _pass_result(
                source_evidence=source_evidence,
                exit_code=exit_code,
                authoring_zip=authoring_zip,
            )
        review_json = snapshot_review_json(
            session_root,
            session_id=session_id,
            oracle_version=SUPPORTED_ORACLE_VERSION,
            staging_dir=staging,
        )
        return _pass_result(
            source_evidence=source_evidence,
            exit_code=exit_code,
            review_json=review_json,
        )
    except OracleArtifactError as error:
        status: Literal["blocked", "rejected"] = (
            "blocked" if error.code == "oracle_session_recovery_required" else "rejected"
        )
        reason = (
            error.code
            if error.code
            in {
                "oracle_artifact_missing",
                "oracle_artifact_ambiguous",
                "oracle_artifact_rejected",
            }
            else "oracle_artifact_rejected"
        )
        return _result(status, reason, source_evidence, exit_code)


def _pass_result(
    *,
    source_evidence: PlanningSourceEvidence,
    exit_code: int | None,
    authoring_zip: OracleAuthoringZipSnapshot | None = None,
    review_json: OracleReviewJsonPayload | None = None,
) -> PlanningInvocationResult:
    typed = authoring_zip if authoring_zip is not None else review_json
    if typed is None:
        raise ValueError("typed Oracle output is required")
    return PlanningInvocationResult(
        status="pass",
        reason="transport_received",
        source_evidence=source_evidence,
        backend_exit_code=exit_code,
        response_bytes=typed.size_bytes,
        response_sha256=typed.sha256,
        authoring_zip=authoring_zip,
        review_json=review_json,
    )


def _result(
    status: Literal["blocked", "rejected"],
    reason: str,
    source_evidence: PlanningSourceEvidence | None,
    exit_code: int | None,
) -> PlanningInvocationResult:
    return PlanningInvocationResult(
        status=status,
        reason=reason,
        source_evidence=source_evidence,
        backend_exit_code=exit_code,
    )


def _sanitized_child_environment() -> dict[str, str]:
    result = {key: value for key, value in os.environ.items() if key in _SAFE_ENVIRONMENT_KEYS or key.startswith("LC_")}
    result.setdefault("PATH", os.defpath)
    return result


def _oracle_home(child_env: dict[str, str]) -> Path:
    configured = child_env.get("ORACLE_HOME_DIR")
    if configured:
        return Path(configured)
    home = child_env.get("HOME")
    return Path(home) / ".oracle" if home else Path.home() / ".oracle"


def _new_session_id(
    role: Literal["planner", "semantic_revision", "reviewer"],
    source_evidence: PlanningSourceEvidence,
) -> str:
    return f"specdock-{_SESSION_ROLE_SLUGS[role]}-{source_evidence.snapshot_id[:6]}-{secrets.token_hex(4)}"


def _write_transport_pack(
    pack: Path,
    synthesized: SynthesizedPlanningPrompt,
    source: PlanningSourceEvidence,
) -> None:
    pack.mkdir()
    (pack / ".specdock-authoring-pack").write_text("issue-planning-transport-v2\n", encoding="utf-8")
    attachment_names: list[str] = []
    for index, (relative, body) in enumerate(synthesized.attachments):
        name = f"context-{index:03d}.md"
        attachment_names.append(name)
        (pack / name).write_text(f"source_path: {relative}\n\n{body}", encoding="utf-8")
    exact_source_hashes: dict[str, str] = {}
    for attachment in synthesized.exact_attachments:
        if attachment.name in attachment_names:
            raise ValueError("exact planning attachment name collides with prompt pack")
        target = pack / attachment.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(attachment.content)
        if hashlib.sha256(target.read_bytes()).hexdigest() != attachment.sha256:
            raise OSError("exact planning attachment changed while writing prompt pack")
        attachment_names.append(attachment.name)
        exact_source_hashes[attachment.source_label] = attachment.sha256
    manifest = {
        "schema_version": 2,
        "generated_by": "spec-dock-issue-planning",
        "expected_output_root": "oracle-session-artifact",
        "required_metadata": [],
        "files": attachment_names,
        "authority": "evidence_only",
        "adoption_status": "unreviewed",
        "bundle_generation_not_promotion": True,
    }
    provenance = {
        "evidence_mode": "github-synced",
        "sync_state": "synced",
        "github_sync": "verified",
        "source_manifest_hash": source.source_manifest_hash,
        "authority": "evidence_only",
        "adoption_status": "unreviewed",
        "bundle_generation_not_promotion": True,
    }
    source_hashes = {path: hashlib.sha256(body.encode("utf-8")).hexdigest() for path, body in synthesized.attachments}
    for label, digest in exact_source_hashes.items():
        existing = source_hashes.get(label)
        if existing is not None and existing != digest:
            raise ValueError("planning attachment source label has conflicting bytes")
        source_hashes[label] = digest
    source_manifest = {
        "source_paths": list(source_hashes),
        "source_hashes": source_hashes,
        "source_manifest_hash": source.source_manifest_hash,
    }
    _write_json(pack / "manifest.json", manifest)
    _write_json(pack / "provenance.json", provenance)
    _write_json(pack / "source-manifest.json", source_manifest)
    _write_json(pack / "stale-if.json", {"source_head_changes": source.local_head})


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _invocation_contract_is_valid(
    role: str,
    synthesized: SynthesizedPlanningPrompt,
    expectation: PlanningOutputExpectation | None,
) -> bool:
    if synthesized.role != role or expectation is None:
        return False
    expected_kind = "review_json" if role == "reviewer" else "authoring_zip"
    return role in {"planner", "semantic_revision", "reviewer"} and expectation.kind == expected_kind
