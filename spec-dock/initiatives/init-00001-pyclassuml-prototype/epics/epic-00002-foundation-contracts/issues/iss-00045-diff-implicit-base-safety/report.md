---
種別: 実装報告書（Issue）
ID: "iss-00045"
タイトル: "Diff Implicit Base Safety"
関連GitHub: ["#45"]
状態: "draft | approved"
作成者: "iwasawayuuta"
最終更新: "2026-08-07"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00002", "init-00001"]
---

# iss-00045 Diff Implicit Base Safety — 実装報告（観測証跡台帳 / Observed Evidence Ledger）

> `report.md` は観測証跡台帳（observed evidence ledger）の scaffold です。planned requirements、evidence destination、closure 条件は `plan.md` が持ち、この文書は実際の Red / Green / Refactor evidence、発見された tests、closure delta、reviewer status、commit/no-op evidence を記録する evidence slot です。workflow / compliance authority は skills、docs、accepted ADRs、reviewer gates に置きます。

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
| D-001 | resolved | implementation | user report / ChatGPT review | default branch no-baseがinitial commitへ遡る | current HEAD / remote default / merge-base / initial fallback | default branch + working-treeは開始時HEAD SHA、default branch + headは明示base必須、feature/detachedはmerge-base、解決不能はfailure | promoted_to_plan | requirement.md、design.md、plan.md、source/tests、`artifacts/20260807t014601z-chatgpt-output-chatgpt-diff-base-spec-review.md` | なし |
| D-002 | resolved | compatibility | ChatGPT review | partial clone lazy fetch、external diff/textconv、nested project path境界 | 現行Git既定 / fail-closed subprocess contract | `GIT_NO_LAZY_FETCH=1`、diff安全flags、raw VCS path carrier、project-relative public DTOを採用 | promoted_to_plan | design.md、tests/vcs/test_diff_file_collect.py、artifact EAL-002 | shallow/partial clone UXは別Issue候補 |
| D-003 | open | operation | fresh ChatGPT implementation review | exact GitHub branchが未commitの実装スナップショットと不一致 | local working tree / pushed exact HEAD | local source/tests/docsを先に完成させ、commit後にpushしてexact branch parityを再確認する | deferred | `artifacts/20260807t023033z-chatgpt-output-chatgpt-diff-base-implementation-review.md` | parity確認後にresolvedへ更新 |

## 証跡採用台帳（Evidence Adoption Ledger / 必須）

Delegated draft、worker note、research、reviewer finding、discussion、command output を canonical artifact や実装判断へ取り込む場合、この台帳に採用判断を記録する。raw transcript ではなく、orchestrator が検証した採否・理由・証跡・次アクションだけを記録する。

- `adoption_status`: `adopted` / `partially_adopted` / `rejected` / `deferred` / `stale` / `blocked`
- `blocked` または `stale` の unresolved entry は promotion / implementation start / issue ready / issue finish / phase completion を止める。
- `deferred` は blocking でない根拠と revisit 条件を持つ場合だけ完了時に残せる。
- Evidence Adoption Ledger なしで delegated evidence の採用を主張してはならない。
- Evidence Adoption Ledger fields: ID, adoption_status, source, source_role, claim, target_artifact, target_section, rationale, evidence_strength, evidence_path, adopter, reviewer, blocking, next_action.

