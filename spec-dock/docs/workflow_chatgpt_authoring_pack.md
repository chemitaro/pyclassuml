# オーサリングパックワークフロー（ChatGPT authoring pack）

この文書は、ChatGPT / Oracle を SpecDock planning workflow の evidence lane として使うための利用者向けガイドです。
Operational entrypoint は `.agents/skills/spec-dock-chatgpt-authoring/SKILL.md` であり、この文書は runtime command、authority boundary、human gate、relay delivery policy の参照面です。

## 基本原則

- ChatGPT / Oracle output は常に `authority: evidence_only` として扱う。
- ChatGPT-first planning route は、非自明な Initiative / Epic / Issue planning の正規 evidence-production route である。`spec-dock-chatgpt-authoring` は evidence lane であり、各 planning skill は共有checkpointの呼出し時点とscope固有のhandoffを所有する。Preservation実行、EAL disposition、canonical rewriteはmain orchestratorが所有する。
- ZIP / tree / staged evidence / candidate validation / approval check の `pass` は command-local validation pass であり、canonical adoption、fresh reviewer pass、execution-ready、PR-ready、merge-ready ではない。
- canonical `requirement.md` / `design.md` / `plan.md` / `report.md` の single-writer は main orchestrator である。
- ChatGPT output の受領後、main orchestrator は採否判断や canonical rewrite の前に semantic completeness と output form を分類し、preservation checkpoint を実行する。保存方法、exact status、receipt / exception field は [authoring/chatgpt-pack.md](authoring/chatgpt-pack.md) が reference authority を持つ。
- ChatGPT evidence を採用する場合、main orchestrator が capture / import、Evidence Adoption Ledger の採否、canonical docsへの再記述を実行し、fresh reviewer gate を通す。Import command、shared skill、planning skillは、canonical adoption、reviewer pass、execution-ready、finish、PR-ready、merge-ready、PR deliveryを自己主張しない。
- reviewed Epic plan が final delivery Issue を明示している場合だけ、中間 Issue は個別 PR を作らず、relay-style に `issue finish` から次 Issue の `issue start` へ進む。それ以外の multi-Issue Epic では通常の PR Delivery / Merge Preparation Gate に従う。
- Capacity limit、queued tab、retryable timeout、recoverable browser/backend failure は wait / retry / recover で扱う。manual planning skill は hard / unrecoverable failure と user-approved emergency backup evidence がある場合だけ使う。

## 正規計画と送達の全体像（ChatGPT First SpecDock Planning And Delivery Workflow）

```plantuml
@startuml
title ChatGPT First SpecDock Planning And Delivery Workflow
skinparam monochrome true
actor Human
participant "Planning Skill" as Planning
participant "ChatGPT Authoring Evidence Lane" as ChatGPT
participant "Main Orchestrator" as Main
participant "Report / EAL" as Report
participant "Spec Reviewer" as Reviewer
participant "Issue Execution" as Execution
participant "Final Quality Issue" as FinalGate

Human -> Planning : clarify scope / approve slices
Planning -> ChatGPT : request evidence
ChatGPT --> Planning : output received
Planning -> Main : request shared preservation checkpoint
Main -> Main : capture/import or exception/ZIP route
Main -> Report : EAL disposition
Main -> Main : canonical rewrite
Main -> Reviewer : review canonical docs
Reviewer --> Main : review_status pass
Main --> Planning : reviewed canonical handoff
Planning -> Execution : handoff execution-ready Issue
Execution -> FinalGate : relay after each Issue finish
FinalGate -> Human : mergeable PR evidence
@enduml
```

この図の `Planning Skill` はshared checkpointの呼出し時点とscope固有handoffを所有し、preservation実行、採用判断、canonical rewriteは行いません。`Main Orchestrator` がcapture/importまたはexception/ZIP route、EAL disposition、canonical rewriteを明示実行し、fresh reviewerへ渡します。`ChatGPT Authoring Evidence Lane` はreviewer passやexecution-readyを付与せず、Issue relayとfinal quality / PR deliveryも各downstream workflowのauthorityに残ります。

## 保存チェックポイント（Preservation checkpoint）

ChatGPT output は次のいずれかへ事前分類します。File の存在、拡張子、size、encoding だけで semantic completeness を自動判定しません。分類できない間は preservation status を付けず、import、EAL disposition、canonical rewrite を block します。

