---
種別: 実装報告書（Issue）
ID: "iss-00036"
タイトル: "Diff Default Branch Base"
関連GitHub: ["#36"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-22"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00002", "init-00001"]
---

# iss-00036 Diff Default Branch Base — 実装報告（Observed Evidence Ledger）

## Spec Interpretation / Decision Ledger (必須)

| ID | Status | Type | Raised By | Trigger / Gap | Options Considered | Decision / Interpretation | Rationale | Disposition | Evidence | Follow-up |
|---|---|---|---|---|---|---|---|---|---|---|
| D-001 | resolved | interpretation | user / orchestrator | `pyclassuml diff` を簡単に使いたいが、upstream や config 必須化は避けたい | upstream 必須; config default 必須; best effort + initial commit fallback | `--base` は任意化し、未指定時は best effort で branch-start base を解決し、最後は initial commit fallback する | 外部 CLI として利用者に設定を強制せず、ただし resolved base を診断で観測可能にするため | promoted_to_design | `requirement.md`, `design.md`, `plan.md` | none |
| D-002 | resolved | compatibility | user / orchestrator | `--base` 指定時の既存挙動と新しい default behavior の関係 | `--base` の意味変更; `--merge-base` 追加; `--base` 指定時は既存互換 | `--base <ref>` 指定時は既存どおり `<ref>` 自体を base にする | 既存利用者の command と mental model を壊さないため | promoted_to_requirement | `requirement.md` AC-002 | none |

## 実装サマリー
- S01 CLI / model no-base contract を実装済み。
- S02 VCS resolved-base resolver を実装済み。
- S03 app/report/CLI transcript integration を実装済み。
- S90 README docs impact resolution を実施済み。
- final quality gate は未着手。

## 実装記録（セッションログ）

### 2026-05-21 - Issue scaffold

#### 対象
- Step: planning only
- AC/EC: AC-001〜AC-004, EC-001〜EC-003
- Planned source:
  - `requirement.md`
  - `design.md`
  - `plan.md`

#### 実施内容
- `spec-dock new issue` で `iss-00036` / GitHub `#36` を作成した。
- 相談内容を requirement / design / plan に整理した。
- 実装は未着手。

#### 実行コマンド / 結果
```bash
./spec-dock/scripts/spec-dock new issue --epic epic-00002 --title "Diff Default Branch Base" --slug diff-default-branch-base

spec-dock: ok (new issue) id=iss-00036 epic=epic-00002 initiative=init-00001 path=spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00002-foundation-contracts/issues/iss-00036-diff-default-branch-base github=#36
spec-dock: ok (new issue auto-sync)
```

#### Red/Green/Refactor Evidence
| step | phase | planned evidence requirement | observed evidence | command / inspection / manual record | result | notes |
|---|---|---|---|---|---|---|
| planning | inspect-only | issue docs created | requirement / design / plan initialized | docs inspection | pass | implementation not started |

#### Discovered Tests
| step | discovered test / risk | source | action taken | closure id / new id | plan amendment required | evidence |
|---|---|---|---|---|---|---|
| planning | default branch candidate priority needs fixed tests | design consultation | recorded in Q-001 and closure ids | tc-002 | no | `plan.md` |
| spec-authoring | candidate order / duplicate skip / next-candidate fallback needs locked tests | plan spec-reviewer | added `tc-008` and `tc-s02-008` | tc-008 | no | `plan.md` |

#### Workflow Delegation Consent
| consent source | repo/worktree | active issue | session | named roles | boundary | expires / invalidation condition | denied / unavailable reason | next action |
|---|---|---|---|---|---|---|---|---|
| user request 2026-05-22 | `/Users/iwasawayuuta/workspace/tools/pyclassuml` | iss-00036 | current session | spec-reviewer, later workflow roles in `plan.md` | spec authoring and review only; no implementation yet | scope change / session end | none | requirement / design / plan review and authoring |

### 2026-05-22 - Spec authoring gate

