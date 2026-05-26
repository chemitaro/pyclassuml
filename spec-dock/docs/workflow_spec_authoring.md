# 仕様 authoring ワークフロー（workflow: spec authoring）

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

## 権限境界（Authority boundary / Promotion Record）

Canonical `requirement.md` / `design.md` / `plan.md` / `report.md` は main orchestrator の single-writer authority です。Sub-agent は canonical docs を直接編集しません。Sub-agent が作る authoring output は、対象 initiative / epic / issue の scope-local `discussions/` 直下に置く flat Markdown draft / analysis / discussion-local report です。

Discussion output filenames follow existing discussion rules:

- `<ts>-<kind>-<slug>.md`
- `<ts>-<nn>-<kind>-<slug>.md` for same-second collisions

Sub-agent-created draft は最低限、`created_by_role`、`scope_id`、`source_paths`、`intended_targets`、`adoption_status: unreviewed`、`reflected_to: []`、`diff_guard_result`、fallback decision、report evidence destination、adoption ledger note を持ちます。Evidence Adoption Ledger fields は ID、adoption_status、source、source_role、claim、target_artifact、target_section、rationale、evidence_strength、evidence_path、adopter、reviewer、blocking、next_action を標準にします。標準 delegated draft evidence として task manifest hash、Permission Profile hash、session invocation hash、probe run id、session hash を要求しません。これらは historical evidence または明示された例外証跡としてだけ扱います。
権限や採用可否の wildcard 指定は使いません。`*`、`grants.*`、`all` は invalid wildcard token として扱い、scope-local discussion direct-write の根拠にしてはなりません。

Sub-agent-created draft は `authority: accepted`、`adoption_status: adopted`、non-empty `reflected_to`、reviewer pass、phase completion、implementation readiness を自己主張してはなりません。`reflected_to` は実際に canonical artifact へ反映済みの対象だけを表し、予定先は `intended_targets` で表します。

Accepted ADR は architecture decision authority を持ち得ますが、discussion draft / research / disc は evidence です。Implementation readiness、phase promotion、issue ready、issue finish、phase completion は、main orchestrator が evidence を canonical docs と `report.md` に再記述し、required reviewer gates が pass した後に成立します。

Promotion Record は delegated draft や reviewer output を canonical authority に昇格した事実だけを記録します。canonical artifact promotion の `promotion_record` は少なくとも `status`, `authority`, `owner_role`, `draft_author_role`, `approval`, `source_revision`, `approved_revision`, `approved_hash`, `reviewer_target_hash`, `promoted_at`, `promoted_by`, `promotion_decision` を持ちます。runtime active selection の promotion record は lifecycle gate 用の最小 record として `status`, `authority`, `source_revision`, `approved_revision`, `approved_hash`, `reviewer_target_hash`, `promotion_decision` を持ち、`source_revision` / `approved_revision` / `approved_hash` / `reviewer_target_hash` は active entry id に対応する `active:<id>` と一致している必要があります。`reviewer_target_hash` と `approved_hash` が一致しない場合、`source_revision` / `approved_revision` が一致しない場合、または active entry id と promotion record が一致しない場合、その promotion は invalid であり downstream authority には使えません。Mismatch / stale を発見した場合は report に reason と next action を残し、fresh reviewer gate と Promotion Record の再作成まで block します。

Active manifest と context-pack は同じ authority/grant 状態を示す必要があります。`spec-dock/.agent/active.json` の issue entry が `authority=proposed`、authority metadata 欠落、stale promotion record、または required exact grant 不足の場合、implementation start、issue ready、issue finish、phase completion の lifecycle handoff は blocked / incomplete とします。`spec-dock/active/context-pack.md` は人間向け guidance ですが、authority source は `spec-dock/.agent/active.json` です。

## ワークフロー単位の委任同意（workflow-scoped delegation consent）

- Issue scope の spec authoring では、reviewer / read-only specialist sub-agent を使う前に、current repo/worktree、active issue、session、named role に限定した issue-scoped workflow delegation consent を確認し、`report.md` に記録する。
- 現在のユーザー指示が「この issue workflow 内では reviewer / specialist を自律利用してよい」と明示している場合、その指示を同一 issue / repo / session / named role に限定した consent として扱える。
- consent がある場合、orchestrator は requirement / design / plan の各 phase ごとに再確認せず、必要な `spec-reviewer` や read-only specialist を起動してよい。
- consent は destructive action、external publishing、credentialed access、scope expansion、named role 以外の delegation、または canonical docs への直接 write を許可しない。scope が変わる場合は再確認する。
- read-only specialist consent と scope-local discussion direct-write consent は別物として扱う。Sub-agent authoring output は proposal-only に限定しないが、許可される write は対象 scope `discussions/` direct child の flat Markdown draft / analysis / discussion-local report に限る。
- scope-local discussion direct-write consent は、target node、role、source artifacts、allowed discussion path rule、forbidden canonical/implementation paths、post-run diff guard、report ledger destination を明示した task-local consent として別途記録する。workflow-wide blanket consent、manual/unprofiled broad write、static broad profile、または Desktop-only fallback は adoption-ready delegated output に数えない。

