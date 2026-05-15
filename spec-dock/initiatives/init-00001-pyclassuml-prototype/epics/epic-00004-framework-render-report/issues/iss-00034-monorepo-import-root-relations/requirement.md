---
種別: 要件定義書（Issue）
ID: "iss-00034"
タイトル: "monorepo import root mismatch drops typed relations"
関連GitHub: ["#34"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-15"
親: ["epic-00004", "init-00001"]
---

# iss-00034 monorepo import root mismatch drops typed relations — 要件定義（WHAT / WHY）

## 目的
- monorepo で Git root と Python import root が一致しない場合でも、`diff` が import / annotation / field 由来の relation を落とさず class diagram を生成できるようにする。
- `project_root` が Git diff と import resolution の両方を暗黙に意味している現状を解消し、context 上で VCS root と import root の責務を分離する。

## 背景・現状
- ユーザー報告では、repo root 直下に `taikyohiyou_management_api/` がある monorepo に対し、`--project-root repo-root --package-root repo-root/taikyohiyou_management_api --scope-root repo-root/taikyohiyou_management_api` で `pyclassuml diff` を実行した。
- 対象 backend は `from shared...` / `from authentication...` のように backend directory を Python import root として import している。
- 現状の import candidate 探索は `project_root / import_parts` を見るため、`repo-root/shared/...` を探索してしまい、実ファイル `repo-root/taikyohiyou_management_api/shared/...` を見つけられない。
- 観測値として `typed_relation_unresolved` が 1013 件発生し、relation は 42 件に留まった。`--project-root` を backend directory に変えると relation は 555 件まで増えた。

## スコープ
- 必須:
  - `ExecutionContext` に VCS root と import roots を表す情報を追加する。
  - import candidate 探索は `import_roots` を基準に行い、monorepo の backend import root を優先できるようにする。
  - diff collection は VCS root を基準に Git を読む。ただし downstream には従来どおり project-relative path を渡す。
  - `package_root != project_root` の context では、`package_root` を import root として優先し、`project_root` を後方互換 fallback として残す。
  - 既存 single-project layout と `project_root` 相対 path contract を壊さない。
- 禁止:
  - 解析対象コードを import 実行しない。
  - 解析対象ソースを書き換えない。
  - 複数 Python project を横断して自動統合する本命対応をこの issue で先回り実装しない。
- 対象外:
  - `pyproject.toml` の packaging metadata からの自動 import root 推定。
  - CLI option と config schema に `vcs_root` / `import_roots` を公開すること。
  - 複数 Python project を含む diff の artifact 分割。

## 非交渉制約
- 外部 CLI / read-only / AST static analysis の product contract を維持する。
- `generate` と `diff` の scope semantics を混同しない。
- 同一入力では同一出力になる決定性を維持する。
- 既存 API の `ExecutionContext(project_root, package_root, scope_root)` 呼び出しは後方互換にする。

## 受け入れ条件
- AC-001:
  - アクター: monorepo 上で `pyclassuml diff` を実行する利用者。
  - 前提: `project_root` は repo root、`package_root` / `scope_root` は repo 配下の Python backend root、backend 内では `from shared.models import User` のような import が使われている。
  - 操作: parse / traversal が seed file の import candidate を探索する。
  - 期待結果: `package_root/shared/models.py` が import candidate として発見され、reachable module として解析対象に入る。
  - 観測点: `ParseResult.module_index.import_candidate_paths` と parsed module path。
- AC-002:
  - アクター: nested project を Git worktree root とは別の project root として扱う利用者。
  - 前提: `vcs_root` は repo root、`project_root` は `repo/packages/app`。
  - 操作: `collect_diff_files` が tracked / untracked files を収集する。
  - 期待結果: downstream には `inside.py` のような project-relative path だけが渡り、repo root 側の `outside.py` は混入しない。
  - 観測点: `ChangedFileEntry.current_project_relative_path`。
- AC-003:
  - アクター: 既存 single-project 利用者。
  - 前提: `project_root == package_root`。
  - 操作: context resolution と import resolution を行う。
  - 期待結果: import root は従来と同じ `project_root` であり、既存テストが維持される。
  - 観測点: context equality / existing parse tests。

## 例外・エッジケース
- EC-001:
  - 条件: `package_root != project_root` だが import が従来どおり `project_root` から解決される layout。
  - 期待: `project_root` を fallback import root として残し、後方互換の解決可能性を維持する。
  - 観測点: `context.import_roots == (package_root, project_root)`。
- EC-002:
  - 条件: Git diff collection が VCS root から実行される。
  - 期待: line range collection と untracked collection の path は最終的に project-relative に正規化される。
  - 観測点: VCS tests。

## 用語
- `vcs_root`: Git diff を読む基準。monorepo root。
- `project_root`: pyclassuml の path 表示、ignore、module path の基準として残る project root。
- `package_root`: 解析対象 Python package / project の範囲。
- `import_roots`: Python import candidate 探索の基準。monorepo では `package_root` を優先する。

## 未確定事項
- なし。この issue では最小対応に限定し、自動検出と複数 project 対応は対象外に固定する。
