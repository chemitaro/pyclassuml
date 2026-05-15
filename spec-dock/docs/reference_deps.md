# reference: deps（依存関係管理）

対象コマンド:

```bash
./spec-dock/scripts/spec-dock deps check <target> [--github|--no-github] [--gh-limit N] [--json]
./spec-dock/scripts/spec-dock deps check --id <node-id> [--github|--no-github] [--gh-limit N] [--json]
./spec-dock/scripts/spec-dock deps check --github-issue <n> [--github|--no-github] [--gh-limit N] [--json]
./spec-dock/scripts/spec-dock deps add --from <node-id> --to <node-id>
./spec-dock/scripts/spec-dock deps remove --from <node-id> --to <node-id>
./spec-dock/scripts/spec-dock active set <target> [--github|--no-github] [--gh-limit N] [--force|-f] [--checkout]
./spec-dock/scripts/spec-dock active set --id <node-id> [--github|--no-github] [--gh-limit N] [--force|-f] [--checkout]
./spec-dock/scripts/spec-dock active set --github-issue <n> [--github|--no-github] [--gh-limit N] [--force|-f] [--checkout]
./spec-dock/scripts/spec-dock sync [--github|--no-github] [--gh-limit N] [--no-update-active] [--force]
```

関連:
- 入口: [README.md](README.md)
- 総合: [guide.md](guide.md)
- sync: [reference_sync.md](reference_sync.md)

## 1. 結論（v3）

- canonical storage は node 直下 `.meta.json` の top-level `depends_on` です。
- reader（`infra/deps_reader.py`）は `.meta.json` だけを読み、`deps.json` dual-read / auto-migration は行いません。
- runtime mutation surface は `deps add --from <id> --to <id>` と `deps remove --from <id> --to <id>` です。
- mutation 対象は existing issue node から existing issue node への direct edge のみです。
- current graph validation は duplicate add / remove not-found / node kind 判定より先に走り、失敗時は `preflight_validate_failed` error で no-write です。
- healthy graph に対する duplicate add は success/no-op で、CLI は `result=unchanged` を返します。
- `deps remove` の edge 不在は success/no-op に丸めず `edge_not_found` error です。
- `depends_on` の field absence は `[]` と同義です。
- raw value grammar は既存 shorthand に限定し、node id / GitHub issue number（int または numeric string）/ `owner/repo#123` / canonical issue URL のみを許可します。
- shorthand は canonical な issue->issue direct edge にコンパイルされ、downstream consumer は既存 `DepsTopologyLoadResult` surface を継続利用します。
- add/remove は `.meta.json` だけを書き換え、write failure 時も partial write を残さない atomic replace を前提にします。
- rollback は compatibility mode ではなく issue diff revert 前提です。

## 2. `.meta.json`（ノード直下 / 任意）

配置場所:
- initiative: `<initiative-dir>/.meta.json`
- epic: `<epic-dir>/.meta.json`
- issue: `<issue-dir>/.meta.json`

スキーマ例:

```json
{
  "schema_version": 1,
  "type": "issue",
  "id": "iss-00100",
  "title": "Example issue",
  "slug": "example-issue",
  "depends_on": [
    "iss-00123",
    "epic-local-00001",
    456,
    "789",
    "owner/repo#123",
    "https://github.com/owner/repo/issues/123"
  ]
}
```

ルール:
- `depends_on` は optional top-level field です
- field absence は `[]` と同義です
- `depends_on` 要素は node id、GitHub issue番号（int / numeric string）、repo-scoped ref（`owner/repo#123` / canonical issue URL）に限定されます
- shorthand は最終的に issue->issue edge へ還元されます
- reader は `.meta.json` だけを読み、legacy `deps.json` は migration 入力にも fallback read source にもしません

構造エラー（fail-fast）:
- JSONパース不正 / top-level object 不正 / `depends_on` の型不正
- unsupported element type / unsupported string
- 未解決参照
- 親->配下（descendant）依存
- 自己依存（shorthand展開で生じる implicit self も含む）

補足:
- shorthand 展開結果が空でもエラーにはせず、warning `deps_ref_expanded_to_empty` を出します。
- no dual-read / no auto-migration / rollback-by-revert を前提にします。

## 3. reader contract

