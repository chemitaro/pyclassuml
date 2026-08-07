## 結論

**P0 はありません。** 添付された実装スナップショットそのものについて、指定された安全性の中核契約を破る P0/P1 の runtime defect は確認できませんでした。特に、開始時 HEAD SHA の固定、default-branch `head` の fail-closed、feature/detached 系の merge-base resolver、initial-commit fallback の production path 廃止、raw-entry→guard→hunk の順序、explicit-base guard bypass、project-relative DTO 変換、scope-only 分類、Git subprocess の offline/read-only hardening は、コード上は概ね設計どおりです。添付 bundle 全体を一次資料として監査しています。

ただし、**P1 が2件**あります。最重要なのは、GitHub connector で 2026-08-07 に確認した exact branch `codex/iss-00045-diff-implicit-base-safety` が、添付された実装状態と一致していないことです。GitHub branch 上の `diff_collect.py` は依然として default branch → initial commit、candidate exhaustion → initial commit fallback、merge-base current side=`HEAD` の旧実装です。 一方、添付版は `HEAD^{commit}` を SHA 化し、default-branch `head` を失敗、candidate exhaustion を失敗へ変更しています。

したがって、現時点の判定は **「添付実装は概ね成立しているが、exact GitHub branch と canonical authority が implementation-complete 状態ではない」** です。

---

## P1

### P1-1 — exact GitHub branch がレビュー対象実装を含んでいない

**根拠:** GitHub の指定 branch の `src/pyclassuml/vcs/diff_collect.py` では `_resolve_base_ref(vcs_root, requested_base_ref)` が `current_state` を受け取らず、default branch では `_initial_commit_base_resolution()`、candidate exhaustion でも同 fallback を返しています。また merge-base は symbolic `"HEAD"` に対して計算しています。`src/pyclassuml/vcs/diff_collect.py:221-276` 相当です。

対して添付版は `src/pyclassuml/vcs/diff_collect.py:271-313` で、no-base 時に `HEAD^{commit}` を一度 SHA 化し、default branch + `HEAD` を `diff_default_branch_head_requires_base`、candidate exhaustion を `diff_base_resolution_unavailable` にしています。

さらに GitHub branch の Issue #45 `report.md` は、実装後の Red/Green/verification ledger ではなく scaffold/template の状態です。

**再現・追加検証:** exact branch から `diff_collect.py` を取得し、添付版との blob/content parity を確認する。より強い再現として、その branch を checkout した clean clone で「複数 historical commit を持つ `main` + working-tree 1変更 + no-base」を実行し、base が HEAD SHA ではなく initial commit になることを確認できるはずです。

**採否判断:** **採用・P1 blocker。** 添付が意図的な未commit working tree である可能性はあります。その場合これはローカル実装 defect ではありませんが、**exact-branch review / merge / closure の blocker** です。branch を添付実装と一致させた新 HEAD に対し、focused/full verification を再取得する必要があります。

---

### P1-2 — `iss-00044` canonical contract が `iss-00045` と矛盾している

Issue #45 は Issue #44 の depth/config authority を維持しつつ、VCS implicit-base behavior の後続 authority を #45 として cross-reference することを要求しています。特に initial fallback は production contract から supersede されます。

しかし GitHub の指定 branch にある `iss-00044` requirement の AC-012 は現在も、

> `explicit base、merge-base、initial fallback、current-state... の既存 test が回帰しない`

という現行 acceptance を持っています。 これは Issue #45 の「production resolver は initial fallback しない」という不変条件と同時には現行契約として成立しません。

なお、**iss-00036 側の partial-supersede 方針そのものには問題を確認していません**。問題は iss-00044 側の authority handoff が未完な点です。

**再現・追加検証:** `iss-00044/{requirement,design,plan}.md` の `initial fallback` と `iss-00045` 参照を検索し、「Issue #44 実装当時の historical regression」と「Issue #45 適用後の current contract」を明確に分離できることを確認する。

**採否判断:** **採用・P1 canonical-spec blocker。** `initial fallback` の記録自体を削除する必要はありませんが、現行 acceptance として読めない supersede/authority note が requirement/design/plan の3文書に必要です。

---

## P2

### P2-1 — breadth-guard diagnostic が仕様どおりの exact remediation を出していない

Requirement RQ-010 は、guard failure の診断に resolved base と actual count、limit に加え、**同じ resolved base を `--base <resolved-sha>` として指定できる remediation** を含めることを要求しています。

実装 `src/pyclassuml/vcs/diff_collect.py:526-538` は resolved SHA 自体は message に出しますが、末尾は generic な:

`Specify --base <commit> to opt in to an explicit range.`

です。つまり情報は揃っていますが、canonical contract が要求する exact actionable form にはなっていません。

既存 test `tests/vcs/test_diff_file_collect.py:822-857` も `"base {head_sha}"` と `"2 changed paths"` までしか assert していません。

**追加テスト:** guard failure に対し `f"--base {head_sha}" in diagnostic.message` を assert する。

**採否判断:** **採用。** P2 wording/diagnostic contract 修正。

---

### P2-2 — generic zero-target message が設計より狭い

Design DES-010 は generic zero-target message が **scope・file type・ignore filtering** のいずれも原因になり得ることを表すよう要求しています。

実装 `src/pyclassuml/targets/diff.py:123-131` は:

`diff changed files produced no seed Python files after scope filtering`

だけです。

分類コード自体は正しいため runtime semantics の defect ではありませんが、non-Python-only や ignored-only の失敗に「scope filtering」とだけ出るのは原因説明として不正確です。

**追加テスト:** non-Python-only と ignored-Python-only の2ケースで generic code と、`scope/file type/ignore` を包含する message を確認する。

