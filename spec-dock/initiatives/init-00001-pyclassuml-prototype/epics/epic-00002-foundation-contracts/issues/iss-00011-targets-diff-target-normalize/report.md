---
種別: 実装報告書（Issue）
ID: "iss-00011"
タイトル: "Targets Diff Target Normalize"
関連GitHub: ["#11"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00002", "init-00001"]
---

# iss-00011 Targets Diff Target Normalize — 実装報告（LOG）

## 実装サマリー
- active issue を `iss-00011-targets-diff-target-normalize` として復元し、`requirement.md` / `design.md` / `plan.md` を実装可能な契約へ整合した。
- `targets.diff` seam に `normalize_diff_targets(ChangedFileCollection, ExecutionContext, AnalysisConfig)` と seam-local `DiffTargetNormalization` を追加し、`vcs` の `ChangedFileCollection` を `TargetSet(seed_files, observations)` と exclusion / failure diagnostics に正規化した。
- generate / diff の ignore 判定を `targets.ignore` に切り出し、`project_root` relative の default / user ignore semantics を共有した。
- Git diff 再実行、explicit target normalize、parse/analyze、render/report、final exit policy は非スコープとして維持する。

## 実装記録（セッションログ）

### 2026-05-04 resume and implementation-readiness repair

#### 対象
- Step: SG1, planning repair
- AC/EC: AC-001, AC-002, AC-003, EC-001, EC-002, EC-003

#### 実施内容
- セッション喪失後の再開として `./spec-dock/scripts/spec-dock active show` を実行し、active issue が `iss-00011` であることを確認した。
- `deps check` で `iss-00011` が ready / blockers=0 であることを確認した。
- `validate` で SpecDock tree が構造的に valid であることを確認した。
- `plan.md` がテンプレート状態だったため、`requirement.md` / `design.md` / `iss-00009` の既存実装計画パターンを参照し、S01/S02/S03/S90/S99 の実行契約へ置き換えた。
- `report.md` がテンプレート状態だったため、再開時点の判断と検証証跡を記録できる issue 固有 report へ置き換えた。

#### 実行コマンド / 結果
```bash
./spec-dock/scripts/spec-dock active show

initiative: init-00001 (spec-dock/initiatives/init-00001-pyclassuml-prototype)
epic: epic-00002 (spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00002-foundation-contracts)
issue: iss-00011 (spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00002-foundation-contracts/issues/iss-00011-targets-diff-target-normalize)
```

```bash
./spec-dock/scripts/spec-dock deps check iss-00011

spec-dock: ok (deps check) target=iss-00011 authority=github effective_status=open source=cache stale=true last_sync_at=2026-04-16T16:09:02Z ready=true blockers=0
```

```bash
./spec-dock/scripts/spec-dock validate

spec-dock: ok (validate) nodes=21
```

#### 変更したファイル
- `spec-dock/active/issue/plan.md` - issue-specific execution contract へ置き換え。
- `spec-dock/active/issue/report.md` - resume / readiness repair evidence を記録。

#### コミット
- 実装・検証差分とまとめて判断する。

#### メモ
- `git status --short --branch` は `## main...origin/main [ahead 10]` で、作業ツリーの未コミット差分はなかった。
- active docs のうち `requirement.md` と `design.md` は issue 固有内容だったが、`plan.md` と `report.md` はテンプレート状態だった。
- `./spec-dock/scripts/spec-dock sync --github` は stale cache 解消のため final gate で実行する。

### 2026-05-04 implementation and verification

#### 対象
- Step: S01, S02, S03, S90, S99
- AC/EC: AC-001, AC-002, AC-003, EC-001, EC-002, EC-003

#### 実施内容
- `src/pyclassuml/targets/diff.py` を追加し、changed files から scope 内 Python seed を構築する `normalize_diff_targets` を実装した。
- scope 外 changed file を `diff_scope_exclusion` warning と `TargetObservations.diff_scope_excluded_count` に carry した。
- default / user ignore、non-Python filtering、duplicate current path dedupe、upstream diagnostics carry を実装した。
- filtering 後 seed 0 件を `diff_zero_target_after_scope_filter` の fatal diagnostic とし、empty `TargetSet` success を返さないようにした。
- `src/pyclassuml/targets/ignore.py` を追加し、`explicit` と `diff` の project-root-relative ignore matcher を共有 helper へ切り出した。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest tests/targets/test_diff_target_normalize.py -q

5 passed in 0.02s
```

```bash
uv run --with pytest pytest tests/targets/test_diff_target_normalize.py tests/targets/test_explicit_target_normalize.py tests/vcs/test_diff_file_collect.py -q

38 passed in 0.90s
```

```bash
uv run --with pytest pytest -q

93 passed in 0.97s
```

```bash
./spec-dock/scripts/spec-dock validate

spec-dock: ok (validate) nodes=21
```

```bash
./spec-dock/scripts/spec-dock sync --github

spec-dock: ok (sync) wrote=spec-dock/.agent/index-all.json,spec-dock/.agent/tree-all.json,spec-dock/.agent/index.json,spec-dock/.agent/tree.json,spec-dock/tree-all.puml,spec-dock/tree.puml,spec-dock/.agent/deps-issues.json,spec-dock/deps-issues.puml,spec-dock/dashboard.md
```

```bash
git diff --check

ok
```

```bash
rg --files | rg '[A-Z]'

AGENTS.md
spec-dock/templates/README.md
spec-dock/scripts/README.md
spec-dock/system/README.md
spec-dock/system/active-none/README.md
spec-dock/system/active-none/initiative/README.md
spec-dock/system/active-none/issue/README.md
spec-dock/system/active-none/epic/README.md
spec-dock/docs/README.md
```

#### 変更したファイル
- `src/pyclassuml/targets/__init__.py` - diff target normalize の public surface を追加。
- `src/pyclassuml/targets/diff.py` - diff target normalization implementation。
- `src/pyclassuml/targets/ignore.py` - generate / diff shared ignore matcher。
- `src/pyclassuml/targets/explicit.py` - shared ignore matcher を利用する behavior-preserving refactor。
- `tests/targets/test_diff_target_normalize.py` - AC/EC と failure diagnostics の unit tests。
- `spec-dock/active/issue/plan.md` - execution contract と refactor target を更新。
- `spec-dock/active/issue/report.md` - validation evidence。

#### レビュー / QA
- Implementation review: self-review pass。scope filtering / diagnostics / failure reason / shared ignore helper の責務分離を確認した。
- QA review: self-review pass。AC/EC coverage、zero-target failure、deterministic ordering、explicit target 回帰、vcs collection 回帰を pytest で確認した。
- QA reviewer pass 1: fail。完了証跡の末尾に古い未完了メモが残り、report 内で完了 / 未完了が自己矛盾していると指摘された。
- QA reviewer finding resolution: 古い未完了メモを削除し、レビュー完了後に最終 reviewer verdict と commit hash をこの report に追記する。
- Implementation review: pass。code-reviewer は AC/EC と `targets.diff` / `targets.ignore` / `targets.explicit` の実装整合を確認し、finding なし。
- QA re-review: pass。QA reviewer は前回 finding 解消、AC/EC coverage、targeted/full pytest、SpecDock validate evidence を確認し、finding なし。

#### コミット
- `b624945 feat(targets): diffターゲット正規化を追加`
- `99cc13f docs(spec-dock): iss-00011の完了証跡を修正`

#### メモ
- `uv` が生成した `uv.lock` は scope 外生成物のため成果差分から除外する。

## 遭遇した問題と解決
- 問題: `plan.md` / `report.md` がテンプレート状態で、workflow_issue の complete 条件を満たせない状態だった。
  - 解決: issue requirement / design に合わせ、実装ステップ、検証、review、docs impact、final exit contract を具体化した。

## 学んだこと
- `iss-00011` は `iss-00010` の Git collection と後続 `app.diff-wiring` の間にあるため、Git 操作や report policy を持ち込まず、`targets.diff` の handoff contract に集中する必要がある。

## 今後の推奨事項
- 実装時は `iss-00009` の ignore matcher と result shape を流用可能か確認しつつ、explicit target の scope violation hard failure と diff target の scope exclusion warning を混同しない。

## 省略/例外メモ
- root `AGENTS.md`、README、SpecDock workflow docs への恒久 docs 変更は不要。変更は issue-scoped docs と targets seam implementation に限定した。
- `uv` が生成した `uv.lock` は scope 外生成物のため成果差分から除外した。
- 現時点の残作業は GitHub issue close、`sync --github` による dashboard の done 反映である。
