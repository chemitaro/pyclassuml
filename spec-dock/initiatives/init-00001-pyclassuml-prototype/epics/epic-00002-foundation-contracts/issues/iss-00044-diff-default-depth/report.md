---
種別: 実装報告書（Issue）
ID: "iss-00044"
タイトル: "Diff Default Traversal Depth"
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-08-04"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00002", "init-00001"]
---

# iss-00044 Diff Default Traversal Depth — 実装報告（観測証跡台帳 / Observed Evidence Ledger）

> `report.md` は観測証跡台帳（observed evidence ledger）です。planned requirements、evidence destination、closure 条件は `plan.md` が所有し、この文書は実際の Red / Green / Refactor evidence、発見された tests、closure delta、reviewer status、commit/no-op evidence を記録する。

## 仕様解釈・判断台帳（Spec Interpretation / Decision Ledger / 必須）

`report.md` は実装中・文書更新中に発生した material な仕様解釈、判断、plan 逸脱、tradeoff、open question、promotion / follow-up を記録する audit trail でもある。worker の raw note や作業 transcript を貼る場所ではなく、orchestrator が source docs、diff、tests、reviewer output と照合して issue-level の canonical entry に統合する。

Material な判断がない場合もこの section は残し、次を明示する。

- No material interpretation changes.
- No decision entries.

Ledger entry は次の契約値を使う。

- `Status`: `open` / `resolved` / `superseded`
- `Type`: `interpretation` / `scope` / `implementation` / `compatibility` / `test-strategy` / `operation` / `deviation` / `follow-up`
- `Disposition`: `applied` / `rejected` / `promoted_to_design` / `promoted_to_adr` / `promoted_to_plan` / `converted_to_followup` / `deferred` / `no_action` / `superseded`

完了時の意味論（completion semantics）:
- issue completion 前に `Status=open` の entry を残してはならない。
- `Status=resolved` は `Disposition`、evidence、必要な follow-up を持つ。
- `Status=superseded` または `Disposition=superseded` は置換先 entry ID を持つ。
- `Disposition=promoted_to_design` / `promoted_to_adr` / `promoted_to_plan` は昇格先 artifact と evidence を持つ。
- `Disposition=converted_to_followup` は follow-up issue / discussion / ADR candidate の参照を持つ。
- `Disposition=deferred` は scope 外である理由、blocking でない根拠、revisit 条件を持つ。
- `Disposition=no_action` は issue-local な判断で追加対応不要である理由を持つ。将来も効く durable decision を `report.md` だけに閉じ込めてはならない。

Disposition ごとの必須証跡:
- `applied`: 変更した artifact / 実装証跡と、issue-local 適用で十分な理由。
- `rejected`: 却下した選択肢、理由、blocking impact が残らない根拠。
- `promoted_to_design` / `promoted_to_adr` / `promoted_to_plan`: 昇格先 artifact 参照と証跡。
- `converted_to_followup`: follow-up issue / discussion / ADR candidate 参照と blocking / non-blocking の分類。
- `deferred`: scope-out 理由、non-blocking の根拠、revisit 条件。
- `no_action`: 判断が issue-local で durable ではない理由。
- `superseded`: 置換先 entry ID と置換理由。

| 識別子（ID） | 状態（Status） | 種別（Type） | 起票元（Raised By） | 契機 / 差分（Gap） | 検討した選択肢 | 判断 / 解釈 | 根拠（Rationale） | 処置（Disposition） | 証跡（Evidence） | フォローアップ（Follow-up） |
|---|---|---|---|---|---|---|---|---|---|---|
| D-001 | resolved | operation / deviation | orchestrator | SpecDock update前に作成されたIssue scaffoldは、更新後planning parserのfront matter契約と一致せず、formal planning preflightが `planning_context_rejected` になった。 | managed stateを手編集で修復する; formal routeを同期後に再試行する; 最新ユーザー指示に従いChatGPT-Use local-context advisoryで仕様候補を作る | `.serena/project.yml`、Issue update差分、managed bundleは保持した。formal Candidate/applyは未実施と明示し、完了済みChatGPT advisoryを証拠としてcanonical requirement/design/planへ統合した。manual backupは採用せず、ChatGPT-First試験導線のlocal-context evidenceとして扱った | `spec-dock update .`、`validate`、`doctor`、`git diff --check`は更新後に確認済み。formal `planning create`はIssue schema不一致とdetached HEAD `8bb20e9faa06` のGitHub exact HEAD不成立で停止。最新ユーザー指示はChatGPT-Useによる仕様作成を優先した | applied | `./spec-dock/scripts/spec-dock update .`; `./spec-dock/scripts/spec-dock assurance classify --stage requirement --issue iss-00044 --format json`; `artifacts/20260804t093411z-chatgpt-output-chatgpt-depth-design-review.md`; `pyclassuml-depth-review-reduced`; canonical `requirement.md`/`design.md`/`plan.md` | fresh `spec-reviewer #15` pass後にS00-PROMOTEでreport gate、canonical design/runtime readinessを確認し、formal routeとの差分を再確認する |
| D-002 | resolved | compatibility / test-strategy | orchestrator | `diff` の未指定 defaultを `1`にすると、旧来の `None` 相当の無制限diffを明示指定する現行経路がなく、depthはparse範囲ではなくtraversal/render frontierを制限する | `diff` default=1をbreaking changeとして採用; unlimited表現を同一Issueに追加; unlimitedを別Issueへ延期 | `generate=None`、CLI > config > command default、traversal/VCS collector非変更をrequirement/design/planへ採用。unlimited sentinelは追加せず、現行制約として文書化した。parse frontier非連動も採用した | `parse_target_set()`はdepth非依存でcandidateをparseし、`traverse_dependencies()`がhopを制限することをlocal sourceで確認。既存CLI/configは非負整数のみである | deferred | `artifacts/20260804t093411z-chatgpt-output-chatgpt-depth-design-review.md`; `src/pyclassuml/parse/indexer.py`; `src/pyclassuml/analyze/traversal.py`; baseline focused tests 144 passed | unlimited explicit inputは別Issueで再検討する。実装ではresolver/app regressionとREADME契約を閉じる |
| D-003 | superseded | scope / deviation | user instruction + orchestrator | 親Epic `epic-00002`の現行planがM1の6 Issueを閉鎖範囲として列挙していたため、当初はIssue-local exceptionだけで扱った | 親Epic planへ追加してM1 scopeを再定義する; Issue-local exceptionだけで扱う | 親Epic planのcanonical scope exceptionへ昇格したため、旧Issue-local-only判断はD-006へ置換する | D-006、親Epic `plan.md`のcorrective issue exception | superseded | D-006; parent `epic-00002/plan.md`; source task delegation `019fcba8-ca5e-71d2-a6a7-ddec18085eff` | D-006が親EpicとIssueのclosure ownerを明示する |
| D-004 | resolved | test-strategy | dev-coder S00 + orchestrator | fresh reviewer #5が指摘したEC-002/004/005 named testの不在により、planのfocused pytest commandが実行不能だった | named testを本番実装と同時に追加する; production source変更前のS00 test-only preparationで追加する | `tests/app/test_diff.py`、`tests/analyze/test_traversal.py`、`tests/parse/test_module_parse_and_index.py`を変更し、複数changed seedのhop 0、複数candidateの同一hop、`AnalysisConfig(depth=1)`下の深いsyntax diagnostic保持を固定した。production source/README/SpecDock/skillは変更していない。深いtransitive fixtureへ更新後、EC-002 testは旧resolverで意図的にRedになった。追加のconfig/bind/generate exact contract testもtest-only workerで準備した | 深いfixture更新前は指定3 nodeidが3 passed、app 59、traversal 15、parse 44だった。更新後はEC-002 named testが`reachable_file_count 4 != 3`でRed、appは58 passed/1 failed。追加workerは4 passed/1 intended Red、config 47 passed/1 failed、bind 11 passed、generate 18 passedで、旧resolverがdefault depthを検出できることを確認した | applied | `tests/config/test_context_resolve.py`; `tests/cli/test_bind.py`; `tests/app/test_generate.py`; `tests/analyze/test_traversal.py`; `tests/parse/test_module_parse_and_index.py`; `EXEC-S00-TEST-CONTRACT`; dev-coder worker results | S00 exact extensionとfresh spec-reviewer #8/#9/#10/#11の指摘修正後に、fresh spec-reviewer #12で実装前ゲートを再確認する。format driftはissue scopeを拡大せず最終品質ゲートで再評価する |
| D-005 | resolved | operation / test-strategy | spec-reviewer #6 + orchestrator | Ruffがproject dependencyに定義されず、全体lint/format baseline failureの再現性・ownerが未固定だった | Ruffをproject dev dependencyへ追加して全体baselineを修復する; pinned external toolとIssue-scoped gateを採用し、既存baselineを別maintenance ownerへ残す | `ruff==0.9.3`を`uvx --from`で固定し、全体lint/formatを診断、Issue変更pathのlintを必須化する。実装前の4 F821（`render/document.py`）と32 format対象は今回のscope外として明示し、新規errorのみblockingとする。exact contract extension後のfull pytestは443 passed/2 intended Redで、いずれも新規default contract testである | `uvx --from ruff==0.9.3 ruff --version`は0.9.3、deep fixture追加前のfull pytestは439 passed、exact extension後は443 passed/2 intended failure、scoped test lintはpass。Ruff全体baseline failureはsource未変更の既存状態であり、別repository maintenance ownerへdeferする。scoped formatの6 files非0は既存行由来で、追加blockのformat driftは修正または確認済み | applied | plan §9 quality baseline; `pyproject.toml`; `uv.lock`; `src/pyclassuml/render/document.py`; `EXEC-S99-TOOLING-BASELINE`; current pytest/Ruff output | production implementation後もbaseline外の新規ruff errorを許容しない。全体baselineの恒久修復は別Issueで扱う |
| D-006 | resolved | scope / deviation | doc-writer + user instruction | fresh spec-reviewer #8がIssue-local-only exceptionでは親Epic closure scopeを判断できないと指摘した | 親Epic M1へiss-00044を追加して再定義する; 親Epic planへM1計画外corrective issue exceptionをcanonical化する | `iss-00044`をM1の6 Issue closureへ算入せず、E-RQを変更せず、ユーザー承認済みのPyClassUML本体補正Issueとして親Epic planに明記した。closure ownerはIssue-local `requirement/design/plan/report`とする | parent `epic-00002/plan.md`のout-of-plan exception節、source task delegation `019fcba8-ca5e-71d2-a6a7-ddec18085eff`、doc-writerのvalidate/doctor結果 | applied | parent `epic-00002/plan.md`、`spec-dock validate` nodes=41、`doctor findings=0` | 親EpicのM1再定義が必要になった場合は別途Epic plan reviewを行う。今回のIssue scopeは変更しない |

| D-007 | resolved | operation / deviation | fresh spec-reviewer #9 + orchestrator | canonical designは内容が実質的でもfront matterの`状態: "draft"`がruntimeの`design-not-substantive`を発生させ、runbookをblockedにしていた。review passだけをS01条件にすると、design promotionとworkflow readinessが未定義のまま実装へ進める余地が残る | review前にdesignをapprovedへ変更する; review pass後のS00-PROMOTEでcanonical statusをapprovedへ更新し、active/runbook/assurance/SpecDockを正規コマンドで再生成・検証する | review前のdraft/blockedは保持し、fresh reviewer #15 pass後だけcanonical design statusをapprovedへ更新するS00-PROMOTE、tc-010、EXEC-S00-PROMOTEをplanへ追加した。active/runbook/metadataは手編集せず、spec-managerの`active set`、assurance、workflow/guidance、validate/doctor/diff-checkでreadyを確認する | workflow source `workflow_spec_authoring.md` / `workflow_issue.md`、fresh reviewer #9 finding、current `guidance issue-execution`の`design-not-substantive`、plan S00-PROMOTE/tc-010 | applied | plan S00-PROMOTE、`design.md`はreview前draft維持、`workflow/guidance`現状blocked、fresh #15 required | fresh #15 pass後にmain orchestratorがcanonical design front matterだけをapprovedへ更新し、spec-managerが正規projectionを更新・検証する。runbookがreadyにならない場合はS01を開始しない |

