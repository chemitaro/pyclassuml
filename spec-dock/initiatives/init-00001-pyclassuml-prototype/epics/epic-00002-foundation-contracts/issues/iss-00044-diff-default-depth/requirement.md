---
種別: 要件定義書（Issue）
ID: "iss-00044"
タイトル: "Diff Default Traversal Depth"
状態: "draft"
作成者: "ChatGPT"
最終更新: "2026-08-05"
親: ["epic-00002", "init-00001"]
---

# iss-00044 Diff Default Traversal Depth — 要件定義（canonical 候補）

> 本書は `chemitaro/pyclassuml` の branch `codex/iss-00044-chatgpt-first-planning`、commit `d04c6aa175d1f6261c7c4378435b5d54b4efef27`、および提供された source / tests / SpecDock 文書 / artifacts を根拠に作成した候補である。repository、active state、canonical docs、GitHub Issue を変更したものではなく、review pass や実装完了を主張しない。

## 1. 目的

`diff` の依存探索既定値を import hop `1` に限定しつつ、`generate` の既定値 `None`（unlimited）を維持する。同時に、同一 `.pyclassuml.toml` におけるトップレベル共通設定を正式なベースとし、`[generate]` と `[diff]` が共通設定をコマンド単位で上書きできる設定契約を確立する。

利用者から観測できる最終契約は次のとおりである。

- 共通設定はトップレベルに一度記述できる。
- `generate` または `diff` だけ値を変えたい場合は、対応する `[generate]` または `[diff]` に同じ共通キーを記述する。
- 解決優先順位は、各フィールドについて `CLI の当該コマンドで明示した値 > コマンド別設定 > トップレベル共通設定 > コマンド既定値` である。
- CLI/config のいずれにも `depth` がない場合、`generate` は `None`、`diff` は `1` となる。
- 明示 `--depth 0` および config の `depth = 0` は有効値であり、未指定として扱わない。
- `current_state` と `include_untracked` は Diff 固有キーとして `[diff]` にだけ置く。
- Git 比較、target normalization、traversal、DTO、module limit、read-only / AST-only / non-invasive の既存境界を変更しない。

## 2. 背景と現状

現行 `src/pyclassuml/config/resolver.py` は、共通値をトップレベルからだけ読み、`[diff]` では `current_state` と `include_untracked` だけを許可する。`[generate]` は未定義であり、`depth` は `CLI > トップレベル > None` として両コマンド共通に解決される。このため、現行 source では `diff` の全未指定時も `AnalysisConfig.depth is None` である。

一方、現行 tests には `diff` の全未指定時に `depth == 1` を要求する先行テストと、A→B→C の dependency chain で default `diff` が A/B だけを到達可能にすることを要求する先行テストが含まれる。したがって、現時点の source と tests は意図的な Red 状態を含み得る。

既存 Issue 文書は主として「トップレベル `depth` と command default」の補正だけを扱い、`[generate]` / `[diff]` による全共通設定の上書きを対象外としている。2026-08-05 の最新ユーザー決定により、command-specific only および旧トップレベル廃止案は撤回され、トップレベル共通ベース + command override が採用方針となった。

## 3. 用語

- **共通設定**: `generate` と `diff` の双方に適用可能な config key。
- **コマンド別設定**: `[generate]` または `[diff]` 内の共通設定。対応コマンドについてトップレベル共通設定を上書きする。
- **Diff 固有設定**: `[diff].current_state` と `[diff].include_untracked`。
- **CLI 明示値**: CLI parser が「利用者がそのオプションを指定した」と判定できる値。`depth=0` や `include_untracked=false` を truthiness で未指定扱いしてはならない。
- **command default**: CLI、コマンド別設定、トップレベル共通設定がすべて未指定の場合に resolver が採用する値。
- **seed / hop 0**: `generate` の explicit target または `diff` の changed file。
- **import hop 1**: seed から直接 import される内部候補。
- **traversal frontier**: `AnalysisConfig.depth` により制限される reachable dependency graph。
- **parse frontier**: AST parse の候補範囲。`depth` の制限対象ではない。
- **config-origin path**: トップレベルまたは command table から選択された path 値。
- **CLI-origin path**: CLI option から選択された path 値。

## 4. 設定ファイル契約

### 4.1 正式な設定形状

```toml
# トップレベル: generate / diff の共通ベース
project_root = "."
package_root = "src"
scope_root = "src"
output = "diagram.puml"
ignore = ["tests/**", "build/**"]
depth = 3
mode = "warn"
target_python = "3.12"
relative_path_base = "config"

# generate だけの上書き
[generate]
output = "generate.puml"
depth = 5
ignore = []

# diff だけの共通設定上書き + Diff 固有設定
[diff]
output = "diff.puml"
depth = 1
current_state = "working-tree"
include_untracked = true
```

