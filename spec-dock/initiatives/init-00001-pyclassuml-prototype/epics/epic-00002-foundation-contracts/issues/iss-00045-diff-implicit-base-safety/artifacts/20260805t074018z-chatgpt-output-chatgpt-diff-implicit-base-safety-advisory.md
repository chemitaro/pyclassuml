# 結論

**採用すべき設計は、default branch 上の no-base を `current_state` に応じて分ける案です。**

| `--base` | 現在 branch                | `current_state` | 比較基点・結果                                    |
| -------- | ------------------------ | --------------- | ------------------------------------------ |
| 明示あり     | 任意                       | `working-tree`  | 指定 base → working tree。常に利用者指定を尊重          |
| 明示あり     | 任意                       | `head`          | 指定 base → `HEAD`。常に利用者指定を尊重                |
| 省略       | current default branch   | `working-tree`  | **`HEAD` commit SHA → working tree**       |
| 省略       | current default branch   | `head`          | **専用 diagnostic で fail-fast。`--base` を要求** |
| 省略       | feature branch           | いずれも            | 従来どおり default branch 候補との merge-base       |
| 省略       | feature/detached で候補解決不能 | いずれも            | **initial commit に落とさず fail-fast**         |

併せて、暗黙に解決した base についてのみ、**変更パス数 1,000 件の breadth guard** を入れるのが妥当です。明示 `--base` はこの guard を迂回し、無効な ref、Git 読み取り失敗、OS エラー以外では別の base に差し替えません。

現行挙動は単なる実装事故ではなく、default branch 自身と候補解決不能時に initial commit を返すコード、テスト、README が揃っているため、**現仕様に対する不具合ではなく、仕様上の安全性欠陥を修正する契約変更**です。現行 `_resolve_base_ref()` は default branch 判定直後と候補ループ失敗後の双方で initial commit を返し、既存テストもその degraded success を固定しています。

また、添付された `iss-00044` 候補文書は VCS algorithm、initial fallback、DTO を変更しないことを明記しています。この修正を `iss-00044` の実装に混ぜるなら requirement/design の明示的な scope amendment が必要であり、より安全なのは別の VCS safety issue として扱うことです。 

---

# 1. default branch で base 未指定時の意味論

## 採用案

### `current_state=working-tree`

比較は次の意味に固定します。

```text
base side    = コマンド開始時に解決した HEAD commit SHA
current side = index + working tree
untracked    = include_untracked=true の場合だけ別途追加
```

Git コマンドとしては現在の `git diff <base>` と同じ形を保ち、`<base>` に `HEAD` の解決済み SHA を渡します。したがって、default branch の過去の committed history は changed seed に入りません。

`resolved_base_ref` には文字列 `"HEAD"` ではなく、`rev-parse HEAD^{commit}` で得た SHA を保持すべきです。これにより、report と base blob 読み取りが実行中の branch 移動に依存しません。

推奨する resolution は次です。

```python
DiffBaseResolution(
    requested_base_ref=None,
    resolved_base_ref=head_sha,
    resolution_kind="default_branch_head",
    candidate_ref=None,
)
```

### `current_state=head`

default branch 上で base 省略時に `HEAD` を base にすると、比較は `HEAD..HEAD` となり常に空です。一方、remote default を暗黙に選ぶと、比較対象が「最後に fetch した時点」に依存します。

したがって、ここでは次の専用エラーで止めます。

```text
error:diff_default_branch_head_requires_base:
no-base diff with current_state=head on the current default branch has
no non-degenerate implicit base; specify --base <ref>
```

利用例は文書で示します。

```bash
# 最後の commit を比較
pyclassuml diff --current-state head --base HEAD~1

# 明示的に remote-tracking default との差を見る
pyclassuml diff --current-state head --base origin/develop
```

`--base HEAD` を明示された場合もその指定は尊重します。この場合は利用者が意図的に空の `HEAD..HEAD` を選んだことになり、その後は既存の zero-target 契約に従います。

## `head` の既存 downstream semantics

現在の `head` は完全な「HEAD snapshot レンダリング」ではありません。

* changed-file collection と hunk classification は base → `HEAD`
* classification 用 current source は `HEAD` blob
* 一方、通常の `parse_target_set()` と最終描画の source は working tree

という分割です。README も、HEAD だけの図が必要なら working tree を clean にするよう説明しています。この契約は今回変更しない方がよいです。

---

# 2. remote default を暗黙 base にしない理由

