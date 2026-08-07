---
種別: 要件定義書（Issue）
ID: "iss-00045"
タイトル: "Diff Implicit Base Safety"
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-08-07"
親: ["epic-00002", "init-00001"]
---

# iss-00045 Diff Implicit Base Safety — 要件定義（WHAT / WHY）

## 0. 結論

`pyclassuml diff` の base 未指定実行は、次の契約へ変更する。

| `--base` | 現在位置                                     | `current_state` | 契約                                                       |
| -------- | ---------------------------------------- | --------------- | -------------------------------------------------------- |
| 明示あり     | 任意                                       | `working-tree`  | 明示 ref 自体を base として working tree と比較する                   |
| 明示あり     | 任意                                       | `head`          | 明示 ref 自体を base として `HEAD` と比較する                         |
| なし       | current default branch                   | `working-tree`  | コマンド開始時に解決した `HEAD` commit SHA を base とする                |
| なし       | current default branch                   | `head`          | 非退化な暗黙 base を一意に定められないため、明示 `--base <ref>` を要求して失敗する     |
| なし       | feature branch または detached HEAD         | いずれも            | default branch 候補と開始時 `HEAD` SHA の merge-base を使う        |
| なし       | feature branch または detached HEAD で候補解決不能 | いずれも            | initial commit へ fallback せず、明示 `--base <ref>` を要求して失敗する |

追加の安全契約として、暗黙 base から得た project-root-relative changed path が **1,000 件を超える場合**、per-file hunk 取得、target normalization、AST parse より前に失敗する。明示 `--base` は利用者による範囲の明示承認としてこの guard の対象外とする。

scope 外の Python 変更だけが存在する場合は、変更なし、非 Python 変更だけ、ignore による全除外と同じ generic zero-target 診断へ潰さず、専用 diagnostic で区別する。

本 Issue は成功から失敗への変更を含む公開 CLI 振る舞い変更、diagnostic code 追加、公開 DTO の許容値追加、およびリソース消費 guard を伴うため、実装開始前に **Strict 相当の review・QA・evidence gate** を要求する。`authorized_profile` 自体は SpecDock の正規 `assurance classify --stage requirement` 結果を authority とし、standard が返る場合も manual escalation として Strict 相当の追加ゲートを `report.md` に記録する。profile を手編集で上書きしない。

## 1. 文書の位置づけと根拠

### 1.1 対象スナップショット

GitHub connector で次を確認した。

| 項目                                  | 確認結果                                              |
| ----------------------------------- | ------------------------------------------------- |
| repository                          | `chemitaro/pyclassuml`                            |
| 対象 branch                           | `codex/iss-00045-diff-implicit-base-safety`       |
| branch HEAD                         | `e5a4cf2b2ac8d4a8e9523f83b10febbe5515e2a8`        |
| runtime source / tests / README の基準 | `ce7917cbe04829ad829f62d01169c48dd349a2b4`        |
| Issue                               | GitHub Issue #45、open、`Diff Implicit Base Safety` |

対象 branch の HEAD は Issue #45 文書整備 commit である。 GitHub Issue #45 は open 状態で、本文は SpecDock への参照だけを持つ。 `ce7917c` から対象 branch HEAD までの GitHub compare では Issue #45 の SpecDock 文書・metadata と親 Epic plan だけが変更され、production source、tests、README は変更されていない。

### 1.2 参照した資料

本書は、添付された source、tests、README、`iss-00036`、`iss-00044`、親 Epic 文書、前回 advisory を根拠とする。添付 bundle 全体の参照は次のとおりである。

主要な確認対象は次である。

* `src/pyclassuml/vcs/diff_collect.py`
* `src/pyclassuml/targets/diff.py`
* `src/pyclassuml/app/diff.py`
* `src/pyclassuml/model/contracts.py`
* `src/pyclassuml/config/resolver.py`
* `src/pyclassuml/cli/bind.py`
* `src/pyclassuml/report/policy.py`
* `tests/vcs/test_diff_file_collect.py`
* `tests/targets/test_diff_target_normalize.py`
* `tests/app/test_diff.py`
* `tests/cli/test_main.py`
* `tests/model/test_contracts.py`
* `tests/report/test_policy.py`
* `README.md`
* `iss-00036-diff-default-branch-base/{requirement,design}.md`
* `iss-00044-diff-default-depth/{requirement,design,plan}.md`
* `epic-00002-foundation-contracts/{requirement,design,plan}.md`
* `20260805t074018z-chatgpt-output-chatgpt-diff-implicit-base-safety-advisory.md`

