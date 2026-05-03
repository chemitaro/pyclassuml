# workflow: issue（TDD）

Issue は実装の最小単位です。
この workflow は、active issue を入口にした TDD、step review loop、docs impact、final quality gate を正本として扱います。
この workflow の品質ゲートは scope 固有の additive gate であり、`phase_*.md` の shared minimum gate 通過を前提とします。

対応 leaf skill:
- `.agents/skills/spec-dock-issue-execution/SKILL.md`

関連:
- 総合: [guide.md](guide.md)
- Epic: [workflow_epic.md](workflow_epic.md)
- ADR: [workflow_adr.md](workflow_adr.md)
- GitHub 連携: [reference_github.md](reference_github.md)
- 共通 phase playbook: [phase_requirement.md](phase_requirement.md), [phase_design.md](phase_design.md), [phase_plan.md](phase_plan.md)
- Issue plan playbook: [phase_plan_issue.md](phase_plan_issue.md)

## 作成と active set

```bash
./spec-dock/scripts/spec-dock new issue --epic <epic-id> --title "..."
./spec-dock/scripts/spec-dock new issue --create-github-issue --epic <epic-id> --title "..."

./spec-dock/scripts/spec-dock import issue <num|#num|canonical-url> --title "..." [--epic <epic-id>]

./spec-dock/scripts/spec-dock active set <issue-id|github-issue-number|url>
./spec-dock/scripts/spec-dock active set --id <issue-id>
./spec-dock/scripts/spec-dock active set --github-issue <n>
./spec-dock/scripts/spec-dock active set <issue-id|github-issue-number|url> --checkout
./spec-dock/scripts/spec-dock active show

./spec-dock/scripts/spec-dock deps check <target> --github
./spec-dock/scripts/spec-dock deps add --from <issue-id> --to <issue-id>
./spec-dock/scripts/spec-dock deps remove --from <issue-id> --to <issue-id>
```

- `import issue` で `--epic` を省略した場合は current active から親 epic を解決する
- `import issue` の canonical URL は current repo と照合され、current repo を検証できない場合も含めて foreign GitHub issue URL は fail-closed で reject される
- `--allow-foreign-url` は compatibility flag として残るが、cross-repo node identity import の成功経路にはならない
- canonical でない URL-like target は受け付けない
- `active set` のデフォルトは no-checkout。ブランチ移動が必要な場合だけ `--checkout`
- `active set` は `<target>` の後方互換を維持しつつ、`--id` / `--github-issue` の explicit form も使える
- 依存未解決なら `active set` は通常失敗する。確認は `./spec-dock/scripts/spec-dock deps check <target> --github`
- 例外で進める場合だけ `./spec-dock/scripts/spec-dock active set <target> --github --force`
- 依存 edge の追加/削除は metadata を直編集せず `./spec-dock/scripts/spec-dock deps add --from <issue-id> --to <issue-id>` / `./spec-dock/scripts/spec-dock deps remove --from <issue-id> --to <issue-id>` を使う

## spec authoring

- active issue 配下の `requirement.md` / `design.md` / `plan.md` を埋める
- `discussions/`: `new doc {adr|disc|research|note} --issue <issue-id> --title "..."` で、この issue の `discussions/` 配下に timestamp-prefixed original を作成する。標準形は `<ts>-<kind>-<slug>.md`、same-second collision は `<ts>-<nn>-<kind>-<slug>.md`。詳細 contract は [reference_naming.md](reference_naming.md) を参照する
- templates は完成形ではなく、書き始めるための最小 scaffold に留める。仕様書作成の説明や判断基準は docs / skills を参照する
- agent は、プロジェクトの目的、作業内容、人間の理解しやすさ、エージェントの実行可能性に合わせて、項目を追加・削除・統合・並べ替えてよい
- 不要な placeholder や該当しない節は削ってよいが、正確性、検証可能性、人間の理解、エージェントの実行に必要な情報は削らない
- テンプレートにない図表や節も、[phase_design.md](phase_design.md) の `optional diagram catalog` から必要なものを選んで追加してよい。カタログ外でも、構造・境界・責務・流れ・状態・依存を人間が理解しやすくする情報なら追加してよい
- shared な書き方は `phase_*.md`、Issue plan の構造化は `phase_plan_issue.md`、Issue 固有の実行 policy はこの workflow を正本とする
- Issue design では [phase_design.md](phase_design.md) に従い、必要な粒度で依存関係分析、`Module Dependency Diagram`、Linux `tree` style の `ディレクトリ / ファイル変更計画` を置く
- Issue plan では [phase_plan_issue.md](phase_plan_issue.md) に従い、design の依存関係分析、module dependency diagram、directory / file change plan から step 順を導く

