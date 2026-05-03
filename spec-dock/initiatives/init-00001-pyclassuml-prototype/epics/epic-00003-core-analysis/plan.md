---
種別: 計画書（Epic）
ID: "epic-00003"
タイトル: "Core Analysis"
関連GitHub: ["#3"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
依存: ["requirement.md", "design.md"]
親: ["init-00001"]
---

# epic-00003 Core Analysis — 計画（Issues / Order）

## この計画で閉じる E-RQ / E-AC
- E-RQ:
  - `E-RQ-001` から `E-RQ-006` を、4 issue の seam owner 単位で閉じる。
- E-AC:
  - `E-AC-001` から `E-AC-003` を、issue requirement / design と canonical verification scenario の整合で満たす。

## Issue 分割方針
- slicing principle:
  - `1 issue = 1 seam` を守り、`parse` と `analyze` の責務を feature 横断で混ぜない。
  - shared DTO は initiative `plan.md` の baseline table に従い、必要以上の DTO 昇格は避ける。
  - `frameworks` / `render` が必要とする材料は、core-analysis では DTO か seam-local handoff として明示する。
- exceptions:
  - `ChangedClassInventory` は `analyze` owner のまま独立 issue にし、selection semantics と summary semantics を分離する。

## Issue 一覧（順序 / tranche 付き）
1. `iss-00012-parse-module-parse-and-index`
   - 目的:
     - import 非実行 AST parse、`ParsedModule[]`、dependency candidate ignore を固定する。
   - deliverable:
     - `ParsedModule[]` shared DTO と `ModuleIndex` seam-local handoff。
   - tranche:
     - `M2-a`
   - closes:
     - `E-RQ-001`
     - `E-RQ-006`
   - depends on:
     - `iss-00008-config-context-resolve`
     - `iss-00009-targets-explicit-target-normalize`
     - `iss-00011-targets-diff-target-normalize`
2. `iss-00013-analyze-traversal`
   - 目的:
     - depth / package / scope 境界つき reachability を固定する。
   - deliverable:
      - `DependencyGraph` shared DTO と `TraversalObservations(seed_project_relative_paths, scope_stop_count, traversal_limit_reached, reachable_file_count)` seam-local handoff。
   - tranche:
     - `M2-a`
   - closes:
     - `E-RQ-002`
     - `E-RQ-006`
   - depends on:
     - `iss-00012-parse-module-parse-and-index`
3. `iss-00014-analyze-relationship-and-selection`
   - 目的:
     - relation extraction、起点ファイル全表示、relation-based selection を固定する。
   - deliverable:
      - `SelectedClasses` shared DTO と `SelectedRelations` / `SelectionObservations(extracted_class_count, extracted_relation_count, warning_diagnostics: Diagnostic[])` seam-local handoff。
   - tranche:
     - `M2-b`
   - closes:
     - `E-RQ-003`
     - `E-RQ-005`
   - depends on:
     - `iss-00013-analyze-traversal`
4. `iss-00015-changed-class-inventory`
   - 目的:
     - changed file 内 class 定義を authoritative に数える summary semantics を固定する。
   - deliverable:
      - `ChangedClassInventory(class_count, changed_files)` shared DTO。
   - tranche:
     - `M2-b`
   - closes:
     - `E-RQ-004`
     - `E-RQ-005`
   - depends on:
      - `iss-00012-parse-module-parse-and-index`
      - `iss-00011-targets-diff-target-normalize`

## dependency rationale
- `iss-00012` を先頭に置くのは、`ParsedModule[]` と diagnostics owner が曖昧なまま traversal / relation を定義しないため。
- `iss-00013` を `iss-00012` の直後に置くのは、package / scope / depth の frontier owner を `analyze` に固定するため。
- `iss-00014` は traversal 済み frontier がないと relation-based selection の meaning が揺れるため、その後に置く。
- `iss-00015` は parse 済み class 定義だけで閉じる独立 seam だが、relation / selection との意味分離を読みやすくするため M2-b の最後に置く。

## what gets fixed in M2
- import 非実行 AST parse と syntax degradation 範囲。
- dependency candidate への `project_root` 相対 ignore / default ignore 適用。
- depth / package / scope 境界つき reachability。
- 起点ファイル class 全表示、dependency-only class の relation-based selection。
- changed file 内 class inventory と user-visible summary count semantics。

## 統合チェックポイント
- G1 decomposition review:
  - 4 issue の owner / upstream / observable behavior が initiative `plan.md` の issue baseline table と一致している。
- G2 integration readiness:
  - `parse` / `analyze` の downstream handoff だけで `frameworks` / `render` / `report` が要求する入力を説明できる。
- G3 rollout/docs impact:
  - epic docs が initiative whole-system canonical を上書きせず、M2 の dependency rationale だけを補完している。
- G9 final epic spec review:
  - syntax degradation、traversal semantics、selection semantics、changed class semantics が review 可能な粒度で固定されている。

## 品質ゲート
- test:
  - `fx-parse-syntax-error`, `fx-parse-ignored-dependency-candidate`, `fx-traversal-depth-matrix`, `fx-traversal-package-boundary`, `fx-traversal-scope-stop`, `fx-traversal-limit-reached`, `fx-analyze-seed-full-display`, `fx-analyze-relation-only-dependency`, `fx-analyze-relation-ambiguity`, `fx-analyze-changed-unreachable`, `fx-analyze-changed-file-without-class`, `fx-analyze-changed-syntax-error-join-miss` に対応する verification mapping が issue docs にある。
- observability:
  - parse / traversal / selection / changed inventory それぞれの counter / diagnostics owner が明示されている。
- migration:
  - `frameworks` / `render` / `report` の責務を侵食していない。
- docs:
  - initiative `requirement.md` / `design.md` / `plan.md` / v5 / roadmap bridge と矛盾しない。

## ロールアウト / docs impact
- rollout order:
  - `M2-a` で parse と traversal を固定する。
  - `M2-b` で relation / selection と changed class inventory を固定する。
- contract / docs refresh:
  - issue `plan.md` は execution 直前に issue 単位で具体化する。
  - issue `report.md` は execution / verification の記録として更新する。

## Issue readiness contract
- Issue に要求する最低条件:
  - upstream / downstream が initiative baseline table と一致する。
  - shared DTO と seam-local handoff のどちらかが明示されている。
  - deterministic / AST-only / read-only 制約が requirement と design の双方に現れている。
  - downstream `frameworks` / `report` が依存する counter / diagnostics owner が分かる。

## final exit contract
- E-AC closure:
  - parse / traversal / selection / changed class inventory の acceptance と edge case が issue docs で閉じている。
- integration / rollout complete:
  - `epic-framework-render-report` が core-analysis の handoff に依存して着手可能である。
- docs impact resolved:
  - whole-system canonical は initiative docs に残し、epic docs は M2 の sequencing と dependency rationale の補助正本になっている。

## 依存 / ブロッカー
- D-001:
  - `epic-foundation-contracts` の `TargetSet`, `ExecutionContext`, `AnalysisConfig` 契約が前提である。
- D-002:
  - issue `plan.md` は execution 直前まで詳細化しないため、本書が M2 内 sequencing と tranche 管理の epic-level planning source になる。

## 未確定事項
- なし:
  - dependency sequence と M2 exit の定義は initiative canonical docs から十分に導出できる。
