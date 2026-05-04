---
種別: 要件定義書（Issue）
ID: "iss-00026"
タイトル: "Analyze Typed Relations"
関連GitHub: ["#26"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
親: ["epic-00023", "init-00001"]
---

# iss-00026 Analyze Typed Relations — 要件定義（WHAT / WHY）

## 目的
- parsed member / base / annotation evidence から typed relation を分類し、`iss-00014` の `uses` fixed MVP を `inherits`, `association`, `uses` へ拡張する。
- Pydantic `BaseModel` field と quoted forward ref を `association` として扱い、現実的な class diagram に必要な relation semantics を analyze owner で固定する。

## 背景・現状
- 現状の挙動:
  - `select_classes_and_relations` は reachable module edge を一意 endpoint の `uses` relation にしか変換しない。
  - class base、field annotation、method parameter / return annotation は relation_type に反映されない。
- 現状の課題:
  - inheritance と field association が diagram に出ないため、domain model の構造が読み取れない。
  - Pydantic field forward ref は current framework support では `uses` relation へ寄っており、field association としての意味が失われる。
- 再現手順:
  1. `src/pyclassuml/analyze/selection.py` を確認する。
  2. relation_type が `uses` 固定で module import edge だけから作られていることを確認する。
- 情報源:
  - `src/pyclassuml/analyze/selection.py`
  - `src/pyclassuml/frameworks/pydantic.py`
  - `tests/analyze/test_selection.py`
  - `tests/frameworks/test_pydantic.py`
  - `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00003-core-analysis/issues/iss-00014-analyze-relationship-and-selection/{requirement,design}.md`

## 対象ユーザー / 利用シナリオ（必要時）
- 主な利用者:
  - CLI 利用者、analyze / render 実装者
- 代表シナリオ:
  - `Order` が `CustomerAccount` field を持つことを `association` として表示したい。
  - `InvoicePaymentDto(BaseModel)` や custom exception 継承を `inherits` として表示したい。
  - service method parameter / return を `uses` として表示したい。

## スコープ
- MUST:
  - typed evidence は traversal frontier を広げず、`iss-00014` 由来の selected set に既に含まれる internal class 同士だけを relation 化する。
  - `inherits`:
    - selected internal base class への継承 relation を作る。
  - `association`:
    - class field または Pydantic field が selected internal class を指す場合に relation を作る。
  - `uses`:
    - method parameter / return annotation、または existing module import fallback から relation を作る。
  - relation と selected class の ordering を deterministic にする。
  - unresolved / ambiguous / selection-outside warning を existing pattern に合わせて handoff する。
  - `iss-00014` の `uses` fixed contract を typed evidence の範囲で supersede する。
- MUST NOT:
  - composition を断定しない。
  - traversal frontier を広げない。
  - runtime import や framework runtime metadata に依存しない。
- OUT OF SCOPE:
  - composition / aggregation vocabulary
  - non-selected external class への relation 描画
  - render arrow / label formatting

## 境界
- Always:
  - relation_type の owner は `analyze`。
  - seed class full-display と dependency endpoint selection の基本契約は `iss-00014` を継承する。
  - Pydantic `BaseModel` field は generic member / base evidence から `association` を作る。
- Ask:
  - relation vocabulary を 3 種より増やす場合。
  - framework issue 側へ owner を戻す場合。
- Never:
  - ambiguous / unresolved reference を relation として決め打ちしない。
  - `frameworks` が analyze owner の relation_type を上書きできる設計にしない。

## 非交渉制約
- deterministic ordering、warning degraded output、AST-only を維持する。
- `current_state=head` や diff seed semantics を変更しない。

## 前提
- iss-00024 で relation vocabulary が fixed されている。
- iss-00025 で member / base / method typed evidence が `ParsedModule` に入っている。

## 受け入れ条件
- AC-001:
  - Actor:
    - CLI 利用者
  - Given:
    - selected internal base class を持つ class がある。
  - When:
    - relation classification を行う。
  - Then:
    - child -> parent の `inherits` relation が handoff される。
  - 観測点:
    - analyze fixture tests
- AC-002:
  - Actor:
    - CLI 利用者
  - Given:
    - selected internal class を型に持つ field または Pydantic field がある。
  - When:
    - relation classification を行う。
  - Then:
    - `association` relation が handoff される。
  - 観測点:
    - field association tests、Pydantic tests
- AC-003:
  - Actor:
    - CLI 利用者
  - Given:
    - method parameter / return annotation、または relation を支える module import edge がある。
  - When:
    - relation classification を行う。
  - Then:
    - `uses` relation が handoff される。
  - 観測点:
    - method use tests、module import fallback tests
- AC-004:
  - Actor:
    - CLI 利用者
  - Given:
    - ambiguous / unresolved / selection-outside reference がある。
  - When:
    - relation classification を行う。
  - Then:
    - warning diagnostics を返し、確証のない relation は handoff しない。
  - 観測点:
    - warning fixture tests

## 例外・エッジケース
- EC-001:
  - 条件:
    - target name が internal class に解決できない。
  - 期待:
    - warning diagnostic を返し、relation を追加しない。
  - 観測点:
    - unresolved fixture
- EC-002:
  - 条件:
    - short name が複数 internal class に当たる。
  - 期待:
    - warning diagnostic を返し、relation を追加しない。
  - 観測点:
    - ambiguous fixture
- EC-003:
  - 条件:
    - internal class へ解決できるが selected set の外側である。
  - 期待:
    - warning diagnostic を返し、relation を追加しない。
  - 観測点:
    - selection-outside fixture
- EC-004:
  - 条件:
    - same source / target に複数 evidence がある。
  - 期待:
    - same relation_type なら dedupe する。
    - same endpoint に複数 relation_type がある場合は `inherits > association > uses` の優先順位で 1 relation に正規化する。
    - module import fallback の `uses` は semantic evidence がないときだけ残す。
  - 観測点:
    - dedupe / priority fixture

## 入力→出力例（必要時）
- EX-001:
  - Input:
    - `class Order(BaseAggregate): pass`
  - Output:
    - `Order --|> BaseAggregate` 用の `inherits` relation
- EX-002:
  - Input:
    - `class Order: customer: CustomerAccount`
  - Output:
    - `Order --> CustomerAccount` 用の `association` relation
- EX-003:
  - Input:
    - `def submit(self, order: Order) -> Receipt`
  - Output:
    - `submit` 由来の `uses` relation

## 用語（ドメイン語彙）
- TERM-001:
  - module import fallback:
    - typed evidence がなくても reachable module edge から作る `uses` relation
- TERM-002:
  - selection-outside:
    - internal class へ解決できるが、`iss-00014` 由来の selected class set に含まれていない状態。この issue では typed evidence によって selected set を拡張せず、warning を返して relation を追加しない。
- TERM-003:
  - same-endpoint priority:
    - 同じ `(source_class_id, target_class_id)` に複数 evidence がある場合の正規化規則。優先順位は `inherits > association > uses` とする。

## 未確定事項
- なし:
  - composition はこの epic の対象外で固定する。
