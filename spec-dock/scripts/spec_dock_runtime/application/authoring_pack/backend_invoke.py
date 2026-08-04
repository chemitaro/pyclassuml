from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

from spec_dock_runtime.domain.authoring_pack.authority_boundary import is_credential_like_path
from spec_dock_runtime.domain.authoring_pack.backend_invoke_contract import (
    BACKEND_PROMPT_PACK_FILES,
    DEFAULT_BACKEND_PROMPT,
    FALLBACK_BACKEND_ENV,
    PRIMARY_BACKEND_ENV,
    REQUIRED_MANIFEST_FIELDS,
    REQUIRED_PROMPT_PACK_FILES,
    REQUIRED_PROVENANCE_FIELDS,
    REQUIRED_SOURCE_MANIFEST_FIELDS,
    BackendCommandResolution,
    BackendInvokeRequest,
    BackendInvokeResult,
    BackendStreamCapture,
    PromptPackValidation,
)
from spec_dock_runtime.domain.authoring_pack.prompt_pack_contract import (
    ADOPTION_STATUS,
    AUTHORITY,
    BUNDLE_GENERATION_NOT_PROMOTION,
)
from spec_dock_runtime.domain.authoring_pack.provenance_contract import provenance_state_findings

SUMMARY_FILENAME = "invocation-summary.json"


def invoke_backend(request: BackendInvokeRequest, *, env: Mapping[str, str] | None = None) -> BackendInvokeResult:
    result, _ = _invoke_backend_core(request, env=env)
    return result


def invoke_backend_with_capture(
    request: BackendInvokeRequest,
    *,
    env: Mapping[str, str] | None = None,
) -> tuple[BackendInvokeResult, BackendStreamCapture]:
    return _invoke_backend_core(request, env=env)


def _invoke_backend_core(
    request: BackendInvokeRequest,
    *,
    env: Mapping[str, str] | None = None,
) -> tuple[BackendInvokeResult, BackendStreamCapture]:
    environment = env if env is not None else os.environ
    resolution = resolve_backend_command(request.backend_command, environment)
    pack = validate_prompt_pack(request.prompt_pack)
    unsafe_output_blockers = _unsafe_output_blockers(request.output_dir)
    blockers = (*resolution.blockers, *pack.blockers, *unsafe_output_blockers)
    if blockers:
        result = _result(
            request,
            status="rejected" if unsafe_output_blockers else "blocked",
            resolution=resolution,
            pack=pack,
            blockers=blockers,
            remediation=_remediation(blockers),
        )
        if not unsafe_output_blockers:
            _write_summary(request.output_dir, result)
        return result, BackendStreamCapture()

    slug = request.slug or _default_slug(request.prompt_pack, pack.source_manifest_hash)
    prompt = request.prompt or DEFAULT_BACKEND_PROMPT
    invocation_argv = _backend_invocation_argv(
        resolution.argv,
        request.prompt_pack,
        slug=slug,
        prompt=prompt,
    )

    if request.dry_run:
        result = _result(
            request,
            status="pass",
            resolution=resolution,
            pack=pack,
            blockers=(),
            remediation=(),
            slug=slug,
            invocation_argv=invocation_argv,
        )
        _write_summary(request.output_dir, result)
        return result, BackendStreamCapture()

    cwd = str(request.working_dir.resolve(strict=True)) if request.working_dir is not None else None
    try:
        completed = subprocess.run(
            list(invocation_argv),
            check=False,
            capture_output=True,
            timeout=request.timeout_seconds if request.timeout_seconds and request.timeout_seconds > 0 else None,
            cwd=cwd,
        )
    except FileNotFoundError:
        result = _result(
            request,
            status="blocked",
            resolution=resolution,
            pack=pack,
            blockers=("backend_command_not_found",),
            remediation=("configure an executable backend command",),
            slug=slug,
            invocation_argv=invocation_argv,
        )
        _write_summary(request.output_dir, result)
        return result, BackendStreamCapture()
    except OSError as error:
        result = _result(
            request,
            status="blocked",
            resolution=resolution,
            pack=pack,
            blockers=("backend_os_error",),
            remediation=(f"inspect configured backend command: {error.__class__.__name__}",),
            slug=slug,
            invocation_argv=invocation_argv,
        )
        _write_summary(request.output_dir, result)
        return result, BackendStreamCapture()
    except subprocess.TimeoutExpired as error:
        result = _result(
            request,
            status="blocked",
            resolution=resolution,
            pack=pack,
            blockers=("backend_timeout",),
            remediation=("increase --timeout-seconds or inspect protected backend-native diagnostics",),
            slug=slug,
            invocation_argv=invocation_argv,
            stdout=_decode_stream(error.stdout),
            stderr=_decode_stream(error.stderr),
        )
        _write_summary(request.output_dir, result)
        return result, BackendStreamCapture(
            stdout=_stream_bytes(error.stdout),
            stderr=_stream_bytes(error.stderr),
        )

    status = "pass" if completed.returncode == 0 else "blocked"
    blockers = () if completed.returncode == 0 else (f"backend_exit_code:{completed.returncode}",)
    remediation = (
        ()
        if completed.returncode == 0
        else ("inspect protected backend-native diagnostics and rerun after fixing the error",)
    )
    result = _result(
        request,
        status=status,
        resolution=resolution,
        pack=pack,
        blockers=blockers,
        remediation=remediation,
        slug=slug,
        invocation_argv=invocation_argv,
        exit_code=completed.returncode,
        stdout=_decode_stream(completed.stdout),
        stderr=_decode_stream(completed.stderr),
    )
    _write_summary(request.output_dir, result)
    return result, BackendStreamCapture(
        stdout=_stream_bytes(completed.stdout),
        stderr=_stream_bytes(completed.stderr),
    )


