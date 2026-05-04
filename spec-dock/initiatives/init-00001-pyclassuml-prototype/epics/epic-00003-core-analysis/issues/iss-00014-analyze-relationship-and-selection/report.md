---
種別: 実装報告書（Issue）
ID: "iss-00014"
タイトル: "Analyze Relationship And Selection"
関連GitHub: ["#14"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00003", "init-00001"]
---

# iss-00014 Analyze Relationship And Selection — 実装報告（LOG）

## 実装サマリー
- 2026-05-04 時点では、active issue を `iss-00014-analyze-relationship-and-selection` として復元し、`requirement.md` / `design.md` を確認した。
- `plan.md` / `report.md` がテンプレート状態だったため、現行 `ParsedModule` / `ModuleIndex` / `DependencyGraph` から実装可能な selection execution contract へ置き換えた。
- 現行 `ParsedModule` は `imports` / `classes` のみを保持するため、MVP relation は reachable module import edge から source/target class が一意に解決できる場合に限定し、annotation / base class / member type / wildcard token の深い解釈は非スコープとして明示した。
- spec-reviewer pass 1 は fail。multi-class dependency と one-class relation rule の衝突、wildcard/re-export warning trigger の曖昧さ、counter が pre-enrich か final diagram count かの曖昧さを指摘されたため、MVP relation / warning / counter contract を修正した。
- spec-reviewer pass 2 も fail。現行 parse DTO が wildcard token evidence を保持しないため、wildcard warning trigger が実装不能と指摘された。AC-004/EC-001/S03 を endpoint cardinality ambiguity に絞り、wildcard/re-export warning は非スコープへ戻した。
- spec-reviewer pass 3 も fail。sibling exclusion が current DTO では accepted relation と同時に観測不能だったため、AC-003/EC-003/S02 を一意解決可能 relation endpoint と multi-class dependency ambiguity に分離した。
- spec-reviewer pass 4 は findings なしで pass。AC-003 は一意解決可能 one-class source/target relation fixture に限定され、EC-003 は multi-class dependency ambiguity として requirement/design/plan が整合した。
- `select_classes_and_relations` を追加し、`DependencyGraph.reachable_files` を selection frontier として seed full-display、module import relation、ambiguity diagnostics、core-analysis pre-enrich counters を返すようにした。
- code-reviewer / QA reviewer の初回 fail で `reachable_files` gate の不足が見つかったため、seed selection と edge endpoint の両方を reachable subset に制限し、re-review で pass した。

## 実装記録（セッションログ）

### 2026-05-04 active set and implementation-readiness repair

#### 対象
- Step: SG1, planning repair
- AC/EC: AC-001, AC-002, AC-003, AC-004, EC-001, EC-002, EC-003

#### 実施内容
- `iss-00013` close 後、dashboard / deps check により `iss-00014` が ready / blockers=0 であることを確認した。
- spec-manager により `iss-00014` を active set し、active pointers が `init-00001` / `epic-00003` / `iss-00014` になったことを確認した。
- `requirement.md` / `design.md` は issue 固有内容だったが、`plan.md` / `report.md` はテンプレート状態だったため、S01/S02/S03/S90/S99 の execution contract へ置き換えた。
- design の relation extraction を、現行 `ParsedModule.imports` / `ParsedModule.classes` / `ModuleIndex.import_candidate_paths` で実装可能な module import relation MVP へ明確化した。
- spec-reviewer の指摘を受け、current DTO で特定 class endpoint を一意解決できない dependency multi-class case は warning/no relation とし、dependency class selection を追加しない契約へ修正した。
- さらに、relation を持たない sibling class の除外を accepted relation と同時に検証することは current DTO ではできないため、multi-class dependency は ambiguity/no dependency selection として扱う契約へ修正した。
- wildcard/re-export の深い解釈は current parse DTO に token evidence がないため非スコープとし、warning trigger は source/target module class cardinality ambiguity に限定した。
- `SelectionObservations` counters は core-analysis pre-enrich count とし、final diagram count は downstream render/report owner が必要に応じて置き換える契約へ修正した。

#### 実行コマンド / 結果
```bash
./spec-dock/scripts/spec-dock deps check iss-00014 --github

spec-dock: ok (deps check) target=iss-00014 authority=github effective_status=open source=github stale=false ... ready=true blockers=0
```

```bash
./spec-dock/scripts/spec-dock active show

initiative: init-00001 (spec-dock/initiatives/init-00001-pyclassuml-prototype)
epic: epic-00003 (spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00003-core-analysis)
issue: iss-00014 (spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00003-core-analysis/issues/iss-00014-analyze-relationship-and-selection)
```

```bash
./spec-dock/scripts/spec-dock validate

spec-dock: ok (validate) nodes=21
```

#### 変更したファイル
- `spec-dock/active/issue/design.md` - current parse DTO で実装可能な relation MVP と ambiguity handling を明確化。
- `spec-dock/active/issue/plan.md` - issue-specific execution contract へ置き換え。
- `spec-dock/active/issue/report.md` - active set / readiness repair evidence を記録。

#### コミット
- spec-review pass 後に判断する。

#### メモ
- spec-reviewer pass 4 により実装開始ゲートを通過した。

### 2026-05-04 spec-review pass

#### 対象
- Step: SG1 re-review
- AC/EC: AC-001, AC-002, AC-003, AC-004, EC-001, EC-002, EC-003

#### 実施内容
- spec-reviewer re-review により、前回 P1 の sibling-exclusion contradiction が解消済みであることを確認した。
- requirement / design / plan が current DTO evidence から実装可能であり、P0/P1 の残存曖昧さがないことを確認した。

#### 実行コマンド / 結果
```bash
spec-reviewer re-review

review_status: pass
findings: []
```

```bash
./spec-dock/scripts/spec-dock validate

spec-dock: ok (validate) nodes=21
```

#### 変更したファイル
- `spec-dock/active/issue/report.md` - spec-review pass evidence を記録。

#### コミット
- docs repair commit に含める。

### 2026-05-04 implementation and review loop

#### 対象
- Step: S01, S02, S03, RG1, QG1
- AC/EC: AC-001, AC-002, AC-003, AC-004, EC-001, EC-002, EC-003

#### 実施内容
- `src/pyclassuml/analyze/selection.py` を追加し、`select_classes_and_relations(...) -> SelectionResult` を実装した。
- `SelectedRelation` / `SelectedRelations` / `SelectionObservations` / `SelectionResult` を analyze.selection seam-local DTO として定義した。
- `DependencyGraph.reachable_files` を selection frontier とし、seed full-display は seed provenance と reachable subset の交差に限定した。
- `DependencyGraph.edges` は source / target の両方が reachable subset に含まれる edge だけを処理し、stale edge endpoint は relation / diagnostic / counter に入れない boundary guard とした。
- source/target module class がそれぞれ 1 件の場合だけ `uses` / `module_import` relation を追加し、multi-class / zero-class ambiguity は warning diagnostics として保持した。
- code-reviewer 初回は `reachable_files` を selection boundary として使っていない P1 で fail。修正後 re-review は findings なしで pass。
- QA reviewer 初回は reachable_files gating 未保護 P1 と source multi-class ambiguity coverage P2 で fail。修正後 re-review は findings なしで pass。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest tests/analyze/test_selection.py -q

.........                                                                [100%]
9 passed in 0.01s
```

```bash
uv run --with pytest pytest tests/analyze/test_traversal.py -q

..............                                                           [100%]
14 passed in 0.02s
```

```bash
uv run --with pytest pytest -q

122 passed in 0.94s
```

```bash
code-reviewer re-review

review_status: pass
findings: []
```

```bash
qa-reviewer re-review

review_status: pass
findings: []
```

#### 変更したファイル
- `src/pyclassuml/analyze/selection.py` - class/relation selection seam を追加。
- `src/pyclassuml/analyze/__init__.py` - selection public exports を追加。
- `tests/analyze/test_selection.py` - selection contract tests を追加。

#### コミット
- final validation と report update 後に実装コミットへ含める。

### 2026-05-04 final validation

#### 対象
- Step: S90, S99
- AC/EC: final exit contract

#### 実施内容
- issue-scoped docs のみ更新対象であり、root `AGENTS.md`、README、SpecDock workflow docs への恒久 docs 変更は不要と判断した。
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
- 問題: `design.md` は annotation / base class / member type などの抽出を示していたが、現行 `ParsedModule` はそれらを保持していない。
  - 解決: この issue では reachable module import edge から一意解決できる class relation のみを accepted relation とし、深い symbol relation は非スコープとして明示した。
- 問題: 初回実装では `DependencyGraph.reachable_files` を selection frontier として使わず、traversal limit で graph に入らなかった seed や stale edge endpoint を選択しうる状態だった。
  - 解決: seed selection と edge processing の両方を reachable subset に制限し、boundary guard の回帰テストを追加した。

## 学んだこと
- `iss-00014` は `iss-00013` の `DependencyGraph` と seed provenance を初めて消費する issue であり、selection owner と downstream frameworks/render/report の境界を固定する。

## 今後の推奨事項
- 将来 annotation / base class / member type relation を追加する場合は、先に parse DTO に構造化情報を持たせる issue を切る。

## 省略/例外メモ
- `uv run` により未追跡 `uv.lock` が生成される場合があるが、この issue の成果物ではないため削除する。
- `rg --files | rg '[A-Z]'` は既存許可 path の `AGENTS.md` / `README.md` 系のみを出力し、新規 uppercase path は追加していない。
