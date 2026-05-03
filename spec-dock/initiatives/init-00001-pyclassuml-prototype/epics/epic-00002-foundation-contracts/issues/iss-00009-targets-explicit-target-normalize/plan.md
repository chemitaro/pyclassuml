---
種別: 実装計画書（Issue）
ID: "iss-00009"
タイトル: "Targets Explicit Target Normalize"
関連GitHub: ["#9"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
依存: ["requirement.md", "design.md"]
親: ["epic-00002", "init-00001"]
---

# iss-00009 Targets Explicit Target Normalize — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001 file / glob / dir explicit input の dedupe normalize。
  - AC-002 default ignore / user ignore の project_root relative 適用。
  - AC-003 scope outside explicit target の hard failure。
  - AC-004 zero-seed hard failure。
- EC:
  - EC-001 file + glob dedupe。
  - EC-002 dir / glob 展開結果への ignore。
  - EC-003 relative input の execution_cwd base。
  - EC-004 normalize 完了時 seed 0 件の deterministic failure。
- 制約:
  - Git diff read、dependency traversal、parse/analyze、class selection、changed class counting は実装しない。
  - ignore canonical set は initiative requirement の default ignore に従う。
  - success path で empty `TargetSet` を返さない。

## マイルストーン一覧
- M1:
  - 対象: targets package scaffold and file input normalize。
  - exit: single file input から `TargetSet(seed_files)` が返る。
- M2:
  - 対象: glob / dir expansion、dedupe、ignore。
  - exit: AC-001/AC-002/EC-001/EC-002/EC-003 が pytest で観測できる。
- M3:
  - 対象: scope outside / zero-seed failure diagnostics、review / QA / evidence。
  - exit: AC-003/AC-004/EC-004 が pytest と review evidence で観測できる。

## 実装順序の根拠
- 依存関係の正本:
  - `design.md` の `依存関係分析` と module/dependency UML を参照する
- sequencing rule:
  - upstream / prerequisite / lower-dependency slice から先に step を組む
  - downstream / dependent slice は前提が固まってから置く
- step ordering notes:
  - `iss-00007` の `TargetSet` / `TargetObservations` と `iss-00008` の `ExecutionContext` / `AnalysisConfig` を入力にする。
  - success path の deterministic seed set を先に固定し、その後に ignore と failure diagnostics を追加する。

## ステップ一覧
- S01:
  - 観測可能な振る舞い: `normalize_explicit_targets` を import でき、single Python file input が `TargetSet` へ正規化される。
  - closes: AC-001 baseline, EC-003, M1
  - depends on: `iss-00007`, `iss-00008`
  - unblocks: S02
  - target files:
    - `src/pyclassuml/targets/__init__.py`
    - `src/pyclassuml/targets/explicit.py`
    - `tests/targets/test_explicit_target_normalize.py`
  - review gate:
    - targeted pytest pass。
- S02:
  - 観測可能な振る舞い: file / glob / dir input、dedupe、default ignore / user ignore、deterministic ordering が観測できる。
  - closes: AC-001, AC-002, EC-001, EC-002, M2
  - depends on: S01
  - unblocks: S03
  - target files:
    - `src/pyclassuml/targets/explicit.py`
    - `tests/targets/test_explicit_target_normalize.py`
  - review gate:
    - targeted pytest pass。
- S03:
  - 観測可能な振る舞い: scope outside と zero-seed が canonical failure diagnostics になる。
  - closes: AC-003, AC-004, EC-004, M3
  - depends on: S02
  - unblocks: S90, S99, downstream parse / app.generate / report
  - target files:
    - `src/pyclassuml/targets/explicit.py`
    - `tests/targets/test_explicit_target_normalize.py`
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
- AC-001 -> S01
- AC-002 -> S02
- AC-003 -> S03
- AC-004 -> S03
- EC-001 -> S02
- EC-002 -> S02
- EC-003 -> S01
- EC-004 -> S03

## レビュー / QA ゲート方針
- RG1 implementation review:
  - timing:
    - S01-S03 green 後。
  - scope:
    - `src/pyclassuml/targets/**`, `tests/targets/**`。
  - commit gate:
    - pass まで review loop を回し、pass 後に `report.md` を更新して差分確認後にコミットする
- QG1 QA review:
  - timing:
    - RG1 pass 後。
  - scope:
    - AC/EC coverage、ignore semantics、failure diagnostics、deterministic ordering。
  - commit gate:
    - pass まで test loop を回し、pass 後に `report.md` を更新して差分確認後にコミットする
- SG1 spec review:
  - timing:
    - 実装前。
  - scope:
    - issue docs が implementation-ready か、interface / ignore / failure / file plan が十分か。
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

### S01 — single file explicit target normalize
- target:
  - `src/pyclassuml/targets/__init__.py`
  - `src/pyclassuml/targets/explicit.py`
  - `tests/targets/test_explicit_target_normalize.py`
- design refs:
  - `design.md` の `インターフェース契約`
  - `design.md` の `explicit input rules`
  - `design.md` の `ディレクトリ / ファイル変更計画`
- step boundary:
  - single existing `.py` file と relative path base に限定する。

#### update_plan（着手時に登録）
- [ ] `update_plan` に step の作業単位を登録した
- [ ] `./spec-dock/active/issue/report.md` の追記位置を決めた

#### B1 — single file success contract
- purpose:
  - `CommandRequest` / `ExecutionContext` / `AnalysisConfig` から `TargetSet` への最小 handoff を固定する。
- files:
  - `src/pyclassuml/targets/explicit.py`
  - `tests/targets/test_explicit_target_normalize.py`

##### I1 — file target red/green
- slice goal:
  - execution_cwd relative file input が resolved absolute `.py` seed になる。

###### Red
- failing test:
  - `uv run --with pytest pytest tests/targets/test_explicit_target_normalize.py -q`
- expected failure:
  - `ModuleNotFoundError` or missing `normalize_explicit_targets`。

###### Green
- minimum implementation:
  - `TargetNormalization` と single-file success path。
- pass condition:
  - `uv run --with pytest pytest tests/targets/test_explicit_target_normalize.py -q`

###### Refactor
- 目的:
  - Green を維持したまま、必要な範囲で構造や可読性を整える
- guardrail:
  - 振る舞いを変えない
  - この step の範囲を超えて広げない
  - 必要がなければスキップしてよい

#### step gate
- review:
  - `targets` 以外の seam logic が混入していないこと。
- expected tests:
  - `uv run --with pytest pytest tests/targets/test_explicit_target_normalize.py -q`
- report update:
  - reviewer verdict / test結果 / 修正内容 / no-op 理由を `./spec-dock/active/issue/report.md` に残す
- commit:
  - report 更新後に差分確認し、この stage の差分とまとめてコミットする

### S02 — glob / dir expansion, dedupe, and ignore
- target:
  - `src/pyclassuml/targets/explicit.py`
  - `tests/targets/test_explicit_target_normalize.py`
- step boundary:
  - success path の expansion / filtering / ordering に限定する。
- test expectations:
  - file + glob + dir input が重複除去され、resolved absolute path の昇順になる。
  - `__init__.py` を含む `.py` file だけを seed candidate にする。
  - default ignore `.venv/**`, `venv/**`, `**/__pycache__/**`, `site-packages/**` と user ignore を `project_root` relative に適用する。
  - ignored count が `TargetObservations.ignored_seed_candidate_count` に入る。

### S03 — scope outside and zero-seed failures
- target:
  - `src/pyclassuml/targets/explicit.py`
  - `tests/targets/test_explicit_target_normalize.py`
- step boundary:
  - hard failure result / diagnostics に限定する。
- test expectations:
  - scope outside explicit candidate は `FailureReason.GENERATE_SCOPE_VIOLATION` の error diagnostic になる。
  - existing file / directory と glob 展開結果は Python filtering より前に scope validation し、scope 外 non-Python file / directory も `FailureReason.GENERATE_SCOPE_VIOLATION` が勝つ。
  - scope validation は ignore filtering より前に行い、ignore に一致する scope outside path も `FailureReason.GENERATE_SCOPE_VIOLATION` が勝つ。
  - path resolution failure は `FailureReason.GENERATE_SCOPE_VIOLATION` の error diagnostic になる。
  - glob miss、missing non-glob path、all ignored は `FailureReason.GENERATE_ZERO_TARGET_AFTER_NORMALIZE` の error diagnostic になる。
  - failure result は `target_set=None` で、empty `TargetSet` を返さない。
  - failure diagnostic は `origin_seam=OriginSeam.TARGETS`, `severity=DiagnosticSeverity.ERROR`, `recoverability=Recoverability.FATAL`, canonical `failure_reason` をすべて assert する。

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
  - `uv run --with pytest pytest tests/targets/test_explicit_target_normalize.py -q`
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
  - ignore canonical set、explicit input shape、failure taxonomy は issue design で固定済み。

## final exit contract
- AC/EC 達成:
  - AC-001/AC-002/AC-003/AC-004/EC-001/EC-002/EC-003/EC-004 が tests と review evidence で観測できる。
- docs impact resolved:
  - issue docs と report のみ更新し、恒久 docs 変更なしの判断を残す。
- final diff approved:
  - code-reviewer / qa-reviewer が pass し、SpecDock validate/sync evidence が report に記録されている。
