---
種別: 設計書（Issue）
ID: "iss-00013"
タイトル: "Analyze Traversal"
関連GitHub: ["#13"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
依存: ["requirement.md"]
親: ["epic-00003", "init-00001"]
---

# iss-00013 Analyze Traversal — 設計（HOW）

## seam position
- upstream / prerequisite:
  - `iss-00012-parse-module-parse-and-index`
- downstream / dependent:
  - `iss-00014-analyze-relationship-and-selection`
  - `report.artifact-summary-exit-policy`
- seam responsibility:
  - parsed module 群から command-neutral な reachable frontier を確定する唯一の owner。

### UML（module / dependency）
```plantuml
@startuml
top to bottom direction

rectangle "parse\nParsedModule[] + ModuleIndex" as parse
rectangle "config\nExecutionContext + AnalysisConfig" as config
rectangle "analyze.traversal\nDependencyTraverser" as traversal
rectangle "DependencyGraph" as graph
rectangle "TraversalObservations\n(seam-local)" as obs
rectangle "selection / report" as downstream

parse --> traversal
config --> traversal
traversal --> graph
traversal --> obs
graph --> downstream
obs --> downstream
@enduml
```

## インターフェース契約
- input:
  - `ParsedModule[]`
  - `ModuleIndex`
  - `ExecutionContext(package_root, scope_root)`
  - `AnalysisConfig(mode, traversal depth)`
- output:
  - shared DTO:
    - `DependencyGraph(reachable_files, edges)`
  - seam-local handoff:
    - `TraversalObservations`
      - `seed_project_relative_paths`
      - `scope_stop_count`
      - `traversal_limit_reached`
      - `reachable_file_count`
- invariant:
  - `DependencyGraph` は internal reachable files だけを持つ。
  - frontier 初期集合は `ModuleIndex.seed_project_relative_paths` に対応する parsed module から決定する。
  - `TraversalObservations` は report summary と strict failure 昇格の材料になる。
  - traversal は parse 済み情報だけを使い、raw filesystem を再探索しない。
  - hop semantics は seed module を `0`、seed module の direct import を `1` とし、`depth=0` では seed module のみ、`depth=1` では direct import までを reachable とする。
  - candidate の stop reason は `package_root` 外 -> `scope_root` 外 -> depth 超過の順に評価し、最初に成立した理由だけを authoritative に記録する。

## 主要フロー
1. `ModuleIndex.seed_project_relative_paths` に対応する parsed module を frontier の初期集合にする。
2. import candidate を module path 単位で引き当て、`package_root` 外 -> `scope_root` 外 -> depth 超過の順に採否を評価する。
3. reachable file と edge を `DependencyGraph` に追加する。
4. seed provenance、scope stop、探索上限到達を `TraversalObservations` に記録する。
5. graph と observations を downstream へ渡す。

## data / handoff
- shared DTO:
  - `DependencyGraph` は relation extraction の唯一の frontier source とする。
- seam-local:
  - `TraversalObservations` は seed provenance と summary / diagnostics 素材を含む handoff であり、initiative canonical DTO へは昇格させない。
- downstream consumption:
  - `analyze.relationship-and-selection` は `DependencyGraph` と `TraversalObservations.seed_project_relative_paths` を使って relation 抽出対象 module と起点 file full-display rule を確定する。
  - `report` は `scope_stop_count` と `reachable_file_count` を summary 素材として参照する。

## テスト戦略
- Unit:
  - depth=0/1。
  - `package_root` 境界。
  - `scope_root` 境界。
  - traversal limit error。
- Integration:
  - `ParsedModule[] / ModuleIndex -> DependencyGraph` handoff。
  - `TraversalObservations` の counter carry。
- Verification:
  - `fx-traversal-depth-matrix`
  - `fx-traversal-package-boundary`
  - `fx-traversal-scope-stop`
  - `fx-traversal-limit-reached`
  - `fx-analyze-changed-unreachable`

## non-goals
- relation extraction と class selection。
- changed class inventory 算出。
- framework best-effort 補強。

## リスク / 注意点
- frontier 判断を relation extraction 側へ漏らすと owner が二重化する。
- traversal limit を report 側で判断すると analyze owner の失敗責務が崩れる。
- changed file semantics をここで扱い始めると `ChangedClassInventory` 独立 seam の意味が失われる。
