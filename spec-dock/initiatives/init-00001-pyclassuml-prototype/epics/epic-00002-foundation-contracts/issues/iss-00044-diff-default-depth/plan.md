---
種別: 実装計画書（Issue）
ID: "iss-00044"
タイトル: "Diff Default Traversal Depth"
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-08-04"
依存: ["requirement.md", "design.md"]
親: ["epic-00002", "init-00001"]
---

# iss-00044 Diff Default Traversal Depth — 実装計画

## 1. 計画の目的と完了条件

この計画は、`diff`の未指定defaultだけを `1`へ変え、`generate`、explicit CLI/config、traversal、VCS、DTOの契約を保つための実行契約である。実装後にAC-001〜AC-007、EC-001〜EC-008を検証し、READMEの利用者契約を更新し、SpecDock validate/doctor、focused/full test、lint/format、diff check、fresh code/QA/spec reviewを通す。commit、push、PR、merge、Issue finishはこの計画の完了操作に含めない。

## 2. 実行前ゲート

- `active show`で `init-00001` / `epic-00002` / `iss-00044` がactiveであることを確認する。
- `requirement.md`、`design.md`、`plan.md`のfront matterが現行parser schemaであることを確認する。
- ChatGPT-Use advisory artifact `artifacts/20260804t093411z-chatgpt-output-chatgpt-depth-design-review.md`をevidence-onlyとして参照し、採用 claimをlocal source/testsで検証する。
- `.serena/project.yml`、SpecDock managed update差分、`.agents/skills/pyclassuml-repo-map`に触れない。
- fresh `spec-reviewer`がrequirement/design/planをpassするまで、本番コードの実装stepへ進まない。レビュー指摘により不足したnamed testだけは、S00のtest-only preparationとして先に追加できる。review pass後も、S00-PROMOTEのcanonical design promotionとworkflow/runbook readinessが完了するまでS01へ進まない。
- S00-PROMOTE/S01のadmissionは、S99 final quality gateで閉じるfull-suite/Ruff baselineとは分離する。EAL-005の環境差異はS00-PROMOTE/S01ではnon-blocking（owner: orchestrator/qa-reviewer、focused evidenceと再現条件を保持）だが、S99ではgreen full-suiteまたは明示したsupported verification pathが必須である。

## 3. ステップ依存サマリー

| step | 依存 | 主な対象 | 完了後のunblock |
|---|---|---|---|
| S00 | planning docs | EC-002/004/005、default/raw-boundary、CLI/config app integrationの不足したnamed testだけを既存testsへ追加（production source変更なし） | S01/S02の実行可能なtest contract |
| S00-PROMOTE | fresh spec-reviewer #15 pass + S00 extension | report gate update、canonical design promotion、active/runbook、assurance/SpecDock gates | S01 execution admission |
| S01 | S00-PROMOTE | resolver + config tests | effective depth契約をgreenにする |
| S02 | S01 | bind/app/traversal/VCS regression tests | command境界と実出力を確認する |
| S90 | S01 | README、必要ならCLI help | 利用者向け契約を閉じる |
| S99 | S02, S90 | 全体品質・全review | Issue-wide completion evidenceを揃える |

## 4. 仕様固定クロージャ索引

| ID | step | 種別 | 仕様リンク | 固定する期待値 | 観測方法 | 必須 |
|---|---|---|---|---|---|---|
| tc-001 | S01 | acceptance | AC-001 | diff未指定のeffective depthは1 | `tests/config/test_context_resolve.py::test_diff_default_depth_is_one_without_cli_or_config` | yes |
| tc-002 | S01/S02 | acceptance | AC-002 | generate未指定のeffective depthはNoneで、transitive frontierを維持する | `tests/config/test_context_resolve.py::test_generate_default_depth_is_none_without_cli_or_config`; `tests/app/test_generate.py::test_generate_default_depth_remains_unlimited` | yes |
| tc-003 | S01 | acceptance / edge | AC-003 / EC-001 | CLI > config > default、0を保持し、depth=0はseed-only | `tests/config/test_context_resolve.py::test_cli_and_config_depth_precedence_preserves_zero`; `tests/analyze/test_traversal.py::test_depth_zero_keeps_seed_only` | yes |
| tc-004 | S02 | acceptance | AC-004 | bind未指定None、明示0は0 | `tests/cli/test_bind.py::test_bind_depth_preserves_none_and_explicit_zero` | yes |
| tc-005 | S02 | regression | AC-005/006 / EC-007 | traversal/VCS/DTOの責務と既存挙動不変、HEAD比較境界維持 | source diff `git diff -- src/pyclassuml/analyze src/pyclassuml/vcs src/pyclassuml/model`; VCS nodeids listed below | yes |
| tc-006 | S02 | integration | AC-001/002/003 | A→B→Cでdiffのdepth=1/2、CLI/config経路、generateのfrontier差を観測 | `tests/app/test_diff.py::test_diff_explicit_depth_two_reaches_transitive_dependency`; `tests/app/test_diff.py::test_diff_config_depth_two_reaches_transitive_dependency`; `tests/app/test_diff.py::test_diff_changed_seed_files_each_remain_hop_zero_at_default_depth`; `tests/app/test_generate.py::test_generate_default_depth_remains_unlimited` | yes |
| tc-007 | S02 | edge | EC-002/003/004/005/006 | multi-seed、cycle、複数candidate、depth=1 parse diagnostic、module limitを維持 | exact nodeids listed in edge closure table below | yes |
| tc-008 | S90 | inspect-only | AC-007 / EC-005/008 | READMEがdefaults/precedence/Git/parse/unlimited limitsを記載 | DOC-001〜DOC-007 grep/目視と`EXEC-S90-EC-008` positive/negative schema inspection | yes |
| tc-009 | S99 | quality | AC-006/007 / EC-001/005/006/007/008 | INV-001〜INV-006、validate、tests、lint、diff check、review pass | exact named tests/source inspection/quality commands/review listed below | yes |
| tc-010 | S00-PROMOTE | workflow gate | AC-006/007 | fresh reviewer passをreportへ反映し、approved design、active issue、assurance、workflow/runbook readinessを実装前に固定 | `EXEC-S00-PROMOTE`のreport gate/status、canonical doc/status、post-promotion active show、workflow status、guidance、assurance verify、validate、doctor、diff check | yes |

