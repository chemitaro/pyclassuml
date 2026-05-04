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
- `src/pyclassuml/report/` に reusable report API を追加し、artifact naming、summary synthesis、stream material routing、exit policy を report seam の責務として実装した。
- app wiring / actual stdout-stderr emission / console script は downstream issue に残す。

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
- code-reviewer の P2 指摘を受け、分類外 error diagnostic は success にせず `hard_failure` とする contract に明記した。
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

### 2026-05-04 - implementation and review

#### 対象
- Step: S01, S02, S03, S04, RG1, QG1
- AC/EC: AC-001, AC-002, AC-003, EC-001, EC-002, EC-003

#### 実施内容
- `src/pyclassuml/report/__init__.py` と `src/pyclassuml/report/policy.py` を追加し、`ReportInputs`, `ReportRunResult`, `ArtifactNamingDecision`, `ExitPolicyDecision` を public report seam API として export した。
- `decide_artifact_path(...)` で generate / diff の timestamp-based auto naming、relative output の `execution_cwd` 基準解決、absolute output passthrough、suffix collision scan を実装した。
- `build_run_summary(...)` で target / dependency / changed inventory / diagnostics / render counters から deterministic `RunSummary` を合成した。
- `decide_exit_policy(...)` で clean / warning-only / degraded success、strict promoted failure、degraded failure、hard failure の outcome と stream target / exit code を一元化した。
- `write_report(...)` で success 系のみ `.puml` artifact を write し、missing parent directory を作成し、write/create failure を `output_write_failure` hard failure として `stderr_text` に返すようにした。
- `ReportRunResult.stdout_text` / `stderr_text` に summary material を返し、report seam 自身は process stdout/stderr へ直接 emit しない境界を維持した。
- code-reviewer P2 を受け、hard/strict に分類されない upstream error diagnostic も `hard_failure` とし、`RenderFailureSignal` と重なる場合も degraded failure より優先するようにした。
- QA-reviewer P2 を受け、hard failure reason table、non-clean success artifact write、process stream no-emission、RenderFailureSignal diagnostics dedup の regression coverage を追加する。
- final QA-reviewer P2 を受け、strict promoted failure reason table の full coverage を追加した。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest tests/report/test_policy.py tests/model/test_contracts.py tests/render/test_document.py tests/cli/test_bind.py -q
# 69 passed

uv run --with pytest pytest -q
# 233 passed

./spec-dock/scripts/spec-dock validate
# spec-dock: ok (validate) nodes=21

git diff --check
# pass

rg --files | rg '[A-Z]'
# existing allowed AGENTS.md / README.md paths only
```

#### 変更したファイル
- `src/pyclassuml/report/__init__.py` - report seam public API export を追加。
- `src/pyclassuml/report/policy.py` - artifact naming / summary / exit policy / write orchestration を追加。
- `tests/report/test_policy.py` - report seam behavior coverage を追加。
- `spec-dock/active/issue/design.md` - 分類外 error diagnostic の failure contract を追記。
- `spec-dock/active/issue/plan.md` - 分類外 error diagnostic の verification を追記。
- `spec-dock/active/issue/report.md` - implementation / review / validation evidence を記録。

#### レビュー結果
- code-reviewer: pass。P2 として RenderFailureSignal diagnostics の二重集約防止、report stale 記述更新を指摘。
- qa-reviewer: pass。P2 として hard failure reason table、non-clean success artifact write、process stream no-emission の test coverage 補強を指摘。
- final code-reviewer: pass。追加 findings なし。
- final qa-reviewer: pass。P2 として strict promoted failure reason table coverage を指摘し、修正済み。

#### コミット
- docs contract repair: `fc8b6f8 docs(spec-dock): iss-00019の実装契約を具体化`
- implementation: 未作成。P2 補強と最終 validation 後に作成する。

---

## 遭遇した問題と解決 (任意)
- 問題: active docs は `noop` recoverability を要求していたが、現行 shared enum には `noop` が存在しない。
  - 解決: no-op warning の diagnostic code / prose は維持しつつ、classifier は `Recoverability.RECOVERABLE` を operational/no-op warning として扱う contract に修正した。
- 問題: `RenderFailureSignal.diagnostics` は upstream diagnostics を carry し得るため、caller が同じ diagnostics を `ReportInputs.diagnostics` にも渡すと summary と warning count が重複しうる。
  - 解決: report seam の aggregate diagnostics は deterministic に dedup し、同一 diagnostic を一度だけ扱う方針にする。

## 学んだこと (任意)
- report seam は app / cli に十分な stream material を返す必要があるが、実際の stdout/stderr emission は app/cli wiring issue に残す方が責務分離しやすい。

## 今後の推奨事項 (任意)
- downstream `iss-00020` / `iss-00021` では `ReportRunResult.stdout_text` / `stderr_text` を CLI stdout/stderr へ接続し、`CommandResult` を `run_cli` の handler result として返す。

## 省略/例外メモ (必須)
- この issue では app orchestration、console script 登録、PlantUML text generation は実装しない。
