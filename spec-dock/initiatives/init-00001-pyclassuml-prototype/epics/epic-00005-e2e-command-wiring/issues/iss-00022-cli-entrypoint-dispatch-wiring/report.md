---
種別: 実装報告書（Issue）
ID: "iss-00022"
タイトル: "CLI Entrypoint Dispatch Wiring"
関連GitHub: ["#22"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00005", "init-00001"]
---

# iss-00022 CLI Entrypoint Dispatch Wiring — 実装報告（LOG）

## 実装サマリー
- completion audit で見つかった外部 CLI gap を閉じるため、console script / dispatch / process stream projection / `include_untracked` default を実装対象として契約化した。

## 実装記録（セッションログ）

### 2026-05-04 contract repair

#### 対象
- Step: M1 / SG1
- AC/EC: AC-001, AC-002, AC-003, AC-004, EC-001, EC-002

#### 実施内容
- completion audit で `uv run pyclassuml --help` が `No such file or directory` になることを確認した。
- `pyproject.toml` に console script がないこと、`cli.run_cli` が `ReportRunResult` app seam を process streams へ接続していないことを確認した。
- initiative requirement の `diff.include_untracked` default `true` と現行 CLI/config default `false` の不整合を確認した。
- spec-reviewer fail を受け、`iss-00022` が `iss-00006` / `iss-00008` の古い default `false` 契約を supersede し、upstream issue docs を同期する方針を追記した。
- issue requirement/design/plan/report をテンプレートから実装可能な契約へ置き換えた。

#### 実行コマンド / 結果
```bash
uv run pyclassuml --help

error: Failed to spawn: `pyclassuml`
  Caused by: No such file or directory (os error 2)

./spec-dock/scripts/spec-dock active show

initiative: init-00001 (...)
epic: epic-00005 (...)
issue: iss-00022 (...)
```

#### 変更したファイル
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00005-e2e-command-wiring/issues/iss-00022-cli-entrypoint-dispatch-wiring/requirement.md`
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00005-e2e-command-wiring/issues/iss-00022-cli-entrypoint-dispatch-wiring/design.md`
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00005-e2e-command-wiring/issues/iss-00022-cli-entrypoint-dispatch-wiring/plan.md`
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00005-e2e-command-wiring/issues/iss-00022-cli-entrypoint-dispatch-wiring/report.md`

#### コミット
- 未実施。SG1 pass 後に docs commit を作成する。

#### メモ
- #1〜#5 は一度 close したが、この audit gap を閉じるため #22 を追加した。#22 完了後に再 sync / close state を確認する。
- `include_untracked` default の変更は owner-boundary 上は foundation seam に属するため、この issue の実装では source と docs を同時に同期する。

## 省略/例外メモ
- 該当なし。
