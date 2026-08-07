# Git comparison modes

## Intent mapping

| Intent | Runner arguments | Meaning |
| --- | --- | --- |
| Current branch start to current work | `diff --repo <repo>` | PyClassUML resolves a default-branch merge-base when possible; current side is working tree plus untracked files. |
| Default branch HEAD to current work | `diff --base HEAD` | Compare only uncommitted and untracked changes with the current commit; avoids initial-commit fallback on the default branch. |
| Explicit local base to working tree | `diff --base <ref>` | Compare the exact local base ref with working tree. |
| Explicit local base to committed HEAD | `diff --base <ref> --current-state head --no-include-untracked` | Changed-file classification uses HEAD. Require a clean worktree for exact diagram contents. |
| Exact committed A to committed B | `diff --base A --end B` | Resolve both refs locally, clone outside the repository, detach the clone at B, and compare A to clean B. |
| Fresh remote ref | Add `--fetch` | Explicitly run `git fetch --prune` before resolving refs. Never fetch implicitly. |

## No-base behavior

PyClassUML first tries a default-branch candidate and uses its merge-base with HEAD. On the default branch or when no usable candidate exists, it falls back to the repository's initial commit. Confirm `base_resolution`, `resolved_base`, `requested_base`, and `base_candidate` in captured summary data.

Before running without a base, check the current branch. On a large repository's default branch, initial-commit fallback can turn an uncommitted-change question into a full-history analysis. Use `--base HEAD` when the intended comparison is only HEAD to the current working tree plus untracked files.

## Exact committed ranges

`--end` requires `--base`. Both must resolve to commits in the target repository before cloning. The runner:

1. Captures target HEAD and worktree status.
2. Resolves A and B to immutable commit IDs.
3. Creates a no-hardlink, no-checkout local clone under the evidence session.
4. Disables global/system Git config and hooks for checkout, then detaches at B.
5. Runs PyClassUML with base A, `current-state=head`, and no untracked files.
6. Removes the clone and confirms the target HEAD/status snapshot did not change.

Do not use this mode for an uncommitted B. Use working-tree mode instead.

## HEAD caveat

Current PyClassUML uses HEAD for changed-file and hunk classification under `--current-state head`, but reads current-side Python contents from the working tree. Therefore an exact HEAD claim requires a clean target worktree. Exact A-to-B mode avoids this mismatch by using a clean disposable clone at B.

The runner rejects `--current-state head` when the target worktree is dirty. An explicit base is resolved to an immutable commit before PyClassUML is launched.
