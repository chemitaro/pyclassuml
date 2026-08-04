# 結論

**判定は「条件付き採用」です。**

提案の中核である、

> `CLI --depth` ＞ `.pyclassuml.toml` の `depth` ＞ command ごとの既定値
> `generate` の既定値は `None`、`diff` の既定値だけ `1`

という優先順位は妥当です。**command 固有の既定値は `config.resolve_context()` 内で確定し、解決後の `AnalysisConfig.depth` として downstream に渡す**設計を採るべきです。

一方、マージ前に次の2点を明文化する必要があります。

1. 現行 CLI/config では、`diff` の旧挙動である明示的な「無制限 `None`」を指定する方法がありません。後方互換性として無制限モードを残すか、意図的な破壊的変更とするかを決める必要があります。
2. 現在の `depth` は **parse 範囲ではなく traversal/render の reachable frontier だけを制限**します。`depth=1` にしても、2 hop 以降の package-local module は現在の parser により読み込み・構文解析され得ます。

この2点を受け入れ、テストと文書で固定するなら、責務配置としては小さく安全な変更です。

## レビュー基準

GitHub connector では指定された detached commit `8bb20e9faa06` を解決できなかったため、要件に従って default branch `main` の head `c669668a9e8af9ef8c1e475bf56a551121c325a6` を確認しました。その後、添付された checkout の `resolver.py`、`bind.py`、`contracts.py`、`traversal.py`、`diff_collect.py`、`test_context_resolve.py` を補助資料として照合しています。主要な対象箇所については、添付内容と GitHub `main` の実装に実質的な差は見当たりませんでした。     

# 採用すべき設計

## 1. command default の owner は config resolver とする

既存設計文書は、`CommandRequest` を `ExecutionContext` と `AnalysisConfig` に変換する唯一の owner を config seam と定義しています。現在も `_build_analysis_config()` が CLI、config、default のマージを一括して行っています。したがって、`diff` 固有の depth default もここで確定するのが整合的です。

推奨する実装形は次です。

```python
_DIFF_DEFAULT_DEPTH = 1


def _resolve_depth(
    command: CommandName,
    cli_value: object,
    config_value: object,
) -> int | None:
    if cli_value is not None:
        depth = cli_value
    elif config_value is not None:
        depth = config_value
    elif command is CommandName.DIFF:
        depth = _DIFF_DEFAULT_DEPTH
    elif command is CommandName.GENERATE:
        depth = None
    else:
        raise ValueError(f"unsupported command for depth resolution: {command}")

    if depth is not None and (
        isinstance(depth, bool)
        or not isinstance(depth, int)
        or depth < 0
    ):
        _invalid_config("depth must be a non-negative integer")

    return depth
```

呼び出し側は次の形です。

```python
return AnalysisConfig(
    ignore=options.ignore if options.ignore else tuple(config.get("ignore", ())),
    output=output,
    depth=_resolve_depth(
        options.command,
        options.depth,
        config.get("depth"),
    ),
    mode=mode,
    target_python=target_python,
    diff_current_state=diff_current_state,
    diff_include_untracked=diff_include_untracked,
)
```

`_merged_depth()` を残す場合でも、command default を第三引数として渡す形にすべきです。

```python
depth=_merged_depth(
    options.depth,
    config.get("depth"),
    default=1 if options.command is CommandName.DIFF else None,
)
```

ただし、既に単純な二値 merge ではなくなるため、名前は `_resolve_depth()` の方が責務を正確に表します。

## 2. CLI binder は未指定を `None` のまま保持する

`argparse` の `--depth` は現在、未指定なら `None`、指定時は非負整数になります。したがって、`0` を含む明示値と未指定を既に区別できています。ここに `default=1` を追加してはいけません。

正しい seam handoff は次です。

```text
CLI binder:
  未指定       -> CommandOptions.depth = None
  --depth 0    -> CommandOptions.depth = 0
  --depth 2    -> CommandOptions.depth = 2

Config resolver:
  CLI 非 None  -> CLI
  config 有    -> config
  それ以外     -> generate=None / diff=1
```

これにより config の値が CLI parser の既定値で上書きされることを防げます。

