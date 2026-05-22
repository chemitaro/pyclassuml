---
種別: 要件定義書（Issue）
ID: "iss-00040"
タイトル: "Render Direct Class Dependency"
関連GitHub: ["#40"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-22"
親: ["epic-00039", "init-00038"]
---

# iss-00040 Render Direct Class Dependency — 要件定義（WHAT / WHY）

## 目的
- Python class diagram 生成において、class body 内の実行文から一意に解決できる内部 class の直接利用を UML dependency として表示する。
- `generate` / `diff` の両方で、`B()` や `B.factory()` などの直接利用から `A ..> B` を出力できるようにする。
- 既存の association / composition / aggregation / uses の意味を混同せず、runtime direct use を新しい `dependency` relation として扱う。

## 背景・現状
- 現状の挙動:
  - 通常 method body の `B()` / `return B()` / `B.factory()` / `module.B()` などは relation evidence として抽出されない。
  - 一部の two-file ケースでは module import fallback により `uses` relation `..>` が出るが、これは direct-use 解決ではなく、source / target module がどちらも 1 class の場合に限られる。
  - target module に複数 class がある明示 import では `ambiguous_relation_endpoint` になり、relation が出ない。
  - typed field は既存どおり composition `*--`、method parameter / return annotation は `uses` `..>` として扱われる。
- 現状の課題:
  - Class implementation が別 class を直接使用しているにもかかわらず、class diagram 上に依存関係が出ない。
  - `generate` と `diff` の共通 parse/analyze 経路で同じ欠落が起きる。
  - import fallback に依存した表示は、実プロジェクトで自然に発生する multi-class module では機能しにくい。
  - Runtime direct use を既存 `association` に寄せると、一般 UML の association が表す構造的 link と意味が混ざる。
- 再現手順:
  1. 同一ファイル内に `class B` と `class A` を定義し、`A.make()` で `return B()` を行う。
  2. `generate` を実行する。
  3. 同じ変更を一時 Git repository 上で作り、`diff --base HEAD` を実行する。
- 観測点:
  - CLI:
    - `generate` / `diff` の counters と diagnostics。
  - PlantUML:
    - `A ..> B` の dependency edge が出るか。
    - 既存 typed relation の矢印が変わっていないか。
- 情報源:
  - `discussions/20260522t084855z-research-direct-dependency-relation-investigation.md`
  - `discussions/20260522t090118z-interview-direct-dependency-requirement-interview.md`
  - OMG UML 2.5.1
  - PlantUML class diagram relation syntax

## 対象ユーザー / 利用シナリオ（必要時）
- 主な利用者:
  - Python codebase の class dependency を静的解析で把握したい開発者。
  - `generate` で現在構造を確認する利用者。
  - `diff` で変更により増減した class dependency を確認する利用者。
- 代表シナリオ:
  - ある use case / service class が別 domain class や helper class を直接生成・呼び出していることを class diagram で確認する。
  - PR / working tree の変更で、新しい class dependency が増えたことを diff diagram で確認する。

## スコープ
- 必須:
  - Class body 内の `FunctionDef` / `AsyncFunctionDef` の通常 statement body を対象に、内部 class symbol へ一意に解決できる direct use を抽出する。
  - 次の direct-use pattern を dependency evidence として扱う。
    - `B()`
    - `return B()`
    - `x = B()`
    - `B.factory()` / `B.static_method()` / class-level attribute access
    - `module.B()` / `module.B.factory()`
    - `isinstance(x, B)` / `issubclass(x, B)`
    - `typing.cast(B, x)`
    - method body local annotation `x: B`
    - `self.b = B()` のような instance attribute assignment
  - `from target import B` / `from target import B as AliasB` / relative import を、direct-use の target resolution 材料として扱う。
  - Target module に複数 class があっても、明示 import と使用地点から `target.B` に一意解決できる場合は `A ..> B` を出す。
  - `generate` と `diff` の両方で同じ relation classification と ambiguity policy を使う。
  - 内部 relation type として `dependency` を追加し、PlantUML 出力では `..>` に写像する。
  - 同一 endpoint に複数 dependency evidence がある場合は relation を重複出力しない。
- 禁止:
  - Runtime import、対象 code の import 実行、対象 source の書き換え。
  - 既存 `uses` の描画を変更して runtime direct use に流用すること。
  - Runtime direct use を既存 `association` として扱うこと。
  - 単なる `import B` / `from target import B` だけで class relation を出すこと。
  - 曖昧な名前解決で推測 edge を出すこと。
  - 単なる `self.b = B()` から composition / aggregation を推定すること。
- 対象外:
  - Python の完全な名前解決。
  - Data-flow tracking による `cls = B; cls()` の解決。
  - Factory return type inference。
  - `getattr`, `globals`, `locals`, `importlib`, `eval` などの dynamic reference。
  - wildcard import / re-export 経由の複雑解決。
  - nested function / lambda body 内の参照。
  - 外部 package class への relation 表示。
  - association / composition / aggregation 推定の再設計。

## 境界
- 常に行う:
  - AST ベース静的解析のみで direct-use evidence を抽出する。
  - source class から target class へ、client-to-supplier direction の dependency を作る。
  - 一意に解決できない参照は通常図に出さない。
  - 既存 typed relation semantics を維持する。
- 判断が必要:
  - Design phase で、`dependency` と既存 `uses` の priority / dedupe rule を具体化する。
  - Design phase で、`self.b = B()` を dependency evidence として扱いつつ、将来 association 推定を追加した場合の precedence を記録する。
- 行わない:
  - 解析対象 code を import 実行しない。
  - 図の見栄えだけを目的に UML semantics を崩さない。
  - 未解決の候補から最も近そうな class を推測しない。

## 非交渉制約
- 外部 CLI として動作し、解析対象 project の dependency や source code を変更しない。
- 読み取り専用、AST ベース、非 import 実行を維持する。
- 同一入力では同一 PlantUML を生成する決定性を維持する。
- `generate` と `diff` で relation semantics が分裂しない。
- 既存の typed field / method annotation / inheritance / framework hint の挙動を意図せず変えない。

## 前提
- 一般 UML では、method body で別 class を生成・呼び出し・型確認する関係は dependency であり、association は instance 間の構造的 link を表す。
- PlantUML では `-->` と `..>` のどちらも依存表現に使えるが、本 issue では UML 準拠の視覚意味を優先し、dependency は dashed arrow `..>` とする。
- `self.b = B()` は association 候補でもあるが、MVP では composition / aggregation を推定しない。
- `from target import B` は relation そのものではなく、`B()` などの使用地点を解決するための symbol information である。

## 受け入れ条件
- AC-001:
  - アクター: CLI 利用者
  - 前提: 同一ファイル内に `class A` と `class B` があり、`A.make()` が `return B()` を行う。
  - 操作: `generate` を実行する。
  - 期待結果: PlantUML に `A ..> B` 相当の dependency relation が 1 本出力される。
  - 観測点:
    - `extracted_relation_count` が 1 以上になる。
    - 出力 `.puml` に `..>` の relation line が含まれる。
- AC-002:
  - アクター: CLI 利用者
  - 前提: `from pkg.target import B` で import した `B` を、source class の method body で `B()` として使用する。`target.py` には `B` 以外の class も存在する。
  - 操作: `generate` を実行する。
  - 期待結果: 明示 import と使用地点から `B` に一意解決され、source class から `B` へ dependency `..>` が出力される。
  - 観測点:
    - `ambiguous_relation_endpoint` によって relation が欠落しない。
    - target module 内の unrelated class へ relation が出ない。
- AC-003:
  - アクター: CLI 利用者
  - 前提: `from pkg.target import B as TargetB` で alias import した `TargetB` を、source class の method body で `TargetB()` として使用する。
  - 操作: `generate` を実行する。
  - 期待結果: source class から original class `B` へ dependency `..>` が出力される。
  - 観測点:
    - alias 名ではなく canonical class identity で relation が作られる。
- AC-004:
  - アクター: CLI 利用者
  - 前提: `import pkg.target as target` で module alias import し、source class の method body で `target.B()` または `target.B.factory()` を使用する。
  - 操作: `generate` を実行する。
  - 期待結果: source class から `B` へ dependency `..>` が出力される。
  - 観測点:
    - module-qualified access が target class に一意解決される。
- AC-005:
  - アクター: CLI 利用者
  - 前提: source class の method body で `isinstance(x, B)` / `issubclass(x, B)` / `typing.cast(B, x)` / local annotation `x: B` のいずれかがあり、`B` が内部 class に一意解決できる。
  - 操作: `generate` を実行する。
  - 期待結果: source class から `B` へ dependency `..>` が出力される。
  - 観測点:
    - runtime/specification evidence kind は内部的に区別できるが、PlantUML relation は dependency として出る。
- AC-006:
  - アクター: CLI 利用者
  - 前提: `self.b = B()` が source class の method body に存在し、`B` が内部 class に一意解決できる。
  - 操作: `generate` を実行する。
  - 期待結果: source class から `B` へ dependency `..>` が出力される。composition `*--` や aggregation `o--` はこの evidence だけでは出力されない。
  - 観測点:
    - 同一 endpoint に dependency と association/composition が重複出力されない。
- AC-007:
  - アクター: CLI 利用者
  - 前提: AC-001 と同等の direct-use 変更が working tree にあり、base revision にはその relation が存在しない。
  - 操作: `diff --base <base>` を実行する。
  - 期待結果: `generate` と同じ classification により、追加 dependency relation として `A ..> B` が出力される。
  - 観測点:
    - relation kind が `dependency` として diff identity に含まれる。
    - changed / added class decoration と relation 出力が両立する。
- AC-008:
  - アクター: CLI 利用者
  - 前提: 既存 typed field `b: B` と method parameter / return annotation `def f(self, b: B) -> B` を含む。
  - 操作: `generate` を実行する。
  - 期待結果: typed field は既存どおり composition `*--`、method parameter / return annotation は既存どおり `uses` `..>` として扱われ、今回の `dependency` 追加で既存挙動が壊れない。
  - 観測点:
    - 既存 selection / render tests が通る。

## 例外・エッジケース
- EC-001:
  - 条件: 参照名が複数 class に解決可能、または shadowing により class reference と断定できない。
  - 期待: 通常図には relation を出さず、diagnostics / warning に残す。
  - 観測点: 推測による false-positive edge が出ない。
- EC-002:
  - 条件: 単なる import 文のみが存在し、method body / annotation / field などの実使用がない。
  - 期待: class relation を出さない。
  - 観測点: import-only dependency が relation count を増やさない。
- EC-003:
  - 条件: `getattr(module, "B")`, `globals()["B"]`, `importlib.import_module(...)`, `eval(...)` など dynamic reference が存在する。
  - 期待: relation を出さない。
  - 観測点: dynamic reference を静的に推測しない。
- EC-004:
  - 条件: nested function / lambda body 内に `B()` がある。
  - 期待: outer class の direct dependency としては扱わない。
  - 観測点: nested scope の参照が outer class relation として漏れない。
- EC-005:
  - 条件: 同一 endpoint に composition / aggregation / association と dependency evidence が同時に存在する。
  - 期待: design で定義した priority に従い、意味の強い構造 relation を優先し、重複 edge を出さない。
  - 観測点: PlantUML に同じ endpoint の重複 relation が出ない。

## 入力→出力例（必要時）
- EX-001:
  - 入力:
    ```python
    class B:
        pass

    class A:
        def make(self):
            return B()
    ```
  - 出力:
    ```plantuml
    class "A" as c001 {
      + make()
    }
    class "B" as c002
    c001 ..> c002
    ```
- EX-002:
  - 入力:
    ```python
    from pkg.target import B

    class A:
        def make(self):
            return B()
    ```
  - 出力:
    ```plantuml
    c001 ..> c002
    ```
- EX-003:
  - 入力:
    ```python
    from pkg.target import B

    class A:
        def __init__(self):
            self.b = B()
    ```
  - 出力:
    ```plantuml
    c001 ..> c002
    ```
    - この evidence だけでは `*--` / `o--` を出さない。

## 用語（ドメイン語彙）
- TERM-001:
  - `dependency`
    - UML における client が supplier を使用・参照・生成・呼び出し・型仕様として必要とする関係。PlantUML では本 issue において `..>` として出力する。
- TERM-002:
  - `association`
    - Instance 間の構造的 link を表す関係。Runtime direct use だけでは association としない。
- TERM-003:
  - `direct use`
    - Class body 内の実行文または局所型仕様に現れる、内部 class symbol への明示的な参照。
- TERM-004:
  - `client`
    - dependency の source class。例: `A` が `B()` を呼ぶ場合の `A`。
- TERM-005:
  - `supplier`
    - dependency の target class。例: `A` が `B()` を呼ぶ場合の `B`。

## 未確定事項
- なし。

## 設計時確認事項
- DC-001:
  - 論点: `dependency` と既存 `uses` の内部 model 上の整理。
  - 要件上の判断:
    - `uses` は既存 annotation-specific relation として維持し、runtime/specification direct use は新 `dependency` とする。
  - design で具体化すること:
    - relation priority、dedupe rule、render mapping、既存 tests との互換性。
- DC-002:
  - 論点: `typing.cast(B, x)` や local annotation `x: B` の evidence kind。
  - 要件上の判断:
    - dependency として出力する。ただし runtime use ではなく type/specification dependency として evidence kind を分ける。
  - design で具体化すること:
    - parser の expression / annotation walk 範囲、false-positive 回避、diagnostics。
