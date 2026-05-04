---
種別: 実装報告書（Issue）
ID: "iss-00019"
タイトル: "Report Artifact Summary Exit Policy"
関連GitHub: ["#19"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00004", "init-00001"]
---

# iss-00019 Report Artifact Summary Exit Policy — 実装報告（LOG）

## 実装サマリー (任意)
- 現行 repo には `RunSummary` / `CommandResult` / `DiagramModel` / `RenderFailureSignal` は存在するが、report seam 実装はまだ存在しない。
- この issue では `src/pyclassuml/report/` の reusable report API を完成条件にし、app wiring / console script は downstream issue に残す。

## 実装記録（セッションログ） (必須)

### 2026-05-04 - contract repair

#### 対象
- Step: SG1
- AC/EC: AC-001, AC-002, AC-003, EC-001, EC-002, EC-003

#### 実施内容
- dashboard で `iss-00019` が ready であることを確認した。
- spec-manager により `iss-00019` を active 化し、`spec-dock validate` が pass することを確認した。
- `requirement.md` / `design.md` / `plan.md` を読み、`plan.md` がテンプレートのままで実装開始できないことを確認した。
- `src/pyclassuml/model/contracts.py` を確認し、`Recoverability` の現行 shared enum が `recoverable | degraded_output | fatal` であり、`noop` enum value は存在しないことを確認した。
- `iss-00010` の no-op warning 実装を確認し、`head_untracked_noop` は `recoverability=Recoverability.RECOVERABLE` として downstream へ渡されることを確認した。
- `iss-00018` の render seam を確認し、success path は `DiagramModel` / `PlantUmlText`、failure path は `RenderFailureSignal` を返す contract が実装済みであることを確認した。
- requirement / design を現行 enum に合わせ、operational/no-op warning は `recoverability=recoverable`、degraded output warning は `recoverability=degraded_output` として classifier を固定した。
- downstream app / cli が stream 出力できるよう、report seam-local result として `ReportRunResult(command_result, outcome_kind, stdout_text, stderr_text)` を返す contract を design に追加した。
- 自動命名の timestamp は report API 入力として受け取り、report 実装内で clock を直接読まない contract にした。
- hard failure と degraded failure の境界を、hard-failure reason diagnostic / `RenderFailureSignal` / output write failure に分けて具体化した。
- spec-reviewer fail を受け、failure inputs が重なる場合の precedence を `hard_failure` > `strict_promoted_failure` > `degraded_failure` と明記した。
- spec-reviewer fail を受け、missing parent directory は report が作成し、作成失敗は `output_write_failure` とする contract に固定した。
- spec-reviewer pass 後の P2 指摘を受け、parent directory creation failure の expected result を plan の Red case に明記した。
- `plan.md` を S01-S04 / SG1 / RG1 / QG1 / S90 / S99 まで具体化し、実装開始可能な execution contract に修復した。

#### 実行コマンド / 結果
```bash
./spec-dock/scripts/spec-dock deps check iss-00019 --github
# ready=true blockers=0

./spec-dock/scripts/spec-dock active set iss-00019
# spec-dock: ok (active set) target=iss-00019 initiative=init-00001 epic=epic-00004 issue=iss-00019

./spec-dock/scripts/spec-dock active show
# issue: iss-00019

./spec-dock/scripts/spec-dock validate
# spec-dock: ok (validate) nodes=21

rg -n "noop|Recoverability" spec-dock src tests
# `noop` は diagnostic code / prose のみで、shared enum は recoverable/degraded_output/fatal。
```

#### 変更したファイル
- `spec-dock/active/issue/requirement.md` - recoverability enum と stream result contract を明確化。
- `spec-dock/active/issue/design.md` - `ReportRunResult`、timestamp input、hard/degraded failure 境界を明確化。
- `spec-dock/active/issue/plan.md` - execution contract を具体化。
- `spec-dock/active/issue/report.md` - contract repair の判断と証跡を記録。

#### コミット
- 未作成。spec-reviewer pass 後に docs commit を作成する。

#### メモ
- `app.generate-wiring` / `app.diff-wiring` と stdout/stderr emission は downstream owner に残す。
- `report` は upstream DTO / diagnostics / counters を消費するだけで、parse / analyze / frameworks / render / vcs を再実行しない。

---

## 遭遇した問題と解決 (任意)
- 問題: active docs は `noop` recoverability を要求していたが、現行 shared enum には `noop` が存在しない。
  - 解決: no-op warning の diagnostic code / prose は維持しつつ、classifier は `Recoverability.RECOVERABLE` を operational/no-op warning として扱う contract に修正した。

## 学んだこと (任意)
- report seam は app / cli に十分な stream material を返す必要があるが、実際の stdout/stderr emission は app/cli wiring issue に残す方が責務分離しやすい。

## 今後の推奨事項 (任意)
- downstream `iss-00020` / `iss-00021` では `ReportRunResult.stdout_text` / `stderr_text` を CLI stdout/stderr へ接続し、`CommandResult` を `run_cli` の handler result として返す。

## 省略/例外メモ (必須)
- この issue では app orchestration、console script 登録、PlantUML text generation は実装しない。