- 完成 standalone Markdown: Workbench source を `artifact import chatgpt-output` で明示的に保存する。
- 完全に受信した inline answer: answer 本文だけを追加、削除、整形せず Workbench Markdown へ capture して明示的に import する。Provider 内部の original bytes との同一性は主張しない。
- 本当に不完全または取得不能な inline output: unavailable exception を記録する。完全な source の保存失敗をこの branch へ読み替えない。
- ZIP / tree: 既存の review / quarantine / stage lane を使い、single-file import へ流さない。

External preserved evidence、delegated draft evidence、ZIP/tree staged evidence は独立した lane です。External preserved evidence の本文へ delegated draft 用 frontmatter や diff guard を追加せず、既存 delegated / ZIP safety contractも変更しません。詳細なstatus、failure、EAL fieldは [authoring/chatgpt-pack.md](authoring/chatgpt-pack.md) を参照します。

Standalone importは単一`.md` fileだけを対象にし、sourceを残してbytesを変更しないblank Artifact copyとして実行します。言語、拡張子、MIME、内容のclassifierやautomatic importはありません。`chatgpt-output`はimport kindであってtyped Artifact tokenではなく、template-based `new artifact`と独立して共存します。

## 証跡モード（Evidence mode）

### `github-synced`

`github-synced` は repo-aware ChatGPT invocation の default mode です。
GitHub に push 済みの branch / commit / source manifest を ChatGPT が参照できる前提で使います。

この mode でも ChatGPT output は正本ではありません。GitHub 上に存在する状態を参照した evidence として扱い、canonical adoption には EAL、canonical rewrite、fresh reviewer gate が必要です。

#### GitHub 同期 preflight の安全な実行

preflight は shell を介さず、SpecDock entrypoint を direct argv で実行します。shell wrapper、redirect、pipe、`tee`、heredoc、command substitution、inline environment assignment を追加しません。

```text
./spec-dock/scripts/spec-dock authoring preflight github-sync --output-dir <existing-external-directory>
```

`--output-dir` は任意です。receipt を保存する場合は、既存かつ repository 外の non-symlink directory を指定します。receipt は stdout の `--format` と独立した JSON で、file 名は `github-sync-preflight.receipt.json` に固定されます。安全な出力先では pass result と blocked result のどちらも保存されるため、shell redirect は不要です。

fetch と限定 retry は SpecDock が所有し、retry 時も同じ command / environment policy を保ちます。fetch の nonzero は追加権限が必要であることの証跡ではありません。nonzero を理由に `require_escalated` を追加したり、sandbox / permission mode を変更したり、agent-owned raw `git fetch` で preflight を置き換えたりしません。

blocked result では `blockers`、bounded diagnostics、`remediation` を確認し、remote 設定、authentication、rate limit、repository state、安全な出力先など、示された operator remediation を修正して同じ preflight を再実行します。`local-context` または default branch へ暗黙に切り替えません。evidence mode や fallback を変更する場合は、その変更を明示し、planning workflow の authority と `report.md` の記録要件に従います。

receipt が示す freshness は preflight の `observed_at` / snapshot 観測時点に限られます。`authoring pack prepare` は versioned receipt の kind、schema、digest、fetch / snapshot semantics を検証して prompt pack provenance に binding しますが、pack prepare 時点の current repository / remote を再取得・再検証しません。したがって receipt を backend invocation 直前まで fresh である証明として扱いません。

### `local-context`

`local-context` は、GitHub sync を使えない、または使わない理由がある場合に明示的に選ぶ lower-authority evidence mode です。
local docs、diff summary、tree snapshot、artifact、必要な source snippets を prompt pack に含めて ChatGPT に渡します。

`local-context` output は `github_sync: not_verified` 相当の evidence です。採用時は、同期できなかった理由、提供した local context、採用した claim、捨てた claim を `report.md` に残します。

## 上流から下流への使い分け

### イニシアチブ計画での利用（Initiative planning）

Initiative では、要件定義書を起点に Initiative の design / plan と Epic candidate を生成できます。
Epic candidate は提案であり、Epic node creation の前に human approval gate を必ず通します。

推奨 flow:

