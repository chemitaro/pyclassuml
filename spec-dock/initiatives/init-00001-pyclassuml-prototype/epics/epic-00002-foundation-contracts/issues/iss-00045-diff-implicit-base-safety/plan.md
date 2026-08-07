---
種別: 実装計画書（Issue）
ID: "iss-00045"
タイトル: "Diff Implicit Base Safety"
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-08-07"
依存: ["requirement.md", "design.md"]
親: ["epic-00002", "init-00001"]
---

# iss-00045 Diff Implicit Base Safety — 実装計画（TDD / Verification）

## 0. 実装方針

本 Issue は次の順序で実装する。

1. concrete requirement/design/plan に基づき assurance grade を再分類する。
2. 現行 baseline を実行し、既存 failure と本 Issue の intentional Red を分離する。
3. base resolution を fail-closed contractへ変更する。
4. raw entry collection と hunk enrichmentを分離し、implicit breadth guardを追加する。
5. targets seamへ scope-only diagnosticを追加する。
6. app/report/CLI integrationを確認する。
7. README、help、`iss-00036` supersede、`iss-00044` cross-referenceを更新する。
8. focused、cross-Issue、full verificationを実行する。
9. 全 evidenceを Issue #45 `report.md` に記録する。

実装上の固定点は次のとおりとする。

* base resolverは、暗黙解決時の `config.diff_current_state` を唯一の state authorityとし、raw CLI optionを再参照しない。
* HEADは開始時に `HEAD^{commit}` から一度だけ実体SHAへ解決し、default-branch HEAD基点と feature/detached の merge-base候補の両方で同じSHAを使う。
* explicit baseは `<ref>^{commit}` が解決できる Git revision expression とし、name-status収集後の implicit breadth guardを迂回する。
* tracked raw entryのVCS相対pathを保持したまま件数を確定し、guard後にhunkを取得する。nested project、rename、scope boundaryではpublic DTOのproject-relative pathとVCS pathspecを混同しない。
* Git subprocessは `GIT_NO_LAZY_FETCH=1` と外部diff/textconv無効化を共通で適用し、未対応Gitではfail closedする。

本計画は実行済みを意味しない。本書作成時点では test、benchmark、SpecDock commandを実行していない。

## 1. 実装開始条件

### 1.1 必須条件

* [ ] Issue #45 requirement/design/plan が review可能な concrete stateにある。
* [ ] placeholder、`...`、未置換 `XXX` が残っていない。
* [ ] public CLI behavior changeを含むため Strict相当のassurance再分類結果が記録されている。
* [ ] `iss-00036` supersede範囲が承認されている。
* [ ] `iss-00044` の depth/config authorityを変更しないことが確認されている。
* [ ] limit `1000` と explicit bypassが仕様として承認されている。
* [ ] baseline source commitと対象 branch HEADが記録されている。
* [ ] `report.md` にTDD・verification evidenceの記録先がある。
* [ ] baseline test failureがある場合、その原因と本Issueとの関係が分類されている。

### 1.2 Assurance

現行 Issue #45 の provisional metadata は、具体化前の template factsを基に standard分類されている可能性がある。次を実行し、concrete docsに対して再評価する。

* `./spec-dock/scripts/spec-dock assurance classify --stage requirement`
* repositoryの現行SpecDock workflowが要求する場合は、続けて適切な compose / review command
* `./spec-dock/scripts/spec-dock validate`
* `./spec-dock/scripts/spec-dock doctor`

実際の command surface が異なる場合は、`./spec-dock/scripts/spec-dock --help` と repository guideを正本として確認する。CLI-managed projectionを手編集してはならない。

公開 CLI 成功条件の変更、diagnostic code追加、resource guardを concrete factsとして分類入力へ反映する。

## 2. 変更面

### 2.1 許可する production change

| path                                 | 許可内容                                                             |
| ------------------------------------ | ---------------------------------------------------------------- |
| `src/pyclassuml/vcs/diff_collect.py` | base resolver、raw collection、guard、hunk ordering、VCS diagnostics |
| `src/pyclassuml/model/contracts.py`  | `default_branch_head` kind追加                                     |
| `src/pyclassuml/targets/diff.py`     | scope-only分類、generic message                                     |
| `src/pyclassuml/cli/bind.py`         | help / descriptionのみ                                             |
| `README.md`                          | user contract、migration、diagnostics                              |

### 2.2 原則変更不要

| path                                  | 扱い                                            |
| ------------------------------------- | --------------------------------------------- |
| `src/pyclassuml/app/diff.py`          | testsで既存transportが不足すると確認されるまで変更しない           |
| `src/pyclassuml/report/policy.py`     | 既存failure reason projectionが不足すると確認されるまで変更しない |
| `src/pyclassuml/model/__init__.py`    | 新型を追加しないため変更しない                               |
| `src/pyclassuml/config/resolver.py`   | 変更禁止                                          |
| `src/pyclassuml/analyze/traversal.py` | 変更禁止                                          |
| `src/pyclassuml/parse/*`              | 変更禁止                                          |
| `src/pyclassuml/render/*`             | 変更禁止                                          |

