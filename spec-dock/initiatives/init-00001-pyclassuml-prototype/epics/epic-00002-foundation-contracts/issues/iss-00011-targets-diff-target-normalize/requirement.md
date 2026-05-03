---
種別: 要件定義書（Issue）
ID: "iss-00011"
タイトル: "Targets Diff Target Normalize"
関連GitHub: ["#11"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
親: ["epic-00002", "init-00001"]
---

# iss-00011 Targets Diff Target Normalize — 要件定義（WHAT / WHY）

## 目的
- `vcs.diff-file-collect` が集めた changed files を、scope filtering 済みの `TargetSet(seed_files)` に正規化する。
- `diff` における scope outside exclusion と zero-target fail を `targets` seam に閉じる。

## スコープ
- MUST:
  - changed files から scope 内の Python source file だけを `TargetSet.seed_files` に変換する。
  - `project_root` 相対で default ignore と user ignore を changed-file seed 候補へ適用する。
  - scope 外 changed file は exclusion として記録する。
  - scope filtering 後に seed が 0 件なら failure とする。
  - exclusion diagnostics / counters を downstream へ carry する。
- MUST NOT:
  - Git diff を再実行しない。
  - explicit target normalize を行わない。
  - changed class summary や `.puml` 出力を行わない。
- OUT OF SCOPE:
  - final exit code 判定。
  - summary stream routing。

## 受け入れ条件
- AC-001:
  - Actor:
    - `diff` 利用者
  - Given:
    - scope 内外が混在する changed files がある。
  - When:
    - diff target normalize を行う。
  - Then:
    - scope 内 file だけが `TargetSet.seed_files` に残り、scope 外 file は exclusion として記録される。
  - 観測点:
    - scope outside exclusion scenario。
- AC-002:
  - Actor:
    - `diff` 利用者
  - Given:
    - scope filtering 後の seed が 0 件になる。
  - When:
    - diff target normalize を行う。
  - Then:
    - `diff_zero_target_after_scope_filter` を持つ failure として後段 parse を呼ばない。
  - 観測点:
    - zero-target fail scenario。
- AC-003:
  - Actor:
    - `report` / `app.diff-wiring` 実装者
  - Given:
    - exclusion が発生している。
  - When:
    - downstream が diagnostics を読む。
  - Then:
    - strict / warn の最終 policy を決めるための exclusion diagnostics / counter が保持されている。strict 昇格時に downstream が `strict_diff_scope_exclusion` を選べるだけの handoff を行う。
  - 観測点:
    - handoff review。

## 例外・エッジケース
- EC-001:
  - 条件:
    - changed files がすべて scope 外。
  - 期待:
    - exclusion 後に zero-target fail となる。
  - 観測点:
    - all-outside scenario。
- EC-002:
  - 条件:
    - 同じ file が changed-file collection に重複して含まれる。
  - 期待:
    - `TargetSet.seed_files` は unique 集合として扱う。
  - 観測点:
    - dedupe review。
- EC-003:
  - 条件:
    - `vcs` から no-op warning や invalid-base failure が渡される。
  - 期待:
    - その diagnostics を失わず carry し、自身は scope filtering だけに集中する。
  - 観測点:
    - diagnostic carry review。

## 制約
- scope filtering の owner は `targets` とし、`vcs` に戻さない。
- zero-target fail は `diff` 前段 contract の一部であり、empty target を success として downstream へ渡さない。
- strict / warn の最終 exit policy は `report` owner だが、その素材となる exclusion diagnostics / counters はこの issue で揃える。
- diff seed 候補への ignore 適用 owner は `targets.diff-target-normalize` とし、`vcs` は ignore 判定を行わない。
- zero-target hard failure の `failure_reason` は `diff_zero_target_after_scope_filter` に固定する。
- scope outside exclusion 自体は warning / counter として carry し、strict 昇格時に downstream が `strict_diff_scope_exclusion` を使えるようにする。

## 未確定事項
- なし:
  - observable behavior と downstream handoff は initiative canonical docs で確定済みである。
