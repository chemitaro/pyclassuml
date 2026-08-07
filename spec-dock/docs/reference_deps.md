# 依存関係管理参照（reference: deps）

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
- mutation 対象は existing initiative / epic / issue node から existing initiative / epic / issue node への direct edge です。
- current graph validation は duplicate add / remove not-found / semantic validation より先に走り、失敗時は `preflight_validate_failed` error で no-write です。
- healthy graph に対する duplicate add は success/no-op で、CLI は `result=unchanged` を返します。
- duplicate add は source node 直下 `.meta.json.depends_on` に重複 ref を保存しません。
- `deps remove` の edge 不在は success/no-op に丸めず `edge_not_found` error です。
- `deps remove` は source node 直下の direct edge だけを削除します。inherited / compiled-only edge は削除対象ではなく `edge_not_found` です。
- `depends_on` の field absence は `[]` と同義です。
- raw value grammar は既存 shorthand に限定し、node id / GitHub issue number（int または numeric string）/ `owner/repo#123` / canonical issue URL のみを許可します。
- shorthand は canonical な node-level direct edge として解決され、downstream consumer 向けには既存の issue-level `DepsTopologyLoadResult` surface へコンパイルされます。
- raw node-level self / ancestor-container / descendant / cycle と、candidate compiled issue-level cycle / self-edge は保存前に拒否されます。
- empty initiative / epic dependency は raw node-level validation を通れば保存できます。storage format は変えず、`.meta.json.depends_on` は raw direct dependency の保存場所のままです。
- issue-level expansion が空の場合でも、readiness は high-level node status を評価します。open / unknown の empty initiative / epic は node-level blocker になり、done / closed / all-descendant-done の context は satisfied dependency として扱います。
- GitHub の `open` / `closed` は lifecycle fact であり、SpecDock dependency readiness の `blocking` / `satisfied` / `indeterminate` と同義ではありません。readiness は `dependency_disposition` と `disposition_basis` で説明します。
- `deps-issues.*` は readiness / blocker authority で、`deps-raw.puml` は active raw direct visual/debug artifact です。`deps-raw.puml` に high-level state/source が表示されても readiness authority ではありません。
- `deps-issues.puml` と `deps-raw.puml` は active view です。done / closed / satisfied-only context は `.agent/deps-issues.json` の machine-readable context に残しつつ、図では表示ノイズとして省くことがあります。
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
- initiative / epic / issue への direct edge は raw storage として保持されます。empty initiative / epic target も、下記の構造エラーに該当しなければ保存できます。

構造エラー（fail-fast）:
- JSONパース不正 / top-level object 不正 / `depends_on` の型不正
- unsupported element type / unsupported string
- 未解決参照
- raw node-level 自己依存
- ancestor-container 依存
- descendant 依存
- raw node-level cycle
- candidate compiled issue-level cycle / self-edge

補足:
- shorthand 展開結果が空でも storage error にはせず、warning `deps_ref_expanded_to_empty` を出すことがあります。ただし readiness は warning だけでは決まりません。open / unknown の empty high-level target は node-level blocker、done / closed / all-descendant-done の target は satisfied dependency です。
- no dual-read / no auto-migration / rollback-by-revert を前提にします。

## 3. 判定状態（lifecycle / disposition / readiness evaluation）

`lifecycle_state` は GitHub / local state から得る lifecycle fact です。`dependency_disposition` は、その fact と full graph descendant issue を使って dependency readiness 上の意味を決めた結果です。

| 高水準対象（high-level target） | `lifecycle_state` | 子 issue 数（descendant issue count） | 子 issue 状態（descendant state） | `dependency_disposition` | `disposition_basis` | ブロック面（blocker surface） |
|---|---|---:|---|---|---|---|
| `initiative / epic` | `open` | 0 | `N/A` | `blocking` | `empty_open_container` | `node_blocker` |
| `initiative / epic` | `unknown` | 0 | `N/A` | `indeterminate` | `empty_unknown_container` | `node_blocker` |
| `initiative / epic` | `closed` | `any` | `any` | `satisfied` | `lifecycle_closed` | `none` |
| `initiative / epic` | `done` | `any` | `any` | `satisfied` | `local_done` | `none` |
| `initiative / epic` | `open` | `>0` | `all done / closed` | `satisfied` | `all_descendant_issues_done` | `none` |
| `initiative / epic` | `open` | `>0` | `any open / ready / blocked` | `blocking` | `descendant_issue_open` | `descendant issue blockers` |
| `initiative / epic` | `open` | `>0` | `any unknown` | `indeterminate` | `descendant_issue_unknown` | `descendant issue unknown` |

