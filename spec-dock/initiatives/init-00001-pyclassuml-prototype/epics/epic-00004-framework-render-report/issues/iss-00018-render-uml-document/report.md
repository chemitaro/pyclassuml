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
- `RenderFailureSignal` を public DTO として追加し、render seam に `RenderReadyModel -> DiagramModel -> PlantUmlText` の pure transform を追加した。
- SQLAlchemy / Pydantic framework hints は render composition で authoritative relation inventory へ deterministic に合成し、artifact write / summary / exit policy は downstream `iss-00019` に残した。

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

### 2026-05-04 - implementation and validation

#### 対象
- Step: S01, S02, S03, S04, S90, S99
- AC/EC: AC-001, AC-002, AC-003, EC-001, EC-002, EC-003

#### 実施内容
- `RenderFailureSignal(failure_reason, diagnostics, class_count, relation_count, partial_diagram_present)` を public model DTO として追加した。
- `partial_diagram_present == (class_count > 0)` を DTO invariant として validation した。
- `src/pyclassuml/render/` seam を追加し、`compose_render_ready_model`、`build_diagram_model`、`render_plantuml_text`、`render_uml_document`、seam-local `RenderDocumentResult` を実装した。
- selected relations と SQLAlchemy / Pydantic `added_relations` を `(source, target, relation_type)` triple で dedupe し、deterministic に `RenderReadyModel.relations` へ合成した。
- grouping key は selected `ClassId` の module path 部分を唯一の source として導出した。
- 現行 upstream に member / decoration DTO がないため、`members=()` / `class_decorations=()` を保持した。
- `ParsedModule[].diagnostics`、SQLAlchemy warning diagnostics、Pydantic warning diagnostics を deterministic に carry した。
- selected class が `ParsedModule[].classes` と `ModuleIndex.class_to_module` の両方に存在する場合だけ renderable とし、欠落時は `render_selected_class_missing` diagnostic と failure path にした。
- relation endpoint が renderable classes に存在しない場合は `render_relation_endpoint_missing` diagnostic と failure path にした。
- PlantUML text は stable package grouping、alias `c001...`、class line、relation line を deterministic に出力するようにした。
- code-reviewer は P2 修正後に findings なしで pass した。
- qa-reviewer は P2 を指摘したが、framework relation order permutation まで追加検証し、全 P2 を解消した。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest tests/render/test_document.py -q
# 12 passed in 0.04s

uv run --with pytest pytest tests/model/test_contracts.py tests/render/test_document.py tests/frameworks/test_sqlalchemy.py tests/frameworks/test_pydantic.py -q
# 70 passed in 0.06s

uv run --with pytest pytest -q
# 195 passed in 1.04s

./spec-dock/scripts/spec-dock validate
# spec-dock: ok (validate) nodes=21

git diff --check
# pass

rg --files | rg '[A-Z]'
# 既存 uppercase path のみ:
# AGENTS.md
# spec-dock/templates/README.md
# spec-dock/scripts/README.md
# spec-dock/system/README.md
# spec-dock/system/active-none/initiative/README.md
# spec-dock/system/active-none/README.md
# spec-dock/system/active-none/issue/README.md
# spec-dock/docs/README.md
# spec-dock/system/active-none/epic/README.md

find . -name '__pycache__' -o -name '*.pyc' -o -name 'uv.lock'
# cleanup 後は出力なし
```

#### 変更したファイル
- `src/pyclassuml/model/contracts.py` - `RenderFailureSignal` DTO と validation を追加。
- `src/pyclassuml/model/__init__.py` - `RenderFailureSignal` export を追加。
- `src/pyclassuml/render/__init__.py` - render seam public surface を追加。
- `src/pyclassuml/render/document.py` - render-ready composition、diagram build、PlantUML serialization、failure handoff を追加。
- `tests/model/test_contracts.py` - `RenderFailureSignal` contract coverage を追加。
- `tests/render/test_document.py` - render AC/EC coverage を追加。
- `spec-dock/active/issue/report.md` - 実装と検証結果を記録。

#### コミット
- 未作成。最終差分確認後に implementation commit を作成する。

#### メモ
- `.puml` artifact write、summary counters、exit policy は downstream `iss-00019` の責務として未実装。

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
