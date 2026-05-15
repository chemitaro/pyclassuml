---
種別: 実装計画書（Issue）
ID: "iss-00033"
タイトル: "Render Diff Class Colorization"
関連GitHub: ["#33"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-05"
依存: ["requirement.md", "design.md"]
親: ["epic-00004", "init-00001"]
---

# iss-00033 Render Diff Class Colorization — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001 changed class colorization
  - AC-002 dependency-only class default rendering
  - AC-003 generate unaffected
  - AC-004 relation notation regression prevention
  - AC-005 deterministic output
- EC:
  - EC-001 changed file without class
  - EC-002 changed class not selected
  - EC-003 syntax error / join miss
  - EC-004 working-tree / head / untracked semantics
- 制約:
  - render は Git を読まない。
  - 対象コードを import 実行しない。
  - hunk 粒度の member highlight や deleted class 表示は実装しない。
  - hunk range は class-level changed 判定の入力としてのみ扱う。

## マイルストーン一覧
- M1 render style contract:
  - 対象: `render.document` の extra class decorations と PlantUML style block。
  - exit: render unit tests が diff style、Protocol coexistence、no-decoration case を固定する。
- M2 diff decoration handoff:
  - 対象: `app.diff` の selected class と changed file context の join。
  - exit: diff E2E tests が changed / newly added class だけを style 付きとして検証する。
- M3 regression / manual verification:
  - 対象: full tests、manual env diff -> `.puml` / `.svg`、SpecDock validate、review gates。
  - exit: code/QA/spec review pass、report 更新、issue close readiness。

## 依存関係から導く実装順序
- step dependency summary:
  - S01:
    - depends on: existing `RenderReadyModel.class_decorations`
    - unblocks: diff app handoff tests
    - target files: `src/pyclassuml/render/document.py`, `tests/render/test_document.py`
  - S02:
    - depends on: S01 render support
    - unblocks: E2E diff colorization
    - target files: `src/pyclassuml/app/diff.py`, `tests/app/test_diff.py`
  - S03:
    - depends on: S01/S02
    - unblocks: AC-003/AC-004/EC coverage
    - target files: app/render tests as needed
  - S04:
    - depends on: implementation complete
    - unblocks: closure
    - target files: manual output under ignored `build/manual-tests`
  - S90/S99:
    - depends on: validation/review evidence
    - target files: `spec-dock/active/issue/report.md`

## ステップ一覧
- S01 render style contract:
  - 観測可能な振る舞い:
    - `DiffChanged` decoration がある場合だけ PlantUML style block と class stereotype が出る。
    - dependency-only class に `DiffDependency` stereotype / 専用色が出ない。
  - review gate:
    - render unit tests pass。
- S02 diff class decoration handoff:
  - 観測可能な振る舞い:
    - added file 内 selected class、または changed hunk と class span が重なる selected class は `DiffChanged`。
    - selected だが changed hunk と class span が重ならない class は diff decoration なし。
  - review gate:
    - diff E2E tests pass。
    - syntax error / parsed class join miss で `DiffChanged` を捏造せず、parse diagnostics が保持される targeted test が pass。
- S03 regression coverage:
  - 観測可能な振る舞い:
    - generate に diff style が出ない。
    - relation notation と summary counters が維持される。
- S04 manual diff colorization:
  - 観測可能な振る舞い:
    - manual env の Git 差分から `.puml` / `.svg` を生成し、色分けと relation notation を確認する。
- S90 docs / sync / validate:
  - 観測可能な振る舞い:
    - report に実装・検証・レビュー結果が残る。
    - `spec-dock validate` が通る。
- S99 final quality gate:
  - 観測可能な振る舞い:
    - code-reviewer / qa-reviewer / spec-reviewer pass。
    - completion audit で全 AC/EC が実証される。

## 要件 ↔ ステップ対応
- AC-001 -> S02, S04
- AC-002 -> S02, S04
- AC-003 -> S03
- AC-004 -> S01, S03, S04
- AC-005 -> S01, S02, S03
- EC-001 -> S02 or S03 targeted test
- EC-002 -> S02 targeted test
- EC-003 -> S02 targeted syntax-error / join-miss diagnostic test
- EC-004 -> S03 existing matrix preservation + targeted assertion

## レビュー / QA ゲート方針
- SG1 spec review:
  - timing: design / plan 作成後、実装前。
  - scope: requirement/design/plan が実装可能で矛盾しないこと。
- RG1 implementation review:
  - timing: implementation and tests complete.
  - scope: architecture boundary、render does not read Git、classification correctness、regression risk。
- QG1 QA review:
  - timing: automated/manual verification complete.
  - scope: AC/EC coverage、manual diff SVG evidence、summary/generate regression。

## 実行ルール（全ステップ共通）
- main agent は issue scoped docs を直接更新する。
- source/test implementation は dev-coder に委任する。
- final review は fresh code-reviewer / qa-reviewer / spec-reviewer を使う。
- `.serena/project.yml` の既存変更は触らない。
- `uv run` が作る `uv.lock` は成果物でなければ削除する。

## 実装ステップ

### S01 — Render Diff Style Contract
- observable behavior:
  - `render_plantuml_text` が diff decorations を PlantUML style + stereotype として出す。
- design refs:
  - `インターフェース契約`
- depends on:
  - existing class decoration support
- unblocks:
  - S02
- target files:
  - `src/pyclassuml/render/document.py`
  - `tests/render/test_document.py`
- expected tests:
  - diff style block snapshot
  - Protocol + diff stereotype coexistence
  - no decoration => no diff style block
- report update:
  - S01 実施内容と test result。

### S02 — Diff App Decoration Handoff
- observable behavior:
  - `run_diff` が selected classes のうち added file 内 class、または changed hunk と class span が重なる class だけに `DiffChanged` decoration を付与して render に渡す。
- design refs:
  - `依存関係分析`
  - `Module Dependency Diagram`
- depends on:
  - S01
- unblocks:
  - S03/S04
- target files:
  - `src/pyclassuml/app/diff.py`
  - `tests/app/test_diff.py`
- expected tests:
  - changed class highlighted and dependency-only class default-rendered E2E `.puml`
  - same file 内に changed class と unchanged class が共存する場合、changed class だけが highlighted になる
  - module-level only change は class を highlighted しない
  - selected 外 changed class には style を作らない
  - changed file without class has no changed style
  - syntax error changed file or parsed class join miss preserves diagnostics and emits no fabricated `DiffChanged`
- report update:
  - S02 実施内容と test result。

### S03 — Regression And Command Boundary
- observable behavior:
  - `generate` output remains uncolored.
  - composition / aggregation / inheritance / realization / uses relation notation remains unchanged.
  - `changed_class_count` remains existing summary semantics.
- depends on:
  - S02
- target files:
  - `tests/app/test_generate.py`
  - `tests/app/test_diff.py`
  - `tests/render/test_document.py`
- expected tests:
  - targeted app/render tests
  - full suite
- report update:
  - regression coverage evidence。

### S04 — Manual Diff Colorization
- observable behavior:
  - manual env の多段階 commit diff produces colorized `.puml` and `.svg`.
  - changed / newly added class だけが薄い緑になり、dependency-only class は default class box のままになる。
- depends on:
  - S03
- target files:
  - ignored/manual output only under `build/manual-tests/pyclassuml-manual-env/out/iss-00033-green/`
- expected commands:
  - `uv run pyclassuml diff --cwd build/manual-tests/pyclassuml-manual-env/tmp/iss-00033-multicommit-color --base 2fa3434d7ffc40c510f47488757d60ffad8fee73 --current-state head --output ...`
  - `docker run --rm ... plantuml/plantuml:latest -tsvg ...`
  - `rg` checks for `skinparam class`, `<<DiffChanged>>`, absence of `<<DiffDependency>>`, absence of old yellow/blue colors, relation arrows.
  - SVG check confirms dependency-only `Customer` is `fill="#F1F1F1"` / `stroke:#181818`, while changed/newly added classes are `fill="#DFF5DF"` / `stroke:#4F9D5D`.
- cleanup:
  - keep manual env tracked state clean.
  - remove `uv.lock` if generated.
- report update:
  - manual command/output evidence。

### S90 — Docs / Sync / Validate
- 対象:
  - issue report only
- 対応:
  - implementation summary、test/manual/review evidence、AC/EC closure mapping を記録する。
  - `./spec-dock/scripts/spec-dock validate` を実行する。

### S99 — Final Diff Review Quality Gate
- branch diff scope:
  - `iss-00033` source/tests/issue docs only, except existing `.serena/project.yml` ignored.
- required validation:
  - targeted tests
  - full tests
  - `git diff --check`
  - `rg --files | rg '[A-Z]'` existing allowed paths only
  - `test ! -e uv.lock`
  - manual env clean after test
  - `spec-dock validate`
- reviewer approvals:
  - `spec-reviewer`: pass
  - `code-reviewer`: pass
  - `qa-reviewer`: pass
- report update:
  - final closure coverage and residual risk。

## final exit contract
- AC/EC 達成:
  - report の closure coverage に concrete test/manual evidence を持つ。
- docs impact resolved:
  - issue docs updated; broader docs not required unless implementation discovers public docs impact.
- final diff approved:
  - review pass、tests pass、manual pass、worktree has no unexpected generated files。
