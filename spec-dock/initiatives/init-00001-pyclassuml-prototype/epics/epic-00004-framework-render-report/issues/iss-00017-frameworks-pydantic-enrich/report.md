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

## 遭遇した問題と解決 (任意)
- 該当なし

## 学んだこと (任意)
- Pydantic forward reference では、target 名だけでなく「quoted annotation 由来であること」を framework-neutral に保持する必要がある。

## 今後の推奨事項 (任意)
- `iss-00018` では `PydanticEnrichmentHints` を `RenderReadyModel` に合成する。

## 省略/例外メモ (必須)
- render shared DTO への合成は downstream `iss-00018` の責務として、この issue では実装しない。
