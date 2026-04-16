# phase playbook: design

Initiative / Epic / Issue に共通する design の shared playbook です。
scope 固有の entry / quality gate は `workflow_*.md` が additive に定義します。議論資料の置き方は対象 scope 配下の `discussions/rules.md`、命名は [reference_naming.md](reference_naming.md) を参照してください。

関連:
- 全体像: [guide.md](guide.md)
- Scope workflow: [workflow_initiative.md](workflow_initiative.md), [workflow_epic.md](workflow_epic.md), [workflow_issue.md](workflow_issue.md)
- 議論資料の置き方と命名: 対象 scope 配下の `discussions/rules.md`, [reference_naming.md](reference_naming.md)

## phase contract

- 位置: 全体 workflow の `調査分析 → requirement → design → plan → 実装/品質ゲート` の `design`
- 責務: requirement で固定した `WHAT / WHY` を、実装可能な HOW / guardrails に落とす
- 前提入力: reviewer 承認レベルの `requirement.md`、既存実装 / docs / ADR、設計で閉じる論点
- 固定すること: 方針、境界 / 契約、SoR / 依存、依存関係分析、移行、観測性、テスト戦略
- 出力: reviewer が plan へ送れる `design.md` と必要な `research` / `disc` / `adr`
- 非ゴール: requirement の不足のごまかし、比較表の本文への押し込み、実装手順の plan 化
- 正本参照: この playbook の `review / handoff gate` が shared minimum gate。scope 固有 gate は `workflow_*.md` が additive に定義する

## 標準順

1. requirement と対象 scope の workflow を確認する
2. 既存実装 / 既存 docs / 既存 ADR を調べる
3. 比較や下調べは `research` / `disc` に分離する
4. 必要ならヒアリングし、反映前に docs に整理する
5. `design.md` を固めて reviewer loop を回す
6. 関連 docs を束ねて plan へ handoff する

## entry checklist

- `requirement.md` が reviewer 承認レベルにある
- design で閉じる論点と、先にヒアリング / 追加調査が要る論点を分けた
- 既存実装、既存 docs、既存 ADR を見て、採用候補の既存パターンを把握した
- ヒアリング前に docs へ残す前提を整理した
  - 決めたい設計論点
  - 確定事実と既存パターン
  - 未確定事項 / 仮説
  - 選択肢と推奨案
  - 反映先の本文節または ADR
- template:
  - Initiative: `spec-dock/templates/initiative/design.md`
  - Epic: `spec-dock/templates/epic/design.md`
  - Issue: `spec-dock/templates/issue/design.md`

## design checklist

- 既存パターンに乗れるかを最初に確認し、新しい概念は「既存で足りない理由」を残す
- 先に押さえる:
  - 既存の責務分割
  - 現在の入出力契約
  - データ境界と SoR
  - upstream / downstream / prerequisite の依存関係
  - 依存の少ない実装起点
  - 既存テストの守備範囲
  - 移行 / 運用 / 監視で壊しうる点
- 本文には採用結論と guardrails を残し、長い比較や生の調査ログは `discussions/` へ逃がす
- UML は用途付き placeholder だけを残す
- initiative では高レベル図を 1 箇所まで、epic / issue では module / context や class / interface の置き場を明示する
- issue design では module / dependency UML を省略せず、依存方向と実装起点が読めるようにする
- 先に埋める節:
  - Initiative: `アーキテクチャ上の狙い`, `現状と目指す姿`, `対象境界 / 依存`, `ガードレール`, `ロールアウト原則`, `観測性 / NFR 原則`, `主要リスク`
  - Epic: `全体像`, `契約`, `データモデル`, `主要フロー`, `失敗設計`, `移行戦略`, `観測性 / セキュリティ`, `テスト戦略`
  - Issue: `既存実装 / 規約の理解`, `依存関係分析`, `インターフェース契約`, `採用方針 / トレードオフ`, `変更計画`, `要件 → 設計マッピング`, `テスト戦略`, `要件 / 例外 -> verification mapping`

## 論点の逃がし先

- `research`: 既存実装調査、類似機能比較、外部仕様調査
- `disc`: 設計案比較、トレードオフ整理、採否判断の前段
- `note`: 図の叩き台、軽量メモ
- `adr`: 境界 / 契約 / 移行などの長期判断
- 次なら先に docs 化する:
  - 2 案以上の比較がある
  - migration / observability / security の方針比較が長い
  - reviewer やユーザーと論点を切り分けて議論したい
- 次ならヒアリングを挟む:
  - UX / 運用フロー / 監査要件など、code だけでは決められない前提がある
  - ロールアウト条件や業務手順が境界に影響する
  - requirement で残した TBD が利用者都合でしか閉じられない
- 次なら ADR を検討する:
  - 境界、契約、整合性、移行戦略の採択が後続へ長く効く
  - 代替案を比較したうえで 1 案を明示的に選ぶ
  - 将来の変更者が「なぜこうしたか」を参照する必要がある

## review / handoff gate

この節は shared minimum gate です。通過後も scope 固有 gate は対応する `workflow_*.md` に追加で従います。

- requirement の主要論点に対応する設計の置き場がある
- 境界、契約、依存関係分析、観測性、テスト戦略のうち必要なものが抜けていない
- 既存パターンを採る / 採らない理由が説明できる
- plan に渡せる変更単位の見取り図と依存順がある
- `design.md` と必要な `research` / `disc` / `adr` を束で渡せる
- reviewer が「plan へ進めてよい」と判断できる

## short rules

- subagent は `researcher / consultant = 比較と事例収集`, `doc writer = 本文と図の整合`, `reviewer = layering / guardrails / テスト戦略の検出` で使い分ける
- subagent には `対象範囲 / 比較したい論点 / 採用判断に必要な観点` を渡す
- 迷ったら `requirement 不足の切り分け → 既存パターン確認 → disc → adr → review gate 再確認` の順で判断する