## 3. `CommandOptions` と `AnalysisConfig` の型は維持する

`CommandOptions.depth` と `AnalysisConfig.depth` はどちらも現在 `int | None` です。`None` は traversal において「import-hop 上限なし」という有効な意味を持つため、この型は維持すべきです。`AnalysisConfig.depth` の dataclass default も `None` のままにします。

特に、次の変更は行うべきではありません。

```python
@dataclass(frozen=True)
class AnalysisConfig:
    depth: int | None = 1  # 不採用
```

これでは `generate`、traversal 単体利用、直接 `AnalysisConfig()` を作る既存テストのすべてが `depth=1` になります。

## 4. traversal は変更しない

traversal は command-neutral な seam として、解決済みの `AnalysisConfig.depth` だけを消費しています。seed が hop `0`、direct import が hop `1` であり、`depth=1` は direct import まで、`None` は上限なしです。この意味は既存実装・設計・テストで既に固定されています。

したがって、traversal に次のような command default を入れてはいけません。

```python
effective_depth = 1 if config.depth is None else config.depth
```

これは `generate` まで暗黙に `1` にし、traversal seam に command policy を漏らします。

# 優先順位の確定表

| command    | CLI `--depth` | config `depth` | effective depth |
| ---------- | ------------: | -------------: | --------------: |
| `generate` |           未指定 |            未指定 |          `None` |
| `diff`     |           未指定 |            未指定 |             `1` |
| `diff`     |           未指定 |            `0` |             `0` |
| `diff`     |           未指定 |            `3` |             `3` |
| `diff`     |           `0` |            `3` |             `0` |
| `diff`     |           `2` |            `0` |             `2` |
| `generate` |           未指定 |            `3` |             `3` |
| `generate` |           `0` |            `3` |             `0` |

実装では必ず `is not None` を使います。

```python
# 正しい
if cli_value is not None:
    ...

# 誤り
depth = cli_value or config_value or default
```

後者では、正当な値である `0` が未指定として扱われます。現在の config validation は bool を拒否し、非負整数だけを許可しているため、`0` は明確な first-class value です。

# 後方互換性

## 維持される挙動

次は変わりません。

* `generate` で CLI/config とも depth 未指定なら、従来どおり `None`。
* `generate` と `diff` の明示的な `--depth N`。
* top-level config の `depth = N`。
* CLI が config より優先されること。
* `depth=0` が seed-only、`depth=1` が direct import までであること。
* module safety limit `1000`。
* Git base、current state、untracked、rename detection の処理。

## 変わる挙動

CLIにもconfigにも depth がない `diff` だけ、次のように変わります。

```text
変更前: すべての到達可能な package-local import を traversal
変更後: 各 changed seed から direct import まで
```

したがって、2 hop 以上の dependency class/relation が既定の diff 図から消える可能性があります。これは意図した変更でも、出力互換性の観点では明確な behavioral breaking change です。

## 無制限モードの互換性問題

現行 CLI の `--depth` は非負整数しか受け付けず、config の `depth` も非負整数だけです。TOML には `null` 値がありません。そのため `diff` の command default を `1` にすると、利用者が明示的に effective `None` を要求する経路がなくなります。

これはマージ前に判断すべき互換性ゲートです。

**推奨**は、旧挙動を必要とする利用者向けに将来または同一 issue で明示的な unlimited 表現を設けることです。候補は `--depth unlimited` などですが、この場合は「未指定」と「明示 unlimited」を区別する入力 DTO または provenance flag が必要になります。

採用してはいけない表現は次です。

* `--depth -1`: 現在の非負整数契約を破る。
* `depth = 0` を unlimited に再定義する: seed-only という既存意味を破る。
* 非常に大きな整数を unlimited と説明する: traversal module limit への実装依存であり、意味契約として不適切。

今回 unlimited 指定を追加しない場合は、**旧 `diff` の無制限探索を直接再現できなくなることを release note に明記する必要があります。**

# Git 比較方式との相互作用

## 1. depth は Git 比較を変更しない

現在の diff pipeline は次の順序です。

```text
resolve_context
  -> collect_diff_files
  -> normalize_diff_targets
  -> parse_target_set
  -> traverse_dependencies
  -> selection / render
```