証跡レベルは、`tc-001`〜`tc-004`/`tc-006`をred-required、`tc-005`/`tc-007`をcovered-existingまたはred-required、`tc-008`をinspect-only、`tc-009`をmanual-requiredとする。実装中に新しいbug classや仕様変更が出た場合はreportに記録し、plan amendmentと再review要否を判断する。

### エッジケースのclosure対応

| edge ID | owner closure | 固定する期待値 | 観測証跡 |
|---|---|---|---|
| EC-001 | tc-003 | 明示`depth=0`はseed-onlyで、command default `1`へfallbackしない | `tests/analyze/test_traversal.py::test_depth_zero_keeps_seed_only` |
| EC-002 | tc-007 | changed seedは各々hop 0で、別seedのreachable frontierをdepthで失わない | `tests/app/test_diff.py::test_diff_changed_seed_files_each_remain_hop_zero_at_default_depth` |
| EC-003 | tc-007 | cyclic importは既存reachable setで有限停止する | `tests/analyze/test_traversal.py::test_depth_none_terminates_deterministically_on_cyclic_imports` |
| EC-004 | tc-007 | 同一importの複数candidateは同じhopで解決候補として扱われる | `tests/analyze/test_traversal.py::test_multiple_import_candidates_share_same_hop` と`_candidate_paths`/`import_candidate_paths` inspection |
| EC-005 | tc-007 / tc-009 | `AnalysisConfig(depth=1)`でもdepthはparse safety limitではなく、深いmoduleのsyntax diagnosticが残り得る | `tests/parse/test_module_parse_and_index.py::test_parse_target_set_keeps_deeper_syntax_diagnostic_with_depth_one`、`EXEC-S99-INV-005-006`、README parse frontier記述 |
| EC-006 | tc-007 / tc-009 | module limitとlimit diagnosticはdepth変更後も有効 | `tests/analyze/test_traversal.py::test_module_limit_returns_partial_result_and_fatal_diagnostic`; `tests/analyze/test_traversal.py::test_module_limit_applies_to_initial_seed_frontier` |
| EC-007 | tc-005 | `current_state=head`はGit比較対象だけを変え、working-tree parse内容をHEADへ固定しない | `tests/vcs/test_diff_file_collect.py::test_head_diff_uses_head_not_working_tree`、README current-state記述 |
| EC-008 | tc-008 / tc-009 | explicit unlimited diff入力は現行契約になく、sentinelを追加しない | `EXEC-S90-EC-008`: CLI/config schema inspectionと禁止token不在のnegative inspection、README unlimited記述、別Issue延期記録 |

### tc-005 exact VCS regression nodeids

`tc-005`はsource diff inspectionに加え、次の既存VCS nodeidをすべて実行する。これらはdepth defaultの責務をVCS collectorへ移していないこと、およびGit比較方式を保持することを確認する。

```text
tests/vcs/test_diff_file_collect.py::test_working_tree_tracked_added_modified_renamed_and_delete_excluded
tests/vcs/test_diff_file_collect.py::test_explicit_base_sets_authoritative_base_resolution
tests/vcs/test_diff_file_collect.py::test_no_base_feature_branch_resolves_default_branch_merge_base
tests/vcs/test_diff_file_collect.py::test_no_base_without_usable_candidate_uses_initial_commit_fallback
tests/vcs/test_diff_file_collect.py::test_head_diff_uses_head_not_working_tree
tests/vcs/test_diff_file_collect.py::test_working_tree_untracked_included_excluded_and_empty_success
```

### AC-006 invariant closure対応

`INV-001`〜`INV-006`は`tc-009`で最終結果をreportへ記録し、各stepで得た個別テスト結果を再利用する。`INV-005`のsyntax/parse regressionと`INV-006`のAST-only/read-only inspectionは、抽象的な「全体test」だけでは閉じず、requirementの検証表に記載したnamed pathを実行または記録する。

## 5. 共通実行ルール

- 1 stepは1 behavior sliceと1 review scopeに限定する。
- source変更の許可pathはplanに列挙したものだけとし、traversal/VCS/DTOへの変更は停止条件とする。
- observed resultはreportへ記録し、planはplanned contractを保持する。
- 既存のユーザー変更をstash、reset、checkout、cleanで消去しない。
- commit/push/PR/mergeは実行しない。必要になった場合はGit状態と変更範囲を報告して指示を待つ。

## 5.1 step-local execution contract

各stepは、次の契約を満たす入力・証跡・停止条件を持つ。workerはこの表の許可pathだけを変更し、coordinatorは返却された証跡をreportへ統合する。

