from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Literal
from urllib.parse import unquote, urlsplit, urlunsplit

from spec_dock_runtime.application.authoring_pack.github_fetch_policy import (
    Sleeper,
    run_origin_fetch_policy,
    summarize_fetch_outcome,
)
from spec_dock_runtime.domain.authoring_pack.preflight_contract import (
    FetchSummary,
    FreshnessEvidence,
    GitProcessOutcome,
    GitVisibleRef,
    PreflightResult,
    PublicationEvidence,
    RemoteHeadDisposition,
    RepositorySnapshot,
)
from spec_dock_runtime.domain.authoring_pack.source_manifest import (
    build_source_manifest,
    empty_source_manifest,
    expected_hash_from_manifest,
    source_path_blockers,
)
from spec_dock_runtime.infra.authoring_pack.git_fetch import GitFetchExecutionRequest, execute_git_fetch
from spec_dock_runtime.infra.authoring_pack.preflight_receipt_writer import (
    RECEIPT_FILENAME,
    publish_preflight_receipt,
    validate_preflight_receipt_output,
)

EvidenceMode = Literal["github-synced", "local-context"]


@dataclass(frozen=True)
class GitHubSyncPreflightRequest:
    repo_root: Path | None = None
    evidence_mode: EvidenceMode = "github-synced"
    ref: str | None = None
    allow_default_branch_fallback: bool = False
    source_paths: tuple[str, ...] = ()
    expected_source_manifest: Path | None = None
    expected_source_hash: str | None = None
    provided_context_paths: tuple[str, ...] = ()
    diff_summary: str | None = None
    unsynced_reason: str | None = None
    output_dir: Path | None = None


RemoteObserver = Callable[[Path, str | None, bool], GitVisibleRef]
FetchExecutor = Callable[[GitFetchExecutionRequest], GitProcessOutcome]
SnapshotHook = Callable[[str, Path], None]


@dataclass(frozen=True)
class _ObservedRepositorySnapshot:
    repository: RepositorySnapshot
    visible_ref: GitVisibleRef
    internally_stable: bool


@dataclass(frozen=True)
class _RepositoryState:
    normalized_origin: str | None
    branch: str | None
    local_head: str | None
    upstream: str | None
    effective_ref: str | None
    remote_head: str | None
    remote_head_disposition: RemoteHeadDisposition
    worktree_state: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "normalized_origin": self.normalized_origin,
            "branch": self.branch,
            "local_head": self.local_head,
            "upstream": self.upstream,
            "effective_ref": self.effective_ref,
            "remote_head": self.remote_head,
            "remote_head_disposition": self.remote_head_disposition,
            "worktree_state": list(self.worktree_state),
        }


