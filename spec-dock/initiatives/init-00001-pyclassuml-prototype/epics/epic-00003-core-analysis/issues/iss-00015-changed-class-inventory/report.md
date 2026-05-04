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
- `build_changed_class_inventory` を追加し、upstream handed-off changed file 集合と parsed module join から deterministic な `ChangedClassInventory(class_count, changed_files)` を返すようにした。
- implementation review / QA review は findings なしで pass し、changed file count semantics が selection / traversal と独立していることを tests で確認した。

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

### 2026-05-04 implementation and review loop

#### 対象
- Step: S01, S02, RG1, QG1
- AC/EC: AC-001, AC-002, AC-003, EC-001, EC-002, EC-003, EC-004

#### 実施内容
- `src/pyclassuml/analyze/changed.py` を追加し、`build_changed_class_inventory(changed_files, parsed_modules, module_index)` を実装した。
- `changed_files` は upstream handed-off project-root relative `Path` として受け取り、追加 normalization / Git read / ignore filter は行わない実装にした。
- `ModuleIndex.project_relative_file_to_module` で changed file と parsed module を join し、join 成立時だけ `ParsedModule.classes` を class 定義単位で count する。
- classless file / join miss / syntax error 相当は `changed_files` に残し、`class_count` へ加算せず、追加 diagnostics も作らない。
- code-reviewer は findings なしで pass。
- QA reviewer は findings なしで pass。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest tests/analyze/test_changed_inventory.py -q

.........                                                                [100%]
9 passed in 0.01s
```

```bash
uv run --with pytest pytest tests/analyze/test_selection.py -q

.........                                                                [100%]
9 passed in 0.02s
```

```bash
uv run --with pytest pytest -q

131 passed in 0.95s
```

```bash
code-reviewer review

review_status: pass
findings: []
```

```bash
qa-reviewer review

review_status: pass
findings: []
```

#### 変更したファイル
- `src/pyclassuml/analyze/changed.py` - changed class inventory seam を追加。
- `src/pyclassuml/analyze/__init__.py` - changed inventory public export を追加。
- `tests/analyze/test_changed_inventory.py` - changed inventory contract tests を追加。

#### コミット
- final validation と report update 後に実装コミットへ含める。

### 2026-05-04 final validation

#### 対象
- Step: S90, S99
- AC/EC: final exit contract

#### 実施内容
- issue-scoped docs と親 epic consistency 修正以外の恒久 docs 変更は不要と判断した。
- targeted tests、full suite、SpecDock validate を実施した。
- `uv run` が生成しうる未追跡 `uv.lock` は成果物ではないため削除対象とする。

#### 実行コマンド / 結果
```bash
./spec-dock/scripts/spec-dock validate

spec-dock: ok (validate) nodes=21
```

#### 変更したファイル
- `spec-dock/active/issue/report.md` - 実装、レビュー、QA、最終検証の証跡を追記。

#### コミット
- 実装差分と report update をまとめてコミットする。

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
- `uv run` により未追跡 `uv.lock` が生成される場合があるが、この issue の成果物ではないため削除する。
- `rg --files | rg '[A-Z]'` は既存許可 path の `AGENTS.md` / `README.md` 系のみを出力し、新規 uppercase path は追加していない。