| 識別子（ID） | 採用状態（adoption_status） | 出所（source） | 対象（target） | 判断理由（rationale） | 証跡（evidence） | 次アクション（next_action） |
|---|---|---|---|---|---|---|
| EAL-001 | adopted | ChatGPT authoring artifact | canonical requirement/design/plan | 3文書のformal candidateとして採用し、ローカルsource/testsで検証 | ChatGPT-Use browser evidence; GPT-5.6 Sol verified; imported artifact SHA-256 `e7fc0fdb68bf087c03f1672c442874a010401c5cba7b487e6ec221c53190aa38` | 実装後のfresh spec reviewで再確認 |
| EAL-002 | partially_adopted | ChatGPT spec review artifact | canonical docs / implementation plan / tests | P1/P2 findingsをsource・tests・docsへ反映。review verdict自体は初回 `FAIL` のため完了ゲートではない | imported artifact SHA-256 `30d88d249701cc454a04cf88eee29c1a345e25415a6d951612217b7c0970fa20` | 実装後にfresh code/QA/spec review |
| EAL-003 | deferred | SpecDock ChatGPT-first planner | planning workflow | repo-local adapterがoracle 0.16.1 exactを要求し、PATH oracle 0.17.0/0.17.1のためformal sessionを開始できなかった。今回の要件定義・レビューはChatGPT-Use evidence laneで完結させ、formal transportの迂回はしない | command output: `oracle_capability_unsupported`; ChatGPT-Use artifact/reviewを別台帳で検証 | SpecDock provider contractが更新され、formal plannerを再実行できる場合に再訪。今回の実装完了ゲートをブロックしない根拠を記録 |
| EAL-004 | partially_adopted | fresh ChatGPT implementation review | source/tests/docs/report | P1-2件・P2-4件を現物へ反映。P1-1はcommit/push後のexact branch parity、P1-2は#44 authority noteを追加して継続確認する | imported artifact SHA-256 `f91815181197df66545546bda397e3e5a200e142845639b542dff9ed8509de07`; GPT-5.6 Sol / browser model picker / verified=yes | commit/push後にexact branchを再取得して再レビュー |

## 目的整合台帳（Objective Alignment Ledger / 必須）

主要目的と副次要件の主従が逆転していないことを記録する。特に clarification / authoring / handoff の変更では、primary objective evidence、secondary requirement evidence、inversion risk、reviewer verdict を残す。

| 対象 | 主要目的の証跡（primary objective evidence） | 副次要件の証跡（secondary requirement evidence） | 逆転リスク（inversion risk） | レビュアー判定（reviewer verdict） |
|---|---|---|---|---|
| OAL-001 | default branchでの意図しない全履歴走査を止め、working-treeの日常利用を維持する | explicit base authority、read-only、depth/config regression、scope diagnostic | 低 | provisional / implementation verification pending |

## 仕様 authoring ゲート（Spec Authoring Gate / 必須）

Requirement / design / plan の phase promotion ごとに、調査、未確定事項、回答、採用判断、reviewer verdict、blocking / non-blocking、次アクションを記録する。

| フェーズ（phase） | 調査証跡（investigated facts） | 未確定事項 / 回答（open questions / answers） | 採用判断（adoption decision） | レビュアー判定（reviewer verdict） | ブロック有無（blocking） | 昇格 / 次アクション（promotion / next_action） |
|---|---|---|---|---|---|---|
| requirement / design / plan | imported ChatGPT formal docs、local source/tests、#36/#44 authority docs、fresh implementation review | initial review findingsは反映済み。fresh reviewは P0=0/P1=2/P2=4、exact branch parityと最終ゲートが未完了 | partially_adopted; local corrections applied | conditional / not a final pass | yes | commit/push、exact HEAD parity、independent code/QA/spec review |

## 委任ドラフト証跡（Delegated Draft Evidence / 必須）
- 委任 authoring の使用:
  - used
- 未使用の場合:
  - manual authoring path / 委任ドラフトを昇格証跡として使っていない理由。
- lifecycle state（契約値）:
  - `requested`, `produced`, `integrated`, `partially_integrated`, `rejected`, `superseded`, `blocked`, `stale`
- 昇格不可 state:
  - `stale`, `rejected`, `superseded`, `blocked`
- 標準出力先:
  - 対象 scope の `artifacts/` direct child にある flat Markdown
  - filename: typed artifacts use `<ts>-<type>-<slug>.md` or `<ts>-<nn>-<type>-<slug>.md`; blank artifacts use `<ts>-<slug>.md` or `<ts>-<nn>-<slug>.md`
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
  - legacy `discussions/` と既存 `iss-00126` などの manifest/Profile/probe/session artifacts は grandfathered evidence として残し、削除・rename・validation failure 化しない。

| ロール（created_by_role） | 範囲（scope_id） | ドラフトパス（artifact draft path） | 参照元（source_paths） | 予定反映先（intended_targets） | 採用状態（adoption_status） | 反映先（reflected_to） | 差分ガード結果（diff_guard_result） | 統合結果 | 採用しなかった部分 | ブロッカー | レビュー結果（reviewer result） | 昇格判断（promotion decision） |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ChatGPT-Use authoring | iss-00045 | `artifacts/20260807t011027z-chatgpt-output-chatgpt-diff-implicit-base-formal-docs.md` | source/tests、interview context、#36 docs | requirement/design/plan | partially_integrated | canonical requirement/design/plan | imported artifact checksum; source sections extracted and normalized | canonical docsへ反映、レビュー指摘を追加採用 | 初回レビューFAILの未修正部分はなし。fresh reviewは未完了 | fresh code/QA/spec review | initial ChatGPT review: FAIL; findings adopted | implementation後に再レビュー |

