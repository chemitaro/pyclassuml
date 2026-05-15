# phase playbook: plan (issue)

Issue plan の playbook です。
shared axiom は [phase_plan.md](phase_plan.md)、Issue の execution policy は [workflow_issue.md](workflow_issue.md) を参照します。
この文書は policy の再定義ではなく、Issue plan をどう書くかに集中します。

## scope contract

- plan の単位: milestone / step / block / behavior slice / quality gate
- plan の責務: issue requirement / design と `workflow_issue.md` の policy を、依存順に基づく実行順、review / QA / spec gate、docs impact、三者 final quality gate を持つ `plan.md` に変換する
- plan が固定するもの:
  - 満たす要件 ID
  - milestone
  - step 一覧
  - 要件 ↔ step 対応
  - review / QA / spec gate 方針
  - 依存関係から導いた step 順
  - nested execution structure
  - docs impact gate
  - final quality gate with `qa-reviewer` / issue-wide `code-reviewer` / `spec-reviewer`
  - final exit contract

## authoring rules

- `workflow_issue.md` が所有する `1 step = 1 observable behavior` invariant を behavior slice 設計へ落とす
- `block` は optional concern group とし、単純な step では最小 wrapper 1 個でよい
- `behavior slice` は 1 つの観測可能な振る舞いを実装・検証・レビューできる単位とする
- 完成版 Issue plan には `Spec-Locked Closure Index`（仕様固定クロージャ索引）を必須で置く
- `Spec-Locked Closure Index` は Issue 全体のテストケース一覧ではなく、behavior slice / step が満たすべき仕様ロックと closure の traceability を固定する coverage ledger とする
- central index の基本列は `id`、`phase / step`、`slice`、`type`、`spec link`、`locked expectation`、`observable input/state`、`bug class guarded`、`required`、`evidence level`、`closure evidence` とする
- `evidence level` は `red-required`、`covered-existing`、`inspect-only`、`manual-required` のいずれかを使い、すべての row に failing test を要求しない
- central index では private method、実装アルゴリズム、mock 構造、assert 細部を原則固定しない
- 通常 Issue は step / behavior slice ごとに 1〜3 件程度の closure contract を書き、高リスク surface だけ詳細化する
- public CLI behavior、shipped scaffold / runtime contract、template / system docs の互換性、installer / update / migration、filesystem / GitHub / active store、negative path、既存 regression、複数 Agent 並列実装の領域では step-local closure contract を詳細化する
- 各 behavior slice には closure index の `id` に対応する `step closure contract`、`test bundle`、`pre-implementation evidence`、`bounded implementation batch`、`verification`、`refactor / tidy` を置く
- Central index は仕様由来の `spec link`、`locked expectation`、`observable input/state`、`bug class guarded`、`required`、`evidence level`、closure owner step を所有する
- `step closure contract` はその step で満たす closure `id`、close condition、test bundle、pre-implementation evidence、verification command / evidence path、report evidence を所有する
- `test bundle` は step closure contract の一部として、必要な範囲で acceptance / characterization / property or invariant / regression / negative を分類する
- `test ids` と書く場合も Central index の closure `id` の alias として扱い、別 alias を使う場合は report の `Closure Delta` に `test id alias` と `resolves to closure id` を記録する
- `test bundle` は Central index の `locked expectation` / `observable input/state` を再記述しない
- required row の削除、`locked expectation` の変更、`required` の変更、`spec link` の意味変更は plan amendment と re-review を必須にする
- typo / link correction は `report.md` の `Closure Delta` に記録してよい。新規 bug による regression 追加は Central index と step closure contract へ追加し、report に記録する
- `test bundle` は必要な範囲で acceptance / characterization / property or invariant / regression / negative を分類する
- 各 implementation step は `具体テストケース一覧` を必須で持つ。これは TDD 実行入力であり、`Spec-Locked Closure Index` や `test bundle` の代替ではない
- `具体テストケース一覧` は PC の Markdown preview / GitHub 表示で読みやすいカード型ネストリストを標準にする。横長 table は trace matrix や短い index に限定し、1ケースの本文を table に押し込まない
- 各 concrete test case は top-level bullet を ``- `tc-s01-001` acceptance: <短い説明>`` の形にし、下位項目として `前提`、`操作`、`期待結果`、`失敗検出`、`検証方法` を持つ
- concrete test case id は検索できるように各 concrete test case の先頭へ backtick 付きで置く。これは Central index の closure `id` や `test ids` alias とは別物であり、必要な場合だけ `関連 closure id` で紐付ける
- docs-only / approved-no-op step で concrete test case を置かない場合は、テスト不要理由と代替検証方法を `具体テストケース一覧` に明記する
- `具体テストケース一覧` がない implementation step、または「テストを追加する」「動作確認する」だけの抽象表現は implementation-ready ではない
- `pre-implementation evidence` は expected red / characterization pass / test sensitivity evidence のいずれかを明記する
- `test sensitivity evidence` は failing-first を完全要求できない場合に、bug-seed / mutation / contract mismatch / property violation などでテストが欠陥を検出できることを示す
- 各 step の close 判定は Issue 全体の一覧表ではなく、その step の `step closure contract` を正本にする
- `step closure contract` は `close when`、`verification evidence`、`report evidence`、`residual risk` を持ち、step result approval の対象にする
- 各 implementation step は commit 単位として設計し、`1 implementation step = 1 review scope = 1 commit` を標準にする。step が大きすぎる場合は commit をまとめず step を分割する
- 各 step gate には `code-reviewer gate`、`commit gate`、`no-op gate` を置き、`code-reviewer` pass 後に step commit で閉じる。`approved-no-op` は差分なしの場合だけ許可する
- review / QA / docs / final quality gate は behavior slice の外に置き、step gate / milestone gate / `S90` / `S99` に配置する
- `refactor / tidy` は bounded decision point として残し、事前に詳細な cleanup task を書き込まない
- cleanup が最初から明確で大きい場合は、`bounded implementation batch` / design / 別 step で扱う
- step 順は `design.md` の `依存関係分析`、`Module Dependency Diagram`、`ディレクトリ / ファイル変更計画` から導き、upstream / prerequisite / lower-dependency から先に置く
- 各 step には `depends on`、`unblocks`、`design refs`、`target files` を置き、依存関係と変更対象を追えるようにする
- `design.md` の `ディレクトリ / ファイル変更計画` を canonical path inventory とし、plan の `target files` は各 step が触る subset として書く
- templates は最小 scaffold であり、Issue 固有の実行順・依存・検証に不要な placeholder は削除してよい
- stage gate は `pass` まで回す
- stage gate の `pass` 後は `report.md` を更新する。各 implementation step の commit/no-op は `workflow_issue.md` の実行 contract が所有するが、plan には step 固有の review scope、commit scope、no-op 条件を明記する
- `S90 docs impact resolution / docs refresh` は標準配置し、docs / templates / README / workflow / skill / migration notes の影響を確認する。docs 更新が必要な場合は `doc-writer` が修正し、`spec-reviewer` が docs と requirement / design / plan の整合を確認する
- `S99 final quality gate` は標準配置し、`qa-reviewer`、issue-wide `code-reviewer`、`spec-reviewer` の三者 review をすべて `pass` まで回す。final quality gate は step review の代替ではなく、issue 全体の統合確認として扱う
- cadence や approval policy の正本は `workflow_issue.md` に残し、この文書では plan 本文への埋め込み方だけを扱う

