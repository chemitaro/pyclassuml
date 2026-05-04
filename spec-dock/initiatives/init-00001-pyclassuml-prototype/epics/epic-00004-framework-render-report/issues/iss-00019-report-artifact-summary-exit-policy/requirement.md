---
種別: 要件定義書（Issue）
ID: "iss-00019"
タイトル: "Report Artifact Summary Exit Policy"
関連GitHub: ["#19"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
親: ["epic-00004", "init-00001"]
---

# iss-00019 Report Artifact Summary Exit Policy — 要件定義（WHAT / WHY）

## 目的
- render と upstream 各 seam の結果を受けて、`.puml` artifact、summary、stream material routing、strict / warn exit policy を一元化する。
- filesystem write と最終終了コードの owner を `report` に固定し、`cli` / `app` / `render` が reporting policy を再実装しない状態を作る。

## スコープ
  - MUST:
  - success / warning-only success / degraded success で `.puml` artifact を filesystem へ書き出す。
  - `--output` 未指定時の自動命名、`--output` 指定時の `execution_cwd` 基準 path resolve、同名衝突時 suffix 付与を固定する。
  - success path では summary を `ReportRunResult.stdout_text`、failure path では diagnostics / summary を `ReportRunResult.stderr_text` に載せる。
  - strict / warn と degraded success / degraded failure / hard failure の taxonomy を固定する。
  - `Diagnostic.failure_reason` に基づいて strict-promotable diagnostics を判定し、`strict_promoted_failure` を `report` owner で決定する。
  - warning diagnostics の `recoverability` に基づき、`warning_only_success` と `degraded_success` の classifier を固定し、artifact completeness を下げない operational warning は現行 shared enum の `recoverable`、omitted-or-ambiguous content warning は `degraded_output` を使う。
  - parse の syntax degradation は、warn mode では `recoverability=degraded_output` を持つ warning、strict mode では `failure_reason=strict_syntax_error` を持つ failure として扱う。
  - success path の extracted class / relation counter は最終 `DiagramModel` を authoritative source とする。
  - `RenderFailureSignal` がある non-success outcome では、その `class_count` / `relation_count` を summary の authoritative counter source とする。
  - producer seam が未実行のまま hard failure になった counter は `0` fallback で summary を合成する。
  - `output_write_failure` のように render 成功後に起きる hard failure では、summary counter は `DiagramModel` を authoritative source とする。
  - `RunSummary` と `CommandResult` を authoritative output として返す。
  - downstream app / cli が stream 出力できるよう、seam-local result として `stdout_text` / `stderr_text` を返す。
  - failure inputs が重なる場合は `hard_failure` > `strict_promoted_failure` > `degraded_failure` の順で outcome を選ぶ。
- MUST NOT:
  - parse / analyze / frameworks / render を再実行しない。
  - diagram shape や relation 補強を補正しない。
  - `execution_cwd` resolve や target normalization を再実装しない。
  - render 起因の class / relation omission を success taxonomy の warning として扱わない。
- OUT OF SCOPE:
  - console 表示の文言装飾。
  - 実プロセスの stdout / stderr への emission。
  - PlantUML text 自体の生成。
  - `app.generate-wiring` / `app.diff-wiring` の command orchestration。

## 境界
- Always:
  - seam owner は `report`。
  - upstream shared handoff は `PlantUmlText`, `DiagramModel`, `ExecutionContext`, `ChangedClassInventory`, `TargetSet.observations`, VCS diff diagnostics などの確定済み DTO / counter source。
  - `generate` path では upstream が `ChangedClassInventory(class_count=0, changed_files=[])` を必ず supply し、`report` は DTO の有無分岐を持たない。
  - render が `DiagramModel` / `PlantUmlText` を構成できない場合は、upstream は `RenderFailureSignal(failure_reason, diagnostics, class_count, relation_count, partial_diagram_present)` を `report` へ handoff する。
  - downstream shared handoff は `RunSummary` と `CommandResult`。
  - 自動命名の timestamp は report API の入力として受け取り、`report` 内で現在時刻を直接読まない。
- Ask:
  - failure taxonomy を initiative acceptance から変更したい場合。
  - artifact naming の timestamp / suffix rule を変えたい場合。
- Never:
  - warning を勝手に relation 追加や diagram 修復で隠さない。
  - output path resolve を `process_cwd` 基準へ戻さない。
  - `report` 以外で non-zero policy を最終決定させない。

## 制約
- `.puml` artifact は filesystem を正本出力先とし、stdout/stderr と混在させない。
- `--output` 指定または自動命名の parent directory が存在しない場合、report は parent directory を作成する。作成失敗は `output_write_failure` とする。
- summary counter と failure reason は initiative requirement の受け入れ契約を満たす粒度で観測できる。
- 同一入力・同一 output path 状態では summary と exit decision が決定的である。
- hard failure でも summary は生成し、未供給 counter を理由に summary 自体を欠落させない。

## 受け入れ条件
- AC-001:
  - Actor:
    - CLI 利用者
  - Given:
    - render 済み `PlantUmlText` と clean success / warning-only success / degraded success の upstream diagnostics がある。
  - When:
    - `report.artifact-summary-exit-policy` を実行する。
  - Then:
    - initiative requirement の outcome table どおり、clean success / warning-only success / degraded success では `.puml` artifact が書き出され、summary は `ReportRunResult.stdout_text` に載り、終了コードは `0` になる。
  - 観測点:
    - artifact path、`stdout_text` summary、exit code review、および success path summary counter が `DiagramModel.rendered_classes` / `rendered_relations` を起点にしていることの review。
- AC-002:
  - Actor:
    - CLI 利用者
  - Given:
    - `--output` 未指定 / 指定、同名ファイル存在、`generate` / `diff` の各 scenario がある。
  - When:
    - artifact path を決めて書き出す。
  - Then:
    - 自動命名、`execution_cwd` 基準 resolve、suffix collision 回避に加え、`generate` では zero `ChangedClassInventory`、`diff` では actual inventory を input として summary 合成できる。
  - 観測点:
    - filesystem observation review。
- AC-003:
  - Actor:
    - CLI 利用者
  - Given:
    - `RenderFailureSignal` を伴う diagram unbuildable、output write failure、strict で昇格する warning がある。
  - When:
    - exit policy を決定する。
  - Then:
    - initiative requirement の outcome table どおり、strict promoted failure / degraded failure / hard failure が `report` owner で non-zero として観測できる。
  - 観測点:
    - failure taxonomy review と、producer seam 未実行の early hard failure で `0` fallback counter が使われることの review。

## 例外・エッジケース
- EC-001:
  - 条件:
    - `current_state=head` かつ `include_untracked=true` の no-op warning が upstream に含まれる。
  - 期待:
    - success path を維持しつつ、warning が summary で観測できる。
    - no-op warning は diagnostic として `recoverability=recoverable` を使う。
  - 観測点:
    - warning-only success review。
- EC-002:
  - 条件:
    - `PlantUmlText` はあるが artifact write に失敗する。
  - 期待:
    - `.puml` 成功を書かず、failure summary を `ReportRunResult.stderr_text` に載せ、non-zero を返す。
  - 観測点:
    - `output_write_failure` review。
- EC-003:
  - 条件:
    - recoverable diagnostics の結果、diagram を構成できない。
  - 期待:
    - `RenderFailureSignal.failure_reason=diagram_unbuildable_after_recovery` を受けて non-zero を返し、empty diagram を成功 artifact にしない。
  - 観測点:
    - degraded failure review。

## 未確定事項
- なし:
  - report seam の baseline row と acceptance 契約は initiative canonical docs で確定済みである。
