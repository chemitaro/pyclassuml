---
種別: 実装報告書（Issue）
ID: "iss-00035"
タイトル: "Class Level Diff Colorization"
関連GitHub: ["#35"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-15"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00004", "init-00001"]
---

# iss-00035 Class Level Diff Colorization — 実装報告（LOG）

## 実装サマリー
- `pyclassuml diff` の class box colorization を、file status ではなく base/current AST class inventory 比較に基づく class-level classification へ拡張する。
- base に存在しない selected class は `DiffAdded`、base に存在して hunk/span overlap がある selected class は `DiffChanged`、dependency-only class は decoration なしにする。

## 実装記録（セッションログ）

### 2026-05-15 13:03 - 進行中

#### 対象
- Step: issue creation / issue start / spec authoring
- AC/EC: AC-001..AC-004, EC-001..EC-005

#### 実施内容
- `epic-00004-framework-render-report` 配下に `iss-00035-class-level-diff-colorization` を作成した。
- `main` で実装せず、作業ブランチ `iss-00035-class-level-diff-colorization` を作成した。
- `issue start iss-00035` を実行し、active issue を設定した。
- requirement / design / plan を class-level added/modified diff colorization の実装契約へ具体化した。
- spec-reviewer 初回 fail を受け、safe-added base absence と unsafe base failure を分離し、AC-003 E2E closure、nested class addition と class rename conservative Added closure を追加した。
- workflow-scoped delegation consent:
  - ユーザーは SpecDock workflow に沿った実装を依頼している。
  - scope は current repo `/Users/iwasawayuuta/workspace/tools/pyclassuml`、active issue `iss-00035`、named roles `spec-reviewer`, `code-reviewer`, `qa-reviewer`, `repo-analyst` に限定する。
  - write-capable delegation、外部 publishing、破壊的操作、credentialed browser/private systems は scope 外。

#### 実行コマンド / 結果
```bash
./spec-dock/scripts/spec-dock new issue --epic epic-00004 --title "Class Level Diff Colorization" --slug class-level-diff-colorization

spec-dock: ok (new issue) id=iss-00035 epic=epic-00004 initiative=init-00001 ... github=#35
```

```bash
git checkout -b iss-00035-class-level-diff-colorization

Switched to a new branch 'iss-00035-class-level-diff-colorization'
```

```bash
./spec-dock/scripts/spec-dock issue start iss-00035

spec-dock: ok (issue start) target=iss-00035 initiative=init-00001 epic=epic-00004 issue=iss-00035
spec-dock: ok (issue checkout) branch=iss-00035-class-level-diff-colorization
```

#### Step Contract Closure
| step | closure ids | close condition | evidence | result | notes |
|---|---|---|---|---|---|
| spec-authoring | AC-001..AC-004 / EC-001..EC-005 | requirement/design/plan が implementation-ready になる | spec-reviewer first pass fail, rerun pending | pending | 実装前 gate |
| S01 | tc-s01-001, tc-s01-002, tc-s01-003 | base blob read と source text parse helper が tested | `uv run --with pytest pytest tests/vcs/test_diff_file_collect.py tests/parse/test_module_parse_and_index.py -q` -> 63 passed | pass | app no-decoration integration is covered in S02, but S01 unsafe VCS failure handling is closed |
| S02 | tc-s02-001, tc-s02-002, tc-s02-003, tc-s02-004, tc-s02-005 | app.diff が class-level `DiffAdded` / `DiffChanged` / no decoration を分類する | `uv run --with pytest pytest tests/app/test_diff.py -q` -> 46 passed | pass | renderer style is closed in S03 |
| S02-review-fix | tc-s02-001, tc-s02-005 | `--current-state head` で working-tree-only class を diff added と誤色付けしない | `uv run --with pytest pytest tests/vcs/test_diff_file_collect.py tests/app/test_diff.py -q` -> 73 passed | pass | code-reviewer P2 対応 |
| S02-review-fix-2 | tc-s02-001, tc-s02-005 | HEAD diff の分類用 current class inventory を HEAD blob に揃える | `uv run --with pytest pytest tests/vcs/test_diff_file_collect.py tests/app/test_diff.py -q` -> 73 passed | pass | code-reviewer P2 対応。worktree-only class が前方に挿入されても誤色付けしない |
| S02-review-fix-3 | tc-s02-head-current-state | HEAD diff の decorator deletion 判定用 lines も HEAD blob に揃える | `uv run --with pytest pytest tests/vcs/test_diff_file_collect.py tests/app/test_diff.py -q` -> 73 passed | pass | code-reviewer P2 対応。hunk ranges, class spans, current lines を同一 snapshot に統一 |
| S03 | tc-s03-001, tc-s03-002, tc-s03-003 | renderer が `DiffAdded` 水色 style と `DiffChanged` 緑 style を決定的に出力する | `uv run --with pytest pytest tests/render/test_document.py tests/app/test_diff.py -q` -> 75 passed | pass | generate/no-diff unaffected は existing no-style tests と final gate で再確認 |