## entry focus

- AC / EC / constraints が requirement で固定されている
- 変更点、境界、verification strategy、依存関係分析、module dependency diagram、directory / file change plan が design にある
- 実行前に review / QA / docs impact の位置が決まっている

## authoring checklist

- `この計画で満たす要件ID` を先に固定する
- `マイルストーン一覧` を置く
- `依存関係から導く実装順序` を上流で置く
- 各 step の `depends on` / `unblocks` / `target files` を置く
- `ステップ一覧` と `要件 ↔ ステップ対応` を置く
- `レビュー / QA ゲート方針` を置く
- `Spec-Locked Closure Index` を置く
- `実装ステップ` を step / block / behavior slice で書く
- 各 behavior slice の `step closure contract` / `test bundle` / `pre-implementation evidence` / `bounded implementation batch` / `verification` を置き、`test bundle` は closure index の `id` を参照できるようにする
- 各 implementation step に `具体テストケース一覧` を置き、ネストリストで `前提` / `操作` / `期待結果` / `失敗検出` / `検証方法` を書く
- `refactor / tidy` には `目的` と `guardrail` を置き、具体的な refactor 内容は `report.md` へ送る
- 各 step gate に `code-reviewer gate`、`commit gate`、`no-op gate`、`report update` を置く
- `S90 docs impact resolution / docs refresh` を必須で置く
- `S99 final quality gate` を必須で置き、`qa-reviewer` のテスト十分性確認、issue-wide `code-reviewer` の統合 diff review、`spec-reviewer` の要件達成確認を配置する
- `final exit contract` を置く

