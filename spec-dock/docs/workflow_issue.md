# workflow: issue（Agent-Native TDD）

Issue は実装の最小単位です。
この workflow は、active issue を入口にした仕様固定マイクロバッチTDD（Spec-Locked Micro-Batch TDD）、step review loop、docs impact、final quality gate を正本として扱います。
この workflow の品質ゲートは scope 固有の additive gate であり、`phase_*.md` の shared minimum gate 通過を前提とします。

対応 leaf skill:
- `.agents/skills/spec-dock-issue-execution/SKILL.md`

関連:
- 総合: [guide.md](guide.md)
- 仕様書作成: [workflow_spec_authoring.md](workflow_spec_authoring.md)
- Epic: [workflow_epic.md](workflow_epic.md)
- ADR: [workflow_adr.md](workflow_adr.md)
- GitHub 連携: [reference_github.md](reference_github.md)
- 共通 phase playbook: [phase_requirement.md](phase_requirement.md), [phase_design.md](phase_design.md), [phase_plan.md](phase_plan.md)
- Issue plan playbook: [phase_plan_issue.md](phase_plan_issue.md)

## 作成と issue start

```bash
# primary lifecycle
./spec-dock/scripts/spec-dock new issue --epic <epic-id> --title "..."
./spec-dock/scripts/spec-dock new issue --create-github-issue --epic <epic-id> --title "..."

./spec-dock/scripts/spec-dock import issue <num|#num|canonical-url> --title "..." [--epic <epic-id>]

./spec-dock/scripts/spec-dock issue start <issue-id|github-issue-number|url>
./spec-dock/scripts/spec-dock issue start <issue-id|github-issue-number|url> -f
./spec-dock/scripts/spec-dock issue finish

# manual / recovery only
./spec-dock/scripts/spec-dock active set <issue-id|github-issue-number|url>
./spec-dock/scripts/spec-dock active set --id <issue-id>
./spec-dock/scripts/spec-dock active set --github-issue <n>
./spec-dock/scripts/spec-dock active set <issue-id|github-issue-number|url> --checkout
./spec-dock/scripts/spec-dock active show

./spec-dock/scripts/spec-dock deps check <target>
./spec-dock/scripts/spec-dock deps add --from <issue-id> --to <issue-id>
./spec-dock/scripts/spec-dock deps remove --from <issue-id> --to <issue-id>
```

- `import issue` で `--epic` を省略した場合は current active から親 epic を解決する
- `import issue` の canonical URL は current repo と照合され、current repo を検証できない場合も含めて foreign GitHub issue URL は fail-closed で reject される
- `--allow-foreign-url` は compatibility flag として残るが、cross-repo node identity import の成功経路にはならない
- canonical でない URL-like target は受け付けない
- 通常の issue execution 開始は `./spec-dock/scripts/spec-dock issue start <target>` を primary path とし、active set と checkout を一操作で完了する
- `issue start` は unfinished active issue branch 上で別 issue を始めようとした場合だけ default で block する。`main` / `master` / `develop` / `staging` や non-issue branch からの start は block しない
- `./spec-dock/scripts/spec-dock issue start <target> -f` / `--force` は unfinished active issue guard だけを bypass する。依存未解決や他の readiness check は bypass しない
- 通常の issue 完了は `./spec-dock/scripts/spec-dock issue finish` を primary path とする。active issue の linked GitHub issue を close し、already-closed も success として扱い、その確認後に active state を解除する
`issue finish` is lifecycle closure only for delivery completion: it closes or confirms the linked GitHub issue, clears active state, and then runs lifecycle-owned post-mutation sync, but it still does not guarantee commit, push, PR, merge, validate, test, review, or final delivery completion; delivery completion still requires separate evidence in tests, reviews, reports, and PR/merge workflow.
- delivery completion の判定と required evidence の記録・確認は、`issue finish` の前に、active issue が set され対象 issue を確認できる状態で `spec-dock/active/issue/report.md` に対して行う
- `issue finish` 後は active issue が clear されていてよく、active issue が残っていること自体を `complete` condition にしてはならない
- `issue finish` の lifecycle-owned post-mutation sync は、active clear 後に post-mutation no-migrate / no branch-active-update policy で実行される。この自動 sync は、issue branch 上で finish した場合でも、直前に clear した active issue を復元してはならない
- manual `./spec-dock/scripts/spec-dock sync` は lifecycle-owned post-mutation sync とは別物である。人が後から issue branch 上で manual `sync` を実行した場合は、manual sync 側の policy が変わらない限り branch-derived active restoration の caveat が残り得る
- `active set` は manual / recovery command として維持する。unfinished active issue guard の対象外であり、必要時だけ direct に使う
- `active set` のデフォルトは no-checkout。ブランチ移動が必要な場合だけ `--checkout`
- `active set` は `<target>` の後方互換を維持しつつ、`--id` / `--github-issue` の explicit form も使える
- 依存未解決なら `active set` は通常失敗する。確認は `./spec-dock/scripts/spec-dock deps check <target>`
- 例外で進める場合だけ `./spec-dock/scripts/spec-dock active set <target> --force`
- 依存 edge の追加/削除は metadata を直編集せず `./spec-dock/scripts/spec-dock deps add --from <issue-id> --to <issue-id>` / `./spec-dock/scripts/spec-dock deps remove --from <issue-id> --to <issue-id>` を使う

