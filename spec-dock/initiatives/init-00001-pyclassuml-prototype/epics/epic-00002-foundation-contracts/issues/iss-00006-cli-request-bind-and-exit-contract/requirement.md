---
種別: 要件定義書（Issue）
ID: "iss-00006"
タイトル: "CLI Request Bind And Exit Contract"
関連GitHub: ["#6"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
親: ["epic-00002", "init-00001"]
---

# iss-00006 CLI Request Bind And Exit Contract — 要件定義（WHAT / WHY）

## 目的
- `cli` seam の責務を、usage error、`--cwd` を含む CLI option bind、`CommandResult.exit_code` の伝播に限定する。
- `process_cwd` と CLI option 群を `CommandRequest` へ束縛し、4 roots 解決や target normalization を後段へ漏らさず渡す。

## スコープ
- MUST:
  - `generate` / `diff` の subcommand と option を validation 済み `cli_options` として `CommandRequest` に束縛する。
  - `cli_options` の canonical shape を次に固定する。
    - `command: generate | diff`
    - common option: `cwd`, `config`, `project_root`, `package_root`, `scope_root`, `output`, `ignore[]`, `depth`, `strict`, `target_python`
    - `generate.targets[]`
    - `diff.base_ref`, `diff.current_state`, `diff.include_untracked`
  - `process_cwd` を `CommandRequest` に含める。
  - usage error では non-zero を返す。
  - `CommandResult.exit_code` を CLI process の終了コードへそのまま反映する。
- MUST NOT:
  - `execution_cwd` や 4 roots を CLI で resolve しない。
  - config merge、target normalization、summary taxonomy を CLI で再判断しない。
- OUT OF SCOPE:
  - `ExecutionContext` / `AnalysisConfig` の決定。
  - `.puml` artifact 出力や changed class 集計。

## 受け入れ条件
- AC-001:
  - Actor:
    - CLI 利用者
  - Given:
    - 有効な `generate` または `diff` invocation がある。
  - When:
    - CLI が request bind を行う。
  - Then:
    - `CommandRequest` に `process_cwd` と canonical shape の `cli_options` が含まれ、`--cwd` 指定は未解決の option 値として後段へ渡る。
  - 観測点:
    - `CommandRequest(process_cwd, cli_options)` 契約、CLI transcript。
- AC-002:
  - Actor:
    - CLI 利用者
  - Given:
    - 不正 option または usage error がある。
  - When:
    - CLI が parse / bind を試みる。
  - Then:
    - 後段 seam を呼ばずに `cli_usage_error` を持つ non-zero summary / exit で終了する。
  - 観測点:
    - usage error transcript。
- AC-003:
  - Actor:
    - CLI 利用者
  - Given:
    - 後段から `CommandResult(exit_code=0|non-zero)` が返る。
  - When:
    - CLI が process 終了を行う。
  - Then:
    - exit code を再解釈せずにそのまま返す。
  - 観測点:
    - success / failure command transcript。

## 例外・エッジケース
- EC-001:
  - 条件:
    - `--cwd` が相対 path で指定される。
  - 期待:
    - CLI は resolve せず raw option として `CommandRequest` へ保持し、`config.context-resolve` が `process_cwd` 基準で解決する。
  - 観測点:
    - `CommandRequest` field review。
- EC-002:
  - 条件:
    - `diff.current_state` や `include_untracked` が指定される。
  - 期待:
    - CLI は option 値を bind するだけで、default 補完や no-op 判定を行わない。
  - 観測点:
    - `cli_options` handoff review。

## 制約
- CLI 相対 path の基準は initiative canonical docs に従い `execution_cwd` だが、その resolve owner は `config` とする。
- raw argv を後段へ漏らさず、`CommandRequest` を唯一の request handoff とする。
- `config` / `targets` / `vcs` は `CommandRequest.cli_options` の field 名を独自定義せず、上記 canonical shape を参照する。
- success / failure の stream policy は `report` owner のため、この issue では exit code 伝播のみを固定する。
- usage error だけは `cli` owner で `cli_usage_error` を生成し、failure summary を stderr に出す。

## 未確定事項
- なし:
  - issue baseline と v5 で owner と observable behavior が十分に確定している。
