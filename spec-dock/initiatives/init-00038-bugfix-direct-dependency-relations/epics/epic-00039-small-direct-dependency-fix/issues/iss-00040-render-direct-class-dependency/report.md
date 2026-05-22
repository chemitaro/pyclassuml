---
種別: 実装報告書（Issue）
ID: "iss-00040"
タイトル: "Render Direct Class Dependency"
関連GitHub: ["#40"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-22"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00039", "init-00038"]
---

# iss-00040 Render Direct Class Dependency — 実装報告

## 実装サマリー

- ユーザー指示により、直接依存 relation 欠落の詳細調査は `discussions/20260522t084855z-research-direct-dependency-relation-investigation.md` に移した。
- `requirement.md` / `design.md` / `plan.md` は作成済みで、実装前 `spec-reviewer` gate は pass 済み。
- S01 は実装済みで、tc-001 の Red/Green evidence を記録済み。
- S01 code-reviewer gate は再レビューで pass 済み。P2 の status cleanup はこの report 更新で対応した。
- S02 は実装済みで、tc-002 / tc-003 の Red/Green evidence を記録済み。code-reviewer gate は pass 済み。
- S03 は実装済みで、tc-004 / tc-005 / tc-006 の Red/Green evidence を記録済み。code-reviewer gate は pass 済み。
- S04 は実装済みで、tc-007 / tc-008 の Red/Green evidence を記録済み。code-reviewer gate は未実施。
- Final quality gate、PR gate は未実施。

## Spec Interpretation / Decision Ledger

| ID | Status | Type | Raised By | Trigger / Gap | Options Considered | Decision / Interpretation | Rationale | Disposition | Evidence | Follow-up |
|---|---|---|---|---|---|---|---|---|---|---|
| D-001 | resolved | scope | user / investigation | 直接依存 relation 欠落の調査結果を report ではなく research/scratch にまとめるべきという指摘 | report に詳細を置く; research に移し report は参照だけにする | 詳細調査は issue discussions の research artifact に置き、report は作業ログと反映先参照に留める | report は observed evidence ledger であり、調査本文の一次整理は research の責務に合う | applied | `discussions/20260522t084855z-research-direct-dependency-relation-investigation.md` | requirement/design/plan 作成時に research を参照 |
| D-002 | resolved | implementation-detail | dev-coder / parent | S02 で同一 method 内の複数 direct-use evidence が既存 `_ordered_class_references()` の dedupe で潰れうる | method name only; semantic expression owner; method name + AST source position | method body dependency evidence の `reference_owner` は `{method}@{lineno}:{col_offset}` とする | schema 追加なしで distinct evidence と deterministic ordering を保てる。`reference_owner` は user-facing contract ではなく diagnostics / evidence identity 用の issue-local detail | applied | S02 parse tests, parent inspection, code-reviewer pass with P2 disposition cleanup | なし。将来 semantic owner が必要になった場合は別 issue で再検討 |
| D-003 | resolved | integration-risk | dev-coder / parent | S03 selection は alias-aware import metadata を解決できるが、parse の `ast.Import` text が alias を保持しない可能性がある | S03 内では selection helper だけ実装する; S03 で parse も変える; S04 で app failure を見て parse alias preservation を追加する | S04 の app integration red で `import pkg.target as target; target.B` が欠落することを確認し、parse の `ast.Import` text に alias を保持する最小変更を入れる | alias preservation は import candidate lookup の既存責務内で、runtime import execution なしに D-003 を閉じられる | applied | S04 Red `1 failed, 70 passed`; S04 Green app targeted `71 passed`; parse alias regression test | なし |
| D-004 | resolved | false-positive-guard | qa-reviewer / code-reviewer / parent | final QA で method parameter / local assignment / local function / match capture が class-like name を shadow しても bare dependency evidence が出る false-positive と、qualified target の false-negative risk を指摘 | selection で診断して skip; parse で shadowed dependency evidence を出さない; scope out | parse seam で method-local bound names を集め、bare target name が shadowed された direct class call / member access / type-check / cast / local annotation は dependency evidence にしない。`target.B` のような qualified target は import 解決に任せて保持する | shadowing は bare symbol evidence の信頼性問題であり、qualified access は module/import evidence の解決対象であるため、同名 terminal だけで落とさない | applied | QA findings; code-review P2 match capture; parse/app Red for bare direct use/type-spec shadowing and qualified false-negative; Green full pytest `434 passed` | なし |

## 実装記録（セッションログ）

### 2026-05-22 17:41 - 18:00 JST

#### 対象

- Step: issue creation / initial investigation capture
- AC/EC: 未作成
- Planned source:
  - ユーザー指示: bugfix initiative / lightweight bugfix epic / single issue を作成し、issue start 後に調査結果を残す。

#### 実施内容

- `init-00038 Bugfix Direct Dependency Relations` を作成した。
- `epic-00039 Small Direct Dependency Fix` を作成した。
- `iss-00040 Render Direct Class Dependency` を作成した。
- `issue start iss-00040` は最初に新規 scaffold 未コミットのため checkout safety で失敗した。
- scaffold 作成分を `a3b45aa` にコミットし、再度 `issue start iss-00040` を実行して成功した。
- 直接依存 relation 欠落の詳細調査を issue discussion research として作成した。

#### 実行コマンド / 結果

```bash
./spec-dock/scripts/spec-dock new initiative --create-github-issue --title "Bugfix Direct Dependency Relations" --slug bugfix-direct-dependency-relations
# ok: id=init-00038 github=#38

./spec-dock/scripts/spec-dock new epic --create-github-issue --initiative init-00038 --title "Small Direct Dependency Fix" --slug small-direct-dependency-fix
# ok: id=epic-00039 github=#39

./spec-dock/scripts/spec-dock new issue --create-github-issue --epic epic-00039 --title "Render Direct Class Dependency" --slug render-direct-class-dependency
# ok: id=iss-00040 github=#40

./spec-dock/scripts/spec-dock issue start iss-00040
# first attempt failed: Working tree is not clean

git commit -m "docs(spec-dock): 直接依存表示修正の作業ツリーを追加" ...
# ok: a3b45aa

./spec-dock/scripts/spec-dock issue start iss-00040
# ok: branch=iss-00040-render-direct-class-dependency

./spec-dock/scripts/spec-dock new doc research --issue iss-00040 --title "Direct Dependency Relation Investigation" --slug direct-dependency-relation-investigation
# ok: path=.../discussions/20260522t084855z-research-direct-dependency-relation-investigation.md

./spec-dock/scripts/spec-dock validate
# ok: nodes=39
```