def run_github_sync_preflight(
    request: GitHubSyncPreflightRequest,
    *,
    remote_observer: RemoteObserver | None = None,
    fetch_executor: FetchExecutor | None = None,
    fetch_sleeper: Sleeper | None = None,
    snapshot_hook: SnapshotHook | None = None,
) -> PreflightResult:
    repo_root = _resolve_repo_root(request.repo_root)
    output_blocker = None
    if request.output_dir is not None:
        output_blocker = validate_preflight_receipt_output(repo_root=repo_root, output_dir=request.output_dir)
    manifest_paths = request.source_paths
    if request.evidence_mode == "local-context" and not manifest_paths:
        manifest_paths = request.provided_context_paths
    source_blockers = source_path_blockers(repo_root, manifest_paths)
    if any(blocker.startswith("unsafe_source_path:workbench:") for blocker in source_blockers):
        result = _workbench_source_blocked_result(request, source_blockers)
        return _finalize_publication(result, repo_root, request.output_dir, output_blocker)
    expected_source_hash = _resolve_expected_hash(request)
    if request.evidence_mode == "local-context":
        source_manifest = build_source_manifest(repo_root, manifest_paths)
        result = _local_context_result(request, repo_root, source_manifest, expected_source_hash, source_blockers)
        return _finalize_publication(result, repo_root, request.output_dir, output_blocker)

    blockers: list[str] = []
    remediation: list[str] = []
    if output_blocker is not None:
        blockers.append(output_blocker)
        remediation.append("choose an existing external non-symlink directory with no non-owned receipt target")
    blockers.extend(source_blockers)
    if source_blockers:
        remediation.append("remove symlink, absolute-outside-repo, or parent-traversal source paths before preflight")
    missing_source_paths = _missing_explicit_source_paths(repo_root, manifest_paths)
    if missing_source_paths:
        blockers.extend(f"missing_source_path:{path}" for path in missing_source_paths)
        remediation.append("fix or remove missing explicit --source-path entries before authoring preflight")
    branch = _git_stdout(repo_root, "rev-parse", "--abbrev-ref", "HEAD", check=False)
    current_branch = None if branch in (None, "", "HEAD") else branch
    requested_ref = request.ref or current_branch
    fetch_summary = FetchSummary(status="not_started")

    if current_branch is None:
        blockers.append("detached_head")
        remediation.append("checkout a named branch before GitHub-synced authoring preflight")

    if _git_stdout(repo_root, "remote", "get-url", "origin", check=False) is None:
        blockers.append("origin_missing")
        remediation.append("configure origin before GitHub-synced authoring preflight")
    elif not blockers:
        fetch_request = GitFetchExecutionRequest.for_repo(repo_root)
        executor = fetch_executor or execute_git_fetch
        if fetch_sleeper is None:
            fetch_summary = run_origin_fetch_policy(fetch_request, executor=executor)
        else:
            fetch_summary = run_origin_fetch_policy(fetch_request, executor=executor, sleeper=fetch_sleeper)
        if fetch_summary.status != "success":
            blockers.append("origin_fetch_failed")
            remediation.append("fetch origin before GitHub-synced authoring preflight")

    observer = remote_observer or _observe_origin_ref
    first_observation = _capture_repository_snapshot(
        repo_root,
        manifest_paths,
        requested_ref,
        request.allow_default_branch_fallback,
        observer,
        fetch_summary,
        snapshot_hook,
    )
    if snapshot_hook is not None:
        snapshot_hook("before_final_guard", repo_root)
    final_observation = _capture_repository_snapshot(
        repo_root,
        manifest_paths,
        requested_ref,
        request.allow_default_branch_fallback,
        observer,
        fetch_summary,
        None,
    )
    snapshot = first_observation.repository
    final_snapshot = final_observation.repository
    source_manifest = snapshot.source_manifest
    upstream = snapshot.upstream
    if upstream is None:
        blockers.append("remote_branch_missing")
        remediation.append("set an origin upstream branch or use explicit local-context evidence")
    elif not upstream.startswith("origin/"):
        blockers.append("origin_mismatch")
        remediation.append("track an origin branch before repo-aware GitHub authoring")

    visible = first_observation.visible_ref
    blockers.extend(visible.blockers)
    remediation.extend(visible.remediation)

    if visible.state != "resolved":
        blockers.append(visible.state)
    blockers.extend(snapshot.worktree_state)

    concurrent_change = (
        not first_observation.internally_stable
        or not final_observation.internally_stable
        or snapshot.snapshot_id != final_snapshot.snapshot_id
    )
    if concurrent_change:
        blockers.append("concurrent_repo_change")
        remediation.append("rerun preflight after repository and source state stop changing")

    status = "blocked" if blockers else "pass"
    sync_state = "blocked" if blockers else "synced"
    github_sync = "failed" if blockers else "verified"
    if not blockers and snapshot.local_head != snapshot.remote_head:
        ahead, behind = _ahead_behind_heads(repo_root, snapshot.local_head, snapshot.remote_head)
        if ahead > 0 and behind > 0:
            blockers.append("diverged_from_remote")
            remediation.append("reconcile diverged local and origin branches")
            status = "blocked"
            sync_state = "blocked"
        elif ahead > 0:
            blockers.append("ahead_of_remote")
            remediation.append("push local commits before GitHub-synced authoring")
            status = "blocked"
            sync_state = "blocked"
        elif behind > 0:
            blockers.append("behind_remote")
            remediation.append("pull or rebase onto origin before GitHub-synced authoring")
            status = "stale"
            sync_state = "stale"
        else:
            blockers.append("head_mismatch")
            remediation.append("make local HEAD match the remote-visible branch")
            status = "blocked"
            sync_state = "blocked"
        github_sync = "failed"

    checked = expected_source_hash is not None
    if expected_source_hash is not None and expected_source_hash != source_manifest.source_manifest_hash:
        blockers.append("source_hash_mismatch")
        remediation.append("refresh the source manifest baseline before using this evidence")
        status = "stale"
        sync_state = "stale"
        github_sync = "failed"

    if concurrent_change:
        status = "blocked"
        sync_state = "blocked"
        github_sync = "failed"

    result = PreflightResult(
        status=status,
        evidence_mode="github-synced",
        sync_state=sync_state,
        github_sync=github_sync,
        requested_ref=requested_ref,
        effective_ref=snapshot.effective_ref,
        local_head=snapshot.local_head,
        remote_head=snapshot.remote_head,
        source_manifest=source_manifest,
        source_hash_mismatch_checked=checked,
        blockers=tuple(dict.fromkeys(blockers)),
        remediation=tuple(dict.fromkeys(remediation)),
        expected_source_hash=expected_source_hash,
        current_source_hash=source_manifest.source_manifest_hash,
        fetch=fetch_summary,
        freshness=FreshnessEvidence(
            observed_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            snapshot_id=snapshot.snapshot_id,
            final_guard_snapshot_id=final_snapshot.snapshot_id,
            concurrent_change_check="changed" if concurrent_change else "stable",
            remote_head_disposition=snapshot.remote_head_disposition,
        ),
        repository=snapshot,
    )
    return _finalize_publication(result, repo_root, request.output_dir, output_blocker)


