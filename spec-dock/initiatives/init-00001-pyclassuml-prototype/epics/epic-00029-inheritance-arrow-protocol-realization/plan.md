---
種別: 計画書（Epic）
ID: "epic-00029"
タイトル: "Inheritance Arrow And Protocol Realization"
関連GitHub: ["#29"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-05"
依存: ["requirement.md", "design.md"]
親: ["init-00001"]
---

# epic-00029 Inheritance Arrow And Protocol Realization — 計画（Issues / Order）

## この計画で閉じる E-RQ / E-AC
- E-RQ:
  - E-RQ-001, E-RQ-002, E-RQ-003
- E-AC:
  - E-AC-001, E-AC-002, E-AC-003

## Issue 分割方針
- 今回は既存 relation pipeline の小拡張で完結するため、1 issue で実装・E2E・manual acceptance まで閉じる。

## Issue 一覧
- iss-00030-render-upward-inheritance-protocol-realization:
  - 目的:
    - 通常継承の上向き矢印と Protocol realization の点線上向き矢印を実装する。
  - deliverable:
    - source / tests / manual evidence / report
  - closes:
    - E-RQ-001, E-RQ-002, E-RQ-003
    - E-AC-001, E-AC-002, E-AC-003

## 統合チェックポイント
- G1:
  - issue docs が実装可能であること。
- G2:
  - targeted / full tests が通ること。
- G3:
  - manual env で complex sample を再生成し、SVG まで図示できること。

## final exit contract
- `iss-00030` が close 済み。
- `epic-00029` が close 済み。
- `spec-dock validate` が成功。
- GitHub issue #29 / #30 が CLOSED。