#### Red/Green/Refactor Evidence

| step | phase | planned evidence requirement | observed evidence | command / inspection / manual record | result | notes |
|---|---|---|---|---|---|---|
| investigation | characterization | manual-required | direct use 欠落を CLI 手動再現で確認 | research artifact に記録 | pass | `uv run` は環境権限で不可 |
| investigation | inspection | inspect-only | parse / selection / render の責務境界を確認 | research artifact に記録 | pass | render は主因ではない |

#### Discovered Tests

| step | discovered test / risk | source | action taken | closure id / new id | plan amendment required | evidence |
|---|---|---|---|---|---|---|
| investigation | 同一ファイル内 `return B()` で relation 0 | manual repro | research に記録し、requirement/design へ昇格予定 | TBD | yes | `discussions/20260522t084855z-research-direct-dependency-relation-investigation.md` |
| investigation | `from module import B` でも target module 複数 class で relation 0 | manual repro | research に記録し、design の target resolution strategy へ昇格予定 | TBD | yes | `discussions/20260522t084855z-research-direct-dependency-relation-investigation.md` |
| investigation | `uses` は `..>` であり黒実線ではない | code inspection | research に記録し、arrow policy を requirement/design で固定予定 | TBD | yes | `discussions/20260522t084855z-research-direct-dependency-relation-investigation.md` |

#### Workflow Delegation Consent

| consent source | repo/worktree | active issue | session | named roles | boundary | expires / invalidation condition | denied / unavailable reason | next action |
|---|---|---|---|---|---|---|---|---|
| user instruction: deep consultant analysis requested in prior turn | `/Users/iwasawayuuta/workspace/tools/pyclassuml` | iss-00040 | current session | deep-consultant | read-only investigation only; no destructive action / publishing / credentialed access / scope expansion / write-capable delegation | session end / scope change / user revocation | none | use findings as research evidence |

#### Implementation Delegation Gate

| step | decision | required reason | delegated role | delegated scope | source of truth | allowed changes | forbidden changes | required verification | stop conditions | output required | observed result |
|---|---|---|---|---|---|---|---|---|---|---|---|
| investigation | delegated | user explicitly requested deep-consultant analysis | deep-consultant x2 | read-only root cause analysis and repro strategy | current repo code, tests, docs | none | file edits, commits, external publication | code inspection and reproducibility assessment | unable to inspect repo / conflicting evidence | Japanese root cause report | pass |
| research capture | approved-local-execution | issue-local research/report metadata capture requested by user | N/A | active issue discussions and report | current session investigation evidence | `discussions/*.md`, `report.md` | runtime code, requirement/design/plan substantive authoring | `spec-dock validate` after update | validation failure | research content and validation evidence | pass |

#### Delegated Worker Evidence

| step | delegated role | delegated worker summary | changed files | tests run or docs-only verification | reviewer verdict | unresolved risks | parent integration decision |
|---|---|---|---|---|---|---|---|
| investigation | deep-consultant | method body direct use is not parsed; selection ambiguity drops multi-class import fallback; render is not primary cause | none | read-only inspection | N/A | exact AST scope and arrow semantics require requirement/design | accepted into research |
| investigation | deep-consultant | plain `B()` / local var / untyped holding are not relationized; typed relations behave as existing spec | none | read-only inspection | N/A | direct use may need target resolution design separate from arrow policy | accepted into research |

#### Parent Implementation Exception

| step | delegation unavailable/impossible reason | user approval / risk acceptance | allowed files | allowed operation | rollback plan | post-change verification | reviewer gate | unavailable / denied / host conflict / waiver handling |
|---|---|---|---|---|---|---|---|---|
| research capture | issue-local research/report metadata is allowed for parent Codex under workflow policy | user requested research/scratch capture | `spec-dock/active/issue/discussions/*.md`, `spec-dock/active/issue/report.md` | create research and slim report pointer | revert this diff | `./spec-dock/scripts/spec-dock validate` | not requested for initial handoff | N/A |

#### Reviewer Gate Status

| step | gate name | reviewer role | freshness | state | risk acceptance | promotion / completion decision | notes |
|---|---|---|---|---|---|---|---|
| investigation research | initial research capture | N/A | N/A | provisional | no | continue to requirement authoring next | no implementation or final gate attempted |

#### Step Commit Gate

| step | closure state | commit scope | commit hash / final ledger | post-commit clean check | no-op rationale | no-op checked contracts / files | no-op diff-clean command | no-op read-only confirmation |
|---|---|---|---|---|---|---|---|---|
| scaffold creation | committed | new initiative / epic / issue scaffold | `a3b45aa` | clean before issue start | N/A | N/A | N/A | N/A |
| initial report capture | committed | initial detailed report before relocation | `4f1cae9` | clean after commit | N/A | N/A | N/A | N/A |
| research relocation | committed | research artifact and report pointer | `b456b02` | clean after commit | N/A | N/A | N/A | N/A |
| extended investigation | committed | research update and interview artifact | `6e92858` | clean after commit | N/A | N/A | N/A | N/A |
| requirement authoring | committed | answered interview and requirement | `98c5b70` | clean after commit | N/A | N/A | N/A | N/A |
| design-plan authoring | pending commit | design / plan / spec authoring gate evidence | pending | pending | N/A | N/A | N/A | N/A |

#### 変更したファイル