TOML の仕様上、トップレベル共通キーは `[generate]` または `[diff]` の table 宣言より前に記述する。`diff.current_state = "head"` の dotted key 表記は `[diff]` table と同じ意味として扱う。

### 4.2 共通設定一覧

| key | config 型 | トップレベル | `[generate]` | `[diff]` | CLI 対応 | command default |
|---|---|---:|---:|---:|---|---|
| `project_root` | non-empty string path | 可 | 可 | 可 | `--project-root` | config file がある場合はその parent、なければ `execution_cwd` |
| `package_root` | non-empty string path | 可 | 可 | 可 | `--package-root` | effective `project_root` |
| `scope_root` | non-empty string path | 可 | 可 | 可 | `--scope-root` | effective `package_root` |
| `output` | non-empty string path | 可 | 可 | 可 | `--output` | `None`。downstream が自動命名する |
| `ignore` | string list | 可 | 可 | 可 | repeatable `--ignore` | empty tuple |
| `depth` | non-negative integer | 可 | 可 | 可 | `--depth` | `generate=None`, `diff=1` |
| `mode` | `"warn"` / `"strict"` | 可 | 可 | 可 | `--strict` は `"strict"` の明示指定 | `"warn"` |
| `target_python` | `3.<minor>` string | 可 | 可 | 可 | `--target-python` | `None` |
| `relative_path_base` | `"config"` / `"cwd"` | 可 | 可 | 可 | なし | `"config"` |

`ignore = []` は有効であり、command table に置いた場合はトップレベル `ignore` を明示的に空へ置換する。複数レイヤーの `ignore` は連結しない。

### 4.3 Diff 固有設定

| key | 許可位置 | CLI 対応 | default |
|---|---|---|---|
| `current_state` | `[diff]` のみ | `--current-state` | `"working-tree"` |
| `include_untracked` | `[diff]` のみ | `--include-untracked` / `--no-include-untracked` | `true` |

`current_state` と `include_untracked` はトップレベルまたは `[generate]` に置いてはならない。`[diff]` では共通設定と Diff 固有設定の両方を記述できる。

### 4.4 config key ではない入力

次の入力は config layering の対象にしない。

| 入力 | 位置づけ |
|---|---|
| `--cwd` | `execution_cwd` を決める CLI-only meta option |
| `--config` | config file を明示する CLI-only meta option |
| `generate [targets ...]` | CLI positional inputs。`[generate].targets` は追加しない |
| `diff --base <ref>` | CLI-only VCS input。`[diff].base` / `[diff].base_ref` は追加しない |

## 5. 機能要件

### RQ-001 — トップレベル共通設定

resolver はトップレベルにある 9 個の共通設定を、`generate` と `diff` の双方に適用可能な正式ベースとして扱わなければならない。これは legacy fallback ではなく、継続する公開設定契約である。

### RQ-002 — command override

resolver は `[generate]` と `[diff]` の双方で、9 個すべての共通設定を許可しなければならない。command table に key が存在する場合、その値は対応コマンドについてトップレベル値を置換する。

値の選択は「key が存在するか」で判断し、truthiness で判断してはならない。したがって、`depth = 0`、`ignore = []`、`include_untracked = false` は有効な上書きである。

### RQ-003 — 解決優先順位

共通設定の effective value は、フィールドごとに次の順序で選択する。

1. CLI の当該コマンドで明示した値
2. `[generate]` または `[diff]` の値
3. トップレベル共通値
4. command default

CLI 表現が存在しない `relative_path_base` は 2→3→4 の順序で解決する。CLI が `"warn"` を明示する surface は現行提供されず、`--strict` が指定された場合だけ `mode="strict"` として最優先になる。

### RQ-004 — depth default と hop semantics

- `generate` で CLI / `[generate]` / top-level の `depth` がすべて未指定なら、effective `AnalysisConfig.depth` は `None`。
- `diff` で CLI / `[diff]` / top-level の `depth` がすべて未指定なら、effective `AnalysisConfig.depth` は `1`。
- `depth=0` は seed-only。
- seed は hop 0、直接 import は hop 1。
- 複数 changed file は各々 hop 0 の seed であり、別 seed であることを理由に depth で除外してはならない。
- `depth` は traversal/render frontier だけを制限し、Git changed-file collection、base resolution、target normalization、parse frontier を変更してはならない。

