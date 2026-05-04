---
種別: 計画書（Epic）
ID: "epic-00023"
タイトル: "Class Member Rendering"
関連GitHub: ["#23"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md"]
親: ["init-00001"]
---

# epic-00023 Class Member Rendering — 計画（Issues / Order）

## この計画で閉じる E-RQ / E-AC
- E-RQ:
  - E-RQ-001 shared contract を member-aware に更新する
  - E-RQ-002 AST-only member parse を追加する
  - E-RQ-003 typed relation classification を固定する
  - E-RQ-004 class body render を追加する
  - E-RQ-005 `iss-00014` / `iss-00018` の古い前提を supersede / extend する
  - E-RQ-006 CLI / manual E2E で実証する
- E-AC:
  - E-AC-001 class body + typed relation が観測できる
  - E-AC-002 Pydantic field / quoted forward ref を member + relation で表現できる
  - E-AC-003 warning degraded output を維持する
  - E-AC-004 deterministic output を維持する

## Issue 分割方針
- slicing principle:
  - shared contract -> parse evidence -> relation classification -> render -> E2E の dependency order で 1 issue = 1 owner seam を守る。
- exceptions:
  - `iss-00026` は existing `frameworks.pydantic` の一部前提に影響するため、analyze owner を保ったまま framework dedupe の影響も確認する。

## Issue 一覧（順序 / tranche 付き）
- iss-00024-model-member-contracts:
  - 目的:
    - member-aware shared DTO と relation vocabulary を固定する。
  - deliverable:
    - `ClassMember`, `MemberParameter`, `MemberKind`, `MemberVisibility`, shared `SelectedRelation` contract、`ParsedModule.members` / `RenderReadyModel.members` shape。
  - tranche:
    - T1 contract baseline
  - closes:
    - E-RQ-001, E-RQ-005, E-AC-004
  - depends on:
    - existing `iss-00014`, `iss-00018` docs を参照するが、実装依存はなし
- iss-00025-parse-class-members:
  - 目的:
    - AST-only で class members / base refs / typed annotation refs を抽出する。
  - deliverable:
    - member-aware `ParsedModule`、deterministic source order、unsupported annotation degradation。
  - tranche:
    - T2 parse evidence
  - closes:
    - E-RQ-002, E-AC-001, E-AC-002, E-AC-004
  - depends on:
    - iss-00024
- iss-00026-analyze-typed-relations:
  - 目的:
    - parsed evidence を `inherits`, `association`, `uses` に分類する。
  - deliverable:
    - typed relation classification、warning diagnostics、module import fallback policy。
  - tranche:
    - T3 analyze classification
  - closes:
    - E-RQ-003, E-RQ-005, E-AC-001, E-AC-002, E-AC-003, E-AC-004
  - depends on:
    - iss-00024
    - iss-00025
- iss-00027-render-class-members:
  - 目的:
    - PlantUML class body と typed arrow mapping を追加する。
  - deliverable:
    - member-aware `RenderReadyModel` consumption、class body serializer、typed relation arrow mapping。
  - tranche:
    - T4 render output
  - closes:
    - E-RQ-004, E-RQ-005, E-AC-001, E-AC-003, E-AC-004
  - depends on:
    - iss-00024
    - iss-00025
    - iss-00026
- iss-00028-member-rendering-e2e:
  - 目的:
    - CLI generate / diff と manual environment で epic outcome を最終確認する。
  - deliverable:
    - tracked integration assertions、manual `retail_domain` acceptance evidence。
  - tranche:
    - T5 integration closure
  - closes:
    - E-RQ-006, E-AC-001, E-AC-002, E-AC-003, E-AC-004
  - depends on:
    - iss-00024
    - iss-00025
    - iss-00026
    - iss-00027

## 統合チェックポイント
- G1 decomposition review:
  - `iss-00024` 完了時点で DTO / vocabulary / compatibility policy が `iss-00025` 以降を拘束できるか確認する。
- G2 integration readiness:
  - `iss-00026` 完了時点で render に必要な selected members / typed relations / warnings が揃っていることを確認する。
- G3 rollout/docs impact:
  - `iss-00027` 完了時点で `iss-00018` 前提との差分が tests / snapshots / report owner に閉じているか確認する。
- G9 final epic spec review:
  - `iss-00028` の validation と manual acceptance が揃ったら epic close readiness を確認する。

## 品質ゲート
- test / observability / migration / docs:
  - each issue で spec review pass を取り、code review / QA review は実装 issue ごとに閉じる。
  - epic 全体では `./spec-dock/scripts/spec-dock validate`, `git diff --check`, uppercase path check, CLI integration, manual `retail_domain` acceptance を要求する。
  - warning degraded output の diagnostics code / message / order は snapshot で固定する。

## ロールアウト / docs impact
- rollout order:
  - contract first。issue 24 の前に parse / analyze / render 実装へ入らない。
- contract / docs refresh:
  - epic docs で `iss-00014` / `iss-00018` を supersede / extend する箇所を明記し、各 issue report で evidence を残す。

## Issue readiness contract
- Issue に要求する最低条件:
  - requirement / design / plan に owner, target files, verification, supersession scope が明記されていること。
  - downstream issue は upstream issue の DTO / vocabulary が固定されるまで implementation start しないこと。

## final exit contract
- E-AC closure:
  - class body, method signatures, field relations, inherits relation, warnings が tracked test と manual env の両方で観測できる。
- integration / rollout complete:
  - generate / diff CLI で member-aware output が出る。
- docs impact resolved:
  - epic / issue report が supersession と validation evidence を説明できる。

## 依存 / ブロッカー
- D-001:
  - `iss-00014` の current relation contract は `uses` fixed なので、issue 26 で supersede 範囲を明示しないと analyze owner が曖昧になる。
- D-002:
  - `iss-00018` の `RenderReadyModel.members=()` 前提を外さないと render 側で member body を持てない。
- D-003:
  - `frameworks.pydantic` が current implementation で forward ref を `uses` relation として追加しているため、issue 26 / 27 で duplicate / vocabulary drift を防ぐ必要がある。

## 未確定事項
- なし:
  - epic sequencing は `24 -> 25 -> 26 -> 27 -> 28` で固定する。