app/report changeが必要になった場合、先に次を行う。

1. failing focused testを記録する。
2. 既存 transportで成立しない理由を `report.md` に記録する。
3. `design.md` の change surface と interface contractを改訂する。
4. 変更を最小transport差分に限定する。

### 2.3 許可する tests

* `tests/model/test_contracts.py`
* `tests/vcs/test_diff_file_collect.py`
* `tests/targets/test_diff_target_normalize.py`
* `tests/app/test_diff.py`
* `tests/report/test_policy.py`
* `tests/cli/test_bind.py`
* `tests/cli/test_main.py`
* `tests/config/test_context_resolve.py`
* `tests/app/test_generate.py`
* `tests/analyze/test_traversal.py`
* `tests/parse/test_module_parse_and_index.py`

### 2.4 許可する SpecDock / docs

* Issue #45 canonical docs / report
* Issue #36 requirement/design/plan の supersede note
* Issue #44 requirement/design/plan の authority cross-reference
  -必要な場合の parent Epic plan注記
* CLI-managed active projectionは正規 commandによる再生成だけを許可

### 2.5 禁止変更

- 新 CLI flag
- 新 TOML key
- 環境変数によるlimit設定
- 自動 fetch / deepen

* target repository sourceの変更
* Git branch/index/working-tree mutation
* `FailureReason`追加
* `TargetObservations` field追加
* config / traversal algorithm変更
* full HEAD snapshot rendering
* unrelated format-only mass change
* baseline lint driftの一括修正
* Issue #36の履歴削除または過去契約の無言書換え

## 3. マイルストーン

| Milestone | 成果                                 | 主なBehavior  | Gate                         |
| --------- | ---------------------------------- | ----------- | ---------------------------- |
| M0        | baseline・assurance・Red管理           | B-001〜B-003 | baseline / classify          |
| M1        | implicit base contract             | B-004〜B-009 | model + VCS focused          |
| M2        | changed-path breadth guard         | B-010〜B-013 | VCS guard focused            |
| M3        | scope-only diagnosis               | B-014〜B-017 | targets + app focused        |
| M4        | CLI/docs/compatibility             | B-018〜B-021 | CLI transcript / docs review |
| M5        | integration・cross-Issue regression | B-022〜B-025 | app/config/traversal         |
| M99       | final quality gate                 | all         | full suite / SpecDock / diff |

## 4. 振る舞いバックログ

| ID    | Milestone | 振る舞い                                            | 依存           |
| ----- | --------- | ----------------------------------------------- | ------------ |
| B-001 | M0        | 現行 suite baselineを記録する                          | none         |
| B-002 | M0        | 旧 fallback testsをcharacterizationとして確認する        | B-001        |
| B-003 | M0        | concrete docsでStrict相当を再分類する                    | B-001        |
| B-004 | M1        | `default_branch_head` kindを受理する                 | B-001        |
| B-005 | M1        | default branch working-treeがHEAD SHAを使う         | B-004        |
| B-006 | M1        | stale remote defaultを使わない                       | B-005        |
| B-007 | M1        | default branch head no-baseが専用failureになる        | B-005        |
| B-008 | M1        | feature/detached merge-baseを維持する                | B-005        |
| B-009 | M1        | candidate解決不能でinitial fallbackせず失敗する            | B-008        |
| B-010 | M2        | raw entry collectionとhunk enrichmentを分離する       | B-005        |
| B-011 | M2        | implicit 1,000件境界を実装する                          | B-010        |
| B-012 | M2        | guardがhunk/downstream前に停止する                     | B-011        |
| B-013 | M2        | explicit baseがguardを迂回する                        | B-011        |
| B-014 | M3        | Python changed totalとscope-excluded Pythonを区別する | B-001        |
| B-015 | M3        | scope-only専用codeを返す                             | B-014        |
| B-016 | M3        | generic zero-target casesを維持する                  | B-014        |
| B-017 | M3        | counter、diagnostic順序、base summaryを維持する          | B-015        |
| B-018 | M4        | CLI helpに短い契約を追加する                              | B-007        |
| B-019 | M4        | READMEをdecision tableへ更新する                      | B-011, B-015 |
| B-020 | M4        | Issue #36へ部分supersedeを記録する                      | B-009        |
| B-021 | M4        | Issue #44へauthority cross-referenceを記録する        | B-009        |
| B-022 | M5        | app / CLI end-to-endで新契約を確認する                   | B-013, B-017 |
| B-023 | M5        | depth変更でbase/seed不変を確認する                        | B-022        |
| B-024 | M5        | read-only / clone safetyを確認する                   | B-022        |
| B-025 | M5        | legacy DTO/report compatibilityを確認する            | B-004        |
| B-026 | M99       | full suiteとpatch qualityを通す                     | all          |
| B-027 | M99       | SpecDock validate/doctorとevidence ledgerを閉じる    | B-026        |

