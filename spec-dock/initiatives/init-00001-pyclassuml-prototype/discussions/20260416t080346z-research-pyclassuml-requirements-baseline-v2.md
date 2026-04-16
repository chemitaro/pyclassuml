---
種別: research
ID: "20260416t080346z-research"
タイトル: "PyClassUML Requirements Baseline V2"
状態: "completed"
作成者: "iwasawayuuta"
最終更新: "2026-04-16"
親: ["init-00001"]
関連: []
---

# 20260416t080346z-research PyClassUML Requirements Baseline V2

## 調査目的 (必須)
- ユーザー提供の「要件定義書 確定版 v2.0」を、この initiative における基礎仕様として保存する。
- 後続の `requirement.md`、`design.md`、`plan.md` を作成する際の参照元を 1 本に揃える。
- 元文書の意図を失わないよう、要約ではなく原文全体も保持する。

## 調査方法 (必須)
- ユーザーが会話上で提供した要件定義書確定版 v2.0 を一次情報として採用した。
- SpecDock initiative `init-00001` 配下の `discussions/` に `research` として保存し、長期参照可能な形に整えた。
- この文書では、後続作業で引きやすいように要点サマリを先頭に置き、その後ろに原文を保持した。

## 調査結果 (必須)
- `pyclassuml` は Python プロダクトを静的解析し、指定起点から内部依存をたどって PlantUML クラス図を生成する外部 CLI として定義されている。
- 主要ユースケースは `generate` と `diff` の 2 系統で、Git 差分起点と明示起点の両方を扱う。
- 実行コンテキストとして `execution_cwd` を明示的に持ち、`project_root` / `package_root` / `scope_root` を分離することが骨格要件になっている。
- 解析方式は AST ベース静的解析のみで、import 実行を行わない。
- MVP には CLI、設定ファイル `.pyclassuml.toml`、依存探索、UML 出力、SQLAlchemy / Pydantic のベストエフォート対応、strict/warn、実行サマリまでが含まれる。
- 高優先度の未確定事項は実装致命点として残っておらず、要件は実装着手可能な粒度まで固まっている。

## 結論 (必須)
- この文書を prototype initiative における基礎仕様の正規参照元として扱う。
- initiative / epic / issue の `requirement.md` には全文を転載せず、本書から各スコープの責務に合わせて要約・再編して記述する。
- 将来の判断理由や代替案比較が必要になった場合のみ、追加で `disc` や `adr` を分離する。

## リスク/制約 (任意)
- この文書は基礎仕様の保全が目的であり、initiative / epic / issue ごとの受け入れ条件や分解方針そのものではない。
- 実装詳細の具体値や内部構造、分割順序はこの文書だけでは閉じないため、後続の `design.md` と `plan.md` で固定する必要がある。
- 将来仕様更新が入った場合は、この baseline を上書きせず、新しい `research` または `disc` を追加して差分を追えるようにする。

## 参考（References） (任意)
- Source: ユーザー提供「要件定義書 確定版 v2.0」
- Context: `init-00001` PyClassUML Prototype initiative kickoff baseline

## 原文（ユーザー提供要件定義書 確定版 v2.0）

高優先度の未確定事項は、実装に致命的なものとしては残っていません。
要件は実装着手可能な粒度まで固まりました。
以下を **要件定義書 確定版 v2.0** とします。

---

# 要件定義書 確定版 v2.0

対象ツール名: **`pyclassuml`**

## 1. 目的

`pyclassuml` は、Python プロダクトのソースコードを **静的解析** し、指定した起点から **プロダクト内部の依存関係** を探索して、その範囲に含まれるクラス群の UML クラス図を **PlantUML (`.puml`)** 形式で生成する外部 CLI ツールである。

主用途は次の3つ。

1. 任意のファイル、glob、ディレクトリを起点にした設計把握
2. Git 差分を起点にした変更影響範囲の可視化
3. 特定ディレクトリ配下に探索を制限した、レイヤー限定の設計可視化

---

## 2. 配布・実行モデル

このツールは **解析対象プロジェクトに依存として組み込まない**。
外部ツールとして配布し、対象プロジェクトの外側から実行する。

想定実行形態は以下。

```bash
uvx pyclassuml generate ...
uvx pyclassuml diff ...
```

頻用時は外部ツール環境に常設してよいが、対象プロジェクトにはインストールしない。

非侵襲性要件は次のとおり。

* `pyproject.toml` に依存を追加しない
* 対象ソースコードを書き換えない
* 読み取り専用で動作する
* 実行時 import を行わない

---

## 3. CLI 構成

