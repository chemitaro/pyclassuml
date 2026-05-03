---
種別: 要件定義書（Issue）
ID: "iss-00017"
タイトル: "Frameworks Pydantic Enrich"
関連GitHub: ["#17"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
親: ["epic-00004", "init-00001"]
---

# iss-00017 Frameworks Pydantic Enrich — 要件定義（WHAT / WHY）

## 目的
- `analyze.relationship-and-selection` が拾いにくい Pydantic forward reference を best-effort で内部 class relation へ補強し、Pydantic model を含む実務的な図の下限を作る。
- Pydantic 固有の annotation 解釈を `frameworks` owner に閉じ、core-analysis と render/report の責務境界を守る。

## スコープ
- MUST:
  - `ParsedModule[]` と relation inventory を入力に、Pydantic forward reference を内部 class relation に補強する。
  - 一意解決できた forward reference だけを relation hint として downstream に渡す。
  - 解決不能・曖昧解決は `recoverability=degraded_output` を持つ warning diagnostics として保持する。
- MUST NOT:
  - traversal frontier を広げない。
  - artifact write、summary、exit code を決めない。
  - SQLAlchemy support と混在させない。
- OUT OF SCOPE:
  - Pydantic runtime import や model validation 実行。
  - serializer / validator の意味論補強。
  - class selection の再定義。

## 境界
- Always:
  - seam owner は `frameworks`。
  - upstream は `parse.module-parse-and-index` と `analyze.relationship-and-selection`。
  - downstream shared handoff 先は `RenderReadyModel.relations` であり、中間成果は seam-local hint として扱う。
- Ask:
  - forward reference の範囲を prototype baseline より広げる場合。
  - 曖昧解決に対して deterministic tie-break を導入したい場合。
- Never:
  - import 実行で Pydantic metadata を取得しない。
  - 解決不能な forward reference を推測で relation 化しない。
  - changed class 数や summary counter をこの issue で決めない。

## 制約
- AST-only / read-only / deterministic を守る。
- 補強対象は内部 class relation に限定し、外部 symbol は warning のみで継続する。
- warning diagnostics は `report` が summary に載せられる粒度で downstream へ渡す。

## 受け入れ条件
- AC-001:
  - Actor:
    - CLI 利用者
  - Given:
    - quoted forward reference を持つ Pydantic model fixture がある。
  - When:
    - `frameworks.pydantic-enrich` を適用する。
  - Then:
    - 内部 class と一意に対応づけられる限り、relation hint が追加される。
  - 観測点:
    - `fx-framework-pydantic-forward-ref` scenario。
- AC-002:
  - Actor:
    - CLI 利用者
  - Given:
    - Pydantic forward reference が relation inventory に直接は現れていない fixture がある。
  - When:
    - forward reference を補強する。
  - Then:
    - best-effort で補強された relation が downstream render へ届く。
  - 観測点:
    - Pydantic hint handoff review。

## 例外・エッジケース
- EC-001:
  - 条件:
    - forward reference が複数 class に一致して曖昧である。
  - 期待:
    - warning を残し、relation は追加しない。
  - 観測点:
    - ambiguity diagnostic review。
- EC-002:
  - 条件:
    - forward reference が内部 class として解決できない。
  - 期待:
    - warning を残し、既存 relation inventory を壊さず継続する。
  - 観測点:
    - unresolved warning review。
- EC-003:
  - 条件:
    - forward reference で補強できた relation があっても、その class が selection contract 外である。
  - 期待:
    - class selection owner は `analyze.relationship-and-selection` のままとし、この issue は relation hint だけを追加する。
  - 観測点:
    - selection boundary review。

## 未確定事項
- なし:
  - Pydantic best-effort support の baseline row は initiative canonical docs で確定済みである。