## 5. TDD 実行計画

### 5.1 Cycle M0-C1 — baseline

#### Red前確認

変更前に次を実行し、現行 baselineを `report.md` に記録する。

* `uv run pytest -q tests/model/test_contracts.py`
* `uv run pytest -q tests/vcs/test_diff_file_collect.py`
* `uv run pytest -q tests/targets/test_diff_target_normalize.py`
* `uv run pytest -q tests/app/test_diff.py`
* `uv run pytest -q tests/report/test_policy.py`
* `uv run pytest -q tests/cli/test_bind.py tests/cli/test_main.py`
* `uv run pytest -q tests/config/test_context_resolve.py`
  -可能なら `uv run pytest -q`

baseline非0の場合は、次へ分類する。

-既存 regression
-環境・dependency failure
-今回変更予定の旧契約 test
-不明 failure

不明 failureを残したまま production changeへ進まない。

#### Characterization

次の旧期待が現行で成立することを確認する。

* current default branch no-base が `initial_commit_fallback`
* no-candidate feature branchが fallback warning付き成功
* targets all-scope-outsideが generic zero-target
* modelが `initial_commit_fallback` を受理

この結果は採用契約ではなく、変更前baselineとして記録する。

### 5.2 Cycle M1-C1 — model kind

#### Red

`tests/model/test_contracts.py` に次を追加する。

* `DiffBaseResolution(... resolution_kind="default_branch_head")` がvalid
* unknown kindはinvalid
* `initial_commit_fallback` はlegacyとしてvalid

`default_branch_head` が現行許可集合にないことによるRedを確認する。

#### Green

`_DIFF_BASE_RESOLUTION_KINDS` に `default_branch_head` だけを追加する。

#### Refactor / local gate

* public fieldを追加していないことをdiff reviewする。
* `uv run pytest -q tests/model/test_contracts.py`

### 5.3 Cycle M1-C2 — default branch working-tree

#### Red

`tests/vcs/test_diff_file_collect.py` に、default branch上に複数 historical commitsを持ち、最新HEAD後に一件だけworking-tree変更を加えるcaseを追加する。

期待:

* entriesはworking-tree変更だけ
* resolved baseは開始時に一度だけ解決した `HEAD^{commit}` のSHA
* kind=`default_branch_head`
* candidate=`None`
* fallback warningなし
* stale `origin/<default>` の過去changesを含めない

main、developの少なくとも一方を実case、他方をparameterizedまたはdefault-detection unit caseで固定する。

slashful default branch + `origin/HEAD` caseも旧 fallback expectationからHEAD expectationへ置き換える。

#### Green

`_resolve_base_ref` に解決済みconfigの `current_state` を渡し、default branch working-tree pathを追加する。`request.cli_options.diff.current_state` を再参照しない。

開始時 HEAD SHAを一度だけ解決し、resolved baseと merge-base candidateの両方へ使う。merge-base引数に象徴名 `HEAD` を渡さない。

#### Refactor / local gate

* explicit pathが先頭であること
* initial commit helperがこのpathから呼ばれないこと
* default branch判定と `origin/HEAD` / conventional branchの不一致が仕様どおりに扱われること
* `uv run pytest -q tests/vcs/test_diff_file_collect.py -k 'default_branch or explicit_base'`

### 5.4 Cycle M1-C3 — default branch head failure

#### Red

default branch、no-base、`current_state=head` で次を期待する testを追加する。

* collection `None`
* code=`diff_default_branch_head_requires_base`
* severity error
* failure reason `VCS_READ_FAILURE`
* `git diff` 未実行

`_run_git` spyで `diff` commandが呼ばれないことを確認する。

app testでは targets、parse、traversal、renderが呼ばれないことを確認する。

#### Green

default branch判定後、stateがHEADなら専用 `VcsDiffError` を返す。

#### Local gate

* `uv run pytest -q tests/vcs/test_diff_file_collect.py -k 'default_branch and head'`
* `uv run pytest -q tests/app/test_diff.py -k 'default_branch and head and base'`

### 5.5 Cycle M1-C4 — unresolved implicit base

#### Red

次の旧 fallback testを、新しい failure expectationへ置き換える。

* feature branch、candidateなし
* feature branch、candidateはあるが全merge-base失敗
* detached HEAD、candidateなし
* candidateが複数あっても全候補が失敗した場合に `rev-list` を呼ばない

期待:

* code=`diff_base_resolution_unavailable`
* initial fallback diagnosticなし
* targets/hunk collectionなし
* exit 1 at app/CLI

