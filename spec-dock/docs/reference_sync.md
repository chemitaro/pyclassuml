# 状態集計参照（reference: sync）

対象コマンド:

```bash
./spec-dock/scripts/spec-dock sync [--github] [--gh-limit N] [--no-update-active] [--force]
./spec-dock/scripts/spec-dock sync --no-github [--no-update-active] [--force]
```

関連:
- 入口: [README.md](README.md)
- 総合: [guide.md](guide.md)
- deps: [reference_deps.md](reference_deps.md)

## 1. 結論（v2の生成物）

`sync` はローカル SSOT（`spec-dock/initiatives/**/.meta.json`）を走査し、v2 の観測点を生成します（git 管理しない）。
`meta.json`（レガシー名）はサポート対象外で、検出時はエラー停止します（`.meta.json` へ手動移行してください）。
依存更新は `./spec-dock/scripts/spec-dock deps add/remove/check` を使い、実行後は `./spec-dock/scripts/spec-dock validate` と `./spec-dock/scripts/spec-dock sync` で GitHub live state を含めて整合を確認します。

`.agent/`（機械向け）:
- `spec-dock/.agent/index-all.json`（全ノード）
- `spec-dock/.agent/tree-all.json`（全ノードのツリー）
- `spec-dock/.agent/index.json`（todo projection）
- `spec-dock/.agent/tree.json`（todo projection のツリー）
- `spec-dock/.agent/deps-issues.json`（schema v2 readiness / blocker context）

agent-facing の読取契約:
- entry: `spec-dock/.agent/active.json`
- normal default working set: `spec-dock/.agent/index.json` + `spec-dock/.agent/deps-issues.json`
- escalation only: `spec-dock/.agent/index-all.json`（full-history / audit / search）
- `spec-dock/active/context-pack.md` はこの順序を案内する human guidance であり、唯一正本ではない

`spec-dock/` 直下（人間向け）:
- `spec-dock/tree-all.puml`（Readyボード, all）
- `spec-dock/tree.puml`（Readyボード, todo）
- `spec-dock/deps-issues.puml`（readiness / blocker context 依存図）
- `spec-dock/deps-raw.puml`（raw direct dependency visual/debug 可視化）
- `spec-dock/dashboard.md`（todo要約）

legacy v1 生成物（廃止）:
- `spec-dock/.agent/deps.json`
- `spec-dock/.agent/deps.puml`
- `spec-dock/.agent/deps.todo.puml`

上記3つは `sync` 実行時に常に削除されます（stale防止）。

uninstall との関係:
- `spec-dock/active/**` と `spec-dock/.agent/**` は `sync` / active 更新で再生成される状態であり、repo-local uninstall では generated state として cleanup 対象になります
- uninstall は GitHub state や package/environment/`uvx` cache を変更しません。repo-local runtime が削除済みの場合の再実行や復旧は installer CLI の `spec-dock uninstall <target>` / `spec-dock init <target>` / `spec-dock update <target>` を使います

## 2. 全体 / TODO 投影（all / todo projection）

`*-all.json` は全件を保持します。

`index.json` / `tree.json` は todo projection です:
- `status==done` の issue を除外
- todo issue が0件の epic / initiative を除外（empty枝除外）
- `deps.issue_edges` は端点が todo issue の edge のみ保持
- `index.json` と `tree.json` のノード集合は一致

## 3. 依存情報の埋め込み（deps）

`index-*.json` / `tree-*.json` のトップレベルには `deps` が入り、少なくとも以下を持ちます:
- `valid: bool`
- `error: string | null`
- `issue_edges: [{from,to,kind?}]`
- `edge_direction: "depends_on (dependent -> prerequisite)"`

`.agent/index-all.json` の各 node には top-level `depends_on` として `.meta.json.depends_on` から解決した canonical raw direct dependency target ids を保持します。`index.json` / `tree.json` の todo projection と tree artifacts にはこの raw audit field を出しません。issueノードにはこれとは別に readiness projection の `deps`（`ready`, `depends_on`, `blockers_top`）を統合します。