### 委任ドラフトの失敗モード（Delegated Draft Failure Modes）
| 失敗モード | 期待される判定 | 許可される次アクション | レポート証跡の記録先（report evidence destination） | 昇格可否 |
|---|---|---|---|---|
| ワークフロー単位の許可証跡不足（missing workflow-scoped authorization evidence） | blocked / incomplete | ワークフロー利用依頼の authorization source と boundary を記録する、または手動 authoring に戻す | ワークフロー単位の named role 許可（Workflow-Scoped Authorization） / この section | ineligible |
| 前段 reviewer pass 不足 / stale（missing/stale previous reviewer pass） | blocked / incomplete | レビューゲートを再実行する（rerun reviewer gate） | レビューゲート証跡（Reviewer Gate Status / Final Spec Review Gate） | ineligible |
| 設計中の要件 gap（requirement gap during design） | blocked / incomplete | requirement phase へ戻す | 仕様解釈・判断台帳（Spec Interpretation / Decision Ledger） | ineligible |
| 計画中の設計 gap（design gap during plan） | blocked / incomplete | design phase へ戻す | 仕様解釈・判断台帳（Spec Interpretation / Decision Ledger） | ineligible |
| ロール利用不可（role unavailable） | blocked / manual path | 利用不可を記録し、妥当なら手動で続行する | この section | ineligible |
| 禁止行為の試行（forbidden action attempt） | rejected | ドラフトを破棄し incident を記録する | この section / decision ledger | ineligible |
| 古いドラフト（stale draft） | stale | 再生成または差分調整する | この section | ineligible |
| 置換済みドラフト（superseded draft） | superseded | 置換先ドラフトを参照する | この section | ineligible |
| 委任使用主張に対する証跡不足（missing draft evidence when delegated use is claimed） | incomplete | 証跡を追加する、または委任使用 claim を外す | この section | ineligible |
| reviewer 利用不可 / 拒否 / waiver / provisional（reviewer unavailable/denied/waived/provisional） | blocked / incomplete | fresh な passed reviewer を取得する、または昇格なしの risk acceptance を記録する | レビューゲート証跡（Reviewer Gate Status / Final Spec Review Gate） | ineligible |

## 実装サマリー (任意)
- `diff` の no-base resolver を、default branch の working-treeでは開始時 `HEAD` SHA、default branchの `head` では明示base必須、feature/detachedでは local merge-base、解決不能では fail-closed とする契約へ変更した。initial commitへの暗黙fallbackは production pathから廃止し、legacy DTO/report constructionの受理だけを維持した。
- raw changed pathとhunk enrichmentを分離し、implicit 1,000件上限、Git lazy fetch/external diff/textconv無効化、nested project path carrier、scope-only diagnosticを追加した。`generate`、config/depth resolver、traversal、report DTOの不要な変更は行っていない。

## ChatGPT-First authoring / review evidence

- formal docs candidate: `artifacts/20260807t011027z-chatgpt-output-chatgpt-diff-implicit-base-formal-docs.md`
- formal spec review: `artifacts/20260807t014601z-chatgpt-output-chatgpt-diff-base-spec-review.md`
- fresh implementation review: `artifacts/20260807t023033z-chatgpt-output-chatgpt-diff-base-implementation-review.md`
- ChatGPT-Use model evidence: requested/resolved `GPT-5.6 Sol`、browser model picker、verified=yes。
- 初回 spec review verdict は `FAIL`（P0なし、P1=7、P2=4）。read-only、config state authority、nested raw path、revision grammar、#36 plan migration、captured HEAD SHA、artifact/assurance鮮度の指摘を requirement/design/plan、source/testsへ反映した。初回FAILは最終review passを意味しない。
- fresh implementation review は `P0=0 / P1=2 / P2=4`。P1-1（exact branch parity）をcommit/push後の再確認へ保留し、P1-2（#44 authority境界）とP2の診断文言・app guard・detached/matrix/depthテストをローカルへ反映した。ChatGPT自身はテスト未実行のため、実行結果はローカルpytest/Ruff/SpecDockの証跡で別途確認する。
- SpecDockのformal ChatGPT-first plannerは repo-local adapter の `oracle 0.16.1` exact要件と現行PATH oracle `0.17.0/0.17.1` の不一致で blocked だったため、formal transportの迂回は行わず、ChatGPT-Use evidence laneを advisory として採用した。