#### 対象
- Step: spec authoring only
- AC/EC: AC-001〜AC-005, EC-001〜EC-005
- Planned source:
  - `requirement.md`
  - `design.md`
  - `plan.md`
  - `report.md`

#### 実施内容
- 要件定義書を、no-base diff、explicit base 互換、initial commit object fallback、invalid explicit base failure、current-state / untracked / scope boundary の契約として再整理した。
- 設計書を、CLI / model / VCS / app / report の責務境界、resolved base metadata、候補順、default branch self 判定、fallback diagnostic まで含む実装可能な設計へ更新した。
- 実装計画書を、S01 CLI/model、S02 VCS resolver、S03 app/report integration、S90 docs、S99 final gates の execution contract として作成した。
- spec-reviewer の指摘に基づき、候補順と next-candidate fallback の closure、PR Delivery / Merge Preparation Gate、sync、post-commit clean check、report ledger destination を計画へ追加した。
- 実装は未着手。

#### Spec Authoring Review Gate
| artifact | reviewer | result | blocking findings resolved | final evidence |
|---|---|---|---|---|
| requirement.md | Zeno / spec-reviewer | pass | explicit base 互換、no-base と invalid ref の分離、resolved base observability、initial commit object fallback の明確化 | `review_status: pass`, findings empty |
| design.md | Einstein / spec-reviewer | pass | default branch self detection、structured metadata、model export、origin/HEAD precedence、slashful branch preservation、fallback diagnostic code/message | `review_status: pass`, findings empty |
| plan.md | Erdos / spec-reviewer | pass | candidate order / next-candidate coverage、PR Delivery / Merge Preparation Gate、sync、post-commit clean check | `review_status: pass`, remaining P2/P3 fixed |
| plan.md + report.md | Dewey / spec-reviewer | pass | PR Delivery Gate evidence routing、S90 closure ledger naming | `review_status: pass`, remaining P2 report placeholder fixed in this report |

#### Red/Green/Refactor Evidence
| step | phase | planned evidence requirement | observed evidence | command / inspection / manual record | result | notes |
|---|---|---|---|---|---|---|
| spec-authoring | inspect-only | requirement / design / plan reviewer pass | fresh spec-reviewer pass for each phase | subagent review records | pass | implementation not started |

#### Step Contract Closure
| closure id | status | evidence | notes |
|---|---|---|---|
| spec-authoring | pass | requirement / design / plan approved after spec-reviewer pass | runtime closure ids remain pending for implementation |

#### Test Contract Closure
| closure id | status | evidence | notes |
|---|---|---|---|
| tc-001〜tc-010 | pending | no runtime tests executed in spec authoring phase | to be closed by S01-S90 |

#### Closure Coverage
| area | status | evidence |
|---|---|---|
| requirement/design/plan readiness | pass | spec-reviewer passes recorded above |
| implementation closure | pending | S01-S99 not executed |

### 2026-05-22 - S01 CLI / model no-base contract

#### 対象
- Step: S01
- Closure id: tc-001
- 対象ファイル:
  - `src/pyclassuml/cli/bind.py`
  - `src/pyclassuml/model/contracts.py`
  - `src/pyclassuml/model/__init__.py`
  - `tests/cli/test_bind.py`
  - `tests/model/test_contracts.py`

#### Implementation Delegation Gate
| step | decision | delegated role | scope | allowed changes | forbidden changes | required verification | result |
|---|---|---|---|---|---|---|---|
| S01 | delegated | dev-coder | CLI / model no-base contract | S01 target files only | VCS resolver, app/report behavior, README, unrelated DTO changes | `uv run pytest tests/cli/test_bind.py tests/model/test_contracts.py` or environment-equivalent targeted pytest | pass |

#### Worker Result
| step | worker summary | changed files | verification result | unresolved risks | ledger note |
|---|---|---|---|---|---|
| S01 | `--base` optional bind、`DiffOptions.base_ref=None`、`DiffBaseResolution` DTO/export、`CommandResult.diff_base_resolution` を実装 | S01 target files | targeted pytest passed via `/private/tmp` uv cache workaround | VCS resolver / app-report / README remain S02+ | No material implementation decisions beyond the approved plan. |