サブコマンド方式を採用する。

### 3.1 `generate`

明示された起点からクラス図を生成する。

```bash
pyclassuml generate <targets...> [options]
```

### 3.2 `diff`

Git 差分を起点にクラス図を生成する。

```bash
pyclassuml diff --base <ref> [options]
```

### 3.3 グローバルまたは主要オプション

少なくとも以下を持つ。

* `--cwd <path>`
* `--config <path>`
* `--project-root <path>`
* `--package-root <path>`
* `--scope-root <path>`
* `--depth <n>`
* `--ignore <glob>` 複数可
* `--target-python <version>`
* `--output <path>`
* `--strict`

必要に応じて表示制御系オプションを追加する。

---

## 4. 実行コンテキストとパス解決

### 4.1 `process_cwd`

OS プロセス起動時点の実際の current working directory。

### 4.2 `execution_cwd`

ツール内部で採用する実行基準ディレクトリ。
`pyclassuml` はこれを明示的な概念として保持する。

決定規則は次のとおり。

1. `--cwd` が指定されていれば、それを使う
2. 指定が無ければ `process_cwd` を使う

### 4.3 `--cwd` の解決

`--cwd` 自体が相対パスで与えられた場合は、**`process_cwd` 基準** で解決する。
これにより bootstrap の循環を避ける。

### 4.4 `execution_cwd` の許容位置

`execution_cwd` は以下のどれでもよい。

* `project_root` そのもの
* `project_root` 配下
* `project_root` の外側

つまり、**プロジェクト外からの実行を正式にサポートする**。

### 4.5 CLI 相対パスの解決基準

CLI で渡される相対パスは、**すべて `execution_cwd` 基準** で解決する。

対象:

* 起点ターゲット
* `--project-root`
* `--package-root`
* `--scope-root`
* `--config`
* `--output`

### 4.6 `ignore` の解決基準

`--ignore` の glob は **`project_root` 相対** で評価する。
これはパスそのものではなく、解析対象集合へのフィルタだからである。

---

## 5. 設定ファイル

### 5.1 使用ファイル

`pyproject.toml` は使わない。
専用設定ファイル名は **`.pyclassuml.toml`** とする。

### 5.2 設定ファイルの取得方法

優先順位は次のとおり。

1. `--config <path>` が指定されていればそれを使う
2. 指定が無ければ自動探索する

### 5.3 自動探索規則

`--project-root` が明示されている場合は、まず
`<project_root>/.pyclassuml.toml`
を探す。

存在しない場合は、**`execution_cwd` から親方向に辿って、最初に見つかった `.pyclassuml.toml`** を使う。

`--project-root` が明示されていない場合は、最初から
**`execution_cwd` から親方向に辿って、最初に見つかった `.pyclassuml.toml`**
を使う。

### 5.4 設定ファイル内の相対パス

設定ファイル内の相対パスの解決基準は **切替可能** とする。

* デフォルト: **設定ファイル自身の場所基準**
* 切替時: **`execution_cwd` 基準**

設定ファイルには、たとえば次のようなキーを持たせる。

```toml
relative_path_base = "config"  # default
# または
relative_path_base = "cwd"
```

### 5.5 設定可能項目

少なくとも以下を設定できること。

* `project_root`
* `package_root`
* `scope_root`
* `ignore`
* `default_depth`
* 探索上限
* `group_by`
* member visibility
* relation options
* color settings
* output naming settings
* `strict`
* `target_python`
* `relative_path_base`

### 5.6 `project_root` の最終決定

`project_root` は次の優先順位で決定する。

1. `--project-root`
2. 設定ファイル内の `project_root`
3. **読み込まれた設定ファイルのあるディレクトリ**
4. `execution_cwd`

この 3 を入れる理由は、設定ファイルが存在するのに `project_root` が `execution_cwd` に落ちると、プロジェクト境界が不自然になるためである。

---

## 6. 解析対象境界

### 6.1 `project_root`

解析対象プロジェクト全体の基準ディレクトリ。

### 6.2 `package_root`

内部モジュール候補の宇宙を定める境界。
内部モジュールと見なすのは、原則として **`package_root` 配下の Python ソース** のみ。

初期版では **単一の `package_root` のみ** サポートする。
省略時は `project_root` を用いる。

### 6.3 `scope_root`

今回の探索をどこまで許可するかを決める境界。
役割は「内部モジュール候補のうち、今回どこまで辿るか」の制御である。

### 6.4 包含関係

必ず次を満たすこと。

`scope_root ⊆ package_root ⊆ project_root`

違反時はエラー。

### 6.5 `scope_root` の目的

