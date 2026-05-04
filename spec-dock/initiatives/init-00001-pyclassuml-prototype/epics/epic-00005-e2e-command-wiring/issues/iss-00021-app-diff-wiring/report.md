---
種別: 実装報告書（Issue）
ID: "iss-00021"
タイトル: "App Diff Wiring"
関連GitHub: ["#21"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00005", "init-00001"]
---

# iss-00021 App Diff Wiring — 実装報告（LOG）

## 実装サマリー
- 実装前 contract repair として、issue requirement/design/plan を `ReportRunResult` app seam 境界へ更新した。
- `CommandResult` direct-output 前提とテンプレ plan を削除し、diff-specific front-stage、common pipeline、report-owned result material の責務分離を明文化した。
- 実装レビューの P2 を受け、zero-target failure 時にも `DiffTargetNormalization.observations` を report counter に保持する contract を追記した。

## 実装記録（セッションログ）

### 2026-05-04 contract repair

#### 対象
- Step: M1 / SG1
- AC/EC: AC-001, AC-002, AC-003, AC-004, EC-001, EC-002, EC-003

#### 実施内容
- active issue が `iss-00021 App Diff Wiring` であることを確認した。
- requirement/design の stale な `CommandResult` direct-output 契約を `ReportRunResult` 境界へ修正した。
- plan のテンプレートを、public seam、front-stage failure、canonical happy path、warning/counter/failure preservation の実行契約へ置き換えた。
- report を実作業ログ形式へ初期化した。
- spec review fail を受け、`ReportRunResult` の top-level shape と `ChangedClassInventory` へ渡す project-root-relative path 契約を修正した。
- code review P2 を受け、`TargetSet` が生成されない zero-target failure でも `DiffTargetNormalization.observations` を `write_report` へ渡す contract を追記した。

#### 実行コマンド / 結果
```bash
git status --short

# no output

./spec-dock/scripts/spec-dock active show

initiative: init-00001 (spec-dock/initiatives/init-00001-pyclassuml-prototype)
epic: epic-00005 (spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00005-e2e-command-wiring)
issue: iss-00021 (spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00005-e2e-command-wiring/issues/iss-00021-app-diff-wiring)
```

#### 変更したファイル
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00005-e2e-command-wiring/issues/iss-00021-app-diff-wiring/requirement.md` - `ReportRunResult` 境界と AC/EC を具体化。
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00005-e2e-command-wiring/issues/iss-00021-app-diff-wiring/design.md` - diff app seam の flow / handoff / failure 設計を具体化。
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00005-e2e-command-wiring/issues/iss-00021-app-diff-wiring/plan.md` - 実装可能な execution contract へ置換。
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00005-e2e-command-wiring/issues/iss-00021-app-diff-wiring/report.md` - 作業ログを初期化。

#### コミット
- `db5f2bf docs(spec-dock): iss-00021の実装契約を具体化`

#### メモ
- `generate` wiring と同様に、`cli.run_cli` の handler 接続や実プロセス stream emission は本 issue の非スコープにした。
- zero-target failure で counter を保持するために report counter transport 用の empty `TargetSet` は許容するが、parse seed としての fallback seed は作らない。

### 2026-05-04 implementation / review / final gate

#### 対象
- Step: S01, S02, S03, S04, S90, S99
- AC/EC: AC-001, AC-002, AC-003, AC-004, EC-001, EC-002, EC-003

#### 実施内容
- `run_diff(request, *, timestamp) -> ReportRunResult` を `app` public seam として追加した。
- config failure、VCS failure、target zero failure は downstream common pipeline へ進まず `write_report` へ委譲するようにした。
- happy path は `config -> vcs -> targets.diff -> parse -> traversal -> selection -> ChangedClassInventory -> frameworks -> render -> report` の順で接続した。
- changed-file context は `ChangedFileCollection.entries[].current_project_relative_path` から project-root-relative `Path` を作り、`build_changed_class_inventory` へ渡すようにした。
- `DiffTargetNormalization.observations` を追加し、zero-target failure 時も `diff_scope_excluded_count` / ignored counter を report summary に保持した。
- app-level tests で canonical order、working-tree `include_untracked=true/false`、HEAD no-op warning、invalid base ref、VCS/config/target/output/render failure、process stream non-emission を固定した。
- code-reviewer と qa-reviewer を fail -> fix -> pass まで回した。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest tests/app/test_diff.py tests/app/test_generate.py tests/report/test_policy.py tests/model/test_contracts.py tests/render/test_document.py tests/cli/test_bind.py tests/vcs/test_diff_file_collect.py tests/targets/test_diff_target_normalize.py -q

116 passed

uv run --with pytest pytest -q

262 passed

./spec-dock/scripts/spec-dock validate

spec-dock: ok (validate) nodes=21

git diff --check

# no output

rg --files | rg '[A-Z]'

AGENTS.md
spec-dock/templates/README.md
spec-dock/scripts/README.md
spec-dock/system/README.md
spec-dock/system/active-none/initiative/README.md
spec-dock/system/active-none/issue/README.md
spec-dock/system/active-none/epic/README.md
spec-dock/system/active-none/README.md
spec-dock/docs/README.md

find . \( -name '__pycache__' -o -name '*.pyc' -o -name 'uv.lock' \) -print

# no output after cleanup
```

#### 変更したファイル
- `src/pyclassuml/app/diff.py` - `run_diff` app seam と diff pipeline wiring を追加。
- `src/pyclassuml/app/__init__.py` - `run_diff` を public app surface に export。
- `src/pyclassuml/targets/diff.py` - `DiffTargetNormalization.observations` を constructor 互換を保って追加。
- `tests/app/test_diff.py` - diff app wiring の AC/EC coverage を追加。
- `tests/targets/test_diff_target_normalize.py` - observations transport と constructor compatibility を追加。
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00005-e2e-command-wiring/issues/iss-00021-app-diff-wiring/design.md` - zero-target observations handoff を追記。
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00005-e2e-command-wiring/issues/iss-00021-app-diff-wiring/plan.md` - failure observations transport を execution contract に反映。
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00005-e2e-command-wiring/issues/iss-00021-app-diff-wiring/report.md` - 実装・レビュー・検証結果を記録。

#### コミット
- 未実施。final diff 確認後に実装 commit を作成する。

#### メモ
- code-reviewer final: pass。blocking findings なし。
- qa-reviewer final: pass。residual risk は actual CLI process wiring のみで、本 issue では out of scope。
- `DiffTargetNormalization` は exported dataclass の既存 constructor shape を保つため、`observations` を default 付きで `diagnostics` の後ろに置いた。

## 遭遇した問題と解決
- 問題: 既存 docs が `CommandResult` direct-output とテンプレ plan のままで、`iss-00019` / `iss-00020` の `ReportRunResult` 境界と衝突していた。
  - 解決: issue docs を current report seam contract に合わせて修復し、実装前 review gate を置いた。
- 問題: 初回 QA で canonical post-target order、failure branch の process stream capture、working-tree untracked coverage が不足していた。
  - 解決: app-level spy test と `include_untracked=true/false` fixture、failure branch capsys assertion を追加した。
- 問題: 初回 code review で zero-target failure 時の `diff_scope_excluded_count` が summary に残らない可能性を指摘された。
  - 解決: `DiffTargetNormalization.observations` を追加し、report counter transport 用の empty `TargetSet` で summary に保持した。
- 問題: `DiffTargetNormalization` の field 追加で exported constructor compatibility を壊すリスクがあった。
  - 解決: `observations` を default 付きで `diagnostics` の後ろに置き、互換 test を追加した。

## 学んだこと
- diff wiring は generate wiring より front-stage failure が多いため、config / VCS / target failure を common pipeline の手前で `write_report` に渡す契約を明示する必要がある。

## 今後の推奨事項
- 実装では `run_generate` と過度に divergent な後段 pipeline を作らない。必要なら小さな内部 helper 化を検討するが、issue scope を超える大規模 refactor は避ける。
- 次 issue で `cli.run_cli` が app seam を呼ぶ際は、`ReportRunResult.stdout_text` / `stderr_text` の実プロセス emission を CLI owner として接続する。

## 省略/例外メモ
- 該当なし。
