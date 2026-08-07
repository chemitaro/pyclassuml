# エピックワークフロー（workflow: epic）

Epic は設計の背骨です。
この workflow は、Epic 固有の再利用判定、作成、Issue 分割、品質ゲートを正本として扱います。
この workflow の品質ゲートは scope 固有の additive gate であり、`phase_*.md` の shared minimum gate 通過を前提とします。

対応 leaf skill:
- `.agents/skills/spec-dock-epic-planning/SKILL.md`
- `.agents/skills/spec-dock-epic-execution/SKILL.md`

関連:
- 総合: [guide.md](guide.md)
- 仕様書作成: [workflow_spec_authoring.md](workflow_spec_authoring.md)
- Initiative: [workflow_initiative.md](workflow_initiative.md)
- Issue: [workflow_issue.md](workflow_issue.md)
- GitHub 連携: [reference_github.md](reference_github.md)
- 共通 phase playbook: [phase_requirement.md](phase_requirement.md), [phase_design.md](phase_design.md), [phase_plan.md](phase_plan.md)
- Epic plan playbook: [phase_plan_epic.md](phase_plan_epic.md)
- Decision routing: [authoring/decision-routing.md](authoring/decision-routing.md)
- Scope layering: [authoring/scope-layering.md](authoring/scope-layering.md)
- ChatGPT authoring evidence lane: [workflow_chatgpt_authoring_pack.md](workflow_chatgpt_authoring_pack.md)
- Prompt pack / ZIP reference: [authoring/chatgpt-pack.md](authoring/chatgpt-pack.md)

## 再利用判定

- まず親 initiative 配下の既存 epic の `requirement.md` / `design.md` / `plan.md` / `discussions/` を確認する
- 契約、移行、観測性、Done 定義が既存 epic に収まるなら、新規作成せず既存 epic を更新する
- 設計の背骨や rollout 順が崩れる場合だけ `new` / `import` を使う
- 新規作成した理由や既存 epic に収めない理由は、作成後の対象 epic 配下の最初の `disc` に残す

## 作成

```bash
./spec-dock/scripts/spec-dock new epic --initiative <initiative-id> --title "..."
./spec-dock/scripts/spec-dock new epic --initiative <initiative-id> --github-issue <n> --title "..."
./spec-dock/scripts/spec-dock new epic --initiative <initiative-id> --create-github-issue --title "..."

./spec-dock/scripts/spec-dock import epic <num|#num|url> --title "..." [--initiative <initiative-id>]
```

- `import epic` で `--initiative` を省略した場合は current active から親 initiative を解決する
- naming 制約と GitHub 振る舞いは [reference_naming.md](reference_naming.md), [reference_github.md](reference_github.md) を参照する
- Epic 配下の Issue 作成は runtime command `./spec-dock/scripts/spec-dock new issue --epic <epic-id> --title "..."` を使う。生成される `issues/rules.md` は `spec-dock/docs/rules/epic/issues.md` への入口で、作成ルールの正本は後者にある。GitHub linkage は [reference_github.md](reference_github.md) を参照する
- Issue 間依存の追加/削除/確認は `./spec-dock/scripts/spec-dock deps add/remove/check` を使い、反映は `./spec-dock/scripts/spec-dock validate` と `./spec-dock/scripts/spec-dock sync` で確認する

## 記述