## 委任 authoring policy foundation（delegated authoring policy foundation）

- Main orchestrator は canonical `requirement.md` / `design.md` / `plan.md` / `report.md` の最終 ownership、user dialogue、canonical integration、Evidence Adoption Ledger、Promotion Record、phase promotion を所有する。
- Delegated authoring は scope-local flat `discussions/` evidence であり、final canonical authority ではない。delegated output は main orchestrator が採否を判断し、fresh `spec-reviewer` が canonical artifact を pass して初めて phase promotion の根拠にできる。
- Delegated authoring を使う場合は、invocation ごとに node、role、scope、source artifacts、allowed discussion path rule、forbidden actions、output expectation、stop / invalidation condition を明示し、`report.md` に残す。workflow-wide blanket consent は direct-write authoring delegation の根拠にしない。
- Delegated role は対象 scope `discussions/` direct child の naming-rule compliant Markdown だけを作成できる。既存 discussion file の編集は main orchestrator が明示指定した proposed draft に限定する。
- Delegated role は previous phase artifact、implementation code、tests、package/config、GitHub state、reviewer result を編集・確定・上書きしてはならない。destructive action、external publishing、credentialed access、`.github/agents` / Copilot support はこの workflow の delegated authoring policy では許可しない。
- Delegated draft が unavailable / skipped / blocked / stale / rejected / superseded の場合でも、manual authoring path は有効である。ただし delegated authoring を使った evidence として扱ってはならない。
- Delegated draft は fresh `spec-reviewer` pass の代替ではない。`spec-reviewer` は draft 自体ではなく、main orchestrator が統合した canonical artifact と evidence を review する。

## 委任ドラフト証跡 schema（delegated draft evidence schema）

- Delegated draft lifecycle state は `requested` / `produced` / `integrated` / `partially_integrated` / `rejected` / `superseded` / `blocked` / `stale` のいずれかで記録する。
- `stale`、`rejected`、`superseded`、`blocked` の delegated draft は promotion evidence に使えない。`partially_integrated` は採用部分、rejected portions、blockers、promotion decision を `report.md` に明示した場合だけ採用部分の補助 evidence にできる。
- Delegated draft evidence record は少なくとも `created_by_role`、scope、source artifacts、draft artifact path、intended targets、`adoption_status: unreviewed`、`reflected_to: []`、diff guard result、integration result、rejected portions、blockers、reviewer result、promotion decision を持つ。
- `source_snapshot` を記録する場合は source revision、reviewer pass reference、generated_at、stale_if を含める。
- Failure-mode record は expected verdict、allowed next action、report evidence path、promotion eligibility を持つ。
- Required failure modes は missing consent、missing/stale previous reviewer pass、requirement gap during design、design gap during plan、role unavailable、forbidden action attempt、stale draft、superseded draft、missing draft evidence when delegated use is claimed、reviewer unavailable/denied/waived/provisional を含む。
- Delegated draft evidence を使った場合、対象 scope の `report.md` は delegated draft evidence table と failure-mode table を持つ。使わなかった場合は manual authoring / not used として、promotion evidence に delegated draft を使っていないことを短く記録する。

## 証跡採用台帳（Evidence Adoption Ledger）

Delegated draft、worker note、research、reviewer finding、外部調査結果などの証跡を canonical artifact や実装判断へ取り込む場合、`report.md` に Evidence Adoption Ledger を残します。この台帳は raw transcript ではなく、orchestrator が検証した採否判断を記録します。

- `adoption_status`: `adopted` / `partially_adopted` / `rejected` / `deferred` / `stale` / `blocked`
- `source`: evidence の出所（sub-agent、reviewer、discussion、command、external research など）
- `target`: 採用先または影響先 artifact / issue / follow-up
- `rationale`: 採用・部分採用・却下・延期・stale・blocked の理由
- `evidence`: diff、command、reviewer finding、discussion path など検証可能な証跡
- `next_action`: follow-up、再調査、再レビュー、または対応不要の理由