- `spec-dock/initiatives/init-00038-bugfix-direct-dependency-relations/` - new bugfix initiative scaffold.
- `spec-dock/initiatives/init-00038-bugfix-direct-dependency-relations/epics/epic-00039-small-direct-dependency-fix/` - new lightweight bugfix epic scaffold.
- `spec-dock/initiatives/init-00038-bugfix-direct-dependency-relations/epics/epic-00039-small-direct-dependency-fix/issues/iss-00040-render-direct-class-dependency/discussions/20260522t084855z-research-direct-dependency-relation-investigation.md` - direct dependency relation investigation.
- `spec-dock/initiatives/init-00038-bugfix-direct-dependency-relations/epics/epic-00039-small-direct-dependency-fix/issues/iss-00040-render-direct-class-dependency/report.md` - pointer to research and session evidence.

#### コミット

- `a3b45aa docs(spec-dock): 直接依存表示修正の作業ツリーを追加`
- `4f1cae9 docs(spec-dock): 直接依存表示の調査結果を記録`
- `b456b02 docs(spec-dock): 直接依存表示の調査をresearchへ移動`

### 2026-05-22 18:00 - 18:20 JST

#### 対象

- Step: extended investigation before requirement authoring
- AC/EC: 未作成
- Planned source:
  - ユーザー指示: 要件定義書の前に完全理解を目指し、追加調査、deep-consultant 分析、discussion docs への命文化、必要なら interview を行う。

#### 実施内容

- `diff` コマンドで、同一ファイル内 `A.make()` が `B()` を返す代表ケースを手動再現した。
- 結果、`generate` と同じく `extracted_relation_count: 0` で、`A --> B` も `A ..> B` も出ないことを確認した。
- 追加 consultant / deep-consultant の結果を research に統合した。
- 要件化前にユーザー確認が必要な product semantics を interview artifact として作成した。

#### 実行コマンド / 結果

```bash
PYTHONPATH=src python -c 'from pyclassuml.cli.main import main; raise SystemExit(main())' diff \
  --cwd /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/direct-dependency-diff-repro \
  --project-root /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/direct-dependency-diff-repro \
  --package-root /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/direct-dependency-diff-repro/pkg \
  --scope-root /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/direct-dependency-diff-repro/pkg \
  --base HEAD \
  --output /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/direct-dependency-diff-repro/diff_same_file.puml
# clean_success, extracted_class_count=2, extracted_relation_count=0, changed_class_count=2

./spec-dock/scripts/spec-dock new doc interview --issue iss-00040 --title "Direct Dependency Requirement Interview" --slug direct-dependency-requirement-interview
# ok: discussions/20260522t090118z-interview-direct-dependency-requirement-interview.md
```

#### Red/Green/Refactor Evidence

| step | phase | planned evidence requirement | observed evidence | command / inspection / manual record | result | notes |
|---|---|---|---|---|---|---|
| investigation | red/characterization | manual-required | `diff` 同一ファイル direct use でも relation 0 | CLI direct invocation | pass | build 配下の ignored manual fixture |
| investigation | synthesis | discussion-required | research に追加 matrix / diff evidence / consultant findings を追記 | research artifact | pass | requirement 前の source of truth |
| interview | decision-needed | interview-required | arrow semantics / AST scope / ambiguity / relation type の確認事項を記録 | interview artifact | pass | 回答後に requirement へ反映 |

#### Delegated Worker Evidence

| step | delegated role | delegated worker summary | changed files | tests run or docs-only verification | reviewer verdict | unresolved risks | parent integration decision |
|---|---|---|---|---|---|---|---|
| extended investigation | consultant | AST direct-use scope、MVP / defer、ユーザー確認質問を整理 | none | read-only conceptual analysis | N/A | repo inspection は未実施のため親調査で補完 | accepted with caveat |
| extended investigation | deep-consultant | black-box repro matrix / narrow AC / typed relation guard を提案 | none | read-only analysis | N/A | diff 未検証という前提は親調査で更新済み | accepted with correction |
| extended investigation | deep-consultant | renderer ではなく parse/analyze defect、direct runtime use と `uses` semantics の分離を提案 | none | read-only docs/code/tests inspection | N/A | relation type 新設 vs association 流用は未決 | accepted into interview |

#### 変更したファイル

- `spec-dock/initiatives/init-00038-bugfix-direct-dependency-relations/epics/epic-00039-small-direct-dependency-fix/issues/iss-00040-render-direct-class-dependency/discussions/20260522t084855z-research-direct-dependency-relation-investigation.md` - diff 再現、追加 matrix、consultant findings、未決論点を追記。
- `spec-dock/initiatives/init-00038-bugfix-direct-dependency-relations/epics/epic-00039-small-direct-dependency-fix/issues/iss-00040-render-direct-class-dependency/discussions/20260522t090118z-interview-direct-dependency-requirement-interview.md` - 要件化前の確認質問を記録。
- `spec-dock/initiatives/init-00038-bugfix-direct-dependency-relations/epics/epic-00039-small-direct-dependency-fix/issues/iss-00040-render-direct-class-dependency/report.md` - 追加調査の実施記録を追記。

#### コミット

- `6e92858 docs(spec-dock): 直接依存表示の追加調査と確認事項を記録`

### 2026-05-22 18:20 - 18:40 JST

#### 対象

- Step: proxy interview answer and requirement authoring
- AC/EC: `requirement.md` に初回定義
- Planned source:
  - ユーザー指示: ヒアリング質問を deep-consultant に代理回答させ、一般的な class diagram / UML の第一原理に基づく回答を要件定義書に反映する。

#### 実施内容

- deep-consultant 2名に、pyclassuml 固有の期待ではなく一般 UML class diagram の観点から interview 7項目への代理回答を依頼した。
- 両者とも、runtime direct use は association ではなく dependency として扱うべき、という判断で一致した。
- Interview artifact を `answered` に更新し、代理回答を記録した。
- `requirement.md` を作成し、runtime direct use を新 `dependency` relation type として扱い、PlantUML では `..>` を出力する要件にした。

#### Decision Summary

