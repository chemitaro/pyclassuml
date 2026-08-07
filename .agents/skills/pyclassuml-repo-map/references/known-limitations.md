# Known limitations

- Static AST analysis does not prove runtime dispatch, dynamic imports, monkey-patching, dependency injection wiring, or generated code behavior.
- A class-name query seeds the containing file. PyClassUML may render other classes in that file and reachable modules.
- Duplicate class names require user selection; the runner does not rank candidates heuristically.
- `--current-state head` classifies Git changes against HEAD but reads current-side files from the working tree. Require a clean worktree or use exact A-to-B mode.
- A CLI `--ignore` list replaces configured user ignores; it does not append to them. Built-in ignore patterns remain active.
- Core contract `118b7d6` gives unspecified `diff` a depth of `1`, but the current remote fallback commit predates that change. Use `tool.pinned_commit` to distinguish the contracts until the fallback is deliberately repinned to a remotely reachable core commit.
- The new config contract has no unlimited sentinel. A config that inherits `diff` depth `1` cannot explicitly restore unlimited traversal; use an explicit finite depth when broader traversal is required.
- Current `--strict`/`mode` is stored in resolved configuration but is not consistently consumed downstream. Do not use it as the sole safety or completeness gate.
- Current `--target-python` is validated and stored, while parsing uses the running interpreter's normal `ast.parse` behavior. Do not claim language-version emulation.
- PyClassUML no-base diff may fall back to the initial commit. Always inspect base-resolution metadata before describing the result as a default-branch comparison.
- The initial skill contract produces PlantUML text only. It does not verify PlantUML rendering or generate SVG/PNG.
- PyClassUML automatic output names contain a timestamp. The runner avoids that nondeterminism by always passing an explicit evidence-bundle output path.
- Repository config, package boundaries, namespace packages, unresolved imports, syntax errors, traversal limits, and ignored files may narrow the graph. Review diagnostics and source before asserting completeness.
