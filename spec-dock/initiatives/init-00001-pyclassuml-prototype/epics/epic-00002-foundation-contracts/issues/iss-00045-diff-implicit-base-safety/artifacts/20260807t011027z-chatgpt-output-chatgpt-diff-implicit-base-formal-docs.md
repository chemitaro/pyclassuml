## === FILE: requirement.md ===

種別: 要件定義書（Issue）
ID: "iss-00045"
タイトル: "Diff Implicit Base Safety"
関連GitHub: ["#45"]
状態: "draft"
作成者: "ChatGPT"
最終更新: "2026-08-07"
親: ["epic-00002", "init-00001"]
-------------------------------

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

本 Issue は成功から失敗への変更を含む公開 CLI 振る舞い変更、diagnostic code 追加、公開 DTO の許容値追加、およびリソース消費 guard を伴うため、実装開始前に **Strict 相当の assurance 再分類・レビュー対象**とする。

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

## 2. 背景と現状

### 2.1 現行 implicit base

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
* `<ref>` は branch、tag、commit hash として commit-ish に解決可能でなければならない。
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

現行契約どおり deletion-only file entry は含めない。

### RQ-010 — breadth guard failure

* limit は `1000` とする。
* count `1000` は許可する。
* count `1001` 以上は `diff_implicit_range_too_broad` で失敗する。
* failure は per-file hunk extraction、targets、parse、traversal、render より前でなければならない。
* diagnostic message は少なくとも次を含む。

  * resolved base
  * actual changed path count
  * configured safety limit
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

**Given** valid branch、tag、または commit を `--base` に指定する。
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

## === FILE: design.md ===

種別: 設計書（Issue）
ID: "iss-00045"
タイトル: "Diff Implicit Base Safety"
関連GitHub: ["#45"]
状態: "draft"
作成者: "ChatGPT"
最終更新: "2026-08-07"
依存: ["requirement.md"]
親: ["epic-00002", "init-00001"]
-------------------------------

# iss-00045 Diff Implicit Base Safety — 設計（HOW）

## 0. 設計要約

本設計は、既存の `cli -> config -> vcs -> targets -> parse -> analyze -> render -> report` pipeline を維持し、VCS と targets の前段 seam だけで implicit-base safety を確定する。

主要な設計判断は次のとおりである。

1. explicit base path は既存どおり authoritative とする。
2. default branch working-tree no-base は開始時 `HEAD` SHA を使う。
3. default branch head no-base は専用 VCS failure とする。
4. feature branch / detached HEAD の candidate merge-base は維持する。
5. candidate 解決不能時の initial commit fallback を廃止する。
6. `DiffBaseResolution` に `default_branch_head` を追加し、legacy `initial_commit_fallback` acceptance は残す。
7. raw changed-entry collection と per-file hunk enrichment を分離する。
8. implicit changed-path count `>1000` を hunk enrichment 前に拒否する。
9. scope-only zero-target は targets seam の専用 diagnostic とする。
10. config resolver、depth、traversal、parse、render の production implementation は変更しない。
11. app/report の既存 transport と generic exit policyを再利用する。
12. Git と target source に対する read-only、offline、deterministic boundaryを維持する。

## 1. 設計目標

* implicit base を安全かつ決定的に解決する。
* 安全な implicit base がない場合に fail closed する。
  -巨大な implicit range の downstream fan-out を制限する。
* explicit base の既存意味論を変えない。
* feature branch の branch-start 推定を維持する。
* diagnostics から利用者が次の操作を判断できるようにする。
* source/tests の seam ownership を維持する。
* `iss-00036` と `iss-00044` の authority を明示的に分離する。
  -小さい変更面で rollback 可能にする。

## 2. 非目標

* default branch discovery の全面再設計
* remote hosting service API の利用
  -自動 network access
* reflog / fork-point を使う分岐元推定
  -完全な repository snapshot isolation
* hunk parser の意味論変更
* deletion-only file の seed 化
* scope / ignore policy の VCS への移動
* changed-path limit の公開設定化
* explicit range の安全上限
* `FailureReason`、`TargetObservations`、`CommandOptions` の field 追加
* config / traversal / render の再設計
* full HEAD snapshot rendering

## 3. 現行構造

