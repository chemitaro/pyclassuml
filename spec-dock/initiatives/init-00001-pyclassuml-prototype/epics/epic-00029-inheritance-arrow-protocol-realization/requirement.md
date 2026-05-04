---
種別: 要件定義書（Epic）
ID: "epic-00029"
タイトル: "Inheritance Arrow And Protocol Realization"
関連GitHub: ["#29"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-05"
親: ["init-00001"]
---

# epic-00029 Inheritance Arrow And Protocol Realization — 要件定義（WHAT / WHY）

## 目的
- Python class diagram の継承表現を読みやすくし、継承矢印を常に上向きにする。
- `typing.Protocol` / `typing_extensions.Protocol` を Python における interface-like contract とみなし、実装 class から Protocol への関係を点線上向き矢印で表現する。

## Epic requirements
- E-RQ-001:
  - 通常 class inheritance は PlantUML 上で上向き矢印として出力する。
- E-RQ-002:
  - Protocol を interface-like class として判定し、Protocol への継承は通常継承と区別した relation として扱う。
- E-RQ-003:
  - AST-only / read-only / import 実行なしの境界を維持する。

## Epic acceptance criteria
- E-AC-001:
  - Given: `class Child(Base): ...`
  - When: `pyclassuml generate` が PlantUML を生成する
  - Then: relation は `Child -up-|> Base` 相当の上向き通常継承として出る。
- E-AC-002:
  - Given: `class Contract(Protocol): ...` と `class Impl(Contract): ...`
  - When: `pyclassuml generate` が PlantUML を生成する
  - Then: `Contract` は Protocol として識別可能で、`Impl ..up|> Contract` 相当の上向き点線 realization として出る。
- E-AC-003:
  - Given: 既存の association / uses relation
  - When: 同じ図を生成する
  - Then: association / uses の既存意味論を壊さない。

## スコープ
- MUST:
  - relation vocabulary に Protocol realization を表す語彙を追加する。
  - 通常継承と Protocol realization の render arrow を上向きにする。
  - Protocol 判定は明示的な `Protocol` base を優先する。
- MUST NOT:
  - 対象コードを import 実行しない。
  - 対象ソースコードを書き換えない。
  - field / method / association / uses の既存表現を意図なく変えない。
- OUT OF SCOPE:
  - `ABC` / `ABCMeta` / `@abstractmethod` の interface 扱い。
  - method-only class を interface と推測する heuristic。
  - 外部標準ライブラリ class を必ず図に追加表示すること。

## 境界
- Always:
  - AST から取得できる明示的情報だけで判定する。
  - false positive 回避を優先する。
- Ask:
  - `ABC` を interface として扱う opt-in を導入する場合。
- Never:
  - duck typing や runtime inspection で interface を推測しない。
