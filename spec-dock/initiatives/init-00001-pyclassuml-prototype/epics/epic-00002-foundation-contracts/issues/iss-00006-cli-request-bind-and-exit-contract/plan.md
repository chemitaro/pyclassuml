---
種別: 実装計画書（Issue）
ID: "iss-00006"
タイトル: "CLI Request Bind And Exit Contract"
関連GitHub: ["#6"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md"]
親: ["epic-00002", "init-00001"]
---

# iss-00006 CLI Request Bind And Exit Contract — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001 valid `generate` / `diff` invocation を `CommandRequest(process_cwd, cli_options)` に束縛する。
  - AC-002 usage error は downstream handler を呼ばず `cli_usage_error` の non-zero `CommandResult` にする。
  - AC-003 downstream handler の `CommandResult.exit_code` を再解釈せず返す。
- EC:
  - EC-001 relative `--cwd` は resolve せず raw `Path` option として保持する。
  - EC-002 `diff.current_state` / `include_untracked` は bind のみ行い、default 補完や no-op 判定はしない。
- 制約:
  - CLI は `ExecutionContext` / `AnalysisConfig` / target normalization / config merge / summary taxonomy を決めない。
  - raw argv を downstream へ漏らさず、唯一の downstream handoff は `CommandRequest` にする。
  - app generate/diff wiring と packaging console script は downstream `iss-00020` / `iss-00021` の責務に残す。

## マイルストーン一覧
- M1 request binding:
  - 対象: `bind_command_request(argv, process_cwd)`。
  - exit: valid generate/diff option matrix が `CommandRequest` に束縛される。
- M2 usage error handoff:
  - 対象: argparse validation failure -> `CommandResult`。
  - exit: downstream handler は呼ばれず、`FailureReason.CLI_USAGE_ERROR` と `OriginSeam.CLI` diagnostic が返る。
- M3 exit propagation:
  - 対象: `run_cli(argv, process_cwd, handler)`。
  - exit: handler が返した `exit_code` をそのまま返し、summary / diagnostics を再構成しない。

## 実装順序の根拠
- `CommandOptions` / `CommandRequest` / `CommandResult` は `iss-00007` で既に model contract として実装済み。
- `config.context-resolve` は `CommandRequest` を入力にするため、CLI は path resolve ではなく raw option bind だけを担う。
- `app.generate-wiring` / `app.diff-wiring` は未実装なので、CLI seam behavior は injectable handler で固定する。
- console script 登録は packaging + app wiring の最終接続点なので、この issue では追加しない。
- `DiffOptions.current_state` / `include_untracked` は model DTO で required なので、CLI parser は concrete parse defaults `working-tree` / `False` を materialize する。これは VCS no-op 判定や config merge ではなく、CLI option schema を DTO に束縛するための syntactic default として扱う。
- `run_cli` は process を直接終了せず、seam-local `CliRunResult(command_result, exit_code, stderr_text)` を返す。console script が追加される後続 issue で `exit_code` を process status に変換する。

## ステップ一覧
- S01:
  - 観測可能な振る舞い: `generate` / `diff` argv が canonical `CommandOptions` に bind される。
  - closes: AC-001, EC-001, EC-002。
  - review gate: request bind contract review。
- S02:
  - 観測可能な振る舞い: usage error が `cli_usage_error` failure result になり、handler を呼ばない。
  - closes: AC-002。
  - review gate: usage error transcript review。
- S03:
  - 観測可能な振る舞い: valid request は handler に渡り、handler の `CommandResult.exit_code` がそのまま返る。
  - closes: AC-003。
  - review gate: exit propagation review。
- S90:
  - docs impact: issue report のみ。
- S99:
  - final diff review / code-reviewer / qa-reviewer / validation。

## 要件 ↔ ステップ対応
- AC-001 -> S01, S03。
- AC-002 -> S02。
- AC-003 -> S03。
- EC-001 -> S01。
- EC-002 -> S01。
- constraints -> S01, S02, S03, S99。

## レビュー / QA ゲート方針
- SG1 spec review:
  - timing: requirement/design/plan/report の contract repair 後、実装前。
  - scope: CLI owner、downstream handler 境界、usage error result、console script non-scope。
  - commit gate: pass まで review loop を回し、pass 後に docs commit を作成する。
- RG1 implementation review:
  - timing: S01-S03 実装と unit tests が green になった後。
  - scope: argv parsing, DTO construction, no path resolve, no downstream on usage error, exit propagation。
  - commit gate: pass まで review loop を回し、pass 後に `report.md` を更新してコミットする。
- QG1 QA review:
  - timing: targeted / full validation 後。
  - scope: option matrix, usage transcript, handler call/no-call, regression for config/targets/vcs consumers。
  - commit gate: pass まで test loop を回し、pass 後に `report.md` を更新してコミットする。

## 実行ルール（全ステップ共通）
- 実装は active issue を基準に進める。
- `src` / `tests` の変更は dev-coder に委任する。
- main は issue docs の contract / report を更新する。
- CLI seam は `src/pyclassuml/cli/` 配下へ追加する。新規 path は lowercase のみ。
- public API は `src/pyclassuml/cli/__init__.py` から export する。
- `pyproject.toml` の console script はこの issue では追加しない。
- `uv.lock` / `__pycache__` / `.pyc` は残さない。

## 実装ステップ

### S01 — command request bind
- target:
  - `src/pyclassuml/cli/__init__.py`
  - `src/pyclassuml/cli/bind.py`
  - `tests/cli/test_bind.py`
- design refs:
  - `design.md` request bind。
- step boundary:
  - `bind_command_request(argv: Sequence[str], process_cwd: Path) -> CommandRequest` を追加する。
  - subcommand は `generate` / `diff` のみ。
  - common options:
    - `--cwd`
    - `--config`
    - `--project-root`
    - `--package-root`
    - `--scope-root`
    - `--output`
    - repeatable `--ignore`
    - `--depth`
    - `--strict`
    - `--target-python`
  - `generate`:
    - positional `targets...` を `GenerateOptions.targets` に bind する。
  - `diff`:
    - required `--base`
    - optional `--current-state working-tree|head` with parse default `working-tree`
    - optional `--include-untracked` with parse default `False`
  - all path-like CLI values are stored as raw `Path(...)` values and are not resolved.
  - `process_cwd` is stored exactly as given.

#### I1 — generate bind
- Red:
  - generate argv with common options and relative `--cwd` produces expected `CommandRequest` fields。
- Green:
  - parser and DTO construction。
- Refactor:
  - option conversion helpers。

#### I2 — diff bind
- Red:
  - diff argv binds base/current_state/include_untracked without default/no-op decision。
- Green:
  - diff parser and `DiffOptions` construction。

### S02 — usage error result
- target:
  - `src/pyclassuml/cli/bind.py`
  - `tests/cli/test_bind.py`
- design refs:
  - `design.md` exit propagation / usage error invariant。
- step boundary:
  - `run_cli(argv, process_cwd, handler)` returns `CliRunResult` for parse/bind errors.
  - usage error result contains:
    - `CommandResult(artifact_path=None, summary=RunSummary(failure_reason=CLI_USAGE_ERROR), diagnostics=(Diagnostic(...),), exit_code=2)`
    - diagnostic: `severity=ERROR`, `origin_seam=CLI`, `recoverability=FATAL`, `failure_reason=CLI_USAGE_ERROR`, code `cli_usage_error`
  - handler is not called on usage errors.
  - `CliRunResult.exit_code == command_result.exit_code == 2`。
  - `CliRunResult.stderr_text` contains argparse usage/error text for transcript evidence.
  - `CliRunResult` does not expose raw argv to downstream.

#### I1 — invalid argv
- Red:
  - unknown option / missing required subcommand or diff `--base` returns usage error and handler call count is zero。
- Green:
  - non-exiting argparse parser and usage diagnostic。

### S03 — handler exit propagation
- target:
  - `src/pyclassuml/cli/bind.py`
  - `tests/cli/test_bind.py`
- design refs:
  - `design.md` `CommandResult.exit_code` propagation。
- step boundary:
  - valid `run_cli` calls handler exactly once with `CommandRequest`.
  - returned `CliRunResult.command_result` carries the original `CommandResult`.
  - `CliRunResult.exit_code == CommandResult.exit_code` for success and non-zero failure.
  - CLI does not rewrite summary / diagnostics.

#### I1 — success / failure exit propagation
- Red:
  - handler returning exit_code 0 yields 0.
  - handler returning exit_code 7 yields 7 and same `CommandResult` instance/material。
- Green:
  - handler invocation and result wrapper。

### S90 — docs impact resolution
- 対象:
  - issue report。
- 対応:
  - 実装内容、検証結果、review verdict、non-scope (`pyproject.toml` console script / app wiring) を記録する。

### S99 — final diff review quality gate
- branch diff scope:
  - docs commit 以降の `iss-00006` 差分。
- required validation:
  - `uv run --with pytest pytest tests/cli/test_bind.py tests/model/test_contracts.py tests/config/test_context_resolve.py tests/targets/test_explicit_target_normalize.py tests/vcs/test_diff_file_collect.py -q`
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
  - console script / real app execution は downstream issue の owner として明確に非スコープ化する。

## final exit contract
- AC/EC 達成:
  - S01-S03 の tests と review pass で確認する。
- docs impact resolved:
  - `report.md` を更新する。
- final diff approved:
  - code-reviewer / qa-reviewer pass と validation pass を report に残す。
