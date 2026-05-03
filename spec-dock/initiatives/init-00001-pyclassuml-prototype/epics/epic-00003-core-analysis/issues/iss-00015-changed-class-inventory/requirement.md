---
種別: 要件定義書（Issue）
ID: "iss-00015"
タイトル: "Changed Class Inventory"
関連GitHub: ["#15"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
親: ["epic-00003", "init-00001"]
---

# iss-00015 Changed Class Inventory — 要件定義（WHAT / WHY）

## 目的
- changed file 集合と parsed class 定義を突き合わせ、user-visible summary に出す changed class 数の meaning を固定する。
- 図に載る class selection と changed class summary semantics を分離し、`diff` で到達不可 class があっても summary がぶれないようにする。

## スコープ
- MUST:
  - changed file 集合に含まれる file 内 class 定義数を authoritative に数える。
  - count semantics を traversal / selection とは独立に保持する。
  - `ChangedClassInventory(class_count, changed_files)` を downstream `report` が使える形で handoff する。
  - changed file 数と changed class 数の両方を summary 素材として保持する。
- MUST NOT:
  - changed class を diff hunk 粒度で判定しない。
  - reachability を増減して count を調整しない。
  - summary stream や exit code を決めない。
- OUT OF SCOPE:
  - Git diff 自体の収集。
  - UML class selection。
  - output summary formatting。

## 受け入れ条件
- AC-001:
  - Actor:
    - CLI 利用者
  - Given:
    - changed file 集合と parsed module 群がある。
  - When:
    - changed class inventory を作る。
  - Then:
    - `ChangedClassInventory(class_count, changed_files)` が downstream に渡る。
  - 観測点:
    - DTO handoff review。
- AC-002:
  - Actor:
    - CLI 利用者
  - Given:
    - changed file に class はあるが reachable graph に乗らない fixture がある。
  - When:
    - changed class 数を算出する。
  - Then:
    - user-visible changed class 数にはその class を含める。
  - 観測点:
    - `fx-analyze-changed-unreachable` scenario。
- AC-003:
  - Actor:
    - CLI 利用者
  - Given:
    - class を持たない changed file が含まれる。
  - When:
    - changed class inventory を作る。
  - Then:
    - changed file 数には含めても changed class 数には加算しない。
  - 観測点:
    - `fx-analyze-changed-file-without-class` scenario。

## 例外・エッジケース
- EC-001:
  - 条件:
    - changed file が ignore されて upstream `TargetSet` には含まれない。
  - 期待:
    - ignore / seed normalization の owner を侵食せず、inventory は upstream handed-off changed file 集合だけを対象にする。
  - 観測点:
    - upstream ownership review。
- EC-002:
  - 条件:
    - changed file 内に class 定義はあるが、relation が 1 つも検出されない。
  - 期待:
    - changed class 数には加算するが、図の表示対象とは独立に扱う。
  - 観測点:
    - selection との分離 review。
- EC-003:
  - 条件:
    - 同一 file に複数 class がある。
  - 期待:
    - file 単位ではなく class 定義単位で数える。
  - 観測点:
    - counting rule review。
- EC-004:
  - 条件:
    - changed file 自体に syntax error があり、`ParsedModule` join が成立しない。
  - 期待:
    - `changed_files` には残すが `class_count` は増やさず、追加の inventory diagnostics は作らず parse-origin diagnostics をそのまま downstream が参照する。
  - 観測点:
    - `fx-analyze-changed-syntax-error-join-miss` scenario。

## 制約
- authoritative owner は `analyze` とする。
- count source は changed file 集合と parsed class 定義であり、render 後の図要素数ではない。
- `SelectedClasses` や relation inventory を count source に使わない。
- deterministic な file / class 走査順で count を得る。

## 未確定事項
- なし:
  - changed class summary semantics は initiative canonical docs と v5 で確定済みである。