feature/detachedでcandidateありの既存merge-base casesはGreenのまま維持する。

#### Green

candidate loop終了後に initial commit helperを呼ばず、専用 errorを返す。legacy helperやlegacy DTO kindを残す場合も、productionの implicit pathからは呼び出さない。

production pathから `_initial_commit_base_resolution` と `_initial_commit_fallback_diagnostic` を切り離す。historical DTO/report testが必要とする `initial_commit_fallback` の受理は維持する。

#### Local gate

* `uv run pytest -q tests/vcs/test_diff_file_collect.py -k 'no_base or merge_base or candidate or detached'`
* `uv run pytest -q tests/app/test_diff.py -k 'no_base and unavailable'`
* `uv run pytest -q tests/cli/test_main.py -k 'no_base and unavailable'`

### 5.6 Cycle M1-C5 — explicit compatibility

#### Red / characterization

次を確認・必要なら補強する。

* valid branch/tag/commit/`HEAD~1`
* invalid ref
* tree/blobなど commitへ解決できないobject
* explicit `HEAD` + head state
* explicit baseがdefault branch policyを迂回
* invalid baseがfallbackしない

revision expressionは `<requested>^{commit}` で commitへ解決できるものに限定し、解決できないobjectは明確にinvalidとする。requested文字列は結果・診断に保持する。

#### Green

explicit pathを最小変更で維持する。

#### Local gate

* `uv run pytest -q tests/vcs/test_diff_file_collect.py -k 'explicit or invalid_base'`
* `uv run pytest -q tests/app/test_diff.py -k 'invalid_base or explicit'`
* `uv run pytest -q tests/cli/test_main.py -k 'invalid_base'`

## 6. Breadth guard 実装計画

### 6.1 Cycle M2-C1 — raw/hunk分離

#### Red

`_run_git` または hunk helper spyを用いて、raw name-status取得後・hunk取得前に entry countを観測できる seamを要求する testを追加する。

このcycleではobservable outputを変えず、既存casesが同じ entries / rangesを返すことを確認する。

#### Green

tracked collectionを次へ分離する。

* raw name-status parse / project boundary
* guard後の line-range enrichment

raw carrierにはVCS root相対のcurrent/previous pathとchange kindを保持し、project-relative pathはdedupe/count用のprivate keyとして導出する。public `ChangedFileEntry` はhunk enrichment後にだけ生成する。

rename、deleted-only、type change、UTF-8 failure、parse failureの既存 behaviorを維持する。

#### Refactor gate

* `uv run pytest -q tests/vcs/test_diff_file_collect.py`
* raw helperがscope、suffix、ignoreを参照していないことをsource review
* hunk helperがguard前に呼ばれない構造であることをsource review
* nested projectのmodified/renameでhunk pathspecがVCS-relative、public pathがproject-relativeになること

### 6.2 Cycle M2-C2 — limit

#### Red

production定数を monkeypatch可能なmodule constantとして想定し、limit `1` のtestを追加する。

ケース:

* implicit一件: success
* implicit二件: `diff_implicit_range_too_broad`
* messageにresolved base、actual `2`、limit `1`、`--base` hint
* hunk helper call count `0`
* nested modified/rename caseでも guardはVCS pathの件数確定後に発火する

別caseでproduction値のboundaryを、synthetic raw entriesまたはprivate helper unitで次のように固定する。

* 1,000: pass
* 1,001: fail

巨大な1,001-file Git fixtureを常用testにしない。

#### Green

`MAX_IMPLICIT_DIFF_CHANGED_PATHS = 1000` とpredicateを追加する。

#### Local gate

* `uv run pytest -q tests/vcs/test_diff_file_collect.py -k 'implicit_range or changed_path_limit'`

### 6.3 Cycle M2-C3 — count semantics

parameterized testで次を固定する。countはimplicit name-status collectionのraw changed pathsに対して行い、scope filter・ignore filter・hunk enrichmentより前に確定する。

| entry                    |    count |
| ------------------------ | -------: |
| tracked added            |        1 |
| modified                 |        1 |
| renamed previous→current |        1 |
| included untracked       |        1 |
| ignored untracked        |        0 |
| project root内 / scope root外 |     1 |
| project root外            |        0 |
| non-Python                |        1 |
| ignore予定                |        1 |
| deletion-only file        |        0 |
| duplicate current path    | dedupe後1 |

`current_state=head` + `include_untracked=true` は既存 warningを出すが、untrackedをcountしない。ignored untrackedは `git ls-files --others --exclude-standard` の結果に含めず、project root外はscope root判定前に除外する。

### 6.4 Cycle M2-C4 — explicit bypass

#### Red

同じ二件rangeで次を比較する。

* no-base + limit1: failure
* `--base <same-sha>` + limit1: guardを迂回してcollection続行

