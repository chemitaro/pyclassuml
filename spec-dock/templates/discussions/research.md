---
種別: research
ID: "<RESEARCH_ID>"
タイトル: "<RESEARCH_TITLE>"
状態: "draft | completed | archived"
作成者: "<YOUR_NAME>"
最終更新: "YYYY-MM-DD"
親: ["<SCOPE_ID>"]
関連: []
authority: "synthesized"
derived_from: []
reflected_to: []
---

# <RESEARCH_ID> <RESEARCH_TITLE>

## 位置づけ
- 用途: 外部仕様、実装事実、先例、制約、用語衝突、edge case など、検証可能な根拠を整理する。
- authority default: `synthesized`。通常は doc type から推定し、例外時だけ front matter の `authority` で override する。
- この artifact は source-grounded research evidence surface であり、main orchestrator が canonical docs / accepted ADR / `report.md` Evidence Adoption Ledger へ採用するまでは canonical authority ではない。
- 調査結果が選択肢比較を必要とする場合は `disc`、長期判断を支える場合は `adr`、人間判断を必要とする場合は `interview` へつなぐ。
- 事実、推測、未検証事項、用語衝突、edge case、判断への含意を混ぜない。
- local context で解ける疑問は人間に聞かず、この artifact に source-grounding を残す。

## 調査目的 (必須)
- 何を明らかにする調査かを記載する。

## sources / 調査方法 (必須)
- 参照先:
  - ...
- 検証手順:
  - ...
- 実験条件:
  - ...

## facts / 観測できた事実 (必須)
- 観測できた事実を記載する。

## inference / 推測 (必須)
- 事実から推測したこと:
  - ...
- 推測の根拠:
  - ...

## unverified / 未検証事項 (必須)
- まだ確認していないこと:
  - ...
- 確認できない理由:
  - ...

## question candidates / 質問候補 (必須)
- source-grounded に解けず、人間判断が必要な候補:
  - ...
- pressure-test question として切り出すべき候補:
  - ...
- 質問せずに解決できた候補:
  - ...

## terminology conflicts / 用語衝突 (必須)
- 衝突している用語:
  - ...
- 既存 docs / code / tests / discussions での使われ方:
  - ...
- 判断が必要な理由:
  - ...

## edge cases / 具体シナリオ (必須)
- edge case:
  - ...
- その edge case が requirement / design / plan に与える影響:
  - ...

## implications / 判断への含意 (必須)
- requirement / design / plan / adr へ影響する示唆を記載する。

## リスク/制約 (任意)
- ...

## 反映先 (任意)
- reflected_to:
  - ...

## 参考（References） (任意)
- ...
