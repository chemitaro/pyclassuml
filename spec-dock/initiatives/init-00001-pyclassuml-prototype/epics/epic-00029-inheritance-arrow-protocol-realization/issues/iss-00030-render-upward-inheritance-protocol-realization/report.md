---
種別: 実装報告書（Issue）
ID: "iss-00030"
タイトル: "Render Upward Inheritance And Protocol Realization"
関連GitHub: ["#30"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-05"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00029", "init-00001"]
---

# iss-00030 Render Upward Inheritance And Protocol Realization — 実装報告（LOG）

## 実装サマリー
- `realizes` relation type を model contract に追加し、selected Protocol class への base relation を `realizes` に分類する selection logic を実装した。
- PlantUML 出力は通常継承を `-up-|>`、Protocol realization を `..up|>` にし、明示的な `Protocol` base を持つ class に `<<Protocol>>` stereotype を付与する。
- targeted / full tests、manual env generate + SVG 変換、`sync --github`、`validate`、`git diff --check` を実行した。

## 実装記録（セッションログ）

### 2026-05-05 00:xx - 00:xx

#### 対象
- Step: S01, S02, S03, S04, S99
- AC/EC: AC-001, AC-002, AC-003, AC-004, EC-001, EC-002

#### 実施内容
- `epic-00029` と `iss-00030` を作成し、継承矢印上向き / Protocol realization 方針を spec 化した。
- GitHub issue 作成時に一度 `HTTP 502 Bad Gateway` が出たため、ローカル半端 node が無いことを確認して再試行し、作成に成功した。
- `iss-00030` を active set し、`iss-00030-render-upward-inheritance-protocol-realization` branch へ checkout した。

#### 実行コマンド / 結果
```bash
./spec-dock/scripts/spec-dock new epic --initiative init-00001 --title "Inheritance Arrow And Protocol Realization" --slug inheritance-arrow-protocol-realization

first run: HTTP 502 Bad Gateway
retry: ok, epic-00029 github=#29
```

```bash
./spec-dock/scripts/spec-dock new issue --epic epic-00029 --title "Render Upward Inheritance And Protocol Realization" --slug render-upward-inheritance-protocol-realization

ok, iss-00030 github=#30
```

```bash
./spec-dock/scripts/spec-dock active set iss-00030 --checkout

ok, branch=iss-00030-render-upward-inheritance-protocol-realization
```

#### 変更したファイル
- `spec-dock/.../epic-00029-inheritance-arrow-protocol-realization/{requirement,design,plan}.md`
- `spec-dock/.../iss-00030-render-upward-inheritance-protocol-realization/{requirement,design,plan,report}.md`

#### コミット
- `34f3834 docs(spec): 継承矢印とprotocol realizationのissueを追加`

#### メモ
- Implementation / validation evidence は実装後に追記する。

---

### 2026-05-05 00:40 - 00:54

#### 対象
- Step: S01, S02, S03, S04, S99
- AC/EC: AC-001, AC-002, AC-003, AC-004, EC-001, EC-002

#### 実施内容
- `RelationType` vocabulary に `realizes` を追加した。
- analyze selection で selected class が `Protocol` / `typing.Protocol` / `typing_extensions.Protocol` を明示 base に持つ場合のみ Protocol class として扱い、その class への base relation を `realizes` に分類した。
- Protocol marker base 自体は external `Protocol` node / unresolved warning として出さない。
- render で `inherits -> -up-|>`、`realizes -> ..up|>`、`association -> -->`、`uses -> ..>` を出力し、Protocol class declaration に `<<Protocol>>` を付けた。
- model / analyze / render / generate tests を追加・更新した。
- manual env `retail_domain` を書き換えずに generate と SVG 変換を実行し、Protocol stereotype、通常継承上向き、association、uses、member body を確認した。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest -q tests/model/test_contracts.py tests/analyze/test_selection.py tests/render/test_document.py tests/app/test_generate.py

79 passed in 0.05s
```

```bash
uv run --with pytest pytest -q

332 passed in 9.50s
```

```bash
uv run pyclassuml generate --cwd /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env --project-root . --package-root . --scope-root . --output /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/out/iss-00030/generate.puml retail_domain

