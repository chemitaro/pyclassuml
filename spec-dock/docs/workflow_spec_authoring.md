# workflow: spec authoring

Initiative / Epic / Issue の requirement / design / plan を作成・更新する共通 workflow です。
scope 固有の lifecycle / governance は `workflow_initiative.md` / `workflow_epic.md` / `workflow_issue.md` が所有し、この文書は仕様書作成そのものの phase promotion gate を正本として扱います。

関連:
- 総合: [guide.md](guide.md)
- Scope workflow: [workflow_initiative.md](workflow_initiative.md), [workflow_epic.md](workflow_epic.md), [workflow_issue.md](workflow_issue.md)
- Phase playbook: [phase_requirement.md](phase_requirement.md), [phase_design.md](phase_design.md), [phase_plan.md](phase_plan.md)

## 基本契約

- 仕様書作成は `requirement -> spec-reviewer pass -> design -> spec-reviewer pass -> plan -> spec-reviewer pass -> downstream handoff` の順に進める。
- 各 phase promotion は fresh `spec-reviewer` の `review_status: pass` を必須にする。
- `spec-reviewer` が `fail` を返した場合は指摘を修正し、同じ reviewer 状態を再利用せず fresh `spec-reviewer` で再レビューする。
- phase gate verdict は `passed` / `failed` / `unavailable` / `denied` / `waived` / `provisional` のいずれかで記録する。自動 promotion を許可するのは fresh `passed` だけである。
- `waived` は、ユーザーが明示的に risk acceptance を与え、その内容と対象 scope が `report.md` に残っている場合だけ使える。`waived` を reviewer pass と表現してはならない。
- `provisional` は orchestrator self-check の記録であり、`spec-reviewer` の代替ではない。
- reviewer が missing / stale / failed / unavailable / denied / waived / provisional の場合は、phase promotion を block または incomplete として扱う。degraded mode を reviewer gate の degraded success として扱ってはならない。
- 調査で解消できる不明点をユーザー質問で代替しない。先に docs / code / ADR / discussions / 外部一次情報を確認する。
- 調査後もユーザー意図、受け入れ条件、スコープ、非スコープ、優先順位に影響する未確定事項が残る場合は、次 phase へ進む前にユーザーへヒアリングする。
- scope / non-scope に影響する未確認事項が残る場合は `blocked` または `incomplete` として扱い、次 phase へ進めない。

## workflow-scoped delegation consent

- Issue scope の spec authoring では、reviewer / read-only specialist sub-agent を使う前に、current repo/worktree、active issue、session、named role に限定した issue-scoped workflow delegation consent を確認し、`report.md` に記録する。
- 現在のユーザー指示が「この issue workflow 内では reviewer / specialist を自律利用してよい」と明示している場合、その指示を同一 issue / repo / session / named role に限定した consent として扱える。
- consent がある場合、orchestrator は requirement / design / plan の各 phase ごとに再確認せず、必要な `spec-reviewer` や read-only specialist を起動してよい。
- consent は destructive action、external publishing、credentialed access、scope expansion、write-capable delegation、named role 以外の delegation を許可しない。scope が変わる場合は再確認する。

## authoring lifecycle

1. 対象 scope と既存 node を確認する。
2. 対象 artifact に対応する `docs/authoring/<scope>-<phase>.md` がある場合は最初に読む。
3. 対象 scope の `workflow_*.md` と phase playbook を読む。
4. 調査結果、仮説、選択肢、質問を必要に応じて `discussions/` に分離する。
5. 対象 artifact を更新する。
6. fresh `spec-reviewer` を起動し、対象 artifact と upstream artifact を review する。
7. `fail` なら修正し、fresh `spec-reviewer` で再レビューする。
8. `pass` なら `report.md` に gate evidence を残し、次 phase へ進む。

## requirement gate

- As-Is、制約、user intent、scope、non-scope、acceptance criteria、edge cases を一次情報またはヒアリングで固定する。
- `WHAT / WHY / scope / success` を固定し、HOW は design へ送る。
- ユーザー意図、受け入れ条件、scope / non-scope に関わる TBD が残る場合、design へ進めない。
- `spec-reviewer` は requirement 単体と、必要な upstream initiative / epic / discussion / ADR との整合を確認する。

## design gate

- reviewer-pass 済み requirement を前提にする。
- 既存実装、既存 docs、ADR、依存、責務境界、互換性、移行、テスト戦略を確認する。
- requirement 不足が判明した場合は design で補わず、requirement へ戻して修正し、requirement gate を再実行する。
- `spec-reviewer` は design と requirement の traceability、責務境界、失敗設計、未解決論点の有無を確認する。

## plan gate

- reviewer-pass 済み requirement / design を前提にする。
- 分解、順序、依存、検証、review gate、完了条件、downstream handoff を固定する。
- 未解決設計論点や未承認 requirement を plan に先送りしない。
- Issue plan は `docs/authoring/issue-plan.md` の concrete test case contract に従い、各 implementation step に step-local な `具体テストケース一覧` を置く。
- `spec-reviewer` は plan が requirement / design と矛盾せず、次工程へ安全に渡せることを確認する。

## downstream handoff

- Initiative は plan gate pass 後に Epic 分解へ進む。
- Epic は plan gate pass 後に Issue 分割へ進む。
- Issue は plan gate pass 後に `workflow_issue.md` の execution contract へ進む。
- downstream で requirement / design / plan の不足が見つかった場合は、該当 phase へ戻して修正し、promotion gate を再実行する。

## report evidence contract

対象 scope の `report.md` に `Spec Authoring Gate` を置き、phase ごとに次を残す。

- phase: `requirement` / `design` / `plan`
- investigated facts: 確認した docs / code / ADR / discussions / 外部一次情報
- open questions: 未確定事項、ユーザー質問、回答
- delegation consent: scope、named roles、source、boundary、expires / invalidation condition
- reviewer: fresh `spec-reviewer` の実行単位と review scope
- verdict: `passed` / `failed` / `unavailable` / `denied` / `waived` / `provisional` と理由。`passed` 以外は reviewer gate pass ではない
- fixes: 指摘に対する修正要約
- promotion: 次 phase へ進めるか、`blocked` / `incomplete` の reason と next action

長い調査、比較、ヒアリング transcript は `discussions/` に分離してよい。ただし `report.md` には判断に必要な要約と参照を残す。
