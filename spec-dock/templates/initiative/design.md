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

# <INIT_ID> <INIT_TITLE> — 設計（HOW / Guardrails）

## アーキテクチャ上の狙い
- ...

## 現状と目指す姿
- As-Is:
  - ...
- To-Be:
  - ...

## System Context
- Title:
  - System context / target-state overview
- Question answered:
  - ...
- Scope:
  - ...
- Excluded details:
  - ...
- Update trigger:
  - ...

### UML（推奨: system context / target-state overview）
```plantuml
@startuml
!include C4_Context.puml

LAYOUT_WITH_LEGEND()

title System context / target-state overview

Person(user, "User", "Primary actor")
System(system, "Target system", "System under this initiative")
System_Ext(external, "External system", "External dependency")

Rel(user, system, "Uses")
Rel(system, external, "Depends on")
@enduml
```

## ドメイン境界 / ユビキタス言語（必要時）
- bounded context / domain area:
  - ...
- core / supporting / generic domain:
  - ...
- key domain terms:
  - ...
- cross-epic actor-goal overview:
  - N/A: reason

## Container Overview（必要時）
- Title:
  - ...
- Question answered:
  - ...
- Scope:
  - ...
- Excluded details:
  - ...
- Update trigger:
  - ...
- UML:
  - N/A: reason

## 対象境界 / 依存
- in scope:
  - ...
- external dependency:
  - ...
- boundary policy:
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

## ロールアウト原則
- rollout strategy:
  - ...
- rollback principle:
  - ...
- feature flag principle:
  - ...

## 観測性 / NFR 原則
- observability:
  - ...
- performance / reliability:
  - ...
- audit / compliance:
  - ...

## 主要リスク
- R-001:
  - ...
- R-002:
  - ...

## 関連 ADR
- adr-...:
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
