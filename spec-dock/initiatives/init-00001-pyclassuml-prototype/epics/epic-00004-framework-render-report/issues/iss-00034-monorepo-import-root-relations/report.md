---
種別: 実装報告書（Issue）
ID: "iss-00034"
タイトル: "monorepo import root mismatch drops typed relations"
関連GitHub: ["#34"]
状態: "in_progress"
作成者: "iwasawayuuta"
最終更新: "2026-05-15"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00004", "init-00001"]
---

# iss-00034 monorepo import root mismatch drops typed relations — 実装報告（LOG）

## 実装サマリー
- monorepo で Git root と Python import root がずれる場合の relation 欠落を、context root の責務分離で修正する。
- `ExecutionContext` に `vcs_root` と `import_roots` を追加し、`package_root != project_root` では `package_root` を import root として優先する。
- Reviewer sub-agent gate はこのセッションの host policy と衝突するため未実施。代替として targeted tests / full tests / validate / self-check を provisional evidence として残す。

## Workflow Delegation Consent
| source | repo/worktree | active issue | named roles | boundary | state | notes |
|---|---|---|---|---|---|---|
| user request to create and complete issue workflow | `/Users/iwasawayuuta/workspace/tools/pyclassuml` | `iss-00034` | spec-reviewer, code-reviewer, qa-reviewer | read-only reviewer roles only; no destructive/external publishing expansion | unavailable | developer policy forbids spawning sub-agents unless explicitly asked for sub-agents/delegation, so required reviewer gates are not claimed as passed |

## Spec Authoring Gate
| phase | investigated facts | reviewer | verdict | promotion | notes |
|---|---|---|---|---|---|
| requirement | user problem report; `AGENTS.md`; `workflow_issue.md`; `workflow_spec_authoring.md`; `src/pyclassuml/config/resolver.py`; `src/pyclassuml/parse/indexer.py`; `src/pyclassuml/vcs/diff_collect.py` | spec-reviewer | provisional | promoted by orchestrator self-check | reviewer unavailable due host policy; requirement scope fixed to minimal response |
| design | resolver, parser, VCS, target normalization contracts | spec-reviewer | provisional | promoted by orchestrator self-check | no CLI/config surface expansion; downstream project-relative contract preserved |
| plan | issue plan authoring contract and concrete test case contract | spec-reviewer | provisional | promoted by orchestrator self-check | required closure ids and targeted tests defined before implementation |

## 実装記録（セッションログ）

### 2026-05-15 11:50 - in progress

#### 対象
- Step: issue creation / start
- AC/EC: N/A

#### 実施内容
- `iss-00034-monorepo-import-root-relations` を `epic-00004` 配下に作成し、GitHub issue `#34` と対応付けた。
- 作成直後の scaffold が未追跡だったため、issue 登録のみ先行 commit した。
- `issue start iss-00034 -f` により active issue と branch を切り替えた。`-f` は既存 active issue guard のみを bypass した。

#### 実行コマンド / 結果
```bash
./spec-dock/scripts/spec-dock new issue --epic epic-00004 --title "monorepo import root mismatch drops typed relations" --slug "monorepo-import-root-relations"
# ok: id=iss-00034 github=#34

git commit -m "docs(spec-dock): monorepo import root問題のissueを追加" ...
# ok: 03ce54d

./spec-dock/scripts/spec-dock issue start iss-00034 -f
# ok: branch=iss-00034-monorepo-import-root-relations
```

### 2026-05-15 11:55 - 12:10

#### 対象
- Step: S01, S02, S03
- AC/EC: AC-001, AC-002, AC-003, EC-001, EC-002

#### 実施内容
- `ExecutionContext` に backward-compatible な `vcs_root` / `import_roots` を追加した。
- resolver で `package_root != project_root` のとき `import_roots=(package_root, project_root)` を構築するようにした。
- parse indexer が `context.import_roots` を順に探索し、candidate を dedupe するようにした。
- VCS diff collection が `context.vcs_root` から Git を読み、entries を `context.project_root` 相対に正規化するようにした。

