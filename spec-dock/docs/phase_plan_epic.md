# エピック計画フェーズ playbook（phase playbook: plan / epic）

Epic plan の playbook です。
shared axiom は [phase_plan.md](phase_plan.md)、Epic の lifecycle / governance は [workflow_epic.md](workflow_epic.md) を参照します。

## 範囲契約（scope contract）

- plan の単位: issue tranche / integration checkpoint / rollout tranche
- plan の責務: epic requirement / design を、issue 分割、統合順、ロールアウト準備、issue handoff へ変換する
- plan が固定するもの:
  - issue slicing strategy
  - issue order / tranche
  - integration checkpoint
  - rollout / docs impact gate
  - scope-specific readiness contract
  - final exit contract
- plan が固定しないもの:
  - issue 内 step の切り方
  - TDD cadence
  - commit rhythm

## 入場 focus（entry focus）

- E-RQ / E-AC が requirement で固定されている
- 契約 / 移行 / 観測性 / rollback が design にある
- integration risk が見えている

## 作成 checklist 項目（authoring checklist）

- `この計画で閉じる E-RQ / E-AC` を先に置く
- `Issue 分割方針` を置く
- `Issue 一覧（順序 / tranche 付き）` を置く
- `統合チェックポイント` を置く
- `品質ゲート` に observability / migration / docs を置く
- `ロールアウト / docs impact` を置く
- `Issue readiness contract` を置く
- `final exit contract` を置く

## 図表 / trace 指針（diagram / trace guidance）

- 必要な場合だけ Issue dependency graph、tranche / rollout map、Closure matrix を置く
- 図表は E-RQ / E-AC、design decision、Issue、verification の対応を確認する用途に限定する
- Issue 内 step、TDD cadence、commit rhythm は図表化しない

## レビューゲート（review gate）

- issue 群で E-AC を閉じられる説明がある
- integration checkpoint がある
- rollout / docs impact が露出している
- issue handoff に必要な readiness がある
- delegated plan draft を使う場合、lightweight provenance、fresh requirement/design reviewer pass、approved artifacts への traceability、stale / superseded handling、scope discipline、phase gate preservation が確認できる
- delegated draft を fresh `spec-reviewer` pass の代替にしていない
- read-only specialist consent と scope-local discussion direct-write consent が分離され、direct-write delegated authoring は target scope `discussions/` direct child、allowed filename rule、forbidden canonical/implementation paths、post-run diff guard、report evidence destination を step-local に固定している
- implementation planner が direct-write draft authoring を使う場合でも、出力は scope-local flat discussion Markdown に限られ、canonical `plan.md` edit、final authority、phase promotion、reviewer-pass claim、requirement/design rewrite、implementation-readiness claim、完了済み issue plan/report の修正を含まない
- static adapter は guarded workspace-write で scope-local `discussions/` Markdown draft を作成し、workspace-write が hard path allow-list ではない前提で delegated plan authoring output は invocation scope、diff guard pass、report ledger adoption evidence が揃うまで adoption-ineligible として扱われている
- delegated authoring unavailable / skipped の場合も manual authoring path が有効である