| step | planned obligation | Red / 代替証跡 | refactor guardrail | report evidence destination | amendment trigger | delegation input / owner | stop condition | required output |
|---|---|---|---|---|---|---|---|---|
| S00 | EC-002/004/005、default/raw-boundary、CLI/config app integrationの不足したnamed testを追加し、S02/S99のコマンドを実行可能にする | test-only preparation。テストが既存実装でgreenでも可。本番sourceとREADMEは変更しない。diff default testは旧実装でRedを許容する | `tests/config/test_context_resolve.py`, `tests/cli/test_bind.py`, `tests/app/test_generate.py`, `tests/app/test_diff.py`, `tests/analyze/test_traversal.py`, `tests/parse/test_module_parse_and_index.py`だけ。fixtureはtest内の`tmp_path`に限定 | reportのS00/TDD、changed test paths、`EXEC-S00-TEST-CONTRACT` | named testの意味が既存contractと衝突する、production source変更が必要、許可path外変更 | dev-coderへtest-only bounded taskを入力 | production source/docs変更、named path未生成、test不能、path外変更 | changed test files、focused pytest output、path/status evidence、未解決risk |
| S00-PROMOTE | fresh spec-reviewer #15 pass後にreportのreview/evidence gateを更新し、canonical designをapprovedへ昇格し、active/runbook/assurance/SpecDock状態を再生成・検証する | review pass前はdesignのdraft状態、reportの#15 required、workflow blockedを保持する。review pass後にmain orchestratorがreportのSpec Authoring Gate、Reviewer Gate Status、Final Spec Review Gate、current gate、target/source evidenceをpassへ更新し、その後canonical design front matterをapprovedへ変更する。active/runbook/metadataは正規コマンドで更新する。EAL-005のfull-suite環境差異はS99 final quality gateのblockingであり、S00-PROMOTE/S01のadmission blockerではない | issue-local `report.md`のfresh pass evidenceと`design.md`の状態更新、`active set`、post-promotion `active show`、`guidance`、assurance/validate/doctor/diff-checkのみ。source/tests/README/managed bundle/skill/Serenaは禁止 | reportの`EXEC-S00-PROMOTE`、tc-010、workflow/runbook JSON、post-promotion active show、protected status、EAL-005 scope disposition | reportとprojectionのreview status不一致、approved statusとreviewer target hash不一致、runbookがreadyにならない、managed state手修復が必要 | fresh spec-reviewerへrequirement/design/plan/reportを入力。#15 pass後、main orchestratorがreportとcanonical design statusだけを更新し、spec-managerへcommand-first bounded taskをhandoffする | fresh spec-reviewer未pass、report gate未更新、active scope不一致、assurance verify failure、workflow blocked、validate/doctor/diff-check failure | report/status diff、exact commands/results、post-promotion active scope、runbook readiness、assurance/SpecDock evidence、EAL-005 final-quality disposition、risk |
| S01 | resolverのcommand-aware defaultとCLI/config precedenceを実装し、tc-001〜tc-003をgreenにする | S00-PROMOTE完了後、実装前`tests/config/test_context_resolve.py`のsensitivityを記録。diff default testはRed、generate/precedence testsは既存実装でgreenでもよい | resolverのdepth merge以外を変更しない。bind/model/traversal/VCS/READMEは禁止 | reportのTDD表、S01 closure、changed files | `depth=0`優先やgenerate=Noneを同時に成立できない、許可path外変更が必要 | fresh spec-reviewer #15 passとS00-PROMOTE完了後、dev-coderへrequirement/design/planとresolver+config testを入力 | fresh spec-reviewer未pass、S00-PROMOTE未完、test不能、path外変更 | changed files、focused test output、risk、review request |
| S02 | bind raw境界、A→B→C、多seed/cycle/limit、複数candidate、depth=1 parse diagnostic、VCS regressionをtc-004〜tc-007で閉じる | 既存test coverageを確認し、必要なintegration/edge testをtests内へ追加 | sourceのbind policy、traversal/VCS/DTOを変更しない。testsの許可path外変更は禁止 | reportのS02 closure、VCS command output、EC-002〜EC-007、QA/code review | traversal/VCS/DTO変更が必要、Git semanticsが変わる、named edge証跡が取れない | dev-coderへS02 allowed test pathsとS01結果を入力。qa-reviewer/code-reviewerへdiffを入力 | S01未完、VCS regression failure、scope boundary violation | changed tests、focused/VCS outputs、closure update、review verdict |
| S90 | DOC-001〜DOC-007をREADMEへ反映し、EC-005/008の利用者制約とCLI/config schema制約を明文化する | docs-only inspection。READMEだけで不足する場合はdoc-writerへ委任 | source/tests/managed bundle/skillsを変更しない | reportのtc-008、`EXEC-S90-EC-008`、README path、docs inspection result | READMEで契約を誤読させる、未知の恒久docs変更が必要 | doc-writerへREADMEとDOC checklistを入力 | source/managed/skill変更要求、契約不一致 | changed README、grep/inspection evidence、schema inspection、docs review |
| S99 | tc-009と全体品質・全reviewを完了し、実装前後のGit/SpecDock状態を記録する | command failureの原因を分類し、環境info以外は未完了とする | commit/push/merge/finishなし。SpecDock操作はspec-manager原則 | reportのFinal Quality Gate、closure coverage、protected-boundary baseline、Git status | required check failure、review fail、未解消open entry | spec-manager/code-reviewer/qa-reviewer/spec-reviewerへ各scopeを入力 | any blocking gate fail、managed state手修復が必要 | exact commands/results、review statuses、protected path classification、unresolved risks、handoff |

