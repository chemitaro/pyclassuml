---
種別: 要件定義書（Epic）
ID: "epic-00004"
タイトル: "Framework Render Report"
関連GitHub: ["#4"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
親: ["init-00001"]
---

# epic-00004 Framework Render Report — 要件定義（WHAT / WHY）

## 目的（Initiative との紐づき）
- initiative goal / metric:
  - `epic-core-analysis` が確定した relation / class selection を受け、M2 で framework best-effort、deterministic render、artifact / summary / exit policy を downstream 責務として成立させる。
  - `app` が M3 で stitcher に徹するために、SQLAlchemy / Pydantic 補強、PlantUML text、reporting contract を先に閉じる。
- この epic が提供する能力:
  - `frameworks.sqlalchemy-enrich` による `Mapped[T]` と `relationship("T")` の best-effort relation 補強。
  - `frameworks.pydantic-enrich` による forward reference の best-effort relation 補強。
  - `render.uml-document` による deterministic な `DiagramModel` / `PlantUmlText` 構築。
  - `report.artifact-summary-exit-policy` による `.puml` artifact、summary、stream routing、failure taxonomy、strict / warn exit policy の固定。

## ユースケース
- happy path:
  - 利用者が SQLAlchemy や Pydantic を含む Python プロジェクトに対して `generate` / `diff` を実行したとき、core-analysis だけでは拾えない framework relation が best-effort で図へ反映される。
  - 利用者が同一入力を繰り返し解析したとき、同一順序・同一 grouping・同一 label の PlantUML text と summary を観測できる。
- exception / operation scenario:
  - framework 解決が曖昧または不能でも、既知の class / relation で図を構成できる限り `warn` で継続し、warning を summary へ残せる。
  - recoverable diagnostics の結果として図を構成できない場合や artifact write が失敗した場合は、`report` owner で degraded failure / hard failure として non-zero を返せる。

## Epic requirements
- E-RQ-001:
  - `iss-00016-frameworks-sqlalchemy-enrich` は、`analyze.relationship-and-selection` と `parse.module-parse-and-index` を upstream に、SQLAlchemy `Mapped[T]` / `relationship("T")` の best-effort relation 補強を `frameworks` owner で固定する。
- E-RQ-002:
  - `iss-00017-frameworks-pydantic-enrich` は、`analyze.relationship-and-selection` と `parse.module-parse-and-index` を upstream に、Pydantic forward reference の best-effort relation 補強を `frameworks` owner で固定する。
- E-RQ-003:
  - `iss-00018-render-uml-document` は、core selection と framework hint を upstream に、authoritative な `RenderReadyModel` の合成 owner と deterministic な `DiagramModel` / `PlantUmlText` の render owner を同一 seam 内で固定する。
- E-RQ-004:
  - `iss-00019-report-artifact-summary-exit-policy` は、`render.uml-document` と upstream 各 seam の diagnostics / counters を集約し、`.puml` write、summary、stream routing、failure taxonomy、strict / warn exit policy decision table、generate 時の zero `ChangedClassInventory` handoff を `report` owner で固定する。
- E-RQ-005:
  - この epic は、shared DTO と seam-local handoff の境界を明示し、initiative `design.md` の whole-system source を上書きせずに downstream dependency rationale を補う。
- E-RQ-006:
  - framework 補強、render、report はいずれも AST-only / read-only / deterministic guardrail を壊さず、target repository import 実行、Git write、core traversal 再実行を行わない。

## Epic acceptance criteria
- E-AC-001:
  - Given:
    - `epic-core-analysis` で確定した `ParsedModule[]`, `SelectedClasses`, relation inventory, `ChangedClassInventory` がある。
  - When:
    - epic / issue requirement と design をレビューする。
  - Then:
    - `frameworks -> render -> report` の依存順、owner、shared DTO、seam-local handoff が一意に説明できる。
  - 観測点:
    - initiative `plan.md` の issue baseline table、epic design の seam contract table、issue design の handoff 節。
- E-AC-002:
  - Given:
    - SQLAlchemy / Pydantic fixture と deterministic render fixture がある。
  - When:
    - `iss-00016` から `iss-00018` の contract を適用する。
  - Then:
    - `fx-framework-sqlalchemy-basic`、`fx-framework-pydantic-forward-ref`、stable order / grouping / label review により、framework 補強と deterministic render の下限が観測できる。
  - 観測点:
    - issue requirement の AC / EC、issue design の verification mapping。
- E-AC-003:
  - Given:
    - warning-only success、degraded success、diagram unbuildable、output write failure、`--output` 未指定 / 指定の scenario がある。
  - When:
    - `iss-00019` の contract を適用する。
  - Then:
    - artifact naming、suffix collision、stdout/stderr routing、failure taxonomy、strict / warn exit policy の owner が `report` に閉じている。
  - 観測点:
    - summary counter review、failure taxonomy review、command transcript / filesystem observation。

## スコープ
- MUST:
  - `iss-00016` から `iss-00019` までの 4 seams を対象にする。
  - framework best-effort の下限、deterministic PlantUML、artifact / summary / exit policy を M2 exit seams として固定する。
  - initiative baseline row の owner / upstream dependency / completion / canonical verification を epic 粒度で束ね直す。
- MUST NOT:
  - whole-system boundary を initiative `design.md` から取り上げて再定義しない。
  - `parse` / `analyze` の core logic や `app` の end-to-end stitching をこの epic で肩代わりしない。
  - issue `plan.md` や `report.md` の execution detail をこの turn の対象にしない。
- OUT OF SCOPE:
  - framework registry 化や plugin architecture。
  - PNG / SVG など PlantUML 以外の renderer。
  - `app.generate-wiring` / `app.diff-wiring` の command orchestration。

## 境界
- Always:
  - `frameworks` は core traversal frontier を広げず、既知の relation / class selection の best-effort 補強だけを行う。
  - `render` は text generation だけを担い、filesystem write や exit code 決定を持たない。
  - `report` は artifact / summary / exit policy の唯一の owner とし、parse / analyze / render を再実行しない。
  - issue docs は initiative baseline row を具体化し、initiative docs の canonical split を壊さない。
- Ask:
  - SQLAlchemy / Pydantic support の範囲を prototype baseline から広げたい場合。
  - render で grouping / alias の意味論を変更し、既存 determinism 契約へ影響する場合。
  - failure taxonomy を `report` 以外の seam に分散させたい場合。
- Never:
  - framework 解決不能時に推測で relation を追加しない。
  - `render` が summary counter や stream routing を決めない。
  - `report` が diagram shape や framework relation を補正しない。

## 非機能要件
- performance:
  - 同一 `RenderReadyModel`、同一 config、同一 Git 基準では、render 順序、artifact naming、summary 表現が決定的であること。
- reliability / consistency:
  - framework 補強不能、diagram unbuildable、output write failure の owner と degraded / hard failure 境界が曖昧でないこと。
  - strict / warn の最終 exit policy が `report` に閉じ、他 seam が独自に non-zero を決めないこと。
- security:
  - target repository import 実行、対象コード書き換え、Git write を行わないこと。
- operations:
  - summary で class / relation / warning / ignore / scope 起因 counter と failure reason を観測できること。
  - artifact path と stream routing の違いを利用者が一意に追えること。

## 依存 / 影響範囲
- impacted components:
  - `frameworks`
  - `render`
  - `report`
  - downstream consumer として `app.generate-wiring`, `app.diff-wiring`
- external dependency:
  - filesystem artifact write
  - stdout / stderr
- compatibility:
  - initiative `requirement.md`, `design.md`, `plan.md`
  - `20260416t113919z-note-pyclassuml-architecture-v5.md`
  - `20260417t152718z-note-pyclassuml-prototype-roadmap-bridge-v1.md`
  - `epic-00003-core-analysis` の issue baseline と dependency order

## 未確定事項
- なし:
  - M2 で固定すべき framework / render / report の baseline は initiative canonical docs で確定済みである。
