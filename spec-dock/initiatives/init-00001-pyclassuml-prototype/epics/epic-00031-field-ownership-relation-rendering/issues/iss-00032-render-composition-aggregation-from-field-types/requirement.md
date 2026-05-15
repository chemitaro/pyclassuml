---
種別: 要件定義書（Issue）
ID: "iss-00032"
タイトル: "Render Composition And Aggregation From Field Types"
関連GitHub: ["#32"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-05"
親: ["epic-00031", "init-00001"]
---

# iss-00032 Render Composition And Aggregation From Field Types — 要件定義（WHAT / WHY）

## 目的
- field annotation から読み取れる class-to-class relation を、通常 association ではなく composition / aggregation として PlantUML class diagram に出力する。
- 直接 field 型は composition、Optional / Union / collection に包まれた field 型は aggregation として分類し、クラス図上で所有関係の強弱を読み取れるようにする。

## 背景・現状
- 現状の挙動:
  - `field_annotation` / `init_field_annotation` 由来で selected internal class が解決できる場合、relation は `association` として扱われ、PlantUML では通常矢印で表現される。
  - そのため、`Order.customer: Customer` のような必須構成要素と、`Order.coupon: Coupon | None` や `Order.lines: list[OrderLine]` のような任意・集合的参照の違いが図から読み取りにくい。
- 現状の課題:
  - field が class の内部状態として保持する型であるにもかかわらず、method parameter / return 由来の依存関係との差が弱い。
  - Optional / Union / list などの現実的な Python type annotation を、UML の aggregation として表現できていない。
- 再現手順:
  1. `customer: Customer`、`coupon: Coupon | None`、`lines: list[OrderLine]` を持つ class を含む package に対して `pyclassuml generate` を実行する。
  2. 出力された `.puml` の relation arrow を確認する。
- 観測点:
  - `.puml`: composition は黒塗り diamond、aggregation は白抜き diamond を持つ PlantUML relation として出る。通常矢印頭は付けない。
  - summary: class / relation count は既存方針どおり出る。
  - diagnostics: 解決不能な外部型は warning として扱い、捏造 relation を出さない。
- 情報源:
  - ユーザー要望: field の型が直接指定されている場合は composite、Optional / Union / list 内包型は aggregate として表現したい。
  - `epic-00031` Field Ownership Relation Rendering。

## 対象ユーザー / 利用シナリオ
- 主な利用者:
  - Python プロダクトのドメインモデルや DTO / Pydantic model の構造を UML class diagram で把握したい開発者。
- 代表シナリオ:
  - 複雑な domain object の必須構成要素、任意関連、集合関連を class diagram から素早く読み分ける。

## スコープ
- MUST:
  - field annotation 由来で selected internal class に解決できる relation を、annotation shape に応じて `composition` または `aggregation` として分類する。
  - 直接型 `field: Target` は composition とする。
  - Optional / nullable union `field: Target | None`、`field: Optional[Target]`、`field: Union[Target, None]` は aggregation とする。
  - 複数候補 union `field: TargetA | TargetB`、`field: Union[TargetA, TargetB]` は、解決できる各 selected internal class への aggregation とする。
  - collection generic `list[Target]` / `set[Target]` / `tuple[Target, ...]` / `Sequence[Target]` / `Iterable[Target]` など、field が container の中で selected internal class を参照する場合は aggregation とする。
  - mapping generic `dict[str, Target]` / `Mapping[str, Target]` / `MutableMapping[str, Target]` など、field が mapping value として selected internal class を参照する場合は aggregation とする。
  - mapping key type は ownership target とみなさず、`dict[TargetKey, TargetValue]` では value 側の selected internal class だけを aggregation 候補にする。
  - `Annotated[Target, ...]` のように metadata wrapper がある場合、内側の Target 判定を維持する。
  - `Optional[list[Target]]`、`Annotated[list[Target], ...]`、`dict[str, list[Target]]` のような nested wrapper は、内側の item / value target を aggregation として扱う。
  - PlantUML render では composition を黒塗り diamond、aggregation を白抜き diamond として、diamond 側が field owner class になる向きで出力する。
  - composition / aggregation relation は通常矢印頭を持たない line として出力する。
  - 同一 source / target 間に field-origin ownership relation と method-origin uses relation が併存する場合、ownership relation を優先して diagram に出す。
  - 既存の inheritance `-up-|>`、Protocol realization `..up|>`、method-only uses `..>` の表現を維持する。
- MUST NOT:
  - 対象コードを import 実行しない。
  - 対象ソースコードを書き換えない。
  - method parameter annotation / method return annotation を composition / aggregation にしない。
  - 解決不能な外部型、built-in 型、selected 外 class に対して relation を捏造しない。
- OUT OF SCOPE:
  - multiplicity 表示、role label、field name label の追加。
  - runtime ownership や lifecycle の意味論推測。
  - SQLAlchemy `relationship()` の cascade / uselist など framework-specific ownership 判定。
  - Pydantic model config による ownership 推測。

## 境界
- Always:
  - AST-only、read-only、deterministic ordering を守る。
  - annotation の構文上の shape を根拠に分類し、runtime 値や import 実行で判断しない。
  - 直接型は stronger ownership として composition、nullable / choice / collection は weaker ownership として aggregation に分類する。
- Ask:
  - recursive wrapper extraction が ambiguity や探索爆発を起こす未知の typing construct に遭遇した場合。
  - field name label や multiplicity label も同時に出したい場合。
- Never:
  - duck typing や constructor body assignment の推測だけで composition / aggregation を作らない。

## 非交渉制約
- 外部 CLI として動作する。
- 解析対象 project の依存関係を増やさない。
- 対象 repository に対して read-only で動作する。
- 対象コードを import 実行しない。
- 同一入力では同一 `.puml` を出力する。

## 前提
- `iss-00030` により、通常継承は `-up-|>`、Protocol realization は `..up|>` として出力できる。
- 既存 parser / analyzer は field annotation 由来の typed relation evidence を持っている。
- Pydantic `BaseModel` 自体は外部 class として unresolved warning になりうるが、BaseModel subclass の field annotation に含まれる selected internal class は ownership 判定対象にできる。

## 受け入れ条件
- AC-001:
  - Actor: pyclassuml user
  - Given: `class Order: customer: Customer`
  - When: `pyclassuml generate` が `.puml` を生成する
  - Then: `Order` から `Customer` への relation は composition であり、PlantUML 上では `Order` 側に黒塗り diamond が出る。通常矢印頭は出ない。
  - 観測点: `.puml` に `*--` 相当の composition relation が含まれ、`*-->` は含まれない。
- AC-002:
  - Actor: pyclassuml user
  - Given: `class Order: coupon: Coupon | None`
  - When: `pyclassuml generate` が `.puml` を生成する
  - Then: `Order` から `Coupon` への relation は aggregation であり、PlantUML 上では `Order` 側に白抜き diamond が出る。通常矢印頭は出ない。
  - 観測点: `.puml` に `o--` 相当の aggregation relation が含まれ、`o-->` は含まれない。
- AC-003:
  - Actor: pyclassuml user
  - Given: `class Order: lines: list[OrderLine]`
  - When: `pyclassuml generate` が `.puml` を生成する
  - Then: `Order` から `OrderLine` への relation は aggregation として出る。
  - 観測点: `.puml` に `Order` owner side の矢印頭なし aggregation relation が含まれる。
- AC-004:
  - Actor: pyclassuml user
  - Given: `class Payment: source: Card | Invoice`
  - When: `pyclassuml generate` が `.puml` を生成する
  - Then: 解決できる `Card` と `Invoice` それぞれへの aggregation relation が出る。
  - 観測点: `.puml` に複数 target への矢印頭なし aggregation relation が含まれる。
- AC-005:
  - Actor: pyclassuml user
  - Given: `class Catalog: items_by_sku: dict[str, Item]` または `items_by_sku: Mapping[str, Item]`
  - When: `pyclassuml generate` が `.puml` を生成する
  - Then: `Catalog` から `Item` への relation は aggregation として出る。
  - 観測点: `.puml` に `Catalog` owner side の矢印頭なし aggregation relation が含まれる。
- AC-006:
  - Actor: pyclassuml user
  - Given: `class Catalog: items_by_key: dict[ItemKey, Item]`
  - When: `pyclassuml generate` が `.puml` を生成する
  - Then: mapping key type の `ItemKey` は aggregation target にならず、value type の `Item` だけが aggregation target になる。
  - 観測点: `.puml` に `Catalog` から `Item` への aggregation relation が含まれ、`Catalog` から `ItemKey` への ownership relation は含まれない。
- AC-007:
  - Actor: pyclassuml user
  - Given: method parameter / method return だけで参照される selected internal class
  - When: `pyclassuml generate` が `.puml` を生成する
  - Then: その relation は composition / aggregation ではなく既存の uses relation として出る。
  - 観測点: `.puml` の method-only relation は `..>` のまま。
- AC-008:
  - Actor: pyclassuml maintainer
  - Given: `iss-00030` の inheritance / Protocol realization fixtures
  - When: full test suite と manual generate を実行する
  - Then: `-up-|>` と `..up|>` の既存表現は regression しない。
  - 観測点: automated test と manual `.puml` inspection。

## 例外・エッジケース
- EC-001:
  - 条件: field annotation が外部型、built-in 型、または selected 外 class にしか解決できない。
  - 期待: relation は追加せず、既存 diagnostics 方針に従う。
  - 観測点: `.puml` に捏造 diamond relation が出ない。
- EC-002:
  - 条件: `field: Target | None` と `field: list[Target]` のように aggregation shape が複数ある。
  - 期待: relation は重複せず、deterministic に 1 本の aggregation として出る。
  - 観測点: `.puml` の relation 重複がない。
- EC-003:
  - 条件: 同じ source / target に直接 field と optional field が併存する。
  - 期待: より強い composition を優先する。
  - 観測点: `.puml` では composition が出て aggregation は重複しない。
- EC-004:
  - 条件: `field: list[UnknownTarget]` のように container 内 target が解決不能。
  - 期待: aggregation を捏造せず、warning-only success の範囲で継続する。
  - 観測点: diagnostics と `.puml`。
- EC-005:
  - 条件: `field: dict[UnknownKey, Target]` のように mapping key が解決不能で value は解決可能。
  - 期待: key 側は ownership 抽出対象外のため、key 由来の ownership relation も key 由来の unresolved warning も必須にしない。value 側の aggregation は保持する。
  - 観測点: `.puml` に value 側 aggregation が含まれ、key 側 ownership relation が含まれない。
- EC-006:
  - 条件: `field: Optional[list[Target]]`、`field: Annotated[list[Target], ...]`、`field: dict[str, list[Target]]` のように wrapper が nested している。
  - 期待: 内側の selected internal class は aggregation として扱う。
  - 観測点: `.puml` に owner side の矢印頭なし aggregation relation が含まれる。

## 入力→出力例
- EX-001:
  - Input:
    ```python
    class Customer:
        pass

    class Coupon:
        pass

    class OrderLine:
        pass

    class Order:
        customer: Customer
        coupon: Coupon | None
        lines: list[OrderLine]
        lines_by_sku: dict[str, OrderLine]
    ```
  - Output:
    ```plantuml
    Order *-- Customer
    Order o-- Coupon
    Order o-- OrderLine
    ```

## 用語
- TERM-001:
  - composition: UML の黒塗り diamond。ここでは direct field type による強い所有関係を表す。
- TERM-002:
  - aggregation: UML の白抜き diamond。ここでは Optional / Union / collection field type による弱い所有・参照集合関係を表す。
- TERM-003:
  - owner class: field を定義している source class。diamond は owner class 側に置く。

## 分析メモ
- AM-001:
  - `dict` / `Mapping` 対応は今回 scope に含める。
  - 理由:
    - 既存 parser は annotation 内の class-like target を AST-only で抽出できており、mapping value の判定も annotation shape classifier を追加すれば実装できる。
    - `list[T]` / `set[T]` / `tuple[T]` と同じく `Subscript` 形状を読む処理なので、value 側だけを対象にする制約を置けば技術的難易度は高くない。
    - 注意点は、`dict[Key, Value]` の key type を ownership target にしないこと。これは acceptance criteria と regression test で固定する。

## 未確定事項
- 該当なし。`dict` / `Mapping` は今回 scope に含める。