| seam                           | 現行責務                                          | Issue #45 での扱い                    |
| ------------------------------ | --------------------------------------------- | --------------------------------- |
| `cli.bind`                     | raw argv を DTO に bind                         | grammar と raw value は維持。help だけ補強 |
| `model.contracts`              | immutable shared DTO と enum 相当 validation     | resolution kind を一値追加             |
| `config.resolver`              | roots、config layering、depth defaults          | 変更しない                             |
| `vcs.diff_collect`             | base resolution、Git diff、untracked、hunk range | implicit policy と guard を変更       |
| `targets.diff`                 | scope、`.py`、ignore、zero-target                | scope-only diagnosis を追加          |
| `app.diff`                     | stage orchestration、base classification       | 原則変更不要                            |
| `report.policy`                | summary、stream、exit                           | 原則変更不要                            |
| `parse` / `analyze` / `render` | AST・traversal・diagram                         | 変更しない                             |

現行 `vcs.diff_collect` は base resolution と、name-status 取得から per-entry hunk extraction までを一つの `_tracked_entries` path で行う。そのため changed path count を確認する時点では、すでに per-entry Git command が実行済みである。

現行 `targets.diff` は scope 外件数を保持するが、zero-target code は一種類である。

## 4. 要件から設計への追跡

| Requirement    | Design  | 内容                                       |
| -------------- | ------- | ---------------------------------------- |
| RQ-001         | DES-001 | explicit base path を resolver の先頭で分離     |
| RQ-002         | DES-002 | no-base の開始時 HEAD SHA snapshot           |
| RQ-003         | DES-003 | default branch identity 判定               |
| RQ-004         | DES-004 | `default_branch_head` resolution         |
| RQ-005         | DES-005 | default branch head no-base failure      |
| RQ-006         | DES-006 | candidate merge-base                     |
| RQ-007         | DES-007 | implicit resolution unavailable failure  |
| RQ-008         | DES-008 | model kind compatibility                 |
| RQ-009, RQ-010 | DES-009 | raw collection と breadth guard           |
| RQ-011, RQ-012 | DES-010 | scope-only zero-target classification    |
| RQ-013         | DES-011 | read-only / clone safety                 |
| RQ-014         | DES-012 | seam ownership と depth separation        |
| RQ-015         | DES-013 | CLI help / README                        |
| RQ-016         | DES-014 | deterministic diagnostics / report reuse |

## 5. 責務境界

### 5.1 CLI

`src/pyclassuml/cli/bind.py` は次だけを担う。

* `--base` の optional non-empty string bind
* `base_ref=None` の保持
* `--current-state` の raw presence
* `--include-untracked` の raw presence
* short help / subcommand description

CLI は次を行わない。

* current branch の照会
* default branch 判定
* ref validation
* HEAD SHA 解決
* candidate enumeration
* breadth guard
* exit policy の独自実装

### 5.2 Config

`src/pyclassuml/config/resolver.py` は `iss-00044` の authority を維持する。

* command-specific common config
* Diff 固有 config
* roots / containment
* `diff depth=1`
* `generate depth=None`
* CLI presence precedence

Config は `base_ref`、Git state、guard limit を解釈しない。

### 5.3 Model

`src/pyclassuml/model/contracts.py` は最小 DTO validation だけを担う。

* `DiffOptions.base_ref: str | None`
* `DiffBaseResolution`
* `CommandResult.diff_base_resolution`

Model は branch/state policy や candidate order を持たない。

### 5.4 VCS

`src/pyclassuml/vcs/diff_collect.py` は次の owner とする。

* explicit ref validation
  -開始時 HEAD SHA 解決
* current branch / default branch 判定
* candidate merge-base
* implicit resolution failure
* raw tracked / untracked entries
* project-root boundary
* deterministic dedupe / sort
* implicit changed-path guard
* current-side hunk enrichment
* VCS-origin diagnostics

VCS は scope、`.py`、ignore を解釈しない。

### 5.5 Targets

`src/pyclassuml/targets/diff.py` は次を担う。

* project-relative path の current filesystem path 化
* scope filtering
* `.py` filtering
* ignore filtering
* scope exclusion observation / warning
* scope-only と generic zero-target の区別

Targets は Git を再読み取りせず、base resolution や path limit を解釈しない。

### 5.6 App / Report

`app.diff` は既存どおり、成功した `ChangedFileCollection.base_resolution` を base blob classification と report input の両方へ渡す。

VCS fatal 時は collection が `None` となり、既存 path で targets 以降を呼ばず report へ渡す。

