---
種別: 実装報告書（Issue）
ID: "iss-00021"
タイトル: "App Diff Wiring"
関連GitHub: ["#21"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00005", "init-00001"]
---

# iss-00021 App Diff Wiring — 実装報告（LOG）

## 実装サマリー
- 実装前 contract repair として、issue requirement/design/plan を `ReportRunResult` app seam 境界へ更新した。
- `CommandResult` direct-output 前提とテンプレ plan を削除し、diff-specific front-stage、common pipeline、report-owned result material の責務分離を明文化した。

## 実装記録（セッションログ）

### 2026-05-04 contract repair

#### 対象
- Step: M1 / SG1
- AC/EC: AC-001, AC-002, AC-003, AC-004, EC-001, EC-002, EC-003

#### 実施内容
- active issue が `iss-00021 App Diff Wiring` であることを確認した。
- requirement/design の stale な `CommandResult` direct-output 契約を `ReportRunResult` 境界へ修正した。
- plan のテンプレートを、public seam、front-stage failure、canonical happy path、warning/counter/failure preservation の実行契約へ置き換えた。
- report を実作業ログ形式へ初期化した。
- spec review fail を受け、`ReportRunResult` の top-level shape と `ChangedClassInventory` へ渡す project-root-relative path 契約を修正した。

#### 実行コマンド / 結果
```bash
git status --short

# no output

./spec-dock/scripts/spec-dock active show

initiative: init-00001 (spec-dock/initiatives/init-00001-pyclassuml-prototype)
epic: epic-00005 (spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00005-e2e-command-wiring)
issue: iss-00021 (spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00005-e2e-command-wiring/issues/iss-00021-app-diff-wiring)
```

#### 変更したファイル
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00005-e2e-command-wiring/issues/iss-00021-app-diff-wiring/requirement.md` - `ReportRunResult` 境界と AC/EC を具体化。
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00005-e2e-command-wiring/issues/iss-00021-app-diff-wiring/design.md` - diff app seam の flow / handoff / failure 設計を具体化。
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00005-e2e-command-wiring/issues/iss-00021-app-diff-wiring/plan.md` - 実装可能な execution contract へ置換。
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00005-e2e-command-wiring/issues/iss-00021-app-diff-wiring/report.md` - 作業ログを初期化。

#### コミット
- 未実施。SG1 pass 後に docs commit を作成する。

#### メモ
- `generate` wiring と同様に、`cli.run_cli` の handler 接続や実プロセス stream emission は本 issue の非スコープにした。

## 遭遇した問題と解決
- 問題: 既存 docs が `CommandResult` direct-output とテンプレ plan のままで、`iss-00019` / `iss-00020` の `ReportRunResult` 境界と衝突していた。
  - 解決: issue docs を current report seam contract に合わせて修復し、実装前 review gate を置いた。

## 学んだこと
- diff wiring は generate wiring より front-stage failure が多いため、config / VCS / target failure を common pipeline の手前で `write_report` に渡す契約を明示する必要がある。

## 今後の推奨事項
- 実装では `run_generate` と過度に divergent な後段 pipeline を作らない。必要なら小さな内部 helper 化を検討するが、issue scope を超える大規模 refactor は避ける。

## 省略/例外メモ
- 該当なし。
