---
種別: 実装報告書（Issue）
ID: "iss-00015"
タイトル: "Changed Class Inventory"
関連GitHub: ["#15"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00003", "init-00001"]
---

# iss-00015 Changed Class Inventory — 実装報告（LOG）

## 実装サマリー
- 2026-05-04 時点では、active issue を `iss-00015-changed-class-inventory` として復元し、`requirement.md` / `design.md` を確認した。
- `plan.md` / `report.md` がテンプレート状態だったため、changed file 集合と parsed module join から実装可能な execution contract へ置き換えた。
- `design.md` の lookup 名を現行 `ModuleIndex.project_relative_file_to_module` に合わせた。
- spec-reviewer は issue-level contract を implementation-ready として pass。親 epic design に残っていた diagnostic ownership conflict と stale lookup 名の P2/P3 を指摘したため、親 epic design も最小修正した。

## 実装記録（セッションログ）

### 2026-05-04 active set and implementation-readiness repair

#### 対象
- Step: SG1, planning repair
- AC/EC: AC-001, AC-002, AC-003, EC-001, EC-002, EC-003, EC-004

#### 実施内容
- `iss-00014` close 後、dashboard / deps check により `iss-00015` が ready になったことを確認した。
- spec-manager により `iss-00015` を active set し、active pointers が `init-00001` / `epic-00003` / `iss-00015` になったことを確認した。
- `requirement.md` / `design.md` は issue 固有内容だったが、`plan.md` / `report.md` はテンプレート状態だったため、S01/S02/S90/S99 の execution contract へ置き換えた。
- current source では `ModuleIndex.project_relative_file_to_module` が lookup 名であるため、design の古い `project_relative_file_path -> module_path` 表記を修正した。
- spec-reviewer pass 後、親 epic design の `ModuleIndex.project_relative_file_path -> module_path` 表記を `project_relative_file_to_module` へ修正した。
- 親 epic design の `ChangedClassInventory` warning owner 記述を、join miss では追加 diagnostics を作らず parse-origin diagnostics を再利用する契約へ狭めた。

#### 実行コマンド / 結果
```bash
./spec-dock/scripts/spec-dock active show

initiative: init-00001 (spec-dock/initiatives/init-00001-pyclassuml-prototype)
epic: epic-00003 (spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00003-core-analysis)
issue: iss-00015 (spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00003-core-analysis/issues/iss-00015-changed-class-inventory)
```

```bash
./spec-dock/scripts/spec-dock validate

spec-dock: ok (validate) nodes=21
```

#### 変更したファイル
- `spec-dock/active/issue/design.md` - `ModuleIndex.project_relative_file_to_module` に lookup 名を修正。
- `spec-dock/active/issue/plan.md` - issue-specific execution contract へ置き換え。
- `spec-dock/active/issue/report.md` - active set / readiness repair evidence を記録。
- `spec-dock/active/epic/design.md` - parent artifact の lookup 名と diagnostics owner 記述を issue contract に同期。

#### コミット
- spec-review pass 後に判断する。

#### メモ
- spec-reviewer pass により実装開始ゲートを通過した。

### 2026-05-04 spec-review pass

#### 対象
- Step: SG1 re-review
- AC/EC: AC-001, AC-002, AC-003, EC-001, EC-002, EC-003, EC-004

#### 実施内容
- spec-reviewer により issue-level contract が implementation-ready と判断された。
- 残指摘は parent artifact consistency の P2/P3 のみで実装ブロッカーではないが、将来の監査混乱を避けるため親 epic design へ反映した。

#### 実行コマンド / 結果
```bash
spec-reviewer review

review_status: pass
```

```bash
./spec-dock/scripts/spec-dock validate

spec-dock: ok (validate) nodes=21
```

#### 変更したファイル
- `spec-dock/active/issue/report.md` - spec-review pass evidence を記録。
- `spec-dock/active/epic/design.md` - parent artifact consistency を修正。

#### コミット
- docs repair commit に含める。

## 遭遇した問題と解決
- 問題: `plan.md` / `report.md` がテンプレート状態で、workflow_issue の complete 条件を満たせない状態だった。
  - 解決: issue requirement / design に合わせ、実装ステップ、検証、review、docs impact、final exit contract を具体化した。
- 問題: `design.md` の lookup 名が現行 `ModuleIndex` と一致していなかった。
  - 解決: `project_relative_file_to_module` を authoritative lookup として修正した。

## 学んだこと
- `ChangedClassInventory` は selection / traversal と独立した summary semantics であり、diff summary の意味を安定させるための seam である。

## 今後の推奨事項
- changed file path normalization は upstream targets/app owner に残し、この seam は handed-off changed file 集合だけを扱う。

## 省略/例外メモ
- 現時点では未完了。spec review、実装、targeted/full tests、implementation review、QA review、`sync --github`、final report update が未実施である。