### RQ-005 — `relative_path_base` と path 解決順序

resolver は active command の effective `relative_path_base` を、他の config-origin path を解決する前に確定しなければならない。

- effective `relative_path_base="config"`: config-origin path は config file の parent 基準。
- effective `relative_path_base="cwd"`: config-origin path は `execution_cwd` 基準。
- command table の `relative_path_base` は active command 全体の effective base であり、command table 由来の path だけでなく、継承されたトップレベル path にも適用する。
- CLI-origin path は常に `execution_cwd` 基準であり、`relative_path_base` の影響を受けない。
- `ignore` pattern は path 値ではなく、effective `project_root` 相対の filter として評価する。
- default `project_root` は、config file がある場合は config file parent、ない場合は `execution_cwd`。この default は `relative_path_base` で再解釈しない。
- default `package_root` と `scope_root` は、すでに解決済みの effective root を継承する。

### RQ-006 — config discovery

config discovery の順序を維持する。

1. `--config` があれば、`execution_cwd` 基準で解決した明示 path
2. CLI `--project-root` があれば、その directory 直下の `.pyclassuml.toml`
3. `execution_cwd` から parent 方向への `.pyclassuml.toml` 探索

config file 内のトップレベルまたは command-specific `project_root` は、config file 自身の discovery には使用しない。config を load した後の effective context にだけ使用する。

### RQ-007 — Diff 固有設定と collision 防止

共通キー集合と Diff 固有キー集合は disjoint でなければならない。将来同名 collision が発生した場合、暗黙の last-write-wins を採用せず、schema 定義または test を失敗させ、明示的な設計判断を要求する。

- `[generate]` の許可キー: 共通キーのみ。
- `[diff]` の許可キー: 共通キー + `current_state` + `include_untracked`。
- トップレベルの許可キー: 共通キー + table 名 `generate` + `diff`。
- unknown key、非 table の `generate` / `diff`、Diff 固有キーの誤配置は fail-fast。

### RQ-008 — CLI 明示値の検出

- optional path / string は `is not None` で明示判定する。
- `depth` は `is not None` で判定し、`0` を保持する。
- repeatable `--ignore` は 1 個以上なら CLI 明示値。現行 CLI は「空 list を明示して config ignore を消す」surface を持たない。
- `--strict` は `True` のときだけ CLI 明示値。現行 CLI は `--no-strict` / `--mode warn` を持たない。
- `DiffOptions.current_state_cli_provided` と `include_untracked_cli_provided` を維持し、enum default や bool value 自体を明示判定に流用しない。
- 将来、明示 `false` や empty collection を持つ共通 CLI option を追加する場合は、value と presence を分離する metadata を追加する。

### RQ-009 — validation と diagnostics

config 全体に対して unknown key、section type、value type、enum domain を検証する。inactive command section も schema/type validation の対象とするが、filesystem existence と containment は active command の effective path に対してだけ実施する。

必須 validation:

- `project_root`, `package_root`, `scope_root`, `output`: non-empty string
- `ignore`: string list。各要素は non-empty。empty list 自体は有効
- `depth`: bool ではない non-negative integer
- `mode`: `warn` または `strict`
- `target_python`: `3.<minor>`
- `relative_path_base`: `config` または `cwd`
- `current_state`: `working-tree` または `head`
- `include_untracked`: bool
- root existence と directory 判定
- `package_root` が `project_root` の内側または同一
- `scope_root` が `package_root` の内側または同一

既存の `ConfigError`、`Diagnostic.origin_seam=CONFIG`、fatal recoverability、failure reason の境界を維持する。message は `generate.depth`、`diff.relative_path_base` のように section-qualified field を識別可能にする。

### RQ-010 — Generate targets と Diff `--base`

- `generate` targets は CLI positional input のまま維持する。
- targets の相対 path は `execution_cwd` 基準で normalize する。
- file / directory / glob、ignore、scope outside、zero target の既存契約を変更しない。
- `diff --base <ref>` は CLI-only のまま維持する。
- 明示 base が invalid な場合は failure とし、no-base resolution へ fallback しない。
- no-base の default branch merge-base、initial commit fallback、`working-tree` / `head`、untracked、rename の既存規則を変更しない。
- config resolver は `base_ref` の検証や Git command 実行を担わない。

### RQ-011 — traversal / VCS / DTO の責務維持

次の production module は command-specific config policy を解釈してはならない。

- `src/pyclassuml/analyze/traversal.py`
- `src/pyclassuml/vcs/diff_collect.py`
- `src/pyclassuml/model/contracts.py`
- target normalization modules

