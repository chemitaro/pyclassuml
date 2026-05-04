---
種別: 設計書（Issue）
ID: "iss-00020"
タイトル: "App Generate Wiring"
関連GitHub: ["#20"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
依存: ["requirement.md"]
親: ["epic-00005", "init-00001"]
---

# iss-00020 App Generate Wiring — 設計（HOW）

## seam position
- upstream / prerequisite:
  - `iss-00006-cli-request-bind-and-exit-contract`
  - `iss-00007-model-execution-contracts`
  - `iss-00008-config-context-resolve`
  - `iss-00009-targets-explicit-target-normalize`
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
  - `generate` 実行時の stage invocation order を固定する。
  - empty changed-file context と `TargetSet.observations` を欠落させず downstream へ運ぶ。
  - `report` 由来の `ReportRunResult` を app seam result として返し、その中の `CommandResult` を再構築せず downstream へ transport できる形にする。

### UML（module / dependency）
```plantuml
@startuml
top to bottom direction

rectangle "cli\nCommandRequest(generate)" as cli
rectangle "app.generate-wiring" as app
rectangle "config\nExecutionContext + AnalysisConfig" as config
rectangle "targets.explicit\nTargetSet + TargetObservations" as targets
rectangle "common pipeline\nparse -> analyze -> frameworks -> render -> report" as common
rectangle "report-owned\nReportRunResult\n(CommandResult + stream material)" as result

cli --> app
app --> config
app --> targets
targets --> common
config --> common
common --> result
result --> cli
@enduml
```

## インターフェース契約
- input:
  - `CommandRequest(process_cwd, cli_options.command=generate, cli_options.generate.targets, common options)`
  - `ExecutionContext(execution_cwd, project_root, package_root, scope_root)`
  - `AnalysisConfig(ignore, output, depth, mode, target_python, diff settings)`
  - `TargetSet(seed_files, observations)`
- output:
  - shared DTO:
    - `CommandResult(artifact_path, summary, diagnostics, exit_code)`
  - report seam result:
    - `ReportRunResult(command_result, outcome_kind, stdout_text, stderr_text)`
  - app-local transport:
    - `empty_changed_file_context`
      - `changed_files=[]`
    - `original_target_observations`
      - `TargetSet.observations`
- invariant:
  - usage error は `cli` で止まり、この seam に入らない。
  - `TargetSet` 生成後は generate 専用 branch を追加しない。
  - `ChangedClassInventory` は `analyze` が empty changed-file context から生成する。
  - `TargetSet.observations` は mutate せず `report` まで transport する。
  - `ReportRunResult` は `report` が生成したものをそのまま返し、`app` は summary / exit code / stream material を編集しない。
  - actual process stdout / stderr emission はこの issue の責務ではなく、`ReportRunResult.stdout_text` / `stderr_text` を observation として扱う。
  - config resolution が失敗して `ExecutionContext` / `AnalysisConfig` が得られない場合のみ、`app` は `request.process_cwd` を解決した fallback `ExecutionContext` と default `AnalysisConfig()` を report invocation のために作る。この fallback は summary / exit policy の再実装ではなく、`report` owner の hard failure result を得るための最小入力である。

## 主要フロー
1. `CommandRequest(command=generate)` を受け、`config.context-resolve` を呼ぶ。
2. `ExecutionContext` / `AnalysisConfig` を受け、`targets.explicit-target-normalize` を呼ぶ。
3. `TargetSet` を受けたら empty changed-file context を app-local に固定する。
4. `parse.module-parse-and-index` を呼び、`ParsedModule[]` と `ModuleIndex` を得る。
5. `analyze.traversal`、`analyze.relationship-and-selection`、`ChangedClassInventory` を順に呼び、zero changed-class inventory を含む analyze outputs を得る。
6. `frameworks.sqlalchemy-enrich`、`frameworks.pydantic-enrich`、`render.uml-document`、`report.artifact-summary-exit-policy` を順に呼ぶ。
7. `report` へ渡すとき、`TargetSet.observations` と zero `ChangedClassInventory` を欠落させない。
8. 返ってきた `ReportRunResult` を app result として返す。

## data / handoff
- from `config`:
  - `ExecutionContext` と `AnalysisConfig` を front-stage / downstream 共通入力として使い、`AnalysisConfig.output` と `ExecutionContext.execution_cwd` を mutate せず `report` まで transport する。
- from `targets.explicit-target-normalize`:
  - `TargetSet.seed_files` は parse の唯一入力。
  - `TargetSet.observations` は summary counter source として `report` まで transport する。
- to `ChangedClassInventory`:
  - generate では empty changed-file context を渡し、`analyze` owner で `ChangedClassInventory(class_count=0, changed_files=[])` を生成させる。
- to `report`:
  - `TargetSet.observations`
  - `ChangedClassInventory`
  - upstream diagnostics
  - `DiagramModel`
  - `PlantUmlText`
  - deterministic timestamp

## failure handoff
- config failure:
  - `resolve_context(...)` が diagnostics only を返した場合、`app` は fallback context/config と diagnostics を `write_report(...)` に渡す。
  - `plantuml_text` / `diagram_model` / `target_set` / `changed_class_inventory` は渡さない。
  - expected outcome は `hard_failure`、`artifact_path=None`、`stderr_text` summary、non-zero exit。
- target normalization failure:
  - `normalize_explicit_targets(...)` が diagnostics only を返した場合、config diagnostics と target diagnostics を順序保持で `write_report(...)` に渡す。
  - `TargetSet` 以降の parse/analyze/framework/render は呼ばない。
- traversal / render / output failure:
  - traversal diagnostics、`RenderFailureSignal`、output write failure は `report` の failure taxonomy に任せ、`app` は再分類しない。
- diagnostics aggregation:
  - app は stage order に沿って diagnostics を append する。
  - render failure path では `RenderFailureSignal.diagnostics` が upstream diagnostics を carry し得るため、重複排除は `report` owner に委ねる。

## テスト戦略
- Unit:
  - stage invocation order。
  - empty changed-file context transport。
  - `TargetSet.observations` pass-through。
  - `ReportRunResult` / `CommandResult` 非改変返却。
- Integration:
  - `config -> targets.explicit -> parse -> analyze -> frameworks -> render -> report` の順序確認。
  - zero changed-class inventory が summary source として `report` に届くことの review。
- Verification:
  - generate transcript。
  - filesystem artifact と `stdout_text` summary observation。
  - auto naming / `--output` path resolution passthrough review。
  - failure transcript review。

## non-goals
- diff changed-file collection。
- summary 文面や failure taxonomy の決定。
- output path resolve の再実装。

## リスク / 注意点
- `ChangedClassInventory` を `app` が直接合成すると analyze owner が崩れる。
- `TargetSet.observations` を parse 側で失うと `report` の summary counter semantics が壊れる。
- `CommandResult` を `app` で再構築すると `report` owner と `cli` との契約が崩れる。
