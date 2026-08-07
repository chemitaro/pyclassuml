---
name: spec-dock-chatgpt-authoring
description: Shared evidence-lane skill for using ChatGPT / Oracle with SpecDock planning workflows, including sync/local-context modes, prompt packs, ZIP/tree outputs, validation, and adoption boundaries.
---

# Spec-Dock ChatGPT Authoring

Use this skill when ChatGPT / Oracle is requested for SpecDock planning authoring. It is the shared evidence lane invoked by ChatGPT-first Initiative, Epic, and Issue planning workflows; it does not own canonical docs, reviewer gates, assurance state, execution readiness, or PR delivery.

This skill is an operational kernel. Keep canonical adoption in the relevant planning skill and keep global invariants in `spec-dock-hub`.

Contract anchor: ChatGPT / Oracle output is evidence-only until the main orchestrator adopts or rejects it in `report.md`, integrates accepted claims into canonical docs, and obtains the required fresh reviewer pass.

## Read First

- Current state: `./spec-dock/scripts/spec-dock active show`
- Relevant planning entrypoint:
  - Initiative decomposition: `spec-dock-initiative-planning`
  - Epic Issue slicing or draft handoff: `spec-dock-epic-planning`
  - Issue draft adoption or formalization: `spec-dock-issue-planning`
- Active or parent scope docs: `requirement.md`, `design.md`, `plan.md`, `report.md`, and scope-local `artifacts/`
- Authoring runtime help when available:
  - `./spec-dock/scripts/spec-dock authoring --help`
  - `./spec-dock/scripts/spec-dock authoring preflight --help`
  - `./spec-dock/scripts/spec-dock authoring pack --help`
  - `./spec-dock/scripts/spec-dock authoring validate --help`
- Preservation reference: `spec-dock/docs/authoring/chatgpt-pack.md`

## Evidence Modes

- `github-synced`: use when the branch and relevant commits are pushed and visible to GitHub-backed tools. Record the sync evidence used for the prompt pack.
- `local-context`: use when GitHub sync is intentionally unavailable or not required. Attach local docs, diffs, tree snapshots, or artifacts directly, label output as lower-confidence local-context evidence, and do not claim GitHub-synced coverage.

## GitHub 同期 preflight の実行契約

`github-synced` を選ぶ場合は、SpecDock の entrypoint を direct argv で実行します。shell wrapper、redirect、pipe、`tee`、heredoc、command substitution、inline environment assignment を追加してはいけません。

```text
Run the SpecDock entrypoint as direct argv.
Do not add shell wrappers, redirects, pipes, tee, heredocs,
command substitution, or inline environment assignment.
```

receipt を file として残す場合は、既存の repository 外 directory を `--output-dir` に指定します。file 名は `github-sync-preflight.receipt.json` で固定され、stdout の `--format` にかかわらず JSON です。安全な出力先なら、pass だけでなく blocked result も同じ固定名へ保存されます。

```text
./spec-dock/scripts/spec-dock authoring preflight github-sync --output-dir <existing-external-directory>
```

fetch の nonzero は failure の証跡ですが、追加権限が必要であることの証跡ではありません。fetch result を理由に `require_escalated` を追加したり、sandbox / permission mode を変更したりしてはいけません。retry は SpecDock が同じ実行形を保ったまま限定的に行います。agent-owned raw `git fetch` で preflight を置き換えてはいけません。

```text
A nonzero fetch result is not evidence that additional permissions are required.
Never add require_escalated or change sandbox/permission mode in response to a fetch result.

Use --output-dir to persist the preflight receipt.
Retry is owned by SpecDock and preserves the same execution shape.
Do not replace preflight with agent-owned raw git fetch.
Do not silently switch to local-context or default branch.
```

blocked result では `blockers`、bounded diagnostics、`remediation` を読み、remote configuration、authentication、rate limit、repository state、safe output directory など、示された operator remediation を直します。`local-context` や default branch へ暗黙に切り替えません。mode または fallback の変更が必要なら、planning workflow の authority と evidence 制約に照らして明示的に判断・記録します。

persisted receipt は preflight 観測時点の evidence です。`authoring pack prepare` は versioned receipt の kind、schema、digest、fetch / snapshot semantics を検証して prompt pack へ binding しますが、pack prepare 時点の repository や remote を再取得・再検証しません。backend invocation 直前までの freshness や reviewer / execution / PR authority を receipt から推測してはいけません。

## Operating Spine

1. Resolve the active scope and target planning workflow.
   - If the requested scope is unclear, return to the relevant planning skill or `spec-dock-clarification`.
2. Choose `github-synced` or `local-context`.
   - Stop if synced evidence is required but missing or stale.
3. Prepare the prompt pack and output contract.
   - Include source constraints, target scope, expected artifact shape, and forbidden authority claims.
4. Invoke only an operator-configured backend or runtime path.
   - Do not require private local wrapper paths, account state, or browser profile details as SpecDock product dependencies.
   - SpecDock does not select an Oracle implementation or version. The operator-owned backend wrapper resolves the single backend command and selects the current ChatGPT `Pro` model.
   - Treat tab capacity, queued browser sessions, and retryable backend timeouts as wait/retry conditions, not as reasons to use the manual route.
   - Treat browser/backend startup failure as recoverable when restart, session cleanup, or configuration repair is available.
5. Before adoption or canonical rewrite, apply the preservation checkpoint below to the received output.
   - This skill classifies the output and evaluates the resulting evidence. The main orchestrator explicitly performs any capture, import, exception recording, or ZIP/tree routing.
