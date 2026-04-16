---
name: git-commit-conventional-ja
description: Delegate git commit work to an appropriate sub-agent and create safe Japanese multi-line Conventional Commits messages based on the actual staged diff. Use when Codex is asked to inspect git changes, choose an appropriate Conventional Commits type/scope/subject/body/footer, handle pre-commit or commit-hook failures safely, and return the resulting commit hash and message.
---

# Git Commit Conventional JA

Inspect the actual commit target before writing anything. Read `references/conventional-commits-v1.0.0.md` only when exact normative wording, edge cases, or allowed footer syntax matter.

## Delegation Guidance

- Prefer delegating commit work to an appropriate sub-agent instead of spending main-session context on routine git operations.
- `spark-worker` or `utility-worker` are usually good fits for this kind of bounded git task. Choose whichever best matches the task size and complexity.
- When delegating, pass the intended commit scope, any staging constraints, whether hook failures may be investigated, and the required return values: commit hash, exact committed message, or a clear blocker.

## Workflow

1. Inspect `git status --short`, staged diff stats, and staged hunks first. Use `git diff --cached --stat` and `git diff --cached` as the default source of truth.
2. If nothing is staged, inspect unstaged changes before acting. Do not silently stage unrelated files; stage only the intended scope or ask when the target commit set is unclear.
3. Choose `type`, optional `scope`, `summary`, bullet body, and optional footer from the reviewed diff, not from filenames or branch names alone.
4. If the staged diff mixes unrelated concerns, split the work into multiple commits instead of forcing one broad message.
5. Write the message in a file and use `git commit -F <file>` to avoid shell-escaping mistakes when the delegated worker or fallback executor performs the commit.
6. After commit, return the commit hash and the exact committed message.

## Message Rules

- Keep Conventional Commits tokens exactly as specified: `feat`, `fix`, `BREAKING CHANGE`. Keep these tokens in English and preserve required casing.
- Write the human explanation in Japanese: summary, bullet body text, and footer values should be Japanese unless a spec token or identifier must stay as-is.
- Use this shape:

```text
type(scope): summary

- 変更点その1
- 変更点その2

Refs: #123
```

- Keep `scope` optional and short. Omit it when it does not add useful context.
- Prefer concise Japanese summaries on the first line. Keep the body as flat bullet points that explain the reviewed changes and their intent.
- Use only footers grounded in the task, typically `BREAKING CHANGE:`, `Refs:`, or `Closes #...`.
- Common types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `build`, `ci`, `perf`, `revert`. For exact rules and footer grammar, consult the reference.

## Breaking Change Judgment

- Treat the commit as breaking when it changes a public API, CLI contract, schema, required configuration, data shape, default behavior, or any other behavior that can require downstream action.
- Use `!` immediately before `:` in the header when the change is breaking.
- Add a `BREAKING CHANGE:` footer whenever the reader needs a concrete migration or impact note. Prefer including the footer even when `!` is already present if the impact needs explanation.
- If the impact is ambiguous after inspecting the diff and nearby docs/tests, pause and clarify instead of guessing.

## Hook Failure Handling

- If `git commit` triggers hooks and they fail, do not bypass them with `--no-verify` unless the user explicitly requests that.
- Capture the failing command or output, fix what is safely fixable, rerun the relevant checks, and retry the commit.
- If the failure is environmental or outside the reviewed change set, explain the blocker clearly and stop before creating a misleading commit.

## Minimal Command Pattern

```bash
git status --short
git diff --cached --stat
git diff --cached
git commit -F /tmp/commit-message.txt
git rev-parse HEAD
git log -1 --format=%B
```
