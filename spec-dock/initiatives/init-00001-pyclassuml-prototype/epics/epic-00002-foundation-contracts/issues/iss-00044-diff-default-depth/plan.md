---
種別: 実装計画書（Issue）
ID: "iss-00044"
タイトル: "Diff Default Traversal Depth"
状態: "draft"
作成者: "ChatGPT"
最終更新: "2026-08-05"
依存: ["requirement.md", "design.md"]
親: ["epic-00002", "init-00001"]
---

# iss-00044 Diff Default Traversal Depth — 実装計画（canonical 候補）

> 本書は implementation candidate である。branch `codex/iss-00044-chatgpt-first-planning` / commit `d04c6aa175d1f6261c7c4378435b5d54b4efef27` に対する変更を実行したものではなく、commit、push、PR、canonical promotion、review pass を主張しない。

## 1. 計画の目的

次の target behavior を、責務境界を壊さずに実装・検証する。

- トップレベル共通設定を正式ベースとして維持する。
- `[generate]` / `[diff]` に 9 個すべての共通設定を許可する。
- `CLI > command section > top-level common > command default` を全フィールドに適用する。
- `relative_path_base` を config-origin path より先に解決する。
- `current_state` / `include_untracked` を Diff 固有として維持する。
- default depth を `generate=None`, `diff=1` とする。
- explicit `depth=0` を保持する。
- targets / `--base` / VCS / traversal / DTO / module limit / read-only / AST-only を変更しない。

## 2. 完了条件

次をすべて満たした時点で implementation complete 候補とする。

1. `requirement.md` の `AC-001`〜`AC-015` が test/evidence に対応する。
2. `design.md` の schema、selection、path order が source と一致する。
3. current intended Red tests が Green になる。
4. 9 個の共通キーの top/common/command/CLI precedence を focused tests が検証する。
5. invalid config、collision、empty/zero/false の edge case を focused tests が検証する。
6. VCS/traversal/parse/DTO production source に不要な変更がない。
7. app-level generate/diff depth behavior が Green。
8. README が target config shape と一致する。
9. focused tests、full tests、changed-path lint/format、`git diff --check` が合格する。
10. repository-wide既存 baseline failure がある場合、Issue 由来の failure と分離して report へ記録する。
11. SpecDock validate/doctor と必要な review gate を通す。
12. report に actual commands、results、changed files、unresolved risks を記録する。

## 3. 実行前 baseline

### 3.1 repository identity

実装開始前に次を固定する。

```bash
git branch --show-current
git rev-parse HEAD
git status --short --untracked-files=all
```

期待 snapshot:

```text
branch: codex/iss-00044-chatgpt-first-planning
HEAD: d04c6aa175d1f6261c7c4378435b5d54b4efef27
```

異なる場合は target ref を再確認し、別 snapshot の結果を混在させない。

### 3.2 source/test mismatch baseline

現行 source inspection:

```bash
rg -n "_TOP_LEVEL_KEYS|_DIFF_KEYS|_merged_depth|depth=_merged_depth" \
  src/pyclassuml/config/resolver.py
```

現行期待:

- `[generate]` schema なし。
- `[diff]` common override なし。
- `_merged_depth(None, None) -> None`。
- `diff` default test は Red になり得る。

実装前に exact focused tests を実行し、Red/Green を report へ記録する。

```bash
uv run pytest \
  tests/config/test_context_resolve.py::test_diff_default_depth_is_one_without_cli_or_config \
  tests/config/test_context_resolve.py::test_generate_default_depth_is_none_without_cli_or_config \
  tests/cli/test_bind.py::test_bind_depth_preserves_none_and_explicit_zero \
  tests/app/test_diff.py::test_diff_changed_seed_files_each_remain_hop_zero_at_default_depth \
  tests/app/test_generate.py::test_generate_default_depth_remains_unlimited \
  -q
```

### 3.3 process baseline

