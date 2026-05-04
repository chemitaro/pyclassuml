---
種別: 実装報告書（Issue）
ID: "iss-00026"
タイトル: "Analyze Typed Relations"
関連GitHub: ["#26"]
状態: "draft | approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00023", "init-00001"]
---

# iss-00026 Analyze Typed Relations — 実装報告（LOG）

## 実装サマリー (任意)
- `analyze.selection` で `ClassReference` evidence を `inherits` / `association` / `uses` に分類し、resolver warning、same-module preference、selection-outside 非拡張、dedupe / priority を実装した。
- `frameworks.pydantic` は analyze-owned endpoint と同じ `pydantic_forward_ref` uses を追加せず、semantic field evidence と重複する compatibility warning を抑制する。
- code review は pass。QA review は pass 後、P2 coverage 指摘（selected candidate を含む ambiguity）を追加テストで解消した。

## 実装記録（セッションログ） (必須)

### 2026-05-04 22:02 - 22:02

#### 対象
- Step: S01, S02, S03, S90, S99
- AC/EC: AC-001, AC-002, AC-003, AC-004, EC-001, EC-002, EC-003, EC-004, EC-005

#### 実施内容
- typed relation resolver を追加し、full class id、module-qualified target、short name、same-module preference を固定した。
- `class_base` を `inherits`、`field_annotation` / `init_field_annotation` を `association`、method annotation を `uses` に分類した。
- same triple の canonical evidence と same endpoint の relation priority を正規化し、semantic relation がある endpoint では module import fallback を抑制した。
- Pydantic forward ref fallback は legacy path を保持しつつ、analyze-owned association と duplicate warning を抑制した。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest tests/analyze/test_selection.py tests/frameworks/test_pydantic.py tests/app/test_generate.py -q

56 passed in 0.08s
```

```bash
uv run --with pytest pytest -q

319 passed in 10.08s
```

```bash
./spec-dock/scripts/spec-dock validate

spec-dock: ok (validate) nodes=28
```

```bash
git diff --check

passed
```

```bash
rg --files | rg '[A-Z]'

AGENTS.md
spec-dock/templates/README.md
spec-dock/scripts/README.md
spec-dock/system/README.md
spec-dock/system/active-none/initiative/README.md
spec-dock/system/active-none/issue/README.md
spec-dock/system/active-none/epic/README.md
spec-dock/system/active-none/README.md
spec-dock/docs/README.md
```

```bash
code-reviewer

review_status: pass
findings: none
```

```bash
qa-reviewer

review_status: pass
finding: P2 coverage gap for ambiguity with selected candidate
resolution: added regression test; targeted/full tests passed
```

#### 変更したファイル
- `src/pyclassuml/analyze/selection.py` - typed relation classification / resolver / dedupe
- `src/pyclassuml/frameworks/pydantic.py` - duplicate endpoint suppression
- `tests/analyze/test_selection.py` - resolver / warning / classification / dedupe / ambiguity-priority tests
- `tests/frameworks/test_pydantic.py` - Pydantic duplicate endpoint suppression tests
- `tests/app/test_generate.py` - typed relation generate integration and warning outcome tests

#### コミット
- 未実施（commit 前の最終 report 更新）

#### メモ
- `iss-00014` の module import fallback は semantic endpoint relation がない場合だけ `uses` として残る。
- Pydantic `BaseModel` 自体の unresolved base warning は analyze owner の typed warning として report される。

---

## 遭遇した問題と解決 (任意)
- 問題: full pytest で Pydantic duplicate warning 前提の generate test が `degraded_success` を期待して失敗した。
  - 解決: analyze-owned recoverable warning contract に合わせて `warning_only_success` と `typed_relation_unresolved` を期待するよう更新した。
- 問題: QA review で、selected candidate を含む short-name ambiguity が selected-set filtering より前に warning になることの coverage 不足が P2 指摘された。
  - 解決: selected candidate と同名の reachable internal class があるケースを追加し、relation なし + `typed_relation_ambiguous` warning を固定した。

## 学んだこと (任意)
- semantic endpoint relation がある場合、Pydantic fallback は relation type を問わず lower-priority `uses` を足さない必要がある。
- ambiguity は selected-set filtering より前に確定し、選択済み候補があることを理由に曖昧性を握りつぶさない。

## 今後の推奨事項 (任意)
- `iss-00027` ではこの relation type / evidence kind を PlantUML rendering に接続し、fields / methods と同時に deterministic output を確認する。

## 省略/例外メモ (必須)
- 該当なし
