# phase playbook: plan (issue)

Issue plan の playbook です。
shared axiom は [phase_plan.md](phase_plan.md)、Issue の lifecycle / execution / reviewer / completion policy は [workflow_issue.md](workflow_issue.md)、Issue plan の field semantics と executable step schema は [authoring/issue-plan.md](authoring/issue-plan.md) を参照します。
この文書は field-level template manual ではなく、Issue plan をどう設計し、どう review するかに集中します。

## scope contract

- plan の単位: milestone / step / block / behavior slice / quality gate
- plan の責務: issue requirement / design と `workflow_issue.md` の policy を、依存順に基づく実行順、review / QA / spec gate、docs impact、三者 final quality gate を持つ `plan.md` に変換する
- plan は planned contract であり、実装者が step を上から順に実行できる command queue として書く
- report は observed evidence ledger であり、実行結果、逸脱、discovered tests、reviewer verdict、commit/no-op evidence は `report.md` に残す
- plan が固定するもの:
  - 満たす要件 ID
  - milestone
  - step 一覧
  - 要件 ↔ step 対応
  - review / QA / spec gate 方針
  - 依存関係から導いた step 順
  - nested execution structure
  - per-step delegation contract
  - risk-calibrated test obligation coverage
  - docs impact gate
  - final quality gate with `qa-reviewer` / issue-wide `code-reviewer` / `spec-reviewer`
  - final exit contract

## authoring philosophy

- `workflow_issue.md` が所有する `1 step = 1 observable behavior` invariant を behavior slice 設計へ落とす
- `block` は optional concern group とし、単純な step では最小 wrapper 1 個でよい
- `behavior slice` は 1 つの観測可能な振る舞いを実装・検証・レビューできる単位とする
- 完成版 Issue plan には `Spec-Locked Closure Index`（仕様固定クロージャ索引）を置き、仕様由来の `spec link`、`locked expectation`、`observable input/state`、`bug class guarded`、`required`、`evidence level`、closure owner step を固定する
- `Spec-Locked Closure Index` は Issue 全体のテスト実装詳細ではなく、behavior slice / step が満たすべき仕様ロックと closure traceability を固定する coverage ledger とする
- テスト十分性は raw count ではなく、AC / EC、changed contract、negative / error path、regression、invariant、manual / integration risk に基づく risk-calibrated obligation coverage で判断する
- public CLI behavior、shipped scaffold / runtime contract、template / system docs の互換性、installer / update / migration、filesystem / GitHub / active store、negative path、既存 regression、複数 Agent 並列実装の領域では、step-local obligation と planned verification evidence を厚くする
- 低リスク docs-only / inspect-only step は code test を義務化しないが、inspection、structural assertion、manual evidence、docs diff などの代替 evidence path と rationale を step-local に固定する
- required row の削除、`locked expectation` の変更、`required` の変更、`spec link` の意味変更は plan amendment と re-review を必須にする
- typo / link correction は `report.md` の `Closure Delta` に記録してよい。新規 bug による regression 追加は Central index と step closure contract へ追加し、report に記録する
- 各 implementation step は commit 単位として設計し、`1 implementation step = 1 review scope = 1 commit` を標準にする。step が大きすぎる場合は commit をまとめず step を分割する
- review / QA / docs / final quality gate は behavior slice の外に置き、step gate / milestone gate / `S90` / `S99` に配置する
- `refactor / tidy` は bounded decision point として残し、事前に詳細な cleanup task を書き込まない
- cleanup が最初から明確で大きい場合は、`bounded implementation batch` / design / 別 step で扱う
- step 順は `design.md` の `依存関係分析`、`Module Dependency Diagram`、`ディレクトリ / ファイル変更計画` から導き、upstream / prerequisite / lower-dependency から先に置く
- templates は最小 scaffold であり、Issue 固有の実行順・依存・検証に不要な placeholder は削除してよい
- cadence、approval policy、reviewer gate mapping、completion policy の正本は `workflow_issue.md` に残し、この文書では plan 本文への埋め込み方だけを扱う

## schema routing

