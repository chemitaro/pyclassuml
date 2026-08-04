---
種別: 要件定義書（Issue）
ID: "iss-00044"
タイトル: "Diff Default Traversal Depth"
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-08-04"
親: ["epic-00002", "init-00001"]
---

# iss-00044 Diff Default Traversal Depth — 要件定義

## 1. 目的と観測可能な成果

`diff` のCLIおよび設定ファイルで `depth` が指定されていない場合だけ、依存探索・図出力の既定 frontier を import hop 1 に制限する。`generate` の未指定時の既定値は現行どおり無制限を表す `None` とし、明示値の既存挙動を保つ。

完了後、利用者はCLI、トップレベル設定、command defaultの優先順位を文書で確認でき、同じ入力に対して `diff` と `generate` の既定 depth が意図どおり異なることをテストと出力で観測できる。

## 2. 背景・現状

現行の責務分担は、CLI bindが未指定の `--depth` を `None` として `CommandOptions` に保持し、config resolverがCLI値とトップレベル `depth` をマージして `AnalysisConfig.depth` を作り、traversalが解決済みの値だけを消費する形である。現在のresolver defaultは両commandとも `None` である。

traversalではseedをhop 0、直接importをhop 1として扱い、`None` はhop上限なしを表す。解析対象のpackage-local候補はparse seamで読み込まれるため、depthはparse対象全体ではなく、主にreachable traversal/render frontierを制限する。既存のmodule limit、diagnostic、AST-only、read-only、決定性の契約は別に維持する。

`diff` のGit比較はVCS seamが担当し、明示 `--base`、base未指定時のdefault branchとのmerge-base、initial commit fallback、working-tree/head、include-untrackedの既存規則でchanged filesをseedとして集める。depthはGitの比較対象・base解決・seed収集を変更しない。

## 3. 対象範囲

### 3.1 必須変更

- `diff` のCLI/config未指定時のeffective `AnalysisConfig.depth` を `1` にする。
- `generate` のCLI/config未指定時のeffective `AnalysisConfig.depth` を `None` のまま維持する。
- 優先順位を `CLI --depth > top-level config depth > command default` と固定する。
- `0` を未指定と区別し、CLI/configの明示 `0` を必ず優先する。
- resolver、CLI契約、Git比較方式、depthのhop semantics、既知制約をテストまたはREADMEで明文化する。
- focus testと全体テストで既存のgenerate、traversal、VCS契約への回帰がないことを確認する。

### 3.2 変更対象の責務

- command defaultの所有者は `src/pyclassuml/config/resolver.py` のconfig resolution seamとする。
- `src/pyclassuml/cli/bind.py` は未指定を `None`、明示値を非負整数として保持する既存契約を維持する。
- `AnalysisConfig.depth` と `CommandOptions.depth` の `int | None` 型を維持する。
- traversal、VCS diff collector、target normalization、DTOはcommand policyを解釈せず、変更しない。

## 4. 対象外

- `[diff].depth` という新しい設定キーの追加。
- `None` をCLIまたはTOMLから明示的に要求するための新しいsentinel、文字列、特殊値の追加。
- parse frontierをdepthで制限する設計変更、深いmoduleのsyntax diagnostic範囲の変更。
- traversalアルゴリズム、module limit、cycle処理、relation抽出、PlantUML rendererの変更。
- GitHub API、remote fetch、checkout、Git比較方式、base解決、untracked/rename規則の変更。
- `.agents/skills/pyclassuml-repo-map`、user-level skill、SpecDock managed bundle、Issueのmerge/close、commit/push/PR。

## 5. 非交渉制約と不変条件

- PyClassUMLは解析対象へ組み込まない外部CLIであり、対象プロジェクトのファイルを変更しない。
- 解析はASTベースの静的解析だけで行い、対象コードをimport実行しない。
- 同一入力では決定的な結果を返す。
- `execution_cwd`、`project_root`、`package_root`、`scope_root`の境界を崩さない。
- top-level `depth` は `generate` と `diff` の共通設定であり、設定が存在する場合はcommand defaultより優先する。
- changed fileはdepthにかかわらずdiffのseed（hop 0）として扱う。

## 6. 利用シナリオと優先順位

利用者が `diff` を実行したとき、CLI/config双方に `depth` がなければ直接依存までを既定で図示する。利用者が `depth = 3` または `--depth 3` を指定すれば、その明示値が使われる。`--depth 0` はseed-onlyとして扱われる。