def _finalize_publication(
    result: PreflightResult,
    repo_root: Path,
    output_dir: Path | None,
    preflight_blocker: str | None,
) -> PreflightResult:
    if output_dir is None:
        return result
    if preflight_blocker is not None:
        return replace(
            result,
            status="blocked",
            blockers=tuple(dict.fromkeys((*result.blockers, preflight_blocker))),
            remediation=tuple(
                dict.fromkeys((
                    *result.remediation,
                    "choose an existing external non-symlink directory with no non-owned receipt target",
                ))
            ),
            publication=PublicationEvidence(
                requested=True,
                status="rejected",
                filename=RECEIPT_FILENAME,
                blocker=preflight_blocker,
            ),
        )

    candidate = replace(
        result,
        publication=PublicationEvidence(requested=True, status="published", filename=RECEIPT_FILENAME),
    )
    publication = publish_preflight_receipt(
        repo_root=repo_root,
        output_dir=output_dir,
        payload=candidate.to_dict(),
    )
    if publication.status == "published":
        return candidate
    blocker = publication.blocker or "receipt_publication_failed"
    return replace(
        result,
        status="blocked",
        blockers=tuple(dict.fromkeys((*result.blockers, blocker))),
        remediation=tuple(
            dict.fromkeys((
                *result.remediation,
                "preserve the existing receipt and choose a safe writable output directory",
            ))
        ),
        publication=publication,
    )


def _workbench_source_blocked_result(
    request: GitHubSyncPreflightRequest,
    source_blockers: tuple[str, ...],
) -> PreflightResult:
    local_context = request.evidence_mode == "local-context"
    source_manifest = empty_source_manifest()
    return PreflightResult(
        status="blocked",
        evidence_mode=request.evidence_mode,
        sync_state="local_context" if local_context else "blocked",
        github_sync="not_verified" if local_context else "failed",
        requested_ref=request.ref,
        effective_ref=None,
        local_head=None,
        remote_head=None,
        source_manifest=source_manifest,
        source_hash_mismatch_checked=False,
        blockers=source_blockers,
        remediation=("remove Workbench paths from semantic authoring sources before preflight",),
        expected_source_hash=None,
        provided_context_paths=request.provided_context_paths,
        diff_summary=request.diff_summary,
        unsynced_reason=request.unsynced_reason,
        current_source_hash=source_manifest.source_manifest_hash,
    )


def _local_context_result(
    request: GitHubSyncPreflightRequest,
    repo_root: Path,
    source_manifest,
    expected_source_hash: str | None,
    source_blockers: tuple[str, ...],
) -> PreflightResult:
    blockers: list[str] = []
    remediation: list[str] = []
    blockers.extend(source_blockers)
    if source_blockers:
        remediation.append("remove symlink, absolute-outside-repo, or parent-traversal context paths before preflight")
    if not request.unsynced_reason:
        blockers.append("missing_unsynced_reason")
        remediation.append("provide --unsynced-reason for local-context evidence")
    if not request.provided_context_paths and not request.diff_summary:
        blockers.append("missing_context_provenance")
        remediation.append("provide --provided-context-path or --diff-summary for local-context evidence")
    missing_context_paths = _missing_explicit_source_paths(repo_root, request.provided_context_paths)
    if missing_context_paths:
        blockers.extend(f"missing_context_path:{path}" for path in missing_context_paths)
        remediation.append("provide readable --provided-context-path files for local-context evidence")
    status = "blocked" if blockers else "pass"
    if expected_source_hash is not None and expected_source_hash != source_manifest.source_manifest_hash:
        blockers.append("source_hash_mismatch")
        remediation.append("refresh the source manifest baseline before using this evidence")
        status = "blocked" if status == "blocked" else "stale"
    return PreflightResult(
        status=status,
        evidence_mode="local-context",
        sync_state="local_context",
        github_sync="not_verified",
        requested_ref=request.ref,
        effective_ref=None,
        local_head=None,
        remote_head=None,
        source_manifest=source_manifest,
        source_hash_mismatch_checked=expected_source_hash is not None,
        blockers=tuple(blockers),
        remediation=tuple(remediation),
        expected_source_hash=expected_source_hash,
        provided_context_paths=request.provided_context_paths,
        diff_summary=request.diff_summary,
        unsynced_reason=request.unsynced_reason,
        current_source_hash=source_manifest.source_manifest_hash,
    )


