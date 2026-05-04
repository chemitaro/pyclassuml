---
種別: 実装計画書（Issue）
ID: "iss-00014"
タイトル: "Analyze Relationship And Selection"
関連GitHub: ["#14"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md"]
親: ["epic-00003", "init-00001"]
---

# iss-00014 Analyze Relationship And Selection — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001 起点 file class の full-display と dependency relation endpoint selection を行う。
  - AC-002 reachable graph 外の class は selection から分離する。
  - AC-003 relation endpoint になった dependency-only class だけを選択する。
  - AC-004 endpoint ambiguity warning diagnostics と extracted counters を downstream へ渡す。
- EC:
  - EC-001 endpoint を一意解決できない relation は warning diagnostic を保持し、relation を追加しない。
  - EC-002 relation を持たない起点 file class は表示対象に残す。
  - EC-003 current DTO で一意解決できない multi-class dependency file は warning/no relation とし、dependency class selection を追加しない。
- 制約:
  - traversal frontier は拡張しない。
  - changed class counting は行わない。
  - framework-specific relation 補強は行わない。
  - annotation / base class / member type / wildcard token / re-export の深い symbol 解釈は、現行 `ParsedModule` が保持する `imports` / `classes` / `ModuleIndex.import_candidate_paths` の範囲を超えて推測しない。
  - `SelectionObservations` counters は core-analysis pre-enrich count であり、final diagram count は downstream render/report owner が必要に応じて置き換える。
  - MVP relation は一意な module import endpoint から作る `relation_type=\"uses\"`, `evidence_kind=\"module_import\"` に限定する。

## マイルストーン一覧
- M1:
  - 対象: selection public seam と seed full-display。
  - exit: `select_classes_and_relations` が seed class をすべて `SelectedClasses` に含める。
- M2:
  - 対象: reachable edge から一意 relation を抽出し、dependency endpoint class を選択する。
  - exit: relation-only dependency class と multi-class dependency ambiguity が pytest で観測できる。
- M3:
  - 対象: ambiguity diagnostics、observations、review / QA / evidence。
  - exit: warning diagnostics と extracted counters が pytest と report evidence で観測できる。

## 実装順序の根拠
- 依存関係の正本:
  - `design.md` の `インターフェース契約`、`主要フロー`、`data / handoff` を参照する。
- sequencing rule:
  - seed full-display と result shape を先に固定する。
  - reachable edge 由来の一意 relation を追加する。
  - ambiguity warning と observation counters を最後に追加する。
- step ordering notes:
  - `iss-00013` の `DependencyGraph` / `TraversalObservations` を入力にする。
  - downstream frameworks / render / report はこの issue では呼ばず、`SelectedClasses` / `SelectedRelations` / `SelectionObservations` の handoff shape だけを固定する。

## ステップ一覧
- S01:
  - 観測可能な振る舞い: `select_classes_and_relations` が seed module classes を relation の有無に関わらず `SelectedClasses` に含める。
  - closes: AC-001 baseline, EC-002, M1
  - target files:
    - `src/pyclassuml/analyze/selection.py`
    - `src/pyclassuml/analyze/__init__.py`
    - `tests/analyze/test_selection.py`
  - review gate:
    - `uv run --with pytest pytest tests/analyze/test_selection.py -q` pass。
- S02:
  - 観測可能な振る舞い: reachable edge の source/target module class が一意な場合に `SelectedRelation` を追加し、dependency endpoint class だけを選択する。
  - closes: AC-001, AC-002, AC-003, EC-003, M2
  - depends on: S01
  - target files:
    - `src/pyclassuml/analyze/selection.py`
    - `tests/analyze/test_selection.py`
  - review gate:
    - `uv run --with pytest pytest tests/analyze/test_selection.py -q` pass。
- S03:
  - 観測可能な振る舞い: relation endpoint ambiguity で warning diagnostics を返し、relation を追加せず、observations に class / relation / warning counters を保持する。
  - closes: AC-004, EC-001, M3
  - depends on: S02
  - target files:
    - `src/pyclassuml/analyze/selection.py`
    - `tests/analyze/test_selection.py`
  - review gate:
    - `uv run --with pytest pytest tests/analyze/test_selection.py -q` pass。
- S90:
  - 観測可能な振る舞い: docs impact が issue-scoped report へ記録される。
  - closes: docs impact resolution
  - depends on: S03
  - target files:
    - `spec-dock/active/issue/report.md`
  - review gate:
    - report に判断を残す。
- S99:
  - 観測可能な振る舞い: final validation、implementation review、QA review、SpecDock evidence が揃う。
  - closes: final exit contract
  - depends on: S90
  - target files:
    - `spec-dock/active/issue/report.md`
  - review gate:
    - required review verdict が pass。

## 要件 ↔ ステップ対応
- AC-001 -> S01, S02
- AC-002 -> S02
- AC-003 -> S02
- AC-004 -> S03
- EC-001 -> S03
- EC-002 -> S01
- EC-003 -> S02

## レビュー / QA ゲート方針
- SG1 spec review:
  - timing:
    - 実装前。
  - scope:
    - issue docs が implementation-ready か、現行 parse/traversal DTO から実装可能か。
  - commit gate:
    - pass まで review loop を回し、pass 後に `report.md` を更新して docs repair をコミットする。
- RG1 implementation review:
  - timing:
    - S01-S03 green 後。
  - scope:
    - `src/pyclassuml/analyze/selection.py`, `src/pyclassuml/analyze/__init__.py`, `tests/analyze/test_selection.py`。
  - commit gate:
    - pass まで review loop を回し、pass 後に `report.md` を更新して差分確認後にコミットする。
- QG1 QA review:
  - timing:
    - RG1 pass 後。
  - scope:
    - seed full-display、dependency endpoint selection、multi-class dependency ambiguity、unreachable exclusion、ambiguity diagnostics、core-analysis counters、deterministic ordering。
  - commit gate:
    - pass まで test loop を回し、pass 後に `report.md` を更新して差分確認後にコミットする。

## 実行ルール（全ステップ共通）
- cadence / approval policy は `workflow_issue.md` を正本とする。
- 互換参照: `Red -> Green -> Refactor -> review -> fix -> re-review -> report -> commit/no-op`
- 各 step は 1 つの観測可能な振る舞いを単位とする。
- failing test は iteration ごとに 1 本ずつ進める。
- `Green` は最小実装、`Refactor` は green 維持を前提とする。
- docs impact が `none` でなければ `S90` を実行する。
- reviewer verdict は `report.md` に残す。
- 各 stage gate（SG/RG/QG）は `pass` まで回す。
- no-op の場合のみ `report.md` に理由を残し、commit を省略できる。

## 実装ステップ

### S01 — seed full-display and selection result
- target:
  - `src/pyclassuml/analyze/selection.py`
  - `src/pyclassuml/analyze/__init__.py`
  - `tests/analyze/test_selection.py`
- design refs:
  - `design.md` の `インターフェース契約`
  - `design.md` の `主要フロー` 1, 3
- step boundary:
  - result DTO shape と seed class selection に限定する。
  - relation extraction と ambiguity diagnostics は S02/S03 へ回す。
- test expectations:
  - seed module の全 classes が deterministic に `SelectedClasses.class_ids` へ入る。
  - relation のない seed class も残る。
  - unreachable module class は selected classes に入らない。

### S02 — module import relation and dependency endpoint selection
- target:
  - `src/pyclassuml/analyze/selection.py`
  - `tests/analyze/test_selection.py`
- design refs:
  - `design.md` の `主要フロー` 2, 4
  - `requirement.md` の AC-001/AC-002/AC-003/EC-003
- step boundary:
  - `DependencyGraph.edges` にある module import relation だけを扱う。
  - annotation / base class / member type / framework relation は扱わない。
- test expectations:
  - source module class と target module class がそれぞれ 1 件なら `SelectedRelation(source_class_id, target_class_id, relation_type=\"uses\", evidence_kind=\"module_import\")` を返す。
  - dependency module の relation endpoint class は selected classes に入る。
  - multi-class dependency module は、current DTO で relation endpoint class を一意解決できないため selected classes に入らず、warning diagnostic になる。
  - reachable graph に乗らない parsed module class は selected classes に入らない。
  - ordering は deterministic。

### S03 — ambiguity diagnostics and selection observations
- target:
  - `src/pyclassuml/analyze/selection.py`
  - `tests/analyze/test_selection.py`
- design refs:
  - `requirement.md` の AC-004/EC-001
  - `design.md` の `data / handoff`
- step boundary:
  - endpoint ambiguity を warning diagnostic と observation counter に限定する。
  - strict/warn exit policy は report owner に残す。
- test expectations:
  - source module class または target module class が複数/0 件なら relation を追加せず warning diagnostic を返す。
  - diagnostic は `DiagnosticSeverity.WARNING`, `OriginSeam.ANALYZE`, `Recoverability.RECOVERABLE`, `failure_reason=None`。
  - `SelectionObservations.extracted_class_count` / `extracted_relation_count` / `warning_diagnostics` が core-analysis result と一致する。

### S90 — docs impact resolution / docs refresh
- 対象:
  - issue-scoped docs only
- 対応:
  - `requirement.md` / `design.md` / `plan.md` / `report.md` の整合を確認する。
  - root `AGENTS.md`、README、SpecDock workflow docs への恒久 docs 変更は不要と判断する。

### S99 — final diff review quality gate
- branch diff scope:
  - `git diff origin/main...HEAD` と working tree diff。
- required validation:
  - `uv run --with pytest pytest tests/analyze/test_selection.py -q`
  - `uv run --with pytest pytest tests/analyze/test_traversal.py -q`
  - `uv run --with pytest pytest -q`
  - `./spec-dock/scripts/spec-dock validate`
  - `./spec-dock/scripts/spec-dock sync --github`
  - `rg --files | rg '[A-Z]'`
- reviewer approvals:
  - spec review pass
  - implementation review pass
  - QA review pass
- report update:
  - final diff review verdict / closing evidence / no-op 理由を `./spec-dock/active/issue/report.md` に残す。
- commit expectation:
  - `report.md` 更新後に差分確認し、追加修正があれば最終コミットを作成する。無ければ直前 gate のコミットを最終成果として扱う。

## 未確定事項
- なし:
  - 現行 parse DTO で扱える MVP relation の範囲は `design.md` で固定済みである。
  - wildcard import / re-export の詳細 warning は current parse DTO に token evidence がないため非スコープである。

## final exit contract
- AC/EC 達成:
  - AC-001/AC-002/AC-003/AC-004/EC-001/EC-002/EC-003 が tests と review evidence で観測できる。
- docs impact resolved:
  - issue docs と report のみ更新し、恒久 docs 変更なしの判断を残す。
- final diff approved:
  - spec review / implementation review / QA review が pass し、SpecDock validate/sync evidence が report に記録されている。