### 1.3 実測の扱い

今回提示された旧 PyClassUML `8bb20e9` のスモークは、default branch 上の base 未指定 diff が initial commit fallback へ進み、巨大な履歴由来の changed set を処理し得ることの再現証拠として扱う。

ただし、このスモークは次を検証した証拠ではない。

* `ce7917c` の command-specific config layering
* `diff` の default `depth=1`
* `[generate]` / `[diff]` override
* `depth=0` の presence semantics
* `ce7917c` における focused test または full test の pass 状態

`ce7917c` の source では `diff` の未指定 depth が resolver により `1`、`generate` が `None` に解決される。一方、`depth` は changed-file collection や base resolution を制限せず、changed Python files はすべて hop 0 seed になる。したがって、旧スモークが示す問題は `iss-00044` の depth/config 契約とは独立した VCS implicit-base safety 問題である。

本書作成時には test suite、performance benchmark、SpecDock validation を実行していない。

## 2. 背景と変更前の現状

### 2.1 変更前の implicit base（historical baseline）

以下は Issue #45 適用前の実装・スモークで観測した baseline であり、現在の採用契約ではない。現在の契約は本書 0 章と 11 章の supersede 境界を正本とする。

現行 `src/pyclassuml/vcs/diff_collect.py` は、base 未指定時に次の順序で base を解決する。

1. `HEAD` commit の存在を確認する。
2. current branch が default branch 自身なら initial commit を返す。
3. それ以外では default branch 候補を決定的順序で試し、最初に成功した merge-base を返す。
4. 全候補が失敗した場合も initial commit を返す。

initial commit fallback は `diff_base_initial_commit_fallback` warning を追加し、通常は `degraded_success`、exit code `0` として処理を継続する。

### 2.2 巨大 changed set の増幅

現行 VCS collection は、最初の `git diff --name-status` で得た各 changed entry に対して、current-side changed line range を得るため個別の `git diff --unified=0` を実行する。

scope filtering、`.py` 判定、ignore filtering はその後の `targets.diff-target-normalize` に属する。このため、initial commit や古い implicit base が多数の changed path を生成すると、次の path も per-file Git subprocess の対象になり得る。

* scope 外 path
* 非 Python path
* ignore 対象 path
* 最終的に seed にならない path

`depth=1` はこの changed-file collection を減らさない。depth は seed 確定後の dependency traversal frontier だけを制限する。

### 2.3 zero-target 診断

現行 `targets.diff-target-normalize` は scope 外 entry の件数を `diff_scope_excluded_count` に保持し、`diff_scope_exclusion` warning を追加する。

その後 seed が 0 件なら、原因を区別せず `diff_zero_target_after_scope_filter` を返す。このため、少なくとも次が同じ fatal code になる。

* changed set 自体が空
* 非 Python change だけ
* Python change がすべて ignore 対象
* Python change がすべて scope 外

scope 外だけの変更は「変更なし」と異なる修正行動を要求するため、機械判定可能な専用 code が必要である。

## 3. 目的

1. base 未指定 diff を、利用者が意図していない巨大な履歴範囲へ silent に拡張しない。
2. current default branch 上の通常作業では、committed history ではなく `HEAD` 以降の working-tree change を扱う。
3. 非退化な implicit base を安全に決定できない場合は fail closed とし、明示 `--base` による判断を利用者へ戻す。
4. feature branch の branch-start 推定として有用な default branch merge-base は維持する。
5. implicit range の異常な breadth を downstream fan-out 前に制限する。
6. scope 外だけの Python change を、no-change や ignore-only と区別できる診断にする。
7. `iss-00036` の有用な optional-base 契約を維持しつつ、安全性上置き換える部分を明示する。
8. `iss-00044` の depth/config 契約と責務境界を変更しない。

## 4. スコープ

### 4.1 対象

* explicit base の優先性と invalid-ref failure の再固定
* current default branch 判定
* default branch + working-tree の `HEAD` base
* default branch + head の explicit-base requirement
* feature branch / detached HEAD の merge-base
* implicit resolution failure
* initial commit fallback の production 廃止
* implicit changed-path breadth guard
* VCS diagnostic code、severity、failure reason、exit contract
* scope-only zero-target diagnostic
* `DiffBaseResolution` の resolution kind
* README、CLI help、migration note
* focused tests、integration tests、full regression
* `iss-00036` supersede 記録
* `iss-00044` との authority 分離記録
* read-only / clone safety

