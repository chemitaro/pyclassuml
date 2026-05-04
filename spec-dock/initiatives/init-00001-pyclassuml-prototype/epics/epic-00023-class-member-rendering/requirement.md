---
種別: 要件定義書（Epic）
ID: "epic-00023"
タイトル: "Class Member Rendering"
関連GitHub: ["#23"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
親: ["init-00001"]
---

# epic-00023 Class Member Rendering — 要件定義（WHAT / WHY）

## 目的（Initiative との紐づき）
- initiative goal / metric:
  - `pyclassuml` の UML 出力を、class 一覧 + `uses` relation だけの prototype から、現実的なドメインオブジェクトを読める class diagram へ拡張する。
  - `build/manual-tests/pyclassuml-manual-env/retail_domain` のような複雑な fixture で、class body と typed relation が CLI 出力として観測できる状態を作る。
- この epic が提供する能力:
  - PlantUML class body に fields / methods を表示する。
  - relation type を少なくとも `inherits`, `association`, `uses` に分類する。
  - Pydantic `BaseModel` field と quoted forward ref を、field member と typed relation の両方で表現する。
  - 既存の AST-only / non-invasive / deterministic な骨格を崩さずに、member-aware な parse / analyze / render / E2E 契約へ更新する。

## ユースケース
- happy path:
  - 利用者が `generate` で domain model や Pydantic schema を入力したとき、各 class の field / method と `inherits` / `association` / `uses` を含む `.puml` を得られる。
  - 利用者が `diff` を使ったとき、変更起点の diagram に class body と typed relation が同じ語彙で現れ、ドメイン変更の影響範囲を読み取れる。
- exception / operation scenario:
  - unresolved / ambiguous / selection-outside の typed reference は warning として残し、diagram 生成自体は degraded output で継続できる。
  - syntax error や unsupported annotation があっても、既存の parse failure policy を維持しつつ、残りの selected class は deterministic に描画できる。

## Epic requirements
- E-RQ-001:
  - shared contract を member-aware に拡張し、`ParsedModule` と `RenderReadyModel` が意味のある member collection を authoritative に持てるようにする。
- E-RQ-002:
  - class body から field / method / base / typed annotation evidence を AST-only で抽出できるようにする。
- E-RQ-003:
  - relation classification の authoritative owner を `analyze` に置き、`inherits`, `association`, `uses` の語彙と warning pattern を固定する。
- E-RQ-004:
  - `render` が class body と typed relation arrow mapping を deterministic に出力できるようにする。
- E-RQ-005:
  - `iss-00014` の `relation_type="uses"` 固定と、`iss-00018` の `RenderReadyModel.members=()` authoritative 契約を、この epic の下位 issue で supersede / extend する。
- E-RQ-006:
  - final E2E では `build/manual-tests/pyclassuml-manual-env/retail_domain` を含む fixture で、Pydantic `BaseModel`、dataclass、Protocol、exception、nested / ambiguous / unresolved refs を観測できる。

## Epic acceptance criteria
- E-AC-001:
  - Given:
    - dataclass / Pydantic `BaseModel` / Protocol / exception を含む selected class 群がある。
  - When:
    - member-aware parse / analyze / render を通して `.puml` を生成する。
  - Then:
    - class body に fields / methods が表示され、typed relation が `inherits`, `association`, `uses` のいずれかとして現れる。
  - 観測点:
    - render snapshot、CLI integration test、manual fixture output。
- E-AC-002:
  - Given:
    - Pydantic `BaseModel` field と quoted forward ref を含む schema fixture がある。
  - When:
    - `.puml` を生成する。
  - Then:
    - field member と corresponding typed relation の両方が観測できる。
  - 観測点:
    - Pydantic fixture test、manual `retail_domain/api/schemas.py` output。
- E-AC-003:
  - Given:
    - ambiguous / unresolved / selection-outside の typed reference がある。
  - When:
    - relation classification と render を行う。
  - Then:
    - warning diagnostics が summary / failure handoff に残り、確証のない relation は diagram に追加しない。
  - 観測点:
    - analyze / render tests、CLI stderr / summary、manual fixture warnings。
- E-AC-004:
  - Given:
    - 同一 source tree、同一 CLI options、同一 Git baseline がある。
  - When:
    - 2 回 `.puml` を生成する。
  - Then:
    - class / member / relation / warning の順序が一致し、出力は決定的である。
  - 観測点:
    - snapshot test、manual repeated run diff。

## スコープ
- MUST:
  - `ParsedModule`, relation DTO, `RenderReadyModel`, render serializer, CLI integration test を member-aware / typed-relation-aware に拡張する。
  - `inherits`, `association`, `uses` の arrow mapping と member line format を固定する。
  - `retail_domain` manual environment を最終 acceptance に使う。
- MUST NOT:
  - AST-only / import 非実行 / read-only / deterministic の前提を壊さない。
  - 対象コードや対象 repo を書き換えない。
  - composition を Python AST だけで断定しない。
- OUT OF SCOPE:
  - composition / aggregation の追加語彙。
  - runtime import や Pydantic validation 実行による型解決。
  - rich / colorized diagram、layout 最適化、report ownership の変更。

## 境界
- Always:
  - member extraction の owner は `parse`。
  - typed relation classification の owner は `analyze`。
  - PlantUML class body / arrow mapping の owner は `render`。
  - artifact write / summary / exit policy の owner は `report` と `cli` のまま据え置く。
- Ask:
  - `relation_type` を 3 語彙より増やす場合。
  - magic method の表示方針や property 表示方針を大きく変える場合。
  - framework issue (`iss-00016` / `iss-00017`) の owner 境界を変更する場合。
- Never:
  - member text や relation label を `report` / `app` で再構成しない。
  - parse / analyze / render の責務を CLI へ逆流させない。
  - uncertain reference を relation として決め打ちしない。

## 非機能要件
- performance:
  - member extraction と typed relation classificationは既存 parse / analyze の線形走査に収め、target expansion を増やさない。
- reliability / consistency:
  - source order、relation sort、warning sort、PlantUML serialization は deterministic である。
- security:
  - import 実行禁止、対象コード書き換え禁止、外部 API 依存なしを維持する。
- operations:
  - manual environment は Git 管理外の受け入れ確認環境として使い、tracked tests には最小再現だけを残す。

## 依存 / 影響範囲
- impacted components:
  - `src/pyclassuml/model`
  - `src/pyclassuml/parse`
  - `src/pyclassuml/analyze`
  - `src/pyclassuml/frameworks`
  - `src/pyclassuml/render`
  - `tests/parse`
  - `tests/analyze`
  - `tests/frameworks`
  - `tests/render`
  - `tests/app`
- external dependency:
  - なし。対象 repo / manual fixture を read-only input として使う。
- compatibility:
  - `iss-00014` の core relation contract と `iss-00018` の render contractを拡張するため、既存 tests / fixtures / snapshot は更新前提とする。
  - existing `generate` / `diff` command surface は維持し、observable change は diagram content の richer output に限定する。

## 未確定事項
- なし:
  - relation vocabulary は `inherits`, `association`, `uses` でこの epic の MVP を固定する。
  - composition / aggregation は future extension として切り離す。
