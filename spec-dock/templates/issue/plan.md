---
種別: 実装計画書（Issue）
ID: "<ISS_ID>"
タイトル: "<ISS_TITLE>"
関連GitHub: ["<GITHUB_ISSUE_NUMBER_OR_URL>"]
状態: "draft | approved"
作成者: "<YOUR_NAME>"
最終更新: "YYYY-MM-DD"
依存: ["requirement.md", "design.md"]
親: ["<EPIC_ID>", "<INIT_ID>"]
---

# <ISS_ID> <ISS_TITLE> — 実装計画（Execution Contract）

> このテンプレートは最小 scaffold です。プロジェクトの目的、作業内容、人間の理解しやすさ、エージェントの実行可能性に合わせて、項目は追加・削除・統合・並べ替えてよい。実行方針は `workflow_issue.md`、Issue 計画の書き方は `phase_plan_issue.md` を正本にする。

## この計画で満たす要件ID
- AC:
  - ...
- EC:
  - ...
- 制約:
  - ...

## マイルストーン一覧
- M1:
  - 対象:
  - 完了条件:
- M2:
  - ...

## 依存関係から導く実装順序
- 依存関係の正本:
  - `design.md` の `依存関係分析`
  - `design.md` の `Module Dependency Diagram`
  - `design.md` の `ディレクトリ / ファイル変更計画`
- 順序ルール:
  - upstream / prerequisite / lower-dependency slice から先に step を組む
  - downstream / dependent slice は前提が固まってから置く
- step 順序メモ:
  - どの step が何に依存するかを短く書く
- step 依存 summary:
  - S01:
    - 依存:
    - unblock:
    - 対象ファイル:

## ステップ一覧
- S01:
  - 観測可能な振る舞い:
  - 依存:
  - unblock:
  - 対象ファイル:
  - 閉じる要件:
  - レビューゲート:
- S02:
  - ...

## 要件 ↔ ステップ対応
- AC-001 -> S01
- EC-001 -> S02

## Spec-Locked Closure Index（仕様固定クロージャ索引）

> これは Issue 全体のテストケース一覧ではなく、エージェントが仕様を縮小解釈・後付けテスト・過剰実装しないための coverage ledger です。実際の test contract と close 条件は各 step の `step closure contract` に置く。具体テストケース本文は各 implementation step の `具体テストケース一覧` にカード型ネストリストで置く。private method、実装アルゴリズム、mock 構造、assert 細部は原則固定しない。

| id | phase / step | slice | type | spec link | locked expectation | observable input/state | bug class guarded | required | evidence level | closure evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| tc-001 | S01 | <behavior> | acceptance | AC-001 | ... | ... | spec drift | yes | red-required | report step closure |
| tc-002 | S01 | <behavior> | negative | EC-001 | ... | ... | silent failure | yes | covered-existing | report step closure |

- 必要時に追加する詳細列:
  - fixture メモ:
  - golden output:
  - manual verification:
  - property domain:
  - 非目標:
- evidence level の値:
  - red-required:
  - covered-existing:
  - inspect-only:
  - manual-required:
- 詳細化方針:
  - 通常 Issue は step / behavior slice ごとに 1〜3 件程度の検証契約を書く。
  - 中央 index は重複するテストケース表にせず、仕様ロック、担当 step、required、evidence level、closure evidence だけを追う。
  - 具体テストケース本文は横長 table にせず、各 step の `具体テストケース一覧` にネストリストで書く。
  - public CLI behavior、shipped scaffold / runtime contract、template / system docs の互換性、installer / update / migration、filesystem / GitHub / active store、negative path、既存 regression、複数 Agent 並列実装の領域では詳細化する。

## レビュー / QA ゲート方針
- RG1 implementation review:
  - 実施タイミング: 各 implementation step の commit 前
  - reviewer: code-reviewer
  - pass 条件: review_status: pass
  - 範囲: 現在 step の diff、tests、docs/report 更新、spec 影響
- QG1 QA review:
  - 実施タイミング: S99 final quality gate
  - reviewer: qa-reviewer
  - 範囲: Issue 全体の test 十分性と integration test 要否
- SG1 spec review:
  - 実施タイミング: S90 docs impact resolution と S99 final quality gate
  - reviewer: spec-reviewer
  - 範囲: requirement / design / plan / report / docs 整合と要件達成

## 実行ルール（全ステップ共通）
- 実行 policy、approval cadence、completion contract は `workflow_issue.md` を正本にする。
- step / block / behavior slice の書き方は `phase_plan_issue.md` を正本にする。
- plan 本文には、この Issue 固有の順序、依存、検証、review / QA gate だけを書く。
- 各 implementation step は commit 単位として設計し、`code-reviewer gate` を pass してから `commit gate` で閉じる。
- `approved-no-op` は差分なしの場合だけ許可し、理由、確認対象、差分なし確認コマンドを report に残す。
- implementation step を追加する場合は S01 の subsections を複製し、`具体テストケース一覧`、`step closure contract`、`behavior slice execution`、`step gate` を各 step に必ず置く。