def resolve_backend_command(backend_command: str | None, env: Mapping[str, str]) -> BackendCommandResolution:
    candidates = (
        ("cli", backend_command, False),
        (f"env:{PRIMARY_BACKEND_ENV}", env.get(PRIMARY_BACKEND_ENV), False),
        (f"env:{FALLBACK_BACKEND_ENV}", env.get(FALLBACK_BACKEND_ENV), True),
    )
    for source, value, fallback in candidates:
        command = (value or "").strip()
        if not command:
            continue
        try:
            argv = tuple(shlex.split(command, posix=True))
        except ValueError:
            return BackendCommandResolution(
                status="blocked",
                source=source,  # type: ignore[arg-type]
                argv=(),
                compatibility_fallback=fallback,
                blockers=(f"malformed_backend_command:{source}",),
            )
        if not argv:
            continue
        return BackendCommandResolution(
            status="pass",
            source=source,  # type: ignore[arg-type]
            argv=argv,
            compatibility_fallback=fallback,
            blockers=(),
        )
    return BackendCommandResolution(
        status="blocked",
        source="unset",
        argv=(),
        compatibility_fallback=False,
        blockers=(f"backend_command_unset:set_{PRIMARY_BACKEND_ENV}",),
    )


def validate_prompt_pack(prompt_pack: Path) -> PromptPackValidation:
    blockers: list[str] = []
    symlink_blocker = _symlink_path_blocker(prompt_pack)
    if symlink_blocker:
        return PromptPackValidation("blocked", prompt_pack, (symlink_blocker,), None, None, None, None)
    root = prompt_pack.resolve()
    if not root.is_dir():
        return PromptPackValidation("blocked", prompt_pack, ("prompt_pack_missing",), None, None, None, None)

    for relative_path in REQUIRED_PROMPT_PACK_FILES:
        path = root / relative_path
        if not path.is_file():
            blockers.append(f"missing_prompt_pack_file:{relative_path}")
        elif path.is_symlink():
            blockers.append(f"unsafe_prompt_pack_file_symlink:{relative_path}")

    manifest = _read_json(root / "manifest.json", blockers, "manifest")
    provenance = _read_json(root / "provenance.json", blockers, "provenance")
    source_manifest = _read_json(root / "source-manifest.json", blockers, "source_manifest")
    stale_if = _read_json(root / "stale-if.json", blockers, "stale_if")

    _require_fields(manifest, REQUIRED_MANIFEST_FIELDS, blockers, "manifest")
    _require_fields(provenance, REQUIRED_PROVENANCE_FIELDS, blockers, "provenance")
    _require_fields(source_manifest, REQUIRED_SOURCE_MANIFEST_FIELDS, blockers, "source_manifest")
    if stale_if is not None and not isinstance(stale_if, dict):
        blockers.append("stale_if_not_object")
    if isinstance(manifest, dict):
        _manifest_file_blockers(root, manifest, blockers)
    if isinstance(provenance, dict):
        _provenance_sync_blockers(provenance, blockers)

    for name, payload in (("manifest", manifest), ("provenance", provenance)):
        if payload is None:
            continue
        if payload.get("authority") != AUTHORITY:
            blockers.append(f"{name}_authority_not_evidence_only")
        if payload.get("adoption_status") != ADOPTION_STATUS:
            blockers.append(f"{name}_adoption_status_not_unreviewed")
        if payload.get("bundle_generation_not_promotion") is not BUNDLE_GENERATION_NOT_PROMOTION:
            blockers.append(f"{name}_bundle_generation_not_promotion_not_true")

    return PromptPackValidation(
        status="blocked" if blockers else "pass",
        prompt_pack=prompt_pack,
        blockers=tuple(blockers),
        evidence_mode=str(provenance.get("evidence_mode")) if isinstance(provenance, dict) else None,
        source_manifest_hash=str(source_manifest.get("source_manifest_hash"))
        if isinstance(source_manifest, dict)
        else None,
        github_sync=str(provenance.get("github_sync")) if isinstance(provenance, dict) else None,
        sync_state=str(provenance.get("sync_state")) if isinstance(provenance, dict) else None,
    )