current default branch 上では `origin/develop` などを自動選択しません。

理由は次のとおりです。

1. remote-tracking ref は最後に fetch したローカル状態であり、実際の remote HEAD とは限りません。
2. clone や fetch 時刻によって同じ working tree から異なる結果が出ます。
3. stale ref が長期間 behind していると、今回と同様の巨大差分を再発させます。
4. 自動 fetch は read-only、offline、determinism の既存方針を崩します。
5. remote との差分を求める利用者は `--base origin/develop` で明示できます。

feature branch では、既存の default branch candidate と `HEAD` の merge-base を使う方式を維持します。ここでは remote ref は「remote との差分」そのものではなく、branch start に近い共通祖先を推定する候補として使われるため、用途が異なります。

---

# 3. initial commit fallback

## 採用案: production から自動 fallback を廃止

次の二つをともに廃止します。

* current branch が default branch の場合の initial commit fallback
* default branch candidate を一つも merge-base にできない場合の initial commit fallback

候補解決不能時は次の fatal diagnostic とします。

```text
error:diff_base_resolution_unavailable:
no implicit diff base could be resolved from the available default branch
candidates; specify --base <ref>
```

可能なら message に試行した candidate を含めます。ただし diagnostic field や DTO を増やす必要はありません。

## fallback を小規模 repository にだけ残す案も不採用

「変更ファイル数が少なければ initial commit fallback を許す」という案は、性能面は緩和しても意味論を修正しません。

initial commit は一般に次のいずれでもありません。

* feature branch の開始点
* default branch の直前状態
* remote との同期点
* 利用者が意図した比較基点

したがって、repository が小さい場合でも誤った changed set を作る可能性があります。性能 guard と base correctness は分けるべきです。

## DTO の legacy compatibility

`DiffBaseResolution` が受け入れる `"initial_commit_fallback"` 文字列は、当面は削除しないことを推奨します。

* production resolver は新規には生成しない
* 過去 report、外部テスト、外部コードによる DTO construction は直ちに壊さない
* README では「過去バージョンで出力され得た legacy kind」と扱う
* 次の major compatibility boundary で削除を検討

現在の DTO は resolution kind を三値に限定しています。新しい `"default_branch_head"` を追加するだけなら field shape は変わりません。

---

# 4. 巨大履歴ガード

## 採用案: commit depth ではなく changed-path breadth を guard

ここで問題になるコストは、単純なコミット数ではありません。

現在の VCS 実装は最初に `--name-status` を取得した後、各 changed entry について個別に `git diff --unified=0` を実行します。その後に targets seam で scope、`.py`、ignore filtering が行われます。つまり、巨大な changed path 集合は、scope 外や非 Python であっても先に多数の subprocess を発生させます。

そのため、次を採用します。

```python
MAX_IMPLICIT_DIFF_CHANGED_PATHS = 1000
```

適用条件:

```text
requested_base_ref is None
and
deduped project-root-relative changed path count > 1000
```

対象 path:

* tracked added / modified / renamed
* `working-tree` で include される untracked
* scope 外、非 Python、ignore 対象も含む
* rename は current path 一件として数える
* 既存どおり deletion-only file entry は changed seed に含めない

発火位置:

```text
base resolution
  -> raw name-status collection
  -> project_root filtering
  -> untracked collection
  -> dedupe/count
  -> implicit breadth guard
  -> per-file hunk extraction
  -> targets normalization
  -> AST parse
```

エラー例:

```text
error:diff_implicit_range_too_broad:
implicitly resolved base <sha> produced 12437 changed paths, exceeding
the safety limit 1000; rerun with --base <sha> to confirm this range
```

この再実行方法により、新しい CLI option や config を追加せずに、利用者が同一 range を明示的に opt in できます。

## 明示 `--base` は guard 対象外

明示 base では path 数を理由に拒否しません。

```text
--base が有効     -> その base を使用
--base が無効     -> invalid_base_ref
Git/OS failure     -> read failure
changed path 多数  -> 続行
```

これは「成功を保証する」という意味ではなく、暗黙の安全 policy によって利用者指定を別 base に置換したり拒否したりしないという意味です。

## 数値 1,000 の位置づけ

1,000 は具体的な初期値として妥当ですが、性能実測に基づく値ではありません。正式採用前に 100、1,000、5,000 path fixture で subprocess 数、wall time、peak memory を測定する必要があります。契約上重要なのは次の三点です。

