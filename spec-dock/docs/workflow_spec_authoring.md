# 仕様 authoring ワークフロー（workflow: spec authoring）

Initiative / Epic / Issue の requirement / design / plan を作成・更新する共通 workflow です。
Operational entrypoint / first-read spine は `spec-dock-initiative-planning`、`spec-dock-epic-planning`、`spec-dock-issue-planning` などの planning skill が所有します。
scope 固有の lifecycle / governance は `workflow_initiative.md` / `workflow_epic.md` / `workflow_issue.md` が detail / reference semantics を持ち、この文書は仕様書作成そのものの phase promotion gate、delegated evidence、hard cases の詳細参照として扱います。

関連:
- 総合: [guide.md](guide.md)
- Scope workflow: [workflow_initiative.md](workflow_initiative.md), [workflow_epic.md](workflow_epic.md), [workflow_issue.md](workflow_issue.md)
- ChatGPT evidence lane: [workflow_chatgpt_authoring_pack.md](workflow_chatgpt_authoring_pack.md)
- Phase playbook: [phase_requirement.md](phase_requirement.md), [phase_design.md](phase_design.md), [phase_plan.md](phase_plan.md)
- Decision routing: [authoring/decision-routing.md](authoring/decision-routing.md)
- Scope layering: [authoring/scope-layering.md](authoring/scope-layering.md)
- Clarification workflow: [workflow_clarification.md](workflow_clarification.md)

## 基本契約

- 仕様書作成は `requirement -> spec-reviewer pass -> design -> spec-reviewer pass -> plan -> spec-reviewer pass -> downstream handoff` の順に進める。
- 各 phase promotion は fresh `spec-reviewer` の `review_status: pass` を必須にする。
- `spec-reviewer` が `fail` を返した場合は指摘を修正し、同じ reviewer 状態を再利用せず fresh `spec-reviewer` で再レビューする。
- phase gate verdict は `passed` / `failed` / `unavailable` / `denied` / `waived` / `provisional` のいずれかで記録する。自動 promotion を許可するのは fresh `passed` だけである。
- `waived` は、ユーザーが明示的に risk acceptance を与え、その内容と対象 scope が `report.md` に残っている場合だけ使える。`waived` を reviewer pass と表現してはならない。
- `provisional` は orchestrator self-check の記録であり、`spec-reviewer` の代替ではない。
- reviewer が missing / stale / failed / unavailable / denied / waived / provisional の場合は、phase promotion を block または incomplete として扱う。degraded mode を reviewer gate の degraded success として扱ってはならない。
- 調査で解消できる不明点をユーザー質問で代替しない。先に docs / code / ADR / discussions / 外部一次情報を確認する。
- 調査後もユーザー意図、受け入れ条件、スコープ、非スコープ、優先順位に影響する未確定事項が残る場合は、[workflow_clarification.md](workflow_clarification.md) に従い、次 phase へ進む前に orchestrator が一問ずつヒアリングする。
- scope / non-scope に影響する未確認事項が残る場合は `blocked` または `incomplete` として扱い、次 phase へ進めない。
- authoring 中に Decision-only finding を見つけた場合は、execution handoff 前に [authoring/scope-layering.md](authoring/scope-layering.md) と [authoring/decision-routing.md](authoring/decision-routing.md) で placement を確認する。Issue-local なら対象 Issue に閉じ、cross-issue なら Epic、cross-epic / investment なら Initiative、long-lived architecture decision なら ADR 候補、判断材料不足なら clarification へ戻す。routing 判断は canonical artifact または `report.md` の evidence に残し、template や skill に長い例を複製しない。
- ChatGPT / Oracle を使う場合は [workflow_chatgpt_authoring_pack.md](workflow_chatgpt_authoring_pack.md) を参照し、external preserved evidence、delegated draft evidence、ZIP/tree staged evidence を独立した lane として扱う。ZIP/tree/staged evidence、candidate validation、draft adoption validation、approval check の `pass` は command-local pass であり、canonical adoption、fresh reviewer pass、execution-ready、PR-ready ではない。
- ChatGPT output の受領後は、採否判断や canonical rewrite より先に preservation checkpoint を実行する。main orchestrator は output form と semantic completeness を分類し、該当する保存または既存 ZIP/tree lane の証跡を確認してから Evidence Adoption Ledger に採否を記録する。完全な source が存在するのに保存が未完了、失敗、receipt 不明、または未分類なら次工程を block し、source unavailable として迂回しない。
- ChatGPT evidence を採用する場合は、Evidence Adoption Ledger に採否を記録し、main orchestrator が canonical docs へ再記述し、fresh `spec-reviewer` pass を通す。順序は `output received -> preservation checkpoint -> EAL disposition -> canonical rewrite -> fresh reviewer` である。
- ChatGPT-first planning route is the normal route for non-trivial Initiative / Epic / Issue planning. Browser tab capacity、retryable timeout、stale sync、fixable backend setup は wait / retry / recover の対象であり、manual route へ自動 fallback しない。
- Manual route is a human-approved emergency backup only. `spec-dock-initiative-planning-manual`、`spec-dock-epic-planning-manual`、`spec-dock-issue-planning-manual` は hard / unrecoverable failure と explicit human approval、failure evidence、recovery attempts、fresh reviewer gate を必要とする。