#### 実行コマンド / 結果
```bash
uv run pytest ...
# fail: pytest executable/module not installed in local .venv

uvx --with pytest --with . python -m pytest \
  tests/parse/test_module_parse_and_index.py::test_import_candidates_use_package_import_root_when_project_root_is_monorepo \
  tests/config/test_context_resolve.py::test_package_root_is_preferred_import_root_for_monorepo_context \
  tests/vcs/test_diff_file_collect.py::test_vcs_root_can_differ_from_project_root_for_monorepo_diff \
  tests/vcs/test_diff_file_collect.py::test_nested_project_root_working_tree_returns_project_relative_paths_only
# first run: 1 failed due test assertion placement mistake
# second run: 4 passed
```

#### Step Contract Closure
| step | closure ids | close condition | evidence | result | notes |
|---|---|---|---|---|---|
| S01 | tc-s01-001 | resolver default exposes package-root-first import roots | targeted pytest config test | pass | `package_root != project_root` case fixed |
| S02 | tc-s02-001 | backend-local `from shared...` import resolves to backend path | targeted pytest parse test | pass | parsed modules include `backend/shared/models.py` |
| S03 | tc-s03-001, tc-s99-001 | VCS root can differ while entries remain project-relative | targeted pytest VCS tests | pass | tracked/untracked project files preserved, outside file excluded |

#### Test Contract Closure
| closure id / test id | step | required | evidence level | pre-implementation evidence | verification command | result | notes |
|---|---|---|---|---|---|---|---|
| tc-s01-001 | S01 | yes | red-required | user report and missing context fields showed no package-root-first import default | `uvx --with pytest --with . python -m pytest ...test_package_root_is_preferred_import_root_for_monorepo_context` | pass | first run exposed test placement issue, fixed |
| tc-s02-001 | S02 | yes | red-required | current `_existing_python_candidates(project_root, parts)` cannot find backend/shared | `uvx --with pytest --with . python -m pytest ...test_import_candidates_use_package_import_root_when_project_root_is_monorepo` | pass | confirms import candidate path |
| tc-s03-001 | S03 | yes | red-required | current collection used `project_root` as Git root only | `uvx --with pytest --with . python -m pytest ...test_vcs_root_can_differ_from_project_root_for_monorepo_diff` | pass | confirms path contract |
| tc-s99-001 | S03 | yes | covered-existing | existing nested project regression test | `uvx --with pytest --with . python -m pytest ...test_nested_project_root_working_tree_returns_project_relative_paths_only` | pass | compatibility check |

#### Closure Coverage
| closure id | step | verification evidence | result | notes |
|---|---|---|---|---|
| tc-s01-001 | S01 | targeted pytest | pass | context default |
| tc-s02-001 | S02 | targeted pytest | pass | import root resolution |
| tc-s03-001 | S03 | targeted pytest | pass | VCS/project path split |
| tc-s99-001 | S03/S99 | targeted pytest | pass | full suite to run in S99 |

#### Closure Delta
| change | closure id | test id alias | resolves to closure id | reason | re-review required |
|---|---|---|---|---|---|
| none | N/A | N/A | N/A | closure ids defined before implementation and retained | no |

#### Implementation Delegation Gate
| step | decision | required reason | agent role | delegated scope | result | local-execution rationale |
|---|---|---|---|---|---|---|
| S01 | approved-local-execution | context/default field addition | N/A | N/A | pass | small prerequisite change, tightly coupled to immediate implementation |
| S02 | approved-local-execution | parser import candidate change | N/A | N/A | pass | localized parser behavior with focused regression |
| S03 | approved-local-execution | VCS path conversion | N/A | N/A | pass | localized VCS behavior with tracked/untracked regression |

#### Code Review Gate
| step | reviewer | review scope | review_status | findings / fixes | re-review count | result |
|---|---|---|---|---|---|---|
| S01 | code-reviewer | step diff | unavailable | host policy prevents sub-agent use without explicit delegation request | 0 | provisional self-check only |
| S02 | code-reviewer | step diff | unavailable | host policy prevents sub-agent use without explicit delegation request | 0 | provisional self-check only |
| S03 | code-reviewer | step diff | unavailable | host policy prevents sub-agent use without explicit delegation request | 0 | provisional self-check only |