descendant issue は todo projection ではなく full graph で数えます。done issue が `index.json` から消えていても、all-descendant-done 判定では descendant issue として扱います。

unknown は fail-closed です。unknown high-level target や unknown descendant issue は、明示的に satisfied と判断できるまで ready 扱いしません。

## 4. 読み取り契約（reader contract）

- `infra/deps_reader.py` は node 直下 `.meta.json` から `depends_on` を読みます。
- shorthand 解決、issue-level edge compile、dedupe、deterministic sort、descendant/self reject、warning `deps_ref_expanded_to_empty` は current contract を維持します。
- downstream consumer 向けの issue-level compiled dependency は `issue_depends_on_map` として維持します。raw node dependency context は readiness evaluation が node blocker / satisfied dependency を判断できるように保持されます。
- reader は storage / topology facts を返すだけで、readiness authority ではありません。open / unknown / done / closed / all-descendant-done の解釈は readiness evaluation 側で行います。
- `deps add/remove` の変更契約（mutation contract）は次節の通りで、delete scrub と `validate` / `sync` / `active set` parity の詳細はこの reference の主題に含めません。

## 5. 変更契約（mutation contract）

コマンド surface:

```bash
./spec-dock/scripts/spec-dock deps add --from <node-id> --to <node-id>
./spec-dock/scripts/spec-dock deps remove --from <node-id> --to <node-id>
```

契約:
- add/remove ともに current graph preflight-first です。この preflight は dependency graph consistency を対象とし、GitHub mandatory linkage は mutation preflight では強制しません（local-compat mode、`enforce_github_mandatory_linkage=False`）。graph が壊れている場合は duplicate add / remove not-found / semantic validation より前に `preflight_validate_failed` error で終了します。
- `--from` / `--to` は existing initiative / epic / issue node id を受け付けます。
- add は source node 直下 `.meta.json.depends_on` に target node id を direct ref として保存します。remove は source node 直下 `.meta.json.depends_on` から matching direct ref だけを削除します。
- duplicate add / remove not-found の存在判定は compiled dependency / inherited dependency ではなく、`from` node 直下 `.meta.json.depends_on` に保持された raw direct ref の有無を基準にします。
- `deps add` は healthy graph に限り duplicate edge を success/no-op とし、CLI は `spec-dock: ok (deps add) ... result=unchanged` を返します。依存配列へ同一 edge を重複保存しません。
- `deps remove` は healthy graph でも direct edge が無ければ `edge_not_found` error です。remove not-found を no-op success にはしません。inherited / compiled-only edge は direct edge とみなしません。
- raw node-level self / ancestor-container / descendant / cycle と、candidate compiled issue-level cycle / self-edge は保存前に拒否され、no-write で終了します。exact self は `invalid_add_self_dependency`、ancestor / descendant / raw cycle / compiled cycle は `invalid_add_cycle` です。
- Empty initiative / epic など、source または target 配下に issue がまだ存在しない場合でも、raw node-level validation を通る direct dependency は保存できます。保存時点で storage format は変わりません。readiness evaluation では open / unknown の empty high-level target は node-level blocker、done / closed / all-descendant-done の target は satisfied dependency です。
- add/remove 成功時の CLI は `from=<id> to=<id> result=updated` を返します。
- mutation write path は node 直下 `.meta.json` の `depends_on` のみです。`deps.json` fallback write や互換モードはありません。
- write failure は `write_failed` error で返し、temp file + replace の atomic write により partial write を残しません。rollback は compatibility mode ではなく issue diff revert 前提です。

## 6. 下流境界メモ（downstream boundary note）