`spec-dock/.agent/deps-issues.json` は `index.json` の todo issue-only graph を再パースした派生物ではありません。`sync_state` の readiness evaluation から生成する schema v2 artifact です。GitHub `open` / `closed` は lifecycle fact であり、dependency readiness の `blocking` / `satisfied` / `indeterminate` は `dependency_disposition` と `disposition_basis` で表します。

主な契約:
- `schema_version: 2`
- `projection: "issue-readiness-with-dependency-context"`
- `source.sync_state: "readiness_evaluation"`
- issue-level blocker、node-level blocker、satisfied dependency を区別できる typed context を含む
- `nodes` / `edges` は active readiness graph として、open / unknown issue nodes、readiness を説明する issue blocker nodes、node-level blocker の initiative / epic nodes、active blocking edges を含める
- `dependency_contexts` は evaluated high-level dependency context として、GitHub-open all-descendant-done、closed high-level、empty-open high-level などの lifecycle / disposition / basis を保持する

high-level dependency の主な判定:
- GitHub open かつ descendant issue が 0 件の initiative / epic は `dependency_disposition=blocking`, `disposition_basis=empty_open_container` で node blocker になります。
- GitHub open でも full graph descendant issue が存在し、その全てが done / closed なら `dependency_disposition=satisfied`, `disposition_basis=all_descendant_issues_done` です。
- GitHub closed または local done の high-level node は satisfied です。
- unknown は fail-closed です。unknown high-level target や unknown descendant issue は indeterminate として扱います。

`.meta.json.depends_on` は raw storage のままです。empty initiative / epic dependency は raw validation を通れば保存できますが、readiness evaluation では open / unknown の empty high-level target が node blocker になり、done / closed / all-descendant-done の context は satisfied dependency として扱われます。

## 4. `sync --force`（deps preflight失敗時）

deps 構造エラー（未解決参照 / self / cycle / descendant依存 / schema不正など）がある場合:
- 通常 `sync`: 失敗（非0）
- `sync --force`: index/tree 更新は継続し、`deps_preflight_failed` を warn + warnings に出力

`--force` で deps 無効化時の挙動:
- `index-*.json` / `tree-*.json`: `deps.valid=false`, `deps.issue_edges=[]`, `deps.error` を設定
- issueノードの `deps` は `null`（未計算扱い）
- `spec-dock/.agent/deps-issues.json` は placeholder（`deps.valid=false`, `nodes={}`, `edges=[]`）で上書き
- `spec-dock/deps-issues.puml`, `spec-dock/deps-raw.puml`, `spec-dock/tree*.puml`, `spec-dock/dashboard.md` も placeholder内容で上書き
- `--force` はデバッグ/リカバリ用途のため、depsの成否に関わらず active auto-update を無効化（`--no-update-active` 相当）

削除ではなく上書きにすることで、stale 参照を防ぎます。
raw node-level cycle などで deps preflight が失敗した場合、この placeholder path は fail-closed です。placeholder を partial readiness authority として読まず、構造エラーを解消してから通常の `sync` を再実行してください。
`--force` 実行後に active を更新したい場合は、`./spec-dock/scripts/spec-dock active set <target>` を使って明示更新してください。

## 5. GitHub の既定動作（GitHub default）と `--no-github`

`sync` / `sync --github`:
- `gh issue list` の読み取り結果で issue status を enrich（OPEN/CLOSED -> open/done）
- `--github` は後方互換 flag で、flag なしの `sync` と同じ GitHub enabled mode です

`sync --no-github`:
- GitHubへアクセスしない
- 既存スナップショットを使う場合は `index-all.json` を優先し、無ければ `index.json` へ fallback
- どちらも無ければ issue status は `unknown`
- この `index-all.json -> index.json` は issue status 補完のための runtime 内部 fallback であり、agent-facing の通常読取順ではない

