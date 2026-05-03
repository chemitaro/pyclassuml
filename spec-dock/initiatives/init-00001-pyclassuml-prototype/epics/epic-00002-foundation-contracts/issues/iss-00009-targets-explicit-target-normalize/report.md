---
種別: 実装報告書（Issue）
ID: "iss-00009"
タイトル: "Targets Explicit Target Normalize"
関連GitHub: ["#9"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-03"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00002", "init-00001"]
---

# iss-00009 Targets Explicit Target Normalize — 実装報告（LOG）

## 実装サマリー
- `targets` seam に `normalize_explicit_targets(CommandRequest, ExecutionContext, AnalysisConfig)` と seam-local `TargetNormalization` を追加し、`generate` の explicit file / glob / dir input を `TargetSet(seed_files, observations)` へ正規化した。
- `execution_cwd` 基準の input 解決、`project_root` 相対 ignore、scope validation precedence、zero-seed failure、diagnostic shape を pytest で固定した。
- Git diff read、dependency traversal、parse/analyze、class selection、output / exit logic は非スコープとして実装していない。

## 実装記録（セッションログ）

### 2026-05-03 implementation-readiness review

#### 対象
- Step: SG1
- AC/EC: AC-001, AC-002, AC-003, AC-004, EC-001, EC-002, EC-003, EC-004

#### 実施内容
- `design.md` に `TargetNormalization` result、explicit input rules、ignore rules、scope / zero-seed failure rules、file plan を追記した。
- `plan.md` に S01/S02/S03/S90/S99、test expectations、review/QA gate、final exit contract を具体化した。
- spec-reviewer で fail -> repair -> fail -> repair -> pass を実施した。scope validation は existing file / directory / glob expansion result に対して Python filtering / ignore / zero-seed より前に行う契約へ固定した。

#### 実行コマンド / 結果
```bash
./spec-dock/scripts/spec-dock validate

spec-dock: ok (validate) nodes=21
```

#### 変更したファイル
- `spec-dock/active/issue/design.md` - targets seam contract と precedence を具体化。
- `spec-dock/active/issue/plan.md` - implementation steps と final gates を具体化。

#### コミット
- 実装・検証差分とまとめて commit。

#### メモ
- spec-reviewer final verdict: pass。

### 2026-05-03 implementation and verification

#### 対象
- Step: S01, S02, S03, S90, S99
- AC/EC: AC-001, AC-002, AC-003, AC-004, EC-001, EC-002, EC-003, EC-004

#### 実施内容
- `src/pyclassuml/targets/__init__.py` と `src/pyclassuml/targets/explicit.py` を追加した。
- file / glob / dir expansion、dedupe、absolute path ordering、`.py` filtering、`__init__.py` inclusion を実装した。
- default ignore と user ignore を `project_root` relative に適用し、`*` は path segment 内、`**` は directory 横断として扱う segment-aware matcher を実装した。
- scope outside と zero-seed を `TargetNormalization(target_set=None, diagnostics=...)` として返し、empty `TargetSet` success を禁止した。
- code-reviewer は最終 pass、qa-reviewer は最終 pass。非ブロッキング coverage 指摘は追加テストで解消した。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest tests/targets/test_explicit_target_normalize.py -q

20 passed in 0.04s
```

```bash
uv run --with pytest pytest -q

75 passed in 0.17s
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
- `src/pyclassuml/targets/__init__.py` - targets seam public surface。
- `src/pyclassuml/targets/explicit.py` - explicit target normalization implementation。
- `tests/targets/test_explicit_target_normalize.py` - AC/EC と failure diagnostics の unit tests。
- `spec-dock/active/issue/design.md` - implementation design update。
- `spec-dock/active/issue/plan.md` - execution/test/review plan update。
- `spec-dock/active/issue/report.md` - validation evidence。

#### コミット
- 実施予定。

#### メモ
- `uv` が生成した `uv.lock` は scope 外生成物のため削除した。
- pytest の `__pycache__` は削除した。

## 遭遇した問題と解決
- 問題: scope outside と ignore / Python filtering / zero-seed の precedence が曖昧だった。
  - 解決: existing file / directory と glob expansion result は、Python filtering / ignore / zero-seed より前に scope validation する契約へ固定した。
- 問題: `fnmatch` は `/` を path separator として扱わず、`pkg/*.py` が `pkg/nested/mod.py` に一致しうる。
  - 解決: path segment aware matcher を実装し、`*` は segment 内、`**` は directory 横断として扱うようにした。

## 学んだこと
- targets seam では missing path / glob miss と scope outside を明確に分けないと、zero-seed と scope violation の診断が不安定になる。
- ignore は `execution_cwd` ではなく `project_root` relative で固定し、path separator semantics までテストで守る必要がある。

## 今後の推奨事項
- `iss-00011` の diff target normalize では、scope outside が warn / strict で扱い分けられるため、今回の explicit target と同じ matcher を再利用するか shared helper 化を検討する。

## 省略/例外メモ
- root `AGENTS.md`、README、SpecDock workflow docs への恒久 docs 変更は不要。変更は issue-scoped docs に限定した。
