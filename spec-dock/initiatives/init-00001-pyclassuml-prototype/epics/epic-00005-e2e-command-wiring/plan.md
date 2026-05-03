---
種別: 計画書（Epic）
ID: "epic-00005"
タイトル: "E2E Command Wiring"
関連GitHub: ["#5"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
依存: ["requirement.md", "design.md"]
親: ["init-00001"]
---

# epic-00005 E2E Command Wiring — 計画（Issues / Order）

## この計画で閉じる E-RQ / E-AC
- E-RQ:
  - `E-RQ-001` から `E-RQ-006` を、`app.generate-wiring` と `app.diff-wiring` の 2 issue で閉じる。
- E-AC:
  - `E-AC-001` から `E-AC-004` を、issue requirement / design と command transcript review で閉じる。

## Issue 分割方針
- slicing principle:
  - `1 issue = 1 command wiring seam` を守り、`generate` と `diff` の front-stage 差分だけを分ける。
  - post-`TargetSet` pipeline は issue 間で共通 guardrail として揃え、`app` が downstream logic owner にならないようにする。
  - shared DTO の producer / consumer は initiative `plan.md` と upstream epics に従い、`app` は transport owner に留める。
- exceptions:
  - `generate` は diff 起点がないため、empty changed-file context を analyze へ渡す transport だけを app-local rule として持つ。
  - `diff` は `vcs` / `targets.diff` 由来の actual changed-file context と current-state / untracked warning を transport するため、front-stage 差分の説明量が `generate` より多い。

## Issue 一覧（順序 / tranche 付き）
1. `iss-00020-app-generate-wiring`
   - 目的:
     - explicit target 起点の `generate` を end-to-end で成立させ、M3 の共通 pipeline stitching 基準を先に固定する。
   - deliverable:
     - `config -> targets.explicit -> parse -> analyze -> frameworks -> render -> report` の canonical order と、empty changed-file context transport rule。
   - tranche:
     - `M3-a`
   - closes:
     - `E-RQ-001`
     - `E-RQ-003`
     - `E-RQ-004`
     - `E-RQ-005`
     - `E-RQ-006`
   - depends on:
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
2. `iss-00021-app-diff-wiring`
   - 目的:
     - diff 起点の front-stage context を common pipeline に接続し、current-state / untracked 差を user-visible に保ったまま `diff` を end-to-end で成立させる。
   - deliverable:
     - `config -> vcs -> targets.diff -> parse -> analyze -> frameworks -> render -> report` の canonical order と、actual changed-file context / observations transport rule。
   - tranche:
     - `M3-b`
   - closes:
     - `E-RQ-002`
     - `E-RQ-003`
     - `E-RQ-004`
     - `E-RQ-005`
     - `E-RQ-006`
   - depends on:
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

## dependency rationale
- `iss-00020` を先に置くのは、`generate` が最小の front-stage 差分で common pipeline stitching を説明できるためである。
- `iss-00021` は `vcs` / `targets.diff` / changed-file context transport を追加で扱うが、post-`TargetSet` order は `iss-00020` と同一でなければならない。
- 2 issue を同じ epic に残すことで、`app` が report policy や analysis policy を抱え込まず、front-stage 差分だけが command 固有であることを review しやすくする。

## 統合チェックポイント
- G1 decomposition review:
  - 2 issue の owner / upstream / downstream / canonical verification が initiative `plan.md` の baseline row と一致している。
- G2 integration readiness:
  - `generate` と `diff` の front-stage 差分だけで post-`TargetSet` pipeline が共通であることを issue design から説明できる。
- G3 rollout/docs impact:
  - `cli` usage error owner と `report` summary / result owner が issue docs で崩れていない。
  - issue `plan.md` / `report.md` を触らずに M3 の sequencing と transport rule が読める。
- G9 final epic spec review:
  - `.puml` artifact、summary stream、exit code、current-state / untracked 差のすべてが M3 exit seams として reviewer に一意に説明できる。

## 品質ゲート
- test:
  - `iss-00020` は generate transcript と filesystem / stdout observation を持つ。
  - `iss-00021` は diff transcript と warning / counter observation を持つ。
  - 両 issue は auto naming / `--output` path resolution passthrough を verification に含む。
- observability:
  - `TargetSet.observations`、`ChangedClassInventory`、upstream diagnostics の transport path が issue docs に明示されている。
- migration:
  - `app` が target normalization、graph 解析、render、report policy を再実装していない。
- docs:
  - initiative `requirement.md` / `design.md` / `plan.md`、architecture v5、roadmap bridge、upstream epics と矛盾しない。

## ロールアウト / docs impact
- rollout order:
  - `M3-a` で `generate` の minimal stitching を固める。
  - `M3-b` で `diff` の front-stage 差分 transport を追加し、epic を閉じる。
- contract / docs refresh:
  - この turn では epic `requirement.md` / `design.md` / `plan.md` と issue `requirement.md` / `design.md` のみを更新する。
  - issue `plan.md` は execution 直前に具体化し、issue `report.md` は execution / verification で更新する。

## Issue readiness contract
- Issue に要求する最低条件:
  - upstream / downstream が initiative baseline row と一致する。
  - post-`TargetSet` common pipeline guardrail が requirement と design の双方に現れている。
  - usage error owner と non-usage result owner の split が requirement と design の双方に現れている。
  - transport する DTO / observations / diagnostics が `report` の summary source と接続している。

## final exit contract
- E-AC closure:
  - `E-AC-001` から `E-AC-004` が issue docs と epic integration checkpoint で閉じている。
- integration / rollout complete:
  - `generate` と `diff` の दोनों command が、front-stage 差分だけを除いて共通 pipeline へ接続できる。
- docs impact resolved:
  - placeholder が消え、M3 の sequencing / transport / owner split を epic / issue docs だけで読める。

## 依存 / ブロッカー
- D-001:
  - `iss-00019-report-artifact-summary-exit-policy` が `CommandResult` / `RunSummary` の owner であることが前提であり、ここが揺れると M3 全体の owner split が崩れる。
- D-002:
  - `iss-00015-changed-class-inventory` の shared DTO contract が generate / diff 両 command の summary semantics に影響するため、empty / actual changed-file context transport を docs で明示する必要がある。

## 未確定事項
- なし:
  - sequencing と integration checkpoint は initiative canonical docs と upstream epics から十分に確定できる。
