---
種別: 実装報告書（Issue）
ID: "iss-00016"
タイトル: "Frameworks SQLAlchemy Enrich"
関連GitHub: ["#16"]
状態: "draft | approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00004", "init-00001"]
---

# iss-00016 Frameworks SQLAlchemy Enrich — 実装報告（LOG）

## 実装サマリー (任意)
- `ParsedModule` に framework-neutral な `ClassReference` evidence を追加し、parse seam が class-body annotation / call site evidence を AST-only で保持できるようにした。
- `frameworks.sqlalchemy` seam を追加し、`Mapped[T]` / `relationship("T")` を seam-local `SqlalchemyEnrichmentHints` へ deterministic に変換する。
- render shared DTO への合成は downstream `iss-00018` に残し、この issue は relation hint と warning diagnostics までを完了範囲にした。

## 実装記録（セッションログ） (必須)

### 2026-05-04 - contract repair

#### 対象
- Step: SG1
- AC/EC: AC-001, AC-002, EC-001, EC-002, EC-003

#### 実施内容
- `ParsedModule` の現行 contract が `imports/classes/diagnostics` のみで、`Mapped[T]` / `relationship("T")` を downstream framework seam が観測できないことを確認した。
- `requirement.md` / `design.md` / `plan.md` を、framework-neutral `ClassReference` evidence 追加と SQLAlchemy seam-local enrichment の契約へ更新した。
- warning diagnostic は shared enum に合わせ、`origin_seam=frameworks`、`recoverability=degraded_output`、`failure_reason=None` と定義した。
- spec-reviewer fail を受け、parse 抽出規則を generic `Owner[T]` / `callee("T")` evidence に寄せ、SQLAlchemy 語彙の解釈を `frameworks.sqlalchemy` 側に限定した。
- AC は seam-local `SqlalchemyEnrichmentHints.added_relations` の観測へ寄せ、実 render 観測と class decoration はこの issue の完成条件から外した。
- spec-reviewer pass 後の P2 指摘を受け、resolver 候補集合を all-internal class id に固定し、selected/non-selected mixed collision は ambiguity warning/no relation と定義した。
- warning diagnostic code を `sqlalchemy_relation_ambiguous` / `sqlalchemy_relation_unresolved` / `sqlalchemy_relation_selection_outside` に固定した。

#### 実行コマンド / 結果
```bash
sed -n '1,260p' src/pyclassuml/parse/indexer.py
sed -n '1,320p' src/pyclassuml/model/contracts.py

現行 ParsedModule は class body annotation / call site evidence を保持していない。
```

#### 変更したファイル
- `spec-dock/active/issue/requirement.md` - parse/model evidence 追加と selection boundary を明文化。
- `spec-dock/active/issue/design.md` - `ClassReference` contract と SQLAlchemy hint flow を具体化。
- `spec-dock/active/issue/plan.md` - TDD step、review/QA gate、final exit contract を具体化。
- `spec-dock/active/issue/report.md` - 契約修復の判断と証跡を記録。

#### コミット
- `f4d6f87` `docs(spec-dock): iss-00016の実装契約を具体化`

#### メモ
- parse は relation 解釈を行わず、AST evidence の保持だけに留める。
- render 反映は downstream `iss-00018` の owner なので、この issue では seam-local hints までを完成範囲とする。

---

### 2026-05-04 - implementation and review

#### 対象
- Step: S01, S02, S90, S99
- AC/EC: AC-001, AC-002, EC-001, EC-002, EC-003, EC-004