current report が記録する assurance/profile、fresh spec reviewer、environment variance は独立 gate として再確認する。本計画はそれらを自動的に解消しない。

## 4. 変更範囲

### 4.1 production source

必須:

- `src/pyclassuml/config/resolver.py`

原則変更しない:

- `src/pyclassuml/cli/bind.py`
- `src/pyclassuml/model/contracts.py`
- `src/pyclassuml/analyze/traversal.py`
- `src/pyclassuml/vcs/diff_collect.py`
- targets / parse / render / report production modules

`bind.py` は CLI help text だけで README 要件を満たせない場合に限り変更候補とする。raw bind/default/presence contract は変更しない。

### 4.2 tests

- `tests/config/test_context_resolve.py`
- `tests/cli/test_bind.py`
- `tests/app/test_diff.py`
- `tests/app/test_generate.py`
- `tests/analyze/test_traversal.py`
- `tests/parse/test_module_parse_and_index.py`
- `tests/vcs/test_diff_file_collect.py`

新 fixture は同じ test file の `tmp_path` 内に限定し、repository fixture/data を恒久変更しない。

### 4.3 docs

- `README.md`
- Issue `requirement.md`, `design.md`, `plan.md`, `report.md` は canonical adoption workflow が許可した場合だけ更新する。

### 4.4 forbidden

- target project source/Git metadata の変更
- `.agents/skills/pyclassuml-repo-map`
- unrelated SpecDock managed bundle
- `.serena/project.yml` の既存 user change
- dependency 追加
- commit/push/PR/merge/Issue close（別途明示指示がない限り）

## 5. 実装順序

| step | 目的 | 依存 | 主な path |
|---|---|---|---|
| `S00` | spec/baseline/Red の固定 | なし | docs/report、inspection |
| `S01` | schema validation と key set | S00 | resolver + config tests |
| `S02` | layered selection と CLI presence | S01 | resolver + config/bind tests |
| `S03` | relative path order / roots / depth default | S02 | resolver + config tests |
| `S04` | app/traversal/VCS/parse regression | S03 | tests only |
| `S90` | README / migration / known constraints | S03 | README |
| `S99` | full quality、review、handoff | S04, S90 | full repo checks/report |

順序を変更し、path resolve を schema/selection より先に実装してはならない。

## 6. S00 — specification / baseline gate

### 6.1 作業

- latest user decision と candidate requirement/design/plan を照合する。
- current canonical docs の旧記述を一覧化する。
- source/test baseline を exact command で記録する。
- current branch/HEAD/status を固定する。
- process gate の blocking/non-blocking を report で分類する。

### 6.2 exit criteria

- command-specific only / top-level 廃止案が active requirement に残っていない。
- source 未実装と先行 tests を明確に分離。
- S01 の allowed path と Red test が確定。
- unrelated working tree change を消していない。

## 7. S01 — schema と validation

### 7.1 production change

`resolver.py` の key set を次へ再構成する。

```python
_COMMON_CONFIG_KEYS
_DIFF_ONLY_CONFIG_KEYS
_COMMAND_TABLE_KEYS
_TOP_LEVEL_KEYS
_GENERATE_KEYS
_DIFF_KEYS
```

追加/変更 helper 候補:

```python
_validate_config_schema
_validate_common_section
_validate_generate_section
_validate_diff_section
_validate_non_empty_path_string
_qualified_field_name
```

### 7.2 必須 behavior

- top-level: common + `generate` / `diff`
- `[generate]`: common only
- `[diff]`: common + diff-only
- common/diff-only disjoint guard
- non-table section failure
- all-section type/domain validation
- path string non-empty
- `ignore=[]` valid
- `depth` bool/negative invalid
- section-qualified message

### 7.3 tests

新規 test 候補:

```text
test_top_level_common_schema_remains_valid
test_generate_table_accepts_all_common_keys
test_diff_table_accepts_all_common_keys_and_diff_specific_keys
test_non_table_generate_is_failure
test_non_table_diff_is_failure
test_unknown_generate_key_is_failure
test_unknown_diff_key_is_failure
test_top_level_diff_only_key_is_failure
test_generate_diff_only_key_is_failure
test_generate_targets_config_key_is_failure
test_diff_base_config_key_is_failure
test_command_common_value_validation_reports_qualified_field
test_empty_config_path_value_is_failure
test_command_ignore_empty_list_is_valid
```

既存 validation parameterization は top-level / generate / diff の各 origin を追加する。

### 7.4 focused command

```bash
uv run pytest tests/config/test_context_resolve.py -q
```

### 7.5 exit criteria

- schema tests Green。
- path resolution behavior はまだ変更してもよいが、unknown/type/domain contract が固定。
- `traversal.py`, `diff_collect.py`, `contracts.py`, `bind.py` に production diff なし。

## 8. S02 — layered selection と presence

### 8.1 production change

private origin/presence helper を追加する。

```python
_MISSING
_ValueOrigin
_SelectedValue
_select_value
```

または同等の明示的 implementation とする。必須条件は次。

- config layer は `key in mapping` で presence 判定。
- CLI `depth` は `is not None`。
- command `depth=0` を保持。
- command `ignore=[]` を保持。
- Diff bool/enum は existing `*_cli_provided` を使う。
- `ignore` は replacement。
- `mode` は `--strict` true のときだけ CLI override。
- `relative_path_base` に CLI layer を作らない。

### 8.2 tests

```text
test_generate_command_section_overrides_top_level_common_values
test_diff_command_section_overrides_top_level_common_values
test_inactive_command_section_does_not_override_active_command
test_cli_common_values_override_command_and_top_level_config
test_cli_and_config_depth_precedence_preserves_zero
test_command_depth_zero_overrides_top_level_depth
test_command_ignore_empty_list_clears_top_level_ignore
test_cli_ignore_replaces_command_and_top_level_ignore
test_command_mode_warn_overrides_top_level_strict_without_cli
test_cli_strict_overrides_command_mode_warn
test_cli_diff_unset_current_state_uses_config_before_default
test_cli_no_include_untracked_overrides_config_true
```

9 個の共通キーすべてについて、少なくとも top/common/command selection を parameterized または明示 test で閉じる。roots は directory fixture、output は path assertion、scalar/list は direct assertion を使う。

### 8.3 CLI boundary

既存 test を維持/拡張する。

```bash
uv run pytest tests/cli/test_bind.py -q
```

必須 assertion:

- `generate` / `diff` の `--depth` 未指定は raw `None`
- `--depth 0` は raw `0`
- `--strict` 未指定は raw `False`
- Diff `--no-include-untracked` は value `False` + provided `True`
- resolver 後だけ default `diff=1` が現れる

### 8.4 exit criteria

- all precedence tests Green。
- truthiness bug を再現する negative case がある。
- public DTO field change なし。
- bind raw contract change なし。

## 9. S03 — path order、roots、depth default

### 9.1 production change

順序:

1. active command section
2. effective `relative_path_base`
3. config base
4. project/package/scope selection
5. origin-aware path resolution
6. existence/containment
7. output
8. remaining AnalysisConfig
9. Diff specific

`_merged_root` / `_config_base` / `_merged_depth` は責務に合わせて改名・分割してよいが、不要な public abstraction は追加しない。

depth helper:

```python
def _default_depth(command: CommandName) -> int | None:
    if command is CommandName.DIFF:
        return 1
    if command is CommandName.GENERATE:
        return None
    raise AssertionError(f"unsupported command: {command}")
```

### 9.2 path tests

