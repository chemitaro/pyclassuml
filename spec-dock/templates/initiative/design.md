---
種別: 設計書（Initiative）
ID: "<INIT_ID>"
タイトル: "<INIT_TITLE>"
関連GitHub: ["<GITHUB_ISSUE_NUMBER_OR_URL>"]
状態: "draft | approved"
作成者: "<YOUR_NAME>"
最終更新: "YYYY-MM-DD"
依存: ["requirement.md"]
---

# <INIT_ID> <INIT_TITLE> — 設計（どう実現し、何を守るか）

## 作成方針
- この文書は Initiative 全体の設計境界、意思決定権限、Epic への handoff 方針を固定する。
- 日本語を主文とし、ファイルパス、コマンド、コード識別子、SpecDock 固定語は原文のまま扱ってよい。
- 既存プロダクトでは、対象システムの現行アーキテクチャ、設計指針、用語、境界に合わせて設計する。方針が不明または新規開発の場合は、コード・既存資料・ユーザー確認に基づいて方針を明確化してから設計する。
- Issue-level の実装詳細、検証の細かな実行手順、内部 class / file 設計はここで必須化しない。

## アーキテクチャ上の狙い
- ...

## 現状と目指す姿
- 現状:
  - ...
- 目指す姿:
  - ...

## 対象範囲と責務境界（scope boundary）
- Initiative が所有する判断:
  - ...
- Epic に委譲する判断:
  - ...
- Issue に委譲する実装判断:
  - ...
- 対象外として固定するもの:
  - ...
- scope-layering reference:
  - `docs/authoring/scope-layering.md` を参照する。この template には責務表を複製しない。

## システムコンテキスト
- タイトル:
  - システムコンテキスト / 目指す状態の全体像
- 答える問い:
  - ...
- 範囲:
  - ...
- 含めない詳細:
  - ...
- 更新条件:
  - ...

### 図表（UML / 推奨: システムコンテキスト / 目指す状態の全体像）
```plantuml
@startuml
!include C4_Context.puml

LAYOUT_WITH_LEGEND()

title システムコンテキスト / 目指す状態の全体像

Person(user, "利用者", "主なアクター")
System(system, "対象システム", "この Initiative の対象システム")
System_Ext(external, "外部システム", "外部依存")

Rel(user, system, "利用する")
Rel(system, external, "依存する")
@enduml
```

## 業務領域 / 概念境界（必要時）
- 対象領域 / 責務境界:
  - ...
- 主要な関心領域:
  - ...
- 主要用語:
  - ...
- Epic 横断の actor-goal 概要:
  - N/A: 理由

## コンテナ概要（必要時）
- タイトル:
  - ...
- 答える問い:
  - ...
- 範囲:
  - ...
- 含めない詳細:
  - ...
- 更新条件:
  - ...
- UML:
  - N/A: 理由

## 対象境界 / 依存
- 対象範囲:
  - ...
- 外部依存:
  - ...
- 境界方針:
  - ...

## 意思決定権限（decision authority）
- Initiative で確定する設計判断:
  - ...
- ADR に昇格する判断:
  - ...
- Epic / Issue planning に渡す未確定判断:
  - ...
- ユーザー確認が必要な判断:
  - ...

## 証跡採用（artifact adoption）
- 採用する research / discussion / draft artifact:
  - ...
- 採用しない、または歴史的証跡として残す artifact:
  - ...
- `report.md` の Evidence Adoption Ledger に残す採否:
  - ...
- 正本 `requirement.md` / `design.md` / `plan.md` へ反映する範囲:
  - ...

## ガードレール
- 互換性:
  - ...
- セキュリティ:
  - ...
- データ境界:
  - ...
- 品質条件:
  - ...

## レビューゲート（reviewer gate）
- 必須 reviewer:
  - spec-reviewer:
    - ...
- 必要時の専門家:
  - system-architect:
    - ...
  - implementation-planner:
    - ...
- promotion 条件:
  - ...

## ロールアウト原則
- ロールアウト戦略:
  - ...
- ロールバック原則:
  - ...
- feature flag 原則:
  - ...

## 観測性 / NFR 原則
- 観測性:
  - ...
- 性能 / 信頼性:
  - ...
- 監査 / コンプライアンス:
  - ...

## 主要リスク
- R-001:
  - ...
- R-002:
  - ...

## 関連 ADR
- adr-...:
  - ...

## エピック分割境界（Epic boundary）
- Epic 候補:
  - ...
- Epic 間依存:
  - ...
- Epic ごとの handoff package:
  - requirement:
    - ...
  - draft design:
    - ...
  - draft implementation plan:
    - ...
- controlled re-slicing が必要になる条件:
  - ...

## 未確定事項
- Q-001:
  - 質問:
  - 選択肢:
    - A:
      - ...
    - B:
      - ...
  - 推奨案:
    - ...
  - 影響範囲:
    - ...
