# エピックレポート（Epic report / placeholder / Activeなし）

現在アクティブな Epic はありません。

- ここは placeholder です（編集対象外）
- 正しい場所: `spec-dock/initiatives/**/epics/**/report.md`

## 委任ドラフト証跡 schema（Delegated Draft Evidence Schema / reference）
- lifecycle state（契約値）: `requested`, `produced`, `integrated`, `partially_integrated`, `rejected`, `superseded`, `blocked`, `stale`
- 昇格不可 state: `stale`, `rejected`, `superseded`, `blocked`
- 標準出力先: target scope `artifacts/` direct child の flat Markdown。typed artifact filename は `<ts>-<type>-<slug>.md` または same-second collision 用 `<ts>-<nn>-<type>-<slug>.md`。blank artifact filename は `<ts>-<slug>.md` または same-second collision 用 `<ts>-<nn>-<slug>.md`
- 軽量 provenance field: `created_by_role`, `scope_id`, `source_paths`, `intended_targets`, `adoption_status: unreviewed`, `reflected_to: []`, `diff_guard_result`, fallback decision, report evidence destination, adoption ledger note
- 互換 label: role, phase, scope, authorization source, source artifacts, draft artifact path, status, integration result, rejected portions, blockers, reviewer result, promotion decision
- 禁止 self-claim: `authority: accepted`, `adoption_status: adopted`, non-empty `reflected_to`, reviewer pass, phase completion, implementation readiness
- 標準必須にしない field: task manifest hash, Permission Profile hash, session invocation hash, probe run id, session hash
- 禁止 wildcard token: `*`, `grants.*`, `all`
- historical note: legacy `discussions/` と既存 `iss-00126` などの manifest/Profile/probe/session artifacts は grandfathered evidence として残し、削除・rename・validation failure 化しない
- Evidence Adoption Ledger fields: ID, adoption_status, source, source_role, claim, target_artifact, target_section, rationale, evidence_strength, evidence_path, adopter, reviewer, blocking, next_action.
- Promotion Record / `promotion_record` fields: `status`, `authority`, `owner_role`, `draft_author_role`, `approval`, `source_revision`, `approved_revision`, `approved_hash`, `reviewer_target_hash`, `promoted_at`, `promoted_by`, `promotion_decision`
- `reviewer_target_hash` / `approved_hash` の不一致、または stale な `source_revision` / `approved_revision` は promotion と下流 authority をブロックする。
- failure-mode field: expected verdict, allowed next action, report evidence path, promotion eligibility

| 失敗モード | 期待される判定 | 許可される次アクション | report 証跡の記録先 | 昇格可否 |
|---|---|---|---|---|
| ワークフロー単位の許可証跡不足（missing workflow-scoped authorization evidence） | blocked / incomplete | ワークフロー利用依頼の authorization source と boundary を記録する、または手動 authoring に戻す | ワークフロー単位の named role 許可（Workflow-Scoped Authorization） / この section | ineligible |
| 前段 reviewer pass 不足 / stale（missing/stale previous reviewer pass） | blocked / incomplete | reviewer gate を再実行する | Spec Authoring Gate / reviewer evidence | ineligible |
| 設計中の要件 gap（requirement gap during design） | blocked / incomplete | requirement phase へ戻す | decision ledger / gate evidence | ineligible |
| 計画中の設計 gap（design gap during plan） | blocked / incomplete | design phase へ戻す | decision ledger / gate evidence | ineligible |
| ロール利用不可（role unavailable） | blocked / manual path | 利用不可を記録し、妥当なら手動で続行する | Delegated Draft Evidence | ineligible |
| 禁止行為の試行（forbidden action attempt） | rejected | ドラフトを破棄し incident を記録する | Delegated Draft Evidence / decision ledger | ineligible |
| 古いドラフト（stale draft） | stale | 再生成または差分調整する | Delegated Draft Evidence | ineligible |
| 置換済みドラフト（superseded draft） | superseded | 置換先ドラフトを参照する | Delegated Draft Evidence | ineligible |
| 委任使用主張に対する証跡不足（missing draft evidence when delegated use is claimed） | incomplete | 証跡を追加する、または委任使用 claim を外す | Delegated Draft Evidence | ineligible |
| reviewer 利用不可 / 拒否 / waiver / provisional（reviewer unavailable/denied/waived/provisional） | blocked / incomplete | fresh な passed reviewer を取得する、または昇格なしの risk acceptance を記録する | reviewer gate evidence | ineligible |