| D-008 | resolved | operation / follow-up | fresh spec-reviewer #10 + orchestrator | fresh reviewer passをcanonical reportのReviewer Gate / Spec Authoring Gateへ反映してからdesign promotionとworkflow readinessを評価する順序、およびpost-promotion active scope証跡がplanに不足していた | fresh pass後にreportを更新しない; report gate更新→canonical design promotion→post-promotion active show→workflow/runbook/assurance/SpecDock検証の順序をS00-PROMOTEへ追加する | S00-PROMOTE、tc-010、CASE-S00-PROMOTE-001を拡張し、#15 pass後のreport更新、`active set`直後の`active show`、report/projection一致をS01 admission条件に固定した | fresh #10 findings、workflow_issue.md / workflow_spec_authoring.mdのreport evidence gate、current runbook blocked state | applied | plan S00-PROMOTE/tc-010、report current gate #1〜#14 fail/#15 required、fresh #15 required | fresh #15 pass後にreport gateを更新し、S00-PROMOTEをcommand-firstで実施する。readyにならなければS01を開始しない |
| D-009 | resolved | quality-gate scope | fresh spec-reviewer #11 + orchestrator | EAL-005のfull-suite環境差異がS00-PROMOTE/S01のadmission blockerなのか、S99 final-quality blockerなのかが文書間で曖昧だった | full-suite/RuffをS00-PROMOTE前に必須化する; S99までnon-blockingに延期する | EAL-005を`S00-PROMOTE/S01ではnon-blocking、S99ではblocking`と再分類し、ownerをorchestrator/qa-reviewer、focused evidenceと再現条件を保持する。S99ではgreen full-suiteまたはsupported verification pathを必須とする | fresh #11 P1、plan §2/S00-PROMOTE/S99、EAL-005 | applied | plan/reportのgate scope、S99 final quality contract | fresh #12 reviewでgate scopeの一貫性を再確認し、S99前にfull-suite/Ruffを再実行する |
| D-010 | resolved | evidence preservation | fresh spec-reviewer #11 + orchestrator | ChatGPT artifactの採用receiptにoutput form、preservation status、capture boundary、import kind、source/destination identity、byte countが不足していた | 不完全receiptのままadoptedを維持する; receiptを実測値で補完する | `pyclassuml-depth-review-reduced-answer.md`をexternal source basenameとして、`import_kind=chatgpt-output`、`output_form=complete_standalone_markdown`、`preservation_status=imported_byte_exact`、destination、24635 bytes、SHA-256、`committed=true`、warningなし、`diff -q` passをEAL/reportへ追加した。絶対host pathは記録しない | fresh #11 P1、chatgpt-pack preservation checkpoint、artifact `shasum`/`wc`/`diff -q` | applied | EAL-001、ChatGPT-First observation、artifact receipt | fresh #12でreceipt completenessとadvisory-only adoptionを再確認する |
| D-011 | resolved | test-strategy / integration | fresh spec-reviewer #11 + orchestrator | designが要求するtop-level config `depth=2`のapplication pathにexact app nodeidがなく、resolver-level testだけではapp wiringを検出できなかった | resolver-level evidenceだけで閉じる; S00 test-only app integrationを追加する | S00 allowed test pathの`tests/app/test_diff.py`へ`test_diff_config_depth_two_reaches_transitive_dependency`を追加する契約をplan/design/tc-006へ固定した。production source変更なしで旧resolverのRedを許容し、実装後にgreenへ閉じる | fresh #11 P2、design §8.2、plan tc-006/CASE-S02-002 | applied | plan/design修正、S00 dev-coder bounded task、`SPEC-REVIEW-011` | S00 test resultを取り込み、fresh #12でclosure exactnessを再確認する |
| D-012 | resolved | workflow evidence / audit | fresh spec-reviewer #12 + orchestrator | reportに`Grade Specialist Evidence Gate`がなく、Standard profileのspecialist use/skip/manual fallbackをexecution readinessへ接続できなかった。またdelegated worker rowsにrequired decision-noteがなかった | gateを追加せずreview passへ進む; named specialistsを実際に再起動する; reportへStandard skip/manual evidenceと各workerのno-material decision-noteを追加する | user-selected ChatGPT-First/ChatGPT-Use advisoryを使った理由、named `system-architect`/`implementation-planner` skip reason、manual canonical integration、#12 fail/#13 requiredをGrade Specialist Evidence Gateへ追加した。S00 worker rowsへexact `No material implementation decisions beyond the approved plan.`を記録した。新たなsource/README/skill/managed-state変更は行わない | fresh #12 P1/P2、`workflow_spec_authoring.md` grade matrix/report gate、`workflow_issue.md` worker decision-note contract、issue report template | applied | report Grade Specialist Evidence Gate、worker evidence rows、`SPEC-REVIEW-012`、fresh #15 required | #15 pass後にreport-first S00-PROMOTEへ進み、未passなら追加修正する |
| D-013 | resolved | scope / compatibility / workflow evidence | fresh spec-reviewer #13 retry + orchestrator | PyClassUMLの公開CLI `diff`既定挙動を変更するIssueについて、Standard authorityを維持する適用範囲とStrict相当の補償ゲートがcanonical docsに明示されておらず、Test Contract Closureが`tc-010`を列挙していなかった | SpecDock managed stateを手修正してStrictへ自己再分類する; product CLIの挙動変更を否認してStandardを維持する; SpecDock運用契約とPyClassUML product contractを分離し、Standard適用例外・再分類条件・補償ゲートをcanonical requirement/designへ追加し、`tc-010`をclosureへ追加する | PyClassUMLのruntime behavior変更は明示的に認める。既存`diff` / `--depth`入力面、型、config schema、終了契約、SpecDock自身の公開CLI/workflow/metadata/stateは変更しないため、現行`authorized_profile=standard`を維持する。これは互換性リスクの免除ではなく、ChatGPT-Use local verification、fresh spec review、focused/full tests、VCS/read-only/no-import inspection、README、code/QA reviewを必須化する補償判断である。`.assurance.json`は正規CLI生成物のため手編集しない | fresh #13 P1/P2、standard/strict profile templates、`workflow_spec_authoring.md` grade matrix、current assurance CLI help/source、plan closure index | applied | requirement §10.1、design §1.1、plan S00-PROMOTE/tc-010、report Test Contract Closure/Closure Coverage、`SPEC-REVIEW-013` | fresh #14でこのscope exception、compensating gates、closure mappingを再判定する。reviewerがproduct CLIをStrict triggerと判定する場合は、実装前にユーザー判断またはrisk-fact対応の正式routeを必要とする |

| D-014 | open | scope / operation / workflow evidence | fresh spec-reviewer #14 + orchestrator | 現行standard profileの`公開CLI挙動を変更する`Strict triggerは、Issue-localなStandard scope exceptionやmanual compensating gateでは上書きできない。さらにtc-010は範囲表記だけではrequired closureごとの個別証跡にならない | SpecDock policy/assuranceを本体Issueの範囲外で変更する; managed `.assurance.json`を手修正してStrictを自己主張する; ユーザー承認のもとで正式Strict分類またはpolicy-supported exceptionを確定し、tc-010個別行を追加する | #14はStandard結論を不受理。P2の個別tc-010行はcanonical reportへ追加する。P1は正式なStrict分類またはSpecDock policy-supported exceptionが必要で、実装・promotionを停止する。現在のAssurance CLIにprofile/risk-fact入力経路がないため、追加権限なしでの解消はできない | fresh #14 P1/P2、`spec-dock/templates/issue-profiles/standard/design.md` §1.3、`workflow_spec_authoring.md` grade matrix、`workflow_issue.md` closure contract、current assurance CLI help/source | deferred | #14 review output、D-014、reportの個別`tc-010 / EXEC-S00-PROMOTE` closure | ユーザーが正式Strict routeまたはpolicy変更の範囲を決定するまでblocking。決定後、canonical docsと正規assurance projectionを更新し、fresh #15を取得する |

## 証跡採用台帳（Evidence Adoption Ledger / 必須）

Delegated draft、worker note、research、reviewer finding、discussion、command output を canonical artifact や実装判断へ取り込む場合、この台帳に採用判断を記録する。raw transcript ではなく、orchestrator が検証した採否・理由・証跡・次アクションだけを記録する。

- `adoption_status`: `adopted` / `partially_adopted` / `rejected` / `deferred` / `stale` / `blocked`
- `blocked` または `stale` の unresolved entry は promotion / implementation start / issue ready / issue finish / phase completion を止める。
- `deferred` は blocking でない根拠と revisit 条件を持つ場合だけ完了時に残せる。
- Evidence Adoption Ledger なしで delegated evidence の採用を主張してはならない。
- Evidence Adoption Ledger fields: ID, adoption_status, source, source_role, claim, target_artifact, target_section, rationale, evidence_strength, evidence_path, adopter, reviewer, blocking, next_action.

| ID | adoption_status | source | source_role | claim | target_artifact | target_section | rationale | evidence_strength | evidence_path | adopter | reviewer | blocking | next_action |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EAL-001 | adopted | external advisory / local verification | ChatGPT-Use advisory + orchestrator | resolverをcommand defaultのownerとし、CLI未指定を`None`のまま保持し、DTO/traversal/VCS collectorへdefault policyを移さない。`diff`未指定=1、`generate`未指定=None、CLI > config > default、明示0優先 | `requirement.md`, `design.md`, `plan.md` | scope / design / steps S01-S02 / closure index | advisoryの関係整理だけを採用し、GitHub exact HEAD等の未検証claimは採用しない。canonical docsへ反映した内容をsource構造とbaseline testで照合した。保存receiptは完全なstandalone Markdownのbyte identityを実測し、保存とcanonical adoptionを分離した | strong for responsibility analysis; provisional for implementation until tests | preservation receipt: `output_form=complete_standalone_markdown`; `preservation_status=imported_byte_exact`; `capture_boundary=ChatGPT-Use answer file -> imported Artifact`; `import_kind=chatgpt-output`; `storage_identity=blank`; `source_basename=pyclassuml-depth-review-reduced-answer.md`（external Workbench、絶対host pathは非記録）; `destination_repo_relative=spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00002-foundation-contracts/issues/iss-00044-diff-default-depth/artifacts/20260804t093411z-chatgpt-output-chatgpt-depth-design-review.md`; `byte_count=24635`; SHA-256 `a1fd48017f60c04f511ce831b6ae0761f32d04967c4ea33603adccdd698f59cc`; `committed=true`; `warning=none`; `diff -q` pass; plus `src/pyclassuml/config/resolver.py`, `src/pyclassuml/cli/bind.py`, `src/pyclassuml/analyze/traversal.py`, `src/pyclassuml/vcs/diff_collect.py`, `EXEC-PLANNING-001`（実装前local verification、focused baselineのみ） | orchestrator | fresh spec-reviewer #1/#2/#3/#4/#5/#6/#7/#8/#9/#10/#11/#12/#13/#14 fail | yes until fresh pass | #13 retry findings were repaired in D-013; #14 P1 remains open; fresh spec-reviewer #15 required |
| EAL-002 | deferred | command / workflow preflight | SpecDock planning transport | formal `planning create`はIssue schema不一致とGitHub exact HEAD不成立でCandidateを生成できなかった。これはcanonical docsの内容ではなく同期済みbranchを要求するformal transportの制約 | formal ChatGPT-First Candidate lifecycle | workflow / promotion boundary | local-context advisoryによる仕様作成を妨げず、formal Candidate/apply未実施を明示する。branch/HEAD同期時にformal routeとの差分を再確認する | direct command evidence; non-blocking workflow limitation | `planning create` -> `planning_context_rejected`; `gh api .../commits/8bb20e9faa06` -> no commit found; detached HEAD; `EXEC-PLANNING-001` assurance verify -> ok after canonical reclassification | orchestrator | fresh spec-reviewer #1/#2/#3/#4/#5/#6/#7/#8/#9/#10（content gateとは別のdeferred transport） | no | 同期可能時にformal Candidate/applyとの同一性を再確認する |
| EAL-003 | rejected | ChatGPT-Use recovery | ChatGPT-Use attempted authoring session | 3文書生成を依頼したsessionの初回応答はHEAD注意書き1文だけで、follow-upも本文を生成しなかったためcanonical docsへ採用しない | none | evidence rejection only | 未完了/UI placeholderを仕様根拠にしない。完全な設計レビュー `pyclassuml-depth-review-reduced` だけを採用根拠とする | conclusive rejection | `pyclassuml-iss00044-spec-authoring`; `required-repository-connector-context-repository-6/7/8`; harvested output 169 bytes / UI placeholder | orchestrator | browser recovery diagnostics; no canonical promotion | no | なし |
| EAL-004 | adopted | delegated test-only worker | dev-coder + orchestrator | EC-002/004/005とtc-001〜tc-004/tc-006のnamed testを追加し、S02/S99の実行契約を実行可能にした | `plan.md`, `report.md`, test files | S00 evidence / EC closure / TDD | test-only scopeに限定し、workerのformat drift観測はsource実装判断へ拡張しない | strong for test existence and behavior; format status remains pre-existing risk | `EXEC-S00-TEST-CONTRACT`; six test files; pre-deep focused output: 3 named passed, app 59, traversal 15, parse 44; post-deep EC-002 is intended Red; exact extension 4 passed/1 intended Red; explicit tc-006 depth=1/2 nodeid 1 passed; config tc-006 nodeid 1 passed; current app suite 60 passed/1 intended Red; scoped `ruff check` pass; `ruff format --check` baseline failure; `git diff --check` pass | orchestrator | fresh spec-reviewer #7/#8/#9/#10/#11/#12/#13/#14 fail | no | S00 six-path provenance、config app integration、full-suite環境差分、Standard scope exceptionの撤回、S00-PROMOTE report gate/active showを反映後、fresh spec-reviewer #15を取得する |
| EAL-005 | adopted | local verification after reviewer finding | orchestrator | current worktreeのfull pytestを、S00 deep fixture追加前のbaseline、coordinatorの現行Red、fresh reviewerの別環境failureに分けて記録し、Ruff tool/versionとbaseline failureを再現可能にする | `report.md`, `plan.md` | S99 final quality gate（S00-PROMOTE/S01ではnon-blocking） | coordinatorは同一worktreeで`443 passed / 2 intended Red`を再現した一方、fresh spec-reviewer #8は`438 passed / 7 failed`（うち`tests/cli/test_main.py`のDNS/依存解決5件）を観測した。両方を隠さず環境別evidenceとして分離する。fresh spec-reviewer #9/#10/#11の指摘と現行判断では、この環境差異はS00-PROMOTE/S01を止める仕様ゲートではなく、orchestrator/qa-reviewerがS99でgreen full-suiteまたはsupported verification pathを閉じるfinal-quality blockerである | strong for coordinator current worktree; environment variance remains blocking for final quality only | pre-deep `uv run pytest` -> `439 passed in 16.67s`; coordinator exact extension後 -> `443 passed, 2 failed`; focused all -> `226 passed, 2 failed`; reviewer #8 environment -> `438 passed, 7 failed`; added nodeids -> 4 passed/1 intended Red; `ruff 0.9.3`; full Ruff output captured in `EXEC-S99-TOOLING-BASELINE` | orchestrator / qa-reviewer | fresh spec-reviewer #7/#8/#9/#10/#11 fail | no for S00-PROMOTE/S01; yes for S99 | S00-PROMOTE/S01はfocused contractとSpecDock readinessで進め、S99前にfull-suite/Ruffを再実行し、environment varianceを解消またはsupported verification pathとして明示する |

## 目的整合台帳（Objective Alignment Ledger / 必須）

主要目的と副次要件の主従が逆転していないことを記録する。特に clarification / authoring / handoff の変更では、primary objective evidence、secondary requirement evidence、inversion risk、reviewer verdict を残す。

| 対象 | 主要目的の証跡（primary objective evidence） | 副次要件の証跡（secondary requirement evidence） | 逆転リスク（inversion risk） | レビュアー判定（reviewer verdict） |
|---|---|---|---|---|
| OAL-001 | `diff` の CLI/config 未指定時だけ traversal/render の default frontier を depth=1 にする | `generate` の default=None、CLI > config > command default、Git base/current-state/include-untracked semantics、read-only/deterministic constraints | medium（unlimited compatibility と parse/traversal terminology の誤記） | blocked（fresh spec-reviewer #1/#2/#3/#4/#5/#6/#7/#8/#9/#10/#11/#12/#13/#14 fail、P1解消後の#15再レビュー待ち） |