## spec authoring

- active issue 配下の `requirement.md` / `design.md` / `plan.md` を埋める
- Requirement / design / plan の phase promotion は `workflow_spec_authoring.md` を正本にし、各 artifact ごとに fresh `spec-reviewer` の `review_status: pass` まで次 phase へ進めない
- `discussions/`: `new doc {adr|disc|research|note} --issue <issue-id> --title "..."` で、この issue の `discussions/` 配下に timestamp-prefixed original を作成する。標準形は `<ts>-<kind>-<slug>.md`、same-second collision は `<ts>-<nn>-<kind>-<slug>.md`。詳細 contract は [reference_naming.md](reference_naming.md) を参照する
- templates は完成形ではなく、書き始めるための最小 scaffold に留める。仕様書作成の説明や判断基準は docs / skills を参照する
- agent は、プロジェクトの目的、作業内容、人間の理解しやすさ、エージェントの実行可能性に合わせて、項目を追加・削除・統合・並べ替えてよい
- 不要な placeholder や該当しない節は削ってよいが、正確性、検証可能性、人間の理解、エージェントの実行に必要な情報は削らない
- テンプレートにない図表や節も、[phase_design.md](phase_design.md) の `optional diagram catalog` から必要なものを選んで追加してよい。カタログ外でも、構造・境界・責務・流れ・状態・依存を人間が理解しやすくする情報なら追加してよい
- shared な書き方は `phase_*.md`、Issue plan の構造化は `phase_plan_issue.md`、Issue 固有の実行 policy はこの workflow を正本とする
- Issue design では [phase_design.md](phase_design.md) に従い、必要な粒度で依存関係分析、`Module Dependency Diagram`、Linux `tree` style の `ディレクトリ / ファイル変更計画` を置く
- Issue plan では [phase_plan_issue.md](phase_plan_issue.md) に従い、design の依存関係分析、module dependency diagram、directory / file change plan から step 順を導く

## workflow-scoped delegation consent

- Issue workflow の開始時、または reviewer / specialist sub-agent を初めて起動する前に、active issue scope の issue-scoped workflow delegation consent を確認し、`report.md` に記録する。
- consent scope は current repo/worktree、active issue、current session、named reviewer / read-only specialist role に限定する。現在のユーザー指示がこの scope の自律委任を明示している場合は consent として扱える。
- consent がある場合、orchestrator は同一 issue / repo / session / named role の範囲で、`spec-reviewer`、`code-reviewer`、`qa-reviewer`、および必要な read-only specialist を phase ごとに再確認せず起動してよい。
- consent は destructive action、external publishing、credentialed access、scope expansion、write-capable delegation、named role 以外の delegation、browser/private external systems の利用を許可しない。これらが必要な場合は別途明示確認する。
- consent がない、または host policy と衝突する場合は `denied` または `unavailable` として記録し、required reviewer gate を満たしたことにしてはならない。

## 実行 contract