#### Test Contract Closure
| closure id / test id | step | required | evidence level | pre-implementation evidence | verification command | result | notes |
|---|---|---|---|---|---|---|---|
| tc-s01-001 | S01 | yes | red-required | import missing before helper implementation | `uv run --with pytest pytest tests/vcs/test_diff_file_collect.py tests/parse/test_module_parse_and_index.py -q` | pass | base blob read + logical path parse |
| tc-s01-002 | S01 | yes | red-required | import missing before helper implementation | `uv run --with pytest pytest tests/vcs/test_diff_file_collect.py -q` | pass | safe-added base absence via `missing_ok=True` |
| tc-s01-003 | S01 | yes | red-required | unsafe Git failures could be masked before fix | `uv run --with pytest pytest tests/vcs/test_diff_file_collect.py tests/parse/test_module_parse_and_index.py -q` | pass | invalid base and base-tree failure raise VcsDiffError; app classifier no-decoration remains S02 |
| tc-s02-001 | S02 | yes | red-required | missing before implementation | `uv run --with pytest pytest tests/app/test_diff.py -q` | pass | modified file new class is `DiffAdded` |
| tc-s02-002 | S02 | yes | covered-existing + updated | covered as green-only regression | `uv run --with pytest pytest tests/app/test_diff.py -q` | pass | existing class modified remains `DiffChanged` |
| tc-s02-003 | S02 | yes | covered-existing + updated | covered as dependency-only no `DiffChanged` | `uv run --with pytest pytest tests/app/test_diff.py -q` | pass | dependency-only has no diff decoration |
| tc-s02-004 | S02 | yes | red-required | missing before implementation | `uv run --with pytest pytest tests/app/test_diff.py -q` | pass | nested new class is `DiffAdded` |
| tc-s02-005 | S02 | yes | red-required | missing before implementation | `uv run --with pytest pytest tests/app/test_diff.py -q` | pass | current-only class identity is `DiffAdded`; rename heuristic not introduced |
| tc-s02-head-current-state | S02 | yes | regression | code-reviewer P2 findings | `uv run --with pytest pytest tests/vcs/test_diff_file_collect.py tests/app/test_diff.py -q` | pass | HEAD diff classification uses HEAD blob inventory and does not color worktree-only class in modified or added file |
| tc-s03-001 | S03 | yes | red-required | pending before style implementation | `uv run --with pytest pytest tests/render/test_document.py tests/app/test_diff.py -q` | pass | renderer outputs `DiffAdded` style |
| tc-s03-002 | S03 | yes | covered-existing | covered by existing no-style tests | `uv run --with pytest pytest tests/render/test_document.py tests/app/test_diff.py -q` | pass | no diff decorations still suppress style block |
| tc-s03-003 | S03 | yes | red-required | pending before style implementation | `uv run --with pytest pytest tests/render/test_document.py tests/app/test_diff.py -q` | pass | added / untracked E2E includes `DiffAdded` style assertions |

#### Closure Coverage
| closure id | step | verification evidence | result | notes |
|---|---|---|---|---|
| tc-s01-001 | S01 | targeted pytest | pass |  |
| tc-s01-002 | S01 | targeted pytest | pass |  |
| tc-s01-003 | S01 | targeted pytest for VCS helper | pass | app no-decoration path remains S02 |
| tc-s02-001 | S02 | targeted pytest | pass |  |
| tc-s02-002 | S02 | targeted pytest | pass |  |
| tc-s02-003 | S02 | targeted pytest | pass |  |
| tc-s02-004 | S02 | targeted pytest | pass |  |
| tc-s02-005 | S02 | targeted pytest | pass |  |
| tc-s02-head-current-state | S02 | targeted pytest | pass | code-reviewer P2 fixes for modified and added files, including prepended worktree-only class |
| tc-s03-001 | S03 | targeted pytest | pass |  |
| tc-s03-002 | S03 | targeted pytest | pass |  |
| tc-s03-003 | S03 | targeted pytest | pass |  |

#### Closure Delta
| change | closure id | test id alias | resolves to closure id | reason | re-review required |
|---|---|---|---|---|---|
| none | all | same | same | initial plan | yes |