exit_code: 0
outcome: warning_only_success
extracted_class_count: 32
extracted_relation_count: 32
warning_count: 47
observed: <<Protocol>> on InventoryRepository / OrderRepository / PaymentGateway, -up-|> for DomainError inheritance, --> associations, ..> uses, field / method bodies
```

```bash
docker run --rm -v /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/out/iss-00030:/work plantuml/plantuml:latest -tsvg /work/generate.puml

ok, generated build/manual-tests/pyclassuml-manual-env/out/iss-00030/generate.svg
```

```bash
uv run pyclassuml generate --cwd /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/tmp/iss-00030-protocol-worktree --project-root . --package-root . --scope-root . --output /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/out/iss-00030/protocol-realization.puml retail_domain

exit_code: 0
outcome: warning_only_success
extracted_class_count: 33
extracted_relation_count: 33
warning_count: 49
observed: disposable copy added RecordingPaymentGateway(PaymentGateway), PaymentGateway <<Protocol>>, RecordingPaymentGateway ..up|> PaymentGateway, DomainError inheritance -up-|>
```

```bash
docker run --rm -v /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/out/iss-00030:/work plantuml/plantuml:latest -tsvg /work/protocol-realization.puml

ok, generated build/manual-tests/pyclassuml-manual-env/out/iss-00030/protocol-realization.svg
```

```bash
./spec-dock/scripts/spec-dock sync --github

spec-dock: sync: active unchanged (matched id in branch: iss-00030)
spec-dock: ok (sync) wrote=spec-dock/.agent/index-all.json,spec-dock/.agent/tree-all.json,spec-dock/.agent/index.json,spec-dock/.agent/tree.json,spec-dock/tree-all.puml,spec-dock/tree.puml,spec-dock/.agent/deps-issues.json,spec-dock/deps-issues.puml,spec-dock/dashboard.md
```

```bash
./spec-dock/scripts/spec-dock validate

spec-dock: ok (validate) nodes=30
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
git -C build/manual-tests/pyclassuml-manual-env status --short --branch

## main
```

#### 変更したファイル
- `src/pyclassuml/model/contracts.py` - `realizes` relation type validation
- `src/pyclassuml/analyze/selection.py` - Protocol marker detection and realizes classification
- `src/pyclassuml/render/document.py` - upward inheritance / realization arrows and Protocol stereotype rendering
- `tests/model/test_contracts.py` - model relation type coverage
- `tests/analyze/test_selection.py` - Protocol classification, `ABC` non-heuristic, method-only non-heuristic coverage
- `tests/render/test_document.py` - arrow mapping and Protocol stereotype rendering coverage
- `tests/app/test_generate.py` - generate E2E assertions for upward inheritance, Protocol stereotype, and realization
- `spec-dock/.../iss-00030-render-upward-inheritance-protocol-realization/report.md` - implementation and validation evidence

#### コミット
- 未実施（commit 前の最終 report 更新）

#### メモ
- `retail_domain` source fixture は explicit Protocol implementation class を持たないため、source fixture を直接変更せず disposable copy に `RecordingPaymentGateway(PaymentGateway)` を追加して `..up|>` を manual 観測した。
- manual output/logs are ignored by repo root and by manual env git: `build/manual-tests/pyclassuml-manual-env/out/iss-00030/`.

---

### 2026-05-05 00:57 - 01:02

#### 対象
- Step: S02, S99
- AC/EC: AC-002, EC-001, EC-002

#### 実施内容
- code review P2 を反映し、project 内部の通常 class `Protocol` へ `Foo(Protocol)` した場合は marker ではなく通常 `inherits` として扱うようにした。
- QA review P2 を反映し、method-only-like class を Protocol と推測しない負例、class_base unresolved / selection outside で relation を捏造しない負例を追加した。
- RG1 / QG1 / SG1 は pass。P2 指摘は上記追加 test / logic と report 更新で反映した。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest -q tests/analyze/test_selection.py

25 passed in 0.02s
```

```bash
uv run --with pytest pytest -q tests/model/test_contracts.py tests/analyze/test_selection.py tests/render/test_document.py tests/app/test_generate.py

79 passed in 0.05s
```

```bash
uv run --with pytest pytest -q

332 passed in 9.50s
```

```bash
git diff --check

passed
```

#### 変更したファイル
- `src/pyclassuml/analyze/selection.py` - bare `Protocol` marker resolution guard
- `tests/analyze/test_selection.py` - internal `Protocol` / method-only / class_base warning negative coverage

