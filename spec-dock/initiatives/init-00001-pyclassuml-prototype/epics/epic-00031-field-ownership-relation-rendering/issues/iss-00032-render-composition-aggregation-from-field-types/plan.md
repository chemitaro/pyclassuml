---
種別: 実装計画書（Issue）
ID: "iss-00032"
タイトル: "Render Composition And Aggregation From Field Types"
関連GitHub: ["#32"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-05"
依存: ["requirement.md", "design.md"]
親: ["epic-00031", "init-00001"]
---

# iss-00032 Render Composition And Aggregation From Field Types — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001, AC-002, AC-003, AC-004, AC-005, AC-006, AC-007, AC-008
- EC:
  - EC-001, EC-002, EC-003, EC-004, EC-005, EC-006
- 制約:
  - AST-only / read-only / deterministic / import execution forbidden

## マイルストーン一覧
- M1:
  - 対象: model contract と parser shape extraction
  - exit: parse/model targeted tests pass
- M2:
  - 対象: analyzer classification and relation priority
  - exit: analyze targeted tests pass
- M3:
  - 対象: render output and app E2E
  - exit: render/app targeted tests pass
- M4:
  - 対象: manual test, review gates, final validation, close
  - exit: full tests, manual SVG, `sync --github`, `validate`, reviewer pass

## 依存関係から導く実装順序
- S01 fixes the data contract consumed by all downstream steps.
- S02 depends on parser shape metadata and relation vocabulary.
- S03 depends on relation type output from analyzer.
- S04 depends on all implementation slices and validates real CLI behavior.
- S90/S99 resolve docs/report/review and final quality gates.

## ステップ一覧
- S01:
  - 観測可能な振る舞い: `ClassReference` can carry field annotation shape and model accepts `composition` / `aggregation`.
  - depends on: requirement/design.
  - unblocks: analyzer classification.
  - target files: `src/pyclassuml/model/contracts.py`, `src/pyclassuml/parse/indexer.py`, `tests/model/test_contracts.py`, `tests/parse/test_module_parse_and_index.py`
  - closes: AC-005, AC-006 parser/model prerequisites; EC-005 parser prerequisite.
  - review gate: targeted tests.
- S02:
  - 観測可能な振る舞い: field-origin relations become `composition` / `aggregation`; method-only remains `uses`.
  - depends on: S01.
  - unblocks: render.
  - target files: `src/pyclassuml/analyze/selection.py`, `tests/analyze/test_selection.py`
  - closes: AC-001 through AC-007, EC-001 through EC-005 at selection layer.
  - review gate: targeted analyze tests.
- S03:
  - 観測可能な振る舞い: PlantUML outputs `*--` and `o--` without normal arrow heads.
  - depends on: S02.
  - unblocks: E2E and manual.
  - target files: `src/pyclassuml/render/document.py`, `tests/render/test_document.py`, `tests/app/test_generate.py`
  - closes: AC-001 through AC-008 at output layer.
  - review gate: render/app targeted tests.
- S04:
  - 観測可能な振る舞い: real CLI generates `.puml` / `.svg` for complex sample with composition, aggregation, mapping value, inheritance, Protocol realization.
  - depends on: S03.
  - unblocks: final close.
  - target files: `build/manual-tests/pyclassuml-manual-env/out/iss-00032/*` ignored artifacts only.
  - closes: AC-008, manual acceptance.
  - review gate: manual inspection and full tests.
- S90:
  - 観測可能な振る舞い: docs impact resolved and report evidence updated.
  - depends on: S04.
  - target files: `spec-dock/active/issue/report.md`; requirement/design/plan only if implementation discovers mismatch.
- S99:
  - 観測可能な振る舞い: final diff reviewed, reviewers pass, issue/epic closure verified.
  - depends on: S90.
  - target files: none except report updates.

## 要件 ↔ ステップ対応
- AC-001 -> S01, S02, S03, S04
- AC-002 -> S01, S02, S03, S04
- AC-003 -> S01, S02, S03, S04
- AC-004 -> S01, S02, S03, S04
- AC-005 -> S01, S02, S03, S04
- AC-006 -> S01, S02, S04
- AC-007 -> S02, S03
- AC-008 -> S03, S04, S99
- EC-001 -> S02, S04
- EC-002 -> S02
- EC-003 -> S02
- EC-004 -> S02, S04
- EC-005 -> S01, S02, S04
- EC-006 -> S01, S02, S04

## レビュー / QA ゲート方針
- RG1 implementation review:
  - timing: S01-S03 implementation and targeted/full tests pass.
  - scope: model/parse/analyze/render correctness and regression risk.
- QG1 QA review:
  - timing: manual test evidence and full tests pass.
  - scope: AC/EC coverage, negative cases, manual env cleanliness.
- SG1 spec review:
  - timing: design/plan/report updated and implementation evidence exists.
  - scope: docs reflect implementation and closure evidence.

## 実行ルール（全ステップ共通）
- Use `./spec-dock/scripts/spec-dock ...` for SpecDock commands.
- Use TDD-style small slices: tests first where practical, then implementation, then refactor.
- Keep source changes scoped to the listed files.
- Do not edit target manual sample directly except disposable copies under ignored `tmp`.
- Remove generated `uv.lock` if `uv run --with pytest` creates it.

## 実装ステップ

### S01 — model and parser shape metadata
- observable behavior:
  - Parser emits `annotation_shape` for field/init field references.
  - Mapping value targets are emitted as `mapping_value`; mapping key targets are not ownership semantic references.
- design refs:
  - `Annotation Shape Contract`, `インターフェース契約`
- expected tests:
  - `uv run --with pytest pytest -q tests/model/test_contracts.py tests/parse/test_module_parse_and_index.py`
- report update:
  - Record changed files and command results.

### S02 — selection classification and priority
- observable behavior:
  - `direct` field -> `composition`
  - `optional` / `union` / `collection` / `mapping_value` -> `aggregation`
  - `inherits` / `realizes` remain top priority; composition beats aggregation; aggregation beats association/uses.
  - mapping key does not create ownership relation and does not require an unresolved warning.
  - nested wrapper item/value targets remain aggregation.
- expected tests:
  - `uv run --with pytest pytest -q tests/analyze/test_selection.py`
- report update:
  - Record AC/EC coverage.

### S03 — render and app E2E
- observable behavior:
  - `composition` renders `*--`
  - `aggregation` renders `o--`
  - no `*-->` / `o-->`
  - inheritance and realization unchanged.
- expected tests:
  - `uv run --with pytest pytest -q tests/render/test_document.py tests/app/test_generate.py`
- report update:
  - Record output assertions.

### S04 — manual test and full validation
- observable behavior:
  - Manual complex sample produces `.puml` and `.svg`.
  - Output contains direct composition, optional/list/mapping aggregation, `-up-|>`, and `..up|>`.
- expected commands:
  - `uv run --with pytest pytest -q`
  - `uv run pyclassuml generate ...`
  - `docker run --rm ... plantuml/plantuml:latest -tsvg ...`
  - `git -C build/manual-tests/pyclassuml-manual-env status --short --branch`
- report update:
  - Record manual command output and key `.puml` lines.

### S90 — docs impact resolution / docs refresh
- 対象:
  - issue docs and report only unless implementation reveals broader docs impact.
- 対応:
  - Update `report.md`.
  - Run `./spec-dock/scripts/spec-dock sync --github`.
  - Run `./spec-dock/scripts/spec-dock validate`.

### S99 — final diff review quality gate
- branch diff scope:
  - `iss-00032-render-composition-aggregation-from-field-types`
- required validation:
  - targeted tests, full tests, manual test, `git diff --check`, uppercase path scan, manual env clean.
- reviewer approvals:
  - code-reviewer pass
  - qa-reviewer pass
  - spec-reviewer pass
- report update:
  - Final evidence, commit hash, close evidence.

## 未確定事項
- 該当なし。

## final exit contract
- AC/EC 達成:
  - All AC/EC mapped to tests or manual evidence in `report.md`.
- docs impact resolved:
  - `requirement.md` / `design.md` / `plan.md` are issue-specific; report contains evidence.
- final diff approved:
  - Reviewers pass, validations pass, issue and epic closed.