`report.policy` は既存 `VCS_READ_FAILURE` と `DIFF_ZERO_TARGET_AFTER_SCOPE_FILTER` の hard-failure projection を再利用する。新 code ごとの分岐を追加しない。

## 6. DES-001 — explicit base path

base resolver の最初の branch は `requested_base_ref is not None` とする。

処理は次の順序とする。

1. requested ref が commit-ish として解決可能か確認する。
2. invalid なら `VcsDiffError("invalid_base_ref", ...)` を送出する。
3. valid なら次を返す。

   * `requested_base_ref=<requested>`
   * `resolved_base_ref=<requested>`
   * `resolution_kind="explicit_base"`
   * `candidate_ref=None`
4. current branch、default branch、initial commit、candidate、guard policyを base 解決には混ぜない。

ref validation は `<ref>^{commit}` 相当の確認を用い、branch、tag、commitを許可し、commit として扱えない object を明確に拒否する。ただし downstream Git command と report に渡す resolved string は、既存互換のため requested ref 自体を維持する。

## 7. DES-002 — 開始時 HEAD snapshot

no-base path では、branch/state 判定前に `HEAD^{commit}` を SHA として解決する。

この SHA を次に共通利用する。

* default branch working-tree の resolved base
* candidate との merge-base の current side
* guard diagnostic の remediation ref

symbolic `"HEAD"` を `resolved_base_ref` として保持しない。これにより、少なくとも base side はコマンド途中の branch movement から分離される。

repository に HEAD commit がない場合は既存 `git_diff_read_failure` とする。

## 8. DES-003 — default branch 判定

current branch name は read-only `git symbolic-ref --quiet --short HEAD` 相当で得る。

### 8.1 `origin/HEAD` がある場合

`refs/remotes/origin/HEAD` の symbolic target を得て、`refs/remotes/origin/` または `origin/` prefix だけを取り除いた full branch name と current branch name を比較する。

例:

* `origin/HEAD -> origin/main`、current=`main`: default branch
* `origin/HEAD -> origin/release/main`、current=`release/main`: default branch
* `origin/HEAD -> origin/main`、current=`develop`: default branch ではない

`release/main` を `main` に短縮してはならない。

### 8.2 `origin/HEAD` がない場合

current branch が `main`、`develop`、`master` のいずれかなら default branch とみなす。

### 8.3 detached HEAD

current branch name が得られない場合、default branch 自身とはみなさず candidate merge-base path へ進む。

## 9. DES-004 / DES-005 — current default branch

### 9.1 `working-tree`

current default branch、no-base、`DiffCurrentState.WORKING_TREE` では次を返す。

| field                | value                 |
| -------------------- | --------------------- |
| `requested_base_ref` | `None`                |
| `resolved_base_ref`  | 開始時 HEAD commit SHA   |
| `resolution_kind`    | `default_branch_head` |
| `candidate_ref`      | `None`                |

tracked comparison は既存の `git diff <resolved-base> -- <project-pathspec>` 形式を使う。これにより index と working tree の変更が対象になる。

untracked は既存どおり別 collection として追加する。

### 9.2 `head`

current default branch、no-base、`DiffCurrentState.HEAD` では `DiffBaseResolution` を生成せず、次の VCS error を返す。

* code: `diff_default_branch_head_requires_base`
* message:

  * current default branch 上の no-base `head` には非退化な implicit base がないこと
  * `--base <ref>` が必要であること
  * `HEAD~1` や `origin/<branch>` は利用者が意図に応じて明示できること

この failure は raw diff collection 前に発生させる。

## 10. DES-006 / DES-007 — feature / detached resolution

default branch 自身でない no-base invocation は、開始時 HEAD SHA に対して candidate を試す。

candidate source と順序は次のとおりである。

1. `refs/remotes/origin/HEAD` の targetを display ref へ正規化した値
2. `origin/main`
3. `origin/develop`
4. `origin/master`
5. `main`
6. `develop`
7. `master`

処理規則:

* duplicate は最初だけ保持する。
* local に存在しない ref は skip する。
* `git merge-base <candidate> <head-sha>` が成功し、non-empty single lineを返した最初の candidateを採用する。
* merge-base outputを resolved SHA とする。
  -全 candidate が失敗した場合は `diff_base_resolution_unavailable` とする。
* initial commit探索を呼ばない。

failure message は少なくとも次を含む。

-利用可能な default branch candidate から implicit baseを解決できなかったこと

* explicit `--base <ref>` が必要であること
* shallow history 等が原因の場合も PyClassUML は自動 fetch/deepen しないこと