- 実装前に `requirement.md` / `design.md` / `plan.md` の整合を確認し、特に `design.md` の依存関係分析 / module dependency diagram / directory tree と `plan.md` の step 順が一致していることを確認して、plan upfront approval を得る
- 実装前に `workflow_spec_authoring.md` の requirement / design / plan gate がすべて pass し、`Spec Authoring Gate` evidence が `report.md` に残っていることを確認する
- 各 implementation step は `step closure contract / test bundle / pre-implementation evidence → implementation delegation decision → bounded implementation batch → verification → refactor/tidy → report draft update → code-reviewer → fix → re-review → commit → clean確認` の順で進める
- 完成版 `plan.md` には `Spec-Locked Closure Index`（仕様固定クロージャ索引）を置き、各 behavior slice の仕様ロックと closure owner step を実装前に固定する
- `Spec-Locked Closure Index` は Issue 全体のテストケース一覧や詳細なテスト実装指示ではなく、観測可能な入力・状態・locked expectation・防ぐ欠陥クラス・required/evidence level を固定する coverage ledger である
- `test bundle` は step closure contract の一部として、step の観測可能な振る舞いに必要な acceptance / characterization / property or invariant / regression / negative を分類する
- `step closure contract` は closure index の `id` を参照し、どの検証契約をその step で満たせば close してよいかを追えるようにする
- 実装開始前に required closure id が behavior slice の `closure ids` / `test ids` から参照され、各 required row に step-local close condition と verification command または evidence path があることを確認する
- required closure row、`locked expectation`、`required`、`spec link` を変更する場合は plan amendment と re-review を先に通す
- `pre-implementation evidence` は expected red / characterization pass / test sensitivity evidence のいずれかを記録し、failing-first を完全要求できない場合もテストが欠陥を検出できる根拠を残す
- `Implementation Delegation Gate` は各 implementation step の開始前に必ず置く。step が複数 layer / module / package にまたがる、runtime / CLI / infra / templates / shipped scaffold / shared docs に影響する、既存 pattern 調査や影響範囲分析が必要、integration test / migration / backward compatibility / filesystem / GitHub / active state に関わる、または独立 worker scope に分割できる大きさの場合は、適切なサブエージェント利用を必須にする
- `delegated` の場合は sub-agent role、scope、依頼内容、戻り値、取り込み結果を `report.md` に残す。`approved-local-execution` は小さい単一ファイル修正、機械的文言修正、明確な localized change、または即時 blocking / tightly coupled で main agent が担当すべき場合だけ許可し、条件付き必須に該当しない理由を `no delegation rationale` として残す
- reviewer gate state は `passed` / `failed` / `unavailable` / `denied` / `waived` / `provisional` のいずれかで記録する。required reviewer gate を満たすのは fresh `passed` だけである
- `waived` はユーザーの明示的 risk acceptance が `report.md` にある場合だけ許可する。`provisional` は orchestrator self-check の記録であり、`spec-reviewer` / `code-reviewer` / `qa-reviewer` の代替ではない
- サブエージェント機能が利用できない、拒否された、または host policy と衝突する場合、required reviewer gate は `unavailable` / `denied` として blocked / 未完了に分類する。degraded mode は status/context gathering や追加 verification に限定し、reviewer gate、implementation readiness、final quality gate を満たさない
- `bounded implementation batch` は step の scope、allowed files、forbidden scope に収まる最小実装単位とする
- `refactor/tidy` は verification 後の bounded decision point とし、plan では詳細 task を事前確定しない
- step 順は `design.md` の依存関係分析、module dependency diagram、directory / file change plan を根拠に、upstream / prerequisite から downstream へ組む
- cleanup が既知で大きい場合は `bounded implementation batch` / design / 別 step へ切り出す
- review / QA / spec の各 stage gate は `pass` まで回す
- 各 implementation step は、サブエージェント `code-reviewer` の `review_status: pass` を得てから、その step の実装・テスト・必要な report draft update をまとめてコミットする
- implementation delegation は per-step `code-reviewer` の代替ではない。`dev-coder` などの worker が実装した場合でも、その step diff は必ず `code-reviewer` pass を得る
- `1 implementation step = 1 review scope = 1 commit` を標準とし、複数 step の変更を 1 commit に混ぜてはならない。step が大きすぎる場合は commit をまとめず step を分割する
- step commit 後は `git status --short` などで、次 step へ持ち越す意図しない staged / unstaged 変更がないことを確認する
- step の close state は `committed` または `approved-no-op` のどちらかにする。`approved-no-op` は差分が本当にない場合だけ許可し、小さい変更、あとでまとめる、report だけ、時間不足を理由にしてはならない
- `approved-no-op` には対象 step、変更不要の理由、確認した契約やファイル、差分なし確認コマンド、review 不要または read-only 確認の根拠を `report.md` に残す
- `1 step = 1 つの観測可能な振る舞い` を原則にし、各 step に観測用の 1 本のコマンドを置く
- `plan.md` では agent-native TDD cycle を step / block / behavior slice に埋め込み、配置ルールは `phase_plan_issue.md` に従う
- 各 step は step result approval を得てから次へ進む
- final quality gate の前に `S90 docs impact resolution / docs refresh` を必ず置く。docs impact `none` は、docs / templates / README / workflow / skill / migration notes を確認し、更新不要の根拠と `spec-reviewer` の docs/spec alignment 結果を `report.md` に記録した場合だけ使える。更新が必要な場合は `doc-writer` が対象 docs を更新し、`spec-reviewer` が docs と requirement / design / plan の整合を確認する
- `S99 final quality gate` は独立 step にし、final review だけで step review を代替してはならない
- `S99 final quality gate` では、`qa-reviewer` がテスト十分性と issue 全体を達成する integration test の要否を確認し、必要な integration test が不足していれば追加を要求する
- `S99 final quality gate` では、`code-reviewer` が issue 全体の統合 diff を俯瞰し、構造、責務、回帰リスク、保守性を確認する
- `S99 final quality gate` では、`spec-reviewer` が requirement / design / plan / report、実装、テスト、docs が一致し、全要件を満たしているか確認する
- `qa-reviewer` / issue-wide `code-reviewer` / `spec-reviewer` のいずれかが `fail` の場合は修正し、該当 reviewer を再実行して `pass` まで回す
- 三者すべての final gate が `pass` した後、final report ledger に各 step の closure、三者 final review、final commit scope、post-commit external evidence の記録先を更新し、final commit を作成する。final commit の hash と clean check は final commit 後にしか確定できないため、committed `report.md` 内の必須記録ではなく、最終応答、PR、issue comment などの external delivery evidence として残す
- route だけ、または manual `active set` だけでは Issue work は完了しない。通常の開始/終了は `issue start` / `issue finish` を使う
- `complete` と報告してよいのは、`issue finish` 前に active issue が set されその対象 issue を確認できる状態で、`spec-dock/active/issue/requirement.md` / `design.md` / `plan.md` / `report.md` の 4 点が issue 固有の内容になっており、`spec-dock/active/issue/report.md` に required `sync` / `validate` の成功または pass 結果、required review の approval または pass 結果を示すコマンド証跡、各 implementation step の `Implementation Delegation Gate` が `delegated` / `approved-local-execution` / degraded mode のいずれかで閉じている証跡、required closure id が `Step Contract Closure` / `Test Contract Closure` / `Closure Coverage` で pass または approved-no-op として閉じている証跡、全 implementation step が `committed` または正当な `approved-no-op` で閉じている証跡、final docs impact resolved、final `qa-reviewer` pass、issue-wide `code-reviewer` pass、final `spec-reviewer` pass、final report ledger が記録済みであり、final commit 済みと意図しない staged / unstaged 変更なしの post-commit external delivery evidence を確認している場合のみである。ここで degraded mode は implementation delegation availability の証跡に限られ、required reviewer gate pass ではない
- 4 点の issue docs のいずれかが untouched、template、placeholder、または実質未記入の状態で残る場合は `未完了` であり、成功報告をしてはならない
- required step（`sync` / `validate` / `required review` / implementation delegation decision / per-step code review / step commit / final QA review / issue-wide code review / final spec review / final commit）のいずれかを未実施のままにした場合、または実行しても成功、pass、approval、`delegated`、`approved-local-execution`、`committed`、または正当な `approved-no-op` に到達しなかった場合、理由の記録は必須だが `complete` にはならない。`blocked` または `未完了` に分類し、`report.md` に reason と next action を残す
- `blocked` は、外部依存、権限不足、サービス停止、その他の環境条件によって次の required action を進められない状態を指す
- `blocked` の場合は `report.md` に reason と next action を残す。blocker type と impact は該当する場合に併記する
- `未完了` は、product work、docs 更新、または証跡が不足している状態を指す。product gap は環境 blocker がない限り `blocked` ではなく `未完了` として扱う
- `未完了` の場合も `report.md` に reason と next action を残す
- 完了条件を満たせない状態は `blocked` または `未完了` として扱い、成功報告をしてはならない

