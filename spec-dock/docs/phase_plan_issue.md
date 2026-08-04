# 課題計画フェーズ playbook（phase playbook: plan / issue）

Issue plan の playbook です。
shared axiom は [phase_plan.md](phase_plan.md)、Issue の lifecycle / execution / reviewer / completion policy は [workflow_issue.md](workflow_issue.md)、Issue plan の field semantics と executable step schema は [authoring/issue-plan.md](authoring/issue-plan.md)、scope ownership と authority flow は [authoring/scope-layering.md](authoring/scope-layering.md) を参照します。
Operational entrypoint / first-read spine は `spec-dock-issue-planning` skill です。この文書は skill から到達する detail / reference surface として、field-level template manual ではなく、Issue plan をどう設計し、どう review するかに集中します。

## 範囲契約（scope contract）

- plan の単位: milestone / step / block / behavior slice / quality gate
- plan の責務: issue requirement / design と `workflow_issue.md` の policy を、依存順に基づく実行順、review / QA / spec gate、docs impact、三者最終品質ゲート（final quality gate）を持つ `plan.md` に変換する
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
  - `qa-reviewer` / issue-wide `code-reviewer` / `spec-reviewer` による最終品質ゲート（final quality gate）
  - final exit contract

## 作成方針（authoring philosophy）

- `workflow_issue.md` が所有する `1 step = 1 observable behavior` invariant を behavior slice 設計へ落とす
- Issue-local plan は親 scope の目的、責務境界、Issue handoff boundary を再定義しない。Epic から渡された Issue-local `draft-design` / `draft-plan` は evidence として採否判断し、Canonical Issue `design.md` / `plan.md` へ採用する場合だけ本文化する
- Option 3+ の draft-adoption では、Issue planning が current repository state、prior completed Issues、dependency state、unresolved report ledger を確認してから canonical docs を正式化する。draft-only / validation-only / raw ChatGPT output は execution-ready ではない。
- `block` は optional concern group とし、単純な step では最小 wrapper 1 個でよい
- `behavior slice` は 1 つの観測可能な振る舞いを実装・検証・レビューできる単位とする
- Epic から Issue へ切る場合、各 Issue は `vertical behavior slice` として、利用者価値または運用上観測できる 1 つの振る舞いを thin end-to-end に閉じる。DB / API / UI / docs のような層別作業だけで切る `horizontal batching` は避け、層別作業が必要な場合も最初に薄い縦の完了点を置く
- Issue の `dependency order` は、設計上の prerequisite、public contract、データ / runtime 互換性、review gate を根拠に upstream から downstream へ並べる。依存関係が循環する場合は、先に `vertical tracer bullet` を置いて interface と verification path を確かめてから後続 Issue に広げる
- 複数 Issue にまたがる Epic では、各 vertical slice の後または依存境界の節目に `integration checkpoint` を置き、provider asset、dogfooding workspace、tests / manual evidence、docs impact のどれで統合状態を確認するかを plan または Epic plan に明記する
- `HITL` / `AFK` は Issue slicing の annotation として、人間判断が必要な境界、または agent が自律実行しやすい範囲を示す。これは approval、reviewer pass、plan readiness、GitHub label readiness の代替ではない
- 完成版 Issue plan には仕様固定クロージャ索引（`Spec-Locked Closure Index`）を置き、仕様由来の `spec link`、`locked expectation`、`observable input/state`、`bug class guarded`、`required`、`evidence level`、closure owner step を固定する
- 仕様固定クロージャ索引（`Spec-Locked Closure Index`）は Issue 全体のテスト実装詳細ではなく、behavior slice / step が満たすべき仕様ロックと closure traceability を固定する coverage ledger とする
- テスト十分性は raw count ではなく、AC / EC、changed contract、negative / error path、regression、invariant、manual / integration risk に基づく risk-calibrated obligation coverage で判断する
- TDD step は private method や内部分解ではなく、`public interface / observable behavior` を固定する first test、または docs-only なら first inspection target から始める。実装は `one test -> minimal implementation` の小さな cycle で進め、最初の Green は `vertical tracer bullet` として end-to-end の観測点を通す
- TDD plan は完全な test inventory ではなく、step-local concrete seeds と verification path を固定する。層ごとの作業をまとめてから最後に検証する `horizontal batching` に見える場合は、behavior slice、test obligation、integration checkpoint を分割し直す
- public CLI behavior、shipped scaffold / runtime contract、template / system docs の互換性、installer / update / migration、filesystem / GitHub / active store、negative path、既存 regression、複数 Agent 並列実装の領域では、step-local obligation と planned verification evidence を厚くする
- 低リスク docs-only / inspect-only step は code test を義務化しないが、inspection、structural assertion、manual evidence、docs diff などの代替 evidence path と rationale を step-local に固定する
- required row の削除、`locked expectation` の変更、`required` の変更、`spec link` の意味変更は plan amendment と re-review を必須にする
- typo / link correction は `report.md` のクロージャ差分（`Closure Delta`）に記録してよい。新規 bug による regression 追加は中央索引（central index）と step クロージャ契約（step closure contract）へ追加し、report に記録する
- テンプレート内の連番項目は例示であり、目的に応じて必要な数だけ追加・削除してよい。`XXX` placeholder がある場合は、作成時に実IDへ置換するか削除する
- `standard` / `strict` / `critical` の plan では、マイルストーン完了ゲートに `commit候補` を置き、レビュー可能な履歴を残す。review scope と commit scope は一致してもよいが、常に完全一致するとは定義しない
- review / QA / docs / 最終品質ゲート（final quality gate）は behavior slice の外に置き、step gate / milestone gate / `S90` / `S99` に配置する
- `refactor / tidy` は bounded decision point として残し、事前に詳細な cleanup task を書き込まない
- cleanup が最初から明確で大きい場合は、`bounded implementation batch` / design / 別 step で扱う
- step 順は `design.md` の `依存関係分析`、`Module Dependency Diagram`、`ディレクトリ / ファイル変更計画` から導き、upstream / prerequisite / lower-dependency から先に置く
- templates は最小 scaffold であり、Issue 固有の実行順・依存・検証に不要な placeholder は削除してよい
- cadence、approval policy、reviewer gate mapping、completion policy の正本は `workflow_issue.md` に残し、この文書では plan 本文への埋め込み方だけを扱う

