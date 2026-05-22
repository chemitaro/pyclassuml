---
種別: 実装計画書（Issue）
ID: "iss-00040"
タイトル: "Render Direct Class Dependency"
関連GitHub: ["#40"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-22"
依存: ["requirement.md", "design.md"]
親: ["epic-00039", "init-00038"]
---

# iss-00040 Render Direct Class Dependency — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001 same-file direct constructor dependency in `generate`
  - AC-002 explicit from-import multi-class target dependency
  - AC-003 from-import alias dependency
  - AC-004 module-qualified dependency
  - AC-005 type/specification dependency in method body
  - AC-006 `self.b = B()` dependency without ownership inference
  - AC-007 same relation semantics in `diff`
  - AC-008 existing typed relations remain compatible
- EC:
  - EC-001 ambiguity fail-closed
  - EC-002 import-only produces no relation
  - EC-003 dynamic reference skipped
  - EC-004 nested function / lambda skipped
  - EC-005 duplicate endpoint relation priority
- 制約:
  - AST-only, read-only, no target import execution, deterministic output.
  - Runtime direct use must be `dependency`, not `association`.
  - Existing `uses`, typed field, inheritance, framework hint behavior must not regress.

## 依存関係から導く実装順序
- 依存関係の正本:
  - `design.md` の依存関係、図、ファイル変更計画
- 順序ルール:
  - prerequisite / lower-dependency slice から先に閉じる
  - downstream slice は前提が固定されてから置く
- step 依存 summary:
  - S01:
    - 依存: requirement / design
    - unblock: S02-S04 can use `dependency` relation type safely
    - 対象ファイル: `src/pyclassuml/model/contracts.py`, `src/pyclassuml/render/document.py`, model/render tests
  - S02:
    - 依存: S01 relation type contract
    - unblock: S03 can select dependency references
    - 対象ファイル: `src/pyclassuml/parse/indexer.py`, parse tests
  - S03:
    - 依存: S01/S02
    - unblock: S04 app integration
    - 対象ファイル: `src/pyclassuml/analyze/selection.py`, analyze tests
  - S04:
    - 依存: S01-S03
    - unblock: S90/S99
    - 対象ファイル: app tests and minimal pipeline adjustments if needed

## ステップ一覧
- S01:
  - 観測可能な振る舞い: `SelectedRelation(..., "dependency", ...)` が model contract で有効になり、render が `..>` を出す
  - 依存: requirement/design
  - unblock: S02/S03/S04
  - 対象ファイル: model/render contract and tests
  - 閉じる要件: AC-008 part, dependency output contract
  - レビューゲート: code-reviewer
- S02:
  - 観測可能な振る舞い: method body direct use が `ClassReference` evidence として抽出される
  - 依存: S01
  - unblock: S03
  - 対象ファイル: parse/indexer and tests
  - 閉じる要件: AC-001, AC-005, AC-006, EC-003, EC-004 parse-side
  - レビューゲート: code-reviewer
- S03:
  - 観測可能な振る舞い: dependency evidence が selected dependency relation になり、target class が選択される
  - 依存: S01/S02
  - unblock: S04
  - 対象ファイル: analyze/selection and tests
  - 閉じる要件: AC-001-AC-006, AC-008, EC-001, EC-002, EC-005
  - レビューゲート: code-reviewer
- S04:
  - 観測可能な振る舞い: `generate` / `diff` が direct dependency を end-to-end に出力する
  - 依存: S01-S03
  - unblock: S90/S99
  - 対象ファイル: app tests, app pipeline if required
  - 閉じる要件: AC-001, AC-002, AC-003, AC-004, AC-005, AC-006, AC-007
  - レビューゲート: code-reviewer

## 要件 ↔ ステップ対応
- AC-001 -> S02/S03/S04
- AC-002 -> S03/S04
- AC-003 -> S03/S04
- AC-004 -> S03/S04
- AC-005 -> S02/S03/S04
- AC-006 -> S02/S03/S04
- AC-007 -> S04
- AC-008 -> S01/S03
- EC-001 -> S03
- EC-002 -> S03
- EC-003 -> S02
- EC-004 -> S02
- EC-005 -> S03

## Spec-Locked Closure Index（仕様固定クロージャ索引）

| id | step | slice | type | spec link | locked expectation | observable input/state | bug class guarded | required | evidence level | closure evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| tc-001 | S01 | relation contract | acceptance | AC-008 / constraints | `dependency` relation type is accepted and rendered as `..>` while existing mappings remain unchanged | model/render unit tests | relation type contract missing or arrow drift | yes | red-required | report step closure |
| tc-002 | S02 | parse direct-use evidence | acceptance | AC-001 / AC-005 / AC-006 | method body direct-use patterns emit deterministic dependency evidence | parse fixture with `B()`, `B.factory()`, `B.CONST`, `isinstance`, `cast`, local annotation, `self.b = B()` | parser misses runtime/spec dependency | yes | red-required | report step closure |
| tc-003 | S02 | parse skip boundaries | negative | EC-003 / EC-004 | dynamic references and nested function/lambda bodies do not become outer class dependency evidence | parse fixture with `getattr`, nested function, lambda | false-positive dependency evidence | yes | red-required | report step closure |
| tc-004 | S03 | selection dependency | acceptance | AC-001 / AC-006 | dependency evidence resolves to selected target class and selected relation `dependency` | selection fixtures same-module and `self.b = B()` | relation evidence not selected | yes | red-required | report step closure |
| tc-005 | S03 | import resolution | acceptance | AC-002 / AC-003 / AC-004 | explicit import, alias import, relative import, and module-qualified access resolve to the intended class when unique | selection fixtures with multi-class target module | import fallback ambiguity still drops direct-use relation | yes | red-required | report step closure |
| tc-006 | S03 | ambiguity and dedupe | negative/regression | EC-001 / EC-002 / EC-005 / AC-008 | ambiguous/import-only references are skipped and structural/typed relations keep priority | selection fixtures | false-positive edge or relation priority regression | yes | red-required | report step closure |
| tc-007 | S04 | generate integration | acceptance | AC-001 / AC-002 / AC-003 / AC-004 / AC-005 / AC-006 | `generate` renders direct dependency `..>` end-to-end for constructor, import alias, module-qualified call/member access, type/specification, and self-attribute cases | app generate fixture matrix | common pipeline misses dependency for user-visible cases | yes | red-required | report step closure |
| tc-008 | S04 | diff integration | acceptance | AC-007 | `diff` renders added direct dependency with common relation semantics | app diff fixture | diff path diverges from generate | yes | red-required | report step closure |

## レビュー / QA ゲート方針
- RG1 step review:
  - 実施タイミング: 各 implementation step の commit 前
  - reviewer: code-reviewer for code / runtime / tests / scaffold behavior; spec-reviewer for docs-only / template-only / skill-text-only
  - pass 条件: review_status: pass
- QG1 final QA:
  - reviewer: qa-reviewer
  - 範囲: Issue 全体の obligation coverage、missing high-value tests、manual / integration test 要否
- SG1 final spec review:
  - reviewer: spec-reviewer
  - 範囲: requirement / design / plan / report / docs 整合

## 実行ルール（全ステップ共通）
- 各 implementation step は原則として 1 behavior slice / 1 review scope / 1 commit boundary とする。
- `plan.md` には planned requirements、evidence destination、closure 条件だけを書く。observed result は `report.md` に書く。
- docs-only / inspect-only / manual-required step は code test 前提にせず、代替 evidence path と rationale を implementation 前に固定する。
- implementation 中に新しい仕様、bug class、外部 contract risk、未計画の closure が見つかった場合は、report 記録だけで足りるか、plan amendment と re-review が必要かを判断する。

## 実装ステップ

### S01 — dependency relation contract and render mapping
- behavior goal:
  - `dependency` relation type を model contract に追加し、PlantUML `..>` として描画できるようにする。
- design 参照:
  - `design.md` Evidence Kind 方針 / インターフェース契約。
- 依存:
  - requirement/design。
- unblock:
  - S02/S03/S04。
- 対象ファイル:
  - `src/pyclassuml/model/contracts.py`
  - `src/pyclassuml/render/document.py`
  - `tests/model/test_contracts.py`
  - `tests/render/test_document.py`
- planned contract:
  - scope:
    - 実装・文書化する範囲:
      - `dependency` relation type の許可と arrow mapping。
  - test obligation:
    - closure id:
      - tc-001
    - coverage rationale:
      - Relation type contract は下流全体の前提であり、missing contract と existing mapping drift を最初に検出する。
  - Red / alternative evidence requirement:
    - red-required:
      - `SelectedRelation(..., "dependency", ...)` が実装前に `ValueError` になる test。
      - render mapping test に `dependency` を追加し、実装前に mapping がないことで失敗する test。
  - implementation scope:
    - allowed paths:
      - `src/pyclassuml/model/contracts.py`
      - `src/pyclassuml/render/document.py`
      - `tests/model/test_contracts.py`
      - `tests/render/test_document.py`
    - forbidden changes:
      - parse / analyze behavior changes。
      - existing relation arrow changes。
  - Green verification:
    - command / inspection / manual evidence:
      - `pytest tests/model/test_contracts.py tests/render/test_document.py`
  - Refactor / cleanup guardrail:
    - 目的: relation type list と error message の整合。
    - 禁止する広がり: renderer structure rewrite。
  - closure evidence requirements:
    - Step Contract Closure: tc-001 pass。
    - Test Contract Closure: targeted pytest result。
    - Closure Coverage: AC-008 / relation contract。
  - report evidence destination:
    - `report.md` Step Contract Closure / Test Contract Closure / Reviewer Gate Status / Step Commit Gate。
  - amendment trigger:
    - `dependency` cannot be added without changing public schema beyond relation type list。

#### delegation contract
- delegated role:
  - dev-coder
- input docs:
  - `requirement.md`
  - `design.md`
  - `plan.md`
  - workflow / authoring docs:
    - `spec-dock/docs/workflow_issue.md`
  - current target files:
    - listed in target files above
- allowed paths:
  - S01 target files only.
- forbidden changes:
  - parse / analyze / app files.
- acceptance criteria:
  - tc-001.
- required tests or docs-only verification:
  - `pytest tests/model/test_contracts.py tests/render/test_document.py`
- reviewer focus:
  - code-reviewer for code / runtime / tests / scaffold behavior; spec-reviewer for docs-only / template-only / skill-text-only docs/spec alignment
- output required:
  - changed files, verification result, unresolved risks, Ledger Note or no material decision statement.
- stop conditions:
  - relation type contract requires larger model schema migration.

#### 具体テストケース一覧

- `tc-s01-001` acceptance: dependency relation type and arrow mapping
  - 前提: `SelectedRelation` と render mapping が `dependency` をまだ知らない。
  - 操作: model contract test と render relation mapping test に `dependency` を追加する。
  - 期待結果: `dependency` が許可され、PlantUML relation line は `..>` になる。
  - 失敗検出: relation type validation failure、または render mapping missing / wrong arrow を検出する。
  - 検証方法: `pytest tests/model/test_contracts.py tests/render/test_document.py`
  - 関連 closure id: tc-001

#### step closure contract
- closure id:
  - tc-001
- close 条件:
  - targeted tests pass and code-reviewer pass.
- 検証 evidence:
  - targeted command / inspection / manual evidence:
    - `pytest tests/model/test_contracts.py tests/render/test_document.py`
- report evidence:
  - Step Contract Closure:
  - Test Contract Closure:
  - Closure Coverage:
  - Closure Delta:
- 残リスク:
  - None beyond downstream use.

#### step gate
- report update gate:
  - 実施タイミング: targeted verification 後、step reviewer gate 前。
  - 記録内容: Step Contract Closure、Test Contract Closure、Closure Coverage、Implementation Delegation Gate、Reviewer Gate Status draft。
- step reviewer gate:
  - reviewer: code-reviewer
  - review 範囲: S01 files only.
  - pass 条件: review_status: pass
  - re-review rule: 指摘を修正し pass まで再実行
- commit / no-op gate:
  - closure 状態: committed / approved-no-op
  - commit 範囲: S01 files and report evidence only.
  - no-op の場合の確認対象、差分なし確認コマンド、read-only evidence: not expected.

### S02 — parse method body dependency evidence
- behavior goal:
  - Method body direct-use patterns を `ClassReference` evidence として抽出する。
- design 参照:
  - `design.md` Evidence Kind 方針。
- 依存:
  - S01
- unblock:
  - S03
- 対象ファイル:
  - `src/pyclassuml/parse/indexer.py`
  - `tests/parse/test_module_parse_and_index.py`
- planned contract:
  - scope:
    - 実装・文書化する範囲:
      - direct-use evidence extraction, nested/dynamic skip behavior.
  - test obligation:
    - closure id:
      - tc-002
      - tc-003
    - coverage rationale:
      - AC direct-use coverage と EC false-positive guard を parse seam で固定する。
  - Red / alternative evidence requirement:
    - red-required:
      - direct-use evidence が現行では出ないことを parse test で検出する。
  - implementation scope:
    - allowed paths:
      - `src/pyclassuml/parse/indexer.py`
      - `tests/parse/test_module_parse_and_index.py`
    - forbidden changes:
      - selection / render behavior changes。
  - Green verification:
    - command / inspection / manual evidence:
      - `pytest tests/parse/test_module_parse_and_index.py`
  - Refactor / cleanup guardrail:
    - 目的: helper extraction for readable AST walking.
    - 禁止する広がり: data-flow tracking, dynamic reference inference.
  - closure evidence requirements:
    - Step Contract Closure: tc-002/tc-003 pass.
    - Test Contract Closure: parse pytest result.
    - Closure Coverage: AC-001/AC-005/AC-006/EC-003/EC-004.
  - report evidence destination:
    - `report.md` Step Contract Closure / Test Contract Closure / Closure Coverage / Reviewer Gate Status / Step Commit Gate.
  - amendment trigger:
    - Required pattern cannot be represented as `ClassReference` without model schema change.

#### delegation contract
- delegated role:
  - dev-coder
- input docs:
  - `requirement.md`, `design.md`, `plan.md`, S01 result, target files.
- allowed paths:
  - S02 target files only.
- forbidden changes:
  - selection/render/app changes.
- acceptance criteria:
  - tc-002, tc-003.
- required tests or docs-only verification:
  - `pytest tests/parse/test_module_parse_and_index.py`
- reviewer focus:
  - code-reviewer for parse evidence extraction and test sensitivity.
- output required:
  - changed files, verification result, unresolved risks, Ledger Note or no material decision statement.
- stop conditions:
  - AST scope requires data-flow or runtime import execution.

#### 具体テストケース一覧

- `tc-s02-001` acceptance: method body direct-use evidence
  - 前提: `class A` method body に `B()`, `B.factory()`, `B.CONST`, `module.B()`, `module.B.CONST`, `isinstance(x, B)`, `typing.cast(B, x)`, `x: B`, `self.b = B()` がある。
  - 操作: `parse_target_set` を実行する。
  - 期待結果: source class `A` から each target name への dependency evidence kind が抽出される。
  - 失敗検出: method body direct-use を relation evidence にしない現行欠落を検出する。
  - 検証方法: `pytest tests/parse/test_module_parse_and_index.py`
  - 関連 closure id: tc-002

- `tc-s02-002` negative: dynamic and nested scopes are skipped
  - 前提: method body または class body に nested function / lambda / `getattr(module, "B")` がある。
  - 操作: `parse_target_set` を実行する。
  - 期待結果: outer class の dependency evidence は作られない。
  - 失敗検出: false-positive dependency evidence を検出する。
  - 検証方法: `pytest tests/parse/test_module_parse_and_index.py`
  - 関連 closure id: tc-003

#### step closure contract
- closure id:
  - tc-002
  - tc-003
- close 条件:
  - targeted tests pass and code-reviewer pass.
- 検証 evidence:
  - targeted command / inspection / manual evidence:
    - `pytest tests/parse/test_module_parse_and_index.py`
- report evidence:
  - Step Contract Closure:
  - Test Contract Closure:
  - Closure Coverage:
  - Closure Delta:
- 残リスク:
  - Selection resolution remains unimplemented until S03.

#### step gate
- report update gate:
  - 実施タイミング: targeted verification 後、step reviewer gate 前。
  - 記録内容: Step Contract Closure、Test Contract Closure、Closure Coverage、Implementation Delegation Gate、Reviewer Gate Status draft。
- step reviewer gate:
  - reviewer: code-reviewer
  - review 範囲: S02 files only.
  - pass 条件: review_status: pass
  - re-review rule: 指摘を修正し pass まで再実行
- commit / no-op gate:
  - closure 状態: committed / approved-no-op
  - commit 範囲: S02 files and report evidence only.
  - no-op の場合の確認対象、差分なし確認コマンド、read-only evidence: not expected.

### S03 — select dependency relations and resolve explicit imports
- behavior goal:
  - Dependency evidence を selected target class と `SelectedRelation(..., "dependency", ...)` に変換する。
- design 参照:
  - `design.md` Target Resolution 方針。
- 依存:
  - S01/S02
- unblock:
  - S04
- 対象ファイル:
  - `src/pyclassuml/analyze/selection.py`
  - `tests/analyze/test_selection.py`
- planned contract:
  - scope:
    - 実装・文書化する範囲:
      - dependency relation classification, import-based target resolution, ambiguity skip, dedupe/priority.
  - test obligation:
    - closure id:
      - tc-004
      - tc-005
      - tc-006
    - coverage rationale:
      - Selection seam owns class selection, relation identity, and false-positive guard.
  - Red / alternative evidence requirement:
    - red-required:
      - dependency references currently produce no relation and imported multi-class target is dropped.
  - implementation scope:
    - allowed paths:
      - `src/pyclassuml/analyze/selection.py`
      - `tests/analyze/test_selection.py`
    - forbidden changes:
      - parse/render/app changes.
  - Green verification:
    - command / inspection / manual evidence:
      - `pytest tests/analyze/test_selection.py`
  - Refactor / cleanup guardrail:
    - 目的: keep target resolution helpers local and deterministic.
    - 禁止する広がり: full Python name resolution, data-flow, external package resolution.
  - closure evidence requirements:
    - Step Contract Closure: tc-004/tc-005/tc-006 pass.
    - Test Contract Closure: analyze pytest result.
    - Closure Coverage: AC-001-AC-006/AC-008/EC-001/EC-002/EC-005.
  - report evidence destination:
    - `report.md` Step Contract Closure / Test Contract Closure / Closure Coverage / Decision Ledger if needed / Reviewer Gate Status / Step Commit Gate.
  - amendment trigger:
    - Required import resolution cannot be derived from existing ParsedModule imports / ModuleIndex.

#### delegation contract
- delegated role:
  - dev-coder
- input docs:
  - `requirement.md`, `design.md`, `plan.md`, S01/S02 result, target files.
- allowed paths:
  - S03 target files only.
- forbidden changes:
  - parse/render/app changes.
- acceptance criteria:
  - tc-004, tc-005, tc-006.
- required tests or docs-only verification:
  - `pytest tests/analyze/test_selection.py`
- reviewer focus:
  - code-reviewer for target resolution, relation normalization, and ambiguity behavior.
- output required:
  - changed files, verification result, unresolved risks, Ledger Note or no material decision statement.
- stop conditions:
  - resolution needs full import execution or out-of-scope global symbol analysis.

#### 具体テストケース一覧

- `tc-s03-001` acceptance: dependency selects target class
  - 前提: source class has dependency evidence for same-module `B` or `self.b = B()`.
  - 操作: `select_classes_and_relations` を実行する。
  - 期待結果: target class is selected and relation type is `dependency`.
  - 失敗検出: dependency evidence ignored or target outside selected warning.
  - 検証方法: `pytest tests/analyze/test_selection.py`
  - 関連 closure id: tc-004

- `tc-s03-002` acceptance: explicit import resolves multi-class target
  - 前提: source imports `B` from target module that also defines `Helper`, then uses `B()`.
  - 操作: `select_classes_and_relations` を実行する。
  - 期待結果: relation points only to `target.B`; `Helper` is not selected through that evidence.
  - 失敗検出: old ambiguous module fallback behavior drops direct-use relation.
  - 検証方法: `pytest tests/analyze/test_selection.py`
  - 関連 closure id: tc-005

- `tc-s03-003` acceptance: alias, relative, and module-qualified imports resolve unique targets
  - 前提: source uses `from pkg.target import B as AliasB; AliasB()`, `from .target import B; B()`, and `import pkg.target as target; target.B.factory()` against target modules with unrelated classes.
  - 操作: `select_classes_and_relations` を実行する。
  - 期待結果: each relation points to the intended canonical `B` class and does not select unrelated target classes.
  - 失敗検出: alias/local name, relative import, or module-qualified access is ignored or resolved to the wrong class.
  - 検証方法: `pytest tests/analyze/test_selection.py`
  - 関連 closure id: tc-005

- `tc-s03-004` negative/regression: ambiguity and priority
  - 前提: unresolved / ambiguous reference, import-only module edge, and existing structural relation cases.
  - 操作: `select_classes_and_relations` を実行する。
  - 期待結果: ambiguous reference warns/skips; import-only does not create dependency; structural relation wins over dependency for same endpoint.
  - 失敗検出: false-positive edge or priority regression.
  - 検証方法: `pytest tests/analyze/test_selection.py`
  - 関連 closure id: tc-006

#### step closure contract
- closure id:
  - tc-004
  - tc-005
  - tc-006
- close 条件:
  - targeted tests pass and code-reviewer pass.
- 検証 evidence:
  - targeted command / inspection / manual evidence:
    - `pytest tests/analyze/test_selection.py`
- report evidence:
  - Step Contract Closure:
  - Test Contract Closure:
  - Closure Coverage:
  - Closure Delta:
- 残リスク:
  - End-to-end CLI behavior remains unproven until S04.

#### step gate
- report update gate:
  - 実施タイミング: targeted verification 後、step reviewer gate 前。
  - 記録内容: Step Contract Closure、Test Contract Closure、Closure Coverage、Implementation Delegation Gate、Reviewer Gate Status draft。
- step reviewer gate:
  - reviewer: code-reviewer
  - review 範囲: S03 files only.
  - pass 条件: review_status: pass
  - re-review rule: 指摘を修正し pass まで再実行
- commit / no-op gate:
  - closure 状態: committed / approved-no-op
  - commit 範囲: S03 files and report evidence only.
  - no-op の場合の確認対象、差分なし確認コマンド、read-only evidence: not expected.

### S04 — generate and diff integration
- behavior goal:
  - Common app pipeline で direct dependency `..>` が `generate` / `diff` に出ることを保証する。
- design 参照:
  - `design.md` 要件 / 例外 -> verification mapping。
- 依存:
  - S01/S02/S03
- unblock:
  - S90/S99
- 対象ファイル:
  - `tests/app/test_generate.py`
  - `tests/app/test_diff.py`
  - app source only if integration failure proves source change is required
- planned contract:
  - scope:
    - 実装・文書化する範囲:
      - app-level regression tests; minimal app pipeline fix if required.
  - test obligation:
    - closure id:
      - tc-007
      - tc-008
    - coverage rationale:
      - Generate/diff path share pipeline but diff has changed inventory/decorations; generate must also observe every user-facing AC pattern from AC-001 through AC-006.
  - Red / alternative evidence requirement:
    - red-required:
      - app tests fail before S01-S03 implementation or before integration fix.
  - implementation scope:
    - allowed paths:
      - `tests/app/test_generate.py`
      - `tests/app/test_diff.py`
      - `src/pyclassuml/app/*.py` only when necessary
    - forbidden changes:
      - scope expansion beyond common pipeline wiring.
  - Green verification:
    - command / inspection / manual evidence:
      - `pytest tests/app/test_generate.py tests/app/test_diff.py`
      - `pytest tests/model/test_contracts.py tests/parse/test_module_parse_and_index.py tests/analyze/test_selection.py tests/render/test_document.py tests/app/test_generate.py tests/app/test_diff.py`
  - Refactor / cleanup guardrail:
    - 目的: app fixtures reusable enough for readability.
    - 禁止する広がり: CLI option changes or output schema changes.
  - closure evidence requirements:
    - Step Contract Closure: tc-007/tc-008 pass.
    - Test Contract Closure: targeted and combined pytest result.
    - Closure Coverage: AC-001/AC-002/AC-003/AC-004/AC-005/AC-006/AC-007.
  - report evidence destination:
    - `report.md` Step Contract Closure / Test Contract Closure / Closure Coverage / Reviewer Gate Status / Step Commit Gate.
  - amendment trigger:
    - Generate/diff divergence requires design change to common pipeline.

#### delegation contract
- delegated role:
  - dev-coder
- input docs:
  - `requirement.md`, `design.md`, `plan.md`, S01-S03 result, app tests.
- allowed paths:
  - S04 target files.
- forbidden changes:
  - CLI contract changes unless plan amended.
- acceptance criteria:
  - tc-007, tc-008.
- required tests or docs-only verification:
  - app targeted pytest and combined targeted pytest.
- reviewer focus:
  - code-reviewer for app coverage and integration risk.
- output required:
  - changed files, verification result, unresolved risks, Ledger Note or no material decision statement.
- stop conditions:
  - app behavior needs CLI/API contract change.

#### 具体テストケース一覧

- `tc-s04-001` acceptance: generate renders dependency matrix
  - 前提: temp project has same-file `return B()`, explicit multi-class import `B()`, alias import `AliasB()`, module-qualified `target.B.factory()` and `target.B.CONST`, type/specification dependency, and `self.b = B()` cases.
  - 操作: `run_generate` を実行する。
  - 期待結果: PlantUML contains the expected `..>` dependency lines for all AC-001 through AC-006 generate-visible cases and no unrelated target relation.
  - 失敗検出: end-to-end pipeline misses selected dependency for any user-visible AC path.
  - 検証方法: `pytest tests/app/test_generate.py`
  - 関連 closure id: tc-007

- `tc-s04-002` acceptance: diff renders added dependency
  - 前提: base revision lacks `A -> B` direct use; working tree adds it.
  - 操作: `run_diff` を実行する。
  - 期待結果: PlantUML contains added class decoration and dependency `..>` relation.
  - 失敗検出: diff relation identity or changed selection misses dependency.
  - 検証方法: `pytest tests/app/test_diff.py`
  - 関連 closure id: tc-008

#### step closure contract
- closure id:
  - tc-007
  - tc-008
- close 条件:
  - app targeted and combined targeted tests pass; code-reviewer pass.
- 検証 evidence:
  - targeted command / inspection / manual evidence:
    - `pytest tests/app/test_generate.py tests/app/test_diff.py`
    - combined targeted pytest listed in Green verification.
- report evidence:
  - Step Contract Closure:
  - Test Contract Closure:
  - Closure Coverage:
  - Closure Delta:
- 残リスク:
  - Full suite remains for S99.

#### step gate
- report update gate:
  - 実施タイミング: targeted verification 後、step reviewer gate 前。
  - 記録内容: Step Contract Closure、Test Contract Closure、Closure Coverage、Implementation Delegation Gate、Reviewer Gate Status draft。
- step reviewer gate:
  - reviewer: code-reviewer
  - review 範囲: S04 files and integration behavior.
  - pass 条件: review_status: pass
  - re-review rule: 指摘を修正し pass まで再実行
- commit / no-op gate:
  - closure 状態: committed / approved-no-op
  - commit 範囲: S04 files and report evidence only.
  - no-op の場合の確認対象、差分なし確認コマンド、read-only evidence: not expected.

### S90 — docs impact resolution / docs refresh
- 対象:
  - README / user docs / CLI docs / templates / workflow / skill / migration notes.
- 対応:
  - Inspect docs for relation type or class diagram arrow semantics that need update.
  - If user-facing docs mention relation arrows, update through doc-writer and run spec-reviewer docs/spec alignment.
  - If no docs impact, record inspection evidence and spec-reviewer pass.
- doc update owner:
  - doc-writer when updates are required
- spec/doc review:
  - reviewer: spec-reviewer
  - pass 条件: docs が requirement / design / plan と整合し、未解決の必須 docs 影響が残っていない

### S99 — final quality gate
- branch diff 範囲:
  - All commits for iss-00040.
- 必須 validation:
  - `pytest`
  - `./spec-dock/scripts/spec-dock validate`
  - `./spec-dock/scripts/spec-dock sync`
- final QA gate:
  - reviewer: qa-reviewer
  - 範囲: Issue 全体の obligation coverage と integration test 要否
  - pass 条件: reviewer pass
- final code review ゲート:
  - reviewer: code-reviewer
  - 範囲: issue-wide integrated diff、構造、責務境界、回帰リスク、保守性
  - pass 条件: review_status: pass
- final spec review ゲート:
  - reviewer: spec-reviewer
  - 範囲: requirement / design / plan / report / implementation / tests / docs 整合
  - pass 条件: reviewer pass
- final commit gate:
  - commit 範囲:
    - final report updates only, if needed.
  - final report ledger:
    - closure coverage, reviewer verdicts, PR delivery and merge preparation gates.
  - post-commit external evidence destination:
    - final response / PR body.

## 未確定事項
- なし。

## 最終完了条件
- AC/EC 達成:
  - All required closure ids tc-001 through tc-008 are closed.
- docs 影響解決:
  - S90 pass.
- 全 implementation step 完了:
  - committed / approved-no-op:
    - S01-S04 committed or approved-no-op with evidence.
- final quality gate pass:
  - qa-reviewer:
    - pass.
  - issue-wide code-reviewer:
    - pass.
  - final spec-reviewer:
    - pass.
- PR:
  - PR Delivery Gate pass and Merge Preparation Gate pass.
- lifecycle:
  - final commit clean, PR ready/merge-prepared, then `./spec-dock/scripts/spec-dock issue finish`.
- final commit 完了:
  - final report ledger updates are committed after S99 when needed.
  - post-commit external evidence records final commit hash and clean worktree.
- 必須 closure id 完了:
  - Step Contract Closure: tc-001 through tc-008 pass.
  - Test Contract Closure: required targeted tests, combined targeted tests, and full `pytest` pass or documented blocker.
  - Closure Coverage: every AC/EC maps to closed closure evidence.
- final clean state:
  - no unintended staged / unstaged changes after final commit.
- PR / merge preparation:
  - PR URL, selected base, head branch/SHA, issue linkage, PR Delivery Gate, and Merge Preparation Gate are recorded in `report.md`.
  - Required checks and review/merge blockers are monitored; unresolved blockers prevent completion.
- lifecycle closure:
  - `./spec-dock/scripts/spec-dock issue finish` runs only after PR Delivery Gate and Merge Preparation Gate pass.