## 仕様 authoring ゲート（Spec Authoring Gate / 必須）

Requirement / design / plan の phase promotion ごとに、調査、未確定事項、回答、採用判断、reviewer verdict、blocking / non-blocking、次アクションを記録する。

| フェーズ（phase） | 調査証跡（investigated facts） | 未確定事項 / 回答（open questions / answers） | 採用判断（adoption decision） | レビュアー判定（reviewer verdict） | ブロック有無（blocking） | 昇格 / 次アクション（promotion / next_action） |
|---|---|---|---|---|---|---|
| requirement | `resolver.py`, `bind.py`, `contracts.py`, `parse/indexer.py`, `traversal.py`, `vcs/diff_collect.py`; research discussion; imported advisory; baseline 144 tests | 要件上のopen questionなし。formal Candidate lifecycleは未実施 | adopted from verified local advisory | fail（fresh reviewer #1: EC/traceability、#2: EC closure/INV-005/006、#3: tc-009実行経路、#4: gate/EC/INV/boundary wiring、#5: current gate、named test実在性、EC-008 negative inspection、親Epic scope exception、#6: Ruff/full-suite/EC-002 evidence、#7: current full-suite/report mismatch、closure exactness、format disposition、#8: S00 6-path provenance、explicit depth integration、親Epic scope、full-suite環境差分、#9: design promotion/runbook readiness、D-005 duplicate ID、#10: report gate update orderとpost-promotion active show、#11: EAL-005 gate scope、ChatGPT receipt、config app integration、#12: Grade Specialist Evidence Gate、worker decision-note、#13: product CLI grade rationale、tc-010 closure、#14: Standard profile Strict triggerとtc-010個別closureを指摘。修正中） | yes | #14 P1を解消し、fresh spec-reviewer #15でrequirementを再確認する |
| design | 既存Epic design、resolver/traversal/VCS contract、ChatGPT advisory、canonical requirement | 設計上のopen questionなし。GitHub未同期由来のformal evidenceは採用しない | adopted from verified local advisory | fail（fresh reviewer #1: bind/effective境界、#2: step-local execution contractとreport接続、#3: INV-005/006実行経路、#4:保護境界/step wiring、#5: current gateと親Epic scope、#6: quality baselineとEC-002 evidence、#7: current full-suite/report mismatch、closure exactness、format disposition、#8: S00 6-path provenance、explicit depth integration、親Epic scope、full-suite環境差分、#9: draft designがruntimeをblockedにするためpromotion/runbook transitionが不足、D-005 duplicate ID、#10: report gate update orderとpost-promotion active show、#11: EAL-005 gate scope、ChatGPT receipt、config app integration、#12: Grade Specialist Evidence Gate、worker decision-note、#13: product CLI grade rationale、tc-010 closure、#14: Standard profile Strict triggerとtc-010個別closureを指摘。修正中） | yes | Standard scope exceptionは撤回扱いとし、P1解消後にfresh spec-reviewer #15でdesignを再確認する |
| plan | canonical requirement/design、baseline focused tests、closure index | 実装結果とreviewer verdictは未観測 | adopted from verified local advisory | fail（fresh reviewer #1: VCS path/README checklist/owner、#2: closure全件とstep-local contract、#3: tc-009 parse/status/inspection手順、#4: EC/INV/境界の再現手順、#5: named test未生成、EC-008 negative check、親Epic scope、#6: Ruff/full-suite/EC-002 evidence、#7: current full-suite/report mismatch、closure exactness、format disposition、#8: S00 6-path provenance、explicit depth integration、親Epic scope、full-suite環境差分、#9: draft designのpromotion/runbook transitionとD-005 duplicate ID、#10: report gate update orderとpost-promotion active show、#11: EAL-005 gate scope、ChatGPT receipt、config app integration、#12: Grade Specialist Evidence Gate、worker decision-note、#13: product CLI grade rationale、tc-010 closure、#14: Standard profile Strict triggerとtc-010個別closureを指摘。修正中） | yes | P1解消後のS00-PROMOTEとfresh spec-reviewer #15 passまでS01を開始しない |

## 委任ドラフト証跡（Delegated Draft Evidence / 必須）
- 委任 authoring の使用:
  - used / not used
- 未使用の場合:
  - manual authoring path / 委任ドラフトを昇格証跡として使っていない理由。
- lifecycle state（契約値）:
  - `requested`, `produced`, `integrated`, `partially_integrated`, `rejected`, `superseded`, `blocked`, `stale`
- 昇格不可 state:
  - `stale`, `rejected`, `superseded`, `blocked`
- 標準出力先:
  - 対象 scope の `discussions/` direct child にある flat Markdown
  - filename: `<ts>-<kind>-<slug>.md` または same-second collision 用 `<ts>-<nn>-<kind>-<slug>.md`
- 軽量 provenance:
  - `created_by_role`, `scope_id`, `source_paths`, `intended_targets`, `adoption_status: unreviewed`, `reflected_to: []`, `diff_guard_result`, fallback decision, report evidence destination, adoption ledger note
  - 互換 label: source artifacts, draft artifact path, status, integration result, rejected portions, blockers, reviewer result, promotion decision
- 禁止 self-claim:
  - `authority: accepted`, `adoption_status: adopted`, non-empty `reflected_to`, reviewer pass, phase completion, implementation readiness
- 禁止 wildcard token:
  - `*`, `grants.*`, `all`
- 標準必須にしない field:
  - task manifest hash, Permission Profile hash, session invocation hash, probe run id, session hash
- historical note:
  - 既存 `iss-00126` などの manifest/Profile/probe/session artifacts は grandfathered evidence として残し、削除・rename・validation failure 化しない。

| ロール（created_by_role） | 範囲（scope_id） | ドラフトパス（discussion draft path） | 参照元（source_paths） | 予定反映先（intended_targets） | 採用状態（adoption_status） | 反映先（reflected_to） | 差分ガード結果（diff_guard_result） | 統合結果 | 採用しなかった部分 | ブロッカー | レビュー結果（reviewer result） | 昇格判断（promotion decision） |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 該当なし | 該当なし | 該当なし | 該当なし | 該当なし | 未使用（not used） | なし（[]） | 未実行（not_run） | 手動 authoring | 該当なし | なし（none） | 該当なし | 委任ドラフト昇格なし |

### 委任ドラフトの失敗モード（Delegated Draft Failure Modes）
| 失敗モード | 期待される判定 | 許可される次アクション | レポート証跡の記録先（report evidence destination） | 昇格可否 |
|---|---|---|---|---|
| 同意なし（missing consent） | blocked / incomplete | 範囲付き同意を取得する、または手動 authoring に戻す | この section | ineligible |
| 前段 reviewer pass 不足 / stale（missing/stale previous reviewer pass） | blocked / incomplete | レビューゲートを再実行する（rerun reviewer gate） | レビューゲート証跡（Reviewer Gate Status / Final Spec Review Gate） | ineligible |
| 設計中の要件 gap（requirement gap during design） | blocked / incomplete | requirement phase へ戻す | 仕様解釈・判断台帳（Spec Interpretation / Decision Ledger） | ineligible |
| 計画中の設計 gap（design gap during plan） | blocked / incomplete | design phase へ戻す | 仕様解釈・判断台帳（Spec Interpretation / Decision Ledger） | ineligible |
| ロール利用不可（role unavailable） | blocked / manual path | 利用不可を記録し、妥当なら手動で続行する | この section | ineligible |
| 禁止行為の試行（forbidden action attempt） | rejected | ドラフトを破棄し incident を記録する | この section / decision ledger | ineligible |
| 古いドラフト（stale draft） | stale | 再生成または差分調整する | この section | ineligible |
| 置換済みドラフト（superseded draft） | superseded | 置換先ドラフトを参照する | この section | ineligible |
| 委任使用主張に対する証跡不足（missing draft evidence when delegated use is claimed） | incomplete | 証跡を追加する、または委任使用 claim を外す | この section | ineligible |
| reviewer 利用不可 / 拒否 / waiver / provisional（reviewer unavailable/denied/waived/provisional） | blocked / incomplete | fresh な passed reviewer を取得する、または昇格なしの risk acceptance を記録する | レビューゲート証跡（Reviewer Gate Status / Final Spec Review Gate） | ineligible |

#### グレード別専門家証跡ゲート（Grade Specialist Evidence Gate / 必須）

assurance classify の `authorized_profile=standard` に対応する。ユーザーの最新指示により ChatGPT-Use を試行し、SpecDock named specialist の直接 authoring は行わず、manual canonical authoring と local source/tests verification を採用した。これは execution-ready の代替ではなく、fresh spec-reviewer と S00-PROMOTE を引き続き要求する。

| グレード（Grade） | 必要な専門家 / 代替（required specialist / fallback） | 使用状況（usage） | 証跡（evidence） | 鮮度 spec-reviewer 判定（fresh spec-reviewer verdict） | 実行可否（execution readiness） |
|---|---|---|---|---|---|
| `standard` | `system-architect / implementation-planner / manual fallback` | `system-architect` / `implementation-planner`: skipped; ChatGPT-Use advisory: used; manual fallback: used for canonical single-writer integration; Standard scope exception: rejected by fresh #14 | skip reason: user explicitly selected experimental ChatGPT-First and ChatGPT-Use specification authoring; parent Epic design plus local source/tests were sufficient to resolve the bounded responsibility/precedence questions; product runtime behavior change is recorded, but SpecDock public CLI/workflow contract is unchanged; `EAL-001`, imported ChatGPT artifact, `EXEC-PLANNING-001`, requirement §10.1, design §1.1, local test evidence; manual authoring is not promoted without fresh review | #14 `fail`; #15 required after formal Strict/policy resolution | `blocked` |

## 実装前 fresh spec review（2026-08-04）

初回の独立 `spec-reviewer` は `fail`。実装は開始せず、次の仕様・証跡修正を行う。

| 優先度 | 指摘 | 修正内容 | 状態 |
|---|---|---|---|
| P1 | `plan.md` が参照するEC-001〜EC-008を`requirement.md`が定義していない | §8の各エッジケースへEC IDを付与し、`tc-007`の参照を整合 | resolved |
| P1 | bind直後の`None`とresolver後の`diff=1`が混同され得る | S02の`tc-s02-001`にraw `CommandOptions`とeffective `AnalysisConfig`の別assertionを明記 | resolved |
| P1 | S02のVCS回帰コマンドに`tests/vcs/test_diff_file_collect.py`がない | S02およびS99の実行対象へ追加 | resolved |
| P1 | EAL-001のadvisory provenanceと既存検証コマンドの記録が不足 | EAL必須fieldを列化し、`assurance verify`、`validate`、`doctor`、focused 144 tests、`git diff --check`の実測結果を追加 | resolved |
| P2 | AC-006不変条件の個別追跡が弱い | `INV-001`〜`INV-006`をrequirementへ追加 | resolved |
| P2 | README検証項目の列挙数が曖昧 | `DOC-001`〜`DOC-007` checklistと`tc-s90-001`の対応をplanへ追加 | resolved |
| P2 | SpecDock直接コマンドのownerがplan上不明 | `spec-manager`委任を原則とし、必要時のbounded direct実行例外と記録方法を明記 | resolved |

修正後に同じ範囲のfresh `spec-reviewer`を再実行し、`pass`を得るまでS01実装へ進まない。

## 実装前 fresh spec review #2（2026-08-04）

修正後の独立 `spec-reviewer` も `fail`。主要な責務境界はpass相当と確認されたが、次の検証契約・証跡修正を実装前に追加する。

| 優先度 | 指摘 | 修正内容 | 状態 |
|---|---|---|---|
| P1 | EC-001〜EC-008のうちclosure indexが一部しか参照していない | closure indexをAC/EC全件のownerへ拡張し、edge closure対応表を追加 | resolved |
| P1 | INV-005/006が抽象的でnamed pathとreport先が不足 | syntax/parse regression test、AST-only/read-only source inspection、`tc-009`を明記 | resolved |
| P1 | S01/S02/S90/S99のstep-local obligationと停止条件が不足 | §5.1へRed/代替証跡、guardrail、evidence destination、amendment、委任入出力、stop conditionを追加 | resolved |
| P1 | reportの現行レビュー状態と各台帳にテンプレート値が残る | fresh review #2、未実施step、委任/レビュー/commit/Final Quality Gateを実値へ更新 | resolved |
| P2 | EAL-001の実測コマンドへの直接リンクが弱い | `EXEC-PLANNING-001`を付与し、advisory baselineとVCS未実施を区別 | resolved |

この修正後に fresh `spec-reviewer #3` を実行し、`pass`を得るまでS01実装へ進まない。

## 実装前 fresh spec review #3（2026-08-04）

修正後の独立 `spec-reviewer` は `fail`。既定値、責務境界、EC/INV mapping、step contract、EAL分離は整合したが、`tc-009`の個別実行経路とreport状態に次の修正が必要とされた。

| 優先度 | 指摘 | 修正内容 | 状態 |
|---|---|---|---|
| P1 | INV-005/006のnamed parse test、AST-only inspection、前後Git statusがS99の実行手順に未固定 | S99へnamed pytest、`rg` source inspection、前後`git status --short`の順序、期待値、`EXEC-S99-INV-005-006`記録先を追加 | resolved |
| P1 | Step Contract Closureの`approved-no-op`がreview fail/blockingと矛盾 | planning/S01 resultを`blocked`/`not_started`へ修正し、承認済みを示さない状態へ統一 | resolved |

この修正後に fresh `spec-reviewer #4` を実行し、`pass`を得るまでS01実装へ進まない。

## 実装前 fresh spec review #4（2026-08-04）

修正後の独立 `spec-reviewer` は `fail`。#1〜#3の修正は確認されたが、current gateの同期、EC/INVのowner wiring、protected baseline、step-local case cardsについて追加修正が必要とされた。

