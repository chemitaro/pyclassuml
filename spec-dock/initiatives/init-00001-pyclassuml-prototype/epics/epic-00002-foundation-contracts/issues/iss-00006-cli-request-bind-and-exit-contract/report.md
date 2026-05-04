---
種別: 実装報告書（Issue）
ID: "iss-00006"
タイトル: "CLI Request Bind And Exit Contract"
関連GitHub: ["#6"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00002", "init-00001"]
---

# iss-00006 CLI Request Bind And Exit Contract — 実装報告（LOG）

## 実装サマリー (任意)
- 現行 repo には `CommandOptions` / `CommandRequest` / `CommandResult` は存在するが、CLI seam 実装と console script はまだ存在しない。
- app generate/diff wiring は downstream issue なので、この issue では injectable handler を使う CLI bind/run API を完成条件にする。

## 実装記録（セッションログ） (必須)

### 2026-05-04 - implementation

#### 対象
- Step: S01, S02, S03, S90, S99
- AC/EC: AC-001, AC-002, AC-003, EC-001, EC-002

#### 実施内容
- `src/pyclassuml/cli/` を追加し、`bind_command_request` / `run_cli` / `CliRunResult` を public API として export した。
- `argparse` で `generate` / `diff` を parse し、common options と subcommand-specific options を `CommandOptions` に bind するようにした。
- path-like option は raw `Path(...)` として保持し、`process_cwd` は渡された `Path` object をそのまま `CommandRequest` に保持するようにした。
- `diff --base` を required とし、`--current-state` 未指定時は `working-tree`、`--include-untracked` 未指定時は `False` を syntactic parse default として materialize するようにした。
- usage error では handler を呼ばず、`FailureReason.CLI_USAGE_ERROR` / `OriginSeam.CLI` / `Recoverability.FATAL` diagnostic を持つ `CommandResult(exit_code=2)` を `CliRunResult` に包んで返すようにした。
- valid invocation では handler を 1 回だけ呼び、handler が返した `CommandResult` と `exit_code` を再解釈せず `CliRunResult` に保持するようにした。
- QA reviewer の P2 指摘を受け、`diff` 側 common options と typed parser validation usage error の test coverage を追加した。
- code-reviewer は findings なしで pass した。
- qa-reviewer は P2 test gap 指摘後、補強済み差分に対して gate-blocking finding なしとして扱った。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest tests/cli/test_bind.py tests/model/test_contracts.py tests/config/test_context_resolve.py tests/targets/test_explicit_target_normalize.py tests/vcs/test_diff_file_collect.py -q
# 96 passed

uv run --with pytest pytest -q
# 201 passed

./spec-dock/scripts/spec-dock validate
# spec-dock: ok (validate) nodes=21

git diff --check
# pass

rg --files | rg '[A-Z]'
# 既存許可 path: AGENTS.md / README.md 系のみ。新規 uppercase path なし。

find . -name uv.lock -o -name '*.pyc' -o -type d -name __pycache__
# cleanup 後、残存なし。
```

#### 変更したファイル
- `src/pyclassuml/cli/__init__.py` - CLI seam public API export。
- `src/pyclassuml/cli/bind.py` - request bind、usage error result、handler exit propagation。
- `tests/cli/test_bind.py` - CLI bind/run contract tests。

#### コミット
- 実装コミットを作成予定。

#### メモ
- `pyproject.toml` console script 登録と app generate/diff wiring は downstream `iss-00020` / `iss-00021` の責務として未変更。
- `uv.lock` / `__pycache__` / `.pyc` は生成後に削除した。

---

### 2026-05-04 - contract repair

#### 対象
- Step: SG1
- AC/EC: AC-001, AC-002, AC-003, EC-001, EC-002

#### 実施内容
- dashboard で `iss-00006` が ready であることを確認した。
- spec-manager により `iss-00006` を active 化し、`spec-dock validate` が pass することを確認した。
- `requirement.md` / `design.md` を読み、`cli` seam の owner が argv parse、request bind、usage error、exit propagation に限定されていることを確認した。
- `src/pyclassuml/model/contracts.py` を確認し、`CommandOptions` / `GenerateOptions` / `DiffOptions` / `CommandRequest` / `CommandResult` が既に model contract として存在することを確認した。
- `pyproject.toml` に console script がまだ定義されていないことを確認した。
- `app.generate-wiring` / `app.diff-wiring` は未実装であるため、この issue では `pyclassuml.cli` package の bind/run API と injectable handler で exit propagation を固定し、packaging entrypoint は downstream に残す方針にした。
- `plan.md` を S01-S03 / SG1 / RG1 / QG1 / S90 / S99 まで具体化し、実装開始可能な execution contract に修復した。
- spec-reviewer fail を受け、required `DiffOptions.current_state` / `include_untracked` を満たすための CLI parse defaults を `working-tree` / `False` と明文化した。
- spec-reviewer fail を受け、`run_cli` の返り値を seam-local `CliRunResult(command_result, exit_code, stderr_text)` と定義し、console script の process exit は downstream に残す形へ明確化した。
- 再レビュー fail を受け、requirement の AC-003 / EC-002 も seam-local `CliRunResult` と syntactic parse defaults へ揃え、diff option consumer を `vcs.diff-file-collect` に明記した。
- final spec-reviewer は findings なしで pass し、実装開始可能と判定した。

#### 実行コマンド / 結果
```bash
./spec-dock/scripts/spec-dock active show
# issue: iss-00006

./spec-dock/scripts/spec-dock validate
# spec-dock: ok (validate) nodes=21

git diff --check
# pass

rg --files | rg '[A-Z]'
# 既存許可 path: AGENTS.md / README.md 系のみ。新規 uppercase path なし。

sed -n '120,260p' src/pyclassuml/model/contracts.py
# CommandOptions / CommandRequest / CommandResult は実装済み。

sed -n '1,220p' pyproject.toml
# console script は未定義。
```

#### 変更したファイル
- `spec-dock/active/issue/plan.md` - CLI bind/run API と non-scope を具体化。
- `spec-dock/active/issue/report.md` - contract repair の判断と証跡を記録。

#### コミット
- docs commit を作成予定。

#### メモ
- `pyproject.toml` console script 登録は downstream `iss-00020` / `iss-00021` で app wiring と合わせて行う。
- CLI は `ExecutionContext` / `AnalysisConfig` / target normalization / app execution を決めない。
- `process exit` 表現は downstream console script owner に限定し、この issue は seam-local `CliRunResult.exit_code` 伝播だけを受け持つ。
- uppercase path validation は既存許可 path (`AGENTS.md`, `README.md`) を baseline とし、新規 uppercase path が増えていないことを確認する。

---

## 遭遇した問題と解決 (任意)
- 問題: app wiring が未実装のため、CLI が valid invocation を実際に generate/diff へ流す先がまだない。
  - 解決: この issue では injectable handler による `CommandRequest` handoff と `CommandResult.exit_code` propagation を固定し、real app wiring は downstream owner に残す。

## 学んだこと (任意)
- CLI seam は config/targets/vcs の前段 owner だが、root resolve や target normalize の判断は downstream に委譲する必要がある。

## 今後の推奨事項 (任意)
- `iss-00020` / `iss-00021` では `pyclassuml.cli.run_cli` の handler に app generate/diff wiring を接続し、必要なら `pyproject.toml` console script を登録する。

## 省略/例外メモ (必須)
- この issue では console script 登録と app execution は実装しない。