| command | CLI `--depth` | config `depth` | effective depth |
|---|---:|---:|---:|
| `generate` | 未指定 | 未指定 | `None` |
| `diff` | 未指定 | 未指定 | `1` |
| `diff` | 未指定 | `0` | `0` |
| `diff` | 未指定 | `3` | `3` |
| `diff` | `0` | `3` | `0` |
| `diff` | `2` | `0` | `2` |
| `generate` | 未指定 | `3` | `3` |

## 7. 受け入れ条件

### AC-001 — diff command default

- 前提: CLI/configの `depth` が未指定で、AがBを直接importし、BがCをimportする。
- 操作: `diff` を実行する。
- 期待: effective `AnalysisConfig.depth == 1`、AとBはreachable/render対象、Cはdepthによるreachable frontier外となる。
- 観測: resolver focused testおよびapp-level testで確認する。

### AC-002 — generate default compatibility

- 前提: CLI/configの `depth` が未指定で、A→B→Cの依存がある。
- 操作: `generate` を実行する。
- 期待: effective `AnalysisConfig.depth is None`、既存のtransitive traversalが維持される。

### AC-003 — explicit precedence and zero

- 前提: config `depth = 3` または `depth = 0` を用意する。
- 操作: CLI未指定、CLI `--depth 0`、CLI `--depth 2`をそれぞれ実行する。
- 期待: config値はcommand defaultに勝ち、CLIの明示値はconfig値に勝ち、`0` は有効値として保持される。

### AC-004 — CLI bind boundary

- 操作: `--depth`未指定および `--depth 0` をbindする。
- 期待: 未指定は `None`、明示 `0` は `0` であり、CLI parserが `1` を注入しない。

### AC-005 — Git comparison compatibility

- 操作: explicit base、base未指定、working-tree/head、include-untracked、initial commit fallbackの既存テストとdiffを実行する。
- 期待: base解決、changed-file収集、seed選択、untracked/renameの規則はdepth変更前後で不変である。depthはGit commandの引数や比較結果の選択に影響しない。

### AC-006 — invariant and error preservation

- 期待: invalid depthは既存のvalidation errorを返し、対象source/Gitを変更せず、import実行せず、同一入力で決定的に動作する。module limit、cycle、diagnosticの契約も維持する。

#### AC-006の検証対応

| 検証ID | 不変条件 | 検証証跡 |
|---|---|---|
| INV-001 | invalid depthのvalidation error | `tests/config/test_context_resolve.py::test_invalid_config_file_schema_values_are_failures`、`tests/cli/test_bind.py`の非負整数parserケース |
| INV-002 | depth=0のseed-onlyとdepth境界 | `tests/analyze/test_traversal.py::test_depth_zero_keeps_seed_only`、`test_depth_one_includes_direct_import_only` |
| INV-003 | cycle停止と決定的なreachable結果 | `tests/analyze/test_traversal.py::test_depth_none_terminates_deterministically_on_cyclic_imports`、`test_reachable_files_and_edges_are_deterministically_ordered` |
| INV-004 | module limitとdiagnosticの維持 | `tests/analyze/test_traversal.py::test_module_limit_returns_partial_result_and_fatal_diagnostic`、`test_module_limit_applies_to_initial_seed_frontier` |
| INV-005 | diffの決定性とdiagnostic維持 | `tests/app/test_diff.py::test_diff_colorized_output_is_deterministic`、`test_diff_syntax_error_preserves_diagnostics_and_emits_no_fabricated_diff_changed`、`test_head_current_parse_failure_emits_warning_and_no_fabricated_decoration`、`tests/parse/test_module_parse_and_index.py::test_syntax_error_dependency_is_excluded_from_parsed_modules_and_indexes`。結果はreportの`tc-009`へ記録する |
| INV-006 | read-only・no-import境界 | `src/pyclassuml/parse/indexer.py::parse_target_set` / `parse_module_source_text`のAST parse source inspection（`ast.parse`のみで対象moduleをimport実行しないこと）、`tests/parse/test_module_parse_and_index.py`、実行前後の`git status --short`。結果とinspection commandはreportの`tc-009`へ記録する |

### AC-007 — documentation

- READMEまたは同等の利用者向け文書に、hop semantics、commandごとのdefault、CLI > config > default、top-level configの適用範囲、Git比較方式、既知制約を記載する。

## 8. エッジケースと既知制約