```text
test_command_relative_path_base_cwd_resolves_command_paths_from_execution_cwd
test_command_relative_path_base_applies_to_inherited_top_level_paths
test_generate_and_diff_can_resolve_same_top_level_path_from_different_effective_bases
test_cli_paths_ignore_config_relative_path_base
test_default_project_root_remains_config_parent_when_path_is_absent
test_package_and_scope_defaults_use_resolved_effective_parent
test_command_project_root_changes_diff_vcs_root_after_config_discovery
test_cli_project_root_still_has_config_discovery_priority
test_config_project_root_does_not_participate_in_config_discovery
test_command_root_containment_violation_is_failure
```

### 9.3 depth tests

既存:

```text
tests/config/test_context_resolve.py::test_diff_default_depth_is_one_without_cli_or_config
tests/config/test_context_resolve.py::test_generate_default_depth_is_none_without_cli_or_config
tests/config/test_context_resolve.py::test_cli_and_config_depth_precedence_preserves_zero
```

追加:

```text
test_diff_command_depth_overrides_top_level_depth
test_generate_command_depth_overrides_top_level_depth
test_top_level_depth_applies_to_both_commands_when_command_depth_absent
test_diff_default_depth_applies_only_when_all_layers_absent
```

### 9.4 focused command

```bash
uv run pytest tests/config/test_context_resolve.py tests/cli/test_bind.py -q
```

### 9.5 exit criteria

- current intended resolver Red が Green。
- inherited path + command base contract が Green。
- roots/containment regression なし。
- diff-specific behavior regression なし。

## 10. S04 — integration / regression

### 10.1 app integration

必須 nodeids:

```text
tests/app/test_diff.py::test_diff_changed_seed_files_each_remain_hop_zero_at_default_depth
tests/app/test_diff.py::test_diff_explicit_depth_two_reaches_transitive_dependency
tests/app/test_diff.py::test_diff_config_depth_two_reaches_transitive_dependency
tests/app/test_generate.py::test_generate_default_depth_remains_unlimited
```

追加:

```text
test_diff_command_section_depth_two_reaches_transitive_dependency
test_generate_command_section_depth_zero_keeps_seed_only
test_generate_and_diff_use_different_output_and_scope_from_same_config
```

A→B→C fixture 期待:

| command/config | reachable |
|---|---|
| default `diff` | A, B |
| top-level `depth=2` | A, B, C for both |
| `[diff].depth=2` | A, B, C for diff |
| default `generate` | A, B, C |
| `[generate].depth=0` | seed only |

### 10.2 traversal regression

```bash
uv run pytest tests/analyze/test_traversal.py -q
```

重要 nodeids:

```text
test_depth_zero_keeps_seed_only
test_depth_one_includes_direct_import_only
test_multiple_import_candidates_share_same_hop
test_depth_none_traverses_transitively
test_depth_none_terminates_deterministically_on_cyclic_imports
test_module_limit_returns_partial_result_and_fatal_diagnostic
test_module_limit_applies_to_initial_seed_frontier
test_reachable_files_and_edges_are_deterministically_ordered
```

`src/pyclassuml/analyze/traversal.py` に production diff がないことを確認する。

### 10.3 parse / AST-only regression

```bash
uv run pytest tests/parse/test_module_parse_and_index.py -q
rg -n "ast\.parse|importlib|__import__|exec\(|eval\(" src/pyclassuml/parse/indexer.py
```

重要 contract:

- depth=1 でも parse frontier を狭めない。
- deeper syntax diagnostic が必要な既存 test は維持。
- target modules を import/exec/eval しない。

### 10.4 VCS regression

```bash
uv run pytest tests/vcs/test_diff_file_collect.py -q
```

重要 nodeids:

```text
test_working_tree_tracked_added_modified_renamed_and_delete_excluded
test_explicit_base_sets_authoritative_base_resolution
test_invalid_explicit_base_does_not_fallback
test_no_base_feature_branch_resolves_default_branch_merge_base
test_no_base_without_usable_candidate_uses_initial_commit_fallback
test_head_diff_uses_head_not_working_tree
test_working_tree_untracked_included_excluded_and_empty_success
```

`src/pyclassuml/vcs/diff_collect.py` に production diff がないことを確認する。

