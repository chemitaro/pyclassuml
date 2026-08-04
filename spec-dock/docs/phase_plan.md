# 計画フェーズ playbook（phase playbook: plan）

Initiative / Epic / Issue に共通する plan の shared axiom です。
scope 固有の plan authoring rule は `phase_plan_<scope>.md` を参照してください。
workflow は `workflow_initiative.md` / `workflow_epic.md` が lifecycle / governance、`workflow_issue.md` が lifecycle / governance / execution policy の正本です。

関連:
- 全体像: [guide.md](guide.md)
- Scope workflow: [workflow_initiative.md](workflow_initiative.md), [workflow_epic.md](workflow_epic.md), [workflow_issue.md](workflow_issue.md)
- Spec authoring workflow: [workflow_spec_authoring.md](workflow_spec_authoring.md)
- Scope plan playbook: [phase_plan_initiative.md](phase_plan_initiative.md), [phase_plan_epic.md](phase_plan_epic.md), [phase_plan_issue.md](phase_plan_issue.md)
- Scope layering: [authoring/scope-layering.md](authoring/scope-layering.md)

## フェーズ契約（phase contract）

- 位置: `調査分析 → requirement → design → plan → 実装/品質ゲート` の `plan`
- 責務: 確定した requirement / design を、実行可能な分解・順序・停止点・品質ゲートへ変換する
- 前提入力: reviewer 承認レベルの `requirement.md` / `design.md`、依存、ブロッカー、対象 scope の workflow / phase plan
- 固定すること:
  - target
  - decomposition
  - sequence
  - gate
  - dependency
  - exit
- 出力: reviewer が handoff できる `plan.md` と必要な `disc` / `research` / `adr`
- 非ゴール: requirement / design の再議論、設計不足の隠蔽、将来作業の過剰先読み

## 範囲所有（scope ownership）

- Initiative plan:
  - 所有する判断:
    - Epic portfolio、roadmap、dependency、milestone、Initiative-level gate、metric review
  - 所有しない判断:
    - 個別 Issue の TODO、code-level 作業手順、未承認の requirement / design
- Epic plan:
  - 所有する判断:
    - Issue slicing、Issue dependency、integration checkpoint、Epic-level quality gate、E-RQ / E-AC closure
  - 所有しない判断:
    - Issue plan の詳細手順、Initiative roadmap の再記述
- Issue plan:
  - 所有する判断:
    - 実装 step、変更対象、test / review gate、rollback / compatibility、docs impact、final diff gate
  - 所有しない判断:
    - 未承認の requirement / design、上位目的の再説明、未解決設計論点の先送り
- trace rule:
  - 各 plan item は requirement item または design decision に紐づける
  - trace できない step / issue / epic は scope creep として削るか、前 phase に戻す
  - scope ownership や handoff authority が曖昧な場合は [authoring/scope-layering.md](authoring/scope-layering.md) と対象 `workflow_*.md` を authoritative routing として確認する

## 共有 terminology（shared terminology）

- `shared minimum gate`: 全 scope に共通して満たす最小 gate
- `scope-specific readiness contract`: 次の実行単位へ handoff するために対象 scope が追加で満たす条件
- `final exit contract`: この plan が閉じたと判断する最終条件

## 共有 entry checklist（shared entry checklist）

- `requirement.md` と `design.md` が reviewer 承認レベルにある
- `requirement.md` と `design.md` が `workflow_spec_authoring.md` の promotion gate を pass している
- この plan が扱う単位を明確にした
- 依存、ブロッカー、外部制約を露出した
- 分割案や順序案の比較が必要なら `disc` に逃がすと決めた
- 対象 scope の `phase_plan_<scope>.md` と `workflow_<scope>.md` を確認した

## 委任 plan authoring ゲート（delegated plan authoring gate）

Delegated plan authoring は、対象 scope の `artifacts/` 直下へ flat Markdown draft / analysis / artifact-local report を直接保存できる支援です。proposal-only ではありませんが、canonical `requirement.md` / `design.md` / `plan.md` / `report.md` は main orchestrator の single-writer authority であり、sub-agent は直接編集しません。Delegated draft は evidence であり、fresh `spec-reviewer` pass の代替ではありません。

Delegated plan draft を使う場合、orchestrator は draft 生成前に次を確認します。