* 特定レイヤー配下だけに探索を留める
* 余分な探索を避ける
* 深さ未指定時の探索拡大を抑える
* レイヤー限定の図を作る

### 6.6 初期版の `scope_root`

**単一のみ** サポートする。
将来版で複数対応を検討する。

---

## 7. 起点指定仕様

### 7.1 `generate` の起点

次を受け付ける。

* ファイルパス
* glob パターン
* ディレクトリパス
* 複数指定

### 7.2 ディレクトリ指定

ディレクトリパスは内部的に再帰展開し、意味としては次に等しい。

```text
<dir> -> <dir>/**/*.py
```

### 7.3 `generate` 起点未指定

エラー。

### 7.4 起点の重複

正規化後に一意化する。

### 7.5 `generate` と `scope_root`

`generate` では、**起点ファイルが `scope_root` 外ならエラー**。

理由は、`generate` の起点は利用者が明示的に指定しているため、scope と起点の矛盾は即失敗にした方が一貫するからである。

---

## 8. `diff` モード仕様

### 8.1 基本意味

`diff` は、**指定した ref** と **現在状態** の差分を起点にクラス図を生成する。

`main` は特別扱いしない。
`--base main` も `--base feature/x` も `--base <commit>` も、同じ意味で扱う。

### 8.2 現在状態

切替可能。

* `working-tree`
* `head`

デフォルトは **`working-tree`**

### 8.3 untracked ファイル

切替可能。
デフォルトは **含める**。

### 8.4 起点に含める変更種別

* 追加
* 変更

初期版では削除は起点に含めない。
rename は **移動後の現在存在するファイル側のみ** 扱う。

### 8.5 `diff` と `scope_root`

`diff` では起点が差分から自動生成されるため、`generate` と少し挙動を変える。

* 差分起点のうち **`scope_root` 外のものは事前に除外** する
* 除外が発生した場合は通常モードで警告する
* 除外後に **`scope_root` 内の起点が 0 件** ならエラー

### 8.6 クラスが存在しない変更ファイル

図には直接出さない。
ただし **依存探索の起点としては使う**。

### 8.7 changed class の定義

初期版では、**変更ファイル内に存在するクラス** を changed class とする。
diff hunk 単位の判定は将来拡張。

---

## 9. ignore 仕様

### 9.1 指定方法

`--ignore <glob>` を複数回指定可能。

### 9.2 評価基準

`project_root` 相対で評価する。

### 9.3 適用対象

起点候補にも依存探索候補にも適用する。

### 9.4 デフォルト ignore

最小限の安全なデフォルト ignore を持つ。

```text
.venv/**
venv/**
**/__pycache__/**
site-packages/**
```

ユーザー指定 ignore はこれに追加される。

---

## 10. 探索深さと安全上限

### 10.1 `depth` の意味

`depth` は **import グラフのホップ数**。

* `depth=0`: 起点のみ
* `depth=1`: 起点の直接 import 先まで
* `depth=n`: n ホップまで

### 10.2 デフォルト

ユーザー仕様上は **制限なし**。

### 10.3 循環防止

循環 import は **visited 管理** で防ぐ。
これは depth とは別責務。

### 10.4 実装上の安全上限

探索爆発を防ぐため、内部的に十分大きなハード上限を持つ。
上限到達時はエラー。

上限対象は少なくとも以下。

* 最大探索ファイル数
* 最大抽出クラス数
* 最大関係数

具体数値は実装設計で決めるが、**設定可能であること** を要件とする。

### 10.5 `scope_root` との関係

探索可否は次の順で判定する。

1. 内部モジュールか
2. `scope_root` 内か
3. depth 制限内か

---

## 11. 解析方式

### 11.1 基本方針

**AST ベースの静的解析のみ** で行う。
対象コードを import 実行しない。

### 11.2 解決対象

初期版で扱う対象は次のとおり。

* `import ...`
* `from ... import ...`
* 相対 import
* `if TYPE_CHECKING:` 内 import
* forward reference 文字列
* `from __future__ import annotations`
* `__init__.py` による re-export
* import alias (`as`)
* wildcard import (`from x import *`) の限定対応

### 11.3 wildcard import

`from x import *` は検出対象に含める。
ただし **`__all__` が明示されている場合のみ** ベストエフォートで解決する。

`__all__` の解決対象は **リテラルな list / tuple のみ**。

対応例:

```python
__all__ = ["A", "B"]
__all__ = ("A", "B")
```

非対応例:

```python
__all__ = BASE + ["A"]
__all__ = compute_all()
```

### 11.4 解決不能時

