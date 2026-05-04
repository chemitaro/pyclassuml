---
種別: 実装報告書（Issue）
ID: "iss-00020"
タイトル: "App Generate Wiring"
関連GitHub: ["#20"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00005", "init-00001"]
---

# iss-00020 App Generate Wiring — 実装報告（LOG）

## 実装サマリー (任意)
- `src/pyclassuml/app/` に `run_generate(...) -> ReportRunResult` を追加し、generate の canonical pipeline を `report.write_report(...)` まで接続した。
- actual CLI stream emission / console script / diff wiring は非スコープに残した。

## 実装記録（セッションログ） (必須)

### 2026-05-04 - contract repair

#### 対象
- Step: SG1
- AC/EC: AC-001, AC-002, AC-003, EC-001, EC-002, EC-003

#### 実施内容
- spec-manager により `iss-00020` を active 化し、`spec-dock validate` が pass すること、worktree が clean であることを確認した。
- `requirement.md` / `design.md` / `plan.md` / `report.md` を確認し、`plan.md` と `report.md` がテンプレートのままで実装開始に不足していることを確認した。
- 現行 `cli.run_cli` は handler から `CommandResult` だけを受け取る一方、`report.write_report(...)` は `ReportRunResult(command_result, stdout_text, stderr_text)` を返すことを確認した。
- この issue の scope を app seam の `ReportRunResult` 返却に補正し、actual process stdout / stderr emission と `cli.run_cli` handler signature 変更は非スコープに明記した。
- config failure では `ExecutionContext` / `AnalysisConfig` が得られないため、report invocation 用の fallback context/default config を app が最小構築する contract を design に追加した。
- explicit target normalization failure、render failure、output write failure は app が再分類せず `write_report(...)` に handoff する contract にした。
- `plan.md` を S01-S04 / SG1 / RG1 / QG1 / S90 / S99 まで具体化し、実装可能な execution contract に修復した。
- spec-reviewer fail を受け、issue design に残っていた stale な `CommandResult` app-output 表現を `ReportRunResult` に修正した。
- spec-reviewer fail を受け、epic design の seam contract table / flow / sequence / partial failure / unit test 観点も `ReportRunResult` boundary に揃えた。
- spec-reviewer re-review は pass。P2 として EC-003 に残っていた direct `CommandResult` 表現を指摘されたため、`ReportRunResult.command_result` の non-zero outcome を保持する表現へ補正した。

#### 実行コマンド / 結果
```bash
./spec-dock/scripts/spec-dock active set iss-00020
# spec-dock: ok (active set) target=iss-00020 initiative=init-00001 epic=epic-00005 issue=iss-00020

./spec-dock/scripts/spec-dock active show
# issue: iss-00020

./spec-dock/scripts/spec-dock validate
# spec-dock: ok (validate) nodes=21

git status --short
# clean

rg --files src tests | sort
# app package は未実装。config/targets/parse/analyze/frameworks/render/report/cli seams は存在。

git diff --check
# pass
```

#### 変更したファイル
- `spec-dock/active/issue/requirement.md` - `ReportRunResult` boundary と non-scope を明確化。
- `spec-dock/active/issue/design.md` - fallback failure handoff と stream material boundary を明確化。
- `spec-dock/active/issue/plan.md` - execution contract を具体化。
- `spec-dock/active/issue/report.md` - contract repair の判断と証跡を記録。
- `spec-dock/active/epic/design.md` - app generate/diff seam output を `ReportRunResult` boundary に補正。

#### コミット
- `6885aa3 docs(spec-dock): iss-00020の実装契約を具体化`

#### メモ
- `ReportRunResult.stdout_text` / `stderr_text` はこの issue の observation であり、actual stdout/stderr emission は downstream integration として残す。
- `app` は stage invocation order と transport owner に限定し、summary / exit policy / render / analysis policy を再実装しない。

---

### 2026-05-04 - implementation and review

#### 対象
- Step: S01, S02, S03, S04, RG1, QG1, S99
- AC/EC: AC-001, AC-002, AC-003, EC-001, EC-002, EC-003

#### 実施内容
- `src/pyclassuml/app/__init__.py` と `src/pyclassuml/app/generate.py` を追加し、`run_generate(request, *, timestamp) -> ReportRunResult` を public app seam API として export した。
- non-generate `CommandRequest` は `ValueError` とし、app seam では usage error result を作らない guard を追加した。
- generate happy path を `config -> targets.explicit -> parse -> traversal -> selection -> changed inventory -> sqlalchemy -> pydantic -> render -> report` の canonical order で接続した。
- generate path の changed-file context は `()` として `build_changed_class_inventory(...)` に渡し、zero `ChangedClassInventory` を analyze owner のまま report へ transport した。
- `TargetSet.observations`、`DependencyGraph`、`ChangedClassInventory`、`scope_stop_count`、stage diagnostics、render success/failure DTO を `ReportInputs` へ渡すようにした。
- config failure と target normalization failure は downstream stages を呼ばず、diagnostics を `write_report(...)` に渡して report-owned non-zero `ReportRunResult` を返すようにした。
- render failure と output write failure は app が再分類せず、`write_report(...)` の result をそのまま返すようにした。
- app は actual process stdout/stderr へ write せず、`ReportRunResult.stdout_text` / `stderr_text` を返す境界を維持した。
- QA fail を受け、zero inventory handoff を `build_changed_class_inventory` / `write_report` spy で直接固定した。
- QA P2/P3 を受け、timestamp passthrough、non-clean branch の process stream no-emission、`scope_stop_count` handoff を tests で固定した。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest tests/app/test_generate.py tests/report/test_policy.py tests/model/test_contracts.py tests/render/test_document.py tests/cli/test_bind.py -q
# 79 passed

uv run --with pytest pytest -q
# 243 passed

./spec-dock/scripts/spec-dock validate
# spec-dock: ok (validate) nodes=21

git diff --check
# pass

rg --files | rg '[A-Z]'
# existing allowed AGENTS.md / README.md paths only

find . \( -name '__pycache__' -o -name '*.pyc' -o -name 'uv.lock' \) -print
# no output after cleanup
```

#### 変更したファイル
- `src/pyclassuml/app/__init__.py` - app seam public API export を追加。
- `src/pyclassuml/app/generate.py` - generate pipeline wiring を追加。
- `tests/app/test_generate.py` - generate app seam の happy / failure / transport / no-emission coverage を追加。
- `spec-dock/active/issue/report.md` - implementation / validation / review evidence を記録。

#### レビュー結果
- code-reviewer: pass。追加 findings なし。
- qa-reviewer: fail -> fix -> pass。P1 zero inventory handoff coverage、P2 timestamp / scope-stop handoff、P3 non-clean stream no-emission を補強済み。

#### コミット
- 未作成。report 更新後に実装コミットを作成する。

---

## 遭遇した問題と解決 (任意)
- 問題: active docs は stdout summary を要求していたが、現行 `cli.run_cli` は stdout material を扱わず、`report` が `ReportRunResult.stdout_text` を返す構造になっている。
  - 解決: `iss-00020` の観測点を `ReportRunResult.stdout_text` に補正し、actual process stream emission は非スコープとして残した。
- 問題: config failure path では report に渡す `ExecutionContext` / `AnalysisConfig` が通常 seam から得られない。
  - 解決: app が fallback context/default config を最小構築し、diagnostics とともに `write_report(...)` へ渡して report-owned hard failure result を得る contract にした。
- 問題: summary の `changed_class_count: 0` は `ChangedClassInventory` 未指定でも出せるため、AC-002 の transport 契約が summary 文字列だけでは守れない。
  - 解決: `build_changed_class_inventory((), ...)` と `ReportInputs.changed_class_inventory` を spy test で直接固定した。

## 学んだこと (任意)
- app seam を thin stitcher に保つには、failure path でも `CommandResult` を app が直接作らず、report invocation のための最小入力だけを準備する必要がある。

## 今後の推奨事項 (任意)
- downstream CLI integration では `ReportRunResult.stdout_text` / `stderr_text` を actual process streams へ接続し、`command_result.exit_code` を process exit code へ伝播させる。
- `iss-00021` では `iss-00020` の common pipeline helper を再利用し、front-stage diff-specific work だけを追加する。

## 省略/例外メモ (必須)
- この issue では diff wiring、console script 登録、actual stdout/stderr emission、`cli.run_cli` handler signature 変更は実装しない。