- `requirement.md`: 期待する価値、受け入れ条件、非機能、スコープ
- `design.md`: 契約、移行、観測性、リスク
- `plan.md`: Issue 分割、依存順、品質ゲート。shared axiom は `phase_plan.md`、Epic 固有の書き方は `phase_plan_epic.md`
- Epic は複数 Issue の設計の背骨を所有する。Issue 分割、責務境界、依存方向、shared component / workflow policy、rollout 順に影響する durable decision は Epic requirement / design / plan に反映してから Issue へ落とす。Epic をまたいで product / operating model / 投資判断へ広がる場合は Initiative へ戻し、長期 architecture decision として独立に記録すべき場合は ADR 候補にする。責務境界と authority flow の共通参照は [authoring/scope-layering.md](authoring/scope-layering.md)、routing 例は [authoring/decision-routing.md](authoring/decision-routing.md) を参照する
- ChatGPT / Oracle は非自明な Epic planning の ChatGPT-first primary route として、Epic requirement / design / plan と Issue draft requirement / draft design / draft plan の evidence producer に使う。Issue candidate / draft は正本ではなく、Issue node 作成前に人間の承認を通す。作成後の draft adoption は Issue planning が正式 docs へ採用し、fresh `spec-reviewer` pass を通す
- `spec-dock-epic-planning-manual` は human-approved emergency backup であり、hard / unrecoverable ChatGPT route failure と recovery attempts、explicit approval、fresh reviewer gate の evidence がある場合だけ使う
- Requirement / design / plan の phase promotion は `workflow_spec_authoring.md` を正本にし、各 artifact ごとに fresh `spec-reviewer` の `review_status: pass` まで次 phase へ進めない
- `artifacts/`: `new artifact <type> --epic <epic-id> --title "..."` で、この epic の `artifacts/` 配下に timestamp-prefixed original を作成する。current catalog は `blank` / `adr` / `disc` / `research` / `interview` / `decision-candidate` / `pr-repair-batch`。`draft-requirement` / `draft-design` / `draft-plan` は Issue-only artifact として扱う。runtime が filename / path を生成し、caller は stdout の `path=...` を正本として扱う。標準形は `<ts>-<kind>-<slug>.md`、same-second collision fallback は `<ts>-<nn>-<kind>-<slug>.md`。既存 `discussions/` 配下の artifact は legacy/grandfathered として保持する。詳細 contract は [reference_naming.md](reference_naming.md) を参照する
- `note` は新規作成 catalog から retired。既存 `note` artifact は grandfathered として壊さない。
- shared な書き方は `phase_*.md`、lifecycle / governance と Epic 固有の分割判断はこの workflow を正本とする

## 計画完了 / 引き継ぎ（Planning Completion / Handoff）

Epic planning completion は、Epic の `requirement.md` / `design.md` / `plan.md` が必要な phase promotion gate と fresh `spec-reviewer` の `review_status: pass` を通過し、downstream Issue が参照できる handoff package が揃った状態です。委任 draft の採用、Evidence Adoption Ledger、diff guard、fresh reviewer gate の詳細は [workflow_spec_authoring.md](workflow_spec_authoring.md) を正本とし、この節では Epic 固有の handoff 境界だけを定義します。

Handoff package は少なくとも次を含みます。

- reviewer-gated Epic requirement / design / plan
- Issue list, responsibility boundary, dependency order, and known non-blocking deferrals
- dependency mutation の command evidence は `./spec-dock/scripts/spec-dock deps add --from <dependent-node-id> --to <prerequisite-node-id>`、`./spec-dock/scripts/spec-dock deps remove --from <dependent-node-id> --to <prerequisite-node-id>`、`./spec-dock/scripts/spec-dock deps check <target>` を使う。`--from` は `.meta.json.depends_on` を更新する node、`--to` はその prerequisite を指す。metadata を直接編集しない
- cross-issue draft package covering shared vocabulary, responsibility boundaries, dependency order, handoff inputs / outputs, and validation strategy across the planned Issues
- Issue-local draft requirement path and Issue-local `draft-design` / `draft-plan` path index for each target Issue after Issue creation, or explicit skip / fallback evidence

Cross-issue draft package は planning evidence であり、Issue の canonical `requirement.md` / `design.md` / `plan.md` ではありません。個別 Issue の draft requirement / `draft-design` / `draft-plan` は、runtime-owned artifact creation command で作成します。