- `deps check`、`active set`、`validate`、`sync`、`delete` は compiled dependency result を消費する downstream consumer です。
- `deps check` / `active set` / `issue start` / `sync` の readiness interpretation は、issue blockers、node blockers、satisfied dependencies、unknown fail-closed を含む同じ readiness evaluation に基づきます。
- `.agent/deps-issues.json` は schema v2 の readiness / blocker context artifact です。`projection` は `issue-readiness-with-dependency-context`、`source.sync_state` は `readiness_evaluation` です。
- `deps-issues` には typed issue blockers、typed node blockers、satisfied dependencies が含まれます。todo-only `index.json` の再パース結果ではありません。
- `.agent/deps-issues.json` の `nodes` / `edges` は active readiness graph です。done / closed / satisfied-only context は active graph から省かれることがあります。
- `.agent/deps-issues.json` の `dependency_contexts` は evaluated high-level dependency context を保持します。GitHub-open all-descendant-done high-level dependency など、図に出ない satisfied context の確認先です。
- `.agent/index-all.json` は各 node payload の top-level `depends_on` に canonical raw direct dependency target ids を保持します。source / target kind は `nodes[source].type` と `nodes[target].type` を join して取得します。
- `sync` が生成する `deps-issues.puml` は active readiness / blocker view です。blocking edge は user-facing label `blocks` で表示し、done / closed / satisfied-only edge は表示ノイズとして省きます。
- `sync` が生成する `deps-raw.puml` は `.meta.json.depends_on` の active raw direct dependency を可視化する確認用 artifact です。high-level node の state / source を表示できますが、readiness / blocker 判定の authority は `deps-issues.*` 側にあります。complete raw metadata audit は `.meta.json.depends_on` と `.agent/index-all.json` の `nodes[*].depends_on` を確認します。
- raw node-level cycle などの deps preflight failure や disabled path は fail-closed です。`sync --force` では stale graph を残さない placeholder が出力され、partial readiness authority として読んではいけません。
- 運用では `deps add/remove` の後に `./spec-dock/scripts/spec-dock deps check <target>`、`./spec-dock/scripts/spec-dock validate`、`./spec-dock/scripts/spec-dock sync` を順に実行して、標準の GitHub live state で整合を確認します。GitHub を呼ばない cache/local 確認が必要な場合だけ `--no-github` を指定します。
- この文書は `.meta.json` schema / reader / `deps check` / `deps add/remove` の command contract を固定するもので、downstream parity や hard cutover 完了を意味しません。
- provider-side のこのファイルが dependency reference の正本であり、dogfooding 側 copy は secondary verification です。

## 7. 移行 / ロールバックのガードレール（migration / rollback guardrails）

- no dual-read: reader は `.meta.json` のみを対象にし、`deps.json` fallback read を持ちません。
- no auto-migration: runtime は `deps.json` から `.meta.json` への自動変換・救済を行いません。
- rollback-by-revert: compatibility mode は導入せず、issue diff revert で戻します。

## 8. ハードカットオーバーの所有境界（hard cutover owner boundary）

- legacy `deps.json` checked-in data manual fix と dogfooding `./spec-dock/scripts/spec-dock validate` / `sync` evidence、hard cutover judgment の primary owner は `iss-00062` です。
- `iss-00060` / `iss-00061` がこの reference で固定するのは `.meta.json` schema、読み取り契約（reader contract）、変更コマンド契約（mutation command contract）、provider-side dependency docs 正本更新までです。

## 9. ハードカットオーバー開始契約（hard cutover entry contract / T3/T4 split）

- hard cutover entry 条件は次の 3 点に固定します:
  - docs 更新（provider-side 正本 + dogfooding mirror）
  - checked-in dogfooding data の legacy `deps.json` manual fix
  - `./spec-dock/scripts/spec-dock validate` と `./spec-dock/scripts/spec-dock sync` の実測 evidence
- manual fix は checked-in data の修正に限定し、runtime fallback / dual-read / auto-migration は導入しません。
- hard cutover judgment の primary owner は T3 integration issue（`iss-00062`）です。T4 closure issue（`iss-00063`）は T3 judgment を参照して final parity / close review を実施します。
- cutover evidence の fixed-key contract（`cutover_entry.*` / `cutover_judgment.*`、`targeted_regression_summary` 含む）は `workflow_issue.md` を正本として追跡します。
