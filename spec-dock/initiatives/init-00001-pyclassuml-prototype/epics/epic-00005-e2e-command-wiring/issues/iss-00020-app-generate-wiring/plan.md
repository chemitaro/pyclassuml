---
種別: 実装計画書（Issue）
ID: "iss-00020"
タイトル: "App Generate Wiring"
関連GitHub: ["#20"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md"]
親: ["epic-00005", "init-00001"]
---

# iss-00020 App Generate Wiring — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001 explicit target 起点の generate を canonical order で report まで接続し、artifact / `stdout_text` summary / exit code を観測可能にする。
  - AC-002 `TargetSet.observations` と zero `ChangedClassInventory` を欠落なく report へ渡す。
  - AC-003 usage error 以外の non-zero outcome を upstream / report owner のまま返し、app が summary / exit code / stream material を再分類しない。
- EC:
  - EC-001 zero-target failure で fallback target を作らない。
  - EC-002 warning-only success で diagnostics と observations を保持する。
  - EC-003 output write failure を `.puml` success と偽装しない。
- 制約:
  - app は stitcher に限定し、target normalization / parse / analyze / frameworks / render / report logic を再実装しない。
  - actual process stdout / stderr emission と `cli.run_cli` handler signature 変更はこの issue では扱わない。

## マイルストーン一覧
- M1 app public seam:
  - 対象: `src/pyclassuml/app/__init__.py`, `src/pyclassuml/app/generate.py`。
  - exit: `run_generate(request, timestamp=...) -> ReportRunResult` を public API として呼べる。
- M2 front-stage failure handoff:
  - 対象: config failure / explicit target normalization failure。
  - exit: downstream stages を呼ばず、diagnostics を `write_report(...)` に渡して non-zero `ReportRunResult` を得る。
- M3 common pipeline stitching:
  - 対象: `parse -> traversal -> selection -> changed inventory -> frameworks -> render -> report`。
  - exit: generate happy path が artifact と `stdout_text` summary を返し、changed class count は `0`。
- M4 verification / review:
  - 対象: unit / integration tests、review、report update、commit。

## 実装順序の根拠
- `config`, `targets`, `parse`, `analyze`, `frameworks`, `render`, `report` は既に public seam API を持つ。
- `app` は新規 seam なので、まず public API と stage order の薄い wrapper を作る。
- failure handoff を先に固定すると、front-stage failure で後段を誤って呼ぶ regression を防げる。
- happy path は upstream DTO をそのまま渡すだけにし、post-`TargetSet` に generate 専用分岐を作らない。
- `ChangedClassInventory` は `build_changed_class_inventory((), parsed_modules, module_index)` で analyze owner に生成させる。

## ステップ一覧
- S01:
  - 観測可能な振る舞い: `run_generate` が non-generate request を拒否し、generate request だけを app seam に入れる。
  - closes: constraint。
  - review gate: app public API / command guard review。
- S02:
  - 観測可能な振る舞い: config / target normalization failure が downstream stages を呼ばず report-owned non-zero result になる。
  - closes: AC-003, EC-001。
  - review gate: failure handoff review。
- S03:
  - 観測可能な振る舞い: generate happy path が canonical order で artifact / `stdout_text` summary / exit code 0 を返す。
  - closes: AC-001, AC-002, EC-002。
  - review gate: stage order / transport review。
- S04:
  - 観測可能な振る舞い: output write failure と render failure を app が再分類せず report result として返す。
  - closes: AC-003, EC-003。
  - review gate: non-zero outcome preservation review。
- S90:
  - docs impact: issue report のみ。
- S99:
  - final diff review / code-reviewer / qa-reviewer / validation。

## 要件 ↔ ステップ対応
- AC-001 -> S03。
- AC-002 -> S03。
- AC-003 -> S02, S04。
- EC-001 -> S02。
- EC-002 -> S03。
- EC-003 -> S04。
- constraints -> S01-S04, S99。

## レビュー / QA ゲート方針
- SG1 spec review:
  - timing: requirement/design/plan/report の contract repair 後、実装前。
  - scope: `ReportRunResult` boundary、fallback context、failure handoff、common pipeline guardrail、non-scope。
  - commit gate: pass まで review loop を回し、pass 後に docs commit を作成する。
- RG1 implementation review:
  - timing: S01-S04 実装と targeted / full tests が green になった後。
  - scope: stage order、owner split、diagnostics transport、zero inventory、`ReportRunResult` preservation、no actual stdout/stderr emission。
  - commit gate: pass まで review loop を回し、pass 後に `report.md` を更新してコミットする。
- QG1 QA review:
  - timing: validation 後。
  - scope: happy path、warning-only success、zero-target/config failure、render failure、output write failure、artifact / summary observation。
  - commit gate: pass まで test loop を回し、pass 後に `report.md` を更新してコミットする。

## 実行ルール（全ステップ共通）
- 実装は active issue を基準に進める。
- `src` / `tests` の変更は dev-coder に委任する。
- main は issue docs の contract / report を更新する。
- app seam は `src/pyclassuml/app/` 配下へ追加する。新規 path は lowercase のみ。
- public API は `src/pyclassuml/app/__init__.py` から export する。
- `pyproject.toml` console script と actual stdout/stderr emission はこの issue では追加しない。
- `uv.lock` / `__pycache__` / `.pyc` は残さない。

## 実装ステップ

### S01 — app public seam and command guard
- target:
  - `src/pyclassuml/app/__init__.py`
  - `src/pyclassuml/app/generate.py`
  - `tests/app/test_generate.py`
- design refs:
  - `design.md` invariant / interface contract。
- step boundary:
  - `run_generate(request: CommandRequest, *, timestamp: datetime) -> ReportRunResult` を追加する。
  - `request.cli_options.command is not CommandName.GENERATE` は `ValueError` とし、usage error result は作らない。
  - app は actual stdout/stderr へ write しない。

#### I1 — command guard
- Red:
  - diff request を渡すと `ValueError` になり、downstream seam は呼ばれない。
- Green:
  - public API と command guard の最小実装。

### S02 — front-stage failure handoff
- target:
  - `src/pyclassuml/app/generate.py`
  - `tests/app/test_generate.py`
- design refs:
  - `design.md` failure handoff。
- step boundary:
  - `resolve_context(request)` を最初に呼ぶ。
  - config diagnostics only の場合、fallback context/config と diagnostics を `write_report(...)` に渡す。
  - `normalize_explicit_targets(...)` が diagnostics only の場合、config diagnostics と target diagnostics を `write_report(...)` に渡す。
  - failure path では parse/analyze/framework/render を呼ばない。

#### I1 — config failure
- Red:
  - invalid config path request が `hard_failure`, non-zero, no artifact, `stderr_text` summary を返す。
  - parse / targets / render の stage hook が呼ばれないことを確認する。
- Green:
  - fallback context/config と report handoff。

#### I2 — zero target failure
- Red:
  - missing/glob-miss target が `generate_zero_target_after_normalize` diagnostic を含む non-zero result を返す。
  - fallback target を作らない。
- Green:
  - target normalization failure handoff。

### S03 — canonical generate happy path
- target:
  - `src/pyclassuml/app/generate.py`
  - `tests/app/test_generate.py`
- design refs:
  - `design.md` major flow / data handoff。
- step boundary:
  - canonical order:
    - config
    - explicit target normalization
    - parse
    - traversal
    - selection
    - `build_changed_class_inventory((), parsed_modules, module_index)`
    - SQLAlchemy hints
    - Pydantic hints
    - render
    - report
  - diagnostics order は stage order に沿って append する。
  - `TargetSet.observations`, `DependencyGraph`, `ChangedClassInventory(class_count=0)`, `scope_stop_count` を report へ渡す。
  - render success では `plantuml_text` / `diagram_model` を report へ渡す。

#### I1 — happy path artifact and summary
- Red:
  - simple explicit target fixture で `.puml` artifact が作成され、`stdout_text` に `outcome: clean_success` と `changed_class_count: 0` が出る。
  - `stderr_text == ""`。
- Green:
  - canonical pipeline wiring。

#### I2 — observations and warning-only/degraded diagnostics transport
- Red:
  - ignored seed candidate count と warning diagnostics が summary に反映される。
  - app は diagnostics / observations を mutate しない。
- Green:
  - diagnostics / observations transport。

### S04 — non-zero result preservation
- target:
  - `src/pyclassuml/app/generate.py`
  - `tests/app/test_generate.py`
- design refs:
  - `design.md` failure handoff / risk。
- step boundary:
  - render failure は `render_failure_signal` と upstream diagnostics を report へ渡す。
  - output write failure は `write_report(...)` result をそのまま返す。
  - app は `outcome_kind`, `CommandResult.exit_code`, `RunSummary.failure_reason`, stream material を再分類しない。

#### I1 — render failure
- Red:
  - selected class が空になる fixture または injected render result で `degraded_failure`, non-zero, no artifact, `stderr_text` summary になる。
- Green:
  - render failure handoff。

#### I2 — output write failure
- Red:
  - unwritable parent/write hook failure で `output_write_failure`, non-zero, no artifact になる。
- Green:
  - report result preservation。

### S90 — docs impact resolution
- 対象:
  - issue report のみ。
- 対応:
  - 実装内容、検証、review verdict、未解決事項を `report.md` に記録する。

### S99 — final diff review quality gate
- branch diff scope:
  - `iss-00020` docs、`src/pyclassuml/app/`、`tests/app/test_generate.py`。
- required validation:
  - targeted app/report/model/render/cli tests。
  - full pytest。
  - `./spec-dock/scripts/spec-dock validate`。
  - `git diff --check`。
  - uppercase path check。
  - generated artifact cleanup check。
- reviewer approvals:
  - code-reviewer pass。
  - qa-reviewer pass。
- report update:
  - final diff review verdict / closing evidence / no-op 理由を `report.md` に残す。
- commit expectation:
  - `report.md` 更新後に差分確認し、最終コミットを作成する。

## 未確定事項
- なし:
  - app generate の scope は `ReportRunResult` を返す app seam に閉じ、actual CLI stream emission は downstream integration として残す。

## final exit contract
- AC/EC 達成:
  - AC-001 から AC-003、EC-001 から EC-003 が tests / report evidence / review で確認済み。
- docs impact resolved:
  - issue report に実装と検証を記録済み。
- final diff approved:
  - code-reviewer / qa-reviewer pass。