## グレード別authoring matrix（Issue grade authoring matrix）

Issue の `authorized_profile` は runtime template、guidance、authoring obligation の authority です。manual escalation は reviewer / specialist / evidence gate を強める運用判断であり、`authorized_profile` を上書きする authority ではありません。manual escalation を使った場合は、理由、追加した gate、`authorized_profile` との差分、戻し条件を `report.md` の `Spec Authoring Gate` に残します。

Lite は automatic default ではありません。Issue が小さく、低リスクで、既存 contract / scaffold / runtime / user-facing behavior への影響が限定されることを明示できる場合だけ Lite として扱えます。grade が unknown / ambiguous、または影響範囲や reviewer obligation を判断できない場合は Standard 以上に倒し、Lite として進めてはなりません。

| グレード（Grade） | 要件（Requirement） | 設計（Design） | 計画（Plan） | レビュー / 報告証跡（Review / report evidence） |
|---|---|---|---|---|
| `lite` | 目的、scope / non-scope、AC / EC、低リスク根拠を短く固定する。Lite 採用理由を明示する。 | 既存 pattern の再利用と変更境界を示す。新規 architecture 判断、runtime contract、scaffold API 変更が出たら Standard 以上へ上げる。 | 軽量確認（docs-only / inspect-only）なら軽量 step でよい。途中 commit 候補や三者 gate を必須化しないが、完了条件と代替 evidence を置く。 | 新鮮な `spec-reviewer` pass と `report.md` の Lite 採用理由、未使用 specialist 理由、検証結果を残す。 |
| `standard` | 受け入れ条件（AC / EC）、scope、上位 trace、未確定事項を固定し、曖昧さが残る場合は clarification へ戻す。 | `system-architect` などの specialist 使用を推奨する。使わない場合は、既存 pattern で十分な理由、リスク、skip reason を `report.md` に残す。 | `implementation-planner` などの specialist 使用を推奨する。使わない場合は、manual authoring の根拠と skip reason を `report.md` に残す。 | 新鮮な `spec-reviewer` pass、specialist 使用 / 未使用理由、manual evidence、promotion evidence を残す。 |
| `strict` | 要件（requirement）は上位 requirement / ADR / workflow contract との trace と non-scope を明確にし、曖昧な判断を plan へ送らない。 | 専門家（specialist）は原則必須。unavailable / denied / host conflict の場合だけ manual fallback を使い、利用不可理由、代替調査、採用判断を `report.md` に残す。 | 専門家（specialist）は原則必須。plan は closure index、step-local evidence、review / QA / docs gate、commit 候補を持つ。fallback 時は manual planning evidence を残す。 | 新鮮な `spec-reviewer` pass に加え、specialist evidence または manual fallback evidence、failure-mode record、promotion evidence を残す。 |
| `critical` | 要件（requirement）は安全性、不可逆性、外部契約、運用影響、rollback / risk acceptance を明示する。 | 専門家（specialist）は必須。複数観点 review、ADR / escalation、risk acceptance が必要な場合は design で固定する。利用不可時は blocked を基本とし、manual fallback は明示承認と強い evidence がある場合だけ使う。 | 専門家（specialist）は必須。integration / rollback / observability / smoke / manual gate を plan に固定し、実行前に final quality gate を明示する。 | 新鮮な `spec-reviewer` pass、必要な追加 reviewer、manual fallback approval、risk acceptance、report evidence gate を残す。 |