### 4.2 対象外

* `--allow-large-diff` 等の新 CLI option
* changed-path limit の TOML、環境変数、CLI からの設定
* 自動 `git fetch`、`pull`、`remote set-head`、deepen、unshallow
* `HEAD~1`、first-parent、fork-point、reflog による新しい暗黙推定
* GitHub PR API からの base branch 取得
* explicit base に対する breadth guard
* commit 数、履歴 byte 数、diff byte 数の追加 guard
* `current_state=head` の完全な HEAD snapshot rendering
* zero-target 自体を成功へ変更すること
* `AnalysisConfig.depth`、config precedence、traversal algorithm の変更
* target project の source、Git metadata、branch、index、working tree の変更
* concurrent Git mutation に対する repository-wide snapshot lock
* public `FailureReason` の細分化
* `TargetObservations` の public field 追加

## 5. 契約候補の比較と採用理由

### 5.1 explicit `--base`

| 候補                                           | 評価                      | 決定  |
| -------------------------------------------- | ----------------------- | --- |
| 指定 ref 自体を authoritative base とする            | 既存互換であり、利用者 intent が明確  | 採用  |
| 指定 ref と `HEAD` の merge-base に置換する           | `--base` の既存意味を変更する     | 不採用 |
| invalid ref を no-base resolver へ fallback する | 入力誤りを隠し、別範囲を解析する        | 不採用 |
| explicit range にも breadth guard を適用する        | 利用者が明示した大規模 range を拒否する | 不採用 |

### 5.2 current default branch + `working-tree`

| 候補                             | 評価                                      | 決定  |
| ------------------------------ | --------------------------------------- | --- |
| initial commit                 | 履歴全体へ拡張し、branch-start でもない              | 不採用 |
| remote-tracking default branch | fetch 時刻・stale ref・clone 状態に依存する        | 不採用 |
| current `HEAD` commit SHA      | staged・unstaged・untracked の現在作業だけを自然に表す | 採用  |
| base 未指定を常に失敗                  | 安全だが、日常的な working-tree convenience を失う  | 不採用 |

`HEAD` という symbolic name ではなく、コマンド開始時に `HEAD^{commit}` から得た SHA を resolved base とする。

### 5.3 current default branch + `head`

| 候補                             | 評価                                               | 決定  |
| ------------------------------ | ------------------------------------------------ | --- |
| base=`HEAD`                    | `HEAD` 対 `HEAD` となり必ず空で、generic zero-target に流れる | 不採用 |
| base=`HEAD^`                   | 「直前 commit」という別の暗黙概念を導入し、merge commit で曖昧        | 不採用 |
| remote-tracking default branch | stale ref と fetch 時刻に依存する                        | 不採用 |
| 明示 `--base` を要求                | 比較意図を利用者が一意に指定できる                                | 採用  |

### 5.4 feature branch / detached HEAD での解決不能

| 候補                               | 評価                                     | 決定  |
| -------------------------------- | -------------------------------------- | --- |
| initial commit fallback          | branch-start を表さず、誤った seed と巨大負荷を生成し得る | 不採用 |
| repository が小さい場合だけ fallback     | 性能だけを緩和し、base correctness を解決しない       | 不採用 |
| fail closed して explicit base を要求 | 意味論と負荷の両方を安全側に固定する                     | 採用  |

### 5.5 巨大 implicit range guard

| 候補                              | 評価                                                             | 決定  |
| ------------------------------- | -------------------------------------------------------------- | --- |
| guard なし                        | initial fallback 廃止後も stale candidate 等で大規模 implicit range が残る | 不採用 |
| commit 数で制限                     | changed path breadth や subprocess fan-out と相関しない               | 不採用 |
| target filtering 後の seed 数で制限   | scope 外・非 Python path の per-file hunk costを防げない                | 不採用 |
| raw changed path 数を hunk 取得前に制限 | 現行の主要な fan-out を直接制限できる                                        | 採用  |
| limit を利用者設定可能にする               | 初期修正として policy surface と組合せが過剰                                 | 不採用 |

初期 limit は `MAX_IMPLICIT_DIFF_CHANGED_PATHS = 1000` とする。1,000 件は許可し、1,001 件以上を拒否する。

