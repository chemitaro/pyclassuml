# 仕様明確化ワークフロー（workflow: clarification）

既存ドキュメントとコードを根拠に、曖昧さを一問一答で解消し、合意内容を spec-dock の成果物へ昇華する workflow です。

この workflow は Issue planning の補助節ではなく、requirement / design / plan authoring の前後、局所的な decision clarification、analysis-only / draft-only 作業のいずれでも使える first-class entrypoint です。

関連:
- Spec authoring workflow: [workflow_spec_authoring.md](workflow_spec_authoring.md)
- Issue execution workflow: [workflow_issue.md](workflow_issue.md)
- Discussion rules: 対象 scope 配下の `discussions/rules.md`
- Naming rules: [reference_naming.md](reference_naming.md)

## 基本契約

- 先に source-grounded read を行う。active docs、parent docs、`discussions/`、関連 source / tests / templates、既存 ADR を確認し、local context で解ける疑問を人間へ質問しない。
- decision tree traversal として、曖昧な論点を分解し、次に答えるべき本質的な質問を一つだけ選ぶ。
- 人間ユーザーへの本質的な質問は orchestrator が一問ずつ行う。専門 agent は人間へ直接質問せず、質問候補、理由、影響 artifact、推奨回答を orchestrator へ返す。
- 用語、責務境界、domain relationship が曖昧な場合は、既存 docs / code の言葉を照合し、domain language を sharpen する。
- 抽象論で閉じず、必要に応じて concrete scenario、edge case、code / docs cross-check で境界を確認する。
- 合意内容は docs synthesis を通じて `requirement.md` / `design.md` / `plan.md` / ADR / `report.md` へ反映する。discussion artifact は evidence / proposal であり、採用判断なしに canonical source of truth にしない。
- ADR は sparingly に使う。後から戻しにくく、将来の読者に意外性があり、実質的な tradeoff がある判断だけを ADR candidate にする。

## 実行モード

- analysis-only mode:
  - canonical docs 作成や変更を目的にしない。
  - `research` / `disc` / unanswered or answered `interview` などで、曖昧さ、選択肢、質問候補、推奨案、未解決 gap を整理する。
  - 採用済み仕様として扱うには、後続の authoring mode で canonical docs と `report.md` へ反映する。
- authoring mode:
  - clarification evidence を `requirement.md` / `design.md` / `plan.md` へ統合する。
  - 採用判断は `report.md` の Evidence Adoption Ledger、Objective Alignment Ledger、Spec Authoring Gate に残す。
  - phase promotion は `workflow_spec_authoring.md` の fresh `spec-reviewer` gate に従う。

## 成果物の使い分け（artifact selection）

- `scratch`: raw capture。非 authoritative。
- `research`: source-grounding。事実、推測、未検証事項、用語衝突、edge case、判断への含意を分ける。
- `interview`: 正式質問シート。重要判断は回答前に unanswered artifact を作り、回答後に同じ artifact へユーザー回答、採用判断、反映先を追記する。追加の高影響質問が生じたら、同じ artifact に質問を増やさず次の unanswered `interview` を作る。
- `disc`: 複数質問 / research の synthesis、中間レポート、reflection proposal、ADR candidate triage。
- `adr`: durable architecture / contract / migration decision。
- `report.md`: canonical observed evidence ledger。discussion catalog ではなく、Evidence Adoption Ledger、Objective Alignment Ledger、Spec Authoring Gate の採用証跡を持つ。

## 正式質問の起動条件（formal question trigger）

次のいずれかに該当する場合は、chat のみで確定せず、回答前に unanswered `interview` artifact を作成する。

- requirement / design / plan / ADR / scope / non-scope / workflow / template / agent role に影響する。
- implementation step、test obligation、review gate、migration / rollback、cleanup 対象を変える。
- 複数 artifact へ反映する必要がある。
- 複数の選択肢、tradeoff、Codex recommendation を提示してからユーザー判断を得る必要がある。
- 回答後に採用 / 部分採用 / 棄却 / deferred の判断を追跡する必要がある。

軽微な確認は chat 上の一問でよい。ただし、回答が重要判断へ発展した場合は formal `interview` lifecycle へ戻す。

## 統合と採用（synthesis and adoption）

- `research` と `interview` から得た facts / answers / options は、必要に応じて `disc` で束ねる。
- `disc` は proposal と反映候補を整理する場所であり、採否を確定する canonical ledger ではない。
- 外部支援 artifact は通常 evidence として扱い、外部ツール固有の操作手順、責務、セッション管理を spec-dock の要件へ混入しない。
- Evidence Adoption Ledger には adoption decision、target artifact / section、evidence、next_action を残す。
- Objective Alignment Ledger には primary objective evidence、secondary requirement evidence、inversion risk、reviewer verdict を残す。
- Spec Authoring Gate には investigated facts、open questions、answers、reviewer verdict、blocking / non-blocking、promotion decision を残す。

## 実装 Issue への引き継ぎ境界（issue handoff boundary）

Issue execution への handoff で扱うのは次に限定する。

- `workflow_clarification.md` を参照し、未解決 specification gap は authoring / clarification phase へ戻す。
- implementation start 前に requirement / design / plan gate と `Spec Authoring Gate` evidence を確認する。
- handoff readiness evidence を `report.md` に残す。

Issue planning / execution split、execution policy、delegation framework、PR delivery、issue finish lifecycle をこの workflow の headline deliverable にしない。