#### 実施内容
- `ClassReference(source_class_id, target_name, reference_kind, reference_owner)` を shared model contract に追加し、`ParsedModule.class_references` と public export を追加した。
- parse seam で generic `annotation_subscript` / `call_string_arg` evidence を抽出するようにした。
- parse evidence は framework-neutral に保ち、nested function / async function / class / lambda body は class-body evidence から除外した。
- class-level control statement 配下の annotation evidence は含め、typing wrapper (`Optional`, `Union`, `Annotated`, `ClassVar`, `Final`, `Literal`, `Required`, `NotRequired`) は target evidence から除外した。
- `frameworks.sqlalchemy` seam を追加し、`Mapped` / `relationship` evidence を `SelectedRelation` hint と warning diagnostics に変換するようにした。
- resolver は all-internal class id 候補集合、selected boundary、mixed selected/non-selected collision、module-qualified relationship string を扱うようにした。
- relation hint は source / target / relation_type triple で dedupe し、既存 relation inventory と同一 extraction 内の `Mapped` + `relationship` 重複を防いだ。
- warning diagnostic code は `sqlalchemy_relation_ambiguous` / `sqlalchemy_relation_unresolved` / `sqlalchemy_relation_selection_outside` に固定した。
- QA / code review の P1/P2 指摘を反映し、relationship warning path、parse-to-framework handoff、module-qualified suffix、unselected source ignore などの regression tests を追加した。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest -q

157 passed in 0.95s

./spec-dock/scripts/spec-dock validate

spec-dock: ok (validate) nodes=21

git diff --check

pass

rg --files | rg '[A-Z]'

既存の AGENTS.md / README.md 系のみ。新規 uppercase path なし。
```

#### 変更したファイル
- `src/pyclassuml/model/contracts.py` - `ClassReference` と `ParsedModule.class_references` を追加。
- `src/pyclassuml/model/__init__.py` - `ClassReference` を public export。
- `src/pyclassuml/parse/indexer.py` - framework-neutral class reference evidence 抽出を追加。
- `src/pyclassuml/frameworks/__init__.py` - framework seam export を追加。
- `src/pyclassuml/frameworks/sqlalchemy.py` - SQLAlchemy enrichment hint extractor を追加。
- `tests/model/test_contracts.py` - model contract / validation tests を追加。
- `tests/parse/test_module_parse_and_index.py` - parse evidence extraction / exclusion tests を追加。
- `tests/frameworks/test_sqlalchemy.py` - SQLAlchemy enrichment AC/EC/regression tests を追加。

#### コミット
- 未作成。最終差分確認後に implementation commit を作成する。

#### レビュー結果
- spec-reviewer:
  - 初回 fail の P1 は、parse 抽出規則の framework-neutral 化と render 観測の切り離しで解消した。
  - 再レビューは pass。P2 の mixed collision / warning code 明確化も実装前に反映した。
- code-reviewer:
  - `Mapped` + `relationship` 同一 relation triple 重複、module-qualified suffix 解決などの指摘を修正済み。
  - 最終 review は pass。最後の P2 `models.B` suffix 解決も修正済み。
- qa-reviewer:
  - existing relation inventory dedupe、nested function body exclusion、parse-to-framework fixture、relationship warning path などの指摘を修正済み。
  - 最終 QA review は pass。

#### メモ
- `uv run --with pytest` が生成した `uv.lock` は成果物ではないため削除した。
- `frameworks` と `tests/frameworks` はこの issue で新規追加した lowercase path である。

---

## 遭遇した問題と解決 (任意)
- 問題: 現行 `ParsedModule` には SQLAlchemy evidence を判断する材料がなかった。
  - 解決: parse/model に framework-neutral `ClassReference` evidence を追加し、SQLAlchemy 解釈は `frameworks.sqlalchemy` に閉じた。
- 問題: relation hint が既存 relation や同一 extraction 内の evidence 違いで重複し得た。
  - 解決: source / target / relation_type triple の seen set で dedupe した。

## 学んだこと (任意)
- SQLAlchemy support は parse 側に framework 語彙を持たせるより、generic evidence と framework seam 解釈を分ける方が後続 Pydantic support とも整合する。
- render で evidence kind が落ちる relation は、framework hint 生成時点で triple dedupe しておく必要がある。

## 今後の推奨事項 (任意)
- `iss-00018` では `SqlalchemyEnrichmentHints` を `RenderReadyModel` へ合成する際、今回の triple dedupe 前提を維持する。
- Pydantic enrich でも `ClassReference` を再利用し、parse seam に framework-specific DTO を追加しない。

## 省略/例外メモ (必須)
- render shared DTO への合成は downstream `iss-00018` の責務として、この issue では実装しない。