def _read_json(path: Path, blockers: list[str], label: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        blockers.append(f"{label}_json_unreadable")
        return None
    if not isinstance(payload, dict):
        blockers.append(f"{label}_json_not_object")
        return None
    return payload


def _symlink_path_blocker(path: Path) -> str | None:
    current = path if path.is_absolute() else Path.cwd() / path
    if current.is_symlink():
        return "prompt_pack_symlink_path"
    try:
        relative = current.resolve(strict=False).relative_to(Path.cwd().resolve())
    except ValueError:
        return None
    probe = Path.cwd().resolve()
    for part in relative.parts:
        probe = probe / part
        if probe.is_symlink():
            return "prompt_pack_symlink_path"
    return None


def _require_fields(
    payload: dict[str, Any] | None, required_fields: tuple[str, ...], blockers: list[str], label: str
) -> None:
    if payload is None:
        return
    for field in required_fields:
        if field not in payload:
            blockers.append(f"missing_{label}_field:{field}")


def _manifest_file_blockers(root: Path, manifest: dict[str, Any], blockers: list[str]) -> None:
    files = manifest.get("files")
    if not isinstance(files, list):
        blockers.append("manifest_files_not_list")
        return
    for value in files:
        if not isinstance(value, str):
            blockers.append("manifest_file_not_string")
            continue
        unsafe = _unsafe_manifest_file(value)
        if unsafe:
            blockers.append(unsafe)
            continue
        path = root / value
        try:
            path.resolve(strict=False).relative_to(root.resolve())
        except ValueError:
            blockers.append("unsafe_manifest_file:outside-pack")
            continue
        if path.is_symlink():
            blockers.append(f"unsafe_manifest_file_symlink:{value}")


def _provenance_sync_blockers(provenance: dict[str, Any], blockers: list[str]) -> None:
    blockers.extend(provenance_state_findings(provenance))


def _backend_invocation_argv(
    backend_argv: tuple[str, ...],
    prompt_pack: Path,
    *,
    slug: str,
    prompt: str,
) -> tuple[str, ...]:
    argv = [*backend_argv]
    argv.extend(["--slug", slug, "-p", prompt])
    for relative_path in _backend_attachment_files(prompt_pack):
        argv.extend(["--file", str((prompt_pack / relative_path).resolve())])
    return tuple(argv)


def _backend_attachment_files(prompt_pack: Path) -> tuple[str, ...]:
    files = list(BACKEND_PROMPT_PACK_FILES)
    try:
        manifest = json.loads((prompt_pack / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return tuple(files)
    if not isinstance(manifest, dict):
        return tuple(files)
    for value in manifest.get("files") or ():
        if not isinstance(value, str):
            continue
        if value in files:
            continue
        if _unsafe_manifest_file(value):
            continue
        path = prompt_pack / value
        try:
            path.resolve(strict=False).relative_to(prompt_pack.resolve())
        except ValueError:
            continue
        if path.is_file() and not path.is_symlink():
            files.append(value)
    return tuple(files)


def _unsafe_manifest_file(value: str) -> str | None:
    if "\\" in value:
        return f"unsafe_manifest_file:backslash-separator:{value}"
    if len(value) >= 2 and value[1] == ":" and value[0].isalpha():
        return f"unsafe_manifest_file:drive-path:{value}"
    rel = PurePosixPath(value)
    if rel.is_absolute():
        return "unsafe_manifest_file:absolute-path"
    if any(part == ".." for part in rel.parts):
        return "unsafe_manifest_file:parent-traversal"
    if any(part.startswith(".") for part in rel.parts):
        return f"unsafe_manifest_file:hidden-path:{value}"
    if is_credential_like_path(value):
        return f"unsafe_manifest_file:secret-path:{value}"
    return None


def _unsafe_output_blockers(output_dir: Path) -> tuple[str, ...]:
    blockers: list[str] = []
    raw_parts = tuple(part.lower() for part in output_dir.parts)
    if _is_canonical_output_parts(raw_parts):
        blockers.append("canonical_output_target")
    resolved_parts: tuple[str, ...] = ()
    try:
        resolved_parts = tuple(part.lower() for part in output_dir.resolve(strict=False).parts)
    except OSError:
        blockers.append("unsafe_output_path_unresolvable")
    resolved_is_canonical = bool(resolved_parts and _is_canonical_output_parts(resolved_parts))
    if resolved_is_canonical and "canonical_output_target" not in blockers:
        blockers.append("canonical_output_target")
    current = Path(output_dir.anchor) if output_dir.is_absolute() else Path()
    has_parent_symlink = False
    for part in output_dir.parts:
        if part == output_dir.anchor:
            continue
        current = current / part
        if current.is_symlink():
            if current == output_dir:
                blockers.append("unsafe_output_dir_symlink")
                break
            elif not (output_dir.is_absolute() and current.parent == Path(output_dir.anchor)):
                has_parent_symlink = True
                break
    if has_parent_symlink:
        blockers.append("unsafe_output_parent_symlink")
    if output_dir.is_symlink() and "unsafe_output_dir_symlink" not in blockers:
        blockers.append("unsafe_output_dir_symlink")
    if output_dir.exists() and not output_dir.is_dir():
        blockers.append("unsafe_output_dir_not_directory")
    summary = output_dir / SUMMARY_FILENAME
    if summary.is_symlink() or (summary.exists() and not summary.is_file()):
        blockers.append(f"unsafe_output_entry:{SUMMARY_FILENAME}")
    return tuple(blockers)


def _is_canonical_output_parts(parts: tuple[str, ...]) -> bool:
    return "spec-dock" in parts and ("active" in parts or "initiatives" in parts or "system" in parts)


def _write_summary(output_dir: Path, result: BackendInvokeResult) -> None:
    if _unsafe_output_blockers(output_dir):
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / SUMMARY_FILENAME).write_text(json.dumps(result.to_dict(), sort_keys=True) + "\n", encoding="utf-8")


def _decode_stream(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return value.decode("utf-8", errors="replace")


def _stream_bytes(value: str | bytes | None) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    return value.encode("utf-8")


def _default_slug(prompt_pack: Path, source_manifest_hash: str | None) -> str:
    digest = hashlib.sha256()
    digest.update(str(prompt_pack.resolve()).encode("utf-8"))
    if source_manifest_hash:
        digest.update(source_manifest_hash.encode("utf-8"))
    return f"specdock-authoring-{digest.hexdigest()[:12]}"


def _result(
    request: BackendInvokeRequest,
    *,
    status: str,
    resolution: BackendCommandResolution,
    pack: PromptPackValidation,
    blockers: tuple[str, ...],
    remediation: tuple[str, ...],
    slug: str | None = None,
    invocation_argv: tuple[str, ...] = (),
    exit_code: int | None = None,
    stdout: str = "",
    stderr: str = "",
) -> BackendInvokeResult:
    summary_path = None
    if not blockers or status in {"pass", "blocked"}:
        summary_path = str((request.output_dir / SUMMARY_FILENAME).resolve())
    return BackendInvokeResult(
        status=status,  # type: ignore[arg-type]
        authority=AUTHORITY,
        adoption_status=ADOPTION_STATUS,
        bundle_generation_not_promotion=BUNDLE_GENERATION_NOT_PROMOTION,
        evidence_mode=pack.evidence_mode or request.evidence_mode,
        sync_state=pack.sync_state,
        github_sync=pack.github_sync,
        backend_source=resolution.source,
        compatibility_fallback=resolution.compatibility_fallback,
        prompt_pack=str(request.prompt_pack),
        output_dir=str(request.output_dir),
        summary_path=summary_path,
        slug=slug,
        dry_run=request.dry_run,
        backend_argv=resolution.argv,
        invocation_argv=invocation_argv,
        exit_code=exit_code,
        stdout="",
        stderr="",
        stdout_bytes=len(stdout.encode("utf-8")),
        stderr_bytes=len(stderr.encode("utf-8")),
        stream_output_disposition="not_persisted",
        source_manifest_hash=pack.source_manifest_hash,
        blockers=blockers,
        remediation=remediation,
        local_context_requires_eal_disposition=(pack.evidence_mode or request.evidence_mode) == "local-context",
    )


def _remediation(blockers: tuple[str, ...]) -> tuple[str, ...]:
    if any(blocker.startswith("backend_command_unset") for blocker in blockers):
        return (f"set {PRIMARY_BACKEND_ENV} or pass --backend-command",)
    if any(blocker.startswith("malformed_backend_command") for blocker in blockers):
        return ("provide a backend command that can be parsed as argv",)
    if any("prompt_pack" in blocker or "manifest" in blocker or "provenance" in blocker for blocker in blockers):
        return ("regenerate the prompt pack before invoking the backend",)
    if any("output" in blocker for blocker in blockers):
        return ("choose a non-canonical non-symlink output directory for adapter diagnostics",)
    return ("resolve blockers before invoking the backend",)


def _redact(value: str) -> str:
    redacted = re.sub(r"/Users/[^\s'\"]+", "[redacted-path]", value)
    redacted = re.sub(r"/private/[^\s'\"]+", "[redacted-path]", redacted)
    redacted = re.sub(r"/var/folders(?:/[^\s'\"]*)?", "[redacted-path]", redacted)
    redacted = re.sub(r"/tmp(?:/[^\s'\"]*)?", "[redacted-path]", redacted)
    redacted = re.sub(
        r"(?i)\b([A-Za-z0-9_-]*(?:api[_-]?key|password|token|secret|credential|key)[A-Za-z0-9_-]*)=\S+",
        r"\1=[redacted]",
        redacted,
    )
    redacted = re.sub(
        r"(?i)(--(?:api[_-]?key|password|token|secret|credential|key)\s+)\S+",
        r"\1[redacted]",
        redacted,
    )
    redacted = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "sk-[redacted]", redacted)
    redacted = re.sub(r"gh[pousr]_[A-Za-z0-9_]{8,}", "gh[token-redacted]", redacted)
    redacted = re.sub(r"xox[baprs]-[A-Za-z0-9-]{8,}", "xox[token-redacted]", redacted)
    redacted = re.sub(r"AKIA[0-9A-Z]{16}", "AKIA[redacted]", redacted)
    return redacted
