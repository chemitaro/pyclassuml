# phase playbook: plan (epic)

Epic plan の playbook です。
shared axiom は [phase_plan.md](phase_plan.md)、Epic の lifecycle / governance は [workflow_epic.md](workflow_epic.md) を参照します。

## scope contract

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

## entry focus

- E-RQ / E-AC が requirement で固定されている
- 契約 / 移行 / 観測性 / rollback が design にある
- integration risk が見えている

## authoring checklist

- `この計画で閉じる E-RQ / E-AC` を先に置く
- `Issue 分割方針` を置く
- `Issue 一覧（順序 / tranche 付き）` を置く
- `統合チェックポイント` を置く
- `品質ゲート` に observability / migration / docs を置く
- `ロールアウト / docs impact` を置く
- `Issue readiness contract` を置く
- `final exit contract` を置く

## diagram / trace guidance

- 必要な場合だけ Issue dependency graph、tranche / rollout map、Closure matrix を置く
- 図表は E-RQ / E-AC、design decision、Issue、verification の対応を確認する用途に限定する
- Issue 内 step、TDD cadence、commit rhythm は図表化しない

## review gate

- issue 群で E-AC を閉じられる説明がある
- integration checkpoint がある
- rollout / docs impact が露出している
- issue handoff に必要な readiness がある
