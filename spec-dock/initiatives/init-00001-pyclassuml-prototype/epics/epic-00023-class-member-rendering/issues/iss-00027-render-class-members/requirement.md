---
種別: 要件定義書（Issue）
ID: "iss-00027"
タイトル: "Render Class Members"
関連GitHub: ["#27"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
親: ["epic-00023", "init-00001"]
---

# iss-00027 Render Class Members — 要件定義（WHAT / WHY）

## 目的
- typed relation と structured member collection を、deterministic な PlantUML class body と typed arrow へ変換する。
- `iss-00018` の memberless render contract を拡張し、field / method / inherits / association / uses が読める `.puml` を出力する。

## 背景・現状
- 現状の挙動:
  - current render は package / class / relation line だけを出力し、class body を持たない。
  - relation line は `-->` + raw relation_type label で描かれ、semantic arrow mapping がない。
- 現状の課題:
  - class structure が見えず、domain object の責務や field relation が読み取れない。
  - `inherits`, `association`, `uses` の違いが矢印形で表現されない。
- 再現手順:
  1. `src/pyclassuml/render/document.py` を確認する。
  2. `RenderReadyModel.members=()` と `--> : relation_type` 出力を確認する。
- 情報源:
  - `src/pyclassuml/render/document.py`
  - `tests/render/test_document.py`
  - `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00004-framework-render-report/issues/iss-00018-render-uml-document/{requirement,design}.md`

## 対象ユーザー / 利用シナリオ（必要時）
- 主な利用者:
  - CLI 利用者、render 実装者
- 代表シナリオ:
  - dataclass / Pydantic schema / Protocol / exception を含む diagram で、class body を読みたい。
  - field relation と inheritance を矢印の見た目で判別したい。

## スコープ
- MUST:
  - field line を `+ name: Type` 形式で描画する。
  - method line を `+ method(arg: Type): Return` 形式で描画する。
  - visibility を `public=+`, `protected=#`, `private=-` に写像する。
  - `staticmethod`, `classmethod`, `property`, `async` modifier を visibility の直後に deterministic に描画する。
  - `inherits -> --|>`, `association -> -->`, `uses -> ..>` の arrow mapping を固定する。
  - selected class だけの member を class body に出し、ordering / escaping を deterministic にする。
  - `iss-00018` の `RenderReadyModel.members=()` authoritative 契約を supersede する。
- MUST NOT:
  - artifact write、summary、exit policy を持ち込まない。
  - relation endpoint 不整合を暗黙補完しない。
  - report / app ownership を侵食しない。
- OUT OF SCOPE:
  - layout tuning、skinparam customization、rich / colorized output。
  - relation label の人間向け文章化。
  - class decoration の追加語彙。

## 境界
- Always:
  - render owner は `ClassMember` を preformatted line へ変換する。
  - same input -> same `.puml` を維持する。
  - relation arrow direction は `source_class_id -> target_class_id` に統一する。
  - memberless class は既存の one-line syntax `class "Name" as alias` を維持する。
  - member を 1 件以上持つ class だけを brace block `class "Name" as alias { ... }` で描画する。
- Ask:
  - property を field-style 表示へ変えたい場合。
  - relation label を arrow に追加したい場合。
- Never:
  - render が class member を再解析しない。
  - relation_type を render で再分類しない。

## 非交渉制約
- deterministic output と existing render failure policy を維持する。
- import 非実行、対象コード非変更の全体要件を壊さない。

## 前提
- iss-00024 で `RenderReadyModel.members` の shape が固定済み。
- iss-00025, iss-00026 で selected classes / members / typed relations が handoff 済み。

## 受け入れ条件
- AC-001:
  - Actor:
    - CLI 利用者
  - Given:
    - selected class に field / method member がある。
  - When:
    - PlantUML text を render する。
  - Then:
    - class body に field / method line が deterministic に描画される。
  - 観測点:
    - `tests/render/test_document.py`
- AC-002:
  - Actor:
    - CLI 利用者
  - Given:
    - `inherits`, `association`, `uses` relation がある。
  - When:
    - PlantUML text を render する。
  - Then:
    - relation type ごとに fixed arrow mapping が使われ、raw label へ依存しない。
  - 観測点:
    - render arrow snapshot
- AC-003:
  - Actor:
    - CLI 利用者
  - Given:
    - class-only、field-only、method-only の input がある。
  - When:
    - render する。
  - Then:
    - memberless class は one-line class syntax のまま、field-only / method-only class は brace block として生成される。
  - 観測点:
    - render snapshot tests
- AC-004:
  - Actor:
    - CLI 利用者
  - Given:
    - selected class missing または relation endpoint missing がある。
  - When:
    - render する。
  - Then:
    - existing failure handoff policy を維持し、phantom class を描かない。
  - 観測点:
    - render failure tests

## 例外・エッジケース
- EC-001:
  - 条件:
    - field member に type text がない。
  - 期待:
    - `+ name` として描画し、余計な `:` を出さない。
  - 観測点:
    - render field fixture
- EC-002:
  - 条件:
    - method return annotation がない。
  - 期待:
    - `+ method(arg)` として描画し、戻り値部分を省略する。
    - parameter が 0 件なら `+ method()` として描画する。
    - parameter の annotation text がない場合は `+ method(arg)`、typed / untyped が混在する場合は DTO の parameter order どおり `+ method(raw, typed: Type)` として描画する。
  - 観測点:
    - render method fixture
- EC-003:
  - 条件:
    - class body が空で relation だけがある。
  - 期待:
    - class declaration は既存 one-line syntax のまま relation を描画し、空 brace block は出さない。
  - 観測点:
    - relation-only fixture
- EC-004:
  - 条件:
    - modifier が複数ある。
  - 期待:
    - visibility の後ろ、member signature の前に `{static}`, `{class}`, `{property}`, `{async}` の順で描画する。
    - duplicate modifier は 1 回に dedupe する。
    - 未対応 modifier は render 行に出さず、failure にはしない。
  - 観測点:
    - modifier ordering fixture
- EC-005:
  - 条件:
    - field / method / parameter / annotation text / return text に PlantUML-sensitive text が含まれる。
  - 期待:
    - 既存 `_escape_plantuml` と同じ escaping を member line segment に適用し、quote と backslash を escape する。
    - newline は literal line break として持ち込まず、space に正規化する。
  - 観測点:
    - member escaping fixture

## 入力→出力例（必要時）
- EX-001:
  - Input:
    - field member `customer: CustomerAccount`
  - Output:
    - `+ customer: CustomerAccount`
- EX-002:
  - Input:
    - method member `submit(order: Order) -> Receipt`
  - Output:
    - `+ submit(order: Order): Receipt`
- EX-003:
  - Input:
    - `relation_type="inherits"`
  - Output:
    - `source --|> target`
- EX-004:
  - Input:
    - static async method `build(raw, typed: Order) -> Receipt`
  - Output:
    - `+ {static} {async} build(raw, typed: Order): Receipt`
- EX-005:
  - Input:
    - memberless class `Order`
  - Output:
    - `class "Order" as c001`

## 用語（ドメイン語彙）
- TERM-001:
  - typed arrow mapping:
    - relation_type を PlantUML arrow に写像する固定規則
- TERM-002:
  - modifier prefix:
    - visibility symbol の直後、signature の直前に置く `{static}`, `{class}`, `{property}`, `{async}` の render 表現

## 未確定事項
- なし:
  - relation label は arrow shape へ集約し、raw relation_type text は表示しない。
