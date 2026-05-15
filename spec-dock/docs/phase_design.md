# phase playbook: design

Initiative / Epic / Issue に共通する design の shared playbook です。
scope 固有の entry / quality gate は `workflow_*.md` が additive に定義します。議論資料の置き方は対象 scope 配下の `discussions/rules.md`、命名は [reference_naming.md](reference_naming.md) を参照してください。

関連:
- 全体像: [guide.md](guide.md)
- Spec authoring workflow: [workflow_spec_authoring.md](workflow_spec_authoring.md)
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

## scope ownership

- Initiative design:
  - 所有する判断:
    - system context、architecture policy、cross-cutting constraint、target-state、bounded context / ubiquitous language、Epic が守る guardrail
  - 所有しない判断:
    - Issue-level class / function / file design、局所 sequence、実装順序
- Epic design:
  - 所有する判断:
    - 複数 Issue が共有する boundary、responsibility、data flow、domain model / aggregate、failure / migration strategy、ADR 分離基準
  - 所有しない判断:
    - Issue 内だけで閉じる細かな実装手順や局所 refactor
- Issue design:
  - 所有する判断:
    - 局所構造、既存 pattern の採否、interface contract、dependency direction、domain model delta、test strategy、rollback / compatibility
  - 所有しない判断:
    - 親 design の再定義、Red / Green / Refactor の作業手順、commit / review の運用順序
- ADR rule:
  - 長寿命・横断的・不可逆寄りの判断は ADR / decision log に分離する
  - 局所的で可逆な判断は対象 scope の design に置く

## 標準順

1. requirement と対象 scope の workflow を確認する
2. 既存実装 / 既存 docs / 既存 ADR を調べる
3. 比較や下調べは `research` / `disc` に分離する
4. 必要ならヒアリングし、反映前に docs に整理する
5. `design.md` を固めて fresh `spec-reviewer` loop を `review_status: pass` まで回す
6. 関連 docs を束ねて plan へ handoff する

## entry checklist

- `requirement.md` が reviewer 承認レベルにある
- `requirement.md` が `workflow_spec_authoring.md` の requirement gate を pass している
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
- template flexibility:
  - templates は完成形や準拠規格ではなく、書き始めるための最小 scaffold として扱う
  - agent は、プロジェクトの目的、作業内容、人間の理解しやすさ、エージェントの実行可能性に合わせて、項目を追加・削除・統合・並べ替えてよい
  - 不要な placeholder や該当しない節は削ってよいが、要件、設計判断、検証可能性、人間の理解に必要な情報は削らない

## design checklist

- 既存パターンに乗れるかを最初に確認し、新しい概念は「既存で足りない理由」を残す
- 先に押さえる:
  - 既存の責務分割
  - 現在の入出力契約
  - データ境界と SoR
  - domain vocabulary / bounded context / invariant
  - module / class / function / file の依存方向
  - upstream / downstream / prerequisite の依存関係
  - 依存の少ない実装起点
  - 追加 / 変更 / 削除 / 移動する directory / file と目的
  - 既存テストの守備範囲
  - 移行 / 運用 / 監視で壊しうる点
- 本文には採用結論と guardrails を残し、長い比較や生の調査ログは `discussions/` へ逃がす
- UML / PlantUML は、人間が誤読しやすい構造・境界・責務・流れ・状態・依存を可視化する用途で使う
- 図は本文の代替ではなく、本文で固定した設計判断を視覚的に検証する補助資料にする
- 図を置かない場合も、期待される図が不要な理由を `N/A: reason` として残す
- 先に埋める節:
  - Initiative: `アーキテクチャ上の狙い`, `現状と目指す姿`, `System Context`, `ドメイン境界 / ユビキタス言語`, `対象境界 / 依存`, `ガードレール`, `ロールアウト原則`, `観測性 / NFR 原則`, `主要リスク`
  - Epic: `全体像`, `Component / Module View`, `Package Dependency`, `Domain Model（DDD 必要時）`, `契約`, `データモデル`, `主要フロー`, `State / Activity（必要時）`, `失敗設計`, `移行戦略`, `観測性 / セキュリティ`, `テスト戦略`
  - Issue: `Parent Diagram References`, `既存実装 / 規約の理解`, `依存関係分析`, `Module Dependency Diagram`, `ディレクトリ / ファイル変更計画`, `インターフェース契約`, `Sequence Delta（必要時）`, `Domain Model Delta（必要時）`, `採用方針 / トレードオフ`, `要件 → 設計マッピング`, `テスト戦略`, `要件 / 例外 -> verification mapping`

## PlantUML / UML usage policy

- Purpose:
  - design.md は、人間が構造・境界・責務・流れ・状態・依存を短時間で理解できる設計書にする
  - UML / PlantUML は、大量の文章を読む負荷を下げ、設計の全体像と変更点を視覚的・構造的に把握しやすくするために使う
  - 図で表現できる設計情報は積極的に可視化する。ただし、図は本文の代替ではなく、本文で固定した判断を読みやすく検証する補助資料にする
  - 目的は「図を増やすこと」ではなく、reviewer / 実装者 / 将来の保守者が誤読しやすい構造を正しく共有すること
