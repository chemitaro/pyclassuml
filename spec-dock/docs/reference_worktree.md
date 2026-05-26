# 作業ツリー参照（reference: worktree）

`spec-dock worktree` は、長命の手動管理 Git linked worktree を作るための補助コマンドです。
Codex app が `$CODEX_HOME/worktrees` 配下に作る短命 worktree は、このコマンドの管理対象ではありません。

## コマンド（command）

```bash
./spec-dock/scripts/spec-dock worktree create [LABEL]
```

`LABEL` は任意です。指定する場合は lowercase letters、digits、hyphen のみを使います。
underscore、dot、space、slash、uppercase、shell metacharacters は拒否されます。

## ディレクトリ構成（directory layout）

main checkout と同じ親ディレクトリに `<repo-basename>-worktrees/` を作り、その中に worktree を作ります。
main checkout の中に nested `.worktrees/` は作りません。

```text
~/workspace/tools/
  spec-dock/
  spec-dock-worktrees/
    spec-dock-wt1/
    spec-dock-feature/
```

linked worktree から実行した場合も、Git が認識する main worktree を基準に container path と repo basename を決めます。
branch name は実行元 checkout の current branch を基準にします。

## 命名（naming）

LABEL なし:

```text
id: wt1, wt2, wt3, ...
path: <repo-basename>-worktrees/<repo-basename>-<id>
branch: <current-branch>-<id>
```

LABEL あり:

```text
id: <label>, <label>2, <label>3, ...
path: <repo-basename>-worktrees/<repo-basename>-<id>
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

成功時は absolute worktree path、id、branch、bootstrap status を出力します。
bootstrap warning は既存 CLI warning path に流れます。

```text
spec-dock: ok (worktree create) id=wt1 branch=main-wt1 path=/abs/path/spec-dock-worktrees/spec-dock-wt1
spec-dock: worktree bootstrap status=skipped command=-
```

## 失敗条件（failure）

次は fatal error です。

- Git repo 外での実行。
- detached HEAD での実行。
- invalid label。
- container path の作成失敗。
- non-retryable `git worktree add` failure。
- candidate retry ceiling exhaustion。

## スコープ境界（scope boundary）

この command は create のみを扱います。
`worktree list`、`status`、`remove`、`prune`、Codex-managed worktree cleanup は future extension です。