* 暗黙 base だけに適用する
* per-file hunk extraction より前に判定する
* 明示 base で同じ range を承認できる

---

# 5. diagnostic code / DTO の最小変更

## 推奨変更

| seam    | code / field                             | severity | failure reason                        | 用途                                      |
| ------- | ---------------------------------------- | -------: | ------------------------------------- | --------------------------------------- |
| VCS     | `diff_default_branch_head_requires_base` |    error | `VCS_READ_FAILURE`                    | default branch + no-base + `head`       |
| VCS     | `diff_base_resolution_unavailable`       |    error | `VCS_READ_FAILURE`                    | feature/detached で候補解決不能                |
| VCS     | `diff_implicit_range_too_broad`          |    error | `VCS_READ_FAILURE`                    | 暗黙 range が path limit 超過                |
| TARGETS | `diff_zero_target_scope_excluded_only`   |    error | `DIFF_ZERO_TARGET_AFTER_SCOPE_FILTER` | changed Python files がすべて scope 外       |
| DTO     | resolution kind `default_branch_head`    |        — | —                                     | default branch working-tree の HEAD base |

`FailureReason` は増やしません。現在も `invalid_base_ref` を含む全 `VcsDiffError` が `VCS_READ_FAILURE` に投影されるため、新しい diagnostic code だけで詳細を表し、exit policy を維持するのが最小です。Report policy は resolution kind を列挙せず文字列をそのまま出力しているため、model の許可集合と README/test の更新だけで新しい kind を表示できます。

## scope 外だけの zero-target

現在は scope 除外数を保持し、warning を出した後、すべての zero-target に同じ `diff_zero_target_after_scope_filter` を追加しています。したがって機械判定には二つの diagnostics を組み合わせる必要があります。

最小変更は、normalization 内部で次の二つだけを追加計数することです。

```python
python_changed_count
scope_excluded_python_count
```

選択規則:

```python
if not seed_files:
    if (
        python_changed_count > 0
        and scope_excluded_python_count == python_changed_count
    ):
        diff_zero_target_scope_excluded_only
    else:
        diff_zero_target_after_scope_filter
```

これにより、次を区別できます。

| changed set                             | fatal code                             |
| --------------------------------------- | -------------------------------------- |
| Python changes がすべて scope 外             | `diff_zero_target_scope_excluded_only` |
| Python files がすべて ignore                | 既存 generic code                        |
| non-Python changes のみ                   | 既存 generic code                        |
| changed set 自体が空                        | 既存 generic code                        |
| scope 外 Python + scope 内 ignored Python | 既存 generic code                        |

`TargetObservations` は増やさず、既存 `diff_scope_excluded_count` をそのまま保持します。failure reason、exit code、summary counter も変えません。

generic message だけは、実態に合わせて次のように直す価値があります。

```text
diff changed files produced no seed Python files after scope, file-type,
and ignore filtering
```

---

# 6. production 変更面

## 必須

```text
src/pyclassuml/vcs/diff_collect.py
src/pyclassuml/model/contracts.py
src/pyclassuml/targets/diff.py
README.md
```

`diff_collect.py` では `_resolve_base_ref()` に `current_state` を渡し、raw entry collection と line-range enrichment を分離します。

概念形は次です。

```python
def _resolve_base_ref(vcs_root, requested_base_ref, current_state):
    if requested_base_ref is not None:
        return explicit(requested_base_ref)

    head_sha = resolve_head_sha()

    if current_branch_is_default:
        if current_state is WORKING_TREE:
            return default_branch_head(head_sha)
        raise default_branch_head_requires_base

    for candidate in default_candidates:
        if merge_base := resolve_merge_base(candidate, head_sha):
            return default_branch_merge_base(merge_base, candidate)

    raise base_resolution_unavailable
```

## 原則変更不要

```text
src/pyclassuml/app/diff.py
src/pyclassuml/cli/bind.py
src/pyclassuml/report/policy.py
src/pyclassuml/config/resolver.py
```

現在の app は VCS fatal をそのまま report に流し、target fatal 時には空 `TargetSet` と observations を渡しているため、新 diagnostic と counter は既存経路で投影できます。

新しい CLI flag、TOML key、environment variable は追加しません。

---

# 7. 回帰テスト

## VCS: `tests/vcs/test_diff_file_collect.py`

