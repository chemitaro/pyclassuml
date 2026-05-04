---
種別: 実装報告書（Issue）
ID: "iss-00016"
タイトル: "Frameworks SQLAlchemy Enrich"
関連GitHub: ["#16"]
状態: "draft | approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00004", "init-00001"]
---

# iss-00016 Frameworks SQLAlchemy Enrich — 実装報告（LOG）

## 実装サマリー (任意)
- 現行 `ParsedModule` が SQLAlchemy annotation / call site を保持していないため、実装前に契約を修復している。
- 方針は parse/model に framework-neutral な `ClassReference` evidence を最小追加し、SQLAlchemy 固有の relation 解釈は `frameworks.sqlalchemy` に閉じる。

## 実装記録（セッションログ） (必須)

### 2026-05-04 - contract repair

#### 対象
- Step: SG1
- AC/EC: AC-001, AC-002, EC-001, EC-002, EC-003

#### 実施内容
- `ParsedModule` の現行 contract が `imports/classes/diagnostics` のみで、`Mapped[T]` / `relationship("T")` を downstream framework seam が観測できないことを確認した。
- `requirement.md` / `design.md` / `plan.md` を、framework-neutral `ClassReference` evidence 追加と SQLAlchemy seam-local enrichment の契約へ更新した。
- warning diagnostic は shared enum に合わせ、`origin_seam=frameworks`、`recoverability=degraded_output`、`failure_reason=None` と定義した。
- spec-reviewer fail を受け、parse 抽出規則を generic `Owner[T]` / `callee("T")` evidence に寄せ、SQLAlchemy 語彙の解釈を `frameworks.sqlalchemy` 側に限定した。
- AC は seam-local `SqlalchemyEnrichmentHints.added_relations` の観測へ寄せ、実 render 観測と class decoration はこの issue の完成条件から外した。
- spec-reviewer pass 後の P2 指摘を受け、resolver 候補集合を all-internal class id に固定し、selected/non-selected mixed collision は ambiguity warning/no relation と定義した。
- warning diagnostic code を `sqlalchemy_relation_ambiguous` / `sqlalchemy_relation_unresolved` / `sqlalchemy_relation_selection_outside` に固定した。

#### 実行コマンド / 結果
```bash
sed -n '1,260p' src/pyclassuml/parse/indexer.py
sed -n '1,320p' src/pyclassuml/model/contracts.py

現行 ParsedModule は class body annotation / call site evidence を保持していない。
```

#### 変更したファイル
- `spec-dock/active/issue/requirement.md` - parse/model evidence 追加と selection boundary を明文化。
- `spec-dock/active/issue/design.md` - `ClassReference` contract と SQLAlchemy hint flow を具体化。
- `spec-dock/active/issue/plan.md` - TDD step、review/QA gate、final exit contract を具体化。
- `spec-dock/active/issue/report.md` - 契約修復の判断と証跡を記録。

#### コミット
- 未作成。spec-reviewer pass 後に docs commit を作成する。

#### メモ
- parse は relation 解釈を行わず、AST evidence の保持だけに留める。
- render 反映は downstream `iss-00018` の owner なので、この issue では seam-local hints までを完成範囲とする。

---

## 遭遇した問題と解決 (任意)
- 問題: ...
  - 解決: ...

## 学んだこと (任意)
- ...
- ...

## 今後の推奨事項 (任意)
- ...
- ...

## 省略/例外メモ (必須)
- render shared DTO への合成は downstream `iss-00018` の責務として、この issue では実装しない。
