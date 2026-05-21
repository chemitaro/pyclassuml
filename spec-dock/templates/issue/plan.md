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

> このテンプレートは最小 scaffold です。`plan.md` は planned contract を所有し、実装者が step を上から順に実行できる command queue として書く。実行結果、逸脱、discovered tests、reviewer verdict、commit/no-op evidence は `report.md` の observed evidence ledger に記録する。実行 policy は `workflow_issue.md`、Issue 計画の書き方は `phase_plan_issue.md` と `docs/authoring/issue-plan.md` を正本にする。

## この計画で満たす要件ID
- AC:
  - ...
- EC:
  - ...
- 制約:
  - ...

## 依存関係から導く実装順序
- 依存関係の正本:
  - `design.md` の依存関係、図、ファイル変更計画
- 順序ルール:
  - prerequisite / lower-dependency slice から先に閉じる
  - downstream slice は前提が固定されてから置く
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

> これは Issue 全体のテスト一覧ではなく、仕様を縮小解釈・後付けテスト・過剰実装しないための coverage ledger です。実際の step-local obligation と concrete seeds は各 implementation step の `具体テストケース一覧` に置く。

| id | step | slice | type | spec link | locked expectation | observable input/state | bug class guarded | required | evidence level | closure evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| tc-001 | S01 | <behavior> | acceptance | AC-001 | ... | ... | spec drift | yes | red-required | report step closure |
| tc-002 | S01 | <behavior> | negative | EC-001 | ... | ... | silent failure | yes | inspect-only | report step closure |

- evidence level:
  - red-required: 実装前に失敗する新規 test / characterization を固定する。
  - covered-existing: 既存 test が対象 behavior を検出できる根拠を固定する。
  - inspect-only: docs / template / config などを inspection、structural assertion、review evidence で閉じる。
  - manual-required: 自動化できない確認手順、期待結果、記録先を固定する。
- 詳細化方針:
  - 件数ではなく、AC、changed contract、failure mode、regression risk、invariant、manual / integration risk から必要な obligation を決める。
  - private method、実装アルゴリズム、mock 構造、assert 細部は原則固定しない。

## レビュー / QA ゲート方針
- RG1 step review:
  - 実施タイミング: 各 implementation step の commit 前
  - reviewer: code-reviewer for code / runtime / tests / scaffold behavior; spec-reviewer for docs-only / template-only / skill-text-only
  - pass 条件: review_status: pass
- QG1 final QA:
  - reviewer: qa-reviewer
  - 範囲: Issue 全体の obligation coverage、missing high-value tests、manual / integration test 要否
- SG1 final spec review:
  - reviewer: spec-reviewer
  - 範囲: requirement / design / plan / report / docs 整合

## 実行ルール（全ステップ共通）
- 各 implementation step は原則として 1 behavior slice / 1 review scope / 1 commit boundary とする。
- `plan.md` には planned requirements、evidence destination、closure 条件だけを書く。observed result は `report.md` に書く。
- docs-only / inspect-only / manual-required step は code test 前提にせず、代替 evidence path と rationale を implementation 前に固定する。
- implementation 中に新しい仕様、bug class、外部 contract risk、未計画の closure が見つかった場合は、report 記録だけで足りるか、plan amendment と re-review が必要かを判断する。

## 実装ステップ

### S01 — <観測可能な振る舞い>
- behavior goal:
  - ...
- design 参照:
  - ...
- 依存:
  - ...
- unblock:
  - ...
- 対象ファイル:
  - ...
- planned contract:
  - scope:
    - 実装・文書化する範囲:
  - test obligation:
    - closure id:
      - tc-001
    - coverage rationale:
      - AC / changed contract / failure mode / regression risk / invariant / manual risk から必要性を書く:
  - Red / alternative evidence requirement:
    - red-required / covered-existing:
      - 実装前に確認する failing test、characterization、または既存 test sensitivity:
    - docs-only / inspect-only / manual-required:
      - code test を置かない理由:
      - 代替 evidence path:
      - manual 手順と期待結果:
  - implementation scope:
    - allowed paths:
      - ...
    - forbidden changes:
      - ...
  - Green verification:
    - command / inspection / manual evidence:
      - ...
  - Refactor / cleanup guardrail:
    - 目的:
    - 禁止する広がり:
  - closure evidence requirements:
    - Step Contract Closure:
    - Test Contract Closure:
    - Closure Coverage:
  - report evidence destination:
    - `report.md` の対象 section / ledger:
  - amendment trigger:
    - plan amendment と re-review が必要になる発見:

#### delegation contract
- delegated role:
  - dev-coder / doc-writer / other named worker / N/A
- input docs:
  - `requirement.md`
  - `design.md`
  - `plan.md`
  - workflow / authoring docs:
  - current target files:
- allowed paths:
  - ...
- forbidden changes:
  - ...
- acceptance criteria:
  - closure id / step close condition:
- required tests or docs-only verification:
  - targeted command / inspection / docs diff / manual evidence:
- reviewer focus:
  - code-reviewer for code / runtime / tests / scaffold behavior; spec-reviewer for docs-only / template-only / skill-text-only docs/spec alignment
- output required:
  - changed files:
  - verification result:
  - report evidence to update:
  - unresolved risks:
- stop conditions:
  - input docs conflict / path outside allowed scope / verification cannot run / acceptance cannot be met:

#### 具体テストケース一覧

> この欄は full test inventory ではありません。step-local obligation と concrete red / characterization / inspect / manual seeds を、実装前に固定するための欄です。

- `tc-s01-001` acceptance: <短い説明>
  - 前提: ...
  - 操作: ...
  - 期待結果: ...
  - 失敗検出: ...
  - 検証方法: ...
  - 関連 closure id: tc-001

- `tc-s01-002` inspect-only / manual-required: <短い説明>
  - テスト不要理由: <自動テスト不要の理由>
  - 代替検証方法: <確認手順>
  - 期待結果: <期待される状態>
  - 記録先: <証跡の保存先>
  - 関連 closure id: tc-002

#### step closure contract
- closure id:
  - tc-001
- close 条件:
  - ...
- 検証 evidence:
  - targeted command / inspection / manual evidence:
- report evidence:
  - Step Contract Closure:
  - Test Contract Closure:
  - Closure Coverage:
  - Closure Delta:
- 残リスク:
  - ...

#### step gate
- step reviewer gate:
  - reviewer:
  - review 範囲:
  - pass 条件: review_status: pass
  - re-review rule: 指摘を修正し pass まで再実行
- commit / no-op gate:
  - closure 状態: committed / approved-no-op
  - commit 範囲:
  - no-op の場合の確認対象、差分なし確認コマンド、read-only evidence:

### Sxx — <next observable behavior>
- S01 の subsections を複製して記入する。
- `planned contract`、`delegation contract`、`具体テストケース一覧`、`step closure contract`、`step gate` がない implementation step は implementation-ready ではない。

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
  - 範囲: Issue 全体の obligation coverage と integration test 要否
  - pass 条件: reviewer pass
- final code review ゲート:
  - reviewer: code-reviewer
  - 範囲: issue-wide integrated diff、構造、責務境界、回帰リスク、保守性
  - pass 条件: review_status: pass
- final spec review ゲート:
  - reviewer: spec-reviewer
  - 範囲: requirement / design / plan / report / implementation / tests / docs 整合
  - pass 条件: reviewer pass
- final commit gate:
  - commit 範囲:
  - final report ledger:
  - post-commit external evidence destination:

## 未確定事項
- Q-001:
  - 質問:
  - 推奨案:
  - 影響範囲:

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
