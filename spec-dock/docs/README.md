# 文書入口（spec-dock docs）

このディレクトリは `spec-dock init/update` により導入先リポジトリへ配置されます。  
Agent の operational entrypoint / first-read spine は導入済み skill です。まず skill で実行順序、停止条件、reviewer gate を確認し、docs は detail / reference layer として artifact semantics、policy detail、hard cases を調べるために参照します。
全体像は `guide.md`、曖昧さの明確化の bridge/reference は `workflow_clarification.md`、仕様書作成の phase promotion semantics は `workflow_spec_authoring.md`、scope 固有の lifecycle / governance detail は対象 scope の `workflow_*.md` を参照してください。
plan だけは `phase_plan.md` の shared axiom と `phase_plan_<scope>.md` の scope-specific playbook を合わせて参照します。
Core runtime command の現行 contract は `./spec-dock/scripts/spec-dock ...`、Issue Planning command の現行 contract は `./spec-dock/scripts/spec-dock-chatgpt ...` です。

## エージェント起点

`spec-dock init/update` は次の skill を導入します。これらが operational entrypoint / first-read spine であり、docs は skill から到達する detail / reference surface です。

- Hub: `.agents/skills/spec-dock-hub/SKILL.md`
- Clarification: `.agents/skills/spec-dock-clarification/SKILL.md`
- Initiative: `.agents/skills/spec-dock-initiative-planning/SKILL.md`
- Epic planning: `.agents/skills/spec-dock-epic-planning/SKILL.md`
- Epic execution: `.agents/skills/spec-dock-epic-execution/SKILL.md`
- Issue planning: `.agents/skills/spec-dock-issue-planning/SKILL.md`
- Issue execution: `.agents/skills/spec-dock-issue-execution/SKILL.md`
- ChatGPT authoring evidence lane: `.agents/skills/spec-dock-chatgpt-authoring/SKILL.md`
- Manual planning backups: `.agents/skills/spec-dock-initiative-planning-manual/SKILL.md`, `.agents/skills/spec-dock-epic-planning-manual/SKILL.md`, `.agents/skills/spec-dock-issue-planning-manual/SKILL.md`
- ADR: `.agents/skills/spec-dock-adr-facilitation/SKILL.md`

## 読み順

1. [guide.md](guide.md)
2. 対象 scope の workflow
   - [workflow_spec_authoring.md](workflow_spec_authoring.md)
   - [workflow_clarification.md](workflow_clarification.md)
   - [workflow_initiative.md](workflow_initiative.md)
   - [workflow_epic.md](workflow_epic.md)
   - [workflow_issue.md](workflow_issue.md)
   - [workflow_adr.md](workflow_adr.md)
3. phase の shared playbook
   - [phase_requirement.md](phase_requirement.md)
   - [phase_design.md](phase_design.md)
   - [phase_plan.md](phase_plan.md)
4. scope 固有の plan playbook
   - [phase_plan_initiative.md](phase_plan_initiative.md)
   - [phase_plan_epic.md](phase_plan_epic.md)
   - [phase_plan_issue.md](phase_plan_issue.md)
5. reference レイヤ
   - [reference_github.md](reference_github.md)
   - [reference_naming.md](reference_naming.md)
   - [reference_deps.md](reference_deps.md)
   - [reference_sync.md](reference_sync.md)
   - [workflow_chatgpt_authoring_pack.md](workflow_chatgpt_authoring_pack.md)
   - [reference_authoring_pack_backend.md](reference_authoring_pack_backend.md)
   - [authoring/chatgpt-pack.md](authoring/chatgpt-pack.md)

## 最短コマンド