#### Implementation Delegation Gate
| step | decision | required reason | agent role | delegated scope | result | local-execution rationale |
|---|---|---|---|---|---|---|
| spec-authoring | delegated | workflow requires fresh spec review before implementation | spec-reviewer | requirement/design/plan implementation readiness | pending | N/A |
| S01 | approved-local-execution | small upstream seam helper and tests, immediate blocking prerequisite | N/A | VCS / parse helper implementation | pass | Pattern was localized to existing seams; code-reviewer gate still required |
| S02 | approved-local-execution | tightly coupled app.diff classifier and regression tests | N/A | app.diff class-level decoration implementation | pass | Main orchestrator handled small classifier change; code-reviewer gate still required |

#### Code Review Gate
| step | reviewer | review scope | review_status | findings / fixes | re-review count | result |
|---|---|---|---|---|---|---|
| S01 | code-reviewer | S01 VCS/parse helper diff and tests/report | pending | pending | 0 | pending |
| S02 | code-reviewer | S02 app.diff classifier diff and tests/report | pending | pending | 0 | pending |
| S03 | code-reviewer | renderer styling for `DiffAdded` plus render/app tests | pass | findings none | 0 | pass |

#### Step Commit Gate
| step | closure state | commit scope | commit hash / final ledger | post-commit clean check | no-op rationale | no-op checked contracts / files | no-op diff-clean command | no-op read-only confirmation |
|---|---|---|---|---|---|---|---|---|
| issue scaffold | committed | initial generated issue docs | 7275771 | clean before issue start | N/A | N/A | N/A | N/A |
| S01 | committed | `src/pyclassuml/vcs/*`, `src/pyclassuml/parse/*`, tests, report | 8c9421c | clean before S02 | N/A | N/A | N/A | N/A |
| S02 | committed | `src/pyclassuml/app/diff.py`, `tests/app/test_diff.py`, report | 58086d3 | clean before S03 | N/A | N/A | N/A | N/A |
| S03 | pending | `src/pyclassuml/render/document.py`, render/app tests, report | pending | pending | N/A | N/A | N/A | N/A |

#### 変更したファイル
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00004-framework-render-report/issues/iss-00035-class-level-diff-colorization/requirement.md` - class-level diff colorization 要件へ具体化。
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00004-framework-render-report/issues/iss-00035-class-level-diff-colorization/design.md` - base/current AST inventory 比較設計へ具体化。
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00004-framework-render-report/issues/iss-00035-class-level-diff-colorization/plan.md` - S01-S03 execution contract へ具体化。
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00004-framework-render-report/issues/iss-00035-class-level-diff-colorization/report.md` - workflow evidence を記録。
- `src/pyclassuml/vcs/diff_collect.py` - base revision file blob read helper を追加。
- `src/pyclassuml/vcs/__init__.py` - VCS helper を public surface に追加。
- `src/pyclassuml/parse/indexer.py` - source text から logical module path で `ParsedModule` を作る helper を追加。
- `src/pyclassuml/parse/__init__.py` - parse helper を public surface に追加。
- `tests/vcs/test_diff_file_collect.py` - base blob read / safe missing / unsafe missing tests を追加。
- `src/pyclassuml/app/diff.py` - base/current class inventory による class-level `DiffAdded` / `DiffChanged` classifier を追加。
- `tests/app/test_diff.py` - modified file new class、nested added class、unsafe base inventory、added/untracked E2E の tests を追加・更新。
- `src/pyclassuml/vcs/diff_collect.py` - tracked added file でも current-side hunk ranges を収集し、HEAD diff と working tree の色分けズレを抑止。
- `tests/app/test_diff.py` - `--current-state head` で worktree-only class を `DiffAdded` にしない regression を追加。
- `tests/parse/test_module_parse_and_index.py` - logical path parse test を追加。
- `src/pyclassuml/render/document.py` - `DiffAdded` / `DiffChanged` の PlantUML style block を decoration presence に応じて決定的に出力。
- `tests/render/test_document.py` - `DiffAdded` style と mixed style ordering の render tests を追加。
- `tests/app/test_diff.py` - added / untracked E2E で `DiffAdded` style 出力を検証。

#### コミット
- `7275771` `docs(spec-dock): class単位のdiff色分けissueを追加`
- `8c9421c` `feat(diff): class単位色分け用のbase解析を追加`
- `58086d3` `feat(diff): class単位の追加差分色分けを実装`

#### メモ
- `issue start` は untracked issue scaffold があると checkout safety guard で止まるため、作業ブランチ上で initial scaffold commit を作成してから再実行した。
- main branch で実装は行っていない。