6. Review returned ZIP/tree output, candidate reports, draft docs, or summaries as evidence.
   - Preserve eligible complete output separately from adopted canonical text.
7. Validate candidates or draft-adoption input when runtime support exists.
   - Runtime validation can make evidence easier to review; it is not a reviewer pass.
8. Route back to the relevant planning skill for canonical adoption.
   - Initiative planning owns Initiative docs and Epic decomposition approval.
   - Epic planning owns Epic docs, Issue slicing, and human approval before Issue node creation.
   - Issue planning owns Issue `requirement.md`, `design.md`, `plan.md`, Evidence Adoption Ledger entries, fresh `spec-reviewer`, and execution handoff.

## Preservation Checkpoint

Classify semantic completeness and output form before preservation, Evidence Adoption Ledger disposition, or canonical rewrite. Do not infer completeness from file presence, extension, size, or encoding. If classification is unresolved, return a blocking handoff without a preservation status.

Choose exactly one branch:

- Complete standalone Markdown: the main orchestrator places the source in Workbench, explicitly runs `artifact import chatgpt-output`, and verifies the receipt. A complete receipt establishes `imported_byte_exact` only from the Workbench source to the imported Artifact.
- Complete received inline answer: the main orchestrator captures only the complete answer text, without adding, removing, reformatting, or normalizing content, then explicitly imports it. Record `captured_received_text`; never claim identity with provider-original bytes or durably import a wrapper transcript containing prompts or metadata.
- Genuinely incomplete or unavailable inline output: record `skipped_inline_unavailable` with reason, decision owner, nonblocking rationale, and next action or revisit condition. Do not record source/destination paths, hashes, byte counts, or a byte-exact claim.
- ZIP/tree output: route to the existing review, quarantine, stage, and validation lane. Do not convert it to single-file import or weaken existing ZIP safety checks.

Evaluate an import result as follows:

- `committed=true` with final repo-relative path, SHA-256, byte count, `import_kind=chatgpt-output`, and `storage_identity=blank`, and with no warning: preservation result is `pass`.
- The same complete receipt with `committed=true` and a warning: preservation result is `pass-with-warning`; retain the warning and do not retry automatically or create a duplicate import.
- `committed=false`, a missing receipt field, an eligibility failure, or unresolved semantic completeness: block adoption and canonical rewrite.
- Never reclassify a complete source whose import failed as `skipped_inline_unavailable`.

Return a content-free handoff containing the selected branch or unresolved classification, preservation status when applicable, receipt metadata or exception-field completeness, blocking decision, and next action. Receipt metadata is limited to repo-relative paths, hash, byte count, import/storage identity, committed state, and warning; do not include the evidence body, secret-like values, or absolute host paths.

This skill owns only the shared classification contract and evidence evaluation. It does not execute capture or import, write the Evidence Adoption Ledger, adopt claims, rewrite canonical docs, mutate assurance state, or claim reviewer/readiness/finish/PR status. The main orchestrator owns preservation execution, adoption disposition, and canonical rewrite; the relevant planning workflow and fresh reviewers retain their existing gates.

## Evidence Contract

- Record prompt source, evidence mode, invocation summary, output location, validation result, adoption/rejection decision, and reviewer gate status in the relevant `report.md`.
- Treat generated Requirement / Design / Plan text, Issue drafts, candidate lists, ZIPs, staged trees, review reports, and validation reports as source evidence.
- Adopt only specific claims that are source-grounded, locally checked, and integrated by the main orchestrator.
- Keep rejected, unsafe, stale, or unverifiable claims out of canonical docs and record why they were rejected when material.

## Failure Classification

- `retryable`: tab-capacity wait, queued run, transient timeout, temporary browser contention, or stale sync that can be refreshed.
- `recoverable`: browser/backend startup failure, local configuration issue, missing backend command, or prompt-pack preparation failure that can be repaired in the current environment.
- `blocked`: required synced evidence, account access, GitHub visibility, or source context is missing and cannot be supplied in the current run.
- `stale`: output was produced against an older branch, commit, artifact set, or dependency state.
- `rejected`: output is unsafe, unverifiable, contradicts source evidence, lacks requested files, or uses forbidden authority claims.
- `hard-unrecoverable`: ChatGPT / browser / backend provider failure remains unresolved after wait / retry / recovery, and the user explicitly approves using a manual backup planning skill.

## Forbidden Claims

ChatGPT authoring output, runtime validation, ZIP review, candidate validation, or staged draft artifacts must not claim:

- canonical adoption completed
- canonical docs were written or approved by ChatGPT / Oracle
- `.assurance.json` mutation
- `authorized_profile` decision
- reviewer pass, including fresh `spec-reviewer`, `code-reviewer`, or `qa-reviewer` pass
- execution-ready
- PR-ready
- merge-ready
- Issue finish
- Epic completion
- PR delivery

## Stop Conditions

- Active scope or target planning workflow is missing or contradictory.
- `github-synced` evidence is required but branch, commit, or GitHub visibility evidence is stale or missing.
- ChatGPT / Oracle output is unreviewed, unsafe, unverifiable, or not traceable to provided sources.
- Human approval before Epic or Issue node creation is missing.
- Issue docs are draft-only, template-only, or lack Evidence Adoption Ledger entries for draft adoption.
- Fresh `spec-reviewer` pass is missing after canonical doc changes.
- Any output claims canonical authority, assurance mutation, reviewer pass, readiness, finish/completion, mergeability, or PR delivery.