- **EC-001**: `depth=0` はseed-onlyであり、既定値 `1`へのfallbackではない。
- **EC-002**: 複数のchanged fileは各々hop 0のseedであり、あるseedから深い依存でも別seedなら残る。
- **EC-003**: cyclic importは既存のreachable set/cycle処理で停止する。
- **EC-004**: 同じimportが複数候補へ解決される場合、候補は同じhopで扱われる。
- **EC-005**: depth=1でもparse seamがpackage-local候補を読み、深いmoduleのsyntax errorがdiagnosticとして観測される可能性がある。depthをparse safety limitと解釈しない。
- **EC-006**: module limitは引き続き有効で、depth=1でもseed数・直接候補数によりlimit diagnosticが発生し得る。
- **EC-007**: `current_state=head` はGitの比較対象をHEADへ切り替えるが、parse対象のworking-tree内容までHEADへ固定する契約ではない。正確なHEAD図にはclean working treeが必要である。
- **EC-008**: 明示的な無制限 `diff` を表すCLI/config入力は現行契約にない。今回の範囲では新sentinelを追加せず、この互換性制約を文書化し、必要なら別Issueで扱う。

## 9. Git比較契約

- `--base <ref>` がある場合、そのrefを明示baseとして使い、無効refをdefault branchへ黙ってfallbackしない。
- base未指定時はdefault branchとのmerge-baseをbest-effortで解決し、比較不能な履歴ではinitial commit fallbackを使う既存規則を維持する。
- working-tree/current-stateは、baseと現在状態の比較方法を選ぶVCS設定であり、depthとは独立である。
- `include_untracked` はGit差分収集時のseed選択だけを変える。depthはuntracked fileのseed性を変えない。
- VCS seamはGit read-only操作とchanged-file収集を担い、dependency traversalのdefault policyを担わない。

## 10. 根拠と用語

根拠は上位Initiative/Epicの要件・設計、既存 `resolver.py`、`bind.py`、`contracts.py`、`traversal.py`、`diff_collect.py`、関連tests、README、research discussion、およびChatGPT-Useの設計レビューartifactである。ChatGPT出力はadvisory evidenceであり、canonical authorityやreview passではない。採用する主張はlocal source/testsで再検証する。

### 10.1 SpecDock assurance profileの適用範囲

このIssueはPyClassUML外部CLIの利用者向け既定挙動を変更するため、`runtime_behavior_change=true`である。この事実を「公開挙動に影響しない」とは扱わない。一方、現行SpecDockの`authorized_profile`が直接統制するSpecDock自身の公開CLI、workflow、active/validate/lifecycle、template、metadata、workspace scaffold、永続状態は変更しない。変更対象はPyClassUML本体の`resolver`と利用者向けREADMEであり、SpecDockの運用契約ではない。

したがって、現行のprofile scopeでは次のStandard適用例外を採用する。

- `public_contract_change=false`: PyClassUMLの既存`diff` / `--depth`入力面、型、設定schema、終了契約を変更せず、未指定時のeffective policyだけを変更する。
- `migration_or_persistence_change=false`、`rollback_difficulty_high=false`、`security_or_privacy_sensitive=false`: 永続データ、workspace、GitHub状態、secret、不可逆migrationを扱わない。
- `docs_only_change=false`: runtime behaviorは実際に変更するため、docs-onlyとは主張しない。
- `assurance classify`はrisk factを入力するCLIを現行提供せず、`.assurance.json`は正規コマンド生成物である。managed stateを手修復してStrictを自己主張しない。

この例外はユーザー向け互換性リスクの免除ではない。公開挙動変更に対する補償として、ChatGPT-Use advisoryのlocal検証、fresh `spec-reviewer`、resolver/app/focused/full test、VCS・read-only・no-import inspection、README、code/QA reviewを必須化する。将来、変更がSpecDockの公開CLI/workflow契約へ広がる、またはrisk factを正規入力してStrictへ再分類できる実装が利用可能になった場合は、実装前にStrictへ引き上げる。

- effective depth: resolverがCLI/config/defaultから確定して `AnalysisConfig`へ渡す値。
- seed/hop 0: generateの明示targetまたはdiffのchanged file。
- import hop 1: seedから直接importされる候補。
- traversal/render frontier: depthで制限されるreachable・図出力の範囲。
- parse frontier: parserが診断のために読み込む範囲。今回depthでは制限しない。
- current-state: diffが比較対象としてworking treeまたはHEADを選ぶ設定。

## 11. 未確定事項

今回の実装に必要な要件上の未確定事項はない。無制限 `diff` の明示指定は現行制約として別Issueへ延期する。canonical promotion、実装着手、README変更の最終レビューはfresh reviewer gateで確認する。