| topic | decision | rationale |
|---|---|---|
| `B()` / `B.factory()` | dependency `..>` | 一時的な生成・呼び出しは構造的 association ではなく UML dependency |
| `self.b = B()` | dependency evidence; composition / aggregation は推定しない | 属性保持は association 候補だが lifecycle ownership までは静的に断定できない |
| import only | relation なし | import は解決材料であり class relation の evidence ではない |
| explicit import multi-class target | 使用地点があり一意解決できる場合だけ dependency | `from target import B` は `B` を一意に選ぶが、未使用 import だけでは edge にしない |
| ambiguity | fail closed | UML edge は意味の断言であり false-positive を避ける |
| generate / diff | 共通要件 | relation semantics は出力経路で分裂させない |
| internal relation type | new `dependency` | `association` と runtime dependency の意味混同を避ける |

#### 検証

```bash
./spec-dock/scripts/spec-dock validate
# spec-dock: ok (validate) nodes=39

git diff --check
# ok
```

#### 変更したファイル

- `spec-dock/initiatives/init-00038-bugfix-direct-dependency-relations/epics/epic-00039-small-direct-dependency-fix/issues/iss-00040-render-direct-class-dependency/discussions/20260522t090118z-interview-direct-dependency-requirement-interview.md` - deep-consultant proxy answers を記録。
- `spec-dock/initiatives/init-00038-bugfix-direct-dependency-relations/epics/epic-00039-small-direct-dependency-fix/issues/iss-00040-render-direct-class-dependency/requirement.md` - dependency semantics に基づく要件定義を作成。
- `spec-dock/initiatives/init-00038-bugfix-direct-dependency-relations/epics/epic-00039-small-direct-dependency-fix/issues/iss-00040-render-direct-class-dependency/report.md` - 要件作成の根拠と検証を記録。

#### コミット

- `98c5b70 docs(spec-dock): 直接依存表示の要件定義を作成`

### 2026-05-22 18:40 - 19:20 JST

#### 対象

- Step: design / plan authoring and spec authoring gate
- AC/EC: `design.md` / `plan.md` に反映
- Planned source:
  - ユーザー指示: workflow に則り、設計書、実装計画書を作成した上で実装へ進む。

#### 実施内容

- `design.md` を作成し、既存 parse/analyze/render pipeline に沿って `dependency` relation type を追加する設計にした。
- `plan.md` を作成し、S01 model/render contract、S02 parse evidence、S03 selection target resolution、S04 generate/diff integration、S90 docs impact、S99 final quality gate に分割した。
- `spec-reviewer` に実装前 review を依頼し、2回 fail 指摘を受けた。
- 指摘を反映し、3回目の `spec-reviewer` で `review_status: pass` を得た。

#### Spec Authoring Gate Evidence

| artifact | reviewer | attempt | result | findings / action |
|---|---|---|---|---|
| requirement/design/plan | spec-reviewer | 1 | fail | AC-003〜AC-006 の generate-level evidence 不足、tc-005 の import form 不足、final exit contract placeholder、report-update gate 不足、design N/A placeholder |
| requirement/design/plan | spec-reviewer | 2 | fail | `B.CONST` の non-call class member access が plan verification に未固定、S02 planned contract の Markdown 階層不備 |
| requirement/design/plan | spec-reviewer | 3 | pass | prior concerns resolved; executable plan traces AC/EC through closure ids, step obligations, verification commands, report destinations, reviewer gates |

#### 検証

```bash
./spec-dock/scripts/spec-dock validate
# spec-dock: ok (validate) nodes=39

git diff --check
# ok

UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/model/test_contracts.py tests/render/test_document.py
# 53 passed

UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/parse/test_module_parse_and_index.py
# 38 passed

UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/analyze/test_selection.py
# 33 passed
```

#### Workflow Delegation Consent

| consent source | repo/worktree | active issue | session | named roles | boundary | expires / invalidation condition | denied / unavailable reason | next action |
|---|---|---|---|---|---|---|---|---|
| user instruction: workflow に則って実装完了と PR 作成まで依頼 | `/Users/iwasawayuuta/workspace/tools/pyclassuml` | iss-00040 | current session | spec-reviewer, code-reviewer, qa-reviewer, dev-coder, doc-writer, github-pr-merge-preparer | issue-local execution / review / PR delivery only; no destructive action outside workflow; no credentialed external use beyond GitHub PR workflow | session end / scope change / user revocation | none | proceed to S01 implementation |

#### 変更したファイル

- `spec-dock/initiatives/init-00038-bugfix-direct-dependency-relations/epics/epic-00039-small-direct-dependency-fix/issues/iss-00040-render-direct-class-dependency/design.md` - implementation design, dependency analysis, module diagram, file change plan.
- `spec-dock/initiatives/init-00038-bugfix-direct-dependency-relations/epics/epic-00039-small-direct-dependency-fix/issues/iss-00040-render-direct-class-dependency/plan.md` - executable implementation plan and closure index.
- `spec-dock/initiatives/init-00038-bugfix-direct-dependency-relations/epics/epic-00039-small-direct-dependency-fix/issues/iss-00040-render-direct-class-dependency/report.md` - spec authoring gate evidence.

### 2026-05-22 19:20 - 19:35 JST

#### 対象

- Step: S01 dependency relation contract and render mapping
- Closure ids:
  - `tc-001`
- Planned source:
  - `plan.md` S01

#### Implementation Delegation Gate

| step | decision | required reason | delegated role | delegated scope | source of truth | allowed changes | forbidden changes | required verification | stop conditions | output required | observed result |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S01 | delegated | code / runtime / tests change | dev-coder | add `dependency` relation type and render mapping | `requirement.md`, `design.md`, `plan.md` S01 | `src/pyclassuml/model/contracts.py`, `src/pyclassuml/render/document.py`, `tests/model/test_contracts.py`, `tests/render/test_document.py` | parse/analyze/app changes, existing arrow mapping changes | `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/model/test_contracts.py tests/render/test_document.py` | relation type contract requires larger schema migration | changed files, verification result, Ledger Note | completed; no material implementation decisions beyond approved plan |

#### Red / Green Evidence