- `authoring/issue-plan.md` が所有するもの:
  - executable step schema
  - `delegation contract` の field semantics
  - `具体テストケース一覧` の card schema
  - docs-only / inspect-only / manual-required の書き方
  - reviewer fail 条件
- `workflow_issue.md` が所有するもの:
  - lifecycle command
  - execution order
  - parent / delegation invariant
  - reviewer gate mapping
  - completion policy
- `templates/issue/plan.md` が所有するもの:
  - copyable minimal scaffold
  - required headings
  - issue-local example shape
- `templates/issue/report.md` が所有するもの:
  - observed evidence ledger
  - closure delta
  - reviewer and commit evidence

## entry focus

- AC / EC / constraints が requirement で固定されている
- 変更点、境界、verification strategy、依存関係分析、module dependency diagram、directory / file change plan が design にある
- 実行前に review / QA / docs impact の位置が決まっている

## authoring checklist

- `この計画で満たす要件ID` を先に固定する
- `マイルストーン一覧` を必要に応じて置く
- `依存関係から導く実装順序` を上流で置く
- 各 step の `depends on` / `unblocks` / `target files` を置く
- `ステップ一覧` と `要件 ↔ ステップ対応` を置く
- `レビュー / QA ゲート方針` を置く
- `Spec-Locked Closure Index` を置く
- `実装ステップ` を step / block / behavior slice で書く
- 各 behavior slice の planned obligation、pre-implementation evidence、bounded implementation batch、verification evidence path、report evidence destination、amendment trigger を置く
- 各 implementation step に `delegation contract` を置き、`workflow_issue.md` の execution policy を再定義せずに worker handoff へ必要な入力、許可範囲、禁止範囲、検証、reviewer focus、停止条件、出力を具体化する
- 各 implementation step に `具体テストケース一覧` を置く。これは完全な test inventory ではなく、step-local obligation と concrete red / characterization / inspect / manual seeds を実装前に固定する欄である
- `refactor / tidy` には `目的` と `guardrail` を置き、具体的な refactor 内容は `report.md` へ送る
- 各 step gate に `step reviewer gate`、`commit gate`、`no-op gate`、`report update` を置き、reviewer は `workflow_issue.md` の mapping に従って選ぶ
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
- every `required=yes` closure row が少なくとも 1 つの behavior slice の closure contract から参照されている
- every required row が non-placeholder の `spec link`、`observable input/state`、`locked expectation`、`evidence level`、`closure evidence` を持つ
- every required row に step-local close condition と planned verification evidence path がある
- test obligation が raw count ではなく risk-calibrated obligation coverage として説明されている
- behavior slice が planned obligation、pre-implementation evidence、bounded implementation batch、verification evidence path、report evidence destination、amendment trigger を持ち、planned contract として実行できる
- 各 implementation step が `delegation contract` を持ち、step 固有の worker handoff contract として書かれている
- reviewer focus が step の変更種別と矛盾する場合、または delegated worker work を reviewer gate の代替として扱っている場合は fail とする
- 各 implementation step が step-local な `具体テストケース一覧` を持つ。完全な issue-wide inventory ではなく、実装前に固定する concrete seeds と alternative evidence path を確認できる
- concrete test case が横長 table に押し込まれて読みづらい場合、または global test plan だけで step-local case がない場合は fail とする
- docs-only / approved-no-op step は、テスト不要理由と inspection / manual / docs diff などの代替検証方法を持つ
- 各 implementation step が commit 単位として設計され、`step reviewer gate`、`commit gate`、`no-op gate` を持っている
- step 順が design の依存関係分析、Module Dependency Diagram、directory / file change plan と矛盾しない
- 各 step の `depends on` / `unblocks` / `target files` が、実装順と変更対象の確認に使える
- report update が stage gate に置かれている。report-before-commit、step reviewer gate pass、step commit、approved-no-op の実行順は `workflow_issue.md` の実行 contract で確認する
- AC / EC と step の対応が取れている
- docs impact と final quality gate が計画に埋め込まれ、`doc-writer` による必要 docs 更新、`qa-reviewer`、issue-wide `code-reviewer`、`spec-reviewer` の三者 review が追跡できる
- reviewer が「この plan で実装してよい」と判断できる
