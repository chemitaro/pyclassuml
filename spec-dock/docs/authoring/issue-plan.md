# authoring: issue plan

Issue の `plan.md` を作成・更新するときの agent-facing entrypoint です。
共通正本は `workflow_spec_authoring.md`、`phase_plan.md`、`phase_plan_issue.md`、`workflow_issue.md` です。
この文書は Issue plan の field semantics と executable step schema の正本です。Lifecycle / execution / reviewer / completion policy は `workflow_issue.md`、plan philosophy と review checklist は `phase_plan_issue.md` を参照します。

## 読む順序

この文書を入口として読んだあと、次の共通正本へ進む。

1. `workflow_spec_authoring.md`
2. `phase_plan.md`
3. `phase_plan_issue.md`
4. `workflow_issue.md`
5. `templates/issue/plan.md`

## この artifact の責務

- reviewer-pass 済みの `requirement.md` と `design.md` を、実装可能な step、検証、review gate、commit gate、final quality gate へ変換する。
- `plan.md` を planned contract として扱い、実装者が step を上から順に実行できる command queue にする。
- `report.md` を observed evidence ledger として扱い、実際の Red / Green / Refactor 結果、discovered tests、closure delta、reviewer verdict、commit/no-op evidence の記録先にする。
- `Spec-Locked Closure Index` で仕様 coverage を固定し、各 implementation step の `具体テストケース一覧` で step-local obligation と concrete red / characterization / inspect / manual seeds を固定する。
- step 順、依存、対象ファイル、検証方法、report evidence destination、amendment trigger を実装者が判断せずに実行できる粒度へ落とす。
- `workflow_issue.md` の delegated-by-default policy を再定義せず、各 implementation step の `delegation contract` として委任先、入力、許可範囲、検証、reviewer focus、停止条件、出力を具体化する。

## planned contract / observed evidence ledger

- `plan.md` は planned executable workflow contract である。
  - behavior goal
  - scope / allowed paths / forbidden changes
  - risk-calibrated test obligation coverage
  - Red evidence requirement or justified alternative path
  - implementation scope
  - Green verification command or evidence path
  - refactor / cleanup guardrail
  - closure evidence requirements
  - report evidence destination
  - amendment trigger
- `report.md` は observed evidence ledger である。
  - actual Red / Green / Refactor evidence
  - actual verification result
  - observed deviations and discovered tests
  - closure delta and amendment history
  - delegated worker evidence
  - reviewer gate status
  - step commit / approved-no-op evidence
- `report.md` は `Spec Interpretation / Decision Ledger` も持つ。実行中に発生した material な仕様解釈、判断、plan 逸脱、tradeoff、open question、promotion / follow-up は report 側に記録し、`plan.md` を実行中判断の追記先にしない。
- `plan.md` は decision result を所有しない。将来も効く durable decision が実行中に見つかった場合は、report に evidence と disposition を残したうえで、必要に応じて `design.md`、ADR、plan amendment、follow-up issue へ昇格する。
- 実行中に見つかった新しい bug class、外部 contract risk、仕様差分が既存 plan obligation の範囲外なら、report に発見を残すだけで閉じず、plan amendment と re-review を先に行う。

## 必須項目

- `この計画で満たす要件ID`
- `依存関係から導く実装順序`
- `ステップ一覧`
- `要件 ↔ ステップ対応`
- `Spec-Locked Closure Index`
- 各 implementation step の `delegation contract`
- 各 implementation step の `具体テストケース一覧`
- 各 implementation step の `step closure contract`
- 各 implementation step の `behavior slice execution`
- 各 implementation step の `step gate`
- `S90 docs impact resolution / docs refresh`
- `S99 final quality gate`
- `Final Exit Contract`

## executable step schema

各 implementation step は、少なくとも次の意味を表現できる構造にする。

```text
Sxx behavior slice
|-- behavior goal
|-- planned contract
|   |-- scope
|   |-- test obligation
|   |-- red or alternative evidence requirement
|   |-- green verification
|   |-- refactor guardrail
|   `-- amendment trigger
|-- delegation contract
|-- 具体テストケース一覧
|-- step closure contract
|-- report evidence destination
`-- step gate
```