| 優先度 | 指摘 | 修正内容 | 状態 |
|---|---|---|---|
| P1 | reportの一部next-actionが#4 passのまま | D-001、EAL、delegation/reviewer/S90/problem/memoのcurrent stateを#1〜#4 fail、#5 requiredへ統一 | resolved |
| P1 | EC-005がdepth=1のnamed behavior testに接続されていない | `AnalysisConfig(depth=1)`のparse diagnostic testをS02/tc-007/tc-009へ配線 | resolved |
| P1 | INV-006の禁止token検査がnamed function範囲を示さない | `sed`で`parse_target_set`/`parse_module_source_text`範囲を表示し、禁止token `rg`のexit 1を期待値化 | resolved |
| P1 | EC-004/EC-008のinspectionがowner stepへ未配線 | S02のcandidate inspection、S90のCLI/config schema inspection、EXEC ID、report先を追加 | resolved |
| P1 | protected boundary baselineの完全なstatus・所有者分類が不足 | 317 status entriesとpath別分類、実装前後比較コマンドをreportへ追加 | resolved |
| P2 | #3修正のClosure Deltaが未記録 | `SPEC-REVIEW-003`に対応するtc-009/EXEC-S99 deltaを追加 | resolved |

この修正後に fresh `spec-reviewer #5` を実行したが、`fail`。以下の指摘を解消し、fresh `spec-reviewer #6`が`pass`するまでS01実装へ進まない。

## 実装前 fresh spec review #5（2026-08-04）

修正後の独立 `spec-reviewer` は `fail`。#1〜#4の修正は確認されたが、実行可能性と親Epicのscope接続に追加修正が必要とされた。

| 優先度 | 指摘 | 修正内容 | 状態 |
|---|---|---|---|
| P1 | reportのcurrent gateが#4のみを参照し、#5のfail後に実装停止理由が同期していない | EAL/OAL/phase/delegation/worker/parent/S90/final qualityのlive fieldsを#1〜#5 fail、#6 required/pass待ちへ更新 | resolved |
| P1 | EC-004/005のnamed testが現行testsに存在せず、そのままではpytestがexit 4になる | S00 test-only preparationをplanへ追加し、`tests/analyze/test_traversal.py::test_multiple_import_candidates_share_same_hop`と`tests/parse/test_module_parse_and_index.py::test_parse_target_set_keeps_deeper_syntax_diagnostic_with_depth_one`をproduction source変更前に生成する | applied; worker dispatch pending |
| P1 | EC-008のpositive rgだけでは`[diff].depth` / unlimited sentinelの不在を検査できない | schema positive evidenceに加え、禁止tokenのnegative `rg`（exit 1 / no output）を`EXEC-S90-EC-008`へ固定 | resolved |
| P1 | 親Epic planは6 IssueのM1 closureを列挙し、iss-00044を含まない | 親EpicのM1 scopeを再定義せず、ユーザー承認済みのIssue-local out-of-plan exceptionをD-003としてDecision Ledgerへ記録 | resolved |

S00のtest-only preparation完了後にSpecDock assurance/validate/doctor/diff checkを再実行し、fresh `spec-reviewer #6`を取得した。

## 実装前 fresh spec review #6（2026-08-04）

S00後の独立 `spec-reviewer` は `fail`。#5の実行可能性・negative inspection・scope修正は確認されたが、品質ツールbaseline、full-suite evidence、EC-002のnamed testに追加修正が必要とされた。full pytestの環境失敗指摘は、同じcurrent worktreeでの再実行により反証されたため、source-grounded evidenceを優先して却下する。

| 優先度 | 指摘 | 修正内容 | 状態 |
|---|---|---|---|
| P1 | Ruffが`pyproject.toml`/`uv.lock`に定義されず、全体lint/formatがbaseline failureを持つため、S99の再現性とownerが不明 | `ruff==0.9.3`のpinned command、実装前4 F821/32 format baseline、Issue-scoped lint必須、baseline恒久修復は別maintenance ownerという契約をplan §9へ追加 | resolved |
| P2 | full pytestがDNS由来の5 failureになったというevidenceがreportにない | current worktreeで`uv run pytest`を再実行し`439 passed in 16.67s`を確認。reviewerの異なる環境の434+5 failureはcurrent evidenceと矛盾するためrejected/stale | resolved; rejected as stale external observation |
| P2 | EC-002がgeneric multi-seed app testで、named nodeid/assertionがない | S00 extensionとして`tests/app/test_diff.py::test_diff_changed_seed_files_each_remain_hop_zero_at_default_depth`を追加し、1 passed / app suite 59 passedを確認 | resolved |

S00 extensionのtest-only preparation、pinned Ruff diagnostics、assurance refresh後にfresh `spec-reviewer #7`を取得する。production source implementationは引き続き保留する。

## 実装前 fresh spec review #7（2026-08-04）

S00 extension後の独立 `spec-reviewer #7` は `fail`。#1〜#6の主要修正は確認されたが、現行evidenceとの同期、closureの実在性、format baselineの扱いに追加修正が必要とされた。production source implementationは開始しない。

| 優先度 | 指摘 | 修正内容 | 状態 |
|---|---|---|---|
| P1 | reportのfull pytest evidenceが、reviewerが観測した `440 collected / 435 passed / 5 DNS failures` と、既存reportの`439 passed`のどちらを現行値とするか不明だった | 同じworktreeでS00 deep fixture追加後のfull pytestを再実行し、`439 passed / 1 failed`（EC-002 named Redのみ）を現行値として記録する。deep fixture追加前の`439 passed`はhistorical baselineとして区別する | applied; current rerun evidence recorded |
| P1 | EC-002 named testがdeep transitive fixtureを十分に通らず、旧resolverでもgreenになり得た | `tests/app/test_diff.py::test_diff_changed_seed_files_each_remain_hop_zero_at_default_depth`を`First -> Helper -> Transitive`へ深くし、旧resolverで`reachable_file_count 4 != 3`となるRedを確認した | applied; intentional Red |
| P1 | closure index `tc-001`〜`tc-006`の観測方法がfile-levelで、実装後にどのnodeidで閉じるか曖昧だった | config/bind/generateのexact nodeidをS00へ追加し、VCS regression nodeid、source diff command、tc-006 app nodeidをplanへ明記する | resolved; tc-006 app nodeid added and passed |
| P1 | Ruff pinned baseline/scoped gateは定義されたが、changed test filesのformat check非0を新規hunkと既存baselineへ分離する手順が不足していた | `ruff format --check`と`ruff format --diff`を全許可test pathへ固定し、`git diff --unified=0`とのhunk照合で追加ブロック由来をblocking、既存行由来をfile/line分類付きnon-blockingとする | resolved; worker verified added-hunk classification and minimally corrected config/bind |
| P2 | D-001、S00、S01など一部next actionがfresh reviewer #7 pass前提のまま残っていた | live gateを#1〜#7 fail、#8 requiredへ同期する | applied |

この修正後にSpecDock assurance/validate/doctor/diff checkを再実行し、追加test-only workerの結果を取り込んだうえで fresh `spec-reviewer #8`を取得する。#8がpassするまでS01 production source implementationへ進まない。

## 実装前 fresh spec review #8（2026-08-04）

S00 exact contract extensionとparent plan更新後の独立 `spec-reviewer #8` は `fail`。2つの意図的Red自体は適切と確認されたが、S00の6ファイルprovenance、explicit depth integration、parent scope、full-suite環境差分に追加修正が必要とされた。production source implementationは引き続き開始しない。

| 優先度 | 指摘 | 修正内容 | 状態 |
|---|---|---|---|
| P1 | planのS00許可pathが4系統なのに、既存S00のtraversal/parse変更をreportが記録し、provenanceが不一致 | S00のcanonical allowed test pathsを6系統（config/bind/generate/diff/traversal/parse）へ拡張し、protected-boundary、worker evidence、format gate、reportを6 filesへ統一 | applied |
| P1 | tc-006がdefault diff/generateだけで、明示`--depth 2`のapp/traversal integrationを実行できない | `tests/app/test_diff.py::test_diff_explicit_depth_two_reaches_transitive_dependency`を追加し、explicit depth=1/2のreachable/output差を1 nodeidで検証 | applied; 1 passed |
| P1 | D-003のIssue-local parent scope exceptionだけではfresh actorが親Epic closure scopeを判断できない | parent `epic-00002/plan.md`へM1計画外corrective issue exceptionを追加し、M1 6 Issue/E-RQを変更せず、Issue-local docsをclosure ownerと明記。D-003をsuperseded、D-006へ置換 | applied; parent validate/doctor pass |
| P2 | fresh reviewer環境ではfull pytestが`438 passed / 7 failed`となり、coordinatorの`443 passed / 2 intended Red`と異なった | 両結果をreportへenvironment-specific evidenceとして併記。focused all `226 passed / 2 intended Red`を実装前TDD evidenceとし、full-suite final gateは未完了・再現環境の確定待ちとする | applied; final quality remains blocked |

修正後にSpecDock assurance/validate/doctor/diff check、focused/all current tests、full-suite evidenceの再確認を行い、fresh `spec-reviewer #9`を取得する。#9がpassするまでS01 production source implementationへ進まない。

## 実装前 fresh spec review #9（2026-08-05）

S00 exact contract extension、parent plan更新、SpecDock refresh後の独立 `spec-reviewer #9` は `fail`。depth契約、ChatGPT advisoryのadvisory-only provenance、非変更境界、S00 six-path、tc-006 explicit depth=1/2、親Epic exception、coordinator/reviewer環境差分は整合していると確認された。一方、canonical designのdraft状態がSpecDock runtimeの`design-not-substantive`とblocked runbookを生むため、review pass後のcanonical promotionとrunbook readinessをS01の前提へ追加する必要がある。また、Decision LedgerのD-005重複IDが監査を曖昧にしていた。production source implementationは開始しない。

| 優先度 | 指摘 | 修正内容 | 状態 |
|---|---|---|---|
| P1 | `design.md`の`状態: "draft"`がruntimeの`design-not-substantive`を発生させ、current runbookをblockedにしている。plan S01がfresh #9 passだけを条件にしており、design promotion、active/runbook refresh、assurance/SpecDock readinessの遷移が未定義 | review pass前のdraft/blockedを保持し、fresh #10 pass後だけcanonical design statusを`approved`へ更新するS00-PROMOTE、tc-010、CASE-S00-PROMOTE-001をplanへ追加。main orchestratorはcanonical design statusだけを更新し、spec-managerが`active set`、assurance、workflow/guidance、validate/doctor/diff-checkを実行する | applied; fresh #10 required |
| P2 | Decision LedgerのD-005が同一内容で重複し、IDが一意でない | 重複行を削除し、D-005を一意化。D-007へpromotion/runtime readinessの判断を追加 | applied |

修正後にfresh `spec-reviewer #10`を実施し、pass後にのみS00-PROMOTEのcanonical design promotionとworkflow/runbook readiness検証へ進む。S00-PROMOTEがreadyでない限りS01 production source implementationへ進まない。

## 実装前 fresh spec review #10（2026-08-05）

修正後の独立 `spec-reviewer #10` は `fail`。depth契約、責務分離、ChatGPT advisoryのadvisory-only provenance、S00-PROMOTEの方向性、保護境界は確認された。一方、fresh reviewの合格をreportのゲートへ反映する順序と、promotion後のactive scope証跡が不足していたため、canonical docsのruntime readinessを確認する前に次の補正を行う。production source implementationは開始しない。

| 優先度 | 指摘 | 修正内容 | 状態 |
|---|---|---|---|
| P1 | S00-PROMOTEがrequirement/design/planだけをfresh review対象とし、`report.md`のSpec Authoring Gate、Reviewer Gate Status、Final Spec Review Gate、current gate、target/source evidenceを更新する操作を含んでいない。現行reportは#1〜#9 fail / #10 requiredのままで、workflowのreport evidence gateと一致しない | S00-PROMOTE、tc-010、CASE-S00-PROMOTE-001の対象へreport gate updateを追加し、fresh #11 pass後にmain orchestratorがreportを先に更新し、その後design promotionとSpecDock projection検証を行う順序をcanonical化 | applied; fresh #11 required |
| P2 | `active set`後のpost-promotion `active show`が明示されず、promotion後のactive issue scopeをreportと突合できない | S00-PROMOTEの正規コマンド列と期待証跡へ`active show`を追加し、`iss-00044`のactive scopeをreportへ記録する | applied; fresh #11 required |

修正後にfresh `spec-reviewer #11`を実施する。#11がpassするまではreportのpass昇格、canonical designの`approved`変更、workflow/runbook readinessのpromotion、S01 production source implementationを行わない。#11 pass後は、まずreport gateを更新し、次にdesignをapprovedへ昇格し、最後にspec-managerのcommand-first検証を実行する。

### #10修正後のSpecDock preflight（EXEC-S00-PROMOTE-PREFLIGHT-011）

fresh #11前の状態を、spec-managerがcommand-firstで再確認した。design promotionは行っていない。

```text
active show                              -> active issue=iss-00044
assurance classify --stage requirement   -> ok; status=valid; authorized_profile=standard; complexity_tier=normal; source binding valid
assurance verify                         -> ok
workflow status --format json            -> state=blocked; reason_code=design-not-substantive; may_execute_approved_plan=false
guidance issue-execution                 -> state=blocked; next_action=issue-planning-required; projection written=true
validate                                 -> spec-dock: ok (validate) nodes=41
doctor                                   -> spec-dock: ok (doctor) findings=0
git diff --check                         -> pass
```

`assurance classify`は最新planを反映し、`.assurance.json`を正規コマンドで再生成した。doctorの`github_target_unavailable` / `actions_read`はseverity=`info`のcapability probe情報であり、failureではない。`.serena/project.yml`、SpecDock managed update bundle、protected skill、source/tests/READMEの既存差分は保持し、今回のpreflightでは手編集・commit/push/PR/merge/finishを行っていない。review前のdraft/blocked状態は期待値として保持している。

### S00 config app integration後のSpecDock preflight（EXEC-S00-TEST-CONTRACT-PREFLIGHT-012）

config app integration testの追加後、spec-managerが同じworktreeでcommand-first検証を再実行した。design promotionはまだ行っていない。

```text
active show                              -> active issue=iss-00044-diff-default-depth
assurance classify --stage requirement   -> success; status=valid; authorized_profile=standard; complexity_tier=normal
assurance verify                         -> assurance verify: ok
workflow status --format json            -> state=blocked; reason_code=design-not-substantive; may_execute_approved_plan=false
guidance issue-execution                 -> may_execute_approved_plan=false
validate                                 -> spec-dock: ok (validate) nodes=41
doctor                                   -> spec-dock: ok (doctor) findings=0
git diff --check                         -> pass
```

