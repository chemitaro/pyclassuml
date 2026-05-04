---
種別: 実装報告書（Issue）
ID: "iss-00027"
タイトル: "Render Class Members"
関連GitHub: ["#27"]
状態: "draft | approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00023", "init-00001"]
---

# iss-00027 Render Class Members — 実装報告（LOG）

## 実装サマリー (任意)
- `RenderReadyModel.members` に selected class の `ClassMember` を deterministic に carry し、member 有り class だけを PlantUML brace block として描画するようにした。
- field / method / visibility / modifier / parameter / escaping と、`inherits --|>` / `association -->` / `uses ..>` の typed arrow mapping を実装した。
- spec review / code review / QA review は pass。QA P2 の coverage gap は generate-level member assertions と field-only / method-only snapshot で解消した。

## 実装記録（セッションログ） (必須)

### 2026-05-04 22:36 - 22:36

#### 対象
- Step: S01, S02, S03, S90, S99
- AC/EC: AC-001, AC-002, AC-003, AC-004, EC-001, EC-002, EC-003, EC-004, EC-005

#### 実施内容
- `compose_render_ready_model` で selected class に属する member だけを class id / source_order / kind / name の stable order で carry した。
- `render_plantuml_text` を `RenderReadyModel` + `DiagramModel` 入力に変更し、memberless class は既存 one-line syntax、member 有り class は brace block で描画した。
- field / method line、visibility symbol、modifier order/dedupe、typed/untyped parameter、return annotation、quote/backslash escaping、newline normalization を実装した。
- relation label 出力を廃止し、relation type ごとの arrow mapping に切り替えた。
- generate-level regression test を arrow/no-label と member line 出力の両方へ更新した。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest tests/render/test_document.py tests/app/test_generate.py -q

28 passed in 0.04s
```

```bash
uv run --with pytest pytest -q

324 passed in 10.47s
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
spec-dock/system/active-none/README.md
spec-dock/system/active-none/epic/README.md
spec-dock/system/active-none/issue/README.md
spec-dock/docs/README.md
```

```bash
spec-reviewer

review_status: pass
initial fail P1/P2 resolved in docs commit 8996a16
```

```bash
code-reviewer

review_status: pass
findings: none
```

```bash
qa-reviewer

review_status: pass
finding: P2 coverage gaps for generate member assertions and field-only/method-only snapshots
resolution: added tests; targeted/full tests passed
```

#### 変更したファイル
- `src/pyclassuml/render/document.py` - member carry, class body serializer, typed arrow mapping
- `tests/render/test_document.py` - member body / modifier / escaping / arrow / failure regression tests
- `tests/app/test_generate.py` - generate-level typed arrows, no-label, member line regression

#### コミット
- 未実施（commit 前の最終 report 更新）

#### メモ
- `render_plantuml_text` は `RenderReadyModel.members` を参照するため、呼び出し signature を `render_plantuml_text(render_ready_model, diagram_model)` へ変更した。
- `tests/app/test_generate.py` は render 仕様変更の E2E regression として必要な最小更新。

---

## 遭遇した問題と解決 (任意)
- 問題: 実装前 spec review で empty body syntax、modifier placement、method parameter serialization、escaping、step closure mapping が曖昧として fail した。
  - 解決: requirement / design / plan を更新し、fresh spec review pass 後に実装した。
- 問題: QA review で generate-level member assertion と field-only / method-only snapshot の coverage gap が P2 指摘された。
  - 解決: `tests/app/test_generate.py` と `tests/render/test_document.py` に regression test を追加した。
- 問題: 初回 code review は sub-agent 側の git diff 実行制約で fail した。
  - 解決: `/tmp/iss-00027-render-diff.patch` を用意し、fresh code review で pass を取得した。

## 学んだこと (任意)
- memberless class の one-line syntax を維持すると、既存 iss-00018 の snapshot 影響を最小化できる。
- CLI-user behavior の確認には render unit snapshot だけでなく generate-level `.puml` assertion も必要。

## 今後の推奨事項 (任意)
- `iss-00028` で複雑な Pydantic / domain object manual fixture に対して、field / method / typed arrow が実際の `.puml` に出ることを手動確認する。

## 省略/例外メモ (必須)
- 該当なし
