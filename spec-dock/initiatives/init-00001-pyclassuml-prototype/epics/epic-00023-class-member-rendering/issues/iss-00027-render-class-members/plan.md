---
種別: 実装計画書（Issue）
ID: "iss-00027"
タイトル: "Render Class Members"
関連GitHub: ["#27"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md"]
親: ["epic-00023", "init-00001"]
---

# iss-00027 Render Class Members — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001 class body rendering
  - AC-002 typed arrow mapping
  - AC-003 empty / partial body success
  - AC-004 failure handoff continuity
- EC:
  - EC-001 field without type
  - EC-002 method without return
  - EC-003 relation-only class block
  - EC-004 modifier ordering
- 制約:
  - no filesystem write
  - no relation reclassification
  - deterministic output

## マイルストーン一覧
- M1:
  - 対象:
    - member-aware render-ready composition
  - exit:
    - `RenderReadyModel.members` が selected class members を持つ
- M2:
  - 対象:
    - class body serializer
  - exit:
    - field / method line snapshot が通る
- M3:
  - 対象:
    - typed arrow mapping / failure regression
  - exit:
    - arrow mapping と failure path が通る

## 依存関係から導く実装順序
- 依存関係の正本:
  - `design.md` の `依存関係分析`
  - `design.md` の `Module Dependency Diagram`
  - `design.md` の `ディレクトリ / ファイル変更計画`
- sequencing rule:
  - upstream / prerequisite / lower-dependency slice から先に step を組む
  - downstream / dependent slice は前提が固まってから置く
- step ordering notes:
  - compose で member inventory を渡せるようにしてから serializer を変える
- step dependency summary:
  - S01:
    - depends on:
      - iss-00024
      - iss-00025
      - iss-00026
    - unblocks:
      - S02, S03
    - target files:
      - `src/pyclassuml/render/document.py`
      - `tests/render/test_document.py`

## ステップ一覧
- S01:
  - 観測可能な振る舞い:
    - `compose_render_ready_model` が selected class members を deterministic に含める
  - depends on:
    - iss-00024
    - iss-00025
    - iss-00026
  - unblocks:
    - S02, S03
  - target files:
    - `src/pyclassuml/render/document.py`
    - `tests/render/test_document.py`
  - closes:
    - AC-001
  - review gate:
    - render-ready member tests pass
- S02:
  - 観測可能な振る舞い:
    - class body に field / method line が描画される
  - depends on:
    - S01
  - unblocks:
    - S03
  - target files:
    - `src/pyclassuml/render/document.py`
    - `tests/render/test_document.py`
  - closes:
    - AC-001, AC-003, EC-001, EC-002, EC-003, EC-004
  - review gate:
    - body snapshot tests pass
- S03:
  - 観測可能な振る舞い:
    - typed relation が arrow mapping で出力され、failure path regression がない
  - depends on:
    - S02
  - unblocks:
    - issue 28
  - target files:
    - `src/pyclassuml/render/document.py`
    - `tests/render/test_document.py`
  - closes:
    - AC-002, AC-004
  - review gate:
    - arrow mapping / failure tests pass
- S90:
  - 観測可能な振る舞い:
    - `iss-00018` supersession scope が report に残る
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
    - issue 28
  - target files:
    - `spec-dock/active/issue/report.md`
  - closes:
    - final exit contract
  - review gate:
    - SG/RG/QG pass

## 要件 ↔ ステップ対応
- AC-001 -> S01, S02
- AC-002 -> S03
- AC-003 -> S02
- AC-004 -> S03
- EC-001 -> S02
- EC-002 -> S02
- EC-003 -> S02
- EC-004 -> S02

## レビュー / QA ゲート方針
- RG1 implementation review:
  - timing:
    - S01-S03 green 後
  - scope:
    - render owner 境界、serializer change、determinism
- QG1 QA review:
  - timing:
    - RG1 pass 後
  - scope:
    - class body snapshots、arrow mapping、failure regression
- SG1 spec review:
  - timing:
    - 実装前
  - scope:
    - body format、typed arrow mapping、issue 18 supersession 範囲

## 実行ルール（全ステップ共通）
- 実行 policy、approval cadence、completion contract は `workflow_issue.md` を正本にする。
- step / block / iteration の書き方は `phase_plan_issue.md` を正本にする。
- plan 本文には、この Issue 固有の順序、依存、検証、review / QA gate だけを書く。

## 実装ステップ

### S01 — member-aware render-ready composition
- observable behavior:
  - selected class members が `RenderReadyModel.members` に入る
- design refs:
  - `design.md` の `インターフェース契約`
- depends on:
  - iss-00024
  - iss-00025
  - iss-00026
- unblocks:
  - S02, S03
- target files:
  - `src/pyclassuml/render/document.py`
  - `tests/render/test_document.py`
- expected tests:
  - member carry test
  - selected class filtering test
- report update:
  - member carry policy を残す
- notes:
  - source_order は parse owner の値を信頼し、render で再計算しない

#### TDD iterations（必要時）
- I1:
  - Red:
    - render-ready member carry test を追加する
  - Green:
    - compose に member inventory を追加する
  - Refactor:
    - class-to-members lookup helper を切り出す

#### step gate
- review:
  - render-ready contract review
- expected tests:
  - `uv run --with pytest pytest tests/render/test_document.py -q`
- report update:
  - member carry evidence を記録する

### S02 — class body serializer
- observable behavior:
  - field / method line が class block に描画される
- design refs:
  - `design.md` の `render line policy`
- depends on:
  - S01
- unblocks:
  - S03
- target files:
  - `src/pyclassuml/render/document.py`
  - `tests/render/test_document.py`
- expected tests:
  - field line snapshot
  - method line snapshot
  - modifier ordering snapshot
  - empty body snapshot
- report update:
  - class body format を残す

### S03 — typed arrows and failure continuity
- observable behavior:
  - relation_type ごとに arrow が変わり、failure path regression がない
- design refs:
  - `design.md` の `arrow mapping`
- depends on:
  - S02
- unblocks:
  - issue 28
- target files:
  - `src/pyclassuml/render/document.py`
  - `tests/render/test_document.py`
- expected tests:
  - typed arrow snapshot
  - selected class missing / relation endpoint missing tests
- report update:
  - `iss-00018` supersession note を残す

### S90 — docs impact resolution / docs refresh
- 対象:
  - docs
- 対応:
  - report に arrow mapping と body format を記録する

### S99 — final diff review quality gate
- branch diff scope:
  - `iss-00027` render body and typed arrows
- required validation:
  - `uv run --with pytest pytest tests/render/test_document.py -q`
  - `./spec-dock/scripts/spec-dock validate`
  - `git diff --check`
  - `rg --files | rg '[A-Z]'`
- reviewer approvals:
  - spec-reviewer pass
  - code-reviewer pass
  - qa-reviewer pass
- report update:
  - final verdict と E2E assumptions を残す

## 未確定事項
- なし:
  - arrow mapping と label suppression はこの issue で固定する

## final exit contract
- AC/EC 達成:
  - member body / arrow mapping / failure tests が揃う
- docs impact resolved:
  - `iss-00018` supersession が report に残る
- final diff approved:
  - SG / RG / QG pass