```bash
./spec-dock/scripts/spec-dock new artifact draft-requirement --issue <issue-id> --title "..."
./spec-dock/scripts/spec-dock new artifact draft-design --issue <issue-id> --title "..."
./spec-dock/scripts/spec-dock new artifact draft-plan --issue <issue-id> --title "..."
```

各 command が返す `path=...` が artifact path です。Epic handoff package には、target Issue id ごとにこれらの path index を置きます。これらの Issue-local drafts は artifact evidence / planning input として扱い、ad hoc file writes や canonical issue docs への直接書き込みで代替してはいけません。Canonical Issue `design.md` / `plan.md` は pre-start で本文化せず、個別 Issue planning workflow、assurance compose、[workflow_issue.md](workflow_issue.md) の authoring contract で正式化します。`assurance compose` は canonical compose 専用であり、draft artifact 作成 command ではありません。actor / specialist / depth 別の draft command は作らず、grade 別 obligation は handoff evidence、Issue planning、reviewer gate で扱います。

Target Issue が draft-requirement、`draft-design`、`draft-plan` の一部または全部を意図的に受け取らない場合、Epic report / handoff evidence は target Issue id、skipped draft type(s)、理由、その omission が Issue planning handoff を block しない理由、必要に応じた revisit / follow-up condition を記録します。

Option 3+ は正式な Epic planning baseline です。Epic planning では Issue slices、dependency order、Issue-local draft path index までをまとめて作成し、canonical Issue docs は各 Issue start 前後の Issue planning で current repository state と prior completed Issues を踏まえて正式化します。全 Issue を先に canonical execution-ready 化しないことで drift を抑え、draft だけでは拾いにくい Issue 間不整合は Epic execution 中の integration checkpoint と final quality Issue で検出します。

```plantuml
@startuml
title Issue Draft To Canonical Planning And Execution
skinparam monochrome true
participant "Epic Planning" as EpicPlanning
participant "Issue Draft Artifacts" as Drafts
participant "Issue Planning" as IssuePlanning
participant "Issue Execution" as IssueExecution
participant "Epic Planning Repair" as Repair

EpicPlanning -> Drafts : create draft requirement/design/plan
Drafts -> IssuePlanning : handoff-ready evidence
IssuePlanning -> IssuePlanning : refresh current repo and prior Issues
IssuePlanning -> IssuePlanning : adopt / reject draft claims
IssuePlanning -> IssueExecution : execution-ready after reviewer pass
IssueExecution -> IssuePlanning : next Issue starts just-in-time planning
IssuePlanning -> Repair : scope drift changes Epic boundary
Repair -> EpicPlanning : revise slices / dependency order
@enduml
```

Downstream Issue は、Epic planning outputs とこの completion / handoff contract を input として参照できます。各 downstream Issue は、Epic plan が dependency edge を明示しない限り独立した Issue として扱います。Epic execution coordinator は downstream Issue handoff package を読み、`handoff-ready` と `execution-ready` を分けます。`handoff-ready` は Issue planning へ渡せる状態であり、canonical Issue `design.md` / `plan.md` が compose 前でもよいが実装開始は許可しません。`execution-ready` は Issue planning が evidence 採否、canonical compose、fresh `spec-reviewer` pass、実行可能 plan、required verification、delegation contract、reviewer focus を揃えた状態です。Epic execution coordinator behavior、issue start / finish cycle、PR merge-ready preparation は、later Issue が明示的に定義しない限り、この Epic planning handoff section の外側に置きます。

## 実行ライフサイクル（Epic Execution Lifecycle）

Epic planning completion 後の実行調整は `spec-dock-epic-execution` を first-read coordinator とします。この coordinator は reviewer-gated Epic `requirement.md` / `design.md` / `plan.md`、evidence ledger としての Epic `report.md`、downstream Issue handoff package を読んでから、ready Issue を一つずつ選び、Issue planning / execution へ渡します。Issue の詳細な実行規約と `issue finish` 判断は [workflow_issue.md](workflow_issue.md) を正本とし、この workflow では重複定義しません。

Epic execution の readiness inspection は structural gate であり、semantic reviewer ではありません。次は structural blocker として fail-closed で止めます: missing canonical docs、missing / stale reviewer pass、missing Issue readiness contract、missing executable plan structure、missing delegation contract、missing verification、missing reviewer focus、unresolved blocking / stale report entries、raw artifact authority、decision-only execution-ready、grade が要求する specialist / fallback evidence の欠落。構造はあるが acceptance criteria、test strategy、採用理由、設計妥当性、日本語ファースト wording の十分性が疑わしい場合は reviewer finding として記録し、`spec-reviewer` や Issue planning に route します。

Issue 実装後の PR delivery は通常 `github-pr-merge-preparer` へ handoff します。ただし reviewed Epic plan が、Issue を一つずつ進め、final PR delivery を `iss-00276` や `iss-00307` のような final quality Issue に意図的に集約すると定義している場合は、中間 Issue の `report.md` に deferred PR delivery gate evidence を残します。この evidence は、defer 先 final quality Issue id、defer 先 dependency edge、per-Issue PR を作らない理由、final PR delivery まで merge-prepared を主張しないこと、reviewer が確認した local completion / issue finish 条件を含みます。中間 Issue ごとの PR preparation は要求しませんが、[workflow_issue.md](workflow_issue.md) の `issue finish` 条件を迂回してはなりません。この例外は通常 workflow の PR-preparer guidance を削除するものではありません。

日本語運用では、Epic execution / readiness 中に作成・更新する docs、`report.md`、artifacts の本文は日本語ファーストにします。commands、paths、IDs、role 名などの正確な識別子はそのまま保持します。

Epic completion gate は、required Issues が完了済みまたは fresh spec-reviewed plan により明示的に不要化され、Epic-level evidence、品質ゲート、PR handoff expectation が揃った状態です。multi-Issue implementation Epic は final quality / PR delivery Issue を持ち、その Issue はすべての implementation Issues に依存します。single-Issue / docs-only / no-op Epic で final quality Issue を省略する場合は、skipped-work rationale と completion evidence を Epic `report.md` に残します。それ以外の省略例外は Issue 作成前に別途 accepted decision を必要とします。

## 品質ゲート

- requirement:
  - Done 条件が観測可能
  - スコープと非スコープが明確
  - 新規 epic が必要な理由を最初の `disc` で追える
- design:
  - 契約が明記されている
  - 移行 / 互換 / ロールバックが整理されている
  - 観測性の方針がある
- plan:
  - Issue へ分割できている
  - 依存順が現実的
- authoring:
  - requirement / design / plan の各 promotion gate が `Spec Authoring Gate` として `report.md` に記録されている
  - scope / acceptance criteria / Issue 分割に影響する未確認事項が残っていない
  - plan gate pass 後に Issue 分割へ進む
- epic-wide pre-PR:
  - Epic の全 Issue 実装が完了し、Epic PR を更新する前に、開発ベースラインから最終実装状態までの全差分を対象に品質ゲートを置く
  - `gh pr view <pr> --json baseRefName,baseRefOid,headRefName,headRefOid` で base endpoint を記録し、local `HEAD` を final endpoint として固定する
  - `git diff --stat <baseRefOid>...HEAD` と `git diff --name-status <baseRefOid>...HEAD` を `report.md` または `artifacts/` の共有証跡に残す
  - fresh `deep-consultant` と fresh `spec-reviewer` が同じ共有証跡と endpoint を参照して Epic 全体をレビューする
  - すべての指摘は `fixed` / `superseded` / `explicitly_deferred_with_user_acceptance` のいずれかに disposition されるまで PR update / push を行わない
  - `fixed` または `superseded` の指摘は再検証と fresh re-review を通してから PR update / push に進む

## 仕上げ

```bash
./spec-dock/scripts/spec-dock validate
./spec-dock/scripts/spec-dock sync
```