`.assurance.json`は`assurance classify`で再生成され、SHA-256は`8a00839e9f033bdab244e9fbc3292a20aea140a0af710ec7b0189b19fd79454e`である。canonical designは`状態: "draft"`、runtimeは`design-not-substantive` blockedのまま保持した。doctorのGitHub `actions_read` / `target_unavailable`はseverity=`info`のnon-blocking capability情報である。`.serena/project.yml`はコマンド前後でSHA-256不変（`a75eb68d496f42d39867bdb01e28836c5902a902fa22220701394f0f49876851`）で、protected skill（このworktreeにはpath自体が存在しない）とmanaged bundleは変更していない。

## 実装前 fresh spec review #11（2026-08-05）

fresh `spec-reviewer #11` は `fail`。#10のreport-first gate updateとpost-promotion `active show`は、S00-PROMOTE、tc-010、CASE-S00-PROMOTE-001へ反映され、promotion前のdraft/blocked runtimeとも整合していると確認された。追加で、full-suite環境差異のgate scope、ChatGPT保存receipt、top-level config `depth=2`のapp-level closureが不足していた。production source implementationは開始しない。

| 優先度 | 指摘 | 修正内容 | 状態 |
|---|---|---|---|
| P1 | EAL-005がfull-suite環境差異を`blocking=yes`と記録する一方、S00-PROMOTE/S01はfocused contractだけで進める計画で、promotionのblocking scopeが曖昧 | EAL-005のblocking scopeを`S00-PROMOTE/S01ではnon-blocking、S99 final qualityではblocking`へ明示し、orchestrator/qa-reviewerをowner、S99のgreen full-suiteまたはsupported verification pathを必須化 | applied; fresh #12 required |
| P1 | ChatGPT artifact receiptにoutput form、preservation status、capture boundary、`import_kind`、source/destination identity、byte countが不足 | artifactと同一hash/byte countのexternal answer basename、destination repo-relative path、`import_kind=chatgpt-output`、`storage_identity=blank`、`committed=true`、warningなし、`diff -q` passをEAL-001とChatGPT-First observationへ追加。絶対host pathと本文は記録しない | applied; fresh #12 required |
| P2 | designが要求するtop-level config `depth=2`のapplication pathにexact app nodeidがなく、resolver-level testだけではapp wiringを検出できない | `tests/app/test_diff.py::test_diff_config_depth_two_reaches_transitive_dependency`をS00 test-only preparationとして追加する計画をdesign、plan tc-006、CASE-S02-002へ固定。旧resolverのRedを許容し、実装後greenへ閉じる | applied; dev-coder S00 bounded task pending |

修正後にS00のtest-only app integrationを実行し、SpecDock assurance/validate/doctor/diff-checkを再確認したうえでfresh `spec-reviewer #12`を取得する。#12がpassするまでreport gateのpass昇格、canonical designの`approved`変更、S00-PROMOTE、S01 production source implementationは行わない。

## 実装前 fresh spec review #12（2026-08-05）

fresh `spec-reviewer #12` は `fail`。CLI契約、resolver責務、traversal/VCS/DTO非変更境界、S00 test evidence、ChatGPT advisoryのadvisory-only採用、EAL-005のS00/S01非blocking・S99 blocking分類、config app integration、保護境界、未昇格のdraft/blocked runtimeは整合していると確認された。追加で、Standard profileに必要な専門家証跡ゲートとdelegated worker decision-noteがreportへ明示されていなかった。production source implementationは開始しない。

| 優先度 | 指摘 | 修正内容 | 状態 |
|---|---|---|---|
| P1 | `report.md`に`Grade Specialist Evidence Gate`がなく、`authorized_profile=standard`のspecialist use/skip/manual fallbackとexecution readinessの接続を確認できない | Standard rowを追加し、`system-architect` / `implementation-planner`のskip reason、ChatGPT-Use advisory使用、manual canonical integration、EAL/artifact/local verification、#12 fail/#13 required、blocked readinessを記録 | applied; fresh #13 required |
| P2 | delegated worker outputに必要なLedger Noteまたはexact no-material decision statementがworker evidence rowsにない | S00、Bernoulli、Peirce、Pasteurのworker rowsへ`No material implementation decisions beyond the approved plan.`を記録し、orchestrator adoptionを明示 | applied; fresh #13 required |

修正後にfresh `spec-reviewer #13`を実施する。#13がpassするまでreport gateのpass昇格、canonical designの`approved`変更、workflow/runbook readinessのpromotion、S01 production source implementationは行わない。

### plan live-gate sync後のSpecDock authority再確認（EXEC-SPEC-REVIEW-013-PREFLIGHT-014）

fresh #13の指摘に対応してplanのlive prerequisiteを#13へ更新した後、spec-managerが再度command-firstで確認した。最初の要約には`authority-invalid`が含まれたが、同じcurrent checkoutで各コマンドを個別に再実行したraw outputではsource binding一致と`design-not-substantive`が確認されたため、後者をcurrent evidenceとして採用する。managed stateの手修復は行っていない。

```text
assurance verify --issue iss-00044 -> ok; mode=adaptive; has_contract=true; authorized_profile=standard; complexity_tier=normal; reason=ok
workflow status --format json     -> state=blocked; reason_code=design-not-substantive; may_execute_approved_plan=false; authority=authorized_profile=standard
guidance issue-execution          -> state=blocked; reason_code=design-not-substantive; may_execute_approved_plan=false
validate                          -> spec-dock: ok (validate) nodes=41
doctor                            -> spec-dock: ok (doctor) findings=0; github_target_unavailable/actions_read is severity=info
git diff --check                  -> pass
```

source bindingは、design=`beb5287f888f577ffd9585beaf178ef8153aa646eff530d9dd5be5a22b6827c5`、plan=`bf48fa568f18fa333de0f9c3cfe39973788732eb68e185f9dd799e7055dd1907`、requirement=`6f5629a908f4fafba772cff6d0cc13fac454e1bb7e646905473b0397c0c214d7`で実ファイルと一致した。`.assurance.json`は正規CLI生成で、SHA-256は`b27a43f8d632f672158e0cbc0dc77c2aa1a34a1ddfa02825fa6059c94c5dbcbb`。canonical designは`draft`のため、current blockerはauthorityではなくdesign substanceである。

## 実装前 fresh spec review #13 retry（2026-08-05）

fresh `spec-reviewer #13`の再レビューは`fail`。#12修正、ChatGPT-Use advisoryのadvisory-only provenance、S00 test evidence、report gateの構造は確認された。一方、公開CLIのdefault behavior changeに対するgrade rationaleと、reportのclosure mappingに補正が必要とされた。production source implementationは開始しない。

| 優先度 | 指摘 | 修正内容 | 状態 |
|---|---|---|---|
| P1 | PyClassUMLの公開CLI `diff`既定挙動を変更するため、standard profile templateの`strict` escalation guardに該当する。現行`.assurance.json`/reportは`authorized_profile=standard`のままで、`public_contract_change` / `runtime_behavior_change`のunknownも解消されていない | PyClassUML runtime behaviorの変更自体は否認しない。requirement §10.1とdesign §1.1へ、SpecDock自身の公開CLI/workflow/metadata/stateを変更しないprofile scope、既存PyClassUML入力面/schema/終了契約を維持するStandard適用例外、`.assurance.json`を手修正しない理由、Strict相当の補償ゲート、Strictへ引き上げる再分類条件を明記。現行`authorized_profile=standard`とdocsの判断をreport D-013/Grade Specialist Gateへ接続 | applied; fresh #14 required |
| P2 | Test Contract Closure / Closure Coverageが`tc-001〜tc-009`までで、必須の`tc-010/EXEC-S00-PROMOTE`を含んでいない | `tc-001〜tc-010`へ拡張し、`tc-010`をS00-PROMOTE、report-first gate update、approved design、active/runbook、assurance/validate/doctor/diff-checkへ明示的に接続 | applied; fresh #14 required |

この修正でStandard authorityを形式的にStrictへ上書きしていない。P1のscope exceptionが現行SpecDock profile semanticsに適合しないとfresh reviewerが判断する場合、PyClassUML product contractをStrict triggerとして正式に扱うためのユーザー判断またはrisk-fact対応の正規SpecDock routeが必要であり、実装へ進まない。

## 実装前 fresh spec review #14（2026-08-05）

fresh `spec-reviewer #14` は `fail`。ChatGPT-Use artifactの保存・local source/tests検証・canonical rewrite、#13 P1の事実認定、S00 evidence、実装停止境界は受理された。一方、現行profile semanticsではPyClassUMLの公開CLI挙動変更をStandard例外として扱えず、`tc-010 / EXEC-S00-PROMOTE`も個別closure行が必要と判定された。production source/README実装とS00-PROMOTEは継続して停止する。

| 優先度 | 指摘 | 修正・判断 | 状態 |
|---|---|---|---|
| P1 | `spec-dock/templates/issue-profiles/standard/design.md` §1.3の「公開CLI挙動を変更する」はStrict triggerであり、`workflow_spec_authoring.md`は`authorized_profile`をmanual escalationで上書きできない。Issue-localのStandard scope exception、risk-fact入力CLI欠如、補償ゲートだけではStandard authorityを正当化できない | Standard結論を不受理し、D-014をopenで記録。managed `.assurance.json`は手修正しない。正式Strict分類またはcanonical policy-supported exceptionが確定するまで、promotion/実装を停止する | blocking; user direction required |
| P2 | reportのTest Contract Closure / Closure Coverageは`tc-001〜tc-010`の範囲表記で、`tc-010 / EXEC-S00-PROMOTE`の個別状態・証跡・blocked条件が不足 | reportに個別`tc-010 / EXEC-S00-PROMOTE`行を追加し、report-first gate update、approved design、active/runbook、assurance、validate/doctor/diff-checkを列挙する | applied; fresh #15 required after P1 resolution |

reviewer verdict: `review_status=fail`。#13で追加したscope exception・補償ゲートは事実認定として受理されたが、Standard authorityの根拠としては不受理である。

### #14判定後のSpecDock preflight（EXEC-SPEC-REVIEW-014-PREFLIGHT-015、2026-08-05）

#14のfailと次の#15 gateをcanonical report/planへ反映した後、SpecDock専任`spec-manager`が正規コマンドでpreflightを再実行した。全コマンドはexit 0だが、実装admissionは発行していない。

```text
active show                                  -> iss-00044
assurance classify --stage requirement       -> valid; authorized_profile=standard; complexity_tier=normal; lite_candidate=false
assurance verify --issue iss-00044           -> ok
workflow status --format json                -> blocked; reason_code=design-not-substantive
guidance issue-execution                     -> blocked; next_action=issue-planning-required; may_execute_approved_plan=false
validate                                     -> ok; nodes=41
doctor                                       -> ok; findings=0
git diff --check                              -> pass
```

`doctor`のGitHub capability `target_unavailable`はinfoであり、failureではない。正規`assurance classify`で再生成された`.assurance.json`のSHA-256は`53ebdb22251d52b0d51de4e919b279309095519b56f5053acff433324de3fdac`、source bindingはdesign=`5890c7ddb9eb486bc35b86767932a9e0cb2a70c09f8d5b8dd59a99541387f21a`、plan=`722210bf5b3f43ee097f72fb4a7658280e398e9249c173994beee98377f721a6`、requirement=`a58068b4db04dab694bcce17aebc25872686375b0cddb0aed20158b78f624c4b`である。

protected `.agents/skills/pyclassuml-repo-map`は変更なし、`.serena/project.yml`は既存`M`を保持しSHA-256=`a75eb68d496f42d39867bdb01e28836c5902a902fa22220701394f0f49876851`で不変、`src`/`README.md`は変更なし、testsは既存6ファイル差分を保持した。active set、design promotion、managed state手修復、commit/push/PR/merge/finishは行っていない。`authorized_profile=standard`のまま公開CLI挙動変更のP1は未解消であり、formal Strict/policy routeまたはユーザー判断なしに#15 review、promotion、実装へ進まない。

## 実装サマリー (任意)
- 実装はまだ開始していない。ChatGPT-Useの完了済み設計レビューをlocal source/testsで再検証し、`requirement.md`、`design.md`、`plan.md`へ採用した契約を反映した。
- 現時点ではcanonical docsはdraft/provisionalであり、fresh `spec-reviewer` #1/#2/#3/#4/#5/#6/#7/#8/#9/#10/#11/#12/#13/#14はいずれもfail。#14のP1を解消する正式Strict/policy routeが確定した後に#15を実施し、pass後にS00-PROMOTE、production source変更、focused/full test、README更新、code/QA reviewへ進む。

### ChatGPT-First試行の観測

- 正式 `spec-dock-chatgpt planning create` は、detached HEADとGitHub exact HEAD不一致および旧Issue front matter不一致でCandidateを生成できなかった。
- ユーザー最新指示に従い、`chatgpt-use` skillの完了済み `pyclassuml-depth-review-reduced`（Pro、model verified、15m06s、22.46k input / 4.08k output）を仕様作成のadvisory sourceとして使用した。
- 3文書を直接返す別セッションはUI送信失敗となったため、未完了応答は棄却し、完全な設計レビューからlocal検証済みclaimsだけをcanonical docsへ統合した。
- ChatGPTレビューartifactは `artifacts/20260804t093411z-chatgpt-output-chatgpt-depth-design-review.md` にimport済みである。preservation receiptは `output_form=complete_standalone_markdown`、`preservation_status=imported_byte_exact`、`capture_boundary=ChatGPT-Use answer file -> imported Artifact`、`import_kind=chatgpt-output`、`storage_identity=blank`、external source basename=`pyclassuml-depth-review-reduced-answer.md`、destination repo-relative path、`byte_count=24635`、SHA-256 `a1fd48017f60c04f511ce831b6ae0761f32d04967c4ea33603adccdd698f59cc`、`committed=true`、`warning=none`、`diff -q` passを含む。絶対host pathと本文はreceiptへ記録していない。artifact保存（evidence-only）とcanonical adoptionは分離している。

### S00/S99 preproduction verification（EXEC-S00-TEST-CONTRACT / EXEC-S99-TOOLING-BASELINE）

