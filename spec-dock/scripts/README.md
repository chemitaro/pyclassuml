# spec-dock/scripts

このディレクトリは、`spec-dock` が作成する補助スクリプト置き場です。

v2 では、日常運用（initiative/epic/issue/doc の作成、active 切り替え、sync/validate）は
このディレクトリ内の **ローカルスクリプト**で実行します。

- `new initiative` / `new epic` はデフォルトで local-only です（`gh` は呼びません）。
- `new issue` はデフォルトで GitHub Issue を作成します（`--no-github` で local-only）。
- discussion docs は `new doc <type>` のみを使います（`type=adr|disc|research|note`）。
- `new/import {initiative,epic,issue}` と `new doc <type>` の `--slug` は kebab-case が必要です（詳細は `spec-dock/docs/reference_naming.md`）。

## 使い方（例）

```bash
# 新規作成（initiative/epic はデフォルト local-only）
./spec-dock/scripts/spec-dock new initiative --title "Auth platform"                    # id=init-local-00001
./spec-dock/scripts/spec-dock new epic --initiative 1 --title "JWT auth"               # id=epic-local-00001

# issue はデフォルトで GitHub Issue を作成
./spec-dock/scripts/spec-dock new issue --epic 1 --title "Add refresh token"           # id=iss-00123
./spec-dock/scripts/spec-dock new issue --no-github --epic 1 --title "Add refresh token" # id=iss-local-00001

# discussion docs（timestamp-prefixed filename）
./spec-dock/scripts/spec-dock new doc adr --issue iss-00123 --title "Token rotation"    # 20260329t123456z-adr-...
./spec-dock/scripts/spec-dock new doc disc --issue iss-00123 --title "API options"      # 20260329t123457z-disc-...
./spec-dock/scripts/spec-dock new doc research --issue iss-00123 --title "Benchmarks"   # 20260329t123458z-research-...
./spec-dock/scripts/spec-dock new doc note --issue iss-00123 --title "Kickoff memo"     # 20260329t123459z-note-...

# active（現在作業中）を設定
./spec-dock/scripts/spec-dock active set 123
./spec-dock/scripts/spec-dock active set iss-00123 --checkout
./spec-dock/scripts/spec-dock active set iss-local-00001

# 状態集計を生成
./spec-dock/scripts/spec-dock sync
./spec-dock/scripts/spec-dock sync --github

# 構造チェック
./spec-dock/scripts/spec-dock validate
```

discussion docs 補足:
- ファイル名 contract は `<ts>-<kind>-<slug>.md`、same-second collision 時は `<ts>-<nn>-<kind>-<slug>.md` です。
- `ts = yyyymmddthhmmssz`（UTC, lowercase `t` / `z`）、`nn = 01..99` です。
- `doc_id` は slugless identity（`<ts>-<kind>` / `<ts>-<nn>-<kind>`）で、filename stem は `<doc_id>-<slug>` です。
- allocation 対象は valid timestamp-contract files のみです。
- unrelated files は無視されます（例: `rules.md`, `README.md`）。
- legacy sequential discussion docs（`<nnn>-<kind>-<slug>.md`）は grandfathered ですが、自動 rename や basename 再利用はしません。
- ただし discussion-doc intent を持つ malformed basename は explicit failure です（例: `foo-adr-kickoff.md`, `bogus-01-adr-kickoff.md`, `20260329x-adr-kickoff.md`）。
- same-second collision suffix が `99` まで埋まると失敗します。follow-up issue で archive または contract 拡張を判断してください。

注:
- `spec-dock/.agent/` と `spec-dock/active/` は生成物です（git 管理しません）。
- 導入/更新（`spec-dock/{docs,templates,scripts}` の配置）は `uvx spec-dock init/update` を使います。