Downstream stable wording として、G2 は `draft routing` を `authorized_profile` に従う runtime-owned artifact draft selection と呼び、G3 は `report evidence gate` を grade / specialist / fallback / promotion evidence の `report.md` 記録確認と呼び、G4 は `integrated smoke matrix` を Lite / Standard / Strict / Critical の各 grade が draft routing、report evidence gate、execution handoff の整合を保つことを確認する matrix と呼びます。G1 の guidance はこれらの用語を提供するだけで、routing enforcement、report validation、smoke 実装は行いません。

`report evidence gate` は implementation start 前 readiness に含まれます。`workflow status` / `guidance issue-execution` は、`report.md` に fresh `spec-reviewer` pass、Spec Authoring Gate、Evidence Adoption Ledger、Delegated Draft Evidence、Grade Specialist Evidence Gate、Reviewer Gate Status、未解決でない EAL がない場合、execution-ready として扱いません。Lite でも fresh review / report evidence は必要です。ただし Lite は specialist / fallback evidence 自体を必須化せず、Grade Specialist Evidence Gate には not applicable / skip reason を短く残します。Standard は specialist use、skip reason、または manual fallback evidence を残します。Strict / Critical は specialist use、または明示的な unavailable / manual fallback evidence を残します。skip reason だけでは Strict / Critical の readiness evidence になりません。

## 権限境界（Authority boundary / Promotion Record）

Canonical `requirement.md` / `design.md` / `plan.md` / `report.md` は main orchestrator の single-writer authority です。Sub-agent は canonical docs を直接編集しません。Sub-agent が作る authoring output は、対象 initiative / epic / issue の scope-local `artifacts/` 直下に置く flat Markdown draft / analysis / artifact-local report です。

Artifact output は runtime-owned `new artifact <type>` generation で作成し、returned `path=...` を本文更新の正本にします。Generated filenames は artifact rules に従います:

- `<ts>-<kind>-<slug>.md`
- `<ts>-<nn>-<kind>-<slug>.md` for same-second collisions
- `<ts>-<slug>.md` / `<ts>-<nn>-<slug>.md` for blank artifacts

Sub-agent-created draft は最低限、`created_by_role`、`scope_id`、`source_paths`、`intended_targets`、`adoption_status: unreviewed`、`reflected_to: []`、`diff_guard_result`、fallback decision、report evidence destination、adoption ledger note を持ちます。Evidence Adoption Ledger fields は ID、adoption_status、source、source_role、claim、target_artifact、target_section、rationale、evidence_strength、evidence_path、adopter、reviewer、blocking、next_action を標準にします。標準 delegated draft evidence として task manifest hash、Permission Profile hash、session invocation hash、probe run id、session hash を要求しません。これらは historical evidence または明示された例外証跡としてだけ扱います。
権限や採用可否の wildcard 指定は使いません。`*`、`grants.*`、`all` は invalid wildcard token として扱い、scope-local artifact direct-write の根拠にしてはなりません。

Workbench から `artifact import chatgpt-output` で保存した external evidence は、delegated authoring role が作成した draft ではありません。Imported body は evidence-only のまま内容不変とし、delegated draft 用 frontmatter、provenance fields、diff guard を追加しません。この分離は existing delegated draft の frontmatter、provenance、diff guard、authority restriction を緩和するものではありません。

このimportはapproved Workbenchの完成した単一Markdownをsource/bytes不変でcopyする明示操作です。`chatgpt-output` typed Artifact tokenを予約せず、templateから作る`new artifact`と共存します。File type/content classifier、automatic import、Workbench source削除は行いません。

Sub-agent-created draft は `authority: accepted`、`adoption_status: adopted`、non-empty `reflected_to`、reviewer pass、phase completion、implementation readiness を自己主張してはなりません。`reflected_to` は実際に canonical artifact へ反映済みの対象だけを表し、予定先は `intended_targets` で表します。

Accepted ADR は architecture decision authority を持ち得ますが、artifact draft / research / disc は evidence です。Implementation readiness、phase promotion、issue ready、issue finish、phase completion は、main orchestrator が evidence を canonical docs と `report.md` に再記述し、required reviewer gates が pass した後に成立します。