S00 deep fixtureとexact contract extension後、production source/README/SpecDock/skillを変更せず、次をcurrent worktreeで再実行した。

```text
uv run pytest tests/app/test_diff.py::test_diff_changed_seed_files_each_remain_hop_zero_at_default_depth → 1 failed (intentional Red: reachable_file_count 4 != 3)
uv run pytest tests/analyze/test_traversal.py::test_multiple_import_candidates_share_same_hop \
  tests/parse/test_module_parse_and_index.py::test_parse_target_set_keeps_deeper_syntax_diagnostic_with_depth_one → 2 passed
uv run pytest tests/app/test_diff.py → 58 passed, 1 failed (same intentional Red)
uv run pytest tests/analyze/test_traversal.py → 15 passed
uv run pytest tests/parse/test_module_parse_and_index.py → 44 passed
uv run pytest → 443 passed, 2 failed (intentional Red: EC-002 app + tc-001 resolver; 16.46s)
uvx --from ruff==0.9.3 ruff --version → ruff 0.9.3
uvx --from ruff==0.9.3 ruff check tests/app/test_diff.py tests/analyze/test_traversal.py tests/parse/test_module_parse_and_index.py → pass
uvx --from ruff==0.9.3 ruff check tests/config/test_context_resolve.py tests/cli/test_bind.py tests/app/test_generate.py → pass
uvx --from ruff==0.9.3 ruff format --check tests/config/test_context_resolve.py tests/cli/test_bind.py tests/app/test_generate.py tests/app/test_diff.py tests/analyze/test_traversal.py tests/parse/test_module_parse_and_index.py → 6 files would be reformatted (existing lines only; added config/bind blocks minimally corrected, generate/traversal/parse blocks clean, existing app_diff S00 block retained)
git diff --check → pass
```

上記はconfig app integration追加前のS00 baselineである。追加後のcurrent app evidenceは、`uv run pytest -q tests/app/test_diff.py::test_diff_config_depth_two_reaches_transitive_dependency`が`1 passed`、`uv run pytest -q tests/app/test_diff.py`が`60 passed, 1 failed`（既知のdefault-depth Red、期待3/実測4）、`uvx --from ruff==0.9.3 ruff check tests/app/test_diff.py`がpass、`git diff --check`がpassである。追加test hunkはformat対象外で、既存baseline driftのため全体format checkは非0のまま保持した。full pytestはS99で再実行する。

S00 deep fixture追加前のhistorical baselineはfull pytest `439 passed in 16.67s`だった。exact contract extension後の現行Redは新規EC-002 app testとtc-001 resolver testだけで、`443 passed / 2 failed`（`16.46s`）となった。追加nodeidは`F....`、4 passed/1 intended Red、config suiteは47 passed/1 failed、bind 11 passed、generate 18 passed、VCS regression 6 passedだった。全体Ruff診断は次の既存baselineを再現した。`ruff check src tests`は`src/pyclassuml/render/document.py`の未変更F821 4件でexit 1、`ruff format --check src tests`は32 files would be reformattedでexit 1。許可test pathsのscoped lintはpassし、scoped formatの6 files非0は既存行由来で、config/bind追加blockは最小修正済み、generate/traversal/parse追加blockはdriftなし、既存app_diff S00 blockは変更せず保持した。`ruff==0.9.3`のpinned command、baseline、別maintenance owner、Issue-scoped gateはplan §9とD-005へ昇格した。

### S00 exact contract extension / SpecDock refresh（2026-08-04）

S00 exact contract extension worker `Bernoulli` は、production source、README、SpecDock managed state、`.agents/skills`、`.serena/project.yml`を変更せず、次のtest-only変更を完了した。

```text
tests/config/test_context_resolve.py
  test_diff_default_depth_is_one_without_cli_or_config          -> Red (None != 1)
  test_generate_default_depth_is_none_without_cli_or_config    -> pass
  test_cli_and_config_depth_precedence_preserves_zero           -> pass
tests/cli/test_bind.py
  test_bind_depth_preserves_none_and_explicit_zero              -> pass
tests/app/test_generate.py
  test_generate_default_depth_remains_unlimited                  -> pass
```

追加nodeidは `4 passed / 1 intended Red`、config suiteは `47 passed / 1 failed`、bind suiteは `11 passed`、generate suiteは `18 passed`。既存S00のdeep EC-002 testを含むcurrent full suiteは `443 passed / 2 failed`で、2 failureは`test_diff_changed_seed_files_each_remain_hop_zero_at_default_depth`と`test_diff_default_depth_is_one_without_cli_or_config`だけである。scoped Ruff checkはpass、`git diff --check`はpass。Ruff format checkは6 test filesがreformat対象だが、追加config/bind blockは最小修正し、generate/traversal/parse追加blockはdriftなし、既存app_diff S00 blockのdriftは変更せずbaselineとして保持した。

同じworktreeでSpecDock command-first refreshを再実行した。

```text
active show                              -> init-00001 / epic-00002 / iss-00044
assurance classify                       -> ok; standard; normal; .assurance.json written
assurance verify                         -> ok
validate                                 -> spec-dock: ok (validate) nodes=41
doctor                                   -> spec-dock: ok (doctor) findings=0
doctor GitHub capability                 -> github_target_unavailable/actions_read, info, non-blocking
git diff --check                         -> pass
```

classifyが生成した`.assurance.json`以外のmanaged stateは手編集していない。`.serena/project.yml`、SpecDock updater bundle、protected skillの既存状態を保持し、commit/push/PR/merge/finishは実施していない。

## 実装記録（セッションログ） (必須)

### セッションログ（2026-08-04 09:15 - 11:45）

#### 対象
- Step: planning preflight / canonical docs authoring
- AC/EC: AC-001〜AC-007、EC-001〜EC-008（実装前）
- 計画上の出典（Planned source）:
  - `plan.md` sections 1〜5、`tc-001`〜`tc-009`
  - closure ids: `tc-001`〜`tc-009`（未完了）

#### 実施内容
- active state、SpecDock update後のGit差分、`.serena/project.yml`を再確認し、既存変更を保持した。
- formal `planning create`の拒否を記録した後、完了済みChatGPT-Use advisoryをevidence-onlyで採用し、current schemaのrequirement/design/planを作成した。
- `assurance classify --stage requirement` は `status=valid`、`authorized_profile=standard` を返した。実装・reviewer gateは未開始である。

#### 実行コマンド / 結果（EXEC-PLANNING-001）
```bash
./spec-dock/scripts/spec-dock assurance classify --stage requirement --issue iss-00044 --format json

status=valid; mode=adaptive; authorized_profile=standard; .assurance.json written

./spec-dock/scripts/spec-dock assurance verify --issue iss-00044

assurance verify: ok; mode=adaptive; has_contract=true; authorized_profile=standard; complexity_tier=normal

./spec-dock/scripts/spec-dock validate

spec-dock: ok (validate) nodes=41

./spec-dock/scripts/spec-dock doctor

spec-dock: ok (doctor) findings=0
github capability diagnostics=1 (severity=info; target_unavailable; non-blocking)

uv run pytest tests/config/test_context_resolve.py tests/analyze/test_traversal.py tests/cli/test_bind.py tests/app/test_diff.py tests/app/test_generate.py

144 passed in 4.70s

git diff --check

pass (no output)
```

#### テスト駆動開発証跡（TDD / Red / Green / Refactor Evidence）
| ステップ（step） | フェーズ（phase） | 計画した証跡要件 | 観測した証跡 | 証跡手段（command / inspection / manual record） | 結果（result） | メモ（notes） |
|---|---|---|---|---|---|---|
| planning | 代替証跡（Alternative） | inspect-only | ChatGPT advisoryをlocal source/testsで再検証し、canonical docsへ統合 | artifact import、source inspection、assurance classify | pass | reviewer pass前のdraft統合のみ |
| S00 | 赤フェーズ準備（Test-only contract preparation） | named-test-required | EC-002/004/005のnamed testとdefault/raw-boundaryのexact testsをproduction source変更なしで追加し、深いEC-002 fixtureで旧resolverのRedを確認。tc-001〜tc-004/tc-006 exact testsは4 passed/1 intended Red | `EXEC-S00-TEST-CONTRACT`、test-only worker output | completed | production source implementationではない。full Ruff baselineはD-005で別扱い |
| S00-PROMOTE | 実装前promotion/readiness gate | workflow-required | fresh spec-reviewer #15 pass後にreport gateを更新し、canonical designをapprovedへ更新し、active/runbook/assurance/SpecDock readinessを確認する | plan S00-PROMOTE / `EXEC-S00-PROMOTE` | blocked / not_started | fresh spec-reviewer #15 pass後にreport先行のspec-manager command-first promotionを実施 |
| S01 | 赤フェーズ（Red） | red-required | `tests/config/test_context_resolve.py`のexact default testをS00 exact contract extensionで追加済み。現状はproduction source変更前 | plan.mdの実装前gate | blocked / not_started | fresh spec-reviewer #15 passとS00-PROMOTE完了待ち |
| S01 | 緑フェーズ（Green） | red-required | 未実施 | plan.md S01 command | not_started | source変更未開始 |

#### 発見されたテスト / リスク（Discovered Tests）
| ステップ（step） | 発見されたテスト / リスク（test / risk） | 起票元（source） | 実施した対応 | クロージャID / 新規ID（closure id / new id） | 計画修正要否（plan amendment required） | 証跡（evidence） |
|---|---|---|---|---|---|---|
| planning | formal Candidate unavailable / direct spec-authoring incomplete | workflow / ChatGPT-Use | complete advisoryのみ採用、未完了出力はrejected | EAL-002, EAL-003 | no | report EAL / artifact receipt |
| planning | fresh spec-reviewer 初回fail: EC、bind/effective、VCS path、provenance、traceability、owner | fresh spec-reviewer | 実装を停止し、requirement/plan/reportを修正 | SPEC-REVIEW-001 | yes | review output and amended canonical docs |
| planning | fresh spec-reviewer #2 fail: EC closure全件、INV-005/006、step-local contract、report台帳 | fresh spec-reviewer | 実装を停止し、requirement/plan/reportを追加修正 | SPEC-REVIEW-002 | yes | review output and amended canonical docs |
| planning | fresh spec-reviewer #3 fail: tc-009のnamed test/source/status execution path、approved-no-op矛盾 | fresh spec-reviewer | 実装を停止し、plan/reportを追加修正 | SPEC-REVIEW-003 | yes | review output and amended canonical docs |
| planning | fresh spec-reviewer #4 fail: current gate、EC-005 depth=1、INV-006 named function、EC-004/008 wiring、protected baseline | fresh spec-reviewer | 実装を停止し、plan/reportを追加修正 | SPEC-REVIEW-004 | yes | review output and amended canonical docs |
| planning | fresh spec-reviewer #5 fail: current gate、named test未生成、EC-008 negative inspection、親Epic scope | fresh spec-reviewer | 実装を停止し、plan/reportを追加修正。S00 test-only preparationを追加 | SPEC-REVIEW-005 | yes | review output and amended canonical docs |
| planning | fresh spec-reviewer #6 fail: Ruff baseline/reproducibility、full pytest evidence、EC-002 named multi-seed test | fresh spec-reviewer | 実装を停止し、plan/reportを追加修正。pinned Ruff/baseline contract、439-pass rerun、S00 extensionを追加 | SPEC-REVIEW-006 | yes | review output and amended canonical docs |
| planning | fresh spec-reviewer #7 fail: current full-suite/report mismatch、EC-002 sensitivity、closure exactness、format disposition、stale next actions | fresh spec-reviewer | 実装を停止し、full pytest current Red、deep fixture、exact nodeid、format hunk分類、live gateを追加 | SPEC-REVIEW-007 | yes | review output and amended canonical docs |
| S01 | resolver default tests | plan | deferred until fresh spec review | tc-001〜tc-003 | no | `tests/config/test_context_resolve.py` |

#### ステップ契約の完了証跡（Step Contract Closure）
| ステップ（step） | クロージャID（closure ids） | 計画上の close 条件（close condition from plan） | 観測した証跡 | 結果（result） | メモ（notes） |
|---|---|---|---|---|---|
| planning | none | canonical docs are valid, but review gate must pass before implementation admission | assurance classify/verify valid; fresh spec-reviewer #1/#2/#3/#4/#5/#6/#7/#8/#9/#10/#11/#12/#13/#14 fail | blocked | review gate failure is an implementation blocker; no production source change |
| S00 | `EXEC-S00-TEST-CONTRACT` | named EC-002/004/005 and default/raw-boundary tests exist and focused command is executable; production source unchanged | pre-deep named tests 3 passed; deep EC-002 is intentional Red; exact contract extension completed | completed | format check baseline drift remains separately recorded |
| S00-PROMOTE | tc-010 / EXEC-S00-PROMOTE | report gate、canonical design status、active/runbook、assurance/SpecDock readiness required | 未実施 | not_started | fresh spec-reviewer #15 pass待ち |
| S01 | tc-001〜tc-003 | source change and focused tests required | 未実施 | not_started | fresh spec-reviewer #15 passとS00-PROMOTE完了待ち |

#### テスト契約の完了証跡（Test Contract Closure）
| クロージャID / テストID（closure id / test id） | ステップ（step） | 必須 | 証跡レベル（evidence level） | 実装前証跡 | 検証コマンドまたは代替 path | 観測結果 | メモ（notes） |
|---|---|---|---|---|---|---|---|
| S00 / `EXEC-S00-TEST-CONTRACT` | S00 | yes | named-test-required | EC-002/004/005 plus tc-001〜tc-004/tc-006 named paths exist; production source unchanged | focused nodeids and selected suites | completed | EC-002 is intentionally Red until resolver implementation; S01 still blocked |
| tc-001〜tc-010 | S01/S02/S90/S99/S00-PROMOTE | yes | red-required / covered-existing / inspect-only / workflow-required / manual-required | plan固定済み。`tc-010`はS00-PROMOTEのreport gate、design promotion、active/runbook、assurance/SpecDock readinessを閉じる | 各step command / report | not_started | production implementation未開始 |
| tc-010 / `EXEC-S00-PROMOTE` | S00-PROMOTE | yes | workflow-required | fresh spec-reviewer pass後にreport gateを先に更新し、canonical designをapprovedへ変更し、active scope/runbook/assurance/SpecDock projectionを同期する | report-first gate diff、design status、active show、workflow status/guidance、assurance verify、validate、doctor、git diff --check | not_started | #14 fail、P1のStrict/policy decision未解消、promotion前のためblocked |