#### Red/Green/Refactor Evidence
| step | phase | planned evidence requirement | observed evidence | command / inspection / manual record | result | notes |
|---|---|---|---|---|---|---|
| S01 | red | no-base bind / DTO export tests detect missing contract | test-first run failed with `ImportError: cannot import name 'DiffBaseResolution'` | `uv --cache-dir /private/tmp/uv-cache run --with pytest pytest tests/cli/test_bind.py tests/model/test_contracts.py` | pass | literal `uv run pytest ...` is blocked by uv cache permission on `/Volumes/990p2t/.cache/uv/sdists-v9/.git` |
| S01 | green | S01 targeted tests pass | 36 targeted tests passed | `uv --cache-dir /private/tmp/uv-cache run --with pytest pytest tests/cli/test_bind.py tests/model/test_contracts.py` | pass | parent re-run confirmed |
| S01 | static | whitespace / diff hygiene | no diff check errors | `git diff --check` | pass | parent re-run confirmed |
| S01 | refactor | bounded tidy after green | no additional tidy needed | worker inspection | pass | no unrelated model reshaping |

#### Step Contract Closure
| step | closure id | close condition | evidence | result |
|---|---|---|---|---|
| S01 | tc-001 | S01 targeted tests pass and code-reviewer passes | targeted pytest 36 passed; code-reviewer `review_status: pass` | pass |

#### Test Contract Closure
| closure id | step | evidence level | pre-implementation evidence | verification command | result |
|---|---|---|---|---|---|
| tc-001 | S01 | red-required | `DiffBaseResolution` import failure after test-first change | `uv --cache-dir /private/tmp/uv-cache run --with pytest pytest tests/cli/test_bind.py tests/model/test_contracts.py` | pass |

#### Closure Coverage
| closure id | locked expectation | covering tests | result |
|---|---|---|---|
| tc-001 | no-base diff is valid input and explicit base remains a non-empty string | `tests/cli/test_bind.py`, `tests/model/test_contracts.py` | pass |

#### Reviewer Gate Status
| gate name | reviewer role | freshness | state | evidence | risk acceptance |
|---|---|---|---|---|---|
| S01 step review | code-reviewer | fresh after S01 diff | passed | findings empty; `review_status: pass` | none |

#### Step Commit Gate
| step | review scope | step reviewer verdict | commit scope | closure state | commit evidence | post-commit clean check |
|---|---|---|---|---|---|---|
| S01 | S01 target files | code-reviewer pass | S01 implementation/tests plus report evidence | committed | `3010c1a` | `git status --short` clean after commit |

### 2026-05-22 - S02 VCS resolved-base resolver

#### 対象
- Step: S02
- Closure id: tc-002, tc-003, tc-004, tc-005, tc-006, tc-007, tc-008
- 対象ファイル:
  - `src/pyclassuml/vcs/diff_collect.py`
  - `tests/vcs/test_diff_file_collect.py`

#### Implementation Delegation Gate
| step | decision | delegated role | scope | allowed changes | forbidden changes | required verification | result |
|---|---|---|---|---|---|---|---|
| S02 | delegated | dev-coder | VCS resolved-base resolver | S02 target files only | CLI/model/report/docs changes, Git mutation commands, checkout-based implementation | `uv run pytest tests/vcs/test_diff_file_collect.py` or environment-equivalent targeted pytest | pass |

#### Worker Result
| step | worker summary | changed files | verification result | unresolved risks | ledger note |
|---|---|---|---|---|---|
| S02 | explicit/no-base resolved base、candidate order、default branch self、initial commit fallback、fallback diagnostic、no-commit failure を実装 | S02 target files | VCS targeted pytest passed via `/private/tmp` uv cache workaround | app/report transport remains S03 | No material implementation decisions beyond the approved plan. |