## report

- `spec-dock/active/issue/report.md` に、実行コマンド、結果、判断、想定外と対処を残す
- `Step Contract Closure` に step、closure id、close condition、evidence、result を残す
- `Test Contract Closure` に required closure id、step、evidence level、pre-implementation evidence、verification command、result を残す
- `Closure Coverage` に各 required closure id と verification evidence の対応を残す
- `Closure Delta` に追加・削除・変更・未実装 row と re-review 要否を残す
- `Implementation Delegation Gate` に step、decision、required reason、agent role、delegated scope、result、local-execution rationale を残す。`delegated` の場合は依頼内容、戻り値、取り込み結果を追跡し、`approved-local-execution` の場合は no delegation rationale を残す
- `Workflow Delegation Consent` に consent source、repo/worktree、active issue、session、named roles、boundary、expires / invalidation condition、`denied` / `unavailable` の場合の reason と next action を残す
- `Reviewer Gate Status` に gate name、reviewer role、freshness、state（`passed` / `failed` / `unavailable` / `denied` / `waived` / `provisional`）、risk acceptance の有無、promotion / completion decision を残す
- `Step Commit Gate` に step、review scope、`code-reviewer` verdict、commit scope、closure state、commit evidence、post-commit clean check を残す
- `Final QA Gate` に `qa-reviewer` verdict、テスト十分性、integration test 追加要否、追加した場合の evidence を残す
- `Final Code Review Gate` に issue-wide `code-reviewer` verdict、統合 diff scope、修正と re-review の evidence を残す
- `Final Spec Review Gate` に `spec-reviewer` verdict、requirement / design / plan / report / docs 整合、docs 修正が必要な場合の `doc-writer` 更新 evidence を残す
- `Final Commit` に final report ledger、final commit scope、post-commit external evidence の記録先を残す。final commit hash と final clean worktree check は final commit 後の external delivery evidence として残し、committed `report.md` 内の自己参照証跡にしない
- `complete` 判定に必要な required `sync` / `validate` の成功または pass 結果と required review の approval または pass 結果を示すコマンド証跡を、`issue finish` 前に active issue を確認できる状態の report に残す
- `issue finish` 後は active issue が clear されていてよく、`complete` 判定は active state の残存ではなく `issue finish` 前に記録・確認した report evidence で行う
- `complete` 判定に必要な required closure id は、report の `Step Contract Closure` / `Test Contract Closure` / `Closure Coverage` で pass または approved-no-op として閉じている必要がある
- `complete` 判定に必要な各 implementation step は、report の `Implementation Delegation Gate` で `delegated`、`approved-local-execution`、または degraded mode として閉じている必要がある。delegation evidence が不足している場合は `未完了` として扱う
- required step（`sync` / `validate` / `required review` / implementation delegation decision / per-step code review / step commit / final QA review / issue-wide code review / final spec review / final commit）を未実施にした場合、または実行しても成功、pass、approval、`delegated`、`approved-local-execution`、`committed`、または正当な `approved-no-op` に到達しなかった場合は reason と next action を残し、`blocked` / `未完了` に分類する
- `blocked` / `未完了` の場合は reason と next action を残し、環境 blocker と product gap を混在させない
- `blocked` では blocker type と impact を該当する範囲で残す
- stage gate ごとの reviewer verdict / test結果 / 修正内容 / no-op 理由もここに残す
- 実際に行った refactor は事前計画ではなくここに残す
- 依存関係の想定と違った実装順や refactor が必要になった場合もここに残す
- 1 セッション 1 追記でよいが、未来の自分と reviewer が追える粒度を保つ

