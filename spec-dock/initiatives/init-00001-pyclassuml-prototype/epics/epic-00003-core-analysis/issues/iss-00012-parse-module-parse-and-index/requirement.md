---
種別: 要件定義書（Issue）
ID: "iss-00012"
タイトル: "Parse Module Parse And Index"
関連GitHub: ["#12"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
親: ["epic-00003", "init-00001"]
---

# iss-00012 Parse Module Parse And Index — 要件定義（WHAT / WHY）

## 目的
- `TargetSet` を import 非実行 AST parse に変換し、`analyze` が一貫して消費できる `ParsedModule[]` の正本を作る。
- syntax degradation と dependency candidate ignore を `parse` seam に閉じ、後続 traversal / relation extraction が raw filesystem 探索を再実装しない状態を作る。

## スコープ
- MUST:
  - `TargetSet.seed_files` を起点に `.py` source を import 非実行 AST parse する。
  - `ParsedModule(module_path, imports, classes, diagnostics)` を構築する。
  - syntax error を diagnostics として保持し、strict failure への昇格材料を downstream へ渡す。
  - 依存探索中に発見した candidate file に対して `project_root` 相対 ignore と default ignore を適用する。
  - `package_root` / `scope_root` を跨ぐかどうか判断するための module lookup 材料を保持する。
- MUST NOT:
  - 対象コード import 実行をしない。
  - traversal depth や relation selection を決めない。
  - Git diff を直接読まない。
- OUT OF SCOPE:
  - relation extraction。
  - changed class counting。
  - framework-specific enrich。

## 受け入れ条件
- AC-001:
  - Actor:
    - CLI 利用者
  - Given:
    - `targets.explicit-target-normalize` または `targets.diff-target-normalize` から `TargetSet` が渡される。
  - When:
    - `parse.module-parse-and-index` を実行する。
  - Then:
    - 起点 file ごとに `ParsedModule[]` が得られ、後続 `analyze` が raw source を再読せずに解析を進められる。
  - 観測点:
    - `ParsedModule[]` handoff review。
- AC-002:
  - Actor:
    - CLI 利用者
  - Given:
    - syntax error を含む fixture がある。
  - When:
    - AST parse を行う。
  - Then:
    - 構文エラーを含む module の discard 範囲と diagnostics owner が `parse` として説明できる。
  - 観測点:
    - `fx-parse-syntax-error` scenario。
- AC-003:
  - Actor:
    - CLI 利用者
  - Given:
    - import で辿れる candidate file の中に ignore 対象が含まれる。
  - When:
    - candidate file を index 対象へ追加しようとする。
  - Then:
    - ignore 対象は graph 候補から除外され、ignore 件数の材料が downstream に渡る。
  - 観測点:
    - `fx-parse-ignored-dependency-candidate` scenario。

## 例外・エッジケース
- EC-001:
  - 条件:
    - 起点 file は parse できるが、その import 先 candidate に syntax error がある。
  - 期待:
    - 起点 module の parse 結果は保持し、error module の diagnostics を downstream に渡す。
  - 観測点:
    - syntax degradation の discard 範囲 review。
- EC-002:
  - 条件:
    - import candidate が `scope_root` 配下には存在するが ignore pattern に一致する。
  - 期待:
    - traversal 候補へ加えず、ignore owner は `parse` として扱う。
  - 観測点:
    - ignore 件数の carry review。
- EC-003:
  - 条件:
    - import candidate が `package_root` 外にあり内部 import graph に昇格できない。
  - 期待:
    - `parse` は candidate path / module lookup 材料を保持するが、frontier へ採用するかどうかの最終判断は行わない。
    - `package_root` 外 candidate を internal reachable module として frontier に採用するかの owner は `analyze.traversal` である。
  - 観測点:
    - parse / traversal の owner boundary review。

## 制約
- AST-only / read-only / deterministic を守る。
- parse 順序、diagnostics 順序、candidate 列挙順は同一入力で安定している。
- `ignore` の解釈 owner は `config` であり、`parse` はその確定済み値だけを消費する。

## 未確定事項
- なし:
  - `ParsedModule[]`、syntax degradation、dependency candidate ignore の owner は initiative canonical docs で確定済みである。
