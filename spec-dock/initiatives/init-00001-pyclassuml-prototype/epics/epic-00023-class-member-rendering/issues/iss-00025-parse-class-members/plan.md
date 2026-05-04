---
種別: 実装計画書（Issue）
ID: "iss-00025"
タイトル: "Parse Class Members"
関連GitHub: ["#25"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md"]
親: ["epic-00023", "init-00001"]
---

# iss-00025 Parse Class Members — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001 field / method member 抽出
  - AC-002 typed reference evidence 抽出
  - AC-003 `__init__` instance field 抽出
  - AC-004 Pydantic field / forward ref evidence
- EC:
  - EC-001 unsupported annotation degrade
  - EC-002 untyped field member
  - EC-003 syntax error policy reuse
  - EC-004 `__init__`-only body analysis
- 制約:
  - no runtime import
  - no generic body analysis
  - deterministic source order

## マイルストーン一覧
- M1:
  - 対象:
    - field / method member baseline
  - exit:
    - `ParsedModule.members` が class-level member を返す
- M2:
  - 対象:
    - typed reference evidence
  - exit:
    - field / method / base の evidence 種別が downstream で区別できる
- M3:
  - 対象:
    - `__init__` instance field と degraded path
  - exit:
    - `self.x` assignment と unsupported annotation handling が通る

## 依存関係から導く実装順序
- 依存関係の正本:
  - `design.md` の `依存関係分析`
  - `design.md` の `Module Dependency Diagram`
  - `design.md` の `ディレクトリ / ファイル変更計画`
- sequencing rule:
  - upstream / prerequisite / lower-dependency slice から先に step を組む
  - downstream / dependent slice は前提が固まってから置く
- step ordering notes:
  - member DTO baseline を先に通し、typed references と degraded path を後ろに置く
- step dependency summary:
  - S01:
    - depends on:
      - iss-00024
    - unblocks:
      - S02, S03
    - target files:
      - `src/pyclassuml/parse/indexer.py`
      - `tests/parse/test_module_parse_and_index.py`

## ステップ一覧
- S01:
  - 観測可能な振る舞い:
    - class-level field / method member が `ParsedModule.members` に source order で入る
  - depends on:
    - iss-00024
  - unblocks:
    - S02, S03
  - target files:
    - `src/pyclassuml/parse/indexer.py`
    - `tests/parse/test_module_parse_and_index.py`
  - closes:
    - AC-001, EC-002
  - review gate:
    - parse member baseline tests pass
- S02:
  - 観測可能な振る舞い:
    - base / field / method parameter / method return の typed reference evidence が区別可能に handoff される
  - depends on:
    - S01
  - unblocks:
    - issue 26
  - target files:
    - `src/pyclassuml/parse/indexer.py`
    - `tests/parse/test_module_parse_and_index.py`
    - `tests/frameworks/test_pydantic.py`
  - closes:
    - AC-002, AC-004
  - review gate:
    - parse-to-framework handoff review
- S03:
  - 観測可能な振る舞い:
    - `__init__` direct `self.x` assignment が instance field member へ変換される
  - depends on:
    - S02
  - unblocks:
    - issue 27
  - target files:
    - `src/pyclassuml/parse/indexer.py`
    - `tests/parse/test_module_parse_and_index.py`
  - closes:
    - AC-003, EC-004
  - review gate:
    - `__init__` assignment tests pass
- S04:
  - 観測可能な振る舞い:
    - unsupported annotation は member を残しつつ degrade する
  - depends on:
    - S03
  - unblocks:
    - final close
  - target files:
    - `src/pyclassuml/parse/indexer.py`
    - `tests/parse/test_module_parse_and_index.py`
  - closes:
    - EC-001, EC-003
  - review gate:
    - degraded parse tests pass
- S90:
  - 観測可能な振る舞い:
    - report に parse evidence scope が残る
  - depends on:
    - S04
  - unblocks:
    - S99
  - target files:
    - `spec-dock/active/issue/report.md`
  - closes:
    - docs impact
  - review gate:
    - report evidence review
- S99:
  - 観測可能な振る舞い:
    - final validation と review が揃う
  - depends on:
    - S90
  - unblocks:
    - epic downstream execution
  - target files:
    - `spec-dock/active/issue/report.md`
  - closes:
    - final exit contract
  - review gate:
    - SG/RG/QG pass

## 要件 ↔ ステップ対応
- AC-001 -> S01
- AC-002 -> S02
- AC-003 -> S03
- AC-004 -> S02
- EC-001 -> S04
- EC-002 -> S01
- EC-003 -> S04
- EC-004 -> S03

## レビュー / QA ゲート方針
- RG1 implementation review:
  - timing:
    - S01-S04 green 後
  - scope:
    - parse helper 分割、source-order determinism、degrade policy
- QG1 QA review:
  - timing:
    - RG1 pass 後
  - scope:
    - AC/EC coverage、Pydantic handoff、syntax error regression
- SG1 spec review:
  - timing:
    - 実装前
  - scope:
    - member parse 範囲、`__init__` boundary、unsupported annotation policy

## 実行ルール（全ステップ共通）
- 実行 policy、approval cadence、completion contract は `workflow_issue.md` を正本にする。
- step / block / iteration の書き方は `phase_plan_issue.md` を正本にする。
- plan 本文には、この Issue 固有の順序、依存、検証、review / QA gate だけを書く。

## 実装ステップ

### S01 — class-level member baseline
- observable behavior:
  - class-level field / method member が `ParsedModule.members` に追加される
- design refs:
  - `design.md` の `インターフェース契約`
- depends on:
  - iss-00024
- unblocks:
  - S02, S03
- target files:
  - `src/pyclassuml/parse/indexer.py`
  - `tests/parse/test_module_parse_and_index.py`
- expected tests:
  - dataclass / plain class member extraction tests
- report update:
  - member baseline と source-order rule を残す
- notes:
  - `self` / `cls` は rendered parameter 候補から外す

#### TDD iterations（必要時）
- I1:
  - Red:
    - field / method member extraction test を追加する
  - Green:
    - member helper を実装する
  - Refactor:
    - annotation / modifier helper を分離する

#### step gate
- review:
  - parse baseline review
- expected tests:
  - `uv run --with pytest pytest tests/parse/test_module_parse_and_index.py -q`
- report update:
  - source-order decision を記録する

### S02 — typed reference evidence for field / method / base
- observable behavior:
  - downstream が field / method / base reference を区別できる
- design refs:
  - `design.md` の `インターフェース契約`
- depends on:
  - S01
- unblocks:
  - issue 26 relation classification
- target files:
  - `src/pyclassuml/parse/indexer.py`
  - `tests/parse/test_module_parse_and_index.py`
  - `tests/frameworks/test_pydantic.py`
- expected tests:
  - base ref test
  - parameter / return ref test
  - Pydantic quoted ref handoff test
- report update:
  - evidence vocabulary を残す

### S03 — `__init__` direct instance field extraction
- observable behavior:
  - `self.customer = customer` から field member が得られる
- design refs:
  - `design.md` の `採用方針 / トレードオフ`
- depends on:
  - S02
- unblocks:
  - issue 27 member rendering
- target files:
  - `src/pyclassuml/parse/indexer.py`
  - `tests/parse/test_module_parse_and_index.py`
- expected tests:
  - `__init__` parameter annotation reuse test
  - nested function exclusion test
- report update:
  - direct assignment boundary を記録する

### S04 — degraded annotation and syntax-error paths
- observable behavior:
  - unsupported annotation は degrade し、syntax error module policy は維持される
- design refs:
  - `design.md` の `テスト戦略`
- depends on:
  - S03
- unblocks:
  - final close
- target files:
  - `src/pyclassuml/parse/indexer.py`
  - `tests/parse/test_module_parse_and_index.py`
- expected tests:
  - unsupported annotation fixture
  - existing syntax error regression
- report update:
  - degraded output policy を残す

### S90 — docs impact resolution / docs refresh
- 対象:
  - docs
- 対応:
  - report に parse scope と未実施 scope なしを記録する

### S99 — final diff review quality gate
- branch diff scope:
  - `iss-00025` parse member extraction
- required validation:
  - `uv run --with pytest pytest tests/parse/test_module_parse_and_index.py tests/frameworks/test_pydantic.py -q`
  - `./spec-dock/scripts/spec-dock validate`
  - `git diff --check`
  - `rg --files | rg '[A-Z]'`
- reviewer approvals:
  - spec-reviewer pass
  - code-reviewer pass
  - qa-reviewer pass
- report update:
  - final verdict と downstream assumptions を残す

## 未確定事項
- なし:
  - `__init__` assignment scope はこの issue で固定する

## final exit contract
- AC/EC 達成:
  - member / reference / degraded parse tests が揃っている
- docs impact resolved:
  - report に parse boundary が残っている
- final diff approved:
  - SG / RG / QG pass