## グレード補足（issue grade guidance）

Issue plan は [workflow_spec_authoring.md](workflow_spec_authoring.md) の `グレード別authoring matrix（Issue grade authoring matrix）` と `authorized_profile` を入口にします。manual escalation は plan の reviewer / QA / evidence gate を強める補助判断であり、`authorized_profile` を置き換えません。

- Lite は default ではない。Lite plan は低リスク根拠、軽量完了条件、docs-only / inspect-only の代替 evidence を持つ場合だけ使う。
- unknown / ambiguous な Issue、または実装影響、検証 obligation、reviewer gate が判断できない Issue は Standard 以上として計画する。
- Standard では `implementation-planner` などの planning specialist 使用を推奨する。使わない場合は、manual authoring の根拠、skip reason、確認した source、残リスクを `report.md` に残す。
- Strict / Critical では planning specialist を原則必須にする。specialist が unavailable / denied / host conflict の場合は、manual fallback evidence として利用不可理由、代替 planning evidence、step / closure / reviewer gate の妥当性を `report.md` に残す。
- `draft routing`、`report evidence gate`、`integrated smoke matrix` は後続 G2 / G3 / G4 の stable term として扱い、この文書では plan 上の参照語に留める。runtime routing、report validation、smoke matrix 実装はここで定義しない。

## スキーマ routing の方針（schema routing）

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

## 入場 focus（entry focus）

- AC / EC / constraints が requirement で固定されている
- 変更点、境界、verification strategy、依存関係分析、module dependency diagram、directory / file change plan が design にある
- 実行前に review / QA / docs impact の位置が決まっている

## 作成 checklist 項目（authoring checklist）