## 実装記録（セッションログ） (必須)

### 実測セッション（2026-08-07）

#### 対象
- Step: S01〜S08
- AC/EC: default branch no-base、explicit base、feature/detached candidate、breadth guard、scope-only diagnosis、depth/config non-interference、read-only Git boundary、docs/spec traceability
- 実装基準: clean clone `codex/iss-00045-diff-implicit-base-safety`。元 worktree の `.serena/project.yml` は変更していない。

#### 実施内容
- VCS resolver を default branch working-tree の開始時 `HEAD` SHA、default branch `head` の explicit-base requirement、feature/detached の merge-base、候補不足の fail-closed へ変更した。
- raw VCS path を保持した changed-entry collection と hunk enrichment を分離し、implicit 1,000 path guard、Git offline/read-only flags、nested project boundary を実装した。
- target seam に scope-only diagnostic と、scope/file-type/ignore filtering を含む generic zero-target message を追加した。
- `iss-00036` の supersede 境界、`iss-00044` の authority note、README/CLI help、ChatGPT review artifacts/report を更新した。

#### 実行コマンド / 結果
```bash
uv run pytest tests/vcs/test_diff_file_collect.py tests/targets/test_diff_target_normalize.py tests/app/test_diff.py tests/config/test_context_resolve.py tests/model/test_contracts.py tests/cli/test_main.py
# 232 passed

uv run pytest
# 500 passed in 16.40s

uv run ruff check src/pyclassuml/cli/bind.py src/pyclassuml/model/contracts.py src/pyclassuml/targets/diff.py src/pyclassuml/vcs/diff_collect.py tests/app/test_diff.py tests/cli/test_main.py tests/model/test_contracts.py tests/targets/test_diff_target_normalize.py tests/vcs/test_diff_file_collect.py
# All checks passed!

python -m compileall -q src tests
git diff --check
# pass

./spec-dock/scripts/spec-dock validate
# spec-dock: ok (validate) nodes=42

./spec-dock/scripts/spec-dock doctor
# spec-dock: ok (doctor) findings=0

./spec-dock/scripts/spec-dock assurance classify --stage requirement
# authorized_profile=standard, complexity_tier=normal, reason=ok
```

全体 `uv run ruff check` は今回変更外の `src/pyclassuml/render/document.py` に既存の F821 4件があり非0だった。対象変更ファイルのRuffは通過しており、既存baselineとして記録する。現行対象 checkout への smoke は current clean-clone executable で実施したが、対象が feature branch かつ scope内変更なしだったため `default_branch_merge_base` / zero-target の結果であり、旧 `8bb20e9` の default-branch initial-fallback挙動や本修正の default-branch fixtureを検証する証拠にはしない。

#### テスト駆動開発証跡（TDD / Red / Green / Refactor Evidence）
| フェーズ | 観測した証跡 | 結果 | メモ |
|---|---|---|---|
| Red / characterization | 旧 initial-fallback期待を新 fail-closed / `default_branch_head` 契約へ置換し、source/test差分を確認 | approved-no-op | 旧契約の baseline は #36 と report artifact に保持 |
| Green | focused suite、全体500件、depth 0/1/2 invariance、detached、breadth、scope-only、app guard、Git state/sentinelを実行 | pass | ChatGPTレビュー自身はテスト未実行。実行事実は本セッションのコマンド結果 |
| Refactor / guardrail | targeted Ruff、compileall、diff check、SpecDock validate/doctor | pass | whole Ruffは既存4 F821を別記 |

