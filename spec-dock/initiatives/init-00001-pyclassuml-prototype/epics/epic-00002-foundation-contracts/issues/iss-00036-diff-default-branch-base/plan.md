---
種別: 実装計画書（Issue）
ID: "iss-00036"
タイトル: "Diff Default Branch Base"
関連GitHub: ["#36"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-21"
依存: ["requirement.md", "design.md"]
親: ["epic-00002", "init-00001"]
---

# iss-00036 Diff Default Branch Base — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001: `pyclassuml diff` の default branch merge-base 解決。
  - AC-002: `--base <ref>` の既存互換。
  - AC-003: initial commit fallback。
  - AC-004: `--current-state head` との整合。
- EC:
  - EC-001: commit なし repository。
  - EC-002: candidate merge-base failure。
  - EC-003: default branch 自身での fallback。
- 制約:
  - read-only Git 操作、deterministic resolver、対象コード import 不使用。

## 依存関係から導く実装順序
- 依存関係の正本:
  - `design.md` の module dependency diagram と file change plan。
- step 依存 summary:
  - S01:
    - 依存: なし。
    - unblock: CLI / DTO が `--base` optional を表現できる。
    - 対象ファイル: `cli.bind`, `model.contracts`, `config.resolver`, related tests。
  - S02:
    - 依存: S01。
    - unblock: `vcs.diff_collect` が resolved base を必ず持てる。
    - 対象ファイル: `vcs.diff_collect`, vcs tests。
  - S03:
    - 依存: S02。
    - unblock: app/report/README が user-visible behavior を閉じる。
    - 対象ファイル: `app.diff`, `report`, `README.md`, integration tests。

## ステップ一覧
- S01:
  - 観測可能な振る舞い: `pyclassuml diff` が usage error にならず、optional base DTO として bind される。
  - レビューゲート: code-reviewer。
- S02:
  - 観測可能な振る舞い: `--base` 未指定時に deterministic resolver が default branch merge-base または initial commit fallback を返す。
  - レビューゲート: code-reviewer。
- S03:
  - 観測可能な振る舞い: resolved base が app/report/README で観測でき、`--current-state head` も既存仕様と整合する。
  - レビューゲート: code-reviewer。
- S90:
  - docs impact resolution。
- S99:
  - final QA / code / spec review と final commit gate。

## 要件 ↔ ステップ対応
- AC-001 -> S02, S03
- AC-002 -> S01, S02
- AC-003 -> S02, S03
- AC-004 -> S02, S03
- EC-001 -> S02
- EC-002 -> S02
- EC-003 -> S02

## Spec-Locked Closure Index（仕様固定クロージャ索引）

| id | step | slice | type | spec link | locked expectation | observable input/state | bug class guarded | required | evidence level | closure evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| tc-001 | S01 | cli-model | acceptance | AC-002 | `diff --base <ref>` remains explicit and `diff` without base is valid | parser bind inputs | compatibility break / usage error regression | yes | red-required | report step closure |
| tc-002 | S02 | vcs-resolver | acceptance | AC-001 | no-base diff resolves merge-base against default branch candidate | temp repo with default branch and feature branch | wrong default base / no-base failure | yes | red-required | report step closure |
| tc-003 | S02 | fallback | acceptance | AC-003, EC-003 | no-base diff falls back to initial commit when no candidate is usable | repo without usable default candidate | arrogant config/upstream requirement | yes | red-required | report step closure |
| tc-004 | S02 | failure | negative | EC-001 | no-commit repo fails before parse/analyze | empty git repo | ambiguous base / late pipeline failure | yes | red-required | report step closure |
| tc-005 | S03 | current-state | acceptance | AC-004 | resolved base works with `--current-state head` and keeps untracked semantics | feature branch with working-tree-only file | head/working-tree semantic drift | yes | red-required | report step closure |
| tc-006 | S03 | docs-report | acceptance | AC-001, AC-003 | resolved base and resolution kind are visible in diagnostics/report/docs | command/report inspection | silent surprising base choice | yes | red-required | report step closure |

## レビュー / QA ゲート方針
- RG1 step review:
  - 実施タイミング: 各 implementation step の commit 前。
  - reviewer: code-reviewer。
  - pass 条件: review_status: pass。
- QG1 final QA:
  - reviewer: qa-reviewer。
  - 範囲: Issue 全体の obligation coverage、missing high-value tests、manual / integration test 要否。
- SG1 final spec review:
  - reviewer: spec-reviewer。
  - 範囲: requirement / design / plan / report / docs 整合。

## 実行ルール（全ステップ共通）
- `plan.md` には planned requirements、evidence destination、closure 条件だけを書く。
- observed result、逸脱、discovered tests、reviewer verdict、commit/no-op evidence は `report.md` に記録する。
- implementation 中に resolver の候補順や diagnostic severity を変更する必要が出た場合は、`report.md` の decision ledger に記録し、必要なら plan amendment と re-review を行う。

## 実装ステップ

### S01 — CLI / DTO の `--base` optional 化
- behavior goal:
  - `pyclassuml diff` が valid invocation になり、明示 `--base <ref>` は既存どおり bind される。
- design 参照:
  - `design.md` のインターフェース契約。
- 依存:
  - なし。
- unblock:
  - S02 が no-base と explicit-base を区別できる。
- 対象ファイル:
  - `src/pyclassuml/cli/bind.py`
  - `src/pyclassuml/model/contracts.py`
  - `src/pyclassuml/config/resolver.py`
  - `tests/cli/test_bind.py`
  - `tests/model/test_contracts.py`
  - `tests/config/test_context_resolve.py`
- planned contract:
  - test obligation:
    - closure id: tc-001
    - coverage rationale: CLI usage compatibility と DTO invariant の regression を検出する。
  - Red / alternative evidence requirement:
    - red-required: `diff` without `--base` bind test と explicit `--base` compatibility test。
  - implementation scope:
    - allowed paths: 対象ファイルに限定。
    - forbidden changes: diff collection algorithm の実装。
  - Green verification:
    - `uv run pytest tests/cli/test_bind.py tests/model/test_contracts.py tests/config/test_context_resolve.py`
  - report evidence destination:
    - `report.md` の S01 session、Step Contract Closure、Test Contract Closure。
  - amendment trigger:
    - `DiffOptions` に optional field 以外の大きな DTO 再設計が必要になった場合。

### S02 — VCS branch-start base resolver
- behavior goal:
  - `--base` 未指定時に default branch candidate merge-base、または initial commit fallback を resolved base として返す。
- design 参照:
  - `design.md` の採用方針 / インターフェース契約。
- 依存:
  - S01。
- unblock:
  - S03 が resolved base diagnostics と app integration を閉じられる。
- 対象ファイル:
  - `src/pyclassuml/vcs/diff_collect.py`
  - `tests/vcs/test_diff_file_collect.py`
- planned contract:
  - test obligation:
    - closure id: tc-002, tc-003, tc-004
    - coverage rationale: no-base happy path、fallback path、no-commit failure を固定する。
  - Red / alternative evidence requirement:
    - red-required: temp Git repository fixtures で default branch merge-base / fallback / no commit failure を検出する tests。
  - implementation scope:
    - allowed paths: vcs diff collection と vcs tests。
    - forbidden changes: parser / renderer / analyzer behavior。
  - Green verification:
    - `uv run pytest tests/vcs/test_diff_file_collect.py`
  - report evidence destination:
    - `report.md` の S02 session、Step Contract Closure、Test Contract Closure。
  - amendment trigger:
    - candidate priority を Q-001 推奨案から変える場合。

### S03 — App / report / docs integration
- behavior goal:
  - resolved base が app pipeline、report diagnostics、README で観測でき、`--current-state head` との整合を確認する。
- design 参照:
  - `design.md` のテスト戦略とリスク緩和。
- 依存:
  - S02。
- unblock:
  - S90 / S99。
- 対象ファイル:
  - `src/pyclassuml/app/diff.py`
  - `src/pyclassuml/report/`
  - `README.md`
  - `tests/app/test_diff.py`
  - `tests/report/test_policy.py`
  - `tests/cli/test_main.py`
- planned contract:
  - test obligation:
    - closure id: tc-005, tc-006
    - coverage rationale: current-state semantics と user-visible explanation の regression を検出する。
  - Red / alternative evidence requirement:
    - red-required: no-base `--current-state head` integration test と diagnostics/report assertion。
  - implementation scope:
    - allowed paths: app/report/docs/integration tests。
    - forbidden changes: UML rendering algorithm の仕様外変更。
  - Green verification:
    - `uv run pytest tests/app/test_diff.py tests/report/test_policy.py tests/cli/test_main.py`
  - report evidence destination:
    - `report.md` の S03 session、Step Contract Closure、Test Contract Closure。
  - amendment trigger:
    - report schema / summary contract の変更が必要になった場合。

### S90 — docs impact resolution / docs refresh
- 対象:
  - `README.md`
  - 必要に応じて config reference。
- 対応:
  - `diff [options] [--base <ref>]`、`--base` 省略時の best effort resolver、initial commit fallback、明示 `--base` の後方互換を文書化する。
- spec/doc review:
  - reviewer: spec-reviewer。
  - pass 条件: docs が requirement / design / plan と整合する。

### S99 — final quality gate
- branch diff 範囲:
  - `iss-00036` issue branch 全体。
- 必須 validation:
  - `uv run pytest`
  - `./spec-dock/scripts/spec-dock validate`
  - `git diff --check`
- final QA gate:
  - reviewer: qa-reviewer。
  - 範囲: obligation coverage と integration test 要否。
  - pass 条件: reviewer pass。
- final code review ゲート:
  - reviewer: code-reviewer。
  - 範囲: issue-wide integrated diff、構造、責務境界、回帰リスク、保守性。
  - pass 条件: review_status: pass。
- final spec review ゲート:
  - reviewer: spec-reviewer。
  - 範囲: requirement / design / plan / report / implementation / tests / docs 整合。
  - pass 条件: reviewer pass。
- final commit gate:
  - commit 範囲: issue implementation, tests, docs, report ledger。
  - post-commit external evidence destination: final response / PR description。

## 未確定事項
- Q-001:
  - 質問: default branch candidate の固定順序。
  - 推奨案: `origin/HEAD`, `origin/main`, `origin/develop`, `main`, `develop`, `master`。
  - 影響範囲: resolver tests、README 文面。

## 最終完了条件
- AC/EC 達成:
  - AC-001〜AC-004、EC-001〜EC-003 が closure evidence で閉じている。
- docs 影響解決:
  - README 更新済み。
- 全 implementation step 完了:
  - S01〜S03 committed / approved-no-op。
- final quality gate pass:
  - qa-reviewer / code-reviewer / spec-reviewer が pass。
