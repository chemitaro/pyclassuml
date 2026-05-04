---
種別: 要件定義書（Issue）
ID: "iss-00021"
タイトル: "App Diff Wiring"
関連GitHub: ["#21"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
親: ["epic-00005", "init-00001"]
---

# iss-00021 App Diff Wiring — 要件定義（WHAT / WHY）

## 目的
- diff front-stage で生成した actual changed-file context と `TargetSet` を common pipeline に接続し、`diff` を end-to-end で成立させる。
- `working-tree|head` と `include_untracked` の user-visible 差を `vcs` / `targets.diff` の seed・warning・counter 差に閉じ、post-`TargetSet` pipeline を `generate` と共通に保つ。
- app seam の戻り値を `ReportRunResult` に統一し、nested `CommandResult` と stdout/stderr material の producer を `report` に固定する。

## スコープ
- MUST:
  - `CommandRequest(command=diff)` を受け、`config.context-resolve`、`vcs.diff-file-collect`、`targets.diff-target-normalize` を呼ぶ。
  - actual changed-file context と `TargetSet` を `parse -> analyze.traversal -> analyze.relationship-and-selection -> ChangedClassInventory -> frameworks -> render -> report` の canonical order へ接続する。
  - `TargetSet.observations`、`ChangedClassInventory`、upstream diagnostics を `report` へ transport する。
  - `current_state` / `include_untracked` 差を front-stage warning / counter 差として保持し、post-`TargetSet` pipeline に diff-specific branch を追加しない。
  - `report` が返した `ReportRunResult` を app seam の結果としてそのまま返す。
- MUST NOT:
  - usage error summary を生成しない。
  - Git diff 読み取り、scope filtering、summary synthesis、exit policy、stream material synthesis を `app` で再実装しない。
  - `TargetSet` 以降で `diff` 専用の relation / render / report logic を増やさない。
  - `app` から実プロセスの stdout/stderr へ直接 emit しない。
- OUT OF SCOPE:
  - `generate` 専用 wiring。
  - `cli.run_cli` の handler signature 変更や console script 接続。
  - diff hunk 粒度 changed class 判定。
  - progress 表示や retry。

## 境界
- Always:
  - seam owner は `app`。
  - current-state / untracked の意味論は `config` / `vcs` / `targets.diff` owner のまま使い、`app` では transport だけを行う。
  - actual changed-file context から `ChangedClassInventory` を生成する authoritative owner は `analyze` とする。
  - non-usage outcome の `RunSummary` / `CommandResult` / stdout_text / stderr_text は `report` owner とし、`ReportRunResult` に保持する。
- Ask:
  - diff path に post-`TargetSet` の command-specific branch を足したい場合。
  - `current_state=head` と `include_untracked=true` の no-op warning を `app` で消したい場合。
  - `cli` の process stream emission までこの issue に含めたい場合。
- Never:
  - `cli` usage error をこの issue に流し込まない。
  - diff scope exclusion や warning を `app` で握りつぶさない。
  - `report` が作った summary / exit code / stdout_text / stderr_text を `app` で再解釈しない。

## 制約
- `generate` と `diff` の差は前段 seed / changed-file context 生成に閉じる。
- `TargetSet.observations.diff_scope_excluded_count` と no-op warning は summary source として保持する。
- 同一 diff 基準、同一 upstream outputs では stage invocation order が決定的である。
- config resolution failure でも `report` owner の result を返すため、`app` は fallback `ExecutionContext` と default `AnalysisConfig()` で `write_report` を呼ぶ。

## 受け入れ条件
- AC-001:
  - Actor:
    - CLI 利用者
  - Given:
    - valid な `diff --base <ref>` invocation と changed file fixture がある。
  - When:
    - `app.diff-wiring` を実行する。
  - Then:
    - diff front-stage の後は common pipeline を canonical order で通り、`.puml` artifact、summary、exit code、stdout_text が `ReportRunResult` として観測できる。
  - 観測点:
    - diff transcript、filesystem observation、summary review、および auto naming / `--output` path resolution が end-to-end で保たれることの review。
- AC-002:
  - Actor:
    - CLI 利用者
  - Given:
    - `working-tree|head` と `include_untracked=true|false` の fixture がある。
  - When:
    - `app.diff-wiring` を実行する。
  - Then:
    - user-visible な差は changed seed / warning / counter に限られ、post-`TargetSet` pipeline は `generate` と同一 order で維持される。
  - 観測点:
    - current-state / untracked transcript review。
- AC-003:
  - Actor:
    - `report` / `app` 実装者
  - Given:
    - `TargetSet.observations`、actual changed-file context、`ChangedClassInventory` がある。
  - When:
    - `app.diff-wiring` が downstream handoff を行う。
  - Then:
    - `report` は changed class 数、diff scope exclusion、warning 数を欠落なく summary に反映でき、actual changed-file context 本体は `ChangedClassInventory` producer のためにだけ使われる。
  - 観測点:
    - issue design の transport rule、summary counter review。
- AC-004:
  - Actor:
    - CLI 利用者
  - Given:
    - config failure、invalid `--base <ref>`、diff zero-target、render failure、output write failure の scenario がある。
  - When:
    - `app.diff-wiring` を実行する。
  - Then:
    - usage error 以外の non-zero outcome は upstream / `report` owner のまま `ReportRunResult` で返り、`app` は summary / exit code / stream material を再分類しない。
  - 観測点:
    - failure transcript review、`iss-00006` / `iss-00010` / `iss-00011` / `iss-00019` / `iss-00020` との cross-check。

## 例外・エッジケース
- EC-001:
  - 条件:
    - `current_state=head` かつ `include_untracked=true` で no-op warning が出る。
  - 期待:
    - warning を保持したまま success / failure 判定を downstream owner に委ねる。
  - 観測点:
    - no-op warning review。
- EC-002:
  - 条件:
    - changed files の一部が scope outside で除外される。
  - 期待:
    - `diff_scope_excluded_count` と関連 diagnostics を保持したまま続行または failure 判定へ進む。
  - 観測点:
    - scope exclusion counter review。
- EC-003:
  - 条件:
    - scope filtering 後に `TargetSet.seed_files` が 0 件になる。
  - 期待:
    - fallback seed を作らず、`ReportRunResult.command_result.exit_code != 0` の zero-target failure を返す。
  - 観測点:
    - diff zero-target failure review。

## 未確定事項
- なし:
  - diff path の owner split、common pipeline guardrail、`ReportRunResult` 境界は epic / upstream issue docs で確定済みである。