#### 変更したファイル
- `src/pyclassuml/model/contracts.py` - context root fields
- `src/pyclassuml/config/resolver.py` - import root default
- `src/pyclassuml/parse/indexer.py` - import roots based candidate search
- `src/pyclassuml/vcs/diff_collect.py` - VCS root and project-relative conversion
- `tests/config/test_context_resolve.py` - context default regression
- `tests/parse/test_module_parse_and_index.py` - monorepo import regression
- `tests/vcs/test_diff_file_collect.py` - VCS/project split regression

### 2026-05-15 12:10 - 12:15

#### 対象
- Step: S99
- AC/EC: AC-001, AC-002, AC-003, EC-001, EC-002

#### 実施内容
- full test suite を実行し、VCS monkeypatch tests の helper signature 追従漏れ 3 件を修正した。
- 修正後、full test suite と SpecDock validate が成功した。
- uppercase path check は既存正規ファイル名のみを検出し、新規 uppercase path は追加していないことを確認した。

#### 実行コマンド / 結果
```bash
uvx --with pytest --with . python -m pytest
# first full run: 381 passed, 3 failed
# failures: tests/vcs/test_diff_file_collect.py monkeypatch stubs still used old _tracked_entries signature

uvx --with pytest --with . python -m pytest
# second full run: 384 passed in 10.79s

./spec-dock/scripts/spec-dock validate
# ok: nodes=34

./spec-dock/scripts/spec-dock sync
# ok: active unchanged; wrote generated SpecDock indexes/diagrams/dashboard

./spec-dock/scripts/spec-dock validate
# ok: nodes=34

rg --files | rg '[A-Z]'
# existing allowed uppercase paths only: AGENTS.md and spec-dock README.md files

git diff --check
# ok: no output
```

#### Closure Coverage
| closure id | step | verification evidence | result | notes |
|---|---|---|---|---|
| tc-s01-001 | S01/S99 | `uvx --with pytest --with . python -m pytest` | pass | covered in full suite |
| tc-s02-001 | S02/S99 | `uvx --with pytest --with . python -m pytest` | pass | covered in full suite |
| tc-s03-001 | S03/S99 | `uvx --with pytest --with . python -m pytest` | pass | covered in full suite |
| tc-s99-001 | S99 | full pytest, SpecDock sync/validate, diff check | pass | 384 tests passed, sync ok, validate ok |

## Final Quality Gate

### S90 Docs Impact Resolution
| target | update required | owner | evidence | spec-reviewer result |
|---|---|---|---|---|
| product docs / CLI docs | no | N/A | CLI/config public surface unchanged; issue docs record new internal context contract; `sync` / `validate` ok | unavailable / provisional |

### Final QA Gate
| reviewer | scope | integration test decision | evidence | result |
|---|---|---|---|---|
| qa-reviewer | whole issue test adequacy | targeted unit/integration-style tests added; full pytest passed | `uvx --with pytest --with . python -m pytest` -> 384 passed | unavailable / provisional |

### Final Code Review Gate
| reviewer | scope | findings / fixes | re-review count | result |
|---|---|---|---|---|
| code-reviewer | issue-wide integrated diff | self-check found long-line/readability cleanup in VCS helpers and stale monkeypatch signatures; fixed before final verification | 0 | unavailable / provisional |

### Final Spec Review Gate
| reviewer | scope | findings / fixes | re-review count | result |
|---|---|---|---|---|
| spec-reviewer | requirement / design / plan / report / implementation / tests alignment | self-check found docs/report needed final evidence; updated; validate passed | 0 | unavailable / provisional |

### Final Commit
| final report ledger | final commit scope | post-commit external evidence destination | result |
|---|---|---|---|
| full pytest, sync, validate, diff check, uppercase path check, closure coverage recorded | implementation, tests, issue docs, report | final response | ready |

## 省略/例外メモ
- Required reviewer gates are not claimed as passed because sub-agent invocation is unavailable under the current host policy unless explicitly requested as delegation.