## 実行 contract

- 実装前に `requirement.md` / `design.md` / `plan.md` の整合を確認し、特に `design.md` の依存関係分析 / module dependency diagram / directory tree と `plan.md` の step 順が一致していることを確認して、plan upfront approval を得る
- 各 step は `Red → Green → Refactor → review → fix → re-review → report → コミット/no-op` の順で進める
- `Refactor` は Green 後の bounded decision point とし、plan では詳細 task を事前確定しない
- step 順は `design.md` の依存関係分析、module dependency diagram、directory / file change plan を根拠に、upstream / prerequisite から downstream へ組む
- cleanup が既知で大きい場合は `Green` / design / 別 step へ切り出す
- review / QA / spec の各 stage gate は `pass` まで回す
- 各 stage gate の `pass` 後は、`spec-dock/active/issue/report.md` を更新し、差分確認後に report とまとめてコミットするか no-op とするかを判断する
- `1 step = 1 つの観測可能な振る舞い` を原則にし、各 step に観測用の 1 本のコマンドを置く
- `plan.md` では TDD cycle を step / block / iteration に埋め込み、配置ルールは `phase_plan_issue.md` に従う
- 各 step は step result approval を得てから次へ進む
- docs impact が `none` でない場合は、final quality gate の前に docs refresh / docs impact resolution step を置く
- `git diff <base>...HEAD` を見る final diff review quality gate は独立 step にし、reviewer approval まで終える
- route だけ、または `active set` だけでは Issue work は完了しない
- `complete` と報告してよいのは、active issue が set され、その対象 issue を確認でき、`spec-dock/active/issue/requirement.md` / `design.md` / `plan.md` / `report.md` の 4 点が issue 固有の内容になっており、`spec-dock/active/issue/report.md` に required `sync` / `validate` の成功または pass 結果と required review の approval または pass 結果を示すコマンド証跡が記録されている場合のみである
- 4 点の issue docs のいずれかが untouched、template、placeholder、または実質未記入の状態で残る場合は `未完了` であり、成功報告をしてはならない
- required step（`sync` / `validate` / `required review`）のいずれかを未実施のままにした場合、または実行しても成功、pass、approval に到達しなかった場合、理由の記録は必須だが `complete` にはならない。`blocked` または `未完了` に分類し、`report.md` に reason と next action を残す
- `blocked` は、外部依存、権限不足、サービス停止、その他の環境条件によって次の required action を進められない状態を指す
- `blocked` の場合は `report.md` に reason と next action を残す。blocker type と impact は該当する場合に併記する
- `未完了` は、product work、docs 更新、または証跡が不足している状態を指す。product gap は環境 blocker がない限り `blocked` ではなく `未完了` として扱う
- `未完了` の場合も `report.md` に reason と next action を残す
- 完了条件を満たせない状態は `blocked` または `未完了` として扱い、成功報告をしてはならない

## report

- `spec-dock/active/issue/report.md` に、実行コマンド、結果、判断、想定外と対処を残す
- `complete` 判定に必要な required `sync` / `validate` の成功または pass 結果と required review の approval または pass 結果を示すコマンド証跡を残す
- required step（`sync` / `validate` / `required review`）を未実施にした場合、または実行しても成功、pass、approval に到達しなかった場合は reason と next action を残し、`blocked` / `未完了` に分類する
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
  - step が TDD と review loop を回せる粒度
  - docs impact / docs refresh step が必要なら入っている
  - final diff review quality gate が独立している
- report:
- `complete` を報告する場合に必要な required `sync` / `validate` の成功または pass 結果と required review の approval または pass 結果を示すコマンド証跡が残っている
- required step を未実施にした場合、または実行しても成功、pass、approval に到達しなかった場合は `blocked` / `未完了` の reason と next action が残っている
  - `blocked` の blocker type / impact が必要な場合に残っている
  - 想定外と対処が追える

## 仕上げ

```bash
./spec-dock/scripts/spec-dock validate
./spec-dock/scripts/spec-dock sync --github
```