- `test obligation` は raw test count ではなく、AC / EC、changed contract、negative / error path、regression、invariant、manual / integration risk に基づく risk-calibrated obligation coverage として書く。
- `red or alternative evidence requirement` は `red-required`、`covered-existing`、`inspect-only`、`manual-required` のいずれかを使い、failing-first を完全要求できない場合も test sensitivity または代替 evidence path を固定する。
- docs-only / template-only / skill-text-only step は code test を無理に作らず、inspection、structural assertion、manual evidence、docs diff、spec-review evidence を planned verification として書く。
- `report evidence destination` は、実行結果を `report.md` のどの ledger に残すかを明示する。`plan.md` へ observed evidence を戻して正本を二重化しない。
- `amendment trigger` は、どの発見が report 記録だけで足りず plan amendment / re-review を必要にするかを示す。

## delegation contract

各 implementation step は、`workflow_issue.md` の `Parent Agent Invariant`、`Implementation Delegation Gate`、delegated worker handoff、reviewer gate mapping を参照し、その step 固有の handoff contract を持つ。
この欄は execution policy の再定義ではない。plan author は、worker が追加判断なしに作業でき、reviewer が scope / verification / report evidence を確認できるように、次の項目を step-local に埋める。

標準項目:

- `delegated role`:
  - runtime / CLI / infra / code / tests / scaffold behavior は `dev-coder`、shipped docs / templates / skills / workflow text は `doc-writer` を primary worker とする。
- `input docs`:
  - `requirement.md`、`design.md`、`plan.md`、該当 workflow / authoring docs、target files などの source of truth。
- `allowed paths`:
  - `design.md` の `ディレクトリ / ファイル変更計画` から、その step が触る subset。
- `forbidden changes`:
  - scope 外ファイル、別 step の変更、source-of-truth 逸脱、runtime と docs の不用意な混在など。
- `acceptance criteria`:
  - closure index と step closure contract へ追跡できる、観測可能な完了条件。
- `required tests or docs-only verification`:
  - targeted command、manual evidence、inspection、docs diff など、その step の検証方法。
- `reviewer focus`:
  - `workflow_issue.md` の mapping に従い、code / runtime / tests / scaffold behavior は `code-reviewer`、docs-only / template-only / skill-text-only は `spec-reviewer` docs/spec alignment を基本にする。
- `stop conditions`:
  - 入力 docs の矛盾、許可パス外変更が必要、検証不能、delegated role 不適合、host policy / tool 制約、acceptance 未達など。
- `output required`:
  - changed files、worker summary、verification result、unresolved risks、report へ転記する delegation evidence。
  - `Ledger Note` または `No material implementation decisions beyond the approved plan.`。
  - `Ledger Note` は worker の一次情報であり accepted decision ではない。material な仕様解釈、判断、逸脱、tradeoff、open question、follow-up がある場合は、source-agent、topic、trigger、ambiguity / constraint、observed facts、options considered、proposed decision、rationale、affected files、affected tests、risk if wrong、rollback or revisit、confidence、needs orchestrator decision を含める。

複数 layer / package / shipped asset にまたがる step は、親 Codex が直接実装せず、allowed paths と dependency boundary を明記して委任する。docs-only / template-only / skill-text-only step であっても、shipped artifact を変更する場合は `doc-writer` 委任と docs/spec alignment review を plan に残す。

## 具体テストケース一覧

各 implementation step は、PC の Markdown preview / GitHub 表示で読みやすいカード型のネストリストで具体テストケースを書く。横長テーブルに押し込まない。
この見出しは完全な test inventory ではない。step 開始前に実装を後付けにしないための concrete red / characterization / inspect / manual seeds と、risk-calibrated obligation coverage への対応を固定する欄である。
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
- implementation step に `delegation contract` がない、または `delegated role`、`input docs`、`allowed paths`、`forbidden changes`、`acceptance criteria`、`required tests or docs-only verification`、`reviewer focus`、`stop conditions`、`output required` のいずれかが欠けている。
- `delegation contract` が `workflow_issue.md` と矛盾する execution policy を再定義している。
- delegated worker work を reviewer gate の代替として扱っている、または step の変更種別と reviewer focus が矛盾している。
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
