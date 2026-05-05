---
種別: 要件定義書（Issue）
ID: "iss-00033"
タイトル: "Render Diff Class Colorization"
関連GitHub: ["#33"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-05"
親: ["epic-00004", "init-00001"]
---

# iss-00033 Render Diff Class Colorization — 要件定義（WHAT / WHY）

## 目的
- `pyclassuml diff` の PlantUML class diagram で、Git 差分に含まれる changed class と、到達関係によって図に載る dependency-only class を色分けして表示する。
- 初期 research baseline の「changed / dependency-only 色分け」を正式 issue scope に昇格し、差分図をレビューしやすくする。

## 背景・現状
- 現状の挙動:
  - `pyclassuml diff --base <ref>` は、ブランチ名 / commit hash / tag などの Git ref を基点に changed files を収集し、差分起点の class diagram を生成できる。
  - summary には `changed_class_count` が出る。
  - ただし `.puml` 上の class box は通常表示のみで、changed class と dependency-only class を視覚的に区別できない。
- 現状の課題:
  - 差分レビュー時に、実際に変更された class と、関連として図に載っただけの class を目視で追い分ける必要がある。
  - 初期 baseline には「changed class / dependency-only class の 2 分類色分け」が定義されていたが、既存の diff / changed inventory / render issue には正式要件として取り込まれていない。
- 再現手順:
  1. Git 管理された Python project で class を含む file を変更する。
  2. `pyclassuml diff --base <ref> --current-state working-tree --output diff.puml` を実行する。
  3. `.puml` の class box を確認する。
- 観測点:
  - `.puml`: changed class と dependency-only class に異なる style / color が付与される。
  - SVG: PlantUML 変換後に色分けが視覚的に確認できる。
  - summary: 既存の `changed_class_count` は維持される。
- 情報源:
  - `spec-dock/initiatives/init-00001-pyclassuml-prototype/discussions/20260416t080346z-research-pyclassuml-requirements-baseline-v2.md`
    - `## 21. 色分け仕様`
    - `changed class`
    - `dependency-only class`
    - `changed / dependency-only 色分け`

## 対象ユーザー / 利用シナリオ
- 主な利用者:
  - Pull Request や作業ブランチの変更影響を UML class diagram で確認したい開発者。
- 代表シナリオ:
  - `main` や特定 commit からの差分を `pyclassuml diff` で図示し、変更された class と依存関係で表示された class を一目で読み分ける。

## スコープ
- MUST:
  - `pyclassuml diff` の出力 class box を、少なくとも 2 分類で色分けする。
  - changed class:
    - `--base <ref>` からの Git 差分に含まれる changed file 内で定義され、diff diagram に表示される class。
  - dependency-only class:
    - diff 起点の traversal / relation selection によって表示されるが、changed file 内 class ではない class。
  - 初期版はデフォルトテーマを持ち、設定なしで色分けされた `.puml` / SVG が得られる。
  - `.puml` は PlantUML 標準記法で色分けを表現し、PlantUML Docker 変換で SVG に反映される。
  - `generate` command の通常図には diff-specific colorization を適用しない。
  - 既存の class member rendering、composition / aggregation、inheritance / Protocol realization、uses relation の表現を維持する。
  - `changed_class_count` summary semantics を維持する。
- MUST NOT:
  - 対象コードを import 実行しない。
  - 対象ソースコードを書き換えない。
  - Git diff の hunk 粒度で method / field 単位の変更判定を行わない。
  - 追加 / 変更 / 削除の 3 分類色分けをこの issue の必須要件にしない。
  - render 層が Git を直接読む実装にしない。
- OUT OF SCOPE:
  - ユーザー設定による任意カラーテーマ指定。
  - hunk 粒度の changed member highlight。
  - deleted class の墓標表示。
  - relation edge の色分け。
  - HTML / PNG など SVG 以外の追加出力形式。

## 境界
- Always:
  - Git ref / changed file collection は既存 `vcs` / `targets.diff` owner に従う。
  - changed class 判定は existing changed-file context と parsed class definition の join を根拠にする。
  - render は downstream handoff された class decoration 情報だけを使い、Git を直接読まない。
  - 同一入力、同一 base ref、同一 working tree では同一 `.puml` を出力する。
- Ask:
  - 追加 / 変更 / 削除の 3 分類、deleted class 表示、または user configurable colors まで同時に入れたい場合。
- Never:
  - runtime inspection や import 実行で changed / dependency-only を判定しない。
  - summary の `changed_class_count` を図に表示された colored class 数から逆算しない。

## 非交渉制約
- 外部 CLI として動作する。
- 解析対象 project の依存関係を増やさない。
- 対象 repository に対して read-only で動作する。
- 対象コードを import 実行しない。
- AST-only / deterministic ordering を維持する。

## 前提
- `pyclassuml diff --base <ref>` は実装済みで、Git ref から changed files を収集できる。
- `ChangedClassInventory(class_count, changed_files)` は実装済みで、changed file と class definition の関係を summary 用に保持している。
- render は class decoration / stereotype を PlantUML に出力できる既存 seam を持つ。
- `iss-00032` により field ownership relation は `*--` / `o--` として出力できる。

## 受け入れ条件
- AC-001:
  - Actor: pyclassuml user
  - Given: `--base <ref>` からの差分に `Order` class を含む changed file がある
  - When: `pyclassuml diff --base <ref> --current-state working-tree --output diff.puml` を実行する
  - Then: `Order` の class box は changed class として色分けされる。
  - 観測点: `.puml` に `Order` へ changed class 用の PlantUML style / color が付与され、SVG 変換後に視覚的に区別できる。
- AC-002:
  - Actor: pyclassuml user
  - Given: changed class が `Customer` に relation を持ち、`Customer` 自体は changed file 内 class ではない
  - When: `pyclassuml diff` が diagram を生成する
  - Then: `Customer` は dependency-only class として changed class とは別色で表示される。
  - 観測点: `.puml` / SVG で changed class と dependency-only class の class box 色が異なる。
- AC-003:
  - Actor: pyclassuml user
  - Given: `pyclassuml generate` を実行する
  - When: 通常の class diagram を生成する
  - Then: diff-specific colorization は適用されない。
  - 観測点: generate 出力に changed / dependency-only style が出ない。
- AC-004:
  - Actor: pyclassuml maintainer
  - Given: `iss-00032` の composition / aggregation fixture がある
  - When: `pyclassuml diff` で色分け付き diagram を生成する
  - Then: class box colorization と relation notation が併存し、`*--` / `o--` / `-up-|>` / `..up|>` / `..>` は regression しない。
  - 観測点: automated tests と manual `.puml` / SVG inspection。
- AC-005:
  - Actor: pyclassuml maintainer
  - Given: 同じ diff input が複数回実行される
  - When: `.puml` を比較する
  - Then: class order、style declaration、色分け結果は deterministic である。
  - 観測点: snapshot / text equality test。

## 例外・エッジケース
- EC-001:
  - 条件: changed file に class 定義がない。
  - 期待: 図に changed class color は追加されず、既存の summary / warning 方針を維持する。
  - 観測点: `.puml` と `changed_class_count`。
- EC-002:
  - 条件: changed file 内 class が traversal / selection 結果に含まれない。
  - 期待: summary の changed class count は既存 semantics を維持し、図に表示されない class へ無理に color declaration を作らない。
  - 観測点: summary と `.puml` の分離。
- EC-003:
  - 条件: changed file が syntax error で parsed class join に失敗する。
  - 期待: changed class color を捏造せず、parse diagnostics と既存 failure / warning 方針を維持する。
  - 観測点: diagnostics と `.puml`。
- EC-004:
  - 条件: untracked file を含む diff、または `--current-state head` が指定される。
  - 期待: 既存の changed-file collection semantics に従い、colorization は downstream された changed-file context だけを反映する。
  - 観測点: working-tree / head / include-untracked matrix。

## 入力→出力例
- EX-001:
  - Input:
    ```bash
    pyclassuml diff --base main --current-state working-tree --output diff.puml
    ```
  - Expected diagram semantics:
    ```text
    Order: changed class color
    Customer: dependency-only class color
    Order *-- Customer: existing relation notation unchanged
    ```

## 用語
- TERM-001:
  - changed class: Git 差分に含まれる changed file 内で定義され、diff diagram に表示される class。
- TERM-002:
  - dependency-only class: changed class の依存・関係先として diagram に表示されるが、changed file 内 class ではない class。
- TERM-003:
  - default theme: 設定なしで使う初期色。具体色は design で決める。

## 未確定事項
- 該当なし。初期版は baseline どおり changed class / dependency-only class の 2 分類色分けを実装対象にする。
