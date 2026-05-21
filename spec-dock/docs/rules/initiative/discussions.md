# discussions/rules.md

このディレクトリには initiative に紐づく議論資料を置きます。

- Discussion workflow: `spec-dock/docs/workflow_adr.md`
- Naming rules: `spec-dock/docs/reference_naming.md`
- 作成される docs はこの directory に timestamp-prefixed original として保存されます（標準: `<ts>-<kind>-<slug>.md` / same-second collision: `<ts>-<nn>-<kind>-<slug>.md`）。legacy sequential files は grandfathered で、自動 rename しません。
- 実行場所: コマンドはリポジトリ root から実行してください。`./spec-dock/scripts/spec-dock ...` はその位置で保証される実行経路で、nested directory では相対 path が変わります。
- Current catalog:
  - `scratch`: raw capture。非 authoritative。未整理の発話、観察、思考、会話ログを置く。
  - `interview`: ヒアリング記録。人間から未確定情報を引き出し、回答欄と反映先を管理する。
  - `research`: 事実調査。事実、推測、未検証、判断への含意を分ける。
  - `disc`: 論点整理。集まった情報をもとに評価軸、選択肢、合意点を整理する。
  - `adr`: 意思決定記録。長期的な判断と理由を固定する。
- `note` は retired。既存 artifact は grandfathered だが、新規 raw capture は `scratch` を使う。
- `disc` が大きくなりすぎたら、質問回答は `interview`、事実調査は `research`、生ログは `scratch`、長期判断は `adr` へ分割してください。
- Create commands:
  - `./spec-dock/scripts/spec-dock new doc scratch --initiative <id> --title "<title>"`
  - `./spec-dock/scripts/spec-dock new doc interview --initiative <id> --title "<title>"`
  - `./spec-dock/scripts/spec-dock new doc research --initiative <id> --title "<title>"`
  - `./spec-dock/scripts/spec-dock new doc disc --initiative <id> --title "<title>"`
  - `./spec-dock/scripts/spec-dock new doc adr --initiative <id> --title "<title>"`
