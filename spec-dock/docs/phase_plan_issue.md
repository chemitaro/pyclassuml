# phase playbook: plan (issue)

Issue plan の playbook です。
shared axiom は [phase_plan.md](phase_plan.md)、Issue の execution policy は [workflow_issue.md](workflow_issue.md) を参照します。
この文書は policy の再定義ではなく、Issue plan をどう書くかに集中します。

## scope contract

- plan の単位: milestone / step / block / iteration / quality gate
- plan の責務: issue requirement / design と `workflow_issue.md` の policy を、依存順に基づく実行順、review / QA / spec gate、docs impact、final diff review を持つ `plan.md` に変換する
- plan が固定するもの:
  - 満たす要件 ID
  - milestone
  - step 一覧
  - 要件 ↔ step 対応
  - review / QA / spec gate 方針
  - 依存関係から導いた step 順
  - nested execution structure
  - docs impact gate
  - final diff review quality gate
  - final exit contract

## authoring rules

- `workflow_issue.md` が所有する `1 step = 1 observable behavior` invariant を step 設計へ落とす
- `block` は optional concern group とし、単純な step では最小 wrapper 1 個でよい
- `iteration` は 1 回の TDD cycle とし、内部に `Red / Green / Refactor` を置く
- failing test は iteration ごとに 1 本ずつ進める
- review / QA / docs / final diff は TDD cycle の外に置き、step gate / milestone gate / `S90` / `S99` に配置する
- `Refactor` は bounded decision point として残し、事前に詳細な cleanup task を書き込まない
- cleanup が最初から明確で大きい場合は、`Green` / design / 別 step で扱う
- step 順は `design.md` の `依存関係分析`、`Module Dependency Diagram`、`ディレクトリ / ファイル変更計画` から導き、upstream / prerequisite / lower-dependency から先に置く
- 各 step には `depends on`、`unblocks`、`design refs`、`target files` を置き、依存関係と変更対象を追えるようにする
- `design.md` の `ディレクトリ / ファイル変更計画` を canonical path inventory とし、plan の `target files` は各 step が触る subset として書く
- templates は最小 scaffold であり、Issue 固有の実行順・依存・検証に不要な placeholder は削除してよい
- stage gate は `pass` まで回す
- stage gate の `pass` 後は `report.md` を更新する。commit/no-op は `workflow_issue.md` の実行 contract が所有し、plan には Issue 固有の判断が必要な場合だけ書く
- cadence や approval policy の正本は `workflow_issue.md` に残し、この文書では plan 本文への埋め込み方だけを扱う

## entry focus

- AC / EC / constraints が requirement で固定されている
- 変更点、境界、verification strategy、依存関係分析、module dependency diagram、directory / file change plan が design にある
- 実行前に review / QA / docs impact の位置が決まっている

## authoring checklist

- `この計画で満たす要件ID` を先に固定する
- `マイルストーン一覧` を置く
- `依存関係から導く実装順序` を上流で置く
- 各 step の `depends on` / `unblocks` / `target files` を置く
- `ステップ一覧` と `要件 ↔ ステップ対応` を置く
- `レビュー / QA ゲート方針` を置く
- `実装ステップ` を step / block / iteration で書く
- `Refactor` には `目的` と `guardrail` を置き、具体的な refactor 内容は `report.md` へ送る
- 各 step gate に `report update` を置く。commit/no-op は `workflow_issue.md` を参照し、Issue 固有の判断が必要な場合だけ明記する
- `S90 docs impact resolution / docs refresh` を必要時に入れる
- `S99 final diff review quality gate` を必須で置く
- `final exit contract` を置く

## diagram / trace guidance

- 必要な場合だけ step dependency graph、test matrix、rollback map を置く
- 図表は `実装順序の根拠`、`要件 ↔ ステップ対応`、review / QA gate の理解を助ける用途に限定する
- 新しい設計判断や未承認 requirement を図表で追加しない
- step dependency graph を置く場合は、design の `Module Dependency Diagram` と矛盾しないようにする

## review gate

- step 粒度で review / test / report 判断を回せる
- step 順が design の依存関係分析、Module Dependency Diagram、directory / file change plan と矛盾しない
- 各 step の `depends on` / `unblocks` / `target files` が、実装順と変更対象の確認に使える
- report update が stage gate に置かれている。report-before-commit/no-op の実行順は `workflow_issue.md` の実行 contract で確認する
- AC / EC と step の対応が取れている
- docs impact と final diff review が計画に埋め込まれている
- reviewer が「この plan で実装してよい」と判断できる