### step-local executable case cards

各stepのnamed caseは、実装担当が前提・操作・期待結果・失敗検出・検証方法を同じ契約で実行できるように固定する。closure indexの各IDは、下記の実在nodeidまたは明示したsource/inspection commandで閉じる。

#### CASE-S00-PROMOTE-001 — report gate, canonical design promotion, and runbook readiness

- 前提: S00 test-only preparationが完了し、fresh `spec-reviewer #15`がrequirement/design/plan/reportをpassしている。reviewer target hashとcanonical docsの内容が一致し、production source/READMEに実装差分がない。
- 操作: まずmain orchestratorがissue-local canonical `report.md`のSpec Authoring Gate、Reviewer Gate Status、Final Spec Review Gate、current gate、target/source evidenceへ#15 passを反映する。次にcanonical `design.md`のfront matter状態を`draft`から`approved`へ更新する。その後、spec-managerが次を順に実行する。

```bash
./spec-dock/scripts/spec-dock active set --id iss-00044
./spec-dock/scripts/spec-dock active show
./spec-dock/scripts/spec-dock assurance classify --stage requirement --issue iss-00044 --format json
./spec-dock/scripts/spec-dock assurance verify --issue iss-00044
./spec-dock/scripts/spec-dock workflow status --format json
./spec-dock/scripts/spec-dock guidance issue-execution
./spec-dock/scripts/spec-dock validate
./spec-dock/scripts/spec-dock doctor
git diff --check
```

- 期待結果: reportのcurrent gateとReviewer Gate Statusは#15 pass、active scopeは`iss-00044`、designは`approved`、assuranceはvalid、`workflow status`はready、`guidance issue-execution`のrunbookは`may_execute_approved_plan=true`、validate/doctor/diff-checkはpassである。GitHub capability infoはnon-blockingとする。
- 失敗検出: review pass前のreport/status変更、reviewer target hash不一致、active scope不一致、workflow blocked、runbook projection未更新、assurance/validate/doctor/diff-check非0、protected pathの新規差分をfailとする。
- 検証方法: `tc-010`、`EXEC-S00-PROMOTE`、report diff、post-promotion active show、workflow/runbook JSON、assurance verify、validate/doctor/diff-check結果をreportへ記録し、S01をadmitする。

#### CASE-S01-001 — resolver default and precedence

- 前提: S00-PROMOTEが完了し、`fresh spec-reviewer #15`がpassしている。`EXEC-PROTECTED-BASELINE`でproduction source/READMEに実装差分がない。
- 操作: `uv run pytest tests/config/test_context_resolve.py -q`を実装前後に実行し、diff/generateのconfigなし、config `0/3`、CLI `0/2`のresolverケースを確認する。
- 期待結果: diff未指定は`AnalysisConfig.depth == 1`、generate未指定は`None`、configはdefaultに勝ち、CLIはconfigに勝ち、`0`は保持される。
- 失敗検出: pytest非0、assertion failure、invalid bool/negative validationの差分、または許可外source diffをfailとしてS01を閉じない。
- 検証方法: `tc-001`〜`tc-003`とnamed test outputをreportのTDD/S01 closureへ記録し、code-reviewer passを取得する。

#### CASE-S02-001 — raw bind boundary

- 前提: S01がgreenで、CLI parserの既存契約を変更していない。
- 操作: `uv run pytest tests/cli/test_bind.py -q`を実行し、`--depth`未指定と`--depth 0`をbindする。
- 期待結果: `CommandOptions.depth`は未指定なら`None`、明示`0`なら`0`。effective値の`diff=1`はresolver後だけに現れ、bindが`1`を注入しない。
- 失敗検出: bind assertion failure、CLI help/parser差分、`None`と`1`の観測点混同をfailとする。
- 検証方法: `tc-004`、`tests/cli/test_bind.py` output、source diffで`bind.py`無変更をreportへ記録する。

#### CASE-S02-002 — A→B→C integration and VCS regression

- 前提: S01がgreenで、diff fixtureのGit repositoryが初期化される。
- 操作: A→B→C fixtureを使うapp testsを実行し、CLI `depth=1/2`とtop-level config `depth=2`を別nodeidで検証する。`tests/vcs/test_diff_file_collect.py`は explicit base、merge-base、initial fallback、current-state、include-untrackedの順に含めて実行する。
- 期待結果: diff未指定はA/Bまで、CLIまたはtop-level configのdepth 2はCまで、generate未指定はCまで。Gitのbase/seed/untracked/rename結果は既存期待値から変わらない。
- 失敗検出: app/VCS pytest非0、changed seedの欠落、Git metadataの変化、traversal/VCS/DTO source diffをfailとする。
- 検証方法: `tc-005`/`tc-006`、S02 pytest output、`git diff -- src/pyclassuml/analyze src/pyclassuml/vcs src/pyclassuml/model`をreportへ記録する。

#### CASE-S02-003 — edge behavior and candidate/parse evidence