試行 candidate 一覧を message に含める場合は、決定的順序で表示する。

## 11. DES-008 — model delta

`_DIFF_BASE_RESOLUTION_KINDS` を次へ変更する。

* `explicit_base`
* `default_branch_head`
* `default_branch_merge_base`
* `initial_commit_fallback`

`initial_commit_fallback` は legacy acceptance であり、producer contract には含めない。

新しい public field、enum class、failure reason は追加しない。

producer-level field contract は次とする。

| kind                        | requested | resolved        | candidate     |
| --------------------------- | --------- | --------------- | ------------- |
| `explicit_base`             | non-empty | requested ref   | `None`        |
| `default_branch_head`       | `None`    | HEAD SHA        | `None`        |
| `default_branch_merge_base` | `None`    | merge-base SHA  | candidate ref |
| `initial_commit_fallback`   | `None`    | historical base | `None`        |

既存外部 construction への影響を抑えるため、dataclass constructor へ新たな cross-field exhaustive validation は追加しない。production producer tests で正しい組合せを固定する。

## 12. DES-009 — raw collection と breadth guard

### 12.1 collection phase の分離

現行の tracked entry path を、意味上次の二段階へ分ける。

1. **raw entry collection**

   * name-status を一回取得
   * added / modified / renamed を parse
   * project-root 内だけを current project-relative path に変換
   * line range はまだ取得しない
2. **hunk enrichment**

   * guard 通過後、各 tracked entry の current changed line ranges を取得
   * rename は previous/current pathを使う
   * untracked は line rangeなしのまま維持

private helper の名称は実装中に選べるが、この phase order は変更してはならない。

### 12.2 guard 前の entry set

guard対象 entry set は次の順序で作る。

1. raw tracked entries
2. `working-tree` かつ `include_untracked=true` なら untracked entries
3. current project-relative path で dedupe
4. path の昇順で deterministic sort
5. count

rename は current pathを dedupe key とし、previous path は metadata として保持する。

同じ current path に複数 entry がある場合の precedence は既存 `_dedupe_and_sort` の最終 entry semantics を維持するか、明示的で決定的な precedence に固定する。変更する場合は既存 rename/dedupe testを更新する。

### 12.3 guard 条件

private module constant を次とする。

* `MAX_IMPLICIT_DIFF_CHANGED_PATHS = 1000`

guard predicate は次である。

* `base_resolution.requested_base_ref is None`
* `len(deduped_entries) > MAX_IMPLICIT_DIFF_CHANGED_PATHS`

`len == 1000` は通過する。

### 12.4 guard failure

guard failure は `VcsDiffError` を使用する。

* code: `diff_implicit_range_too_broad`
* message fields:

  * implicit resolved base
  * actual count
  * limit
  * `--base <resolved-sha>` remediation
* failure reason: app の既存 projectionにより `VCS_READ_FAILURE`
* artifact: none

guard failure時は次を呼ばない。

* per-entry hunk diff
* `normalize_diff_targets`
* `parse_target_set`
* dependency traversal
* class selection
* base class inventory
* render
* output write

### 12.5 explicit bypass

explicit base の場合も raw entries は通常どおり収集するが、countにかかわらず implicit guard predicateは false とする。

これは処理成功の保証ではない。Git/OS failure、parse failure、traversal limit 等の既存 failure は引き続き発生し得る。

### 12.6 性能上の限界

本 guard は次を防ぐ。

* changed path数に比例した per-file hunk subprocess
* target normalizationへの巨大 collection
* seed/parse/traversalへの巨大 fan-out

最初の name-status command の出力生成とmemoryは guard前に必要であり、完全には制限しない。これを追加で制限するには streaming parser、Git output byte limit、timeout等の別設計が必要であり、本 Issue の対象外とする。

## 13. DES-010 — scope-only diagnostic

`normalize_diff_targets` 内で public DTO を増やさず、次の seam-local countを保持する。

* `python_changed_count`
* `scope_excluded_python_count`
  -既存 `excluded_count`
  -既存 `ignored_count`

entry processing orderは次とする。

1. current project-relative pathを解決する。
2. path suffix が `.py` なら `python_changed_count` を増やす。
3. scope 外なら既存 `excluded_count` を増やす。
4. scope 外かつ `.py` なら `scope_excluded_python_count` を増やす。
5. scope 内 `.py` だけを ignore candidateへ渡す。
6. ignore を適用する。
7. seedを dedupe / sortする。