invalid explicit baseはguardより先に `invalid_base_ref` となることも確認する。

#### Green

guard predicateを `requested_base_ref is None` に限定する。

#### Local gate

* `uv run pytest -q tests/vcs/test_diff_file_collect.py -k 'implicit_range or explicit'`

### 6.5 App stop test

`tests/app/test_diff.py` で guard failure時に次が呼ばれないことをspyする。

* `normalize_diff_targets`
* `parse_target_set`
* `traverse_dependencies`
* `render_uml_document`

期待:

* hard failure
* exit 1
* failure reason `VCS_READ_FAILURE`
* diagnostic code `diff_implicit_range_too_broad`
* artifactなし

## 7. Scope-only diagnostic 実装計画

### 7.1 Cycle M3-C1 —専用分類

#### Red

`tests/targets/test_diff_target_normalize.py` に次を追加する。

1. outside `.py` だけ

   * `diff_scope_exclusion`
   * `diff_zero_target_scope_excluded_only`
2. outside `.py` + inside non-Python

   * scope-only code
3. outside `.py` + inside ignored `.py`

   * generic code
4. non-Python only

   * generic code
5. ignored `.py` only

   * generic code
6. no entries

   * generic code
7. inside `.py` 一件以上

   * success
8. outside non-Pythonだけ

   * generic code

既存 `assert_zero_target_failure` helperはexpected codeを引数化する。

Python changed totalが1以上で、その全てが project root内かつ scope root外、seedが0の場合だけ `diff_zero_target_scope_excluded_only` を返す。project root外、non-Pythonのみ、ignore後に0件となるケースは専用分類に含めない。

#### Green

seam-local Python countsとcode selectionを追加する。

#### Refactor / local gate

* public `TargetObservations`を変更していないこと
* `diff_scope_excluded_count` の旧意味を維持すること
* `uv run pytest -q tests/targets/test_diff_target_normalize.py`

### 7.2 Cycle M3-C2 — app/report projection

app fixtureで、outside Pythonだけのcaseを実行する。

期待:

* hard failure
* exit 1
* failure reason `DIFF_ZERO_TARGET_AFTER_SCOPE_FILTER`
* `diff_scope_excluded_count > 0`
* `diff_scope_exclusion` warning
* `diff_zero_target_scope_excluded_only` error
* successful base resolution metadataがstderr summaryに残る
* parse/traversal/render未実行
* artifactなし

generic zero-target app testsは既存 codeのまま維持する。

## 8. CLI / report / model integration

### 8.1 App tests

追加・置換するcase:

* default branch historical commits + working-tree一件
* stale origin default
* slashful default
* default branch head no-base failure
* default branch head + explicit `HEAD~1` success
* feature merge-base working-tree
* feature merge-base head
* feature no-candidate failure
* implicit guard failure
* explicit guard bypass
* scope-only target failure
* read-only state
* nested project / monorepo
* untracked inclusion
* rename
* depth invariance
* configで解決した `diff_current_state` とraw CLI stateが異なる場合のauthority
* changed-path count後にhunk/downstreamへ進まないこと

### 8.2 CLI tests

`tests/cli/test_main.py` と console-script boundaryで次を確認する。

| command                                                  | 期待                                 |
| -------------------------------------------------------- | ---------------------------------- |
| `pyclassuml diff` on default branch with worktree change | success、`default_branch_head`      |
| `pyclassuml diff --current-state head` on default branch | exit 1、requires-base code          |
| `pyclassuml diff --current-state head --base HEAD~1`     | explicit success                   |
| `pyclassuml diff` on unresolved feature                  | exit 1、resolution-unavailable code |
| implicit over-limit                                      | exit 1、range-too-broad code        |
| scope外Pythonのみ                                           | exit 1、scope-only code             |
| invalid explicit base                                    | 既存 exit 1、invalid-base code        |

CLI parser/bindについては、新surfaceがないため次を維持する。

* base未指定→`None`
* empty base rejected
* current-state presence metadata
* include-untracked presence metadata
* depth未指定→raw `None`

help testで次の語義を確認する。

* explicit base
* implicit base
* default branch working-tree / HEAD
* default branch head requires explicit base

help全文のgolden化は避け、重要phraseだけをassertする。

### 8.3 Report tests

`tests/report/test_policy.py` では次を確認する。

* `default_branch_head` をgeneric summaryが表示
* `explicit_base` を維持
* `default_branch_merge_base` を維持
* manually constructed legacy `initial_commit_fallback` のsummaryを維持
  -新VCS errorは `VCS_READ_FAILURE` によりhard failure
* scope-only errorは既存 target failure reasonによりhard failure

report production codeを変更せずGreenになることを優先する。

## 9. `iss-00044` 回帰計画

### 9.1 Config focused tests

