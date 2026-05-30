# SpecDock Bootstrap Bridge

Treat these instructions as a temporary SpecDock bootstrap bridge.

Apply them only when `.codex/config.toml` configures `.codex/AGENTS.md` as a fallback project document and the repository root does not already provide authoritative `AGENTS.md` guidance for the same scope.

Resolve overlap by scope: `spec-dock/active/*` defines the current task contract, the repository root `AGENTS.md` defines repo, product, and domain rules, `.codex/config.toml` defines session and orchestrator behavior, and these instructions remain subordinate bootstrap guidance.

Limit these instructions to SpecDock bootstrap workflow rules such as active-doc discovery, `validate` / `sync` usage, handling of SpecDock-managed files, default delegation for SpecDock operations, and a short capability summary for first use.
Do not apply them to repo architecture, product/domain guidance, coding conventions, testing policy, or session/orchestrator behavior.

If the repository root `AGENTS.md` exists, treat it as authoritative for repo, product, and domain guidance. Keep these instructions limited to bootstrap workflow rules only.

## Default Operator

Treat `spec-manager` as the default specialist for SpecDock operations.

Use `spec-manager` by default for SpecDock command workflows instead of operating the tool ad hoc. If `spec-manager` delegates to other specialists, the authoritative task contract still comes from `spec-dock/active/*` and the current issue docs.

Keep requirement/design/plan/report authoring with the main orchestrator. Use `spec-manager` for bounded command execution, command lookup, and operational evidence only.

For mixed tasks, keep docs/context ownership in the main orchestrator and delegate only the command portion to `spec-manager`.

## What SpecDock Can Do

SpecDock provides a CLI workflow for spec-driven execution. It can:
- create and import spec nodes such as initiatives, epics, issues, and discussion docs
- maintain the active working context for the current task
- validate the tree and diagnose broken or incomplete state
- regenerate CLI-managed derived state
- check dependency readiness before implementation starts

## Read First
1. `spec-dock/active/issue/{requirement,design,plan}.md`
2. `spec-dock/active/epic/{requirement,design,plan}.md`
3. `spec-dock/active/initiative/{requirement,design,plan}.md`
4. Repository root `AGENTS.md`, if it exists

Always start from `spec-dock/active/*`. When no active context exists, those paths already resolve to the built-in placeholder provided by SpecDock.

## Learn SpecDock

For SpecDock usage and workflow details, start here:
- `spec-dock/docs/guide.md`: overall entry point
- `spec-dock/docs/workflow-tree.md`: tree structure, active context, and sync outputs
- `spec-dock/docs/workflow_issue.md`: issue execution workflow
- `spec-dock/docs/reference_sync.md`: sync behavior and generated artifacts

## Operating Rules
- Treat repo docs as the source of truth, not chat history.
- Do not implement until issue `requirement.md`, `design.md`, and `plan.md` are aligned.
- Record decisions, validation, and unresolved items in issue `report.md`.
- Run `./spec-dock/scripts/spec-dock active show` at session start.
- Run `./spec-dock/scripts/spec-dock validate` after structural changes and before handoff.
- Use `./spec-dock/scripts/spec-dock sync` only to regenerate CLI-managed views, pointers, or exported state. Do not use it as a general repair step.

## Scoped Discussion Draft Authoring

Canonical `requirement.md` / `design.md` / `plan.md` / `report.md` are main orchestrator single-writer authority. System-architect and implementation-planner style sub-agents must not directly edit those canonical docs.

Sub-agent authoring outputs are not proposal-only. When the active issue contract permits delegated authoring, sub-agents may directly create exactly one new scope-local flat Markdown draft, analysis, or discussion-local report under the target `discussions/` direct child.

Filenames follow the existing discussion rules:

- `<ts>-<kind>-<slug>.md`
- `<ts>-<nn>-<kind>-<slug>.md` for same-second collisions

Do not create per-agent directories, run/task directories, global draft stores, or `discussions/delegated-authoring/` output for new delegated authoring runs.

Sub-agent-created drafts use lightweight provenance: `created_by_role`, `scope_id`, `source_paths`, `intended_targets`, `adoption_status: unreviewed`, `reflected_to: []`, `diff_guard_result`, and an adoption ledger note. Do not require task manifest hash, Permission Profile hash, session invocation hash, or probe run id as standard delegated draft evidence.

Static adapters for `system-architect` and `implementation-planner` use guarded workspace-write for scope-local `discussions/` authoring. Workspace-write is not a hard path allow-list and is not permission to perform canonical target write. Delegated authoring may create exactly one new flat Markdown draft/analysis/report file directly under initiative, epic, or issue `discussions/`; existing discussion draft updates are out of scope for the static adapter contract unless a later workflow explicitly defines a narrower allowlist. The target `discussions/` directory should be clean at baseline time. Dirty or untracked target discussion entries make delegated output adoption-ineligible until post-run diff guard passes and `report.md` records the ledger entry.

Historical `iss-00126` delegated-authoring manifest/Profile/probe/session artifacts are grandfathered evidence. Do not delete, rename, or treat them as validation failures solely because the current contract has changed.

## Source Boundaries
- `spec-dock/active/*`: current task contract
- Repository root `AGENTS.md`: repo, product, and domain rules
- `.codex/config.toml`: session behavior and orchestrator rules
- `.codex/AGENTS.md`: bootstrap-only SpecDock operating rules
- `ADR`: accepted durable decisions
- `discussion`: supporting rationale and context; may include superseded options

## Do Not
- Do not treat chat logs as canonical instructions.
- Do not start implementation before issue `requirement.md`, `design.md`, and `plan.md` are aligned.
- Do not hand-edit `spec-dock/active/*` links or `.path` files.
- Do not hand-edit CLI-managed generated views or exported state when `sync` owns regeneration.
- Do not use these instructions for repo, product, domain, or session rules.

## Escalate When
- Active docs conflict with each other or with the repository root `AGENTS.md`.
- `validate` fails and the cause is unclear.
- Dependency readiness blocks implementation.
- It is unclear whether a file is CLI-managed or safe to edit manually.
- A structural change would broadly rewrite SpecDock-managed docs or generated state.
