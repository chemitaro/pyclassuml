---
種別: 実装計画書（Issue）
ID: "iss-00013"
タイトル: "Analyze Traversal"
関連GitHub: ["#13"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md"]
親: ["epic-00003", "init-00001"]
---

# iss-00013 Analyze Traversal — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001 `ParsedModule[]` / `ModuleIndex` から reachable file と edge を持つ `DependencyGraph` を構築する。
  - AC-002 depth を import-graph hop として扱い、`depth=0` は seed のみ、`depth=1` は direct import まで、`depth=None` は traversal safety limit まで reachable にする。
  - AC-003 `scope_root` 外 candidate は frontier 拡張せず、reason-specific stop 件数を保持する。
  - AC-004 `package_root` 外 candidate は frontier に含めない。
- EC:
  - EC-001 reachable module 数が安全上限を超える場合、`analyze` owner の error diagnostic と traversal observations を返す。
  - EC-002 parse 済みでも seed frontier から到達しない candidate は `DependencyGraph` に含めない。
  - EC-003 changed class semantics には干渉せず、scope stop を保持するだけに留める。
- 制約:
  - `vcs` を直接読まない。
  - raw filesystem を再探索せず、parse 済み `ModuleIndex` / candidate lookup だけを使う。
  - relation extraction、class selection、changed class counting、framework fallback は実装しない。
  - `AnalysisConfig.depth=None` は import-hop 上限なしを意味し、traversal safety limit だけを上限にする。
  - candidate stop reason は `package_root` 外 -> `scope_root` 外 -> depth 超過の順で最初の理由だけを authoritative にし、`package_stop_count` / `scope_stop_count` / `depth_stop_count` に反映する。
  - traversal safety limit の既定値は `DEFAULT_TRAVERSAL_MODULE_LIMIT = 1000` とし、テストでは `traverse_dependencies(..., module_limit=<small int>)` で上限到達を観測する。

## マイルストーン一覧
- M1:
  - 対象: traversal public seam scaffold と seed frontier。
  - exit: `traverse_dependencies` を import でき、seed module だけの graph / observations が返る。
- M2:
  - 対象: import edge expansion と depth semantics。
  - exit: depth=0/1/None と unreachable parsed module exclusion が pytest で観測できる。
- M3:
  - 対象: package/scope stop、limit failure、review / QA / evidence。
  - exit: boundary counters と limit error が pytest と report evidence で観測できる。

## 実装順序の根拠
- 依存関係の正本:
  - `design.md` の `インターフェース契約`、`主要フロー`、`data / handoff` を参照する。
- sequencing rule:
  - seed frontier と `TraversalResult` shape を先に固定する。
  - depth semantics と reachable edge expansion を追加する。
  - package/scope stop と limit failure は最後に追加する。
- step ordering notes:
  - `iss-00012` の `ParseResult` / `ModuleIndex` を入力にする。
  - downstream relation / changed inventory / report はこの issue では呼ばず、`DependencyGraph` と `TraversalObservations` の handoff shape だけを固定する。

## ステップ一覧
- S01:
  - 観測可能な振る舞い: `traverse_dependencies` が seed provenance から seed-only `DependencyGraph` と `TraversalObservations` を返す。
  - closes: AC-001 baseline, M1
  - target files:
    - `src/pyclassuml/analyze/__init__.py`
    - `src/pyclassuml/analyze/traversal.py`
    - `tests/analyze/test_traversal.py`
  - review gate:
    - `uv run --with pytest pytest tests/analyze/test_traversal.py -q` pass。
- S02:
  - 観測可能な振る舞い: parsed import candidate lookup から reachable edge を展開し、depth=0/1/None と unreachable exclusion を deterministic に扱う。
  - closes: AC-001, AC-002, EC-002, M2
  - depends on: S01
  - target files:
    - `src/pyclassuml/analyze/traversal.py`
    - `tests/analyze/test_traversal.py`
  - review gate:
    - `uv run --with pytest pytest tests/analyze/test_traversal.py -q` pass。
- S03:
  - 観測可能な振る舞い: package_root 外 stop、scope_root 外 stop、traversal limit error が観測できる。
  - closes: AC-003, AC-004, EC-001, EC-003, M3
  - depends on: S02
  - target files:
    - `src/pyclassuml/analyze/traversal.py`
    - `tests/analyze/test_traversal.py`
  - review gate:
    - `uv run --with pytest pytest tests/analyze/test_traversal.py -q` pass。
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
- AC-003 -> S03
- AC-004 -> S03
- EC-001 -> S03
- EC-002 -> S02
- EC-003 -> S03

## レビュー / QA ゲート方針
- SG1 spec review:
  - timing:
    - 実装前。
  - scope:
    - issue docs が implementation-ready か、frontier / depth / boundary / limit / result handoff が十分か。
  - commit gate:
    - pass まで review loop を回し、pass 後に `report.md` を更新して docs repair をコミットする。
- RG1 implementation review:
  - timing:
    - S01-S03 green 後。
  - scope:
    - `src/pyclassuml/analyze/**`, `tests/analyze/**`, parse `ModuleIndex` consumption。
  - commit gate:
    - pass まで review loop を回し、pass 後に `report.md` を更新して差分確認後にコミットする。
- QG1 QA review:
  - timing:
    - RG1 pass 後。
  - scope:
    - AC/EC coverage、depth=0/1/None semantics、package/scope/depth stop ordering、limit failure、deterministic ordering、non-goal leakage。
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

### S01 — seed frontier and traversal result
- target:
  - `src/pyclassuml/analyze/__init__.py`
  - `src/pyclassuml/analyze/traversal.py`
  - `tests/analyze/test_traversal.py`
- design refs:
  - `design.md` の `インターフェース契約`
  - `design.md` の `主要フロー` 1
- step boundary:
  - seed provenance と result DTO shape に限定する。
  - import edge expansion、boundary stop、limit error は S02/S03 へ回す。
- test expectations:
  - `ModuleIndex.seed_project_relative_paths` に対応する parsed module が reachable seed になる。
  - `TraversalResult(graph, observations, diagnostics)` を返す。
  - `TraversalObservations.seed_project_relative_paths` と `reachable_file_count` が deterministic に入る。

### S02 — depth semantics and reachable edge expansion
- target:
  - `src/pyclassuml/analyze/traversal.py`
  - `tests/analyze/test_traversal.py`
- design refs:
  - `design.md` の `主要フロー` 2-3
  - `requirement.md` の AC-001/AC-002/EC-002
- step boundary:
  - parse 済み candidate lookup から reachable file / edge を作ることに限定する。
- test expectations:
  - `depth=0` では seed module のみ reachable。
  - `depth=1` では seed direct import まで reachable。
  - `depth=None` では traversal safety limit まで reachable internal imports を辿る。
  - seed から到達しない parsed module は graph に入らない。
  - edge ordering と reachable file ordering は deterministic。

### S03 — package/scope stops and traversal limit
- target:
  - `src/pyclassuml/analyze/traversal.py`
  - `tests/analyze/test_traversal.py`
- design refs:
  - `requirement.md` の AC-003/AC-004/EC-001/EC-003
  - `design.md` の `インターフェース契約`
  - `design.md` の `主要フロー`
- step boundary:
  - boundary stop と limit diagnostic に限定する。
  - relation extraction、changed inventory、report exit policy は実装しない。
- test expectations:
  - package_root 外 candidate は graph に入らず、`TraversalObservations.package_stop_count` に入る。
  - scope_root 外 candidate は graph に入らず、`TraversalObservations.scope_stop_count` に入る。
  - depth 超過 candidate は graph に入らず、`TraversalObservations.depth_stop_count` に入る。
  - package_root 外かつ scope_root 外の candidate は package stop が優先され、scope_stop_count には入らない。
  - `traverse_dependencies(..., module_limit=1)` のように小さい limit を渡し、2 件目の reachable module を追加する直前に `traversal_limit_reached` error diagnostic、`origin_seam=OriginSeam.ANALYZE`、`recoverability=Recoverability.FATAL`、`failure_reason=FailureReason.TRAVERSAL_LIMIT_REACHED` を返す。
  - limit failure 時は partial `TraversalResult.graph` と `TraversalObservations(traversal_limit_reached=True)` を返し、limit を超えた candidate は reachable_files / edges に追加しない。

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
  - `uv run --with pytest pytest tests/analyze/test_traversal.py -q`
  - `uv run --with pytest pytest tests/parse/test_module_parse_and_index.py -q`
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
  - frontier owner、depth semantics、boundary stop ordering、limit failure は requirement / design で固定済みである。

## final exit contract
- AC/EC 達成:
  - AC-001/AC-002/AC-003/AC-004/EC-001/EC-002/EC-003 が tests と review evidence で観測できる。
- docs impact resolved:
  - issue docs と report のみ更新し、恒久 docs 変更なしの判断を残す。
- final diff approved:
  - spec review / implementation review / QA review が pass し、SpecDock validate/sync evidence が report に記録されている。
