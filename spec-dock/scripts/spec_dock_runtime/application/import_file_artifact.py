from __future__ import annotations

from dataclasses import dataclass, replace
import os
from pathlib import Path
import stat
from typing import TYPE_CHECKING

from spec_dock_runtime.application.contracts import (
    BinaryArtifactPublishError,
    ExplicitFileArtifactPublishRequest,
    ExplicitFileSourcePreflightRequest,
    FileArtifactImportError,
    FileArtifactImportRequest,
    FileArtifactImportResult,
)
from spec_dock_runtime.application.create_artifact_doc import (
    ArtifactSetupTarget,
    _format_artifact_timestamp,
    _preflight_artifacts_setup_for_target,
)
from spec_dock_runtime.application.create_node import (
    _acquire_create_lock,
    _prefix_for_kind,
    _release_create_lock,
    _resolve_specdock_dir,
    load_graph,
)
from spec_dock_runtime.domain.artifacts import allocate_generic_imported_artifact_filename_for_timestamp
from spec_dock_runtime.domain.ids import resolve_id_input

if TYPE_CHECKING:
    from spec_dock_runtime.application.ports import Ports


@dataclass(frozen=True)
class _FileArtifactTarget:
    kind: str
    id: str
    path: Path
    artifacts_dir: Path
    rules_kind: str


_MAX_PUBLICATION_ATTEMPTS = 100
_RulesLinkIdentity = tuple[int, int, int, int]


