---
種別: 実装報告書（Issue）
ID: "iss-00033"
タイトル: "Render Diff Class Colorization"
関連GitHub: ["#33"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-05"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00004", "init-00001"]
---

# iss-00033 Render Diff Class Colorization — 実装報告（LOG）

## 実装サマリー
- `pyclassuml diff` の表示 class のうち changed / newly added class だけに `DiffChanged` decoration を付与し、PlantUML の `skinparam class` と stereotype で薄い緑に色分けできるようにした。
- dependency-only class は diff-specific decoration を付与せず、PlantUML default の通常 class box 表示に戻した。
- changed class 判定は `app.diff` が VCS の current-side changed hunk ranges、parse の class definition spans、`ModuleIndex`、`SelectedClasses` を join して行い、render は Git を読まず、渡された decoration だけを描画する。
- `generate` には diff-specific style を適用せず、既存の class member、composition / aggregation、inheritance / Protocol realization、uses relation 表現を維持した。

## 実装記録（セッションログ）

### 2026-05-05 - docs and implementation

#### 対象
- Step: S01, S02, S03
- AC/EC: AC-001 - AC-005, EC-001 - EC-004

#### 実施内容
- `design.md` を作成し、`app.diff` が diff class decorations を作り、`render.document` が decoration/style handoff だけを描画する責務分離を固定した。
- `plan.md` を作成し、render style contract、diff app handoff、regression coverage、manual diff colorization、review gates の実行順序を具体化した。
- spec-reviewer の P2 指摘を受け、EC-003 syntax error / join miss の検証を plan に明示した。
- dev-coder に実装を委任し、以下を追加した。
  - `app.diff` の `_diff_class_decorations(...)`
  - `render_uml_document(..., class_decorations=...)` optional handoff
  - `compose_render_ready_model` の Protocol + external decoration merge
  - `render_plantuml_text` の diff style block出力
  - render/app/generate regression tests
- QA P2 を受け、EC-004 の `include_untracked=True` と `current_state=head` における色分け assertion を追加した。

#### 実行コマンド / 結果
```bash
./spec-dock/scripts/spec-dock validate

spec-dock: ok (validate) nodes=33
```

```bash
uv run --with pytest pytest tests/app/test_diff.py -q

27 passed in 2.20s
```

```bash
PYTHONPATH=src uv run --no-project --with pytest python -m pytest -q tests/render/test_document.py tests/app/test_diff.py tests/app/test_generate.py

65 passed in 2.23s
```

```bash
PYTHONPATH=src uv run --no-project --with pytest python -m pytest -q

359 passed in 10.69s
```

```bash
git diff --check

passed
```

```bash
rg --files | rg '[A-Z]'

existing allowed uppercase paths only: AGENTS.md and README.md files
```

```bash
test ! -e uv.lock && printf 'uv.lock absent\n'

uv.lock absent
```

#### 変更したファイル
- `src/pyclassuml/app/diff.py` - diff class decoration handoff を追加。
- `src/pyclassuml/render/document.py` - extra class decorations と diff style block を追加。
- `tests/app/test_diff.py` - diff E2E、determinism、EC-001〜EC-004、relation regression coverage を追加。
- `tests/app/test_generate.py` - generate に diff style が出ない regression assertion を追加。
- `tests/render/test_document.py` - style block、Protocol coexistence、non-rendered decoration ignore を追加。
- `spec-dock/.../iss-00033-render-diff-class-colorization/design.md` - 実装設計を作成。
- `spec-dock/.../iss-00033-render-diff-class-colorization/plan.md` - 実装計画を作成。
- `spec-dock/.../iss-00033-render-diff-class-colorization/report.md` - 実装・検証結果を記録。

#### コミット
- `51f3bcf docs(spec): diff class色分け設計と計画を具体化`
- `7a9baa1 feat(render): diff classを色分け表示`

#### メモ
- `.serena/project.yml` は作業前からの既存変更として触っていない。
- `uv run` が `uv.lock` を生成したが、この issue の成果物ではないため削除済み。

---

### 2026-05-05 - manual diff colorization

> Historical note: この節は最初の yellow / blue 実装時の手動証跡である。現在の正本は後続の `color palette revision to green-only highlight` 節と Closure Coverage である。

