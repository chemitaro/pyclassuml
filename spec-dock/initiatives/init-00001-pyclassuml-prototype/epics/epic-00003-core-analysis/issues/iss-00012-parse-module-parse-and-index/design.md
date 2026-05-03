---
種別: 設計書（Issue）
ID: "iss-00012"
タイトル: "Parse Module Parse And Index"
関連GitHub: ["#12"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
依存: ["requirement.md"]
親: ["epic-00003", "init-00001"]
---

# iss-00012 Parse Module Parse And Index — 設計（HOW）

## seam position
- upstream / prerequisite:
  - `iss-00008-config-context-resolve`
  - `iss-00009-targets-explicit-target-normalize`
  - `iss-00011-targets-diff-target-normalize`
- downstream / dependent:
  - `iss-00013-analyze-traversal`
  - `iss-00014-analyze-relationship-and-selection`
  - `frameworks.sqlalchemy-enrich`
  - `frameworks.pydantic-enrich`
  - `report.artifact-summary-exit-policy`
- seam responsibility:
  - `TargetSet` を AST parse 済み module 集合へ変換し、後続 seam の lookup 材料を揃える唯一の owner。

### UML（module / dependency）
```plantuml
@startuml
top to bottom direction

rectangle "targets\nTargetSet" as targets
rectangle "config\nExecutionContext + AnalysisConfig" as config
rectangle "parse\nAstIndexer" as parse
rectangle "ParsedModule[]" as parsed
rectangle "ModuleIndex\n(seam-local)" as index
rectangle "analyze / frameworks / report" as downstream

targets --> parse
config --> parse
parse --> parsed
parse --> index
parsed --> downstream
index --> downstream
@enduml
```

## インターフェース契約
- input:
  - `TargetSet(seed_files, observations)`
  - `ExecutionContext(project_root, package_root, scope_root)`
  - `AnalysisConfig(ignore, mode)`
- output:
  - shared DTO:
    - `ParsedModule[]`
  - seam-local handoff:
    - `ModuleIndex`
      - `module_path -> ParsedModule`
      - `project_relative_file_path -> module_path`
      - `class_id -> owning module`
      - `seed_project_relative_paths`
      - import candidate lookup table
  - diagnostics:
    - syntax error
    - candidate ignore
- invariant:
  - import 実行を行わない。
  - 起点 file から始まる deterministic order を保つ。
  - `ModuleIndex` は `analyze` が raw filesystem を再探索しなくても frontier 判定できる最小 lookup と seed provenance を持つ。
  - parse は `TargetSet.seed_files` から始めて、ignore を通過した Python source candidate を再帰的に materialize し、downstream `analyze` が raw source reread や lazy parse を行わずに reachability を判定できる parse closure を作る。

## 主要フロー
1. `TargetSet.seed_files` を deterministic order で巡回する。
2. file ごとに AST parse を行い、module path、imports、class 定義、diagnostics を `ParsedModule` に格納する。
3. import candidate を列挙し、`project_root` 相対 ignore / default ignore を適用して parse universe 候補を絞る。
4. ignore を通過した candidate file が未 parse なら同じ手順で再帰的に AST parse し、その candidate から見つかった import candidate も同様に処理する。
5. 新規 candidate がなくなった時点で parse closure を確定し、`TargetSet.seed_files` を `project_root` relative path に正規化して `ModuleIndex.seed_project_relative_paths` に保持する。
6. `ParsedModule[]` と `ModuleIndex` をまとめて downstream に渡す。

## data / handoff
- shared DTO:
  - `ParsedModule[]` は initiative canonical DTO として `analyze` / `frameworks` / `report` が参照できる。
- seam-local:
  - `ModuleIndex` は class lookup、module path reverse lookup、candidate file 判定だけを担う parse 内部 handoff であり、initiative canonical docs へは昇格させない。
- downstream consumption:
  - `analyze.traversal` は、parse closure 済み `ParsedModule[]` と `ModuleIndex` だけを使って frontier expansion を行う。
  - `analyze.relationship-and-selection` と `frameworks.*` は `ParsedModule[]` から import / class / annotation 情報を読む。
  - `report` は syntax diagnostics と candidate ignore 件数だけを summary 素材として読む。

## テスト戦略
- Unit:
  - `ParsedModule` の構築。
  - syntax error 発生時の diagnostics carry。
  - candidate file への ignore 適用。
- Integration:
  - `TargetSet -> ParsedModule[] / ModuleIndex` handoff。
  - `ModuleIndex` を使った class / module lookup review。
- Verification:
  - `fx-parse-syntax-error`
  - `fx-parse-ignored-dependency-candidate`

## non-goals
- reachability frontier 決定。
- relation extraction。
- changed class inventory。

## リスク / 注意点
- `ModuleIndex` を shared DTO にすると `model` が肥大化する。
- syntax error 時に module 全体を無条件破棄すると、strict/warn の degradation 範囲が曖昧になる。
- ignore 適用を traversal 側に遅らせると parse owner の件数計測と責務境界が崩れる。