#### 発見されたテスト / リスク
| テスト / リスク | 起票元 | 対応 | 状態 |
|---|---|---|---|
| exact GitHub branchが未commitの実装と不一致 | fresh ChatGPT implementation review | commit/push後にexact HEAD parityを再確認する | open / blocking completion |
| `iss-00044` の初期 authority文言 | fresh ChatGPT implementation review | requirement/design/planへ#45 authority noteを追加 | applied / independent spec review pending |
| diagnostic wordingとdepth/guard/scope matrixの不足 | fresh ChatGPT implementation review | source/tests/README/helpへ反映しfocused/full suiteで検証 | applied |

#### 実測時点の closure
- local implementation and tests: pass
- SpecDock structural validation: pass
- independent code/QA/spec review: pending
- commit/push/exact remote parity: pending
- PR/merge/main-side pull: not started

#### Evidence ID 対応表
| Evidence ID | 観測結果 |
|---|---|
| EVD-001 | clean clone branch `codex/iss-00045-diff-implicit-base-safety`、pre-implementation remote HEAD `e5a4cf2`、source changeは未commit時点で確認 |
| EVD-002 | focused suite pass、full suite 500 passed in 16.40s after added app/read-only/breadth/sentinel tests |
| EVD-003 | `assurance classify` / `verify` pass、正規 profile は standard、Strict相当はmanual escalationとして記録 |
| EVD-004〜EVD-009 | model kind、default branch HEAD、default branch head failure、candidate failure、guard boundary/stop-order、explicit bypassのfocused tests pass |
| EVD-010 | scope-only、mixed、ignored-only、non-Python、empty、project-root外のtarget matrixをfocused testsで確認 |
| EVD-011 | app default/head、feature failure、breadth guard、help phraseを確認。CLI full smokeは現行対象branchのscope外変更のみで本契約の成功証跡にしない |
| EVD-012 | VCS/target seamとapp seamでdepth 0/1/2のbase、changed entries、seed不変、reachable graph差を確認し、full suite 500 passed |
| EVD-013 | Git state（HEAD/branch/status/index/refs）前後不変、forbidden command不使用、external diff/textconv sentinel不実行をfocused testsで確認。partial/promisor clone実fixtureは未実施 |
| EVD-014 | README/helpにbranch/state、exit 1/artifactなし、安全flags、explicit remediationを反映 |
| EVD-015 | #36 supersede note、#44 authority noteを3文書へ反映し、SpecDock validate pass |
| EVD-016〜EVD-017 | latest source/docs反映後のfull suite、diff check、validate/doctorを再実行予定。直近validate/doctorはpass |
| EVD-018 | commit/push、exact remote SHA、PRは未実施 |

### セッションログ（2026-08-05 HH:MM - HH:MM）

#### 対象
- Step: S01, S02, ...
- AC/EC: AC-___, EC-___
- 計画上の出典（Planned source）:
  - `plan.md` section:
  - closure ids:

#### 実施内容
- ...

#### 実行コマンド / 結果
```bash
<command>

<result>
```

#### テスト駆動開発証跡（TDD / Red / Green / Refactor Evidence）
| ステップ（step） | フェーズ（phase） | 計画した証跡要件 | 観測した証跡 | 証跡手段（command / inspection / manual record） | 結果（result） | メモ（notes） |
|---|---|---|---|---|---|---|
| S01 | 赤フェーズ / 代替証跡（Red / alternative） | red-required / covered-existing / inspect-only / manual-required | ... | `command` / 文書点検（docs inspection） / 手動記録（manual record） | pass / approved-no-op / fail / blocked | ... |
| S01 | 緑フェーズ（Green） | ... | ... | `command` / 点検（inspection） / 手動記録（manual record） | pass / fail / blocked | ... |
| S01 | リファクタリング（Refactor） | guardrail satisfied / no refactor needed | ... | 差分点検（diff inspection） / command | pass / approved-no-op / fail / blocked | ... |

#### 発見されたテスト / リスク（Discovered Tests）
| ステップ（step） | 発見されたテスト / リスク（test / risk） | 起票元（source） | 実施した対応 | クロージャID / 新規ID（closure id / new id） | 計画修正要否（plan amendment required） | 証跡（evidence） |
|---|---|---|---|---|---|---|
| S01 | none / ... | implementation / review / QA / user report | recorded / added test / deferred / amended plan | tc-001 / new | yes / no | ... |