- `この計画で満たす要件ID` を先に固定する
- `マイルストーン一覧` を必要に応じて置く
- `依存関係から導く実装順序` を上流で置く
- 各 step の `depends on` / `unblocks` / `target files` を置く
- `ステップ一覧` と `要件 ↔ ステップ対応` を置く
- `レビュー / QA ゲート方針` を置く
- 仕様固定クロージャ索引（`Spec-Locked Closure Index`）を置く
- `実装ステップ` を step / block / behavior slice で書く
- Epic -> Issue slicing が必要な場合は、各 Issue の `vertical behavior slice`、`dependency order`、`integration checkpoint`、`HITL` / `AFK` annotation を plan 上で追跡できるようにする
- 各 behavior slice の planned obligation、pre-implementation evidence、bounded implementation batch、verification evidence path、report evidence destination、amendment trigger を置く
- 各 implementation step に `delegation contract` を置き、`workflow_issue.md` の execution policy を再定義せずに worker handoff へ必要な入力、許可範囲、禁止範囲、検証、reviewer focus、停止条件、出力を具体化する
- 各 implementation step に `具体テストケース一覧` を置く。これは完全な test inventory ではなく、step-local obligation と concrete red / characterization / inspect / manual seeds を実装前に固定する欄である
- `具体テストケース一覧` の first case は `public interface / observable behavior` を観測するものにし、必要なら `vertical tracer bullet` として最小の end-to-end Green を先に置く。private method 先行や `horizontal batching` だけの plan になっていないか確認する
- `refactor / tidy` には `目的` と `guardrail` を置き、具体的な refactor 内容は `report.md` へ送る
- 各 step / milestone gate に reviewer gate、`commit候補` または no-op 判定、`report update` を置き、reviewer は `workflow_issue.md` の mapping に従って選ぶ
- `S90 docs 影響解決 / docs 更新（S90 docs impact resolution / docs refresh）` を必須で置く
- `S99 最終品質ゲート（S99 final quality gate）` を必須で置き、`qa-reviewer` のテスト十分性確認、issue-wide `code-reviewer` の統合 diff review、`spec-reviewer` の要件達成確認を配置する
- `final exit contract` を置く

## 図表 / trace 指針（diagram / trace guidance）

- 仕様固定クロージャ索引（`Spec-Locked Closure Index`）は必須で置き、必要な場合だけ step dependency graph、追加の decision table、rollback map を置く
- 図表は `実装順序の根拠`、`要件 ↔ ステップ対応`、review / QA gate の理解を助ける用途に限定する
- 新しい設計判断や未承認 requirement を図表で追加しない
- step dependency graph を置く場合は、design の `Module Dependency Diagram` と矛盾しないようにする

## レビューゲート（review gate）

- step 粒度で review / test / report 判断を回せる
- 仕様固定クロージャ索引（`Spec-Locked Closure Index`）が AC / EC / design / bug / risk と behavior slice の closure contract を固定している
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
- `standard` 以上では主要マイルストーンが `commit候補` または no-op 判定を持ち、`lite` では途中 commit を前提にしない軽量完了条件になっている
- step 順が design の依存関係分析、Module Dependency Diagram、directory / file change plan と矛盾しない
- 各 step の `depends on` / `unblocks` / `target files` が、実装順と変更対象の確認に使える
- report update が stage gate に置かれている。report-before-commit、step reviewer gate pass、step / milestone result approval、approved-no-op の実行順は `workflow_issue.md` の実行 contract で確認する
- AC / EC と step の対応が取れている
- docs impact と最終品質ゲート（final quality gate）が計画に埋め込まれ、`doc-writer` による必要 docs 更新、`qa-reviewer`、issue-wide `code-reviewer`、`spec-reviewer` の三者 review が追跡できる
- delegated plan draft を使う場合、lightweight provenance、fresh requirement/design reviewer pass、approved artifacts への traceability、stale / superseded handling、scope discipline、phase gate preservation が確認できる
- delegated draft を fresh `spec-reviewer` pass、step reviewer gate、final QA/code/spec gate の代替にしていない
- read-only specialist consent と scope-local artifact direct-write consent が分離され、direct-write delegated authoring は target scope `artifacts/` direct child、allowed filename rule、forbidden canonical/implementation paths、post-run diff guard、report evidence destination を step-local に固定している
- implementation planner が direct-write draft authoring を使う場合でも、出力は scope-local flat artifact Markdown に限られ、canonical `plan.md` edit、final authority、phase promotion、reviewer-pass claim、requirement/design rewrite、implementation-readiness claim、完了済み issue plan/report の修正を含まない
- static adapter は guarded workspace-write で scope-local `artifacts/` Markdown draft を作成し、workspace-write が hard path allow-list ではない前提で delegated plan authoring output は invocation scope、diff guard pass、report ledger adoption evidence が揃うまで adoption-ineligible として扱われている
- delegated authoring unavailable / skipped の場合も manual authoring path が有効である
- reviewer が「この plan で実装してよい」と判断できる
