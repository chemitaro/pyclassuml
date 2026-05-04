---
種別: 要件定義書（Issue）
ID: "iss-00016"
タイトル: "Frameworks SQLAlchemy Enrich"
関連GitHub: ["#16"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
親: ["epic-00004", "init-00001"]
---

# iss-00016 Frameworks SQLAlchemy Enrich — 要件定義（WHAT / WHY）

## 目的
- `analyze.relationship-and-selection` が確定した relation inventory を基礎に、SQLAlchemy `Mapped[T]` と `relationship("T")` を best-effort で内部 class relation へ補強する。
- core-analysis や render/report に SQLAlchemy 固有ロジックを漏らさず、framework support の owner を `frameworks` に固定する。

## スコープ
- MUST:
  - `ParsedModule[]` と `SelectedClasses` / `SelectedRelations` を入力に、`Mapped[T]` から選択済み内部 class relation を補強する。
  - `relationship("T")` が選択済み内部 class へ一意に解決できる場合、内部 class relation を補強する。
  - 補強結果を seam-local `SqlalchemyEnrichmentHints.added_relations` と diagnostics に変換する。
  - 補強不能・曖昧解決は `recoverability=degraded_output` を持つ warning として保持し、推測 relation は追加しない。
  - 現行 `ParsedModule` が class body の annotation / call site evidence を保持していないため、parse/model seam に framework-neutral な class reference evidence を最小追加する。
- MUST NOT:
  - traversal frontier を広げない。
  - Git diff、artifact write、exit code 決定を行わない。
  - SQLAlchemy 以外の framework rule を混在させない。
  - parse seam に SQLAlchemy 固有の relation 解釈を持ち込まない。
- OUT OF SCOPE:
  - ORM registry や mapper metadata の import 実行。
  - database schema 解析。
  - Pydantic や一般 Python annotation の補強。

## 境界
- Always:
  - seam owner は `frameworks`。
  - upstream は `parse.module-parse-and-index` と `analyze.relationship-and-selection`。
  - この issue 自身の成果は seam-local hint として扱い、downstream shared handoff への合成は `render.uml-document` 側の責務にする。
  - parse/model 追加は AST から観測できる class-body reference evidence の保持に限定し、framework relation の意味付けは `frameworks.sqlalchemy-enrich` で行う。
- Ask:
  - SQLAlchemy support を prototype baseline の `Mapped[T]` / `relationship("T")` から広げたい場合。
  - relation ambiguity 時に warning ではなく推測接続を許容したい場合。
- Never:
  - import 実行で SQLAlchemy runtime metadata を読まない。
  - 解決不能な文字列 relation を決め打ちしない。
  - class selection contract を上書きしない。

## 制約
- AST-only / read-only / deterministic を守る。
- 補強は `SelectedClasses` 内で一意に解決できる既知の内部 class relation に限定し、外部 dependency や未選択 frontier を勝手に追加しない。
- warning diagnostics は `report` が summary へ反映できる粒度で downstream へ渡す。
- warning diagnostics は shared enum の範囲に従い、`origin_seam=frameworks`、`recoverability=degraded_output`、`failure_reason=None` とする。
- warning diagnostic code は stable snake_case とし、曖昧解決は `sqlalchemy_relation_ambiguous`、未解決は `sqlalchemy_relation_unresolved`、selection 外衝突は `sqlalchemy_relation_selection_outside` とする。
- 追加 relation hint は deterministic order で重複排除する。

## 受け入れ条件
- AC-001:
  - Actor:
    - CLI 利用者
  - Given:
    - `Mapped[T]` を持つ SQLAlchemy model fixture がある。
  - When:
    - `frameworks.sqlalchemy-enrich` を適用する。
  - Then:
    - `T` が選択済み内部 class として一意解決できる限り、`SqlalchemyEnrichmentHints.added_relations` に source / target / evidence kind が deterministic に追加される。
  - 観測点:
    - SQLAlchemy seam unit test。
- AC-002:
  - Actor:
    - CLI 利用者
  - Given:
    - `relationship("T")` を持つ SQLAlchemy model fixture がある。
  - When:
    - 文字列 relation を解決する。
  - Then:
    - 一意解決できる場合だけ relation hint を追加し、解決結果は deterministic である。
  - 観測点:
    - SQLAlchemy string relation review。

## 例外・エッジケース
- EC-001:
  - 条件:
    - `relationship("T")` が複数 class に一致して曖昧である。
  - 期待:
    - warning を残し、relation は追加しない。
  - 観測点:
    - ambiguity diagnostic review。
- EC-002:
  - 条件:
    - `Mapped[T]` または `relationship("T")` の `T` が内部 class として解決できない。
  - 期待:
    - warning を残し、既存 relation inventory を壊さず継続する。
  - 観測点:
    - unresolved relation review。
- EC-003:
  - 条件:
    - SQLAlchemy relation の target name が selection contract 外の内部 class に一致する。
  - 期待:
    - class selection owner は `analyze.relationship-and-selection` のままとし、warning を残して relation は追加しない。
  - 観測点:
    - selection boundary review。
- EC-004:
  - 条件:
    - target name が 1 件の selected class と 1 件以上の non-selected internal class の両方に一致する。
  - 期待:
    - all-internal candidate set では曖昧と扱い、`sqlalchemy_relation_ambiguous` warning を残して relation は追加しない。
  - 観測点:
    - mixed selected/non-selected collision review。

## 未確定事項
- なし:
  - 現行 model の不足は、この issue 内で parse/model の framework-neutral evidence を最小追加して解消する。
