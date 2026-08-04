# spec-dock/scripts

このディレクトリは、`spec-dock` が作成する補助スクリプト置き場です。

v2 では、日常運用（initiative/epic/issue/artifact の作成、active 切り替え、sync/validate）は
このディレクトリ内の **ローカルスクリプト**で実行します。

- `new initiative` / `new epic` / `new issue` はデフォルトで GitHub Issue を作成します。
- 既存 current-repo Issue へ紐づける場合は `--github-issue <n>` を使います。
- `--no-github` は node creation option ではありません。
- working artifacts は `new artifact <type>` を使います（current catalog: `blank` / `interview` / `research` / `disc` / `decision-candidate` / `adr` / `pr-repair-batch` / issue-only `draft-requirement` / `draft-design` / `draft-plan`）。
- `scratch` / `note` は new artifact catalog には含めません。既存 artifact は grandfathered として壊さず、新規 untyped capture は `blank` を使います。
- `new/import {initiative,epic,issue}` と `new artifact <type>` の `--slug` は kebab-case が必要です（詳細は `spec-dock/docs/reference_naming.md`）。

## 使い方（例）

```bash
# 新規作成（デフォルトで GitHub Issue を作成）
./spec-dock/scripts/spec-dock new initiative --title "Auth platform"                    # id=init-00101
./spec-dock/scripts/spec-dock new epic --initiative 101 --title "JWT auth"             # id=epic-00201
./spec-dock/scripts/spec-dock new issue --epic 201 --title "Add refresh token"         # id=iss-00301

# 既存 current-repo GitHub Issue へリンクする
./spec-dock/scripts/spec-dock new issue --epic 201 --github-issue 302 --title "Rotate refresh token"

# working artifacts（timestamp-prefixed filename）
./spec-dock/scripts/spec-dock new artifact blank --issue iss-00123 --title "Kickoff memo"       # 20260329t123456z-kickoff-memo.md
./spec-dock/scripts/spec-dock new artifact interview --issue iss-00123 --title "Rollout policy" # 20260329t123457z-interview-...
./spec-dock/scripts/spec-dock new artifact research --issue iss-00123 --title "Benchmarks"      # 20260329t123458z-research-...
./spec-dock/scripts/spec-dock new artifact disc --issue iss-00123 --title "API options"         # 20260329t123459z-disc-...
./spec-dock/scripts/spec-dock new artifact decision-candidate --issue iss-00123 --title "Token options" # 20260329t123500z-decision-candidate-...
./spec-dock/scripts/spec-dock new artifact adr --issue iss-00123 --title "Token rotation"       # 20260329t123501z-adr-...
./spec-dock/scripts/spec-dock new artifact pr-repair-batch --issue iss-00123 --title "PR Repair Batch" # 20260329t123502z-pr-repair-batch-...
./spec-dock/scripts/spec-dock new artifact draft-plan --issue iss-00123 --title "Step slicing"  # 20260329t123503z-draft-plan-...

# active（現在作業中）を設定
./spec-dock/scripts/spec-dock active set 123
./spec-dock/scripts/spec-dock active set iss-00123 --checkout

# 状態集計を生成
./spec-dock/scripts/spec-dock sync
./spec-dock/scripts/spec-dock sync --no-github

# 構造チェック
./spec-dock/scripts/spec-dock validate
```

artifact 補足:
- typed artifact のファイル名 contract は `<ts>-<type>-<slug>.md`、same-second collision 時は `<ts>-<nn>-<type>-<slug>.md` です。
- `blank` artifact は filename に type token を含めず、`<ts>-<slug>.md` / `<ts>-<nn>-<slug>.md` を使います。
- legacy discussion docs の timestamp contract は `<ts>-<kind>-<slug>.md` / `<ts>-<nn>-<kind>-<slug>.md` です。
- `ts = yyyymmddthhmmssz`（UTC, lowercase `t` / `z`）、`nn = 01..99` です。
- `artifact_id` は slugless identity（typed: `<ts>-<type>` / `<ts>-<nn>-<type>`、blank: `<ts>` / `<ts>-<nn>`）で、filename stem は `<artifact_id>-<slug>` です。
- allocation 対象は valid timestamp-contract files のみです。
- unrelated files は無視されます（例: `rules.md`, `README.md`）。
- legacy sequential discussion docs（`<nnn>-<kind>-<slug>.md`）や legacy `scratch` / `note` files は grandfathered ですが、自動 rename や basename 再利用はしません。
- `scratch` / `note` は grandfathered existing artifacts only; do not create new `scratch` / `note` artifacts.
- ただし artifact intent を持つ malformed basename は explicit failure です（例: `foo-adr-kickoff.md`, `bogus-01-adr-kickoff.md`, `20260329x-adr-kickoff.md`）。
- same-second collision suffix が `99` まで埋まると失敗します。follow-up issue で archive または contract 拡張を判断してください。

注:
- `spec-dock/.agent/` と `spec-dock/active/` は生成物です（git 管理しません）。
- 導入/更新（`spec-dock/{docs,templates,scripts}` の配置）は `uvx spec-dock init/update` を使います。
