# authoring: issue plan

Issue の `plan.md` を作成・更新するときの agent-facing entrypoint です。
共通正本は `workflow_spec_authoring.md`、`phase_plan.md`、`phase_plan_issue.md`、`workflow_issue.md` です。この文書は、それらを Issue plan 作成時に読み落とさないための entrypoint です。

## 読む順序

この文書を入口として読んだあと、次の共通正本へ進む。

1. `workflow_spec_authoring.md`
2. `phase_plan.md`
3. `phase_plan_issue.md`
4. `workflow_issue.md`
5. `templates/issue/plan.md`

## この artifact の責務

- reviewer-pass 済みの `requirement.md` と `design.md` を、実装可能な step、検証、review gate、commit gate、final quality gate へ変換する。
- `Spec-Locked Closure Index` で仕様 coverage を固定し、各 implementation step の `具体テストケース一覧` で TDD 実行入力を固定する。
- step 順、依存、対象ファイル、検証方法、report evidence を実装者が判断せずに実行できる粒度へ落とす。

## 必須項目

- `この計画で満たす要件ID`
- `依存関係から導く実装順序`
- `ステップ一覧`
- `要件 ↔ ステップ対応`
- `Spec-Locked Closure Index`
- 各 implementation step の `具体テストケース一覧`
- 各 implementation step の `step closure contract`
- 各 implementation step の `behavior slice execution`
- 各 implementation step の `step gate`
- `S90 docs impact resolution / docs refresh`
- `S99 final quality gate`
- `Final Exit Contract`

## 具体テストケース一覧

各 implementation step は、PC の Markdown preview / GitHub 表示で読みやすいカード型のネストリストで具体テストケースを書く。横長テーブルに押し込まない。
ここで先頭に置く ID は concrete test case id であり、`Spec-Locked Closure Index` の closure `id` や `test ids` alias とは別物として扱う。step に複数の closure id または複数の concrete test case がある場合は、各 case に `関連 closure id` を置いて紐付ける。1 step = 1 closure id = 1 concrete case で対応が明らかな場合だけ省略してよい。

標準形:

```markdown
#### 具体テストケース一覧

- `tc-s01-001` acceptance: 作成後に自動 sync される
  - 前提: temp repo に GitHub issue 作成 stub があり、sync artifact は作成前の状態。
  - 操作: `spec-dock new issue --create-github-issue ...` を実行する。
  - 期待結果: 手動 `sync` なしで `.agent/index-all.json` と `dashboard.md` に新 issue が反映される。
  - 失敗検出: 作成は成功するが派生 artifact が stale のまま残る回帰を検出する。
  - 検証方法: `tests/cli_runtime/test_new.py` に red-first test を追加する。
  - 関連 closure id: `tc-001`

- `tc-s01-002` negative: 作成失敗時は post-sync しない
  - 前提: create preflight が失敗する不正な parent id を指定する。
  - 操作: `spec-dock new issue --epic missing ...` を実行する。
  - 期待結果: command は失敗し、post-sync は呼ばれず、既存 artifact は変化しない。
  - 失敗検出: mutation failure 後に sync が走り、artifact が意図せず更新される回帰を検出する。
  - 検証方法: `tests/cli_runtime/test_new.py` の failure-path test。
  - 関連 closure id: `tc-002`
```

## reviewer fail 条件

- implementation step に `具体テストケース一覧` がない。
- concrete test case が step-local ではなく、global test plan だけに置かれている。
- `前提`、`操作`、`期待結果`、`失敗検出`、`検証方法` のいずれかが欠けている。
- 「テストを追加する」「動作確認する」など、実装者が fixture / command / expected observation を判断する必要がある抽象表現だけになっている。
- 1ケースの本文が横長 table に押し込まれ、Markdown preview / GitHub 上で読みづらい。
- docs-only / approved-no-op step で、テスト不要理由と代替検証方法が明記されていない。

## 記法ルール

- 1つのテストケースは1つの top-level bullet にする。
- top-level bullet は ``- `tc-s01-001` acceptance: <短い説明>`` の形にし、先頭の backtick 付き ID は concrete test case id として扱う。
- 標準の下位項目は `前提`、`操作`、`期待結果`、`失敗検出`、`検証方法` の5つにする。
- 必要な場合だけ `対象ファイル`、`fixture`、`manual evidence` を追加する。
- `関連 closure id` は、step に複数の closure id または複数の concrete test case がある場合は必須にする。1 step = 1 closure id = 1 concrete case で対応が明らかな場合だけ省略してよい。
- 1項目が長くなりすぎる場合は2文までに抑え、詳細は `discussions/` または `report.md` に分離する。
- `Spec-Locked Closure Index` は coverage ledger なので table のままでよい。具体テストケース本文とは役割を分ける。
