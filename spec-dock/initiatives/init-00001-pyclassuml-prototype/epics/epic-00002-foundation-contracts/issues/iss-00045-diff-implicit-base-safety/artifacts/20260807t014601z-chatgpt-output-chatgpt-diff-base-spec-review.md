REVIEW_STATUS: FAIL

## 結論

**P0 はありません。P1 が7件あり、現状の文書セットをそのまま実装へ渡すことはできません。**

ただし、Issue #45 の中心方針は妥当です。次の契約は、現行コードの責務分割を大きく崩さず実装できます。

* default branch / working-tree / no-base は開始時 `HEAD` SHA
* default branch / head / no-base は明示 base 要求
* feature branch・detached HEAD は default branch candidate との merge-base
* candidate 解決不能時は initial commit fallback なし
* explicit base は常に優先
* implicit changed-path guard は hunk extraction 前
* scope-only diagnostic は public DTO を増やさず targets → app → report へ伝播

一方、read-only/offline safety、config 解決済み state の受け渡し、nested project における raw path の基準、explicit base の文法、旧 Issue の supersede、テストの観測点、正本文書への採用と assurance gate が未閉鎖です。

レビュー対象は添付された候補文書一式です。GitHub connector では指定ブランチを開き、現行 production source がなお initial commit fallback と hunk 先行処理を持つことを確認しました。添付候補そのものは、現時点の指定ブランチ上の canonical requirement/design/plan とは一致していません。

## P0 findings

該当なし。

破壊的な Git 書き込み、データ移行、credential 処理を設計として要求している箇所はありません。以下の P1 を修正すれば、設計全体を破棄する必要はありません。

## P1 findings

### P1-01 — read-only / offline 契約が Git の暗黙副作用を遮断していない

候補文書は `fetch`、`deepen`、`update-ref` 等を直接呼ばないことを規定していますが、それだけでは partial clone の network-free・clone-immutable 契約になりません。

partial clone では、ローカルにない object が必要になると Git 自身が promisor remote から demand fetch できます。Git の公式文書は、欠落 object の取得が内部的な `git fetch` subprocess によって行われること、現在の Git では `GIT_NO_LAZY_FETCH=1` または `git --no-lazy-fetch` でこれを止められることを説明しています。([Git][1])

さらに現行コードの `git diff` は `--no-ext-diff`、`--no-textconv` を指定していません。Git は `diff.external` や diff driver の command を実行でき、`git diff` では textconv が既定で有効になり得ます。したがって、対象 repository の設定次第では任意の外部 command が実行され、hunk parser が期待する unified diff 以外の出力を受け取る可能性もあります。([Git][2])

**必要な修正**

1. VCS adapter が起動する全 Git subprocess に、少なくとも `GIT_NO_LAZY_FETCH=1` を設定する契約を design に追加する。
2. `git diff` の name-status と hunk command に `--no-ext-diff --no-textconv --no-color` を固定する。
3. 対応する最低 Git version、または古い Git での fail-closed 方針を明記する。
4. partial clone test は `_run_git` の引数 spy だけで済ませず、promisor remote への接続 sentinel と object database の前後比較を行う。
5. external diff / textconv command に sentinel script を設定し、PyClassUML 実行時に起動されないことを確認する。

現在の read-only receipt は HEAD、branch、index、status、remote refs が中心で、lazy fetch による object database の増加や textconv cache ref を検出できません。

### P1-02 — resolver に渡す `current_state` の authority が明記されていない

候補 design/plan は `_resolve_base_ref` に `current_state` を渡すとしていますが、**その値が `request.cli_options.diff.current_state` ではなく `config.diff_current_state` であることを規範化していません。**

現行 CLI DTO は、CLI で `--current-state` が省略されても一旦 `WORKING_TREE` を保持し、別の presence field で未指定を表します。その後、config resolver が `[diff].current_state` と CLI presence を解決して最終的な `AnalysisConfig.diff_current_state` を作ります。