- fresh requirement reviewer pass と fresh design reviewer pass があり、pass 対象 revision を特定できる
- design dependency analysis、file/module change plan、verification strategy、rollback / compatibility が plan 入力として確認できる
- invocation contract が scope、source artifacts、allowed actions、forbidden actions、boundary、invalidation conditions を含む
- read-only specialist consent と scope-local artifact direct-write consent は分離されている
- allowed actions は、対象 scope の `artifacts/` direct child にある naming-rule compliant Markdown 1 ファイルの新規作成に限定される。既存 proposed artifact draft の更新は static adapter contract の対象外であり、将来必要な場合は別 workflow / follow-up で narrower allowlist と追加 gate を定義する
- new artifact draft は runtime-owned `new artifact <type>` で作成し、返された `path=...` を正本として本文を更新する。post-run diff guard は generated filename が artifact rules（typed artifact 標準 `<ts>-<kind>-<slug>.md`、same-second collision fallback `<ts>-<nn>-<kind>-<slug>.md`、blank artifact `<ts>-<slug>.md` / `<ts>-<nn>-<slug>.md`）に一致することを確認する
- forbidden actions は canonical `requirement.md` / `design.md` / `plan.md` / `report.md`、implementation、tests、package/config、`.agents`、`.codex`、`.github`、`.env*`、GitHub mutation、phase promotion、reviewer-pass claim、implementation-readiness claim、user への直接質問を含む
- forbidden locations は per-agent directory、run/task directory、global draft store、`discussions/delegated-authoring/`、`artifacts/delegated-authoring/` を含む
- required plan draft output contract が、計画要約（Plan Summary）、要件 / 設計 traceability（Requirement / Design Traceability）、milestone（Milestones）、依存関係から導く実行順序（Dependency-Derived Execution Order）、Issue / step 分割（Issue / Step Slicing）、テスト戦略 mapping（Test Strategy Mapping）、review gate（Review Gates）、rollback / compatibility（Rollback / Compatibility）、docs impact（Docs Impact）、最終品質ゲート（Final Quality Gate）、plan blocker（Plan Blockers）、integration notes（Integration Notes）を含む
- static adapter は guarded workspace-write で scope-local `artifacts/` Markdown draft を作成する。workspace-write は hard path allow-list ではなく canonical target write の許可でもない。run ごとの permission context 生成に依存せず、run は post-run diff guard pass と `report.md` ledger 記録まで adoption-ineligible とする

Sub-agent-created draft は lightweight provenance として `created_by_role`、`scope_id`、`source_paths`、`intended_targets`、`adoption_status: unreviewed`、`reflected_to: []`、`diff_guard_result`、adoption ledger note を持ちます。標準 delegated draft evidence として task manifest hash、Permission Profile hash、session invocation hash、probe run id を要求しません。これらは historical evidence または明示された例外証跡としてだけ扱います。

Delegated plan draft を統合する場合、main orchestrator が canonical `report.md` の Evidence Adoption Ledger に採否を残し、採用部分だけ canonical `plan.md` へ再記述します。Accepted ADR は architecture decision authority を持ち得ますが、artifact draft は evidence であり、implementation / phase authority は canonical docs への反映後に成立します。既存 `discussions/` と `iss-00126` delegated-authoring manifest/Profile/probe/session artifacts は grandfathered historical evidence として残し、削除・rename・validation failure 化しません。

Reviewer は delegated draft を含む plan を review するとき、次を fail / incomplete 条件として扱います。

- delegated draft provenance が不明
- draft が `authority: accepted`、`adoption_status: adopted`、non-empty `reflected_to` を自己主張している
- draft が stale / superseded / rejected / blocked のまま promotion evidence に使われている
- approved requirement / design への traceability がない
- delegated content が scope creep または parent non-scope の破り込みを含む
- post-run diff guard が failed / not run のまま採用されている
- phase gate bypass、reviewer gate bypass、または delegated draft を reviewer pass とみなす記述がある
- delegated authoring unavailable / skipped のときに manual authoring path が閉じられている

## 共有 review / handoff gate（shared review / handoff gate）

- 順序の理由が説明できる
- 粒度が対象 scope に対して妥当である
- 依存とブロッカーが plan に露出している
- gate と exit が plan に反映されている
- `plan.md` と必要な `disc` / `research` / `adr` を束で渡せる
- fresh `spec-reviewer` が plan を requirement / design と照合し、`review_status: pass` を返している
- reviewer が「この計画で次へ進める」と判断できる
- `report.md` の `Spec Authoring Gate` に調査、ヒアリング、review、修正、promotion evidence が残っている

## 図表指針（diagram guidance）

- Initiative:
  - 推奨:
    - roadmap
    - Epic dependency map
    - Metric / I-AC / Epic / evidence の traceability matrix
- Epic:
  - 推奨:
    - Issue dependency graph
    - tranche / rollout map
    - E-RQ / E-AC / design decision / Issue / verification の traceability matrix
- Issue:
  - 推奨:
    - step dependency graph
    - 仕様固定クロージャ索引（Spec-Locked Closure Index。AC / EC / constraint / step-local closure contract の索引）
    - rollback map
- review:
  - 図表の依存関係が本文の順序・depends on・gate と一致している
  - 図表だけにしか存在しない作業や gate がない

## 退避手順（escape hatch）

- 分割案 / 順序案 / gate 案の比較は `disc`
- 外部制約や運用条件は `research`
- 恒久化すべき運用方針は `adr`
