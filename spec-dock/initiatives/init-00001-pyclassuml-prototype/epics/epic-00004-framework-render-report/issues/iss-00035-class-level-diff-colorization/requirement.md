---
種別: 要件定義書（Issue）
ID: "iss-00035"
タイトル: "Class Level Diff Colorization"
関連GitHub: ["#35"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-15"
親: ["epic-00004", "init-00001"]
---

# iss-00035 Class Level Diff Colorization — 要件定義（WHAT / WHY）

## 目的
- `pyclassuml diff` の PlantUML class box 色分けを、file status ではなく class 単位の差分状態で表現する。
- base revision に存在しない class は水色、base revision から存在していて class 定義範囲に変更がある class は既存の緑、diff に直接含まれない依存 class は通常表示のままにする。

## 背景・現状
- 現状の挙動:
  - `iss-00033` で `pyclassuml diff` は changed / newly added class を `DiffChanged` として薄い緑に色分けするようになった。
  - ただし added 判定は主に file status に依存し、既存ファイル内に新規 class を追加した場合は modified file 内の changed class として扱われる。
  - dependency-only class は diff-specific stereotype を持たず、PlantUML の通常 class box 表示になる。
- 現状の課題:
  - 利用者は Git diff 図から「新規に追加された class」と「既存 class の修正」を別々に読み取りたい。
  - file 単位の added / modified 判定では、既存ファイルに追加された class を新規追加として扱えない。
- 情報源:
  - ユーザー要望: 既存ファイル内の新規 class も class 単位で水色にしたい。
  - 既存実装: `src/pyclassuml/app/diff.py` の `_diff_class_decorations`。
  - 既存実装: `src/pyclassuml/vcs/diff_collect.py` の `ChangedFileEntry` / `ChangedLineRange`。

## スコープ
- 必須:
  - `diff` command の表示対象 class について、base/current の AST class inventory を比較して class 単位の `added` / `modified` / unchanged を判定する。
  - base に存在しない current class は `DiffAdded` stereotype を付け、水色系の PlantUML style を出力する。
  - base に存在し、current changed hunk が current 側 `ClassSpan` と重なる class は `DiffChanged` stereotype を付け、既存の緑 style を維持する。
  - base に存在し、changed hunk と重ならない dependency-only class は diff-specific decoration なしにする。
  - 新規ファイルおよび included untracked file 内の selected class は `DiffAdded` とみなす。
  - `generate` command の通常図には diff-specific colorization を適用しない。
- 禁止:
  - 解析対象プロジェクトの Python code を import 実行しない。
  - 解析対象ソースを書き換えない。
  - base revision の file を workspace に永続書き出ししない。
  - class rename / move を類似度推定で既存 class とみなさない。
- 対象外:
  - deleted class の図示。
  - relation edge や member 単位の色分け。
  - user configurable colors。
  - summary counter を added / modified 別に増やすこと。

## 非交渉制約
- 外部 CLI として読み取り専用・非侵襲で動作する。
- 同一入力、同一 `--base`、同一 current state では deterministic な `.puml` を出力する。
- class-level classification は rendering のための decoration とし、既存の dependency traversal / relation selection / changed_class_count の意味を変えない。

## 受け入れ条件
- AC-001: 既存ファイル内に新規 class を追加した場合の水色表示
  - アクター: `pyclassuml diff` 利用者
  - 前提: base revision に `Existing` class だけがあり、current で同じ file に `NewlyAdded` class が追加される
  - 操作: `pyclassuml diff --base <base>` を実行する
  - 期待結果: `NewlyAdded` class declaration は `<<DiffAdded>>` を持ち、`Existing` は変更がなければ `DiffChanged` / `DiffAdded` を持たない
  - 観測点: `.puml` class declaration と `skinparam class` block
- AC-002: 既存 class 修正の緑表示
  - アクター: `pyclassuml diff` 利用者
  - 前提: base/current に同じ class identity があり、current changed hunk がその class span と重なる
  - 操作: `pyclassuml diff --base <base>` を実行する
  - 期待結果: 対象 class declaration は `<<DiffChanged>>` を持ち、既存の緑 style が出力される
  - 観測点: `.puml` class declaration と `skinparam class`
- AC-003: 新規ファイル / untracked file 内 class の水色表示
  - アクター: `pyclassuml diff` 利用者
  - 前提: base revision に存在しない Python file が diff seed へ含まれる
  - 操作: `pyclassuml diff --base <base> --include-untracked` または tracked added file を含む diff を実行する
  - 期待結果: その file 内の selected class は `<<DiffAdded>>` を持つ
  - 観測点: `.puml` class declaration
- AC-004: dependency-only class の通常表示
  - アクター: `pyclassuml diff` 利用者
  - 前提: changed class から依存関係で到達する class が base/current ともに存在し、変更 hunk と重ならない
  - 操作: `pyclassuml diff --base <base>` を実行する
  - 期待結果: dependency-only class に `DiffAdded` / `DiffChanged` / `DiffDependency` が出ない
  - 観測点: `.puml` class declaration

## 例外・エッジケース
- EC-001: rename-only file
  - 条件: Git が file rename を検出し、class 本体に current changed hunk がない
  - 期待: file rename metadata で base path を current path に正規化して class identity を比較し、class 自体は decoration なしにする
  - 観測点: `.puml` class declaration
- EC-002: class rename / move
  - 条件: class 名または module path が file rename metadata だけでは対応できない形で変わる
  - 期待: 旧 class の削除 + 新 class の追加として扱い、current 側 class は `DiffAdded` になる
  - 観測点: `.puml` class declaration
- EC-003: nested class
  - 条件: 既存 outer class に新しい nested class を追加する
  - 期待: nested class は `DiffAdded` として表示される。outer class の扱いは current changed hunk が outer の直接 span と重なる既存仕様に従う
  - 観測点: `.puml` class declaration
- EC-004: syntax error / base blob 読み取り失敗
  - 条件: base または current の class inventory を安全に作れない
  - 期待: 正当な added / untracked / file rename missing-old-path 以外の Git read error、invalid base、UTF-8 decode failure、base parse failure、current parse failure では `DiffAdded` / `DiffChanged` を捏造しない。既存 diagnostics / failure policy に従う
  - 観測点: command result、stderr/stdout、`.puml`
- EC-005: 安全に `DiffAdded` とみなせる base 欠損
  - 条件: `ChangedFileEntry.change_kind == "added"`、included untracked file、または Git rename metadata に基づく previous path が存在しないことが確認できる
  - 期待: base class identity が存在しないため、current selected class を `DiffAdded` とみなせる
  - 観測点: `.puml` class declaration

## 用語（ドメイン語彙）
- class identity:
  - `module_path:qualified_name`。file rename 時は VCS rename metadata で base 側 module path を current path へ正規化して比較する。
- `DiffAdded`:
  - base/current class inventory 比較により current 側にだけ存在する selected class を示す PlantUML stereotype。
- `DiffChanged`:
  - base/current の両方に存在し、current changed hunk が current `ClassSpan` と重なる selected class を示す既存 stereotype。

## 未確定事項
- なし。class rename / move 推定、deleted class 表示、user configurable colors は明示的に対象外とする。