raw request の値を resolver に渡すと、例えば次が誤動作します。

```toml
[diff]
current_state = "head"
```

default branch、no-base でも working-tree path と誤判定され、`diff_default_branch_head_requires_base` ではなく `default_branch_head` 成功になり得ます。

**必要な修正**

design に次を明記してください。

```python
base_resolution = _resolve_base_ref(
    vcs_root,
    requested_base_ref,
    config.diff_current_state,
)
```

加えて以下の test が必要です。

* config だけで `current_state=head` → requires-base failure
* config `head` + CLI `--current-state working-tree` → HEAD SHA base 成功
* config `working-tree` + CLI `--current-state head` → requires-base failure
* depth の変更は state/base 判定に影響しない

### P1-03 — raw collection を project-relative 化すると nested project の hunk path が壊れる

現行実装は、name-status が返した **VCS-root-relative path** を `_entry_with_current_changed_line_ranges` に渡し、hunk を取得した後で project-relative path に変換しています。

候補 design は raw phase で project-root 内判定と project-relative 変換を行い、その後 hunk enrichment を行うとしています。しかし、例えば次の構成では基準が異なります。

```text
vcs_root/
└── packages/app/        # project_root
    └── pkg/model.py
```

Git を `vcs_root` で実行するときの pathspec は `packages/app/pkg/model.py` でなければなりません。raw phase で `pkg/model.py` に変換して既存 hunk helper に渡すと、別 path を参照します。

rename は previous/current の双方を hunk command に渡すため、同じ問題がより強く現れます。

**必要な修正**

private な raw carrier を設計してください。public DTO の追加は不要です。例えば次の情報を guard 通過まで保持します。

```text
current_vcs_relative_path
previous_vcs_relative_path | None
current_project_relative_path
change_kind
```

* dedupe/count key: `current_project_relative_path`
* hunk pathspec: VCS-relative path
* public `ChangedFileEntry`: enrichment 後に project-relative path で構築

併せて、project boundary を横断する rename の意味論も決める必要があります。

* outside → inside
* inside → outside
* previous path だけ project 外

少なくとも nested project の modified/rename 双方を guard 前後の integration test で固定してください。

### P1-04 — explicit base の受理文法が文書内で一致していない

RQ-001 は branch、tag、commit hash を受理対象として列挙しています。一方、同じ文書群の diagnostic、README、test plan は `HEAD~1` を正式な例として使っています。

現行 CLI は任意の non-empty string を bind し、現行 VCS validator も Git revision として解決しています。

したがって、実装前に次のどちらかへ統一する必要があります。

**推奨する契約**

> explicit base は、`<requested>^{commit}` が一意な commit に解決できる任意の non-empty Git revision expression とする。branch、tag、commit hash、`HEAD~1` を含む。report と downstream へ渡す文字列は既存互換のため requested text を保持する。

この場合、次を test します。

* local / remote-tracking branch
* lightweight tag
* annotated tag to commit
* full SHA、unique short SHA
* `HEAD~1`
* tree/blob または non-commit tag の拒否
* missing / ambiguous revision の拒否
* invalid explicit base から implicit resolver へ進まない

branch/tag/hash のみに制限するなら、`HEAD~1` の全例を削除し、現行より狭くなる compatibility change として明示する必要があります。

### P1-05 — `iss-00036` の supersede 対象から `plan.md` が漏れている

候補文書は Issue #36 の requirement/design に supersede note を追加するとしています。しかし、現行の approved `iss-00036/plan.md` も、次を実装契約として明示しています。

* candidate 不在時の initial commit fallback
* current default branch の initial commit fallback
* fallback を伴う degraded success
* AC/EC と実装 step における fallback 維持

したがって requirement/design だけを更新すると、approved plan が旧契約のまま残ります。

**必要な修正**

`iss-00036` の次の3文書すべてに、同一の部分 supersede note を追加してください。

```text
requirement.md
design.md
plan.md
```

過去本文は削除せず、冒頭で次を明示します。