1. Initiative requirement を人間と main orchestrator で固定する。必要なら ChatGPT evidence を使ってもよい。
2. `authoring preflight github-sync` を direct argv で実行して GitHub 同期状態を確認する。receipt が必要なら `--output-dir <existing-external-directory>` を指定する。
3. `authoring pack prepare --mode initiative` で prompt pack を作る。
4. `authoring backend invoke` で backend command を使って ChatGPT / Oracle を呼び出す。
5. `authoring pack review` と `authoring pack stage` で ZIP / tree output を evidence として点検・配置する。
6. `authoring validate initiative-epic-candidates` で candidate schema を検査する。
7. 人間が Epic candidate を承認した後、main orchestrator が Epic node を作成し、canonical docs / report に採用判断を記録する。

### エピック計画での利用（Epic planning）

Epic では、Epic requirement / design / plan と、配下 Issue の draft requirement / draft design / draft plan をまとめて生成できます。
Issue candidate / draft は提案であり、Issue node creation の前に human approval gate を通します。

推奨 flow:

1. Epic requirement を固定する。必要に応じて Epic design / plan まで ChatGPT に一括生成させる。
2. `authoring pack prepare --mode epic` で prompt pack を作る。
3. ChatGPT output を preservation checkpoint で分類する。ZIP / tree なら `authoring pack review` と `authoring pack stage`、完成 standalone / inline なら reference contractの明示保存を使う。
4. `authoring validate epic-issue-candidates` で Issue candidate を検査する。
5. 人間が Issue slice を承認した後、Issue node を作成する。
6. 作成した各 Issue の draft docs は Issue-local artifacts として扱い、Issue planning 時に正式版へ採用する。

### イシュー計画での利用（Issue planning）

Issue には大きく二つの入口があります。

- Epic planning で作られた draft requirement / draft design / draft plan を正式版に整える。
- 単体 Issue として、人間との議論や既存 artifact から requirement / design / plan を作る。

Epic draft から採用する場合も、`authoring validate issue-draft-adoption` は draft adoption input の形式や一致を確認するだけです。`pass` は reviewer pass ではありません。
main orchestrator が採用部分を canonical docs に再記述し、fresh `spec-reviewer` pass を通してから execution-ready とします。

## 対応済み authoring commands（Supported authoring commands）

現在 supported として案内できる command は次の通りです。

```bash
./spec-dock/scripts/spec-dock authoring preflight github-sync
./spec-dock/scripts/spec-dock authoring preflight github-sync --output-dir <existing-external-directory>
./spec-dock/scripts/spec-dock authoring pack prepare
./spec-dock/scripts/spec-dock authoring backend invoke
./spec-dock/scripts/spec-dock authoring pack review
./spec-dock/scripts/spec-dock authoring pack stage
./spec-dock/scripts/spec-dock authoring validate initiative-epic-candidates
./spec-dock/scripts/spec-dock authoring validate epic-issue-candidates
./spec-dock/scripts/spec-dock authoring validate issue-draft-adoption
./spec-dock/scripts/spec-dock authoring validate selected-skeleton-fill
./spec-dock/scripts/spec-dock authoring approval check
```

## 延期・未対応の操作（Deferred / unsupported operations）

次の操作はこの runtime lane の supported command として案内しません。

- ChatGPT output から canonical docs を自動採用する。
- ZIP から Issue node を自動作成する。
- reviewer pass、authorized profile、execution-ready、PR-ready、merge-ready を自動設定する。

このため、`authoring adopt`、`authoring create-issues-from-zip`、`authoring mark-reviewer-pass`、`authoring set-authorized-profile`、`authoring issue-execution-ready`、`authoring pr-ready` のような操作名は、現在の supported usage example として使いません。

## 人間ゲートとリレー型 delivery（Human gate / relay delivery）

Epic / Issue の node creation 前には、candidate list を人間が確認し、明示的に承認します。
承認済み Issue の draft adoption では、commands が evidence の review / stage / validation を支援できます。ただし canonical adoption は自動化せず、main orchestrator の EAL disposition、canonical rewrite、fresh `spec-reviewer` pass を必ず通します。

Epic execution で reviewed Epic plan が final delivery Issue を定義している場合、中間 Issue は個別 PR を作りません。
`issue finish` で次 Issue に進み、最後の delivery Issue で Epic 全体の品質ゲート、レビュー指摘修正、手動確認、push、mergeable PR 作成をまとめて行います。
reviewed Epic plan がこの集約を定義していない場合は、通常の PR Delivery / Merge Preparation Gate に従います。
