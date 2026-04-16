---
種別: 設計書（Epic）
ID: "<EPIC_ID>"
タイトル: "<EPIC_TITLE>"
関連GitHub: ["<GITHUB_ISSUE_NUMBER_OR_URL>"]
状態: "draft | approved"
作成者: "<YOUR_NAME>"
最終更新: "YYYY-MM-DD"
依存: ["requirement.md"]
親: ["<INIT_ID>"]
---

# <EPIC_ID> <EPIC_TITLE> — 設計（HOW）

## 全体像
- target boundary:
  - ...
- impacted area:
  - ...
- existing relation:
  - ...

### UML（推奨: module / context）
```plantuml
@startuml
' module / context diagram
@enduml
```

## 契約
### API（必要時）
- API-001:
  - Request:
  - Response:
  - Errors:

### Event（必要時）
- EVT-001:
  - Producer:
  - Consumer:
  - Payload:

### Data boundary
- SoR:
  - ...
- consistency model:
  - ...

## データモデル
- model / table changes:
  - ...
- invariants:
  - ...

### UML（任意: data model）
```plantuml
@startuml
' data / entity diagram
@enduml
```

## 主要フロー
- Flow-A:
  1. ...
  2. ...
  3. ...
- Flow-B:
  - ...

### UML（任意: sequence / flow）
```plantuml
@startuml
' sequence / flow diagram
@enduml
```

## 失敗設計
- failure mode:
  - ...
- retry:
  - ...
- idempotency:
  - ...
- partial failure:
  - ...

## 移行戦略
- migration strategy:
  - ...
- dual write/read if needed:
  - ...
- rollback:
  - ...

## 観測性 / セキュリティ
- observability:
  - ...
- role / auth:
  - ...
- audit / pii:
  - ...

## テスト戦略
- Unit:
  - ...
- Integration:
  - ...
- E2E:
  - ...
- E-AC mapping:
  - E-AC-001 -> ...

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
