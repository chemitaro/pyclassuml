---
種別: 実装計画書（Issue）
ID: "iss-00017"
タイトル: "Frameworks Pydantic Enrich"
関連GitHub: ["#17"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md"]
親: ["epic-00004", "init-00001"]
---

# iss-00017 Frameworks Pydantic Enrich — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001: direct quoted forward reference `field: "T"` から selected internal relation hint を追加する。
  - AC-002: quoted subscript forward reference `list["T"]` / `Optional["T"]` / `Union["T", "U"]` から relation hint を追加する。
- EC:
  - EC-001: 曖昧な forward reference は warning/no relation。
  - EC-002: 未解決 forward reference は warning/no relation。
  - EC-003: selection contract 外の class は warning/no relation。
  - EC-004: selected/non-selected mixed collision は ambiguity warning/no relation。
- 制約:
  - AST-only / read-only / deterministic。
  - traversal frontier、artifact write、summary、exit code 決定を行わない。
  - parse には framework-neutral quoted annotation evidence だけを追加し、Pydantic relation 解釈を漏らさない。

## マイルストーン一覧
- M1 parse evidence:
  - 対象: `ClassReference` の quoted annotation evidence と class base evidence 抽出。
  - exit: parse unit tests が通り、既存 SQLAlchemy parse evidence tests が regress しない。
- M2 Pydantic enrichment:
  - 対象: `frameworks.pydantic` seam-local hint extractor。
  - exit: direct quoted / quoted subscript / warning edge / dedupe tests が通る。
- M3 review/QA/finalization:
  - 対象: code review、QA review、full test、SpecDock validation、report、commit。
  - exit: reviewer/QA pass、`pytest` full pass、`spec-dock validate` pass。

## 実装順序の根拠
- quoted annotation evidence が無ければ Pydantic seam は direct `field: "T"` を観測できない。
- Pydantic seam は `SelectedClasses` を resolver boundary として使うため、class selection は変更せず hint だけを返す。
- render 反映は downstream `iss-00018` の owner なので、この issue では seam-local hint と diagnostics までを完成条件にする。

## レビュー / QA ゲート方針
- SG1 spec review:
  - timing: 実装着手前。
  - scope: requirement/design/plan/report が実装可能で、quoted annotation evidence 追加が owner 境界を壊していないこと。
  - commit gate: pass まで review loop を回し、pass 後に `report.md` を更新して docs commit を作成する。
- RG1 implementation review:
  - timing: M1/M2 実装と最小 verification 後。
  - scope: seam boundary、DTO reuse、deterministic order、warning diagnostics、selection 非侵食、triple dedupe。
  - commit gate: pass まで review loop を回し、pass 後に `report.md` を更新して implementation commit を作成する。
- QG1 QA review:
  - timing: RG1 と並行または直後。
  - scope: AC/EC coverage、regression coverage、full suite risk。
  - commit gate: pass まで test loop を回し、pass 後に `report.md` を更新して implementation commit に含める。

## 実行ルール（全ステップ共通）
- 各 step は 1 つの観測可能な振る舞いを単位とする。
- failing test は iteration ごとに 1 本ずつ進める。
- `Green` は最小実装、`Refactor` は green 維持を前提とする。
- docs impact が `none` でなければ `S90` を実行する。
- reviewer verdict と QA verdict は `report.md` に残す。
- 各 stage gate は `pass` まで回す。
- no-op の場合のみ `report.md` に理由を残し、commit を省略できる。

## 実装ステップ

### S01 — quoted annotation evidence
- target:
  - parse seam の generic quoted annotation evidence と class base evidence 抽出。
- design refs:
  - `design.md` の `parse/model evidence contract`。
- step boundary:
  - Pydantic relation 解釈、diagnostics、selection 解決は行わない。

#### B1 — direct quoted annotation
- files:
  - `src/pyclassuml/parse/indexer.py`
  - `tests/parse/test_module_parse_and_index.py`

##### I1 — `field: "T"`
- Red:
  - failing test: `class A: child: "B"` が `annotation_string/annotation/B` evidence を返す。
- Green:
  - minimum implementation: class body annotation AST から direct quoted string target を抽出する。
- Refactor:
  - deterministic sort/dedupe を既存 `ClassReference` sort にそろえる。

#### B1b — class base evidence
- files:
  - `src/pyclassuml/parse/indexer.py`
  - `tests/parse/test_module_parse_and_index.py`

##### I1 — direct class base evidence
- Red:
  - failing tests:
    - `class A(BaseModel): ...` と `class A(pydantic.BaseModel): ...` が `class_base/base/BaseModel` / `class_base/base/pydantic.BaseModel` evidence を返す。
    - `class A(CustomBase): ...` も `class_base/base/CustomBase` evidence を返し、parse が Pydantic base 名だけを特別扱いしていないことを固定する。
- Green:
  - minimum implementation: class definition direct base AST から base name を抽出する。
- Refactor:
  - parse は base が Pydantic 由来かを import 実行で確認しない。

#### B2 — quoted subscript annotation
- files:
  - `src/pyclassuml/parse/indexer.py`
  - `tests/parse/test_module_parse_and_index.py`

##### I1 — `list["T"]` / `Optional["T"]` / `Union["T", "U"]`
- Red:
  - failing test: quoted subscript annotation が `annotation_string/<owner>/T` evidence を返し、typing wrapper 自体は target にならない。
- Green:
  - minimum implementation: existing annotation walk で quoted string constants を quoted evidence として抽出する。
- Refactor:
  - SQLAlchemy 用 `annotation_subscript` evidence を壊さない。

#### B3 — nested body exclusion
- files:
  - `src/pyclassuml/parse/indexer.py`
  - `tests/parse/test_module_parse_and_index.py`

##### I1 — nested function / async function / nested class / lambda body
- Red:
  - failing test: nested function / async function / nested class / lambda body 内の quoted annotation は outer class の `annotation_string` evidence にならない。
- Green:
  - minimum implementation: quoted annotation evidence の walker が nested executable/class bodies に入らない。
- Refactor:
  - existing SQLAlchemy evidence の exclusion behavior と揃える。

### S02 — Pydantic enrichment hints
- target:
  - `frameworks.pydantic` seam-local extractor。
- design refs:
  - `design.md` の `主要フロー` と `要件 / 例外 -> verification mapping`。
- step boundary:
  - render shared DTO への合成は行わない。

#### B1 — hint DTO and happy paths
- files:
  - `src/pyclassuml/frameworks/pydantic.py`
  - `src/pyclassuml/frameworks/__init__.py`
  - `tests/frameworks/test_pydantic.py`

##### I1 — direct quoted forward reference
- Red:
  - failing test: selected `A(BaseModel)` から selected `B` への `field: "B"` evidence が relation hint を返す。
- Green:
  - minimum implementation: selected/all-internal resolver と relation hint 生成を追加する。
- Refactor:
  - SQLAlchemy resolver と必要以上に共有せず、重複が問題になった時だけ抽出する。

##### I2 — quoted subscript forward reference
- Red:
  - failing tests:
    - `list["B"]` / `Optional["B"]` evidence が relation hint を返す。
    - `Union["B", "C"]` evidence が uniquely resolved member ごとに relation hint を返す。
- Green:
  - minimum implementation: `annotation_string` evidence を resolver に通す。
- Refactor:
  - evidence kind と relation order を deterministic にする。

##### I3 — non-Pydantic quoted annotation ignore
- Red:
  - failing test: `BaseModel` / `pydantic.BaseModel` base evidence のない source class の quoted annotation は warning なしで no relation。
- Green:
  - minimum implementation: Pydantic eligible source class set を base evidence から作る。
- Refactor:
  - source selection gate と Pydantic eligibility gate の順序を明確にする。

#### B2 — warning and dedupe edges
- files:
  - `src/pyclassuml/frameworks/pydantic.py`
  - `tests/frameworks/test_pydantic.py`

##### I1 — ambiguity / unresolved / selection outside / mixed collision
- Red:
  - failing tests:
    - 複数 internal class が target name に一致すると `pydantic_forward_ref_ambiguous` warning/no relation。
    - target name が一致しないと `pydantic_forward_ref_unresolved` warning/no relation。
    - non-selected internal class にしか一致しない場合は `pydantic_forward_ref_selection_outside` warning/no relation。
    - selected class と non-selected internal class が同じ target name に一致する mixed collision も ambiguity warning/no relation。
- Green:
  - minimum implementation: `OriginSeam.FRAMEWORKS`、`DiagnosticSeverity.WARNING`、`Recoverability.DEGRADED_OUTPUT`、`failure_reason=None` の diagnostics を返す。
- Refactor:
  - warning code/message を stable にする。

##### I2 — relation triple dedupe
- Red:
  - failing tests:
    - existing `SelectedRelations` と同じ source / target / relation_type の hint は追加しない。
    - direct quoted と quoted subscript が同じ relation triple を示す場合、追加 hint は 1 件だけ。
    - `Union["B", "C"]` と他 evidence が重複する場合も source / target / relation_type triple で dedupe する。
- Green:
  - minimum implementation: source / target / relation_type triple の seen set で dedupe する。
- Refactor:
  - deterministic に残す evidence kind を test で固定する。

##### I3 — unselected source boundary
- Red:
  - failing test: source class id が `SelectedClasses` 外の場合、target が selected/internal でも warning なしで no relation。
- Green:
  - minimum implementation: source class id を先に `SelectedClasses` で gate する。
- Refactor:
  - SQLAlchemy seam の boundary behavior と揃える。

### S90 — docs impact resolution / docs refresh
- 対象:
  - issue report。
- 対応:
  - spec review、implementation review、QA review、test/validate 結果、commit を `report.md` に追記する。
  - root docs や user onboarding docs は更新しない。

### S99 — final diff review quality gate
- branch diff scope:
  - `iss-00017` docs、parse quoted annotation evidence、frameworks Pydantic seam、関連 tests。
- required validation:
  - `pytest tests/parse/test_module_parse_and_index.py tests/frameworks/test_pydantic.py`
  - `pytest`
  - `./spec-dock/scripts/spec-dock validate`
  - `rg --files | rg '[A-Z]'` で新規 uppercase path が無いこと。
- reviewer approvals:
  - code-reviewer pass。
  - qa-reviewer pass。
- report update:
  - final diff review verdict / closing evidence / no-op 理由を `./spec-dock/active/issue/report.md` に残す。
- commit expectation:
  - docs commit と implementation commit を分ける。

## 未確定事項
- なし:
  - Pydantic 解釈は `annotation_string` evidence に限定し、non-quoted annotation support は out of scope にする。

## final exit contract
- AC/EC 達成:
  - AC-001/AC-002/EC-001/EC-002/EC-003/EC-004 の tests が通る。
- docs impact resolved:
  - `report.md` に review/test/validate/commit 結果が残る。
- final diff approved:
  - code-reviewer / qa-reviewer pass。
  - full suite と SpecDock validation pass。