#### 対象
- Step: S04
- AC/EC: AC-001, AC-002, AC-004, AC-005

#### 実施内容
- `build/manual-tests/pyclassuml-manual-env` の内部 git を使い、`sample_pkg/service.py` に一時差分を作った。
- `pyclassuml diff --base HEAD --current-state working-tree` で `.puml` を生成した。
- PlantUML Docker で SVG に変換した。
- `.puml` に `skinparam class`、`<<DiffChanged>>`、`<<DiffDependency>>`、既存 `*--` relation が出ることを確認した。
- manual env の一時変更は `git restore` で復旧した。

#### 実行コマンド / 結果
```bash
PYTHONPATH=/Users/iwasawayuuta/workspace/tools/pyclassuml/src uv run --no-project pyclassuml diff \
  --cwd /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env \
  --project-root . \
  --package-root . \
  --scope-root . \
  --base HEAD \
  --current-state working-tree \
  --output /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/out/iss-00033/colorized-diff.puml

outcome: clean_success
exit_code: 0
seed_file_count: 1
reachable_file_count: 2
extracted_class_count: 2
extracted_relation_count: 1
changed_class_count: 1
warning_count: 0
```

```plantuml
skinparam class {
  BackgroundColor<<DiffChanged>> #fff3b0
  BorderColor<<DiffChanged>> #d39e00
  BackgroundColor<<DiffDependency>> #e8f4ff
  BorderColor<<DiffDependency>> #5b8def
}
class "UserService" as c001 <<DiffChanged>>
class "User" as c002 <<DiffDependency>>
c001 *-- c002
```

```bash
docker run --rm -v /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/out/iss-00033:/work plantuml/plantuml:latest -tsvg /work/colorized-diff.puml

success
```

```bash
test -s build/manual-tests/pyclassuml-manual-env/out/iss-00033/colorized-diff.svg && wc -c build/manual-tests/pyclassuml-manual-env/out/iss-00033/colorized-diff.svg

7684 build/manual-tests/pyclassuml-manual-env/out/iss-00033/colorized-diff.svg
```

```bash
rg -n '#FFF3B0|#D39E00|#E8F4FF|#5B8DEF|DiffChanged|DiffDependency|UserService|User' \
  build/manual-tests/pyclassuml-manual-env/out/iss-00033/colorized-diff.svg

class UserService: rect fill="#FFF3B0" style="stroke:#D39E00;..."
class UserService: text "DiffChanged"
class User: rect fill="#E8F4FF" style="stroke:#5B8DEF;..."
class User: text "DiffDependency"
```

#### SVG 視覚確認
- AC-001: changed class `UserService` は SVG 内で `fill="#FFF3B0"`、`stroke:#D39E00`、`DiffChanged` stereotype として描画された。
- AC-002: dependency-only class `User` は SVG 内で `fill="#E8F4FF"`、`stroke:#5B8DEF`、`DiffDependency` stereotype として描画された。
- AC-004: relation は SVG 内で composition link として保持され、class box colorization と `c001 *-- c002` が併存した。

```bash
git -C build/manual-tests/pyclassuml-manual-env status --short --branch

## main
```

#### 変更したファイル
- ignored manual output:
  - `build/manual-tests/pyclassuml-manual-env/out/iss-00033/colorized-diff.puml`
  - `build/manual-tests/pyclassuml-manual-env/out/iss-00033/colorized-diff.svg`

#### コミット
- 該当なし。manual output は ignored artifact。

---

### 2026-05-05 - color palette revision to green-only highlight

#### 対象
- Step: S01, S02, S03, S04
- AC/EC: AC-001 - AC-005, EC-001 - EC-004

#### 実施内容
- ユーザー確認に基づき、旧配色の yellow/blue 2 色分類を廃止した。
- `DiffChanged` の theme を薄い緑へ変更した。
  - `BackgroundColor<<DiffChanged>> #dff5df`
  - `BorderColor<<DiffChanged>> #4f9d5d`
