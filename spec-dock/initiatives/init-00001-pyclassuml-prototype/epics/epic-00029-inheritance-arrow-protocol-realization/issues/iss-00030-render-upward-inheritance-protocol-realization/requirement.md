---
種別: 要件定義書（Issue）
ID: "iss-00030"
タイトル: "Render Upward Inheritance And Protocol Realization"
関連GitHub: ["#30"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-05"
親: ["epic-00029", "init-00001"]
---

# iss-00030 Render Upward Inheritance And Protocol Realization — 要件定義（WHAT / WHY）

## 目的
- PlantUML の継承矢印を常に上向きにし、Python `Protocol` を interface-like contract として点線上向き矢印で表現する。

## 背景・現状
- 現状:
  - `ClassReference(reference_kind="class_base")` は一律 `relation_type="inherits"` になる。
  - `inherits` は `--|>` で描画され、方向は PlantUML 自動レイアウトに委ねられる。
  - `Protocol` / `ABC` / `@abstractmethod` を切り分ける relation logic はない。
- 課題:
  - 図上で継承方向が読みにくい。
  - Python Protocol を実装 class と同じ通常継承として描くため、interface-like contract が読み取りにくい。

## スコープ
- MUST:
  - 通常継承を `-up-|>` として出力する。
  - relation type に `realizes` を追加する。
  - selected class が明示的に `Protocol` / `typing.Protocol` / `typing_extensions.Protocol` を継承する場合、その class を Protocol とみなす。
  - Protocol class への base relation は `realizes` として分類し、`..up|>` として出力する。
  - Protocol class は `<<Protocol>>` decoration を持つ class として描画する。
- MUST NOT:
  - import 実行や runtime inspection をしない。
  - `ABC` / `@abstractmethod` / method-only class を今回 interface と推測しない。
  - association / uses の意味論を変えない。
- OUT OF SCOPE:
  - CLI option 追加。
  - external `typing.Protocol` node を図へ追加表示すること。

## 受け入れ条件
- AC-001:
  - Given: internal `Base` と `Child(Base)` が selected class に含まれる
  - When: PlantUML を生成する
  - Then: relation は `Child -up-|> Base` として出る。
- AC-002:
  - Given: internal `Repository(Protocol)` と `SqlRepository(Repository)` が selected class に含まれる
  - When: PlantUML を生成する
  - Then: `Repository` は `<<Protocol>>` decoration を持ち、`SqlRepository ..up|> Repository` として出る。
- AC-003:
  - Given: Protocol class が method annotation で別 class を参照する
  - When: PlantUML を生成する
  - Then: existing `uses` relation は引き続き `..>` として出る。
- AC-004:
  - Given: 既存 complex manual env `retail_domain`
  - When: `pyclassuml generate` と PlantUML SVG 変換を実行する
  - Then: 通常継承、Protocol decoration、Protocol realization、field / method body が観測できる。

## 例外・エッジケース
- EC-001:
  - 条件: `ABC` / `@abstractmethod` を持つ class
  - 期待: 今回は通常 class inheritance として扱う。
- EC-002:
  - 条件: `Protocol` target が selected set 外または unresolved
  - 期待: 既存の unresolved / selection outside warning と同じ扱いで、relation を捏造しない。

## 非交渉制約
- AST-only / read-only / deterministic output を維持する。
- 新規 path は lowercase のみ。
