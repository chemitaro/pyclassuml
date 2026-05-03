---
種別: 実装計画書（Issue）
ID: "iss-00012"
タイトル: "Parse Module Parse And Index"
関連GitHub: ["#12"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md"]
親: ["epic-00003", "init-00001"]
---

# iss-00012 Parse Module Parse And Index — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001 `TargetSet.seed_files` から import 非実行 AST parse を行い、後続 `analyze` が消費できる `ParsedModule[]` と `ModuleIndex` を `ParseResult` で返す。
  - AC-002 syntax error を parse diagnostics として保持し、discard 範囲と owner を `parse` に閉じる。
  - AC-003 import candidate への project-root-relative ignore を適用し、除外件数を downstream が読める形で carry する。
- EC:
  - EC-001 起点 file は parse 成功し、import 先 candidate が syntax error の場合、起点 module は保持し、error module diagnostic を carry する。
  - EC-002 scope 内 import candidate が ignore pattern に一致する場合、parse closure へ加えず、ignore owner を `parse` として記録する。
  - EC-003 package_root 外 candidate は frontier 採否を決めず、lookup 材料として保持するに留める。
- 制約:
  - 対象コードを import 実行しない。
  - 対象 repository を書き換えない。
  - Git diff を読まない。
  - traversal depth、relation selection、changed class counting、framework enrich は実装しない。
  - parse / diagnostics / candidate ordering は deterministic にする。

## マイルストーン一覧
- M1:
  - 対象: parse public seam scaffold と seed file AST parse。
  - exit: `parse_target_set` を import でき、seed file の `ParsedModule` と `ModuleIndex` が構築される。
- M2:
  - 対象: import candidate discovery と recursive parse closure。
  - exit: relative / absolute import candidate が deterministic に materialize され、後続 traversal 用 lookup が揃う。
- M3:
  - 対象: syntax degradation、candidate ignore、package/scope boundary handoff、review / QA / evidence。
  - exit: AC/EC が pytest と report evidence で観測できる。

## 実装順序の根拠
- 依存関係の正本:
  - `design.md` の `seam position`、`インターフェース契約`、`主要フロー` を参照する。
- sequencing rule:
  - `TargetSet -> ParsedModule[]` の success path を先に固定する。
  - import candidate lookup を足して parse closure を作る。
  - 最後に syntax degradation / ignore / boundary handoff を追加する。
- step ordering notes:
  - `targets` と `config` の DTO は既存実装を入力にする。
  - `analyze.traversal` はこの issue では呼ばず、`ModuleIndex` の lookup shape だけを固定する。

## ステップ一覧
- S01:
  - 観測可能な振る舞い: `parse_target_set` が seed Python file を AST parse し、module path / imports / classes を `ParseResult(parsed_modules, module_index, observations, diagnostics)` に返す。
  - closes: AC-001 baseline, M1
  - target files:
    - `src/pyclassuml/parse/__init__.py`
    - `src/pyclassuml/parse/indexer.py`
    - `tests/parse/test_module_parse_and_index.py`
  - review gate:
    - `uv run --with pytest pytest tests/parse/test_module_parse_and_index.py -q` pass。
- S02:
  - 観測可能な振る舞い: seed module の import から project 内 Python candidate を見つけ、recursive parse closure と `ModuleIndex` lookup を deterministic に返す。
  - closes: AC-001, EC-003, M2
  - depends on: S01
  - target files:
    - `src/pyclassuml/parse/indexer.py`
    - `tests/parse/test_module_parse_and_index.py`
  - review gate:
    - `uv run --with pytest pytest tests/parse/test_module_parse_and_index.py -q` pass。
- S03:
  - 観測可能な振る舞い: syntax error module の diagnostic carry、candidate ignore count、scope/package boundary lookup が観測できる。
  - closes: AC-002, AC-003, EC-001, EC-002, EC-003, M3
  - depends on: S02
  - target files:
    - `src/pyclassuml/parse/indexer.py`
    - `tests/parse/test_module_parse_and_index.py`
  - review gate:
    - `uv run --with pytest pytest tests/parse/test_module_parse_and_index.py -q` pass。
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
- AC-002 -> S03
- AC-003 -> S03
- EC-001 -> S03
- EC-002 -> S03
- EC-003 -> S02, S03

## レビュー / QA ゲート方針
- SG1 spec review:
  - timing:
    - 実装前。
  - scope:
    - issue docs が implementation-ready か、parse closure / diagnostics / ignore / ModuleIndex handoff が十分か。
  - commit gate:
    - pass まで review loop を回し、pass 後に `report.md` を更新して docs repair をコミットする。
- RG1 implementation review:
  - timing:
    - S01-S03 green 後。
  - scope:
    - `src/pyclassuml/parse/**`, `tests/parse/**`, shared ignore usage。
  - commit gate:
    - pass まで review loop を回し、pass 後に `report.md` を更新して差分確認後にコミットする。
- QG1 QA review:
  - timing:
    - RG1 pass 後。
  - scope:
    - AC/EC coverage、AST-only / read-only、syntax degradation、candidate ignore、deterministic ordering、downstream handoff。
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

### S01 — seed file AST parse and public seam
- target:
  - `src/pyclassuml/parse/__init__.py`
  - `src/pyclassuml/parse/indexer.py`
  - `tests/parse/test_module_parse_and_index.py`
- design refs:
  - `design.md` の `インターフェース契約`
  - `design.md` の `主要フロー` 1-2
- step boundary:
  - seed file の AST parse、module path extraction、top-level / nested class qualname extraction、import name extraction に限定する。
  - import 実行、filesystem write、traversal frontier 判定は行わない。
- test expectations:
  - `TargetSet(seed_files=(pkg/a.py,))` から `ParseResult(parsed_modules=(ParsedModule(...),), module_index=..., observations=..., diagnostics=())` が返る。
  - class id は prototype MVP の既存 contract に合わせ `<module_path>:<qualname>` 形式にする。
  - `from x import y` と `import x.y` は downstream lookup 可能な import candidate 文字列として deterministic に保持する。

### S02 — recursive import candidate parse closure and ModuleIndex
- target:
  - `src/pyclassuml/parse/indexer.py`
  - `tests/parse/test_module_parse_and_index.py`
- design refs:
  - `design.md` の `主要フロー` 3-6
  - epic `design.md` の `ModuleIndex` handoff
- step boundary:
  - parse 済み import から `package_root` / `project_root` 内の `.py` candidate を探索し、parse closure を構築する。
  - package_root 外 candidate と scope_root 外 candidate は `ModuleIndex.import_candidate_paths` に保持し、frontier 採否はしない。
- test expectations:
  - relative import と absolute import の candidate file が parse closure に入る。
  - `ModuleIndex.module_by_path` / `project_relative_file_to_module` / `class_to_module` / `seed_project_relative_paths` / `import_candidate_paths` が deterministic に構築される。
  - `package_root` 内だが `scope_root` 外の candidate も lookup 材料として `import_candidate_paths` に残る。

### S03 — syntax degradation, ignore, and boundary handoff
- target:
  - `src/pyclassuml/parse/indexer.py`
  - `tests/parse/test_module_parse_and_index.py`
- design refs:
  - `requirement.md` の AC-002/AC-003/EC-001/EC-002/EC-003
  - `design.md` の `diagnostics` / `リスク`
- step boundary:
  - parse owner の diagnostics / ignore observations に限定する。
  - strict / warn の final exit policy は `report` に残す。
- test expectations:
  - syntax error module は `bad_syntax` error diagnostic、`origin_seam=OriginSeam.PARSE`、`recoverability=Recoverability.DEGRADED_OUTPUT`、`failure_reason=FailureReason.STRICT_SYNTAX_ERROR` を `ParseResult.diagnostics` に carry する。
  - syntax error module は `ParseResult.parsed_modules` と `ModuleIndex.module_by_path` / `project_relative_file_to_module` / `class_to_module` に含めない。
  - seed module が成功し、import candidate が syntax error の場合、seed module は保持される。
  - ignored dependency candidate は parse closure に入らず、`ParseResult.observations.ignored_dependency_candidate_count` に入る。
  - scope_root 内 / package_root 外 candidate と package_root 内 / scope_root 外 candidate は `ModuleIndex.import_candidate_paths` に残り、parse が frontier 採否しないことを観測する。

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
  - `uv run --with pytest pytest tests/parse/test_module_parse_and_index.py -q`
  - `uv run --with pytest pytest tests/targets/test_diff_target_normalize.py tests/targets/test_explicit_target_normalize.py -q`
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
  - observable behavior、ModuleIndex の seam-local owner、syntax degradation、candidate ignore は requirement / design で固定済みである。

## final exit contract
- AC/EC 達成:
  - AC-001/AC-002/AC-003/EC-001/EC-002/EC-003 が tests と review evidence で観測できる。
- docs impact resolved:
  - issue docs と report のみ更新し、恒久 docs 変更なしの判断を残す。
- final diff approved:
  - spec review / implementation review / QA review が pass し、SpecDock validate/sync evidence が report に記録されている。
