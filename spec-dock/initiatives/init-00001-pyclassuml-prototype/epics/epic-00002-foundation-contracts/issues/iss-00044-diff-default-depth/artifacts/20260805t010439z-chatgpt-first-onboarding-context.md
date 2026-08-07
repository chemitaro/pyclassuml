---
種別: onboarding / context companion
対象: "iss-00044"
状態: "candidate-evidence"
作成者: "ChatGPT"
最終更新: "2026-08-05"
---

# iss-00044 canonical candidate — onboarding / context

## 1. この companion の役割

この文書は、同梱する `requirement.md`、`design.md`、`plan.md` を既存 repository 文脈へ統合する担当者向けの handoff である。候補3文書の契約本文に混ぜるべきでない現状差分、過去判断、既知 failure、未検証事項をまとめる。

本 ZIP は Markdown 候補/evidence だけを含む。repository、canonical docs、active state、assurance state、GitHub Issue、branch、commit を変更していない。review pass、implementation complete、tests Green、canonical adoption を主張しない。

## 2. target identity

GitHub connector で確認した target:

```text
repository: chemitaro/pyclassuml
branch: codex/iss-00044-chatgpt-first-planning
commit: d04c6aa175d1f6261c7c4378435b5d54b4efef27
branch comparison: commit と identical
GitHub Issue: #44 "Diff Default Traversal Depth"
Issue state: open
```

Issue identityを維持するため、候補3文書の front matter title は既存の `"Diff Default Traversal Depth"` のままとした。ただし、最新決定により実質 scope は「default depth + common config base + command override」へ拡張されている。

## 3. evidence set

### GitHub branch で直接確認した主な対象

- `AGENTS.md`
- `src/pyclassuml/config/resolver.py`
- `src/pyclassuml/cli/bind.py`
- `tests/config/test_context_resolve.py`
- `tests/analyze/test_traversal.py`
- `tests/vcs/test_diff_file_collect.py`
- current Issue requirement
- latest ADR artifact
- superseded interview artifact
- GitHub Issue #44

### 添付 bundle で確認した対象

- `README.md`
- resolver / bind / contracts / traversal / diff collector
- config / CLI / app generate / app diff tests
- parent Epic requirement / design / plan / report
- current Issue requirement / design / plan / report
- ChatGPT design-review artifact
- compatibility interview
- formal-planning evidence-mode interview
- common-config command-overrides ADR
- SpecDock workflow / authoring docs

添付 bundle の内容と GitHub branch で直接取得した key files は、主要な識別子・契約・source behavior について一致していた。ただし bundle 全ファイルの byte identity を connector 上で検証したわけではない。

## 4. 最新ユーザー決定

同梱候補が採用する決定:

```text
トップレベル共通設定
  + [generate] / [diff] の共通キー上書き
  + [diff] の current_state / include_untracked
```

共通キー:

```text
project_root
package_root
scope_root
output
ignore
depth
mode
target_python
relative_path_base
```

precedence:

```text
CLI の当該コマンドで明示した値
  > command section
  > top-level common
  > command default
```

depth:

```text
generate: all unset -> None
diff: all unset -> 1
explicit 0: valid
```

撤回済み:

```text
command-specific config only
top-level depth 廃止
legacy top-level fallback としてのみ残す設計
```

latest ADR artifact は同じ決定を記録しているが、front matter は `draft` / non-authoritative のままである。今回のユーザープロンプトが明示した最新決定を primary instruction として候補文書へ反映した。

## 5. current source facts

### `src/pyclassuml/config/resolver.py`

現行実装:

- `_TOP_LEVEL_KEYS`:
  - 9 個の共通キー
  - `"diff"`
- `_DIFF_KEYS`:
  - `current_state`
  - `include_untracked`
- `[generate]` table:
  - 未対応
- `[diff]` の共通キー:
  - 未対応
- `depth`:
  - `_merged_depth(options.depth, config.get("depth"))`
  - command-aware default なし
- `relative_path_base`:
  - top-level だけ
- merge:
  - `ignore=options.ignore if options.ignore else tuple(config.get("ignore", ()))`
  - root/output/depth/target_python は raw CLI > top-level
  - Diff bool/enum は provided flag > `[diff]` > default

したがって、candidate target は未実装である。

### `src/pyclassuml/cli/bind.py`