この値は performance benchmark で導出されたものではない。初期公開安全値として仕様化し、変更する場合は source 定数だけを silent に変えず、要件・README・test expectation を同時に改訂する。

### 5.6 scope 外だけの変更

| 候補                                   | 評価                                                | 決定  |
| ------------------------------------ | ------------------------------------------------- | --- |
| generic zero-target code のまま         | no-change、non-Python-only、ignore-only と機械的に区別しにくい | 不採用 |
| 新しい `FailureReason` を追加              | report / exit compatibility に対して過剰                | 不採用 |
| 専用 diagnostic code、既存 failure reason | 最小変更で原因と終了契約を両立できる                                | 採用  |

## 6. 規範的振る舞い

### RQ-001 — explicit base authority

* `--base <ref>` が指定された場合、no-base resolution を実行してはならない。
* `<ref>` は `<ref>^{commit}` が一意な commit に解決できる、空でない Git revision expression でなければならない。branch、tag、commit hash、`HEAD~1` を含む。
* valid explicit base は、文字列として指定された `<ref>` 自体を `resolved_base_ref` とする。
* invalid explicit base は `invalid_base_ref` で失敗し、別 base へ fallback してはならない。
* explicit base は implicit changed-path guard の対象外とする。

### RQ-002 — no-base と explicit base の区別

* `DiffOptions.base_ref=None` は no-base invocation を表す。
* empty string は no-base とみなさず invalid input とする。
* no-base resolution は開始時 `HEAD^{commit}` を SHA として解決してから branch/state 判定を行う。
* no commit repository は VCS read failure とする。

### RQ-003 — current default branch 判定

current branch が default branch 自身かは、次の順序で判定する。

1. `refs/remotes/origin/HEAD` が symbolic ref として解決できる場合、その full branch name と current branch name を比較する。
2. `origin/HEAD` が利用できない場合だけ、current branch name が `main`、`develop`、`master` のいずれかなら default branch とみなす。
3. detached HEAD は current default branch とみなさない。

`release/main` 等の slashful branch name は末尾だけへ丸めない。

### RQ-004 — default branch working-tree no-base

* `current_state=working-tree` かつ current default branch かつ no-base の場合、開始時 `HEAD` SHA を resolved base とする。
* resolution kind は `default_branch_head` とする。
* current side は index + working tree とする。
* `include_untracked=true` の場合、既存どおり untracked entries を追加する。
* default branch の過去 committed history を暗黙 changed set に含めてはならない。
* stale `origin/<default>` を implicit base に使ってはならない。

### RQ-005 — default branch head no-base

* `current_state=head` かつ current default branch かつ no-base の場合、`diff_default_branch_head_requires_base` で失敗する。
* `git diff`、target normalization、parse、traversal、render を実行してはならない。
* diagnostic は `--base HEAD~1` や `--base origin/<branch>` 等を利用者が明示できることを案内するが、特定 ref を自動選択してはならない。

### RQ-006 — feature branch / detached HEAD merge-base

* current default branch でない no-base invocation は、default branch candidates を決定的順序で試す。
* candidate 順序は次とする。

  1. `origin/HEAD` の target
  2. `origin/main`
  3. `origin/develop`
  4. `origin/master`
  5. `main`
  6. `develop`
  7. `master`
* duplicate candidate は最初の一件だけ扱う。
* local に存在しない candidate は skip する。
* 開始時 `HEAD` SHA と candidate の最初に成功した merge-base を resolved base とする。
* resolution kind は `default_branch_merge_base` とし、成功した candidate を `candidate_ref` に保持する。
* `working-tree` / `head` の current-side 意味論は既存契約を維持する。

### RQ-007 — implicit resolution failure

* candidate が存在しない場合、または全 candidate で merge-base が得られない場合、`diff_base_resolution_unavailable` で失敗する。
* shallow clone、partial clone、unrelated histories、remote ref 不足も、利用可能な local Git state で解決不能なら同じ fail-closed contract に従う。
* production resolver は initial commit fallback を生成してはならない。
* 自動 fetch、deepen、unshallow を行ってはならない。

partial clone の欠落 object に対する Git の lazy fetch も許可しない。VCS subprocess は `GIT_NO_LAZY_FETCH=1` を含む安全な環境で起動し、`git diff` には `--no-ext-diff --no-textconv --no-color` を指定して対象 repository の外部 diff・textconv・色付き出力を無効化する。

