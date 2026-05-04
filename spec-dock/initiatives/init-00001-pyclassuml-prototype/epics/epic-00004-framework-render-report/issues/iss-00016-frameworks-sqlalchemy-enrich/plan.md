---
種別: 実装計画書（Issue）
ID: "iss-00016"
タイトル: "Frameworks SQLAlchemy Enrich"
関連GitHub: ["#16"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md"]
親: ["epic-00004", "init-00001"]
---

# iss-00016 Frameworks SQLAlchemy Enrich — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001: `Mapped[T]` から選択済み内部 class relation hint を追加する。
  - AC-002: `relationship("T")` を一意解決できる場合だけ relation hint を追加する。
- EC:
  - EC-001: 曖昧な string relation は warning/no relation。
  - EC-002: 未解決の `Mapped[T]` / `relationship("T")` は warning/no relation。
  - EC-003: selection contract 外の class は warning/no relation。
  - EC-004: selected/non-selected mixed collision は ambiguity warning/no relation。
- 制約:
  - AST-only / read-only / deterministic。
  - traversal frontier、Git diff、artifact write、exit code 決定を行わない。
  - parse には framework-neutral evidence だけを追加し、SQLAlchemy relation 解釈を漏らさない。

## マイルストーン一覧
- M1 parse/model evidence:
  - 対象: `ClassReference` と `ParsedModule.class_references`、parse evidence 抽出。
  - exit: model/parse unit test が通り、既存 parse/analyze tests が regress しない。
- M2 SQLAlchemy enrichment:
  - 対象: `frameworks.sqlalchemy` seam-local hint extractor。
  - exit: `Mapped[T]` / `relationship("T")` / warning edge tests が通る。
- M3 review/QA/finalization:
  - 対象: code review、QA review、full test、SpecDock validation、report、commit。
  - exit: reviewer/QA pass、`pytest` full pass、`spec-dock validate` pass。

## 実装順序の根拠
- parse/model evidence が無ければ SQLAlchemy seam は annotation / call site を観測できない。
- SQLAlchemy seam は `SelectedClasses` を resolver boundary として使うため、class selection は変更せず hint だけを返す。
- render 反映は downstream `iss-00018` の owner なので、この issue では seam-local hint と diagnostics までを完成条件にする。

## レビュー / QA ゲート方針
- SG1 spec review:
  - timing: 実装着手前。
  - scope: requirement/design/plan/report が実装可能で、parse evidence 追加が owner 境界を壊していないこと。
  - commit gate: pass まで review loop を回し、pass 後に `report.md` を更新して docs commit を作成する。
- RG1 implementation review:
  - timing: M1/M2 実装と最小 verification 後。
  - scope: seam boundary、DTO validation、deterministic order、warning diagnostics、selection 非侵食。
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

### S01 — framework-neutral class reference evidence
- target:
  - `ClassReference`
  - `ParsedModule.class_references`
  - parse seam の class body evidence 抽出。
- design refs:
  - `design.md` の `parse/model evidence contract`。
- step boundary:
  - SQLAlchemy relation 解釈、diagnostics、selection 解決は行わない。

#### B1 — model contract
- files:
  - `src/pyclassuml/model/contracts.py`
  - `src/pyclassuml/model/__init__.py`
  - `tests/model/test_contracts.py`

##### I1 — ClassReference DTO
- Red:
  - failing test: `ClassReference` を public import でき、invalid field を拒否する。
- Green:
  - minimum implementation: frozen dataclass と export を追加する。
- Refactor:
  - shared validation helper を既存 style にそろえる。

#### B2 — parse evidence extraction
- files:
  - `src/pyclassuml/parse/indexer.py`
  - `tests/parse/test_module_parse_and_index.py`

##### I1 — generic annotation-subscript evidence
- Red:
  - failing test: `class A: b: Owner[B]` と `Owner[list[B]]` が `annotation_subscript/Owner/B` evidence を返す。
- Green:
  - minimum implementation: class body annotation AST から owner name と target names を抽出する。
- Refactor:
  - nested class の source id 生成を `_extract_classes` と共有可能な形に整える。

##### I2 — generic string-call evidence
- Red:
  - failing test: `class A: b = link_to("B")` が `call_string_arg/link_to/B` evidence を返す。
- Green:
  - minimum implementation: class body assignment/call AST から callee name と最初の文字列引数を抽出する。
- Refactor:
  - deterministic sort/dedupe を固定する。

### S02 — SQLAlchemy enrichment hints
- target:
  - `frameworks.sqlalchemy` seam-local extractor。
- design refs:
  - `design.md` の `主要フロー` と `要件 / 例外 -> verification mapping`。
- step boundary:
  - render shared DTO への合成は行わない。

#### B1 — hint DTO and happy paths
- files:
  - `src/pyclassuml/frameworks/sqlalchemy.py`
  - `src/pyclassuml/frameworks/__init__.py`
  - `tests/frameworks/test_sqlalchemy.py`

##### I1 — Mapped relation
- Red:
  - failing test: selected `A` から selected `B` への `Mapped[B]` evidence が relation hint を返す。
- Green:
  - minimum implementation: selected short-name resolver と relation hint 生成を追加する。
- Refactor:
  - duplicate selected relation と duplicate evidence の重複排除を固定する。

##### I2 — relationship string relation
- Red:
  - failing test: selected `A` から selected `B` への `relationship("B")` evidence が relation hint を返す。
- Green:
  - minimum implementation: `call_string_arg/relationship` evidence を resolver に通す。
- Refactor:
  - evidence kind と relation order を deterministic にする。

#### B2 — warning edges
- files:
  - `src/pyclassuml/frameworks/sqlalchemy.py`
  - `tests/frameworks/test_sqlalchemy.py`

##### I1 — ambiguity / unresolved / selection outside
- Red:
  - failing tests:
    - 複数 selected class が target name に一致すると warning/no relation。
    - target name が一致しないと warning/no relation。
    - non-selected internal class にしか一致しない場合も warning/no relation。
    - selected class と non-selected internal class が同じ target name に一致する mixed collision も warning/no relation。
- Green:
  - minimum implementation: `OriginSeam.FRAMEWORKS`、`DiagnosticSeverity.WARNING`、`Recoverability.DEGRADED_OUTPUT`、`failure_reason=None` の diagnostics を返す。
- Refactor:
  - warning code/message を stable にする。
  - warning code は ambiguity=`sqlalchemy_relation_ambiguous`、unresolved=`sqlalchemy_relation_unresolved`、selection outside=`sqlalchemy_relation_selection_outside` を assertion で固定する。

### S90 — docs impact resolution / docs refresh
- 対象:
  - issue report。
- 対応:
  - spec review、implementation review、QA review、test/validate 結果、commit を `report.md` に追記する。
  - root docs や user onboarding docs は更新しない。

### S99 — final diff review quality gate
- branch diff scope:
  - `iss-00016` docs、parse/model evidence、frameworks SQLAlchemy seam、関連 tests。
- required validation:
  - `pytest tests/model/test_contracts.py tests/parse/test_module_parse_and_index.py tests/frameworks/test_sqlalchemy.py`
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
  - `ParsedModule` の不足は、この issue 内の framework-neutral `ClassReference` 追加で解決する。

## final exit contract
- AC/EC 達成:
  - AC-001/AC-002/EC-001/EC-002/EC-003/EC-004 の tests が通る。
- docs impact resolved:
  - `report.md` に review/test/validate/commit 結果が残る。
- final diff approved:
  - code-reviewer / qa-reviewer pass。
  - full suite と SpecDock validation pass。
