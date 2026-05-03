---
種別: 実装計画書（Issue）
ID: "iss-00010"
タイトル: "VCS Diff File Collect"
関連GitHub: ["#10"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
依存: ["requirement.md", "design.md"]
親: ["epic-00002", "init-00001"]
---

# iss-00010 VCS Diff File Collect — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001 valid base/current_state/include_untracked matrix。
  - AC-002 invalid base / Git diff read failure の hard failure。
  - AC-003 `current_state=head` + `include_untracked=true` の no-op warning。
- EC:
  - EC-001 untracked file がない状態での include_untracked=true。
  - EC-002 scope filtering せず raw changed paths を収集する。
- 制約:
  - Git repository は read-only に扱う。
  - `project_root` は config が確定したものを使う。
  - `TargetSet`、scope filtering、summary/exit policy は実装しない。

## マイルストーン一覧
- M1:
  - 対象: vcs package scaffold and working-tree tracked diff。
  - exit: valid base から tracked changed files を `ChangedFileCollection` で返す。
- M2:
  - 対象: head state、untracked option、rename/delete normalization。
  - exit: matrix と name-status parsing が pytest で観測できる。
- M3:
  - 対象: invalid base / Git read failure / no-op warning / review evidence。
  - exit: failure diagnostics と warning diagnostics が pytest と review evidence で観測できる。

## 実装順序の根拠
- 依存関係の正本:
  - `design.md` の `依存関係分析` と module/dependency UML を参照する
- sequencing rule:
  - upstream / prerequisite / lower-dependency slice から先に step を組む
  - downstream / dependent slice は前提が固まってから置く
- step ordering notes:
  - `iss-00007` の `CommandRequest` / `Diagnostic` と `iss-00008` の `ExecutionContext` / `AnalysisConfig` を入力にする。
  - Git command execution と name-status parsing を先に閉じ、scope filtering と `TargetSet` 生成は `iss-00011` に残す。

## ステップ一覧
- S01:
  - 観測可能な振る舞い: `collect_diff_files` を import でき、working-tree tracked diff が `ChangedFileCollection` になる。
  - closes: M1
  - depends on: `iss-00007`, `iss-00008`
  - unblocks: S02
  - target files:
    - `src/pyclassuml/vcs/__init__.py`
    - `src/pyclassuml/vcs/diff_collect.py`
    - `tests/vcs/test_diff_file_collect.py`
  - review gate:
    - targeted pytest pass。
- S02:
  - 観測可能な振る舞い: working-tree/head、include_untracked、rename/delete handling、scope filtering なしが観測できる。
  - closes: AC-001, AC-003, EC-001, EC-002, M2
  - depends on: S01
  - unblocks: S03
  - target files:
    - `src/pyclassuml/vcs/diff_collect.py`
    - `tests/vcs/test_diff_file_collect.py`
  - review gate:
    - targeted pytest pass。
- S03:
  - 観測可能な振る舞い: invalid base / Git command failure が canonical failure diagnostics になる。
  - closes: AC-002, M3
  - depends on: S02
  - unblocks: S90, S99, downstream `iss-00011`
  - target files:
    - `src/pyclassuml/vcs/diff_collect.py`
    - `tests/vcs/test_diff_file_collect.py`
  - review gate:
    - targeted pytest pass。
- S90:
  - 観測可能な振る舞い: docs impact が issue-scoped report へ記録される。
  - closes: docs impact resolution
  - depends on: S03
  - unblocks: S99
  - target files:
    - `spec-dock/active/issue/report.md`
  - review gate:
    - report に判断を残す。
- S99:
  - 観測可能な振る舞い: final validation、code review、QA review、SpecDock evidence が揃う。
  - closes: final exit contract
  - depends on: S90
  - unblocks: issue close / next ready issue
  - target files:
    - `spec-dock/active/issue/report.md`
  - review gate:
    - required review verdict が pass。

## 要件 ↔ ステップ対応
- AC-001 -> S01, S02
- AC-002 -> S03
- AC-003 -> S02
- EC-001 -> S02
- EC-002 -> S02

## レビュー / QA ゲート方針
- RG1 implementation review:
  - timing:
    - S01-S03 green 後。
  - scope:
    - `src/pyclassuml/vcs/**`, `tests/vcs/**`。
  - commit gate:
    - pass まで review loop を回し、pass 後に `report.md` を更新して差分確認後にコミットする
- QG1 QA review:
  - timing:
    - RG1 pass 後。
  - scope:
    - matrix coverage、failure diagnostics、Git fixture isolation、read-only boundary。
  - commit gate:
    - pass まで test loop を回し、pass 後に `report.md` を更新して差分確認後にコミットする
- SG1 spec review:
  - timing:
    - 実装前。
  - scope:
    - issue docs が implementation-ready か、git command contract / name-status parsing / failure taxonomy / file plan が十分か。
  - commit gate:
    - pass まで review loop を回し、pass 後に `report.md` を更新してドキュメントだけをコミットする

## 実行ルール（全ステップ共通）
- plan 全体は実装着手前に承認する。
- cadence / approval policy は `workflow_issue.md` を正本とする。
- 互換参照: `Red → Green → Refactor → review → fix → re-review → report → commit/no-op`
- 各 step は 1 つの観測可能な振る舞いを単位とする。
- `block` は optional concern group。単純な step では最小 wrapper 1 個でよい。
- `iteration` は 1 回の TDD cycle とし、各 iteration は `Red → Green → Refactor` で閉じる。
- failing test は iteration ごとに 1 本ずつ進める。
- `Green` は最小実装、`Refactor` は green 維持を前提とする。
- shared minimum gate と scope-specific readiness contract / final exit contract を満たす。
- docs impact が `none` でなければ `S90` を実行する。
- 最後に `git diff <base>...HEAD` を対象に `S99 final diff review quality gate` を実施する。
- reviewer verdict は `report.md` に残す。
- 各 stage gate（SG/RG/QG）は `pass` まで回す。
- 各 stage gate の `pass` 後は、`report.md` を更新し、差分確認後に report とまとめてコミットする。
- no-op の場合のみ `report.md` に理由を残し、commit を省略できる。

## 実装ステップ

### S01 — working-tree tracked diff collection
- target:
  - `src/pyclassuml/vcs/__init__.py`
  - `src/pyclassuml/vcs/diff_collect.py`
  - `tests/vcs/test_diff_file_collect.py`
- design refs:
  - `design.md` の `インターフェース契約`
  - `design.md` の `git command contract`
  - `design.md` の `ディレクトリ / ファイル変更計画`
- step boundary:
  - valid base と working-tree tracked A/M/D/R diff の success path に限定する。

#### update_plan（着手時に登録）
- [ ] `update_plan` に step の作業単位を登録した
- [ ] `./spec-dock/active/issue/report.md` の追記位置を決めた

#### B1 — tracked diff success contract
- purpose:
  - Git `--name-status` を seam-local collection に変換する。
- files:
  - `src/pyclassuml/vcs/diff_collect.py`
  - `tests/vcs/test_diff_file_collect.py`

##### I1 — working-tree diff red/green
- slice goal:
  - base commit から working tree までの added / modified / renamed を current path で収集し、delete-only を除外する。

###### Red
- failing test:
  - `uv run --with pytest pytest tests/vcs/test_diff_file_collect.py -q`
- expected failure:
  - `ModuleNotFoundError` or missing `collect_diff_files`。

###### Green
- minimum implementation:
  - seam-local DTO、Git command runner、name-status parser、working-tree tracked diff。
- pass condition:
  - `uv run --with pytest pytest tests/vcs/test_diff_file_collect.py -q`

###### Refactor
- 目的:
  - Green を維持したまま、必要な範囲で構造や可読性を整える
- guardrail:
  - 振る舞いを変えない
  - この step の範囲を超えて広げない
  - 必要がなければスキップしてよい

#### step gate
- review:
  - `vcs` が scope filtering / TargetSet generation を持たないこと。
- expected tests:
  - `uv run --with pytest pytest tests/vcs/test_diff_file_collect.py -q`
- report update:
  - reviewer verdict / test結果 / 修正内容 / no-op 理由を `./spec-dock/active/issue/report.md` に残す
- commit:
  - report 更新後に差分確認し、この stage の差分とまとめてコミットする

### S02 — head / untracked / warning matrix
- target:
  - `src/pyclassuml/vcs/diff_collect.py`
  - `tests/vcs/test_diff_file_collect.py`
- test expectations:
  - `current_state=working-tree`, `include_untracked=true` は untracked を `added` として含める。
  - `current_state=working-tree`, `include_untracked=false` は untracked を含めない。
  - `current_state=working-tree`, `include_untracked=true` で untracked file がない場合も failure せず collection を返す。
  - `current_state=head` は `base_ref..HEAD` の tracked diff を返す。
  - `current_state=head`, `include_untracked=true` は untracked を含めず `code=head_untracked_noop`, `origin_seam=OriginSeam.VCS`, `severity=DiagnosticSeverity.WARNING`, `recoverability=Recoverability.RECOVERABLE`, `failure_reason=None` の warning を返す。
  - scope 外 path もそのまま `ChangedFileCollection` に含め、scope filtering しない。

### S03 — invalid base and git read failure diagnostics
- target:
  - `src/pyclassuml/vcs/diff_collect.py`
  - `tests/vcs/test_diff_file_collect.py`
- test expectations:
  - invalid `base_ref` は `FailureReason.VCS_READ_FAILURE` の error diagnostic になる。
  - non-Git / Git command failure は `FailureReason.VCS_READ_FAILURE` の error diagnostic になる。
  - invalid base は `code=invalid_base_ref`、Git command failure は `code=git_diff_read_failure`、unsupported status / path decode failure は `code=git_diff_parse_failure` を assert する。
  - failure result は `collection=None` で、ambiguous changed files を返さない。
  - failure diagnostic は `origin_seam=OriginSeam.VCS`, `severity=DiagnosticSeverity.ERROR`, `recoverability=Recoverability.FATAL`, canonical `failure_reason` をすべて assert する。

### nested の使い方
- `step` は常に使う
- `block` は必要な時だけ分ける
- `iteration` は必要な数だけ並べる
- review / QA / docs / final diff は iteration の外に置く

### S90 — docs impact resolution / docs refresh
- 対象:
  - issue-scoped docs only
- 対応:
  - `requirement.md` / `design.md` / `plan.md` / `report.md` の整合を確認する。
  - root `AGENTS.md`、README、SpecDock workflow docs への恒久 docs 変更は不要と判断する。

### S99 — final diff review quality gate
- branch diff scope:
  - `git diff origin/main...HEAD` と working tree diff。
- required validation:
  - `uv run --with pytest pytest tests/vcs/test_diff_file_collect.py -q`
  - `uv run --with pytest pytest -q`
  - `./spec-dock/scripts/spec-dock validate`
  - `./spec-dock/scripts/spec-dock sync --github`
  - `rg --files | rg '[A-Z]'`
- reviewer approvals:
  - spec-reviewer pass
  - code-reviewer pass
  - qa-reviewer pass
- report update:
  - final diff review verdict / closing evidence / no-op 理由を `./spec-dock/active/issue/report.md` に残す
- commit expectation:
  - `report.md` 更新後に差分確認し、追加修正があれば最終コミットを作成する。無ければ直前 gate のコミットを最終成果として扱う

## 未確定事項
- なし:
  - git command contract、name-status parsing、failure taxonomy は issue design で固定済み。

## final exit contract
- AC/EC 達成:
  - AC-001/AC-002/AC-003/EC-001/EC-002 が tests と review evidence で観測できる。
- docs impact resolved:
  - issue docs と report のみ更新し、恒久 docs 変更なしの判断を残す。
- final diff approved:
  - code-reviewer / qa-reviewer が pass し、SpecDock validate/sync evidence が report に記録されている。
