---
種別: disc
ID: "<DISC_ID>"
タイトル: "<DISC_TITLE>"
状態: "draft | proposed | archived"
作成者: "<YOUR_NAME>"
最終更新: "YYYY-MM-DD"
親: ["<SCOPE_ID>"]
関連: []
authority: "proposed"
derived_from: []
reflected_to: []
---

# <DISC_ID> <DISC_TITLE>

## 位置づけ
- 用途: 集まった情報をもとに、論点、評価軸、選択肢、合意点/未合意点を整理する。
- authority default: `proposed`。通常は doc type から推定し、例外時だけ front matter の `authority` で override する。
- 人間から回答を引き出し、回答欄や未回答事項を管理する場合は `interview` を使う。
- 生ログや未整理の思考は `scratch`、事実確認や外部根拠は `research`、長期判断の固定は `adr` に分ける。
- doc が大きくなりすぎたら、質問回答は `interview`、事実調査は `research`、raw capture は `scratch`、長期決定は `adr` へ分割する。

## 議題 (必須)
- 今回決めること/整理することを明確に記載する。

## 背景 (必須)
- 前提、制約、現状の課題を箇条書きで記載する。

## 選択肢 (必須)
- Option A:
  - Pros:
    - ...
  - Cons:
    - ...
- Option B:
  - Pros:
    - ...
  - Cons:
    - ...

## 推奨案 (必須)
- 現時点の推奨案と理由を記載する。

## 未決事項 (任意)
- ...

## 次アクション (必須)
- `requirement.md` / `design.md` / `plan.md` / `adr` へ反映する内容:
  - ...
- 追加で作る discussion docs:
  - ...
