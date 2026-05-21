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
- 用途: 外部仕様、実装事実、先例、制約など、検証可能な根拠を整理する。
- authority default: `synthesized`。通常は doc type から推定し、例外時だけ front matter の `authority` で override する。
- 調査結果が選択肢比較を必要とする場合は `disc`、長期判断を支える場合は `adr`、人間判断を必要とする場合は `interview` へつなぐ。
- 事実、推測、未検証事項、判断への含意を混ぜない。

## 調査目的 (必須)
- 何を明らかにする調査かを記載する。

## 調査方法 (必須)
- 参照先、検証手順、実験条件を記載する。

## 調査結果 (必須)
- 観測できた事実を記載する。

## 推測 / 未検証事項 (必須)
- 推測:
  - ...
- 未検証:
  - ...

## 判断への含意 (必須)
- requirement / design / plan / adr へ影響する示唆を記載する。

## リスク/制約 (任意)
- ...

## 反映先 (任意)
- reflected_to:
  - ...

## 参考（References） (任意)
- ...