### 10.5 DTO regression

```bash
git diff -- src/pyclassuml/model/contracts.py
```

期待: empty。`AnalysisConfig.depth` / `CommandOptions.depth` は `int | None` のまま。

### 10.6 exit criteria

- app/traversal/parse/VCS focused tests Green。
- default diff behavior 以外の output/diagnostics regression なし。
- source diff が resolver に局在。
- read-only / AST-only evidence が残る。

## 11. S90 — README と migration

### 11.1 README 更新

最低限、次を反映する。

1. top-level common 9 keys
2. `[generate]` / `[diff]` common override
3. Diff 固有 `current_state/include_untracked`
4. precedence
5. `generate=None` / `diff=1`
6. seed hop 0 / direct import hop 1
7. explicit `depth=0`
8. `relative_path_base` を先に解決し inherited path にも適用
9. CLI path は execution_cwd
10. ignore は project_root-relative
11. command `ignore=[]` clear / CLI empty clear 不可
12. generate targets は positional only
13. diff base は CLI-only
14. Git explicit/no-base/current-state/untracked behavior
15. explicit unlimited diff なし
16. `--strict` one-way
17. current-state head の current-side source 制約

### 11.2 example

README example は requirement/design と同じ config shape を使い、トップレベル key を table 宣言より前に置く。

### 11.3 docs validation

```bash
rg -n "\[generate\]|\[diff\]|relative_path_base|depth|current_state|include_untracked|--base" README.md
```

誤記禁止:

- top-level common は deprecated
- command-specific only
- `[generate].targets`
- `[diff].base`
- `depth` が parse frontier を制限
- `current_state=head` が自動的に HEAD blob を render

### 11.4 exit criteria

- source/test behavior と README が一致。
- migration/known constraints が明示。
- source/tests へ docs step 由来の変更なし。

## 12. test closure matrix

| Test ID | requirement | design obligation | concrete evidence |
|---|---|---|---|
| `TC-001` | AC-001/002 | schema + active section | config section tests |
| `TC-002` | AC-003/004 | generic selection/default | precedence/default tests |
| `TC-003` | AC-005 | list replacement | empty/CLI ignore tests |
| `TC-004` | AC-006/007 | base-first/origin path | relative path tests |
| `TC-005` | AC-008/009 | collision/full validation | invalid config tests |
| `TC-006` | AC-010/011 | targets/base boundaries | config reject + existing target/VCS tests |
| `TC-007` | AC-012 | downstream unchanged | traversal/parse/VCS/DTO |
| `TC-008` | AC-013 | app wiring | generate/diff A→B→C |
| `TC-009` | AC-014 | backward compatibility | existing top-level/diff config tests |
| `TC-010` | AC-015 | docs/full quality | README/full suite/lint/SpecDock |

## 13. focused test command set

```bash
uv run pytest tests/config/test_context_resolve.py -q
uv run pytest tests/cli/test_bind.py -q
uv run pytest \
  tests/app/test_diff.py::test_diff_changed_seed_files_each_remain_hop_zero_at_default_depth \
  tests/app/test_diff.py::test_diff_explicit_depth_two_reaches_transitive_dependency \
  tests/app/test_diff.py::test_diff_config_depth_two_reaches_transitive_dependency \
  tests/app/test_generate.py::test_generate_default_depth_remains_unlimited \
  -q
uv run pytest tests/analyze/test_traversal.py -q
uv run pytest tests/parse/test_module_parse_and_index.py -q
uv run pytest tests/vcs/test_diff_file_collect.py -q
```

新規 exact nodeids は実装時に report の closure table へ確定名で記録する。

## 14. S99 — full quality gate

### 14.1 full tests

```bash
uv run pytest
```

必須判断:

- new functional failure: blocking
- environment/network-only failure: command/output/reproduction を記録し、supported verification path で再実行
- pre-existing failure: baseline と同一であることを証明し、別 owner を明示
- intended Red: implementation後は残してはならない