def import_file_artifact(req: FileArtifactImportRequest, ports: Ports) -> FileArtifactImportResult:
    repo_root = _absolute_path(ports.repo_root)
    source_guard = ports.explicit_file_source_guard
    publisher = ports.explicit_file_artifact_publisher
    if repo_root is None or source_guard is None or publisher is None:
        raise FileArtifactImportError(code="runtime_not_configured", cleanup_state="not_created")
    specdock_dir = _resolve_specdock_dir(ports)
    target = _resolve_target(req, ports, specdock_dir)
    original_basename = req.source_path.name
    if original_basename in ("", ".", ".."):
        raise FileArtifactImportError(code="source_ineligible", cleanup_state="not_created") from None
    timestamp = _format_artifact_timestamp(ports.clock.now_iso() if ports.clock is not None else None)

    try:
        guarded_source = source_guard.guard_explicit_file_source(
            ExplicitFileSourcePreflightRequest(
                repo_root=repo_root,
                source_path=req.source_path,
            )
        )
    except BinaryArtifactPublishError as error:
        raise FileArtifactImportError(code=error.code, cleanup_state=error.cleanup_state) from None
    except Exception:
        raise FileArtifactImportError(code="runtime_failed", cleanup_state="not_created") from None

    source_visibility = guarded_source.source_visibility
    source_display = guarded_source.source_display

    lock_path: Path | None = None
    lock_token: str | None = None
    result: FileArtifactImportResult | None = None
    body_error: FileArtifactImportError | None = None
    retry_cleanup_state = "not_created"
    target_directory_fd: int | None = None
    target_directory_identity: tuple[int, int, int] | None = None
    artifacts_directory_fd: int | None = None
    artifacts_directory_identity: tuple[int, int, int] | None = None
    fresh_rules_identity: _RulesLinkIdentity | None = None
    try:
        try:
            lock_path, lock_token = _acquire_create_lock(specdock_dir)
        except RuntimeError:
            raise FileArtifactImportError(code="create_lock_failed", cleanup_state="not_created") from None
        except OSError:
            raise FileArtifactImportError(code="runtime_failed", cleanup_state="not_created") from None
        setup_target = ArtifactSetupTarget(
            path=target.path,
            artifacts_dir=target.artifacts_dir,
            rules_kind=target.rules_kind,
        )
        artifacts_was_missing = not os.path.lexists(target.artifacts_dir)
        try:
            _preflight_artifacts_setup_for_target(target=setup_target, specdock_dir=specdock_dir)
            (
                target_directory_fd,
                target_directory_identity,
                target_name_max,
            ) = _open_verified_directory(target.path)
            if artifacts_was_missing:
                name_max_bytes = target_name_max
            else:
                assert target_directory_fd is not None
                (
                    artifacts_directory_fd,
                    artifacts_directory_identity,
                    name_max_bytes,
                ) = _open_verified_child_directory(
                    target_directory_fd,
                    target.artifacts_dir.name,
                    target.artifacts_dir,
                )
            _allocate_generic_destination(
                artifacts_dir=target.artifacts_dir,
                timestamp=timestamp,
                original_basename=original_basename,
                name_max_bytes=name_max_bytes,
                cleanup_state=retry_cleanup_state,
            )
            if artifacts_was_missing:
                assert target_directory_fd is not None
                assert target_directory_identity is not None
                (
                    artifacts_directory_fd,
                    artifacts_directory_identity,
                    verified_name_max,
                    fresh_rules_identity,
                ) = _create_bound_fresh_artifacts_setup(
                    target=setup_target,
                    specdock_dir=specdock_dir,
                    target_directory_fd=target_directory_fd,
                    target_directory_identity=target_directory_identity,
                )
                if not _destination_binding_is_current(
                    target=target,
                    target_directory_fd=target_directory_fd,
                    target_directory_identity=target_directory_identity,
                    artifacts_directory_fd=artifacts_directory_fd,
                    artifacts_directory_identity=artifacts_directory_identity,
                ):
                    _rollback_bound_rules_link(
                        artifacts_directory_fd=artifacts_directory_fd,
                        created_rules_identity=fresh_rules_identity,
                    )
                    raise RuntimeError("artifact target identity changed during setup")
            else:
                assert artifacts_directory_fd is not None
                assert artifacts_directory_identity is not None
                created_rules_identity = _ensure_bound_existing_artifacts_setup(
                    target=setup_target,
                    specdock_dir=specdock_dir,
                    artifacts_directory_fd=artifacts_directory_fd,
                )
                if not _destination_binding_is_current(
                    target=target,
                    target_directory_fd=target_directory_fd,
                    target_directory_identity=target_directory_identity,
                    artifacts_directory_fd=artifacts_directory_fd,
                    artifacts_directory_identity=artifacts_directory_identity,
                ):
                    _rollback_bound_rules_link(
                        artifacts_directory_fd=artifacts_directory_fd,
                        created_rules_identity=created_rules_identity,
                    )
                    raise RuntimeError("artifact target identity changed during setup")
                verified_name_max = _name_max_for_descriptor(artifacts_directory_fd)
            if verified_name_max != name_max_bytes:
                if artifacts_was_missing:
                    _rollback_fresh_artifacts_setup(target=setup_target, specdock_dir=specdock_dir)
                raise FileArtifactImportError(
                    code="artifact_allocation_failed",
                    cleanup_state=retry_cleanup_state,
                )
        except FileArtifactImportError:
            raise
        except RuntimeError:
            raise FileArtifactImportError(
                code="artifact_setup_failed",
                cleanup_state=retry_cleanup_state,
            ) from None
        except OSError:
            raise FileArtifactImportError(
                code="runtime_failed",
                cleanup_state=retry_cleanup_state,
            ) from None

        assert artifacts_directory_fd is not None
        assert artifacts_directory_identity is not None
        for _attempt in range(_MAX_PUBLICATION_ATTEMPTS):
            destination_path, filename = _allocate_generic_destination(
                artifacts_dir=target.artifacts_dir,
                timestamp=timestamp,
                original_basename=original_basename,
                name_max_bytes=verified_name_max,
                cleanup_state=retry_cleanup_state,
            )
            try:
                destination = destination_path.relative_to(repo_root)
            except ValueError:
                raise FileArtifactImportError(
                    code="result_path_invalid",
                    cleanup_state=retry_cleanup_state,
                ) from None
            if not _destination_binding_is_current(
                target=target,
                target_directory_fd=target_directory_fd,
                target_directory_identity=target_directory_identity,
                artifacts_directory_fd=artifacts_directory_fd,
                artifacts_directory_identity=artifacts_directory_identity,
            ):
                if artifacts_was_missing:
                    _rollback_bound_rules_link(
                        artifacts_directory_fd=artifacts_directory_fd,
                        created_rules_identity=fresh_rules_identity,
                    )
                raise FileArtifactImportError(
                    code="artifact_setup_failed",
                    cleanup_state=retry_cleanup_state,
                )
            if artifacts_was_missing:
                assert fresh_rules_identity is not None
                rules_source = specdock_dir / "docs" / "rules" / setup_target.rules_kind / "artifacts.md"
                rules_target = os.path.relpath(rules_source, start=target.artifacts_dir)
                try:
                    rules_status = os.stat(
                        "rules.md",
                        dir_fd=artifacts_directory_fd,
                        follow_symlinks=False,
                    )
                    _validate_bound_rules_link(
                        rules_source=rules_source,
                        rules_target=rules_target,
                        artifacts_directory_fd=artifacts_directory_fd,
                        rules_status=rules_status,
                        expected_rules_identity=fresh_rules_identity,
                    )
                except (OSError, RuntimeError):
                    _rollback_bound_rules_link(
                        artifacts_directory_fd=artifacts_directory_fd,
                        created_rules_identity=fresh_rules_identity,
                    )
                    raise FileArtifactImportError(
                        code="artifact_setup_failed",
                        cleanup_state=retry_cleanup_state,
                    ) from None
            try:
                published = publisher.publish_explicit_file(
                    ExplicitFileArtifactPublishRequest(
                        repo_root=repo_root,
                        guarded_source=guarded_source,
                        destination_path=destination_path,
                    )
                )
            except BinaryArtifactPublishError as error:
                retry_cleanup_state = _merge_cleanup_state(retry_cleanup_state, error.cleanup_state)
                if error.code == "destination_exists":
                    continue
                raise FileArtifactImportError(
                    code=error.code,
                    cleanup_state=retry_cleanup_state,
                ) from None

            if published.destination_path != destination_path or not published.committed:
                raise RuntimeError("explicit publisher returned an invalid committed identity")
            cleanup_state = _merge_cleanup_state(retry_cleanup_state, published.cleanup_state)
            warning_codes = list(published.warning_codes)
            if retry_cleanup_state == "retained" and "temp_cleanup_retained" not in warning_codes:
                warning_codes.append("temp_cleanup_retained")
            publication_state = "committed_with_warning" if warning_codes else "committed"
            result = FileArtifactImportResult(
                import_kind="file",
                storage_identity="generic",
                target_kind=req.target_kind,
                target_id=target.id,
                artifact_id=filename,
                source_visibility=source_visibility,
                source=source_display,
                destination=destination,
                committed=True,
                publication_state=publication_state,
                cleanup_state=cleanup_state,
                warning_codes=tuple(warning_codes),
                retry_disposition="not_needed",
                canonical=False,
            )
            break
        else:
            raise FileArtifactImportError(
                code="artifact_slot_exhausted",
                cleanup_state=retry_cleanup_state,
            )
    except FileArtifactImportError as error:
        body_error = error
    finally:
        if artifacts_directory_fd is not None:
            _close_descriptor_noexcept(artifacts_directory_fd)
        if target_directory_fd is not None:
            _close_descriptor_noexcept(target_directory_fd)
        guarded_source.close()
        if lock_path is not None and lock_token is not None:
            try:
                _release_create_lock(lock_path, lock_token, specdock_dir=specdock_dir)
            except Exception as release_error:
                if body_error is None and result is not None:
                    result = replace(
                        result,
                        publication_state="committed_with_warning",
                        warning_codes=(*result.warning_codes, "create_lock_release_failed"),
                    )
                elif body_error is None:
                    body_error = FileArtifactImportError(
                        code="create_lock_release_failed",
                        cleanup_state="not_created",
                    )
                else:
                    raise body_error from release_error
    if body_error is not None:
        raise body_error
    assert result is not None
    return result


