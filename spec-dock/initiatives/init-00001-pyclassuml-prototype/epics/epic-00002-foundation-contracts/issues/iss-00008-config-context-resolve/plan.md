---
種別: 実装計画書（Issue）
ID: "iss-00008"
タイトル: "Config Context Resolve"
関連GitHub: ["#8"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
依存: ["requirement.md", "design.md"]
親: ["epic-00002", "init-00001"]
---

# iss-00008 Config Context Resolve — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001 `process_cwd` 基準の `--cwd` resolve。
  - AC-002 CLI / config / default merge。
  - AC-003 config discovery order。
  - AC-004 invalid config / path / containment の hard failure handoff。
- EC:
  - EC-001 config file directory fallback project_root。
  - EC-002 `relative_path_base=cwd`。
  - EC-003 `--project-root` 指定時の fallback discovery。
- 制約:
  - 4 roots resolve owner は `config`。
  - explicit / diff target selection、Git diff、parse/analyze、summary / output write / exit policy は実装しない。
  - config file absent は default 継続、invalid config は hard failure。

## マイルストーン一覧
- M1:
  - 対象: config package scaffold and success result。
  - exit: `resolve_context(CommandRequest)` が default `ExecutionContext` / `AnalysisConfig` を返す。
- M2:
  - 対象: path resolution / config discovery / merge。
  - exit: AC-001/AC-002/AC-003/EC-001/EC-002/EC-003 が pytest で観測できる。
- M3:
  - 対象: failure diagnostics / review / QA / SpecDock evidence。
  - exit: AC-004、review pass、`validate` / `sync` evidence が report に残る。

## 実装順序の根拠
- 依存関係の正本:
  - `design.md` の `依存関係分析` と module/dependency UML を参照する
- sequencing rule:
  - upstream / prerequisite / lower-dependency slice から先に step を組む
  - downstream / dependent slice は前提が固まってから置く
- step ordering notes:
  - `model` DTO は `iss-00007` で完了済みなので、それを import して `config` seam-local result を作る。
  - filesystem discovery が必要なため、tests は `tmp_path` 上に real project tree を作る。
  - failure diagnostics は success path と merge rules が固まってから追加する。

## ステップ一覧
- S01:
  - 観測可能な振る舞い: config package から `resolve_context` を import でき、config file なし default invocation で `ExecutionContext` / `AnalysisConfig` が返る。
  - closes: AC-001 baseline, M1
  - depends on: `iss-00007`
  - unblocks: S02
  - target files:
    - `src/pyclassuml/config/__init__.py`
    - `src/pyclassuml/config/resolver.py`
    - `tests/config/test_context_resolve.py`
  - review gate:
    - targeted pytest pass。
- S02:
  - 観測可能な振る舞い: CLI / config / default merge、config file discovery order、relative path base、root fallback が観測できる。
  - closes: AC-002, AC-003, EC-001, EC-002, EC-003, M2
  - depends on: S01
  - unblocks: S03
  - target files:
    - `src/pyclassuml/config/resolver.py`
    - `tests/config/test_context_resolve.py`
  - review gate:
    - targeted pytest pass。
- S03:
  - 観測可能な振る舞い: invalid config read/value/path/containment が `DiagnosticSeverity.ERROR` と canonical `FailureReason` を持つ failure result になる。
  - closes: AC-004, M3
  - depends on: S02
  - unblocks: S90, S99, downstream `iss-00009`, `iss-00010`
  - target files:
    - `src/pyclassuml/config/resolver.py`
    - `tests/config/test_context_resolve.py`
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
  - 観測可能な振る舞い: final diff review、code review、QA review、SpecDock validate/sync evidence が揃う。
  - closes: final exit contract
  - depends on: S90
  - unblocks: issue close / next ready issue
  - target files:
    - `spec-dock/active/issue/report.md`
  - review gate:
    - required review verdict が pass。

## 要件 ↔ ステップ対応
- AC-001 -> S01, S02
- AC-002 -> S02
- AC-003 -> S02
- AC-004 -> S03
- EC-001 -> S02
- EC-002 -> S02
- EC-003 -> S02

## レビュー / QA ゲート方針
- RG1 implementation review:
  - timing:
    - S01-S03 green 後。
  - scope:
    - `src/pyclassuml/config/**`, `tests/config/**`。
  - commit gate:
    - pass まで review loop を回し、pass 後に `report.md` を更新して差分確認後にコミットする
- QG1 QA review:
  - timing:
    - RG1 pass 後。
  - scope:
    - AC/EC coverage、failure diagnostics coverage、filesystem tmp fixtures。
  - commit gate:
    - pass まで test loop を回し、pass 後に `report.md` を更新して差分確認後にコミットする
- SG1 spec review:
  - timing:
    - 実装前。
  - scope:
    - issue docs が implementation-ready か、schema / merge / failure / file plan が十分か。
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

### S01 — default context resolve and package scaffold
- target:
  - `src/pyclassuml/config/__init__.py`
  - `src/pyclassuml/config/resolver.py`
  - `tests/config/test_context_resolve.py`
- design refs:
  - `design.md` の `インターフェース契約`
  - `design.md` の `path resolution rules`
  - `design.md` の `ディレクトリ / ファイル変更計画`
- step boundary:
  - config file なし、CLI cwd あり/なし、default values の成功 path に限定する。
- depends on:
  - `iss-00007`
- unblocks:
  - S02
- target files:
  - `src/pyclassuml/config/__init__.py`
  - `src/pyclassuml/config/resolver.py`
  - `tests/config/test_context_resolve.py`

#### update_plan（着手時に登録）
- [ ] `update_plan` に step の作業単位を登録した
- [ ] `./spec-dock/active/issue/report.md` の追記位置を決めた

#### B1 — default success contract
- purpose:
  - `CommandRequest` から `ExecutionContext` / `AnalysisConfig` への最小 handoff を固定する。
- files:
  - `src/pyclassuml/config/resolver.py`
  - `tests/config/test_context_resolve.py`

##### I1 — default no-config resolve
- slice goal:
  - config file なしで `execution_cwd=process_cwd`, `project_root=package_root=scope_root=execution_cwd` になる。

###### Red
- failing test:
  - `uv run --with pytest pytest tests/config/test_context_resolve.py -q`
- expected failure:
  - `ModuleNotFoundError` or missing `resolve_context`。

###### Green
- minimum implementation:
  - `ConfigResolution` と `resolve_context` の scaffold、default success path。
- pass condition:
  - `uv run --with pytest pytest tests/config/test_context_resolve.py -q`

###### Refactor
- 目的:
  - Green を維持したまま、必要な範囲で構造や可読性を整える
- guardrail:
  - 振る舞いを変えない
  - この step の範囲を超えて広げない
  - 必要がなければスキップしてよい

#### step gate
- review:
  - `config` 以外の seam logic が混入していないこと。
- expected tests:
  - `uv run --with pytest pytest tests/config/test_context_resolve.py -q`
- report update:
  - reviewer verdict / test結果 / 修正内容 / no-op 理由を `./spec-dock/active/issue/report.md` に残す
- commit:
  - report 更新後に差分確認し、この stage の差分とまとめてコミットする

### S02 — discovery, path base, and merge rules
- target:
  - `src/pyclassuml/config/resolver.py`
  - `tests/config/test_context_resolve.py`
- design refs:
  - `design.md` の `config file schema`
  - `design.md` の `path resolution rules`
  - `design.md` の `merge rules`
- step boundary:
  - successful config read / discovery / merge scenarios に限定する。
- depends on:
  - S01
- unblocks:
  - S03
- target files:
  - `src/pyclassuml/config/resolver.py`
  - `tests/config/test_context_resolve.py`

#### B1 — filesystem discovery and merge
- purpose:
  - `.pyclassuml.toml` discovery と CLI > config > default merge を観測する。
- files:
  - `src/pyclassuml/config/resolver.py`
  - `tests/config/test_context_resolve.py`

##### I1 — config discovery and merge red/green
- slice goal:
  - `--project-root` 指定時は `<project_root>/.pyclassuml.toml` を優先し、なければ `execution_cwd` 親探索へ fallback する。
  - `relative_path_base=cwd` と config-file-dir fallback project_root を観測する。
  - `ignore`, `output`, `depth`, `mode`, `target_python`, `[diff].current_state`, `[diff].include_untracked` の CLI / config / default merge を観測する。
  - `strict=False` は config `mode` を override せず、`strict=True` だけが config `mode` より優先することを観測する。
  - `[diff]` table と dotted `diff.current_state` / `diff.include_untracked` が同じ nested schema として扱われることを観測する。

###### Red
- failing test:
  - `uv run --with pytest pytest tests/config/test_context_resolve.py -q`
- expected failure:
  - discovery / merge 未実装。

###### Green
- minimum implementation:
  - TOML read via stdlib `tomllib`、schema validation、path resolution、merge。
- pass condition:
  - `uv run --with pytest pytest tests/config/test_context_resolve.py -q`

###### Refactor
- 目的:
  - discovery / schema / merge helper を private function に分ける。
- guardrail:
  - target selection, Git read, parse, report output は入れない。

#### step gate
- review:
  - AC-002/AC-003/EC-001/EC-002/EC-003 が tests と実装で説明できること。
  - schema supported fields の success path が tests と実装で説明できること。
- expected tests:
  - `uv run --with pytest pytest tests/config/test_context_resolve.py -q`
- report update:
  - test結果と判断を `./spec-dock/active/issue/report.md` に残す。
- commit:
  - report 更新後に差分確認し、この stage の差分とまとめてコミットする。

### S03 — invalid config and containment failure diagnostics
- target:
  - `src/pyclassuml/config/resolver.py`
  - `tests/config/test_context_resolve.py`
- design refs:
  - `design.md` の `path resolution rules`
  - `design.md` の failure taxonomy
- step boundary:
  - hard failure result / diagnostics に限定する。
- depends on:
  - S02
- unblocks:
  - S90
  - S99
  - downstream `iss-00009`
  - downstream `iss-00010`
- target files:
  - `src/pyclassuml/config/resolver.py`
  - `tests/config/test_context_resolve.py`

#### B1 — failure diagnostics
- purpose:
  - invalid config/path/containment を downstream が policy 判定できる failure handoff にする。
- files:
  - `src/pyclassuml/config/resolver.py`
  - `tests/config/test_context_resolve.py`

##### I1 — hard failure red/green
- slice goal:
  - invalid TOML、missing/unreadable explicit `--config`、unknown top-level key、unknown `[diff]` key、non-path schema value type mismatch、invalid config enum value、invalid config `target_python` / `depth`、config/CLI 起点の unresolved root path は `invalid_config_or_config_path` を持つ error diagnostic になる。
  - nonexistent / non-directory `--cwd` と containment violation は `invalid_path_or_containment` を持つ error diagnostic になる。

###### Red
- failing test:
  - `uv run --with pytest pytest tests/config/test_context_resolve.py -q`
- expected failure:
  - failure result / diagnostics 未実装。

###### Green
- minimum implementation:
  - `ConfigResolution` failure result と canonical diagnostics。
- pass condition:
  - `uv run --with pytest pytest tests/config/test_context_resolve.py -q`

###### Refactor
- 目的:
  - diagnostic construction helper を整理する。
- guardrail:
  - exit code / stream routing は実装しない。

#### step gate
- review:
  - AC-004 が failure taxonomy と一致すること。
- expected tests:
  - `uv run --with pytest pytest tests/config/test_context_resolve.py -q`
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
  - `uv run --with pytest pytest tests/config/test_context_resolve.py -q`
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
  - schema / discovery / merge / failure taxonomy はこの issue の design で固定済み。

## final exit contract
- AC/EC 達成:
  - AC-001/AC-002/AC-003/AC-004/EC-001/EC-002/EC-003 が tests と review evidence で観測できる。
- docs impact resolved:
  - issue docs と report のみ更新し、恒久 docs 変更なしの判断を残す。
- final diff approved:
  - code-reviewer / qa-reviewer が pass し、SpecDock validate/sync evidence が report に記録されている。