#### Red/Green/Refactor Evidence
| step | phase | planned evidence requirement | observed evidence | command / inspection / manual record | result | notes |
|---|---|---|---|---|---|---|
| S02 | red | temp Git repo tests for tc-002〜tc-008 detect missing resolver | test-first run failed with 7 failures and 26 passes | `uv --cache-dir /private/tmp/uv-cache run --with pytest pytest tests/vcs/test_diff_file_collect.py` | pass | failures included missing `base_resolution` and no-base `None` handling |
| S02 | green | S02 targeted tests pass | 33 targeted tests passed | `uv --cache-dir /private/tmp/uv-cache run --with pytest pytest tests/vcs/test_diff_file_collect.py` | pass | parent re-run confirmed |
| S02 | static | whitespace / diff hygiene | no diff check errors | `git diff --check` | pass | parent re-run confirmed |
| S02 | refactor | helper extraction stays inside `diff_collect.py` | resolver helpers kept in VCS module only | diff inspection | pass | no cross-module abstraction |

#### Step Contract Closure
| step | closure id | close condition | evidence | result |
|---|---|---|---|---|
| S02 | tc-002, tc-003, tc-004, tc-005, tc-006, tc-007, tc-008 | S02 targeted tests pass and code-reviewer passes | targeted pytest 33 passed; code-reviewer `review_status: pass` | pass |

#### Test Contract Closure
| closure id | step | evidence level | pre-implementation evidence | verification command | result |
|---|---|---|---|---|---|
| tc-002 | S02 | red-required | explicit-base tests failed before resolver update | `uv --cache-dir /private/tmp/uv-cache run --with pytest pytest tests/vcs/test_diff_file_collect.py` | pass |
| tc-003 | S02 | red-required | no-base merge-base test failed before resolver update | same as above | pass |
| tc-004 | S02 | red-required | initial fallback test failed before resolver update | same as above | pass |
| tc-005 | S02 | red-required | default branch self test failed before resolver update | same as above | pass |
| tc-006 | S02 | red-required | no-commit failure test failed before resolver update | same as above | pass |
| tc-007 | S02 | red-required | untracked/project-boundary no-base test failed before resolver update | same as above | pass |
| tc-008 | S02 | red-required | candidate precedence test failed before resolver update | same as above | pass |

#### Closure Coverage
| closure id | locked expectation | covering tests | result |
|---|---|---|---|
| tc-002 | explicit base uses provided ref and invalid explicit base never falls back | `test_explicit_base_sets_authoritative_base_resolution`, `test_invalid_explicit_base_does_not_fallback` | pass |
| tc-003 | no-base feature branch resolves default merge-base | `test_no_base_feature_branch_resolves_default_branch_merge_base` | pass |
| tc-004 | no usable candidate falls back to initial commit object with metadata | `test_no_base_without_usable_candidate_uses_initial_commit_fallback` | pass |
| tc-005 | current default branch skips probing and preserves slashful branch comparison | `test_no_base_current_slashful_default_branch_uses_initial_commit_fallback` | pass |
| tc-006 | no commit repository fails fast | `test_no_base_no_commit_repository_fails_fast` | pass |
| tc-007 | no-base preserves untracked and project/scope boundaries | `test_no_base_preserves_untracked_and_project_boundaries` | pass |
| tc-008 | candidate order skips missing/duplicate refs and continues after merge-base failure | `test_no_base_candidate_order_skips_missing_duplicates_and_merge_base_failures` | pass |

#### Reviewer Gate Status
| gate name | reviewer role | freshness | state | evidence | risk acceptance |
|---|---|---|---|---|---|
| S02 step review | code-reviewer | fresh after S02 diff | passed | findings empty; `review_status: pass` | none |

#### Step Commit Gate
| step | review scope | step reviewer verdict | commit scope | closure state | commit evidence | post-commit clean check |
|---|---|---|---|---|---|---|
| S02 | S02 target files | code-reviewer pass | S02 implementation/tests plus report evidence | committed | `a2f86ff` | `git status --short` clean after commit |

### 2026-05-22 - S03 App / report / CLI transcript integration

