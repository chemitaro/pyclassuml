---
種別: 実装計画書（Issue）
ID: "iss-00024"
タイトル: "Model Member Contracts"
関連GitHub: ["#24"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md"]
親: ["epic-00023", "init-00001"]
---

# iss-00024 Model Member Contracts — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001 member-aware shared DTO を追加する
  - AC-002 relation vocabulary を shared contract に固定する
  - AC-003 downstream が lossless に member metadata を読める
- EC:
  - EC-001 nullable field annotation
  - EC-002 empty params / return annotation omission
  - EC-003 tuple coercion / stable ordering
- 制約:
  - no convenience field
  - immutable DTO
  - parse / analyze / render logic を入れない

## マイルストーン一覧
- M1:
  - 対象:
    - `ClassMember` 系 DTO と validation
  - exit:
    - `tests/model/test_contracts.py` で member DTO contract が通る
- M2:
  - 対象:
    - relation shared contract と import surface alignment
  - exit:
    - `SelectedRelation` が shared import から使え、vocabulary validation が通る
- M3:
  - 対象:
    - compatibility / docs impact / final review
  - exit:
    - downstream issue がこの contract を前提に着手できる

## 依存関係から導く実装順序
- 依存関係の正本:
  - `design.md` の `依存関係分析`
  - `design.md` の `Module Dependency Diagram`
  - `design.md` の `ディレクトリ / ファイル変更計画`
- sequencing rule:
  - upstream / prerequisite / lower-dependency slice から先に step を組む
  - downstream / dependent slice は前提が固まってから置く
- step ordering notes:
  - DTO shape を先に固定しないと parse / analyze / render の target files が揺れる
- step dependency summary:
  - S01:
    - depends on:
      - なし
    - unblocks:
      - S02, S03
    - target files:
      - `src/pyclassuml/model/contracts.py`
      - `tests/model/test_contracts.py`

## ステップ一覧
- S01:
  - 観測可能な振る舞い:
    - `ClassMember` / `MemberParameter` / `MemberKind` / `MemberVisibility` が immutable DTO として構築できる
  - depends on:
    - なし
  - unblocks:
    - `ParsedModule.members` / `RenderReadyModel.members` 更新
  - target files:
    - `src/pyclassuml/model/contracts.py`
    - `tests/model/test_contracts.py`
  - closes:
    - AC-001, AC-003, EC-001, EC-002, EC-003
  - review gate:
    - DTO validation test pass
- S02:
  - 観測可能な振る舞い:
    - relation shared contract が `inherits`, `association`, `uses` だけを許可する
  - depends on:
    - S01
  - unblocks:
    - issue 26 typed relation classification
  - target files:
    - `src/pyclassuml/model/contracts.py`
    - `src/pyclassuml/model/__init__.py`
    - `src/pyclassuml/analyze/selection.py`
    - `src/pyclassuml/analyze/__init__.py`
    - `tests/model/test_contracts.py`
    - `tests/analyze/test_selection.py`
  - closes:
    - AC-002
  - review gate:
    - shared import surface review
- S03:
  - 観測可能な振る舞い:
    - `ParsedModule.members` と `RenderReadyModel.members` が structured DTO を受け取れる
  - depends on:
    - S01, S02
  - unblocks:
    - issue 25, issue 27
  - target files:
    - `src/pyclassuml/model/contracts.py`
    - `src/pyclassuml/model/__init__.py`
    - `tests/model/test_contracts.py`
    - `tests/render/test_document.py`
  - closes:
    - AC-001, AC-003
  - review gate:
    - compatibility review
- S90:
  - 観測可能な振る舞い:
    - supersession scope が report に残る
  - depends on:
    - S03
  - unblocks:
    - final close
  - target files:
    - `spec-dock/active/issue/report.md`
  - closes:
    - docs impact
  - review gate:
    - report evidence review
- S99:
  - 観測可能な振る舞い:
    - final validation と review verdict が揃う
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
- AC-001 -> S01, S03
- AC-002 -> S02
- AC-003 -> S01, S03
- EC-001 -> S01
- EC-002 -> S01
- EC-003 -> S01

## レビュー / QA ゲート方針
- RG1 implementation review:
  - timing:
    - S01-S03 green 後
  - scope:
    - shared DTO shape、backward compatibility、import surface
- QG1 QA review:
  - timing:
    - RG1 pass 後
  - scope:
    - DTO validation coverage、no convenience field、stable tuple coercion
- SG1 spec review:
  - timing:
    - 実装前
  - scope:
    - DTO shape、relation vocabulary、supersession scope

## 実行ルール（全ステップ共通）
- 実行 policy、approval cadence、completion contract は `workflow_issue.md` を正本にする。
- step / block / iteration の書き方は `phase_plan_issue.md` を正本にする。
- plan 本文には、この Issue 固有の順序、依存、検証、review / QA gate だけを書く。

## 実装ステップ

### S01 — member DTO baseline
- observable behavior:
  - field / method member が structured DTO として構築できる
- design refs:
  - `design.md` の `インターフェース契約`
- depends on:
  - なし
- unblocks:
  - S02, S03
- target files:
  - `src/pyclassuml/model/contracts.py`
  - `tests/model/test_contracts.py`
- expected tests:
  - member DTO validation test
  - tuple coercion test
  - nullable annotation / return test
- report update:
  - contract shape と no convenience field rationale を残す
- notes:
  - `source_order` は non-negative int で固定する

#### TDD iterations（必要時）
- I1:
  - Red:
    - member DTO construction / invalid input tests を追加する
  - Green:
    - new DTO と validation を追加する
  - Refactor:
    - existing helper を再利用する

#### step gate
- review:
  - model contract review
- expected tests:
  - `uv run --with pytest pytest tests/model/test_contracts.py -q`
- report update:
  - DTO field list と理由を記録する

### S02 — shared relation contract and import alignment
- observable behavior:
  - shared import から `SelectedRelation` を使え、`relation_type` validation が通る
- design refs:
  - `design.md` の `採用方針 / トレードオフ`
- depends on:
  - S01
- unblocks:
  - issue 26 typed relation classification
- target files:
  - `src/pyclassuml/model/contracts.py`
  - `src/pyclassuml/model/__init__.py`
  - `src/pyclassuml/analyze/selection.py`
  - `src/pyclassuml/analyze/__init__.py`
  - `tests/model/test_contracts.py`
  - `tests/analyze/test_selection.py`
- expected tests:
  - shared import test
  - invalid relation_type reject test
- report update:
  - shared化方針と compatibility note を残す

### S03 — member-aware ParsedModule and RenderReadyModel
- observable behavior:
  - `ParsedModule.members` と `RenderReadyModel.members` が `ClassMember` tuple を受け取れる
- design refs:
  - `design.md` の `インターフェース契約`
- depends on:
  - S01, S02
- unblocks:
  - issue 25 parse
  - issue 27 render
- target files:
  - `src/pyclassuml/model/contracts.py`
  - `src/pyclassuml/model/__init__.py`
  - `tests/model/test_contracts.py`
  - `tests/render/test_document.py`
- expected tests:
  - `ParsedModule` member construction test
  - `RenderReadyModel` member construction test
- report update:
  - `iss-00018` supersession scope を残す

### S90 — docs impact resolution / docs refresh
- 対象:
  - docs
- 対応:
  - `spec-dock/active/issue/report.md` に supersession と validation evidence を記録する

### S99 — final diff review quality gate
- branch diff scope:
  - `iss-00024` contract change
- required validation:
  - `uv run --with pytest pytest tests/model/test_contracts.py tests/analyze/test_selection.py tests/render/test_document.py -q`
  - `./spec-dock/scripts/spec-dock validate`
  - `git diff --check`
  - `rg --files | rg '[A-Z]'`
- reviewer approvals:
  - spec-reviewer pass
  - code-reviewer pass
  - qa-reviewer pass
- report update:
  - final verdict と remaining downstream assumptions を残す

## 未確定事項
- なし:
  - issue 25 以降はこの DTO を正本として使う

## final exit contract
- AC/EC 達成:
  - member DTO、relation vocabulary、compatibility tests が揃っている
- docs impact resolved:
  - `iss-00014` / `iss-00018` supersession scope を report で説明できる
- final diff approved:
  - SG / RG / QG pass