#### コミット
- 未実施（commit 前の最終 report 更新）

---

### 2026-05-05 01:02 - 01:07

#### 対象
- Step: S03, S04, S99
- AC/EC: AC-001, AC-002, AC-004, EC-001

#### 実施内容
- QA/spec review P1 を反映し、render 側でも project 内部の通常 class `Protocol` を `<<Protocol>>` と誤表示しない guard と regression test を追加した。
- 最後の code/report 変更後に、targeted/full tests、manual generate + SVG、`sync --github`、`validate`、`git diff --check`、manual env clean、uppercase path scan を再実行した。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest -q tests/render/test_document.py tests/app/test_generate.py tests/analyze/test_selection.py

56 passed in 0.06s
```

```bash
uv run --with pytest pytest -q tests/model/test_contracts.py tests/analyze/test_selection.py tests/render/test_document.py tests/app/test_generate.py

80 passed in 0.06s
```

```bash
uv run --with pytest pytest -q

333 passed in 9.80s
```

```bash
uv run pyclassuml generate --cwd /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/tmp/iss-00030-protocol-worktree --project-root . --package-root . --scope-root . --output /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/out/iss-00030/protocol-realization-final.puml retail_domain

exit_code: 0
outcome: warning_only_success
extracted_class_count: 33
extracted_relation_count: 33
warning_count: 49
observed: PaymentGateway <<Protocol>>, RecordingPaymentGateway ..up|> PaymentGateway, DomainError inheritance -up-|>, field / method bodies
```

```bash
docker run --rm -v /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/out/iss-00030:/work plantuml/plantuml:latest -tsvg /work/protocol-realization-final.puml

ok, generated build/manual-tests/pyclassuml-manual-env/out/iss-00030/protocol-realization-final.svg
```

```bash
./spec-dock/scripts/spec-dock sync --github
./spec-dock/scripts/spec-dock validate

spec-dock: ok (sync)
spec-dock: ok (validate) nodes=30
```

```bash
git diff --check
git -C build/manual-tests/pyclassuml-manual-env status --short --branch
rg --files | rg '[A-Z]'

diff check: passed
manual env: ## main
uppercase scan: existing allowed uppercase paths only: AGENTS.md and README.md files
```

#### 変更したファイル
- `src/pyclassuml/render/document.py` - render-side Protocol marker guard
- `tests/render/test_document.py` - internal normal `Protocol` render negative coverage
- `spec-dock/.../iss-00030-render-upward-inheritance-protocol-realization/report.md` - final evidence

#### コミット
- 未実施（commit 前の最終 report 更新）

---

### 2026-05-05 01:07 - 01:15

#### 対象
- Step: S02, S03, S04, S99
- AC/EC: AC-002, AC-004, EC-001, EC-002

#### 実施内容
- spec review P1 を反映し、bare `Protocol` 判定で source module の `from typing import Protocol` / `from typing_extensions import Protocol` import を参照するようにした。
- 別 module に通常 class `Protocol` が存在しても、typing から import された bare `Protocol` は marker として扱い、通常 internal `Protocol` は引き続き通常継承として扱う regression coverage を追加した。
- render 側の `<<Protocol>>` decoration 判定も同じ import-aware semantics に合わせた。
- qualified `typing.Protocol` / `typing_extensions.Protocol` の visible render coverage を追加した。
- 最後の code/report 変更後に final validation を再実行した。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest -q tests/analyze/test_selection.py tests/render/test_document.py tests/app/test_generate.py

59 passed in 0.04s
```

```bash
uv run --with pytest pytest -q tests/model/test_contracts.py tests/analyze/test_selection.py tests/render/test_document.py tests/app/test_generate.py

83 passed in 0.05s
```

```bash
uv run --with pytest pytest -q

336 passed in 9.36s
```

```bash
uv run pyclassuml generate --cwd /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/tmp/iss-00030-protocol-worktree --project-root . --package-root . --scope-root . --output /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/out/iss-00030/protocol-realization-final2.puml retail_domain

exit_code: 0
outcome: warning_only_success
extracted_class_count: 33
extracted_relation_count: 33
warning_count: 49
observed: PaymentGateway <<Protocol>>, RecordingPaymentGateway ..up|> PaymentGateway, DomainError inheritance -up-|>, field / method bodies
```