| ケース                                                      | 期待                                                             |
| -------------------------------------------------------- | -------------------------------------------------------------- |
| default `develop`、複数 historical commit、working-tree 一件変更 | 変更一件だけ。base は実行時 HEAD SHA、kind は `default_branch_head`         |
| default branch、stale `origin/develop` が behind           | remote ref を使わず HEAD base                                      |
| slashful default branch + `origin/HEAD`                  | working-tree では HEAD base                                      |
| default branch + no-base + `head`                        | `diff_default_branch_head_requires_base`、`git diff` 未実行        |
| feature branch + usable candidate                        | 既存 `default_branch_merge_base`                                 |
| feature branch + candidate 不在                            | `diff_base_resolution_unavailable`、initial fallback warning なし |
| detached HEAD + usable candidate                         | merge-base 維持                                                  |
| detached HEAD + candidate 不在                             | fail-fast                                                      |
| explicit valid base                                      | 全 branch/state で exact base                                    |
| explicit invalid base                                    | `invalid_base_ref`、fallback なし                                 |
| implicit changed path limit 超過                           | `diff_implicit_range_too_broad`、per-file diff 未実行              |
| 同じ range を explicit base 化                               | limit を迂回して収集続行                                                |
| working-tree + untracked                                 | limit count と entry の双方に反映                                     |
| head + include-untracked                                 | 既存 noop warning。feature/explicit ケースで維持                        |
| rename                                                   | previous/current path 維持                                       |
| nested project root                                      | project 相対 path と boundary 維持                                  |
| read-only                                                | HEAD、branch、index、working tree、remote refs 不変                  |
| depth `None/0/1/2`                                       | VCS base と changed entries が同一                                 |

guard test では production 定数を monkeypatch して `limit=1` とし、巨大 fixture を作らずに「二件で発火」「explicit では発火しない」を固定できます。

## targets: `tests/targets/test_diff_target_normalize.py`

| ケース                                     | 期待                                                                            |
| --------------------------------------- | ----------------------------------------------------------------------------- |
| Python changed files が全件 scope 外        | warning `diff_scope_exclusion` → error `diff_zero_target_scope_excluded_only` |
| scope 外 Python + scope 内 non-Python     | scope-only error                                                              |
| scope 外 Python + scope 内 ignored Python | generic zero-target                                                           |
| non-Python のみ                           | generic zero-target                                                           |
| ignored Python のみ                       | generic zero-target                                                           |
| scope 内 Python が一件以上                    | success、既存 warning と counter                                                  |
| all-scope-outside                       | `diff_scope_excluded_count` が既存どおり全 changed file 数                            |

既存の helper `assert_zero_target_failure()` は expected code を引数化するのが簡潔です。

## app: `tests/app/test_diff.py`

追加・置換すべき e2e:

1. default branch の historical commits が seed に入らず、working-tree change だけが図に出る。
2. `base_resolution: default_branch_head` と HEAD SHA が stdout に出る。
3. default branch + no-base + `head` が parse/traversal/render を呼ばず hard failure。
4. 同じ `head` 実行に `--base HEAD~1` を与えると成功。
5. feature no-candidate が degraded success ではなく hard failure。
6. implicit path guard が target/parse/render を呼ばない。
7. scope-only failure が専用 code を出しつつ、`diff_scope_excluded_count` と既存 failure reason を保持。
8. feature branch の `head` classification、working-tree-only class 非着色、rename、untracked を回帰。
9. default depth、`--depth 0`、`--depth 2` で **seed set/base は不変、reachable graph だけ変わる**。

## CLI: `tests/cli/test_main.py`

```text
pyclassuml diff
  default branch + working-tree change
  -> success / default_branch_head

pyclassuml diff --current-state head
  default branch / no base
  -> exit 1 / diff_default_branch_head_requires_base

pyclassuml diff --current-state head --base HEAD~1
  -> explicit base success

pyclassuml diff
  feature branch / no candidate
  -> exit 1 / diff_base_resolution_unavailable

pyclassuml diff --scope-root pkg
  only outside Python changed
  -> diff_zero_target_scope_excluded_only
     + diff_scope_excluded_count retained
```

CLI parser/binder 自体には新 surface がないため、bind unit test の追加は不要です。

---

# 8. 後方互換性

## 維持されるもの

* 明示 `--base` の優先性
* invalid explicit base の fail-fast
* feature branch の default candidate merge-base
* `working-tree` / `head` の current-side Git 比較
* untracked の working-tree 限定
* rename metadata
* nested project / monorepo boundary
* Git read-only
* scope exclusion counter
* failure exit code policy
* CLI option と config schema

