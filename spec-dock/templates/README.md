# spec-dock/templates

このディレクトリは、ローカルスクリプト `./spec-dock/scripts/spec-dock new ...` が
新規ノードを作成する際に参照するテンプレート群です。

- `initiative/` → `initiatives/init-xxxx-<slug>/`
- `epic/` → `.../epics/epic-xxxx-<slug>/`
- `issue/` → `.../issues/iss-xxxx-<slug>/`
- `discussions/{adr,disc,research,note}.md` → `<scope>/discussions/<ts>-<kind>-<slug>.md`
- same-second collision 時は `<scope>/discussions/<ts>-<nn>-<kind>-<slug>.md`

注意:
- discussion docs の公開 CLI は `new doc <type>` のみです。
- discussion docs の filename contract は timestamp-prefix です（標準: `<ts>-<kind>-<slug>.md` / same-second collision: `<ts>-<nn>-<kind>-<slug>.md`）。
- `ts = yyyymmddthhmmssz`（UTC, lowercase `t` / `z`）、`nn = 01..99` です。
- `doc_id` は slugless identity（`<ts>-<kind>` / `<ts>-<nn>-<kind>`）で、filename stem は `<doc_id>-<slug>` です。
- `discussions/` 配下の allocation は valid timestamp-contract files を対象にし、unrelated files（例: `rules.md`, `README.md`）は無視されます。
- legacy sequential discussion docs（`<nnn>-<kind>-<slug>.md`）は grandfathered artifact として許容されますが、自動 rename や basename 再利用はしません。
- ただし discussion-doc intent を持つ malformed basename は explicit failure です（例: `foo-adr-kickoff.md`, `bogus-01-adr-kickoff.md`, `20260329x-adr-kickoff.md`）。
- same-second collision suffix が `99` まで埋まった場合は失敗します。follow-up issue で archive または contract 拡張を判断してください。
- 生成後のファイルは自由に編集して構いません（テンプレは雛形）。
- 命名規則は **全て小文字**（macOS のケース非区別FS対策）。
- `new/import {initiative,epic,issue}` の `--slug` は kebab-case（小文字英数字 + `-`）です。`--slug` 省略時は `--title` から合成されます（詳細は `spec-dock/docs/reference_naming.md`）。
- 各ノードの子スコープ配下には canonical guidance への `rules.md` symlink が含まれます（例: `epics/rules.md`, `issues/rules.md`, `discussions/rules.md`）。`rules.md` は入口/ナビゲーション用です。
- 作成/運用ルールの正本は `spec-dock/docs/rules/**` です。runtime command はサポートされた実行経路です。
- 新規ノードにはテンプレ由来の `README.md` は生成されません。
