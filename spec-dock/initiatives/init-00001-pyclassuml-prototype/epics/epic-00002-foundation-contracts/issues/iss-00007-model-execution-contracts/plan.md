---
種別: 実装計画書（Issue）
ID: "iss-00007"
タイトル: "Model Execution Contracts"
関連GitHub: ["#7"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
依存: ["requirement.md", "design.md"]
親: ["epic-00002", "init-00001"]
---

# iss-00007 Model Execution Contracts — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001 DTO 群の必須 field、producer / consumer、carry 情報を review 可能にする。
  - AC-002 `process_cwd -> execution_cwd`、diagnostic origin / recoverability / failure_reason、summary / exit_code carry を明文化し、実装 contract として観測可能にする。
- EC:
  - EC-001 failure path で artifact がない `CommandResult` を許容する。
  - EC-002 `ChangedClassInventory` を `SelectedClasses` から分離する。
  - EC-003 `RenderReadyModel` と `DiagramModel` を分離する。
  - EC-004 `TargetObservations` を `TargetSet` に同伴させる。
- 制約:
  - DTO は immutable / reviewable な value object とする。
  - algorithm、stream routing、Git / filesystem I/O は実装しない。
  - issue baseline にない convenience field は追加しない。

## マイルストーン一覧
- M1:
  - 対象: package scaffold、test runner、model contract public surface
  - exit: `pyclassuml.model` から DTO / enum を import できる。
- M2:
  - 対象: DTO invariant 実装
  - exit: nullability、collection immutability、diagnostic failure rule が unit test で観測できる。
- M3:
  - 対象: review / QA / SpecDock evidence
  - exit: required tests、code review、QA review、`validate` / `sync` evidence が report に残る。

## 実装順序の根拠
- 依存関係の正本:
  - `design.md` の `依存関係分析` と module/dependency UML を参照する
- sequencing rule:
  - upstream / prerequisite / lower-dependency slice から先に step を組む
  - downstream / dependent slice は前提が固まってから置く
- step ordering notes:
  - repo に runtime package がないため、最初に package scaffold と `pyproject.toml` を置く。
  - DTO は downstream 依存の基盤なので、`model` 以外の seam 実装はこの issue に含めない。
  - tests は contract review の観測点として先に失敗させ、その後に DTO 実装で green にする。

## ステップ一覧
- S01:
  - 観測可能な振る舞い: `pyclassuml.model` の public contract surface から全 DTO / enum を import できる。
  - closes: AC-001 の DTO 一覧 import 観測、M1
  - depends on: none
  - unblocks: S02, S03, downstream issue imports
  - target files:
    - `pyproject.toml`
    - `src/pyclassuml/__init__.py`
    - `src/pyclassuml/model/__init__.py`
    - `src/pyclassuml/model/contracts.py`
    - `tests/model/test_contracts.py`
  - review gate:
    - pytest で import contract が通る。
- S02:
  - 観測可能な振る舞い: DTO invariant が immutable value object として保持され、invalid `depth` / `mode` / `target_python` / negative counters / diagnostic failure rule を拒否する。
  - closes: AC-001, AC-002, EC-001, EC-004, M2
  - depends on: S01
  - unblocks: S03
  - target files:
    - `src/pyclassuml/model/contracts.py`
    - `tests/model/test_contracts.py`
  - review gate:
    - pytest で invariant contract が通る。
- S03:
  - 観測可能な振る舞い: downstream handoff 分離として `ChangedClassInventory`、`RenderReadyModel`、`DiagramModel`、`PlantUmlText`、`RunSummary`、`CommandResult` の nullability / carry が観測できる。
  - closes: EC-001, EC-002, EC-003
  - depends on: S02
  - unblocks: S90, S99, `iss-00006`, `iss-00008`
  - target files:
    - `src/pyclassuml/model/contracts.py`
    - `tests/model/test_contracts.py`
  - review gate:
    - pytest で result / render handoff contract が通る。
- S90:
  - 観測可能な振る舞い: docs impact が issue-scoped report へ記録され、必要な恒久 docs 更新がないことを確認できる。
  - closes: docs impact resolution
  - depends on: S03
  - unblocks: S99
  - target files:
    - `spec-dock/active/issue/report.md`
  - review gate:
    - report に判断を残す。
- S99:
  - 観測可能な振る舞い: final diff review quality gate、code review、QA review、SpecDock validate/sync evidence が揃っている。
  - closes: final exit contract
  - depends on: S90
  - unblocks: issue close / next ready issue
  - target files:
    - `spec-dock/active/issue/report.md`
  - review gate:
    - required review verdict が pass。

## 要件 ↔ ステップ対応
- AC-001 -> S01, S02
- AC-002 -> S02, S03
- EC-001 -> S03
- EC-002 -> S03
- EC-003 -> S03
- EC-004 -> S02

## レビュー / QA ゲート方針
- RG1 implementation review:
  - timing:
    - S01-S03 green 後。
  - scope:
    - `pyproject.toml`, `src/pyclassuml/model/**`, `tests/model/**`。
  - commit gate:
    - pass まで review loop を回し、pass 後に `report.md` を更新して差分確認後にコミットする
- QG1 QA review:
  - timing:
    - RG1 pass 後。
  - scope:
    - pytest coverage と issue acceptance の対応、negative invariant tests の十分性。
  - commit gate:
    - pass まで test loop を回し、pass 後に `report.md` を更新して差分確認後にコミットする
- SG1 spec review:
  - timing:
    - 実装前にこの `requirement.md` / `design.md` / `plan.md` を対象に実施する。
  - scope:
    - issue docs が implementation-ready か、workflow_issue.md の required sections を満たすか。
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

### S01 — model package scaffold and public import surface
- target:
  - `pyproject.toml`
  - `src/pyclassuml/__init__.py`
  - `src/pyclassuml/model/__init__.py`
  - `src/pyclassuml/model/contracts.py`
  - `tests/model/test_contracts.py`
- design refs:
  - `design.md` の `ディレクトリ / ファイル変更計画`
  - initiative `design.md` の top-level package structure
- step boundary:
  - package scaffold と public re-export のみ。DTO invariant の詳細は S02/S03 で観測する。
- depends on:
  - none
- unblocks:
  - S02
  - S03
- target files:
  - `pyproject.toml`
  - `src/pyclassuml/__init__.py`
  - `src/pyclassuml/model/__init__.py`
  - `src/pyclassuml/model/contracts.py`
  - `tests/model/test_contracts.py`

#### update_plan（着手時に登録）
- [ ] `update_plan` に step の作業単位を登録した
- [ ] `./spec-dock/active/issue/report.md` の追記位置を決めた

#### B1 — package import contract
- purpose:
  - downstream issue が `pyclassuml.model` から shared DTO を import できる入口を固定する。
- files:
  - `src/pyclassuml/model/__init__.py`
  - `src/pyclassuml/model/contracts.py`
  - `tests/model/test_contracts.py`

##### I1 — public DTO symbol import
- slice goal:
  - 全 DTO / enum の import が失敗する Red を作り、空実装ではなく最小 symbol 定義で Green にする。

###### Red
- failing test:
  - `pytest tests/model/test_contracts.py -q`
- expected failure:
  - `ModuleNotFoundError` または missing symbol。

###### Green
- minimum implementation:
  - `pyproject.toml` と package scaffold、DTO / enum の最小 class 定義、public re-export。
- pass condition:
  - `pytest tests/model/test_contracts.py -q`

###### Refactor
- 目的:
  - Green を維持したまま、必要な範囲で構造や可読性を整える
- guardrail:
  - 振る舞いを変えない
  - この step の範囲を超えて広げない
  - 必要がなければスキップしてよい

#### step gate
- review:
  - public surface が issue baseline table と一致すること。
- expected tests:
  - `pytest tests/model/test_contracts.py -q`
- report update:
  - reviewer verdict / test結果 / 修正内容 / no-op 理由を `./spec-dock/active/issue/report.md` に残す
- commit:
  - report 更新後に差分確認し、この stage の差分とまとめてコミットする

### S02 — front-stage and diagnostic invariant contracts
- target:
  - `src/pyclassuml/model/contracts.py`
  - `tests/model/test_contracts.py`
- design refs:
  - `design.md` の `インターフェース契約`
  - `design.md` の `data / DTO handoff`
- step boundary:
  - `CommandRequest`, `ExecutionContext`, `AnalysisConfig`, `TargetObservations`, `TargetSet`, `Diagnostic` の invariant に限定する。
  - stream routing は実装せず、consumer が routing 判定に使う `CommandResult.exit_code` は S03 で carry contract として扱う。
- depends on:
  - S01
- unblocks:
  - S03
- target files:
  - `src/pyclassuml/model/contracts.py`
  - `tests/model/test_contracts.py`

#### B1 — immutable validation contract
- purpose:
  - mutable input を tuple 化し、invalid field を fail-fast する。
- files:
  - `src/pyclassuml/model/contracts.py`
  - `tests/model/test_contracts.py`

##### I1 — validation red/green
- slice goal:
  - invalid `depth`, `mode`, `target_python`, negative counters、non-python seed、failure diagnostic missing `failure_reason`、invalid diagnostic enum / failure reason、不正な command-specific nested option 組み合わせを拒否する。

###### Red
- failing test:
  - `pytest tests/model/test_contracts.py -q`
- expected failure:
  - invalid 値が受け入れられる、または required validation が未実装。

###### Green
- minimum implementation:
  - `__post_init__` validation と tuple normalization。
  - `CommandOptions` / `GenerateOptions` / `DiffOptions` / `AnalysisConfig` の nullability と absence rule。
- pass condition:
  - `pytest tests/model/test_contracts.py -q`

###### Refactor
- 目的:
  - validation helper を private function に寄せ、DTO field contract を読みやすくする。
- guardrail:
  - model 以外の seam policy は実装しない。

#### step gate
- review:
  - invalid 値拒否が issue の制約を越えていないこと。
- expected tests:
  - `pytest tests/model/test_contracts.py -q`
- report update:
  - test結果と判断を `./spec-dock/active/issue/report.md` に残す。
- commit:
  - report 更新後に差分確認し、この stage の差分とまとめてコミットする。

### S03 — downstream handoff and command result contracts
- target:
  - `src/pyclassuml/model/contracts.py`
  - `tests/model/test_contracts.py`
- design refs:
  - `design.md` の `インターフェース契約`
  - requirement EC-001 から EC-003
- step boundary:
  - `ChangedClassInventory`, `RenderReadyModel`, `DiagramModel`, `PlantUmlText`, `RunSummary`, `CommandResult` の carry / nullability に限定する。
- depends on:
  - S02
- unblocks:
  - S90
  - S99
  - downstream `iss-00006`
  - downstream `iss-00008`
- target files:
  - `src/pyclassuml/model/contracts.py`
  - `tests/model/test_contracts.py`

#### B1 — result and render handoff contract
- purpose:
  - changed class summary と UML掲載対象、render-ready と PlantUML shaping、artifact optional result を分離して観測する。
- files:
  - `src/pyclassuml/model/contracts.py`
  - `tests/model/test_contracts.py`

##### I1 — separation and optional artifact red/green
- slice goal:
  - failure `CommandResult` が `artifact_path=None` でも summary / diagnostics / exit_code を持つこと、render handoff DTO が分離されていること、`exit_code` は stream routing 実装ではなく consumer-side routing 判定の carry field に留まることを観測する。

###### Red
- failing test:
  - `pytest tests/model/test_contracts.py -q`
- expected failure:
  - optional artifact / handoff DTO が未実装。

###### Green
- minimum implementation:
  - downstream DTO と result DTO の invariant / tuple normalization。
- pass condition:
  - `pytest tests/model/test_contracts.py -q`

###### Refactor
- 目的:
  - shared validation helper だけを整理する。
- guardrail:
  - report policy、stream routing、artifact write は実装しない。

#### step gate
- review:
  - EC-001 から EC-003 が tests と実装で説明できること。
- expected tests:
  - `pytest tests/model/test_contracts.py -q`
- report update:
  - test結果と判断を `./spec-dock/active/issue/report.md` に残す。
- commit:
  - report 更新後に差分確認し、この stage の差分とまとめてコミットする。

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
  - root `AGENTS.md`、SpecDock workflow docs、README 類への恒久 docs 変更は不要と判断する。

### S99 — final diff review quality gate
- branch diff scope:
  - `git diff origin/main...HEAD` と working tree diff。
- required validation:
  - `pytest tests/model/test_contracts.py -q`
  - `./spec-dock/scripts/spec-dock validate`
  - `./spec-dock/scripts/spec-dock sync --github`
  - `rg --files | rg '[A-Z]'` で既存 uppercase 以外を増やしていないことを確認する。
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
  - この issue では DTO contract の最小実装に限定し、downstream algorithm は後続 issue へ残す。

## final exit contract
- AC/EC 達成:
  - AC-001/AC-002/EC-001/EC-002/EC-003/EC-004 が tests と review evidence で観測できる。
- docs impact resolved:
  - issue docs と report のみ更新し、恒久 docs 変更なしの判断を残す。
- final diff approved:
  - code-reviewer / qa-reviewer が pass し、SpecDock validate/sync evidence が report に記録されている。