現行 CLI contract:

- common:
  - `--cwd`
  - `--config`
  - `--project-root`
  - `--package-root`
  - `--scope-root`
  - `--output`
  - repeatable `--ignore`
  - `--depth`
  - `--strict`
  - `--target-python`
- generate:
  - positional `targets`
- diff:
  - `--base`
  - `--current-state`
  - `--include-untracked` / `--no-include-untracked`

raw presence:

- depth unset `None`
- depth 0 `0`
- strict unset `False`
- current_state/include_untracked は explicit flags あり

candidate design は production bind behavior を変更しない。

### `src/pyclassuml/model/contracts.py`

維持する型:

```text
CommandOptions.depth: int | None
AnalysisConfig.depth: int | None
DiffOptions.current_state_cli_provided: bool
DiffOptions.include_untracked_cli_provided: bool
```

public DTO へ config layer/origin を追加しない。

### traversal

現行 semantics:

- seed hop 0
- direct import hop 1
- `depth=None` unlimited
- `hop > depth` で stop
- module limit `1000`
- deterministic sort / cycle termination

candidate design は traversal source を変更しない。

### VCS

現行 semantics:

- explicit `--base` は authoritative
- invalid explicit base は failure、no-base fallback なし
- no-base は default branch candidate との merge-base
- usable candidate がなければ initial commit fallback
- `working-tree` / `head`
- working-tree の untracked include/exclude
- head + include_untracked は no-op warning
- rename/current-side changed-file collection
- Git read-only

candidate design は VCS source を変更しない。

## 6. current tests と意図的 Red

添付/current branch tests には、source 実装より先行する contract がある。

明確な mismatch:

```text
tests/config/test_context_resolve.py::
  test_diff_default_depth_is_one_without_cli_or_config
```

期待 `1` に対し、current `_merged_depth(None, None)` は `None`。

app-level mismatch 候補:

```text
tests/app/test_diff.py::
  test_diff_changed_seed_files_each_remain_hop_zero_at_default_depth
```

current report は、default depth が unlimited のため reachable count が期待 `3` に対して実測 `4` となる intended Red を記録している。

current report の historical evidence:

```text
coordinator environment:
  443 passed / 2 intended Red

別 reviewer environment:
  438 passed / 7 failed
  うち 5 件は DNS / dependency resolution と分類
```

これらの test count は今回の authoring session では再実行していない。独立検証済みとして扱わない。

## 7. current docs との差分

### current Issue `requirement.md`

現行記述:

- top-level `depth` は generate/diff 共通
- precedence `CLI > top-level depth > command default`
- `[diff].depth` は対象外
- command override は対象外

candidate:

- top-level 9 keys を formal common base
- `[generate]` / `[diff]` が全9 keysを override
- precedence に command section を追加
- `[diff].depth` と `[generate].depth` を正式化
- Diff 固有 key は同じ `[diff]` に共存

### current Issue `design.md`

現行設計:

- resolver の `_resolve_depth` 相当だけを最小変更
- CLI/traversal/VCS/DTO unchanged
- command-specific config なし

candidate:

- resolver-only production ownership は維持
- schema validation、section extraction、presence-based generic selection、origin-aware path resolution を追加
- public DTO/traversal/VCS unchanged
- source change は depth helper より広いが config seam 内に局在

### current Issue `plan.md`

現行 plan:

- S01 は command-aware depth default
- S02 は bind/app/traversal/VCS regression
- `[generate]` / `[diff]` common override test なし
- `relative_path_base` command override test なし
- collision/invalid placement test なし

candidate:

- schema → selection/presence → path/default → integration の順に分解
- 9 common keys の test matrix
- command-specific path base、ignore clear、Diff-only collision、targets/base rejection
- migration/docs/full suite を追加

### current README

現行 README:

- top-level common config
- `[diff]` は current_state/include_untracked only
- CLI > config
- command section override なし
- diff default depth 1 の説明なし

candidate implementation 後に更新が必要。

## 8. superseded / stale artifacts

### compatibility interview

`20260804t224225z-interview-depth-compatibility-fallback-question.md` は、回答欄に command-specific only / top-level depth 廃止を記録しているが、同 artifact 内で 2026-08-05 に撤回済み・stale と明示されている。

canonical adoption に使うべきでない旧判断:

```text
[generate].depth / [diff].depth only
top-level depth unsupported
migration unnecessary
```

### formal planning evidence-mode interview

`20260804t225509z-interview-formal-planning-evidence-mode-selection.md` は unanswered/proposed template state を残し、古い detached HEAD `8bb20e9faa060e68900045c0aa1d13040ec3759f` と GitHub exact branch 不成立を前提にしている。

今回 connector では named branch が存在し、HEAD は `d04c6aa175d1f6261c7c4378435b5d54b4efef27` と identical であるため、古い branch-sync blocker は current snapshot へそのまま適用できない。ただし、artifact 自体の unanswered state や current SpecDock workflow stateを今回変更していない。

### latest ADR

`20260804t232417z-adr-common-config-command-overrides-decision.md` は current user decision と一致する。ただし:

- `状態: draft`
- `authority: draft`
- `accepted_authority` empty
- `mirror_eligible: false`
- `reflected_to: []`

candidate docs への採用 evidence であり、accepted ADR と主張しない。

## 9. process blockers / current report

current Issue report は次を記録する。

- production source / README 未変更
- pre-implementation spec review #1〜#14 fail
- #15 pending
- `D-014` open/deferred:
  - Standard profile と公開 CLI behavior change の Strict trigger
  - formal Strict/policy-supported route が必要という判断
- S00 test-only preparation は実施済みとの記録
- S00-PROMOTE / S01 production implementation は blocked
- code review / QA review / final spec review は未完

今回の candidate authoring は、`D-014`、assurance projection、review status、runbook readiness を解消・更新していない。Codex 側統合時に current policy と candidate scope を再評価する必要がある。

## 10. quality baseline

current report が記録する既存 baseline:

- full Ruff:
  - `src/pyclassuml/render/document.py` の F821 4件
- format:
  - 32 files が reformat candidate
- fixed tool:
  - `ruff==0.9.3`

今回独立再実行なし。candidate plan は次の原則を採用する。

- changed path の新規 lint/format failure は blocking。
- repository-wide existing baseline を broad repair しない。
- full test は final gate で必須。
- environment-only failure は exact output と supported verification path を記録。
- intended Red は implementation 後に残さない。

## 11. candidate design の重要な解釈

### command-specific `relative_path_base`

candidate は、active command の effective `relative_path_base` を一度選び、トップレベルから継承した path を含むすべての config-origin path に適用する。

例:

```toml
project_root = "project"

[diff]
relative_path_base = "cwd"
```

- generate: config file parent / `project`
- diff: `execution_cwd` / `project`

これは source にまだ存在しない新契約である。統合時に別解釈を採用する場合は requirement/design/plan の3文書を同時に改訂する。

### empty path validation

candidate は empty path string を invalid とする。現行 source は string type だけを検証し、empty string を明示的には拒否しない。これは safety hardening かつ小さな互換性変更である。受け入れない場合は requirement の RQ-009、AC-009、migration、design validation、plan tests を一括修正する。

### inactive section validation

candidate は inactive command section も schema/type/domain validation する。一方、filesystem existence/containment は active section の effective path だけに適用する。

## 12. remaining product constraints

本 Issue で解消しない。

- explicit unlimited diff sentinel
- CLI `warn` override
- CLI ignore clear-to-empty
- `[generate].targets`
- `[diff].base`
- HEAD blob-only rendering
- config include/profile
- multiple package/scope roots

別 Issue 化する場合も、current issue の acceptance を曖昧にしない。

## 13. integration checklist

1. target branch/commit を再確認。
2. candidate3文書と latest user decision を照合。
3. empty path / command base / inactive validation の3解釈を owner が承認。
4. current process blocker `D-014` の disposition を決定。
5. formal review gate を通す。
6. canonical docs を command-first workflow で更新。
7. S01以前に exact Red baseline を再実行。
8. resolver-only production implementation。
9. focused + full quality。
10. reportへ actual evidence。
11. commit/push/PR/merge は別指示に従う。

## 14. 未検証主張

次は今回の authoring session で独立検証していない。

- historical test pass/fail counts
- historical Ruff/format counts
- current local working tree status
- current SpecDock assurance/workflow/runbook runtime output
- #14 review findingの現在有効性
- source bundle 全ファイルと GitHub branch の byte identity
- CI status

Codex 側で source checkout と current commands により再検証する。
