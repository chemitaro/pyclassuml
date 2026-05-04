---
種別: 要件定義書（Issue）
ID: "iss-00022"
タイトル: "CLI Entrypoint Dispatch Wiring"
関連GitHub: ["#22"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
親: ["epic-00005", "init-00001"]
---

# iss-00022 CLI Entrypoint Dispatch Wiring — 要件定義（WHAT / WHY）

## 目的
- `pyclassuml` を package console script として起動できる外部 CLI prototype にする。
- `cli` が `app.run_generate` / `app.run_diff` を dispatch し、`ReportRunResult.stdout_text` / `stderr_text` を実プロセス stdout/stderr に流す。
- completion audit で見つかった initiative-level gap を閉じ、GitHub issue / SpecDock 上の全 task close だけでなく、外部 CLI の observable contract を満たす。

## 背景・現状
- 現状の挙動:
  - `uv run pyclassuml --help` が `No such file or directory` で失敗する。
  - `pyproject.toml` に `[project.scripts] pyclassuml = ...` がない。
  - `cli.run_cli` は usage bind と `CommandResult` handler propagation だけを扱い、`ReportRunResult` app seam と実 process stream emission を接続していない。
  - `diff.include_untracked` の CLI/config default は現実実装では `false` だが、initiative requirement の外部契約は default `true` である。
  - `iss-00006` / `iss-00008` には default `false` の古い seam-local 契約が残っている。
- 現状の課題:
  - all issues closed / tests pass / SpecDock dashboard 0 は、外部 CLI prototype の受け入れ契約を直接満たす証拠にならない。
  - `generate` / `diff` app seams は実装済みだが、利用者が `pyclassuml generate ...` / `pyclassuml diff ...` として実行できない。
- 再現手順:
  1. `uv run pyclassuml --help`
  2. `No such file or directory` が返る。
- 情報源:
  - `spec-dock/initiatives/init-00001-pyclassuml-prototype/requirement.md`
  - `src/pyclassuml/cli/bind.py`
  - `src/pyclassuml/app/generate.py`
  - `src/pyclassuml/app/diff.py`
  - `pyproject.toml`

## スコープ
- MUST:
  - `pyproject.toml` に console script `pyclassuml` を追加する。
  - CLI entrypoint `main(argv=None) -> int` を追加し、`sys.argv[1:]` / `Path.cwd()` / current timestamp を使って `run_cli` を実行する。
  - `generate` request は `app.run_generate(request, timestamp=...)`、`diff` request は `app.run_diff(request, timestamp=...)` へ dispatch する。
  - `ReportRunResult.command_result.exit_code` を process exit code として返す。
  - `ReportRunResult.stdout_text` は stdout、`ReportRunResult.stderr_text` と usage error の argparse text は stderr へ write する。
  - success path は `.puml` artifact を filesystem に書き、summary を stdout で観測できる。
  - failure path は `.puml` artifact を保証せず、summary / diagnostics を stderr で観測できる。
  - `diff` の外部 CLI default は initiative requirement に合わせ、`include_untracked=true` として観測できる。
  - `iss-00006` / `iss-00008` の default `false` 契約を、この issue の completion-audit repair として明示的に supersede し、必要な upstream issue docs を同期する。
  - `current_state=head` かつ default / explicit `include_untracked=true` では、untracked を seed に含めず no-op warning を summary に残す。
- MUST NOT:
  - `cli` に parse / analyze / render / report policy を持ち込まない。
  - `cli` が summary 文面、exit policy、artifact path を再合成しない。
  - `app` や `report` から実プロセス stdout/stderr へ直接 write しない。
  - 対象 repository を書き換えない。ただし `.puml` artifact の出力は利用者指定の正本出力であり許可する。
- OUT OF SCOPE:
  - console 装飾、progress bar、rich formatting。
  - install packaging metadata の完全整備。
  - namespace package 完全対応や未実装 future extension。

## 境界
- Always:
  - usage error の producer は `cli`。
  - non-usage result の producer は `report`。
  - `cli` は process stream emission と exit code projection だけを担う。
  - `app` は `ReportRunResult` を返すだけで process streams へ直接 emit しない。
  - `include_untracked` default は initiative requirement を最上位 source of truth とし、この issue の契約が `iss-00006` / `iss-00008` の古い default `false` 記述を supersede する。
- Ask:
  - CLI command option schema を大きく変える場合。
  - `include_untracked` default を initiative requirement 以外へ戻したい場合。
- Never:
  - `cli` が `ReportRunResult.stdout_text` / `stderr_text` を再分類しない。
  - `.puml` 本文を stdout/stderr へ流さない。

## 非交渉制約
- read-only / AST-only / non-invasive を維持する。
- 同一入力・同一 timestamp・同一 Git 基準では、`.puml` artifact と summary counters は決定的である。
- 新規 path は lowercase のみ。

## 受け入れ条件
- AC-001 console script availability:
  - Actor:
    - CLI 利用者
  - Given:
    - package checkout がある。
  - When:
    - `uv run pyclassuml --help` を実行する。
  - Then:
    - command が存在し、usage text を表示し、exit code `0` で終了する。
  - 観測点:
    - subprocess result。
- AC-002 generate process wiring:
  - Actor:
    - CLI 利用者
  - Given:
    - Python file fixture と output path がある。
  - When:
    - `uv run pyclassuml generate <file> --output <path>` を実行する。
  - Then:
    - exit code `0`、stdout summary、empty stderr、`.puml` artifact が観測できる。
  - 観測点:
    - stdout/stderr/filesystem。
- AC-003 diff process wiring:
  - Actor:
    - CLI 利用者
  - Given:
    - Git repo、base ref、tracked changed Python file、untracked Python file がある。
  - When:
    - `uv run pyclassuml diff --base <ref> --output <path>` を `--include-untracked` なしで実行する。
  - Then:
    - initiative default により untracked Python file も seed / artifact / changed class count に含まれる。
  - 観測点:
    - stdout summary、artifact text、changed counters。
- AC-004 usage and failure streams:
  - Actor:
    - CLI 利用者
  - Given:
    - usage error または invalid base ref がある。
  - When:
    - CLI を実行する。
  - Then:
    - non-zero exit、stderr diagnostics / summary、empty stdout が観測できる。
  - 観測点:
    - subprocess result。

## 例外・エッジケース
- EC-001:
  - 条件:
    - `diff --current-state head` で default `include_untracked=true` が適用される。
  - 期待:
    - untracked を artifact に含めず、`head_untracked_noop` warning を stdout summary に残す。
  - 観測点:
    - stdout summary、artifact text。
- EC-002:
  - 条件:
    - app seam が hard failure `ReportRunResult.stderr_text` を返す。
  - 期待:
    - CLI はその stderr_text を stderr へそのまま write し、stdout は空にする。
  - 観測点:
    - subprocess result。

## 未確定事項
- なし:
  - これは completion audit で見つかった implementation gap の修復 issue であり、外部 CLI 契約は initiative requirement に従う。
