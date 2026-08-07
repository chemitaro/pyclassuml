---
種別: interview
ID: "20260804t224225z-interview"
タイトル: "depth互換fallback採用方針の確認"
状態: "answered"
作成者: "iwasawayuuta"
最終更新: "2026-08-04"
親: ["iss-00044"]
関連: []
scope: "issue"
scope_id: "iss-00044"
created_at: "2026-08-04T22:42:25Z"
created_by: "iwasawayuuta"
status: "answered"
authority: "user-approved"
adoption_status: "stale"
derived_from: []
reflected_to: []
---

# 20260804t224225z-interview depth互換fallback採用方針の確認

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
    - depth/config precedence の契約が変わるため。
  - `design.md`:
    - resolver の責務と設定解決順序が変わるため。
  - `plan.md`:
    - test matrix と compatibility の検証内容が変わるため。
  - `ADR`:
    - command-specific config only と旧 top-level depth fallback なしの採用判断を記録するため。
- chat 上の軽微な一問では足りない理由:
  - 回答が canonical な要件・設計・計画へ反映される重要判断であり、source-grounded な回答証跡が必要なため。

## 質問の目的 (必須)
- 対象者:
  - ユーザー（仕様・互換性の採用判断者）。
- 何を明確にする質問か:
  - `depth` の command-specific 設定と既存トップレベル設定の後方互換 fallback の採用方針。
- 回答が後続判断へ与える影響:
  - requirement / design / plan の precedence、resolver 責務、test matrix / compatibility の方針を確定する。

## 質問 (必須)
- pressure-test question:
  - generate と diff で設定を分離したとき、既存利用者のトップレベル `depth` をどの期間・順位で互換維持するか。
- 質問:
  - generateとdiffを設定ファイルで分離する場合、`[generate].depth`と`[diff].depth`を追加し、既存トップレベル`depth`は後方互換fallbackとして残す優先順位 `CLI --depth > command-specific config > legacy top-level depth > command default` を採用しますか。それともトップレベル`depth`を廃止し、command-specific設定だけにしますか。
- 回答してほしいこと:
  - Option A / B / C のいずれを採用するか（必要なら理由を添えてください）。

## source-grounded context (必須)
- 確認済みの docs / code / tests / ADR / artifacts / primary source:
  - `src/pyclassuml/config/resolver.py` の `_TOP_LEVEL_KEYS` に `depth`、`_DIFF_KEYS` は `current_state/include_untracked` のみ。
  - 同ファイルの `_build_analysis_config` は `_merged_depth(options.depth, config.get("depth"))` を使い、command 共通で解決する。
  - `CommandOptions.depth` と `AnalysisConfig.depth` は共通である。
  - 現行テストと README もトップレベル `depth` を共通設定として扱っている。
- local context で解決できたこと:
  - 現行実装では `depth` が generate / diff 共通のトップレベル設定であり、diff 専用設定は存在しない。
- まだ人間判断が必要な理由:
  - 新しい command-specific 設定を導入するか、既存トップレベル設定を廃止するかは互換性と仕様の採用判断だから。

## 回答案 (必須)
- Option A:
  - command-specific 設定を追加し、トップレベル `depth` を後方互換 fallback として残す（推奨）。
- Option B:
  - command-specific 設定だけにし、トップレベル `depth` を廃止する（breaking）。
- Option C:
  - 現行の共通トップレベル `depth` を維持し、今回の提案を見送る。

## Codex の分析 (必須)
- 判断軸:
  - 既存設定の互換性、command ごとの意図の明確さ、precedence の決定性、実装・テスト範囲。
- tradeoff:
  - Option A は移行コストを抑えながら分離できる一方、fallback の順位と将来の廃止方針が必要。Option B は単純だが既存設定を壊す。Option C は安全だが diff 固有の depth 要件を解決しない。
- リスク:
  - 方針未確定のまま実装すると、設定 precedence、resolver の責務、既存利用者の挙動、test matrix が不整合になる。
- 具体シナリオ / edge case:
  - top-level `depth=3`、`[diff].depth=1`、CLI `diff --depth=2` の場合、Option A の優先順位では diff は `2`。generate が未指定の場合は `None` となり、legacy top-level fallback が有効なら `3`、それもなければ command default を使う。

## Codex の推奨案 (必須)
- 推奨:
  - Option A: command-specific 追加 + top-level fallback。