* superseded-by: `iss-00045-diff-implicit-base-safety`
* 置換される requirement / AC / EC / design / plan step
* 引き続き有効な optional-base、explicit authority、feature merge-base、DTO transport、read-only 契約

historical `report.md` や過去 evidence は書き換えない方針で正しいです。

### P1-06 — 開始時 HEAD SHA と default-branch identity の核心不変条件が test で固定されない

候補 plan の通常 repository fixtureだけでは、実装が引き続き次を使っていても test が通り得ます。

```python
git merge-base <candidate> HEAD
```

repository が test 中に変化しなければ、開始時 SHA を渡した場合と同じ結果になるためです。

また、現行 helper は `origin/HEAD` が取得できる場合にはその full branch name を優先し、conventional name fallback は使いません。候補 requirement はこの点を正しく記述していますが、test matrix が十分ではありません。

**必要な追加 test**

1. `HEAD^{commit}` の解決結果を捕捉し、`merge-base` の第2引数が symbolic `HEAD` ではなく、その exact SHA であること。
2. no-base 一実行につき開始時 SHA を一回だけ解決すること。
3. current branch=`main`、`origin/HEAD -> origin/develop` の場合に current default branch と誤認しないこと。
4. slashful `release/main` を末尾 `main` に丸めないこと。
5. candidate exhaustion 時に `rev-list --max-parents=0` を一度も呼ばないこと。
6. explicit base path では no-base 用 HEAD/candidate resolution を呼ばないこと。
7. detached HEAD でも captured SHA が merge-base current side になること。

### P1-07 — 添付候補が canonical 文書・assurance state に未採用

GitHub connector で指定 branch の canonical requirement/design/plan を取得したところ、添付された2026-08-07版の具体文書ではなく、placeholder を含む Standard template 系の内容でした。現在の `.assurance.json` も `status=provisional`、`authorized_profile=standard` で、public contract change 等が unknown のままです。

これは添付候補の内容レビューを妨げませんが、**implementation admission は閉じていません。**

実装前に必要なのは次です。

1. 修正版 requirement/design/plan を canonical path へ採用する。
2. 採用後の exact artifact hash に assurance binding を更新する。
3. public CLI behavior、public DTO allowed value、fatal diagnostic、resource guard を既知の risk facts として再分類する。
4. Strict 相当の required review を実施する。
5. `validate` / `doctor` の実結果を `report.md` に記録する。
6. 採用後の branch SHA を baseline として再記録する。

## P2 findings

### P2-01 — model の許容集合だけでなく validation message も更新が必要

現行 `_DIFF_BASE_RESOLUTION_KINDS` に `default_branch_head` を追加する方針は正しいです。ただし、現在の validation error message は3種類を文字列で直接列挙しています。集合だけを変更すると、実際の許容値と error message が不一致になります。

次も変更対象に明記してください。

```python
"resolution_kind must be one of: explicit_base, default_branch_head, "
"default_branch_merge_base, initial_commit_fallback"
```

report は kind を列挙せず、その文字列をそのまま summary に出すため、production report code の変更は不要です。

### P2-02 — guard count の用語をさらに固定すべき

候補の count 定義は概ね一貫していますが、次を明記してください。

* 「untracked」は既存 `ls-files --others --exclude-standard` が返すものだけ
* Git ignore 対象の untracked は count しない
* 「ignore 対象を count」は PyClassUML の `AnalysisConfig.ignore` によって後段除外される path を指す
* `scope 外` は project root 内かつ scope root 外
* project root 外は raw collection から除外され count しない
* type-change `T` は modified 1件
* rename は current path 1件
* deletion-only file entry は0件
* `head + include_untracked=true` は untracked 0件
* duplicate current path の precedence を「現行どおり後勝ち」等に確定する

また、limit は設定可能ではないため、RQ-010 の “configured safety limit” は **“fixed safety limit”** または単に **“safety limit”** に修正すべきです。

### P2-03 — `1000` は採用可能だが、性能的に妥当と認定してはならない