```bash
./spec-dock/scripts/spec-dock new initiative --title "..."
./spec-dock/scripts/spec-dock new epic --initiative <initiative-id> --title "..."
./spec-dock/scripts/spec-dock new issue --epic <epic-id> --title "..."
./spec-dock/scripts/spec-dock new issue --create-github-issue --epic <epic-id> --title "..."

./spec-dock/scripts/spec-dock import epic <num-or-canonical-url> --title "..." [--initiative <id>] [--allow-foreign-url]
./spec-dock/scripts/spec-dock import issue <num-or-canonical-url> --title "..." [--epic <id>] [--allow-foreign-url]

./spec-dock/scripts/spec-dock issue start <github-issue-number>
./spec-dock/scripts/spec-dock issue start --id <issue-id>
./spec-dock/scripts/spec-dock issue finish

# Issue Planning（外部 output directory が必須）
./spec-dock/scripts/spec-dock-chatgpt planning create --issue <issue-id> --output <external-dir>
./spec-dock/scripts/spec-dock-chatgpt review planning --issue <issue-id> --mode archive-candidate --candidate <candidate.zip> --output <external-review-dir>
./spec-dock/scripts/spec-dock-chatgpt review planning --issue <issue-id> --mode git-bound --candidate <candidate.zip> --reviewed-head <sha> --output <external-review-dir>
./spec-dock/scripts/spec-dock-chatgpt planning revise --candidate <candidate.zip> --request <external-review-dir>/planning-revision-request.json --output <external-dir>
./spec-dock/scripts/spec-dock-chatgpt planning apply --issue <issue-id> --mode archive-candidate --review-result <review.json> --human-decision <decision.json> --expected-head <sha> --output <external-dir> --candidate <candidate.zip> --logical-filename <name> --zip-sha256 <sha256>
./spec-dock/scripts/spec-dock-chatgpt planning apply --issue <issue-id> --mode git-bound --review-result <review.json> --human-decision <decision.json> --expected-head <sha> --output <external-dir> --candidate <candidate.zip> --reviewed-head <sha>

./spec-dock/scripts/spec-dock active set <id|#num|url>
./spec-dock/scripts/spec-dock active set --id <node-id>
./spec-dock/scripts/spec-dock active set --github-issue <n>
./spec-dock/scripts/spec-dock active set <id|#num|url> --checkout
./spec-dock/scripts/spec-dock active show

./spec-dock/scripts/spec-dock deps check <target>
./spec-dock/scripts/spec-dock deps add --from <issue-id> --to <issue-id>
./spec-dock/scripts/spec-dock deps remove --from <issue-id> --to <issue-id>
./spec-dock/scripts/spec-dock validate
./spec-dock/scripts/spec-dock sync

# experimental: one-shot scoped Workbench copy
./spec-dock/scripts/spec-dock workbench copy --scope <initiative|epic|issue-id> --to <linked-worktree>

# specialized Workbench Markdown evidence import
./spec-dock/scripts/spec-dock artifact import chatgpt-output --issue <issue-id> --file <workbench-file.md> --title "..."

# generic opaque evidence import: one explicit regular file, no Workbench requirement
./spec-dock/scripts/spec-dock artifact import file --root --file <path>
./spec-dock/scripts/spec-dock artifact import file --initiative <initiative-id> --file <path>
./spec-dock/scripts/spec-dock artifact import file --epic <epic-id> --file <path>
./spec-dock/scripts/spec-dock artifact import file --issue <issue-id> --file <path> [--json]

# 管理対象 files/docs/templates/scripts/skills の更新（refresh）
./spec-dock/scripts/spec-dock update
./spec-dock/scripts/spec-dock update /path/to/project
```

## 高頻度ルール