def _resolve_target(
    req: FileArtifactImportRequest,
    ports: Ports,
    specdock_dir: Path,
) -> _FileArtifactTarget:
    if req.target_kind == "root":
        if req.target_value is not None:
            raise FileArtifactImportError(code="target_invalid", cleanup_state="not_created")
        if specdock_dir.is_symlink() or not specdock_dir.is_dir():
            raise FileArtifactImportError(code="target_invalid", cleanup_state="not_created")
        return _FileArtifactTarget(
            kind="root",
            id="root",
            path=specdock_dir,
            artifacts_dir=specdock_dir / "artifacts",
            rules_kind="root",
        )
    if req.target_kind not in ("initiative", "epic", "issue") or req.target_value is None:
        raise FileArtifactImportError(code="target_invalid", cleanup_state="not_created")
    graph = load_graph(ports, validate=False)
    try:
        target_id = resolve_id_input(
            req.target_value,
            prefix=_prefix_for_kind(req.target_kind),
            field=f"--{req.target_kind}",
            nodes=graph.nodes_by_id,
        )
    except RuntimeError:
        raise FileArtifactImportError(code="target_invalid", cleanup_state="not_created") from None
    node = graph.nodes_by_id.get(target_id)
    if node is None or node.kind != req.target_kind:
        raise FileArtifactImportError(code="target_invalid", cleanup_state="not_created")
    return _FileArtifactTarget(
        kind=node.kind,
        id=node.id,
        path=node.path,
        artifacts_dir=node.path / "artifacts",
        rules_kind=node.kind,
    )


