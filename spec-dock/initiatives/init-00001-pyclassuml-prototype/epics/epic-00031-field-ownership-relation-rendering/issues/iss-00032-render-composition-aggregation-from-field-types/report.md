---
種別: 実装報告書（Issue）
ID: "iss-00032"
タイトル: "Render Composition And Aggregation From Field Types"
関連GitHub: ["#32"]
状態: "closed"
作成者: "iwasawayuuta"
最終更新: "2026-05-05"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00031", "init-00001"]
---

# iss-00032 Render Composition And Aggregation From Field Types — 実装報告（LOG）

## 実装サマリー
- field annotation 由来の selected internal class relation を `composition` / `aggregation` に分類し、PlantUML では owner 側 diamond 付き・矢印頭なしの `*--` / `o--` として出力する実装を追加した。
- direct field は composition、Optional / Union / collection / mapping value / nested wrapper は aggregation になり、mapping key は ownership target から除外される。
- targeted/full tests と manual env generate + SVG 変換を実行済み。

## 実装記録（セッションログ）

### 2026-05-05 02:xx - 02:xx

#### 対象
- Step: planning
- AC/EC: AC-001 - AC-008, EC-001 - EC-006

#### 実施内容
- active issue が `iss-00032` であることを確認した。
- `requirement.md` を読み、`composition` / `aggregation` の diamond 付き・矢印頭なし出力、mapping value 対応、mapping key 除外を design / plan に反映した。
- `design.md` をテンプレートから、model / parse / analyze / render の責務と annotation shape contract を含む詳細設計へ更新した。
- `plan.md` をテンプレートから、S01-S04/S90/S99 の段階実装計画へ更新した。
- repo-analyst に既存 parse/analyze/render 構造を read-only 分析してもらい、`ClassReference` への optional metadata 追加、mapping value のみの aggregation、`*--` / `o--` render、relation priority の注意点を設計へ反映した。
- spec-reviewer の P1/P2 指摘を受け、mapping key は ownership 抽出対象外で warning 必須ではないこと、nested wrapper は recursive に item/value target を aggregation とすることを requirement / design / plan に明記した。

#### 実行コマンド / 結果
```bash
./spec-dock/scripts/spec-dock active show

initiative: init-00001
epic: epic-00031
issue: iss-00032
```

#### 変更したファイル
- `spec-dock/.../iss-00032-render-composition-aggregation-from-field-types/design.md` - 詳細設計を作成
- `spec-dock/.../iss-00032-render-composition-aggregation-from-field-types/plan.md` - 実装計画を作成
- `spec-dock/.../iss-00032-render-composition-aggregation-from-field-types/report.md` - 作業記録を初期化

#### コミット
- `6b2740c docs(spec): ownership relation実装計画を具体化`

#### メモ
- 実装は S01 から開始する。

---

### 2026-05-05 02:xx - 02:xx

#### 対象
- Step: S01, S02, S03, S04
- AC/EC: AC-001 - AC-008, EC-001 - EC-006

#### 実施内容
- dev-coder に S01-S03 実装を委任し、model / parser / analyzer / renderer / tests を更新した。
- `ClassReference.annotation_shape` を追加し、field / init field semantic reference に `direct` / `optional` / `union` / `collection` / `mapping_value` を保持するようにした。
- relation vocabulary に `composition` / `aggregation` を追加し、selection で direct field を composition、それ以外の ownership shape を aggregation に分類した。
- relation priority を `inherits` / `realizes` > `composition` > `aggregation` > `association` > `uses` にした。
- render mapping に `composition -> *--`、`aggregation -> o--` を追加し、既存の `-up-|>` / `..up|>` / `-->` / `..>` は維持した。
- manual env の disposable copy に direct / optional / list / dict value / nested Mapping / Annotated list / Protocol implementation を追加し、`.puml` と `.svg` を生成した。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest -q tests/model/test_contracts.py tests/parse/test_module_parse_and_index.py tests/analyze/test_selection.py tests/frameworks/test_sqlalchemy.py tests/render/test_document.py tests/app/test_generate.py tests/app/test_diff.py

163 passed in 1.01s
```

```bash
uv run --with pytest pytest -q

348 passed in 10.12s
```

```bash
uv run --with pytest pytest -q tests/parse/test_module_parse_and_index.py::test_mixed_unknown_and_known_wrappers_sort_safely_and_keep_fallback_targets tests/analyze/test_selection.py::test_mixed_unknown_and_known_field_wrappers_keep_ownership_over_fallback

