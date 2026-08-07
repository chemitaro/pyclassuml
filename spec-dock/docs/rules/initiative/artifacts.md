# 成果物ルール（artifacts/rules.md）

このディレクトリには initiative に紐づく future working artifacts を置きます。

- Artifact workflow: future `new artifact` surface が作成する作業用 evidence surface です。
- Naming rules: `spec-dock/docs/reference_naming.md`
- 作成される artifacts はこの directory に timestamp-prefixed original として保存されます。
  - typed artifacts: `<ts>-<type>-<slug>.md`
  - typed same-second collision: `<ts>-<nn>-<type>-<slug>.md`
  - blank artifacts: `<ts>-<slug>.md`
  - blank same-second collision: `<ts>-<nn>-<slug>.md`
- `blank` は filename token を使わず、front matter の `template: "blank"` で template identity を示します。
- Canonical `requirement.md` / `design.md` / `plan.md` / `report.md` は artifacts ではありません。canonical docs は main orchestrator single-writer authority です。
- Artifact は evidence / draft / synthesis / decision candidate の作業面です。採用は canonical docs、accepted ADR、または `report.md` Evidence Adoption Ledger への反映で成立します。
- `artifact import file --initiative <id> --file <path>` は、Workbench を要求せず、一件の明示 regular file を generic Artifact として保存します。source は変更せず、bytes は opaque evidence のままです。`canonical=false` は自動採用しないことを表します。命名は [reference_naming.md](../../reference_naming.md)、privacy-safe result と publication / retry state は [guide.md](../../guide.md) を参照してください。
- Legacy `discussions/` は preservation surface です。既存 discussion docs は削除、移動、rename せず grandfathered evidence として扱います。
- Future `artifacts/` adoption は legacy `discussions/` validation を弱めません。
- ADR originals may live under future `artifacts/` or legacy `discussions/`; ADR mirror collection must collect both without moving originals.
- Direct artifact template catalog:
  - `blank`: 型を先に決めない working evidence。filename に `blank` token は要求しません。
  - `research`: source-grounded read。事実、推測、未検証、用語衝突、edge case、判断への含意を分ける。
  - `interview`: docs-aware clarification の正式質問シート。重要判断は一問一答で扱う。
  - `disc`: synthesis / 中間レポート / reflection proposal / ADR candidate triage。
  - `decision-candidate`: canonical docs / ADR / report ledger へ採用する前の判断候補。
  - `pr-repair-batch`: PR repair workflow の observation、concern inventory、repair queue、merge-prepared gate を記録する。
  - `adr`: 意思決定記録。作成直後は draft / non-authoritative / non-mirror で、accepted 後に authority fields と mirror eligibility を埋めます。
- Unsupported issue-only draft artifact types:
  - `draft-requirement`: Initiative scope では unsupported です。future `new artifact draft-requirement --initiative` は write 前に no-write fail-closed します。
  - `draft-design`: Initiative scope では unsupported です。future `new artifact draft-design --initiative` は write 前に no-write fail-closed します。
  - `draft-plan`: Initiative scope では unsupported です。future `new artifact draft-plan --initiative` は write 前に no-write fail-closed します。
  - Safety-sensitive `draft-*` routing is issue-only unless a later accepted ADR defines a non-Issue assurance model.
- `scratch` is legacy-only and is not part of the future `new artifact` catalog. New untyped capture uses `blank`.
- `note` は retired。既存 artifact は grandfathered として壊しません。
- 実行場所: コマンドはリポジトリ root から実行してください。`./spec-dock/scripts/spec-dock ...` はその位置で保証される実行経路で、nested directory では相対 path が変わります。