`AnalysisConfig.depth: int | None`、`CommandOptions.depth: int | None` を維持する。`DEFAULT_TRAVERSAL_MODULE_LIMIT = 1000`、cycle termination、deterministic ordering、scope/package stop、diagnostic behavior を維持する。

### RQ-012 — non-invasive / read-only / AST-only

- 解析対象 source を変更しない。
- 解析対象 package に dependency を追加しない。
- 解析対象 module を import 実行しない。
- AST static analysis を維持する。
- Git metadata、branch、index、working tree を変更しない。
- `.puml` output 以外の対象 project artifact を生成しない。
- 同一 input/config/Git state から deterministic な effective config と出力を得る。

### RQ-013 — documentation / migration / quality

README または同等の利用者向け文書に、config shape、全共通キー、precedence、path base、depth defaults、Diff 固有キー、targets/base の非 config 性、known constraints を記載する。

実装は focused tests と full tests の双方で検証し、既存 baseline と新規 failure を分離する。repository-wide lint/format の既存 failure を本 Issue の機能実装に混入させず、変更 path の新規 failure は許容しない。

## 6. 不変条件

1. `CLI > command section > top-level common > command default` は全共通フィールドで同一。
2. layer selection は presence-based であり、truthiness-based ではない。
3. `relative_path_base` は config-origin path resolution より先に一度だけ解決する。
4. CLI-origin path は常に `execution_cwd` 基準。
5. root containment は symlink 解決後の absolute path で判定する。
6. `generate` default depth は `None`、`diff` default depth は `1`。
7. `depth=0` は有効。
8. changed files は常に diff seed / hop 0。
9. `current_state` / `include_untracked` は Diff 固有。
10. `targets` / `base_ref` は config key にしない。
11. resolver は Git 読み取りや traversal を実行しない。
12. VCS/traversal/DTO は command default を知らない。
13. module limit、cycle、determinism、read-only、AST-only を維持する。

## 7. 受け入れ条件

### AC-001 — schema と共通ベース

**Given** 9 個の共通値をトップレベルに持つ config  
**When** `generate` と `diff` をそれぞれ resolve する  
**Then** 両コマンドがトップレベル値を effective value として使用する。

### AC-002 — 全共通設定の command override

**Given** トップレベルと active command table に同じ共通キーがある  
**When** resolve する  
**Then** active command table の値が選択され、inactive command table の値は選択されない。9 個の共通キーすべてで同じ規則が成立する。

### AC-003 — CLI precedence と明示 `0`

**Given** top-level `depth=4`、`[diff].depth=2`  
**When** `diff --depth 0` を実行する  
**Then** effective depth は `0`。CLI 未指定なら `2`、`[diff].depth` も未指定なら `4`。

### AC-004 — command defaults

**Given** depth が全レイヤーで未指定  
**When** `generate` / `diff` を resolve する  
**Then** `generate=None`、`diff=1`。

### AC-005 — list replacement と clear

**Given** top-level `ignore=["tests/**"]`、`[generate].ignore=[]`  
**When** `generate` を resolve する  
**Then** effective ignore は empty tuple。top-level list と連結しない。

### AC-006 — `relative_path_base` の先行解決

**Given** config file が `config/`、`execution_cwd` が `work/`、top-level `project_root="project"`、`[diff].relative_path_base="cwd"`  
**When** `diff` を resolve する  
**Then** inherited top-level `project_root` は `work/project` に解決される。`generate` に command override がなければ `config/project` に解決される。

### AC-007 — CLI path independence

**Given** config の effective `relative_path_base="config"` と CLI `--output out.puml`  
**When** resolve する  
**Then** output は `execution_cwd/out.puml`。config directory 基準にしない。

### AC-008 — Diff 固有キーの配置

**Given** `[diff].current_state` / `[diff].include_untracked`  
**When** `diff` を resolve する  
**Then** CLI 明示値があれば CLI、なければ `[diff]`、なければ default。トップレベルまたは `[generate]` に置いた場合は `invalid_config`。

### AC-009 — invalid config

unknown key、non-table section、invalid type/domain、empty path string、negative/bool depth、containment violation は downstream VCS/targets/parse を呼ぶ前に fatal config diagnostic となる。

### AC-010 — Generate targets boundary

`[generate].targets` は unknown key として failure。CLI targets は既存どおり normalize され、scope outside / zero target の既存 failure contract を維持する。

### AC-011 — Diff base boundary