- `closure id / test id` は Spec-Locked Closure Index の `id` を指す。別 alias を使う場合は `Closure Delta` で対応を記録する。

#### クロージャ網羅（Closure Coverage）
| クロージャID（closure id） | ステップ（step） | 検証証跡 | 観測結果 | メモ（notes） |
|---|---|---|---|---|
| tc-001〜tc-010 / EC-001〜EC-008 / INV-001〜INV-006 / DOC-001〜DOC-007 | S00-PROMOTE/S01/S02/S90/S99 | plan closure index、workflow gate、edge/invariant mapping | not_started | implementation未開始。`tc-010` / `EXEC-S00-PROMOTE`をS00-PROMOTEのreport/projection/readiness closureとして追加 |
| tc-010 / `EXEC-S00-PROMOTE` | S00-PROMOTE | report-first gate update、approved design、active/runbook、assurance/SpecDock readinessの個別closure | not_started | #14 failとP1 blockingのため未実施。fresh #15はP1解消後に取得 |

#### クロージャ差分（Closure Delta）
| 変更種別（change） | クロージャID（closure id） | テストID alias（test id alias） | 解決先クロージャID（resolved closure id） | 理由 | 計画修正要否（plan amendment required） | 再レビュー要否（re-review required） |
|---|---|---|---|---|---|---|
| added | tc-003, tc-005, tc-007, tc-008, tc-009 | EC/INV/DOC mapping; named evidence | tc-003, tc-005, tc-007, tc-008, tc-009 | fresh reviewer #1/#2 findingsに対応する検証traceability補強 | yes | yes |
| added | tc-009 / EXEC-S99-INV-005-006 | named pytest、AST inspection、前後status、blocking状態 | tc-009 / EXEC-S99-INV-005-006 | fresh reviewer #3 findingsに対応する実行経路とreport状態補強 | yes | yes |
| added | tc-007 / tc-008 / tc-009 / EXEC-S02-EDGE-001 / EXEC-S90-EC-008 / EXEC-PROTECTED-BASELINE | EC-005/EC-004/EC-008/protected baseline wiring | named edge/inspection/status cards | fresh reviewer #4 findingsに対応するowner wiringとboundary audit | yes | yes |
| added | S00 / EXEC-S00-TEST-CONTRACT / SPEC-REVIEW-005 | EC-004/005 named testの実在性、EC-008 negative inspection、親Epic scope exception | test-only preparation、negative command、D-003 | fresh reviewer #5 findingsに対応する実行可能性とscope audit | yes | yes |
| added | S00 extension / SPEC-REVIEW-006 | EC-002 named multi-seed test、Ruff baseline/pinned tool、full pytest evidence | test-only app test、plan §9 baseline contract、439-pass local rerun | fresh reviewer #6 findingsに対応するquality/evidence/edge closure | yes | yes |
| added | S00 exact contract extension / SPEC-REVIEW-007 | tc-001〜tc-006の実在nodeid、current Red、format hunk classification | config/bind/generate test paths、plan closure index、full pytest rerun | fresh reviewer #7 findingsに対応するexecution traceabilityとquality disposition | yes | yes |
| added | S00 six-path provenance / tc-006 / SPEC-REVIEW-008 | S00 allowed test paths、explicit depth=1/2 integration、parent scope、full-suite environment variance | plan S00 six-path contract、parent Epic exception、environment-specific evidence | fresh reviewer #8 findingsに対応するprovenance、integration、scope、quality evidence | yes | yes |
| added | S00-PROMOTE / D-007 / SPEC-REVIEW-009 | canonical design promotion、runtime readiness、D-005 unique ledger ID | plan S00-PROMOTE/tc-010、D-007、重複D-005削除 | fresh reviewer #9 findingsに対応するdesign statusとrunbook transition | yes | yes |
| added | S00-PROMOTE / tc-010 / EXEC-S00-PROMOTE / SPEC-REVIEW-010 | report gate update order、report/projection一致、post-promotion active show | plan S00-PROMOTE、CASE-S00-PROMOTE-001、D-008 | fresh reviewer #10 findingsに対応するreport evidence gateとactive scope証跡 | yes | yes |
| added | S00 test-only app integration / SPEC-REVIEW-011 | top-level config `depth=2`のreal app wiring、EAL-005 gate scope、ChatGPT receipt completeness | `tests/app/test_diff.py::test_diff_config_depth_two_reaches_transitive_dependency`、plan/design更新、EAL-001/EAL-005 | fresh reviewer #11 findingsに対応するapplication-level closureとevidence ledger補強 | yes | yes |
| added | report evidence / SPEC-REVIEW-012 | Standard Grade Specialist Evidence Gate、named specialist skip/manual fallback reason、delegated worker decision-note | report Grade Specialist Evidence Gate、S00/Bernoulli/Peirce/Pasteur worker rows、D-012 | fresh reviewer #12 findingsに対応するworkflow auditability補強 | yes | yes |
| added | requirement/design profile scope exception / `tc-010` / SPEC-REVIEW-013 | PyClassUML product runtime behaviorとSpecDock public workflow contractの境界、Strict-equivalent compensating gates、S00-PROMOTE closureの全件追跡 | requirement §10.1、design §1.1、report D-013、Test Contract Closure/Closure Coverage | fresh reviewer #13 P1/P2 findingsに対応するgrade rationaleとclosure completeness補強 | yes | yes |

#### ワークフロー委任同意の証跡（Workflow Delegation Consent）
`workflow_issue.md` is the policy source for workflow-scoped delegation consent. This report records observed consent, boundary, expiry, and denied / unavailable handling only.

| 同意元（consent source） | リポジトリ / worktree（repo/worktree） | 対象課題（active issue） | セッション（session） | 指名ロール（named roles） | 境界（boundary） | 期限 / 無効化条件（expires / invalidation condition） | 拒否 / 利用不可理由（denied / unavailable reason） | 次アクション（next action） |
|---|---|---|---|---|---|---|---|---|
| user instruction (source task `019fcba8-ca5e-71d2-a6a7-ddec18085eff`) | current PyClassUML worktree | iss-00044 | current session | spec-reviewer / code-reviewer / qa-reviewer / dev-coder / doc-writer as separately delegated | this worktree owns PyClassUML source / tests / README / SpecDock; source task owns only `.agents/skills/pyclassuml-repo-map`; share only Markdown or task messages; no merge or cross-task implementation request | issue complete / session end / scope change / user revocation | manual backup was explicitly approved in an earlier instruction, then latest instruction selected experimental ChatGPT-First/local-context authoring instead; no skill or user-level skill changes | preserve boundary; keep formal candidate/apply separate from local advisory evidence |

#### 実装委任ゲート（Implementation Delegation Gate）
`workflow_issue.md` is the policy source for delegation, reviewer gates, waiver, unavailable, denied, and host-conflict semantics. This report records observed evidence only.

| ステップ（step） | 判断（decision） | 必須理由（required reason） | 委任ロール（delegated role） | 委任範囲（delegated scope） | 正本（source of truth） | 許可変更（allowed changes） | 禁止変更（forbidden changes） | 必須検証（required verification） | 停止条件（stop conditions） | 必須出力（output required） | 観測結果（observed result） |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S00 | completed test-only preparation | fresh reviewer #5/#6/#7/#8のP1/P2: named test未生成、EC-002感度、closure exactness、tc-006 integrationを解消し、production implementationの前にplan commandを実行可能にする | dev-coder（完了） | EC-002/004/005 + tc-001〜tc-004/tc-006のnamed tests | plan S00 / requirement AC/EC | `tests/config/test_context_resolve.py`, `tests/cli/test_bind.py`, `tests/app/test_generate.py`, `tests/app/test_diff.py`, `tests/analyze/test_traversal.py`, `tests/parse/test_module_parse_and_index.py`のみ | production source、README、SpecDock、managed bundle、skill、Serenaの変更 | exact nodeids、focused 226 passed/2 intended Red、tc-006 1 passed、scoped ruff check、diff check | production source/docs/metadata変更、named test不足、path外変更 | changed test files、exact results、red/green evidence、risk note | completed; S00 evidence captured as `EXEC-S00-TEST-CONTRACT` |
| S00-PROMOTE | planned command-first promotion; blocked before promotion | fresh spec-reviewer #14 failとP1を解消し、report gateを更新したうえでapproved designとready runbookを得る実装前ゲート | spec-manager（未起動） + orchestrator | issue-local report/design status、active/runbook/assurance/SpecDock projection | plan S00-PROMOTE、fresh reviewer #15 pass後 | issue-local report/design front matterと正規SpecDock projectionsのみ | review pass前のreport/design status変更、active/runbook/metadata手修復、source/tests/README/managed bundle/skill/Serena変更 | exact report diff、command output、workflow/runbook JSON、post-promotion active show、assurance/validate/doctor/diff-check、protected status | fresh spec-reviewer未pass、report/projection不一致、workflow blocked、assurance/validate/doctor/diff-check failure | changed report/design status、command results、readiness evidence、risk | blocked / not_started |
| S01 | planned delegation; blocked before dispatch | fresh spec-reviewer #1〜#14 failを解消し、S00 exact contract extensionとpromotion gateを完了する実装前ゲート | dev-coder（未起動） | resolver.py + tests/config/test_context_resolve.py、requirement/design/plan/report | plan S01、fresh reviewer #15 pass + S00-PROMOTE完了後 | `src/pyclassuml/config/resolver.py`, `tests/config/test_context_resolve.py`のみ | bind/model/traversal/VCS/README変更、S00 extension未完、test不能、fresh spec-reviewer未pass、S00-PROMOTE未完 | focused resolver tests、changed files、risk、code-review request | fresh spec-reviewer #1〜#14 fail | worker summary / changed files / verification / risks / integration decision | blocked / not_started |

#### 委任 worker 証跡（Delegated Worker Evidence）
| ステップ（step） | 委任ロール（delegated role） | 委任 worker 要約（delegated worker summary） | 変更ファイル（changed files） | 実行 tests または docs-only 検証（tests run or docs-only verification） | レビュアー判定（reviewer verdict） | 未解決リスク（unresolved risks） | 親統合判断（parent integration decision） |
|---|---|---|---|---|---|---|---|
| S00 | dev-coder | named test 3件を追加し、EC-002 fixtureをdeep transitiveへ更新。production source/README/SpecDock/skill/Serena/managed bundleは変更なし。Ledger Note: `No material implementation decisions beyond the approved plan.` | `tests/app/test_diff.py`, `tests/analyze/test_traversal.py`, `tests/parse/test_module_parse_and_index.py` | pre-deep nodeids 3 passed; current EC-002 1 intended failure; app 58 passed/1 failed; ruff check pass; diff check pass; format check baseline failure | provisional / accepted for S00; fresh spec review #8/#9/#10/#11/#12/#13/#14 fail / #15 required | ruff format drift classification resolved; no broad reformat performed | adopted into S00 / EAL-004; S00-PROMOTE and S01 remain blocked |
| S00 exact contract extension | dev-coder `Bernoulli` | tc-001〜tc-004/tc-006 exact config/bind/generate testsを追加。production source/README/SpecDock/skill/Serena/managed bundleは変更なし。Ledger Note: `No material implementation decisions beyond the approved plan.` | `tests/config/test_context_resolve.py`, `tests/cli/test_bind.py`, `tests/app/test_generate.py` | 4 passed/1 intended Red; config 47 passed/1 failed; bind 11 passed; generate 18 passed; scoped ruff check pass; diff check pass | provisional / accepted for S00 extension; fresh spec review #8/#9/#10/#11/#12/#13/#14 fail / #15 required | format checkは6 files非0だが、追加hunk分類済み（config/bindは最小修正、generate/traversal/parseはdriftなし、既存app_diff blockは保持） | adopted into S00 / EAL-004; S00-PROMOTE and S01 remain blocked |
| S00 tc-006 integration | dev-coder `Peirce` | explicit depth=1/2 app integration testを追加。production source/README/SpecDock/skill/Serena/managed bundleは変更なし。Ledger Note: `No material implementation decisions beyond the approved plan.` | `tests/app/test_diff.py::test_diff_explicit_depth_two_reaches_transitive_dependency` | nodeid 1 passed; app suite 59 passed/1 intended Red; scoped Ruff pass; diff check pass | provisional / accepted for S00/S02 traceability; fresh spec review #9/#10/#11/#12/#13/#14 fail / #15 required | warning-only successを許容し、reachable count/outputを検証 | adopted into S00 test evidence / S02 tc-006; S00-PROMOTE and S01 remain blocked |
| S00 config integration | dev-coder `Pasteur` | top-level config `depth=2`のreal app integration testを追加。production source/README/SpecDock/skill/Serena/managed bundleは変更なし。Ledger Note: `No material implementation decisions beyond the approved plan.` | `tests/app/test_diff.py::test_diff_config_depth_two_reaches_transitive_dependency` | named 1 passed; app suite 60 passed/1 intended Red（既存のdefault depth Red、期待3/実測4）; scoped `ruff==0.9.3` check pass; `git diff --check` pass; format checkは既存baseline driftで非0 | provisional / accepted for S00 extension; fresh #13 retry fail / #14 fail / #15 required | `.pyclassuml.toml` top-level depth=2、A→B→C fixture、reachable count 3、Source/Helper/Transitive outputをreal `run_diff` pathで確認。旧resolverのdefault depth RedはS01実装でgreenへ閉じる | adopted into S00 / EAL-004; S00-PROMOTE and S01 remain blocked |
| S00-PROMOTE | spec-manager | 未起動（fresh spec-reviewer #14 failのためpromotion前） | なし（canonical design status更新前） | 未実施 | provisional / blocked | fresh #15 pass後にP1解消済みのcanonical status更新とcommand-first readiness確認 | needs follow-up |
| S01 | dev-coder | 未起動（fresh spec-reviewer #1〜#14 failのためproduction dispatch前） | なし | 未実施 | provisional / blocked | S00-PROMOTE完了とfresh spec-reviewer #15 pass後にdispatch | needs follow-up |

