---
種別: 実装報告書（Issue）
ID: "iss-00008"
タイトル: "Config Context Resolve"
関連GitHub: ["#8"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-03"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00002", "init-00001"]
---

# iss-00008 Config Context Resolve — 実装報告（LOG）

## 実装サマリー
- `config` seam に `resolve_context(CommandRequest)` と seam-local `ConfigResolution` を追加し、`execution_cwd`, `project_root`, `package_root`, `scope_root`, `AnalysisConfig` の discovery / merge / validation を実装した。
- `.pyclassuml.toml` の schema validation、`relative_path_base`、diff 設定、root containment、path resolution failure、canonical diagnostic handoff を pytest で固定した。
- `target selection`, Git read, parse/analyze, output write, exit routing は非スコープとして実装していない。

## 実装記録（セッションログ）

### 2026-05-03 implementation-readiness review

#### 対象
- Step: SG1
- AC/EC: AC-001, AC-002, AC-003, AC-004, EC-001, EC-002, EC-003

#### 実施内容
- `requirement.md` / `design.md` / `plan.md` を、schema / discovery / merge / failure taxonomy / file plan が実装可能な契約になるよう更新した。
- `AnalysisConfig.mode` は `strict=True` だけが config `mode` より優先し、`strict=False` は config を override しない契約に固定した。
- `CommandOptions` DTO が CLI scalar shape を守り、`config` seam が config-file scalar validation と path/context failure を扱うよう、issue docs を `iss-00007` の model contract と整合させた。
- spec-reviewer は fail -> repair -> fail -> repair -> pass。最終 pass 後の P2 は plan に反映した。

#### 実行コマンド / 結果
```bash
./spec-dock/scripts/spec-dock validate

spec-dock: ok (validate) nodes=21
```

#### 変更したファイル
- `spec-dock/active/issue/requirement.md` - scope / failure taxonomy / DTO boundary を具体化。
- `spec-dock/active/issue/design.md` - config seam contract、TOML schema、merge/path rules、file plan を具体化。
- `spec-dock/active/issue/plan.md` - S01/S02/S03/S90/S99、test expectations、review gates を具体化。

#### コミット
- 実装・検証差分とまとめて commit。

#### メモ
- spec-reviewer final verdict: pass。

### 2026-05-03 implementation and verification

#### 対象
- Step: S01, S02, S03, S90, S99
- AC/EC: AC-001, AC-002, AC-003, AC-004, EC-001, EC-002, EC-003

#### 実施内容
- `src/pyclassuml/config/__init__.py` と `src/pyclassuml/config/resolver.py` を追加した。
- config file 不在時の default success、`--cwd` resolve、explicit `--config`、project-root 優先 discovery、parent-search fallback、config-file-dir fallback、`relative_path_base=cwd` を実装した。
- CLI / config / default merge、`ignore`, `output`, `depth`, `mode`, `target_python`, `[diff]` / dotted diff keys を実装した。
- invalid TOML、missing explicit config、unknown keys、schema values、unresolved roots、cwd/path resolution errors、root/scope containment を failure diagnostic として返すよう実装した。
- code-reviewer は最終 pass、qa-reviewer は最終 pass。非ブロッキング coverage 指摘は追加テストで解消した。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest tests/config/test_context_resolve.py -q

38 passed in 0.04s
```

```bash
uv run --with pytest pytest -q

55 passed in 0.08s
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
spec-dock/system/active-none/initiative/README.md
spec-dock/system/active-none/issue/README.md
spec-dock/system/active-none/epic/README.md
spec-dock/system/active-none/README.md
spec-dock/docs/README.md
```

#### 変更したファイル
- `src/pyclassuml/config/__init__.py` - config seam public surface。
- `src/pyclassuml/config/resolver.py` - context/config resolution implementation。
- `tests/config/test_context_resolve.py` - AC/EC と failure diagnostics の unit tests。
- `spec-dock/active/issue/requirement.md` - implementation contract update。
- `spec-dock/active/issue/design.md` - implementation design update。
- `spec-dock/active/issue/plan.md` - execution/test/review plan update。
- `spec-dock/active/issue/report.md` - validation evidence。

#### コミット
- 実施予定。

#### メモ
- `uv` が生成した `uv.lock` は scope 外生成物のため削除した。
- `.venv/` は ignored の作業環境として残っている。

## 遭遇した問題と解決
- 問題: 実装前 review で `strict` と config `mode` の precedence が衝突していた。
  - 解決: `strict=True` のみ CLI override とし、`strict=False` は config `mode` を override しない契約に修正した。
- 問題: QA review で invalid CLI scalar を config seam の public path として扱う契約が `CommandOptions` DTO invariant と衝突していた。
  - 解決: CLI scalar shape は `CommandOptions`、config-file scalar validation は `config` seam の責務として issue docs と tests を整合させた。

## 学んだこと
- config seam は path/context failure を diagnostic に変換するが、CLI DTO の shape validation を二重に public contract 化しない。
- `Path.resolve()` の failure も seam 境界で捕捉しないと、filesystem edge case で diagnostic handoff が破れる。

## 今後の推奨事項
- 後続 CLI binding issue で raw CLI 入力から `CommandOptions` へ変換する段階の `cli_usage_error` と user-facing message を別途固定する。

## 省略/例外メモ
- root `AGENTS.md`、README、SpecDock workflow docs への恒久 docs 変更は不要。変更は issue-scoped docs に限定した。
