---
種別: 要件定義書（Issue）
ID: "iss-00018"
タイトル: "Render UML Document"
関連GitHub: ["#18"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
親: ["epic-00004", "init-00001"]
---

# iss-00018 Render UML Document — 要件定義（WHAT / WHY）

## 目的
- core selection と framework hint を authoritative な `RenderReadyModel` に合成したうえで deterministic な PlantUML text へ変換し、report が artifact / summary / exit policy だけに集中できる状態を作る。
- diagram shape と text generation の owner を `render` に固定し、filesystem write や summary policy を持ち込まない。

## スコープ
- MUST:
  - `ParsedModule[]`, `ModuleIndex`, `SelectedClasses`, `SelectedRelations`, `SqlalchemyEnrichmentHints`, `PydanticEnrichmentHints` を入力に authoritative な `RenderReadyModel` を合成する。
  - 合成した `RenderReadyModel` から `DiagramModel` と `PlantUmlText` を構築する。
  - class、relation、grouping、label、alias の順序を deterministic にする。
  - framework 補強の有無に依らず同一 render contract を保つ。
- MUST NOT:
  - filesystem write を行わない。
  - summary、stream routing、exit code を決めない。
  - parse / analyze / frameworks を再実行しない。
- OUT OF SCOPE:
  - PNG / SVG など text 以外の renderer。
  - artifact naming。
  - warning の non-zero 昇格判断。

## 境界
- Always:
  - seam owner は `render`。
  - upstream shared handoff は `ParsedModule[]`, `ModuleIndex`, `SelectedClasses`, `SelectedRelations` であり、framework hint は seam-local 補助入力として受ける。
  - downstream shared handoff は success path の `DiagramModel` と `PlantUmlText`、failure path の `RenderFailureSignal` である。
- Ask:
  - grouping / alias rule を deterministic 契約から変えたい場合。
  - PlantUML 以外の出力形式を追加したい場合。
- Never:
  - summary counter を render で計算しない。
  - output path や collision suffix を render で決めない。
  - framework warning をもとに diagram shape を恣意的に変えない。

## 制約
- 同一 `RenderReadyModel` から同一 `PlantUmlText` を生成する決定性を守る。
- AST-only / read-only guardrail を壊さず、artifact write や console 出力を持たない。
- 生成不能時は failure 材料を downstream report へ渡し、自分で exit を決めない。

## 受け入れ条件
- AC-001:
  - Actor:
    - CLI 利用者
  - Given:
    - 同一内容の `RenderReadyModel` が 2 回与えられる。
  - When:
    - render を実行する。
  - Then:
    - `PlantUmlText.text` の順序、grouping、label、alias は一致する。
  - 観測点:
    - stable order / grouping / labels review。
- AC-002:
  - Actor:
    - CLI 利用者
  - Given:
    - SQLAlchemy / Pydantic 補強を含む `RenderReadyModel` がある。
  - When:
    - render を実行する。
  - Then:
    - framework 補強済み relation / decoration が diagram shape に反映される。
  - 観測点:
    - render-ready handoff review。
- AC-003:
  - Actor:
    - CLI 利用者
  - Given:
    - recoverable diagnostics を含むが `RenderReadyModel` から diagram を構築できない入力がある。
  - When:
    - render を実行する。
  - Then:
    - `RenderFailureSignal(failure_reason, diagnostics, class_count, relation_count, partial_diagram_present)` が report へ handoff され、render 自身は exit や stream routing を決めない。
  - 観測点:
    - failure handoff schema review。

## 例外・エッジケース
- EC-001:
  - 条件:
    - 同名 class が複数あり alias が必要である。
  - 期待:
    - alias 割当規則は deterministic である。
  - 観測点:
    - alias rule review。
- EC-002:
  - 条件:
    - relation がなく class だけの図になる。
  - 期待:
    - empty diagram ではない限り diagram は構築され、class-only document を返せる。
  - 観測点:
    - class-only render review。
- EC-003:
  - 条件:
    - `RenderReadyModel` の整合が崩れ、diagram を構築できない。
  - 期待:
    - `RenderFailureSignal.failure_reason=diagram_unbuildable_after_recovery` と、render が保有する diagnostics / class_count / relation_count / partial_diagram_present を report へ渡す。
  - 観測点:
    - failure handoff review。

## 未確定事項
- なし:
  - render baseline row は initiative canonical docs で確定済みである。