```bash
docker run --rm -v /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/out/iss-00030:/work plantuml/plantuml:latest -tsvg /work/protocol-realization-final2.puml

ok, generated build/manual-tests/pyclassuml-manual-env/out/iss-00030/protocol-realization-final2.svg
```

```bash
./spec-dock/scripts/spec-dock sync --github
./spec-dock/scripts/spec-dock validate

spec-dock: ok (sync)
spec-dock: ok (validate) nodes=30
```

```bash
git diff --check
git -C build/manual-tests/pyclassuml-manual-env status --short --branch
rg --files | rg '[A-Z]'

diff check: passed
manual env: ## main
uppercase scan: existing allowed uppercase paths only: AGENTS.md and README.md files
```

#### 変更したファイル
- `src/pyclassuml/analyze/selection.py` - import-aware bare Protocol marker classification
- `src/pyclassuml/render/document.py` - import-aware Protocol decoration classification
- `tests/analyze/test_selection.py` - imported bare Protocol / unrelated internal Protocol coexistence coverage
- `tests/render/test_document.py` - qualified Protocol and internal Protocol visible render coverage
- `spec-dock/.../iss-00030-render-upward-inheritance-protocol-realization/report.md` - final evidence

#### コミット
- 未実施（commit 前の最終 report 更新）

---

### 2026-05-05 01:15 - 01:18

#### 対象
- Step: S02, S99
- AC/EC: EC-002

#### 実施内容
- QA review P2 を反映し、bare `Protocol` が reachable だが unselected な internal class へ解決する場合、marker / relation を捏造せず `typed_relation_selection_outside` warning を出す regression coverage を追加した。
- 最後の test/report 変更後に targeted/full tests と final checks を再実行した。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest -q tests/analyze/test_selection.py tests/render/test_document.py tests/app/test_generate.py

60 passed in 0.06s
```

```bash
uv run --with pytest pytest -q tests/model/test_contracts.py tests/analyze/test_selection.py tests/render/test_document.py tests/app/test_generate.py

84 passed in 0.05s
```

```bash
uv run --with pytest pytest -q

337 passed in 9.62s
```

```bash
./spec-dock/scripts/spec-dock sync --github
./spec-dock/scripts/spec-dock validate

spec-dock: ok (sync)
spec-dock: ok (validate) nodes=30
```

```bash
git diff --check
git -C build/manual-tests/pyclassuml-manual-env status --short --branch
rg --files | rg '[A-Z]'

diff check: passed
manual env: ## main
uppercase scan: existing allowed uppercase paths only: AGENTS.md and README.md files
```

#### 変更したファイル
- `tests/analyze/test_selection.py` - Protocol-specific selection-outside coverage
- `spec-dock/.../iss-00030-render-upward-inheritance-protocol-realization/report.md` - final evidence

#### コミット
- 未実施（commit 前の最終 report 更新）

---

### 2026-05-05 01:18 - 01:24

#### 対象
- Step: S02, S03, S99
- AC/EC: AC-002, EC-002

#### 実施内容
- 残 P2 alias-binding edge case を反映し、`from typing import Protocol as TypingProtocol` を source module の bare `Protocol` import と誤判定しないようにした。
- `ParsedModule.imports` の `ImportFrom` 表示に `as` alias を残し、import candidate 解決用の元名は維持した。
- analyze / render の bare `Protocol` marker 判定を「source module 内で local name が実際に `Protocol` になる import」に揃えた。
- `from typing import Any, Protocol` は bare Protocol marker、`from typing import Protocol as TypingProtocol` + internal normal class `Protocol` + `Foo(Protocol)` は通常継承、qualified `typing.Protocol` / `typing_extensions.Protocol` は marker のまま、という regression coverage を追加した。
- 最後の code/report 変更後に full tests、manual generate + SVG、`sync --github`、`validate`、`git diff --check`、manual env clean、uppercase path scan を再実行した。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest -q tests/parse/test_module_parse_and_index.py tests/analyze/test_selection.py tests/render/test_document.py tests/app/test_generate.py

95 passed in 0.08s
```

```bash
uv run --with pytest pytest -q tests/model/test_contracts.py tests/analyze/test_selection.py tests/render/test_document.py tests/app/test_generate.py

86 passed in 0.05s
```

