# PyClassUML

PyClassUML は、Python プロジェクトのソースコードを静的解析し、PlantUML のクラス図ファイルを生成する外部 CLI ツールです。

主な用途は次の 2 つです。

- 任意のファイル、ディレクトリ、glob を起点にクラス図を作る
- Git 差分を起点に、変更影響範囲のクラス図を作る

PyClassUML は解析対象プロジェクトに依存として組み込まず、対象コードを書き換えず、対象コードを import 実行しません。AST ベースの静的解析だけで、到達可能なクラスと関係を抽出します。

## インストールと実行

通常利用では、対象プロジェクトにインストールせず `uvx` などの外部実行環境から呼び出します。

```bash
uvx pyclassuml generate ...
uvx pyclassuml diff ...
```

このリポジトリをローカルで開発・確認している場合は、次のように実行できます。

```bash
uv run pyclassuml --help
```

## クイックスタート

明示した Python ファイルからクラス図を作る場合:

```bash
pyclassuml generate pkg/model.py --output diagram.puml
```

ディレクトリや glob を起点にする場合:

```bash
pyclassuml generate pkg --output diagram.puml
pyclassuml generate "pkg/**/*.py" --output diagram.puml
```

Git 差分からクラス図を作る場合:

```bash
pyclassuml diff --base main --output diff.puml
```

monorepo やレイヤー限定の解析では、境界を明示します。

```bash
pyclassuml diff \
  --base main \
  --project-root . \
  --package-root backend \
  --scope-root backend/app \
  --ignore "backend/tests/**" \
  --output diff.puml
```

## CLI リファレンス

PyClassUML には `generate` と `diff` の 2 つのサブコマンドがあります。

### `generate`

```bash
pyclassuml generate [options] [targets ...]
```

`targets` には、ファイル、ディレクトリ、glob を指定できます。相対パスは `--cwd` で決まる実行基準ディレクトリから解決されます。

対象は `.py` ファイルだけです。ディレクトリを指定した場合は、配下の `.py` ファイルを再帰的に対象にします。`--scope-root` の外にあるターゲットはエラーになります。

### `diff`

```bash
pyclassuml diff [options] --base <ref>
```

`diff` は Git 差分から対象ファイルを集めてクラス図を作ります。`--base` は必須で、Git の revision を指定します。

`--current-state` は比較対象を選びます。

- `working-tree`: `--base` と現在の作業ツリーを比較します。デフォルトです。
- `head`: `--base` と `HEAD` を比較します。

`--current-state head` は、Git 差分の対象ファイルと差分分類を `HEAD` 基準で集めるための指定です。図を作るために読む現在側のファイル内容は作業ツリー上のファイルなので、`HEAD` の内容だけを図にしたい場合は作業ツリーを clean にしてから実行してください。

`--include-untracked` / `--no-include-untracked` は、未追跡ファイルを差分対象に含めるかを指定します。デフォルトは include です。`--current-state head` の場合、未追跡ファイルは Git の `HEAD` 差分に含まれないため、この指定は実質的に効きません。

### 共通オプション

```text
--cwd <path>
--config <path>
--project-root <path>
--package-root <path>
--scope-root <path>
--output <path>
--ignore <glob>
--depth <n>
--strict
--target-python <3.x>
```

- `--cwd`: PyClassUML が内部で使う実行基準ディレクトリです。未指定ならプロセスの current working directory を使います。
- `--config`: `.pyclassuml.toml` のパスを明示します。
- `--project-root`: 解析対象プロジェクト全体の基準ディレクトリです。
- `--package-root`: import 解決の主な基準ディレクトリです。
- `--scope-root`: 解析・探索を許可する範囲です。
- `--output`: 出力する `.puml` ファイルのパスです。
- `--ignore`: 除外する glob です。複数回指定できます。
- `--depth`: 依存探索の最大深さです。0 以上の整数を指定します。
- `--strict`: 警告扱いの一部の問題を失敗として扱います。
- `--target-python`: 解析対象の Python バージョンを `3.12` のような形式で指定します。

## パスと境界

PyClassUML では、パスの意味を明確に分けています。

- `process_cwd`: CLI プロセスが起動された実際の current working directory
- `execution_cwd`: PyClassUML 内部の実行基準ディレクトリ。`--cwd` があればそれを使い、なければ `process_cwd` を使います。
- `project_root`: 解析対象プロジェクト全体の基準
- `package_root`: Python import 解決の主な基準
- `scope_root`: 解析対象として許可する範囲

CLI に渡す相対パスは、基本的に `execution_cwd` 基準で解決されます。`--ignore` の glob は、解析対象集合へのフィルタとして `project_root` 相対で評価されます。

`package_root` は `project_root` の内側、`scope_root` は `package_root` の内側である必要があります。

## 設定ファイル

設定ファイル名は `.pyclassuml.toml` です。`pyproject.toml` は PyClassUML の設定ファイルとしては使いません。

```toml
project_root = "."
package_root = "src"
scope_root = "src"
output = "diagram.puml"
ignore = ["tests/**", "build/**"]
depth = 3
mode = "warn"
target_python = "3.12"
relative_path_base = "config"

[diff]
current_state = "working-tree"
include_untracked = true
```

現在利用できる主な設定は次のとおりです。

- `project_root`, `package_root`, `scope_root`
- `output`
- `ignore`
- `depth`
- `mode`: `warn` または `strict`
- `target_python`
- `relative_path_base`: `config` または `cwd`
- `[diff].current_state`: `working-tree` または `head`
- `[diff].include_untracked`: `true` または `false`

CLI オプションで指定した値は、設定ファイルの値より優先されます。

設定ファイル内の相対パスは、デフォルトでは設定ファイル自身の場所を基準に解決されます。`relative_path_base = "cwd"` を指定すると、設定ファイル内の `project_root`、`package_root`、`scope_root`、`output` は `execution_cwd` 基準で解決されます。CLI オプションで渡した相対パスは、この設定に関係なく `execution_cwd` 基準です。

設定ファイルを明示しない場合、PyClassUML はまず `--project-root` 配下の `.pyclassuml.toml` を探し、見つからない場合は `execution_cwd` から親ディレクトリへ向かって `.pyclassuml.toml` を探します。

## 出力と終了結果

成功すると PlantUML の `.puml` ファイルを書き出します。CLI の `--output` と設定ファイルの `output` のどちらも指定しない場合は、`execution_cwd` に次の形式で出力します。

```text
pyclassuml_YYYYMMDD_HHMMSS.puml
pyclassuml_diff_YYYYMMDD_HHMMSS.puml
```

同名ファイルがすでにある場合は、`_2`, `_3` のような suffix を付けて上書きを避けます。

実行後は標準出力または標準エラーにサマリが出ます。サマリには、結果種別、終了コード、対象ファイル数、抽出クラス数、関係数、警告数などが含まれます。

警告だけの場合は `.puml` を出力して成功扱いになることがあります。`--strict` または `mode = "strict"` を使うと、一部の解析失敗や解決失敗を終了コード 1 の失敗として扱います。

## 設計上の制約

PyClassUML は、解析対象プロジェクトに対して非侵襲に動作することを重視します。

- 解析対象プロジェクトの `pyproject.toml` に依存を追加しません。
- 解析対象のソースコードを書き換えません。
- 解析対象コードを import 実行しません。
- AST ベースの静的解析だけで扱います。
- 同じ入力からはできるだけ決定的な出力になるようにします。

## 開発者向け情報

この README は PyClassUML を使う人向けの説明です。リポジトリの開発方針、SpecDock 運用、エージェント向けの作業規約は `AGENTS.md` を参照してください。