- 前提: S01がgreenで、test-only additionsがplanのallowed test pathsに限定される。
- 操作: `uv run pytest tests/app/test_diff.py::test_diff_changed_seed_files_each_remain_hop_zero_at_default_depth tests/analyze/test_traversal.py::test_multiple_import_candidates_share_same_hop tests/parse/test_module_parse_and_index.py::test_parse_target_set_keeps_deeper_syntax_diagnostic_with_depth_one tests/analyze/test_traversal.py::test_depth_none_terminates_deterministically_on_cyclic_imports tests/analyze/test_traversal.py::test_module_limit_returns_partial_result_and_fatal_diagnostic tests/analyze/test_traversal.py::test_module_limit_applies_to_initial_seed_frontier -q`、`rg -n "^def _candidate_paths|import_candidate_paths" src/pyclassuml/parse/indexer.py src/pyclassuml/analyze/traversal.py`を実行する。
- 期待結果:複数changed seedは各々hop 0で残り、複数candidateは同じhopで扱われ、`AnalysisConfig(depth=1)`でも深いbroken moduleの`bad_syntax` diagnosticが残り、candidate集合の責務はparse/traversal境界にある。
- 失敗検出: named test非0、`_candidate_paths`/`import_candidate_paths`が確認できない、depth=1でdiagnosticが消える、またはtest path外変更をfailとする。
- 検証方法: 6 named nodeid、`EC-002`〜`EC-006`、`EXEC-S02-EDGE-001`、`tc-007`をreportへ記録し、qa-reviewerがmulti-seed/cycle/limit coverageをpassする。

#### CASE-S90-001 — README contract checklist

- 前提: S01/S02のeffective contractがgreenで、README変更はdoc-writerのallowed scopeに限定される。
- 操作: READMEをDOC-001〜DOC-007の順に目視/grepし、`generate=None`、`diff=1`、precedence、Git方式、changed seed、current-state、unlimited制約を確認する。
- 期待結果: 利用者向け文書がsourceの実挙動と一致し、hop semanticsと既知制約を誤解させない。
- 失敗検出: DOCコードの欠落、`[diff].depth`やexplicit unlimitedが存在するとの誤記、README以外の許可外恒久docs変更をfailとする。
- 検証方法: `tc-008`、`DOC-001`〜`DOC-007`、S90 docs inspectionをreportへ記録し、doc-writer reviewをpassさせる。

#### CASE-S90-002 — explicit unlimited schema limitation

- 前提: 現行CLI/config schemaが非負整数のみで、sentinel追加はscope外である。
- 操作: `rg -n '"depth"|_TOP_LEVEL_KEYS|_DIFF_KEYS|_non_negative_int' src/pyclassuml/config/resolver.py src/pyclassuml/cli/bind.py`でpositive schema evidenceを確認し、続けて `rg -n '\[diff\]\.depth|diff\.depth|unlimited|sentinel' src/pyclassuml/config/resolver.py src/pyclassuml/cli/bind.py`を実行する。後者はexit `1`を期待し、READMEのunlimited制約記述と照合する。
- 期待結果: `depth`はtop-level key、`[diff].depth`は存在せず、CLI parserは非負整数を受け、explicit unlimited sentinelはない。
- 失敗検出: positive schema evidenceの欠落、negative inspectionのexit `0`、READMEとの不整合、sentinel追加のsource diffをfailとする。
- 検証方法: `EC-008`、`EXEC-S90-EC-008`、`tc-008`をreportへ記録する。

#### CASE-S99-001 — protected boundary and no-op ownership

- 前提: `EXEC-PROTECTED-BASELINE`の317 status entriesと所有分類がreportに記録済みである。
- 操作: baselineと同じ4つの`git status`コマンドを実装前後に実行し、`.agents/skills/pyclassuml-repo-map`、`.serena/project.yml`、`src/tests/README`をpath別比較する。
- 期待結果: protected skillは空、Serenaの既存`M`は保持、managed bundleはbaselineから変化せず、実装surfaceはallowed pathだけになる。
- 失敗検出: protected pathの新規status、Serena既存変更の消失、managed差分の変更、allowed path外のsource/docs変更をfailとする。
- 検証方法: `EXEC-PROTECTED-BASELINE`、`tc-009`、report protected-boundary tableへ前後出力と分類を記録する。

#### CASE-S99-002 — INV-005/INV-006 named evidence

- 前提: source/tests/README実装が完了し、S02/S90のreviewがpassしている。
- 操作: named pytest、`sed`で`parse_target_set`/`parse_module_source_text`の範囲表示、禁止token `rg`を実行し、前後Git statusを取得する。
- 期待結果: syntax/parse diagnostic testsがgreen、AST parse callとnamed function範囲が表示され、禁止token `rg`はexit `1`、前後statusのprotected分類が一致する。
- 失敗検出: named test非0、`sed`範囲欠落、禁止tokenrgがexit `0`、前後status不一致をfailとする。
- 検証方法: `INV-005`/`INV-006`、`EXEC-S99-INV-005-006`、`tc-009`へcommand/output/exit statusを記録する。

#### CASE-S99-003 — final quality and reviewer admission

- 前提: S01/S02/S90のclosureがgreenで、未解消のblocking entryがない。
- 操作: `assurance verify`、`validate`、`doctor`、focused/full pytest、ruff check/format、`git diff --check`をspec-manager経由で実行し、code/QA/spec reviewerをfreshで取得する。
- 期待結果: 必須commandがpass（doctorのGitHub target infoはnon-blocking）、全reviewが`review_status: pass`、commit/push/merge/finishは未実施のままhandoff可能になる。
- 失敗検出: command非0（info以外）、review fail、未解消open entry、commit作成をfail/stopとする。
- 検証方法: `tc-009`、Final Quality Gate、Git status、review outputsをreportへ記録する。

