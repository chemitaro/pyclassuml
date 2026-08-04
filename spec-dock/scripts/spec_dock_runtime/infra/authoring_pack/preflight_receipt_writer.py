from __future__ import annotations

from contextlib import suppress
import json
import os
from pathlib import Path
import secrets
import stat

from spec_dock_runtime.domain.authoring_pack.preflight_contract import PublicationEvidence

RECEIPT_FILENAME = "github-sync-preflight.receipt.json"
RECEIPT_KIND = "spec-dock.authoring.github-sync-preflight"
MAX_EXISTING_RECEIPT_BYTES = 1024 * 1024


def validate_preflight_receipt_output(*, repo_root: Path, output_dir: Path) -> str | None:
    if ".." in output_dir.parts:
        return "receipt_output_parent_traversal"
    candidate = output_dir if output_dir.is_absolute() else Path.cwd() / output_dir
    candidate = candidate.absolute()
    try:
        trusted_repo_root = repo_root.resolve(strict=True)
    except (OSError, RuntimeError):
        return "receipt_output_directory_unavailable"
    symlink_blocker = _symlink_component_blocker(candidate)
    if symlink_blocker is not None:
        return symlink_blocker
    try:
        output_stat = candidate.stat()
    except FileNotFoundError:
        return "receipt_output_directory_missing"
    except OSError:
        return "receipt_output_directory_unavailable"
    if not stat.S_ISDIR(output_stat.st_mode):
        return "receipt_output_not_directory"
    try:
        resolved_repo = trusted_repo_root
        resolved_output = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        return "receipt_output_directory_unavailable"
    if _is_relative_to(resolved_output, resolved_repo):
        return "receipt_output_inside_repository"
    return _existing_target_blocker(candidate / RECEIPT_FILENAME)


def publish_preflight_receipt(*, repo_root: Path, output_dir: Path, payload: dict[str, object]) -> PublicationEvidence:
    blocker = validate_preflight_receipt_output(repo_root=repo_root, output_dir=output_dir)
    if blocker is not None:
        return PublicationEvidence(requested=True, status="rejected", filename=RECEIPT_FILENAME, blocker=blocker)

    directory = (output_dir if output_dir.is_absolute() else Path.cwd() / output_dir).absolute()
    target = directory / RECEIPT_FILENAME
    temp = directory / f".{RECEIPT_FILENAME}.{secrets.token_hex(8)}.tmp"
    encoded = (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    fd: int | None = None
    try:
        directory_identity = _directory_identity(directory)
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb", closefd=True) as stream:
            fd = None
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        post_blocker = validate_preflight_receipt_output(repo_root=repo_root, output_dir=output_dir)
        if post_blocker is not None:
            return PublicationEvidence(
                requested=True,
                status="rejected",
                filename=RECEIPT_FILENAME,
                blocker=post_blocker,
            )
        if _directory_identity(directory) != directory_identity:
            raise OSError("output directory changed during publication")
        temp.replace(target)
        _fsync_directory_best_effort(directory)
        target_stat = target.lstat()
        if stat.S_ISLNK(target_stat.st_mode) or not stat.S_ISREG(target_stat.st_mode):
            raise OSError("published receipt is not a regular file")
        return PublicationEvidence(requested=True, status="published", filename=RECEIPT_FILENAME)
    except OSError:
        return PublicationEvidence(
            requested=True,
            status="failed",
            filename=RECEIPT_FILENAME,
            blocker="receipt_publication_failed",
        )
    finally:
        if fd is not None:
            with suppress(OSError):
                os.close(fd)
        with suppress(OSError):
            temp.unlink(missing_ok=True)


def _symlink_component_blocker(path: Path) -> str | None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            component_stat = current.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            return "receipt_output_directory_unavailable"
        if stat.S_ISLNK(component_stat.st_mode):
            return "receipt_output_symlink"
    return None


def _existing_target_blocker(target: Path) -> str | None:
    try:
        target_stat = target.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        return "non_owned_existing_receipt_target"
    if stat.S_ISLNK(target_stat.st_mode) or not stat.S_ISREG(target_stat.st_mode):
        return "non_owned_existing_receipt_target"
    if target_stat.st_size > MAX_EXISTING_RECEIPT_BYTES:
        return "non_owned_existing_receipt_target"
    try:
        with target.open("rb") as stream:
            raw = stream.read(MAX_EXISTING_RECEIPT_BYTES + 1)
        if len(raw) > MAX_EXISTING_RECEIPT_BYTES:
            return "non_owned_existing_receipt_target"
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return "non_owned_existing_receipt_target"
    if not isinstance(payload, dict) or payload.get("receipt_kind") != RECEIPT_KIND:
        return "non_owned_existing_receipt_target"
    schema_version = payload.get("schema_version")
    if schema_version not in (None, 1):
        return "non_owned_existing_receipt_target"
    return None


def _directory_identity(path: Path) -> tuple[int, int]:
    path_stat = path.stat()
    if not stat.S_ISDIR(path_stat.st_mode):
        raise OSError("output directory is not a directory")
    return path_stat.st_dev, path_stat.st_ino


def _fsync_directory_best_effort(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