- Markdown preview compatibility:
  - PlantUML / C4 / DDD 図は Markdown 内では `plantuml` fence を使う
  - C4 Context が必要な場合は `!include C4_Context.puml` を明示する
  - `c4plantuml` fence は VS Code Markdown preview 互換性のため使わない
  - remote include は原則避け、利用する場合は理由と render 環境を明記する
- Diagram metadata:
  - すべての図は `Title`, `Question answered`, `Scope`, `Excluded details`, `Update trigger` を持つ
  - 図の直後か直前に、その図で固定する設計判断を本文で説明する
  - 図だけにしか存在しない設計判断を残さない
  - 図を省略する場合は `N/A: reason` を書き、対応する `plantuml` block は削除する
  - 図を書く場合は `N/A: reason` を残さない
- Relationship rules:
  - arrow は意味ラベルを持つ
  - `dependency`, `data flow`, `runtime call`, `ownership`, `publishes`, `implements` を曖昧にしない
  - 外部 actor / external system / out of scope component は境界外として分かるようにする
- Diagram budget:
  - Initiative / Epic は 1-3 図を目安にする
  - Issue は 0-2 図を目安にし、親 design の図を再掲しない
  - 図が増えすぎる場合は、親 scope への昇格、`discussions/` への分離、または低価値図の削除を検討する
- Avoid:
  - exhaustive class / file / method diagram
  - 実装作業順序だけを表す plan 相当の図
  - requirement の価値説明だけを表す図
  - すぐ古くなる generated call graph

## optional diagram catalog

テンプレートから削った図表は「不要になった情報」ではなく、必要時に追加する候補です。
agent はこの一覧から、設計上の誤読を減らすものだけを選び、必要ならここにない図表も追加してよいです。
ただし、追加した図表は `PlantUML / UML usage policy`、`diagram selection rules`、`UML review gate` に従います。

- Use Case:
  - actor と goal の理解をそろえる
  - Initiative / Epic の requirement-design 境界で、利用者・外部 actor・主要 goal が曖昧なときに使う
  - 内部実装、class、処理順は描かない
- C4 System Context:
  - 対象 system と外部 actor / external system の境界を示す
  - Initiative design の標準候補
- C4 Container:
  - deployable / runnable な container 境界や主要通信を示す
  - Initiative / Epic で container 構成が変わるときだけ使う
- Component / Module View:
  - codebase 内の責務分割や component/module 境界を示す
  - Epic design の主戦場。Issue では差分だけを書く
- Package Dependency / Package Dependency Delta:
  - source / compile-time dependency direction を示す
  - Epic / Issue で依存方向、循環、layer boundary が重要なときに使う
- Module Dependency Diagram:
  - module / class / file / function のうち、実装順や責務境界に影響する依存だけを示す
  - Issue design の標準候補。全 call graph にはしない
- Sequence:
  - 時系列の interaction、transaction、retry、queue、external API 呼び出しを示す
  - Epic は main sequence、Issue は changed sequence delta に限定する
- Activity:
  - 分岐や並行を含む workflow / business process を示す
  - 単純な直列処理には使わない
- State:
  - lifecycle、状態遷移、terminal state、guard を示す
  - status model や retry / failure lifecycle が変わるときに使う
- Domain Model / Aggregate:
  - aggregate root、entity、value object、domain event、policy / specification、invariant を示す
  - DDD 採用時の Epic design で共有モデルを固定し、Issue では delta だけを書く
- Bounded Context Map:
  - context 境界、context 間の関係、ubiquitous language の意味差を示す
  - Initiative design で domain boundary を固定するときに使う
- Object:
  - invariant や relationship の具体例を示す
  - 抽象 domain model だけでは誤読が残る場合に補助的に使う
- Class / Interface:
  - 局所的な責務、public contract、collaboration を示す
  - exhaustive generated-code inventory にはしない
- ER / DB Schema:
  - persistence model、table relationship、migration impact を示す
  - domain model の代替にしない
- Deployment:
  - runtime 配置、network boundary、infra dependency を示す
  - infra-impacting Initiative / Epic で使う
- Step Dependency Graph / Test Matrix / Rollback Map:
  - plan の理解補助として、実装順、検証範囲、rollback path を示す
  - 新しい design decision や未承認 requirement は追加しない

## diagram selection rules

- Initiative:
  - 標準:
    - C4 System Context
  - DDD 採用時:
    - Bounded Context Map
    - Ubiquitous Language table
  - 必要時:
    - C4 Container
    - C4 Deployment
    - Activity / State for central lifecycle or business process
    - Use Case for actor-goal clarification
  - 避ける:
    - detailed class diagram
    - object diagram
    - issue-level sequence diagram
    - exhaustive component diagram