## 意図的に変わるもの

| 旧挙動                                                  | 新挙動                           |
| ---------------------------------------------------- | ----------------------------- |
| default branch no-base working-tree → initial commit | HEAD → working tree           |
| default branch no-base head → initial commit → HEAD  | dedicated hard failure        |
| candidate 解決不能 → initial commit degraded success     | hard failure、`--base` 要求      |
| implicit base の path 数無制限                            | 1,000 件で safety failure       |
| scope-only zero-target も generic code                | scope-only 専用 diagnostic code |
| `initial_commit_fallback` を生成                        | production では生成しない            |

外部利用者が diagnostic code や resolution kind を exhaustive match している場合は更新が必要です。`FailureReason` と DTO field shape を維持することで影響を限定できます。

---

# 9. 文書化

README の `diff` 節は、説明文だけでなく decision table に変更するのが明確です。

必須記載:

* default branch + working-tree の base は HEAD
* default branch + head では `--base` 必須
* feature branch no-base は default candidate merge-base
* candidate 不在では initial commit に fallback しない
* remote default を見たい場合は明示 `--base origin/<branch>`
* implicit base の changed-path safety limit
* explicit base は limit の opt-in override
* `head` の最終描画 source に関する既存 clean-worktree caveat
* `initial_commit_fallback` は legacy report 値
* scope-only diagnostic code

CLI help に長い policy を埋め込む必要はありません。`--base` に短い help text を追加する場合も、README を正本とします。

---

# 10. 不採用案

| 案                                     | 不採用理由                                                          |
| ------------------------------------- | -------------------------------------------------------------- |
| default branch では常に remote default    | stale ref、clone/fetch 依存、巨大差分再発                                |
| default branch では両 state とも HEAD      | `head` が常に空で generic zero-target に流れる                          |
| default branch では両 state とも fail-fast | working-tree の自然な HEAD 比較まで失う                                  |
| `head` の implicit base を `HEAD^` にする  | 「最後の commit」という別概念を暗黙導入。merge commit でも曖昧                      |
| initial fallback を warning のまま維持      | warning では誤った seed set と負荷を防げない                                |
| 小規模 repository だけ initial fallback    | 性能だけ改善し、base correctness は改善しない                                |
| explicit base にも path guard           | 利用者の明示的な range 選択を拒否する                                         |
| `--allow-large-diff` を新設              | `--base <resolved-sha>` が既に明示 opt-in として使える                    |
| TOML に limit を追加                      | policy surface と組合せテストが増える。初期修正には過剰                            |
| guard を `depth` に連動                   | depth は dependency traversal であり changed seed collection とは別責務 |
| 自動 `git fetch`                        | read-only/offline/deterministic 契約を崩す                          |
| scope-only 用に新 FailureReason を追加      | diagnostic code だけで判別でき、report/exit compatibility を壊す必要がない     |

---

# 11. リスク

### 互換性破壊

候補のない clone や default branch の `head` 実行は、従来の成功から失敗になります。

**緩和:** diagnostic に具体的な `--base` 例を含め、release note で明示します。

### guard の誤検知

正当な大規模 feature branch が 1,000 path を超える可能性があります。

**緩和:** diagnostic に resolved SHA を示し、同じ値を `--base` に渡せば続行できる設計にします。

### default branch 判定の誤り

既存判定は `origin/HEAD` を優先し、なければ `main/develop/master` 名を使います。`origin/HEAD` が誤設定されている custom repository は default branch と認識されない可能性があります。

**緩和:** 自動推測を増やさず、candidate 解決不能時の明確な diagnostic と explicit base を使います。

### `head` の snapshot 混在

明示 base または feature branch の `head` でも、最終描画は working-tree source を含み得ます。

**緩和:** 今回は変更せず、README の既存 caveat を保持します。完全 HEAD snapshot は別 issue に分離します。

### 新 resolution kind

外部コードが三値を exhaustive match していると `"default_branch_head"` で失敗します。

**緩和:** field shape と legacy value acceptance を維持し、migration note を出します。

### explicit base による高負荷

利用者が initial commit や非常に古い SHA を明示すれば、引き続き巨大処理が可能です。

**緩和:** これは明示 intent として許容し、README で負荷可能性を説明します。

---

# 12. 検証手順

## focused tests