`1000` / `1001` の境界は明確で、公開 policy として test 可能です。しかし文書自身が認めるとおり、benchmark で導出された値ではありません。

判断は次のように分けるべきです。

* **guard mechanism:** 採用
* **exact threshold 1000:** product-policy として暫定採用
* **性能最適値であるとの主張:** 保留
* **将来の silent constant change:** 不可

performance calibration が未実施でも安全修正を止める必要はありませんが、owner による policy 承認を implementation entry checklist に残してください。

### P2-04 — plan/design の番号・箇条書きを修正すべき

候補文書には、少なくとも次の編集上の不整合があります。

* 実装方針の `9.` が `8.` の内側へ誤って indent
* app/report change 時の番号が重複・飛び番
* Definition of Done の `14.` が重複
* design の一部 bullet で `-` 後の空白がなく、別項目が前項へ連結
* 「clean success」と「clean working tree」を混同し得る test 名・説明

意味論には直ちに影響しませんが、TDD step ID と evidence ledger の追跡性を損なうため採用前に直してください。

## 採用・修正・保留の判断

| 対象                                                          | 判断               | 理由                                                              |
| ----------------------------------------------------------- | ---------------- | --------------------------------------------------------------- |
| default branch + working-tree + no-base → 開始時 HEAD SHA      | **修正採用**         | Git command 構造と整合する。resolved config state と exact SHA test が必要  |
| default branch + head + no-base → explicit base requirement | **修正採用**         | 現行 VCS fatal pathを再利用可能。config由来 head testが必要                   |
| feature/detached → candidate merge-base                     | **修正採用**         | 現行 candidate helperを再利用可能。symbolic HEADではなくcaptured SHAを固定      |
| candidate解決不能 → no initial fallback                         | **採用**           | 現行 initial fallback pathを専用 errorへ置換可能                          |
| explicit base優先                                             | **修正採用**         | 処理順は現行と一致。受理するGit revision文法を明確化する必要あり                          |
| `DiffBaseResolution.default_branch_head`                    | **採用**           | field shape不変、report generic表示、legacy kind保持で整合                 |
| legacy `initial_commit_fallback` acceptance                 | **採用**           | historical/external construction互換に有効。production producerからのみ除去 |
| implicit changed-path guard                                 | **修正採用**         | raw/hunk分離で実装可能。VCS-relative/private raw path保持が必要              |
| limit `1000`                                                | **暫定採用／性能評価は保留** | 明確なpolicy boundaryだがbenchmark由来ではない                             |
| explicit base guard bypass                                  | **採用**           | 利用者の明示 intent と整合                                               |
| scope-only diagnostic                                       | **採用**           | seam-local countで成立しpublic DTO不要                                |
| app production変更なし                                          | **採用**           | 現行target failure pathがbase resolutionとobservationsをreportへ渡せる   |
| report production変更なし                                       | **採用**           | 既存FailureReason projectionとgeneric kind表示で成立                    |
| config/traversal production変更なし                             | **採用**           | `iss-00044` 境界と一致。ただしconfig-resolved state test必須               |
| read-only / offline / partial-clone safety                  | **要修正**          | lazy fetch、external diff、textconvが未遮断                           |
| `iss-00036` supersede                                       | **要修正**          | requirement/designに加えてapproved planも対象                          |
| README/help plan                                            | **修正採用**         | 基本項目は正しい。explicit grammar、Git-ignore、fixed limit、安全制約を追記        |
| implementation開始                                            | **保留**           | canonical adoption、assurance再分類、P1修正、review gateが未完了            |

## 現行 app/report/DTO との整合性

scope-only diagnostic は public DTO を追加せずに実装できます。

現行 targets は seam-local result と `TargetObservations` を返します。app は target normalization が失敗した場合、空の `TargetSet` に observations を格納し、成功済み `DiffBaseResolution` と diagnostics を `ReportInputs` へ渡します。report は既存 failure reason によって hard failure とし、同じ summary に base resolution と counter を表示します。したがって新しい public field、`FailureReason`、app/report の diagnostic-code 分岐は不要です。