### RQ-008 — base resolution metadata

production が成功時に生成する resolution kind は次の三つとする。

* `explicit_base`
* `default_branch_head`
* `default_branch_merge_base`

`initial_commit_fallback` は historical report、既存外部 construction、段階的互換性のため DTO の許容値として残す。ただし Issue #45 適用後の production resolver は新規生成しない。

### RQ-009 — implicit changed-path breadth guard

guard は次の条件をすべて満たす場合だけ適用する。

* `requested_base_ref is None`
* base resolution が成功済み
* raw tracked entries と、該当する場合の untracked entries を収集済み
* project-root-relative current path で dedupe 済み
* changed path count が `MAX_IMPLICIT_DIFF_CHANGED_PATHS` を超える

count には次を含む。

* tracked added
* tracked modified
* type-changed を modified として扱う既存 entry
* renamed entry の current path 一件
* `working-tree` かつ `include_untracked=true` の untracked
* scope 外 path
* 非 Python path
* ignore 対象 path

untracked は既存の `git ls-files --others --exclude-standard` が返すものだけを対象とし、Git ignore対象はcountしない。scope外はproject root内かつscope root外を指し、project root外はcountしない。`current_state=head` ではuntrackedをcountしない。type-changeはmodified一件、deletion-onlyは0件、重複current pathは既存の決定的dedupe後に一件としてcountする。

現行契約どおり deletion-only file entry は含めない。

### RQ-010 — breadth guard failure

* limit は `1000` とする。
* count `1000` は許可する。
* count `1001` 以上は `diff_implicit_range_too_broad` で失敗する。
* failure は per-file hunk extraction、targets、parse、traversal、render より前でなければならない。
* diagnostic message は少なくとも次を含む。

  * resolved base
  * actual changed path count
  * fixed safety limit
  * 同じ resolved base を `--base <resolved-sha>` として明示すれば implicit guard を解除できること
* failure reason は既存 `VCS_READ_FAILURE`、exit code は `1`、artifact は生成しない。
* explicit base に同じ path breadth があっても、この guard を理由に拒否しない。

### RQ-011 — scope-only zero-target

次の条件をすべて満たす場合、`diff_zero_target_scope_excluded_only` を返す。

* current `.py` changed entry が一件以上ある。
* すべての current `.py` changed entry が `scope_root` 外である。
* scope filtering 後の seed が 0 件である。

既存の `diff_scope_exclusion` warning と `diff_scope_excluded_count` は先に保持する。

専用 diagnostic の failure reason は `DIFF_ZERO_TARGET_AFTER_SCOPE_FILTER`、severity は error、recoverability は fatal、exit code は `1` とする。

### RQ-012 — generic zero-target の維持

次は `diff_zero_target_after_scope_filter` のまま維持する。

* changed entry が 0 件
* non-Python entry だけ
* in-scope Python entry がすべて ignore 対象
* scope 外 Python entry と in-scope ignored Python entryの混在
* その他、scope-only 条件を満たさない zero-target

generic message は、scope だけでなく file type と ignore filtering も原因になり得ることを示す。

### RQ-013 — read-only / clone safety

* Git 操作は読み取り専用に限る。
* checkout、switch、reset、clean、stash、add、commit、update-ref、symbolic-ref の書き込み、fetch、pull、remote mutation を行わない。
* target source、index、working tree、branch、remote-tracking refs を変更しない。
* `.puml` artifact 以外の target project artifact を生成しない。
* target source を import 実行しない。
* AST static analysis を維持する。
* local clone に必要な ref/history がない場合、ネットワーク操作で補正せず明示的に失敗する。
* partial clone の lazy fetch、external diff、textconv の実行による対象clone・外部command・object databaseの副作用を許可しない。
* read-only検証ではGit stateだけでなく、必要に応じてobject databaseとsentinel external commandの不変性も確認する。

### RQ-014 — 責務境界と `iss-00044`

* CLI bind は `base_ref=None|str`、current-state、include-untracked の raw bind と help text だけを担う。
* config resolver は `iss-00044` の config layering と command default depth を担い、Git base policy を解釈しない。
* VCS は Git base resolution、raw changed-file collection、breadth guard、hunk extraction を担う。
* targets は scope、file type、ignore、zero-target diagnosis を担う。
* app は stage orchestration と resolved-base transportを担う。
* report は summary、stream、exit projection を担う。
* `depth` は base resolution、changed path count、seed setを変更してはならない。

