# CLI contract

## Tool resolution

The runner resolves PyClassUML in this order:

1. `--tool-repo`
2. `PYCLASSUML_REPO`
3. The repository containing this skill after resolving symlinks
4. Exact fallback `uvx --from git+https://github.com/chemitaro/pyclassuml.git@c669668a9e8af9ef8c1e475bf56a551121c325a6 pyclassuml`

Local checkout execution uses an already-installed `.venv/bin/pyclassuml` (or Windows equivalent) directly, so it cannot trigger environment synchronization in the analyzed repository. If no existing local console script is available, the runner uses the exact `uvx` fallback. The analyzed project never receives a dependency.

The PyClassUML child process runs with `PYTHONSAFEPATH=1` and `PYTHONDONTWRITEBYTECODE=1`; this avoids current-directory import injection and bytecode-cache writes in an analyzed checkout that is also the tool checkout.

## Boundaries

- `--repo` is the analyzed repository root and process working directory.
- `--project-root` defaults to `--repo`.
- `--package-root`, when supplied, must be inside `project_root`.
- `--scope-root`, when supplied, must be inside `package_root` or `project_root` when package root is omitted.
- Relative boundary paths are resolved from `--repo` by the runner and passed as absolute paths.
- An explicit `--config` must be inside `--repo`.

For monorepos, set all three boundaries explicitly. For ordinary repositories with a correct `.pyclassuml.toml`, avoid redundant overrides.

## Depth and configuration

Do not add `--depth` by habit. Core contract `118b7d6` resolves each common setting by presence in this order:

1. Explicit CLI value
2. Active `[generate]` or `[diff]` command section
3. Top-level common setting
4. Command default

The nine common settings are `project_root`, `package_root`, `scope_root`, `output`, `ignore`, `depth`, `mode`, `target_python`, and `relative_path_base`. `[generate]` may override those nine. `[diff]` may override those nine plus `current_state` and `include_untracked`. Generate targets and diff base refs remain CLI-only.

Presence matters: `depth = 0`, `include_untracked = false`, and `ignore = []` are explicit values rather than missing values. Command-section `ignore = []` clears a top-level ignore list. Repeated CLI `--ignore` values replace configured user ignores rather than extending them; built-in ignores still apply.

With all layers unspecified, `generate` depth remains unlimited (`None`) and `diff` depth is `1`. Depth limits dependency traversal and the render frontier; it does not limit Git changed-file collection or the AST parse frontier. There is no config sentinel for explicitly restoring unlimited `diff` traversal. Specify depth only when the analysis question justifies a hop limit.

The current remote fallback commit `c669668a9e8af9ef8c1e475bf56a551121c325a6` predates command-section overrides and the `diff` depth-1 default. Until the new core commit is remotely reachable and deliberately repinned, inspect `tool.pinned_commit` and do not assume the new defaults on fallback runs.

Config-origin relative paths use the active command's `relative_path_base`; explicit CLI paths remain relative to the execution cwd. The selected `project_root` is also the VCS root for diff analysis.

`--strict` and `--target-python` are accepted by the current CLI but are not reliable completeness or parser-version guarantees. See `known-limitations.md`.

## Generate targets

Targets may be Python files, directories, or quoted globs. The runner resolves ordinary relative file and directory targets under `--repo`; it preserves glob strings for PyClassUML.

`--class-name` performs AST-only discovery. It selects the containing file as a PyClassUML seed; it does not filter the resulting diagram to one class. Use a module-qualified name to disambiguate where possible.