#### 対象
- Step: S03
- Closure id: tc-009
- 対象ファイル:
  - `src/pyclassuml/app/diff.py`
  - `src/pyclassuml/report/policy.py`
  - `tests/app/test_diff.py`
  - `tests/report/test_policy.py`
  - `tests/cli/test_main.py`

#### Implementation Delegation Gate
| step | decision | delegated role | scope | allowed changes | forbidden changes | required verification | result |
|---|---|---|---|---|---|---|---|
| S03 | delegated | dev-coder | app/report/CLI transcript integration | S03 target files only | VCS candidate order, DTO public contract drift, README | `uv run pytest tests/app/test_diff.py tests/report/test_policy.py tests/cli/test_main.py` or environment-equivalent targeted pytest | pass |

#### Worker Result
| step | worker summary | changed files | verification result | unresolved risks | ledger note |
|---|---|---|---|---|---|
| S03 | app base-side read を resolved base に切替え、ReportInputs / CommandResult / summary に base resolution metadata を transport | S03 target files | targeted app/report/CLI pytest passed via `/private/tmp` uv cache workaround | S90 README remains pending | No material implementation decisions beyond the approved plan. |

#### Red/Green/Refactor Evidence
| step | phase | planned evidence requirement | observed evidence | command / inspection / manual record | result | notes |
|---|---|---|---|---|---|---|
| S03 | red | app/report/CLI tests detect missing resolved-base transport | test-first run failed with 6 failures and 95 passes | `uv --cache-dir /private/tmp/uv-cache run --with pytest pytest tests/app/test_diff.py tests/report/test_policy.py tests/cli/test_main.py` | pass | failures included raw `base_ref=None` base blob read and missing report metadata |
| S03 | green | S03 targeted tests pass | 101 targeted tests passed | `uv --cache-dir /private/tmp/uv-cache run --with pytest pytest tests/app/test_diff.py tests/report/test_policy.py tests/cli/test_main.py` | pass | parent re-run confirmed |
| S03 | static | whitespace / diff hygiene | no diff check errors | `git diff --check` | pass | parent re-run confirmed |
| S03 | refactor | summary helper extraction allowed, exit policy unchanged | `_optional_summary_value` only | diff inspection | pass | VCS resolver policy unchanged |

#### Step Contract Closure
| step | closure id | close condition | evidence | result |
|---|---|---|---|---|
| S03 | tc-009 | S03 targeted tests pass and code-reviewer passes | targeted pytest 101 passed; code-reviewer `review_status: pass` | pass |

#### Test Contract Closure
| closure id | step | evidence level | pre-implementation evidence | verification command | result |
|---|---|---|---|---|---|
| tc-009 | S03 | red-required | app/report/CLI tests failed before resolved-base transport | `uv --cache-dir /private/tmp/uv-cache run --with pytest pytest tests/app/test_diff.py tests/report/test_policy.py tests/cli/test_main.py` | pass |

#### Closure Coverage
| closure id | locked expectation | covering tests | result |
|---|---|---|---|
| tc-009 | app uses resolved base everywhere and CommandResult/summary expose it | `test_no_base_diff_uses_resolved_base_for_classification_and_report`, report metadata tests, fallback degraded success tests, no-base head semantics tests, console transcript test | pass |

#### Reviewer Gate Status
| gate name | reviewer role | freshness | state | evidence | risk acceptance |
|---|---|---|---|---|---|
| S03 step review | code-reviewer | fresh after S03 diff | passed | findings empty; `review_status: pass` | none |

#### Step Commit Gate
| step | review scope | step reviewer verdict | commit scope | closure state | commit evidence | post-commit clean check |
|---|---|---|---|---|---|---|
| S03 | S03 target files | code-reviewer pass | S03 implementation/tests plus report evidence | committed | `9256f36` | `git status --short` clean after commit |

### 2026-05-22 - S90 Docs impact resolution / docs refresh

#### 対象
- Step: S90
- Closure id: tc-010
- 対象ファイル:
  - `README.md`