```bash
uv run pytest -q tests/vcs/test_diff_file_collect.py
uv run pytest -q tests/targets/test_diff_target_normalize.py
uv run pytest -q tests/app/test_diff.py \
  -k 'no_base or default_branch or scope or implicit_range or current_state'
uv run pytest -q tests/cli/test_main.py -k diff
```

## depth/config の独立検証

```bash
uv run pytest -q tests/config/test_context_resolve.py -k depth
uv run pytest -q tests/app/test_diff.py \
  -k 'default_depth or depth_zero or depth_two or changed_seed'
```

ここでは次を別々に記録します。

```text
resolved AnalysisConfig.depth
DiffBaseResolution
seed_file_count
reachable_file_count
changed entry paths
```

期待する分離:

```text
depth を 0 / 1 / 2 に変える
  -> base resolution 不変
  -> changed seed set 不変
  -> reachable dependency set だけ変化
```

## full suite と patch quality

```bash
uv run pytest -q
git diff --check
```

この repository の接続済み `pyproject.toml` では pytest は確認できますが、ruff 等の lint tool は dev dependencies に確認できないため、未導入の lint command を必須 gate として仮定しない方がよいです。

## manual behavior matrix

1. `develop` に三つ以上の historical commit を作る。
2. 最新 HEAD 後に Python 一件だけを working tree で変更。
3. `pyclassuml diff --no-include-untracked` を実行。
4. seed が一件、base が HEAD SHA、過去 commit のファイルが入らないことを確認。
5. `--current-state head` の no-base が専用 code で失敗することを確認。
6. `--current-state head --base HEAD~1` が成功することを確認。
7. default candidate のない feature branch が initial commit を使わず失敗することを確認。
8. guard limit を超える synthetic path set で、per-file hunk/parse 前に停止することを確認。
9. 同じ resolved SHA を明示 base にして guard を迂回することを確認。
10. scope 外 Python のみで専用 code と counter を確認。

## read-only invariant

各シナリオの前後で少なくとも次を比較します。

```bash
git rev-parse HEAD
git branch --show-current
git ls-files -s
git status --porcelain=v1
git for-each-ref refs/remotes --format='%(refname) %(objectname)'
```

`.puml` 出力以外について、HEAD、branch、index、tracked/untracked state、remote-tracking refs が不変であることを確認します。

---

# 根拠

GitHub connector で対象 branch `codex/iss-00044-chatgpt-first-planning` を開き、VCS、DTO、targets、app、report、tests、README を確認しました。旧 `8bb20e9` と接続 branch の `src/pyclassuml/vcs/diff_collect.py` は同じ blob SHA `ecd9dffb5ad62d8a13eedaa835dc9a689c005181` であり、接続済み branch について VCS 実装不変は確認できます。

一方、接続 branch の config resolver は、未指定 depth に command-specific default を注入せず、CLI 値または top-level config 値をそのまま返す形でした。したがって、GitHub 上の branch 内容だけでは、提示されたローカル `ce7917c` の diff default depth/config 契約は確認できません。

重要なのは、仮に `ce7917c` で default depth が `1` に修正済みでも、depth は changed-file collection を減らしません。changed file はすべて hop 0 seed であり、depth はその後の dependency traversal を制限する契約だからです。したがって旧実測は depth/config の検証証拠ではありませんが、initial-commit base による seed explosion という VCS 設計問題とは独立しています。

# 仮定

* no-base は「現在 branch で利用者が作業している変更」を安全に推定する convenience surface である。
* remote との差分や古い commit との差分は、利用者が `--base` で明示できる。
* explicit base は、大規模 range を含めて利用者が意図を表明したものとして扱う。
* zero-target 自体を成功に変更することは今回の対象外である。

# 不確実性

* path limit `1,000` の数値は性能 benchmark 未実施の暫定値です。
* custom default branch 判定をどこまで拡張すべきかは、実 repository の `origin/HEAD` 品質に依存します。
* local worktree commit `ce7917c` は GitHub connector から解決できなかったため、その exact source、config resolver、test result は独立確認していません。
* 本レビューでは test suite を実行していません。

# 未検証主張

* 旧実測時の正確な CLI argv、`.pyclassuml.toml`、環境、resolved `AnalysisConfig.depth`
* 旧実測の changed path 数、subprocess 数、wall time、memory
* 対象 repository の当時の `origin/HEAD`、remote-tracking ref、shallow-clone 状態
* `ce7917c` での focused/full test pass 状態