| step | phase | planned evidence requirement | observed evidence | command / inspection / manual record | result | notes |
|---|---|---|---|---|---|---|
| S01 | Red | `dependency` relation type and render mapping tests fail before implementation | delegated worker reported `2 failed, 51 passed`; `SelectedRelation(..., relation_type="dependency")` rejected with `ValueError` | `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/model/test_contracts.py tests/render/test_document.py` | pass | red evidence from delegated worker |
| S01 | Green | model/render targeted tests pass after implementation | parent rerun confirmed `53 passed` | `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/model/test_contracts.py tests/render/test_document.py` | pass | dependency -> `..>` mapping included |

#### Step Contract Closure

| step | closure id | close condition | evidence | result | notes |
|---|---|---|---|---|---|
| S01 | tc-001 | dependency relation type is accepted and rendered as `..>` while existing mappings remain unchanged | targeted model/render tests passed; diff inspected by parent | pass | code-reviewer initial review found report evidence missing, not code defect |

#### Test Contract Closure

| closure id | step | evidence level | pre-implementation evidence | verification command | result |
|---|---|---|---|---|---|
| tc-001 | S01 | red-required | delegated worker observed `2 failed, 51 passed` before implementation | `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/model/test_contracts.py tests/render/test_document.py` | pass, `53 passed` |

#### Closure Coverage

| closure id | AC / EC / constraint | evidence | status |
|---|---|---|---|
| tc-001 | AC-008 / relation contract / dependency output contract | `SelectedRelation(..., "dependency", ...)` accepted; `dependency` renders `..>`; existing mapping test still passes | closed |

#### Closure Delta

| step | added | removed | changed | re-review required | notes |
|---|---|---|---|---|---|
| S01 | none | none | report status cleanup only | no | no plan amendment; code-reviewer re-review passed |

#### Reviewer Gate Status

| step | gate name | reviewer role | freshness | state | risk acceptance | promotion / completion decision | notes |
|---|---|---|---|---|---|---|---|
| S01 | code review | code-reviewer | fresh before report update | failed | no | not complete | P1: report lacked S01 closure evidence; code changes otherwise matched S01 goal |
| S01 | code review re-run | code-reviewer | fresh after report update | passed | no | S01 can be committed | P2: stale report status cleanup; addressed before commit |

#### 変更したファイル

- `src/pyclassuml/model/contracts.py` - `dependency` relation type を追加。
- `src/pyclassuml/render/document.py` - `dependency` を `..>` に mapping。
- `tests/model/test_contracts.py` - `dependency` relation type contract を追加。
- `tests/render/test_document.py` - `dependency` arrow mapping assertion を追加。
- `spec-dock/initiatives/init-00038-bugfix-direct-dependency-relations/epics/epic-00039-small-direct-dependency-fix/issues/iss-00040-render-direct-class-dependency/report.md` - S01 closure evidence を記録。

#### コミット

- `d80fb8c feat(render): dependency relation typeを追加`

### 2026-05-22 19:35 - 19:55 JST

#### 対象

- Step: S02 parse method body dependency evidence
- Closure ids:
  - `tc-002`
  - `tc-003`
- Planned source:
  - `plan.md` S02

#### Implementation Delegation Gate

| step | decision | required reason | delegated role | delegated scope | source of truth | allowed changes | forbidden changes | required verification | stop conditions | output required | observed result |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S02 | delegated | code / tests change | dev-coder | method body direct-use dependency evidence extraction | `requirement.md`, `design.md`, `plan.md` S02 | `src/pyclassuml/parse/indexer.py`, `tests/parse/test_module_parse_and_index.py` | model/render/analyze/app changes, spec-dock docs/report changes, target resolution, data-flow tracking, dynamic inference | `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/parse/test_module_parse_and_index.py` | AST scope requires data-flow/runtime import execution | changed files, Red/Green result, Ledger Note | completed; Ledger Note D-002 integrated |

#### Red / Green Evidence

| step | phase | planned evidence requirement | observed evidence | command / inspection / manual record | result | notes |
|---|---|---|---|---|---|---|
| S02 | Red | direct-use dependency parse tests fail before implementation | delegated worker reported `1 failed, 39 passed`; dependency evidence was empty | `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/parse/test_module_parse_and_index.py` | pass | red evidence from delegated worker |
| S02 | Green | parse targeted tests pass after implementation | parent rerun confirmed `40 passed` | `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/parse/test_module_parse_and_index.py` | pass | includes direct-use and skip-boundary tests |
| S02 | Regression | existing analyze/model/render tests still pass after parse evidence addition | parent ran combined targeted tests | `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/analyze/test_selection.py tests/model/test_contracts.py tests/render/test_document.py` | pass, `86 passed` | selection ignores new evidence until S03 |

#### Step Contract Closure

| step | closure id | close condition | evidence | result | notes |
|---|---|---|---|---|---|
| S02 | tc-002 | method body direct-use patterns emit deterministic dependency evidence | parse targeted tests pass; diff inspected by parent | pass | parse-side only; selection is S03 |
| S02 | tc-003 | dynamic references and nested function/lambda bodies do not become outer class dependency evidence | parse targeted tests pass | pass | false-positive guard |

#### Test Contract Closure

| closure id | step | evidence level | pre-implementation evidence | verification command | result |
|---|---|---|---|---|---|
| tc-002 | S02 | red-required | delegated worker observed `1 failed, 39 passed` before implementation | `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/parse/test_module_parse_and_index.py` | pass, `40 passed` |
| tc-003 | S02 | red-required | delegated worker observed `1 failed, 39 passed` before implementation | `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/parse/test_module_parse_and_index.py` | pass, `40 passed` |

#### Closure Coverage

| closure id | AC / EC / constraint | evidence | status |
|---|---|---|---|
| tc-002 | AC-001 / AC-005 / AC-006 parse-side | direct constructor, member access, type check, cast, local annotation, `self.b = B()` evidence extracted | closed |
| tc-003 | EC-003 / EC-004 parse-side | dynamic `getattr`, nested function, async nested function, lambda, nested class bodies skipped | closed |

#### Closure Delta

