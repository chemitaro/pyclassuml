---
種別: 要件定義書（Issue）
ID: "iss-00017"
タイトル: "Frameworks Pydantic Enrich"
関連GitHub: ["#17"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
親: ["epic-00004", "init-00001"]
---

# iss-00017 Frameworks Pydantic Enrich — 要件定義（WHAT / WHY）

## 目的
- `analyze.relationship-and-selection` が拾いにくい Pydantic forward reference を best-effort で内部 class relation へ補強し、Pydantic model を含む実務的な図の下限を作る。
- Pydantic 固有の annotation 解釈を `frameworks` owner に閉じ、core-analysis と render/report の責務境界を守る。
- `iss-00016` で追加した `ClassReference` evidence を再利用し、parse seam に framework-specific DTO を増やさない。

## スコープ
- MUST:
  - `ParsedModule[]`、`ModuleIndex`、`SelectedClasses`、`SelectedRelations` を入力に、quoted forward reference から選択済み内部 class relation を補強する。
  - direct quoted annotation `field: "T"` と generic quoted subscript annotation `field: list["T"]` / `field: Optional["T"]` / `field: Union["T", "U"]` を best-effort 対象にする。
  - AST-only の Pydantic eligibility として、source class が `BaseModel` または `pydantic.BaseModel` を直接継承している場合だけ Pydantic forward reference として扱う。
  - 一意解決できた forward reference だけを seam-local `PydanticEnrichmentHints.added_relations` として返す。
  - 解決不能・曖昧解決・selection 外は `recoverability=degraded_output` を持つ warning diagnostics として保持し、推測 relation は追加しない。
  - 現行 parse evidence が direct quoted annotation / quoted subscript / direct class base の evidence を保持していないため、parse/model seam に framework-neutral な quoted annotation evidence と direct class-base evidence を最小追加する。
- MUST NOT:
  - traversal frontier を広げない。
  - artifact write、summary、exit code を決めない。
  - SQLAlchemy support と混在させない。
  - parse seam に Pydantic 固有の relation 解釈を持ち込まない。
- OUT OF SCOPE:
  - Pydantic runtime import や model validation 実行。
  - serializer / validator の意味論補強。
  - class selection の再定義。
  - non-quoted annotation `field: T` の一般 Python typing 補強。

## 境界
- Always:
  - seam owner は `frameworks`。
  - upstream は `parse.module-parse-and-index` と `analyze.relationship-and-selection`。
  - この issue 自身の成果は seam-local hint として扱い、downstream shared handoff への合成は `render.uml-document` 側の責務にする。
  - parse/model 追加は AST から観測できる quoted annotation evidence と direct class-base evidence の保持に限定し、Pydantic relation や Pydantic eligibility の意味付けは `frameworks.pydantic-enrich` で行う。
  - direct class-base evidence は `ClassReference(reference_kind=class_base, reference_owner=base, target_name=<direct base name>)` として保持し、parse は `BaseModel` / `pydantic.BaseModel` を特別扱いしない。
- Ask:
  - forward reference の範囲を prototype baseline より広げる場合。
  - 曖昧解決に対して deterministic tie-break を導入したい場合。
- Never:
  - import 実行で Pydantic metadata を取得しない。
  - 解決不能な forward reference を推測で relation 化しない。
  - changed class 数や summary counter をこの issue で決めない。

## 制約
- AST-only / read-only / deterministic を守る。
- 補強は source と target の両方が `SelectedClasses` 内にある既知の内部 class relation に限定し、外部 dependency や未選択 frontier を勝手に追加しない。
- warning diagnostics は shared enum の範囲に従い、`origin_seam=frameworks`、`recoverability=degraded_output`、`failure_reason=None` とする。
- warning diagnostic code は stable snake_case とし、曖昧解決は `pydantic_forward_ref_ambiguous`、未解決は `pydantic_forward_ref_unresolved`、selection 外衝突は `pydantic_forward_ref_selection_outside` とする。
- 追加 relation hint は source / target / relation_type の triple で deterministic に重複排除する。

## 受け入れ条件
- AC-001:
  - Actor:
    - CLI 利用者
  - Given:
    - direct quoted forward reference `field: "T"` を持つ Pydantic model fixture がある。
  - When:
    - `frameworks.pydantic-enrich` を適用する。
  - Then:
    - `T` が選択済み内部 class として一意解決できる限り、`PydanticEnrichmentHints.added_relations` に source / target / evidence kind が deterministic に追加される。
  - 観測点:
    - Pydantic seam unit test。
- AC-002:
  - Actor:
    - CLI 利用者
  - Given:
    - quoted subscript forward reference `field: list["T"]` / `field: Optional["T"]` / `field: Union["T", "U"]` を持つ Pydantic model fixture がある。
  - When:
    - forward reference を補強する。
  - Then:
    - relation inventory に直接現れていない selected internal relation が seam-local hint として追加され、`Union["T", "U"]` は uniquely resolved member ごとに relation hint を追加する。
  - 観測点:
    - Pydantic hint handoff review。

## 例外・エッジケース
- EC-001:
  - 条件:
    - forward reference が複数 internal class に一致して曖昧である。
  - 期待:
    - `pydantic_forward_ref_ambiguous` warning を残し、relation は追加しない。
  - 観測点:
    - ambiguity diagnostic review。
- EC-002:
  - 条件:
    - forward reference が内部 class として解決できない。
  - 期待:
    - `pydantic_forward_ref_unresolved` warning を残し、既存 relation inventory を壊さず継続する。
  - 観測点:
    - unresolved warning review。
- EC-003:
  - 条件:
    - forward reference の target name が selection contract 外の内部 class に一致する。
  - 期待:
    - class selection owner は `analyze.relationship-and-selection` のままとし、`pydantic_forward_ref_selection_outside` warning を残して relation は追加しない。
  - 観測点:
    - selection boundary review。
- EC-004:
  - 条件:
    - target name が 1 件の selected class と 1 件以上の non-selected internal class の両方に一致する。
  - 期待:
    - all-internal candidate set では曖昧と扱い、`pydantic_forward_ref_ambiguous` warning を残して relation は追加しない。
  - 観測点:
    - mixed selected/non-selected collision review。

## 未確定事項
- なし:
  - `ClassReference` の quoted annotation evidence を最小追加し、Pydantic 解釈は `frameworks.pydantic` に閉じる。