`[diff].base` / `[diff].base_ref` は unknown key として failure。CLI `--base` の explicit/no-base behavior は現行 VCS tests と一致する。

### AC-012 — traversal / VCS regression

depth 0/1/None、multi-seed、multiple candidate、cycle、module limit、explicit base、merge-base、initial fallback、current-state、untracked、rename の既存 test が回帰しない。

### AC-013 — app integration

A→B→C の fixture で、default `diff` は A/B、`diff --depth 2` または `[diff].depth=2` は A/B/C、default `generate` は A/B/C を出力する。

### AC-014 — compatibility

既存のトップレベル-only config と `[diff]` の `current_state/include_untracked` config は引き続き有効。command-specific only / top-level 廃止を要求しない。

### AC-015 — docs と全体品質

README の設定例と source behavior が一致し、focused test、full test、changed-path lint/format、`git diff --check`、SpecDock validation の必要な evidence が揃う。

## 8. acceptance / test matrix

| Test ID | 主な acceptance | 検証対象 |
|---|---|---|
| `TC-001` | AC-001, AC-002 | top-level common と `[generate]` / `[diff]` の全共通キー |
| `TC-002` | AC-003, AC-004 | precedence、default、明示 `depth=0` |
| `TC-003` | AC-005 | `ignore` replacement / empty clear |
| `TC-004` | AC-006, AC-007 | `relative_path_base`、CLI/config path origin |
| `TC-005` | AC-008, AC-009 | Diff 固有 key、unknown/type/domain/containment |
| `TC-006` | AC-010, AC-011 | generate targets / diff `--base` boundary |
| `TC-007` | AC-012 | traversal / VCS / DTO regression |
| `TC-008` | AC-013 | app-level depth behavior |
| `TC-009` | AC-014 | existing config compatibility |
| `TC-010` | AC-015 | README、focused/full quality gates |

## 9. 移行と互換性

### 9.1 維持する互換性

- 既存トップレベル共通設定はそのまま有効。
- 既存 `[diff].current_state` と `[diff].include_untracked` はそのまま有効。
- CLI option 名、型、generate targets、diff `--base` を維持。
- `AnalysisConfig` / `CommandOptions` の公開型を維持。
- Git 比較と traversal algorithm を維持。

### 9.2 新規に有効になる形状

- `[generate]` に全共通キー。
- `[diff]` に全共通キー + 既存 Diff 固有キー。
- command-specific `relative_path_base`。
- command-specific empty `ignore=[]` による common ignore clear。

### 9.3 意図的な挙動変更

- `diff` の depth 全未指定時は `None` から `1` へ変わる。
- empty path string は fail-fast とする。基準 directory を表す場合は `"."` を明示する。
- command-specific `relative_path_base` は inherited top-level path の解釈も変える。

### 9.4 既知の互換性制約

- 現行 CLI/TOML には `diff` の unlimited `None` を明示する sentinel がない。
- `--strict` は strict への one-way override であり、CLI から warn を強制できない。
- CLI から config `ignore` を empty へ clear する option はない。
- command-specific `project_root` は config discovery を変更せず、load 後の effective context だけを変更する。
- `current_state=head` は Git changed-file comparison を HEAD に切り替えるが、図の current-side source を自動的に HEAD blob に固定するものではない。

## 10. 対象外

- explicit unlimited depth sentinel の追加。
- `--mode warn`、`--no-strict`、CLI ignore clear option の追加。
- `[generate].targets`、`[diff].base` / `[diff].base_ref` の追加。
- config file include / profile / environment expansion。
- multiple `package_root` / `scope_root`。
- traversal、parse frontier、module limit、Git algorithm、renderer、DTO の再設計。
- target project source、Git metadata、SpecDock managed state の変更。
- commit、push、PR、merge、Issue close。

## 11. 根拠と未検証事項

主な根拠:

- `AGENTS.md`
- `README.md`
- `src/pyclassuml/config/resolver.py`
- `src/pyclassuml/cli/bind.py`
- `src/pyclassuml/model/contracts.py`
- `src/pyclassuml/analyze/traversal.py`
- `src/pyclassuml/vcs/diff_collect.py`
- 関連 config / CLI / app / traversal / VCS tests
- parent Epic の requirement / design / plan
- Issue `iss-00044` の既存 requirement / design / plan / report
- `20260804t232417z-adr-common-config-command-overrides-decision.md`
- 2026-08-05 の最新ユーザー決定

本書作成時には test suite、lint、SpecDock command を実行していない。既存 report に記録された過去の pass/fail 数は evidence として参照するが、独立再検証済みとは扱わない。