- `_diff_class_decorations(...)` は selected classes のうち changed / newly added class だけを返すようにした。
- `DiffDependency` style / stereotype の出力を廃止し、dependency-only class は通常 class box のままにした。
- render/app tests を更新し、dependency-only class に diff-specific stereotype が出ないことを確認した。
- code-reviewer の P1 指摘を受け、changed file 内の全 class を `DiffChanged` にする判定を廃止した。
- VCS seam で current 側 changed hunk line ranges を収集し、parse seam で `ClassSpan(class_id, start_line, end_line)` を保持するようにした。
- `app.diff` は added file 内 selected class、または changed hunk range と class span が重なる selected class だけを `DiffChanged` にする。
- class body の deletion-only hunk も changed class として扱い、module-level only change / module-level deletion は class highlight しない。
- deletion-only hunk は hunk 本文の削除行も確認し、インデントされた非空削除行を含む場合のみ current-side point range として class span との重なり判定に使う。
- deletion-only hunk 判定は VCS seam が current-side point と deleted lines を保持し、app.diff が class span と deleted line の形を見て class body / decorator 削除かを判定する形へ寄せた。
- class 直後の module-level 複合リテラル削除、decorator-only class change、`ParsedModule` positional constructor compatibility を追加テストで固定した。
- code-reviewer / qa-reviewer の P1 指摘を受け、current-side `+0,0` になる class 先頭 decorator 削除も class change として扱うようにした。
- qa-reviewer の P1 指摘を受け、nested class の inner-only change では最も内側の changed class だけを `DiffChanged` にし、outer class は default rendering のままにするようにした。
- code-reviewer の P2 指摘を受け、top-level function decorator の削除が直後の unchanged class に誤って `DiffChanged` として接続されないようにした。
- code-reviewer の追加 P2 指摘を受け、decorated top-level helper がファイル先頭から丸ごと削除され、class が line 1 に移動する場合も `DiffChanged` を誤付与しないようにした。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest tests/vcs/test_diff_file_collect.py tests/parse/test_module_parse_and_index.py tests/model/test_contracts.py tests/app/test_diff.py tests/render/test_document.py tests/app/test_generate.py -q

159 passed in 3.20s
```

```bash
PYTHONPATH=src uv run --no-project --with pytest python -m pytest -q

381 passed in 11.91s
```

```bash
git diff --check

passed
```

```bash
rg --files | rg '[A-Z]'

existing allowed uppercase paths only: AGENTS.md and README.md files
```

```bash
test ! -e uv.lock && printf 'uv.lock absent\n'

uv.lock absent
```

```bash
./spec-dock/scripts/spec-dock validate

spec-dock: ok (validate) nodes=33
```

```bash
git -C build/manual-tests/pyclassuml-manual-env/tmp/iss-00033-multicommit-color status --short --branch

## main
```

#### 多段階コミット手動テスト
- manual repo:
  - `build/manual-tests/pyclassuml-manual-env/tmp/iss-00033-multicommit-color`
- commit history:
  - `2fa3434 base domain model`
  - `41178bb add optional payment method`
  - `96f2c15 add shipment collection`
- base ref:
  - `2fa3434d7ffc40c510f47488757d60ffad8fee73`
- diff:
  - `M shop_domain/order.py`
  - `A shop_domain/payment.py`
  - `A shop_domain/shipping.py`

```bash
PYTHONPATH=/Users/iwasawayuuta/workspace/tools/pyclassuml/src uv run --no-project pyclassuml diff \
  --cwd /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/tmp/iss-00033-multicommit-color \
  --project-root . \
  --package-root . \
  --scope-root . \
  --base 2fa3434d7ffc40c510f47488757d60ffad8fee73 \
  --current-state head \
  --output /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/out/iss-00033-green/colorized-green-from-base-2fa3434.puml

outcome: warning_only_success
exit_code: 0
seed_file_count: 3
reachable_file_count: 4
extracted_class_count: 4
extracted_relation_count: 3
changed_class_count: 3
warning_count: 1
warning:head_untracked_noop: include_untracked has no effect when diff current_state is head
```

```plantuml
skinparam class {
  BackgroundColor<<DiffChanged>> #dff5df
  BorderColor<<DiffChanged>> #4f9d5d
}
class "Customer" as c001
class "Order" as c002 <<DiffChanged>>
class "PaymentMethod" as c003 <<DiffChanged>>
class "Shipment" as c004 <<DiffChanged>>
c002 *-- c001
c002 o-- c003
c002 o-- c004
```

```bash
docker run --rm -v /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/out/iss-00033-green:/work plantuml/plantuml:latest -tsvg /work/colorized-green-from-base-2fa3434.puml