`blocked` または `stale` の entry が未解決のまま残っている場合、phase promotion、implementation start、issue ready、issue finish、phase completion に進めません。`deferred` は blocking でない根拠と revisit 条件を持つ場合だけ完了時に残せます。Evidence Adoption Ledger を使わずに delegated evidence の採用を主張してはなりません。

## 深さ2までの委任（Bounded Depth=2 Delegation）

Main orchestrator が canonical artifact と final reviewer gate を所有します。System architect や implementation planner などの authoring specialist は、depth=2 の範囲で leaf-only evidence producer を呼び出せます。leaf-only evidence producer は repo analysis、research、consultation、QA-style evidence などの補助証跡を返すだけで、さらに子エージェントを呼び出して depth=3 / grandchild delegation を作ってはなりません。

- allowed depth=2: main orchestrator -> authoring specialist -> leaf-only evidence producer
- forbidden depth=3: main orchestrator -> authoring specialist -> leaf producer -> grandchild
- authoring specialist と leaf-only evidence producer は、scope-local `discussions/` direct child の flat Markdown evidence 作成以外の canonical edit、implementation edit、phase promotion、reviewer-pass claim、final authority、issue ready / issue finish claim を行わない。leaf-only evidence producer は常に canonical edit を行わない
- preflight reviewer output は設計・計画の改善 input として扱い、final fresh reviewer pass とは分離する
- reviewer independence: final `spec-reviewer` / `code-reviewer` / `qa-reviewer` は、同じ artifact を作成した authoring specialist や leaf-only evidence producer の代替ではない fresh gate として実行する

## Scope-local discussion write gate

System architect / implementation planner の static adapter は、scope-local `discussions/` Markdown draft だけに write-capable な delegated authoring surface です。broad write や canonical target write を許可してはなりません。Run ごとの permission context 生成は標準経路にせず、post-run diff guard pass と canonical `report.md` の ledger entry 記録まで adoption-ineligible として扱います。

Allowed delegated output は target scope `discussions/` direct-child Markdown files に限定し、filename は `<ts>-<kind>-<slug>.md` または `<ts>-<nn>-<kind>-<slug>.md` に一致させます。既存 discussion update は explicit orchestrator allowlist を必須にし、accepted ADR、superseded、stale、rejected、adopted evidence ではなく proposed draft だけを対象にします。`--baseline-status` を使う場合も target scope `discussions/` は run 開始時点で clean にし、baseline に target discussion subtree の dirty/untracked entry がある delegated output は adoption-ineligible とします。pre-existing non-target dirtiness は repo 外に生成した `delegated-authoring baseline-status --output <path>` の file-state snapshot が current file content and mode と一致する場合に限り delegated output diff から除外できます。baseline entry が current status から消えた場合は、delegated run 中の non-target 変更として fail-closed に扱います。

Forbidden output は canonical docs、implementation files、tests、package/config、`.agents`、`.codex`、`.github`、`.env*`、nested discussion directories、symlinks、non-Markdown files、deletes、renames、copied paths、out-of-scope discussions、mixed staged/unstaged discussion states、unmerged discussion states を含みます。

Historical `iss-00126` task manifest / Permission Profile / probe / session artifacts は grandfathered evidence です。current standard が manifest-heavy success path を使わなくなったことだけを理由に削除、rename、validation failure 化してはなりません。

| 失敗モード | 期待される判定 | 許可される次アクション | report 証跡の記録先 | 昇格可否 |
|---|---|---|---|---|
| missing consent（同意欠落） | blocked / incomplete | obtain scoped consent or use manual authoring（scope 付き同意を取得する、または手動 authoring を使う） | Delegated Draft Evidence | ineligible |
| missing/stale previous reviewer pass（前段 reviewer pass の欠落 / stale） | blocked / incomplete | rerun reviewer gate（reviewer gate を再実行する） | Spec Authoring Gate / reviewer evidence | ineligible |
| requirement gap during design（design 中の requirement gap） | blocked / incomplete | return to requirement phase（requirement phase に戻す） | decision ledger / gate evidence | ineligible |
| design gap during plan（plan 中の design gap） | blocked / incomplete | return to design phase（design phase に戻す） | decision ledger / gate evidence | ineligible |
| role unavailable（role 利用不可） | blocked / manual path | record unavailable and continue manually if valid（利用不可を記録し、妥当なら手動で継続する） | Delegated Draft Evidence | ineligible |
| forbidden action attempt（禁止アクションの試行） | rejected | discard draft and record incident（draft を破棄し、incident を記録する） | Delegated Draft Evidence / decision ledger | ineligible |
| stale draft（stale な draft） | stale | regenerate or reconcile（再生成または整合する） | Delegated Draft Evidence | ineligible |
| superseded draft（置換済み draft） | superseded | reference replacement draft（置換後 draft を参照する） | Delegated Draft Evidence | ineligible |
| missing draft evidence when delegated use is claimed（委任利用を主張しているが draft 証跡が欠落） | incomplete | add evidence or remove delegated-use claim（証跡を追加する、または委任利用 claim を削除する） | Delegated Draft Evidence | ineligible |
| reviewer unavailable/denied/waived/provisional（reviewer 利用不可 / denied / waived / provisional） | blocked / incomplete | obtain fresh passed reviewer or record risk acceptance without promotion（fresh passed reviewer を取得する、または昇格なしの risk acceptance を記録する） | reviewer gate evidence | ineligible |

