---
種別: 要件定義書（Issue）
ID: "iss-00010"
タイトル: "VCS Diff File Collect"
関連GitHub: ["#10"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
親: ["epic-00002", "init-00001"]
---

# iss-00010 VCS Diff File Collect — 要件定義（WHAT / WHY）

## 目的
- `diff` command の前段で、`--base <ref>`、`current_state`、`include_untracked` に基づく changed files を read-only に収集する。
- Git 読み取りを `vcs` seam に閉じ、scope filtering や target normalization を後続 `targets.diff-target-normalize` に残す。

## スコープ
- MUST:
  - `--base <ref>` を比較基点として changed files を収集する。
  - `current_state=working-tree | head` を切り替えられる。
  - `include_untracked=true | false` を切り替えられる。
  - invalid `--base <ref>` と Git diff read failure を failure とする。
  - `current_state=head` かつ `include_untracked=true` では untracked を diff seed に含めず warning を残す。
- MUST NOT:
  - scope filtering を行わない。
  - explicit target normalize を行わない。
  - changed class counting や summary policy を決めない。
- OUT OF SCOPE:
  - `TargetSet` の生成。
  - strict / warn の最終 exit code 決定。

## 受け入れ条件
- AC-001:
  - Actor:
    - `diff` 利用者
  - Given:
    - 有効な `--base <ref>` と `current_state` / `include_untracked` 指定がある。
  - When:
    - VCS diff collect を行う。
  - Then:
    - changed files が後続 seam に渡せる形で収集される。
  - 観測点:
    - `working-tree` / `head`、untracked on/off の matrix。
- AC-002:
  - Actor:
    - `diff` 利用者
  - Given:
    - invalid `--base <ref>` または Git diff read failure がある。
  - When:
    - VCS diff collect を行う。
  - Then:
    - `vcs_read_failure` を持つ failure として後続へ曖昧な changed files を渡さない。
  - 観測点:
    - failure scenario review。
- AC-003:
  - Actor:
    - `diff` 利用者
  - Given:
    - `current_state=head` かつ `include_untracked=true` が指定される。
  - When:
    - VCS diff collect を行う。
  - Then:
    - untracked は含めず、no-op warning を後続へ渡す。
  - 観測点:
    - head + untracked scenario。

## 例外・エッジケース
- EC-001:
  - 条件:
    - untracked file が存在しない状態で `include_untracked=true`。
  - 期待:
    - changed file collection は通常どおり生成され、余分な failure は出さない。
  - 観測点:
    - untracked off/on scenario。
- EC-002:
  - 条件:
    - changed file に scope 外 path が含まれる。
  - 期待:
    - `vcs` はそのまま収集し、scope filtering は `targets.diff-target-normalize` に委ねる。
  - 観測点:
    - seam boundary review。

## 制約
- Git repository は read-only に扱う。
- `project_root` は `config.context-resolve` が確定したものを使う。
- `vcs` seam は changed-file collection を返すだけで、`TargetSet` や summary counter の authoritative owner にならない。
- invalid `--base <ref>` と Git diff read failure の `failure_reason` は `vcs_read_failure` に固定する。

## 未確定事項
- なし:
  - observable behavior と failure ownership は initiative canonical docs で確定済みである。