2 passed in 0.02s
```

```bash
uv run --with pytest pytest -q tests/parse/test_module_parse_and_index.py tests/analyze/test_selection.py

68 passed in 0.07s
```

```bash
uv run pyclassuml generate --cwd /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/tmp/iss-00032-ownership-worktree --project-root . --package-root . --scope-root . --output /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/out/iss-00032/ownership-rerun.puml retail_domain

outcome: warning_only_success
exit_code: 0
seed_file_count: 15
reachable_file_count: 15
extracted_class_count: 34
extracted_relation_count: 33
warning_count: 50
```

```bash
docker run --rm -v /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/out/iss-00032:/work plantuml/plantuml:latest -tsvg /work/ownership-rerun.puml

ok, generated build/manual-tests/pyclassuml-manual-env/out/iss-00032/ownership-rerun.svg
```

```bash
rg -n '\\*--|o--|-->|\\.\\.>|-up-\\|>|\\.\\.up\\|>|OrderLineKey|OrderLine|CustomerAccount|PaymentLedger|PaymentGateway|RecordingPaymentGateway|<<Protocol>>' build/manual-tests/pyclassuml-manual-env/out/iss-00032/ownership-rerun.puml

observed:
- Order class contains customer: CustomerAccount, lines: list[OrderLine], payment_ledger: PaymentLedger, primary_line: OrderLine | None, lines_by_key: dict[OrderLineKey, OrderLine], nested_lines: Mapping[str, list[OrderLine]], annotated_lines: Annotated[list[OrderLine], 'manual']
- c022 *-- c013  # Order -> CustomerAccount composition
- c022 o-- c023  # Order -> OrderLine aggregation from list / optional / mapping value / nested wrappers
- c022 *-- c028  # Order -> PaymentLedger composition
- c024 OrderLineKey has no ownership relation from Order
- c016 -up-|> c015 and c017 -up-|> c015 inheritance regression preserved
- c034 ..up|> c033 Protocol realization regression preserved
```

```bash
rg -n '\\*-->|o-->|c022 .*c024|c024 .*c022' build/manual-tests/pyclassuml-manual-env/out/iss-00032/ownership-rerun.puml || true

no output: no arrowhead ownership relations and no Order <-> OrderLineKey ownership relation
```

```bash
uv run pyclassuml generate --cwd /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/tmp/iss-00032-union-output-worktree --project-root . --package-root . --scope-root . --output /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/out/iss-00032/union-output-rerun.puml retail_domain

outcome: warning_only_success
exit_code: 0
seed_file_count: 15
reachable_file_count: 15
extracted_class_count: 35
extracted_relation_count: 34
warning_count: 47
observed: PaymentSourceChoice.source: CardPaymentSource | InvoicePaymentSource
observed: c030 o-- c026 and c030 o-- c027
```

```bash
docker run --rm -v /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/out/iss-00032:/work plantuml/plantuml:latest -tsvg /work/union-output-rerun.puml

ok, generated build/manual-tests/pyclassuml-manual-env/out/iss-00032/union-output-rerun.svg
```

```bash
./spec-dock/scripts/spec-dock sync --github
./spec-dock/scripts/spec-dock validate

spec-dock: ok (sync)
spec-dock: ok (validate) nodes=32
```

```bash
git -C build/manual-tests/pyclassuml-manual-env status --short --branch
git diff --check
rg --files | rg '[A-Z]'
test ! -e uv.lock && printf 'uv.lock absent\n' || printf 'uv.lock present\n'

