---
種別: 実装計画書（Issue）
ID: "iss-00030"
タイトル: "Render Upward Inheritance And Protocol Realization"
関連GitHub: ["#30"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-05"
依存: ["requirement.md", "design.md"]
親: ["epic-00029", "init-00001"]
---

# iss-00030 Render Upward Inheritance And Protocol Realization — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001, AC-002, AC-003, AC-004
- EC:
  - EC-001, EC-002
- 制約:
  - AST-only / read-only / deterministic output / lowercase path

## ステップ一覧
- S01:
  - 観測可能な振る舞い:
    - model が `realizes` relation type を受け入れる。
  - target files:
    - `src/pyclassuml/model/contracts.py`
    - model contract tests
  - closes:
    - AC-002 prerequisite
- S02:
  - 観測可能な振る舞い:
    - selected Protocol class への base relation が `realizes` になる。
  - target files:
    - `src/pyclassuml/analyze/selection.py`
    - `tests/analyze/test_selection.py`
  - closes:
    - AC-002, EC-001, EC-002
- S03:
  - 観測可能な振る舞い:
    - PlantUML が `inherits -> -up-|>` / `realizes -> ..up|>` / Protocol stereotype を出す。
  - target files:
    - `src/pyclassuml/render/document.py`
    - `tests/render/test_document.py`
  - closes:
    - AC-001, AC-002, AC-003
- S04:
  - 観測可能な振る舞い:
    - generate E2E と manual env で新表現を確認する。
  - target files:
    - `tests/app/test_generate.py`
    - `spec-dock/.../iss-00030.../report.md`
  - closes:
    - AC-004
- S99:
  - final validation:
    - targeted tests
    - full tests
    - manual generate + SVG
    - `spec-dock sync --github`
    - `spec-dock validate`
    - `git diff --check`
    - uppercase path scan

## 要件 ↔ ステップ対応
- AC-001 -> S03, S04
- AC-002 -> S01, S02, S03, S04
- AC-003 -> S03, S04
- AC-004 -> S04
- EC-001 -> S02
- EC-002 -> S02

## レビュー / QA ゲート方針
- RG1 implementation review:
  - timing: S04 後
  - scope: source / tests / report
- QG1 QA review:
  - timing: final validation 後
  - scope: AC/EC coverage, manual env evidence
- SG1 spec review:
  - timing: close 前
  - scope: requirement / design / plan / report closure

## final exit contract
- AC/EC 達成:
  - report に source/test/manual evidence を記録する。
- docs impact resolved:
  - persistent docs 更新は不要。issue / epic docs に契約を残す。
- final diff approved:
  - code / QA / spec review pass。