- `infra/deps_reader.py` は node 直下 `.meta.json` から `depends_on` を読みます。
- shorthand 解決、issue-level direct edge compile、dedupe、deterministic sort、descendant/self reject、warning `deps_ref_expanded_to_empty` は current contract を維持します。
- downstream consumer 向けの return shape は既存 `DepsTopologyLoadResult(issue_depends_on_map, warnings)` のままです。
- `deps add/remove` の mutation contract は次節の通りで、delete scrub と `validate` / `sync` / `active set` parity の詳細はこの reference の主題に含めません。

## 4. mutation contract

コマンド surface:

```bash
./spec-dock/scripts/spec-dock deps add --from <node-id> --to <node-id>
./spec-dock/scripts/spec-dock deps remove --from <node-id> --to <node-id>
```

契約:
- add/remove ともに current graph preflight-first です。この preflight は dependency graph consistency を対象とし、GitHub mandatory linkage は mutation preflight では強制しません（local-compat mode、`enforce_github_mandatory_linkage=False`）。graph が壊れている場合は duplicate add / remove not-found / non-issue node 判定より前に `preflight_validate_failed` error で終了します。
- `--from` / `--to` は existing issue node id のみを受け付けます。existing initiative / epic など non-issue node は `unsupported_node_kind` error です。
- duplicate add / remove not-found の存在判定は compiled dependency / inherited dependency ではなく、`from` node 直下 `.meta.json.depends_on` に保持された raw direct ref の有無を基準にします。
- `deps add` は healthy graph に限り duplicate edge を success/no-op とし、CLI は `spec-dock: ok (deps add) ... result=unchanged` を返します。依存配列へ同一 edge を重複保存しません。
- `deps remove` は healthy graph でも対象 edge が無ければ `edge_not_found` error です。remove not-found を no-op success にはしません。
- add/remove 成功時の CLI は `from=<id> to=<id> result=updated` を返します。
- mutation write path は node 直下 `.meta.json` の `depends_on` のみです。`deps.json` fallback write や互換モードはありません。
- write failure は `write_failed` error で返し、temp file + replace の atomic write により partial write を残しません。rollback は compatibility mode ではなく issue diff revert 前提です。

## 5. downstream boundary note

- `deps check`、`active set`、`validate`、`sync`、`delete` は compiled dependency result を消費する downstream consumer です。
- 運用では `deps add/remove` の後に `./spec-dock/scripts/spec-dock deps check <target>`、`./spec-dock/scripts/spec-dock validate`、`./spec-dock/scripts/spec-dock sync` を順に実行して、標準の GitHub live state で整合を確認します。GitHub を呼ばない cache/local 確認が必要な場合だけ `--no-github` を指定します。
- この文書は `.meta.json` schema / reader / `deps check` / `deps add/remove` の command contract を固定するもので、downstream parity や hard cutover 完了を意味しません。
- provider-side のこのファイルが dependency reference の正本であり、dogfooding 側 copy は secondary verification です。

## 6. migration / rollback guardrails

- no dual-read: reader は `.meta.json` のみを対象にし、`deps.json` fallback read を持ちません。
- no auto-migration: runtime は `deps.json` から `.meta.json` への自動変換・救済を行いません。
- rollback-by-revert: compatibility mode は導入せず、issue diff revert で戻します。

## 7. hard cutover owner boundary

- legacy `deps.json` checked-in data manual fix と dogfooding `./spec-dock/scripts/spec-dock validate` / `sync` evidence、hard cutover judgment の primary owner は `iss-00062` です。
- `iss-00060` / `iss-00061` がこの reference で固定するのは `.meta.json` schema、reader contract、mutation command contract、provider-side dependency docs 正本更新までです。

## 8. hard cutover entry contract（T3/T4 split）

- hard cutover entry 条件は次の 3 点に固定します:
  - docs 更新（provider-side 正本 + dogfooding mirror）
  - checked-in dogfooding data の legacy `deps.json` manual fix
  - `./spec-dock/scripts/spec-dock validate` と `./spec-dock/scripts/spec-dock sync` の実測 evidence
- manual fix は checked-in data の修正に限定し、runtime fallback / dual-read / auto-migration は導入しません。
- hard cutover judgment の primary owner は T3 integration issue（`iss-00062`）です。T4 closure issue（`iss-00063`）は T3 judgment を参照して final parity / close review を実施します。
- cutover evidence の fixed-key contract（`cutover_entry.*` / `cutover_judgment.*`、`targeted_regression_summary` 含む）は `workflow_issue.md` を正本として追跡します。
