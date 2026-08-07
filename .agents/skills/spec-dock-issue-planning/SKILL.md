---
name: spec-dock-issue-planning
description: ChatGPT-first Issue planning entrypoint for creating canonical Issue requirement, design, and plan artifacts from requirement-heavy, draft-heavy, or context-heavy inputs.
---

# Spec-Dock Issue Planning

Use this skill for non-trivial Issue planning. This is the primary planning route and it is ChatGPT-first.

The old local/manual planning workflow is not the normal route. Use `spec-dock-issue-planning-manual` only as a human-approved emergency backup after the ChatGPT-first route is hard-failed and unrecoverable.

## Responsibility

This skill orchestrates canonical Issue planning. It does not split the workflow into separate planning modes. Different inputs change the context framing and review focus only.

Codex owns:

- confirming the active Issue and parent Epic context;
- collecting repository, branch, parent, prior Issue, dependency, artifact, ADR, code, test, operator intent, and development background context;
- invoking the repo-local `./spec-dock/scripts/spec-dock-chatgpt` command family;
- preserving immutable Candidate and fresh Review evidence outside the repository;
- obtaining a Human decision bound to the exact Review bytes and reviewed identity;
- applying an approved plan only through `planning apply`;
- handing execution off only after the apply result is `ready`.

ChatGPT may produce:

- exactly one Planner or Semantic Revision authoring ZIP containing canonical `requirement.md`, `design.md`, and `plan.md` plus exactly one runtime-selected onboarding companion;
- closed Reviewer JSON;
- `information_insufficient` with missing information and questions.

The onboarding companion is subordinate evidence, not a fourth canonical specification. Candidate and Review output are evidence only. They do not grant canonical adoption, execution-ready, PR-ready, merge-ready, Issue finish, Epic completion, or PR delivery. Only `planning apply` with exact PASS Review evidence and exact Human approval may make managed writes and adopt the planning documents, and only its `ready` result completes the planning lifecycle.

## Execution Boundary

Use only the repo-local `./spec-dock/scripts/spec-dock-chatgpt` entrypoint. It resolves `oracle` through `PATH` as its only external product execution dependency. Missing or unsupported Oracle blocks the run; do not use a personal wrapper, arbitrary backend, or API fallback.

Before a formal ChatGPT run, set `SPECDOCK_ORACLE_REMOTE_CHROME` to the loopback CDP endpoint of an already-running authenticated managed Chrome, using only `127.0.0.1:<port>` or `localhost:<port>`. The runtime fails closed when this variable is absent, malformed, unreachable, or not a matching CDP endpoint. Chrome lifecycle and its dedicated persistent profile remain operator-owned: do not pass, copy, or discover a browser profile, cookies, credentials, or API token through SpecDock.

Before a formal run, verify the exact current repository, named branch, and HEAD through GitHub. Do not substitute a default branch, attachment, prompt context, or memory when that exact branch verification is unavailable.

## Read First

- Runtime help: `./spec-dock/scripts/spec-dock-chatgpt --help`
- `spec-dock/docs/workflow_issue.md`
- `spec-dock/docs/workflow_spec_authoring.md`
- `spec-dock/docs/authoring/decision-routing.md`
- `spec-dock/docs/authoring/scope-layering.md`
- active Issue `requirement.md`, `design.md`, `plan.md`, `report.md`, and scope-local `artifacts/`
- parent Epic docs, prior completed Issues, dependency state, ADRs, code, tests, and user-provided material relevant to the Issue

## Input Context Framing

Issue Planning has one workflow. Use these labels only to frame the prompt and adoption review:

- `requirement-heavy`: a requirement or requirement candidate is the strongest input; design and implementation planning are the main work.
- `draft-heavy`: draft requirement/design/plan artifacts already exist; formalization, refresh, consistency repair, and adoption review are the main work.
- `context-heavy`: discussion, artifacts, ADRs, code, tests, or background context are the strongest inputs; requirement extraction and boundary definition are the main work.

The required Planner/Semantic Revision output is exactly one authoring ZIP containing canonical Issue `requirement.md`, `design.md`, and `plan.md` plus exactly one runtime-selected onboarding companion, or `information_insufficient`. Do not create separate workflow modes from these labels.

## Operating Spine