| step | added | removed | changed | re-review required | notes |
|---|---|---|---|---|---|
| S02 | none | none | none | yes | no plan amendment; code-reviewer review required |

#### Reviewer Gate Status

| step | gate name | reviewer role | freshness | state | risk acceptance | promotion / completion decision | notes |
|---|---|---|---|---|---|---|---|
| S02 | code review | code-reviewer | fresh after report update | passed | no | S02 committed | initial P2 D-002 disposition cleanup addressed before commit |

#### 変更したファイル

- `src/pyclassuml/parse/indexer.py` - method body direct-use dependency evidence extraction を追加。
- `tests/parse/test_module_parse_and_index.py` - direct-use extraction と skip-boundary tests を追加。
- `spec-dock/initiatives/init-00038-bugfix-direct-dependency-relations/epics/epic-00039-small-direct-dependency-fix/issues/iss-00040-render-direct-class-dependency/report.md` - S02 closure evidence と D-002 を記録。

#### コミット

- `aab1056 feat(parse): method bodyの直接依存evidenceを抽出`

### 2026-05-22 20:00 - 20:25 JST

#### 対象

- Step: S03 select dependency relations and resolve explicit imports
- Closure ids:
  - `tc-004`
  - `tc-005`
  - `tc-006`
- Planned source:
  - `plan.md` S03

#### Implementation Delegation Gate

| step | decision | required reason | delegated role | delegated scope | source of truth | allowed changes | forbidden changes | required verification | stop conditions | output required | observed result |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S03 | delegated | code / tests change | dev-coder | dependency evidence selection and explicit import target resolution | `requirement.md`, `design.md`, `plan.md` S03 | `src/pyclassuml/analyze/selection.py`, `tests/analyze/test_selection.py` | parse/render/app/model/spec docs/report changes, full Python resolution, data-flow, runtime import execution | `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/analyze/test_selection.py` | resolution requires import execution or out-of-scope global symbol analysis | changed files, Red/Green result, Ledger Note | completed; Ledger Note D-003 recorded |

#### Red / Green Evidence

| step | phase | planned evidence requirement | observed evidence | command / inspection / manual record | result | notes |
|---|---|---|---|---|---|---|
| S03 | Red | dependency references currently produce no relation and imported multi-class target is dropped | delegated worker reported `4 failed, 33 passed` after adding S03 tests before implementation | `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/analyze/test_selection.py` | pass | red evidence from delegated worker |
| S03 | Green | analyze targeted tests pass after implementation | parent rerun confirmed `37 passed`; after review fixes and added guard tests, parent rerun confirmed `38 passed` | `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/analyze/test_selection.py` | pass | covers dependency selection, import resolution, ambiguity, priority, reachability, import fallback priority |
| S03 | Regression | model/parse/render/analyze targeted tests still pass after selection change | parent ran combined targeted tests after review fixes | `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/model/test_contracts.py tests/parse/test_module_parse_and_index.py tests/render/test_document.py tests/analyze/test_selection.py` | pass, `131 passed` | S01/S02 contracts preserved |
| S03 | Tidy | whitespace / conflict check passes | parent ran diff check | `git diff --check` | pass | no whitespace errors |

#### Step Contract Closure

| step | closure id | close condition | evidence | result | notes |
|---|---|---|---|---|---|
| S03 | tc-004 | dependency evidence resolves to selected target class and selected relation `dependency` | same-module `B` / repeated constructor evidence test passed | pass | target class is added to selected set |
| S03 | tc-005 | explicit import, alias import, relative import, and module-qualified access resolve intended class when unique | selection fixtures with multi-class target modules passed; module-qualified fixture uses real `ast.Import` metadata shape `pkg.target` | pass | app-level module import alias path remains D-003 follow-up |
| S03 | tc-006 | ambiguous/import-only references are skipped and structural/typed relations keep priority | ambiguity/import-only/priority guard test passed | pass | dependency has lower endpoint priority than structural relations |

#### Test Contract Closure

| closure id | step | evidence level | pre-implementation evidence | verification command | result |
|---|---|---|---|---|---|
| tc-004 | S03 | red-required | delegated worker observed S03 test failures before implementation | `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/analyze/test_selection.py` | pass, `38 passed` |
| tc-005 | S03 | red-required | delegated worker observed S03 test failures before implementation | `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/analyze/test_selection.py` | pass, `38 passed` |
| tc-006 | S03 | red-required | delegated worker observed S03 test failures before implementation | `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/analyze/test_selection.py` | pass, `38 passed` |

#### Closure Coverage

| closure id | AC / EC / constraint | evidence | status |
|---|---|---|---|
| tc-004 | AC-001 / AC-006 selection-side | same-module direct constructor and `self.b = B()` equivalent evidence selects target and relation | closed |
| tc-005 | AC-002 / AC-003 / AC-004 selection-side | from-import, from-import alias, relative import, and real-metadata module-qualified access resolve to intended `B` in multi-class target module | closed with D-003 integration follow-up for `import pkg.target as target` app path |
| tc-006 | EC-001 / EC-002 / EC-005 / AC-008 | ambiguous reference warns/skips, import-only relation does not become dependency, structural relation wins over dependency | closed |

#### Closure Delta

| step | added | removed | changed | re-review required | notes |
|---|---|---|---|---|---|
| S03 | none | none | none | yes | no plan amendment yet; D-003 must be checked during S04 |

#### Reviewer Gate Status

| step | gate name | reviewer role | freshness | state | risk acceptance | promotion / completion decision | notes |
|---|---|---|---|---|---|---|---|
| S03 | code review | code-reviewer | fresh before P1/P2 fixes | failed | no | not complete | P1: dotted dependency resolved without proven import; P2: module alias fixture used metadata shape parser does not emit |
| S03 | code review re-run | code-reviewer | fresh after P1/P2 fixes | failed | no | not complete | P1: dependency target selection bypassed traversal reachability |
| S03 | code review re-run 2 | code-reviewer | fresh after reachability gate fix | failed | no | not complete | P1: module-import `uses` masked direct-use `dependency` for same endpoint |
| S03 | code review re-run 3 | code-reviewer | fresh after relation priority fix | passed | no | S03 can be committed | P2: stale verification counts; addressed before commit |

