---
種別: 実装計画書（Issue）
ID: "iss-00042"
タイトル: "Suppress Self Dependency Relations"
関連GitHub: ["#42"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-26"
依存: ["requirement.md", "design.md"]
親: ["epic-00039", "init-00038"]
---

# iss-00042 Suppress Self Dependency Relations — 実装計画

## この計画で満たす要件ID

- AC-001: self dependency を描画しない
- AC-002: 異なるクラス間の dependency は維持する
- AC-003: relation policy は generate / diff で一致する
- EC-001: 他 relation が同じ endpoint にある場合
- EC-002: type-only / runtime の混在

## 依存関係から導く実装順序

- S01:
  - 依存: `design.md` の selection 層方針
  - unblock: app-level generate / diff consistency tests
  - 対象: `src/pyclassuml/analyze/selection.py`, `tests/analyze/test_selection.py`
- S02:
  - 依存: S01 の selection contract
  - unblock: final reviewer / PR delivery
  - 対象: `tests/app/test_generate.py`, `tests/app/test_diff.py`
- S90:
  - 依存: S01 / S02 の実装結果
  - unblock: final spec review
  - 対象: README / docs impact inspection
- S99:
  - 依存: S01 / S02 / S90
  - unblock: PR delivery and merge-preparation
  - 対象: validation, sync, final reviewer gates, commit evidence

## ステップ一覧

- S01:
  - 観測可能な振る舞い: selection 結果に `dependency` self relation が含まれず、non-self dependency は含まれる。
  - レビューゲート: code-reviewer pass。
- S02:
  - 観測可能な振る舞い: generate / diff の `.puml` に self dependency line が出ず、non-self dependency line は出る。
  - レビューゲート: code-reviewer pass。
- S90:
  - 観測可能な振る舞い: public docs 更新の要否が判断され、必要なら反映される。
  - レビューゲート: spec-reviewer pass。
- S99:
  - 観測可能な振る舞い: issue 全体の verification / reviewer / PR delivery evidence が揃う。
  - レビューゲート: qa-reviewer pass, code-reviewer pass, spec-reviewer pass。

## 仕様固定クロージャ索引

| ID | ステップ | スライス | 種別 | 仕様リンク | 固定する期待値 | 観測可能な入力 / 状態 | 防ぐ bug class | 必須 | 証跡レベル | クロージャ証跡 |
|---|---|---|---|---|---|---|---|---|---|---|
| tc-s01-001 | S01 | selection | acceptance | AC-001, AC-002, EC-002 | `dependency` / `uses` self relation は除外され、non-self dependency は残る | 同一 class 参照と別 class 参照を含む ParsedModule | self dashed relation ノイズ再発 / non-self dependency 消失 | yes | red-required | report S01 |
| tc-s02-001 | S02 | generate | acceptance | AC-001, AC-002, AC-003 | generate の `.puml` で `A ..> A` は出ず `A ..> B` は出る | generate fixture | command 別 policy drift | yes | red-required | report S02 |
| tc-s02-002 | S02 | diff | acceptance | AC-001, AC-002, AC-003 | diff の `.puml` で `A ..> A` は出ず `A ..> B` は出る | diff fixture | command 別 policy drift | yes | red-required | report S02 |
| tc-s90-001 | S90 | docs impact | inspection | 禁止事項 / scope | README / docs 更新が不要または必要最小限に反映済み | docs inspection | user-facing semantics の説明漏れ | yes | inspect-only | report S90 |

## 実行ルール

- 実装は active issue を正本として進める。
- runtime code / tests は `dev-coder` へ委任する。委任不可の場合のみ親実装例外を `report.md` に記録する。
- 各 step は Red evidence、Green evidence、reviewer pass を `report.md` に記録する。
- material な仕様解釈が発生したら、実装を広げる前に `report.md` の Decision Ledger に統合し、必要なら plan amendment と再レビューを行う。

## 実装ステップ S01 — selection contract

- behavior goal:
  - `SelectedRelations.relations` に `dependency` / `uses` self relation を含めない。
  - 同じ入力に含まれる non-self dependency relation は残す。
- input docs / source of truth:
  - `requirement.md`
  - `design.md`
  - `plan.md`
  - `spec-dock/docs/workflow_issue.md`
- design 参照:
  - `design.md` の「採用方針」「インターフェース契約」。
- 対象ファイル:
  - `src/pyclassuml/analyze/selection.py`
  - `tests/analyze/test_selection.py`
- Red:
  - `uv run pytest tests/analyze/test_selection.py -k self_dependency`
  - 実装前に新規 test が self dependency の残存で失敗することを確認する。
- Green:
  - `uv run pytest tests/analyze/test_selection.py -k "dependency or self_dependency"`
- forbidden changes:
  - relation type の追加・変更。
  - CLI / render 表記の変更。
  - parse 層の reference 抽出仕様変更。
- closure:
  - `tc-s01-001` が pass。
  - code-reviewer が pass。
- report evidence destination:
  - `report.md` の TDD / Red / Green、Step Contract Closure、Test Contract Closure、Delegated Worker Evidence。
- amendment trigger:
  - `dependency` / `uses` 以外の self relation 抑制が必要になる場合。
  - allowed paths 外の変更が必要になる場合。
  - diagnostics / CLI / render arrow semantics の変更が必要になる場合。

### 具体テストケース S01

- `tc-s01-001`: selection は self dashed relation を除外し non-self dependency を残す。
  - 前提: `ParsedModule` に `A -> A` の `direct_class_call`、`A -> A` の `local_annotation_dependency`、`A -> A` の `method_return_annotation`、`A -> B` の `direct_class_call` がある。
  - 操作: `select((seed,), seeds=("pkg/source.py",), reachable=("pkg/source.py",))` を実行する。
  - 期待結果: `SelectedRelation("pkg/source.py:A", "pkg/source.py:B", "dependency", "direct_class_call")` だけが残り、`A -> A` dependency は残らない。
  - 失敗検出: production suppression なしでは `A -> A` dependency が relations に残る。
  - 検証方法: `uv run pytest tests/analyze/test_selection.py -k self_dependency`。

### 委任契約 S01

- delegated role:
  - dev-coder
- source of truth:
  - active issue docs: `requirement.md`, `design.md`, `plan.md`
- acceptance criteria:
  - AC-001, AC-002, EC-002
- 許可 paths:
  - `src/pyclassuml/analyze/selection.py`
  - `tests/analyze/test_selection.py`
- 禁止 changes:
  - 上記以外の runtime code / docs 変更。
  - CLI option、設定、render arrow 変更。
- 必須出力:
  - 変更ファイル、Red / Green command と結果、material decision の有無。
- reviewer focus:
  - code-reviewer: `_normalize_relations()` で `dependency` / `uses` self relation だけが除外され、non-self dashed relation と他 relation type に副作用がないこと。
- report evidence destination:
  - `report.md` の Delegated Worker Evidence と S01 closure rows。
- 停止条件:
  - 要件と設計の衝突。
  - allowed paths 以外の変更が必要。
  - Red / Green を実行できない。

## 実装ステップ S02 — generate / diff consistency

- behavior goal:
  - `generate` と `diff` の `.puml` 出力で同じ self dependency suppression policy が観測できる。
- input docs / source of truth:
  - `requirement.md`
  - `design.md`
  - `plan.md`
  - `spec-dock/docs/workflow_issue.md`
- 対象ファイル:
  - `tests/app/test_generate.py`
  - `tests/app/test_diff.py`
- Red:
  - `uv run pytest tests/app/test_generate.py tests/app/test_diff.py -k self_dependency`
  - 実装前または S01 実装を一時的に戻した状態で失敗する test sensitivity を確認する。S01 後に追加する場合は、test が実装 contract を直接検出することを inspection で補足する。
- Green:
  - `uv run pytest tests/app/test_generate.py tests/app/test_diff.py -k "self_dependency or direct_dependency"`
- forbidden changes:
  - app CLI behavior や command line contract の変更。
  - PlantUML arrow mapping の変更。
- closure:
  - `tc-s02-001` / `tc-s02-002` が pass。
  - code-reviewer が pass。
- report evidence destination:
  - `report.md` の TDD / Red / Green、Step Contract Closure、Test Contract Closure、Delegated Worker Evidence。
- amendment trigger:
  - S02 で production code 変更が必要になった場合。
  - generate と diff で異なる relation policy が必要になる場合。

### 具体テストケース S02

- `tc-s02-001`: generate は self dependency を出力せず non-self dependency を出力する。
  - 前提: `pkg/source.py` に class `A` と `B` があり、`A.make_self()` が `A()`、`A.make_other()` が `B()` を返す。
  - 操作: `run_generate(... output=Path("self-dependency.puml"))` を実行する。
  - 期待結果: `A ..> A` は出ず、`A ..> B` は出る。
  - 失敗検出: production suppression なしでは `.puml` に `c001 ..> c001` が出る。
  - 検証方法: `uv run pytest tests/app/test_generate.py -k self_dependency`。
- `tc-s02-002`: diff は self dependency を出力せず non-self dependency を出力する。
  - 前提: base では `A.make()` が `None` を返し、working tree で `A.make_self()` が `A()`、`A.make_other()` が `B()` を返す。
  - 操作: `run_diff(... output=Path("self-dependency.puml"))` を実行する。
  - 期待結果: `A ..> A` は出ず、`A ..> B` は出る。
  - 失敗検出: production suppression なしでは `.puml` に `c001 ..> c001` が出る。
  - 検証方法: `uv run pytest tests/app/test_diff.py -k self_dependency`。

### 委任契約 S02

- delegated role:
  - dev-coder
- source of truth:
  - active issue docs: `requirement.md`, `design.md`, `plan.md`
- acceptance criteria:
  - AC-001, AC-002, AC-003
- 許可 paths:
  - `tests/app/test_generate.py`
  - `tests/app/test_diff.py`
- 禁止 changes:
  - production code 変更。S02 で production code 変更が必要になった場合は S01 へ戻す。
- 必須出力:
  - 変更ファイル、Red / Green command と結果、material decision の有無。
- reviewer focus:
  - code-reviewer: app-level tests が generate / diff の共通 selection policy を検出し、CLI contract や arrow mapping を変えていないこと。
- report evidence destination:
  - `report.md` の Delegated Worker Evidence と S02 closure rows。

## ドキュメント影響の解消ステップ S90

- 対象:
  - README / docs / examples の user-facing relation semantics。
- 対応:
  - self dependency suppression は bugfix-level の internal policy であり、公開 CLI contract を変えない。既存 docs に self dependency を明示する箇所がなければ no-op とする。
- 検証:
  - `rg "self dependency|dependency|\\.\\.>" README.md spec-dock -g '*.md'`
- closure:
  - `tc-s90-001` が inspection で pass。
  - spec-reviewer が pass。

## 最終品質ゲート S99

- 実行:
  - `uv run pytest`
  - `./spec-dock/scripts/spec-dock validate`
  - `./spec-dock/scripts/spec-dock sync`
  - `git diff --check`
- reviewer:
  - qa-reviewer: obligation coverage / test adequacy
  - code-reviewer: issue-wide runtime diff
  - spec-reviewer: requirement / design / plan / report alignment
- PR:
  - base: `main`
  - 関連 Issue: `Closes #42`
  - merge-preparation evidence を report に記録する。

## 要件 ↔ ステップ対応

- AC-001 -> S01, S02
- AC-002 -> S01, S02
- AC-003 -> S02
- EC-001 -> S01
- EC-002 -> S01
