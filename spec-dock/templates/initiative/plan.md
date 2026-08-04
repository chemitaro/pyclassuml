---
種別: 計画書（Initiative）
ID: "<INIT_ID>"
タイトル: "<INIT_TITLE>"
関連GitHub: ["<GITHUB_ISSUE_NUMBER_OR_URL>"]
状態: "draft | approved"
作成者: "<YOUR_NAME>"
最終更新: "YYYY-MM-DD"
依存: ["requirement.md", "design.md"]
---

# <INIT_ID> <INIT_TITLE> — 計画（ロードマップ / Epic）

## 作成方針
- この文書は Initiative から Epic 群へ作業を渡すロードマップを固定する。
- 日本語を主文とし、ファイルパス、コマンド、コード識別子、SpecDock 固定語は原文のまま扱ってよい。
- Scope ownership と authority flow は `docs/authoring/scope-layering.md` を参照し、この template には責務表を複製しない。
- Epic / Issue の詳細実装順序は、各スコープの planning / execution で具体化する。

## この計画が達成する目標 / 指標
- 目標:
  - ...
- 対象指標:
  - ...

## マイルストーン
- M1:
  - 成果物:
  - 完了条件:
- M2:
  - ...

## エピックポートフォリオ（Epic portfolio）
- epic-xxxx-...:
  - 目的:
    - ...
  - 成果物:
    - ...
  - 指標との対応:
    - ...
  - 依存:
    - ...
- epic-xxxx-...:
  - ...

## 順序と理由
- 順序の根拠:
  - ...
- 並列化できるもの:
  - ...
- dependency / blocker:
  - ...

## 意思決定ゲート
- G1 戦略レビュー:
  - ...
- G2 マイルストーン準備確認:
  - ...
- G3 ガバナンス / docs 影響:
  - ...
- G9 最終 Initiative 計画レビュー:
  - ...

## エピックへ渡す準備完了条件（handoff readiness）
- 各 Epic に最低限渡すもの:
  - requirement:
    - ...
  - draft design:
    - ...
  - draft implementation plan:
    - ...
  - report evidence:
    - ...
- fresh reviewer gate（最新レビューゲート）:
  - spec-reviewer:
    - ...
- 未解決の質問が残る場合の扱い:
  - ...

## エピック / Issue 分割変更（controlled re-slicing）
- 初期分割:
  - ...
- 追加 Epic / Issue を許容する条件:
  - ...
- 既存分割を維持する条件:
  - ...
- 分割変更時に更新する artifact:
  - `requirement.md`:
    - ...
  - `design.md`:
    - ...
  - `plan.md`:
    - ...
  - `report.md` Evidence Adoption Ledger:
    - ...

## 指標レビュー計画
- レビュー時期:
  - ...
- dashboard / 情報源:
  - ...

## ロールアウト計画
- ロールアウト時期:
  - ...
- リリース / 周知:
  - ...

## エピック準備完了条件（Epic readiness criteria）
- Epic に要求する最低条件:
  - ...
- Epic planning 完了条件:
  - 要件定義書は正本化し、設計書 / 実装計画書の draft artifact と採用判断を残す。
- Epic execution handoff:
  - Issue ごとの開始条件、依存、最終 PR 担当を明示する。

## 最終完了条件
- マイルストーン完了:
  - ...
- 成功指標レビュー:
  - ...
- 残 follow-up の担当:
  - ...

## 依存 / ブロッカー
- D-001:
  - ...
- D-002:
  - ...

## 最終 PR / closeout 方針（final PR / closeout）
- PR 作成タイミング:
  - ...
- まとめて PR に含める完了証跡:
  - ...
- GitHub issue close / SpecDock finish の順序:
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
