---
種別: 要件定義書（Issue）
ID: "iss-00036"
タイトル: "Diff Default Branch Base"
関連GitHub: ["#36"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-21"
親: ["epic-00002", "init-00001"]
---

# iss-00036 Diff Default Branch Base — 要件定義（WHAT / WHY）

## 目的
- `pyclassuml diff` を `--base` なしで実行できるようにし、現在ブランチの開始点から現在状態までの差分クラス図を生成できるようにする。
- 明示的な `--base <ref>` は既存互換のまま維持し、commit hash / branch / tag を指定した比較は従来どおり動作させる。
- base branch や upstream 設定を利用者に強制せず、解決できない場合も initial commit fallback で前に進める。

## 背景・現状
- 現状の挙動:
  - `pyclassuml diff --base <ref>` は必須引数であり、`--base` を省略すると CLI usage error になる。
  - `diff` は Git 差分から対象ファイルを集め、`--current-state working-tree|head` に応じて現在側を比較する。
- 現状の課題:
  - 利用者が最も見たいことが多い「このブランチで積み上げた変更全体」を見るために、毎回 base ref を考える必要がある。
  - upstream がない、または upstream が `origin/<feature-branch>` を指す場合、upstream を必須にすると利用者の意図とずれる。
  - base branch を設定ファイルに必ず書かせる設計は、外部 CLI ツールとして過度に利用者へ運用負担を要求する。
- 情報源:
  - `README.md` の既存 `diff --base <ref>` / `--current-state` 仕様。
  - `epic-00002` の `vcs.diff-file-collect` / `targets.diff-target-normalize` 契約。
  - 2026-05-21 の設計相談: `--base` を任意化し、未指定時は best effort で branch-start base を解決する方針。

## 対象ユーザー / 利用シナリオ
- 主な利用者:
  - Python プロジェクトの feature branch 上で、現在ブランチの変更範囲を UML クラス図で確認したい開発者。
  - PR 作成前やレビュー前に、作業ブランチ全体の設計差分を俯瞰したい開発者。
- 代表シナリオ:
  - `pyclassuml diff` だけで、現在ブランチの開始点から working tree までの差分図を生成する。
  - `pyclassuml diff --current-state head` で、現在ブランチの開始点から `HEAD` までの committed diff 図を生成する。
  - `pyclassuml diff --base origin/main` や `pyclassuml diff --base <commit>` は従来どおり明示 base との比較として使う。

## スコープ
- 必須:
  - `diff` の `--base` を任意化する。
  - `--base <ref>` 指定時の既存挙動と意味論を維持する。
  - `--base` 未指定時に、現在ブランチの開始点に近い base commit を best effort で解決する。
  - base 解決結果と解決理由を diagnostics / report で観測できるようにする。
  - base 解決ができない場合も、initial commit を fallback base として差分収集を続行する。
- 禁止:
  - `--base <ref>` の意味を暗黙に merge-base / three-dot 比較へ変更しない。
  - upstream 設定、config 設定、特定の branch 命名を必須条件にしない。
  - 対象プロジェクトのファイルや Git history を書き換えない。
- 対象外:
  - `pyclassuml diff --branch-base`、`--merge-base`、`--guess-upstream` などの別 UI 追加。
  - GitHub PR API から base branch を取得する機能。
  - fork-point / reflog 依存の精密な分岐元推定。

## 境界
- 常に行う:
  - 明示 `--base` がある場合は、その ref を authoritative base として扱う。
  - `--base` 未指定時は、best effort の branch-start base 解決を行う。
  - 解決結果の commit hash と resolution kind を user-visible diagnostics / report に残す。
- 判断が必要:
  - default branch 候補が複数ある場合の優先順位。
  - initial commit fallback 時の warning severity。
- 行わない:
  - upstream がないことを理由に処理を失敗させない。
  - 設定ファイルに default base を必須として要求しない。
  - `main` / `develop` などの候補が見つからないことだけで usage error にしない。

## 非交渉制約
- 外部 CLI として対象プロジェクトへ依存を追加しない。
- 対象ソースコードを書き換えない。
- 対象コードを import 実行しない。
- Git 操作は読み取り専用に限定する。
- 同一 repository state / same inputs では、base 解決順序と diagnostics 順序を決定的にする。

## 前提
- Git は branch 作成元を永続的な first-class metadata として保持しないため、「現在ブランチの最初」は厳密値ではなく best effort の推定になる。
- initial commit fallback は、正確な branch-start が分からない場合でも `pyclassuml diff` を有用に動かすための degraded but usable behavior とする。

## 受け入れ条件
- AC-001:
  - アクター: 開発者
  - 前提: feature branch が default branch から分岐しており、`--base` は指定されていない。
  - 操作: `pyclassuml diff` を実行する。
  - 期待結果: default branch 候補との merge-base が resolved base になり、その base から現在状態までの diff UML が生成される。
  - 観測点: stdout / stderr / report diagnostics に resolved base と resolution kind が残る。
- AC-002:
  - アクター: 開発者
  - 前提: `--base origin/main` または `--base <commit>` が指定されている。
  - 操作: `pyclassuml diff --base <ref>` を実行する。
  - 期待結果: 既存どおり `<ref>` 自体を base として差分収集し、未指定時の branch-start 解決は実行されない。
  - 観測点: 既存の invalid base / current-state / untracked 挙動が後方互換である。
- AC-003:
  - アクター: 開発者
  - 前提: upstream、default branch 候補、config default が利用できない repository state がある。
  - 操作: `pyclassuml diff` を実行する。
  - 期待結果: initial commit を fallback base として差分収集を続行し、fallback warning を出す。
  - 観測点: usage error ではなく、diagnostic 付きの通常 pipeline 結果になる。
- AC-004:
  - アクター: 開発者
  - 前提: `--current-state head` が指定されている。
  - 操作: `pyclassuml diff --current-state head` を実行する。
  - 期待結果: resolved base から `HEAD` までの tracked diff を収集し、working tree only / untracked は既存仕様どおり含めない。
  - 観測点: `head_untracked_noop` 等の既存 diagnostics と矛盾しない。

## 例外・エッジケース
- EC-001:
  - 条件: repository に commit がない。
  - 期待: diff base を解決できないため、既存の Git diff read failure 系 diagnostics として fail-fast する。
  - 観測点: Python parse / analyze pipeline を呼ばない。
- EC-002:
  - 条件: default branch 候補が存在するが merge-base が取れない。
  - 期待: 次候補へ進み、全候補が失敗したら initial commit fallback を使う。
  - 観測点: failed candidate は必要に応じて debug / warning diagnostics に残せる。
- EC-003:
  - 条件: `--base` 未指定かつ current branch が default branch 自身である。
  - 期待: initial commit または default branch 自身の開始点相当を fallback として扱い、リポジトリ全体の履歴差分として動作する。
  - 観測点: upstream 未設定でも usage error にしない。

## 入力→出力例
- EX-001:
  - 入力: `pyclassuml diff`
  - 出力: `base_resolution=default_branch_merge_base`, `resolved_base=<sha>` を伴う diff UML。
- EX-002:
  - 入力: `pyclassuml diff --base origin/main`
  - 出力: `origin/main` を explicit base とする従来互換 diff UML。
- EX-003:
  - 入力: `pyclassuml diff --current-state head`
  - 出力: resolved base から `HEAD` までの committed diff UML。

## 用語
- TERM-001: explicit base
  - `--base <ref>` で利用者が明示した Git revision。
- TERM-002: resolved base
  - `diff` が実際に Git 差分の起点として使う commit / ref。
- TERM-003: branch-start base
  - `--base` 未指定時に、現在ブランチの開始点に近いものとして best effort で解決した base。
- TERM-004: default branch candidate
  - `origin/HEAD`、`origin/main`、`origin/develop`、`main`、`develop`、`master` など、決定的順序で探索する既知の基準ブランチ候補。

## 未確定事項
- Q-001:
  - 質問: default branch candidate の正確な優先順位をどうするか。
  - 推奨案: `origin/HEAD` を最優先にし、次に `origin/main`, `origin/develop`, `main`, `develop`, `master` を固定順序で試す。
  - 影響範囲: base 解決の決定性、CI / local の再現性、warning 文面。
