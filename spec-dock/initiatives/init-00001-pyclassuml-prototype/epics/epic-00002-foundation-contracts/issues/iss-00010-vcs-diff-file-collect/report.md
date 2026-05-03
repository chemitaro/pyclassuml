---
種別: 実装報告書（Issue）
ID: "iss-00010"
タイトル: "VCS Diff File Collect"
関連GitHub: ["#10"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-03"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00002", "init-00001"]
---

# iss-00010 VCS Diff File Collect — 実装報告（LOG）

## 実装サマリー
- `vcs` seam に `collect_diff_files(CommandRequest, ExecutionContext, AnalysisConfig)` と seam-local `VcsDiffCollection` / `ChangedFileCollection` / `ChangedFileEntry` を追加し、Git diff から raw changed files を read-only に収集できるようにした。
- working-tree / head、untracked on/off、rename/delete normalization、nested `project_root`、invalid base、Git read/parse failure、head+untracked no-op warning を pytest で固定した。
- scope filtering、`TargetSet` 生成、summary / exit policy、parse/analyze は非スコープとして実装していない。

## 実装記録（セッションログ）

### 2026-05-03 implementation-readiness review

#### 対象
- Step: SG1
- AC/EC: AC-001, AC-002, AC-003, EC-001, EC-002

#### 実施内容
- `design.md` に `VcsDiffCollection` result、Git command contract、NUL-delimited path parsing、diagnostic code contract、file plan を追記した。
- `plan.md` に S01/S02/S03/S90/S99、test expectations、review/QA gate、final exit contract を具体化した。
- spec-reviewer で fail -> repair -> pass を実施した。AC-001 は S01+S02 で閉じる形に修正し、NUL-delimited output、canonical diagnostics、EC-001 no-untracked case を明示した。

#### 実行コマンド / 結果
```bash
./spec-dock/scripts/spec-dock validate

spec-dock: ok (validate) nodes=21
```

#### 変更したファイル
- `spec-dock/active/issue/design.md` - Git command contract と seam-local DTO contract を具体化。
- `spec-dock/active/issue/plan.md` - implementation steps と final gates を具体化。

#### コミット
- 実装・検証差分とまとめて commit。

#### メモ
- spec-reviewer final verdict: pass。

### 2026-05-03 implementation and verification

#### 対象
- Step: S01, S02, S03, S90, S99
- AC/EC: AC-001, AC-002, AC-003, EC-001, EC-002

#### 実施内容
- `src/pyclassuml/vcs/__init__.py` と `src/pyclassuml/vcs/diff_collect.py` を追加した。
- `git diff --name-status -z --find-renames --relative ... -- .` と `git ls-files -z --others --exclude-standard -- .` を使い、`project_root` relative の changed file collection を実装した。
- working-tree / head matrix、untracked include/exclude、head+untracked no-op warning、rename current-side entry、delete-only exclusion、nested project-root boundary を実装した。
- invalid base、non-Git / command failure、unsupported status、UTF-8 decode failure を `vcs_read_failure` diagnostics として返すよう実装した。
- code-reviewer は最終 pass、qa-reviewer は最終 pass。非ブロッキング P2 は追加実装・テストで解消した。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest tests/vcs/test_diff_file_collect.py -q

13 passed in 1.21s
```

```bash
uv run --with pytest pytest -q

88 passed in 1.40s
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
spec-dock/docs/README.md
spec-dock/system/active-none/README.md
spec-dock/system/active-none/initiative/README.md
spec-dock/system/active-none/epic/README.md
spec-dock/system/active-none/issue/README.md
```

#### 変更したファイル
- `src/pyclassuml/vcs/__init__.py` - vcs seam public surface。
- `src/pyclassuml/vcs/diff_collect.py` - Git changed-file collection implementation。
- `tests/vcs/test_diff_file_collect.py` - AC/EC と failure diagnostics の unit tests。
- `spec-dock/active/issue/design.md` - implementation design update。
- `spec-dock/active/issue/plan.md` - execution/test/review plan update。
- `spec-dock/active/issue/report.md` - validation evidence。

#### コミット
- 実施予定。

#### メモ
- `uv.lock` と pytest `__pycache__` は scope 外生成物のため削除した。

## 遭遇した問題と解決
- 問題: Git path output の encoding / delimiter が未固定で、rename や特殊 path の parsing が曖昧だった。
  - 解決: `-z` を使う NUL-delimited output に固定し、UTF-8 decode failure を `git_diff_parse_failure` とした。
- 問題: `project_root` が worktree root 配下の subdir の場合、変更 path basis が `project_root` relative にならない可能性があった。
  - 解決: `--relative` と pathspec `-- .` で `project_root` 配下へ制約し、nested project-root test を追加した。

## 学んだこと
- `git -C <project_root>` だけでは monorepo の path basis 契約として不十分で、`--relative` / pathspec まで固定する必要がある。
- success path の diagnostics は明示的に空であることをテストしないと、後続 seam の warning/error handling が濁る。

## 今後の推奨事項
- `iss-00011` では `ChangedFileCollection` を入力にして scope filtering / zero-target fail を実装し、`vcs` には scope semantics を逆流させない。

## 省略/例外メモ
- root `AGENTS.md`、README、SpecDock workflow docs への恒久 docs 変更は不要。変更は issue-scoped docs に限定した。