- 理由:
  - 既存トップレベル設定を壊さずに generate / diff の個別指定を可能にし、明示的な precedence で決定性と移行性を両立できるため。
- 未回答時の影響:
  - この判断が確定するまで planning を停止する。canonical requirement / design / plan への反映も行わない。

## ユーザー回答 (回答後に必須)
- answer capture:
  - Option A のうち command-specific 設定の導入を採用する。ただし、旧 top-level `depth` の後方互換 fallback は採用しない。
- 回答:
  - 設定ファイルは同一ファイルのまま、`[generate].depth` と `[diff].depth` を完全に分離して設定できるようにする。旧 top-level `depth` は残さず、旧設定からの移行も不要とする。CLI `--depth` は実行コマンドに対して最優先とし、未指定時は generate / diff それぞれの command default を使う。
- 回答日時:
  - 2026-08-05

## 追加確認の要否 (回答後に必須)
- 追加確認が必要か:
  - no
- 必要な場合に次の unanswered `interview` として切り出す質問:
  - なし

## 採用判断 (回答後に必須)
- adoption_status:
  - adopted
- adoption target:
  - `requirement.md`, `design.md`, `plan.md`, `report.md` Evidence Adoption Ledger
- 採用 / 棄却 / deferred の理由:
  - Option A の command-specific 設定という部分は採用するが、ユーザー回答に従い旧 top-level `depth` fallback は採用しない。command-specific config only とし、CLI `--depth` を最優先、未指定時はコマンドごとの default とする。旧設定からの移行は不要とする。
- `report.md` Evidence Adoption Ledger への反映要否:
  - yes
- 2026-08-05にユーザーが旧方針（command-specific depth only / top-level fallbackなし）を撤回した。
- 現行判断は、新規ADR artifact `20260804t232417z-adr-common-config-command-overrides-decision.md` の共通設定ベース＋[generate]/[diff] overrideである。
- この旧interviewは履歴・superseded evidenceとしてcanonical adoptionには使わない。
- 新方針の優先順位は CLI > command-specific > top-level common > command default。

## requirement / design / plan / ADR への含意 (回答後に必須)
- `requirement.md`:
  - generate / diff はそれぞれ `[generate].depth` / `[diff].depth` を使用し、旧 top-level `depth` はサポートしない。CLI `--depth` が最優先で、未指定時は各 command default を使用する。
- `design.md`:
  - resolver は command-specific depth と CLI override を分離して解決し、旧 top-level depth fallback を持たない。
- `plan.md`:
  - generate / diff の個別設定、CLI 優先順位、未指定時の command default、旧 top-level depth を fallback にしないことを検証対象とする。
- `ADR`:
  - 必要に応じて、command-specific config only と旧設定移行不要の判断を ADR 化する。
- reflected_to 更新方針:
  - canonical docs と `report.md` Evidence Adoption Ledger へ反映された時点で、実際のパスを `reflected_to` に追記する。
- 2026-08-05の撤回により、旧方針の反映先はなく、この旧interviewは履歴・superseded evidenceとしてcanonical adoptionには使わない。現行判断は新規ADR artifact `20260804t232417z-adr-common-config-command-overrides-decision.md` に基づく。
- 新方針の優先順位は CLI > command-specific > top-level common > command default。
- adoption reflection:
  - 本 artifact はユーザー承認済みの採用判断を保持する。canonical docs への反映完了までは evidence として扱う。

## 条件付き補足 (必要な場合だけ)
- PlantUML 図:
  ```plantuml
  @startuml
  ' 図は不要: 本判断は設定 precedence と互換性方針の記録で完結する
  @enduml
  ```
- 詳細 tradeoff:
  - command-specific config only は設定意図を明確にできる一方、旧 top-level `depth` を利用していた設定は自動移行されない。今回は後方互換性を不要とするため、この breaking change を受け入れる。
- 後続 reflection proposal:
  - canonical requirement / design / plan の該当箇所と `report.md` Evidence Adoption Ledger にこの決定を反映する。
- 追加で作る artifacts:
  - なし

- 2026-08-05にユーザーが旧方針（command-specific depth only / top-level fallbackなし）を撤回した。現行判断は、新規ADR artifact `20260804t232417z-adr-common-config-command-overrides-decision.md` の共通設定ベース＋[generate]/[diff] overrideである。この旧interviewは履歴・superseded evidenceとしてcanonical adoptionには使わない。新方針の優先順位は CLI > command-specific > top-level common > command default。