Promotion Record は delegated draft や reviewer output を canonical authority に昇格した事実だけを記録します。canonical artifact promotion の `promotion_record` は少なくとも `status`, `authority`, `owner_role`, `draft_author_role`, `approval`, `source_revision`, `approved_revision`, `approved_hash`, `reviewer_target_hash`, `promoted_at`, `promoted_by`, `promotion_decision` を持ちます。runtime active selection の promotion record は lifecycle gate 用の最小 record として `status`, `authority`, `source_revision`, `approved_revision`, `approved_hash`, `reviewer_target_hash`, `promotion_decision` を持ち、`source_revision` / `approved_revision` / `approved_hash` / `reviewer_target_hash` は active entry id に対応する `active:<id>` と一致している必要があります。`reviewer_target_hash` と `approved_hash` が一致しない場合、`source_revision` / `approved_revision` が一致しない場合、または active entry id と promotion record が一致しない場合、その promotion は invalid であり downstream authority には使えません。Mismatch / stale を発見した場合は report に reason と next action を残し、fresh reviewer gate と Promotion Record の再作成まで block します。

Active manifest と context-pack は同じ authority/grant 状態を示す必要があります。`spec-dock/.agent/active.json` の issue entry が `authority=proposed`、authority metadata 欠落、stale promotion record、または required exact grant 不足の場合、implementation start、issue ready、issue finish、phase completion の lifecycle handoff は blocked / incomplete とします。`spec-dock/active/context-pack.md` は人間向け guidance ですが、authority source は `spec-dock/.agent/active.json` です。

## ワークフロー単位の named role 許可（workflow-scoped authorization）

- ユーザーが SpecDock workflow の利用を依頼した場合、その依頼自体を、SpecDock が定義する named sub-agent / reviewer を workflow に従って利用する明示的な許可として扱う（"A user request to use a SpecDock workflow is explicit workflow-scoped authorization to use the SpecDock-defined named sub-agents and reviewers required by that workflow."）。
- active repo/worktree、active SpecDock scope、current session、documented role responsibility の範囲内では、SpecDock-defined named role の起動前に role ごと・phase ごとの追加承認を求めない（"Do not ask for additional per-role or per-phase permission before invoking SpecDock-defined named roles within the active repo/worktree, active SpecDock scope, current session, and documented role responsibility."）。
- 追加確認は scope expansion、破壊的操作、外部公開、credential を伴う外部 mutation、private external system、SpecDock workflow 外の role 利用に限る（"Ask the user only for scope expansion, destructive actions, external publishing, credentialed external mutation, private external systems, or roles outside the SpecDock workflow."）。
- この許可は「ユーザーがすべてを許可した」ことを意味しない。範囲は current repo/worktree、active SpecDock scope、current session、SpecDock-defined named roles、documented role responsibility に限る。
- canonical docs の single-writer authority は main orchestrator に残る。Sub-agent / reviewer output は evidence であり、canonical docs への採用は main orchestrator が行う。
- fresh `spec-reviewer` pass など workflow が要求する reviewer pass は gate であり、bounded SpecDock workflow scope 内の追加許可待ちを理由に省略してはならない。
- read-only specialist authorization と scope-local artifact direct-write authorization は別物として扱う。Sub-agent authoring output は proposal-only に限定しないが、採用可能な write は対象 scope `artifacts/` direct child の flat Markdown draft / analysis / artifact-local report に限る。
- scope-local artifact direct-write authorization は、target node、role、source artifacts、allowed artifact path rule、forbidden canonical/implementation paths、post-run diff guard、report ledger destination を明示した task-local authorization として別途記録する。workflow-wide authorization、unguarded workspace-write、static broad profile、または Desktop-only fallback は adoption-ready delegated output に数えない。

## 委任 authoring policy foundation（delegated authoring policy foundation）

- Main orchestrator は canonical `requirement.md` / `design.md` / `plan.md` / `report.md` の最終 ownership、user dialogue、canonical integration、Evidence Adoption Ledger、Promotion Record、phase promotion を所有する。
- Delegated authoring は scope-local flat `artifacts/` evidence であり、final canonical authority ではない。delegated output は main orchestrator が採否を判断し、fresh `spec-reviewer` が canonical artifact を pass して初めて phase promotion の根拠にできる。
- Delegated authoring を使う場合は、invocation ごとに node、role、scope、source artifacts、allowed artifact path rule、forbidden actions、output expectation、stop / invalidation condition を明示し、`report.md` に残す。workflow-wide blanket consent は direct-write authoring delegation の根拠にしない。
- Delegated role は対象 scope `artifacts/` direct child に naming-rule compliant Markdown を 1 ファイルだけ新規作成できる。既存 artifact file の編集は static adapter contract の対象外とし、将来必要な場合は別 workflow / follow-up で narrower allowlist と追加 gate を定義する。
- Delegated role は previous phase artifact、implementation code、tests、package/config、GitHub state、reviewer result を編集・確定・上書きしてはならない。destructive action、external publishing、credentialed access、`.github/agents` / Copilot support はこの workflow の delegated authoring policy では許可しない。
- Delegated draft が unavailable / skipped / blocked / stale / rejected / superseded の場合でも、manual authoring path は有効である。ただし delegated authoring を使った evidence として扱ってはならない。
- Delegated draft は fresh `spec-reviewer` pass の代替ではない。`spec-reviewer` は draft 自体ではなく、main orchestrator が統合した canonical artifact と evidence を review する。