def _absolute_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    return path if path.is_absolute() else Path.cwd() / path


def _allocate_generic_destination(
    *,
    artifacts_dir: Path,
    timestamp: str,
    original_basename: str,
    name_max_bytes: int,
    cleanup_state: str,
) -> tuple[Path, str]:
    try:
        return allocate_generic_imported_artifact_filename_for_timestamp(
            artifacts_dir,
            timestamp=timestamp,
            original_basename=original_basename,
            name_max_bytes=name_max_bytes,
        )
    except RuntimeError as error:
        code = (
            "artifact_slot_exhausted"
            if str(error).startswith("Artifact timestamp suffix exhaustion:")
            else "artifact_allocation_failed"
        )
        raise FileArtifactImportError(code=code, cleanup_state=cleanup_state) from None


def _open_verified_directory(path: Path) -> tuple[int, tuple[int, int, int], int]:
    flags = os.O_RDONLY
    flags |= getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    before = path.lstat()
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        after = path.lstat()
        if not _matching_directory_statuses(before, opened, after):
            raise OSError("directory identity changed")
        identity = (opened.st_dev, opened.st_ino, opened.st_mode)
        return descriptor, identity, _name_max_for_descriptor(descriptor)
    except BaseException:
        _close_descriptor_noexcept(descriptor)
        raise


def _create_bound_fresh_artifacts_setup(
    *,
    target: ArtifactSetupTarget,
    specdock_dir: Path,
    target_directory_fd: int,
    target_directory_identity: tuple[int, int, int],
) -> tuple[int, tuple[int, int, int], int, _RulesLinkIdentity]:
    if not _visible_directory_matches(
        target.path,
        target_directory_fd,
        target_directory_identity,
    ):
        raise RuntimeError("artifact target identity changed before setup")
    os.mkdir(target.artifacts_dir.name, dir_fd=target_directory_fd)
    artifacts_directory_fd: int | None = None
    try:
        (
            artifacts_directory_fd,
            artifacts_directory_identity,
            name_max_bytes,
        ) = _open_verified_child_directory(
            target_directory_fd,
            target.artifacts_dir.name,
            target.artifacts_dir,
        )
        if artifacts_directory_identity[0] != target_directory_identity[0]:
            raise RuntimeError("fresh artifacts directory is on a different filesystem")
        rules_source = specdock_dir / "docs" / "rules" / target.rules_kind / "artifacts.md"
        rules_target = os.path.relpath(rules_source, start=target.artifacts_dir)
        os.symlink(rules_target, "rules.md", dir_fd=artifacts_directory_fd)
        rules_status = os.stat(
            "rules.md",
            dir_fd=artifacts_directory_fd,
            follow_symlinks=False,
        )
        rules_identity = _rules_link_identity(rules_status)
        _validate_bound_rules_link(
            rules_source=rules_source,
            rules_target=rules_target,
            artifacts_directory_fd=artifacts_directory_fd,
            rules_status=rules_status,
            expected_rules_identity=rules_identity,
        )
        return (
            artifacts_directory_fd,
            artifacts_directory_identity,
            name_max_bytes,
            rules_identity,
        )
    except BaseException:
        if artifacts_directory_fd is not None:
            _close_descriptor_noexcept(artifacts_directory_fd)
        raise