#### ステップ契約の完了証跡（Step Contract Closure）
| ステップ（step） | クロージャID（closure ids） | 計画上の close 条件（close condition from plan） | 観測した証跡 | 結果（result） | メモ（notes） |
|---|---|---|---|---|---|
| S01 | tc-001 | ... | ... | pass / approved-no-op / fail / blocked | ... |

#### テスト契約の完了証跡（Test Contract Closure）
| クロージャID / テストID（closure id / test id） | ステップ（step） | 必須 | 証跡レベル（evidence level） | 実装前証跡 | 検証コマンドまたは代替 path | 観測結果 | メモ（notes） |
|---|---|---|---|---|---|---|---|
| tc-001 | S01 | yes | red-required / covered-existing / inspect-only / manual-required | ... | ... | pass / approved-no-op / fail / blocked | ... |

- `closure id / test id` は Spec-Locked Closure Index の `id` を指す。別 alias を使う場合は `Closure Delta` で対応を記録する。

#### クロージャ網羅（Closure Coverage）
| クロージャID（closure id） | ステップ（step） | 検証証跡 | 観測結果 | メモ（notes） |
|---|---|---|---|---|
| tc-001 | S01 | ... | pass / approved-no-op / fail / blocked | ... |

#### クロージャ差分（Closure Delta）
| 変更種別（change） | クロージャID（closure id） | テストID alias（test id alias） | 解決先クロージャID（resolved closure id） | 理由 | 計画修正要否（plan amendment required） | 再レビュー要否（re-review required） |
|---|---|---|---|---|---|---|
| none / added / removed / changed / alias-mapped | tc-001 | tc-001 / test-name | tc-001 | ... | yes / no | yes / no |

#### ワークフロー単位の named role 許可（Workflow-Scoped Authorization）
`workflow_issue.md` is the policy source for workflow-scoped authorization. This report records observed authorization source, boundary, expiry, and denied / unavailable / host conflict handling only.

Authorization source は、ユーザーによる SpecDock workflow 利用依頼でよい。範囲は active repo/worktree、active SpecDock scope、current session、SpecDock-defined named roles、documented role responsibility に限る。この section は role ごと・phase ごとの追加承認 gate ではなく、scope 内の named role 利用前に追加許可を求める根拠にしてはならない。

別途確認が必要なのは scope expansion、破壊的操作、外部公開、credential を伴う外部 mutation、private external system、SpecDock workflow 外の role 利用である。unavailable / denied / host conflict は fail-closed とし、fresh `passed` reviewer gate の代替にしてはならない。

| 許可元（authorization source） | リポジトリ / worktree（repo/worktree） | 対象課題（active issue） | セッション（session） | 指名ロール（named roles） | 境界（boundary） | 期限 / 無効化条件（expires / invalidation condition） | 拒否 / 利用不可 / host conflict 理由（denied / unavailable / host conflict reason） | 次アクション（next action） |
|---|---|---|---|---|---|---|---|---|
| ワークフロー利用依頼 / 明示承認 / なし（user request to use SpecDock workflow / explicit approval / none） | ... | iss-00045 | 現在セッション（current session） / ... | spec-reviewer / code-reviewer / qa-reviewer / read-only specialist | 範囲: active repo/worktree、active SpecDock scope、current session、SpecDock-defined named roles、documented role responsibility。破壊的操作 / 外部公開 / credentialed external mutation / scope expansion / private external system use / out-of-workflow role は含めない | 完了 / セッション終了 / scope 変更 / host policy conflict / user revocation（issue complete / session end / scope change / host policy conflict / user revocation） | none / denied / unavailable / host conflict | 続行 / separate-confirmation exception は user に確認 / block gate / record waiver request |

#### 実装委任ゲート（Implementation Delegation Gate）
`workflow_issue.md` is the policy source for delegation, reviewer gates, waiver, unavailable, denied, and host-conflict semantics. This report records observed evidence only.

| ステップ（step） | 判断（decision） | 必須理由（required reason） | 委任ロール（delegated role） | 委任範囲（delegated scope） | 正本（source of truth） | 許可変更（allowed changes） | 禁止変更（forbidden changes） | 必須検証（required verification） | 停止条件（stop conditions） | 必須出力（output required） | 観測結果（observed result） |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S01 | delegated / approved-local-execution / degraded mode | multi-layer / shipped scaffold / pattern analysis / integration / large worker scope / none | repo-analyst / dev-coder / doc-writer / N/A | ... | ... | ... | ... | ... | ... | worker summary / changed files / verification / risks / integration decision | pass / fail / blocked |