## 作成のライフサイクル（authoring lifecycle）

1. 対象 scope と既存 node を確認する。
2. 対象 artifact に対応する `docs/authoring/<scope>-<phase>.md` がある場合は最初に読む。
3. 対象 scope の `workflow_*.md` と phase playbook を読む。
4. 調査結果、仮説、選択肢、質問を必要に応じて `discussions/` に分離する。raw capture は `scratch`、人間への質問は `interview`、事実調査は `research`、論点整理は `disc`、長期判断は `adr` を使う。
5. 対象 artifact を更新する。
6. fresh `spec-reviewer` を起動し、対象 artifact と upstream artifact を review する。
7. `fail` なら修正し、fresh `spec-reviewer` で再レビューする。
8. `pass` なら `report.md` に gate evidence を残し、次 phase へ進む。

## 要件ゲート（requirement gate）

- As-Is、制約、user intent、scope、non-scope、acceptance criteria、edge cases を一次情報またはヒアリングで固定する。
- `何を / なぜ / スコープ / 成功条件（WHAT / WHY / scope / success）` を固定し、`どう実現するか（HOW）` は design へ送る。
- ユーザー意図、受け入れ条件、scope / non-scope に関わる TBD が残る場合、design へ進めない。
- `spec-reviewer` は requirement 単体と、必要な upstream initiative / epic / discussion / ADR との整合を確認する。

## 設計ゲート（design gate）

- reviewer-pass 済み requirement を前提にする。
- 既存実装、既存 docs、ADR、依存、責務境界、互換性、移行、テスト戦略を確認する。
- requirement 不足が判明した場合は design で補わず、requirement へ戻して修正し、requirement gate を再実行する。
- `spec-reviewer` は design と requirement の traceability、責務境界、失敗設計、未解決論点の有無を確認する。

## 計画ゲート（plan gate）

- reviewer-pass 済み requirement / design を前提にする。
- 分解、順序、依存、検証、review gate、完了条件、downstream handoff を固定する。
- 未解決設計論点や未承認 requirement を plan に先送りしない。
- Issue plan は `docs/authoring/issue-plan.md` の concrete test case contract に従い、各 implementation step に step-local な `具体テストケース一覧` を置く。
- `spec-reviewer` は plan が requirement / design と矛盾せず、次工程へ安全に渡せることを確認する。

## 下流引き渡し（downstream handoff）

- Initiative は plan gate pass 後に Epic 分解へ進む。
- Epic は plan gate pass 後に Issue 分割へ進む。
- Issue は plan gate pass 後に `workflow_issue.md` の execution contract へ進む。
- downstream で requirement / design / plan の不足が見つかった場合は、該当 phase へ戻して修正し、promotion gate を再実行する。

## 報告の証跡契約（report evidence contract）

対象 scope の `report.md` に `Spec Authoring Gate` を置き、phase ごとに次を残す。

- phase: `requirement` / `design` / `plan`
- investigated facts: 確認した docs / code / ADR / discussions / 外部一次情報
- open questions: 未確定事項、ユーザー質問、回答
- delegation consent: scope、named roles、source、boundary、expires / invalidation condition
- reviewer: fresh `spec-reviewer` の実行単位と review scope
- verdict: `passed` / `failed` / `unavailable` / `denied` / `waived` / `provisional` と理由。`passed` 以外は reviewer gate pass ではない
- fixes: 指摘に対する修正要約
- promotion: 次 phase へ進めるか、`blocked` / `incomplete` の reason と next action

長い調査、比較、ヒアリング transcript は `discussions/` に分離してよい。ただし `report.md` には判断に必要な要約と参照を残す。discussion docs は未確定情報の作業面なので、確定させる内容は新しい `adr`、または `requirement.md` / `design.md` / `plan.md` へ反映する。
