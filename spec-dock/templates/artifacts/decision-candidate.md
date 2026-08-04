---
種別: decision-candidate
ID: "<DECISION_CANDIDATE_ID>"
タイトル: "<DECISION_CANDIDATE_TITLE>"
状態: "draft | proposed | accepted | rejected | deferred"
作成者: "<YOUR_NAME>"
最終更新: "YYYY-MM-DD"
親: ["<SCOPE_ID>"]
関連: []
authority: "proposed"
derived_from: []
reflected_to: []
---

# <DECISION_CANDIDATE_ID> <DECISION_CANDIDATE_TITLE>

## 位置づけ
- 用途: requirement / design / plan / ADR へ反映する前の判断候補を、採否と反映先が追える形で整理する。
- authority default: `proposed`。この artifact だけでは accepted decision ではありません。
- 採用された判断は canonical docs、accepted ADR、または `report.md` Evidence Adoption Ledger へ反映します。
- 長期的な architecture / contract / migration decision として固定する必要がある場合は `adr` へ昇格します。

## 判断候補 (必須)
- proposed decision:
  - ...
- trigger:
  - ...
- affected scope:
  - ...

## observed facts (必須)
- ...

## ambiguity / constraint (必須)
- ...

## options considered (必須)
- Option A:
  - ...
- Option B:
  - ...

## rationale (必須)
- ...

## adoption target (必須)
- `requirement.md`:
  - ...
- `design.md`:
  - ...
- `plan.md`:
  - ...
- `ADR`:
  - ...
- `report.md` Evidence Adoption Ledger:
  - ...

## risk if wrong (必須)
- ...

## rollback or revisit (必須)
- ...

## status / disposition (必須)
- status:
  - proposed | accepted | rejected | deferred | superseded
- disposition evidence:
  - ...