## 実装ステップ

### S01 — <観測可能な振る舞い>
- 観測可能な振る舞い:
  - ...
- design 参照:
  - ...
- 依存:
  - ...
- unblock:
  - ...
- 対象ファイル:
  - ...
- test bundle:
  - closure id:
    - tc-001
  - test id:
    - same as closure ids unless a project explicitly documents separate aliases
  - evidence level:
    - red-required / covered-existing / inspect-only / manual-required
  - 受け入れ:
  - characterization:
  - property / invariant:
  - regression:
  - negative:
- pre-implementation evidence:
  - expected red / characterization pass / test sensitivity evidence:

#### 具体テストケース一覧

- `tc-s01-001` acceptance: <短い説明>
  - 前提: ...
  - 操作: ...
  - 期待結果: ...
  - 失敗検出: ...
  - 検証方法: ...
  - 関連 closure id: tc-001

- `tc-s01-002` negative: <短い説明>
  - 前提: ...
  - 操作: ...
  - 期待結果: ...
  - 失敗検出: ...
  - 検証方法: ...
  - 関連 closure id: tc-002

- docs-only / approved-no-op step の場合:
  - テスト不要理由: ...
  - 代替検証方法: ...
- report draft update before review:
  - verification / closure / review intent evidence to include in the step diff:
- notes:
  - ...

#### step closure contract
- closure id:
  - tc-001
- close 条件:
  - ...
- 検証 evidence:
  - targeted command / manual evidence / inspection evidence:
- report evidence:
  - Step Contract Closure:
  - Test Contract Closure:
  - Closure Coverage:
- 残リスク:
  - ...

#### behavior slice execution
- 実装 batch:
  - 許可範囲:
  - 禁止範囲:
- 検証:
  - targeted command:
  - 関連 / full command:
- refactor / tidy:
  - 目的:
  - ガードレール:

#### step gate
- delegation 判断:
  - delegated / approved-local-execution / degraded mode:
  - 必須理由 / no delegation rationale:
- report draft update:
  - update before code-reviewer so the evidence is reviewed and committed with the step:
- code-reviewer gate:
  - reviewer: code-reviewer
  - review 範囲:
  - pass 条件: review_status: pass
  - re-review rule: 指摘を修正し pass まで再実行
- 期待する検証:
  - ...
- commit gate:
  - closure 状態: committed / approved-no-op
  - commit 範囲:
  - commit message 意図:
  - post-commit clean check:
- no-op gate:
  - 許可条件:
  - diff 確認コマンド:
  - 確認した contract / file:
  - read-only 確認 evidence:
  - 根拠:
- post-commit report evidence:
  - commit hash / final ledger 参照:
  - clean check result:

### Sxx — <next observable behavior>
- S01 の subsections を複製して記入する。
- `具体テストケース一覧`、`step closure contract`、`behavior slice execution`、`step gate` がない implementation step は implementation-ready ではない。

### S90 — docs impact resolution / docs refresh
- 対象:
  - docs / templates / README / workflow / skill / migration notes / none
- 対応:
  - ...
- doc update owner:
  - doc-writer when updates are required
- spec/doc review:
  - reviewer: spec-reviewer
  - pass 条件: docs が requirement / design / plan と整合し、未解決の必須 docs 影響が残っていない

### S99 — final quality gate
- branch diff 範囲:
  - ...
- 必須 validation:
  - ...
- final QA gate:
  - reviewer: qa-reviewer
  - 範囲: Issue 全体の test 十分性と integration test 要否
  - pass 条件: reviewer pass。必要なら先に integration test を追加する
  - re-review rule: 指摘を修正し qa-reviewer を pass まで再実行
- final code review ゲート:
  - reviewer: code-reviewer
  - 範囲: issue-wide integrated diff、構造、責務境界、回帰リスク、保守性
  - pass 条件: review_status: pass
  - re-review rule: 指摘を修正し code-reviewer を pass まで再実行
- final spec review ゲート:
  - reviewer: spec-reviewer
  - 範囲: requirement / design / plan / report / implementation / tests / docs 整合
  - pass 条件: reviewer pass
  - re-review rule: 指摘を修正し spec-reviewer を pass まで再実行
- final commit gate:
  - commit 範囲:
  - commit 前の final report ledger:
  - post-commit external evidence の記録先:

## 未確定事項
- Q-001:
  - 質問:
  - 選択肢:
    - A:
      - ...
    - B:
      - ...
  - 推奨案:
    - ...
  - 影響範囲:
    - ...

## 最終完了条件
- AC/EC 達成:
  - ...
- docs 影響解決:
  - ...
- 全 implementation step 完了:
  - committed / approved-no-op:
- final quality gate pass:
  - qa-reviewer:
  - issue-wide code-reviewer:
  - spec-reviewer:
- final commit 完了:
  - ...
- 必須 closure id 完了:
  - Step Contract Closure:
  - Test Contract Closure:
  - Closure Coverage:
- final clean state:
  - no unintended staged / unstaged changes:
