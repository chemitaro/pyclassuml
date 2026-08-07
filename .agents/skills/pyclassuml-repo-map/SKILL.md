---
name: pyclassuml-repo-map
description: Analyze Python class and file dependencies or Git changes with PyClassUML and produce evidence-backed PlantUML class diagrams. Use when Codex needs a token-efficient map of several Python modules, must inspect the impact of a class or file, compare a branch/default branch/working tree/commit range, explain implementation changes before merge, or orient architecture and review work without importing or modifying the target code.
---

# PyClassUML Repo Map

Use PyClassUML as a read-only orientation aid, then verify important conclusions in source. Generate `.puml` and a retained evidence bundle outside the analyzed repository.

## Core workflow

1. Inspect repository instructions and `.pyclassuml.toml` before choosing boundaries.
2. Select one intent:
   - Class, file, package, or dependency impact: use `generate`.
   - Branch start or default-branch merge-base through working tree: use `diff` without `--end`, after checking whether the current branch is the default branch.
   - Uncommitted and untracked changes on the default branch: use `diff --base HEAD`; an omitted base may fall back to the initial commit and scan the repository's full history.
   - Exact committed `A` to committed `B`: use `diff --base A --end B`.
3. Set `project_root`, `package_root`, and `scope_root` only when repository structure requires them. Preserve `scope_root ⊆ package_root ⊆ project_root`.
4. Do not force `--depth`. Let CLI, the active command section, top-level configuration, or the selected PyClassUML command default decide unless a narrower or broader traversal is material to the question.
5. Run `scripts/run_pyclassuml.py`. Do not invoke ad hoc checkout, reset, stash, or target-repository writes around it.
6. Read `run-evidence.json`, then inspect `diagram.puml`. Follow paths back to source for important findings.
7. Report the absolute evidence-bundle path and state the comparison endpoints, scope, depth source, warnings, and source files verified.

## Run the wrapper

Resolve this skill directory and invoke its runner:

```bash
python3 <skill-dir>/scripts/run_pyclassuml.py generate \
  --repo /absolute/path/to/repo \
  --project-root . \
  --package-root src \
  --scope-root src \
  src/domain/model.py
```

Resolve a class name without importing target code:

```bash
python3 <skill-dir>/scripts/run_pyclassuml.py generate \
  --repo /absolute/path/to/repo \
  --class-name OrderService
```

Map the current branch's accumulated and uncommitted changes. Working tree plus untracked files is the default:

```bash
python3 <skill-dir>/scripts/run_pyclassuml.py diff \
  --repo /absolute/path/to/repo
```

Map only the default branch's current uncommitted and untracked changes:

```bash
python3 <skill-dir>/scripts/run_pyclassuml.py diff \
  --repo /absolute/path/to/repo \
  --base HEAD
```

Map an exact committed range without changing the target checkout:

```bash
python3 <skill-dir>/scripts/run_pyclassuml.py diff \
  --repo /absolute/path/to/repo \
  --base <commit-a> \
  --end <commit-b>
```

Pass `--fetch` only when the user explicitly requests fresh remote refs. Normal runs use current local refs.

## Interpret results

- Treat `clean_success` as a usable static-analysis result, not proof of runtime behavior.
- Use `warning_only_success` or `degraded_success` for orientation only. Verify design, review, and merge conclusions against source.
- On `needs_input`, read `class-candidates.json`, present qualified names and paths, and ask the user to choose. Never guess between duplicate class names.
- On failure, inspect `stderr.log` and `run-evidence.json`; do not claim a diagram was produced.
- When depth is not explicit, inspect the selected config and `tool.pinned_commit` before reporting its effective value. Core contract `118b7d6` makes `generate` unlimited and `diff` depth `1`; the current remote fallback predates that contract, so do not claim depth `1` merely because `intent.depth_cli` is null.
- Keep the bundle until explicit cleanup. When the bundle uses `codex-tmp`, use the recorded `cleanup_command` rather than deleting it ad hoc.

## Safety invariants

- Never import or execute analyzed Python modules.
- Never write inside the analyzed repository, except an explicitly requested `git fetch` updates Git refs.
- Never checkout, reset, clean, stash, or switch the target repository.
- Reject evidence paths inside the analyzed repository.
- Use a repository-external disposable clone for explicit committed `A` to `B`; remove that clone after the run.
- Prefer the PyClassUML checkout that owns this skill. Fall back only to the exact commit pinned by the runner.
- Do not silently render SVG or PNG. The initial contract produces `.puml` only.

## Load detailed references as needed

- Read [references/cli-contract.md](references/cli-contract.md) before constructing uncommon path, config, ignore, strict, target-Python, or tool-resolution options.
- Read [references/git-modes.md](references/git-modes.md) for endpoint selection, local-ref policy, arbitrary ranges, and clean-HEAD requirements.
- Read [references/evidence-contract.md](references/evidence-contract.md) when auditing, automating, or summarizing a bundle.
- Read [references/known-limitations.md](references/known-limitations.md) before making architecture, review, or completeness claims.

## Verify skill changes

When this skill or its runner changes, run the skill-local regression gate explicitly; the repository's ordinary `pytest` discovery does not include this hidden skill tree:

```bash
python3 <skill-dir>/scripts/test_run_pyclassuml.py
uv run --with ruff ruff format --check <skill-dir>/scripts
uv run --with ruff ruff check <skill-dir>/scripts
```

Also run the `skill-creator` `quick_validate.py` check and the repository's normal test suite. Keep this maintenance gate skill-local so installing the skill does not change PyClassUML's product test configuration.
