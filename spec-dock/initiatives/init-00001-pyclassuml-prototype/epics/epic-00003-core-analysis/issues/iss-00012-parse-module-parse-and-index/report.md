---
種別: 実装報告書（Issue）
ID: "iss-00012"
タイトル: "Parse Module Parse And Index"
関連GitHub: ["#12"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00003", "init-00001"]
---

# iss-00012 Parse Module Parse And Index — 実装報告（LOG）

## 実装サマリー
- 2026-05-04 時点では、active issue を `iss-00012-parse-module-parse-and-index` として復元し、`requirement.md` / `design.md` を確認した。
- `plan.md` / `report.md` がテンプレート状態だったため、`parse` seam の実装可能な execution contract と evidence log へ置き換えた。
- `parse_target_set(TargetSet, ExecutionContext, AnalysisConfig) -> ParseResult` を追加し、`TargetSet` から import 非実行 AST parse closure、`ParsedModule[]`、`ModuleIndex`、syntax diagnostics、dependency candidate ignore observations を構築した。
- 実装対象は `parse` seam に限定し、traversal / relation / changed class / framework / report policy は非スコープとして維持する。
- spec-reviewer pass 1 は fail。syntax error module の discard / lookup 含有可否、ignore count の返却場所、scope 外 candidate lookup 観測が不足していたため、`ParseResult` / `ParseObservations` と `ModuleIndex.import_candidate_paths` の handoff 契約を design / plan に追記した。

## 実装記録（セッションログ）

### 2026-05-04 active set and implementation-readiness repair

#### 対象
- Step: SG1, planning repair
- AC/EC: AC-001, AC-002, AC-003, EC-001, EC-002, EC-003

#### 実施内容
- `iss-00011` close 後、`iss-00012` の dependency が ready / blockers=0 になったことを確認した。
- spec-manager により `iss-00012` を active set し、active pointers が `init-00001` / `epic-00003` / `iss-00012` になったことを確認した。
- `requirement.md` / `design.md` は issue 固有内容だったが、`plan.md` / `report.md` はテンプレート状態だったため、S01/S02/S03/S90/S99 の execution contract へ置き換えた。

#### 実行コマンド / 結果
```bash
./spec-dock/scripts/spec-dock deps check iss-00012 --github

spec-dock: ok (deps check) target=iss-00012 authority=github effective_status=open source=github stale=false ... ready=true blockers=0
```

```bash
./spec-dock/scripts/spec-dock active set iss-00012

spec-dock: ok (active set) target=iss-00012 initiative=init-00001 epic=epic-00003 issue=iss-00012
```

```bash
./spec-dock/scripts/spec-dock active show

initiative: init-00001 (spec-dock/initiatives/init-00001-pyclassuml-prototype)
epic: epic-00003 (spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00003-core-analysis)
issue: iss-00012 (spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00003-core-analysis/issues/iss-00012-parse-module-parse-and-index)
```

```bash
./spec-dock/scripts/spec-dock validate

spec-dock: ok (validate) nodes=21
```

#### 変更したファイル
- `spec-dock/active/issue/plan.md` - issue-specific execution contract へ置き換え。
- `spec-dock/active/issue/report.md` - active set / readiness repair evidence を記録。

#### コミット
- 実装・検証差分とまとめて判断する。

#### メモ
- worktree は active set 後も clean だった。
- 実装前に spec-reviewer pass を取得する。

### 2026-05-04 spec-review repair

#### 対象
- Step: SG1 repair
- AC/EC: AC-001, AC-002, AC-003, EC-001, EC-002, EC-003

#### 実施内容
- spec-reviewer の P1 指摘に従い、parse seam の戻り値を `ParseResult(parsed_modules, module_index, observations, diagnostics)` と明示した。
- ignored dependency candidate count の返却場所を `ParseResult.observations.ignored_dependency_candidate_count` に固定した。
- syntax error module は `ParsedModule[]` / `ModuleIndex` lookup から除外し、`ParseResult.diagnostics` だけに保持する discard 範囲を固定した。
- package_root 外 candidate と scope_root 外 candidate は `ModuleIndex.import_candidate_paths` に lookup 材料として保持し、parse は frontier 採否しない契約へ修正した。
- spec-reviewer pass 2 は pass。残った P2 の per-step verification command 明示は gate failure ではないが、S01-S03 の review gate に exact pytest command を追記した。

#### 実行コマンド / 結果
```bash
./spec-dock/scripts/spec-dock validate

spec-dock: ok (validate) nodes=21
```

#### 変更したファイル
- `spec-dock/active/issue/design.md` - `ParseResult` / `ParseObservations` / syntax discard / boundary lookup を追記。
- `spec-dock/active/issue/plan.md` - S01-S03 の test expectations と handoff contract を修正。
- `spec-dock/active/issue/report.md` - spec-review repair evidence を追記。

#### コミット
- spec-review pass 後に判断する。

### 2026-05-04 implementation and verification

#### 対象
- Step: S01, S02, S03, S90, S99
- AC/EC: AC-001, AC-002, AC-003, EC-001, EC-002, EC-003

#### 実施内容
- `src/pyclassuml/parse/__init__.py` と `src/pyclassuml/parse/indexer.py` を追加した。
- seam-local DTO として `ParseResult`、`ParseObservations`、`ModuleIndex` を追加した。
- AST-only で module imports / class qualname を抽出し、class id は `<module_path>:<qualname>` 形式で返す。
- seed imports から package-local dependency candidate を deterministic に探索し、recursive parse closure を作る。
- syntax error module は `ParsedModule[]` / `ModuleIndex` lookup から除外し、`ParseResult.diagnostics` に `bad_syntax` diagnostic として carry する。
- dependency candidate ignore は `targets.ignore` を再利用し、`ParseResult.observations.ignored_dependency_candidate_count` に反映する。
- QA pass 1 は fail。recursive parse closure と default ignore candidate のテスト観測不足を指摘されたため、transitive dependency closure と default ignore の coverage を追加した。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest tests/parse/test_module_parse_and_index.py -q

6 passed in 0.03s
```

```bash
uv run --with pytest pytest tests/targets/test_diff_target_normalize.py tests/targets/test_explicit_target_normalize.py -q

25 passed in 0.04s
```

```bash
uv run --with pytest pytest -q

99 passed in 1.05s
```

```bash
./spec-dock/scripts/spec-dock validate

spec-dock: ok (validate) nodes=21
```

#### 変更したファイル
- `src/pyclassuml/parse/__init__.py` - parse seam public surface。
- `src/pyclassuml/parse/indexer.py` - parse target set implementation。
- `tests/parse/test_module_parse_and_index.py` - AC/EC と QA finding coverage の unit tests。
- `spec-dock/active/issue/report.md` - implementation / validation evidence。

#### レビュー / QA
- Implementation review: pass。code-reviewer は AC/EC と実装整合、AST-only/read-only/deterministic、syntax error diagnostics、ignore count、seam-local `ModuleIndex` を確認し、finding なし。
- QA review pass 1: fail。recursive parse closure と default ignore candidate exclusion のテスト観測不足を指摘。
- QA finding resolution: `a.py -> b.py -> c.py` の transitive dependency closure と `venv/**` default ignore dependency candidate exclusion をテストへ追加。
- QA re-review: pass。QA reviewer は recursive parse closure と default ignore candidate exclusion の finding 解消、targeted parse pytest、SpecDock validate、AC/EC coverage を確認し、finding なし。

#### コミット
- 実施予定。

## 遭遇した問題と解決
- 問題: `plan.md` / `report.md` がテンプレート状態で、workflow_issue の complete 条件を満たせない状態だった。
  - 解決: issue requirement / design に合わせ、実装ステップ、検証、review、docs impact、final exit contract を具体化した。

## 学んだこと
- `iss-00012` は core-analysis epic の先頭 issue であり、`ModuleIndex` の seam-local handoff shape が後続 traversal / relation / changed inventory の前提になる。

## 今後の推奨事項
- 実装時は `targets.ignore` を再利用し、seed target normalize と dependency candidate ignore の semantics を分岐させない。

## 省略/例外メモ
- root `AGENTS.md`、README、SpecDock workflow docs への恒久 docs 変更は不要。変更は issue-scoped docs と parse seam implementation に限定した。
- `uv` が生成した `uv.lock` は scope 外生成物のため成果差分から除外した。
- 現時点の残作業は commit、GitHub issue close、`sync --github` による dashboard の done 反映である。