#### Implementation Delegation Gate
| step | decision | delegated role | scope | allowed changes | forbidden changes | required verification | result |
|---|---|---|---|---|---|---|---|
| S90 | delegated | doc-writer | README diff command contract | `README.md` only | source code, tests, spec workflow docs | README inspection and `./spec-dock/scripts/spec-dock validate` | pass |

#### Worker Result
| step | worker summary | changed files | verification result | unresolved risks | ledger note |
|---|---|---|---|---|---|
| S90 | README の diff usage を optional base 形式へ更新し、no-base resolution、explicit-base compatibility、fallback、summary fields を説明 | `README.md` | `git diff --check` passed; parent `spec-dock validate` passed | none | No material implementation decisions beyond the approved plan. |

#### Red/Green/Refactor Evidence
| step | phase | planned evidence requirement | observed evidence | command / inspection / manual record | result | notes |
|---|---|---|---|---|---|---|
| S90 | inspect | README documents no-base behavior and summary fields | README diff inspected by parent and spec-reviewer | `git diff -- README.md` | pass | content aligned with S01-S03 behavior |
| S90 | validate | SpecDock docs validation | validation succeeded | `./spec-dock/scripts/spec-dock validate` | pass | `nodes=36` |
| S90 | static | whitespace / diff hygiene | no diff check errors | `git diff --check` | pass | parent re-run confirmed |

#### Step Contract Closure
| step | closure id | close condition | evidence | result |
|---|---|---|---|---|
| S90 | tc-010 | README updated and spec-reviewer passes | README diff inspection; `spec-dock validate`; spec-reviewer `review_status: pass` | pass |

#### Test Contract Closure
| closure id | step | evidence level | pre-implementation evidence | verification command | result |
|---|---|---|---|---|---|
| tc-010 | S90 | inspect-only | README previously documented `--base` as required | README inspection and `./spec-dock/scripts/spec-dock validate` | pass |

#### Closure Coverage
| closure id | locked expectation | covering evidence | result |
|---|---|---|---|
| tc-010 | README documents no-base behavior, explicit-base compatibility, fallback, and summary fields | README diff plus spec-reviewer pass | pass |

#### Reviewer Gate Status
| gate name | reviewer role | freshness | state | evidence | risk acceptance |
|---|---|---|---|---|---|
| S90 docs/spec review | spec-reviewer | fresh after README diff | passed | README content aligned; remaining P2 validate evidence fixed in this report | none |

#### Step Commit Gate
| step | review scope | step reviewer verdict | commit scope | closure state | commit evidence | post-commit clean check |
|---|---|---|---|---|---|---|
| S90 | README docs | spec-reviewer pass | README plus report evidence | pending commit | pending | pending |

## Final Quality Gate (必須)

### S90 Docs Impact Resolution
| target | update required | owner | evidence | spec-reviewer result |
|---|---|---|---|---|
| README | yes | doc-writer | README updated; `./spec-dock/scripts/spec-dock validate` pass | pass |

### Final QA Gate
| reviewer | scope | integration test decision | evidence | result |
|---|---|---|---|---|
| qa-reviewer | whole issue obligation coverage | pending | pending | pending |

### Final Code Review Gate
| reviewer | scope | evidence | result |
|---|---|---|---|
| code-reviewer | issue-wide integrated diff | pending | pending |

### Final Spec Review Gate
| reviewer | scope | evidence | result |
|---|---|---|---|
| spec-reviewer | requirement / design / plan / report consistency | pending | pending |

### Final Commit Gate
| scope | evidence | result |
|---|---|---|
| issue implementation, tests, docs, report | pending | pending |

### PR Delivery Gate
| pr url | selected base | base-resolution source | conflict handling | draft/ready decision | head branch | head sha | issue linkage | push result | existing/new PR decision | result |
|---|---|---|---|---|---|---|---|---|---|---|
| pending | pending | pending | pending | pending | pending | pending | #36 | pending | pending | pending |

### Merge Preparation Gate
| pr url | checks | codex review | open review comments | unresolved blockers | result |
|---|---|---|---|---|---|
| pending | pending | pending | pending | pending | pending |
