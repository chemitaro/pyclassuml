---
種別: 要件定義書（Issue）
ID: "iss-00025"
タイトル: "Parse Class Members"
関連GitHub: ["#25"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
親: ["epic-00023", "init-00001"]
---

# iss-00025 Parse Class Members — 要件定義（WHAT / WHY）

## 目的
- class body から field / method / base / typed annotation evidence を AST-only で抽出し、issue 26 と issue 27 が再解析なしで使える `ParsedModule` handoff を作る。
- Pydantic `BaseModel` field、quoted forward ref、`__init__` の `self.x` assignment を member-aware parse の MVP に含める。

## 背景・現状
- 現状の挙動:
  - current parse は `ParsedModule.classes` と `ClassReference` の一部しか返さず、member body 自体は保持しない。
  - class-level annotation や quoted forward ref は framework support 向けの generic `ClassReference` にしか残らず、render 用 member collection がない。
- 現状の課題:
  - render は class body を組み立てる材料を持たず、`RenderReadyModel.members=()` のままになる。
  - analyze は method parameter / return annotation と field annotation を区別できないため、typed relation classification ができない。
- 再現手順:
  1. `src/pyclassuml/parse/indexer.py` を確認する。
  2. `ParsedModule` に class member collection がないことを確認する。
- 情報源:
  - `src/pyclassuml/parse/indexer.py`
  - `src/pyclassuml/model/contracts.py`
  - `tests/parse/test_module_parse_and_index.py`
  - `tests/frameworks/test_pydantic.py`

## 対象ユーザー / 利用シナリオ（必要時）
- 主な利用者:
  - parse / analyze / render 実装者
- 代表シナリオ:
  - dataclass や Pydantic schema から field / method を diagram body に出したい。
  - method parameter / return type、base class、Pydantic forward ref を typed relation の材料として downstream へ渡したい。

## スコープ
- MUST:
  - class-level `AnnAssign` / `Assign` から field member を抽出する。
  - Pydantic `BaseModel` field と quoted forward ref を generic parse evidence として抽出する。
  - `FunctionDef` / `AsyncFunctionDef` から method member を抽出する。
  - `staticmethod`, `classmethod`, `property`, `async` modifier を member metadata に反映する。
  - `__init__` の direct `self.x = value` assignment から instance field member を抽出する。
  - base class reference、field annotation reference、method parameter / return annotation reference を downstream で区別可能な形で保持する。
  - member と reference の順序を source-order deterministic にする。
- MUST NOT:
  - runtime import や annotation evaluation を行わない。
  - 一般メソッド body の汎用 data-flow 解析を行わない。
  - Pydantic validation や dataclass runtime metadata に依存しない。
- OUT OF SCOPE:
  - composition 判定。
  - local variable や nested function 内の一時的 symbol の解析。
  - method body 全体の call graph 構築。

## 境界
- Always:
  - parse owner は syntactic evidence の抽出に限定し、relation type の決定は行わない。
  - `__init__` では direct `self.<name>` assignment のみを見る。
  - class-local source order を `ClassMember.source_order` に固定する。
- Ask:
  - property を field として扱いたい場合。
  - `__init__` 以外の method body assignment まで広げたい場合。
- Never:
  - unsupported annotation を runtime で解決しない。
  - source file を書き換えない。

## 非交渉制約
- AST-only / import 非実行 / non-invasive / deterministic を維持する。
- syntax error module の failure policy は existing parse seam と一致させる。

## 前提
- iss-00024 で `ClassMember` 系 DTO と `ParsedModule.members` contract が固定されている。
- existing `ClassReference` / parse diagnostics channel を使って warning を handoff する。

## 受け入れ条件
- AC-001:
  - Actor:
    - CLI 利用者
  - Given:
    - dataclass または plain class に class-level field / method がある。
  - When:
    - parse を行う。
  - Then:
    - `ParsedModule.members` に field / method member が source order で入る。
  - 観測点:
    - `tests/parse/test_module_parse_and_index.py`
- AC-002:
  - Actor:
    - analyze 実装者
  - Given:
    - method parameter / return annotation、field annotation、base class がある。
  - When:
    - parse を行う。
  - Then:
    - downstream が field / method / base evidence を区別できる `ClassReference` または同等 metadata が handoff される。
  - 観測点:
    - parse fixture tests
- AC-003:
  - Actor:
    - render 実装者
  - Given:
    - `__init__` で `self.customer = customer` のような direct assignment がある。
  - When:
    - parse を行う。
  - Then:
    - instance field member が抽出され、parameter annotation があれば type text に反映される。
  - 観測点:
    - parse fixture tests
- AC-004:
  - Actor:
    - CLI 利用者
  - Given:
    - Pydantic `BaseModel` field と quoted forward ref がある。
  - When:
    - parse を行う。
  - Then:
    - field member と downstream typed relation の両方に使える evidence が handoff される。
  - 観測点:
    - Pydantic parse tests

## 例外・エッジケース
- EC-001:
  - 条件:
    - unsupported annotation syntax で stable text 化できない。
  - 期待:
    - member は保持し、該当 annotation text は `None` 相当に degrade し、必要なら warning を追加する。
  - 観測点:
    - parse degraded fixture
- EC-002:
  - 条件:
    - `Assign` で annotation のない field がある。
  - 期待:
    - field member は保持し、type text は持たない。
  - 観測点:
    - parse field fixture
- EC-003:
  - 条件:
    - syntax error module がある。
  - 期待:
    - existing parse diagnostic policy を維持し、その module では member extraction を行わない。
  - 観測点:
    - existing syntax error parse tests
- EC-004:
  - 条件:
    - nested class / nested function が method body 内にある。
  - 期待:
    - method body 汎用解析は行わず、`__init__` direct `self.x` assignment だけを対象にする。
  - 観測点:
    - nested body fixture

## 入力→出力例（必要時）
- EX-001:
  - Input:
    - `class Order: customer: CustomerAccount`
  - Output:
    - field member `customer`
    - field annotation reference `CustomerAccount`
- EX-002:
  - Input:
    - `class Service: def submit(self, order: Order) -> Receipt: pass`
  - Output:
    - method member `submit(order: Order): Receipt`
    - parameter reference `Order`
    - return reference `Receipt`

## 用語（ドメイン語彙）
- TERM-001:
  - direct `self.x` assignment:
    - `__init__` body の top-level statement / if / loop / try 配下にある `self.<name> = value` で、nested function / class を跨がない代入
- TERM-002:
  - unsupported annotation:
    - stable text / reference extraction ができないが module 全体 failure にはしない annotation

## 未確定事項
- なし:
  - property / classmethod / staticmethod / async は modifier として保持する方針で固定する。