`--github` と `--no-github` は同時に指定できません。

## 6. アクティブ更新（active update）

デフォルトでは、ブランチ名から active を best-effort 推定して更新します。

- `sync --no-update-active`: active を更新しない
- `sync --force`: `--no-update-active` 相当として扱い、active auto-update を行わない
- `main` / `develop` など手がかりが無いブランチでは active は維持
- active が未設定でも entry contract は `spec-dock/.agent/active.json` のままで、`spec-dock/active/context-pack.md` は placeholder README への human guidance を表示する

## 7. 矢印方向（JSONとPlantUML）

- JSON（`deps.issue_edges`）: `depends_on` 方向（`dependent -> prerequisite`）
- `deps-issues.puml`: blocks 表示（`prerequisite -> dependent`）
- `deps-raw.puml`: `.meta.json.depends_on` の raw direct edge を node/package endpoint で表示（`prerequisite -> dependent`）

`deps-issues.*` は readiness / blocker 判定に使う authority です。schema v2 の `deps-issues` は typed issue blockers、typed node blockers、satisfied dependencies を含み、todo-only `index.json` から消える context も `dependency_contexts` に保持します。
`deps-issues.puml` は active readiness / blocker view です。done / closed / satisfied-only node/edge は `.agent/deps-issues.json` に context を残し、図では表示ノイズとして省きます。blocking edge は `blocks` として表示します。
`deps-raw.puml` は initiative / epic / issue を含む active raw direct dependency の visual/debug artifact です。high-level participant の state / source を表示できますが、readiness authority ではありません。done / closed / satisfied-only raw context は active raw view から省かれることがあります。complete raw metadata audit は `.meta.json.depends_on` と `.agent/index-all.json` の `nodes[*].depends_on` を確認してください。
同じ依存を、機械向けと可視化向けで向きを分けて表現しています。

## 8. 処理フロー（PlantUML）

```plantuml
@startuml
skinparam monochrome true
hide footbox

actor User
participant "spec-dock\n(runtime script)" as Script
participant "Local FS\n(.meta.json)" as FS
participant "git\n(branch)" as Git
participant "gh\n(GitHub CLI)" as GH
database ".agent/index-all.json" as IndexAll
database ".agent/index.json" as IndexTodo
database ".agent/deps-issues.json" as DepsIssues

User -> Script: sync [flags]
Script -> FS: scan .meta.json
Script -> Script: preflight validate
Script -> Script: deps preflight

alt update_active (default)
  Script -> Git: current branch
  Script -> Script: infer active (best-effort)
end

alt default / --github
  Script -> GH: gh issue list ...
  Script -> Script: enrich statuses
else --no-github
  Script -> Script: use index-all -> index snapshot
end

alt deps preflight ok
  Script -> IndexAll: write(all)
  Script -> IndexTodo: write(todo)
  Script -> DepsIssues: write(valid=true)
else deps preflight failed and --force
  Script -> IndexAll: write(deps.valid=false)
  Script -> IndexTodo: write(deps.valid=false)
  Script -> DepsIssues: write(placeholder)
end
@enduml
```

## 9. ハードカットオーバー検証契約（hard cutover verification contract / iss-00062 / iss-00063）

- hard cutover entry 条件は `docs 更新 + checked-in data manual fix + validate/sync evidence` の 3 点を満たしたときだけ充足です。
- `validate` / `sync` evidence は少なくとも次を issue-level `report.md` に記録します:
  - 実行コマンド
  - exit code
  - pass/fail
  - 結果要約（targeted regression summary を含む）
- `iss-00062`（T3 integration）が entry 条件と hard cutover judgment の primary owner、`iss-00063`（T4 closure）はその judgment を前提に final parity / close review を行う follow-up owner です。
- この split は no fallback / no dual-read / `.meta.json` only contract を維持するための固定境界であり、T4 側で entry 条件や verdict を再定義しません。