推奨する local 判定は候補 design のままで成立します。

```python
python_changed_count > 0
and scope_excluded_python_count == python_changed_count
```

ただし `python_changed_count` は ignore 適用前、scope 判定と独立して数える必要があります。

## 実装前に必要な文書修正

### requirement.md

1. explicit base を「commit に peel できる Git revision expression」として定義し、`HEAD~1` との矛盾を解消する。
2. partial clone での lazy fetch を禁止対象へ追加する。
3. external diff / textconv を実行しないことを read-only・AST-only 契約へ追加する。
4. guard count に Git ignore、project-root boundary、type-change、head/untracked を明記する。
5. “configured safety limit” を “fixed safety limit” に修正する。
6. project boundary を横断する rename の扱いを決定する。
7. `iss-00036` の supersede 対象へ plan を追加する。

### design.md

1. `_resolve_base_ref(..., config.diff_current_state)` を規範的 call とする。
2. 開始時 HEAD resolver が SHA を返し、candidate merge-base の第2引数へ渡すことを明記する。
3. raw tracked entry に VCS-relative path と project-relative count key の双方を保持する。
4. guard → hunk enrichment の exact phase orderingを示す。
5. `_run_git` の no-lazy-fetch environment contract を追加する。
6. diff command の `--no-ext-diff --no-textconv --no-color` を追加する。
7. model の許容集合と error message の双方を変更面へ追加する。
8. object database / textconv cache を含む read-only receipt を追加する。

### plan.md

1. config state precedence testを追加する。
2. captured HEAD SHAをmerge-base引数で検査するtestを追加する。
3. `origin/HEAD` とconventional branch名が矛盾するcaseを追加する。
4. `rev-list --max-parents=0` 非呼び出しtestを追加する。
5. nested project + rename + guardのintegration testを追加する。
6. partial clone lazy-fetch sentinel testを必須化する。
7. external diff / textconv sentinel testを追加する。
8. `iss-00036/plan.md` supersedeを文書変更面へ追加する。
9. 番号・indent・DoD重複を修正する。
10. canonical adoption、assurance再分類、review、validate/doctorを実装開始前 gate として閉じる。

## 検証マトリクス

以下は**必要な検証計画**であり、実行済み結果ではありません。

