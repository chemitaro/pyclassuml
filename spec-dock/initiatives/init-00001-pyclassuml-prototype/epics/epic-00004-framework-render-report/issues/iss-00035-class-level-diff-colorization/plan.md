---
種別: 実装計画書（Issue）
ID: "iss-00035"
タイトル: "Class Level Diff Colorization"
関連GitHub: ["#35"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-15"
依存: ["requirement.md", "design.md"]
親: ["epic-00004", "init-00001"]
---

# iss-00035 Class Level Diff Colorization — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001 modified file 内 new class の `DiffAdded`
  - AC-002 existing class modification の `DiffChanged`
  - AC-003 added / untracked file class の `DiffAdded`
  - AC-004 dependency-only class の通常表示
- EC:
  - EC-001 rename-only file
  - EC-002 class rename / move は conservative Added
  - EC-003 nested class
  - EC-004 parse/read failure で decoration を捏造しない
  - EC-005 safe-added base 欠損だけを `DiffAdded` 前提にする
- 制約:
  - target code import 禁止、base file 永続書き出し禁止、summary semantics 変更禁止

## マイルストーン一覧
- M1: base/current class inventory seam
  - 完了条件: base blob read と source text parse helper が tested。
- M2: class-level diff classifier
  - 完了条件: `DiffAdded` / `DiffChanged` / no decoration が class 単位で決まる。
- M3: renderer/E2E verification
  - 完了条件: `.puml` style と CLI E2E が acceptance を閉じる。

## 依存関係から導く実装順序
- step 依存 summary:
  - S01:
    - 依存: existing VCS / parse contracts
    - unblock: S02 class classifier
    - 対象ファイル: `vcs/diff_collect.py`, `parse/indexer.py`, related unit tests
  - S02:
    - 依存: S01 base/current inventory
    - unblock: S03 renderer/E2E
    - 対象ファイル: `app/diff.py`, `tests/app/test_diff.py`
  - S03:
    - 依存: S02 classifier
    - unblock: S90/S99
    - 対象ファイル: `render/document.py`, app/render tests

## ステップ一覧
- S01:
  - 観測可能な振る舞い: base revision の class inventory を import なしで作れる。
  - 閉じる要件: AC-001, AC-003, EC-001, EC-004 の前提
  - レビューゲート: code-reviewer
- S02:
  - 観測可能な振る舞い: modified file 内 new class と existing modified class を class 単位で分類できる。
  - 閉じる要件: AC-001, AC-002, AC-004, EC-001, EC-002, EC-003, EC-004
  - レビューゲート: code-reviewer
- S03:
  - 観測可能な振る舞い: PlantUML に `DiffAdded` 水色と `DiffChanged` 緑が出る。
  - 閉じる要件: AC-001, AC-002, AC-003, AC-004
  - レビューゲート: code-reviewer

## 要件 ↔ ステップ対応
- AC-001 -> S01, S02, S03
- AC-002 -> S02, S03
- AC-003 -> S01, S02, S03
- AC-004 -> S02, S03
- EC-001 -> S01, S02
- EC-002 -> S02
- EC-003 -> S02
- EC-004 -> S01, S02
- EC-005 -> S01, S02

## Spec-Locked Closure Index（仕様固定クロージャ索引）

| id | phase / step | slice | type | spec link | locked expectation | observable input/state | bug class guarded | required | evidence level | closure evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| tc-s01-001 | S01 | base class inventory | acceptance | AC-001, EC-001 | base blob is parsed with current logical path for rename-aware identity | renamed / modified file with base class | base/current mismatch | yes | red-required | unit test + report |
| tc-s01-002 | S01 | safe-added base absence | acceptance | AC-003, EC-005 | added/untracked base absence is explicit safe-added input | added/untracked file | unsafe base read conflation | yes | red-required | unit test + report |
| tc-s01-003 | S01 | unsafe base failure | negative | EC-004 | unexpected base read/decode/parse failure does not become Added | modified/renamed file with unsafe base failure | fabricated Added | yes | red-required | unit test + report |
| tc-s02-001 | S02 | modified file new class | acceptance | AC-001 | current-only class in modified file gets `DiffAdded` | existing file gains class | file-level false green | yes | red-required | app unit/E2E + report |
| tc-s02-002 | S02 | existing class modified | acceptance | AC-002 | base/current class with hunk overlap gets `DiffChanged` | existing class body edit | lost green regression | yes | covered-existing + updated | app unit/E2E + report |
| tc-s02-003 | S02 | dependency-only unchanged | negative | AC-004 | selected dependency with no class diff has no decoration | changed class depends on unchanged class | noisy dependency color | yes | covered-existing + updated | app E2E + report |
| tc-s02-004 | S02 | nested class addition | edge | EC-003 | current-only nested class is `DiffAdded` | nested class addition | missed nested class addition | yes | red-required | app unit/E2E + report |
| tc-s02-005 | S02 | class rename conservative | edge | EC-002 | renamed current class is `DiffAdded` rather than heuristically matched | class rename / move | unsafe rename heuristic | yes | red-required | app unit/E2E + report |
| tc-s02-unsafe-classification | S04-review-fix | unsafe classification diagnostics | negative | EC-004 | unsafe base/current classification failures emit warning diagnostics and do not fabricate decorations | base read failure / HEAD current parse failure | silent missing colorization or snapshot fallback | yes | regression | app E2E + report |
| tc-s03-001 | S03 | renderer styles | acceptance | AC-001, AC-002 | `DiffAdded` and `DiffChanged` styles are both emitted deterministically | render model with both decorations | missing PlantUML style | yes | red-required | render unit + report |
| tc-s03-002 | S03 | generate unaffected | negative | constraint | generate output has no diff-specific style | generate command | command-scope leak | yes | covered-existing | app/render tests + report |
| tc-s03-003 | S03 | added / untracked diff E2E | acceptance | AC-003 | tracked added and included untracked classes render as `DiffAdded` in `pyclassuml diff` output | added file / untracked file | file-level added not surfaced | yes | red-required | app E2E + report |

## レビュー / QA ゲート方針
- RG1 implementation review:
  - 各 S01-S03 commit 前に code-reviewer を実行し、`review_status: pass` まで修正する。
- QG1 QA review:
  - S99 final quality gate で qa-reviewer を実行し、test 十分性を確認する。
- SG1 spec review:
  - 実装前の requirement/design/plan と S90/S99 で spec-reviewer を実行する。

## 実装ステップ

### S01 — base/current class inventory seam
- 観測可能な振る舞い:
  - base revision の Python blob を workspace に書き出さず AST parse できる。
- design 参照:
  - VCS boundary、Parse boundary
- 対象ファイル:
  - `src/pyclassuml/vcs/diff_collect.py`
  - `src/pyclassuml/parse/indexer.py`
  - `tests/vcs/test_diff_file_collect.py`
  - `tests/parse/test_module_parse_and_index.py`
- test bundle:
  - closure id: tc-s01-001, tc-s01-002, tc-s01-003
  - evidence level: red-required

#### 具体テストケース一覧

- `tc-s01-001` acceptance: base blob を logical current path で class inventory 化できる
  - 前提: Git base に `pkg/old.py:Model` があり、current で `pkg/new.py` に rename される。
  - 操作: base blob read helper と source parse helper を使う。
  - 期待結果: base text が取得でき、logical path を `pkg/new.py` にした class id と span が得られる。
  - 失敗検出: missing blob 扱いになる、または old path の class id のままになる。
  - 検証方法: `uv run --with pytest pytest tests/vcs/test_diff_file_collect.py tests/parse/test_module_parse_and_index.py -q`
  - 関連 closure id: tc-s01-001

- `tc-s01-002` acceptance: safe-added base absence は追加扱いの前提になる
  - 前提: current に untracked / added Python file があり base blob は存在しない。
  - 操作: base blob read helper を呼ぶ。
  - 期待結果: safe-added absence として表現され、後段が Added 判定できる。
  - 失敗検出: Git error diagnostic に昇格する、または Modified 判定材料を捏造する。
  - 検証方法: `uv run --with pytest pytest tests/vcs/test_diff_file_collect.py -q`
  - 関連 closure id: tc-s01-002

- `tc-s01-003` negative: unsafe base failure は Added に変換しない
  - 前提: modified / renamed file の base blob read / base parse、または `--current-state head` の current parse が失敗する。
  - 操作: diff classification を含む `pyclassuml diff` pipeline を実行する。
  - 期待結果: unsafe failure として warning diagnostic / no-decoration path に倒し、`DiffAdded` / `DiffChanged` 判定の材料にしない。
  - 失敗検出: 失敗した file の current class が `DiffAdded` / `DiffChanged` になる、または warning なしで黙って色分けを消す。
  - 検証方法: `uv run --with pytest pytest tests/vcs/test_diff_file_collect.py tests/app/test_diff.py -q`
  - 関連 closure id: tc-s01-003, tc-s02-unsafe-classification

#### step closure contract
- close 条件:
  - tc-s01-001 / tc-s01-002 / tc-s01-003 が pass。
  - target code import と base file 永続書き出しがない。
- 検証 evidence:
  - targeted pytest、`git diff --check`
- report evidence:
  - Step Contract Closure / Test Contract Closure / Closure Coverage へ記録。

#### step gate
- delegation 判断:
  - delegated: VCS / parse seam を跨ぐため repo-analyst または local pattern analysis を記録する。
- code-reviewer gate:
  - review 範囲: S01 diff と tests。
- commit gate:
  - commit 範囲: S01 files only。

### S02 — class-level diff classifier
- 観測可能な振る舞い:
  - modified file 内 new class は `DiffAdded`、existing changed class は `DiffChanged`、unchanged dependency は no decoration。
- design 参照:
  - App diff boundary
- 対象ファイル:
  - `src/pyclassuml/app/diff.py`
  - `tests/app/test_diff.py`
- test bundle:
  - closure id: tc-s02-001, tc-s02-002, tc-s02-003, tc-s02-004, tc-s02-005
  - evidence level: red-required / covered-existing + updated

#### 具体テストケース一覧

- `tc-s02-001` acceptance: 既存ファイル内の新規 class は `DiffAdded`
  - 前提: base に `Existing`、current に `Existing` と `NewlyAdded` がある。
  - 操作: `run_diff` または classifier を実行する。
  - 期待結果: `NewlyAdded` は `<<DiffAdded>>`、`Existing` は変更がなければ decoration なし。
  - 失敗検出: `NewlyAdded` が `DiffChanged` または decoration なしになる。
  - 検証方法: `uv run --with pytest pytest tests/app/test_diff.py -q`
  - 関連 closure id: tc-s02-001

- `tc-s02-002` acceptance: 既存 class 修正は `DiffChanged`
  - 前提: base/current に同じ class があり、class body に current changed hunk がある。
  - 操作: `pyclassuml diff` E2E を実行する。
  - 期待結果: 対象 class は `<<DiffChanged>>`。
  - 失敗検出: `DiffAdded` になる、または decoration が消える。
  - 検証方法: `uv run --with pytest pytest tests/app/test_diff.py -q`
  - 関連 closure id: tc-s02-002

- `tc-s02-003` negative: dependency-only class は通常表示
  - 前提: changed class が unchanged dependency class を参照する。
  - 操作: `pyclassuml diff` E2E を実行する。
  - 期待結果: dependency class に `DiffAdded` / `DiffChanged` / `DiffDependency` が出ない。
  - 失敗検出: dependency class に diff-specific stereotype が出る。
  - 検証方法: `uv run --with pytest pytest tests/app/test_diff.py -q`
  - 関連 closure id: tc-s02-003

- `tc-s02-004` edge: nested class addition は Added
  - 前提: current で既存 outer class に nested class を追加する。
  - 操作: classifier または E2E を実行する。
  - 期待結果: current-only nested class は `DiffAdded`。
  - 失敗検出: nested class が `DiffChanged` または decoration なしになる。
  - 検証方法: `uv run --with pytest pytest tests/app/test_diff.py -q`
  - 関連 closure id: tc-s02-004

- `tc-s02-005` edge: class rename / move は conservative Added
  - 前提: current で class 名または module path が file rename metadata だけでは対応できない形で変わる。
  - 操作: classifier または E2E を実行する。
  - 期待結果: current-only class は `DiffAdded`。
  - 失敗検出: 類似度推定で `DiffChanged` になる。
  - 検証方法: `uv run --with pytest pytest tests/app/test_diff.py -q`
  - 関連 closure id: tc-s02-005

#### step closure contract
- close 条件:
  - tc-s02-001 から tc-s02-005 が pass。
  - `changed_class_count` の意味を変えない。
- 検証 evidence:
  - targeted pytest、`git diff --check`
- report evidence:
  - Step Contract Closure / Test Contract Closure / Closure Coverage へ記録。

#### step gate
- delegation 判断:
  - delegated: app/render integration と existing regression impact があるため code-reviewer 必須。
- code-reviewer gate:
  - review 範囲: S02 diff と tests。
- commit gate:
  - commit 範囲: S02 files only。

### S03 — PlantUML style and command-level E2E
- 観測可能な振る舞い:
  - `DiffAdded` 水色 style と `DiffChanged` 緑 style が同じ `.puml` に deterministic に出る。
- design 参照:
  - Render boundary
- 対象ファイル:
  - `src/pyclassuml/render/document.py`
  - `tests/render/test_document.py`
  - `tests/app/test_diff.py`
  - `tests/app/test_generate.py`
- test bundle:
  - closure id: tc-s03-001, tc-s03-002, tc-s03-003
  - evidence level: red-required / covered-existing

#### 具体テストケース一覧

- `tc-s03-001` acceptance: renderer が `DiffAdded` と `DiffChanged` style を出す
  - 前提: render model に両 decoration がある。
  - 操作: `render_uml_document` を実行する。
  - 期待結果: `BackgroundColor<<DiffAdded>>` と `BackgroundColor<<DiffChanged>>` が出る。
  - 失敗検出: 片方の style がない、または order が不安定。
  - 検証方法: `uv run --with pytest pytest tests/render/test_document.py -q`
  - 関連 closure id: tc-s03-001

- `tc-s03-002` negative: generate には diff-specific style が漏れない
  - 前提: `generate` command を実行する。
  - 操作: generate app tests を実行する。
  - 期待結果: `DiffAdded` / `DiffChanged` / `DiffDependency` が出ない。
  - 失敗検出: generate output に diff style が出る。
  - 検証方法: `uv run --with pytest pytest tests/app/test_generate.py tests/render/test_document.py -q`
  - 関連 closure id: tc-s03-002

- `tc-s03-003` acceptance: tracked added file と untracked file が E2E で `DiffAdded`
  - 前提: diff に tracked added Python file と included untracked Python file が含まれる。
  - 操作: `pyclassuml diff --base <base> --include-untracked` を実行する。
  - 期待結果: 両方の selected class declaration が `<<DiffAdded>>` を持つ。
  - 失敗検出: `DiffChanged` になる、または decoration なしになる。
  - 検証方法: `uv run --with pytest pytest tests/app/test_diff.py -q`
  - 関連 closure id: tc-s03-003

#### step closure contract
- close 条件:
  - tc-s03-001 / tc-s03-002 / tc-s03-003 が pass。
  - AC-001 から AC-004 の E2E evidence が report に残る。
- 検証 evidence:
  - targeted pytest、`git diff --check`
- report evidence:
  - Step Contract Closure / Test Contract Closure / Closure Coverage へ記録。

#### step gate
- delegation 判断:
  - delegated: final integration and renderer behavior require code review.
- code-reviewer gate:
  - review 範囲: S03 diff と tests。
- commit gate:
  - commit 範囲: S03 files only。

### S90 — docs impact resolution / docs refresh
- 対象:
  - Root `AGENTS.md`, README, workflow docs, skill docs は仕様影響を確認する。
- 対応:
  - CLI behavior に user-facing color semantics が増えるため README / docs の該当箇所が存在する場合は更新する。
  - 該当箇所がない場合は approved-no-op とし、確認コマンドを report に残す。
- spec/doc review:
  - reviewer: spec-reviewer
  - pass 条件: docs 影響が requirement / design / plan と整合する。

### S99 — final quality gate
- branch diff 範囲:
  - `git diff origin/main...HEAD` と working tree diff。
- 必須 validation:
  - `uv run --with pytest pytest tests/vcs/test_diff_file_collect.py tests/parse/test_module_parse_and_index.py tests/app/test_diff.py tests/render/test_document.py tests/app/test_generate.py -q`
  - `uv run --with pytest pytest -q`
  - `./spec-dock/scripts/spec-dock validate`
  - `git diff --check`
  - `test ! -e uv.lock`
  - `rg --files | rg '[A-Z]'` を確認し、既存 uppercase 以外を増やしていないことを報告する。
- final QA gate:
  - reviewer: qa-reviewer
  - pass 条件: reviewer pass。必要なら先に integration test を追加する。
- final code review ゲート:
  - reviewer: code-reviewer
  - pass 条件: review_status: pass。
- final spec review ゲート:
  - reviewer: spec-reviewer
  - pass 条件: reviewer pass。
- final commit gate:
  - commit 範囲: final report ledger / residual docs updates。
  - post-commit external evidence の記録先: final response。

## 最終完了条件
- AC/EC 達成:
  - AC-001 から AC-004、EC-001 から EC-005 が report closure で pass。
- docs 影響解決:
  - S90 pass / approved-no-op。
- 全 implementation step 完了:
  - S01-S03 committed / approved-no-op。
- final quality gate pass:
  - qa-reviewer, issue-wide code-reviewer, spec-reviewer。
- final clean state:
  - no unintended staged / unstaged changes。
