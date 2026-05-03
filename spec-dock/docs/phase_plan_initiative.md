# phase playbook: plan (initiative)

Initiative plan の playbook です。
shared axiom は [phase_plan.md](phase_plan.md)、Initiative の lifecycle / governance は [workflow_initiative.md](workflow_initiative.md) を参照します。

## scope contract

- plan の単位: roadmap / milestone / epic portfolio
- plan の責務: initiative requirement / design を、epic 分解、順序、意思決定ゲート、指標レビューへ変換する
- plan が固定するもの:
  - milestone
  - epic portfolio
  - sequencing rationale
  - investment / strategy gate
  - scope-specific readiness contract
  - final exit contract
- plan が固定しないもの:
  - issue 単位の実装順
  - test command
  - per-step review cadence

## entry focus

- 目的と成功指標が requirement で固定されている
- target architecture / guardrails が design で整理されている
- epic 分解前提と外部依存が見えている

## authoring checklist

- `この計画が達成する Goal / Metric` を先に埋める
- `マイルストーン` を exit 付きで置く
- `Epic ポートフォリオ` に目的 / deliverable / metric link / depends on を入れる
- `順序と理由` で並行可能性と停止点を書く
- `意思決定ゲート` で strategy / milestone / governance review を固定する
- `指標レビュー計画` を置く
- `Epic readiness contract` を置く
- `final exit contract` を置く

## diagram / trace guidance

- 必要な場合だけ roadmap、Epic dependency map、Metric / Epic / evidence の対応表を置く
- 図表は `Epic ポートフォリオ`、`順序と理由`、`意思決定ゲート` の理解を助ける用途に限定する
- 個別 Issue の作業手順、test command、file-level dependency は図表化しない

## review gate

- Epic へ handoff できる粒度まで分解されている
- 指標レビューの timing がある
- 投資判断 / milestone 継続判断の gate がある
- governance / rollout 更新の必要性が露出している