def _ensure_bound_existing_artifacts_setup(
    *,
    target: ArtifactSetupTarget,
    specdock_dir: Path,
    artifacts_directory_fd: int,
) -> _RulesLinkIdentity | None:
    rules_source = specdock_dir / "docs" / "rules" / target.rules_kind / "artifacts.md"
    created_identity: _RulesLinkIdentity | None = None
    try:
        try:
            rules_status = os.stat(
                "rules.md",
                dir_fd=artifacts_directory_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            rules_target = os.path.relpath(rules_source, start=target.artifacts_dir)
            os.symlink(rules_target, "rules.md", dir_fd=artifacts_directory_fd)
            rules_status = os.stat(
                "rules.md",
                dir_fd=artifacts_directory_fd,
                follow_symlinks=False,
            )
            created_identity = _rules_link_identity(rules_status)
        _validate_bound_rules_link(
            rules_source=rules_source,
            rules_target=None,
            artifacts_directory_fd=artifacts_directory_fd,
            rules_status=rules_status,
            expected_rules_identity=_rules_link_identity(rules_status),
        )
        return created_identity
    except BaseException as error:
        _rollback_bound_rules_link(
            artifacts_directory_fd=artifacts_directory_fd,
            created_rules_identity=created_identity,
        )
        if isinstance(error, RuntimeError):
            raise
        if isinstance(error, OSError):
            raise RuntimeError("artifact rules setup failed") from None
        raise


def _validate_bound_rules_link(
    *,
    rules_source: Path,
    rules_target: str | None,
    artifacts_directory_fd: int,
    rules_status: os.stat_result,
    expected_rules_identity: _RulesLinkIdentity,
) -> None:
    if _rules_link_identity(rules_status) != expected_rules_identity or not stat.S_ISLNK(rules_status.st_mode):
        raise RuntimeError("artifact rules entry is not a symlink")
    source_fd: int | None = None
    linked_fd: int | None = None
    try:
        source_before = rules_source.lstat()
        source_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        source_fd = os.open(rules_source, source_flags)
        source_opened = os.fstat(source_fd)
        source_after = rules_source.lstat()
        if len({
            (source_before.st_dev, source_before.st_ino, source_before.st_mode),
            (source_opened.st_dev, source_opened.st_ino, source_opened.st_mode),
            (source_after.st_dev, source_after.st_ino, source_after.st_mode),
        }) != 1 or not stat.S_ISREG(source_opened.st_mode):
            raise RuntimeError("artifact rules source identity changed")
        linked_flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
        linked_fd = os.open("rules.md", linked_flags, dir_fd=artifacts_directory_fd)
        linked_status = os.fstat(linked_fd)
        linked_target = os.readlink("rules.md", dir_fd=artifacts_directory_fd)
        rules_after = os.stat(
            "rules.md",
            dir_fd=artifacts_directory_fd,
            follow_symlinks=False,
        )
        if (
            _rules_link_identity(rules_after) != expected_rules_identity
            or not stat.S_ISLNK(rules_after.st_mode)
            or (rules_target is not None and linked_target != rules_target)
            or (
                linked_status.st_dev,
                linked_status.st_ino,
                linked_status.st_mode,
            )
            != (
                source_opened.st_dev,
                source_opened.st_ino,
                source_opened.st_mode,
            )
        ):
            raise RuntimeError("artifact rules link identity changed")
    except OSError:
        raise RuntimeError("artifact rules link validation failed") from None
    finally:
        if linked_fd is not None:
            _close_descriptor_noexcept(linked_fd)
        if source_fd is not None:
            _close_descriptor_noexcept(source_fd)


def _rollback_bound_rules_link(
    *,
    artifacts_directory_fd: int,
    created_rules_identity: _RulesLinkIdentity | None,
) -> None:
    if created_rules_identity is None:
        return
    try:
        current = os.stat(
            "rules.md",
            dir_fd=artifacts_directory_fd,
            follow_symlinks=False,
        )
        if _rules_link_identity(current) != created_rules_identity or not stat.S_ISLNK(current.st_mode):
            return
        # The captured tuple cannot prove ownership at the unlink instant.  A
        # replacement may legally have the same observable identity, so retain
        # the current entry and fail closed through the existing setup error.
        return
    except OSError:
        return


def _rules_link_identity(status: os.stat_result) -> _RulesLinkIdentity:
    return (status.st_dev, status.st_ino, status.st_mode, status.st_ctime_ns)


def _open_verified_child_directory(
    parent_descriptor: int,
    child_name: str,
    visible_path: Path,
) -> tuple[int, tuple[int, int, int], int]:
    flags = os.O_RDONLY
    flags |= getattr(os, "O_DIRECTORY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)
    before = os.stat(child_name, dir_fd=parent_descriptor, follow_symlinks=False)
    descriptor = os.open(child_name, flags, dir_fd=parent_descriptor)
    try:
        opened = os.fstat(descriptor)
        relative_after = os.stat(child_name, dir_fd=parent_descriptor, follow_symlinks=False)
        visible_after = visible_path.lstat()
        if not _matching_directory_statuses(before, opened, relative_after, visible_after):
            raise OSError("child directory identity changed")
        identity = (opened.st_dev, opened.st_ino, opened.st_mode)
        return descriptor, identity, _name_max_for_descriptor(descriptor)
    except BaseException:
        _close_descriptor_noexcept(descriptor)
        raise


def _name_max_for_descriptor(descriptor: int) -> int:
    value = os.fpathconf(descriptor, "PC_NAME_MAX")
    if not isinstance(value, int) or value <= 0:
        raise OSError("PC_NAME_MAX is unavailable")
    return value


def _matching_directory_statuses(*statuses: os.stat_result) -> bool:
    identities = {(status.st_dev, status.st_ino, status.st_mode) for status in statuses}
    return len(identities) == 1 and all(stat.S_ISDIR(status.st_mode) for status in statuses)


def _visible_directory_matches(
    path: Path,
    descriptor: int,
    expected_identity: tuple[int, int, int],
) -> bool:
    try:
        descriptor_status = os.fstat(descriptor)
        path_status = path.lstat()
    except OSError:
        return False
    return (
        (descriptor_status.st_dev, descriptor_status.st_ino, descriptor_status.st_mode)
        == expected_identity
        == (path_status.st_dev, path_status.st_ino, path_status.st_mode)
        and stat.S_ISDIR(descriptor_status.st_mode)
        and stat.S_ISDIR(path_status.st_mode)
    )


def _destination_binding_is_current(
    *,
    target: _FileArtifactTarget,
    target_directory_fd: int | None,
    target_directory_identity: tuple[int, int, int] | None,
    artifacts_directory_fd: int,
    artifacts_directory_identity: tuple[int, int, int],
) -> bool:
    if target_directory_fd is not None:
        if target_directory_identity is None or not _visible_directory_matches(
            target.path,
            target_directory_fd,
            target_directory_identity,
        ):
            return False
        try:
            relative_status = os.stat(
                target.artifacts_dir.name,
                dir_fd=target_directory_fd,
                follow_symlinks=False,
            )
        except OSError:
            return False
        if (
            relative_status.st_dev,
            relative_status.st_ino,
            relative_status.st_mode,
        ) != artifacts_directory_identity:
            return False
    return _visible_directory_matches(
        target.artifacts_dir,
        artifacts_directory_fd,
        artifacts_directory_identity,
    )


def _close_descriptor_noexcept(descriptor: int) -> None:
    try:
        os.close(descriptor)
    except OSError:
        return


def _merge_cleanup_state(first: str, second: str) -> str:
    if "retained" in (first, second):
        return "retained"
    if "removed" in (first, second):
        return "removed"
    return "not_created"


def _rollback_fresh_artifacts_setup(*, target: ArtifactSetupTarget, specdock_dir: Path) -> None:
    artifacts_dir = target.artifacts_dir
    rules_link = artifacts_dir / "rules.md"
    rules_source = specdock_dir / "docs" / "rules" / target.rules_kind / "artifacts.md"
    if artifacts_dir.is_symlink() or not artifacts_dir.is_dir():
        return
    try:
        entries = list(artifacts_dir.iterdir())
    except OSError:
        return
    if entries != [rules_link] or not rules_link.is_symlink():
        return
    try:
        if rules_link.resolve() != rules_source.resolve():
            return
        rules_link.unlink()
        artifacts_dir.rmdir()
    except OSError:
        return