**採否判断:** **採用。** P2 diagnostic accuracy。

---

### P2-3 — default-branch `head` error/help の利用者向け契約が一部不足

Design は `diff_default_branch_head_requires_base` の message に、利用者が意図に応じて `HEAD~1` や `origin/<branch>` を明示できることを案内する設計です。

実装 `src/pyclassuml/vcs/diff_collect.py:286-291` は explicit `--base <ref>` が必要なことだけを通知します。 また CLI help は branch/state matrix と `HEAD~1` を含んでおり大筋は良いものの、既存 help test は `"default branch"`, `"default branchのheadでは"`, `"HEAD~1"` の存在確認に留まります。

README の decision table、explicit revision grammar、no-fallback、1000-limit、HEAD-rendering caveat は整合しており、**README 全体を不整合とは判定しません**。ただし Issue #45 plan が要求する安全フラグの説明に対して README は `lazy fetch/external diff/textconv` を記載する一方、`--no-color` は明示していません。

**追加テスト:** VCS error message に `HEAD~1` と explicit-base guidance、help に explicit base authority/no-base policy の意味が残ることを phrase-level で固定する。

**採否判断:** **採用。** P2 user-facing contract 補完。

---

### P2-4 — 実装ロジックに対する acceptance coverage が計画より不足

これは「コードが間違っている」という指摘ではなく、**計画済み assurance を現在の添付 tests だけでは閉じられない**という指摘です。Issue #45 plan は guard failure 時に targets/parse/traversal/render を呼ばない app-level test と、scope-only の詳細 matrix を明示しています。

添付 tests から直接確認できるのは、1000/1001 boundary、hunk-before-stop、explicit bypass、config-current-state authority、nested rename、Git flags、scope-outside-only/mixed ignored などです。たとえば nested rename は `tests/vcs/test_diff_file_collect.py:1067-1085` で適切に固定されています。

一方、提供された test files では少なくとも次の focused evidence が不足しています。

* detached HEAD + valid candidate / candidate unavailable
* guard count の全 matrix: included untracked、rename=1、scope-outside、non-Python、ignore予定path、project-root外=0、`head` untracked=0
* `diff_implicit_range_too_broad` の **app/CLI** hard-failure・downstream-stop
* external diff/textconv の実 sentinel 不実行、remote refs/object database 不変性
* scope-only の `outside.py + inside non-Python`、non-Python-only、ignored-only、empty 等の全 matrix
* 同一 Git state における depth `0/1/2` の **base resolution / changed entries / seed set 不変性**

特に scope-only test matrix は plan が明示的に8ケースを要求しています。

**追加テスト:** 上記をそのまま focused cases として追加する。1001-file fixture は不要で、既存どおり limit monkeypatch と synthetic raw entries で十分です。

**採否判断:** **採用。** P2 QA/traceability gap。P1-1 解消後の exact HEAD でこの evidence を取得すべきです。

---

## 指定8観点の監査結果

| 観点                                         | 添付実装判定                                    | 注記                                                                                                                                |
| ------------------------------------------ | ----------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| 1. default/head/feature base               | **実装 OK**                                 | start HEAD SHA、default+head fail、candidate exhaustion fail-closed。GitHub exact branch は P1-1                                      |
| 2. CLI/config authority / revision grammar | **実装 OK**                                 | `config.diff_current_state` が VCS authority。explicit は `<ref>^{commit}`。                                                          |
| 3. raw VCS path → project DTO              | **OK**                                    | guard までは raw VCS path、nested rename も current/previous DTO を project-relative 化。                                                 |
| 4. 1000/1001 guard                         | **ロジック OK / P2あり**                        | 1000 inclusive、1001 fail、hunk前stop、explicit bypass。remediation wording と coverage が不足                                             |
| 5. read-only/offline                       | **コード上 OK / verification 部分的**            | 全 Git subprocess に `GIT_NO_LAZY_FETCH=1`、diff に no-ext-diff/no-textconv/no-color。設計契約とも一致。                                        |
| 6. scope-only diagnostic                   | **分類ロジック OK / P2あり**                      | dedicated code と failure reason は正しい。generic message/coverage が不足                                                                 |
| 7. iss36/44/README/help                    | **iss36・README概ねOK / iss44 P1 / help P2** | iss44 の current AC が initial fallback を現行 regression として残す                                                                        |
| 8. generate/depth/config 非影響               | **実装上の破壊は確認せず / 完全検証は未成立**                | current resolver は presence-based `current_state`、diff depth=1、generate depth=None を維持。 exact 0/1/2 base/seed invariance test は不足 |

## 仮定・不確実性・未検証主張

このレビューでは **テストを実行していません**。添付 source/tests/docs の静的監査と、2026-08-07 時点で GitHub connector から取得した指定 branch の内容を突合した結果です。したがって「既存 tests が pass する」「full suite が Green」「partial clone で実際に network access が発生しない」といった実行時事実は未検証です。Issue #45 自身も partial clone 等の failure message や 1000 の benchmark 妥当性を未検証事項として明記しています。

また、GitHub branch と添付実装の差については、**添付が未commit/未pushの意図的 working-tree snapshot である可能性**を排除できません。したがって「実装が失われた」とは断定せず、確定できる主張は「現在 connector から読める exact branch は添付実装と一致せず、branch-level completion evidence としては使えない」です。

**最終 verdict:** `P0=0 / P1=2 / P2=4`。添付コードの安全性コアは採用可能ですが、**P1-1 exact-branch parity と P1-2 canonical authority conflict が解消されるまでは iss-00045 を implementation-complete と判定すべきではありません。**