#### 親実装例外（Parent Implementation Exception）
| ステップ（step） | 委任不可 / 不可能理由（delegation unavailable/impossible reason） | ユーザー承認 / risk acceptance（user approval / risk acceptance） | 許可ファイル（allowed files） | 許可操作（allowed operation） | ロールバック計画（rollback plan） | 変更後検証（post-change verification） | レビューゲート（reviewer gate） | 利用不可 / 拒否 / host conflict / waiver 対応（unavailable / denied / host conflict / waiver handling） |
|---|---|---|---|---|---|---|---|---|
| S00-PROMOTE | 例外なし（spec-manager委任が利用可能で、まだpromotionを実施していない） | user instructionで委任境界を承認済み。risk acceptance不要 | report/design front matterと正規SpecDock projectionsのみ | fresh #15 pass後のreport先行command-first promotion | `assurance verify`/validate/doctor/diff check、post-promotion active show、workflow/runbook readinessを確認する | spec-reviewer #1〜#14 failed | blocked; fresh #15 pass後にreport gateを更新し、canonical design statusをapprovedへ更新し、spec-managerのactive/runbook/assurance/SpecDock検証を通す |
| S01 | 例外なし（dev-coder委任が利用可能で、まだproduction dispatchしていない） | user instructionで委任境界を承認済み。risk acceptance不要 | なし（source変更未実施） | no-op inspectionのみ | `assurance verify`/validate/doctor/diff checkはpass、実装は未開始 | spec-reviewer #1〜#14 failed | blocked; S00-PROMOTE、fresh #15 pass、approved design/runbook readiness後に通常委任へ進む |

#### レビューゲート状態（Reviewer Gate Status）
| ステップ（step） | ゲート名（gate name） | レビュアーロール（reviewer role） | 鮮度（freshness） | 状態（state） | リスク受容（risk acceptance） | 昇格 / 完了判断（promotion / completion decision） | メモ（notes） |
|---|---|---|---|---|---|---|---|
| S01 | pre-implementation spec review #1 | spec-reviewer | fresh | failed | no | blocked / follow-up required | EC/INV/step contract/report evidence |
| S01 | pre-implementation spec review #2 | spec-reviewer | fresh | failed | no | blocked / follow-up required | closure全件、INV-005/006、step-local contract、report台帳 |
| S01 | pre-implementation spec review #3 | spec-reviewer | fresh | failed | no | blocked / follow-up required | tc-009 execution path、approved-no-op state contradiction |
| S01 | pre-implementation spec review #4 | spec-reviewer | fresh | failed | no | blocked / follow-up required | current gate state、EC-005 depth=1、INV-006 named function、EC-004/008 wiring、protected baseline |
| S01 | pre-implementation spec review #5 | spec-reviewer | fresh | failed | no | blocked / follow-up required | current gate state、named test実在性、EC-008 negative inspection、親Epic scope exception |
| S01 | pre-implementation spec review #6 | spec-reviewer | fresh | failed | no | blocked / follow-up required | Ruff baseline/reproducibility、full pytest evidence、EC-002 named multi-seed test |
| S01 | pre-implementation spec review #7 | spec-reviewer | fresh | failed | no | blocked / follow-up required | current full-suite/report mismatch、EC-002 sensitivity、closure exactness、format disposition、stale next actions |
| S01 | pre-implementation spec review #8 | spec-reviewer | fresh | failed | no | blocked / follow-up required | S00 six-path provenance、explicit depth=2 integration、parent Epic scope exception、full-suite environment evidence |
| S01 | pre-implementation spec review #9 | spec-reviewer | fresh | failed | no | blocked / follow-up required | draft designのruntime blocking、canonical promotion/runbook readiness transition、D-005 duplicate ID |
| S01 | pre-implementation spec review #10 | spec-reviewer | fresh | failed | no | blocked / follow-up required | report gate update order、report evidence gateとの一致、post-promotion active show |
| S01 | pre-implementation spec review #11 | spec-reviewer | fresh | failed | no | blocked / follow-up required | EAL-005 gate scope、ChatGPT receipt completeness、top-level config depth=2 app integration |
| S01 | pre-implementation spec review #12 | spec-reviewer | fresh | failed | no | blocked / follow-up required | Grade Specialist Evidence Gate、delegated worker decision-note |
| S01 | pre-implementation spec review #13 | spec-reviewer | fresh | failed | no | blocked / follow-up required | #13 retryでproduct CLI grade rationaleとtc-010 closureを指摘。D-013で修正 |
| S01 | pre-implementation spec review #14 | spec-reviewer | fresh | failed | no | blocked / follow-up required | Standard profileのStrict trigger、policy authority、tc-010個別closure不足を指摘。D-014で記録 |
| S01 | pre-implementation spec review #15 | spec-reviewer | fresh | pending | no | blocked / review required | #14 P1解消後に正式Strict/policy route、canonical docs、assurance binding、tc-010 closureを再確認 |
| S01 | code review | code-reviewer | not_started | not_started | N/A | blocked | source未実装 |
| S01 | QA review | qa-reviewer | not_started | not_started | N/A | blocked | source/test未実装 |

#### ステップ commit ゲート（Step Commit Gate）
| ステップ（step） | クロージャ状態（closure state） | コミット範囲（commit scope） | コミットハッシュ / 最終台帳（commit hash / final ledger） | コミット後 clean 確認（post-commit clean check） | 差分なし根拠（no-op rationale） | 差分なし確認済み契約 / ファイル（no-op checked contracts / files） | 差分なし diff-clean コマンド（no-op diff-clean command） | 差分なし read-only 確認（no-op read-only confirmation） |
|---|---|---|---|---|---|---|---|---|
| S01 | not_started / no commit by instruction | no commit | none | not applicable; worktree intentionally retains user/managed diffs | implementation未開始、commit/push/merge禁止 | issue docs + assurance binding checked | `git diff --check` -> pass | no commit operation performed |

#### 変更したファイル
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00002-foundation-contracts/issues/iss-00044-diff-default-depth/requirement.md` - canonical requirement and INV/EC traceability.
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00002-foundation-contracts/issues/iss-00044-diff-default-depth/design.md` - canonical design（second review repairでは変更なし）。
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00002-foundation-contracts/issues/iss-00044-diff-default-depth/plan.md` - closure mapping and step-local execution contract.
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00002-foundation-contracts/issues/iss-00044-diff-default-depth/report.md` - observed planning/review evidence and current gates.
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00002-foundation-contracts/issues/iss-00044-diff-default-depth/.assurance.json` - regenerated by the canonical `assurance classify` command; not hand-edited.
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00002-foundation-contracts/issues/iss-00044-diff-default-depth/artifacts/20260804t093411z-chatgpt-output-chatgpt-depth-design-review.md` - imported evidence artifact.
- SpecDock managed update bundle and `.serena/project.yml` - pre-existing/in-scope retained diffs; no manual repair.

#### 保護境界の実装前baseline（EXEC-PROTECTED-BASELINE）

実装前に次のコマンドを実行し、Issue実装の所有範囲と既存差分を分類した。

```bash
git status --short --untracked-files=all
git status --short -- .agents/skills/pyclassuml-repo-map
git status --short -- .serena/project.yml
git status --short -- src tests README.md
```

観測結果は `HEAD (no branch)`、全status entry `317`（`.agents=37`, `.codex=23`, `.github=6`, `.serena=1`, `spec-dock=250`, `src=0`, `tests=0`, `README.md=0`）だった。`.agents/skills/pyclassuml-repo-map` のstatusは空、`.serena/project.yml` は `M`、`src/tests/README` は空であり、protected source-task skillとuser既存Serena変更を保持した。

| 分類 | 現在の対象 | 所有者 / 扱い | 実装後の判定 |
|---|---|---|---|
| protected skill | `.agents/skills/pyclassuml-repo-map`（status 0） | 元タスクのskill。今回変更禁止 | 実装前後でstatus空を維持 |
| user existing | `.serena/project.yml`（`M`） | ユーザー既存変更。今回の差分へ混在させない | 同一変更を保持し、新規差分を追加しない |
| managed update | `.agents`, `.codex`, `.github`, `spec-dock`のupdater差分 | SpecDock更新で発生した既存managed bundle。手修復せず保持 | 実装前baselineとの差分を変更しない |
| issue-local planning | iss-00044配下の10 untracked files（requirement/design/plan/report、artifact、discussion/rules、metadata、assurance） | 本Issueのplanning/evidence。canonical command生成物を含む | report/docsの意図した更新として追跡 |
| implementation surface | `src=0`, `tests=0`, `README=0` | 実装前は変更なし | S01/S02/S90の許可pathだけが新規変更になる |

実装後も同じpath別statusを取り、protected skillが空、Serenaが元の`M`のまま、managed updater bundleのbaseline以外に新規変更がなく、source/tests/READMEがplanのallowed pathだけであることを`tc-009`へ記録する。

S00後の再確認では、protected skillのstatusは空、`.serena/project.yml`は既存の`M`、production `src=0`、README=0、testsはplanで許可した6ファイル（既存S00変更を含む）のみが変更された。これはproduction実装前のtest-only preparationであり、S01のsource変更 admissionとは分離して扱う。

#### コミット
- なし。ユーザー指示によりcommit/push/PR/mergeは未実施。

#### メモ
- production source/README/skill変更はまだない。fresh spec review #1〜#14がfailのため、production実装開始を停止している。S00の6 test pathsとtop-level config app integration testはtest-only preparationとして完了し、S00-PROMOTEは#14 P1解消後のfresh #15 pass待ちである。

---

### 修正セッションログ（2026-08-04）

#### 対象
- Step: pre-implementation spec review #2 remediation
- AC/EC: AC-006、EC-001〜EC-008、INV-005/006、tc-003/tc-005/tc-007/tc-008/tc-009

#### 実施内容
- EC全件のclosure ownerと期待値、INV-005/006のnamed evidence、S01/S02/S90/S99のstep-local execution contractをplan/requirementへ追加した。
- EAL-001とreport各gateを現時点のreview verdictおよび未実施状態へ更新した。
- 正規`assurance classify`でsource bindingを再生成し、`assurance verify`、`validate`、`doctor`、`git diff --check`の再通過を確認した。
- fresh spec-reviewer #15を実施するまでproduction source/README実装を保留する。S00 six-path test-only preparation、tc-006 integration補正、top-level config app integration補正、Grade Specialist Evidence Gate/worker decision-note、tc-010 closureのreport補正だけは実装前証跡の補正として許可する。#14 P1の正式Strict/policy route解消と#15 pass後はreport gateを先に更新し、S00-PROMOTEでcanonical designをapprovedへ昇格し、workflow/runbook readinessを確認する。

---

## 最終品質ゲート（Final Quality Gate / 必須）

### ドキュメント影響の解消ステップ S90（Docs Impact Resolution）
| 対象 | 更新要否 | 担当（owner） | 証跡（evidence） | 仕様レビュアー結果（spec-reviewer result） |
|---|---|---|---|---|
| README | yes | doc-writer（S90、未起動） | DOC-001〜DOC-007をplanへ固定済み、README変更未実施 | blocked（pre-implementation spec review #1〜#14 fail、#15 required） |

### 最終 QA ゲート（Final QA Gate）
| レビュアー（reviewer） | 範囲 | 統合テスト判断（integration test decision） | 証跡（evidence） | 結果（result） |
|---|---|---|---|---|
| qa-reviewer | whole issue obligation coverage | not_started | source/tests未実装、S02/S99未実施 | blocked |

### 最終コードレビューゲート（Final Code Review Gate）
| レビュアー（reviewer） | 範囲 | 指摘 / 修正（findings / fixes） | 再 review 回数（re-review count） | 結果（result） |
|---|---|---|---|---|
| code-reviewer | issue-wide integrated diff | not_started; source diffなし | 0 | blocked |

### 最終 spec review ゲート（Final Spec Review Gate）
| レビュアー（reviewer） | 範囲 | 指摘 / 修正（findings / fixes） | 再 review 回数（re-review count） | 結果（result） |
|---|---|---|---|---|
| spec-reviewer | requirement / design / plan / report alignment before production implementation | #1/#2/#3/#4/#5/#6/#7/#8/#9/#10/#11/#12/#13/#14 fail; #15 required after formal Strict/policy resolution, Standard exception disposition, and tc-010 closure repair | 14 | blocked |

### 最終 commit（Final Commit）
| 最終 report 台帳（final report ledger） | 最終 commit 範囲（final commit scope） | コミット後の外部証跡送付先（post-commit external evidence destination） | 結果（result） |
|---|---|---|---|
| no commit | no commit/push/PR/merge per user instruction | final response and source-task Markdown handoff only | blocked pending implementation and final gates |

## 遭遇した問題と解決 (任意)
- 問題: ChatGPT-Firstのformal Candidate lifecycleはdetached HEAD/GitHub exact HEAD不成立で利用できず、fresh spec-reviewer #1〜#12は検証契約・保護境界・台帳整合・実行可能性・品質baseline・runtime promotion・report evidence gateを段階的に指摘した。#14ではStandard profileのStrict triggerが不受理となった。
  - 解決: formal routeとlocal advisoryを混同せず、managed stateを手修復せずにcanonical docsとclosure/report証跡を補強した。S00 six-path provenance、tc-006 explicit integration、top-level config app integration、parent scope exception、pinned tooling/full-suite environment evidence、S00-PROMOTEのcanonical design/runbook transition、report先行gate更新、post-promotion active show、Grade Specialist Evidence Gate、worker decision-note、Standard scope exception、Strict相当の補償ゲート、tc-010 closureを追加した。#14のP1は正式Strict/policy routeが必要なため、解消後に#15を次のゲートとする。

## 学んだこと (任意)
- ChatGPT advisoryの設計主張は、canonical docsへ採用する前にsource/test evidenceとstep-local closureへ分解し、raw bind値とresolver後のeffective値を別の観測点として固定する必要がある。

## 今後の推奨事項 (任意)
- S00 six-path provenance/tc-006 integration/top-level config app integration/parent scope exception/full-suite evidence、Grade Specialist Evidence Gate/worker decision-note、tc-010 closure、#14 P1の正式Strict/policy resolution、fresh spec-reviewer #15 pass、report先行のS00-PROMOTE approved design/runbook readinessの後にのみ、plan S01のproduction dev-coder委任、S90のdoc-writer委任、S02/S99の実装・品質ゲートへ進む。

## 省略/例外メモ (必須)
- 該当なし
