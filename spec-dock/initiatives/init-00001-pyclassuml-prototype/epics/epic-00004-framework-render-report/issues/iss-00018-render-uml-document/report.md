---
種別: 実装報告書（Issue）
ID: "iss-00018"
タイトル: "Render UML Document"
関連GitHub: ["#18"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00004", "init-00001"]
---

# iss-00018 Render UML Document — 実装報告（LOG）

## 実装サマリー (任意)
- `iss-00016` / `iss-00017` で追加した framework hints を初めて authoritative render input に合成する issue として、実装前 contract を修復している。
- 現行 model には requirement/design が要求する `RenderFailureSignal` が存在しないため、この issue の S01 で public DTO として追加する方針にした。

## 実装記録（セッションログ） (必須)

### 2026-05-04 - contract repair

#### 対象
- Step: SG1
- AC/EC: AC-001, AC-002, AC-003, EC-001, EC-002, EC-003

#### 実施内容
- dashboard で `iss-00018` が ready であること、active pointer が完了済み `iss-00017` のままだったことを確認した。
- spec-manager により `iss-00018` を active 化し、`spec-dock validate` が pass することを確認した。
- `requirement.md` / `design.md` を読み、plan がテンプレート状態で実装委任に不十分であることを確認した。
- `src/pyclassuml/model/contracts.py` を確認し、`RenderReadyModel` / `DiagramModel` / `PlantUmlText` / `FailureReason.DIAGRAM_UNBUILDABLE_AFTER_RECOVERY` は存在するが、`RenderFailureSignal` は未実装であることを確認した。
- `src/pyclassuml/analyze/selection.py`、`src/pyclassuml/frameworks/sqlalchemy.py`、`src/pyclassuml/frameworks/pydantic.py` を確認し、render input として `SelectedClasses` / `SelectedRelations` / framework `added_relations` / warning diagnostics を受けられる状態であることを確認した。
- repo-analyst の調査により、現行 `ParsedModule` は member 定義 DTO を持たず、現行 framework hints も decoration を返さないため、この issue では `members=()` / `class_decorations=()` を authoritative に保持する方針へ明確化した。
- `plan.md` を S01-S04 / SG1 / RG1 / QG1 / S90 / S99 まで具体化し、実装開始可能な execution contract に修復した。
- spec-reviewer fail を受け、`DiagramModel` の class-to-container association を `ClassId` の module path 部分から導出する契約へ固定した。
- spec-reviewer fail を受け、`RenderFailureSignal` の diagnostics / class_count / relation_count / partial_diagram_present の値を合成後 count 基準で明文化した。
- design の主要フローから member 定義取得の表現を除き、members は `()` として保持することへ統一した。
- 再レビュー fail を受け、grouping key の authoritative source を selected `ClassId` の module path 部分へ一本化し、`ModuleIndex` は existence / consistency lookup の補助に限定した。
- 再レビュー fail を受け、diagnostics carry の source を `ParsedModule[].diagnostics`、SQLAlchemy warning diagnostics、Pydantic warning diagnostics に固定した。
- spec-reviewer pass 後の P2 を受け、selected class id が `ParsedModule[].classes` / `ModuleIndex.class_to_module` に存在しない場合は `render_selected_class_missing` diagnostic を追加し、phantom class を描かず failure path へ送る契約を明文化した。
- 最終 spec-reviewer は findings なしで pass し、実装着手前 blocker がないことを確認した。

#### 実行コマンド / 結果
```bash
git status --short --branch
# ## main...origin/main

./spec-dock/scripts/spec-dock active show
# issue: iss-00018

./spec-dock/scripts/spec-dock validate
# spec-dock: ok (validate) nodes=21

rg -n "RenderFailureSignal|diagram_unbuildable_after_recovery|FailureReason" src/pyclassuml/model/contracts.py tests/model/test_contracts.py
# RenderFailureSignal は未実装。
# FailureReason.DIAGRAM_UNBUILDABLE_AFTER_RECOVERY は実装済み。
```

#### 変更したファイル
- `spec-dock/active/issue/requirement.md` - AC-002 を現行 upstream hint に合わせ、relation 反映と decoration 空保持の契約へ明確化。
- `spec-dock/active/issue/design.md` - `members=()` / `class_decorations=()` の authoritative carry を明記。
- `spec-dock/active/issue/plan.md` - render implementation contract を具体化。
- `spec-dock/active/issue/report.md` - contract repair の判断と証跡を記録。

#### コミット
- 未作成。最終差分確認後に docs commit を作成する。

#### メモ
- render は filesystem write / summary / stream routing / exit policy を持たない。
- report artifact write と final summary / exit policy は downstream `iss-00019` の責務として残す。

---

## 遭遇した問題と解決 (任意)
- 問題: `RenderFailureSignal` が docs では output contract として定義されているが、model DTO には未実装。
  - 解決: `iss-00018` S01 の明示タスクとして public DTO 追加を固定した。

## 学んだこと (任意)
- framework hints は seam-local relation hints と warning diagnostics まで実装済みで、render が relation inventory へ合成する初めての owner になる。

## 今後の推奨事項 (任意)
- `iss-00019` では `PlantUmlText` / `DiagramModel` / `RenderFailureSignal` から artifact write、summary counters、exit policy を組み立てる。

## 省略/例外メモ (必須)
- この issue では `.puml` artifact write は実装しない。