#### 変更したファイル

- `src/pyclassuml/analyze/selection.py` - dependency evidence classification、target resolution、warning diagnostics、priority を追加。
- `tests/analyze/test_selection.py` - S03 dependency selection / explicit import / alias / relative / module-qualified / ambiguity / priority tests を追加。
- `spec-dock/initiatives/init-00038-bugfix-direct-dependency-relations/epics/epic-00039-small-direct-dependency-fix/issues/iss-00040-render-direct-class-dependency/report.md` - S03 closure evidence と D-003 を記録。

#### コミット

- `c16a74b feat(analyze): 直接依存evidenceをdependency関係に変換`

### 2026-05-22 20:45 - 21:10 JST

#### 対象

- Step: S04 generate and diff integration
- Closure ids:
  - `tc-007`
  - `tc-008`
- Planned source:
  - `plan.md` S04

#### Implementation Delegation Gate

| step | decision | required reason | delegated role | delegated scope | source of truth | allowed changes | forbidden changes | required verification | stop conditions | output required | observed result |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S04 | delegated | app integration tests and possible proven integration fix | dev-coder | generate/diff direct dependency e2e coverage and D-003 confirmation | `requirement.md`, `design.md`, `plan.md` S04, report D-003 | `tests/app/test_generate.py`, `tests/app/test_diff.py`; `src/pyclassuml/parse/indexer.py` and parse tests only if app failure proves alias preservation need | CLI option/output schema changes, data-flow, runtime import execution, external package resolution | app targeted pytest and combined targeted pytest | app behavior needs CLI/API contract change | changed files, Red/Green result, D-003 conclusion | completed; D-003 resolved |

#### Red / Green Evidence

| step | phase | planned evidence requirement | observed evidence | command / inspection / manual record | result | notes |
|---|---|---|---|---|---|---|
| S04 | Red | app tests fail before integration fix | delegated worker reported `1 failed, 70 passed`; module-qualified alias import path missed `B` | `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/app/test_generate.py tests/app/test_diff.py` | pass | D-003 reproduced by app test |
| S04 | Green | generate/diff app targeted tests pass after implementation | parent rerun confirmed `71 passed` | `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/app/test_generate.py tests/app/test_diff.py` | pass | direct dependency matrix and diff added dependency pass |
| S04 | Regression | model/parse/analyze/render/app targeted tests pass together | parent rerun confirmed `203 passed` | `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/model/test_contracts.py tests/parse/test_module_parse_and_index.py tests/analyze/test_selection.py tests/render/test_document.py tests/app/test_generate.py tests/app/test_diff.py` | pass | S01-S04 contracts preserved |
| S04 | Tidy | whitespace and path policy checks pass | parent ran diff check and uppercase path scan | `git diff --check`; `rg --files | rg '[A-Z]'` | pass | uppercase scan returned only existing `AGENTS.md` / `README.md` paths |
| S04 follow-up | QA Red | shadowed method-local names must not create false-positive direct-call dependency | parent added shadowing parse/app tests and confirmed failures: parse `1 failed, 41 passed`; generate `1 failed, 14 passed` | `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/parse/test_module_parse_and_index.py -q`; `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/app/test_generate.py -q` | pass | QA P1 direct-call reproduced |
| S04 follow-up | QA Red 2 | shadowed method-local names must not create false-positive member-access dependency | parent extended shadowing tests and confirmed failures in focused parse/app tests | focused parse/app pytest | pass | QA P1 member-access reproduced |
| S04 follow-up | QA Red 3 | qualified dependency targets must survive same-named method-local terminal shadowing | parent added `target.B()` / `target.B.CONST` tests and confirmed parse focused failure before guard refinement | focused parse pytest | pass | QA P1 qualified false-negative reproduced |
| S04 follow-up | QA Red 4 | shadowed method-local names must not create false-positive type-check, cast, or local-annotation dependency | parent extended shadowing tests and confirmed focused parse/app failures before filter expansion | focused parse/app pytest | pass | QA P1 AC-005 shadowing reproduced |
| S04 follow-up | Code Review Red | match capture names must shadow bare dependency evidence | parent added match capture case and confirmed focused parse failure before pattern capture support | focused parse pytest | pass | code-reviewer P2 addressed |
| S04 follow-up | QA/Review Green | bare shadowed direct use/type-spec evidence is skipped while qualified targets survive and existing contracts pass | parent rerun confirmed focused parse/app pass, combined targeted `207 passed`, full suite `434 passed` | `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest` | pass | D-004 resolved |

#### Step Contract Closure

| step | closure id | close condition | evidence | result | notes |
|---|---|---|---|---|---|
| S04 | tc-007 | `generate` renders direct dependency `..>` end-to-end for AC-001 through AC-006 visible cases | generate app direct dependency matrix passed | pass | same-file, explicit import, from-import alias, module-qualified alias, type/spec, self assignment |
| S04 | tc-008 | `diff` renders added direct dependency with common relation semantics | diff app added dependency test passed | pass | changed source class is decorated and dependency target is rendered |

#### Test Contract Closure

| closure id | step | evidence level | pre-implementation evidence | verification command | result |
|---|---|---|---|---|---|
| tc-007 | S04 | red-required | delegated worker observed `1 failed, 70 passed` before parse alias fix | `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/app/test_generate.py tests/app/test_diff.py` | pass, `71 passed` |
| tc-008 | S04 | red-required | delegated worker observed S04 app tests before integration fix | `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest tests/app/test_generate.py tests/app/test_diff.py` | pass, `71 passed` |

#### Closure Coverage