## 6. 実装ステップ S01 — resolverのcommand-aware default

### 目標と対象

`src/pyclassuml/config/resolver.py`のdepth mergeだけを変更し、`CommandName.DIFF`かつCLI/config双方がNoneのときだけ1を返す。`tests/config/test_context_resolve.py`へ必要な回帰テストを追加する。

### 許可・禁止

- allowed: `src/pyclassuml/config/resolver.py`, `tests/config/test_context_resolve.py`
- forbidden: `src/pyclassuml/cli/bind.py`のdefault policy変更、`contracts.py`の型変更、traversal/VCS/DTO変更、README変更

### 具体テストケース

- `tc-s01-001` / `tc-001`: diff request、configなし -> `config.depth == 1`。
- `tc-s01-002` / `tc-002`: generate request、configなし -> `config.depth is None`。
- `tc-s01-003` / `tc-003`: config `depth=3`、CLI未指定 -> 3；config `depth=0` -> 0；CLI `0`/`2` -> CLI値。
- `tc-s01-004` / `tc-003`: invalid bool/negativeの既存validationを維持する。

### 実行・closure

実装前に次を実行して新規テストが失敗すること、または既存test sensitivityをreportに記録する。

```bash
uv run pytest tests/config/test_context_resolve.py -q
```

実装後に同じcommandを再実行し、`tc-001`〜`tc-003`がgreenであることをStep Contract Closureへ記録する。resolverのdiffはcommand defaultとvalidationのみに限定する。

### レビューゲート

`code-reviewer`はresolver/testの責務、`0`の扱い、generate回帰を確認する。pass条件は `review_status: pass`。指摘があれば修正後にfresh reviewを再実行する。

## 7. 実装ステップ S02 — bind/app/regressionとGit契約

### 目標と対象

CLI bindが未指定Noneを保持すること、A→B→Cの実出力がresolver値を消費すること、既存traversal/VCS契約を変更していないことを確認する。必要なテストだけを追加する。

### 許可・禁止

- allowed: `tests/cli/test_bind.py`, `tests/app/test_diff.py`, `tests/app/test_generate.py`, `tests/analyze/test_traversal.py`, `tests/parse/test_module_parse_and_index.py`, `tests/vcs/test_diff_file_collect.py`、必要なfixtureの同じtest file内
- forbidden: `src/pyclassuml/cli/bind.py`のcommand default追加、`src/pyclassuml/analyze/traversal.py`、`src/pyclassuml/vcs/diff_collect.py`、`src/pyclassuml/model/contracts.py`の変更

### 具体テストケース

- `tc-s02-001` / `tc-004`: `diff`/`generate`の `--depth`未指定はNone、`--depth 0`は0。
- `tc-s02-001`の境界: bind直後の`CommandOptions.depth`は両commandとも未指定なら`None`、明示`0`なら`0`。その後resolverが`diff`だけ`1`へ解決し、`generate`は`None`を維持する。このraw bind値とeffective値を同じassertionとして扱わない。
- `tc-s02-002` / `tc-006`: `tests/app/test_diff.py::test_diff_explicit_depth_two_reaches_transitive_dependency`と`tests/app/test_diff.py::test_diff_config_depth_two_reaches_transitive_dependency`でA→B→C fixtureを使い、CLI/configのdepth `1`はA/Bまで、depth `2`はCまで、`tests/app/test_generate.py::test_generate_default_depth_remains_unlimited`でgenerate未指定はNone。
- `tc-s02-003` / `tc-007`: `test_diff_changed_seed_files_each_remain_hop_zero_at_default_depth`で複数changed seedを失わないことを確認する（EC-002）。cycleは停止する（EC-003）。module limitは既存diagnosticを返す（EC-006）。複数candidateが同じhopで到達可能であることを`test_multiple_import_candidates_share_same_hop`で確認する（EC-004）。
- `tc-s02-004` / `tc-007`: `test_parse_target_set_keeps_deeper_syntax_diagnostic_with_depth_one`で`AnalysisConfig(depth=1)`を渡し、depthがparse safety limitではなく、深いbroken moduleの`bad_syntax` diagnosticを残すことを確認する（EC-005）。
- `tc-s02-005` / `tc-005`: VCS既存testsを実行し、explicit base/default merge-base/current-state/include-untracked/initial fallbackの結果を維持する。

### 実行・closure

```bash
uv run pytest tests/cli/test_bind.py tests/app/test_diff.py tests/app/test_generate.py tests/analyze/test_traversal.py tests/parse/test_module_parse_and_index.py tests/vcs/test_diff_file_collect.py -q
uv run pytest tests/app/test_diff.py::test_diff_explicit_depth_two_reaches_transitive_dependency -q
uv run pytest tests/analyze/test_traversal.py::test_multiple_import_candidates_share_same_hop tests/parse/test_module_parse_and_index.py::test_parse_target_set_keeps_deeper_syntax_diagnostic_with_depth_one -q
rg -n "^def _candidate_paths|import_candidate_paths" src/pyclassuml/parse/indexer.py src/pyclassuml/analyze/traversal.py
```

期待値は、multi-seed/multiple-candidate/deeper-diagnosticのnamed testsがgreen、`_candidate_paths`と`import_candidate_paths`のsource inspectionがcandidate集合の責務を示し、EC-002〜EC-007の結果を`EXEC-S02-EDGE-001`としてreportへ記録できることである。

app fixtureを追加できない場合は、既存testがresolver結果を検出できる根拠をreportに記録し、`covered-existing`へ格下げしない限りS02を閉じない。

