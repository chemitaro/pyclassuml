---
種別: 要件定義書（Issue）
ID: "iss-00042"
タイトル: "Suppress Self Dependency Relations"
関連GitHub: ["#42"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-26"
親: ["epic-00039", "init-00038"]
---

# iss-00042 Suppress Self Dependency Relations — 要件定義（WHAT / WHY）

## 目的

`dependency` relation の導入後に実プロダクトの差分クラス図で観測された、同一クラスから同一クラスへの `..>` relation を抑制する。

## 背景・現状

- `iss-00040` で、method body 内の一時的なクラス利用を UML dependency として PlantUML `..>` に描画するようにした。
- 実プロダクト `taikyohiyou_project-issue-1716` で `make issue-diff-class-diagram` を実行した結果、意図した dependency は描画された。
- 一方で `DispatchOrigin ..> DispatchOrigin` のような self dependency も描画された。
- self dependency は class diagram の読者に新しい構造情報をほぼ与えず、実務上はノイズになりやすい。

## スコープ

### 必須

- `source_class_id == target_class_id` となる `dependency` relation を最終出力に含めない。
- 既存の異なるクラス間の `dependency` relation は維持する。
- `generate` と `diff` の両方で同じ relation suppression policy を適用する。

### 禁止

- `dependency` の矢印表記 `..>` を変更しない。
- `association` / `composition` / `aggregation` などの構造 relation に置き換えない。
- runtime direct dependency と type-only dependency の詳細分類をこの issue で追加しない。
- CLI option や設定 schema を増やさない。
- 解析対象コードを import 実行しない。

### 対象外

- `type-only` / `runtime` のラベル表示。
- dependency relation の細分類。
- self inheritance など、`dependency` 以外の異常 relation の設計見直し。

## 非交渉制約

- 外部 CLI / 読み取り専用 / AST 静的解析のみという pyclassuml の基本制約を維持する。
- 図の意味論は一般的な UML class diagram の dependency semantics に沿わせる。
- 対策は小さく、壊れにくく、既存 relation output への影響を self dependency suppression に限定する。

## 受け入れ条件

### AC-001: self dependency を描画しない

- 前提: 1 つの class が method body、型注釈、classmethod return などで自身を参照する。
- 操作: `generate` または `diff` で PlantUML を生成する。
- 期待結果: `A ..> A` に相当する relation は出力されない。
- 観測点: `.puml` relation lines。

### AC-002: 異なるクラス間の dependency は維持する

- 前提: class `A` が method body で class `B` を生成または参照する。
- 操作: `generate` または `diff` で PlantUML を生成する。
- 期待結果: `A ..> B` は引き続き出力される。
- 観測点: `.puml` relation lines。

### AC-003: relation policy は generate / diff で一致する

- 前提: self dependency と non-self dependency を含む fixture がある。
- 操作: `generate` と `diff` の両方を実行する。
- 期待結果: self dependency は両方で抑制され、non-self dependency は両方で維持される。
- 観測点: app-level tests または共通 selection tests。

## エッジケース

### EC-001: 他 relation が同じ endpoint にある場合

- 条件: `A` から `A` への dependency 候補と、別種の relation 候補が同時に存在する。
- 期待: 少なくとも `dependency` の self relation は出力されない。`dependency` 以外の扱いはこの issue で新規仕様化しない。

### EC-002: type-only / runtime の混在

- 条件: type annotation 由来と method body 由来の dependency が混在する。
- 期待: この issue では区別せず、self dependency 抑制だけを適用する。

## 調査メモ

- 技術的には relation 正規化層で `relation_type == "dependency"` かつ `source_class_id == target_class_id` を除外する方法が最小と見込む。
- 詳細分析は `discussions/20260526t070111z-research-self-dependency-suppression-analysis.md` に記録する。