| 領域                 | ケース                                     | 必須期待                                                            | 証拠レベル                       |
| ------------------ | --------------------------------------- | --------------------------------------------------------------- | --------------------------- |
| Explicit           | branch/tag/SHA/`HEAD~1`                 | kind=`explicit_base`、requested text保持、implicit resolver/guardなし | VCS integration             |
| Explicit           | non-commit object / missing / ambiguous | `invalid_base_ref`、fallbackなし、hunk/targetsなし                    | VCS + app                   |
| Default WT         | historical commits + WT 1件              | resolved base=start HEAD SHA、WT変更だけ                             | VCS + app                   |
| Default WT         | stale `origin/<default>`                | stale ref不使用                                                    | VCS integration             |
| Default HEAD       | CLI `--current-state head`              | requires-base、raw diff未実行                                       | VCS + CLI                   |
| Config state       | `[diff].current_state=head`             | requires-base                                                   | config + app                |
| State precedence   | config head + CLI WT                    | `default_branch_head` 成功                                        | config + app                |
| State precedence   | config WT + CLI head                    | requires-base                                                   | config + app                |
| Feature            | candidateあり                             | captured HEAD SHAとの最初のmerge-base                                | command spy + integration   |
| Detached           | candidateあり                             | captured HEAD SHAとのmerge-base                                   | VCS integration             |
| Identity           | current=`main`, origin/HEAD=`develop`   | default selfと誤認しない                                              | VCS unit/integration        |
| Identity           | slashful default                        | full name比較                                                     | VCS integration             |
| Resolution failure | candidateなし / 全merge-base失敗             | unavailable、`rev-list`なし                                        | VCS + app + CLI             |
| No commit          | unborn repository                       | `git_diff_read_failure`、downstreamなし                            | VCS                         |
| Guard              | 1000 / 1001                             | 1000通過、1001 failure                                             | helper/unit                 |
| Guard stop         | over limit                              | hunk helper 0回、targets/parse/render 0回                          | VCS + app spy               |
| Guard bypass       | 同じSHAをexplicit指定                        | guardなしでcollection継続                                            | VCS integration             |
| Count              | A/M/T                                   | 各current path 1件                                                | parameterized               |
| Count              | rename                                  | current path 1件、previous metadata保持                             | parameterized + integration |
| Count              | untracked                               | WT+include+Git非ignoreのみ1件                                       | parameterized               |
| Count              | scope外/non-Python/PyClassUML ignore     | すべてcount                                                        | parameterized               |
| Count              | Git-ignored untracked                   | count 0                                                         | VCS integration             |
| Count              | deletion-only                           | count 0                                                         | parameterized               |
| Count              | duplicate current path                  | chosen precedenceで1件                                            | unit                        |
| Nested project     | modified/rename                         | hunk commandはVCS-relative、DTOはproject-relative                  | integration                 |
| Scope-only         | outside `.py` のみ                        | warning → dedicated error                                       | targets                     |
| Scope-only         | outside `.py` + inside non-Python       | dedicated error                                                 | targets                     |
| Generic zero       | no-change/non-Python/ignored/mixed      | generic error                                                   | targets                     |
| Target transport   | scope-only fatal                        | base summary、counter、diagnostic順序保持                             | app + report                |
| DTO                | new kind                                | validation成功                                                    | model                       |
| DTO                | legacy fallback                         | validation/report成功                                             | model + report              |
| DTO                | unknown kind                            | validation failure、message正確                                    | model                       |
| Shallow clone      | merge-base object不足                     | no deepen、unavailable                                           | integration/simulation      |
| Partial clone      | missing object                          | networkなし、object DB不変、明示failure                                 | integration                 |
| Diff helper        | external/textconv configured            | helper未起動、builtin diffのみ                                        | integration sentinel        |
| Read-only          | success/failure全scenario                | HEAD/branch/index/status/refs/object DB不変                       | before/after receipt        |
| Depth              | 0/1/2                                   | base/entries/seeds同一、reachableだけ変化                              | app integration             |
| Help               | `diff --help`                           | authority・default WT・default head failureを短く説明                  | CLI                         |
| README             | decision table                          | source/testと一致、legacy/limit/depth caveat記載                      | inspection                  |
| Regression         | focused/full suite                      | baselineとの差を分類                                                  | pytest                      |
| SpecDock           | classify/review/validate/doctor         | exact command/result/hashをreportへ記録                             | workflow evidence           |

## 仮定・不確実性・未検証主張

* このレビューでは pytest、benchmark、lint、SpecDock command を実行していません。
* 添付候補の `1000` は安全 policy 値として評価しており、性能最適値とは評価していません。
* partial clone の no-lazy-fetch 手段は、2026年8月7日に参照した現行 Git 公式文書に基づきます。対象環境の最低 Git version との互換性は後続検証対象です。([Git][1])
* external diff / textconv の指摘も現行 Git 公式文書に基づきます。対象 repository の既存 test fixtureでの実測は未実施です。([Git][2])
* project boundary 横断 rename の現在の実挙動は未測定です。文書で意味論を決めた後、実 Git fixtureで確認する必要があります。
* GitHub branch上の canonical文書と添付候補の差分は確認しましたが、添付候補の採用、commit、push、PR、review passは確認していません。
* current source/testsの pass 状態や、既存baseline failureの有無は未確認です。

[1]: https://git-scm.com/docs/partial-clone.html?utm_source=chatgpt.com "Git - partial-clone Documentation"
[2]: https://git-scm.com/docs/git-diff.html?utm_source=chatgpt.com "Git - git-diff Documentation"