seed 0 件時の code selection は次とする。

| 条件                                                                                  | code                                   |
| ----------------------------------------------------------------------------------- | -------------------------------------- |
| `python_changed_count > 0` かつ `scope_excluded_python_count == python_changed_count` | `diff_zero_target_scope_excluded_only` |
| その他                                                                                 | `diff_zero_target_after_scope_filter`  |

diagnostic order は次とする。

1. upstream VCS diagnostics
2. `diff_scope_exclusion` warning
3. zero-target error

`TargetObservations.diff_scope_excluded_count` は既存どおり全 changed entry の scope exclusion countを保持し、Pythonだけへ意味を変更しない。

generic zero-target message は「scope、file type、ignore filtering 後に seed Python files がない」ことを表す。

## 14. DES-011 — read-only / clone safety

### 14.1 許可する Git 操作

VCS adapter は次の read operation 相当だけを使用する。

* `rev-parse`
* `symbolic-ref` の read
* `merge-base`
* `diff`
* `ls-files`
* `show`
* `ls-tree`

`symbolic-ref` は current branch / origin HEAD の照会だけに使い、refを書き換える引数を使わない。

### 14.2 禁止する操作

* `fetch`
* `pull`
* `push`
* `checkout`
* `switch`
* `reset`
* `clean`
* `stash`
* `add`
* `commit`
* `update-ref`
* branch/tag作成・削除
* remote設定変更
* auto-deepen / unshallow

### 14.3 shallow / partial clone

* default branch working-tree は local HEADだけで解決可能とする。
* feature merge-baseに必要な objectがない場合、候補失敗として扱う。
  -全候補失敗後は `diff_base_resolution_unavailable` とする。
* network accessやclone mutationで補正しない。
  -利用者は必要に応じて repository管理手順として historyを取得するか、localに存在する explicit refを指定する。

## 15. DES-012 — `iss-00044` 分離

production change は次を禁止する。

* `src/pyclassuml/config/resolver.py`
* `src/pyclassuml/analyze/traversal.py`
* `src/pyclassuml/parse/*`
* `AnalysisConfig.depth`
* `CommandOptions.depth`
* command-specific config schema

cross-Issue regression testでは次を別々に観測する。

| 観測値                        | depth変更で変わるか             |
| -------------------------- | ------------------------ |
| `DiffBaseResolution`       | 変わらない                    |
| changed entry paths        | 変わらない                    |
| seed files                 | 変わらない                    |
| reachable dependency files | depthに応じて変わる             |
| diagram selection          | reachable graphに応じて変わり得る |

## 16. DES-013 — CLI / docs

### 16.1 CLI grammar

変更しない。

* `pyclassuml diff [options] [--base <ref>]`
* `--current-state working-tree|head`
* `--include-untracked|--no-include-untracked`

### 16.2 help

`diff` subparser description または option help に次を簡潔に記載する。

* explicit `--base` は authoritative
* no-base は安全な implicit baseを解決する
* current default branch + working-tree は HEAD base
* current default branch + head は explicit base必須
  -詳細は README

長い candidate order、diagnostic table、migration note は helpへ複製しない。

### 16.3 README

README の `diff` 節を decision table中心に更新し、次を記載する。

* branch/state matrix
* default branch working-tree の HEAD SHA
* default branch head の failure
* feature merge-base
* no initial fallback
* shallow clone / offline behavior
* 1,000 path limit
* explicit baseによる同一 rangeの opt-in
* scope-only code
* base summary fields
* `initial_commit_fallback` の legacy status
* `head` の最終描画 sourceに関する既存 caveat
* depthは Git base/seedを制限しないこと

## 17. DES-014 — app / report integration

### 17.1 successful collection

successful `ChangedFileCollection` は既存どおり必ず `base_resolution` を持つ。

`app.diff` は次のすべてに同じ `resolved_base_ref` を使う。

* tracked changed-file comparison
* changed-line ranges
* base class inventory
* base blob reading
* report metadata

### 17.2 VCS failure

`VcsDiffCollection.collection is None` の既存 contractを維持する。

app は次を呼ばず reportへ進む。

* targets
* parse
* traversal
* render

新 VCS diagnostics は既存 `FailureReason.VCS_READ_FAILURE` により hard failure、stderr、exit 1となる。

