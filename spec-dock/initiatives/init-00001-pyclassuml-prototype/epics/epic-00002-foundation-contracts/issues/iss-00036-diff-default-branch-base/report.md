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
- 未実装。
- この report は issue 作成時点の仕様判断と、今後の実装 evidence 保存先を初期化する。

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

## Final Quality Gate (必須)

### S90 Docs Impact Resolution
| target | update required | owner | evidence | spec-reviewer result |
|---|---|---|---|---|
| README / config reference if needed | yes | TBD during implementation | pending | pending |

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
