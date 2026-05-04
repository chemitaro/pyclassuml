---
種別: 実装報告書（Issue）
ID: "iss-00028"
タイトル: "Member Rendering E2E"
関連GitHub: ["#28"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md", "plan.md"]
親: ["epic-00023", "init-00001"]
---

# iss-00028 Member Rendering E2E — 実装報告（LOG）

## 実装サマリー (任意)
- tracked `generate` / `diff` integration に、class body、typed alias arrows、Pydantic quoted refs、dataclass、Protocol、exception、nested class、unresolved / ambiguous warning の assertion を追加した。
- Git 管理外の manual env `build/manual-tests/pyclassuml-manual-env` で generate / diff / ambiguous acceptance を実行し、出力とログを ignored `out/iss-00028/` に残した。
- manual env は pre/post とも clean。source fixture は変更せず、diff/ambiguous は disposable copy で観測した。

## 実装記録（セッションログ） (必須)

### 2026-05-04 23:24 - 23:36

#### 対象
- Step: S01, S02, S03, S90, S99
- AC/EC: AC-001, AC-002, AC-003, AC-004, EC-001, EC-002, EC-003

#### 実施内容
- `tests/app/test_generate.py` に member rendering E2E fixture と alias relation helper を追加した。
- `tests/app/test_diff.py` に independent diff scenario を追加し、diff path の class body / alias arrow / summary を assertion した。
- manual env で `generate` を実行し、`retail_domain` 全体の class body、method signature、field association、inherits relation、warnings を確認した。
- manual env の disposable copy で `diff` と ambiguous warning を実行し、source manual env を clean に保った。

#### 実行コマンド / 結果
```bash
uv run --with pytest pytest tests/app/test_generate.py tests/app/test_diff.py tests/render/test_document.py -q

48 passed in 1.05s
```

```bash
uv run --with pytest pytest -q

326 passed in 9.98s
```

```bash
git -C build/manual-tests/pyclassuml-manual-env status --short --branch

pre-clean:
## main
```

```bash
uv run pyclassuml generate --cwd /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env --project-root . --package-root . --scope-root . --output /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/out/iss-00028/generate.puml retail_domain

exit_code: 0
outcome: warning_only_success
seed_file_count: 15
extracted_class_count: 32
extracted_relation_count: 32
warning_count: 50
observed: CheckoutRequest field body, dataclass Order / OrderLine fields and methods, alias association arrows, DomainError inheritance, Protocol method bodies, GhostPaymentProviderContext warning
```

```bash
uv run pyclassuml diff --cwd /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/tmp/iss-00028-diff-worktree --project-root . --package-root . --scope-root . --base base --current-state working-tree --output /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/out/iss-00028/diff.puml

exit_code: 0
outcome: warning_only_success
seed_file_count: 1
changed_class_count: 1
observed: CheckoutService + last_order, + preview_total(order: Order): Decimal, selection_outside InventoryRepository / InventoryReservation / Order / OrderRepository / PaymentGateway warnings, Decimal unresolved warning
```

```bash
uv run pyclassuml generate --cwd /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/tmp/iss-00028-diff-worktree --project-root . --package-root . --scope-root . --output /Users/iwasawayuuta/workspace/tools/pyclassuml/build/manual-tests/pyclassuml-manual-env/out/iss-00028/ambiguous.puml retail_domain

exit_code: 0
observed: typed_relation_ambiguous for AmbiguousProbe.duplicate / DuplicateName, AmbiguousProbe alias c001 had no arbitrary relation to DuplicateName aliases c002 / c022
```

```bash
git -C build/manual-tests/pyclassuml-manual-env status --short --branch

post-clean:
## main
```

```bash
./spec-dock/scripts/spec-dock sync --github

spec-dock: sync: active unchanged (matched id in branch: iss-00028)
spec-dock: ok (sync) wrote=spec-dock/.agent/index-all.json,spec-dock/.agent/tree-all.json,spec-dock/.agent/index.json,spec-dock/.agent/tree.json,spec-dock/tree-all.puml,spec-dock/tree.puml,spec-dock/.agent/deps-issues.json,spec-dock/deps-issues.puml,spec-dock/dashboard.md
```

```bash
./spec-dock/scripts/spec-dock validate

spec-dock: ok (validate) nodes=28
```

```bash
git diff --check

passed
```

```bash
rg --files | rg '[A-Z]'

existing allowed uppercase paths only: AGENTS.md and README.md files
```

#### 変更したファイル
- `tests/app/test_generate.py` - member rendering generate E2E assertions
- `tests/app/test_diff.py` - member rendering diff E2E assertions
- `spec-dock/.../iss-00028-member-rendering-e2e/{requirement,design,plan}.md` - acceptance contract clarification

#### コミット
- 未実施（commit 前の最終 report 更新）

#### メモ
- manual output/logs are ignored by repo root and by manual env git: `build/manual-tests/pyclassuml-manual-env/out/iss-00028/`.
- disposable copy was removed after manual diff / ambiguous runs.

---

### 2026-05-04 23:36 - 23:36

#### 実施内容
- SG pass after clarifying manual/tracked evidence split.
- RG pass: code-reviewer found no issues.
- QG first pass failed on stale manual diff report evidence; report was corrected to match regenerated `diff.stdout` / `diff.puml` and separate pre/post clean status.
- QG final pass: qa-reviewer confirmed the manual diff evidence mismatch and pre/post clean separation were resolved. Remaining P2 report-completeness note for manual dataclass evidence was reflected.
- Spec review P1 required no-arbitrary-relation evidence for ambiguous typed refs; tracked generate E2E now asserts that two `Duplicate` aliases exist and `CheckoutRequest` emits no `-->` / `..>` relation to either ambiguous candidate.
- QA P2 requested tracked dataclass method evidence; tracked generate E2E now asserts `OrderDraft.confirm(): Authorization` and its uses relation.
- Final reviews: spec-reviewer pass, qa-reviewer pass, code-reviewer pass.
- Final gate rerun after report correction: targeted tests 48 passed, full tests 326 passed, `sync --github` OK, `validate` OK, `git diff --check` passed, manual env post-clean `## main`.

---

## 遭遇した問題と解決 (任意)
- 問題: manual diff では external `Order` が selection outside になり、manual diff artifact に relation arrow が出なかった。
  - 解決: manual diff は changed class body / warning / summary evidence に寄せ、diff arrow は tracked diff fixture で固定する契約へ修正した。
- 問題: existing `LegacyWebhookPayload.duplicate` は same-module preference により ambiguous にならなかった。
  - 解決: disposable copy に `ambiguous_probe.py` を追加し、same-module duplicate を作らず 2 候補の `DuplicateName` で `typed_relation_ambiguous` を観測した。

## 学んだこと (任意)
- manual acceptance は CLI 引数と selection scope に強く依存するため、実測に合わせて tracked/manual の責務分担を明確化する必要があった。
- `out/` / `tmp/` が manual env 内で ignored であることを確認し、source fixture を clean に保ったまま証跡を残せた。

## 今後の推奨事項 (任意)
- epic close 前に issue 24-28 の closed 状態と branch/head commit をまとめて audit する。

## 省略/例外メモ (必須)
- 該当なし
