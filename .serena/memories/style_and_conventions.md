# Style and conventions
- User-facing chat should be in Japanese.
- Assume STT typos; verify identifiers and paths via repo search before acting.
- New paths should use lowercase; avoid creating or renaming files/dirs containing uppercase letters unless explicitly justified.
- Commit messages should be Japanese multi-line Conventional Commits.
- Important domain guardrails: external CLI only, AST-only static analysis, read-only operation, do not import or execute analyzed code, do not modify analyzed projects.
- Important path semantics: keep `execution_cwd`, `project_root`, `package_root`, and `scope_root` as distinct concepts.