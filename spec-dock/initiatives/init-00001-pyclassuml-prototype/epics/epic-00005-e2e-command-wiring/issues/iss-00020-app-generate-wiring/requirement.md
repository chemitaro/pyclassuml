---
種別: 要件定義書（Issue）
ID: "iss-00020"
タイトル: "App Generate Wiring"
関連GitHub: ["#20"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
親: ["epic-00005", "init-00001"]
---

# iss-00020 App Generate Wiring — 要件定義（WHAT / WHY）

## 目的
- explicit target 起点の `generate` を end-to-end で成立させ、`app` が common pipeline の stitcher だけで機能する状態を作る。
- summary / result は `report`、usage error は `cli`、changed class inventory は `analyze`、という upstream owner split を保ったまま command として閉じる。

## スコープ
- MUST:
  - `CommandRequest(command=generate)` を受け、`config.context-resolve` と `targets.explicit-target-normalize` を呼ぶ。
  - `TargetSet` を `parse -> analyze.traversal -> analyze.relationship-and-selection -> ChangedClassInventory -> frameworks -> render -> report` の canonical order へ接続する。
  - generate 専用の changed-file context として empty set を analyze に渡し、`ChangedClassInventory(class_count=0, changed_files=[])` を `analyze` owner で downstream に載せる。
  - `TargetSet.observations`、upstream diagnostics、`ChangedClassInventory` を `report` へ transport する。
  - `report` が返した `ReportRunResult` を app result として返し、その中の `CommandResult` を再構築せず downstream へ transport できる形にする。
- MUST NOT:
  - usage error summary を生成しない。
  - explicit target normalization、graph 解析、framework enrich、render、summary synthesis を再実装しない。
  - `TargetSet` 以降に generate 固有分岐を追加しない。
  - actual stdout / stderr へ write しない。
- OUT OF SCOPE:
  - `diff` の current-state / untracked handling。
  - console 表示の装飾。
  - `cli.run_cli` の handler signature 変更と actual process stdout / stderr emission。
  - retry や progress report。

## 境界
- Always:
  - seam owner は `app`。
  - front-stage 差分は explicit target normalization に閉じ、post-`TargetSet` pipeline は command-neutral とする。
  - `ChangedClassInventory` の producer は `analyze` に保ち、generate path では empty changed-file context を渡して zero inventory を作らせる。
  - non-usage outcome の `RunSummary` / `CommandResult` / `stdout_text` / `stderr_text` は `report` owner とする。
- Ask:
  - generate path に post-`TargetSet` の command-specific branch を足したい場合。
  - changed class 数の `0` を `app` 自身で直接合成したい場合。
- Never:
  - `cli` usage error をこの issue に流し込まない。
  - `report` が作った summary / exit code / stream material を `app` で再解釈しない。
  - `TargetSet.observations` を欠落させたまま `report` に渡さない。

## 制約
- `generate` と `diff` の差は前段 seed / changed-file context 生成に閉じる。
- `report` が summary counter を組み立てられるよう、`TargetObservations` と zero `ChangedClassInventory` を transport する。
- 同一 request、同一 upstream outputs では stage invocation order が決定的である。

## 受け入れ条件
- AC-001:
  - Actor:
    - CLI 利用者
  - Given:
    - valid な `generate` invocation と explicit target fixture がある。
  - When:
    - `app.generate-wiring` を実行する。
  - Then:
    - explicit target normalization の後は common pipeline を canonical order で通り、`.puml` artifact、`ReportRunResult.stdout_text` summary、exit code が観測できる。
  - 観測点:
    - generate transcript、filesystem observation、stdout summary review、および auto naming / `--output` path resolution が end-to-end で保たれることの review。
- AC-002:
  - Actor:
    - `report` / `app` 実装者
  - Given:
    - `TargetSet.observations` と generate の empty changed-file context がある。
  - When:
    - `app.generate-wiring` が downstream handoff を行う。
  - Then:
    - `report` は summary counter source を欠落なく受け取り、changed class 数 `0` を含む summary を構築できる。
  - 観測点:
    - issue design の transport rule、summary counter review。
- AC-003:
  - Actor:
    - CLI 利用者
  - Given:
    - invalid config、zero-target、diagram unbuildable、output write failure の scenario がある。
  - When:
    - `app.generate-wiring` を実行する。
  - Then:
    - usage error 以外の non-zero outcome は upstream / `report` owner のまま返り、`app` は summary / exit code / stream material を再分類しない。
  - 観測点:
    - failure transcript review、`iss-00006` / `iss-00019` との cross-check。

## 例外・エッジケース
- EC-001:
  - 条件:
    - explicit targets がすべて ignore または scope outside で落ち、zero-target failure になる。
  - 期待:
    - front-stage failure を downstream owner のまま返し、`app` は fallback target を作らない。
  - 観測点:
    - zero-target failure review。
- EC-002:
  - 条件:
    - warning-only success で diagram は生成できる。
  - 期待:
    - `app` は warning diagnostics と `TargetSet.observations` を保持したまま `report` に渡し、success path を維持する。
  - 観測点:
    - warning-only success review。
- EC-003:
  - 条件:
    - `report` が `output_write_failure` を返す。
  - 期待:
    - `.puml` success を偽装せず、report-owned `ReportRunResult` をそのまま返し、その nested `command_result` の non-zero outcome を保持する。
  - 観測点:
    - output write failure review。

## 未確定事項
- なし:
  - generate path の owner split と common pipeline guardrail は initiative canonical docs で確定済みである。
