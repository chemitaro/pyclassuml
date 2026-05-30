# 作業ツリー参照（reference: worktree）

`spec-dock worktree` は、長命の手動管理 Git linked worktree を作るための補助コマンドです。
Codex app が `$CODEX_HOME/worktrees` 配下に作る短命 worktree は、このコマンドの管理対象ではありません。

## コマンド（command）

```bash
./spec-dock/scripts/spec-dock worktree create [LABEL]
./spec-dock/scripts/spec-dock worktree list [--json]
./spec-dock/scripts/spec-dock worktree show <target> [--json]
./spec-dock/scripts/spec-dock worktree remove <target> [--force] [--json]
```

`LABEL` は任意です。指定する場合は lowercase letters、digits、hyphen のみを使います。
underscore、dot、space、slash、uppercase、shell metacharacters は拒否されます。

`target` は `worktree list --json` が返す stable `id`、absolute path、または directory basename です。
branch name は target として扱いません。

## ディレクトリ構成（directory layout）

`worktree create` は `SPEC_DOCK_WORKTREE_ROOT` で指定した central root 配下に、repo basename の namespace directory を作り、その中に worktree を作ります。
`SPEC_DOCK_WORKTREE_ROOT` は必須です。未設定、空文字、空白のみの場合は fatal error になり、Git branch、worktree directory、bootstrap side effect は作られません。

layout:

```text
~/workspace/worktrees/
  spec-dock/
    spec-dock-wt1/
    spec-dock-feature/
```

worktree path は `$SPEC_DOCK_WORKTREE_ROOT/<repo-basename>/<repo-basename>-<id>` です。
central root directory と namespace directory は、必要に応じて command が作成します。
main checkout の中に nested `.worktrees/` は作りません。

`SPEC_DOCK_WORKTREE_ROOT` は `~` 展開後に absolute path である必要があります。
通常 directory と directory を指す symlink は許可されます。
relative path、file、壊れた symlink、directory として使えない path は fatal error です。

linked worktree から実行した場合も、Git が認識する main worktree を基準に namespace と repo basename を決めます。
branch name は実行元 checkout の current branch を基準にします。

過去バージョンで作られた sibling `<repo-basename>-worktrees/` は legacy placement です。
この command は既存 sibling worktree を移動・削除・migration しません。
future `worktree create` は central root を使い、missing env var 時に sibling placement へ fallback しません。

## 命名（naming）

LABEL なし:

```text
id: wt1, wt2, wt3, ...
path: $SPEC_DOCK_WORKTREE_ROOT/<repo-basename>/<repo-basename>-<id>
branch: <current-branch>-<id>
```

LABEL あり:

```text
id: <label>, <label>2, <label>3, ...
path: $SPEC_DOCK_WORKTREE_ROOT/<repo-basename>/<repo-basename>-<id>
branch: <current-branch>-<id>
```

directory、branch、Git worktree record の collision がある場合は次候補へ進みます。
candidate exhaustion は fatal error です。

## 初期化（bootstrap）

worktree 作成後、new worktree root で `make init` を任意 bootstrap として実行します。

- `make init` target がない場合は `skipped`。
- `make` が見つからない、Makefile parse error など detection に失敗した場合は `detection_failed` warning。
- `make init` が失敗した場合は `failed` warning。
- `make init` が成功した場合は `succeeded`。

bootstrap の detection / execution failure は worktree 作成成功を取り消さず、command exit code も `0` のままです。

## 出力（output）

`worktree create` 成功時は absolute worktree path、id、branch、bootstrap status を出力します。
bootstrap warning は既存 CLI warning path に流れます。

```text
spec-dock: ok (worktree create) id=wt1 branch=main-wt1 path=/abs/path/worktrees/spec-dock/spec-dock-wt1
spec-dock: worktree bootstrap status=skipped command=-
```

`worktree list --json` は agent-first inventory を返します。各 record は少なくとも `id`、`path`、`basename`、`branch`、`managed`、`main`、`current`、`path_exists`、`record_exists`、`removable`、`remove_blockers` を含みます。

`worktree show <target> --json` は単一 worktree record を返します。target が複数候補に一致する場合は `status=error`、`error.code=ambiguous_target`、`candidates[]` を返します。

`worktree remove <target> --json` は `resolved_target`、`removed_record`、`removed_directory`、`branch_deleted=false` を返します。
expected failure も JSON 指定時は stdout に `status=error` と `error.code` を返します。

## 失敗条件（failure）

次は fatal error です。

- Git repo 外での実行。
- detached HEAD での実行。
- invalid label。
- missing / blank `SPEC_DOCK_WORKTREE_ROOT`。
- invalid `SPEC_DOCK_WORKTREE_ROOT`。
- central root / namespace directory の作成失敗。
- non-retryable `git worktree add` failure。
- candidate retry ceiling exhaustion。
- `list` / `show` / `remove` で Git worktree list が失敗した場合。
- `show` / `remove` target が見つからない、曖昧、または branch-only target の場合。
- `remove` target が unmanaged、main、current、bare、missing path、または containment guard 違反の場合。
- `remove` target に dirty / untracked / locked state があり、Git が `git worktree remove` を拒否した場合。

## 削除（remove）

`worktree remove` は SpecDock managed namespace 配下の linked worktree だけを対象にします。
main checkout、current checkout、unmanaged worktree は `--force` を付けても削除しません。

削除は Git-first です。まず `git worktree remove` を実行し、Git が成功した後だけ、残った individual worktree directory を filesystem cleanup します。
Git が dirty / untracked / locked state を理由に通常 remove を拒否した場合、SpecDock はその Git error を表示し、filesystem cleanup は行いません。
`--force` は Git force removal にだけ対応します。locked worktree など Git がより強い force depth を要求する場合の具体的な Git flag depth は adapter 内部詳細です。SpecDock の managed/current/main/unmanaged guard は bypass しません。

branch は削除しません。成功 JSON の `branch_deleted` は常に `false` です。
`worktree delete` alias はありません。

## スコープ境界（scope boundary）

この command family は create / list / show / remove のみを扱います。
`worktree status`、`prune`、`repair`、Codex-managed worktree cleanup は future extension です。