Git base、`working-tree` / `head`、untracked の判定は traversal より前に完了します。`diff_collect.py` は `AnalysisConfig` から `diff_current_state` と `diff_include_untracked` を参照しますが、`depth` は使用しません。

したがって、新しい既定 depth は次を変更しません。

* explicit `--base`
* default branch candidate との merge-base
* initial commit fallback
* `base..working-tree` と `base..HEAD` の選択
* untracked の追加
* rename detection
* changed hunk の収集

## 2. changed Python file はすべて seed のまま

scope と ignore を通過した changed Python file は、すべて `TargetSet.seed_files` に入ります。depth はその後、各 seed からの dependency expansion にだけ作用します。

したがって、A → B → C の import chain で A と C の両方が Git changed file なら、`depth=1` でも C は hop `0` の seed として残ります。C が「A から2 hop目」であることを理由に除外されることはありません。

これは重要な multi-seed edge case です。

## 3. initial commit fallback では seed 数が大きいままになり得る

default branch 上で base を省略した場合、既存 VCS contract は initial commit object を fallback base として使います。その場合、initial commit 以降に変更された多数の Python file が seed になる可能性があります。depth `1` は dependency expansion を抑えますが、seed 自体の件数は減らしません。

したがって、「diff default depth=1 にすれば、default branch での大規模図も必ず小さくなる」という主張は成立しません。

## 4. `--current-state head` と working tree

既存契約では、`--current-state head` は changed file と差分分類を `HEAD` 基準で収集しますが、通常の parse/traversal は作業ツリー上のファイルを読みます。README にも、HEAD 内容だけを図にしたい場合は working tree を clean にする必要があると明記されています。

したがって `diff` の既定 depth `1` で展開される direct import も、dirty working tree では HEAD と異なる import graph に基づく可能性があります。これは今回新しく生じる不具合ではありませんが、integration test は clean working tree で行うべきです。

# 拒否すべき代替案

## `argparse` の diff parser に `default=1` を置く

**拒否。**

```python
diff_parser.add_argument("--depth", default=1, ...)
```

これでは resolver から見ると CLI depth が常に `1` になり、config の `depth` が採用されません。提案された優先順位を壊します。

## `AnalysisConfig.depth` の dataclass default を `1` にする

**拒否。**

`AnalysisConfig` は command を持たないため、`generate` と traversal 単体テストまで `1` になります。

## `run_diff()` で `None` を `1` に書き換える

**拒否。**

```python
config = replace(config, depth=1) if config.depth is None else config
```

config resolver を唯一の owner とする既存 seam 設計に反し、application wiring に merge policy が漏れます。resolve 後の config と report に渡す config がどの時点で変わったかも不明瞭になります。

## traversal 内で `None` を `1` と解釈する

**拒否。**

traversal は command-neutral であり、`None` は既に「上限なし」という有効な値です。

## `diff_collect` や target normalization で depth を適用する

**拒否。**

Git changed-file collection と seed normalization は、dependency hop の owner ではありません。ここで file を削ると、「changed file はすべて seed」という contract を壊します。

## `options.depth or config.get("depth") or 1`

**拒否。**

`0` を失います。

## `CommandOptions.__post_init__()` で diff の depth を `1` にする

**拒否。**

DTO construction の段階で未指定情報を失い、config の優先適用ができなくなります。

# 見落としやすい edge case

## 1. depth は parse 範囲を制限していない

これは最も重要な注意点です。

`parse_target_set()` は seed から package-local import candidate を再帰的に queue へ追加しており、queue 拡張時に `config.depth` を見ていません。depth が使われるのは、その後の `traverse_dependencies()` です。

したがって A → B → C で `depth=1` の場合でも、

* reachable graph は A と B。
* C は graph/render から除外される。
* ただし C は parser により読み込まれ、AST parse され得る。
* C の syntax error は `bad_syntax` diagnostic になり得る。

実際、syntax error は parse seam で error diagnostic として生成されます。

よって、この改善の正確な説明は、

> diff の既定 **dependency traversal / rendered impact radius** を direct import までにする

です。

次の説明は現行実装では不正確です。

