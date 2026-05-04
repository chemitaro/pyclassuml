---
種別: 実装計画書（Issue）
ID: "iss-00021"
タイトル: "App Diff Wiring"
関連GitHub: ["#21"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md"]
親: ["epic-00005", "init-00001"]
---

# iss-00021 App Diff Wiring — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001 canonical diff happy path
  - AC-002 current-state / untracked 差分の front-stage confinement
  - AC-003 changed-file context / observations / inventory transport
  - AC-004 non-usage failure の owner preservation
- EC:
  - EC-001 head + include_untracked no-op warning
  - EC-002 diff scope exclusion counter
  - EC-003 zero-target failure
- 制約:
  - post-`TargetSet` pipeline は `generate` と同一順序に保つ。
  - `ReportRunResult` / nested `CommandResult` / stream material は `report` owner とする。
  - `app` は実プロセス stdout/stderr emit を行わない。

## マイルストーン一覧
- M1 contract repair:
  - 対象:
    - issue requirement/design/plan/report
  - exit:
    - stale `CommandResult` direct-output 契約を `ReportRunResult` 境界へ修正し、spec review pass を得る。
- M2 app seam implementation:
  - 対象:
    - `src/pyclassuml/app`
    - `tests/app`
  - exit:
    - `run_diff(request, *, timestamp) -> ReportRunResult` が happy path と front-stage failure path を満たす。
- M3 review / QA / finalization:
  - 対象:
    - review 指摘、targeted/full validation、SpecDock state、GitHub issue
  - exit:
    - code-reviewer / qa-reviewer pass、commit、push、GitHub issue close。

## 実装順序の根拠
- 依存関係の正本:
  - `design.md` の module/dependency UML と seam position を参照する。
- sequencing rule:
  - front-stage failure handoff を先に固定してから canonical happy path を接続する。
  - report-owned result preservation は全ステップの gate として扱う。
- step ordering notes:
  - `run_diff` の public seam と command guard がないと failure/happy path test が安定しないため S01 を先行する。
  - `vcs` / `targets.diff` failure は common pipeline に入らないため S02 で閉じる。
  - actual changed-file context と `TargetSet` が成立してから S03 の common pipeline に接続する。
  - warning-only / render / output failure preservation は S04 で cross-cutting に確認する。

## ステップ一覧
- S01 public app seam and command guard:
  - 観測可能な振る舞い:
    - `run_diff(request, *, timestamp)` が diff request だけを受け、`ReportRunResult` を返す。
  - closes:
    - AC-004 の result boundary。
  - review gate:
    - non-diff guard と app export の test。
- S02 front-stage failure handoff:
  - 観測可能な振る舞い:
    - config failure、VCS failure、zero-target failure が downstream stage へ進まず `write_report` に集約され、zero-target の `DiffTargetNormalization.observations` は summary counter に保持される。
  - closes:
    - AC-004, EC-003。
  - review gate:
    - nested `CommandResult.exit_code` と diagnostics producer が保持される。
- S03 canonical diff happy path:
  - 観測可能な振る舞い:
    - config -> vcs -> targets.diff -> parse -> analyze -> frameworks -> render -> report の順に接続し、artifact/summary/stdout_text を得る。
  - closes:
    - AC-001, AC-003。
  - review gate:
    - `build_changed_class_inventory` に project-root-relative changed file `Path` が渡ること。
- S04 warning / counter / failure preservation:
  - 観測可能な振る舞い:
    - no-op warning、diff scope exclusion counter、render/output failure が report owner の結果として保存される。
  - closes:
    - AC-002, AC-004, EC-001, EC-002。
  - review gate:
    - app が summary / exit / stream material を再分類しないこと。

## 要件 ↔ ステップ対応
- AC-001 -> S01, S03
- AC-002 -> S03, S04
- AC-003 -> S03, S04
- AC-004 -> S01, S02, S04
- EC-001 -> S04
- EC-002 -> S04
- EC-003 -> S02

## レビュー / QA ゲート方針
- SG1 spec review:
  - timing:
    - M1 完了後、実装前。
  - scope:
    - issue requirement/design/plan/report と epic `ReportRunResult` 境界の整合。
  - commit gate:
    - pass まで review loop を回し、pass 後に docs commit を作成する。
- RG1 implementation review:
  - timing:
    - M2 実装と targeted/full validation 後。
  - scope:
    - app orchestration、owner split、failure preservation、duplication risk。
  - commit gate:
    - pass まで review loop を回し、pass 後に `report.md` を更新して実装 commit を作成する。
- QG1 QA review:
  - timing:
    - RG1 pass 後。
  - scope:
    - acceptance criteria と edge cases の test adequacy。
  - commit gate:
    - pass まで test loop を回し、pass 後に `report.md` を更新して実装 commit に含める。

## 実行ルール（全ステップ共通）
- plan 全体は実装着手前に承認する。
- 各 step は 1 つの観測可能な振る舞いを単位とする。
- failing test は iteration ごとに 1 本ずつ進める。
- `Green` は最小実装、`Refactor` は green 維持を前提とする。
- docs impact が `none` でなければ `S90` を実行する。
- 最後に `git diff <base>...HEAD` を対象に `S99 final diff review quality gate` を実施する。
- reviewer verdict は `report.md` に残す。
- 各 stage gate（SG/RG/QG）は `pass` まで回す。

## 実装ステップ

### S01 — public app seam and command guard
- target:
  - `src/pyclassuml/app/diff.py`
  - `src/pyclassuml/app/__init__.py`
  - `tests/app/test_diff.py`
- design refs:
  - interface contract
  - invariant
- step boundary:
  - `run_diff(request, *, timestamp) -> ReportRunResult` を公開し、non-diff request は `ValueError` とする。

### S02 — front-stage failure handoff
- target:
  - config failure
  - VCS failure
  - target zero failure with observations transport
- design refs:
  - major flow 2-7
  - data / handoff
- step boundary:
  - downstream parse/analyze/render stages を呼ばず `write_report` を呼ぶ。
  - scope filtering / ignore count は `targets.diff` owner の observations を使い、app では再計算しない。

### S03 — canonical diff happy path
- target:
  - diff fixture から `.puml` artifact と `ReportRunResult.stdout_text` を得る。
  - project-root-relative changed-file `Path` を `build_changed_class_inventory` へ渡す。
- design refs:
  - major flow 8-13
- step boundary:
  - post-`TargetSet` pipeline は generate と同一順序に保つ。

### S04 — warning / counter / failure preservation
- target:
  - head + include_untracked no-op warning
  - diff scope exclusion counter
  - render failure
  - output write failure
- design refs:
  - EC-001
  - EC-002
  - AC-004
- step boundary:
  - `app` では diagnostics / summary / exit / stream material を再分類しない。

### S90 — docs impact resolution / docs refresh
- 対象:
  - issue docs only
- 対応:
  - 実装・レビュー結果を `report.md` に残す。

### S99 — final diff review quality gate
- branch diff scope:
  - issue docs、app diff wiring、tests。
- required validation:
  - targeted pytest
  - full pytest
  - `./spec-dock/scripts/spec-dock validate`
  - `git diff --check`
  - `rg --files | rg '[A-Z]'`
- reviewer approvals:
  - code-reviewer pass
  - qa-reviewer pass
- report update:
  - final diff review verdict / closing evidence / no-op 理由を `report.md` に残す。
- commit expectation:
  - `report.md` 更新後に差分確認し、追加修正があれば最終コミットを作成する。無ければ直前 gate のコミットを最終成果として扱う。

## 未確定事項
- なし:
  - `ReportRunResult` 境界、owner split、scope は upstream docs と epic docs で確定済みである。

## final exit contract
- AC/EC 達成:
  - AC-001〜AC-004、EC-001〜EC-003 の test/review evidence がある。
- docs impact resolved:
  - issue `report.md` に spec review / implementation review / QA / validation の結果がある。
- final diff approved:
  - code-reviewer / qa-reviewer pass、targeted/full validation pass、SpecDock validate pass。
