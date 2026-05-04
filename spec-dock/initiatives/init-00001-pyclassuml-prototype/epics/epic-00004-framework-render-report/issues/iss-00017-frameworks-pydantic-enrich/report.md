---
種別: 実装報告書（Issue）
ID: "iss-00017"
タイトル: "Frameworks Pydantic Enrich"
関連GitHub: ["#17"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00004", "init-00001"]
---

# iss-00017 Frameworks Pydantic Enrich — 実装報告（LOG）

## 実装サマリー (任意)
- 現行 `ClassReference` は SQLAlchemy 実装で追加済みだが、Pydantic の direct quoted forward reference `field: "T"` と quoted 由来の区別には不足があるため、実装前に契約を修復している。
- 方針は parse/model に framework-neutral な quoted annotation evidence を最小追加し、Pydantic 固有の relation 解釈は `frameworks.pydantic` に閉じる。

## 実装記録（セッションログ） (必須)

### 2026-05-04 - contract repair

#### 対象
- Step: SG1
- AC/EC: AC-001, AC-002, EC-001, EC-002, EC-003, EC-004

#### 実施内容
- `iss-00016` 実装後の `ClassReference` と parse evidence を確認した。
- `field: "T"` の direct quoted annotation は現行 parse evidence では表現できず、quoted subscript も quoted 由来かどうかを framework seam が判断できないことを確認した。
- `requirement.md` / `design.md` / `plan.md` を、framework-neutral `annotation_string` evidence 追加と Pydantic seam-local enrichment の契約へ更新した。
- render 反映は downstream `iss-00018` の owner とし、この issue では `PydanticEnrichmentHints.added_relations` と warning diagnostics までを完成条件にした。
- warning diagnostic code を `pydantic_forward_ref_ambiguous` / `pydantic_forward_ref_unresolved` / `pydantic_forward_ref_selection_outside` に固定した。
- spec-reviewer fail を受け、source class id も `SelectedClasses` で gate すること、unselected source は warning なしで no relation とすることを明文化した。
- `Union["B", "C"]` の uniquely resolved member と triple dedupe を Pydantic seam test に含める契約へ補強した。
- 再レビュー fail を受け、AST-only Pydantic eligibility signal として direct base `BaseModel` / `pydantic.BaseModel` の `class_base` evidence を追加する契約にした。
- Pydantic eligibility のない quoted annotation は warning なしで無視する negative test を plan に追加した。
- さらに requirement の境界文言を修正し、`ModuleIndex` を入力契約に追加し、direct class-base evidence を framework-neutral parse evidence として明示した。
- class-base evidence の汎用性を design/plan にも反映し、`CustomBase` でも `class_base/base/CustomBase` evidence を返す検証を追加する契約にした。
- nested function / async function / nested class / lambda body 内 annotation の除外検証を plan に追加した。

#### 実行コマンド / 結果
```bash
sed -n '220,390p' src/pyclassuml/parse/indexer.py
sed -n '1,260p' src/pyclassuml/frameworks/sqlalchemy.py

ClassReference は存在するが、Pydantic direct quoted annotation evidence は未実装。
```

#### 変更したファイル
- `spec-dock/active/issue/requirement.md` - quoted forward reference scope と diagnostics contract を具体化。
- `spec-dock/active/issue/design.md` - `annotation_string` evidence と Pydantic hint flow を具体化。
- `spec-dock/active/issue/plan.md` - TDD step、review/QA gate、final exit contract を具体化。
- `spec-dock/active/issue/report.md` - 契約修復の判断と証跡を記録。

#### コミット
- 未作成。spec-reviewer pass 後に docs commit を作成する。

#### メモ
- parse は quoted annotation evidence の保持だけを担い、Pydantic 解釈は行わない。
- non-quoted annotation `field: T` の一般 typing support は out of scope とする。

---

### 2026-05-04 - implementation and validation

#### 対象
- Step: S01, S02, S90, S99
- AC/EC: AC-001, AC-002, EC-001, EC-002, EC-003, EC-004

#### 実施内容
- `src/pyclassuml/parse/indexer.py` に framework-neutral な `class_base/base` evidence と `annotation_string` evidence を追加した。
- direct quoted annotation、quoted subscript annotation、direct class base を既存 `ClassReference` で表現するようにした。
- nested function / async function / nested class / lambda body の quoted annotation evidence が outer class に混入しないようにした。
- `src/pyclassuml/frameworks/pydantic.py` を追加し、`PydanticEnrichmentHints` と `extract_pydantic_enrichment_hints` を実装した。
- Pydantic eligibility は `class_base/base/BaseModel` と `class_base/base/pydantic.BaseModel` evidence に限定した。
- `annotation_string` evidence のみを forward reference として解釈し、all-internal candidate で一意解決でき、source / target が selected の場合だけ `pydantic_forward_ref` relation hint を返すようにした。
- generic base `BaseModel[T]` / `pydantic.BaseModel[T]` / `CustomBase[T]` は parse seam の direct base evidence として扱うようにした。
- nested class の quoted annotation は outer class に混入させず、nested class 自身の source id で保持するようにした。
- Pydantic の `ClassVar["T"]` は field relation ではないため warning / relation なしで無視するようにした。
- unresolved / ambiguous / selection outside / mixed collision は warning diagnostic として返し、relation は追加しないようにした。
- existing relation inventory と同一 extraction 内の source / target / relation_type triple dedupe を実装した。
- Pydantic seam を `src/pyclassuml/frameworks/__init__.py` から export した。
- parse tests と Pydantic framework tests を追加・更新し、SQLAlchemy framework tests の regression を確認した。
- code-reviewer は P2 指摘修正後に findings なしで pass した。
- qa-reviewer は generic base coverage の P1、nested class / `ClassVar` edge の P2 を指摘し、修正後に pass した。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest tests/parse/test_module_parse_and_index.py tests/frameworks/test_pydantic.py tests/frameworks/test_sqlalchemy.py -q
# 56 passed in 0.06s

uv run --with pytest pytest -q
# 182 passed in 1.04s

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
# spec-dock/system/active-none/issue/README.md
# spec-dock/system/active-none/epic/README.md
# spec-dock/system/active-none/README.md
# spec-dock/docs/README.md

find . -name '__pycache__' -o -name 'uv.lock'
# cleanup 後は出力なし
```

#### レビュー結果
- code-reviewer: pass。P2 指摘修正後の fresh review で findings なし。
- qa-reviewer: pass。generic class-base coverage の P1 は `CustomBase[T]` / `BaseModel[T]` / `pydantic.BaseModel[T]` の parse / handoff regression 追加で解消。
- qa-reviewer: pass。nested class quoted annotation と parser-backed `ClassVar["B"]` no relation/no warning の P2 は regression 追加で解消。

#### 変更したファイル
- `src/pyclassuml/parse/indexer.py` - generic class-base / quoted annotation evidence 抽出を追加。
- `src/pyclassuml/frameworks/pydantic.py` - Pydantic enrichment hint seam を追加。
- `src/pyclassuml/frameworks/__init__.py` - Pydantic seam export を追加。
- `tests/parse/test_module_parse_and_index.py` - parse evidence と exclusion の coverage を追加。
- `tests/frameworks/test_pydantic.py` - Pydantic AC/EC coverage を追加。
- `spec-dock/active/issue/report.md` - 実装と検証結果を記録。

#### コミット
- 未作成。最終検証後に docs commit `0c5584b` とは別の implementation commit を作成する。

#### メモ
- `uv run --with pytest` により `uv.lock` と `__pycache__` が生成されたため削除した。
- render shared DTO への合成は downstream `iss-00018` の責務として残した。

---

## 遭遇した問題と解決 (任意)
- 該当なし

## 学んだこと (任意)
- Pydantic forward reference では、target 名だけでなく「quoted annotation 由来であること」を framework-neutral に保持する必要がある。

## 今後の推奨事項 (任意)
- `iss-00018` では `PydanticEnrichmentHints` を `RenderReadyModel` に合成する。

## 省略/例外メモ (必須)
- render shared DTO への合成は downstream `iss-00018` の責務として、この issue では実装しない。
