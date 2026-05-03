---
種別: 要件定義書（Issue）
ID: "iss-00009"
タイトル: "Targets Explicit Target Normalize"
関連GitHub: ["#9"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
親: ["epic-00002", "init-00001"]
---

# iss-00009 Targets Explicit Target Normalize — 要件定義（WHAT / WHY）

## 目的
- `generate` の explicit input を、後段が command-neutral に扱える `TargetSet(seed_files)` へ正規化する。
- file / glob / dir 起点、dedupe、`project_root` 相対 ignore、scope outside fail を `targets` seam に閉じる。

## スコープ
- MUST:
  - file / glob / dir 形式の explicit input を受け付ける。
  - CLI 相対 path は `execution_cwd` 基準で解釈する。
  - `project_root` 相対で default ignore と user ignore を評価する。
  - 正規化後の Python source file（`*.py`、`__init__.py` を含む）だけを dedupe して `TargetSet` に格納する。
  - scope 外 explicit target は failure とする。
- MUST NOT:
  - Git diff を読まない。
  - dependency candidate ignore や import graph 解析をしない。
  - class selection や changed class counting をしない。
- OUT OF SCOPE:
  - `diff` seed normalization。
  - dependency traversal 中に発見された candidate file への ignore 適用。
  - non-Python file を parse seam へ渡すこと。

## 受け入れ条件
- AC-001:
  - Actor:
    - `generate` 利用者
  - Given:
    - file / glob / dir の explicit input がある。
  - When:
    - target normalize を行う。
  - Then:
    - 重複のない `TargetSet(seed_files)` が生成される。
  - 観測点:
    - file + glob + dir input review。
- AC-002:
  - Actor:
    - `generate` 利用者
  - Given:
    - default ignore と user ignore が設定されている。
  - When:
    - target normalize を行う。
  - Then:
    - `project_root` 相対 ignore が seed 候補に適用される。
  - 観測点:
    - ignore scenario review。
- AC-003:
  - Actor:
    - `generate` 利用者
  - Given:
    - scope 外 explicit target が含まれる。
  - When:
    - target normalize を行う。
  - Then:
    - hard failure となり、後段 parse を呼ばない。`failure_reason` には `generate_scope_violation` を使う。
  - 観測点:
    - scope outside failure scenario。
- AC-004:
  - Actor:
    - `generate` 利用者
  - Given:
    - glob が 0 件に展開される、または候補がすべて ignore される。
  - When:
    - target normalize を行う。
  - Then:
    - zero-seed hard failure となり、empty `TargetSet` を success として返さず、後段 parse を呼ばない。`failure_reason` には `generate_zero_target_after_normalize` を使う。
  - 観測点:
    - zero-seed explicit scenario。

## 例外・エッジケース
- EC-001:
  - 条件:
    - 同じ file が file 指定と glob 展開の両方で現れる。
  - 期待:
    - `TargetSet.seed_files` では 1 回だけ保持する。
  - 観測点:
    - dedupe review。
- EC-002:
  - 条件:
    - dir / glob 展開結果に ignore 対象 file が含まれる。
  - 期待:
    - ignore 対象は seed から除外される。
  - 観測点:
    - default ignore / user ignore scenario。
- EC-003:
  - 条件:
    - relative input が渡される。
  - 期待:
    - `execution_cwd` 基準で解釈される。
  - 観測点:
    - path base review。
- EC-004:
  - 条件:
    - normalize 完了時点で seed file が 0 件である。
  - 期待:
    - `targets.explicit-target-normalize` owner で deterministic に failure を確定し、後段で空集合を再判定させない。
  - 観測点:
    - glob miss / all ignored scenario。

## 制約
- ignore canonical set は initiative `requirement.md` の default ignore に従う。
- `TargetSet` は後段 parse が command を意識せず消費できる集合でなければならない。
- scope outside fail は `generate` 側 contract であり、partial continue しない。
- explicit normalize 完了時に seed 0 件なら hard failure とし、empty artifact path を success にしない。
- explicit zero-seed hard failure の `failure_reason` は `generate_zero_target_after_normalize` に固定する。

## 未確定事項
- なし:
  - seed normalization の owner と observable behavior は initiative canonical docs で確定済みである。
