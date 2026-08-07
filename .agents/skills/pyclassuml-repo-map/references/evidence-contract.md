# Evidence bundle contract

Every attempted analysis creates or uses a repository-external bundle containing:

- `diagram.puml`: PyClassUML output, or a zero-byte placeholder when analysis fails before artifact generation.
- `run-evidence.json`: structured execution evidence.
- `stdout.log`: exact PyClassUML standard output, or runner diagnostics before invocation.
- `stderr.log`: exact PyClassUML standard error plus runner failure details when applicable.
- `class-candidates.json`: present when a class query is ambiguous.

## Important JSON fields

- `schema_version`: evidence schema version.
- `status`: `completed`, `failed`, or `needs_input`.
- `intent`: normalized runner subcommand and user-selected options.
- `repository.before` and `repository.after`: HEAD, branch, porcelain status, dirty/untracked content digest, and combined snapshot digest.
- `repository.worktree_unchanged`: whether HEAD and porcelain status stayed identical during the run.
- `boundaries`: resolved project, package, and scope roots.
- `comparison`: requested and resolved refs, current state, untracked policy, fetch policy, and clone facts.
- `tool`: local checkout or exact fallback selection plus the executable argv prefix.
- `pyclassuml.argv`: exact argv passed to PyClassUML.
- `pyclassuml.exit_code` and `pyclassuml.summary`: captured outcome and counters.
- `class_resolution`: queries, candidates, selected files, and parse diagnostics.
- `artifacts`: size and SHA-256 for retained artifacts.
- `cleanup_command`: managed cleanup command when `codex-tmp` is available.
- `source_verification_required`: true for warnings, degraded output, failures, or ambiguous class resolution.

## Reporting

Return the absolute bundle path. Summarize endpoints, boundaries, whether depth came from defaults/config or explicit CLI, the PyClassUML outcome, warnings, and source files subsequently checked. Do not paste the full `.puml` or evidence JSON unless requested.
