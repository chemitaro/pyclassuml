---
種別: 実装計画書（Issue）
ID: "iss-00018"
タイトル: "Render UML Document"
関連GitHub: ["#18"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md"]
親: ["epic-00004", "init-00001"]
---

# iss-00018 Render UML Document — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001 deterministic PlantUML text。
  - AC-002 framework 補強済み relation の diagram 反映と `class_decorations=()` の保持。
  - AC-003 diagram unbuildable failure handoff。
- EC:
  - EC-001 deterministic alias allocation。
  - EC-002 class-only document success。
  - EC-003 `diagram_unbuildable_after_recovery` failure signal。
- 制約:
  - render seam は pure transform とし、filesystem write / summary / stream routing / exit policy を持たない。
  - parse / analyze / frameworks を再実行しない。

## マイルストーン一覧
- M1 shared failure DTO:
  - 対象: `RenderFailureSignal` contract。
  - exit: model public import surface と validation test が通る。
- M2 render-ready composition:
  - 対象: parse/analyze/framework hints から `RenderReadyModel` を合成する。
  - exit: selected relation と SQLAlchemy/Pydantic hint relation が deterministic に merged / deduped される。
- M3 diagram + PlantUML serialization:
  - 対象: `RenderReadyModel -> DiagramModel -> PlantUmlText`。
  - exit: grouping / alias / class / relation order が snapshot で固定される。
- M4 failure handoff:
  - 対象: empty/unbuildable input の `RenderFailureSignal`。
  - exit: render は exit / stream / summary を決めず、failure material だけ返す。

## 実装順序の根拠
- `RenderFailureSignal` は requirement/design にある downstream handoff だが、現行 `model` には未実装なので最初に contract を固定する。
- `RenderReadyModel` 合成を先に固定し、その同一入力を `DiagramModel` と `PlantUmlText` で消費する。
- framework hint は `iss-00016` / `iss-00017` の seam-local output を render entry で初めて authoritative relation inventory に合成する。
- failure path は success path と同じ validation boundary を通して、図を構成できない場合だけ返す。

## ステップ一覧
- S01:
  - 観測可能な振る舞い: `RenderFailureSignal` が public DTO として validation される。
  - closes: AC-003, EC-003。
  - review gate: model contract review。
- S02:
  - 観測可能な振る舞い: `compose_render_ready_model(...)` が selected classes / relations / framework hints を deterministic に合成する。
  - closes: AC-002。
  - review gate: render-ready handoff review。
- S03:
  - 観測可能な振る舞い: `build_diagram_model(...)` と `render_plantuml_text(...)` が class id 由来の stable grouping / alias / label / relation text を返す。
  - closes: AC-001, EC-001, EC-002。
  - review gate: PlantUML snapshot review。
- S04:
  - 観測可能な振る舞い: `render_uml_document(...)` が success path と failure path を discriminated result として返す。
  - closes: AC-003, EC-003, constraints。
  - review gate: failure handoff review。
- S90:
  - docs impact: issue docs の report のみ。
- S99:
  - final diff review / code-reviewer / qa-reviewer / validation。

## 要件 ↔ ステップ対応
- AC-001 -> S03, S04。
- AC-002 -> S02, S03。
- AC-003 -> S01, S04。
- EC-001 -> S03。
- EC-002 -> S03。
- EC-003 -> S01, S04。
- constraints -> S02, S03, S04, S99。

## レビュー / QA ゲート方針
- SG1 spec review:
  - timing: requirement/design/plan/report の contract repair 後、実装前。
  - scope: scope / constraints / AC/EC / step mapping / downstream owner 境界。
  - commit gate: pass まで review loop を回し、pass 後に docs commit を作成する。
- RG1 implementation review:
  - timing: S01-S04 実装と unit tests が green になった後。
  - scope: render seam owner、DTO 境界、deterministic ordering、no filesystem / no exit policy。
  - commit gate: pass まで review loop を回し、pass 後に `report.md` を更新してコミットする。
- QG1 QA review:
  - timing: targeted / full validation 後。
  - scope: AC/EC coverage、snapshot stability、failure handoff、framework hint integration。
  - commit gate: pass まで test loop を回し、pass 後に `report.md` を更新してコミットする。

## 実行ルール（全ステップ共通）
- 実装は active issue を基準に進める。
- `src` / `tests` の変更は dev-coder に委任する。
- main は issue docs の contract / report を更新する。
- render seam は `src/pyclassuml/render/` 配下へ追加する。新規 path は lowercase のみ。
- public import が必要な DTO / function は package `__init__.py` から export する。
- failing test は step ごとに最小単位で追加し、Green 後に必要範囲だけ refactor する。
- `uv.lock` / `__pycache__` / `.pyc` は残さない。

## 実装ステップ

### S01 — render failure signal contract
- target:
  - `src/pyclassuml/model/contracts.py`
  - `src/pyclassuml/model/__init__.py`
  - `tests/model/test_contracts.py`
- design refs:
  - `design.md` output shared DTO。
- step boundary:
  - `RenderFailureSignal(failure_reason, diagnostics, class_count, relation_count, partial_diagram_present)` を immutable DTO として追加する。
  - `failure_reason` は `FailureReason.DIAGRAM_UNBUILDABLE_AFTER_RECOVERY` を許容し、diagnostics は existing `Diagnostic` validation に従う。
  - class_count / relation_count は non-negative int、partial_diagram_present は bool として validation する。

#### I1 — DTO red / green
- Red:
  - `RenderFailureSignal` public import / construction / invalid value tests を追加する。
- Green:
  - model DTO と export を追加する。
- Refactor:
  - existing validation helpers を再利用する。

### S02 — render-ready composition
- target:
  - `src/pyclassuml/render/__init__.py`
  - `src/pyclassuml/render/document.py`
  - `tests/render/test_document.py`
- design refs:
  - `design.md` major flow 1-2。
- step boundary:
  - `compose_render_ready_model(parsed_modules, module_index, selected_classes, selected_relations, sqlalchemy_hints, pydantic_hints)` を追加する。
  - selected relation と framework `added_relations` を `(source, target, relation_type)` triple で dedupe し、deterministic sort する。
  - diagnostics は `ParsedModule[].diagnostics`、`SqlalchemyEnrichmentHints.warning_diagnostics`、`PydanticEnrichmentHints.warning_diagnostics` を deterministic に carry する。
  - grouping_keys は selected class id の module path 部分（`<module_path>:<qualname>` の `<module_path>`）から deterministic に作る。
  - selected class id が `ParsedModule[].classes` または `ModuleIndex.class_to_module` に存在しない場合は phantom class を描かず、render diagnostic `render_selected_class_missing` を追加し、S04 で failure path へ送る。
  - 現行 `ParsedModule` には member 定義 DTO がないため、members は `()` として保持し、member extraction / rendering は先回り実装しない。
  - 現行 SQLAlchemy / Pydantic hints は relation と diagnostics のみを返すため、class_decorations は `()` として保持する。

#### I1 — core + framework relation merge
- Red:
  - selected relation + SQLAlchemy hint + Pydantic hint が 1 つの `RenderReadyModel.relations` に stable order で入る test。
  - `ParsedModule.diagnostics` と framework warning diagnostics が `RenderReadyModel.diagnostics` に stable order で carry される test。
  - missing selected class id が `render_selected_class_missing` diagnostic を作り、success diagram へ進まない test。
- Green:
  - relation merge / dedupe / diagnostics carry を実装する。
- Refactor:
  - sort key と triple extraction を private helper に分離する。

### S03 — diagram model and PlantUML text
- target:
  - `src/pyclassuml/render/document.py`
  - `tests/render/test_document.py`
- design refs:
  - `design.md` major flow 3-5。
- step boundary:
  - `build_diagram_model(render_ready_model)` と `render_plantuml_text(diagram_model)` を追加する。
  - alias は class id の deterministic index から `c001`, `c002`, ... を割り当てる。
  - containers は grouping key を stable sort し、PlantUML package として出力する。
  - `DiagramModel` には class-to-container parallel mapping を追加せず、serializer は各 `ClassId` の module path 部分から container key を導出する。
  - class line は quoted label と alias を使う。
  - relation line は alias 間の `-->` と relation label を使う。
  - class-only input は success とする。

#### I1 — deterministic snapshot
- Red:
  - 同一 input の 2 回 render が完全一致する snapshot test。
  - 同名 class ids の alias allocation test。
  - 複数 module path の classes が module path package に grouping される snapshot test。
- Green:
  - diagram builder と text serializer を実装する。
- Refactor:
  - PlantUML escaping / label helper を private helper に分離する。

#### I2 — class-only document
- Red:
  - relation なし class-only document が `@startuml` / class line / `@enduml` を返す test。
- Green:
  - relation optional path を実装する。

### S04 — success / failure document entry
- target:
  - `src/pyclassuml/render/document.py`
  - `tests/render/test_document.py`
- design refs:
  - `design.md` major flow 5-6。
- step boundary:
  - `RenderDocumentResult(diagram_model, plantuml_text, failure_signal)` を render seam-local dataclass として追加する。
  - `render_uml_document(...)` を追加し、success では diagram + text、failure では `RenderFailureSignal` のみを返す。
  - empty selected classes は failure とし、`failure_reason=diagram_unbuildable_after_recovery`、class_count / relation_count / partial_diagram_present を handoff する。
  - relation endpoint が `RenderReadyModel.classes` に存在しない場合は diagram unbuildable failure とし、`origin_seam=render` の diagnostic を追加する。
  - missing selected class diagnostic がある場合も diagram unbuildable failure とし、phantom class は描かない。
  - `RenderFailureSignal.class_count` / `relation_count` は `RenderReadyModel` 合成後、diagram build 前の authoritative count とする。
  - `RenderFailureSignal.partial_diagram_present` は `class_count > 0` のとき `true`、empty selected class failure では `false` とする。
  - `RenderFailureSignal.diagnostics` は `RenderReadyModel.diagnostics` を deterministic に carry し、render が検出した failure cause diagnostic を追加できる。
  - render は filesystem write / summary / exit code を一切決めない。

#### I1 — failure handoff
- Red:
  - empty selected classes が `RenderFailureSignal(failure_reason=diagram_unbuildable_after_recovery, class_count=0, relation_count=0, partial_diagram_present=false)` を返し、text を作らない test。
  - missing relation endpoint が `class_count > 0`, deduped `relation_count`, `partial_diagram_present=true`, carried `ParsedModule` / framework diagnostics + render diagnostic を返す test。
  - missing selected class が `render_selected_class_missing` diagnostic を carry し、`PlantUmlText` を返さない test。
- Green:
  - failure handoff を実装する。
- Refactor:
  - success/failure invariant validation を `RenderDocumentResult` に閉じる。

### S90 — docs impact resolution
- 対象:
  - issue report。
- 対応:
  - 実装内容、検証結果、review verdict、残 scope (`iss-00019` report artifact write/summary/exit policy) を記録する。

### S99 — final diff review quality gate
- branch diff scope:
  - docs commit 以降の `iss-00018` 差分。
- required validation:
  - `uv run --with pytest pytest tests/model/test_contracts.py tests/render/test_document.py -q`
  - `uv run --with pytest pytest -q`
  - `./spec-dock/scripts/spec-dock validate`
  - `git diff --check`
  - `rg --files | rg '[A-Z]'`
  - generated file cleanup check。
- reviewer approvals:
  - code-reviewer pass。
  - qa-reviewer pass。
- report update:
  - final diff review verdict / closing evidence / no-op 理由を `./spec-dock/active/issue/report.md` に残す。
- commit expectation:
  - docs commit と implementation commit を分ける。

## 未確定事項
- なし:
  - RenderFailureSignal は requirement/design にある output contract を満たすため、この issue で public DTO として追加する。

## final exit contract
- AC/EC 達成:
  - S01-S04 の tests と review pass で確認する。
- docs impact resolved:
  - `report.md` を更新する。
- final diff approved:
  - code-reviewer / qa-reviewer pass と validation pass を report に残す。
