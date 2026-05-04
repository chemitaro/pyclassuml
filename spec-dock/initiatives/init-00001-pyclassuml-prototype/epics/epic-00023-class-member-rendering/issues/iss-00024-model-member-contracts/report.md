---
種別: 実装報告書（Issue）
ID: "iss-00024"
タイトル: "Model Member Contracts"
関連GitHub: ["#24"]
状態: "draft | approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00023", "init-00001"]
---

# iss-00024 Model Member Contracts — 実装報告（LOG）

## 実装サマリー (任意)
- `ClassMember` / `MemberParameter` / `MemberKind` / `MemberVisibility` を shared model contract に追加し、`ParsedModule.members` と `RenderReadyModel.members` を structured member tuple に更新した。
- `SelectedRelation` / `SelectedRelations` を `pyclassuml.model` の shared import surface へ移し、`pyclassuml.analyze.selection` は compatibility re-export として維持した。
- `relation_type` は `inherits` / `association` / `uses` のみを許可し、render convenience string は member DTO に追加していない。

## 実装記録（セッションログ） (必須)

### 2026-05-04 20:25 JST

#### 対象
- Step: S01, S02, S03, S90, S99
- AC/EC: AC-001, AC-002, AC-003, EC-001, EC-002, EC-003

#### 実施内容
- `src/pyclassuml/model/contracts.py` に member DTO と selected relation DTO を追加した。
- `ParsedModule.members` は constructor compatibility を優先して default 付き末尾 field とし、`RenderReadyModel.members` は既存 field の型を `ClassMember` tuple に更新した。
- `parameters` / `modifiers` / `members` / `relations` は既存 DTO pattern に合わせて tuple coercion と nested value validation を行う。
- `src/pyclassuml/model/__init__.py` から新 contract を re-export し、render / frameworks は shared model surface import に寄せた。
- `src/pyclassuml/analyze/selection.py` は `SelectedRelation` / `SelectedRelations` を model から import して再公開し、旧 import path を維持した。
- `tests/model/test_contracts.py` と `tests/analyze/test_selection.py` に contract / compatibility tests を追加し、render fixture の relation vocabulary を許可語彙へ更新した。
- QA 指摘に基づき、generator input と複数要素の stable order を `ClassMember.parameters` / `ClassMember.modifiers` / `ParsedModule.members` / `RenderReadyModel.members` で追加検証した。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest tests/model/test_contracts.py tests/analyze/test_selection.py tests/render/test_document.py -q
# 46 passed in 0.07s

uv run --with pytest pytest tests/frameworks/test_pydantic.py tests/frameworks/test_sqlalchemy.py -q
# 39 passed in 0.05s

uv run --with pytest pytest -q
# 288 passed in 10.00s

./spec-dock/scripts/spec-dock validate
# spec-dock: ok (validate) nodes=28

git diff --check
# pass

rg --files | rg '[A-Z]'
# existing allowed uppercase paths only: AGENTS.md and README.md files under spec-dock

find . \( -type d -name __pycache__ -o -type f -name '*.pyc' -o -name uv.lock -o -name '*.egg-info' \) -print
# pass after cleanup; no output
```

#### 変更したファイル
- `src/pyclassuml/model/contracts.py` - member DTO / shared relation DTO / relation vocabulary validation / member tuple fields
- `src/pyclassuml/model/__init__.py` - public model import surface
- `src/pyclassuml/analyze/selection.py` - compatibility re-export via shared model owner
- `src/pyclassuml/render/document.py` - shared relation import surface alignment
- `src/pyclassuml/frameworks/pydantic.py` - shared relation import surface alignment
- `src/pyclassuml/frameworks/sqlalchemy.py` - shared relation import surface alignment
- `tests/model/test_contracts.py` - member / relation contract coverage
- `tests/analyze/test_selection.py` - compatibility import coverage
- `tests/render/test_document.py` - relation vocabulary fixture alignment
- `spec-dock/active/issue/report.md` - implementation and validation evidence

#### コミット
- 実装差分と本 report 更新を同一コミットに含める。

#### メモ
- `iss-00014` の `uses` MVP 前提は、shared `SelectedRelation` の許可語彙の一部として維持した。
- `iss-00018` の `RenderReadyModel.members=()` current behavior は、empty `ClassMember` tuple として互換維持した。
- AST parse、relation classification、PlantUML member rendering はこの issue では実装していない。
- Code review: pass（P0/P1 findings なし）。
- QA review: pass。P2 の generator / multi-item tuple coercion coverage は追加テストで対応済み。

---

## 遭遇した問題と解決 (任意)
- 問題: 既存 `tests/render/test_document.py` は自由な relation label（`owns` / `loads` / `validates`）を fixture に使っていた。
  - 解決: contract の許可語彙である `association` / `inherits` / `uses` へ置き換えた。

## 学んだこと (任意)
- `SelectedRelation` は render / frameworks からも使われる handoff contract なので、shared model owner に寄せることで cross-seam import を減らせる。

## 今後の推奨事項 (任意)
- issue 25 以降で member extraction を実装する際は、この DTO に render convenience text を追加せず、render seam で文字列化する。

## 省略/例外メモ (必須)
- SG/RG/QG は実施済み。残件なし。
