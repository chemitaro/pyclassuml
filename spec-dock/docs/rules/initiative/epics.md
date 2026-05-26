# エピック一覧ルール（epics/rules.md）

このディレクトリには initiative 配下の epic を作成します。

- Epic workflow: `spec-dock/docs/workflow_epic.md`
- Naming rules: `spec-dock/docs/reference_naming.md`
- 実行場所: コマンドはリポジトリ root から実行してください。`./spec-dock/scripts/spec-dock ...` はその位置で保証される実行経路で、nested directory では相対 path が変わります。
- Create command: `./spec-dock/scripts/spec-dock new epic --initiative <id> --title "<title>"`
