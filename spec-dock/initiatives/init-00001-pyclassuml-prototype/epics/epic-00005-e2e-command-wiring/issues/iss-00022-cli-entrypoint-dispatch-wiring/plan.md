---
種別: 実装計画書（Issue）
ID: "iss-00022"
タイトル: "CLI Entrypoint Dispatch Wiring"
関連GitHub: ["#22"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md"]
親: ["epic-00005", "init-00001"]
---

# iss-00022 CLI Entrypoint Dispatch Wiring — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001 console script availability
  - AC-002 generate process wiring
  - AC-003 diff process wiring
  - AC-004 usage and failure streams
- EC:
  - EC-001 head + default include_untracked no-op warning
  - EC-002 report-owned failure stderr projection
- 制約:
  - `cli` は process stream / exit projection に限定する。
  - `report` owner の summary / exit / artifact policy を再合成しない。

## マイルストーン一覧
- M1 contract repair:
  - 対象:
    - issue requirement/design/plan/report
  - exit:
    - spec-reviewer pass。
- M2 cli dispatch implementation:
  - 対象:
    - `pyproject.toml`
    - `src/pyclassuml/cli`
    - `tests/cli`
  - exit:
    - `uv run pyclassuml --help` と generate/diff smoke が通る。
- M3 review / QA / closure:
  - 対象:
    - code-reviewer / qa-reviewer / final validation / GitHub close / SpecDock sync
  - exit:
    - issue #22 close、dashboard 0、all nodes closed。

## ステップ一覧
- S01 console script and entrypoint:
  - 観測可能な振る舞い:
    - `uv run pyclassuml --help` が exit `0` で usage を表示する。
  - target files:
    - `pyproject.toml`
    - `src/pyclassuml/cli/main.py`
  - closes:
    - AC-001
- S02 ReportRunResult dispatch and stream projection:
  - 観測可能な振る舞い:
    - `main(argv)` が generate/diff app seam を呼び、stdout/stderr/exit code を返す。
  - target files:
    - `src/pyclassuml/cli/bind.py`
    - `src/pyclassuml/cli/main.py`
    - `tests/cli/test_main.py`
  - closes:
    - AC-002, AC-004, EC-002
- S03 diff include_untracked external default:
  - 観測可能な振る舞い:
    - `diff --base <ref>` は未指定で untracked を含み、`--no-include-untracked` は除外する。
    - `--current-state head` では default true が no-op warning として観測できる。
  - target files:
    - `src/pyclassuml/cli/bind.py`
    - `src/pyclassuml/config/resolver.py`
    - `tests/cli/test_bind.py`
    - `tests/config/test_context_resolve.py`
    - `tests/cli/test_main.py`
    - `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00002-foundation-contracts/issues/iss-00006-cli-request-bind-and-exit-contract/{requirement,plan,report}.md`
    - `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00002-foundation-contracts/issues/iss-00008-config-context-resolve/design.md`
  - closes:
    - AC-003, EC-001
  - supersedes:
    - `iss-00006` の CLI parse default `include_untracked=false`
    - `iss-00008` の config default `diff.include_untracked=false`
- S99 final diff review quality gate:
  - required validation:
    - targeted pytest
    - full pytest
    - real `uv run pyclassuml` smoke
    - `./spec-dock/scripts/spec-dock validate`
    - `git diff --check`
    - uppercase path check
    - cleanup generated files

## レビュー / QA ゲート方針
- SG1 spec review:
  - timing:
    - M1 完了後、実装前。
  - scope:
    - issue docs、initiative external CLI acceptance、`iss-00006` / `iss-00008` default supersession の整合。
- RG1 implementation review:
  - timing:
    - M2/S03 実装と validation 後。
  - scope:
    - stream ownership、handler compatibility、default change、console script。
- QG1 QA review:
  - timing:
    - RG1 pass 後。
  - scope:
    - AC/EC の process-level coverage。

## 要件 ↔ ステップ対応
- AC-001 -> S01
- AC-002 -> S02
- AC-003 -> S03
- AC-004 -> S02
- EC-001 -> S03
- EC-002 -> S02

## final exit contract
- AC/EC 達成:
  - `uv run pyclassuml --help`、generate smoke、diff smoke、failure smoke の evidence がある。
- docs impact resolved:
  - issue report に spec/code/QA review と validation を記録し、`iss-00006` / `iss-00008` の default contract docs を同期する。
- final diff approved:
  - code-reviewer pass、qa-reviewer pass、full validation pass。
