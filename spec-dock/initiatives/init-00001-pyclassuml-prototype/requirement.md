---
種別: 要件定義書（Initiative）
ID: "init-00001"
タイトル: "PyClassUML Prototype"
関連GitHub: ["#1"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-04-16"
---

# init-00001 PyClassUML Prototype — 要件定義（WHAT / WHY）

## 目的（Outcome）
- Primary:
  - Python プロダクトを対象にした `pyclassuml` prototype の planning artifact を完成させる。
  - `generate` と `diff` の 2 つの入口を持つ外部 CLI prototype を、seam-first で実装可能な設計・計画へ落とし込む。
- Secondary:
  - SpecDock で段階実装しやすい seam-first の設計と planning 基盤を整える。
  - SQLAlchemy / Pydantic を含む実務上重要な典型パターンを best-effort で支援する。

## 背景と Why now
- 現状の課題:
  - Python プロダクトの設計把握や変更影響分析を、静的かつ非侵襲に行える外部 CLI が必要である。
  - `execution_cwd` / `project_root` / `package_root` / `scope_root` の意味論が強く、先に全体構造を固めないと patchwork 実装になりやすい。
- 影響:
  - 設計把握、差分可視化、レイヤ限定図の生成を共通ツールで扱える。
  - 後続の epic / issue 実装が seam 単位で進めやすくなる。
- なぜ今やるか:
  - 要件定義書 v2.0 が実装着手可能な粒度まで固まっており、prototype の設計と planning を確定できる状態にある。
- 情報源:
  - `20260416t080346z-research-pyclassuml-requirements-baseline-v2.md`
  - `20260416t113919z-note-pyclassuml-architecture-v5.md`

## 成功指標
- Metric-001:
  - Baseline:
    - 外部 CLI としての prototype は未実装
  - Target:
    - `generate` / `diff` により `.puml` を出力できる prototype 設計と実装計画が完結している
  - 計測方法:
    - initiative 配下の正本 docs と architecture bridge、epic / issue planning の整合で確認する
  - 判定時期:
    - initiative planning 完了時
- Metric-002:
  - Baseline:
    - 設計責務と epic / issue 分解規約が未確定
  - Target:
    - seam-first で epic / issue を切れる設計・計画があり、spec-review を通過できる
  - 計測方法:
    - review status と planning docs の completeness で確認する
  - 判定時期:
    - epic / issue 分解着手前

## スコープ
- MUST:
  - 外部 CLI として動作する prototype を設計・計画する
  - `generate` / `diff`
  - `diff` は `--base <ref>` と現在状態との差分を起点とする
  - `diff` における `working-tree | head` の current state 切替
  - `diff` における untracked 含有切替
  - `--cwd`
  - `project_root` / `package_root` / `scope_root`
  - AST-only の import graph 探索と UML `.puml` 出力
  - `strict` / `warn`、summary、deterministic ordering
  - SQLAlchemy `Mapped[T]` / `relationship("T")` と Pydantic forward reference の best-effort 対応
- MUST NOT:
  - 解析対象プロジェクトへ依存追加しない
  - 対象ソースコードを書き換えない
  - 対象コードを import 実行しない
- OUT OF SCOPE:
  - 複数 `package_root`
  - 複数 `scope_root`
  - diff hunk 単位 changed class 判定
  - namespace package 完全対応
  - PNG / SVG 出力
  - plugin architecture / multi-renderer / cache / parallelism

## 境界
- Always:
  - read-only、AST-only、deterministic を守る
  - `generate` と `diff` の差分は前段で吸収し、後段は共通 pipeline とする
  - `diff.current_state` の既定値は `working-tree`
  - `diff.include_untracked` の既定値は `true`
  - `current_state=head` のとき `include_untracked` は no-op とし、untracked は diff 起点に含めない
- Ask:
  - MVP 範囲と将来拡張の線引きが揺れるとき
  - project/package/scope boundary の意味論を変更したいとき
- Never:
  - 正本 doc の整合が崩れたまま実装に入らない
  - plugin / renderer 拡張を MVP より先に固定しない

## ステークホルダー / 影響範囲
- 利用者:
  - Python プロダクトの設計把握や差分可視化を行いたい開発者
- 運用者:
  - prototype では専任運用者は置かないが、CLI の使い勝手と summary 出力は将来運用前提で設計する
- 開発者:
  - SpecDock を使って epic / issue 単位で実装を進める開発者、レビュー担当者
- 影響システム / 領域:
  - target Python repository の read-only 解析
  - local git history の read-only 参照
  - `.puml` artifact 出力

## 非交渉制約
- 互換性:
  - 対象 repository 非侵襲
  - CLI 相対 path は `execution_cwd` 基準
- セキュリティ / 監査:
  - import 実行禁止
  - read-only access のみ
- 性能 / 可用性:
  - 安全上限を持ち、探索爆発時は error で停止する
- 運用:
  - summary で警告数、対象数、scope 除外数などの最低限の可観測性を持つ

## 受け入れ契約
- この initiative では、**外部から観測できる出力・終了コード・summary / diagnostics 振る舞い** を `requirement.md` の受け入れ条件として扱う。
- `v5` に記載する exit / degradation / handoff の詳細は、seam-level HOW の補助説明であり、外部観測契約の正本は本 `requirement.md` とする。

### 出力と終了コード
- success:
  - clean success と warning-only success では `.puml` を出力し、終了コードは `0`
  - 同一入力、同一設定、同一 Git 基準では、出力される PlantUML text の順序、grouping、label 表現は決定的である
- degraded success:
  - recoverable diagnostics があっても `DiagramModel` を構成できる場合は `.puml` を出力し、終了コードは `0`
  - `current_state=head` かつ `include_untracked=true` の場合は、untracked を diff 起点へ含めずに継続し、warning を 1 件以上残す
- degraded failure:
  - recoverable diagnostics の結果、`DiagramModel` を構成できない場合は `.puml` を出力せず、終了コードは non-zero
  - empty diagram を成功 artifact として扱わない
- hard failure:
  - パス不正 / 包含違反 / scope 契約違反 / diff 除外後起点 0 件 / 出力失敗 / 探索上限到達 / invalid `--base <ref>` / Git diff read failure は `.puml` を保証せず、終了コードは non-zero

### `.puml` artifact 出力契約
- `.puml` artifact の正本出力先は filesystem の output path とする
- `.puml` artifact 自体を stdout / stderr へ流すことは受け入れ契約に含めない
- success / warning-only success / degraded success では、`.puml` artifact を filesystem に書き出す
- `--output` 未指定時は `execution_cwd` 配下へ自動命名した `.puml` を書き出す
- `generate` の自動命名は `pyclassuml_YYYYMMDD_HHMMSS.puml` とする
- `diff` の自動命名は `pyclassuml_diff_YYYYMMDD_HHMMSS.puml` とする
- 同名ファイルが既に存在する場合は、末尾に `_2`, `_3`, ... を付けて衝突回避する
- `--output` 指定時は、CLI 相対 path を `execution_cwd` 基準で解決した先へ `.puml` を書き出す
- success path の summary 出力と `.puml` artifact 書き出しは両立し、summary は stream、artifact は filesystem として分離して観測できる

### `ignore` の可観測契約
- `--ignore` の glob は `project_root` 相対で評価する
- `ignore` は seed 候補にも依存探索候補にも適用する
- default ignore は次を canonical set とする
  - `.venv/**`
  - `venv/**`
  - `**/__pycache__/**`
  - `site-packages/**`
- default ignore と user ignore の両方が最終 target selection と `.puml` 内容に反映される
- `ignore されたファイル数` は summary 上で観測できる

### config merge の可観測契約
- `.pyclassuml.toml` が存在し読み込める場合、その設定値は CLI 引数と merge されて最終実行設定に反映される
- 優先順位は CLI 引数 > config file > default とする
- `--config` 指定時はその path を使う
- `--config` 未指定かつ `--project-root` 指定時は、まず `<project_root>/.pyclassuml.toml` を探す
- 上記で見つからない場合は、`execution_cwd` から親方向へ辿り、最初に見つかった `.pyclassuml.toml` を使う
- `--config` 未指定かつ `--project-root` 未指定時は、最初から `execution_cwd` から親方向へ辿り、最初に見つかった `.pyclassuml.toml` を使う
- config file が見つからない場合は default 設定で継続する
- config file 内の相対 path は `relative_path_base` で解決基準を切り替える
  - `relative_path_base=config` を default とし、config file 自身の配置ディレクトリ基準で解決する
  - `relative_path_base=cwd` 指定時は `execution_cwd` 基準で解決する
- config file が読み込まれ、CLI と config のどちらでも `project_root` が明示されない場合は、config file 自身の配置ディレクトリを `project_root` の fallback とする
- config 読込失敗、無効値、path 解決不能、包含違反は hard failure として non-zero で終了する
- config merge の結果として確定した `project_root` / `package_root` / `scope_root` / `ignore` / `output` は最終 target selection、summary、artifact path に観測可能な差を生む

### CLI の可観測挙動
- usage error や不正オプション入力では non-zero で終了し、failure summary には `cli_usage_error` を使う
- failure path では diagnostics / summary を stderr に出し、stdout を正本出力経路として使わない
- `diff.current_state` と `diff.include_untracked` の切替結果は、changed seed と warning / summary の違いとして user-visible に観測できる

### `target_python` 契約
- `target_python` は Python 3 系の target version hint とし、canonical 表現は `3.<minor>` 文字列に固定する
- semantic validation の owner は `config` とし、CLI 起点・config 起点を問わず最終的に採用された値を `config` が検証する
- `AnalysisConfig.target_python` の canonical state は `null | 3.<minor>` とし、未指定時は `null` を使う
- 不正な `target_python` 値は入力元に関係なく `invalid_config_or_config_path` を使う
- 有効な `target_python` は `AnalysisConfig.target_python` として carry され、downstream `parse` / `analyze` seam が version-sensitive な syntax / typing interpretation の authoritative hint として使う
- prototype では `target_python` 自体を summary counter にしないが、invalid value による failure と、version-sensitive diagnostics の差として user-visible に観測できる

### `strict` / `warn` の外部契約
- strict mode では、次の事象を failure に昇格させる
  - import / re-export / forward reference 解決失敗
  - wildcard import 解決不能
  - 構文エラー
  - `diff` における scope 外起点の除外
- `warn` mode の `diff` では、scope 外 changed file が一部存在しても scope 内 changed file が残る限り、scope 外 changed file は除外し、warning を残して継続する
- `warn` mode では warning として継続できる事象であっても、最終的に `DiagramModel` を構成できない場合は degraded failure として non-zero に昇格する
- `warn` / `strict` を問わず、パス不正 / 包含違反 / `generate` の scope 外起点 / `diff` 除外後起点 0 件 / 出力失敗 / 探索上限到達 / invalid `--base <ref>` / Git diff read failure は hard failure とする
- strict mode では、上記 4 種以外の warning 系事象を追加で failure に昇格させない

### framework support の可観測成功条件
- SQLAlchemy `Mapped[T]` が解決できる場合は、`T` に対応する内部 class relation が UML へ反映される
- SQLAlchemy `relationship("T")` が一意に解決できる場合は、`T` に対応する内部 class relation が UML へ反映される
- SQLAlchemy `relationship("T")` が曖昧または解決不能な場合は、warning / diagnostics を残し、relation は追加しない
- Pydantic forward reference が解決できる場合は、対応する内部 class relation が UML へ反映される
- Pydantic / SQLAlchemy の best-effort 補強に失敗しても、既知の class / relation が保持できる限り `warn` mode では継続する

### UML 掲載対象の可観測契約
- 起点ファイル内の class は原則としてすべて UML 掲載対象に含める
- 依存先ファイル内の class は、関係が検出された class を中心に UML 掲載対象へ含める
- relation が検出されない依存先 class を無制限に追加しない
- framework 補強や degraded output shaping は、上記の掲載対象契約を壊さない範囲で relation / class を補強または削減する

### failure path の可観測性
- degraded failure と hard failure の両方で、summary は **必ず** 出力する
- failure summary には少なくとも次を含める
  - 起点ファイル数
  - 到達ファイル数
  - 抽出クラス数
  - 抽出関係数
  - changed class 数
  - ignore されたファイル数
  - 警告数
  - scope 外のため探索を打ち切った件数
  - `diff` で scope 外起点を除外した件数
  - failure reason の種別
- failure path では、保持できている diagnostics と summary を stderr に出す

### success path の可観測性
- clean success / warning-only success / degraded success のすべてで、summary は **必ず** 出力する
- success path の summary は stdout に出す
- success path で保持された warning diagnostics は、別 stream に分離せず summary に内包して stdout で観測できる形にする
- success path の summary には少なくとも次を含める
  - 起点ファイル数
  - 到達ファイル数
  - 抽出クラス数
  - 抽出関係数
  - changed class 数
  - ignore されたファイル数
  - 警告数
  - scope 外のため探索を打ち切った件数
  - `diff` で scope 外起点を除外した件数
- warning-only success と degraded success では、warning の存在が summary 上で観測できる
- `current_state=head` かつ `include_untracked=true` の no-op warning は、summary text 上でも観測できる

### summary counter semantics
- `起点ファイル数`:
  - `TargetSet` に正規化された一意な seed file 数
- `到達ファイル数`:
  - traversal の結果として到達した内部 Python file 数
- `抽出クラス数`:
  - 最終的に UML 表示対象として選別された class 数
- `抽出関係数`:
  - 最終 `DiagramModel` に採用された relation 数
- `changed class 数`:
  - 到達可否ではなく、変更ファイル内に存在する class 定義数
- `ignore されたファイル数`:
  - default ignore と user ignore により seed 候補または探索候補から除外された file 数
- `警告数`:
  - summary 時点まで保持された recoverable diagnostics と no-op warning の件数
- `scope 外のため探索を打ち切った件数`:
  - traversal 中に scope 外の内部依存として探索打ち切りになった件数
- `diff` で scope 外起点を除外した件数:
  - diff seed 生成後に scope pre-filter で除外された changed file 数
- early hard failure fallback:
  - `invalid_path_or_containment` や `vcs_read_failure` のように producer seam が未実行のまま失敗した counters は `0` を出す

### degraded output shaping rules
- `syntax error in module`:
  - 該当 module 全体を解析対象から外し、他 module の graph / class / relation は保持する
- `import / re-export 解決失敗`:
  - 当該 import に依存する unresolved edge だけを落とし、解決済み edge と既知 class は保持する
- `forward reference / wildcard 解決不能`:
  - unresolved type に由来する relation edge だけを落とし、class 本体と解決済み relation は保持する
- `current_state=head` かつ `include_untracked=true`:
  - untracked file の diff seed 取り込みだけを落とし、`head` 基準で得られる changed file は保持する
- 上記の keep / discard を適用した結果 `DiagramModel` を構成できない場合は `diagram_unbuildable_after_recovery` として degraded failure に昇格する

### failure reason taxonomy
- failure summary に出す `failure reason` の種別は、少なくとも次の有限集合に固定する
  - `cli_usage_error`
  - `invalid_config_or_config_path`
  - `invalid_path_or_containment`
  - `strict_diff_scope_exclusion`
  - `generate_scope_violation`
  - `generate_zero_target_after_normalize`
  - `diff_zero_target_after_scope_filter`
  - `strict_resolution_failure`
  - `strict_syntax_error`
  - `strict_wildcard_resolution_failure`
  - `traversal_limit_reached`
  - `output_write_failure`
  - `vcs_read_failure`
  - `diagram_unbuildable_after_recovery`
- recoverable diagnostics の結果、`DiagramModel` を構成できず failure へ昇格した場合は `diagram_unbuildable_after_recovery` を使う
- usage error や不正オプション入力は `cli_usage_error` を使う
- config read failure、invalid config value、unresolved config path は `invalid_config_or_config_path` を使う
- `generate` で explicit normalize 後に seed が 0 件になった hard failure は `generate_zero_target_after_normalize` を使う
- `diff` で scope 外 changed file が除外され、strict mode により failure へ昇格した場合は `strict_diff_scope_exclusion` を使う
- invalid `--base <ref>` や Git diff read failure は `vcs_read_failure` を使う

## リスク / 依存
- R-001:
  - path semantics と ownership が揺れると epic / issue 分解全体が不安定になる
- R-002:
  - `model` と `report` が dumping ground 化すると downstream 実装が崩れる

## 未確定事項
- Q-001:
  - 質問:
    - なし。prototype initiative の planning 完了条件としては着手可能な状態まで固定する。
  - 選択肢:
    - A:
      - n/a
    - B:
      - n/a
  - 推奨案:
    - 今後の残論点は issue / epic 設計または将来拡張へ送る
  - 影響範囲:
    - initiative planning 以降