guard failureは base resolution後に起きるが、成功 collectionではないため `CommandResult.diff_base_resolution=None` を許容する。resolved baseは diagnostic messageに含める。VCS resultへの重複 metadata field追加は行わない。

### 17.3 target failure

scope-only failure時、app は既存 zero-target pathを使い、次を reportへ渡す。

* empty `TargetSet`
* `TargetObservations`
* successful `DiffBaseResolution`
* diagnostics

これにより base summaryと `diff_scope_excluded_count` を failure outputに保持できる。

## 18. Failure design

| failure point                    | code                                     | downstream stop point |
| -------------------------------- | ---------------------------------------- | --------------------- |
| explicit ref validation          | `invalid_base_ref`                       | base collection前      |
| default branch + head + no-base  | `diff_default_branch_head_requires_base` | raw Git diff前         |
| candidate resolution exhausted   | `diff_base_resolution_unavailable`       | raw Git diff前         |
| implicit path limit exceeded     | `diff_implicit_range_too_broad`          | hunk extraction前      |
| all Python changes outside scope | `diff_zero_target_scope_excluded_only`   | parse前                |
| generic no seed                  | `diff_zero_target_after_scope_filter`    | parse前                |

全 error は既存 report policyの hard failure pathを使う。

## 19. Production change surface

### 19.1 必須変更

| path                                 | 変更                                                                   |
| ------------------------------------ | -------------------------------------------------------------------- |
| `src/pyclassuml/vcs/diff_collect.py` | state-aware base resolver、no fallback、raw/hunk分離、guard、新 diagnostics |
| `src/pyclassuml/model/contracts.py`  | `default_branch_head` kind追加、legacy kind保持                           |
| `src/pyclassuml/targets/diff.py`     | Python/scope local counts、scope-only code、generic message            |
| `src/pyclassuml/cli/bind.py`         | `diff` / `--base` / `--current-state` help補強                         |
| `README.md`                          | 新契約、migration、guard、diagnostics                                      |

### 19.2 原則変更不要

| path                                  | 理由                                             |
| ------------------------------------- | ---------------------------------------------- |
| `src/pyclassuml/config/resolver.py`   | `iss-00044` authority                          |
| `src/pyclassuml/app/diff.py`          | 既存 fatal/metadata transportで成立                 |
| `src/pyclassuml/report/policy.py`     | 既存 failure reason projectionとgeneric kind表示で成立 |
| `src/pyclassuml/model/__init__.py`    | 既存 `DiffBaseResolution` exportを再利用             |
| `src/pyclassuml/analyze/traversal.py` | depth/traversal責務を変更しない                        |
| `src/pyclassuml/parse/*`              | AST parse責務を変更しない                              |
| `src/pyclassuml/render/*`             | output semanticsを変更しない                         |

app/report production変更が必要と判明した場合は、既存 transportで成立しない具体的理由を `report.md` に記録し、本 designを先に改訂する。

### 19.3 文書変更

* Issue #45 `requirement.md`
* Issue #45 `design.md`
* Issue #45 `plan.md`
* Issue #45 `report.md`
* Issue #36 requirement/design の supersede note
* Issue #44 requirement/design/plan の authority cross-reference
  -必要なら parent Epic plan の確認日・依存注記
* README

## 20. Test design

### 20.1 Model

* `default_branch_head` を受理する。
* unknown kindを拒否する。
* `initial_commit_fallback` を legacyとして引き続き受理する。
* `CommandResult.diff_base_resolution` shapeを維持する。

### 20.2 VCS resolver

* explicit valid / invalid
* default main/develop/master working-tree
* slashful default branch
* stale origin default
* default branch head failure
* feature merge-base
* detached merge-base
* candidateなし
* merge-baseなし
* no commit
* candidate order / dedupe
* shallow-history相当 failure
* initial fallback helperがproduction pathから呼ばれないこと

### 20.3 Guard

* limit 1,000通過
* 1,001拒否
* testでは定数を `1` に monkeypatchし、二件で発火させる focused caseも許可
* explicit bypass
* untracked count
* rename一件count
* scope外 / non-Python / ignored予定pathもcount
* guard時 hunk helper未呼び出し
* guard時 targets/app downstream未呼び出し

### 20.4 Targets

* all Python scope-outside専用 code
* scope-outside Python + in-scope non-Pythonも専用 code
* scope-outside Python + in-scope ignored Pythonはgeneric
* non-Python onlyはgeneric
* ignored Python onlyはgeneric
* no-changeはgeneric
* in-scope Pythonありはsuccess
* diagnostic orderとcounter維持