- Initiative / Epic は `new` / `import` の前に既存ノード再利用を確認する
- Requirement / design / plan 作成は対応 planning skill を operational entrypoint にし、`workflow_spec_authoring.md` の phase promotion detail を参照して、fresh `spec-reviewer` の `review_status: pass` まで次 phase へ進めない
- ChatGPT / Oracle を使う planning では `spec-dock-chatgpt-authoring` skill と [workflow_chatgpt_authoring_pack.md](workflow_chatgpt_authoring_pack.md) を参照する。ChatGPT-first planning route が非自明な planning の正規 route であり、ChatGPT output、ZIP/tree、staged evidence、validation `pass` は evidence-only で、canonical adoption / reviewer pass / execution-ready / PR-ready ではない
- Issue Planning は repo-local `./spec-dock/scripts/spec-dock-chatgpt` から `PATH` 上の `oracle` だけを実行依存として使う。Oracle が未導入または非対応なら personal wrapper、arbitrary backend、API fallback を使わず block し、GitHub 上で exact current repository / branch / HEAD を確認できなければ default branchへfallbackしない
- Planner と Semantic Revision は canonical `requirement.md` / `design.md` / `plan.md` と runtime-selected の exactly-one onboarding companion を含む exactly-one authoring ZIP を返し、Reviewer は closed JSON を返す。companion は第四のcanonical specificationではなく subordinate evidence である
- Issue Planning の `planning revise` は request と同じ directory の exact `planning-review-result.json` だけを使う。archive と git-bound は別 identity であり、fresh PASS Review と exact Human approvalを満たして `planning apply` が `ready` を返すまで canonical adoption ではない。PR、Issue finish、merge は別 workflow である
- archive と git-bound の Review/apply は、`planning create` が生成した exact same Candidate を必須とする。Human approval 前に managed write は行わない
- manual planning backups は hard / unrecoverable ChatGPT route failure と human-approved emergency backup evidence がある場合だけ使う。queued tabs、retryable timeout、recoverable browser/backend setup は wait / retry / recover の対象であり、自動 fallback ではない
- 仕様書作成前後の曖昧さ、用語衝突、責務境界、正式質問は `spec-dock-clarification` skill を operational entrypoint にし、`workflow_clarification.md` を bridge/reference として一問ずつ扱う
- plan は shared `phase_plan.md` の後に対象 scope の `phase_plan_<scope>.md` を読む
- `new initiative` / `new epic` / `new issue` はデフォルトで GitHub Issue を作る。node create/import で local-only create へ自動フォールバックしない
- `new issue --create-github-issue` は default create の explicit alias
- node creation で既存 Issue へ紐づける場合は `--github-issue <n>` を使う。`--no-github` は node creation option ではない
- `--allow-foreign-url` は compatibility flag として残るが、current contract mismatch を auto-migrate せず reject/fail-fast しうる
- `import` は読み取り確認のみで、GitHub を更新しない。canonical URL は current repo と照合し、cross-repo node import は reject される
- Issue 実行の通常入口は `issue start <target>`、終了導線は `issue finish`。`active set` / `active set --checkout` は manual / recovery 用の low-level command として使う
- `active set` / `deps check` は `<target>` の後方互換を維持しつつ、`--id` / `--github-issue` の explicit form も使える
- 依存関係の追加/削除/確認は metadata の直編集ではなく `./spec-dock/scripts/spec-dock deps add/remove/check` を使い、変更後は `./spec-dock/scripts/spec-dock validate` と `./spec-dock/scripts/spec-dock sync` で GitHub live state を含めて整合を確認する。GitHub を呼ばない確認が必要な場合だけ `--no-github` を指定する
- legacy sequential discussion docs は grandfathered only。新規作成で sequence reuse / auto-rename / auto-repair はしない
- `./spec-dock/scripts/spec-dock update [path]` は repo-local self-update path で、target 省略時は current directory を更新する。明示 path を渡すとその managed repo を更新する
- runtime update は installer update の wrapper であり、固定 upstream `git+https://github.com/chemitaro/spec-dock` を `uvx --no-cache --from git+https://github.com/chemitaro/spec-dock spec-dock update <target>` として実行する。arbitrary source / cache / `--force` option は公開しない
- update は managed files/docs/templates/scripts/skills の更新であり、`init --force` でも old workspace の in-place migration ツールでもない。current contract mismatch は手動 normalize / rebuild が必要な場合がある
- Workbench は任意です。optional、temporary、worktree-local、disposable、non-canonical な作業場であり、fresh root と future Initiative / Epic / Issue の shell に `.workbench/README.md` が生成されますが、existing scope には no-backfill です。presence は任意であり、不在でも workspace は valid です
- `.workbench/README.md` は direct child の README-only tracking surface です。その他の Workbench entry は ignored payload として Git に ignore されます。Git ignore は security boundary ではありません。secret、credential、private customer data を置かないでください
- Workbench content の read / import authorization は evidence-only であり、canonical adoption ではありません。`artifact import chatgpt-output` は approved Workbench の単一 Markdown を source/bytes 不変で blank Artifact へ copy する実装済み specialized lane です。`chatgpt-output` typed token は予約せず、`new artifact` と共存します。imported ChatGPT output は evidence-only であり、canonical 採用には Evidence Adoption Ledger の採否、canonical docs への再記述、fresh reviewer gate が必要です
- `artifact import file` は Workbench と `chatgpt-output` から独立した generic lane です。`--root` / `--initiative` / `--epic` / `--issue` のいずれか一つと `--file` を指定し、一件の明示 regular file を opaque generic Artifact として保存します。source は変更・削除しません。generic result は source content、hash、byte count、repository 外 absolute path を出さず、repository 内 source は repo-relative、その他は basename のみを表示します
- generic import の成功は `committed=true` です。`publication_state=committed` または commit 後 warning の `committed_with_warning` は `retry_disposition=not_needed`、commit 前 failure は `not_committed` と `safe_after_remediation` です。保存した generic Artifact は常に `canonical=false` であり、Evidence Adoption Ledger、canonical docs、accepted ADR、fresh reviewer gate を経ない自動採用はしません。filename と collision は [reference_naming.md](reference_naming.md)、scope ごとの利用ルールは対象 `artifacts/rules.md` を参照してください
- explicit generic import の publication は platform safety boundary を持ちます。Linux は anonymous `O_TMPFILE` staging を使い、named-temp success fallback を持ちません。macOS は destination-side named stage と検証済み staged descriptor からの `fclonefileat` no-replace publication を使い、commit 後 cleanup の不確実性は unsafe unlink ではなく warning になります。same-UID actor が final check と unlink の間に置換する事象は accepted exclusion のままです。詳細は [guide.md](guide.md) を参照してください
- ordinary `uv run pytest` は default full-regression skip を適用する fast lane です。full-regression body は別の explicit lane であり、`uv run pytest --run-full-regression` を実行します
- root `spec-dock/.workbench/` は日付 bucket と必要 file の手動選択だけを使い、root 一括 copy command は持ちません。Initiative / Epic / Issue scope の copy は、同一 repository の linked worktree へ明示実行する source-wins の one-shot copy であり、自動 sync も copy-back も行いません。Workbench copy は directory をそのまま扱い、言語、拡張子、MIME、内容による file classifier を持ちません。update は既存 Workbench を unmanaged local content として保持し、migration、normalize、delete、promotion しません
- Issue plan は agent-native / behavior-slice based execution contract を持つが、cadence policy の detail/reference は `workflow_issue.md`
- naming 制約、GitHub 副作用、deps / sync の詳細は `reference_*.md` を参照する