通常モードでは警告して継続。
`--strict` ではエラー。

### 11.5 namespace package

初期版は通常 package 前提とし、namespace package は **best-effort** とする。
明示的な完全対応は将来拡張。

---

## 12. クラス抽出対象

### 12.1 対象

* 通常クラス
* `dataclass`
* `ABC`
* `Protocol`
* `Enum`
* Pydantic 系モデル
* SQLAlchemy 系モデル

### 12.2 対象外

初期版では **nested class は対象外**。

### 12.3 ステレオタイプ

可能な範囲で PlantUML 上に付与する。

例:

* `<<dataclass>>`
* `<<protocol>>`
* `<<enum>>`
* `<<pydantic>>`
* `<<sqlalchemy>>`

---

## 13. メンバー表示仕様

### 13.1 デフォルト表示

* フィールド: 型付き属性を表示
* メソッド: public メソッドを表示
* `__init__`: 表示
* `@property`: メソッドと区別して表示
* その他 dunder: 原則省略
* private/protected 風メンバー: オプションで切替

### 13.2 継承メンバー

初期版は **そのクラス自身に定義されたメンバーのみ表示** する。
継承元メンバーのフラット展開は行わない。

### 13.3 モデル系フィールド表示件数

`dataclass` / `pydantic` / `sqlalchemy` のフィールド件数制限は **オプション化** し、デフォルトは制限なし。

---

## 14. 関係抽出仕様

### 14.1 初期版で抽出する関係

1. 継承
2. 属性保持関係
3. メソッド引数・戻り値型による依存

### 14.2 継承

`class Child(Parent)` を継承として扱う。

### 14.3 属性保持関係

以下を対象とする。

* クラス属性
* インスタンス属性
* dataclass フィールド
* Pydantic フィールド
* SQLAlchemy モデル属性

### 14.4 メソッド依存

* 引数型
* 戻り値型

### 14.5 型注釈のない属性代入の限定推論

次の条件を満たす場合のみ保持関係を推論する。

* `self.xxx = arg` の形である
* `arg` がメソッド引数名と一致する
* その引数に型注釈がある

例:

```python
def __init__(self, repo: UserRepository) -> None:
    self.repo = repo
```

この場合、`self.repo` は `UserRepository` を保持するとみなす。

### 14.6 型注釈展開

typing コンテナと Union を展開して中の型を拾う。

対象例:

* `list[T]`
* `set[T]`
* `tuple[T]`
* `dict[K, V]`
* `Sequence[T]`
* `Mapping[K, V]`
* `Optional[T]`
* `T | None`
* `Union[A, B, C]`
* `A | B`

展開後に現れた **内部クラス型** を依存として拾う。

無視するもの:

* `int`, `str`, `float`, `bool`, `bytes`
* `None`
* `Any`
* 型変数
* 外部ライブラリ型
* 標準ライブラリ型

---

## 15. SQLAlchemy / Pydantic の特別扱い

### 15.1 SQLAlchemy

通常の型注釈に加え、以下をベストエフォートで特別扱いする。

* `Mapped[T]`
* `relationship("T")`

`Mapped[T]` は展開して `T` を拾う。

`relationship("T")` は文字列から参照先モデル名を解決する。
同名クラス候補が複数ある場合は **曖昧として警告し、デフォルトでは依存線を出さない**。

### 15.2 Pydantic

一般 forward reference に加えて、自己参照・相互参照の典型パターンをベストエフォートで補強する。

対象例:

* `"User"`
* `"TreeNode"`
* `list["TreeNode"]`
* `Optional["TreeNode"]`
* `TreeNode | None`

### 15.3 解決不能時

通常モードでは警告、`--strict` ではエラー。

---

## 16. 外部基底クラスの扱い

継承元が外部ライブラリ型だった場合、**初期版では外部基底クラスノードを図に出さない**。
必要であればステレオタイプや注記で意味を補う。

---

## 17. UML 表現方針

### 17.1 コンポジション/集約

厳密には区別しない。

### 17.2 PlantUML 記法

* 継承: 継承記法
* 属性保持: `o--`
* 引数/戻り値依存: `..>`

### 17.3 関係ラベル

関係線ラベルは **オプション化** し、**デフォルトでは非表示**。

### 17.4 グルーピング

デフォルトは **なし**。
オプションで以下を選べる。

* `none`
* `package`
* `file`

---

## 18. 表示対象クラスの選別

### 18.1 起点ファイル

起点ファイル内のクラスは **原則すべて表示**。

### 18.2 依存先ファイル

依存先ファイルでは、**実際に関係が検出されたクラス中心** に表示する。

