---
種別: 実装計画書（Issue）
ID: "iss-00026"
タイトル: "Analyze Typed Relations"
関連GitHub: ["#26"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md"]
親: ["epic-00023", "init-00001"]
---

# iss-00026 Analyze Typed Relations — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001 `inherits`
  - AC-002 `association`
  - AC-003 `uses`
  - AC-004 warning diagnostics
- EC:
  - EC-001 unresolved
  - EC-002 ambiguous
  - EC-003 selection-outside
  - EC-004 dedupe / semantic priority
- 制約:
  - no composition
  - no traversal expansion
  - deterministic ordering

## マイルストーン一覧
- M1:
  - 対象:
    - relation resolution helper と warning policy
  - exit:
    - unresolved / ambiguous / selection-outside の fixture が通る
- M2:
  - 対象:
    - `inherits` / `association`
  - exit:
    - base class と field relation が typed relation になる
- M3:
  - 対象:
    - `uses` fallback / dedupe / framework alignment
  - exit:
    - method uses と module import fallback、Pydantic alignment が通る

## 依存関係から導く実装順序
- 依存関係の正本:
  - `design.md` の `依存関係分析`
  - `design.md` の `Module Dependency Diagram`
  - `design.md` の `ディレクトリ / ファイル変更計画`
- sequencing rule:
  - upstream / prerequisite / lower-dependency slice から先に step を組む
  - downstream / dependent slice は前提が固まってから置く
- step ordering notes:
  - warning resolution を先に固定しないと relation semantics の失敗系が揺れる
- step dependency summary:
  - S01:
    - depends on:
      - iss-00024
      - iss-00025
    - unblocks:
      - S02, S03
    - target files:
      - `src/pyclassuml/analyze/selection.py`
      - `tests/analyze/test_selection.py`

## ステップ一覧
- S01:
  - 観測可能な振る舞い:
    - typed reference を internal selected class に resolve し、warning diagnostics を返せる
  - depends on:
    - iss-00024
    - iss-00025
  - unblocks:
    - S02, S03
  - target files:
    - `src/pyclassuml/analyze/selection.py`
    - `tests/analyze/test_selection.py`
  - closes:
    - AC-004, EC-001, EC-002, EC-003
  - review gate:
    - warning resolution tests pass
- S02:
  - 観測可能な振る舞い:
    - base class は `inherits`、field / Pydantic field は `association` になる
  - depends on:
    - S01
  - unblocks:
    - S03
  - target files:
    - `src/pyclassuml/analyze/selection.py`
    - `tests/analyze/test_selection.py`
    - `tests/frameworks/test_pydantic.py`
  - closes:
    - AC-001, AC-002
  - review gate:
    - typed relation tests pass
- S03:
  - 観測可能な振る舞い:
    - method parameter / return と module import fallback が `uses` になり、duplicate relation を作らない
  - depends on:
    - S02
  - unblocks:
    - issue 27
  - target files:
    - `src/pyclassuml/analyze/selection.py`
    - `src/pyclassuml/frameworks/pydantic.py`
    - `tests/analyze/test_selection.py`
    - `tests/frameworks/test_pydantic.py`
  - closes:
    - AC-003, EC-004
  - review gate:
    - dedupe / fallback tests pass
- S90:
  - 観測可能な振る舞い:
    - `iss-00014` supersession scope が report に残る
  - depends on:
    - S03
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
    - issue 27 / 28
  - target files:
    - `spec-dock/active/issue/report.md`
  - closes:
    - final exit contract
  - review gate:
    - SG/RG/QG pass

## 要件 ↔ ステップ対応
- AC-001 -> S02
- AC-002 -> S02
- AC-003 -> S03
- AC-004 -> S01
- EC-001 -> S01
- EC-002 -> S01
- EC-003 -> S01
- EC-004 -> S03

## レビュー / QA ゲート方針
- RG1 implementation review:
  - timing:
    - S01-S03 green 後
  - scope:
    - typed relation owner、warning policy、framework alignment
- QG1 QA review:
  - timing:
    - RG1 pass 後
  - scope:
    - inherits / association / uses coverage、warning coverage、determinism
- SG1 spec review:
  - timing:
    - 実装前
  - scope:
    - relation vocabulary、semantic priority、supersession 範囲

## 実行ルール（全ステップ共通）
- 実行 policy、approval cadence、completion contract は `workflow_issue.md` を正本にする。
- step / block / iteration の書き方は `phase_plan_issue.md` を正本にする。
- plan 本文には、この Issue 固有の順序、依存、検証、review / QA gate だけを書く。

## 実装ステップ

### S01 — reference resolution and warning policy
- observable behavior:
  - typed reference を resolve し、warning code を返せる
- design refs:
  - `design.md` の `インターフェース契約`
- depends on:
  - iss-00024
  - iss-00025
- unblocks:
  - S02, S03
- target files:
  - `src/pyclassuml/analyze/selection.py`
  - `tests/analyze/test_selection.py`
- expected tests:
  - unresolved / ambiguous / selection-outside fixtures
- report update:
  - warning code 方針を残す
- notes:
  - origin_seam は `ANALYZE` を維持する

#### TDD iterations（必要時）
- I1:
  - Red:
    - warning fixture tests を追加する
  - Green:
    - resolution helper を実装する
  - Refactor:
    - sort key と diagnostic builder を helper 化する

#### step gate
- review:
  - warning policy review
- expected tests:
  - `uv run --with pytest pytest tests/analyze/test_selection.py -q`
- report update:
  - warning degraded output rationale を記録する

### S02 — inherits and association classification
- observable behavior:
  - base class と field / Pydantic field が typed relation になる
- design refs:
  - `design.md` の `classification rule`
- depends on:
  - S01
- unblocks:
  - S03
- target files:
  - `src/pyclassuml/analyze/selection.py`
  - `tests/analyze/test_selection.py`
  - `tests/frameworks/test_pydantic.py`
- expected tests:
  - inherits fixture
  - field association fixture
  - Pydantic BaseModel association fixture
- report update:
  - `iss-00014` supersession の中心を残す

### S03 — uses fallback and dedupe
- observable behavior:
  - method uses と module import fallback が共存しつつ duplicate を作らない
- design refs:
  - `design.md` の `dedupe rule`
- depends on:
  - S02
- unblocks:
  - issue 27
- target files:
  - `src/pyclassuml/analyze/selection.py`
  - `src/pyclassuml/frameworks/pydantic.py`
  - `tests/analyze/test_selection.py`
  - `tests/frameworks/test_pydantic.py`
- expected tests:
  - method parameter / return use fixture
  - module import fallback fixture
  - duplicate evidence fixture
- report update:
  - framework alignment note を残す

### S90 — docs impact resolution / docs refresh
- 対象:
  - docs
- 対応:
  - report に `iss-00014` supersession と framework alignment を記録する

### S99 — final diff review quality gate
- branch diff scope:
  - `iss-00026` typed relation classification
- required validation:
  - `uv run --with pytest pytest tests/analyze/test_selection.py tests/frameworks/test_pydantic.py -q`
  - `./spec-dock/scripts/spec-dock validate`
  - `git diff --check`
  - `rg --files | rg '[A-Z]'`
- reviewer approvals:
  - spec-reviewer pass
  - code-reviewer pass
  - qa-reviewer pass
- report update:
  - final verdict と remaining render assumptions を残す

## 未確定事項
- なし:
  - relation owner は analyze で固定する

## final exit contract
- AC/EC 達成:
  - typed relation tests と warning tests が揃う
- docs impact resolved:
  - `iss-00014` supersession が report に残る
- final diff approved:
  - SG / RG / QG pass