### 20.5 App / CLI / Report

* default branch working-tree success + `default_branch_head` summary
* default branch head failure + no downstream
* explicit head success
* unresolved feature failure
* guard hard failure
* scope-only failure + base summary + counter
* feature head classification regression
* `head_untracked_noop`
* rename、nested project、monorepo
* legacy fallback report projection
* help text

### 20.6 `iss-00044` regression

* config default depth
* command override
* depth 0 presence
* A→B→C traversal
* same Git stateで depth 0/1/2 の base/seed不変
* `generate` default unlimited
* config resolver source無変更

## 21. Compatibility / migration

### 21.1 維持

* CLI option names
* `DiffOptions` field shape
* `DiffBaseResolution` field shape
* `CommandResult` field shape
* `FailureReason`
* explicit base meaning
* feature merge-base
* current-state / untracked / rename
* summary fields
* read-only / AST-only
* config/depth contract

### 21.2 意図的変更

| 旧挙動                                                  | 新挙動                       |
| ---------------------------------------------------- | ------------------------- |
| default branch working-tree no-base → initial commit | 開始時 HEAD SHA              |
| default branch head no-base → initial commitからHEAD   | explicit base requirement |
| candidate解決不能 → initial fallback degraded success    | hard failure              |
| implicit changed path無制限                             | 1,000件超でhard failure      |
| scope-onlyもgeneric zero-target                       | 専用 diagnostic code        |
| productionが`initial_commit_fallback`を生成              | productionでは生成しない         |

### 21.3 rollback

source、tests、README、Issue cross-referenceを一単位で rollbackする。

部分 rollbackは禁止する。

* guardだけ戻して no-fallbackを残す
* no-fallbackだけ戻して guardを残す
* model kindだけ戻す
* docsだけ旧契約へ戻す

これらは source/docs/testの不整合を生む。

release後の緊急対応で旧 initial fallbackへ戻す場合は、既知の安全性欠陥を再導入するため通常 rollbackとして扱わず、別の明示判断と利用者告知を必要とする。安全側の暫定措置は、解決不能な no-base pathを fail closedのまま維持することである。

## 22. リスクと緩和

| risk                            | 緩和                                                |
| ------------------------------- | ------------------------------------------------- |
| no-candidate cloneが成功から失敗へ変わる   | 専用 codeとexplicit base remediation                 |
| default branch判定誤り              | 既存決定順維持、silent fallback廃止                         |
| 1,000件が正当なfeature branchを拒否     | resolved SHAをexplicit baseとして再実行可能                |
| explicit baseで高負荷               | explicit intentとして許容しREADMEで説明                    |
| raw name-status自体が巨大            | 本Issueの限界として明記し後続候補化                              |
| model kind exhaustive matchへの影響 | field shape維持、migration note                      |
| scope-only判定の誤分類                | Python total / excluded countを別保持しmatrix test     |
| `iss-00044` regression          | config/traversal production pathを禁止しfocused tests |
| test fixtureが巨大                 | limit monkeypatchでfocused verification            |
| concurrent mutation             | HEAD SHA固定、完全snapshotは別Issue                      |

## 23. 仮定・不確実性

* private helper名と分割方法は、phase orderとobservable behaviorを維持する限り実装中に変更できる。
* limit `1000` は初期 policy値でありbenchmark最適値ではない。
* Git stderrの全文はversion・platformで変わり得るため、testsは専用 codeと必要なmessage要素を検証し、Git固有全文へ過度に依存しない。
  -本設計作成時に tests、benchmark、lint、SpecDock validationは実行していない。
* current branchのsource/test baselineはGitHub compare上 `ce7917c` と同一だが、ローカル未提示worktreeの状態は根拠にしていない。

## === FILE: plan.md ===

種別: 実装計画書（Issue）
ID: "iss-00045"
タイトル: "Diff Implicit Base Safety"
関連GitHub: ["#45"]
状態: "draft"
作成者: "ChatGPT"
最終更新: "2026-08-07"
依存: ["requirement.md", "design.md"]
親: ["epic-00002", "init-00001"]
-------------------------------

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
   9.全 evidenceを Issue #45 `report.md` に記録する。

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
   2.既存 transportで成立しない理由を `report.md` に記録する。