---

## 19. `scope_root` 外依存の扱い

### 19.1 デフォルト動作

内部 import の解決先が `scope_root` 外であれば、**完全に無視し、図にも出さない**。

### 19.2 可観測性

図には出さないが、実行サマリには
**「scope 外のため探索を打ち切った件数」** を出す。

### 19.3 注記モード

初期版では図中 note は出さない。
必要なら将来拡張とする。

---

## 20. 出力仕様

### 20.1 必須出力

PlantUML の `.puml` ファイル。

### 20.2 `--output` 未指定時

**自動命名ファイルを生成** する。

### 20.3 出力先

`--output` 未指定時の出力先は **`execution_cwd`**。

### 20.4 自動命名

現時点では **タイムスタンプ中心** とする。

例:

* `pyclassuml_20260414_153210.puml`
* `pyclassuml_diff_20260414_153210.puml`

### 20.5 `--output` の相対パス

CLI 相対パスなので、**`execution_cwd` 基準** で解決する。

---

## 21. 色分け仕様

初期版の色分けは 2 分類。

1. changed class
2. dependency-only class

色そのものは設定可能だが、初期版では最低限のデフォルトテーマを持つ。
具体色は実装設計で決定する。

---

## 22. 可観測性

最低限、次を要約表示する。

* 起点ファイル数
* 到達ファイル数
* 抽出クラス数
* 抽出関係数
* changed class 数
* ignore されたファイル数
* 警告数
* scope 外のため探索を打ち切った件数
* `diff` で scope 外起点を除外した件数

---

## 23. エラー処理

### 23.1 通常モード

警告して継続する。

### 23.2 strict モード

エラー終了する。

### 23.3 エラー/strict 対象例

* import 解決失敗
* re-export 解決失敗
* forward reference 解決失敗
* wildcard import 解決失敗
* 構文エラー
* パス不正
* 出力失敗
* 探索上限到達
* `scope_root` と `package_root` の包含違反
* `generate` における scope 外起点
* `diff` における除外後起点 0 件

---

## 24. 再現性・決定性

同一入力、同一 Git 状態、同一設定であれば、**出力内容は同一** であること。
そのため、少なくとも以下は安定順序で処理・出力する。

* ファイル列挙順
* クラス列挙順
* 関係列挙順

ソート基準は実装設計で決めるが、**決定的であること** を要件とする。
なお自動命名のタイムスタンプはファイル名にのみ影響し、内容の決定性には含めない。

---

## 25. MVP 範囲

MVP に含めるものは以下。

* 外部 CLI として動作
* `generate` / `diff`
* `--cwd`
* `project_root` / `package_root` / `scope_root`
* ファイル / glob / ディレクトリ起点
* `scope_root` による探索制限
* `diff` における scope 外起点の除外
* default ignore + 追加 ignore
* import 深さ探索
* AST 静的解析
* 継承 / 属性保持 / 引数・戻り値依存
* typing コンテナ展開
* Union 展開
* wildcard import の `__all__` 限定対応
* `.puml` 出力
* changed / dependency-only 色分け
* `.pyclassuml.toml`
* strict / warn
* target Python
* untracked 切替
* 関係ラベルオプション
* nested class 非対応
* SQLAlchemy の `Mapped[T]` / `relationship("T")` ベストエフォート対応
* Pydantic の前方参照・自己参照のベストエフォート対応
* 外部基底クラスは非表示
* 実行サマリ出力

---

## 26. 将来拡張

* 複数 `package_root`
* 複数 `scope_root`
* diff hunk 単位の changed class 判定
* メソッド内部依存抽出の強化
* wildcard import 解決の強化
* namespace package の正式対応強化
* 外部基底クラスの簡易ノード表示オプション
* scope 外依存の図中注記
* 図の自動分割
* PNG / SVG 出力
* IDE / CI / pre-commit 連携
* deleted class の別レポート
* 出力ファイル名テンプレートの高度化

---

## 27. 結論

この仕様で、要件定義としては **確定版** にしてよい状態です。
残っているのは、主に実装設計で決めるべき具体値や内部構造です。

要件として特に強い骨格は次のとおりです。

* 外部 CLI として使う
* 実行コンテキストとして `execution_cwd` を明示的に持つ
* `project_root` / `package_root` / `scope_root` を明確に分離する
* `generate` と `diff` で scope の扱いを適切に分ける
* Python 静的解析として無理のない範囲に責務を絞る
* それでも SQLAlchemy / Pydantic など実務上重要な領域は補強する

この v2.0 を、そのまま実装フェーズの基準仕様として使えます。

