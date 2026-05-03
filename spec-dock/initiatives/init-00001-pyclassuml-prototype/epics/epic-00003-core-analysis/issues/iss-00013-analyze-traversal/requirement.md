---
種別: 要件定義書（Issue）
ID: "iss-00013"
タイトル: "Analyze Traversal"
関連GitHub: ["#13"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
親: ["epic-00003", "init-00001"]
---

# iss-00013 Analyze Traversal — 要件定義（WHAT / WHY）

## 目的
- `ParsedModule[]` を受けて、depth / package / scope 境界つきの reachability を `analyze` seam で authoritative に確定する。
- traversal stop の理由と件数を保持し、relation extraction と report summary が同じ frontier を共有できるようにする。

## スコープ
- MUST:
  - `ParsedModule[]`, `ModuleIndex`, `ExecutionContext`, `AnalysisConfig` を入力に `DependencyGraph(reachable_files, edges)` を構築する。
  - parse から受け取った seed provenance を保持し、起点 frontier を deterministic に確定する。
  - `package_root` と `scope_root` の境界を守る。
  - depth は seed module を hop `0`、seed module の direct import を hop `1` とする import-graph hop semantics として deterministic に扱う。
  - scope 外で frontier を打ち切った件数を保持する。
  - 探索上限到達を `analyze` owner の error として扱う。
- MUST NOT:
  - relation extraction や class selection を決めない。
  - changed class 数を算出しない。
  - framework-specific fallback で frontier を拡張しない。
- OUT OF SCOPE:
  - wildcard import や forward reference の best-effort 補強。
  - render-ready な relation 形成。

## 受け入れ条件
- AC-001:
  - Actor:
    - CLI 利用者
  - Given:
    - 到達可能 import と到達不能 import を含む parsed module 群がある。
  - When:
    - traversal を実行する。
  - Then:
    - `DependencyGraph` に reachable file と edge が記録される。
  - 観測点:
    - graph handoff review。
- AC-002:
  - Actor:
    - CLI 利用者
  - Given:
    - depth=0 と depth=1 の実行条件がある。
  - When:
    - traversal を実行する。
  - Then:
    - `depth=0` では seed module だけが reachable になり、`depth=1` では seed module の direct import までが reachable になる。
  - 観測点:
    - `fx-traversal-depth-matrix` scenario。
- AC-003:
  - Actor:
    - CLI 利用者
  - Given:
    - import candidate の一部が `scope_root` 外にある。
  - When:
    - traversal を継続する。
  - Then:
    - scope 外 candidate は frontier 拡張に使わず、scope stop 件数が保持される。
  - 観測点:
    - `fx-traversal-scope-stop` scenario。
- AC-004:
  - Actor:
    - CLI 利用者
  - Given:
    - import candidate の一部が `package_root` 外にある。
  - When:
    - traversal を継続する。
  - Then:
    - `package_root` 外 candidate は frontier に含めない。
  - 観測点:
    - `fx-traversal-package-boundary` scenario。

## 例外・エッジケース
- EC-001:
  - 条件:
    - reachable module 数が安全上限を超える。
  - 期待:
    - `analyze` owner の error として停止理由が downstream に渡る。
  - 観測点:
    - `fx-traversal-limit-reached` scenario。
- EC-002:
  - 条件:
    - parse 済み module はあるが、内部 import graph 上でどこにも到達しない dependency candidate がある。
  - 期待:
    - `DependencyGraph` には含めず、後段 selection は reachable set だけを入力にする。
  - 観測点:
    - unreachable candidate review。
- EC-003:
  - 条件:
    - diff 実行で changed file 自体はあるが、そこから辿れる内部 dependency が `scope_root` 外しかない。
  - 期待:
    - changed class semantics には干渉せず、traversal では scope stop を保持するだけに留める。
  - 観測点:
    - traversal / changed inventory boundary review。

## 制約
- `analyze.traversal` は `vcs` を直接読まない。
- frontier owner は `analyze` とし、`frameworks` や `render` が到達範囲を追加しない。
- `package_root` 外 candidate の frontier 採否 owner は `analyze.traversal` とし、`parse` は candidate lookup 材料の保持までに留める。
- reachable set と停止件数の順序は deterministic にする。
- candidate の frontier 採否判定順は `package_root` 外判定 -> `scope_root` 外判定 -> depth 超過判定とし、複数条件に当たる candidate でも最初に成立した理由だけを authoritative stop reason として扱う。

## 未確定事項
- なし:
  - traversal boundary と stop owner は initiative canonical docs で確定済みである。