* `uv run pytest -q tests/config/test_context_resolve.py`
* `uv run pytest -q tests/cli/test_bind.py`
* `uv run pytest -q tests/app/test_generate.py`
* `uv run pytest -q tests/analyze/test_traversal.py`
* `uv run pytest -q tests/parse/test_module_parse_and_index.py`

確認事項:

* diff default depth `1`
* generate default `None`
* CLI `depth=0`
* command section override
* top-level fallback
* Diff固有config
* path semantics
* config resolver production diffなし

### 9.2 Base / seed / traversal 分離test

同じ feature branch fixtureで depth `0`、`1`、`2` を実行し、次を個別assertする。

* `DiffBaseResolution` は同一
* changed entry paths は同一
* seed files は同一
* reachable filesだけがdepthに応じて変わる

default branch working-tree fixtureでも、depth変更が `default_branch_head` resolutionを変えないことを確認する。

### 9.3 Issue #44 文書

Issue #44 requirement/design/plan のVCS regression記述を、次のauthority noteで補正する。

* Issue #44 は depth/config implementation時点でVCSを変更しなかった。
  -後続 Issue #45 が implicit-base safetyを変更する。
* Issue #44 のdepth/config acceptanceは維持する。
* Issue #44 の regression expectationから「initial fallbackを永久に維持」を読み取らない。

## 10. `iss-00036` migration 計画

### 10.1 文書更新

Issue #36 requirement/design/plan の冒頭付近に次を追加する。既存本文と既存report/evidenceは削除・書換えせず、歴史的契約として保持する。

* superseded-by: `iss-00045-diff-implicit-base-safety`
* supersede対象:

  * default branch initial fallback
  * unresolved candidate initial fallback
  * fallback degraded success
  * production initial fallback kind
    -維持対象:
  * optional base
  * explicit authority
  * invalid explicit failure
  * feature merge-base
  * resolution transport
  * read-only/current-state/untracked

requirement、design、planの3文書すべてで同じsupersede境界を示し、Issue #36の旧acceptanceが現行のimplicit-base採用契約であると誤読できないようにする。

既存本文を削除せず、historical decisionとして保持する。

### 10.2 Tests migration

次の旧testsは削除ではなく、新契約へrename・置換する。

* `test_no_base_without_usable_candidate_uses_initial_commit_fallback`
* `test_no_base_current_slashful_default_branch_uses_initial_commit_fallback`
* `test_no_base_initial_fallback_is_degraded_success_with_base_metadata`

置換後はそれぞれ次を表す。

* unavailable failure
* slashful default uses HEAD
* default branch working-tree clean success with HEAD metadata

legacy model/report construction testは残す。

## 11. README / help 計画

### 11.1 README decision table

README の `diff` 節へ、requirementのbranch/state matrixと同等の表を追加する。

### 11.2 必須説明

* explicit `--base` の authority
* invalid explicit baseのfailure
* default branch working-treeのHEAD base
* default branch headのexplicit-base requirement
* feature/detached merge-base
* no initial fallback
* local candidate/history不足時のfailure
* no automatic fetch/deepen
* implicit path limit `1000`
* count対象
* exact limitは許可、超過はfailure
* resolved SHAのexplicit指定でopt-in可能
* explicit rangeは高負荷になり得る
* scope-only diagnostic
* base summary fields
* legacy `initial_commit_fallback`
* `current_state=head` のworking-tree rendering caveat
* depthはbase/seedを減らさない
* `GIT_NO_LAZY_FETCH=1`、`--no-ext-diff --no-textconv --no-color`、partial cloneでのfail-closed

### 11.3 Examples

少なくとも次を掲載する。

* default branchのworking-tree diff
  -最後のcommitを明示比較する `--base HEAD~1 --current-state head`
* remote-tracking defaultとの差を明示する `--base origin/main`
* range-too-broad diagnosticに示されたSHAを explicit baseとして再実行する方法

### 11.4 CLI help

`pyclassuml diff --help` は詳細仕様の複製ではなく、READMEへ導く短い説明とする。

## 12. Focused verification matrix

### 12.1 Model / VCS / targets

* `uv run pytest -q tests/model/test_contracts.py`
* `uv run pytest -q tests/vcs/test_diff_file_collect.py`
* `uv run pytest -q tests/targets/test_diff_target_normalize.py`

### 12.2 App / report / CLI

* `uv run pytest -q tests/app/test_diff.py -k 'no_base or default_branch or implicit_range or scope or current_state or invalid_base'`
* `uv run pytest -q tests/report/test_policy.py`
* `uv run pytest -q tests/cli/test_bind.py`
* `uv run pytest -q tests/cli/test_main.py -k 'diff or help'`

### 12.3 Depth/config