### レビューゲート

`code-reviewer`はsource変更範囲、app integration、seed/VCS境界を確認する。`qa-reviewer`はA→B→C、多seed、explicit base/untrackedのcoverageを確認する。両方passが必要である。

## 8. ドキュメント影響解消 S90

### 対象と内容

`README.md`へdepthのhop semantics、`generate=None`、`diff=1`、`CLI > config > command default`、top-level configの共通適用、changed seed、Git比較方式、current-stateの既知制約、明示unlimited未提供を追記する。既存のdiff base/current-state説明を削除・反転しない。

README以外の恒久docsが必要と判明した場合は、doc-writerへ対象pathを明示して委任し、Issue reportに変更範囲を記録する。managed templatesや`.agents/skills`は変更しない。

### 具体検証

- `tc-s90-001` / `tc-008`: READMEをgrep/目視し、次のDOC-001〜DOC-007をすべて確認する。
  - `DOC-001`: seed=hop 0、直接import=hop 1のhop semantics。
  - `DOC-002`: `generate`未指定=`None`、`diff`未指定=`1`。
  - `DOC-003`: CLI > top-level config > command default、およびtop-level configが両commandに適用されること。
  - `DOC-004`: changed fileがdepthにかかわらずdiff seedになること。
  - `DOC-005`: explicit base、merge-base、initial fallback、working-tree/head、include-untrackedのGit比較方式。
  - `DOC-006`: `current_state=head`でもparse内容は自動的にHEADへ固定されない既知制約。
  - `DOC-007`: 明示的なunlimited diff入力が現行契約にないことと別Issue延期。
- `EC-008` / `EXEC-S90-EC-008`: positive schema inspectionで`depth`がtop-level key、CLI parserが非負整数であることを確認し、`rg -n '\[diff\]\.depth|diff\.depth|unlimited|sentinel' src/pyclassuml/config/resolver.py src/pyclassuml/cli/bind.py`がexit `1`・出力なしであることを確認する。両方の出力・exit statusと「explicit unlimited sentinelなし」の判定をreportへ記録する。
- CLI helpへ説明を追加するのはREADMEだけで契約が満たせない場合に限り、bindの未指定値は変えない。

## 9. 最終品質ゲート S99

### 必須コマンド

SpecDockの操作コマンドは原則`spec-manager`へ委任し、workerから返された実行結果をreportへ転記する。今回のように同一worktreeの実装前後ゲートを直ちに確認する必要があり、spec-managerの起動が利用できない場合に限り、coordinatorが同じrepo-local scriptをbounded read/validation operationとして直接実行してよい。その場合はreportに例外理由、対象コマンド、結果を記録し、managed stateの手編集は行わない。

実装前に`EXEC-PROTECTED-BASELINE`として、所有範囲を分けて次を実行する。

```bash
git status --short --untracked-files=all
git status --short -- .agents/skills/pyclassuml-repo-map
git status --short -- .serena/project.yml
git status --short -- src tests README.md
```

期待値と分類は次のとおりである。`pyclassuml-repo-map`は空、`.serena/project.yml`はユーザー既存変更として保持、S00実行前の`src/tests/README`は空、SpecDock updater bundle（`.agents/.codex/.github/spec-dock`）は本Issue実装外の既存managed差分として保持する。S00後はproduction `src=0`、README=0、許可された6 test pathsだけが変更されている状態を保つ。Issue-local planning docs、artifact、assurance stateは本Issueの計画証跡として別分類する。実装後は同じpath別statusを再実行し、protected pathに新規差分がないことと、source/tests/READMEの差分がplan許可pathだけであることをreportへ記録する。

```bash
./spec-dock/scripts/spec-dock active show
./spec-dock/scripts/spec-dock assurance verify --issue iss-00044
./spec-dock/scripts/spec-dock validate
./spec-dock/scripts/spec-dock doctor
uv run pytest tests/config/test_context_resolve.py tests/cli/test_bind.py tests/analyze/test_traversal.py tests/app/test_diff.py tests/app/test_generate.py tests/vcs/test_diff_file_collect.py tests/parse/test_module_parse_and_index.py -q
uv run pytest
uvx --from ruff==0.9.3 ruff check src tests
uvx --from ruff==0.9.3 ruff format --check src tests
uvx --from ruff==0.9.3 ruff check tests/config/test_context_resolve.py tests/cli/test_bind.py tests/app/test_diff.py tests/app/test_generate.py tests/analyze/test_traversal.py tests/parse/test_module_parse_and_index.py tests/vcs/test_diff_file_collect.py
uvx --from ruff==0.9.3 ruff format --check tests/config/test_context_resolve.py tests/cli/test_bind.py tests/app/test_diff.py tests/app/test_generate.py tests/analyze/test_traversal.py tests/parse/test_module_parse_and_index.py tests/vcs/test_diff_file_collect.py
git diff --check
```

### 品質ツールの再現性と既存baselineの扱い

