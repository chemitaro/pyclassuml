---
種別: 実装報告書（Issue）
ID: "iss-00036"
タイトル: "Diff Default Branch Base"
関連GitHub: ["#36"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-21"
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

#### Workflow Delegation Consent
| consent source | repo/worktree | active issue | session | named roles | boundary | expires / invalidation condition | denied / unavailable reason | next action |
|---|---|---|---|---|---|---|---|---|
| none for implementation | `/Users/iwasawayuuta/workspace/tools/pyclassuml` | iss-00036 after start | current session | N/A | planning only | scope change / session end | none | issue start |

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