def _capture_repository_snapshot(
    repo_root: Path,
    source_paths: tuple[str, ...],
    requested_ref: str | None,
    allow_default_branch_fallback: bool,
    observer: RemoteObserver,
    fetch_summary: FetchSummary,
    snapshot_hook: SnapshotHook | None,
) -> _ObservedRepositorySnapshot:
    before_visible = observer(repo_root, requested_ref, allow_default_branch_fallback)
    before_state = _repository_state(repo_root, before_visible, fetch_summary)
    source_manifest = build_source_manifest(
        repo_root,
        source_paths,
        file_observer=(
            None if snapshot_hook is None else lambda _source_path: snapshot_hook("source_file_hashed", repo_root)
        ),
    )
    visible = observer(repo_root, requested_ref, allow_default_branch_fallback)
    state = _repository_state(repo_root, visible, fetch_summary)
    snapshot_payload = {
        **state.to_payload(),
        "source_manifest_hash": source_manifest.source_manifest_hash,
    }
    canonical = json.dumps(snapshot_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    repository = RepositorySnapshot(
        normalized_origin=state.normalized_origin,
        branch=state.branch,
        local_head=state.local_head,
        upstream=state.upstream,
        effective_ref=state.effective_ref,
        remote_head=state.remote_head,
        remote_head_disposition=state.remote_head_disposition,
        worktree_state=state.worktree_state,
        source_manifest=source_manifest,
        snapshot_id=hashlib.sha256(canonical).hexdigest(),
    )
    return _ObservedRepositorySnapshot(
        repository=repository,
        visible_ref=visible,
        internally_stable=before_state == state,
    )


def _repository_state(
    repo_root: Path,
    visible: GitVisibleRef,
    fetch_summary: FetchSummary,
) -> _RepositoryState:
    branch = _git_stdout(repo_root, "rev-parse", "--abbrev-ref", "HEAD", check=False)
    current_branch = None if branch in (None, "", "HEAD") else branch
    return _RepositoryState(
        normalized_origin=_normalized_origin(repo_root),
        branch=current_branch,
        local_head=_git_stdout(repo_root, "rev-parse", "HEAD", check=False),
        upstream=_git_stdout(repo_root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", check=False),
        effective_ref=visible.effective_ref,
        remote_head=visible.remote_head,
        remote_head_disposition=_remote_head_disposition(fetch_summary, visible.remote_head),
        worktree_state=_worktree_blockers(repo_root),
    )


def _remote_head_disposition(fetch_summary: FetchSummary, remote_head: str | None) -> RemoteHeadDisposition:
    if fetch_summary.status == "success":
        return "fetched_remote_tracking_ref" if remote_head is not None else "unavailable"
    return "unverified_cache" if remote_head is not None else "unavailable"


def _normalized_origin(repo_root: Path) -> str | None:
    raw = _git_stdout(repo_root, "remote", "get-url", "origin", check=False)
    if raw is None:
        return None
    if "://" not in raw:
        if raw.startswith(("/", "./", "../", "~")):
            digest = hashlib.sha256(str(Path(raw).expanduser().resolve(strict=False)).encode("utf-8")).hexdigest()
            return f"local-path-sha256:{digest}"
        if "@" in raw and ":" in raw:
            return raw.split("@", 1)[1]
        return raw
    parsed = urlsplit(raw)
    if parsed.scheme.lower() == "file" and parsed.path.startswith("/"):
        local_path = str(Path(unquote(parsed.path)).resolve(strict=False))
        identity = f"{parsed.netloc}:{local_path}" if parsed.netloc not in ("", "localhost") else local_path
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return f"local-path-sha256:{digest}"
    authority = parsed.netloc.rsplit("@", 1)[-1]
    return urlunsplit((parsed.scheme, authority, parsed.path, "", ""))


def _resolve_repo_root(repo_root: Path | None) -> Path:
    if repo_root is not None:
        return repo_root.resolve()
    discovered = _git_stdout(Path.cwd(), "rev-parse", "--show-toplevel", check=False)
    if discovered is None:
        raise RuntimeError("not inside a git repository; provide --repo-root")
    return Path(discovered).resolve()


def _resolve_expected_hash(request: GitHubSyncPreflightRequest) -> str | None:
    manifest_hash = None
    if request.expected_source_manifest is not None:
        manifest_hash = expected_hash_from_manifest(request.expected_source_manifest)
    if manifest_hash and request.expected_source_hash and manifest_hash != request.expected_source_hash:
        raise ValueError("expected source manifest hash and --expected-source-hash disagree")
    return request.expected_source_hash or manifest_hash


def _missing_explicit_source_paths(repo_root: Path, source_paths: tuple[str, ...]) -> tuple[str, ...]:
    missing: list[str] = []
    for source_path in source_paths:
        path = (repo_root / source_path).resolve() if not Path(source_path).is_absolute() else Path(source_path)
        if not path.exists():
            missing.append(source_path)
    return tuple(missing)


def _worktree_blockers(repo_root: Path) -> tuple[str, ...]:
    status = _git_status_porcelain(repo_root)
    if status is None:
        return ("git_status_unavailable",)
    blockers: list[str] = []
    for line in status.splitlines():
        if line.startswith("??"):
            blockers.append("untracked_files")
            continue
        index_state = line[0]
        worktree_state = line[1]
        if index_state != " ":
            blockers.append("staged_changes")
        if worktree_state != " ":
            blockers.append("dirty_tracked")
    return tuple(dict.fromkeys(blockers))


def _git_status_porcelain(repo_root: Path) -> str | None:
    p = subprocess.run(
        ["git", "status", "--porcelain=v1"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if p.returncode != 0:
        return None
    return (p.stdout or "").rstrip("\n")


def _observe_origin_ref(repo_root: Path, requested_ref: str | None, allow_fallback: bool) -> GitVisibleRef:
    if not requested_ref:
        return GitVisibleRef(
            state="branch_missing",
            requested_ref=requested_ref,
            effective_ref=None,
            remote_head=None,
            blockers=("remote_branch_missing",),
            remediation=("checkout a branch or pass --ref",),
        )
    remote_head = _git_stdout(repo_root, "rev-parse", "--verify", f"refs/remotes/origin/{requested_ref}", check=False)
    if remote_head is not None:
        return GitVisibleRef("resolved", requested_ref, requested_ref, remote_head)
    if not allow_fallback:
        return GitVisibleRef(
            state="branch_missing",
            requested_ref=requested_ref,
            effective_ref=None,
            remote_head=None,
            blockers=("remote_branch_missing",),
            remediation=("pass --allow-default-branch-fallback only when default branch evidence is intended",),
        )
    default_ref = _git_stdout(repo_root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD", check=False)
    if default_ref is None or not default_ref.startswith("origin/"):
        return GitVisibleRef(
            state="default_branch_unknown",
            requested_ref=requested_ref,
            effective_ref=None,
            remote_head=None,
            blockers=("default_branch_unknown",),
            remediation=("fetch origin HEAD or pass an explicit existing --ref",),
        )
    effective_ref = default_ref.removeprefix("origin/")
    fallback_head = _git_stdout(repo_root, "rev-parse", "--verify", f"refs/remotes/origin/{effective_ref}", check=False)
    if fallback_head is None:
        return GitVisibleRef(
            state="branch_missing",
            requested_ref=requested_ref,
            effective_ref=effective_ref,
            remote_head=None,
            blockers=("remote_branch_missing",),
            remediation=("fetch the fallback branch before authoring preflight",),
        )
    return GitVisibleRef("resolved", requested_ref, effective_ref, fallback_head)


def _fetch_summary(outcome: GitProcessOutcome) -> FetchSummary:
    return summarize_fetch_outcome(outcome)


def _ahead_behind_heads(repo_root: Path, local_head: str | None, remote_head: str | None) -> tuple[int, int]:
    if local_head is None or remote_head is None:
        return (0, 0)
    output = _git_stdout(repo_root, "rev-list", "--left-right", "--count", f"{local_head}...{remote_head}", check=False)
    if output is None:
        return (0, 0)
    left, right = output.split()
    return (int(left), int(right))


def _git_stdout(repo_root: Path, *args: str, check: bool) -> str | None:
    p = subprocess.run(["git", *args], cwd=str(repo_root), capture_output=True, text=True, check=False)
    if p.returncode != 0:
        if check:
            raise RuntimeError(f"git failed: {' '.join(args)}\n{(p.stderr or '').strip()}")
        return None
    return (p.stdout or "").strip()