| closure id | AC / EC / constraint | evidence | status |
|---|---|---|---|
| tc-007 | AC-001 / AC-002 / AC-003 / AC-004 / AC-005 / AC-006 | generate app matrix renders `..>` for direct constructor, explicit import, from-import alias, module-qualified alias/member access, type/spec dependency, and `self.b = B()` without structural relation | closed |
| tc-008 | AC-007 | diff app renders added same-file direct dependency as `..>` | closed |
| D-003 | app integration risk | `import pkg.target as target; target.B` failed before parse alias preservation and passed after alias text was preserved | resolved |
| D-004 | EC-001 / EC-003 false-positive guard / AC-004 / AC-005 | bare parameter/local assignment/local function/match capture shadowing tests fail before fix and pass after shadow skip; qualified `target.B` survives same terminal shadowing | resolved |

#### Closure Delta

| step | added | removed | changed | re-review required | notes |
|---|---|---|---|---|---|
| S04 | parse alias preservation; method-local bare shadow guard | none | `ast.Import` text now preserves `as` alias; shadowed bare direct use/type-spec evidence no longer emits dependency evidence; qualified targets survive same terminal shadowing | yes | app red evidence proved D-003; final QA proved D-004 |

#### Reviewer Gate Status

| step | gate name | reviewer role | freshness | state | risk acceptance | promotion / completion decision | notes |
|---|---|---|---|---|---|---|---|
| S04 | code review | code-reviewer | fresh after report update | passed | no | S04 can be committed | findings: none |

#### 変更したファイル

- `src/pyclassuml/parse/indexer.py` - `ast.Import` alias text を import candidate key と module imports に保持し、method-local shadowed bare direct use/type-spec evidence を dependency evidence から除外。
- `tests/parse/test_module_parse_and_index.py` - module import alias text preservation、shadowed bare dependency、qualified target preservation の regressions を追加。
- `tests/app/test_generate.py` - generate direct dependency matrix、shadowing false-positive、qualified target preservation の regressions を追加。
- `tests/app/test_diff.py` - diff added direct dependency regression を追加。
- `spec-dock/initiatives/init-00038-bugfix-direct-dependency-relations/epics/epic-00039-small-direct-dependency-fix/issues/iss-00040-render-direct-class-dependency/report.md` - S04 closure evidence と D-003 resolution を記録。

#### コミット

- `02c8ccd feat(app): 直接依存のgenerateとdiff出力を固定`

## Final Quality Gate

この issue は S04 まで実装済みであり、S90 / S99 を実施中。

### S90 Docs Impact Resolution

| target | update required | owner | evidence | spec-reviewer result |
|---|---|---|---|---|
| README / user docs | no | parent inspection | `README.md` は概要、CLI、境界、設定、出力の説明のみで relation arrow semantics の表や直接依存の個別契約を持たない | pending |
| spec-dock docs / templates / workflow / skills | no | parent inspection | `spec-dock/docs` は SpecDock workflow / dependency graph docs であり PyClassUML relation semantics の user-facing docs ではない | pending |

### S99 Validation Evidence

| validation | command | result | notes |
|---|---|---|---|
| full test suite | `UV_CACHE_DIR=/private/tmp/pyclassuml-uv-cache uv run pytest` | pass, `434 passed` | all tests after QA shadowing / qualified-target fix |
| SpecDock validate | `./spec-dock/scripts/spec-dock validate` | pass, `nodes=39` | after S04 commit and report update precheck |
| SpecDock sync | `./spec-dock/scripts/spec-dock sync` | pass, active unchanged / generated state already clean | no generated diff remained |
| diff check | `git diff --check` | pass | S04 pre-commit and final report update precheck |

### Final QA Gate

| reviewer | scope | integration test decision | evidence | result |
|---|---|---|---|---|
| qa-reviewer | whole issue obligation coverage | generate/diff app integration covered by S04; full suite passed | initial fail P1 shadowing false-positive; second fail P1 shadowed member access; third fail P1 qualified-target false-negative; fourth fail P1 shadowed type/spec evidence; D-004 fix added parse/app red-green tests | pass |

### Final Code Review Gate

| reviewer | scope | findings / fixes | re-review count | result |
|---|---|---|---|---|
| code-reviewer | issue-wide integrated diff | pass with P2 findings: match capture shadowing and stale final QA ledger; both addressed before final commit | 1 | pass |

### Final Spec Review Gate

| reviewer | scope | findings / fixes | re-review count | result |
|---|---|---|---|---|
| spec-reviewer | requirement / design / plan / report / implementation / tests / docs alignment | pass with P2 finding: stale trailing status notes; addressed before final commit | 1 | pass |

### Final Commit

| final report ledger | final commit scope | post-commit external evidence destination | result |
|---|---|---|---|
| committed | report final gate cleanup plus D-004 follow-up implementation/tests | final response / PR body | `5be1720` |

### PR Delivery Gate

| PR | base | head branch / SHA | issue linkage | creation route | result |
|---|---|---|---|---|---|
| `https://github.com/chemitaro/pyclassuml/pull/41` | `main` from `origin/HEAD` | `iss-00040-render-direct-class-dependency` / `5be1720` | `Closes #40` in PR body | `gh pr create` / GitHub connector were blocked by local uv cache permission; created through GitHub REST API after branch push | created |

### Merge Preparation Gate

| source | evidence | result | notes |
|---|---|---|---|
| GitHub Actions | PR check `validate` observed in progress on initial PR head | pending | final check state must be re-monitored after PR report commit push |

## 遭遇した問題と解決

- 問題: `uv run pyclassuml --help` が uv cache path の `Operation not permitted` で失敗した。
  - 解決: CLI を `PYTHONPATH=src python -c 'from pyclassuml.cli.main import main; raise SystemExit(main())' ...` で直接起動して再現した。
- 問題: `issue start iss-00040` が scaffold 未コミットのため checkout safety で失敗した。
  - 解決: scaffold 作成分のみをコミットし、再度 `issue start` を実行して成功した。
- 問題: 調査本文を `report.md` に寄せすぎていた。
  - 解決: issue discussion の research artifact に移し、report は参照と運用ログに薄く戻した。

## 今後の推奨事項

- S90/S99 validation and reviewer gates are complete.
- 次は final report commit、PR delivery gate、merge preparation gate、`issue finish` を実施する。

## 省略/例外メモ

- PR gate と lifecycle finish は final report commit 後に実施する。