### RQ-015 — README / help / CLI contract

* CLI option 名、argument shape、default bind 値を変更しない。
* `pyclassuml diff [options] [--base <ref>]` を維持する。
* `--base` help は、指定時は authoritative、未指定時は安全な implicit resolution を行うことを簡潔に示す。
* `--current-state` help は、default branch 上の no-base `head` では explicit base が必要であることを示す。
* 詳細な decision table、guard、diagnostics、migration は README を正本とする。
* 新しい CLI flag、TOML key、環境変数を追加しない。

### RQ-016 — 決定性と観測性

* 同一 local Git state、同一 inputs では candidate 順序、resolved base、changed-entry order、diagnostic order を決定的にする。
* normal resolution は warning count を増やさない。
* fatal implicit-base failure は VCS origin の専用 diagnostic code で機械判定可能にする。
* successful diff の summary は既存どおり base resolution metadata を表示する。
* guard failureでは successful `ChangedFileCollection` が存在しないため、`CommandResult.diff_base_resolution` は `None` を許容する。その場合も remediation に必要な resolved base は diagnostic message に含める。

## 7. Diagnostic / exit 契約

| code                                     | origin  | severity | recoverability | failure reason                        |                exit | artifact |
| ---------------------------------------- | ------- | -------- | -------------- | ------------------------------------- | ------------------: | -------- |
| `invalid_base_ref`                       | VCS     | error    | fatal          | `VCS_READ_FAILURE`                    |                   1 | なし       |
| `diff_default_branch_head_requires_base` | VCS     | error    | fatal          | `VCS_READ_FAILURE`                    |                   1 | なし       |
| `diff_base_resolution_unavailable`       | VCS     | error    | fatal          | `VCS_READ_FAILURE`                    |                   1 | なし       |
| `diff_implicit_range_too_broad`          | VCS     | error    | fatal          | `VCS_READ_FAILURE`                    |                   1 | なし       |
| `head_untracked_noop`                    | VCS     | warning  | recoverable    | なし                                    |  0 または別 failure に従う | 成功時あり    |
| `diff_scope_exclusion`                   | TARGETS | warning  | recoverable    | なし                                    | 0 または後続 failure に従う | 成功時あり    |
| `diff_zero_target_scope_excluded_only`   | TARGETS | error    | fatal          | `DIFF_ZERO_TARGET_AFTER_SCOPE_FILTER` |                   1 | なし       |
| `diff_zero_target_after_scope_filter`    | TARGETS | error    | fatal          | `DIFF_ZERO_TARGET_AFTER_SCOPE_FILTER` |                   1 | なし       |

`diff_base_initial_commit_fallback` は legacy diagnostic として過去 report の解釈対象に残せるが、production の新規実行から生成してはならない。

## 8. 不変条件

1. explicit base は implicit resolution と guard より常に優先する。
2. invalid explicit base を別 base へ置換しない。
3. default branch working-tree の implicit base は開始時 `HEAD` SHA である。
4. default branch head の no-base は成功させない。
5. feature branch の有効な default-candidate merge-base は維持する。
6. implicit resolution failure は initial commit に fallback しない。
7. implicit path limit は hunk extraction 前に適用する。
8. explicit base は path limit を迂回する。
9. VCS は scope、`.py`、ignore の意味論を持たない。
10. targets は Git を再読み取りしない。
11. config、depth、traversal は implicit-base policy を持たない。
12. app の changed-file comparison と base blob classification は同じ resolved base を使う。
13. Git state と target source は読み取り専用である。
14. no-base の安全性を得るために network access を要求しない。
15. diagnostic と candidate 順序は決定的である。

## 9. 受け入れ条件

### AC-001 — explicit valid base

**Given** `<ref>^{commit}` に解決できる branch、tag、commit、または `HEAD~1` 等の Git revision expression を `--base` に指定する。
**When** `working-tree` または `head` で diff を実行する。
**Then** 指定 ref 自体が `explicit_base` となり、implicit resolver と breadth guard は実行されない。

### AC-002 — explicit invalid base

**Given** 解決不能な `--base missing-ref` を指定する。
**When** diff を実行する。
**Then** `invalid_base_ref`、`VCS_READ_FAILURE`、exit `1` となり、fallback、targets、parse、artifact write は行われない。

### AC-003 — default branch working-tree