## 委任ドラフト証跡 schema（delegated draft evidence schema）

- Delegated draft lifecycle state は `requested` / `produced` / `integrated` / `partially_integrated` / `rejected` / `superseded` / `blocked` / `stale` のいずれかで記録する。
- `stale`、`rejected`、`superseded`、`blocked` の delegated draft は promotion evidence に使えない。`partially_integrated` は採用部分、rejected portions、blockers、promotion decision を `report.md` に明示した場合だけ採用部分の補助 evidence にできる。
- Delegated draft evidence record は少なくとも `created_by_role`、scope、source artifacts、draft artifact path、intended targets、`adoption_status: unreviewed`、`reflected_to: []`、diff guard result、integration result、rejected portions、blockers、reviewer result、promotion decision を持つ。
- `source_snapshot` を記録する場合は source revision、reviewer pass reference、generated_at、stale_if を含める。
- Failure-mode record は expected verdict、allowed next action、report evidence path、promotion eligibility を持つ。
- Required failure modes は missing workflow-scoped authorization evidence、missing/stale previous reviewer pass、requirement gap during design、design gap during plan、role unavailable、forbidden action attempt、stale draft、superseded draft、missing draft evidence when delegated use is claimed、reviewer unavailable/denied/waived/provisional を含む。
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
- authoring specialist は、task-local consent がある場合に限り scope-local `artifacts/` direct child の flat Markdown evidence を 1 件新規作成できる。leaf-only evidence producer は repo analysis、research、consultation、QA-style evidence を返すだけで、artifact write を含む file mutation を行わない。authoring specialist と leaf-only evidence producer は canonical edit、implementation edit、phase promotion、reviewer-pass claim、final authority、issue ready / issue finish claim を行わない
- preflight reviewer output は設計・計画の改善 input として扱い、final fresh reviewer pass とは分離する
- reviewer independence: final `spec-reviewer` / `code-reviewer` / `qa-reviewer` は、同じ artifact を作成した authoring specialist や leaf-only evidence producer の代替ではない fresh gate として実行する

## Scope-local artifact write gate

System architect / implementation planner の static adapter は、guarded workspace-write により scope-local `artifacts/` Markdown draft を作成する delegated authoring surface です。Workspace-write は hard path allow-list ではなく、canonical target write の許可でもありません。Run ごとの permission context 生成は標準経路にせず、post-run diff guard pass と canonical `report.md` の ledger entry 記録まで adoption-ineligible として扱います。

Allowed delegated output は target scope `artifacts/` direct-child Markdown file 1 件の新規作成に限定し、creation は runtime-owned `new artifact <type>` を使って returned `path=...` を正本にします。post-run diff guard は generated filename が typed artifact の `<ts>-<kind>-<slug>.md` / `<ts>-<nn>-<kind>-<slug>.md`、または blank artifact の `<ts>-<slug>.md` / `<ts>-<nn>-<slug>.md` に一致することを確認します。新規 artifact draft は frontmatter に `created_by_role`、`scope_id`、`source_paths`、`intended_targets`、`adoption_status: unreviewed`、`reflected_to: []`、`diff_guard_result` を持たなければなりません。`created_by_role` は supported delegated authoring role、`scope_id` は requested scope id と一致する値、`source_paths` と `intended_targets` は non-empty block list である必要があります。inline scalar や `source_paths: []` / `intended_targets: []` は post-run diff guard で不合格になります。

```yaml
source_paths:
  - spec-dock/active/issue/requirement.md
intended_targets:
  - spec-dock/active/issue/report.md
```

