---
種別: 要件定義書（Issue）
ID: "iss-00016"
タイトル: "Frameworks SQLAlchemy Enrich"
関連GitHub: ["#16"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
親: ["epic-00004", "init-00001"]
---

# iss-00016 Frameworks SQLAlchemy Enrich — 要件定義（WHAT / WHY）

## 目的
- `analyze.relationship-and-selection` が確定した relation inventory を基礎に、SQLAlchemy `Mapped[T]` と `relationship("T")` を best-effort で内部 class relation へ補強する。
- core-analysis や render/report に SQLAlchemy 固有ロジックを漏らさず、framework support の owner を `frameworks` に固定する。

## スコープ
- MUST:
  - `ParsedModule[]` と `SelectedRelations` を入力に、`Mapped[T]` から内部 class relation を補強する。
  - `relationship("T")` が一意に解決できる場合、内部 class relation を補強する。
  - 補強結果を downstream render に反映できる hint と diagnostics に変換する。
  - 補強不能・曖昧解決は `recoverability=degraded_output` を持つ warning として保持し、推測 relation は追加しない。
- MUST NOT:
  - traversal frontier を広げない。
  - Git diff、artifact write、exit code 決定を行わない。
  - SQLAlchemy 以外の framework rule を混在させない。
- OUT OF SCOPE:
  - ORM registry や mapper metadata の import 実行。
  - database schema 解析。
  - Pydantic や一般 Python annotation の補強。

## 境界
- Always:
  - seam owner は `frameworks`。
  - upstream は `parse.module-parse-and-index` と `analyze.relationship-and-selection`。
  - downstream shared handoff 先は `RenderReadyModel.relations` / `class_decorations` であり、この issue 自身の中間成果は seam-local hint として扱う。
- Ask:
  - SQLAlchemy support を prototype baseline の `Mapped[T]` / `relationship("T")` から広げたい場合。
  - relation ambiguity 時に warning ではなく推測接続を許容したい場合。
- Never:
  - import 実行で SQLAlchemy runtime metadata を読まない。
  - 解決不能な文字列 relation を決め打ちしない。
  - class selection contract を上書きしない。

## 制約
- AST-only / read-only / deterministic を守る。
- 補強は既知の内部 class relation に限定し、外部 dependency や未選択 frontier を勝手に追加しない。
- warning diagnostics は `report` が summary へ反映できる粒度で downstream へ渡す。

## 受け入れ条件
- AC-001:
  - Actor:
    - CLI 利用者
  - Given:
    - `Mapped[T]` を持つ SQLAlchemy model fixture がある。
  - When:
    - `frameworks.sqlalchemy-enrich` を適用する。
  - Then:
    - `T` が内部 class として解決できる限り、relation hint が追加され、後段 render で relation を観測できる。
  - 観測点:
    - `fx-framework-sqlalchemy-basic` scenario。
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
    - SQLAlchemy relation を解決できても、その class が selection contract 外である。
  - 期待:
    - class selection owner は `analyze.relationship-and-selection` のままとし、この issue は relation / decoration hint の補強に留める。
  - 観測点:
    - selection boundary review。

## 未確定事項
- なし:
  - SQLAlchemy best-effort support の baseline row は initiative canonical docs で確定済みである。
