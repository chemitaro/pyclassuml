---
種別: 要件定義書（Issue）
ID: "iss-00007"
タイトル: "Model Execution Contracts"
関連GitHub: ["#7"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
親: ["epic-00002", "init-00001"]
---

# iss-00007 Model Execution Contracts — 要件定義（WHAT / WHY）

## 目的
- initiative `plan.md` の issue baseline table に列挙された DTO 群の最小 field / invariant を固定し、stage 間 handoff の正本にする。
- `model` を shared dumping ground にせず、front-stage から downstream までの contract 面積を最小に保つ。

## スコープ
  - MUST:
  - 次の DTO の最小 field / invariant を固定する。
    - `CommandRequest(process_cwd, cli_options.command, cli_options.cwd, cli_options.config, cli_options.project_root, cli_options.package_root, cli_options.scope_root, cli_options.output, cli_options.ignore, cli_options.depth, cli_options.strict, cli_options.target_python, cli_options.generate.targets, cli_options.diff.base_ref, cli_options.diff.current_state, cli_options.diff.include_untracked)`
    - `ExecutionContext(execution_cwd, project_root, package_root, scope_root)`
    - `AnalysisConfig(ignore, output, depth, mode, target_python, diff.current_state, diff.include_untracked)` where `depth = null | int >= 0`, `mode = warn | strict`, and `target_python = null | 3.<minor>`
    - `TargetObservations(ignored_seed_candidate_count, diff_scope_excluded_count)`
    - `TargetSet(seed_files, observations)` where `seed_files` are Python source files only
    - `ParsedModule(module_path, imports, classes, diagnostics)`
    - `DependencyGraph(reachable_files, edges)`
    - `SelectedClasses(class_ids)`
    - `ChangedClassInventory(class_count, changed_files)`
    - `RenderReadyModel(classes, members, relations, class_decorations, grouping_keys, diagnostics)`
    - `DiagramModel(containers, rendered_classes, rendered_relations, aliases)`
    - `PlantUmlText(text)`
    - `Diagnostic(severity, code, message, origin_seam, recoverability, failure_reason?)` where failure diagnostic では `failure_reason` 必須、warning-only diagnostic では `null`
    - `RunSummary(counters, failure_reason)`
    - `CommandResult(artifact_path, summary, diagnostics, exit_code)`
  - nullability、owner、producer / consumer、carry すべき failure / diagnostics 情報を review 可能にする。
- MUST NOT:
  - algorithm、stream routing、Git / filesystem I/O を `model` に持ち込まない。
  - issue baseline にない convenience field を rationale なしで追加しない。
  - `CommandResult.exit_code` から stdout / stderr を選ぶ実処理、または stream target 決定 policy を実装しない。
- OUT OF SCOPE:
  - file split、serializer、永続化。
  - seam-local handoff で十分な内部構造の標準化。
  - `report` / `cli` が行う stream routing の振る舞い検証。

## 受け入れ条件
- AC-001:
  - Actor:
    - 実装者 / reviewer
  - Given:
    - initiative canonical docs がある。
  - When:
    - shared contract をレビューする。
  - Then:
    - 上記 DTO 群について、必須 field、producer / consumer、carry する情報が一意に説明できる。
  - 観測点:
    - DTO 一覧、field / invariant 表。
- AC-002:
  - Actor:
    - 実装者 / reviewer
  - Given:
    - `process_cwd`、4 roots、diagnostics、summary、artifact path を伴う pipeline がある。
  - When:
    - handoff rule を確認する。
  - Then:
    - `process_cwd -> execution_cwd`、diagnostic origin / recoverability / failure_reason、summary / exit_code carry が明文化されている。
    - stream routing は `report` / `cli` owner の後続契約であり、この issue は `CommandResult.exit_code` を routing 判定に使える形で carry するところまでを固定している。
  - 観測点:
    - `CommandRequest`, `ExecutionContext`, `Diagnostic`, `CommandResult` の contract。

## 例外・エッジケース
- EC-001:
  - 条件:
    - failure path で `.puml` artifact が生成されない。
  - 期待:
    - `CommandResult` は `summary`, `diagnostics`, `exit_code` を必須に保ち、`artifact_path` は absent を許容できる。
  - 観測点:
    - nullability review。
- EC-002:
  - 条件:
    - changed file 内クラス数と UML 掲載クラス数が一致しない。
  - 期待:
    - `ChangedClassInventory` は `SelectedClasses` と別 DTO とし、changed class summary semantics を保持できる。
  - 観測点:
    - DTO 分離 review。
- EC-003:
  - 条件:
    - framework enrich 後に render 用の情報を渡す。
  - 期待:
    - `RenderReadyModel` と `DiagramModel` を分離し、`render` が解析ロジックを再実行しない。
  - 観測点:
    - downstream handoff review。
- EC-004:
  - 条件:
    - `targets` が ignore / diff exclusion count を後段 summary へ運ぶ必要がある。
  - 期待:
    - `TargetObservations` が shared DTO として固定され、`app.*-wiring` が original `TargetSet.observations` を `report` へ引き渡す authoritative transport path が一意に説明できる。
  - 観測点:
    - `TargetObservations` / `TargetSet` / `app.*-wiring` handoff review。

## 制約
- DTO は immutable / reviewable な value object として扱える粒度に留める。
- shared model の owner は field と invariant を固定するが、各 seam の business decision は各 owner に残す。
- initiative plan にない shared DTO を追加する場合は、この issue の正本を更新して rationale を残す。

## 未確定事項
- なし:
  - DTO の最小集合は initiative `plan.md` と v5 で確定済みである。
