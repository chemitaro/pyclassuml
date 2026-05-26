# テンプレート一覧（spec-dock/templates）

このディレクトリは、ローカルスクリプト `./spec-dock/scripts/spec-dock new ...` が
新規ノードを作成する際に参照するテンプレート群です。

- `initiative/` → `initiatives/init-xxxx-<slug>/`
- `epic/` → `.../epics/epic-xxxx-<slug>/`
- `issue/` → `.../issues/iss-xxxx-<slug>/`
- `discussions/{scratch,interview,research,disc,adr}.md` → `<scope>/discussions/<ts>-<kind>-<slug>.md`
- `draft-requirement` / `draft-design` / `draft-plan` は draft 専用 template file を持たず、scope kind に応じた canonical `templates/{initiative,epic,issue}/{requirement,design,plan}.md` を直接 source として render します。
- same-second collision 時は `<scope>/discussions/<ts>-<nn>-<kind>-<slug>.md`

注意:
- discussion docs の公開 CLI は `new doc <type>` のみです。
- current catalog は `scratch` / `interview` / `research` / `disc` / `adr` / `draft-requirement` / `draft-design` / `draft-plan` です。
- `draft-requirement` / `draft-design` / `draft-plan` は `discussions/` 配置と draft filename で draft artifact として扱います。canonical docs remain main-orchestrator-only; canonical docs direct-write success path はありません。
- `note` は retired です。既存 `note` artifact は grandfathered として壊さず、新規 raw capture は `scratch` を使います。
- discussion docs の filename contract は timestamp-prefix です（標準: `<ts>-<kind>-<slug>.md` / same-second collision: `<ts>-<nn>-<kind>-<slug>.md`）。
- `ts = yyyymmddthhmmssz`（UTC, lowercase `t` / `z`）、`nn = 01..99` です。
- `doc_id` は slugless identity（`<ts>-<kind>` / `<ts>-<nn>-<kind>`）で、filename stem は `<doc_id>-<slug>` です。
- `discussions/` 配下の allocation は valid timestamp-contract files を対象にし、unrelated files（例: `rules.md`, `README.md`）は無視されます。
- legacy sequential discussion docs（`<nnn>-<kind>-<slug>.md`）は grandfathered artifact として許容されますが、自動 rename や basename 再利用はしません。
- ただし discussion-doc intent を持つ malformed basename は explicit failure です（例: `foo-adr-kickoff.md`, `bogus-01-adr-kickoff.md`, `20260329x-adr-kickoff.md`）。
- same-second collision suffix が `99` まで埋まった場合は失敗します。follow-up issue で archive または contract 拡張を判断してください。
- 生成後のファイルは自由に編集して構いません（テンプレは雛形）。
- authority は通常 doc type から推定します。例外時だけ front matter の `authority` で override し、全 artifact に明示必須化しません。
- discussion docs は作業面です。必要な文脈だけを新しい `adr`、または `requirement.md` / `design.md` / `plan.md` へ反映します。
- 命名規則は **全て小文字**（macOS のケース非区別FS対策）。
- `new/import {initiative,epic,issue}` の `--slug` は kebab-case（小文字英数字 + `-`）です。`--slug` 省略時は `--title` から合成されます（詳細は `spec-dock/docs/reference_naming.md`）。
- 各ノードの子スコープ配下には canonical guidance への `rules.md` symlink が含まれます（例: `epics/rules.md`, `issues/rules.md`, `discussions/rules.md`）。`rules.md` は入口/ナビゲーション用です。
- 作成/運用ルールの正本は `spec-dock/docs/rules/**` です。runtime command はサポートされた実行経路です。
- 新規ノードにはテンプレ由来の `README.md` は生成されません。

更新:
- 導入済み repo の managed files/docs/templates/scripts/skills は repo root から `./spec-dock/scripts/spec-dock update [path]` で更新します。
- `path` 省略時の target は current directory です。別 repo を更新する場合は `./spec-dock/scripts/spec-dock update /path/to/project` のように明示します。
- runtime update は installer update の wrapper です。内部では固定 upstream `git+https://github.com/chemitaro/spec-dock` に対して `uvx --no-cache --from git+https://github.com/chemitaro/spec-dock spec-dock update <target>` を実行します。
- runtime update は `init --force` ではなく、自動 migration tool でもありません。legacy / incompatible workspace は手動 normalize または rebuild が必要な場合があります。