## hard cutover evidence contract（必要な issue のみ）

- issue plan が hard cutover を含む場合、entry 条件は `docs 更新 + checked-in data manual fix + validate/sync evidence` の 3 点を必須にする。
- T3/T4 owner split は次に固定する:
  - T3 integration issue（例: `iss-00062`）が entry 条件充足と hard cutover judgment の primary owner
  - T4 closure issue（例: `iss-00063`）は T3 judgment を参照して final parity / close review を実施
- hard cutover evidence の fixed-key contract は issue-level `report.md` に残す。最低限、以下のキー群を使う:
  - `cutover_entry.docs_update.paths`
  - `cutover_entry.docs_update.pass`
  - `cutover_entry.manual_fix.paths`
  - `cutover_entry.manual_fix.pass`
  - `cutover_entry.boundary_tests`
  - `cutover_entry.validate.command`
  - `cutover_entry.validate.exit_code`
  - `cutover_entry.validate.pass`
  - `cutover_entry.sync.command`
  - `cutover_entry.sync.exit_code`
  - `cutover_entry.sync.pass`
  - `cutover_entry.targeted_regression_summary.scope`
  - `cutover_entry.targeted_regression_summary.results`
  - `cutover_entry.targeted_regression_summary.pass`
  - `cutover_entry.entry_conditions_pass`
  - `cutover_judgment.owner_issue_id`
  - `cutover_judgment.owner_role`
  - `cutover_judgment.verdict`
  - `cutover_judgment.fixed_at`
  - `cutover_judgment.follow_up_issue_id`
  - `cutover_judgment.notes`
