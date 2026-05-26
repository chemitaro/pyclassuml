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

# <EPIC_ID> <EPIC_TITLE> — 設計（どう実現するか）

## 全体像
- 対象境界:
  - ...
- 影響領域:
  - ...
- 既存関係:
  - ...
- 参照する親 diagram:
  - ...

## コンポーネント / モジュール構成（Component / Module View）
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

### 図表（UML / 推奨: コンポーネント / モジュール）
```plantuml
@startuml
' component / module diagram（component / module 図）
@enduml
```

## パッケージ依存（Package Dependency）
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

### 図表（UML / 推奨: パッケージ依存 / 依存差分）
```plantuml
@startuml
' package dependency diagram（package 依存図）
@enduml
```

## ドメインモデル（Domain Model / DDD 必要時）
- ユビキタス言語の参照:
  - ...
- 集約ルート:
  - ...
- エンティティ / 値オブジェクト:
  - ...
- ドメインイベント / ポリシー / 仕様:
  - ...
- 不変条件:
  - ...
- diagram メタデータ:
  - タイトル:
    - ...
  - 答える問い:
    - ...
  - 範囲:
    - ...
  - 含めない詳細:
    - persistence schema / full implementation classes
  - 更新条件:
    - aggregate / entity / value object / event / invariant が変わるとき

### 図表（UML / 任意: domain model / aggregate）
- N/A: 理由

## 契約
### インターフェース契約（API / 必要時）
- API-001:
  - リクエスト:
  - レスポンス:
  - エラー:

### イベント契約（Event / 必要時）
- EVT-001:
  - 生成元:
  - 利用先:
  - ペイロード:

### データ境界
- 正本:
  - ...
- 一貫性モデル:
  - ...

## データモデル
- model / table 変更:
  - ...
- 不変条件:
  - ...
- diagram メタデータ:
  - タイトル:
    - ...
  - 答える問い:
    - ...
  - 範囲:
    - ...
  - 含めない詳細:
    - domain model の代替にはしない
  - 更新条件:
    - persistence model / migration impact が変わるとき

### 図表（UML / 任意: data model）
- N/A: 理由

## 主要フロー
- Flow-A:
  1. ...
  2. ...
  3. ...
- Flow-B:
  - ...
- diagram メタデータ:
  - タイトル:
    - ...
  - 答える問い:
    - ...
  - 範囲:
    - ...
  - 含めない詳細:
    - exhaustive internal call graph
  - 更新条件:
    - participant / message / transaction boundary が変わるとき

### 図表（UML / 推奨: main sequence）
```plantuml
@startuml
' main sequence diagram（主要 sequence 図）
@enduml
```

## 状態 / アクティビティ（State / Activity / 必要時）
- State:
  - N/A: 理由
- Activity:
  - N/A: 理由
- diagram メタデータ:
  - タイトル:
    - ...
  - 答える問い:
    - ...
  - 範囲:
    - ...
  - 含めない詳細:
    - implementation order
  - 更新条件:
    - lifecycle / workflow branch / terminal state が変わるとき

### 図表（UML / 任意: state / activity）
- N/A: 理由

## 失敗設計
- 失敗モード:
  - ...
- リトライ:
  - ...
- 冪等性:
  - ...
- 部分失敗:
  - ...

## 移行戦略
- 移行戦略:
  - ...
- 必要時の dual write/read:
  - ...
- ロールバック:
  - ...

## 観測性 / セキュリティ
- 観測性:
  - ...
- ロール / 認可:
  - ...
- 監査 / PII:
  - ...

## テスト戦略
- 単体:
  - ...
- 統合:
  - ...
- E2E:
  - ...
- E-AC 対応:
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