**Given** current default branch に複数の historical commit があり、開始時 `HEAD` 後の working tree に一件だけ変更がある。
**When** `pyclassuml diff` を base なしで実行する。
**Then** resolved base は開始時 `HEAD` SHA、kind は `default_branch_head`、changed entry は working-tree change だけとなる。

### AC-004 — stale remote default を不使用

**Given** current default branch 上で `origin/<default>` が `HEAD` より古い。
**When** no-base working-tree diff を実行する。
**Then** stale remote ref ではなく開始時 `HEAD` SHA を使う。

### AC-005 — default branch head requires base

**Given** current default branch、no-base、`--current-state head`。
**When** diff を実行する。
**Then** `diff_default_branch_head_requires_base`、exit `1` となり、`git diff` と downstream stage は呼ばれない。

### AC-006 — feature branch merge-base

**Given** feature branch と利用可能な default branch candidate が共通祖先を持つ。
**When** no-base diff を実行する。
**Then** 最初に成功した candidate との merge-base が `default_branch_merge_base` として使われる。

### AC-007 — implicit base resolution unavailable

**Given** feature branch または detached HEAD で、利用可能な candidate または merge-base がない。
**When** no-base diff を実行する。
**Then** `diff_base_resolution_unavailable`、exit `1` となり、initial commit warning と artifact は生成されない。

### AC-008 — guard boundary

**Given** implicit base が 1,000 changed path を生成する。
**When** diff を実行する。
**Then** guard は発火せず、通常 collection へ進む。

**Given** implicit base が 1,001 changed path を生成する。
**When** diff を実行する。
**Then** `diff_implicit_range_too_broad`、exit `1` となり、per-file hunk extraction と downstream stage は呼ばれない。

### AC-009 — explicit guard bypass

**Given** AC-008 と同じ resolved SHA を `--base <sha>` として明示する。
**When** diff を実行する。
**Then** breadth guard は発火せず、明示 range の collection を継続する。

### AC-010 — untracked と guard count

**Given** working-tree no-base、`include_untracked=true`。
**When** tracked と untracked の合計が limit を超える。
**Then** untracked current path も count に含まれ、hunk extraction 前に guard が発火する。

### AC-011 — scope-only Python changes

**Given** changed `.py` entries が一件以上あり、すべて `scope_root` 外である。
**When** target normalization を行う。
**Then** `diff_scope_exclusion` に続いて `diff_zero_target_scope_excluded_only` が出力され、既存 `diff_scope_excluded_count` と failure reason が保持される。

### AC-012 — generic zero-target

**Given** non-Python only、ignored Python only、no-change、または scope-outside Python と in-scope ignored Python の混在。
**When** seed が 0 件になる。
**Then** generic `diff_zero_target_after_scope_filter` を使い、scope-only code を誤って返さない。

### AC-013 — legacy resolution compatibility

**Given** 外部コードまたは historical report が `initial_commit_fallback` を含む `DiffBaseResolution` を構築・保持する。
**When** model/report contract を使用する。
**Then**直ちに validation failure へせず、既存 field shape と summary projection を維持する。

### AC-014 — `iss-00044` 回帰防止

**Given**同じ Git state と diff invocation で depth を `0`、`1`、`2` に変える。
**When** config resolution、VCS collection、traversal を実行する。
**Then** base resolution と changed seed set は同一であり、reachable dependency graph だけが depth に応じて変わる。

### AC-015 — read-only

**Given** temp clone または fixture repository。
**When**成功・base failure・guard failure・scope-only failureを実行する。
**Then** `.puml` output を除き、HEAD、current branch、index、tracked/untracked state、remote-tracking refs が実行前後で不変である。

### AC-016 — docs / CLI

**Given** README と `pyclassuml diff --help`。
**When**利用者が no-base 契約を確認する。
**Then** branch/state matrix、explicit authority、no initial fallback、limit、exit behavior、scope-only diagnostic、HEAD rendering caveatを誤解なく確認できる。

## 10. 例外・エッジケース