- no fallback / no dual-read contract を崩す救済策は採用しない（canonical storage / mutation contract の詳細は [reference_deps.md](reference_deps.md) を参照）。

## 品質ゲート

- requirement:
  - AC が観測可能
  - EC が書かれている
  - 対象外が明記されている
- design:
  - 変更点が列挙されている
  - テスト戦略がある
  - 互換 / 移行 / ロールバックが必要なら整理されている
- plan:
  - step が behavior slice と review loop を回せる粒度
  - `Spec-Locked Closure Index` が AC / EC / design / bug / risk と behavior slice を結び、詳細なテスト実装指示になっていない
  - step closure contract / test bundle / pre-implementation evidence / bounded implementation batch が追える
  - every required closure id が behavior slice、step-local close condition、verification evidence、report closure へ追跡できる
  - docs impact / docs refresh step が必要なら入っている
  - final quality gate が独立し、`qa-reviewer`、issue-wide `code-reviewer`、`spec-reviewer` の三者 review を含んでいる
  - 各 implementation step に Implementation Delegation Gate があり、条件付き必須 trigger に該当する step では適切なサブエージェント利用または degraded mode evidence がある
  - 各 implementation step に code-reviewer gate、commit gate、no-op gate がある
- report:
  - `complete` を報告する場合に必要な required `sync` / `validate` の成功または pass 結果と required review の approval または pass 結果を示すコマンド証跡が、`issue finish` 前に active issue を確認できる状態の report に残っている
  - required closure id が `Step Contract Closure` / `Test Contract Closure` / `Closure Coverage` で閉じている
  - required row の削除、locked expectation 変更、required 変更、spec link 意味変更がある場合は re-review 証跡が残っている
  - 全 implementation step の `delegated` / `approved-local-execution` / degraded mode evidence と、`committed` または正当な `approved-no-op` evidence が残っている
  - final docs impact resolved、`qa-reviewer` pass、issue-wide `code-reviewer` pass、`spec-reviewer` pass、final report ledger、final commit scope、post-commit external evidence の記録先が残っている
  - required step を未実施にした場合、または実行しても成功、pass、approval、`committed`、または正当な `approved-no-op` に到達しなかった場合は `blocked` / `未完了` の reason と next action が残っている
  - `blocked` の blocker type / impact が必要な場合に残っている
  - 想定外と対処が追える

## 仕上げ

```bash
./spec-dock/scripts/spec-dock validate
./spec-dock/scripts/spec-dock sync
```
