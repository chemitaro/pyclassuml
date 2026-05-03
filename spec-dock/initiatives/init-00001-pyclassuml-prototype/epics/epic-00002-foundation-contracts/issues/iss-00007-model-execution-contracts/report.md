---
種別: 実装報告書（Issue）
ID: "iss-00007"
タイトル: "Model Execution Contracts"
関連GitHub: ["#7"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-03"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00002", "init-00001"]
---

# iss-00007 Model Execution Contracts — 実装報告（LOG）

## 実装サマリー (任意)
- `pyclassuml.model` の shared DTO / enum / option contract を初期実装し、downstream issue が import できる public surface を追加した。
- contract は immutable value object として実装し、collection / mapping の copy、finite enum domain、diagnostic failure rule、command-specific option absence rule、optional artifact result を pytest で観測できる状態にした。

## 実装記録（セッションログ） (必須)

### 2026-05-03 23:24 JST

#### 対象
- Step: S01, S02, S03, S90, S99
- AC/EC: AC-001, AC-002, EC-001, EC-002, EC-003, EC-004

#### 実施内容
- Active issue を `iss-00007` に設定し、`requirement.md` / `design.md` / `plan.md` を implementation-ready contract へ補強した。
- `spec-reviewer` を fail -> fix -> fail -> fix -> pass まで回し、stream routing ownership、diagnostic value domain、DTO value shape、front-stage option nullability、step dependency を明確化した。
- `pyproject.toml`、`src/pyclassuml/model`、`tests/model` を追加し、DTO / enum / option classes を `pyclassuml.model` から re-export した。
- `dataclass(frozen=True)`、tuple normalization、immutable `MappingProxyType` copy、optional path validation、finite enum validation、command-specific nested option validation、diagnostic failure/nullability rule、non-negative counters / exit code validation を実装した。
- Code review / QA review の fail 指摘を反映し、bare string collection rejection、optional path validation、`diff_scope_excluded_count` carry coverage、exact enum value set assertions、`CommandOptions` scalar invariant tests、nested pair/triple immutable copy tests を追加した。
- Docs impact は issue-scoped docs / report のみ。root `AGENTS.md`、SpecDock workflow docs、README 類の恒久 docs 更新は不要と判断した。

#### 実行コマンド / 結果
```bash
./spec-dock/scripts/spec-dock deps check iss-00007 --github
# authority=github effective_status=open source=github stale=false ready=true blockers=0

./spec-dock/scripts/spec-dock active set --id iss-00007
# active show:
# initiative: init-00001
# epic: epic-00002
# issue: iss-00007

./spec-dock/scripts/spec-dock validate
# spec-dock: ok (validate) nodes=21

uv run --with pytest pytest tests/model/test_contracts.py -q
# 17 passed in 0.01s

uv run --with pytest pytest -q
# 17 passed in 0.05s

rg --files | rg '[A-Z]'
# AGENTS.md と既存 README.md 系のみ。新規 uppercase path なし。

rm -f uv.lock && test ! -e uv.lock && echo 'uv.lock absent'
# uv.lock absent

./spec-dock/scripts/spec-dock sync --github
# spec-dock: sync: active unchanged (unchanged)
# spec-dock: ok (sync) wrote=spec-dock/.agent/index-all.json,spec-dock/.agent/tree-all.json,spec-dock/.agent/index.json,spec-dock/.agent/tree.json,spec-dock/tree-all.puml,spec-dock/tree.puml,spec-dock/.agent/deps-issues.json,spec-dock/deps-issues.puml,spec-dock/dashboard.md

./spec-dock/scripts/spec-dock validate
# spec-dock: ok (validate) nodes=21
```

#### 変更したファイル
- `pyproject.toml` - package metadata と pytest `pythonpath` の最小設定。
- `src/pyclassuml/__init__.py` - package marker。
- `src/pyclassuml/model/__init__.py` - public model contract surface の re-export。
- `src/pyclassuml/model/contracts.py` - immutable DTO / enum / option contract 実装。
- `tests/model/test_contracts.py` - AC/EC と review 指摘を観測する unit tests。
- `spec-dock/active/issue/requirement.md` - stream routing scope と carry evidence を明確化。
- `spec-dock/active/issue/design.md` - DTO value shapes、enum domains、option nullability、stream-routing ownership、file change plan を具体化。
- `spec-dock/active/issue/plan.md` - S01/S02/S03/S90/S99、depends on / unblocks / target files、review / QA gates を具体化。
- `spec-dock/active/issue/report.md` - 本実行証跡。

#### コミット
- 本成果コミットに含める。
- message: `feat(model): 実行契約DTOを追加`

#### メモ
- `spec-reviewer` final verdict: pass。最後の P2 naming clarity は docs へ反映済み。
- `code-reviewer` final verdict: pass。最後の P3 coverage gap は追加テストで解消済み。
- `qa-reviewer` verdict: pass。残 P2 は追加テストで解消済み。
- `uv run --with pytest` は一時的に `uv.lock` を生成するが、この issue の write set 外の実行副産物として削除済み。

---

## 遭遇した問題と解決 (任意)
- 問題: pytest が system Python に入っておらず、最初の `pytest` / `python -m pytest` は実行できなかった。
  - 解決: `uv run --with pytest ...` で isolated test execution を行い、targeted / full pytest を通した。
- 問題: `python3 -m venv .venv` が `ensurepip` failure で壊れた `.venv` を作った。
  - 解決: 自分が作った `.venv` を削除し、`uv run` の managed environment に切り替えた。
- 問題: reviewer が stream routing ownership、DTO value shapes、option nullability、nested collection immutability の不明瞭さを指摘した。
  - 解決: issue docs を補強し、実装 / tests を追加して review pass まで回した。

## 学んだこと (任意)
- root issue である `model.execution-contracts` は、後続実装の自由度を残しつつも enum / nullability / value shape を明確にしないと TDD 実装が分岐しやすい。
- `uv run --with pytest` はこの repo の初期 test bootstrap に有効だが、lockfile 採用方針が決まるまでは `uv.lock` を実行副産物として扱う。

## 今後の推奨事項 (任意)
- 次の ready issue は dependency graph 上 `iss-00007` 完了後に `iss-00006` / `iss-00008` 系へ広がるため、`spec-dock sync --github` 後の dashboard / deps check で ready set を再確認する。
- 後続 issue では `pyclassuml.model` の public DTO を再利用し、dict / tuple の ad-hoc handoff を増やさない。

## 省略/例外メモ (必須)
- `uv.lock` は `uv run --with pytest` の実行副産物として生成されるため削除した。lockfile 採用はこの issue の scope 外。
