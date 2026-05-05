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
- `pyclassuml diff` の表示 class に `DiffChanged` / `DiffDependency` decoration を付与し、PlantUML の `skinparam class` と stereotype で changed class / dependency-only class を色分けできるようにした。
- changed class 判定は `app.diff` が existing changed-file context、`ParsedModule`、`ModuleIndex`、`SelectedClasses` を join して行い、render は Git を読まず、渡された decoration だけを描画する。
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

## Closure Coverage
- AC-001 changed class colorization:
  - `tests/app/test_diff.py` の diff E2E tests で changed class が `<<DiffChanged>>` になることを確認。
  - manual `.puml`: `UserService` が `<<DiffChanged>>`。
- AC-002 dependency-only class colorization:
  - `tests/app/test_diff.py` の diff E2E tests で dependency-only class が `<<DiffDependency>>` になることを確認。
  - manual `.puml`: `User` が `<<DiffDependency>>`。
- AC-003 generate unaffected:
  - `tests/app/test_generate.py` で generate output に `skinparam class` / `DiffChanged` / `DiffDependency` が出ないことを確認。
- AC-004 relation notation regression:
  - `tests/app/test_diff.py` と `tests/render/test_document.py` で `*--` / `o--` / `-up-|>` / `..up|>` / `..>` の維持を確認。
  - manual `.puml`: `c001 *-- c002`。
- AC-005 deterministic output:
  - `tests/app/test_diff.py` で同一 input の diff output equality を確認。
- EC-001 changed file without class:
  - `tests/app/test_diff.py` で changed file without class が changed style を捏造しないことを確認。
- EC-002 changed class not selected:
  - `tests/app/test_diff.py` の `_diff_class_decorations` test で selected 外 changed class を color declaration 対象にしないことを確認。
- EC-003 syntax error / join miss:
  - `tests/app/test_diff.py` で syntax error 時に diagnostics を保持し、`DiffChanged` を捏造しないことを確認。
- EC-004 working-tree / head / untracked semantics:
  - `tests/app/test_diff.py` で `include_untracked=True` の untracked class が `DiffChanged` になることを確認。
  - `tests/app/test_diff.py` で `current_state=head` の HEAD diff semantics に基づく色分けと untracked 不混入を確認。

## Review Gate Evidence
- repo-analyst:
  - `app.diff` で changed / dependency-only を作り、render は decoration handoff だけを読む設計を推奨。
- spec-reviewer:
  - 初回 review は `review_status: pass`。P2 として EC-003 verification 明確化を指摘。
  - plan に syntax error / join miss targeted test を追加済み。
- code-reviewer:
  - 実装レビューは `review_status: pass`。P0/P1 finding なし。
- qa-reviewer:
  - 初回 QA は `review_status: pass`。P2 として EC-004 untracked/head color assertion gap を指摘。
  - `tests/app/test_diff.py` に include-untracked / head current-state の色分け assertion を追加済み。
  - 最終 QA は `review_status: pass`。P2 として EC-001 classless changed Python file の直接 coverage gap を指摘。
  - `tests/app/test_diff.py` に classless changed Python file が diff seed に残りつつ `DiffChanged` を捏造しない assertion を追加済み。
  - 再レビューは `review_status: pass`。AC-001 - AC-005 と EC-001 - EC-004 の coverage が確認された。
- spec-reviewer:
  - report 初回 review は SVG 色確認 evidence と final diff scope evidence の不足で fail。
  - SVG 内の fill/stroke/stereotype evidence と root diff scope evidence を追加後、再レビューは `review_status: pass`。

## Final Diff Scope Evidence
```bash
git status --short --branch

## iss-00033-render-diff-class-colorization...origin/iss-00033-render-diff-class-colorization [ahead 2]
 M .serena/project.yml
 M spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00004-framework-render-report/issues/iss-00033-render-diff-class-colorization/report.md
```

```bash
git diff --name-only

.serena/project.yml
spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00004-framework-render-report/issues/iss-00033-render-diff-class-colorization/report.md
```

- `.serena/project.yml` は作業前からの既存変更であり、この issue の write scope ではない。
- 実装差分は `7a9baa1` にコミット済み。残る未コミット差分は本 report と既存 `.serena/project.yml` のみ。
- 本 issue の変更範囲は `iss-00033` issue docs、`src/pyclassuml/app/diff.py`、`src/pyclassuml/render/document.py`、および app/render/generate tests に限定される。
- `find . -maxdepth 2 -name 'uv.lock' -o -name '__pycache__'` は出力なし。unexpected generated file は検出されていない。

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
- 追加 / 変更 / 削除の 3 分類や user configurable colors は、今回の 2 分類色分けを土台に別 issue で扱う。

## 省略/例外メモ
- `.serena/project.yml` の既存変更は本 issue の対象外として触っていない。
