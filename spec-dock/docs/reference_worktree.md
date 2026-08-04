# 作業ツリー参照（reference: worktree）

`spec-dock worktree` は、長命の Git linked worktree を作成・一覧・参照・削除するための補助コマンドです。
同一 repository の Git linked worktree であれば、SpecDock が作成したものでも、手動作成や Codex app が作成した外部 worktree でも `list` / `show` / `remove` の対象になります。
ただし Codex 固有の lifecycle、metadata、cleanup policy は扱いません。

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
`SPEC_DOCK_WORKTREE_ROOT` は `worktree create` では必須です。未設定、空文字、空白のみの場合は fatal error になり、Git branch、worktree directory、bootstrap side effect は作られません。

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

`worktree create` の `SPEC_DOCK_WORKTREE_ROOT` は `~` 展開後に absolute path である必要があります。
通常 directory と directory を指す symlink は許可されます。
relative path、file、壊れた symlink、directory として使えない path は fatal error です。

`worktree list` / `show` / `remove` は Git worktree records を正本として動作します。
これらの command では `SPEC_DOCK_WORKTREE_ROOT` は managed 判定のための optional context です。
未設定、空文字、invalid root、namespace symlink の場合でも Git records は一覧・参照・削除対象として扱われ、managed 判定は `classification_unavailable` diagnostic として出力されます。

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

`worktree list --json` は agent-first inventory を返します。各 record は少なくとも `id`、`path`、`basename`、`branch`、`managed`、`managed_classification_available`、`classification_reason`、`origin`、`main`、`current`、`path_exists`、`record_exists`、`removable`、`remove_blockers` を含みます。

classification diagnostics:

- `managed` は boolean のまま維持されます。
- `managed_classification_available=false` の場合、`managed=false` は external ではなく「判定不可」を表します。
- `classification_reason` は `root_valid`、`root_missing`、`root_blank`、`root_invalid`、`namespace_symlink` のいずれかです。
- `origin` は `spec_dock_managed`、`external`、`classification_unavailable` のいずれかです。

`worktree show <target> --json` は単一 worktree record を返します。target が複数候補に一致する場合は `status=error`、`error.code=ambiguous_target`、`candidates[]` を返します。
`candidates[]` と remove blocker error の embedded `worktree` も同じ classification diagnostics を含みます。

`worktree remove <target> --json` は `resolved_target`、`removed_record`、`removed_directory`、`branch_deleted=false` を返します。
expected failure も JSON 指定時は stdout に `status=error` と `error.code` を返します。

## 失敗条件（failure）

次は fatal error です。

- Git repo 外での実行。
- detached HEAD での実行。
- invalid label。
- `worktree create` での missing / blank `SPEC_DOCK_WORKTREE_ROOT`。
- `worktree create` での invalid `SPEC_DOCK_WORKTREE_ROOT`。
- central root / namespace directory の作成失敗。
- non-retryable `git worktree add` failure。
- candidate retry ceiling exhaustion。
- `list` / `show` / `remove` で Git worktree list が失敗した場合。
- `show` / `remove` target が見つからない、曖昧、または branch-only target の場合。
- `remove` target が main、current、bare、missing path、または record missing の場合。
- `remove` target が locked state などで Git の force-equivalent remove に拒否された場合。
- Git remove 成功後の target cleanup が unsupported type、permission、race、`lstat` / `unlink` / `rmtree` failure になった場合。

## 削除（remove）

`worktree remove` は Git worktree records に存在する linked worktree を対象にします。
SpecDock が `worktree create` で作った managed worktree だけでなく、external linked worktree も削除できます。
main checkout、current checkout、bare worktree、missing path、record missing は `--force` を付けても削除しません。
containment guard により protected cleanup path と判定された target も削除しません。

削除は Git-first です。まず `git worktree remove` を実行し、Git が成功した後だけ、resolved target path に残った target を filesystem cleanup します。
cleanup は target-only です。parent directory、central root、namespace directory、repo root は削除しません。
directory は tree removal、symlink / broken symlink / regular file は symlink target を follow せず target 自体を unlink します。
eligible linked worktree は option なしで完全削除 default として扱われ、dirty / untracked file / tracked modification を含んでいても Git worktree record と resolved target path を削除します。
`--force` は後方互換のため受け付ける入力です。完全削除を有効にする必須 option ではなく、default remove と同じ成功条件・失敗条件・出力契約を満たします。
locked worktree などで Git が force-equivalent remove を拒否した場合、SpecDock はその Git error を表示し、filesystem cleanup は行いません。具体的な Git flag depth は adapter 内部詳細です。

branch は削除しません。成功 JSON の `branch_deleted` は常に `false` です。
`worktree delete` alias はありません。

## Scoped Workbench handoff（experimental）

Workbench は任意です。optional、temporary、worktree-local、disposable、non-canonical な作業領域です。`.workbench/README.md` は direct child の README-only tracking surface で、その他の Workbench entry は ignored payload として Git に ignore されます。Git ignore は security boundary ではありません。Workbench content の read / import authorization は evidence-only であり、canonical adoption ではありません。

tracked `.workbench/README.md` は root / node とも通常の Git checkout で linked worktree に現れます。ignored payload は checkout では移らず、copy の対象は node-scoped payload に限られます。

```bash
./spec-dock/scripts/spec-dock workbench copy --scope <initiative|epic|issue-id> --to <target>
```

`--to`は`worktree show`と同じstable id、absolute path、またはdirectory basenameで既存linked worktreeを指定します。`--scope`はsource worktreeに存在するfull Initiative / Epic / Issue idです。Initiative / Epic / Issue の ignored payload は明示的な manual one-shot copy の対象です。root は対象外です。Root `spec-dock/.workbench/`で durable に残す一件の file は、`./spec-dock/scripts/spec-dock artifact import file --root --file <path>` で opaque generic Artifact として明示保存できます。これは Workbench copy ではなく、source を変更しない one-file import です。命名と evidence-only boundary は [reference_naming.md](reference_naming.md) および root `artifacts/rules.md` を参照してください。

Copyは明示的なone-shot operationです。Source scope直下の`.workbench/`全体を同じscopeのdestinationへ重ね、source-wins は destination-only entries を保持します。README-specific filter は適用しません。no automatic hook, watch, sync, or copy-back。言語、拡張子、MIME、内容で対象fileを選ぶclassifierもありません。通常file、directory、symlink objectをそのまま扱い、FIFOなどのunsupported special entryやdirectory/non-directory衝突は選別・skipせずcontent-free errorで停止します。Workbenchはnon-canonical、disposableであり、copy成功は永続化やadoptionを意味しません。

`spec-dock update`は既存root/scoped Workbenchをunmanaged local contentとして保持します。Workbenchを別layoutへmigration、normalize、delete、canonical Artifactへpromotionしません。

## スコープ境界（scope boundary）

この command family は create / list / show / remove のみを扱います。
branch deletion、`worktree status`、`prune`、`repair`、orphan cleanup、Codex-managed worktree lifecycle / cleanup は scope 外です。