success
```

```bash
rg -n 'DiffChanged|DiffDependency|#dff5df|#4f9d5d|#fff3b0|#d39e00|#e8f4ff|#5b8def|class "Customer"|class "Order"|class "PaymentMethod"|class "Shipment"|\*--|o--' \
  build/manual-tests/pyclassuml-manual-env/out/iss-00033-green/colorized-green-from-base-2fa3434.puml

3:  BackgroundColor<<DiffChanged>> #dff5df
4:  BorderColor<<DiffChanged>> #4f9d5d
7:  class "Customer" as c001 {
13:  class "Order" as c002 <<DiffChanged>> {
21:  class "PaymentMethod" as c003 <<DiffChanged>> {
27:  class "Shipment" as c004 <<DiffChanged>> {
31:c002 *-- c001
32:c002 o-- c003
33:c002 o-- c004
```

```bash
rg -n 'FFF3B0|D39E00|E8F4FF|5B8DEF|DiffDependency' \
  build/manual-tests/pyclassuml-manual-env/out/iss-00033-green/colorized-green-from-base-2fa3434.svg \
  build/manual-tests/pyclassuml-manual-env/out/iss-00033-green/colorized-green-from-base-2fa3434.puml

no output
```

```bash
rg -n 'DFF5DF|4F9D5D|fill="#F1F1F1"|fill="#DFF5DF"|stroke:#181818|stroke:#4F9D5D|DiffChanged|Customer|Order|PaymentMethod|Shipment' \
  build/manual-tests/pyclassuml-manual-env/out/iss-00033-green/colorized-green-from-base-2fa3434.svg

1:... class c001 Customer rect fill="#F1F1F1" style="stroke:#181818;stroke-width:0.5;"
1:... class c002 Order rect fill="#DFF5DF" style="stroke:#4F9D5D;stroke-width:0.5;" ... DiffChanged
1:... class c003 PaymentMethod rect fill="#DFF5DF" style="stroke:#4F9D5D;stroke-width:0.5;" ... DiffChanged
1:... class c004 Shipment rect fill="#DFF5DF" style="stroke:#4F9D5D;stroke-width:0.5;" ... DiffChanged
```

#### SVG 視覚確認
- `Customer`:
  - dependency-only class として `<<DiffChanged>>` / `<<DiffDependency>>` なし。
  - SVG 内で `fill="#F1F1F1"`、`stroke:#181818` の default class box として描画された。
- `Order` / `PaymentMethod` / `Shipment`:
  - changed / newly added class として `<<DiffChanged>>` 付き。
  - SVG 内で `fill="#DFF5DF"`、`stroke:#4F9D5D` の薄い緑 class box として描画された。
- SVG concrete excerpts:
  - `Customer`: `<rect fill="#F1F1F1" ... style="stroke:#181818;stroke-width:0.5;"`
  - `Order`: `<rect fill="#DFF5DF" ... style="stroke:#4F9D5D;stroke-width:0.5;"`
  - `PaymentMethod`: `<rect fill="#DFF5DF" ... style="stroke:#4F9D5D;stroke-width:0.5;"`
  - `Shipment`: `<rect fill="#DFF5DF" ... style="stroke:#4F9D5D;stroke-width:0.5;"`
- 旧配色:
  - SVG / `.puml` に `#FFF3B0`、`#D39E00`、`#E8F4FF`、`#5B8DEF` は出ない。
- relation:
  - `c002 *-- c001`
  - `c002 o-- c003`
  - `c002 o-- c004`

#### 変更したファイル
- `src/pyclassuml/app/diff.py`
- `src/pyclassuml/model/__init__.py`
- `src/pyclassuml/model/contracts.py`
- `src/pyclassuml/parse/indexer.py`
- `src/pyclassuml/render/document.py`
- `src/pyclassuml/vcs/__init__.py`
- `src/pyclassuml/vcs/diff_collect.py`
- `tests/app/test_diff.py`
- `tests/model/test_contracts.py`
- `tests/parse/test_module_parse_and_index.py`
- `tests/render/test_document.py`
- `tests/vcs/test_diff_file_collect.py`
- `spec-dock/.../iss-00033-render-diff-class-colorization/requirement.md`
- `spec-dock/.../iss-00033-render-diff-class-colorization/design.md`
- `spec-dock/.../iss-00033-render-diff-class-colorization/plan.md`
- `spec-dock/.../iss-00033-render-diff-class-colorization/report.md`

#### 手動生成 artifact
- ignored manual output:
  - `build/manual-tests/pyclassuml-manual-env/out/iss-00033-green/colorized-green-from-base-2fa3434.puml`
  - `build/manual-tests/pyclassuml-manual-env/out/iss-00033-green/colorized-green-from-base-2fa3434.svg`

---

## Closure Coverage
- AC-001 changed class colorization:
  - `tests/app/test_diff.py` の diff E2E tests で changed class が `<<DiffChanged>>` になることを確認。
  - `tests/app/test_diff.py` で same file 内に changed / unchanged class が共存する場合、changed hunk と class span が重なる class だけが `<<DiffChanged>>` になることを確認。
  - `tests/app/test_diff.py` で nested class の inner body だけが変わった場合、inner class だけが `<<DiffChanged>>` になり outer class は default rendering のままになることを確認。
  - `tests/app/test_diff.py` で class body deletion-only hunk が `<<DiffChanged>>` になることを確認。
  - `tests/app/test_diff.py` で decorator-only class change が `<<DiffChanged>>` になることを確認。
  - `tests/app/test_diff.py` で decorator-only class removal が `<<DiffChanged>>` になることを確認。
  - `tests/app/test_diff.py` で top-level function decorator removal が直後の unchanged class に `DiffChanged` を誤付与しないことを確認。
  - `tests/app/test_diff.py` で decorated top-level helper 全体の削除により class が file start へ移動しても、unchanged class に `DiffChanged` を誤付与しないことを確認。
  - `tests/vcs/test_diff_file_collect.py` で deletion-only hunk の current-side point と deleted lines が保持されることを確認。
  - `tests/vcs/test_diff_file_collect.py` で current-side `+0,0` の class 先頭 decorator removal が current-side point と deleted lines として保持されることを確認。
  - manual `.puml`: `Order` / `PaymentMethod` / `Shipment` が `<<DiffChanged>>`。
  - manual SVG: changed / newly added class が `fill="#DFF5DF"`、`stroke:#4F9D5D`。
- AC-002 dependency-only class default rendering:
  - `tests/app/test_diff.py` の diff E2E tests で dependency-only class に `DiffChanged` / `DiffDependency` が出ないことを確認。
  - manual `.puml`: `Customer` が stereotype なし。
  - manual SVG: `Customer` が `fill="#F1F1F1"`、`stroke:#181818`。
- AC-003 generate unaffected:
  - `tests/app/test_generate.py` で generate output に `skinparam class` / `DiffChanged` / `DiffDependency` が出ないことを確認。
- AC-004 relation notation regression:
  - `tests/app/test_diff.py` と `tests/render/test_document.py` で `*--` / `o--` / `-up-|>` / `..up|>` / `..>` の維持を確認。
  - manual `.puml`: `c002 *-- c001`、`c002 o-- c003`、`c002 o-- c004`。
- AC-005 deterministic output:
  - `tests/app/test_diff.py` で同一 input の diff output equality を確認。
- EC-001 changed file without class:
  - `tests/app/test_diff.py` で changed file without class が changed style を捏造しないことを確認。
  - `tests/app/test_diff.py` で module-level only change / module-level deletion-only hunk が class highlight を捏造しないことを確認。
  - `tests/app/test_diff.py` で class 直後の module-level deletion-only hunk が class highlight を捏造しないことを確認。
  - `tests/app/test_diff.py` で class 直後の indented module-level continuation deletion が class highlight を捏造しないことを確認。
  - `tests/app/test_diff.py` で class ではない decorator deletion が class highlight を捏造しないことを確認。
  - `tests/app/test_diff.py` で deleted decorated helper が class highlight を捏造しないことを確認。
- EC-002 changed class not selected:
  - `tests/app/test_diff.py` の `_diff_class_decorations` test で selected 外 changed class を color declaration 対象にしないことを確認。
- EC-003 syntax error / join miss:
  - `tests/app/test_diff.py` で syntax error 時に diagnostics を保持し、`DiffChanged` を捏造しないことを確認。
- EC-004 working-tree / head / untracked semantics:
  - `tests/app/test_diff.py` で `include_untracked=True` の untracked class が `DiffChanged` になることを確認。
  - `tests/app/test_diff.py` で `current_state=head` の HEAD diff semantics に基づく色分けと untracked 不混入を確認。
  - `tests/vcs/test_diff_file_collect.py` で working-tree / rename / deletion-only hunk の current-side changed line range 収集を確認。

## Review Gate Evidence
- repo-analyst:
  - `app.diff` で changed / dependency-only を作り、render は decoration handoff だけを読む設計を推奨。
- spec-reviewer:
  - 初回 review は `review_status: pass`。P2 として EC-003 verification 明確化を指摘。
  - plan に syntax error / join miss targeted test を追加済み。
- code-reviewer:
  - 実装レビューは `review_status: pass`。P0/P1 finding なし。
  - green-only 修正後の review で、changed file 内の全 class を `DiffChanged` にしている P1 を検出。
  - VCS hunk range と parse class span の join に修正し、same-file unchanged class / module-level change / class-body deletion の tests を追加済み。
  - P2 として decorator 行が class span に含まれない点、`ParsedModule` positional constructor compatibility を指摘。
  - class span に decorator 行を含め、`ParsedModule` の既存 positional order を維持する形に修正済み。
  - 追加 review で class 先頭 decorator removal が `+0,0` として落ちる P1 を検出。
  - VCS hunk parser が decorator removal の `+0,0` を class span 判定可能な deletion-only range として保持するように修正済み。
  - 追加 review で top-level function decorator removal が直後の unchanged class に誤接続する P2 を検出。
  - current-side file lines と `is_before_first_line_deletion` を使い、class decorator removal と function decorator removal を切り分ける regression を追加済み。
  - fresh review は `review_status: pass`。P2 として decorated top-level helper 全体削除が file-start class に誤接続しうる edge case を検出。
  - 削除 hunk 内に top-level `def` / `async def` が含まれる場合は class decorator removal とみなさない regression を追加済み。
- qa-reviewer:
  - 初回 QA は `review_status: pass`。P2 として EC-004 untracked/head color assertion gap を指摘。
  - `tests/app/test_diff.py` に include-untracked / head current-state の色分け assertion を追加済み。
  - 最終 QA は `review_status: pass`。P2 として EC-001 classless changed Python file の直接 coverage gap を指摘。
  - `tests/app/test_diff.py` に classless changed Python file が diff seed に残りつつ `DiffChanged` を捏造しない assertion を追加済み。
  - 再レビューは `review_status: pass`。AC-001 - AC-005 と EC-001 - EC-004 の coverage が確認された。
  - 追加 QA で decorator removal の手動相当ケースが不足する P1 を検出。
  - `tests/vcs/test_diff_file_collect.py` と `tests/app/test_diff.py` に decorator removal coverage を追加済み。
  - 追加 QA で nested class の inner-only change が outer class まで highlight されうる P1 を検出。
  - changed hunk に重なる class spans のうち最も内側の span だけを `DiffChanged` にする実装と regression を追加済み。
  - fresh QA は `review_status: pass`。P0/P1/P2/P3 finding なし。
- spec-reviewer:
  - report 初回 review は SVG 色確認 evidence と final diff scope evidence の不足で fail。
  - SVG 内の fill/stroke/stereotype evidence と root diff scope evidence を追加後、再レビューは `review_status: pass`。
  - green-only report review は `review_status: pass`。P2 として SVG positive/negative command evidence、P3 として stale relation evidence の修正を指摘。
  - 本 report に `.puml` positive check、SVG/Puml 旧配色 negative check、relation evidence の修正を追加済み。
  - requirement の dependency-only 定義と design の hunk 粒度除外を、hunk/span class-level classification と矛盾しないよう修正済み。
  - fresh spec review は最終 reviewer pass 証跡と manual contract 整合の不足で fail。
  - plan の S04 manual contract を実際の multi-commit green-only 手順へ更新し、本節へ fresh code-reviewer / qa-reviewer evidence を追記済み。

## Final Diff Scope Evidence
```bash
git status --short --branch

## iss-00033-render-diff-class-colorization...origin/iss-00033-render-diff-class-colorization
 M .serena/project.yml
 M spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00004-framework-render-report/issues/iss-00033-render-diff-class-colorization/design.md
 M spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00004-framework-render-report/issues/iss-00033-render-diff-class-colorization/plan.md
 M spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00004-framework-render-report/issues/iss-00033-render-diff-class-colorization/report.md
 M spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00004-framework-render-report/issues/iss-00033-render-diff-class-colorization/requirement.md
 M src/pyclassuml/app/diff.py
 M src/pyclassuml/model/__init__.py
 M src/pyclassuml/model/contracts.py
 M src/pyclassuml/parse/indexer.py
 M src/pyclassuml/render/document.py
 M src/pyclassuml/vcs/__init__.py
 M src/pyclassuml/vcs/diff_collect.py
 M tests/app/test_diff.py
 M tests/model/test_contracts.py
 M tests/parse/test_module_parse_and_index.py
 M tests/render/test_document.py
 M tests/vcs/test_diff_file_collect.py
```

```bash
git diff --name-only

.serena/project.yml
spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00004-framework-render-report/issues/iss-00033-render-diff-class-colorization/design.md
spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00004-framework-render-report/issues/iss-00033-render-diff-class-colorization/plan.md
spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00004-framework-render-report/issues/iss-00033-render-diff-class-colorization/report.md
spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00004-framework-render-report/issues/iss-00033-render-diff-class-colorization/requirement.md
src/pyclassuml/app/diff.py
src/pyclassuml/model/__init__.py
src/pyclassuml/model/contracts.py
src/pyclassuml/parse/indexer.py
src/pyclassuml/render/document.py
src/pyclassuml/vcs/__init__.py
src/pyclassuml/vcs/diff_collect.py
tests/app/test_diff.py
tests/model/test_contracts.py
tests/parse/test_module_parse_and_index.py
tests/render/test_document.py
tests/vcs/test_diff_file_collect.py
```

- `.serena/project.yml` は作業前からの既存変更であり、この issue の write scope ではない。
- green-only 追加修正は未コミット。変更範囲は `iss-00033` issue docs、diff app、VCS diff collection、parse/model class span、render document、関連 tests に限定される。
- `uv.lock` は test 実行で生成されたが削除済み。
- GitHub issue #33 は以前に close 済みだが、ユーザー追加要望に基づく green-only 修正はこの未コミット差分として継続中。最終 commit evidence は commit 実施時に追記する。

## Close Evidence
```bash
./spec-dock/scripts/spec-dock close iss-00033

spec-dock: ok (close) target=iss-00033 node=iss-00033 kind=issue github=#33 state=CLOSED already_closed=false
```

```bash
gh issue view 33 --json number,state,title,closedAt,url

{"number":33,"state":"CLOSED","title":"Render Diff Class Colorization","closedAt":"2026-05-05T09:42:16Z","url":"https://github.com/chemitaro/pyclassuml/issues/33"}
```

## 遭遇した問題と解決
- 問題: EC-003 の plan verification が抽象的だった。
  - 解決: syntax error / parsed class join miss で `DiffChanged` を捏造しない targeted test を plan と実装に追加した。
- 問題: EC-004 の working-tree untracked / head current-state で色分け自体の assertion が不足していた。
  - 解決: `tests/app/test_diff.py` に untracked included class と head diff class の stereotype assertion を追加した。
- 問題: EC-001 の class 定義がない changed Python file が直接検証されていなかった。
  - 解決: `tests/app/test_diff.py` に classless changed Python file の app-level test を追加し、`changed_class_count == 0`、artifact なし、`class_decorations == ()`、`DiffChanged` を捏造しないことを確認した。

## 学んだこと
- `ChangedClassInventory` は summary semantics を守るため count/files のままにし、diagram decoration は `app.diff` の private helper で selected class に限定して作る方が責務境界を保ちやすい。

## 今後の推奨事項
- 追加 / 変更 / 削除の 3 分類や user configurable colors は、今回の changed / newly added class の単一ハイライトを土台に別 issue で扱う。

## 省略/例外メモ
- `.serena/project.yml` の既存変更は本 issue の対象外として触っていない。