```bash
uv run --with pytest pytest -q

340 passed in 9.39s
```

```bash
uv run pyclassuml generate --cwd /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/tmp/iss-00030-protocol-worktree --project-root . --package-root . --scope-root . --output /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/out/iss-00030/protocol-realization-final3.puml retail_domain

exit_code: 0
outcome: warning_only_success
extracted_class_count: 33
extracted_relation_count: 33
warning_count: 49
observed: PaymentGateway <<Protocol>>, RecordingPaymentGateway ..up|> PaymentGateway, DomainError inheritance -up-|>, field / method bodies
```

```bash
docker run --rm -v /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/out/iss-00030:/work plantuml/plantuml:latest -tsvg /work/protocol-realization-final3.puml

ok, generated build/manual-tests/pyclassuml-manual-env/out/iss-00030/protocol-realization-final3.svg
```

```bash
./spec-dock/scripts/spec-dock sync --github
./spec-dock/scripts/spec-dock validate

spec-dock: ok (sync)
spec-dock: ok (validate) nodes=30
```

```bash
git diff --check
git -C build/manual-tests/pyclassuml-manual-env status --short --branch
rg --files | rg '[A-Z]'

diff check: passed
manual env: ## main
uppercase scan: existing allowed uppercase paths only: AGENTS.md and README.md files
```

#### 変更したファイル
- `src/pyclassuml/parse/indexer.py` - `ImportFrom` alias-preserving import text
- `src/pyclassuml/analyze/selection.py` - alias-aware bare Protocol marker判定
- `src/pyclassuml/render/document.py` - analyze と同じ alias-aware Protocol decoration 判定
- `tests/parse/test_module_parse_and_index.py` - alias-preserving import regression
- `tests/analyze/test_selection.py` - alias import + internal normal `Protocol` regression
- `tests/render/test_document.py` - alias import caseで `<<Protocol>>` を出さない regression
- `spec-dock/.../iss-00030-render-upward-inheritance-protocol-realization/report.md` - P2 alias-binding evidence

#### コミット
- 未実施（commit 前の最終 report 更新）

---

## 遭遇した問題と解決
- 問題: GitHub issue 作成で一度 `HTTP 502 Bad Gateway` が発生した。
  - 解決: local spec node が作成されていないことと `spec-dock validate` OK を確認し、同じ command を再試行して成功した。
- 問題: `retail_domain` fixture は Protocol definition を持つが、明示的に Protocol class を継承する implementation class は持たない。
  - 解決: fixture を直接書き換えず、disposable copy に `RecordingPaymentGateway(PaymentGateway)` を追加して `realizes` の manual evidence を取得し、copy を削除して manual env clean を確認した。
- 問題: bare `Protocol` marker 判定が、project 内部の通常 class `Protocol` と衝突しうる。
  - 解決: bare `Protocol` は selected internal class へ解決できる場合 marker とみなさず、通常 `inherits` として扱う guard と regression test を追加した。
- 問題: render 側も独自に bare `Protocol` を `<<Protocol>>` とみなし、analyze の false-positive fix とズレうる。
  - 解決: render 側の Protocol decoration 判定にも internal class guard を追加し、PlantUML 出力レイヤで `<<Protocol>>` が出ない regression test を追加した。
- 問題: 別 module に通常 class `Protocol` があると、`from typing import Protocol` 由来の bare `Protocol` まで marker から外れうる。
  - 解決: source module imports を参照し、typing / typing_extensions から import された bare `Protocol` は unrelated internal `Protocol` に影響されず marker として扱うようにした。
- 問題: `from typing import Protocol as TypingProtocol` の alias import でも bare `Protocol` を marker と誤判定しうる。
  - 解決: parse import text に alias を保持し、local name が実際に `Protocol` の場合だけ bare marker として扱うようにした。

## 学んだこと
- 新規 issue 作成直後は sync 前に active guard が `unknown` になることがあるため、`deps check --github` と `sync --github` で ready 状態を確認してから active set する。
- Protocol marker base は external typing class への relation ではなく selected class decoration / downstream relation classification の evidence として扱うと、external node を増やさず warning noise も減らせる。

## 今後の推奨事項
- `ABC` / `@abstractmethod` の interface-like opt-in は別 issue として扱う。

## 省略/例外メモ
- 該当なし
