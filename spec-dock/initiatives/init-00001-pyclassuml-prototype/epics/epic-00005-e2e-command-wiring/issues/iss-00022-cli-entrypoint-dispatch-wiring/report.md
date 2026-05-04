---
種別: 実装報告書（Issue）
ID: "iss-00022"
タイトル: "CLI Entrypoint Dispatch Wiring"
関連GitHub: ["#22"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00005", "init-00001"]
---

# iss-00022 CLI Entrypoint Dispatch Wiring — 実装報告（LOG）

## 実装サマリー
- completion audit で見つかった外部 CLI gap を閉じるため、console script / dispatch / process stream projection / `include_untracked` default を実装対象として契約化した。

## 実装記録（セッションログ）

### 2026-05-04 contract repair

#### 対象
- Step: M1 / SG1
- AC/EC: AC-001, AC-002, AC-003, AC-004, EC-001, EC-002

#### 実施内容
- completion audit で `uv run pyclassuml --help` が `No such file or directory` になることを確認した。
- `pyproject.toml` に console script がないこと、`cli.run_cli` が `ReportRunResult` app seam を process streams へ接続していないことを確認した。
- initiative requirement の `diff.include_untracked` default `true` と現行 CLI/config default `false` の不整合を確認した。
- spec-reviewer fail を受け、`iss-00022` が `iss-00006` / `iss-00008` の古い default `false` 契約を supersede し、upstream issue docs を同期する方針を追記した。
- issue requirement/design/plan/report をテンプレートから実装可能な契約へ置き換えた。

#### 実行コマンド / 結果
```bash
uv run pyclassuml --help

error: Failed to spawn: `pyclassuml`
  Caused by: No such file or directory (os error 2)

./spec-dock/scripts/spec-dock active show

initiative: init-00001 (...)
epic: epic-00005 (...)
issue: iss-00022 (...)
```

#### 変更したファイル
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00005-e2e-command-wiring/issues/iss-00022-cli-entrypoint-dispatch-wiring/requirement.md`
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00005-e2e-command-wiring/issues/iss-00022-cli-entrypoint-dispatch-wiring/design.md`
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00005-e2e-command-wiring/issues/iss-00022-cli-entrypoint-dispatch-wiring/plan.md`
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00005-e2e-command-wiring/issues/iss-00022-cli-entrypoint-dispatch-wiring/report.md`

#### コミット
- 未実施。SG1 pass 後に docs commit を作成する。

#### メモ
- #1〜#5 は一度 close したが、この audit gap を閉じるため #22 を追加した。#22 完了後に再 sync / close state を確認する。
- `include_untracked` default の変更は owner-boundary 上は foundation seam に属するため、この issue の実装では source と docs を同時に同期する。

## 省略/例外メモ
- 該当なし。

### 2026-05-04 implementation

#### 対象
- Step: S01, S02, S03, S99
- AC/EC: AC-001, AC-002, AC-003, AC-004, EC-001, EC-002

#### 実施内容
- `pyproject.toml` に console script `pyclassuml = "pyclassuml.cli.main:main"` を追加し、src layout package として `uv run pyclassuml` が起動できる最小 build metadata を追加した。
- `src/pyclassuml/cli/main.py` を追加し、`run_cli(argv, Path.cwd(), handler)` から `app.run_generate` / `app.run_diff` へ timestamp 付きで dispatch し、`CliRunResult.stdout_text` / `stderr_text` を process streams へ投影するようにした。
- `cli.run_cli` / `CliRunResult` を `CommandResult` handler 互換のまま `ReportRunResult` handler に対応させ、report-owned stdout/stderr/exit code を再合成せず保持するようにした。
- argparse help は stdout / exit 0、usage error は stderr / exit 2 として handler を呼ばないようにした。
- `diff.include_untracked` の external default を `true` に変更し、`--include-untracked` は明示 true、`--no-include-untracked` は明示 false として bind するようにした。
- CLI 未指定時の `include_untracked` は config value を優先し、config 未指定時に default `true` へ落ちるよう `CLI > config > default` を維持した。
- `iss-00006` requirement / plan / report と `iss-00008` design の stale default `false` 記述を `iss-00022` の supersession として同期した。
- `tests/cli/test_main.py` を追加し、main-level で help / generate / diff default untracked / opt-out / head no-op warning / invalid base failure の process projection を確認した。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest tests/cli tests/config -q
# 56 passed

uv run --with pytest pytest tests/cli tests/config tests/app tests/report tests/vcs tests/targets -q
# 155 passed

uv run --with pytest pytest -q
# 274 passed

UV_LINK_MODE=copy uv run pyclassuml --help
# exit 0, usage text

UV_LINK_MODE=copy uv run pyclassuml generate --cwd <tmprepo> pkg/model.py --output diagram.puml
# exit 0, clean_success stdout, empty stderr, artifact contains User class

UV_LINK_MODE=copy uv run pyclassuml diff --cwd <tmprepo> --base base --output diff.puml
# exit 0, seed_file_count: 2, changed_class_count: 2, untracked class included

UV_LINK_MODE=copy uv run pyclassuml diff --cwd <tmprepo> --base base --current-state head --output head.puml
# exit 0, warning:head_untracked_noop, untracked omitted from artifact

UV_LINK_MODE=copy uv run pyclassuml diff --cwd <tmprepo> --base missing-ref --output invalid.puml
# exit 1, stderr includes failure_reason: vcs_read_failure and error:invalid_base_ref, no artifact

./spec-dock/scripts/spec-dock validate
# spec-dock: ok (validate) nodes=22
```

#### 変更したファイル
- `pyproject.toml`
- `src/pyclassuml/cli/bind.py`
- `src/pyclassuml/cli/main.py`
- `src/pyclassuml/config/resolver.py`
- `src/pyclassuml/model/contracts.py`
- `tests/cli/test_bind.py`
- `tests/cli/test_main.py`
- `tests/config/test_context_resolve.py`
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00002-foundation-contracts/issues/iss-00006-cli-request-bind-and-exit-contract/requirement.md`
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00002-foundation-contracts/issues/iss-00006-cli-request-bind-and-exit-contract/plan.md`
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00002-foundation-contracts/issues/iss-00006-cli-request-bind-and-exit-contract/report.md`
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00002-foundation-contracts/issues/iss-00008-config-context-resolve/design.md`
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00005-e2e-command-wiring/issues/iss-00022-cli-entrypoint-dispatch-wiring/report.md`

#### コミット
- 未実施。ユーザー指示により edit only。

### 2026-05-04 final review fixes

#### 対象
- Step: S02, S03, S99
- AC/EC: AC-001, AC-003, EC-001

#### 実施内容
- code-reviewer P2 指摘を受け、CLI 未指定の `--current-state` が config `[diff].current_state` を上書きしないよう `DiffOptions.current_state_cli_provided` を追加した。
- `--current-state` 明示時は CLI が勝ち、未指定時は config value、config 未指定時は default `working-tree` になることを `tests/cli/test_bind.py` / `tests/config/test_context_resolve.py` / `tests/model/test_contracts.py` で固定した。
- QA P2 指摘を受け、`tests/cli/test_main.py` に `uv run pyclassuml --help` subprocess test を追加し、console script の削除や entrypoint typo を検出できるようにした。test 内で `uv.lock` が新規生成された場合は削除する。
- `iss-00008` design の config merge 記述を current_state / include_untracked の provenance に合わせて更新した。

#### review gate
- code-reviewer: final review P2 finding addressed; no remaining local code-review blocker in this implementation pass.
- qa-reviewer: final review P2/P3 findings addressed; subprocess coverage, report evidence, and cleanup checks added.

#### final validation evidence
```bash
uv run --with pytest pytest tests/cli tests/config tests/model/test_contracts.py -q
# 79 passed

uv run --with pytest pytest tests/cli tests/config tests/app tests/report tests/vcs tests/targets -q
# 159 passed

uv run --with pytest pytest -q
# 278 passed

UV_LINK_MODE=copy uv run pyclassuml --help
# exit 0, usage text

UV_LINK_MODE=copy uv run pyclassuml generate --cwd <tmprepo> pkg/model.py --output diagram.puml
# exit 0, clean_success stdout, empty stderr, artifact contains User class

UV_LINK_MODE=copy uv run pyclassuml diff --cwd <tmprepo> --base base --output diff.puml
# exit 0, seed_file_count: 2, changed_class_count: 2, untracked class included

UV_LINK_MODE=copy uv run pyclassuml diff --cwd <tmprepo> --base base --current-state head --output head.puml
# exit 0, warning:head_untracked_noop, untracked omitted from artifact

UV_LINK_MODE=copy uv run pyclassuml diff --cwd <tmprepo> --base missing-ref --output invalid.puml
# exit 1, stderr includes failure_reason: vcs_read_failure and error:invalid_base_ref, no artifact

./spec-dock/scripts/spec-dock validate
# spec-dock: ok (validate) nodes=22

git diff --check
# pass, no output

rg --files | rg '[A-Z]'
# existing AGENTS.md / README.md paths only; no new uppercase paths

find . -type d -name __pycache__ -o -type f -name '*.pyc' -o -name uv.lock
# final cleanup leaves no output
```

### 2026-05-04 QA P2/P3 follow-up

#### 対象
- Step: S99
- AC/EC: AC-001, AC-002, AC-003, AC-004

#### 実施内容
- QA reviewer P2 を受け、`tests/cli/test_main.py` の console-script subprocess coverage を `--help` から実際の `generate` / `diff` default include untracked / `diff --no-include-untracked` / invalid base failure まで拡張した。
- QA reviewer P3 を受け、subprocess smoke helper を `uv run --quiet --no-project --isolated --with <repo-root> pyclassuml ...` に変更し、cwd は fixture project/repo に限定した。
- smoke helper は `PYTHONPYCACHEPREFIX` と `UV_CACHE_DIR` を test tmp 配下へ向け、`uv.lock` / `.venv` / `build` / `src/*.egg-info` の実行前状態を記録したうえで、新規生成分のみ `finally` で cleanup する。

#### validation evidence
```bash
uv run --with pytest pytest tests/cli/test_main.py -q
# 11 passed

uv run --with pytest pytest tests/cli tests/config tests/model/test_contracts.py -q
# 83 passed

uv run --with pytest pytest -q
# 282 passed

git diff --check
# pass, no output

./spec-dock/scripts/spec-dock validate
# spec-dock: ok (validate) nodes=22

rg --files | rg '[A-Z]'
# existing AGENTS.md / README.md paths only; no new uppercase paths

find . \( -type d -name __pycache__ -o -type f -name '*.pyc' -o -name uv.lock -o -name '*.egg-info' \) -print
# final cleanup leaves no output
```

#### final review gate
- code-reviewer: pass。CLI entrypoint、binding/config default、main-level tests、console script wiring、active issue contract に P0/P1/P2/P3 findings なし。
- qa-reviewer: pass。前回 P2/P3 は subprocess coverage と generated-state cleanup により解消済み。P0/P1 相当の不足なし。
