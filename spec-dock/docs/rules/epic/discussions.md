# discussions/rules.md

このディレクトリには epic に紐づく議論資料を置きます。

- Discussion workflow: `spec-dock/docs/workflow_adr.md`
- Naming rules: `spec-dock/docs/reference_naming.md`
- 作成される docs はこの directory に timestamp-prefixed original として保存されます（標準: `<ts>-<kind>-<slug>.md` / same-second collision: `<ts>-<nn>-<kind>-<slug>.md`）。legacy sequential files は grandfathered で、自動 rename しません。
- 実行場所: コマンドはリポジトリ root から実行してください。`./spec-dock/scripts/spec-dock ...` はその位置で保証される実行経路で、nested directory では相対 path が変わります。
- Create commands:
  - `./spec-dock/scripts/spec-dock new doc adr --epic <id> --title "<title>"`
  - `./spec-dock/scripts/spec-dock new doc disc --epic <id> --title "<title>"`
  - `./spec-dock/scripts/spec-dock new doc research --epic <id> --title "<title>"`
  - `./spec-dock/scripts/spec-dock new doc note --epic <id> --title "<title>"`
