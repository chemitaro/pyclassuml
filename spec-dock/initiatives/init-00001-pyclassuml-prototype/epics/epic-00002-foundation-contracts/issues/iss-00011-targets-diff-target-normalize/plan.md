---
種別: 実装計画書（Issue）
ID: "iss-00011"
タイトル: "Targets Diff Target Normalize"
関連GitHub: ["#11"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md"]
親: ["epic-00002", "init-00001"]
---

# iss-00011 Targets Diff Target Normalize — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001 scope 内外が混在する changed files から scope 内 Python seed だけを `TargetSet.seed_files` に残し、scope 外 file を exclusion として記録する。
  - AC-002 scope filtering 後 seed が 0 件なら `diff_zero_target_after_scope_filter` の failure とし、後段 parse へ empty target を渡さない。
  - AC-003 exclusion diagnostics / counters を downstream が strict / warn policy に使える形で carry する。
- EC:
  - EC-001 changed files がすべて scope 外なら exclusion 記録後に zero-target failure となる。
  - EC-002 duplicate changed file は unique な seed set に正規化する。
  - EC-003 upstream `vcs` diagnostics は失わず carry し、`targets.diff` 自身は scope filtering / ignore / zero-target に集中する。
- 制約:
  - Git diff を再実行しない。
  - explicit target normalize を行わない。
  - changed class summary、`.puml` 出力、final exit policy、summary stream routing は実装しない。
  - ignore 判定は `project_root` relative で行い、owner は `targets.diff-target-normalize` とする。
  - zero-target hard failure の `failure_reason` は `diff_zero_target_after_scope_filter` に固定する。
  - scope outside exclusion は warning / counter として carry し、strict 昇格素材として `strict_diff_scope_exclusion` を downstream が選べるようにする。

## マイルストーン一覧
- M1:
  - 対象: `targets.diff` public seam scaffold and mixed inside/outside changed-file normalization。
  - exit: scope 内 Python file が `TargetSet.seed_files` になり、scope 外 file が warning diagnostic と counter に残る。
- M2:
  - 対象: ignore、dedupe、non-Python filtering、upstream diagnostics carry。
  - exit: AC-001/AC-003/EC-002/EC-003 が pytest で観測できる。
- M3:
  - 対象: zero-target failure、all-outside scenario、review / QA / evidence。
  - exit: AC-002/EC-001 が pytest と report evidence で観測できる。

## 実装順序の根拠
- 依存関係の正本:
  - `design.md` の module/dependency UML と `インターフェース契約` を参照する。
- sequencing rule:
  - upstream `ChangedFileCollection` と shared `TargetSet` contract を先に接続する。
  - success path の seed / exclusion / counter を固定してから ignore と failure path を足す。
- step ordering notes:
  - `iss-00008` の `ExecutionContext` / `AnalysisConfig` と `iss-00010` の `ChangedFileCollection` を入力にする。
  - downstream `parse` / `report` / `app.diff-wiring` はこの issue では呼ばず、diagnostics と observations の handoff shape だけを固定する。

## ステップ一覧
- S01:
  - 観測可能な振る舞い: `normalize_diff_targets` を import でき、scope 内 Python changed file が `TargetSet` になり、scope 外 changed file が exclusion warning / counter として残る。
  - closes: AC-001 baseline, AC-003 baseline, M1
  - depends on: `iss-00008`, `iss-00010`
  - unblocks: S02
  - target files:
    - `src/pyclassuml/targets/__init__.py`
    - `src/pyclassuml/targets/diff.py`
    - `src/pyclassuml/targets/ignore.py`
    - `tests/targets/test_diff_target_normalize.py`
  - review gate:
    - targeted pytest pass。
- S02:
  - 観測可能な振る舞い: project_root relative ignore、non-Python filtering、duplicate current path dedupe、upstream diagnostics carry が観測できる。
  - closes: AC-001, AC-003, EC-002, EC-003, M2
  - depends on: S01
  - unblocks: S03
  - target files:
    - `src/pyclassuml/targets/explicit.py`
    - `src/pyclassuml/targets/diff.py`
    - `src/pyclassuml/targets/ignore.py`
    - `tests/targets/test_diff_target_normalize.py`
  - review gate:
    - targeted pytest pass。
- S03:
  - 観測可能な振る舞い: filtering 後 seed 0 件が `diff_zero_target_after_scope_filter` failure になり、empty `TargetSet` success を返さない。
  - closes: AC-002, EC-001, M3
  - depends on: S02
  - unblocks: S90, S99, downstream parse / app.diff / report
  - target files:
    - `src/pyclassuml/targets/diff.py`
    - `tests/targets/test_diff_target_normalize.py`
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
  - 観測可能な振る舞い: final validation、implementation review、QA review、SpecDock evidence が揃う。
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
- AC-003 -> S01, S02
- EC-001 -> S03
- EC-002 -> S02
- EC-003 -> S02

## レビュー / QA ゲート方針
- RG1 implementation review:
  - timing:
    - S01-S03 green 後。
  - scope:
    - `src/pyclassuml/targets/**`, `tests/targets/**`。
  - commit gate:
    - pass まで review loop を回し、pass 後に `report.md` を更新して差分確認後にコミットする。
- QG1 QA review:
  - timing:
    - RG1 pass 後。
  - scope:
    - AC/EC coverage、scope exclusion diagnostics、ignore semantics、zero-target failure、deterministic ordering。
  - commit gate:
    - pass まで test loop を回し、pass 後に `report.md` を更新して差分確認後にコミットする。
- SG1 spec review:
  - timing:
    - 実装前。
  - scope:
    - issue docs が implementation-ready か、interface / exclusion / ignore / failure / file plan が十分か。
  - commit gate:
    - pass まで review loop を回し、pass 後に `report.md` を更新してドキュメントだけをコミットする。

## 実行ルール（全ステップ共通）
- cadence / approval policy は `workflow_issue.md` を正本とする。
- 互換参照: `Red -> Green -> Refactor -> review -> fix -> re-review -> report -> commit/no-op`
- 各 step は 1 つの観測可能な振る舞いを単位とする。
- failing test は iteration ごとに 1 本ずつ進める。
- `Green` は最小実装、`Refactor` は green 維持を前提とする。
- docs impact が `none` でなければ `S90` を実行する。
- 最後に `git diff <base>...HEAD` を対象に `S99 final diff review quality gate` を実施する。
- reviewer verdict は `report.md` に残す。
- 各 stage gate（SG/RG/QG）は `pass` まで回す。
- no-op の場合のみ `report.md` に理由を残し、commit を省略できる。

## 実装ステップ

### S01 — diff changed-file scope filtering and exclusion handoff
- target:
  - `src/pyclassuml/targets/__init__.py`
  - `src/pyclassuml/targets/diff.py`
  - `src/pyclassuml/targets/ignore.py`
  - `tests/targets/test_diff_target_normalize.py`
- design refs:
  - `design.md` の `インターフェース契約`
  - `design.md` の `主要フロー`
  - `design.md` の `data / DTO handoff`
- step boundary:
  - changed-file collection を受け取り、scope 内 Python seed と scope outside warning / counter を返す success path に限定する。

#### B1 — mixed inside/outside success contract
- purpose:
  - `ChangedFileCollection` / `ExecutionContext` / `AnalysisConfig` から `TargetSet` への diff front-stage handoff を固定する。
- files:
  - `src/pyclassuml/targets/diff.py`
  - `tests/targets/test_diff_target_normalize.py`

##### I1 — mixed scope red/green
- slice goal:
  - scope 内 Python changed file だけが resolved absolute seed になり、scope 外 changed file が warning diagnostic と `diff_scope_excluded_count` に残る。

###### Red
- failing test:
  - `uv run --with pytest pytest tests/targets/test_diff_target_normalize.py -q`
- expected failure:
  - missing `normalize_diff_targets` or missing `pyclassuml.targets.diff`。

###### Green
- minimum implementation:
  - `normalize_diff_targets` と `DiffTargetNormalization` を追加し、scope filtering / exclusion warning / counter を返す。
- pass condition:
  - `uv run --with pytest pytest tests/targets/test_diff_target_normalize.py -q`

###### Refactor
- 目的:
  - Green を維持したまま、explicit normalize との重複 helper の扱いを必要最小限で整える。
- guardrail:
  - explicit target の behavior を変えない。
  - Git diff collection、parse、report を呼ばない。

### S02 — ignore, dedupe, non-Python filtering, and upstream carry
- target:
  - `src/pyclassuml/targets/explicit.py`
  - `src/pyclassuml/targets/diff.py`
  - `src/pyclassuml/targets/ignore.py`
  - `tests/targets/test_diff_target_normalize.py`
- step boundary:
  - success path の filtering / ordering / handoff に限定する。
  - generate / diff 共通の ignore helper 抽出は behavior-preserving refactor に限定する。
- test expectations:
  - `current_project_relative_path` は `project_root` relative として解釈され、resolved absolute `.py` seed になる。
  - default ignore `.venv/**`, `venv/**`, `**/__pycache__/**`, `site-packages/**` と user ignore を `project_root` relative に適用する。
  - ignored count が `TargetObservations.ignored_seed_candidate_count` に入る。
  - duplicate current path は unique 化され、seed ordering は deterministic。
  - non-Python changed file は seed に入らない。
  - upstream `vcs` diagnostics がある場合、targets diagnostics に順序を保って carry される。

### S03 — zero-target failure after scope filtering
- target:
  - `src/pyclassuml/targets/diff.py`
  - `tests/targets/test_diff_target_normalize.py`
- step boundary:
  - hard failure result / diagnostics に限定する。
- test expectations:
  - scope filtering / ignore / non-Python filtering 後に seed が空なら `FailureReason.DIFF_ZERO_TARGET_AFTER_SCOPE_FILTER` の error diagnostic になる。
  - failure result は `target_set=None` で、empty `TargetSet` を返さない。
  - all-outside scenario では exclusion warning と zero-target error の両方が diagnostics に残る。
  - failure diagnostic は `origin_seam=OriginSeam.TARGETS`, `severity=DiagnosticSeverity.ERROR`, `recoverability=Recoverability.FATAL`, canonical `failure_reason` をすべて assert する。

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
  - `uv run --with pytest pytest tests/targets/test_diff_target_normalize.py -q`
  - `uv run --with pytest pytest tests/targets/test_explicit_target_normalize.py tests/vcs/test_diff_file_collect.py -q`
  - `uv run --with pytest pytest -q`
  - `./spec-dock/scripts/spec-dock validate`
  - `./spec-dock/scripts/spec-dock sync --github`
  - `rg --files | rg '[A-Z]'`
- reviewer approvals:
  - spec review pass
  - implementation review pass
  - QA review pass
- report update:
  - final diff review verdict / closing evidence / no-op 理由を `./spec-dock/active/issue/report.md` に残す。
- commit expectation:
  - `report.md` 更新後に差分確認し、追加修正があれば最終コミットを作成する。無ければ直前 gate のコミットを最終成果として扱う。

## 未確定事項
- なし:
  - observable behavior、failure taxonomy、downstream handoff は requirement / design で固定済みである。

## final exit contract
- AC/EC 達成:
  - AC-001/AC-002/AC-003/EC-001/EC-002/EC-003 が tests と review evidence で観測できる。
- docs impact resolved:
  - issue docs と report のみ更新し、恒久 docs 変更なしの判断を残す。
- final diff approved:
  - implementation review / QA review が pass し、SpecDock validate/sync evidence が report に記録されている。
