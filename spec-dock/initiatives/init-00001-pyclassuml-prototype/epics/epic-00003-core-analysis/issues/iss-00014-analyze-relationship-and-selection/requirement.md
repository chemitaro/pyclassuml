---
種別: 要件定義書（Issue）
ID: "iss-00014"
タイトル: "Analyze Relationship And Selection"
関連GitHub: ["#14"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
親: ["epic-00003", "init-00001"]
---

# iss-00014 Analyze Relationship And Selection — 要件定義（WHAT / WHY）

## 目的
- 到達済み module 群から UML に必要な relation と表示対象 class を確定し、`frameworks` / `render` が解析ロジックを再実行しない状態を作る。
- 起点 file 全表示と dependency-only class の relation-based selection を `analyze` seam に固定する。

## スコープ
- MUST:
  - reachable module 群から class relation を抽出する。
  - 起点 file 内 class を原則すべて表示対象に含める。
  - 依存先 file では、accepted relation の source または target になった class だけを表示対象へ含める。
  - class selection と relation extraction の結果を downstream へ handoff する。
  - current DTO で観測できる relation endpoint ambiguity は diagnostics として保持する。
  - downstream `report` が再集計なしで使える extracted class / relation counter を handoff する。
- MUST NOT:
  - traversal frontier を拡張しない。
  - changed class 数を算出しない。
  - framework-specific relation をここで補う前提にしない。
- OUT OF SCOPE:
  - SQLAlchemy / Pydantic 補強。
  - PlantUML grouping や label 生成。

## 受け入れ条件
- AC-001:
  - Actor:
    - CLI 利用者
  - Given:
    - 起点 file と依存先 file を含む reachable graph がある。
  - When:
    - relation extraction と class selection を行う。
  - Then:
    - 起点 file 内 class は原則すべて、依存先 class は accepted relation の endpoint になった class だけが選別される。
  - 観測点:
    - `fx-analyze-seed-full-display` scenario。
- AC-002:
  - Actor:
    - CLI 利用者
  - Given:
    - changed file に class はあるが reachable graph に乗らない fixture がある。
  - When:
    - relation extraction と class selection を行う。
  - Then:
    - unreachable changed class は図の表示対象に含めなくてもよく、changed class summary semantics とは分離される。
  - 観測点:
    - `fx-analyze-changed-unreachable` scenario。
- AC-003:
  - Actor:
    - CLI 利用者
  - Given:
    - source/target module がそれぞれ 1 class だけを持つ dependency-only relation fixture がある。
  - When:
    - class selection を行う。
  - Then:
    - 一意解決できた relation endpoint の dependency class が表示対象へ含まれる。
  - 観測点:
    - `fx-analyze-relation-only-dependency` scenario。
- AC-004:
  - Actor:
    - CLI 利用者
  - Given:
    - source/target module class が 0 件または複数件で relation endpoint を一意に決められない reachable module edge がある。
  - When:
    - relation extraction と class selection を行う。
  - Then:
    - warning diagnostics と extracted class / relation counter が `SelectionObservations` を通じて downstream `report` へ渡る。
  - 観測点:
    - `fx-analyze-relation-ambiguity` scenario。

## 例外・エッジケース
- EC-001:
  - 条件:
    - source/target module class が 0 件または複数件で relation endpoint を一意に決められない。
  - 期待:
    - diagnostics を保持し、決め打ちの relation は追加しない。
  - 観測点:
    - relation ambiguity review。
- EC-002:
  - 条件:
    - 起点 file に class があるが、どの relation にも現れない。
  - 期待:
    - 起点 file class は表示対象に残す。
  - 観測点:
    - `fx-analyze-seed-full-display` scenario。
- EC-003:
  - 条件:
    - dependency file に複数 class があり、current DTO では特定の relation endpoint class を一意に決められない。
  - 期待:
    - warning diagnostics を保持し、relation と dependency class selection は追加しない。
    - dependency file 全 class や relation を持たない sibling class を推測で追加しない。
  - 観測点:
    - dependency-only selection boundary review。

## 制約
- class selection の owner は `analyze.relationship-and-selection` とする。
- `frameworks` は既存 relation の補強だけを行い、この issue の selection contract を上書きしない。
- selection 順序と relation 順序は deterministic にする。

## 未確定事項
- なし:
  - relation extraction / class selection の baseline row は initiative canonical docs で確定済みである。
  - wildcard import / re-export の詳細な warning は、現行 `ParsedModule` が import token evidence を保持しないため、この issue では扱わない。将来 parse DTO に structured import reference を追加する issue で扱う。
