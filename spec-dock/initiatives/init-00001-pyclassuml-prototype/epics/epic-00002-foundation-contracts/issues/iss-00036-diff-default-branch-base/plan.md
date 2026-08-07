---
種別: 実装計画書（Issue）
ID: "iss-00036"
タイトル: "Diff Default Branch Base"
関連GitHub: ["#36"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-22"
依存: ["requirement.md", "design.md"]
親: ["epic-00002", "init-00001"]
---

# iss-00036 Diff Default Branch Base — 実装計画（Execution Contract）

> **後続Issueによる部分置換:** `iss-00045-diff-implicit-base-safety` は、本書のうち default branch の initial commit fallback、候補解決不能時の initial commit fallback、fallback を degraded success として返す契約、および production の `initial_commit_fallback` resolution kind を置き換える。explicit base の権威性、invalid explicit base の失敗、feature/detached の merge-base、resolution transport、read-only/current-state/untracked の境界は本書から引き継ぐ。以下の本文は当時の計画を復元する historical record として保持する。

## この計画で満たす要件ID
- AC:
  - AC-001: no-base diff が default branch candidate の merge-base を resolved base にする。
  - AC-002: explicit `--base <ref>` は従来互換で `<ref>` 自体を base にする。
  - AC-003: no-base で候補が使えない場合に initial commit object fallback を使う。
  - AC-004: no-base と `--current-state head` が既存 head semantics と整合する。
  - AC-005: invalid explicit base は fallback せず invalid base failure になる。
- EC:
  - EC-001: no commit repository は VCS failure で fail-fast する。
  - EC-002: candidate merge-base failure は次候補または fallback へ進む。
  - EC-003: current branch が default branch 自身なら initial commit object fallback に直行する。
  - EC-004: no-base でも untracked は既存 working-tree semantics に従う。
  - EC-005: no-base でも scope filtering は `targets.diff-target-normalize` に残る。
- 制約:
  - read-only Git 操作、対象コード import 不使用、明示 base 互換、deterministic resolver、resolved base observability。

## 依存関係から導く実装順序
- 依存関係の正本:
  - `design.md` の Module Dependency Diagram、インターフェース契約、ディレクトリ / ファイル変更計画。
- 順序ルール:
  - DTO / CLI bind を先に固定し、VCS resolver が no-base を表現できる状態にする。
  - VCS resolver が resolved base metadata を返してから、app/report integration へ進む。
  - user-facing docs は runtime behavior と report transcript が固まった後に更新する。
- step 依存 summary:
  - S01:
    - 依存: reviewer-pass 済み requirement / design。
    - unblock: S02 が `DiffOptions.base_ref=None` と `DiffBaseResolution` を使える。
    - 対象ファイル: `cli/bind.py`, `model/contracts.py`, `model/__init__.py`, related tests。
  - S02:
    - 依存: S01。
    - unblock: S03 が `ChangedFileCollection.base_resolution` を app/report へ transport できる。
    - 対象ファイル: `vcs/diff_collect.py`, `tests/vcs/test_diff_file_collect.py`。
  - S03:
    - 依存: S02。
    - unblock: S90 / S99。
    - 対象ファイル: `app/diff.py`, `report/policy.py`, integration/report/cli tests。
  - S90:
    - 依存: S03。
    - unblock: S99。
    - 対象ファイル: `README.md`。

## ステップ一覧
- S01:
  - 観測可能な振る舞い: `pyclassuml diff` が `--base` なしで bind でき、explicit base は従来どおり bind される。
  - 依存: none after spec gate。
  - unblock: S02。
  - 対象ファイル: CLI / model contract。
  - 閉じる要件: AC-002, AC-005 の CLI / DTO 部分。
  - レビューゲート: code-reviewer。
- S02:
  - 観測可能な振る舞い: VCS seam が explicit/no-base を解決し、resolved base metadata 付き changed-file collection を返す。
  - 依存: S01。
  - unblock: S03。
  - 対象ファイル: VCS collector。
  - 閉じる要件: AC-001, AC-003, AC-005, EC-001, EC-002, EC-003, EC-004, EC-005。
  - レビューゲート: code-reviewer。
- S03:
  - 観測可能な振る舞い: app/report/CLI transcript が同じ resolved base を使い、structured result と summary で観測できる。
  - 依存: S02。
  - unblock: S90 / S99。
  - 対象ファイル: app/report/integration tests。
  - 閉じる要件: AC-001, AC-003, AC-004 と observability constraint。
  - レビューゲート: code-reviewer。
- S90:
  - 観測可能な振る舞い: README が no-base diff、explicit base 互換、fallback、resolved-base summary を説明する。
  - 依存: S03。
  - unblock: S99。
  - 対象ファイル: README。
  - 閉じる要件: docs impact。
  - レビューゲート: spec-reviewer。
- S99:
  - 観測可能な振る舞い: issue 全体の tests / validate / reviews / final report が完了している。
  - 依存: S01-S90。
  - レビューゲート: qa-reviewer, code-reviewer, spec-reviewer。

## 要件 ↔ ステップ対応
- AC-001 -> S02, S03
- AC-002 -> S01, S02
- AC-003 -> S02, S03
- AC-004 -> S02, S03
- AC-005 -> S01, S02
- EC-001 -> S02
- EC-002 -> S02
- EC-003 -> S02
- EC-004 -> S02
- EC-005 -> S02
- docs impact -> S90
- final validation/review -> S99

## Spec-Locked Closure Index（仕様固定クロージャ索引）

| id | step | slice | type | spec link | locked expectation | observable input/state | bug class guarded | required | evidence level | closure evidence |
|---|---|---|---|---|---|---|---|---|---|---|
| tc-001 | S01 | cli-model | acceptance | AC-002 | no-base diff is valid input and explicit base remains a non-empty string | CLI argv and DTO constructors | usage-error regression / explicit-base break | yes | red-required | S01 closure |
| tc-002 | S02 | explicit-base | compatibility | AC-002, AC-005 | explicit base uses the provided ref and invalid explicit base never falls back | temp Git repo with valid/missing ref | silent wrong base / compatibility break | yes | red-required | S02 closure |
| tc-003 | S02 | default-branch-merge-base | acceptance | AC-001 | no-base feature branch resolves merge-base against deterministic default candidate | main + feature branch repo | wrong branch-start base | yes | red-required | S02 closure |
| tc-004 | S02 | initial-fallback | acceptance | AC-003, EC-002 | no usable candidate resolves to initial commit object with fallback metadata | repo without usable candidate | config/upstream requirement / empty-tree confusion | yes | red-required | S02 closure |
| tc-005 | S02 | default-branch-self | edge | EC-003 | current default branch skips candidate probing and uses initial commit object | current branch equals origin/HEAD target full branch name | empty diff on default branch / wrong candidate | yes | red-required | S02 closure |
| tc-006 | S02 | no-commit | negative | EC-001 | no commit repo fails before target parse/analyze | empty Git repo | late pipeline failure / ambiguous base | yes | red-required | S02 closure |
| tc-007 | S02 | working-tree-untracked-scope | regression | EC-004, EC-005 | no-base keeps existing untracked and scope filtering boundaries | no-base repo with untracked/scope-outside paths | VCS/targets responsibility leak | yes | red-required | S02 closure |
| tc-008 | S02 | candidate-precedence | edge | AC-001, EC-002 | no-base tries candidates in design order, skips duplicates/missing refs, and uses the first later candidate whose merge-base succeeds | repo with origin/HEAD plus duplicate/missing/failing candidates and later valid candidate | nondeterministic base / wrong candidate priority | yes | red-required | S02 closure |
| tc-009 | S03 | app-report-observability | acceptance | AC-001, AC-003, AC-004 | app uses resolved base everywhere and CommandResult/summary expose it | app diff request with no-base and head mode | base mismatch / invisible resolution | yes | red-required | S03 closure |
| tc-010 | S90 | docs | documentation | scope/docs impact | README documents no-base behavior, explicit-base compatibility, fallback, and summary fields | README diff | user-facing contract drift | yes | inspect-only | S90 closure |

## レビュー / QA ゲート方針
- RG1 step review:
  - S01-S03: code-reviewer。
  - S90: spec-reviewer。
  - pass 条件: fresh review_status: pass。
- QG1 final QA:
  - reviewer: qa-reviewer。
  - 範囲: closure coverage、missing high-value tests、integration/manual 要否。
- CG1 final code review:
  - reviewer: code-reviewer。
  - 範囲: issue-wide integrated diff。
- SG1 final spec review:
  - reviewer: spec-reviewer。
  - 範囲: requirement / design / plan / report / README / implementation 整合。

## 実行ルール（全ステップ共通）
- `report.md` に Red / Green / Refactor evidence、reviewer verdict、commit/no-op evidence を記録する。
- runtime / code / tests は dev-coder に委任する。
- shipped docs は doc-writer に委任する。
- 親 Codex が直接実装する場合は、事前に `Parent Implementation Exception` を report に記録する。
- required closure row を変更する場合は plan amendment と fresh spec-review を先に通す。

## 実装ステップ

### S01 — CLI / model no-base contract
- behavior goal:
  - CLI と model が no-base diff を valid input として表現し、explicit base 互換を保つ。
- design 参照:
  - `design.md` の CLI / Model interface contract。
- 依存:
  - reviewer-pass 済み requirement / design。
- unblock:
  - S02。
- 対象ファイル:
  - `src/pyclassuml/cli/bind.py`
  - `src/pyclassuml/model/contracts.py`
  - `src/pyclassuml/model/__init__.py`
  - `tests/cli/test_bind.py`
  - `tests/model/test_contracts.py`
- planned contract:
  - scope:
    - `--base` parser requiredness、`DiffOptions.base_ref` optional invariant、`DiffBaseResolution` / `CommandResult.diff_base_resolution` DTO と exports。
  - test obligation:
    - closure id: tc-001
    - coverage rationale: CLI usage regression と DTO invariant break は後続全 step を壊すため red-required。
  - Red / alternative evidence requirement:
    - red-required: no-base bind、explicit base bind、empty string DTO rejection、新 DTO export、CommandResult metadata invariant。
  - implementation scope:
    - allowed paths: S01 対象ファイルのみ。
    - forbidden changes: VCS resolver、app/report behavior、README。
  - Green verification:
    - `uv run pytest tests/cli/test_bind.py tests/model/test_contracts.py`
  - Refactor / cleanup guardrail:
    - DTO validation helper reuse は許可。unrelated model reshaping は禁止。
  - report evidence destination:
    - S01 Red/Green/Refactor Evidence、Step Contract Closure、Test Contract Closure、Closure Coverage、Implementation Delegation Gate、Step Commit Gate。
  - amendment trigger:
    - `DiffOptions` 以外の command option shape 変更、new public CLI flag 追加、CommandResult 以外の structured result 採用。

#### delegation contract
- delegated role:
  - dev-coder
- input docs:
  - `requirement.md`, `design.md`, `plan.md`, `workflow_issue.md`, target files listed above。
- allowed paths:
  - S01 対象ファイル。
- forbidden changes:
  - Git resolver implementation、report summary、README、unrelated DTO changes。
- acceptance criteria:
  - tc-001 close condition。
- required tests or docs-only verification:
  - `uv run pytest tests/cli/test_bind.py tests/model/test_contracts.py`
- reviewer focus:
  - code-reviewer: CLI compatibility, DTO invariants, package export consistency。
- output required:
  - changed files, verification result, unresolved risks, Ledger Note or no material decisions statement。
- stop conditions:
  - optional base cannot be represented without broader command shape change; tests cannot run; required files outside allowed paths are needed。

#### 具体テストケース一覧

- `tc-s01-001` acceptance: no-base diff bind
  - 前提: process cwd は任意の path。
  - 操作: `bind_command_request(["diff"], process_cwd)` を呼ぶ。
  - 期待結果: `CommandName.DIFF` で、`request.cli_options.diff.base_ref is None` になる。
  - 失敗検出: `--base` 省略が argparse usage error のまま残る回帰を検出する。
  - 検証方法: `tests/cli/test_bind.py`。
  - 関連 closure id: tc-001

- `tc-s01-002` compatibility: explicit base bind
  - 前提: `origin/main` を base ref として指定する。
  - 操作: `bind_command_request(["diff", "--base", "origin/main"], process_cwd)` を呼ぶ。
  - 期待結果: `base_ref == "origin/main"` で、current-state / include-untracked の既存 default が変わらない。
  - 失敗検出: explicit base の bind 互換を壊す回帰を検出する。
  - 検証方法: `tests/cli/test_bind.py`。
  - 関連 closure id: tc-001

- `tc-s01-003` invariant: DTO and export
  - 前提: model DTO を直接構築する。
  - 操作: `DiffOptions(base_ref=None, ...)`、`DiffOptions(base_ref="", ...)`、`CommandResult(diff_base_resolution=...)`、`from pyclassuml.model import DiffBaseResolution` を確認する。
  - 期待結果: `None` は valid、空文字列と invalid metadata は reject、新 DTO は package export される。
  - 失敗検出: no-base と invalid explicit ref の混同、または import seam 破損を検出する。
  - 検証方法: `tests/model/test_contracts.py`。
  - 関連 closure id: tc-001

#### step closure contract
- closure id:
  - tc-001
- close 条件:
  - S01 tests が pass し、code-reviewer が pass する。
- 検証 evidence:
  - targeted pytest command。
- report evidence:
  - Step Contract Closure / Test Contract Closure / Closure Coverage。
- 残リスク:
  - VCS resolver 未実装は S02 へ残す。

#### step gate
- step reviewer gate:
  - reviewer: code-reviewer
  - review 範囲: S01 changed files。
  - pass 条件: review_status: pass。
- commit / no-op gate:
  - closure 状態: committed
  - commit 範囲: S01 files only。
  - post-commit clean check: `git status --short` に意図しない staged / unstaged changes がないことを report に記録する。

### S02 — VCS resolved-base resolver
- behavior goal:
  - VCS seam が explicit/no-base を resolved base に変換し、base metadata 付き changed-file collection を返す。
- design 参照:
  - `design.md` の VCS interface contract。
- 依存:
  - S01。
- unblock:
  - S03。
- 対象ファイル:
  - `src/pyclassuml/vcs/diff_collect.py`
  - `tests/vcs/test_diff_file_collect.py`
- planned contract:
  - scope:
    - explicit base validation、default branch candidate merge-base、default branch self detection、initial commit fallback、fatal no-commit failure、existing untracked/scope handoff。
  - test obligation:
    - closure id: tc-002, tc-003, tc-004, tc-005, tc-006, tc-007, tc-008
    - coverage rationale: Git resolution is the primary behavioral risk and must cover happy path, compatibility, fallback, negative, and boundary cases。
  - Red / alternative evidence requirement:
    - red-required: temp Git repo tests for each closure id。
  - implementation scope:
    - allowed paths: S02 対象ファイルのみ。
    - forbidden changes: app/report summary, parser/analyzer/render behavior。
  - Green verification:
    - `uv run pytest tests/vcs/test_diff_file_collect.py`
  - Refactor / cleanup guardrail:
    - resolver helper extraction is allowed inside `diff_collect.py`; cross-module abstraction is forbidden unless required by tests。
  - report evidence destination:
    - S02 Red/Green/Refactor Evidence and closure ledgers。
  - amendment trigger:
    - candidate order change, fallback base change, use of reflog/fork-point/upstream, empty-tree fallback。

#### delegation contract
- delegated role:
  - dev-coder
- input docs:
  - `requirement.md`, `design.md`, `plan.md`, current `diff_collect.py` and VCS tests。
- allowed paths:
  - `src/pyclassuml/vcs/diff_collect.py`
  - `tests/vcs/test_diff_file_collect.py`
- forbidden changes:
  - CLI parser/model/report/docs changes, Git mutation commands, checkout-based implementation。
- acceptance criteria:
  - tc-002 through tc-008 close conditions。
- required tests or docs-only verification:
  - `uv run pytest tests/vcs/test_diff_file_collect.py`
- reviewer focus:
  - code-reviewer: deterministic Git command sequence, read-only behavior, explicit-base compatibility, edge-case coverage。
- output required:
  - changed files, verification result, unresolved risks, Ledger Note or no material decisions statement。
- stop conditions:
  - resolver needs command mutation, candidate ordering ambiguity, no way to distinguish default branch self without expanding requirement。

#### 具体テストケース一覧

- `tc-s02-001` compatibility: explicit base remains authoritative
  - 前提: temp repo に `base` tag と変更済み Python file がある。
  - 操作: `collect_diff_files` を explicit `base_ref="base"` で呼ぶ。
  - 期待結果: `base_resolution.resolution_kind == "explicit_base"` で、changed files は従来どおり収集される。
  - 失敗検出: explicit base に no-base resolver が混ざる回帰を検出する。
  - 検証方法: `tests/vcs/test_diff_file_collect.py`。
  - 関連 closure id: tc-002

- `tc-s02-002` negative: invalid explicit base does not fallback
  - 前提: temp repo に commit はあるが `missing-ref` は存在しない。
  - 操作: explicit `base_ref="missing-ref"` で `collect_diff_files` を呼ぶ。
  - 期待結果: collection は `None` で `invalid_base_ref` / `vcs_read_failure` diagnostic を返し、initial commit fallback は使われない。
  - 失敗検出: explicit typo が silent に別 base へ置き換わる回帰を検出する。
  - 検証方法: `tests/vcs/test_diff_file_collect.py`。
  - 関連 closure id: tc-002

- `tc-s02-003` acceptance: feature branch resolves default merge-base
  - 前提: `main` から `feature` を分岐し、feature 側で Python file を変更する。
  - 操作: no-base `collect_diff_files` を feature branch で呼ぶ。
  - 期待結果: `resolution_kind == "default_branch_merge_base"` で、resolved base は `main` と feature の merge-base になる。
  - 失敗検出: no-base が usage error / initial fallback / wrong candidate になる回帰を検出する。
  - 検証方法: `tests/vcs/test_diff_file_collect.py`。
  - 関連 closure id: tc-003

- `tc-s02-004` fallback: no usable candidate uses initial commit object
  - 前提: temp repo に initial commit と後続 commit があり、default branch candidate が存在しない。
  - 操作: no-base `collect_diff_files` を呼ぶ。
  - 期待結果: `resolution_kind == "initial_commit_fallback"`、`resolved_base_ref` は initial commit object、fallback diagnostic は `diff_base_initial_commit_fallback`。
  - 失敗検出: upstream/config 必須化、empty-tree fallback、または無診断 fallback を検出する。
  - 検証方法: `tests/vcs/test_diff_file_collect.py`。
  - 関連 closure id: tc-004

- `tc-s02-005` edge: default branch self uses initial commit fallback
  - 前提: `origin/HEAD -> origin/release/main` など slashful default branch を含む temp repo で、current branch が `release/main`。
  - 操作: no-base `collect_diff_files` を呼ぶ。
  - 期待結果: candidate probing せず `initial_commit_fallback` になり、full branch name が保持される。
  - 失敗検出: basename 比較や他 candidate probing による wrong base を検出する。
  - 検証方法: `tests/vcs/test_diff_file_collect.py`。
  - 関連 closure id: tc-005

- `tc-s02-006` negative: no commit repository fails fast
  - 前提: `git init` 済みだが commit がない。
  - 操作: no-base `collect_diff_files` を呼ぶ。
  - 期待結果: collection は `None` で VCS fatal diagnostic を返し、target parse/analyze 用の collection を作らない。
  - 失敗検出: ambiguous empty collection や late pipeline failure を検出する。
  - 検証方法: `tests/vcs/test_diff_file_collect.py`。
  - 関連 closure id: tc-006

- `tc-s02-007` regression: no-base preserves untracked and scope boundaries
  - 前提: no-base temp repo に tracked change、untracked Python file、project_root 外 changed file がある。
  - 操作: `current_state=working-tree` と include_untracked on/off で collection を呼ぶ。
  - 期待結果: untracked は既存設定どおり扱われ、scope outside path は VCS では collection されるか既存境界に従い、final scope filtering は targets 側へ残る。
  - 失敗検出: no-base resolver が untracked / scope filtering の責務を変える回帰を検出する。
  - 検証方法: `tests/vcs/test_diff_file_collect.py` と既存 target normalize tests の確認。
  - 関連 closure id: tc-007

- `tc-s02-008` edge: candidate precedence and next-candidate fallback
  - 前提: temp repo に `origin/HEAD` target、`origin/main`、`origin/develop`、`origin/master`、local `main/develop/master` の候補を構成し、duplicate / missing ref と merge-base failure candidate を含め、後続候補だけが valid merge-base を持つ。
  - 操作: no-base `collect_diff_files` を呼ぶ。
  - 期待結果: design の候補順どおりに missing / duplicate を skip し、merge-base failure candidate では fail-fast せず、最初に成功した後続候補を `candidate_ref` として `default_branch_merge_base` を返す。
  - 失敗検出: `origin/HEAD` priority、duplicate skip、next-candidate fallback、または deterministic order が実装と乖離する回帰を検出する。
  - 検証方法: `tests/vcs/test_diff_file_collect.py`。
  - 関連 closure id: tc-008

#### step closure contract
- closure id:
  - tc-002, tc-003, tc-004, tc-005, tc-006, tc-007, tc-008
- close 条件:
  - S02 targeted tests が pass し、code-reviewer が pass する。
- 検証 evidence:
  - targeted pytest command。
- report evidence:
  - Step Contract Closure / Test Contract Closure / Closure Coverage。
- 残リスク:
  - app/report transport は S03 で閉じる。

#### step gate
- step reviewer gate:
  - reviewer: code-reviewer
  - review 範囲: S02 changed files。
  - pass 条件: review_status: pass。
- commit / no-op gate:
  - closure 状態: committed
  - commit 範囲: S02 files only。
  - post-commit clean check: `git status --short` に意図しない staged / unstaged changes がないことを report に記録する。

### S03 — App / report / CLI transcript integration
- behavior goal:
  - app が resolved base を downstream に一貫して使い、CommandResult と summary transcript が base resolution を観測可能にする。
- design 参照:
  - `design.md` の App / Report interface contract。
- 依存:
  - S02。
- unblock:
  - S90, S99。
- 対象ファイル:
  - `src/pyclassuml/app/diff.py`
  - `src/pyclassuml/report/policy.py`
  - `tests/app/test_diff.py`
  - `tests/report/test_policy.py`
  - `tests/cli/test_main.py`
- planned contract:
  - scope:
    - base class inventory uses resolved base, `ReportInputs`/`CommandResult` carry `diff_base_resolution`, summary fields, fallback degraded outcome, head semantics integration。
  - test obligation:
    - closure id: tc-009
    - coverage rationale: VCS resolver alone cannot guarantee app/report use the same base or expose it to users。
  - Red / alternative evidence requirement:
    - red-required: app no-base integration, report summary/CommandResult assertions, console script transcript test。
  - implementation scope:
    - allowed paths: S03 対象ファイル。
    - forbidden changes: VCS resolver policy, README。
  - Green verification:
    - `uv run pytest tests/app/test_diff.py tests/report/test_policy.py tests/cli/test_main.py`
  - Refactor / cleanup guardrail:
    - summary formatting helper extraction is allowed; unrelated exit policy changes are forbidden。
  - report evidence destination:
    - S03 Red/Green/Refactor Evidence and closure ledgers。
  - amendment trigger:
    - summary field names change from design, fallback outcome differs from `degraded_success`, or CommandResult cannot carry metadata。

#### delegation contract
- delegated role:
  - dev-coder
- input docs:
  - `requirement.md`, `design.md`, `plan.md`, current app/report/CLI tests。
- allowed paths:
  - S03 対象ファイル。
- forbidden changes:
  - VCS candidate order, DTO public contract beyond S01, README。
- acceptance criteria:
  - tc-009 close condition。
- required tests or docs-only verification:
  - `uv run pytest tests/app/test_diff.py tests/report/test_policy.py tests/cli/test_main.py`
- reviewer focus:
  - code-reviewer: resolved-base transport consistency, report policy compatibility, transcript stability。
- output required:
  - changed files, verification result, unresolved risks, Ledger Note or no material decisions statement。
- stop conditions:
  - report policy requires new outcome taxonomy, CommandResult metadata cannot remain optional, or CLI streams need incompatible behavior。

#### 具体テストケース一覧

- `tc-s03-001` acceptance: app uses resolved base consistently
  - 前提: temp repo の no-base feature branch に、base class inventory が wrong base なら changed/added classification が変わる fixture を置く。
  - 操作: `run_diff` を no-base request で実行する。
  - 期待結果: changed-file collection と base class inventory が同じ `resolved_base_ref` を使い、diff class decorations が期待どおりになる。
  - 失敗検出: app が request の raw `base_ref` を再利用する回帰を検出する。
  - 検証方法: `tests/app/test_diff.py`。
  - 関連 closure id: tc-009

- `tc-s03-002` acceptance: CommandResult and summary expose base resolution
  - 前提: report inputs に `DiffBaseResolution` を渡す。
  - 操作: `write_report` を呼ぶ。
  - 期待結果: `command_result.diff_base_resolution` が同じ DTO を持ち、summary に `base_resolution`, `resolved_base`, `requested_base`, `base_candidate` が出る。
  - 失敗検出: CLI 利用者や tests から resolved base が観測不能になる回帰を検出する。
  - 検証方法: `tests/report/test_policy.py`。
  - 関連 closure id: tc-009

- `tc-s03-003` edge: fallback is degraded success
  - 前提: no-base fallback result に `diff_base_initial_commit_fallback` warning が含まれる。
  - 操作: `run_diff` または `write_report` を実行する。
  - 期待結果: outcome は `degraded_success`、warning_count は増え、summary に fallback diagnostic と base metadata が出る。
  - 失敗検出: fallback が clean/warning-only success になったり、diagnostic code が揺れる回帰を検出する。
  - 検証方法: `tests/app/test_diff.py` または `tests/report/test_policy.py`。
  - 関連 closure id: tc-009

- `tc-s03-004` acceptance: no-base head semantics
  - 前提: feature branch に HEAD committed change と working-tree-only change がある。
  - 操作: `run_diff` を no-base + `current_state=head` で実行する。
  - 期待結果: HEAD diff だけが対象になり、working-tree-only / untracked は既存仕様どおり含まれない。
  - 失敗検出: no-base resolver integration が `current_state=head` semantics を壊す回帰を検出する。
  - 検証方法: `tests/app/test_diff.py`。
  - 関連 closure id: tc-009

#### step closure contract
- closure id:
  - tc-009
- close 条件:
  - S03 targeted tests が pass し、code-reviewer が pass する。
- 検証 evidence:
  - targeted pytest command。
- report evidence:
  - Step Contract Closure / Test Contract Closure / Closure Coverage。
- 残リスク:
  - README docs は S90 で閉じる。

#### step gate
- step reviewer gate:
  - reviewer: code-reviewer
  - review 範囲: S03 changed files。
  - pass 条件: review_status: pass。
- commit / no-op gate:
  - closure 状態: committed
  - commit 範囲: S03 files only。
  - post-commit clean check: `git status --short` に意図しない staged / unstaged changes がないことを report に記録する。

### S90 — docs impact resolution / docs refresh
- 対象:
  - `README.md`
- 対応:
  - `pyclassuml diff [options] [--base <ref>]` を文書化する。
  - no-base の best effort resolution、default branch self fallback、initial commit object fallback、explicit base 互換、summary fields を説明する。
- doc update owner:
  - doc-writer
- spec/doc review:
  - reviewer: spec-reviewer
  - pass 条件: README が requirement / design / implementation behavior と整合する。

#### delegation contract
- delegated role:
  - doc-writer
- input docs:
  - `requirement.md`, `design.md`, `plan.md`, implemented CLI/report behavior, `README.md`。
- allowed paths:
  - `README.md`
- forbidden changes:
  - source code, tests, spec workflow docs。
- acceptance criteria:
  - tc-010 close condition。
- required tests or docs-only verification:
  - README inspection and `./spec-dock/scripts/spec-dock validate`。
- reviewer focus:
  - spec-reviewer: docs/spec alignment and no overstatement。
- output required:
  - changed files, docs verification, unresolved risks, Ledger Note or no material decisions statement。
- stop conditions:
  - implementation behavior differs from design, README requires new user-facing option not in requirement。

#### 具体テストケース一覧

- `tc-s90-001` inspect-only: README diff command contract
  - 前提: S01-S03 behavior is implemented.
  - 操作: README の `diff` command section を確認する。
  - 期待結果: no-base / explicit-base / current-state / fallback / summary fields が事実どおり説明されている。
  - 失敗検出: ユーザーが `--base` 必須だと誤読する、または fallback を empty tree と誤読する docs drift を検出する。
  - 検証方法: docs diff inspection + spec-reviewer。
  - 関連 closure id: tc-010

#### step closure contract
- closure id:
  - tc-010
- close 条件:
  - README が更新され、spec-reviewer が pass する。
- 検証 evidence:
  - docs inspection, `./spec-dock/scripts/spec-dock validate`。
- report evidence:
  - S90 Docs Impact Resolution, Step Contract Closure, Test Contract Closure, Closure Coverage。
- 残リスク:
  - none if spec-reviewer passes。

#### step gate
- step reviewer gate:
  - reviewer: spec-reviewer
  - review 範囲: README and spec alignment。
  - pass 条件: review_status: pass。
- commit / no-op gate:
  - closure 状態: committed
  - commit 範囲: README/report docs evidence if separate step commit is used。
  - post-commit clean check: `git status --short` に意図しない staged / unstaged changes がないことを report に記録する。

### S99 — final quality gate
- branch diff 範囲:
  - S01-S90 の統合 diff。
- 必須 validation:
  - `uv run pytest`
  - `./spec-dock/scripts/spec-dock sync`
  - `./spec-dock/scripts/spec-dock validate`
  - `git diff --check`
- final QA gate:
  - reviewer: qa-reviewer
  - 範囲: closure coverage、test sufficiency、integration/manual test 要否。
  - pass 条件: review_status: pass。
- final code review ゲート:
  - reviewer: code-reviewer
  - 範囲: issue-wide integrated diff。
  - pass 条件: review_status: pass。
- final spec review ゲート:
  - reviewer: spec-reviewer
  - 範囲: requirement / design / plan / report / README / implementation / tests 整合。
  - pass 条件: review_status: pass。
- final commit gate:
  - commit 範囲: final report ledger updates and any remaining issue-wide changes。
  - final report ledger: all closure ids pass, all reviewer gates pass, no open decision ledger entries。
  - post-commit external evidence destination: final response / PR description。
- PR delivery gate:
  - owner: github-pr-merge-preparer。
  - pass 条件: branch push、existing PR reuse / new PR creation decision、draft/ready decision、PR URL、selected base、base-resolution source、base-resolution conflict handling、head branch、head SHA、関連 issue linkage、PR description に final evidence が記録されている。
  - evidence: `report.md` の PR Delivery Gate と final response に PR URL、selected base、base-resolution source、conflict handling decision、draft/ready decision、head branch、head SHA、issue linkage、push result、existing/new PR decision を記録する。
- merge-preparation gate:
  - owner: github-pr-merge-preparer。
  - pass 条件: required checks / Codex review / open review comments / unresolved blockers を確認し、人間が merge 判断できる状態として report に記録する。
  - evidence: PR status, check status, unresolved risk summary。

## Final Exit Contract
- 実装前:
  - requirement / design / plan の fresh spec-reviewer pass が `report.md` に記録されている。
- 各 step:
  - required closure ids が Step Contract Closure / Test Contract Closure / Closure Coverage で pass。
  - Implementation Delegation Gate と reviewer gate が pass。
  - Step Commit Gate が committed または正当な approved-no-op。
- final:
  - S99 validation と qa-reviewer / code-reviewer / spec-reviewer が pass。
  - `./spec-dock/scripts/spec-dock sync` が pass。
  - `./spec-dock/scripts/spec-dock validate` が pass。
  - PR Delivery Gate と Merge Preparation Gate が pass。
  - final commit 後に意図しない staged / unstaged changes がない。

## 未確定事項
- なし:
  - requirement / design の未確定事項は design で閉じ、plan は実行契約へ変換済み。