既存 artifact update は static adapter contract の対象外です。accepted ADR、superseded、stale、rejected、adopted evidence、または proposed draft の既存 file update が必要な場合は、別 workflow / follow-up で narrower allowlist と追加 gate を定義します。Delegated authoring agent は `git add`、`git commit`、`git push`、または orchestrator から file changes を隠す操作を実行してはいけません。diff guard は `--baseline-status` を必須入力として実行し、target scope `artifacts/` は run 開始時点で clean にします。baseline に target artifacts subtree の dirty/untracked entry がある delegated output は adoption-ineligible とします。baseline-status に `HEAD` が含まれる場合、diff guard は current `HEAD` と一致しない delegated output を committed side effect として fail-closed に扱います。baseline-status に `HEAD` がない場合は HEAD 比較だけを省略し、artifact draft と side effect 検査は継続します。pre-existing non-target dirtiness は repo 外に生成した `delegated-authoring baseline-status --output <path>` の file-state snapshot が current file content and mode と一致する場合に限り delegated output diff から除外できます。baseline entry が current status から消えた場合や、baseline 後に ignored file / directory side effect が増えた場合は、delegated run 中の non-target 変更として fail-closed に扱います。

Forbidden output は canonical docs、implementation files、tests、package/config、`.agents`、`.codex`、`.github`、`.env*`、nested artifact directories、symlinks、non-Markdown files、deletes、renames、copied paths、out-of-scope artifacts、mixed staged/unstaged artifact states、unmerged artifact states を含みます。

`.env*` read denial は hard sandbox や diff guard で証明されるものではありません。Permission Profile を標準経路から完全削除する方針では、`.env*` read は instruction-forbidden / soft control として扱います。post-run diff guard が検出できるのは `.env*` write、または baseline 後に増えた ignored side effect であり、`.env*` read 自体ではありません。

Historical `iss-00126` task manifest / Permission Profile / probe / session artifacts は grandfathered evidence です。current standard が manifest-heavy success path を使わなくなったことだけを理由に削除、rename、validation failure 化してはなりません。

| 失敗モード | 期待される判定 | 許可される次アクション | report 証跡の記録先 | 昇格可否 |
|---|---|---|---|---|
| ワークフロー単位の許可証跡不足（missing workflow-scoped authorization evidence） | blocked / incomplete | ワークフロー利用依頼の authorization source と boundary を記録する、または手動 authoring を使う | ワークフロー単位の named role 許可（Workflow-Scoped Authorization） / Delegated Draft Evidence | ineligible |
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
4. 調査結果、仮説、選択肢、質問を必要に応じて `artifacts/` に分離する。raw / untyped capture は `blank`、人間への正式質問は一問一答の `interview`、事実調査は `research`、論点整理 / synthesis は `disc`、長期判断は `adr` を使う。formal question trigger と lightweight chat question の境界は `workflow_clarification.md` の bridge/reference detail を参照する。
5. ChatGPT output を受領した場合、main orchestrator が semantic completeness と output form を分類し、[workflow_chatgpt_authoring_pack.md](workflow_chatgpt_authoring_pack.md) の preservation checkpoint を実行する。保存、exception、または ZIP/tree route の必要証跡が成立するまで採否判断や canonical rewrite へ進まない。
6. main orchestrator が Evidence Adoption Ledger に採否を記録する。
7. 対象 artifact を更新する。
8. fresh `spec-reviewer` を起動し、対象 artifact と upstream artifact を review する。
9. `fail` なら修正し、fresh `spec-reviewer` で再レビューする。
10. `pass` なら `report.md` に gate evidence を残し、次 phase へ進む。

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
- clarification evidence: source-grounded read、formal `interview` path、lightweight chat question の扱い、採用 / 非採用判断
- workflow-scoped authorization evidence: authorization source、active repo/worktree、active SpecDock scope、current session、SpecDock-defined named roles、documented role responsibility、boundary、expires / invalidation condition。SpecDock workflow 利用依頼を authorization source として扱い、scope 内の role ごと・phase ごとの追加承認 gate にはしない
- reviewer: fresh `spec-reviewer` の実行単位と review scope
- verdict: `passed` / `failed` / `unavailable` / `denied` / `waived` / `provisional` と理由。`passed` 以外は reviewer gate pass ではない
- fixes: 指摘に対する修正要約
- promotion: 次 phase へ進めるか、`blocked` / `incomplete` の reason と next action

長い調査、比較、ヒアリング transcript は `artifacts/` に分離してよい。ただし `report.md` には判断に必要な要約と参照を残す。artifact docs は未確定情報の作業面なので、確定させる内容は新しい `adr`、または `requirement.md` / `design.md` / `plan.md` へ反映する。既存 `discussions/` は legacy / preservation evidence として参照してよいが、新規 working artifact の推奨先にはしない。
