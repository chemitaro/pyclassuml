---
種別: 設計書（Issue）
ID: "iss-00021"
タイトル: "App Diff Wiring"
関連GitHub: ["#21"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
依存: ["requirement.md"]
親: ["epic-00005", "init-00001"]
---

# iss-00021 App Diff Wiring — 設計（HOW）

## seam position
- upstream / prerequisite:
  - `iss-00006-cli-request-bind-and-exit-contract`
  - `iss-00007-model-execution-contracts`
  - `iss-00008-config-context-resolve`
  - `iss-00010-vcs-diff-file-collect`
  - `iss-00011-targets-diff-target-normalize`
  - `iss-00012-parse-module-parse-and-index`
  - `iss-00013-analyze-traversal`
  - `iss-00014-analyze-relationship-and-selection`
  - `iss-00015-changed-class-inventory`
  - `iss-00016-frameworks-sqlalchemy-enrich`
  - `iss-00017-frameworks-pydantic-enrich`
  - `iss-00018-render-uml-document`
  - `iss-00019-report-artifact-summary-exit-policy`
- downstream / dependent:
  - `cli`
- seam responsibility:
  - `diff` 実行時の front-stage context と common pipeline の接続順を固定する。
  - actual changed-file context、`TargetSet.observations`、upstream diagnostics を欠落させず downstream へ運ぶ。
  - `report` 由来の `CommandResult` を `cli` へ返す。

### UML（module / dependency）
```plantuml
@startuml
top to bottom direction

rectangle "cli\nCommandRequest(diff)" as cli
rectangle "app.diff-wiring" as app
rectangle "config\nExecutionContext + AnalysisConfig" as config
rectangle "vcs.diff\nChangedFileCollection" as vcs
rectangle "targets.diff\nTargetSet + TargetObservations" as targets
rectangle "common pipeline\nparse -> analyze -> frameworks -> render -> report" as common
rectangle "report-owned\nCommandResult" as result

cli --> app
app --> config
app --> vcs
vcs --> targets
config --> targets
targets --> common
config --> common
common --> result
result --> cli
@enduml
```

## インターフェース契約
- input:
  - `CommandRequest(process_cwd, cli_options.command=diff, cli_options.diff.base_ref/current_state/include_untracked, common options)`
  - `ExecutionContext(execution_cwd, project_root, package_root, scope_root)`
  - `AnalysisConfig(ignore, output, depth, mode, target_python, diff.current_state, diff.include_untracked)`
  - `ChangedFileCollection`
  - `TargetSet(seed_files, observations)`
- output:
  - shared DTO:
    - `CommandResult(artifact_path, summary, diagnostics, exit_code)`
  - app-local transport:
    - `original_changed_file_context`
      - `ChangedFileCollection`
    - `original_target_observations`
      - `TargetSet.observations`
- invariant:
  - usage error は `cli` で止まり、この seam に入らない。
  - `vcs.diff-file-collect` と `targets.diff-target-normalize` が diff-specific front-stage owner であり、`app` はその意味論を再実装しない。
  - `TargetSet` 生成後は diff 専用 branch を追加しない。
  - `ChangedClassInventory` は actual changed-file context から `analyze` が生成する。
  - `TargetSet.observations` は mutate せず `report` まで transport する。
  - `CommandResult` は `report` が生成したものをそのまま返し、`app` は summary / exit code を編集しない。

## 主要フロー
1. `CommandRequest(command=diff)` を受け、`config.context-resolve` を呼ぶ。
2. `ExecutionContext` / `AnalysisConfig` を受け、`vcs.diff-file-collect` を呼ぶ。
3. `ChangedFileCollection` を `targets.diff-target-normalize` に渡し、`TargetSet` を得る。
4. `TargetSet` と actual changed-file context を app-local に保持する。
5. `parse.module-parse-and-index` を呼び、`ParsedModule[]` と `ModuleIndex` を得る。
6. `analyze.traversal`、`analyze.relationship-and-selection`、`ChangedClassInventory` を順に呼び、actual changed-file context に基づく inventory を得る。
7. `frameworks.sqlalchemy-enrich`、`frameworks.pydantic-enrich`、`render.uml-document`、`report.artifact-summary-exit-policy` を順に呼ぶ。
8. `report` へ渡すとき、`TargetSet.observations`、actual `ChangedClassInventory`、upstream diagnostics を欠落させない。
9. 返ってきた `CommandResult` を `cli` に返す。

## data / handoff
- from `config`:
  - `ExecutionContext` と `AnalysisConfig` を front-stage / downstream 共通入力として使い、`AnalysisConfig.output` と `ExecutionContext.execution_cwd` を mutate せず `report` まで transport する。
- from `vcs.diff-file-collect`:
  - actual changed-file context を authoritative source として保持する。
  - `current_state=head` + `include_untracked=true` の no-op warning も transport 対象に含める。
- from `targets.diff-target-normalize`:
  - `TargetSet.seed_files` は parse の唯一入力。
  - `TargetSet.observations.diff_scope_excluded_count` と ignore count は summary source として `report` まで transport する。
- to `ChangedClassInventory`:
  - actual changed-file context を渡し、`analyze` owner で user-visible changed class 数を生成させる。
- to `report`:
  - `TargetSet.observations`
  - `ChangedClassInventory`
  - actual changed-file context から派生した upstream diagnostics
  - `DiagramModel`
  - `PlantUmlText`

## テスト戦略
- Unit:
  - stage invocation order。
  - actual changed-file context transport。
  - `TargetSet.observations` pass-through。
  - `CommandResult` 非改変返却。
- Integration:
  - `config -> vcs -> targets.diff -> parse -> analyze -> frameworks -> render -> report` の順序確認。
  - no-op warning と diff scope exclusion counter が `report` まで届くことの review。
- Verification:
  - diff transcript。
  - filesystem artifact と summary observation。
  - auto naming / `--output` path resolution passthrough review。
  - failure transcript review。

## non-goals
- generate explicit target normalization。
- current-state / untracked の意味論決定そのもの。
- summary 文面や failure taxonomy の決定。

## リスク / 注意点
- diff-specific branch を `TargetSet` 以降へ持ち込むと common pipeline 契約が崩れる。
- `ChangedFileCollection` や `TargetSet.observations` を transport し損ねると summary semantics が壊れる。
- no-op warning や scope exclusion を `app` で握りつぶすと `report` owner の exit policy と矛盾する。
