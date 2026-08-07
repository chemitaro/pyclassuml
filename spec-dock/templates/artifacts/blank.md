---
種別: artifact
ID: "<ARTIFACT_ID>"
タイトル: "<ARTIFACT_TITLE>"
状態: "draft | archived"
作成者: "<YOUR_NAME>"
最終更新: "YYYY-MM-DD"
親: ["<SCOPE_ID>"]
template: "blank"
authority: "raw"
derived_from: []
reflected_to: []
---

# <ARTIFACT_ID> <ARTIFACT_TITLE>

## 位置づけ
- 用途: 型を先に決めず、scope-local `artifacts/` に作業用 evidence を置く。
- `blank` は template identity であり、filename token ではありません。filename は `<ts>-<slug>.md` / same-second collision は `<ts>-<nn>-<slug>.md` を使い、`blank` を含める必要はありません。
- canonical `requirement.md` / `design.md` / `plan.md` / `report.md` の代替ではありません。採用する内容は canonical docs、accepted ADR、または `report.md` Evidence Adoption Ledger へ反映します。

## メモ (必須)
- ...

## 整理メモ（任意）
- facts:
  - ...
- questions:
  - ...
- decisions:
  - ...
- actions:
  - ...
- links:
  - ...
- discard condition:
  - ...
