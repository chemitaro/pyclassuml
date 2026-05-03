---
種別: 要件定義書（Epic）
ID: "epic-00003"
タイトル: "Core Analysis"
関連GitHub: ["#3"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
親: ["init-00001"]
---

# epic-00003 Core Analysis — 要件定義（WHAT / WHY）

## 目的（Initiative との紐づき）
- initiative goal / metric:
  - `epic-foundation-contracts` が確定した `TargetSet`, `ExecutionContext`, `AnalysisConfig` を受け、AST-only / read-only / deterministic な解析核を M2 で成立させる。
  - 後続 `frameworks`, `render`, `report`, `app` が command 差分や path semantics を再解釈せずに downstream 処理へ進めるよう、`parse` / `analyze` の責務境界を固定する。
- この epic が提供する能力:
  - import 非実行 AST parse と module index 構築。
  - depth / package / scope 境界つき到達判定。
  - relation extraction と UML class selection。
  - changed file と class 定義を突き合わせた changed class inventory。

## ユースケース
- happy path:
  - `generate` で explicit target から得た `TargetSet` を parse / analyze に通し、到達ファイル、表示対象クラス、関係、changed class 数の材料を deterministic に得られる。
  - `diff` で diff target から得た `TargetSet` を同じ pipeline に通し、changed file に存在する class inventory と reachable graph を分離して downstream へ渡せる。
- exception / operation scenario:
  - 構文エラーや import 解決不能があっても `warn` で継続可能な範囲は diagnostics を保持して解析を続け、strict failure への昇格材料を downstream `report` に渡せる。
  - scope 境界や探索上限で traversal が停止した場合、停止理由と件数を `analyze` owner で保持し、summary 素材として後段へ handoff できる。

## Epic requirements
- E-RQ-001:
  - `iss-00012-parse-module-parse-and-index` は、`TargetSet` と `ExecutionContext` を入力に、import 非実行 AST parse、`ParsedModule[]` の構築、syntax diagnostics、dependency candidate への `project_root` 相対 ignore / default ignore 適用を固定する。
- E-RQ-002:
  - `iss-00013-analyze-traversal` は、`ParsedModule[]`, `ModuleIndex`, `ExecutionContext`, `AnalysisConfig` を入力に、depth / package / scope 境界つき reachability と `DependencyGraph` を固定する。
- E-RQ-003:
  - `iss-00014-analyze-relationship-and-selection` は、到達済み module 集合を入力に、relation extraction、起点ファイル内クラス全表示、依存先クラスの relation-based selection、および downstream `report` が再集計なしで使える relation/class counter と warning diagnostics の carry を固定する。
- E-RQ-004:
  - `iss-00015-changed-class-inventory` は、upstream handed-off changed file 集合と parsed class 定義だけを突き合わせ、selection semantics と独立した changed class summary semantics を固定する。
- E-RQ-005:
  - この epic の各 seam は、shared DTO と seam-local handoff の境界を明示し、`frameworks` 以降が core logic を再実行せずに `RenderReadyModel` を構築できる材料を渡す。
- E-RQ-006:
  - `parse` / `analyze` は AST-only / read-only / deterministic 制約を明示的に守り、対象コード import 実行、filesystem write、Git 直接参照を行わない。

## Epic acceptance criteria
- E-AC-001:
  - Given:
    - `epic-foundation-contracts` で正規化済みの `TargetSet`, `ExecutionContext`, `AnalysisConfig` がある。
  - When:
    - core-analysis の issue requirement / design をレビューする。
  - Then:
    - `parse -> analyze.traversal -> analyze.relationship-and-selection` と、`targets.diff-target-normalize + parse -> ChangedClassInventory` の dependency order と handoff が一意に説明できる。
  - 観測点:
    - initiative `plan.md` の issue baseline table、epic dependency diagram、issue design の handoff 節。
- E-AC-002:
  - Given:
    - 構文エラーを含む fixture と ignore 対象 dependency candidate を含む fixture がある。
  - When:
    - `iss-00012` の contract を適用する。
  - Then:
    - `fx-parse-syntax-error` で discard 範囲と diagnostics owner が説明でき、ignore 対象 candidate が graph 候補から除外される。
  - 観測点:
    - `iss-00012` の AC / EC と canonical verification。
- E-AC-003:
  - Given:
    - depth=0/1、scope 外 import、changed file に class はあるが到達 graph には乗らない fixture、class を持たない changed file fixture、relation ambiguity による warning diagnostics carry を含む fixture がある。
  - When:
    - `iss-00013` から `iss-00015` の contract を適用する。
  - Then:
    - traversal stop、relation-based selection、warning diagnostics carry、changed class counting の各 semantics が相互に混ざらず説明できる。
  - 観測点:
    - `fx-traversal-depth-matrix`, `fx-traversal-package-boundary`, `fx-traversal-scope-stop`, `fx-traversal-limit-reached`, `fx-analyze-changed-unreachable`, `fx-analyze-changed-file-without-class`, `fx-analyze-relation-only-dependency`, `fx-analyze-relation-ambiguity` を使った scenario review。

## スコープ
- MUST:
  - `iss-00012` から `iss-00015` までの 4 seams を対象にする。
  - `TargetSet` を command-neutral に受けて、後続 `frameworks` / `render` / `report` が消費できる解析結果へ変換する。
  - syntax degradation、traversal stop、relation extraction、changed class inventory の owner を `parse` / `analyze` に固定する。
- MUST NOT:
  - config discovery、explicit / diff target normalization、Git diff 収集を再実装しない。
  - SQLAlchemy / Pydantic の framework 補強、PlantUML text 生成、artifact write、exit policy 決定を肩代わりしない。
- OUT OF SCOPE:
  - framework-specific enrich。
  - render / report policy。
  - diff hunk 粒度 changed class 判定。
  - namespace package 完全対応、cache、parallelism。

## 境界
- Always:
  - `parse` は import 実行せず、`project_root`, `package_root`, `scope_root`, `ignore` を `config` owner の解釈どおりに使う。
  - `analyze` は `vcs` を直接読まず、changed file 情報は upstream handoff 経由でのみ扱う。
  - 起点ファイル内 class は原則すべて UML 掲載対象候補に含め、依存先 class は relation 検出を根拠に選別する。
  - changed class 数は「変更ファイル内に存在する class 定義数」を user-visible summary semantics とし、到達可否で減算しない。
- Ask:
  - traversal depth の意味論を package / scope 境界と独立に変えたい場合。
  - relation がない依存先 class を追加掲載したい場合。
  - changed class を diff hunk 粒度へ細分化したい場合。
- Never:
  - `frameworks` に traversal frontier 拡張を任せない。
  - `render` に class selection や changed class counting を再実装させない。
  - `report` に解析失敗の補正ロジックを持ち込まない。

## 非機能要件
- performance:
  - 同一 `TargetSet`、同一 roots、同一 diff 基準では、parse 順序、reachability、selection、summary 用 counter の順序が決定的であること。
- reliability / consistency:
  - syntax error、解決不能 import、scope stop、探索上限到達の ownership が曖昧でないこと。
  - `ChangedClassInventory` が traversal 結果に引きずられず、同一 changed file 集合に対して安定した count を返せること。
- security:
  - AST-only / read-only を守り、対象コード import 実行、書き込み、副作用のある Git 操作を行わないこと。
- operations:
  - `report` が summary を組み立てられるよう、到達ファイル数、抽出 class / relation 数、changed class 数、ignore 件数、scope 外探索停止件数の carry owner を明示すること。

## 依存 / 影響範囲
- impacted components:
  - `parse`
  - `analyze`
  - downstream consumer として `frameworks`, `render`, `report`, `app`
- external dependency:
  - target repository filesystem の read-only AST 読み取り
- compatibility:
  - initiative `requirement.md`, `design.md`, `plan.md`
  - `20260416t113919z-note-pyclassuml-architecture-v5.md`
  - `20260417t152718z-note-pyclassuml-prototype-roadmap-bridge-v1.md`
  - `epic-00002-foundation-contracts` の issue baseline と dependency order

## 未確定事項
- なし:
  - parse / traversal / selection / changed class counting の owner と dependency sequence は initiative canonical docs で確定済みである。
