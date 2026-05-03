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
- 実装対象は `TargetSet` から import 非実行 AST parse closure を作る `parse` seam に限定し、traversal / relation / changed class / framework / report policy は非スコープとして維持する。
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

## 遭遇した問題と解決
- 問題: `plan.md` / `report.md` がテンプレート状態で、workflow_issue の complete 条件を満たせない状態だった。
  - 解決: issue requirement / design に合わせ、実装ステップ、検証、review、docs impact、final exit contract を具体化した。

## 学んだこと
- `iss-00012` は core-analysis epic の先頭 issue であり、`ModuleIndex` の seam-local handoff shape が後続 traversal / relation / changed inventory の前提になる。

## 今後の推奨事項
- 実装時は `targets.ignore` を再利用し、seed target normalize と dependency candidate ignore の semantics を分岐させない。

## 省略/例外メモ
- 現時点では未完了。spec review、実装、targeted/full tests、implementation review、QA review、`sync --github`、final report update が未実施である。
