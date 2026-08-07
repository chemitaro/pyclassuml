---
種別: 設計書（Issue）
ID: "iss-00045"
タイトル: "Diff Implicit Base Safety"
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-08-07"
依存: ["requirement.md"]
親: ["epic-00002", "init-00001"]
---

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

`collect_diff_files` は、resolverへ raw CLI optionではなく、config precedence解決後の `config.diff_current_state` を渡す。規範的な呼び出しは次である。

```python
base_resolution = _resolve_base_ref(
    vcs_root,
    requested_base_ref,
    config.diff_current_state,
)
```

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

ref validation は `<ref>^{commit}` 相当の確認を用い、branch、tag、commit、`HEAD~1` 等の revision expressionを許可し、commit として扱えない object を明確に拒否する。ただし downstream Git command と report に渡す resolved string は、既存互換のため requested ref 自体を維持する。

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

`_ensure_diff_base_resolution_kind` のvalidation error messageも許容集合と同じ順序で `explicit_base, default_branch_head, default_branch_merge_base, initial_commit_fallback` を列挙する。

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

現行の tracked entry path を、意味上次の二段階へ分ける。raw phaseではVCS-root-relative pathを失わず、public DTOへのproject-relative変換はhunk enrichment後またはuntrackedの確定時に行う。

1. **raw entry collection**

   * name-status を一回取得
   * added / modified / renamed を parse
   * project-root 内だけを選別
   * VCS-root-relative current/previous path、current project-relative count key、change kindをprivate raw carrierに保持
   * line range はまだ取得しない
2. **hunk enrichment**

   * guard 通過後、各 tracked entry の current changed line ranges を取得
   * rename はprivate raw carrierのVCS-root-relative previous/current pathを使う
   * untracked は line rangeなしのまま維持

private helper の名称は実装中に選べるが、この phase order は変更してはならない。

### 12.2 guard 前の entry set

guard対象 entry set は次の順序で作る。

1. raw tracked entries
2. `working-tree` かつ `include_untracked=true` なら untracked entries
3. current project-relative path をdedupe keyにしてdedupe（hunk pathspecはVCS-relative pathのまま保持）
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
2. project root外なら対象から除外し、count・scope exclusionへ加えない。
3. path suffix が `.py` なら `python_changed_count` を増やす。
4. scope 外なら既存 `excluded_count` を増やす。
5. scope 外かつ `.py` なら `scope_excluded_python_count` を増やす。
6. scope 内 `.py` だけを ignore candidateへ渡す。
7. ignore を適用する。
8. seedを dedupe / sortする。

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

すべての Git subprocess は `GIT_NO_LAZY_FETCH=1` を設定した環境で起動し、partial cloneの欠落objectを自動取得しない。`diff` commandには `--no-ext-diff --no-textconv --no-color` を指定し、repository設定による外部diff・textconv・色付き出力を無効化する。最低Git versionでこれらの安全契約を保証できない場合は、対象操作をfail closedにする。

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
* read-only receiptではHEAD、branch、index、status、remote refsに加え、必要に応じてobject databaseの一覧・件数とexternal diff/textconv sentinelの不実行を確認する。

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
* Issue #36 requirement/design/plan の supersede note
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
* `HEAD^{commit}` の結果がmerge-baseのcurrent引数に一回だけ使われること
* `origin/HEAD` と conventional branch名が矛盾する場合のdefault branch identity
* candidate exhaustion時に `rev-list --max-parents=0` を呼ばないこと
* configで解決された `current_state=head` がdefault-branch no-base failureになること
* nested projectのmodified/renameでhunk pathspecはVCS-relative、公開entryはproject-relativeであること
* partial clone lazy-fetchとexternal diff/textconv sentinelが発火しないこと

### 20.3 Guard

* limit 1,000通過
* 1,001拒否
* testでは定数を `1` に monkeypatchし、二件で発火させる focused caseも許可
* explicit bypass
* untracked count
* rename一件count
* scope外 / non-Python / ignored予定pathもcount
* project root外pathをcountしないこと
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
