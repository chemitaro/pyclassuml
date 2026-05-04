---
種別: 実装報告書（Issue）
ID: "iss-00025"
タイトル: "Parse Class Members"
関連GitHub: ["#25"]
状態: "draft | approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00023", "init-00001"]
---

# iss-00025 Parse Class Members — 実装報告（LOG）

## 実装サマリー (任意)
- AST-only の class body parse で `ParsedModule.members` を生成し、class-level field、method、`__init__` direct instance field を source-order deterministic に handoff するようにした。
- typed relation 用の semantic `ClassReference` vocabulary を実装し、base / field / init field / method parameter / method return を downstream で区別できるようにした。
- Pydantic `BaseModel` / `pydantic.BaseModel` の syntactic eligibility、quoted forward ref / container annotation、degraded annotation、syntax error policy の受け入れ検証を追加した。

## 実装記録（セッションログ） (必須)

### 2026-05-04 21:40 JST

#### 対象
- Step: S01, S02, S03, S04, S90, S99
- AC/EC: AC-001, AC-002, AC-003, AC-004, EC-001, EC-002, EC-003, EC-004

#### 実施内容
- `src/pyclassuml/parse/indexer.py` で `ClassMember` extraction を追加し、class-level `AnnAssign` / `Assign`、`FunctionDef` / `AsyncFunctionDef`、`__init__` direct `self.<name>` assignment を `ParsedModule.members` に格納するようにした。
- method modifier は `staticmethod` / `classmethod` / `property` / `async` を保持し、implicit receiver `self` / `cls` は parameter list から除外した。
- typed relation 用 semantic evidence として `class_base/base`, `field_annotation/<field_name>`, `init_field_annotation/<field_name>`, `method_parameter_annotation/<method_name>.<parameter_name>`, `method_return_annotation/<method_name>` を出力するようにした。
- quoted forward ref は relation target では quote を外し、`list["Item"]`, `Optional["Item"]`, `Union["A", "B"]` などの container から class-like target を AST-only で抽出し、`Literal[...]` は除外した。
- whole-string quoted container annotation（例: `"list['Item']"` / `"Union[A, B]"`）は Pydantic enrichment handoff 用の compatibility evidence でも inner target を出すようにした。
- degraded annotation では member を保持しつつ annotation text を `None` に落とし、`annotation_text_unavailable` warning を出し、semantic typed reference は出さないようにした。
- source-order determinism を、module-level members、nested class members、raw `ClassReference` ordering、method parameter orderingで検証した。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest tests/parse/test_module_parse_and_index.py tests/frameworks/test_pydantic.py -q
# 54 passed in 0.11s

uv run --with pytest pytest -q
# 305 passed in 10.41s

./spec-dock/scripts/spec-dock validate
# spec-dock: ok (validate) nodes=28

git diff --check
# pass

rg --files | rg '[A-Z]'
# existing allowed uppercase paths only: AGENTS.md and README.md files under spec-dock

find . \( -type d -name __pycache__ -o -type f -name '*.pyc' -o -name uv.lock -o -name '*.egg-info' \) -print
# pass after cleanup; no output
```

#### 変更したファイル
- `src/pyclassuml/parse/indexer.py` - member extraction、semantic typed references、quoted/container refs、degraded annotation policy
- `tests/parse/test_module_parse_and_index.py` - parse member / typed reference / degrade / boundary coverage
- `tests/frameworks/test_pydantic.py` - Pydantic quoted/container handoff coverage
- `spec-dock/active/issue/report.md` - 実装・検証証跡

#### コミット
- 実装差分と本 report 更新を同一コミットに含める。

#### メモ
- SG: initial fail -> requirement/design/plan を補強 -> fresh review pass。
- RG: final pass（P0/P1 findings なし）。
- QG: final pass（残 findings なし）。
- parse は relation_type を決定せず、issue 26 の classification input を作るところまでに留めた。

---

## 遭遇した問題と解決 (任意)
- 問題: typed reference vocabulary と quoted Pydantic forward ref の contract が implementation-ready ではなかった。
  - 解決: requirement / design / plan に exact `ClassReference` vocabulary、quoted container extraction、BaseModel syntactic eligibility、degraded diagnostic payload を明文化し、SG pass を取得した。
- 問題: review 中に source-order、`__init__` assignment boundary、whole-string quoted container、degraded typed reference などの edge coverage gap が見つかった。
  - 解決: focused tests と実装修正を追加し、最終的に RG/QG pass まで回した。

## 学んだこと (任意)
- `ClassReference` DTO は source position を持たないため、parser 内部では position 付き evidence として集めてから stable tuple に落とすのがよい。
- degraded annotation では display text だけでなく typed relation evidence も落とさないと、downstream に不正確な semantic input が流れる。

## 今後の推奨事項 (任意)
- issue 26 では semantic vocabulary を正本にし、既存 compatibility evidence は framework compatibility の補助として扱う。

## 省略/例外メモ (必須)
- 該当なし。SG/RG/QG と指定検証は完了。
