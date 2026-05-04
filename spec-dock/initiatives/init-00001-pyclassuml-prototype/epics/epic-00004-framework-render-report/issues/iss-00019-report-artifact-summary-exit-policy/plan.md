---
種別: 実装計画書（Issue）
ID: "iss-00019"
タイトル: "Report Artifact Summary Exit Policy"
関連GitHub: ["#19"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md"]
親: ["epic-00004", "init-00001"]
---

# iss-00019 Report Artifact Summary Exit Policy — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001 clean / warning-only / degraded success で artifact write、`stdout_text` summary、exit code 0、DiagramModel 起点 counter を固定する。
  - AC-002 auto naming、`--output` resolve、suffix collision、generate zero inventory / diff actual inventory summary を固定する。
  - AC-003 strict promoted failure / degraded failure / hard failure と counter source fallback を固定する。
- EC:
  - EC-001 `head_untracked_noop` のような `recoverability=recoverable` warning は warning-only success として summary に残す。
  - EC-002 render 成功後の output write failure は artifact success とせず、`stderr_text` summary / non-zero にする。
  - EC-003 `RenderFailureSignal(failure_reason=diagram_unbuildable_after_recovery)` は degraded failure として empty artifact を書かない。
- 制約:
  - report は parse / analyze / frameworks / render / config / targets / vcs を再実行しない。
  - filesystem write、summary synthesis、stream material routing、exit policy の owner は `report` だけにする。
  - current timestamp は report API 入力として受け取り、実装内で clock を直接読まない。

## マイルストーン一覧
- M1 report DTO / naming:
  - 対象: `ReportInputs`, `ReportRunResult`, `ArtifactNamingDecision`。
  - exit: `execution_cwd` 基準 resolve、auto name、suffix collision が deterministic に観測できる。
- M2 summary / outcome classifier:
  - 対象: counter synthesis、warning / failure classifier、stream material target。
  - exit: success / warning-only / degraded / strict promoted / hard failure の outcome が tests で固定される。
- M3 filesystem write / CommandResult:
  - 対象: artifact write、write failure、`RunSummary` / `CommandResult` assembly。
  - exit: success 系だけ write し、failure 系は `stderr_text` と non-zero result を返す。

## 実装順序の根拠
- `RunSummary` / `CommandResult` / `DiagramModel` / `RenderFailureSignal` は既に model contract として実装済み。
- `render.uml-document` は filesystem write を行わないため、report が `PlantUmlText` / `DiagramModel` / `RenderFailureSignal` のどちらかを受けて最終 outcome に変換する。
- `app.generate-wiring` / `app.diff-wiring` は downstream なので、この issue は app orchestration ではなく reusable report API を完成条件にする。
- `AnalysisConfig.output` は既に config seam が `execution_cwd` 基準 semantics を確定する前段 input であり、report は `ExecutionContext.execution_cwd` を使って raw relative output を resolve する。
- 自動命名は timestamp を含むため、determinism と testability のために `datetime` input を必須にする。

## ステップ一覧
- S01:
  - 観測可能な振る舞い: `decide_artifact_path(...)` が output 未指定 / 指定 / collision を決定する。
  - closes: AC-002。
  - review gate: naming and path resolve review。
- S02:
  - 観測可能な振る舞い: `build_run_summary(...)` が authoritative counter source から `RunSummary` を作る。
  - closes: AC-001, AC-002, AC-003。
  - review gate: counter source review。
- S03:
  - 観測可能な振る舞い: `decide_exit_policy(...)` が warning / failure diagnostics と `RenderFailureSignal` から outcome を選ぶ。
  - closes: AC-001, AC-003, EC-001, EC-003。
  - review gate: classifier table review。
- S04:
  - 観測可能な振る舞い: `write_report(...) -> ReportRunResult` が artifact write、stream material text、`CommandResult` を返す。
  - closes: AC-001, AC-002, AC-003, EC-002。
  - review gate: write owner / stream material routing / no upstream rerun review。
- S90:
  - docs impact: issue report のみ。
- S99:
  - final diff review / code-reviewer / qa-reviewer / validation。

## 要件 ↔ ステップ対応
- AC-001 -> S02, S03, S04。
- AC-002 -> S01, S02, S04。
- AC-003 -> S02, S03, S04。
- EC-001 -> S03, S04。
- EC-002 -> S04。
- EC-003 -> S03, S04。
- constraints -> S01-S04, S99。

## レビュー / QA ゲート方針
- SG1 spec review:
  - timing: requirement/design/plan/report の contract repair 後、実装前。
  - scope: recoverability enum alignment、ReportRunResult、timestamp input、failure taxonomy、counter source、non-scope。
  - commit gate: pass まで review loop を回し、pass 後に docs commit を作成する。
- RG1 implementation review:
  - timing: S01-S04 実装と unit tests が green になった後。
  - scope: filesystem write owner、path resolve、suffix collision、counter source、classifier、stream material text、CommandResult。
  - commit gate: pass まで review loop を回し、pass 後に `report.md` を更新してコミットする。
- QG1 QA review:
  - timing: targeted / full validation 後。
  - scope: success/failure outcome matrix、write failure、summary counter coverage、determinism、downstream app usability。
  - commit gate: pass まで test loop を回し、pass 後に `report.md` を更新してコミットする。

## 実行ルール（全ステップ共通）
- 実装は active issue を基準に進める。
- `src` / `tests` の変更は dev-coder に委任する。
- main は issue docs の contract / report を更新する。
- report seam は `src/pyclassuml/report/` 配下へ追加する。新規 path は lowercase のみ。
- public API は `src/pyclassuml/report/__init__.py` から export する。
- `pyproject.toml` console script と `app.*-wiring` はこの issue では追加しない。
- `uv.lock` / `__pycache__` / `.pyc` は残さない。

## 実装ステップ

### S01 — artifact naming
- target:
  - `src/pyclassuml/report/__init__.py`
  - `src/pyclassuml/report/policy.py`
  - `tests/report/test_policy.py`
- design refs:
  - `design.md` `ArtifactNamingDecision`。
- step boundary:
  - `decide_artifact_path(command, context, config, timestamp)` を追加する。
  - output 未指定:
    - generate: `pyclassuml_YYYYMMDD_HHMMSS.puml`
    - diff: `pyclassuml_diff_YYYYMMDD_HHMMSS.puml`
    - base directory: `ExecutionContext.execution_cwd`
  - output 指定:
    - relative path は `ExecutionContext.execution_cwd` 基準に resolve する。
    - absolute path はそのまま使う。
    - parent directory が存在しない場合は `write_report` が作成する。
  - collision:
    - resolved path が存在する場合、stem に `_2`, `_3`, ... を付けて最初の未使用 path を選ぶ。
  - parent directory creation failure は `output_write_failure` とする。
  - report は path containment の再検証をしない。

#### I1 — auto naming and output resolve
- Red:
  - fixed timestamp で generate/diff auto names が deterministic に決まる。
  - relative output が `execution_cwd` 基準で absolute path になる。
  - missing parent directory は success write path で作成される。
- Green:
  - naming helper and DTO。

#### I2 — suffix collision
- Red:
  - base path と `_2` が存在すると `_3` を選ぶ。
- Green:
  - deterministic collision scan。

### S02 — summary counter synthesis
- target:
  - `src/pyclassuml/report/policy.py`
  - `tests/report/test_policy.py`
- design refs:
  - `design.md` counter source invariants。
- step boundary:
  - `build_run_summary(...) -> RunSummary` を追加する。
  - counter keys:
    - `seed_file_count`
    - `reachable_file_count`
    - `extracted_class_count`
    - `extracted_relation_count`
    - `changed_class_count`
    - `ignored_file_count`
    - `warning_count`
    - `scope_stop_count`
    - `diff_scope_excluded_count`
  - success path and render-success output write failure:
    - `extracted_class_count = len(DiagramModel.rendered_classes)`
    - `extracted_relation_count = len(DiagramModel.rendered_relations)`
  - `RenderFailureSignal` non-success:
    - `extracted_class_count = signal.class_count`
    - `extracted_relation_count = signal.relation_count`
  - producer seam 未実行 hard failure:
    - missing counter source は `0` fallback。
  - `changed_class_count = ChangedClassInventory.class_count`。
  - `warning_count` は summary 時点の warning diagnostics 数。

#### I1 — success counters
- Red:
  - DiagramModel の class/relation count が summary に入る。
  - target/traversal/changed counters が summary に入る。
- Green:
  - summary builder。

#### I2 — failure counter source
- Red:
  - RenderFailureSignal では signal counters を使う。
  - early hard failure では missing source を 0 fallback にする。
- Green:
  - counter source selection。

### S03 — exit policy classifier
- target:
  - `src/pyclassuml/report/policy.py`
  - `tests/report/test_policy.py`
- design refs:
  - `design.md` outcome decision table / classifier rule。
- step boundary:
  - outcome enum or literal values:
    - `clean_success`
    - `warning_only_success`
    - `degraded_success`
    - `strict_promoted_failure`
    - `degraded_failure`
    - `hard_failure`
  - success outcomes:
    - no error diagnostics and no `RenderFailureSignal`。
    - all warnings `recoverability=recoverable` -> `warning_only_success`。
    - any warning `recoverability=degraded_output` -> `degraded_success`。
  - strict promoted failure:
    - error diagnostic `failure_reason` in `strict_resolution_failure`, `strict_syntax_error`, `strict_wildcard_resolution_failure`, `strict_diff_scope_exclusion`。
  - degraded failure:
    - `RenderFailureSignal`。
  - hard failure:
    - hard-failure reason diagnostic or output write failure。
  - failure precedence:
    - hard failure > strict promoted failure > degraded failure。
    - summary failure reason は chosen outcome の最優先 input reason を使う。
  - exit code:
    - success outcomes `0`。
    - non-success `1`。
  - stream:
    - success outcomes `stdout_text`。
    - non-success `stderr_text`。

#### I1 — success classifiers
- Red:
  - clean, recoverable warning-only, degraded warning success。
- Green:
  - warning classifier。

#### I2 — failure classifiers
- Red:
  - strict-promotable diagnostic、RenderFailureSignal、vcs/config/output hard failure。
  - RenderFailureSignal と strict-promotable diagnostic が重なる場合は `strict_promoted_failure`。
  - RenderFailureSignal / strict-promotable diagnostic と hard-failure diagnostic が重なる場合は `hard_failure`。
- Green:
  - failure classifier。

### S04 — write report result
- target:
  - `src/pyclassuml/report/policy.py`
  - `tests/report/test_policy.py`
- design refs:
  - `design.md` major flow。
- step boundary:
  - `write_report(inputs, *, write_text=None) -> ReportRunResult` を追加する。
  - success outcomes:
    - require `PlantUmlText` and `DiagramModel`。
    - write `.puml` text to chosen path。
    - `CommandResult.artifact_path` is chosen path。
    - summary text in `stdout_text`, empty `stderr_text`。
  - output write failure:
    - no success artifact path in `CommandResult`。
    - append or create `output_write_failure` diagnostic with `origin_seam=report`, `recoverability=fatal`, `failure_reason=output_write_failure`。
    - use DiagramModel counters if present。
    - summary text in `stderr_text`, empty `stdout_text`。
  - parent directory creation failure:
    - output write failure と同じ扱いにする。
  - degraded / hard failure before write:
    - do not write artifact。
    - `CommandResult.artifact_path=None`。
    - summary text in `stderr_text`。
  - stream material text:
    - deterministic line-oriented summary including counters, failure_reason if present, diagnostics code/message list。

#### I1 — success write
- Red:
  - clean success writes file, returns artifact path, `stdout_text` summary, exit 0。
- Green:
  - report orchestration。

#### I2 — failure streams
- Red:
  - RenderFailureSignal does not write file and returns `stderr_text` summary / non-zero。
  - writer raising `OSError` returns output write failure with DiagramModel counters。
  - parent directory creation failure returns `failure_reason=output_write_failure`, non-zero exit, `stderr_text`, `artifact_path=None`, no `stdout_text`, and DiagramModel counters。
- Green:
  - write failure handling。

### S90 — docs impact resolution
- 対象:
  - issue report。
- 対応:
  - 実装内容、検証結果、review verdict、non-scope (`app.*-wiring`, console script) を記録する。

### S99 — final diff review quality gate
- branch diff scope:
  - docs commit 以降の `iss-00019` 差分。
- required validation:
  - `uv run --with pytest pytest tests/report/test_policy.py tests/model/test_contracts.py tests/render/test_document.py tests/cli/test_bind.py -q`
  - `uv run --with pytest pytest -q`
  - `./spec-dock/scripts/spec-dock validate`
  - `git diff --check`
  - `rg --files | rg '[A-Z]'` を実行し、既存許可 path (`AGENTS.md`, `README.md`) 以外の新規 uppercase path が増えていないことを確認する。
  - generated file cleanup check。
- reviewer approvals:
  - code-reviewer pass。
  - qa-reviewer pass。
- report update:
  - final diff review verdict / closing evidence / no-op 理由を `./spec-dock/active/issue/report.md` に残す。
- commit expectation:
  - docs commit と implementation commit を分ける。

## 未確定事項
- なし:
  - `recoverability=recoverable` は operational/no-op warning、`degraded_output` は output completeness degradation として扱う。
  - app wiring と stdout/stderr emission は downstream owner として非スコープ化する。

## final exit contract
- AC/EC 達成:
  - S01-S04 の tests と review pass で確認する。
- docs impact resolved:
  - `report.md` を更新する。
- final diff approved:
  - code-reviewer / qa-reviewer pass と validation pass を report に残す。