### 14.2 lint / format

既存 report の reproducibility に合わせる場合:

```bash
uvx --from ruff==0.9.3 ruff check src tests
uvx --from ruff==0.9.3 ruff format --check src tests
```

変更 path は必ず Green:

```bash
uvx --from ruff==0.9.3 ruff check \
  src/pyclassuml/config/resolver.py \
  tests/config/test_context_resolve.py \
  tests/cli/test_bind.py \
  tests/app/test_diff.py \
  tests/app/test_generate.py

uvx --from ruff==0.9.3 ruff format --check \
  src/pyclassuml/config/resolver.py \
  tests/config/test_context_resolve.py \
  tests/cli/test_bind.py \
  tests/app/test_diff.py \
  tests/app/test_generate.py
```

repository-wide baseline を無関係に修復するための broad reformat は行わない。

### 14.3 repository / SpecDock

```bash
git diff --check
git status --short --untracked-files=all
./spec-dock/scripts/spec-dock validate
./spec-dock/scripts/spec-dock doctor
```

必要な workflow/assurance command は current SpecDock policy に従い、managed state を手編集しない。

### 14.4 source boundary inspection

```bash
git diff -- \
  src/pyclassuml/cli/bind.py \
  src/pyclassuml/model/contracts.py \
  src/pyclassuml/analyze/traversal.py \
  src/pyclassuml/vcs/diff_collect.py
```

期待: empty、または事前承認された help-only diff。

## 15. review gate

### code review

確認事項:

- key set の single source
- presence-based merge
- `relative_path_base` first
- path origin
- future command fail-closed
- no DTO/VCS/traversal policy leakage
- qualified errors
- minimal source diff

### QA review

確認事項:

- all 9 common fields
- false/zero/empty cases
- inactive section behavior
- config discovery vs effective project_root
- app A→B→C
- VCS/traversal/parse invariants
- migration/known constraints
- full-suite classification

### spec review

確認事項:

- requirement/design/plan/README/report consistency
- latest user decision reflected
- superseded command-specific-only wording absent
- candidate/canonical authority correctly stated
- process blocker disposition

全 reviewer が pass するまで completion を主張しない。

## 16. report evidence

各 step で最低限、次を report に記録する。

- target branch/HEAD
- before/after changed files
- exact command
- exit status
- test counts
- Red→Green 対応
- acceptance/Test ID
- source boundary diff
- environment variance
- baseline failure classification
- reviewer verdict
- unresolved risk/follow-up
- no commit/push/PR/merge の状態

## 17. stop conditions

次の場合は step を閉じず、design/plan amendment または owner 判断へ戻る。

- common key の一部だけ異なる precedence が必要になった。
- command-specific `relative_path_base` の inherited path 適用を変更したい。
- `[generate].targets` / `[diff].base` が必要になった。
- explicit unlimited sentinel が同一 Issue に必要になった。
- DTO/traversal/VCS production change が必要になった。
- config discovery に config 内 `project_root` を使いたい。
- current-state head の source blob behavior を変更したい。
- required full test/review が未解消。
- unrelated user/managed change の消去が必要になった。

## 18. rollback

rollback 単位:

1. resolver schema/merge/path/default diff
2. focused tests
3. app integration tests
4. README
5. canonical docs/report reflection

traversal/VCS/DTO/data migration はないため、rollback は code/docs/test diff の revert で完結する。ユーザー既存変更や managed bundle を巻き戻さない。

## 19. handoff

実装担当へ渡す input:

- candidate `requirement.md`
- candidate `design.md`
- 本 `plan.md`
- current issue report
- latest ADR artifact
- target branch/commit
- current source/tests
- baseline command output

実装担当の required output:

- changed files
- exact test/lint/SpecDock results
- acceptance/Test ID closure
- unresolved risks
- report update proposal
- commit/push/PR/merge 未実施の明記
