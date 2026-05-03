---
種別: 設計書（Issue）
ID: "iss-00014"
タイトル: "Analyze Relationship And Selection"
関連GitHub: ["#14"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
依存: ["requirement.md"]
親: ["epic-00003", "init-00001"]
---

# iss-00014 Analyze Relationship And Selection — 設計（HOW）

## seam position
- upstream / prerequisite:
  - `iss-00013-analyze-traversal`
- downstream / dependent:
  - `frameworks.sqlalchemy-enrich`
  - `frameworks.pydantic-enrich`
  - `render.uml-document`
  - `report.artifact-summary-exit-policy`
- seam responsibility:
  - reachable graph から図に載せる class と relation の core contract を確定する唯一の owner。

### UML（module / dependency）
```plantuml
@startuml
top to bottom direction

rectangle "parse\nParsedModule[] + ModuleIndex" as parse
rectangle "analyze.traversal\nDependencyGraph" as traversal
rectangle "analyze.relationship\nSelector" as relation
rectangle "SelectedClasses" as classes
rectangle "SelectedRelations\n(seam-local)" as rels
rectangle "SelectionObservations\n(seam-local)" as selobs
rectangle "frameworks / render / report" as downstream

parse --> relation
traversal --> relation
relation --> classes
relation --> rels
relation --> selobs
classes --> downstream
rels --> downstream
selobs --> downstream
@enduml
```

## インターフェース契約
- input:
  - `ParsedModule[]`
  - `ModuleIndex`
  - `DependencyGraph(reachable_files, edges)`
  - `TraversalObservations(seed_project_relative_paths, ...)`
- output:
  - shared DTO:
    - `SelectedClasses(class_ids)`
  - seam-local handoff:
    - `SelectedRelations`
      - `source_class_id`
      - `target_class_id`
      - `relation_type`
      - `evidence_kind`
    - `SelectionObservations`
      - `extracted_class_count`
      - `extracted_relation_count`
      - `warning_diagnostics`
- invariant:
  - `TraversalObservations.seed_project_relative_paths` に属する起点 file class は relation の有無に関わらず選択対象に残る。
  - dependency file class は accepted relation の source または target になった class だけを選択し、relation を持たない sibling class は追加しない。
  - `SelectedRelations` は downstream `frameworks` が best-effort 補強できる最小情報だけを持つ。
  - `SelectionObservations` は `report` が class / relation 数を再集計せずに summary へ載せ、かつこの seam 由来 warning diagnostics を受け取るための authoritative handoff である。

## 主要フロー
1. `DependencyGraph.reachable_files` を順に読み、module ごとの class 定義を取得する。
2. import、annotation、base class、member type など parse 済み情報から relation 候補を抽出する。
3. `TraversalObservations.seed_project_relative_paths` に対応する起点 file class を `SelectedClasses` に追加する。
4. accepted relation の endpoint になった dependency class だけを `SelectedClasses` に追加し、その relation を `SelectedRelations` に追加する。
5. ambiguity がある relation は diagnostics を残し、確証のない relation は handoff しない。

## data / handoff
- shared DTO:
  - `SelectedClasses` は render-ready model 構築前の authoritative class selection とする。
- seam-local:
  - `SelectedRelations` は `frameworks` と `render` が消費する relation inventory であり、initiative canonical DTO へは昇格させない。
  - `SelectionObservations` は relation / class counter と `Diagnostic[]` 形式の warning_diagnostics をまとめて carry する seam-local handoff であり、initiative canonical DTO へは昇格させない。
- downstream consumption:
  - `frameworks.*` は `SelectedClasses` と `SelectedRelations` を補強入力に使う。
  - `render` は `frameworks` 非依存でも relation inventory を基礎入力として消費できる。
  - `report` は `SelectionObservations.warning_diagnostics` と counter を user-visible summary / warning count へ反映する。

## テスト戦略
- Unit:
  - seed file full-display。
  - relation-only dependency selection。
  - ambiguity 時の diagnostic。
  - `SelectionObservations` への extracted class / relation counter 記録。
- Integration:
  - `DependencyGraph -> SelectedClasses / SelectedRelations` handoff。
  - `SelectedRelations` を使う downstream 前提 review。
  - `SelectionObservations` と warning diagnostics の report-facing carry review。
- Verification:
  - `fx-analyze-seed-full-display`
  - `fx-analyze-relation-only-dependency`
  - `fx-analyze-changed-unreachable`
  - `fx-analyze-relation-ambiguity`

## non-goals
- changed class count の決定。
- framework-specific relation 補強。
- PlantUML alias / grouping / labels の決定。

## リスク / 注意点
- dependency file 全 class を無条件で追加すると selection contract が崩れる。
- relation inventory を `render` 側で再構築すると core-analysis の owner が失われる。
- changed class semantics をここで混ぜると user-visible summary の meaning が不安定になる。
