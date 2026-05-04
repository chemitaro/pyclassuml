---
種別: 要件定義書（Issue）
ID: "iss-00024"
タイトル: "Model Member Contracts"
関連GitHub: ["#24"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
親: ["epic-00023", "init-00001"]
---

# iss-00024 Model Member Contracts — 要件定義（WHAT / WHY）

## 目的
- class member を parse / analyze / render 間で安全に受け渡す shared contract を固定する。
- `iss-00018` の `RenderReadyModel.members=()` authoritative 契約と、`iss-00014` 起点の `relation_type="uses"` 前提を、この issue の DTO 契約で拡張可能な形へ更新する。

## 背景・現状
- 現状の挙動:
  - current output は class 一覧 + relation line のみで、class body は描画されない。
  - `src/pyclassuml/model/contracts.py` の `RenderReadyModel.members` は string tuple 契約だが、実装では常に `()` を authoritative に保持している。
  - relation inventory は `SelectedRelation` が持つが、`iss-00014` の実装 / 契約では `relation_type="uses"` が MVP 固定である。
- 現状の課題:
  - parse から render まで同じ member DTO を共有していないため、field / method を diagram body に表示できない。
  - `render` と `frameworks` が `analyze.selection.SelectedRelation` を直接 import しており、shared contract と seam-local owner が曖昧である。
  - typed relation vocabulary が固定されていないため、`inherits` / `association` / `uses` を deterministic に扱えない。
- 再現手順:
  1. `src/pyclassuml/model/contracts.py` と `src/pyclassuml/render/document.py` を確認する。
  2. `RenderReadyModel.members=()` と `relation_type="uses"` 前提が current contract であることを確認する。
- 情報源:
  - `src/pyclassuml/model/contracts.py`
  - `src/pyclassuml/analyze/selection.py`
  - `src/pyclassuml/render/document.py`
  - `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00003-core-analysis/issues/iss-00014-analyze-relationship-and-selection/{requirement,design}.md`
  - `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00004-framework-render-report/issues/iss-00018-render-uml-document/{requirement,design}.md`

## 対象ユーザー / 利用シナリオ（必要時）
- 主な利用者:
  - parse / analyze / render の実装者
- 代表シナリオ:
  - issue 25 で抽出した field / method を issue 27 が render できる shared DTO を先に確定する。
  - issue 26 が typed relation vocabulary を安全に扱えるようにする。

## スコープ
- MUST:
  - shared DTO `ClassMember`, `MemberParameter`, `MemberKind`, `MemberVisibility` を追加する。
  - `ParsedModule.members` と `RenderReadyModel.members` を structured member collection に更新する。
  - relation inventory の shared contract を fixed し、`relation_type` vocabulary を `inherits`, `association`, `uses` に制限する。
  - `SelectedRelation` / `SelectedRelations` を shared model owner へ昇格するか、同等の shared import surface を追加する。
  - constructor compatibility、tuple coercion、stable ordering、validation policy を明記する。
  - no convenience field:
    - preformatted PlantUML line や display text を contract に入れない。
- MUST NOT:
  - AST parse、relation classification、PlantUML render をこの issue で実装しない。
  - runtime metadata や mutable state を shared DTO に持ち込まない。
- OUT OF SCOPE:
  - member extraction algorithm。
  - typed relation resolution algorithm。
  - CLI / report observable behavior の変更。

## 境界
- Always:
  - model contract の owner は `src/pyclassuml/model/contracts.py` と `src/pyclassuml/model/__init__.py`。
  - shared DTO は immutable / tuple-based / validation 付きとする。
  - `RenderReadyModel.members` は selected classes 向け render-ready member collection を保持する。
- Ask:
  - `SelectedRelation` を rename する場合。
  - `relation_type` vocabulary を 3 種より増やす場合。
- Never:
  - render 専用の convenience string を DTO に保存しない。
  - member ordering を downstream 推測に委ねない。

## 非交渉制約
- AST-only / import 非実行 / non-invasive / deterministic な全体骨格を壊さない。
- new contract 追加後も existing DTO constructor の後方互換を極力維持する。

## 前提
- `ClassId`, `Diagnostic`, `ParsedModule`, `RenderReadyModel` は既に shared model 契約として存在する。
- issue 25 以降は、この issue で fixed した member DTO shape を正本として使う。

## 受け入れ条件
- AC-001:
  - Actor:
    - model seam 実装者
  - Given:
    - existing `ParsedModule` / `RenderReadyModel` / `SelectedRelation` contract がある。
  - When:
    - member-aware shared DTO を追加する。
  - Then:
    - `ParsedModule.members` と `RenderReadyModel.members` が structured collection を保持でき、validation test が通る。
  - 観測点:
    - `tests/model/test_contracts.py`
- AC-002:
  - Actor:
    - analyze / render 実装者
  - Given:
    - relation inventory を shared handoff として使いたい。
  - When:
    - relation contract を更新する。
  - Then:
    - `relation_type` は `inherits`, `association`, `uses` だけを許可し、shared import surface から利用できる。
  - 観測点:
    - relation DTO validation test、import compatibility test
- AC-003:
  - Actor:
    - downstream issue 実装者
  - Given:
    - class member を render text へ変換したい。
  - When:
    - `ClassMember` を使う。
  - Then:
    - owner class、kind、visibility、source order、annotation / parameters / return annotation、modifiers を lossless に参照できる。
  - 観測点:
    - DTO construction test、field / method sample fixtures

## 例外・エッジケース
- EC-001:
  - 条件:
    - field member に annotation がない。
  - 期待:
    - `annotation_text=None` 相当の nullability を許可し、member 自体は保持できる。
  - 観測点:
    - DTO validation test
- EC-002:
  - 条件:
    - method member に parameter が 0 件、または return annotation がない。
  - 期待:
    - empty tuple / `None` を許可する。
  - 観測点:
    - DTO validation test
- EC-003:
  - 条件:
    - downstream が list や generator を渡す。
  - 期待:
    - constructor は tuple 化し、stable order を保持する。
  - 観測点:
    - coercion test

## 入力→出力例（必要時）
- EX-001:
  - Input:
    - class field `customer: CustomerAccount`
  - Output:
    - `ClassMember(owner_class_id="pkg/order.py:Order", name="customer", kind="field", visibility="public", annotation_text="CustomerAccount", parameters=(), return_annotation_text=None, modifiers=(), source_order=10)`
- EX-002:
  - Input:
    - method `def total(self) -> Decimal:`
  - Output:
    - `ClassMember(owner_class_id="pkg/order.py:Order", name="total", kind="method", visibility="public", annotation_text=None, parameters=(), return_annotation_text="Decimal", modifiers=(), source_order=20)`

## 用語（ドメイン語彙）
- TERM-001:
  - `ClassMember`:
    - class body に表示可能な field または method の shared DTO
- TERM-002:
  - `relation_type`:
    - `inherits`, `association`, `uses` の 3 語彙
- TERM-003:
  - no convenience field:
    - render 用の preformatted line を shared DTO に持ち込まない方針

## 未確定事項
- なし:
  - relation contract は shared import surface へ寄せる方針で固定する。