* `uv run pytest -q tests/config/test_context_resolve.py`
* `uv run pytest -q tests/app/test_diff.py -k 'depth or changed_seed'`
* `uv run pytest -q tests/app/test_generate.py`
* `uv run pytest -q tests/analyze/test_traversal.py`
* `uv run pytest -q tests/parse/test_module_parse_and_index.py`

### 12.4 Full suite

* `uv run pytest -q`

`pyproject.toml` の提示内容ではdev dependencyとして確認できるquality toolはpytestだけである。未宣言のlint commandを無条件の必須gateにしない。

repository環境に `ruff` 等が既に利用可能な場合は、changed-path checkを補助 evidenceとして実行できる。ただし、repository-wide既存format driftを本Issueの新規failureと混同しない。

### 12.5 Patch quality

* `git diff --check`
  -変更path一覧の確認
* config/traversal/parse/renderにproduction差分がないことの確認
* unrelated generated stateやuser-local fileがcommit対象に入っていないことの確認

## 13. Read-only / clone safety verification

### 13.1 状態receipt

manualまたはintegration scenarioの前後で次を記録する。

* `git rev-parse HEAD`
* `git branch --show-current`
* `git ls-files -s`
* `git status --porcelain=v1 --untracked-files=all`
* `git for-each-ref refs/remotes --format='%(refname) %(objectname)'`

`.puml` outputによるstatus差を避けるread-only verificationでは、outputをfixture repository外へ指定する。

### 13.2 Scenario

次で前後状態が不変であることを確認する。

* default branch working-tree success
* default branch head failure
* feature merge-base success
* feature resolution unavailable
* implicit range too broad
* scope-only target failure
* explicit invalid base
* explicit large-range bypass

### 13.3 Forbidden Git command test

`_run_git` spyまたはcommand captureで、product executionが次を呼ばないことを確認する。

* fetch
* pull
* checkout / switch
* reset
* clean
* stash
* update-ref
* remote mutation
* add / commit

### 13.4 Shallow clone

一時repositoryから shallow clone相当fixtureを作り、少なくとも次を確認する。

* current default branch working-treeはlocal HEADを使って動作可能
* feature merge-baseに必要なobjectがない場合は explicit failure
  -実行後もshallow stateとrefsが不変
* network accessを試みない

partial cloneのpromisor objectが不足するfixtureでは、`GIT_NO_LAZY_FETCH=1` により lazy fetchへ進まず、解決不能を明示的なfailureとして扱う。external diff driver / textconvが設定されたfixtureでも sentinelが実行されないことを確認する。

環境依存で安定した shallow clone fixtureを作れない場合は、`merge-base` failureのunit simulationを必須 evidenceとし、manual shallow cloneを補助 evidenceとして分類する。

## 14. Performance calibration

### 14.1 必須 test

契約boundary `1000 / 1001` と hunk helper未呼び出しを自動testで固定する。

### 14.2 補助測定

可能なら synthetic repositoryまたはmocked raw entriesで次を測定する。

* 100 paths
* 1,000 paths
* 5,000 paths

記録候補:

* raw name-status wall time
* hunk subprocess count
* wall time
* peak memory
* diagnosticまでの時間

測定はlimit採用の事後検証材料であり、測定未実施だけを理由に安全修正を延期しない。

測定結果が `1000` を明らかに不適切と示す場合は、実装定数だけを変更せず requirement/design/README/testを同時に改訂する。

## 15. Full integration gate

M99で次をすべて満たす。

* [ ] Model focused tests pass
* [ ] VCS focused tests pass
* [ ] Targets focused tests pass
* [ ] App focused tests pass
* [ ] CLI/report focused tests pass
* [ ] Config/depth cross-Issue tests pass
* [ ] Full pytest pass、または既存baseline failureが新規failureと分離されている
* [ ] `git diff --check` pass
* [ ] forbidden production pathsに差分なし
* [ ] README/helpとsource behaviorが一致
* [ ] Issue #36 supersede noteが存在
* [ ] Issue #44 authority noteが存在
* [ ] Parent Epicのcorrective-Issue位置づけと矛盾なし
* [ ] read-only receipt pass
* [ ] SpecDock validate pass
* [ ] SpecDock doctor findingsが分類済み
* [ ] `report.md` にexact commands、結果、commit SHA、未検証事項が記録済み

## 16. Evidence 記録

`report.md` には少なくとも次を記録する。

| Evidence ID | 内容                                    |
| ----------- | ------------------------------------- |
| EVD-001     | 開始branch、HEAD、baseline commit         |
| EVD-002     | baseline focused/full test結果          |
| EVD-003     | assurance分類とreview結果                  |
| EVD-004     | model kind Red/Green                  |
| EVD-005     | default branch HEAD base Red/Green    |
| EVD-006     | default branch head failure Red/Green |
| EVD-007     | no-candidate failure Red/Green        |
| EVD-008     | guard boundary・stop-order             |
| EVD-009     | explicit bypass                       |
| EVD-010     | scope-only matrix                     |
| EVD-011     | app/CLI transcript                    |
| EVD-012     | depth/config invariance               |
| EVD-013     | read-only receipt                     |
| EVD-014     | README/help review                    |
| EVD-015     | Issue #36/#44 cross-reference         |
| EVD-016     | full suite / diff check               |
| EVD-017     | SpecDock validate/doctor              |
| EVD-018     | 最終commit ledger                       |

