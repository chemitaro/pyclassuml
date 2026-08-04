# 議論ルール（discussions/rules.md）

このディレクトリは epic に紐づく legacy / historical discussion docs の preservation surface です。新規 working artifacts は対象 scope の `artifacts/` direct child に作成します。

- Discussion workflow: `spec-dock/docs/workflow_adr.md`
- Naming rules: `spec-dock/docs/reference_naming.md`
- Existing docs in this directory are timestamp-prefixed originals（標準: `<ts>-<kind>-<slug>.md` / same-second collision: `<ts>-<nn>-<kind>-<slug>.md`）。legacy sequential files は grandfathered で、自動 rename しません。
- Delegated authoring の future draft / analysis / artifact-local report は対象 scope の `artifacts/` direct child に flat Markdown として保存します。per-agent directory、run/task directory、global draft store、`discussions/delegated-authoring/`、`artifacts/delegated-authoring/` は新規出力先にしません。
- Sub-agent-created draft は canonical docs への直接書き込みではなく、scope-local `artifacts/` 直下の flat Markdown として保存します。`draft-requirement` / `draft-design` / `draft-plan` は draft 専用 template を持たず、scope kind に応じた canonical template を直接 source として render します。canonical docs remain main-orchestrator-only. `authority: accepted`、`adoption_status: adopted`、non-empty `reflected_to` は自己主張しません。
- Canonical `requirement.md` / `design.md` / `plan.md` / `report.md` は main orchestrator single-writer authority です。artifact draft は evidence であり、採用は canonical `report.md` の Evidence Adoption Ledger と canonical docs への再記述で成立します。
- `report.md` は canonical observed evidence ledger です。legacy discussion-local report artifact catalog には含めません。
- Historical delegated-authoring manifest/Profile/probe/session artifacts は grandfathered evidence です。current delegated drafts が flat model を使うことだけを理由に削除、rename、validation failure 化しません。
- 実行場所: コマンドはリポジトリ root から実行してください。`./spec-dock/scripts/spec-dock ...` はその位置で保証される実行経路で、nested directory では相対 path が変わります。
- Legacy discussion catalog:
  - `scratch`: raw capture。非 authoritative。未整理の発話、観察、思考、会話ログを置く。
  - `interview`: docs-aware clarification の正式質問シート。重要判断は一問一答で扱い、回答前に unanswered artifact を作成し、回答後に同じ artifact へ回答、採用判断、反映先を追記する。既存の複数質問 artifact は grandfathered で、自動分割や rename はしない。
  - `research`: source-grounded read。事実、推測、未検証、用語衝突、edge case、判断への含意を分ける。
  - `disc`: synthesis / 中間レポート / reflection proposal / ADR candidate triage。採否の最終証跡は canonical docs / ADR / `report.md` Evidence Adoption Ledger に昇格する。
  - `adr`: 意思決定記録。後から戻しにくく、将来の読者に意外性があり、実質的な tradeoff がある長期判断を固定する。
  - `pr-repair-batch`: PR repair workflow の observation、concern inventory、repair queue、merge-prepared gate を記録する。
  - `draft-requirement`: scope kind に応じた canonical requirement template を直接 source として render する discussion-local draft。
  - `draft-design`: scope kind に応じた canonical design template を直接 source として render する discussion-local draft。
  - `draft-plan`: scope kind に応じた canonical plan template を直接 source として render する discussion-local draft。
- `note` は retired。既存 artifact は grandfathered です。future raw / untyped capture は `new artifact blank` を使います。
- `disc` が大きくなりすぎたら、質問回答は `interview`、事実調査は `research`、生ログは `scratch`、長期判断は `adr` へ分割してください。`report.md` へ synthesis 本文を抱え込ませず、採用済み evidence と canonical 反映結果だけを残します。
- Do not create new files in this directory for routine work. New working artifacts use `./spec-dock/scripts/spec-dock new artifact <type> --epic <id> --title "<title>"` and target `artifacts/`.
- Historical creation command examples are intentionally omitted so this preservation surface is not advertised as a runnable path.
