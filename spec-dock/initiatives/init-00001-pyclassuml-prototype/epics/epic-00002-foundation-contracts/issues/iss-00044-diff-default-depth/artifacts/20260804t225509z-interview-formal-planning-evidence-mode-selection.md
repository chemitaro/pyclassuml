---
種別: interview
ID: "20260804t225509z-interview"
タイトル: "formal planning evidence mode selection"
状態: "draft | answered | archived"
作成者: "iwasawayuuta"
最終更新: "2026-08-04"
親: ["iss-00044"]
関連: []
scope: "<initiative | epic | issue | local-topic>"
scope_id: "iss-00044"
created_at: "2026-08-04THH:MM:SSZ"
created_by: "iwasawayuuta"
status: "unanswered"
authority: "proposed"
adoption_status: "unreviewed"
derived_from: []
reflected_to: []
---

# 20260804t225509z-interview formal planning evidence mode selection

## 位置づけ
- 用途: 重要判断に関わる一つの質問を、回答前の source-grounded 正式質問シートとして作成し、回答後に同じ artifact を完成 record にする。
- authority default: `proposed`。ユーザー回答と採用判断を反映した後は、必要に応じて `user-approved` または `synthesized` に更新する。
- この artifact は answer capture / adoption target / reflection の evidence surface であり、main orchestrator が canonical docs / accepted ADR / `report.md` Evidence Adoption Ledger へ採用するまでは canonical authority ではない。
- 技術的に調べられることは先に docs / code / tests / ADR / artifacts / primary source を確認する。
- 一つの `interview` artifact には one essential question / 一つの本質的な質問だけを書く。回答によって新しい高影響な曖昧さが見つかった場合は、追加質問をこの file に増やさず、次の unanswered `interview` を作成する。
- trivial な yes/no は、重要な判断、後続反映、回答証跡が必要なら `interview` を使い、そうでなければ issue comment や `blank` で足りる。
- 回答から複数質問の synthesis が必要になったら `disc`、追加調査が必要になったら `research`、長期判断が固まったら `adr` を新規作成する。

## 正式質問として扱う理由 (必須)
- 影響する artifact:
  - `requirement.md`:
    - ...
  - `design.md`:
    - ...
  - `plan.md`:
    - ...
  - `ADR`:
    - ...
- chat 上の軽微な一問では足りない理由:
  - 未同期worktreeでChatGPT-First formal planningを進める evidence mode は、formal planning の入力証跡と信頼度に影響するため、回答と後続の採用判断を記録する必要がある。

## 質問の目的 (必須)
- 対象者:
  - planning の進行判断を行うユーザー
- 何を明確にする質問か:
  - local-context evidence mode で直ちに進めるか、GitHub同期証跡を用意して github-synced で進めるか
- 回答が後続判断へ与える影響:
  - ChatGPT-First formal planning の実行モード、出力の信頼度表記、または別経路への切替を決める。

## 質問 (必須)
- pressure-test question:
  -
- 質問:
  - この未同期worktreeを local-context evidence modeで使ってChatGPT-First formal planningを進めますか。それとも、名前付きbranch/同一HEADのGitHub同期証跡を用意してから github-synced で進めますか。
- 回答してほしいこと:
  - 次の選択肢から一つを選んでください。

## source-grounded context (必須)
- 確認済みの docs / code / tests / ADR / artifacts / primary source:
  - 現在のworktreeは detached HEAD で、HEAD は `8bb20e9faa060e68900045c0aa1d13040ec3759f`。
  - `origin` は `https://github.com/chemitaro/pyclassuml.git`。
  - `origin` の `refs/heads/*` に同一HEADを指すbranchはない。
  - formal planning skill は exact named branch/HEAD の GitHub verification を要求する。
- local context で解決できたこと:
  - 現在のHEAD、origin URL、remote refs/heads に同一HEADのbranchがないことを確認できた。
- まだ人間判断が必要な理由:
  - formal planning の前提を local-context evidence mode の低信頼度で満たすか、GitHub同期後まで待つかはユーザーの進行判断だから。

## 回答案 (必須)
- Option A:
  - local-contextで進める（GitHub同期を要件にせず、出力にlocal-context/低信頼度を明記）
- Option B:
  - github-syncedまで待つ（ユーザーが名前付きbranch/同一HEADの同期状態を用意する。こちらからcommit/pushしない）
- Option C:
  - ChatGPT-Firstを中止して別経路（manual backupには別途明示承認が必要）

## Codex の分析 (必須)
- 判断軸:
  - ...
- tradeoff:
  - ...
- リスク:
  - ...
- 具体シナリオ / edge case:
  - ...

## Codex の推奨案 (必須)
- 推奨:
  - ...
- 理由:
  - ...
- 未回答時の影響:
  - ...

## ユーザー回答 (回答後に必須)
- answer capture:
  -
- 回答:
  -
- 回答日時:
  -

## 追加確認の要否 (回答後に必須)
- 追加確認が必要か:
  - yes | no
- 必要な場合に次の unanswered `interview` として切り出す質問:
  - ...

## 採用判断 (回答後に必須)
- adoption_status:
  - unreviewed | adopted | partially_adopted | rejected | deferred | stale | blocked
- adoption target:
  - `requirement.md` | `design.md` | `plan.md` | `ADR` | `report.md` Evidence Adoption Ledger | none
- 採用 / 棄却 / deferred の理由:
  - ...
- `report.md` Evidence Adoption Ledger への反映要否:
  - yes | no

## requirement / design / plan / ADR への含意 (回答後に必須)
- `requirement.md`:
  - ...
- `design.md`:
  - ...
- `plan.md`:
  - ...
- `ADR`:
  - ...
- reflected_to 更新方針:
  - ...
- adoption reflection:
  - ...

## 条件付き補足 (必要な場合だけ)
- PlantUML 図:
  ```plantuml
  @startuml
  ' TODO: 質問依存、意思決定フロー、before/after、責務境界が必要なら追加する
  @enduml
  ```
- 詳細 tradeoff:
  - ...
- 後続 reflection proposal:
  - ...
- 追加で作る artifacts:
  - ...