pass countやperformance数値は実行結果から転記し、事前推測で埋めない。

## 17. Stop / replan 条件

次のいずれかが発生した場合は、そのcycleを停止して designを再確認する。

* explicit baseの既存意味を変えないと実装できない。
* config resolverやtraversalへimplicit policyを追加する必要が生じる。
* VCSでscope / suffix / ignoreを解釈する必要が生じる。
* guardをper-file hunk取得前に置けない。
  -新 `FailureReason` やpublic DTO fieldが必要になる。
* network accessまたはclone mutationが必要になる。
* current `app.diff` / `report.policy` transportでは診断を保持できない。
* `initial_commit_fallback` legacy acceptanceの削除が必要になる。
* baseline test failureの原因が不明。
* read-only receiptでGit state差分が発生する。
* `iss-00044` のdepth/config behaviorが意図せず変わる。
* limit測定により `1000` が明らかに危険または無意味と判明する。
  -変更がIssue #45のseamを越えて広がる。

## 18. Rollback 計画

### 18.1 実装中

各Milestoneを独立commit可能にするが、最終採用は次を一単位とする。

* model kind
* VCS resolver
* guard
* targets diagnostic
* tests
* README/help
* Issue #36/#44 notes

Redのまま次Milestoneへ進まない。

### 18.2 Release前

Issue #45一式をatomicにrevertできるようにする。partial revertは行わない。

### 18.3 Release後

旧 initial commit fallbackへの単純rollbackは既知の安全性欠陥を再導入する。緊急時も、implicit解決不能pathをfail closedに保つことを優先する。

旧versionへ戻す必要がある場合は、次を明示する。

-既知リスク
-影響するno-base scenarios
-explicit `--base` 利用の回避手順
-再修正版の追跡Issue

永続データmigrationやrepairは不要である。

## 19. 残課題

### FU-001 — limit calibration

`1000` は本Issueで固定する安全上限であり、性能最適値として断定しない。実repository workloadに対する妥当性は継続測定し、将来変更する場合もrequirement/design/plan/README/testを同時に改訂する。

### FU-002 — initial name-status output limit

guard前の単一 `git diff --name-status` 自体に対するtimeout、byte limit、streaming parseは別Issue候補とする。

### FU-003 — complete HEAD snapshot

`current_state=head` でも通常parse/renderがworking-tree sourceの影響を受け得る既存制約は別Issueとする。

### FU-004 — custom default branch discovery

`origin/HEAD` が欠落・誤設定されたcustom default branchのUX改善は、configや新CLI surfaceを含め別Issueで検討する。

### FU-005 — structured guard metadata

guard failure時のresolved base、actual count、limitをmessage以外のstructured fieldで公開する必要が生じた場合、Diagnostic DTOまたはVCS result contractの拡張を別途設計する。

### FU-006 — explicit large range

explicit baseはguard対象外であり、利用者がinitial commitや古いSHAを指定すれば高負荷になり得る。明示range向けの別resource controlは本Issueに含めない。

### FU-007 — concurrent mutation

base sideは開始時SHAで固定するが、working treeの同時更新をtransactionalにsnapshotしない。必要性が確認された場合は別Issueとする。

### FU-008 — shallow / partial clone UX

failure messageだけで不十分な場合、local history不足をより明確に分類するdiagnosticを後続Issueで検討する。自動network accessは導入しない。

## 20. Definition of Done

Issue #45 の実装完了候補は、次をすべて満たした状態とする。

1. requirementの AC-001〜AC-016 にtestまたはinspection evidenceが対応している。
2. default branch working-tree no-baseがHEAD SHAを使う。
3. default branch head no-baseが専用failureになる。
4. feature/detachedのvalid merge-baseが維持される。
5. implicit resolution failureでinitial commitを使用しない。
6. implicit 1,000件超guardがhunk extraction前に発火する。
7. explicit baseがguardを迂回する。
8. scope-only diagnosticがgeneric zero-targetと区別される。
9. config/depth、read-only、rename、untracked、nested projectが回帰しない。
10. README/help/source/testsが一致する。
11. Issue #36 supersedeとIssue #44 authorityが文書化される。
12. focused/full verificationとpatch qualityが記録される。
13. SpecDock validationと必要なreview gateが閉じる。
14. 未検証事項とfollow-upが `report.md` に残る。
15. GitHub Issue close、PR merge、release完了は、実際に実行・検証されるまで主張しない。