manual env: ## main
diff check: passed
uppercase scan: existing allowed uppercase paths only: AGENTS.md and README.md files
uv.lock absent
```

#### 変更したファイル
- `src/pyclassuml/model/contracts.py` - `annotation_shape` contract and `composition` / `aggregation` relation types
- `src/pyclassuml/parse/indexer.py` - field annotation shape extraction, mapping value extraction, mapping key exclusion
- `src/pyclassuml/analyze/selection.py` - ownership relation classification and priority
- `src/pyclassuml/render/document.py` - `*--` / `o--` render mapping
- `tests/model/test_contracts.py` - model contract coverage
- `tests/parse/test_module_parse_and_index.py` - annotation shape coverage
- `tests/analyze/test_selection.py` - selection classification and priority coverage
- `tests/render/test_document.py` - render arrow coverage
- `tests/app/test_generate.py` - generate E2E coverage
- `tests/app/test_diff.py` - diff E2E expected relation update

#### コミット
- `e01e7cf feat(render): field ownershipをdiamondで描画`
- `23387a3 fix(parse): annotation shape混在時のsortを安定化`

#### メモ
- manual env sample source は直接変更せず、ignored `tmp/iss-00032-ownership-worktree` に disposable copy を作成して確認後に削除した。
- QA P2 を反映し、`Card | Invoice` の PEP 604 non-null multi-target union が parser/analyzer automated tests で直接 coverage されるようにした。
- QA P2 を反映し、`mapping_value` が analyzer で aggregation になる direct coverage を追加した。
- code review P2 を反映し、`Callable[[], Target]` / `type[Target]` / `Box[Target]` のような unknown generic は `annotation_shape=None` の association fallback とし、composition に誤分類しない regression coverage を追加した。
- code review P2 を反映し、SQLAlchemy `Mapped[...]` は framework-owned wrapper として ownership semantic extraction から除外し、SQLAlchemy enrichment と field relation の二重出力を防ぐ regression coverage を追加した。
- code review P2 を反映し、`Box[Optional[Target]]` / `Box[list[Target]]` のような unknown generic nested wrapper でも `annotation_shape=None` を維持し、ownership に誤分類しない regression coverage を追加した。
- spec review P1 を反映し、AC-004 の output-layer manual evidence として `PaymentSourceChoice.source: CardPaymentSource | InvoicePaymentSource` から `o--` が2本出る `.puml` / `.svg` を生成した。

---

## Closure Coverage
- AC-001 direct field composition:
  - `tests/parse/test_module_parse_and_index.py` direct `Customer` shape coverage.
  - `tests/analyze/test_selection.py` direct field -> `composition` coverage.
  - `tests/render/test_document.py` `composition -> *--` coverage.
  - manual `.puml`: `c022 *-- c013` (`Order -> CustomerAccount`).
- AC-002 optional aggregation:
  - `tests/parse/test_module_parse_and_index.py` `Coupon | None` / `Optional[Item]` shape coverage.
  - `tests/analyze/test_selection.py` optional field -> `aggregation` coverage.
  - manual `.puml`: `Order.primary_line: OrderLine | None` contributes to `c022 o-- c023`.
- AC-003 collection aggregation:
  - `tests/parse/test_module_parse_and_index.py` `list[OrderLine]`, `Iterable[OrderLine]`, `tuple[OrderLine, ...]` shape coverage.
  - `tests/analyze/test_selection.py` collection field -> `aggregation` coverage.
  - manual `.puml`: `Order.lines: list[OrderLine]` contributes to `c022 o-- c023`.
- AC-004 multi-target union aggregation:
  - `tests/parse/test_module_parse_and_index.py` `source: Card | Invoice` shape coverage for both targets.
  - `tests/analyze/test_selection.py` `Card` and `Invoice` -> two `aggregation` relations.
  - manual `.puml`: `PaymentSourceChoice.source: CardPaymentSource | InvoicePaymentSource` produces `c030 o-- c026` and `c030 o-- c027`; `union-output-rerun.svg` generated.
- AC-005 mapping value aggregation:
  - `tests/parse/test_module_parse_and_index.py` `Mapping[ItemKey, Item]` and `dict[str, list[Item]]` value extraction coverage.
  - `tests/analyze/test_selection.py` `mapping_value` -> `aggregation` coverage.
  - manual `.puml`: `lines_by_key: dict[OrderLineKey, OrderLine]` and `nested_lines: Mapping[str, list[OrderLine]]` contribute to `c022 o-- c023`.
- AC-006 mapping key exclusion:
  - `tests/parse/test_module_parse_and_index.py` asserts `ItemKey` is not a semantic ownership reference.
  - manual negative check: no `c022 .* c024` or `c024 .* c022` relation for `OrderLineKey`.
- AC-007 method-only uses unchanged:
  - `tests/analyze/test_selection.py` method return/parameter references remain `uses`.
  - `tests/render/test_document.py` `uses -> ..>` coverage.
  - manual `.puml`: existing `..>` lines remain present.
- AC-008 inheritance / Protocol realization regression:
  - `tests/render/test_document.py` and `tests/app/test_generate.py` cover `-up-|>` and `..up|>`.
  - manual `.puml`: `c016 -up-|> c015`, `c017 -up-|> c015`, and `c034 ..up|> c033`.
- EC-001 unresolved / external target does not fabricate ownership:
  - existing analyzer warning tests cover unresolved selected target behavior.
  - manual diagnostics show unresolved external/builtin targets as warnings while `.puml` contains no fabricated diamond relation for those external targets.
- EC-002 aggregation duplicate shapes dedupe:
  - `tests/analyze/test_selection.py` relation normalization / priority tests cover duplicate endpoint collapse.
  - manual `.puml`: multiple `OrderLine` aggregation sources collapse to one `c022 o-- c023`.
- EC-003 direct + optional/collection same endpoint prefers composition:
  - `tests/analyze/test_selection.py` priority test covers composition over aggregation/association/uses.
- EC-004 unresolved container target:
  - existing analyzer warning tests cover unresolved field target behavior.
  - manual diagnostics include unresolved field targets without fabricated diamond relations.
- EC-005 unresolved mapping key does not block value aggregation:
  - `tests/parse/test_module_parse_and_index.py` mapping key is excluded from semantic ownership extraction.
  - manual `.puml`: `OrderLineKey` has no ownership relation while `OrderLine` aggregation is present.
- EC-006 nested wrapper aggregation:
  - `tests/parse/test_module_parse_and_index.py` covers `Optional[list[OrderLine]]`, `Annotated[list[OrderLine], ...]`, and `dict[str, list[Item]]`.
  - manual `.puml`: `nested_lines: Mapping[str, list[OrderLine]]` and `annotated_lines: Annotated[list[OrderLine], ...]` contribute to `c022 o-- c023`.
- Additional regression:
  - `tests/parse/test_module_parse_and_index.py` covers unknown generic fallback for `Callable[[], Target]`, `type[Target]`, `Box[Target]`, preventing false composition.
  - `tests/parse/test_module_parse_and_index.py` covers unknown generic nested fallback for `Box[Optional[Target]]` and `Box[list[Target]]`, preventing false aggregation.
  - `tests/parse/test_module_parse_and_index.py` and `tests/analyze/test_selection.py` cover mixed unknown/known wrappers such as `Box[Target] | Target` and `Union[Box[Target], list[Target]]`, preventing `None` / `str` sort crashes while preserving ownership priority.
  - `tests/parse/test_module_parse_and_index.py`, `tests/frameworks/test_sqlalchemy.py`, and `tests/app/test_generate.py` cover SQLAlchemy `Mapped[...]` as framework-owned, avoiding duplicate ownership/framework relations.

## Review Gate Evidence
- spec-reviewer:
  - Initial docs review failed on mapping key diagnostics and nested wrapper ambiguity.
  - Re-review passed after requirement / design / plan clarification.
  - Final pre-close review found missing AC-004 output-layer evidence and reviewer pass evidence; both are addressed in this report.
- code-reviewer:
  - Final code review reached `review_status: pass`.
  - P2 findings for unknown generic fallback, SQLAlchemy `Mapped[...]` duplicate relation, nested unknown generic fallback, and mixed unknown/known wrapper sort stability were addressed with regression tests.
- qa-reviewer:
  - Final QA review reached `review_status: pass`.
  - P2 findings for PEP 604 multi-target union, mapping_value analyzer coverage, uv.lock evidence, and sync/validate evidence were addressed.

## Close Evidence
- `./spec-dock/scripts/spec-dock validate`: `spec-dock: ok (validate) nodes=32`
- GitHub issue `#32` (`iss-00032`) is `CLOSED`; `closedAt=2026-05-04T17:42:51Z`; URL: `https://github.com/chemitaro/pyclassuml/issues/32`
- GitHub epic `#31` (`epic-00031`) is `CLOSED`; `closedAt=2026-05-04T17:43:01Z`; URL: `https://github.com/chemitaro/pyclassuml/issues/31`
- Branch: `iss-00032-render-composition-aggregation-from-field-types`

## 遭遇した問題と解決
- 問題: spec-reviewer から mapping key warning 方針と nested wrapper 境界が不明確と指摘された。
  - 解決: mapping key は ownership 抽出対象外で warning 必須ではないこと、nested wrapper は item/value target を aggregation とすることを requirement / design / plan に明記し、再レビューで pass を取得した。

## 学んだこと
- parser が annotation target を平坦化した後では mapping key/value の役割が失われるため、AST を読める parse seam で target shape を保持するのが安全。

## 今後の推奨事項
- 該当なし

## 省略/例外メモ
- 該当なし
