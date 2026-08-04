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

> このテンプレートは design scaffold / evidence slot です。必要な境界、図、契約、未確定事項を書き始めるための starting shape であり、workflow / compliance authority ではありません。詳細な lifecycle policy や field semantics は skills / docs / accepted ADRs / reviewer gates を参照します。

## 作成方針
- この文書は Epic が固定する Issue 横断の設計境界と契約を記述する。
- 日本語ファーストで作成し、ファイルパス、コマンド、コード識別子、SpecDock 固定語は原文のまま扱ってよい。
- Scope ownership と authority flow は `docs/authoring/scope-layering.md` を参照し、この template には責務表を複製しない。
- 既存プロダクトでは、対象システムの現行アーキテクチャ、設計指針、用語、境界に合わせて設計する。方針が不明または新規開発の場合は、コード・既存資料・ユーザー確認に基づいて方針を明確化してから設計する。
- Issue-level の実装手順、検証の細かな実行手順、private implementation design を必須にしない。

## 全体像
- 対象境界:
  - ...
- 影響領域:
  - ...
- 既存関係:
  - ...
- 参照する親 diagram:
  - ...

## 課題横断境界（cross-Issue boundary）
- Epic が固定する判断:
  - ...
- Issue に委譲する local delta:
  - ...
- forbidden parent boundary changes:
  - ...
- cross-Issue invariant:
  - ...

## 設計スライス一覧（design slice catalog）
- DS-001:
  - 目的:
    - ...
  - closes:
    - E-RQ:
      - ...
    - E-AC:
      - ...
  - owning Issue candidate:
    - ...
  - contract impact:
    - ...
  - expected evidence:
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

## 概念モデル / 業務ルール（必要時）
- 主要用語 / 概念の参照:
  - ...
- 主要概念 / 責務単位:
  - ...
- 状態を持つ対象 / 値として扱う対象:
  - ...
- 重要な状態変化 / ルール / 仕様:
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
    - 主要概念 / ルール / 状態変化 / 不変条件が変わるとき

### 図表（UML / 任意: concept model / rule model）
- N/A: 理由

## 契約
### 契約ポートフォリオ（contract portfolio）
- API / CLI:
  - ...
- event / metadata:
  - ...
- docs / template:
  - ...
- system of record:
  - ...
- compatibility expectation:
  - ...

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
- データの authoritative source / system of record:
  - ...
- 一貫性モデル:
  - ...

## 証跡採用（artifact adoption）
- raw evidence:
  - `artifacts/`:
    - ...
- accepted ADR:
  - ...
- `report.md` Evidence Adoption Ledger:
  - ...
- canonical docs へ反映する範囲:
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
    - 概念モデルや業務ルールの代替にはしない
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
- rollback boundary:
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
- reviewer focus:
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
