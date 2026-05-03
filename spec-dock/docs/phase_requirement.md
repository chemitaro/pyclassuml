# phase playbook: requirement

Initiative / Epic / Issue に共通する requirement の shared playbook です。
scope 固有の entry / quality gate は `workflow_*.md` が additive に定義します。議論資料の置き方は対象 scope 配下の `discussions/rules.md`、命名は [reference_naming.md](reference_naming.md) を参照してください。

関連:
- 全体像: [guide.md](guide.md)
- Scope workflow: [workflow_initiative.md](workflow_initiative.md), [workflow_epic.md](workflow_epic.md), [workflow_issue.md](workflow_issue.md)
- 議論資料の置き方と命名: 対象 scope 配下の `discussions/rules.md`, [reference_naming.md](reference_naming.md)

## phase contract

- 位置: 全体 workflow の `調査分析 → requirement → design → plan → 実装/品質ゲート` の `requirement`
- 責務: 調査分析の結果を `WHAT / WHY / scope / success` に固定する
- 前提入力: 対象 scope、As-Is の一次情報、対象 `workflow_*.md`、既存 `discussions/` / ADR
- 固定すること: 目的、背景・現状、成功条件、スコープ / 非スコープ、主要 TBD の置き場
- 出力: reviewer が design へ送れる `requirement.md` と必要な `research` / `disc` / `adr`
- 非ゴール: HOW の先取り、source のない断定、未確定論点の隠蔽
- 正本参照: この playbook の `review / handoff gate` が shared minimum gate。scope 固有 gate は `workflow_*.md` が additive に定義する

## scope ownership

- Initiative requirement:
  - 所有する判断:
    - why now、outcome、success metric、全体 scope / non-goal、非交渉制約
  - 所有しない判断:
    - Epic / Issue の設計詳細、実装順序、API / DB / file-level contract
- Epic requirement:
  - 所有する判断:
    - Initiative outcome を実現する capability / change area、Epic-level requirement、Epic acceptance criteria
  - 所有しない判断:
    - Issue の実装手順、module / class 詳細、Initiative requirement の再記述
- Issue requirement:
  - 所有する判断:
    - 最小実行単位で満たす振る舞い、AC / EC、上位 Epic から具体化した差分
  - 所有しない判断:
    - file / module / class の変更方針、TDD 手順、上位文書の全文再記述
- trace rule:
  - 下位文書は上位文書を再記述せず、参照と具体化差分だけを書く
  - 下位で上位 requirement と矛盾する場合は、下位で上書きせず上位文書または ADR / decision log を更新する

## 標準順

1. 対象 scope の workflow と template を開く
2. As-Is / 観測点 / 制約を集める
3. requirement に上げる前の事実や比較を `research` / `disc` に残す
4. 必要ならヒアリングし、反映前に docs に整理する
5. `requirement.md` を固めて reviewer loop を回す
6. 関連 docs を束ねて design へ handoff する

## entry checklist

- 対象が Initiative / Epic / Issue のどれかを `workflow_*.md` で確認した
- 対応 template を開き、先に埋める節を把握した
- 既存 `discussions/` と ADR を見て、過去判断と衝突しないことを確認した
- ヒアリング前に docs へ残す前提を整理した
  - 決めたいこと / 聞きたいこと
  - 確定事実
  - 未確定事項 / 仮説
  - 選択肢と推奨案
  - 反映先の本文節
- template:
  - Initiative: `spec-dock/templates/initiative/requirement.md`
  - Epic: `spec-dock/templates/epic/requirement.md`
  - Issue: `spec-dock/templates/issue/requirement.md`

## requirement checklist

- As-Is は一次情報を根拠にし、事実 / 推測 / 未確定を混ぜない
- `WHAT / WHY / scope / success` を先に固め、HOW は入れすぎない
- `MUST / MUST NOT / OUT OF SCOPE` と `Always / Ask / Never` を早めに仮置きする
- requirement 本文には結論と制約を残し、長い比較や調査ログは `discussions/` へ逃がす
- generic DoR / DoD や `省略/例外メモ` は template に戻さない
- 先に埋める節:
  - Initiative: `目的`, `背景と Why now`, `成功指標`, `スコープ`, `境界`, `非交渉制約`, `未確定事項`
  - Epic: `目的`, `ユースケース`, `Epic requirements`, `Epic acceptance criteria`, `スコープ`, `境界`, `依存 / 影響範囲`, `未確定事項`
  - Issue: `目的`, `背景・現状`, `スコープ`, `境界`, `受け入れ条件`, `例外・エッジケース`, `未確定事項`

## diagram guidance

- requirement の図表は、要求の理解や trace を助ける場合だけ置く
- Initiative:
  - 推奨:
    - impact map / outcome map
    - traceability matrix
  - 原則不要:
    - detailed sequence / class diagram
- Epic:
  - 推奨:
    - capability map
    - Initiative item / Epic requirement / Issue candidate の traceability matrix
  - 原則不要:
    - function-level diagram
- Issue:
  - 推奨:
    - AC / EC / constraint / verification の test matrix
    - 条件分岐が多い場合の simple activity diagram
  - 原則不要:
    - detailed class / sequence diagram
- review:
  - 図表だけにしか存在しない要求がない
  - 図表が scope / acceptance criteria / trace と矛盾していない

## 論点の逃がし先

- `research`: 事実収集、現状分析、外部調査
- `disc`: 論点整理、選択肢比較、合意形成の叩き台
- `note`: 軽量メモ、一時整理
- `adr`: 後続へ残る方針決定
- 次なら先に docs 化する:
  - 2 案以上あり比較が要る
  - ヒアリング前に仮説整理が要る
  - requirement に直接書くには早い調査結果を保持したい
  - reviewer へ判断材料を渡したい
- 次ならヒアリングを挟む:
  - 一次情報が docs / code だけでは足りない
  - success が利用者体験や運用判断に依存する
  - 解釈差で scope が変わる
  - reviewer が利用者理解不足と判断しうる
- 次なら ADR を検討する:
  - スコープ境界や方針が後続全体へ影響する
  - 非交渉制約や運用ルールを固定しないと success が閉じない
  - 将来参照したい採択理由を残す必要がある

## review / handoff gate

この節は shared minimum gate です。通過後も scope 固有 gate は対応する `workflow_*.md` に追加で従います。

- 目的が 1〜3 行で説明できる
- As-Is の根拠と主要観測点がある
- `MUST / MUST NOT / OUT OF SCOPE` と `Always / Ask / Never` が曖昧でない
- 主要 TBD に `質問 / 選択肢 / 推奨案` がある
- design 論点と追加調査 / ヒアリング論点が仕分けできている
- `requirement.md` と必要な `research` / `disc` / `adr` を束で渡せる
- reviewer が「design へ進めてよい」と判断できる

## short rules

- subagent は `researcher / consultant = 調査比較`, `doc writer = 文面整合`, `reviewer = WHAT / WHY 逸脱検出` で使い分ける
- subagent には `対象 scope / 未確定論点 / 欲しい出力` を最小セットで渡す
- 迷ったら `追加調査 → ヒアリング → disc → adr → pause` の順で判断する