> diff は既定で1 hop分のファイルしか読み込まない
> diff は既定で2 hop以降を解析しない
> depth=1 により parse performance が必ず改善する

性能や深い依存先の parse failure 隔離まで目的に含むなら、今回の resolver 変更だけでは不足し、parse seam の queue 設計まで再検討が必要です。

## 2. top-level config depth は両 command に作用する

`.pyclassuml.toml` の `depth` は top-level 共通設定です。したがって、既存ファイルに `depth = 3` があれば `diff` の command default `1` は使われず、`generate` と `diff` の両方が `3` になります。

「diff だけ常に1」という仕様ではなく、

> diff の CLI/config 未指定時だけ1

であることを文書化する必要があります。

## 3. `depth=0`

CLI/config の `0` は seed-only です。既定値 `1` への fallback より必ず優先されなければなりません。

## 4. multi-seed

すべての changed Python file が hop `0` です。一方の seed から2 hop以上でも、別の changed file として seed なら残ります。

## 5. cyclic import

既存 traversal は reachable set により cycle を停止します。depth default を resolver で確定する限り、この性質は変わりません。

## 6. module limit

depth `1` でも、seed 数と direct import candidate 数の合計が module limit を超えれば、既存の `traversal_limit_reached` は発生します。また parser 自体には同じ module limit が適用されていないため、depth `1` を parser safety limit とみなしてはいけません。

## 7. direct import の複数 candidate

同じ import text が module file と package `__init__.py` など複数 candidate に解決されれば、それぞれが同じ hop の candidate になります。`depth=1` は「direct import statement ごとに1ファイル」ではなく、「hop が1以下の解決済み candidate」を意味します。

# 必要なテスト

## Config resolver

最低限、次のテストを追加します。

```python
def test_diff_unset_depth_defaults_to_one_without_config(...):
    ...

def test_generate_unset_depth_remains_none_without_config(...):
    ...

def test_diff_config_depth_overrides_command_default(...):
    ...

def test_diff_config_depth_zero_overrides_command_default(...):
    ...

def test_diff_cli_depth_overrides_config(...):
    ...

def test_diff_cli_depth_zero_overrides_config(...):
    ...

def test_generate_config_depth_still_applies(...):
    ...
```

既存の generate default test は `config == AnalysisConfig()` を期待しているため、そのまま維持すべきです。既存テストには CLI `depth=0` が config `depth=2` を上書きするケースも既にあり、これは重要な回帰防止材料です。 

## CLI bind

bind seam では「既定値1」をテストしてはいけません。次をテストします。

```python
def test_diff_unset_depth_binds_none(...):
    request = bind_command_request(("diff",), cwd)
    assert request.cli_options.depth is None

def test_generate_unset_depth_binds_none(...):
    ...

def test_depth_zero_is_preserved(...):
    ...
```

これにより command default の owner が resolver であることを固定できます。

## Traversal

既存の以下の unit test は十分な意味契約を既に持っています。

* `depth=0`: seed-only
* `depth=1`: direct import まで
* `depth=None`: transitive traversal
* cyclic import
* module limit

ここには command-specific default test を追加しません。traversal は command-neutral のままにします。

## App integration

resolver の値が実際の図に反映されることを保証するため、A → B → C の fixture を使います。

| ケース                                 | 期待                          |
| ----------------------------------- | --------------------------- |
| `diff`, CLI/config 未指定              | A・B reachable、C 非 reachable |
| `diff --depth 2`                    | A・B・C reachable             |
| config `depth=2` の `diff`           | A・B・C reachable             |
| config `depth=2` + `diff --depth 1` | A・B reachable               |
| `generate`, CLI/config 未指定          | A・B・C reachable             |
| A と C が changed seed、diff default   | C は seed として残る              |

図面文字列だけでなく、可能なら `dependency_graph.reachable_files` または summary の `reachable_file_count` も検証すべきです。文字列だけでは relation selection や renderer の別要因で失敗原因が曖昧になるためです。

## VCS integration

次を最低限確認します。

* explicit base でも default merge-base でも effective depth が同じように適用される。
* untracked Python file が seed の場合、direct import が default depth `1` で含まれる。
* `current_state=head` のテストは clean working tree で行う。
* initial commit fallback 時、changed files 自体は depth により除外されない。