- lint / format toolは `ruff==0.9.3` を固定し、標準コマンドは `uvx --from ruff==0.9.3 ruff check ...` / `uvx --from ruff==0.9.3 ruff format --check ...` とする。`uv run ruff --version`で同じversionが利用できる場合は同等結果として記録できる。Ruffは現行`pyproject.toml`/`uv.lock`のdev dependencyには追加せず、このIssueで依存管理を拡張しない。
- 実装前baseline（S00前）では、全体`ruff check src tests`に、今回の許可path外である`src/pyclassuml/render/document.py`の既存F821が4件あり、全体format checkは32 filesをreformat対象とする。これは本Issueのresolver/default変更で作ったfailureではないため、今回の実装で修復・全体formatする対象に含めない。
- S99では全体lint/formatを診断コマンドとして実行し、baselineのerror/file listをreportへ固定する。同時に、Issue変更path（S00の6 test pathsとS01/S02/S90の許可path）へscoped `ruff check`を実行してexit 0を必須とし、format checkも同じpathで実行する。format checkが非0の場合は、同じ固定versionの`ruff format --diff`を実行し、出力をIssue追加hunk（`git diff --unified=0`）と照合する。既存行だけのbaseline driftはnon-blockingとしてfile/line分類をreportへ残せるが、追加hunkをreformat対象に含む場合はそのtest/doc-writer workerが追加ブロックだけをformatしてから再確認する。`git diff --check`とcode-reviewerのhunk reviewで新規format driftがないことを確認し、baseline外の新規errorはblockingとする。
- baselineの恒久修復は別 maintenance issue のownerとし、iss-00044のcompletion条件へ混ぜない。baseline dispositionが不明、またはIssue変更pathに新規errorが出た場合はS99を閉じずplan amendmentへ戻る。

`tc-009`のINV-005/006は全体pytestへの包含だけで閉じず、S99で次の順序を実行してreportへ個別記録する。

```bash
git status --short
uv run pytest tests/parse/test_module_parse_and_index.py::test_syntax_error_dependency_is_excluded_from_parsed_modules_and_indexes tests/app/test_diff.py::test_diff_colorized_output_is_deterministic tests/app/test_diff.py::test_diff_syntax_error_preserves_diagnostics_and_emits_no_fabricated_diff_changed tests/app/test_diff.py::test_head_current_parse_failure_emits_warning_and_no_fabricated_decoration -q
rg -n "ast\\.parse|importlib|__import__" src/pyclassuml/parse/indexer.py
git status --short
```

期待値は、named testsがgreen、source inspectionでAST parse経路と対象moduleのimport実行を区別でき、実行前後のGit statusに実装対象外のsource/Git変更が追加されないことである。コマンド出力・前後status・INV-005/006判定はreportの`tc-009`/`EXEC-S99-INV-005-006`へ記録する。

`INV-006`のsource inspectionは次の追加コマンドでnamed functionの範囲を固定する。

```bash
sed -n '/^def parse_target_set/,/^def parse_module_source_text/p' src/pyclassuml/parse/indexer.py
sed -n '/^def parse_module_source_text/,/^def _parsed_module_from_tree/p' src/pyclassuml/parse/indexer.py
rg -n "importlib|__import__|exec\\(|eval\\(" src/pyclassuml/parse/indexer.py
```

前2コマンドは`parse_target_set`/`parse_module_source_text`の実行範囲と`ast.parse`呼び出しを示し、最後のcommandはexit status `1`（禁止されたruntime import/eval tokenなし）を期待する。実測出力、exit status、前後statusは`EXEC-S99-INV-005-006`としてreportへ記録する。

利用可能なproject commandが異なる場合は既存 `pyproject.toml`/CI commandを確認し、代替commandと理由をreportへ記録する。SpecDock doctorのGitHub capability情報は、対象repoが利用不能というinfoであれば失敗と扱わない。

### レビューと完了条件

- `code-reviewer`: issue-wide source/tests diff、scope、回帰riskがpass。
- `qa-reviewer`: closure indexの全obligation、integration、known limitationsがpass。
- `spec-reviewer`: requirement/design/plan/report/実装/tests/README整合がfresh pass。
- `tc-009`の証跡がreportにあり、SpecDock validate/doctor、全テスト、全体lint/format診断、Issue-scoped lint、diff checkが実行済みで、baseline外のfailureがない。既存baselineの恒久failureは別owner/maintenance issueとして明示されている。
- commitは作成せず、Git statusと変更pathを最終報告する。

## 10. 実装委任契約

実装が可能な場合は `dev-coder`へS01/S02、docs変更が必要な場合は `doc-writer`へS90、レビューは各ゲートごとにfresh `code-reviewer`/`qa-reviewer`/`spec-reviewer`へ委任する。入力は本Issueのrequirement/design/plan、親Epic docs、既存source/testsである。workerは許可path外の変更、managed stateの手修復、commit/push/mergeを行わない。必須出力はchanged files、verification、未解決risk、report更新内容であり、path外・仕様衝突・検証不能は停止条件とする。

## 11. ロールバックと中断条件

resolver/tests/READMEの変更をIssue diff単位で戻せば、既定depthは従来値へ戻る。ユーザー既存変更やSpecDock updater差分を対象に含めない。次の場合は実装を止め、reportとユーザー報告で指示を待つ。

- fresh spec-reviewerがfailまたは要件gapを指摘した。
- `depth=0`を未指定として扱う実装しか成立しない。
- traversal/VCS/DTOの変更が必要になった。
- Git comparison semantics、parse frontier、unlimited explicit inputの要件が変更された。
- required test/lint/SpecDock validationが環境要因以外で解消できない。

## 12. 未確定事項

実装順序、責務配置、検証範囲について未確定事項はない。明示的unlimited diffは別Issueへ延期し、今回のplanではsentinel追加を行わない。レビューで新たな判断が必要になった場合だけplan amendmentを行い、fresh spec reviewへ戻る。