1. Confirm the existing Issue, repository, named branch, clean synchronized HEAD, and an existing output directory outside the repository.
2. Create an immutable Candidate:

   ```bash
   ./spec-dock/scripts/spec-dock-chatgpt planning create \
     --issue <iss-id> --output <external-output-dir>
   ```

   When additional repository context is required, pass one external JSON
   context manifest. The manifest is provider-owned and closed to exactly the
   following two arrays; paths remain repository-relative and operator context
   remains bounded and non-sensitive:

   ```json
   {"relevant_source_paths":["src/example.py"],"operator_context":["preserve approved scope"]}
   ```

   ```bash
   ./spec-dock/scripts/spec-dock-chatgpt planning create \
     --issue <iss-id> --output <external-output-dir> \
     --context-manifest <external-context-manifest.json>
   ```

3. Review the exact Candidate with the default archive mode:

   ```bash
   ./spec-dock/scripts/spec-dock-chatgpt review planning \
     --issue <iss-id> --mode archive-candidate \
     --candidate <candidate.zip> --output <external-review-dir>
   ```

   Use the same Candidate with `--mode git-bound --candidate <candidate.zip> --reviewed-head <sha>` only as the explicit fallback when the current canonical three documents must be reviewed. Do not silently reuse a PASS across modes or Candidate versions.
4. Consume only the exact published `planning-review-result.json`. When P0/P1 findings exist, write the closed `planning-revision-request.json` beside that exact Review result and run:

   ```bash
   ./spec-dock/scripts/spec-dock-chatgpt planning revise \
     --candidate <candidate.zip> \
     --request <external-review-dir>/planning-revision-request.json \
     --output <external-output-dir>
   ```

   The command resolves only the fixed sibling `planning-review-result.json`; it does not scan other directories. Review the new Candidate in a fresh conversation. P2/P3-only observations do not trigger revision.
5. Obtain an explicit Human decision bound to the exact PASS Review bytes and reviewed identity. The CLI never generates, guesses, or completes this decision.
6. Apply only the exact approved identity:

   ```bash
   ./spec-dock/scripts/spec-dock-chatgpt planning apply \
     --issue <iss-id> --mode archive-candidate \
     --review-result <planning-review-result.json> \
     --human-decision <planning-human-decision.json> \
     --expected-head <sha> --output <external-operation-dir> \
     --candidate <candidate.zip> \
     --logical-filename <logical-filename> --zip-sha256 <sha256>
   ```

   For git-bound mode, retain `--candidate <candidate.zip>` and use `--reviewed-head <sha>` instead of the three archive identity options. The git-bound Review and apply must use the exact same Candidate created by `planning create`.
7. Accept the implementation handoff only when the result is `ready/adoption_published`. Candidate creation and Review completion return evidence-only `ok` results.
8. Treat live dogfood, PR creation, Issue finish, and merge as separate downstream work; Issue Planning does not imply any of them.

If direct ChatGPT output is received outside the public command workflow during an explicitly approved recovery, preserve it before evaluating or rewriting it:

- Immediately after output is received, and before claim review, Evidence Adoption Ledger disposition, or canonical rewrite, invoke the shared `spec-dock-chatgpt-authoring` preservation checkpoint.
- Refer to the shared skill for branch, status, and import-result rules; do not copy that decision matrix here.

## Manual Backup

Manual backup requires all of:

- hard / unrecoverable ChatGPT, browser, backend, provider, or account-state failure;
- reasonable wait / retry / recover attempts have failed;
- explicit human approval to use `spec-dock-issue-planning-manual`;
- failure class, recovery attempts, approval evidence, and fallback decision recorded in `report.md`.

Queued tabs, slow responses, retryable timeouts, stale sync, missing prompt context, or fixable setup are not manual fallback reasons.

## Stop Conditions

- Active Issue or parent Epic context is missing, stale, or contradictory.
- Repository/branch evidence required for ChatGPT-first planning is unavailable and no explicit local-context run was approved.
- ChatGPT returns `information_insufficient`; ask the human for the missing information instead of fabricating artifacts.
- Candidate or Review identity is missing, stale, ambiguous, or does not match the exact Human decision.
- Review is not PASS, or apply does not return `ready`.
- Candidate or Review evidence is being treated as canonical adoption.
- The Issue-local plan would change Epic boundaries, Issue order, scope allocation, shared architecture, or workflow policy without returning to the owning scope.
- Manual fallback is requested without explicit human approval.
