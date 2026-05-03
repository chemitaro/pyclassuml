---
種別: 計画書（Epic）
ID: "epic-00004"
タイトル: "Framework Render Report"
関連GitHub: ["#4"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
依存: ["requirement.md", "design.md"]
親: ["init-00001"]
---

# epic-00004 Framework Render Report — 計画（Issues / Order）

## この計画で閉じる E-RQ / E-AC
- E-RQ:
  - `E-RQ-001` から `E-RQ-006` までを、4 issue の seam owner 単位で閉じる。
- E-AC:
  - `E-AC-001` から `E-AC-003` を、framework fixture / deterministic render review / command transcript と filesystem observation で閉じる。

## Issue 分割方針
- slicing principle:
  - `1 issue = 1 seam` を守り、framework hint 抽出、render、report を混ぜない。
  - initiative `plan.md` の baseline row をそのまま issue 単位へ落とし、epic は dependency rationale と integration checkpoint を補う。
- exceptions:
  - `frameworks.sqlalchemy-enrich` と `frameworks.pydantic-enrich` は同一 owner `frameworks` 配下だが、evidence source・warning 条件・verification fixture が異なるため別 issue にする。
  - `report.artifact-summary-exit-policy` は upstream 参照が多いが、artifact / summary / exit policy の owner を 1 つに保つため単独 issue にする。

## Issue 一覧（順序 / tranche 付き）
- `iss-00016-frameworks-sqlalchemy-enrich`
  - 目的:
    - `Mapped[T]` と `relationship("T")` の best-effort relation 補強を固定する。
  - deliverable:
    - SQLAlchemy evidence を `RenderReadyModel.relations` / `class_decorations` へ反映する hint contract。
  - tranche:
    - `M2-a`
  - closes:
    - `E-RQ-001`
  - depends on:
    - `iss-00012-parse-module-parse-and-index`
    - `iss-00014-analyze-relationship-and-selection`
- `iss-00017-frameworks-pydantic-enrich`
  - 目的:
    - forward reference の best-effort relation 補強を固定する。
  - deliverable:
    - Pydantic annotation evidence を `RenderReadyModel.relations` へ反映する hint contract。
  - tranche:
    - `M2-a`
  - closes:
    - `E-RQ-002`
  - depends on:
    - `iss-00012-parse-module-parse-and-index`
    - `iss-00014-analyze-relationship-and-selection`
- `iss-00018-render-uml-document`
  - 目的:
    - framework hint と core selection から authoritative な `RenderReadyModel` を合成し、deterministic な `DiagramModel` / `PlantUmlText` を固定する。
  - deliverable:
    - `RenderReadyModel` composition owner と stable order / grouping / labels / alias rule を含む render contract。
  - tranche:
    - `M2-b`
  - closes:
    - `E-RQ-003`
  - depends on:
    - `iss-00016-frameworks-sqlalchemy-enrich`
    - `iss-00017-frameworks-pydantic-enrich`
- `iss-00019-report-artifact-summary-exit-policy`
  - 目的:
    - `.puml` artifact、summary、stream routing、strict / warn exit policy を固定する。
  - deliverable:
    - `RunSummary` / `CommandResult` と artifact naming / failure taxonomy / outcome decision table / generate-mode zero inventory contract。
  - tranche:
    - `M2-c`
  - closes:
    - `E-RQ-004`
    - `E-RQ-005`
    - `E-RQ-006`
  - depends on:
    - `iss-00008-config-context-resolve`
    - `iss-00009-targets-explicit-target-normalize`
    - `iss-00011-targets-diff-target-normalize`
    - `iss-00012-parse-module-parse-and-index`
    - `iss-00013-analyze-traversal`
    - `iss-00014-analyze-relationship-and-selection`
    - `iss-00015-changed-class-inventory`
    - `iss-00016-frameworks-sqlalchemy-enrich`
    - `iss-00017-frameworks-pydantic-enrich`
    - `iss-00018-render-uml-document`

## dependency rationale
- `iss-00016` と `iss-00017` は同じ upstream を持つため `M2-a` で並行に固めやすい。
- `iss-00018` は framework hint を前提にするため `M2-b` に置き、framework support なしの暫定 renderer を作らない。
- `iss-00019` は artifact / summary / exit policy の owner であり、render output と upstream counter source の両方に依存するので最後に置く。
- `config` と `targets` を `iss-00019` の依存へ残すのは、artifact path resolve と summary counter source が M1 / M2 前段契約に依存するためである。

## 統合チェックポイント
- G1 decomposition review:
  - 4 issue の owner / upstream / downstream / verification が initiative `plan.md` の baseline row と一致している。
- G2 integration readiness:
  - `frameworks.*` の hint が `render.uml-document` へ、`render` の output が `report` へ、shared DTO と seam-local handoff を混同せずに接続できる。
- G3 rollout/docs impact:
  - issue requirement / design が initiative whole-system source を上書きせず、epic が dependency rationale だけを補っている。
- G9 final epic spec review:
  - M2 exit seams として framework 下限、deterministic render、artifact / summary / exit policy が reviewer に一意に説明できる。

## 品質ゲート
- test:
  - `iss-00016` と `iss-00017` は fixture review を持つ。
  - `iss-00018` は deterministic render review を持つ。
  - `iss-00019` は command transcript と filesystem / stream observation を持つ。
- observability:
  - warning diagnostics、summary counters、failure reason、artifact path の owner が露出している。
- migration:
  - `frameworks` / `render` / `report` が core-analysis や app orchestration を侵食していない。
- docs:
  - issue `plan.md` / `report.md` を触らずに、requirement / design だけで baseline row が読める。

## ロールアウト / docs impact
- rollout order:
  - `M2-a` で framework best-effort の 2 issues を固める。
  - `M2-b` で deterministic render を固める。
  - `M2-c` で artifact / summary / exit policy を閉じ、M2 exit とする。
- contract / docs refresh:
  - この turn では epic `requirement.md` / `design.md` / `plan.md` と issue `requirement.md` / `design.md` のみを更新する。
  - issue `plan.md` は execution 直前に具体化し、issue `report.md` は execution / verification で更新する。

## Issue readiness contract
- Issue に要求する最低条件:
  - upstream / downstream が initiative baseline row と一致する。
  - shared DTO と seam-local handoff が明示されている。
  - framework hint / render output / report output のどこに authoritative SoR があるかが読める。
  - canonical verification が fixture review か command transcript か区別できる。

## final exit contract
- E-AC closure:
  - `E-AC-001` から `E-AC-003` が issue requirement / design と epic integration checkpoint で閉じている。
- integration / rollout complete:
  - `frameworks -> render -> report` の dependency chain が M3 `app.*-wiring` の前提として利用可能である。
- docs impact resolved:
  - epic / issue docs が placeholder なしで読め、issue `plan.md` 未更新でも execution handoff の前提を壊していない。

## 依存 / ブロッカー
- D-001:
  - `report.artifact-summary-exit-policy` の summary counter source は M1 / M2 upstream docs に依存するため、initiative canonical docs と矛盾させないことが必須である。
- D-002:
  - issue `plan.md` は execution 直前まで詳細化しないため、この epic plan が sequencing と exit seam の epic-level planning source になる。

## 未確定事項
- なし:
  - ordering と integration checkpoint は initiative canonical docs から十分に確定できる。