Git command argumentそのものを depth ごとに重複テストする必要はありません。`diff_collect.py` にコード変更を入れず、app-level regression で十分です。

## Parse semantics の決定テスト

現在の semantics を維持するなら、次のテストを加える価値があります。

```text
A -> B -> C
diff default depth=1
C に syntax error
期待:
  C は reachable graph には入らない
  ただし bad_syntax diagnostic は観測される
```

この結果が要求と違うなら、resolver 変更を進める前に「depth は parse frontier も制限する」という別設計が必要です。

## Verification

実装後は少なくとも次を実行対象にします。

```text
tests/config/test_context_resolve.py
tests/cli/test_bind.py
tests/analyze/test_traversal.py
tests/app/test_diff.py
tests/app/test_generate.py
full pytest suite
```

diff の既定出力が変わるため、app-level fixture や golden assertion が transitive dependency を暗黙に期待している可能性があります。resolver unit test だけでは回帰範囲を評価できません。

# 必要なドキュメント

## README

現在の README は `--depth` を「依存探索の最大深さ」と説明していますが、command ごとの default と hop semantics は書かれていません。

少なくとも次を追記します。

```text
--depth は import hop の最大値です。
seed file は depth 0、direct import は depth 1 です。

CLI 未指定時:
- generate: 上限なし
- diff: 1

優先順位:
CLI --depth > .pyclassuml.toml の depth > command default
```

さらに、top-level config の `depth` は両 command に作用することを明記します。

## `diff` セクション

次を明記します。

* default depth は `1`。
* changed Python file はすべて seed であり、depth は seed からの dependency expansion に作用する。
* Git base/current-state の選択には作用しない。
* `current-state=head` でも dependency parse は working tree の内容に影響されるという既存契約。

## CLI help

現在の parser は `--depth` に help text を持ちません。少なくとも次に相当する説明を追加するのが望ましいです。

```python
parser.add_argument(
    "--depth",
    type=_non_negative_int,
    help=(
        "maximum import hops; defaults to unlimited for generate "
        "and 1 for diff unless configured"
    ),
)
```

## Config resolver 設計書

既存設計書の default values には現在 `depth = None` とだけ書かれています。これを次に更新します。

```text
depth command defaults:
- generate: None
- diff: 1

merge:
CLI depth > config depth > command default
```

## Release note / migration note

明示すべき内容は次です。

* depth 未指定の `diff` 出力から2 hop以上の dependencies が除外される可能性。
* config に `depth` がある場合は新 default が適用されない。
* unlimited diff の明示指定を追加しない場合、旧 unlimited default を直接復元できないこと。
* `generate` の default は変わらないこと。

# 仮定

* 改善目的は **diff 図の既定 impact radius を抑えること**であり、filesystem I/O、AST parse 範囲、syntax diagnostics の範囲を抑えることではない、と仮定しました。
* top-level `depth` を generate/diff 共通設定として維持する、と仮定しました。
* `AnalysisConfig` は resolver 後の effective configuration を downstream に渡す DTO であり、入力 provenance 自体は保持しない現行方針を維持する、と仮定しました。

# 不確実性・未検証主張

* detached commit `8bb20e9faa06` は GitHub connector 上で解決できていません。GitHub `main` と添付されたファイルにない detached checkout 固有の変更は未検証です。
* 実際の checkout 全体で pytest は実行していません。どの app-level golden test が新しい default により失敗するかは未検証です。
* issue #44 の GitHub 本文には詳細仕様がなく、ローカル SpecDock の requirement/design は提示されていません。unlimited mode を残すかどうかについて、確定済みのプロダクト判断は確認できません。
* 「depth default `1` で図が小さくなる」という結論は、changed seed 数が十分小さい通常の feature-branch diff を想定した推論です。initial commit fallback や大量 changed files では効果が限定的です。

総合すると、**resolver だけで command-aware fallback を確定する実装は採用すべきです。CLI、DTO、traversal、VCS collector には default policy を移さず、無制限モードの扱いと parse 範囲非連動を明文化することが採用条件です。**