#### 委任 worker 証跡（Delegated Worker Evidence）
| ステップ（step） | 委任ロール（delegated role） | 委任 worker 要約（delegated worker summary） | 変更ファイル（changed files） | 実行 tests または docs-only 検証（tests run or docs-only verification） | レビュアー判定（reviewer verdict） | 未解決リスク（unresolved risks） | 親統合判断（parent integration decision） |
|---|---|---|---|---|---|---|---|
| S01 | dev-coder / doc-writer / repo-analyst | ... | `path/to/file` | `command` -> pass / docs-only inspection -> pass | pass / fail / unavailable / denied / waived / provisional | none / ... | accepted / rejected / needs follow-up |

#### 親実装例外（Parent Implementation Exception）
| ステップ（step） | 委任不可 / 不可能理由（delegation unavailable/impossible reason） | ユーザー承認 / risk acceptance（user approval / risk acceptance） | 許可ファイル（allowed files） | 許可操作（allowed operation） | ロールバック計画（rollback plan） | 変更後検証（post-change verification） | レビューゲート（reviewer gate） | 利用不可 / 拒否 / host conflict / waiver 対応（unavailable / denied / host conflict / waiver handling） |
|---|---|---|---|---|---|---|---|---|
| S01 | unavailable / denied / host conflict / impossible because ... | approval source / risk accepted: yes / no | `path/to/file` | ... | ... | `command` -> pass / docs-only inspection -> pass | reviewer role + passed / failed / unavailable / denied / waived / provisional | blocked / incomplete / waived with explicit risk acceptance / next action |

#### グレード別専門家証跡ゲート（Grade Specialist Evidence Gate）
Lite は specialist / fallback evidence を必須化しないが、not applicable / skip reason を記録する。Standard は specialist evidence、skip reason、または manual fallback を記録する。Strict / Critical は specialist evidence または明示的な manual fallback を記録し、skip reason だけでは readiness evidence にしない。

正規 `assurance classify --stage requirement --issue iss-00045` の観測結果は `authorized_profile=standard`、`complexity_tier=normal` である。要件が要求する Strict 相当は profile の手編集ではなく、公開CLI契約・VCS安全性・rollback境界に対する manual escalation として以下の追加 code/QA/spec review、read-only receipt、exact branch parity gateで実施する。

| グレード（Grade） | 必要な専門家 / 代替（required specialist / fallback） | 使用状況（usage） | 証跡（evidence） | 鮮度 spec-reviewer 判定（fresh spec-reviewer verdict） | 実行可否（execution readiness） |
|---|---|---|---|---|---|
| `lite` | `not applicable` | `not applicable` | ライト該当なし理由（lite not applicable reason） | `pass / fail / blocked` | `ready / blocked` |
| `standard` | `system-architect / implementation-planner / manual fallback` | manual fallback / ChatGPT-Use advisory | `artifacts/20260807t011027z...`、`artifacts/20260807t014601z...`、`artifacts/20260807t023033z...`、local source/tests | provisional / fresh independent review pending | blocked until final gates |
| `strict` | manual escalation: code-reviewer / qa-reviewer / spec-reviewer | required as supplemental gate; profile not overwritten | report EVD-003、EVD-012、EVD-013、final review rows | pending | blocked until exact HEAD parity |
| `critical` | `system-architect / implementation-planner / manual fallback` | `used / unavailable / denied` | `artifacts/...` / explicit approval and risk acceptance | `pass / fail / blocked` | `ready / blocked` |

#### レビューゲート状態（Reviewer Gate Status）
| ステップ（step） | ゲート名（gate name） | レビュアーロール（reviewer role） | 鮮度（freshness） | 状態（state） | リスク受容（risk acceptance） | 昇格 / 完了判断（promotion / completion decision） | メモ（notes） |
|---|---|---|---|---|---|---|---|
| S01〜S08 | final reviewer | code-reviewer / spec-reviewer / qa-reviewer | fresh | provisional; independent results pending | no waiver | blocked until exact branch parity, assurance verify, and all reviewer results are recorded | ChatGPT fresh review P0=0/P1=2/P2=4; local tests pass |