- Epic:
  - 主戦場:
    - Component / Module View
    - Package Dependency
    - Domain Model / Aggregate
    - Main Sequence
  - required when applicable:
    - State diagram if lifecycle exists
    - Activity diagram if workflow has complex branching
    - C4 Dynamic / sequence if multiple C4 elements collaborate in a non-trivial runtime flow
  - 必要時:
    - Object diagram for concrete invariant examples
    - Deployment diagram for infra-impacting epics
  - 避ける:
    - 親 System Context の再掲
    - 変更のない full Container architecture
    - exhaustive generated-code class diagram
- Issue:
  - default:
    - non-trivial code change、dependency direction 変更、sequencing risk がある場合は Module Dependency Diagram を置く
    - docs-only、typo、局所 test-only など依存関係が自明な場合は `N/A: reason` で省略できる
  - required when applicable:
    - Sequence Delta if crossing components, transactions, queues, external APIs, or retries
    - State Delta if changing lifecycle
    - Domain Model Delta if changing aggregate, entity, value object, domain event, policy, or specification
    - Package Dependency Delta if changing dependency direction
  - 避ける:
    - System Context
    - full Container diagram
    - full Domain Model
    - full Deployment diagram

## Issue dependency and file-change planning

- Issue design は、実装前レビューで人間が確認できる粒度で依存関係と変更対象を固定する
- `依存関係分析` は module / class / function / file dependency を必要な範囲で分けて書く
- `Module Dependency Diagram` は、実装順に影響する module / class / file / function の依存方向を可視化する
- class / function 依存は、責務境界や実装順に影響する場合だけ書き、全 call graph は描かない
- `ディレクトリ / ファイル変更計画` は Linux `tree` style の複数階層構成図で表す
- tree には変更後の配置を表し、各 path のコメントで `Add / Modify / Delete / Move/Rename / Read only`、目的、主要 dependency を短く示す
- tree の下に同じ path 一覧を重複して置かない
- path が未確定の場合は `TBD` で放置せず、調査 step または `未確定事項` に分離する
- 実装順そのものは plan の責務だが、plan が参照する依存関係と変更対象は design で固定する

## DDD diagram guidance

- Initiative:
  - bounded context、core / supporting / generic domain、ubiquitous language の境界を扱う
  - 同じ語が context によって異なる意味を持つ場合は、context map と用語表で分ける
  - aggregate / entity / value object の詳細は原則 Epic へ降ろす
- Epic:
  - aggregate root、entity、value object、domain event、policy / specification、invariant の共有モデルを固定する
  - domain event は過去形の名前にし、internal domain event と integration event を必要時に区別する
  - repository は domain behavior ではなく port / contract として扱う
- Issue:
  - 親 Epic の domain model を参照し、変える aggregate / entity / value object / event / policy の差分だけを書く
  - full domain model を再掲しない
  - invariant や ownership を誤解しやすい場合だけ object diagram で具体例を補う

## UML review gate

- Diagram necessity:
  - 図が named design question に答えている
  - 図の owner level が Initiative / Epic / Issue のどれか明確
  - 図数が budget 内にある
  - 親文書が所有する情報を重複していない
  - 期待される図を省略した場合は `N/A: reason` がある
  - Issue design の Module Dependency Diagram が実装順の根拠として使える
  - Issue design の directory / file change plan が Linux `tree` style で実装前確認に使える
- Diagram correctness:
  - `plantuml` block が `@startuml` / `@enduml` を持つ
  - 図種が目的に合っている
  - Title / Question answered / Scope / Excluded details / Update trigger がある
  - stereotype、色、線種、icon を使う場合は凡例がある
  - element は名前と責務を持つ
  - relationship arrow は意味ラベルを持つ
  - 本文の用語、責務、依存方向と矛盾していない
- UML-specific gate:
  - Use Case は actor-goal を表し、内部実装を表さない
  - Class / Domain Model は概念・責務・関係を表し、生成コード inventory にしない
  - Package Dependency / Package Dependency Delta は compile-time / source dependency を表し、runtime call と混ぜない
  - Sequence は meaningful participants と messages を持つ
  - Activity は decision-heavy / parallel workflow に限定する
  - State は event、guard、terminal state を必要時に含む
  - ER / DB schema は永続化設計であり、domain model の代替にしない

## diagram guidance

この節は後方互換の入口です。図表の選択は `diagram selection rules`、記法と review 条件は `PlantUML / UML usage policy` と `UML review gate`、DDD 図は `DDD diagram guidance` を正本にします。

- 図表には目的、配置、更新タイミング、review 観点を添える
- 図表だけにしか存在しない設計判断を残さない
- Issue の module dependency / file-change planning は `Issue dependency and file-change planning` を参照する

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

- fresh `spec-reviewer` が design を requirement と照合し、`review_status: pass` を返している
- requirement 不足が見つかった場合は design で補わず、requirement gate へ戻している
- `report.md` の `Spec Authoring Gate` に調査、ヒアリング、review、修正、promotion evidence が残っている

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