2. `design.md` の change surface と interface contractを改訂する。
   4.変更を最小transport差分に限定する。

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
* Issue #36 requirement/design の supersede note
* Issue #44 requirement/design/plan の authority cross-reference
  -必要な場合の parent Epic plan注記
* CLI-managed active projectionは正規 commandによる再生成だけを許可

### 2.5 禁止変更

-新 CLI flag
-新 TOML key
-環境変数によるlimit設定
-自動 fetch / deepen

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
* resolved baseは開始時 HEAD SHA
* kind=`default_branch_head`
* candidate=`None`
* fallback warningなし
* stale `origin/<default>` の過去changesを含めない

main、developの少なくとも一方を実case、他方をparameterizedまたはdefault-detection unit caseで固定する。

slashful default branch + `origin/HEAD` caseも旧 fallback expectationからHEAD expectationへ置き換える。

#### Green

`_resolve_base_ref` に `current_state` を渡し、default branch working-tree pathを追加する。

開始時 HEAD SHAを一度だけ解決し、resolved baseへ使う。

#### Refactor / local gate

* explicit pathが先頭であること
* initial commit helperがこのpathから呼ばれないこと
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

期待:

* code=`diff_base_resolution_unavailable`
* initial fallback diagnosticなし
* targets/hunk collectionなし
* exit 1 at app/CLI

feature/detachedでcandidateありの既存merge-base casesはGreenのまま維持する。

#### Green

candidate loop終了後に initial commit helperを呼ばず、専用 errorを返す。

production pathから `_initial_commit_base_resolution` と `_initial_commit_fallback_diagnostic` を削除する。historical test helperとして残す必要はない。

#### Local gate

* `uv run pytest -q tests/vcs/test_diff_file_collect.py -k 'no_base or merge_base or candidate or detached'`
* `uv run pytest -q tests/app/test_diff.py -k 'no_base and unavailable'`
* `uv run pytest -q tests/cli/test_main.py -k 'no_base and unavailable'`

### 5.6 Cycle M1-C5 — explicit compatibility

#### Red / characterization

次を確認・必要なら補強する。

* valid branch/tag/commit
* invalid ref
* explicit `HEAD` + head state
* explicit baseがdefault branch policyを迂回
* invalid baseがfallbackしない

commit-ishでない objectを明確にinvalidとするcaseを追加する場合、既存公開契約がbranch/tag/commitに限定されていることを test名とdocsで明示する。

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

rename、deleted-only、type change、UTF-8 failure、parse failureの既存 behaviorを維持する。

#### Refactor gate

* `uv run pytest -q tests/vcs/test_diff_file_collect.py`
* raw helperがscope、suffix、ignoreを参照していないことをsource review
* hunk helperがguard前に呼ばれない構造であることをsource review

### 6.2 Cycle M2-C2 — limit

#### Red

production定数を monkeypatch可能なmodule constantとして想定し、limit `1` のtestを追加する。

ケース:

* implicit一件: success
* implicit二件: `diff_implicit_range_too_broad`
* messageにresolved base、actual `2`、limit `1`、`--base` hint
* hunk helper call count `0`

別caseでproduction値のboundaryを、synthetic raw entriesまたはprivate helper unitで次のように固定する。

* 1,000: pass
* 1,001: fail

巨大な1,001-file Git fixtureを常用testにしない。

#### Green

`MAX_IMPLICIT_DIFF_CHANGED_PATHS = 1000` とpredicateを追加する。

#### Local gate

* `uv run pytest -q tests/vcs/test_diff_file_collect.py -k 'implicit_range or changed_path_limit'`

### 6.3 Cycle M2-C3 — count semantics

parameterized testで次を固定する。

| entry                    |    count |
| ------------------------ | -------: |
| tracked added            |        1 |
| modified                 |        1 |
| renamed previous→current |        1 |
| included untracked       |        1 |
| excluded untracked       |        0 |
| scope外                   |        1 |
| non-Python               |        1 |
| ignore予定                 |        1 |
| deletion-only file       |        0 |
| duplicate current path   | dedupe後1 |

`current_state=head` + `include_untracked=true` は既存 warningを出すが、untrackedをcountしない。

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

Issue #36 requirement/design の冒頭付近に次を追加する。

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

`1000` の実repository workloadに対する妥当性を継続測定する。将来変更する場合もpublic behavior変更として扱う。

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
    14.未検証事項とfollow-upが `report.md` に残る。
14. GitHub Issue close、PR merge、release完了は、実際に実行・検証されるまで主張しない。