| 条件                                                        | 契約                                                                          |
| --------------------------------------------------------- | --------------------------------------------------------------------------- |
| repository に commit がない                                   | `git_diff_read_failure` で fail-fast                                         |
| slashful default branch + valid `origin/HEAD`             | full branch name で current-default 判定                                       |
| `origin/HEAD` が current branch と異なる                       | conventional nameだけで default 自身と上書き判定しない                                    |
| `origin/HEAD` がない custom default branch                   | default 自身と断定せず feature-style candidate resolution。解決不能なら explicit base を要求 |
| detached HEAD + candidateあり                               | merge-base を許可                                                              |
| detached HEAD + candidateなし                               | `diff_base_resolution_unavailable`                                          |
| shallow clone で merge-base object 不足                      | 自動 deepen せず `diff_base_resolution_unavailable`                             |
| explicit `--base HEAD` + `current_state=head`             | explicit intent を尊重し、空 changed set は既存 zero-target 契約へ進む                    |
| default branch working-tree で change なし                   | generic zero-target failure                                                 |
| `head` + `include_untracked=true` + explicit/feature base | 既存 `head_untracked_noop` warningを維持                                         |
| rename                                                    | current path一件として guard countし、previous/current metadataを維持                 |
| nested project root / monorepo                            | project-root-relative path と `vcs_root` 分離を維持                               |
| concurrent branch・working-tree mutation                   | 開始時 HEAD SHA は固定するが、repository-wide lockやworking-tree snapshotは保証しない        |

## 11. 互換性と supersede 関係

### 11.1 `iss-00036` を維持する部分

次は `iss-00036` の契約を維持する。

* `--base` の optional 化
* `DiffOptions.base_ref=None` による no-base 表現
* explicit base の authority
* invalid explicit base の failure
* feature branch の default candidate merge-base
* `DiffBaseResolution` の transport
* summary の requested/resolved/candidate 表示
* `working-tree` / `head`
* untracked、rename、nested project boundary
* Git read-only
* app が同じ resolved base を classification に使うこと

### 11.2 `iss-00036` を supersede する部分

Issue #45 適用後は、`iss-00036` の次の契約を置き換える。

* default branch 自身で initial commit を使う契約
* candidate 解決不能時に initial commit を使う契約
* initial fallback を warning 付き degraded success とする契約
* `initial_commit_fallback` を production no-base resolver の正常な最終候補とする契約
* initial fallback を前提とする AC-003、EC-002、EC-003、EX-004、および対応 design/test expectation

`iss-00036` の文書は履歴として削除・無言修正せず、先頭に `iss-00045` による部分 supersede note と置換対象を記録する。

### 11.3 `iss-00044` との関係

`iss-00044` は次について引き続き authority を持つ。

* top-level common config
* `[generate]` / `[diff]` override
* `CLI > command section > top-level > command default`
* `generate depth=None`
* `diff depth=1`
* `depth=0`
* config path semantics
* Diff 固有 config
* traversal と config resolver の責務

`iss-00044` にある「initial fallback 等の VCS behavior を変更しない」という記述は、Issue #44 自身の変更範囲を限定した記録であり、後続 corrective Issue #45 を禁止する恒久契約ではない。Issue #44 文書には、VCS implicit-base behavior の後続 authority が Issue #45 であることを cross-reference し、depth/config 契約は変更しない。

## 12. 仮定

* no-base は、利用者が現在 branch で作業している変更を安全に把握する convenience surface である。
* remote との差分、古い commit との差分、最後の commit との差分は explicit `--base` で指定できる。
* explicit base は大規模 range を含め、利用者が範囲を意図的に承認したものとして扱う。
* `origin/HEAD` は利用可能な場合の default-branch identity hint であり、network 上の最新状態を保証するものではない。
* current `.py` suffix 判定は既存どおり case-sensitive とする。
* breadth guard は changed path fan-out を制限するものであり、最初の `git diff --name-status` 自体の出力量を完全には制限しない。
* zero-target failure policy 自体は本 Issue で変更しない。
* `FailureReason` を増やさなくても diagnostic code で必要な機械判定が可能である。

## 13. 不確実性・未検証主張

* `MAX_IMPLICIT_DIFF_CHANGED_PATHS=1000` は benchmark による最適値ではない。
* 旧 `8bb20e9` スモークの正確な argv、resolved base、changed path 数、subprocess 数、wall time、memory、clone depth は本書では再確認していない。
* `ce7917c` の focused/full test pass 状態は本書作成時に独立再実行していない。
* partial clone、promisor remote、特殊 object database における全 Git failure message は未測定である。
* concurrent working-tree mutation 中の一貫した current-side snapshot は保証対象外である。
* custom default branch で `origin/HEAD` が欠落・誤設定されている repository の判定精度は local metadata に依存する。
