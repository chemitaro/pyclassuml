---
種別: 実装計画書（Issue）
ID: "iss-00034"
タイトル: "monorepo import root mismatch drops typed relations"
関連GitHub: ["#34"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-15"
依存: ["requirement.md", "design.md"]
親: ["epic-00004", "init-00001"]
---

# iss-00034 monorepo import root mismatch drops typed relations — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC: AC-001, AC-002, AC-003
- EC: EC-001, EC-002
- 制約: read-only static analysis、既存 CLI/config surface の互換性、project-relative downstream contract。

## 依存関係から導く実装順序
- S01 は context contract と resolver default を先に固定する。Parser / VCS が参照する field をここで用意する。
- S02 は import resolution の observable behavior を直す。monorepo relation 欠落の主因なので parser regression を含める。
- S03 は VCS root と project-relative output の分離を閉じる。diff target downstream contract の回帰を含める。
- S90 は docs impact を確認する。公開 CLI/config を増やさないため README 等の更新は原則不要。
- S99 は targeted tests、full tests、validate、self review の結果をまとめる。

## ステップ一覧
- S01: `ExecutionContext` と resolver が `vcs_root` / `import_roots` を保持し、monorepo default を構築する。
- S02: parse indexer が `import_roots` を基準に absolute / relative import candidate を解決する。
- S03: VCS diff collection が `vcs_root` から Git を読み、project-relative entries を返す。
- S90: docs impact resolution。
- S99: final quality gate。

## Spec-Locked Closure Index（仕様固定クロージャ索引）

| id | phase / step | slice | type | spec link | locked expectation | observable input/state | bug class guarded | required | evidence level | closure evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| tc-s01-001 | S01 | context defaults | acceptance | AC-003, EC-001 | `package_root != project_root` では import roots が `(package_root, project_root)` になる | resolver input with repo/backend roots | monorepo import root not prioritized | yes | red-required | pytest config test |
| tc-s02-001 | S02 | import resolution | acceptance | AC-001 | `from shared.models import User` が backend/shared/models.py に解決される | parse seed under backend/app | typed relations unresolved due wrong root | yes | red-required | pytest parse test |
| tc-s03-001 | S03 | VCS path contract | acceptance | AC-002, EC-002 | `vcs_root != project_root` でも entries は project-relative だけ | repo diff with packages/app and outside.py | outside files leaking into diff targets | yes | red-required | pytest vcs test |
| tc-s99-001 | S99 | regression | regression | AC-003 | 既存 targeted nested project test が維持される | existing VCS nested project test | backward compatibility regression | yes | covered-existing | pytest targeted/full |

## 実装ステップ

### S01 — context defaults
- 観測可能な振る舞い:
  - resolver が `package_root != project_root` のとき `import_roots=(package_root, project_root)` と `vcs_root=project_root` を持つ context を返す。
- 対象ファイル:
  - `src/pyclassuml/model/contracts.py`
  - `src/pyclassuml/config/resolver.py`
  - `tests/config/test_context_resolve.py`
- test bundle:
  - closure id: `tc-s01-001`
  - evidence level: red-required
  - regression: default context equality が壊れないこと。
- 具体テストケース一覧
  - `tc-s01-001` acceptance: monorepo context default
    - 前提: repo root と backend root が存在する。
    - 操作: `resolve_context(diff_request(repo, project_root=repo, package_root=backend, scope_root=backend))` を実行する。
    - 期待結果: `context.import_roots == (backend, repo)`、`context.vcs_root == repo`。
    - 失敗検出: import root が repo のみ、または backend が優先されない。
    - 検証方法: `tests/config/test_context_resolve.py::test_package_root_is_preferred_import_root_for_monorepo_context`
- step closure contract:
  - close 条件: context field と resolver default が test で観測できる。
  - 検証 evidence: targeted pytest。
- step gate:
  - delegation 判断: approved-local-execution。小さな context/default 変更で immediate blocking のため。
  - code-reviewer gate: host policy 上 sub-agent review は未実施。orchestrator self-check を report に provisional として記録する。

### S02 — import roots based parsing
- 観測可能な振る舞い:
  - parse indexer が `context.import_roots` を順に探索し、monorepo backend-local import を解決する。
- 対象ファイル:
  - `src/pyclassuml/parse/indexer.py`
  - `tests/parse/test_module_parse_and_index.py`
- test bundle:
  - closure id: `tc-s02-001`
  - evidence level: red-required
- 具体テストケース一覧
  - `tc-s02-001` acceptance: backend import root candidate
    - 前提: `repo/backend/app/service.py` が `from shared.models import User` を持ち、`repo/backend/shared/models.py` が存在する。
    - 操作: `parse_target_set` を `project_root=repo`、`package_root=backend`、`import_roots=(backend, repo)` で実行する。
    - 期待結果: parsed modules に `backend/shared/models.py` が含まれ、import candidate path も backend 配下を指す。
    - 失敗検出: `repo/shared/models.py` だけを探索し、dependency が parsed modules に入らない。
    - 検証方法: `tests/parse/test_module_parse_and_index.py::test_import_candidates_use_package_import_root_when_project_root_is_monorepo`
- step closure contract:
  - close 条件: import candidate と parsed modules が backend 配下になる。
  - 検証 evidence: targeted pytest。
- step gate:
  - delegation 判断: approved-local-execution。変更範囲は parser の import candidate 探索に限定。
  - code-reviewer gate: host policy 上 sub-agent review は未実施。self-check を provisional として記録する。

### S03 — VCS root based diff collection
- 観測可能な振る舞い:
  - Git は `vcs_root` から読み、`project_root` 外の file は entries に混ぜず、返す path は project-relative にする。
- 対象ファイル:
  - `src/pyclassuml/vcs/diff_collect.py`
  - `tests/vcs/test_diff_file_collect.py`
- test bundle:
  - closure id: `tc-s03-001`, `tc-s99-001`
  - evidence level: red-required / covered-existing
- 具体テストケース一覧
  - `tc-s03-001` acceptance: VCS root and project root split
    - 前提: Git repo root に `outside.py`、`packages/app/inside.py` がある。
    - 操作: `collect_diff_files` を `vcs_root=repo`、`project_root=repo/packages/app` で実行する。
    - 期待結果: entries は `inside.py` と `inside_untracked.py` だけで、project-relative path になる。
    - 失敗検出: `packages/app/inside.py` のような vcs-relative path や `outside.py` が返る。
    - 検証方法: `tests/vcs/test_diff_file_collect.py::test_vcs_root_can_differ_from_project_root_for_monorepo_diff`
  - `tc-s99-001` regression: existing nested project behavior
    - 前提: 既存 nested project fixture。
    - 操作: 既存 targeted VCS test を実行する。
    - 期待結果: 従来どおり `inside.py` / `inside_untracked.py` が返る。
    - 失敗検出: path conversion 変更による regression。
    - 検証方法: `tests/vcs/test_diff_file_collect.py::test_nested_project_root_working_tree_returns_project_relative_paths_only`
- step closure contract:
  - close 条件: VCS root split と既存 nested behavior の両方が pass。
  - 検証 evidence: targeted pytest。
- step gate:
  - delegation 判断: approved-local-execution。変更は VCS path collection に閉じ、テストで tracked / untracked を固定。
  - code-reviewer gate: host policy 上 sub-agent review は未実施。self-check を provisional として記録する。

### S90 — docs impact resolution / docs refresh
- 対象:
  - `AGENTS.md`, `pyproject.toml`, CLI/config docs, spec docs。
- 対応:
  - 公開 CLI/config surface を変更しないため product docs の更新は不要。
  - Issue docs と report に設計判断を記録する。
- spec/doc review:
  - sub-agent reviewer は host policy により未実施。`./spec-dock/scripts/spec-dock validate` と self-check を provisional evidence とする。

### S99 — final quality gate
- 必須 validation:
  - targeted pytest。
  - 可能なら full pytest。
  - `./spec-dock/scripts/spec-dock validate`。
  - uppercase path check: `rg --files | rg '[A-Z]'`。
- final QA / code / spec review:
  - sub-agent gate は host policy により未実施。結果は `provisional` と記録し、complete 判定では reviewer pass と表現しない。
- final commit gate:
  - 実装・テスト・issue docs・report を 1 commit にまとめる。

## 未確定事項
- なし。