#### マイルストーン / commit 候補ゲート（Milestone / Commit Candidate Gate）
| マイルストーン / step | クロージャ状態（closure state） | コミット候補 / コミット範囲（commit candidate / scope） | コミットハッシュ / 最終台帳（commit hash / final ledger） | コミット後 clean 確認（post-commit clean check） | 差分なし根拠（no-op rationale） | 差分なし確認済み契約 / ファイル（no-op checked contracts / files） | 差分なし diff-clean コマンド（no-op diff-clean command） | 差分なし read-only 確認（no-op read-only confirmation） |
|---|---|---|---|---|---|---|---|---|
| S01〜S08 | implementation pending commit | intended source/tests/docs/artifacts only; root `.workbench/` is intentionally untracked and retained | pending | not yet run | no-op not applicable | pending | pending | target checkout read-only evidence recorded; commit/push not started |

#### 変更したファイル
- `path/to/file1` - ...
- `path/to/file2` - ...

#### コミット
- <hash> <message>

#### メモ
- ...

---

### セッションログ（2026-08-05 HH:MM - HH:MM）

#### 対象
- Step: ...
- AC/EC: ...

#### 実施内容
- ...

---

## 最終品質ゲート（Final Quality Gate / 必須）

### ドキュメント影響の解消ステップ S90（Docs Impact Resolution）
| 対象 | 更新要否 | 担当（owner） | 証跡（evidence） | 仕様レビュアー結果（spec-reviewer result） |
|---|---|---|---|---|
| docs / templates / workflow / migration notes | yes | main orchestrator | README/help、#36 supersede note、#44 authority note、Issue #45 requirement/design/plan/report、ChatGPT artifacts | provisional; independent spec review findings still require closure |

### 最終 QA ゲート（Final QA Gate）
| レビュアー（reviewer） | 範囲 | 統合テスト判断（integration test decision） | 証跡（evidence） | 結果（result） |
|---|---|---|---|---|
| qa-reviewer | whole issue obligation coverage | added focused app/VCS/targets tests; full suite rerun pending after latest tests | focused 232 passed before latest additions; latest 3 app tests passed; full 495 passed before latest additions; EVD-012/EVD-013 to refresh | provisional / blocked until final rerun and independent QA review |

### 最終コードレビューゲート（Final Code Review Gate）
| レビュアー（reviewer） | 範囲 | 指摘 / 修正（findings / fixes） | 再 review 回数（re-review count） | 結果（result） |
|---|---|---|---|---|
| code-reviewer | issue-wide integrated diff | fresh ChatGPT review P0=0/P1/P2 findings applied; independent code review pending | `artifacts/20260807t023033z-chatgpt-output-chatgpt-diff-base-implementation-review.md` | 0 | blocked pending independent review and exact branch parity |

### 最終 spec review ゲート（Final Spec Review Gate）
| レビュアー（reviewer） | 範囲 | 指摘 / 修正（findings / fixes） | 再 review 回数（re-review count） | 結果（result） |
|---|---|---|---|---|
| spec-reviewer | requirement / design / plan / report / implementation / tests / docs alignment | independent review found assurance/report closure gaps; profile/manual escalation and report corrections applied; re-review pending | independent spec review notification; `assurance classify` / `verify`; validate/doctor | 1 | blocked pending fresh pass |

### 最終 commit（Final Commit）
| 最終 report 台帳（final report ledger） | 最終 commit 範囲（final commit scope） | コミット後の外部証跡送付先（post-commit external evidence destination） | 結果（result） |
|---|---|---|---|
| local evidence ledger | source/tests/docs/artifacts; commit not yet created | push→PR→merge→main pullの後に branch parity / SHA / PR evidenceを追記 | blocked until independent gates and commit/push |

## 遭遇した問題と解決 (任意)
- 問題: ...
  - 解決: ...

## 学んだこと (任意)
- ...

## 今後の推奨事項 (任意)
- ...

## 省略/例外メモ (必須)
- 該当なし

<!-- spec-dock:managed-section begin id="report.step-evidence" -->
## Step Evidence
- Record Red, Green, and refactor evidence for each executed step.
- Link each closure id to its observed verification result.
<!-- spec-dock:managed-section end id="report.step-evidence" -->