## diagram / trace guidance

- `Spec-Locked Closure Index` は必須で置き、必要な場合だけ step dependency graph、追加の decision table、rollback map を置く
- 図表は `実装順序の根拠`、`要件 ↔ ステップ対応`、review / QA gate の理解を助ける用途に限定する
- 新しい設計判断や未承認 requirement を図表で追加しない
- step dependency graph を置く場合は、design の `Module Dependency Diagram` と矛盾しないようにする

## review gate

- step 粒度で review / test / report 判断を回せる
- `Spec-Locked Closure Index` が AC / EC / design / bug / risk と behavior slice の closure contract を固定している
- central index がテスト実装詳細ではなく、観測可能な入力・状態・locked expectation・防ぐ欠陥クラスを示している
- every `required=yes` closure row が少なくとも 1 つの behavior slice の `closure ids` / `test ids` から参照されている
- every bundle `closure id` が Central index に存在し、別の `test id` alias を使う場合は `Closure Delta` から Central index の closure `id` へ解決できる
- every required row が non-placeholder の `spec link`、`observable input/state`、`locked expectation`、`evidence level`、`closure evidence` を持つ
- every required row に step-local close condition と planned verification evidence path がある
- behavior slice が step closure contract、test bundle、pre-implementation evidence を持ち、bounded implementation batch として原因局所化できる
- 各 implementation step が step-local な `具体テストケース一覧` を持ち、各 case が `前提`、`操作`、`期待結果`、`失敗検出`、`検証方法` を含む
- concrete test case が横長 table に押し込まれて読みづらい場合、または global test plan だけで step-local case がない場合は fail とする
- docs-only / approved-no-op step は、テスト不要理由と inspection / manual / docs diff などの代替検証方法を持つ
- 各 implementation step が commit 単位として設計され、`code-reviewer gate`、`commit gate`、`no-op gate` を持っている
- step 順が design の依存関係分析、Module Dependency Diagram、directory / file change plan と矛盾しない
- 各 step の `depends on` / `unblocks` / `target files` が、実装順と変更対象の確認に使える
- report update が stage gate に置かれている。report-before-commit、code-reviewer pass、step commit、approved-no-op の実行順は `workflow_issue.md` の実行 contract で確認する
- AC / EC と step の対応が取れている
- docs impact と final quality gate が計画に埋め込まれ、`doc-writer` による必要 docs 更新、`qa-reviewer`、issue-wide `code-reviewer`、`spec-reviewer` の三者 review が追跡できる
- reviewer が「この plan で実装してよい」と判断できる
