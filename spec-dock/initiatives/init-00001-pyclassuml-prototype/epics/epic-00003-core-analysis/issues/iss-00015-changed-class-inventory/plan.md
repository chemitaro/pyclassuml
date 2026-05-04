---
種別: 実装計画書（Issue）
ID: "iss-00015"
タイトル: "Changed Class Inventory"
関連GitHub: ["#15"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md"]
親: ["epic-00003", "init-00001"]
---

# iss-00015 Changed Class Inventory — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001 changed file 集合と parsed module 群から `ChangedClassInventory(class_count, changed_files)` を作る。
  - AC-002 reachable graph に乗らない changed file class も changed class 数へ含める。
  - AC-003 class を持たない changed file は changed_files に残し、class_count へ加算しない。
- EC:
  - EC-001 upstream handed-off changed file 集合だけを対象にし、ignore / seed normalization owner を侵食しない。
  - EC-002 relation の有無や selected classes に依存せず class_count を算出する。
  - EC-003 同一 file 内の複数 class を class 定義単位で数える。
  - EC-004 syntax error 等で join 不成立の changed file は changed_files に残し、class_count は増やさず、追加 diagnostics は作らない。
- 制約:
  - Git diff 収集は行わない。
  - hunk 粒度 changed class 判定は行わない。
  - traversal / selection / render の結果を count source にしない。
  - summary stream / exit code / formatting は決めない。
  - changed file path は project-root relative `Path` とし、absolute path normalization は upstream owner に残す。

## マイルストーン一覧
- M1:
  - 対象: inventory public seam と class count baseline。
  - exit: changed file に対応する parsed module classes が `class_count` に加算される。
- M2:
  - 対象: join miss、classless file、multi-class file、selection 分離。
  - exit: changed_files carry と count semantics が pytest で観測できる。

## 実装順序の根拠
- 依存関係の正本:
  - `design.md` の `インターフェース契約`、`主要フロー`、`data / handoff` を参照する。
- sequencing rule:
  - changed file 集合と parsed module join を先に固定する。
  - join miss / classless / multi-class と selection 分離を追加する。
- step ordering notes:
  - `iss-00012` の `ModuleIndex.project_relative_file_to_module` と `ParsedModule.classes` を入力にする。
  - `iss-00014` の `SelectedClasses` / `SelectedRelations` は入力にしない。

## ステップ一覧
- S01:
  - 観測可能な振る舞い: `build_changed_class_inventory` が changed file に対応する parsed module classes を数え、deterministic な `ChangedClassInventory` を返す。
  - closes: AC-001, EC-003, M1
  - target files:
    - `src/pyclassuml/analyze/changed.py`
    - `src/pyclassuml/analyze/__init__.py`
    - `tests/analyze/test_changed_inventory.py`
  - review gate:
    - `uv run --with pytest pytest tests/analyze/test_changed_inventory.py -q` pass。
- S02:
  - 観測可能な振る舞い: unreachable changed class、classless changed file、join-miss changed file を selection/traversal から独立して扱う。
  - closes: AC-002, AC-003, EC-001, EC-002, EC-004, M2
  - depends on: S01
  - target files:
    - `src/pyclassuml/analyze/changed.py`
    - `tests/analyze/test_changed_inventory.py`
  - review gate:
    - `uv run --with pytest pytest tests/analyze/test_changed_inventory.py -q` pass。
- S90:
  - 観測可能な振る舞い: docs impact が issue-scoped report へ記録される。
  - closes: docs impact resolution
  - depends on: S02
  - target files:
    - `spec-dock/active/issue/report.md`
  - review gate:
    - report に判断を残す。
- S99:
  - 観測可能な振る舞い: final validation、implementation review、QA review、SpecDock evidence が揃う。
  - closes: final exit contract
  - depends on: S90
  - target files:
    - `spec-dock/active/issue/report.md`
  - review gate:
    - required review verdict が pass。

## 要件 ↔ ステップ対応
- AC-001 -> S01
- AC-002 -> S02
- AC-003 -> S02
- EC-001 -> S02
- EC-002 -> S02
- EC-003 -> S01
- EC-004 -> S02

## レビュー / QA ゲート方針
- SG1 spec review:
  - timing:
    - 実装前。
  - scope:
    - issue docs が implementation-ready か、changed file path semantics と join miss behavior が十分か。
  - commit gate:
    - pass まで review loop を回し、pass 後に `report.md` を更新して docs repair をコミットする。
- RG1 implementation review:
  - timing:
    - S01-S02 green 後。
  - scope:
    - `src/pyclassuml/analyze/changed.py`, `src/pyclassuml/analyze/__init__.py`, `tests/analyze/test_changed_inventory.py`。
  - commit gate:
    - pass まで review loop を回し、pass 後に `report.md` を更新して差分確認後にコミットする。
- QG1 QA review:
  - timing:
    - RG1 pass 後。
  - scope:
    - class count、changed_files carry、unreachable changed class、classless file、multi-class file、join miss、selection/traversal independence、deterministic ordering。
  - commit gate:
    - pass まで test loop を回し、pass 後に `report.md` を更新して差分確認後にコミットする。

## 実行ルール（全ステップ共通）
- cadence / approval policy は `workflow_issue.md` を正本とする。
- 互換参照: `Red -> Green -> Refactor -> review -> fix -> re-review -> report -> commit/no-op`
- 各 step は 1 つの観測可能な振る舞いを単位とする。
- failing test は iteration ごとに 1 本ずつ進める。
- `Green` は最小実装、`Refactor` は green 維持を前提とする。
- docs impact が `none` でなければ `S90` を実行する。
- reviewer verdict は `report.md` に残す。
- 各 stage gate（SG/RG/QG）は `pass` まで回す。
- no-op の場合のみ `report.md` に理由を残し、commit を省略できる。

## 実装ステップ

### S01 — changed file class count baseline
- target:
  - `src/pyclassuml/analyze/changed.py`
  - `src/pyclassuml/analyze/__init__.py`
  - `tests/analyze/test_changed_inventory.py`
- design refs:
  - `design.md` の `インターフェース契約`
  - `design.md` の `主要フロー` 1-2
- step boundary:
  - changed file collection は入力として受け取り、Git は読まない。
  - selection/traversal は入力にしない。
- test expectations:
  - changed file に対応する parsed module classes を class 定義単位で数える。
  - same file multiple classes を複数 count する。
  - `ChangedClassInventory.changed_files` は sorted deterministic tuple。

### S02 — join miss, classless file, and selection independence
- target:
  - `src/pyclassuml/analyze/changed.py`
  - `tests/analyze/test_changed_inventory.py`
- design refs:
  - `requirement.md` の AC-002/AC-003/EC-001/EC-002/EC-004
  - `design.md` の `主要フロー` 3-4
- step boundary:
  - join miss は diagnostics を作らず class_count へ加算しない。
  - selection / relation / reachable graph は参照しない。
- test expectations:
  - reachable graph に乗らない changed file class も class_count に入る。
  - classless changed file は changed_files に残り class_count には入らない。
  - parse join miss / syntax error 相当の changed file は changed_files に残り class_count には入らない。
  - ignore 済みかどうかは upstream handoff の changed file 入力だけで決まり、inventory は追加 filter しない。

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
  - `uv run --with pytest pytest tests/analyze/test_changed_inventory.py -q`
  - `uv run --with pytest pytest tests/analyze/test_selection.py -q`
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
  - changed file 集合の upstream owner と inventory count semantics は requirement / design で固定済みである。

## final exit contract
- AC/EC 達成:
  - AC-001/AC-002/AC-003/EC-001/EC-002/EC-003/EC-004 が tests と review evidence で観測できる。
- docs impact resolved:
  - issue docs と report のみ更新し、恒久 docs 変更なしの判断を残す。
- final diff approved:
  - spec review / implementation review / QA review が pass し、SpecDock validate/sync evidence が report に記録されている。
