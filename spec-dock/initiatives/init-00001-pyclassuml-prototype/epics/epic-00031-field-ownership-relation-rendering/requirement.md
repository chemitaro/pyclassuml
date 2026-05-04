---
種別: 要件定義書（Epic）
ID: "epic-00031"
タイトル: "Field Ownership Relation Rendering"
関連GitHub: ["#31"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-05"
親: ["init-00001"]
---

# epic-00031 Field Ownership Relation Rendering — 要件定義（WHAT / WHY）

## 目的
- Python class diagram において、field annotation から読み取れる所有関係を UML の composition / aggregation として表現する。
- 現在 association として描画される field-origin relation を、field type の構造に応じてより意味のある diamond notation へ分類する。

## Epic requirements
- E-RQ-001:
  - class field が selected internal class を直接型として参照する場合、所有元 class から参照先 class への composition として扱う。
- E-RQ-002:
  - class field が Optional / Union / collection item / mapping value として selected internal class を参照する場合、所有元 class から参照先 class への aggregation として扱う。
- E-RQ-003:
  - AST-only / read-only / import 実行なしの境界を維持し、既存の inheritance / realization / uses の意味論を壊さない。

## Epic acceptance criteria
- E-AC-001:
  - Given: `class Order: customer: Customer`
  - When: `pyclassuml generate` が PlantUML を生成する
  - Then: `Order` 側に黒塗り diamond を持つ composition が出る。通常矢印頭は付けない。
- E-AC-002:
  - Given: `class Order: lines: list[OrderLine]`、`coupon: Coupon | None`、または `items_by_sku: dict[str, OrderLine]`
  - When: `pyclassuml generate` が PlantUML を生成する
  - Then: `Order` 側に白抜き diamond を持つ aggregation が出る。通常矢印頭は付けない。
- E-AC-003:
  - Given: 既存の inheritance / Protocol realization / method-only uses relation
  - When: 同じ図を生成する
  - Then: 既存の矢印種別と上向き継承表現は維持される。

## スコープ
- MUST:
  - field annotation 由来の internal class relation を composition / aggregation として分類できるようにする。
  - PEP 604 union、`typing.Optional`、`typing.Union`、主要 collection generic、主要 mapping generic の field annotation を対象にする。
- MUST NOT:
  - 対象コードを import 実行しない。
  - 対象ソースコードを書き換えない。
  - composition / aggregation 判定を method parameter / method return の uses relation に適用しない。
- OUT OF SCOPE:
  - runtime instance ownership の推測。
  - multiplicity label の完全表現。
  - SQLAlchemy relationship や Pydantic 固有解析の追加 heuristic。

## 境界
- Always:
  - AST から取得できる annotation 構造のみで判定する。
  - false positive よりも、明示的に読める field annotation の決定的分類を優先する。
- Ask:
  - nested collection / nested mapping の扱いを MVP 以上に拡張する場合。
- Never:
  - runtime inspection や import 実行で ownership を推測しない。
