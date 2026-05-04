---
種別: 実装計画書（Issue）
ID: "iss-00028"
タイトル: "Member Rendering E2E"
関連GitHub: ["#28"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
依存: ["requirement.md", "design.md"]
親: ["epic-00023", "init-00001"]
---

# iss-00028 Member Rendering E2E — 実装計画（Execution Contract）

## この計画で満たす要件ID
- AC:
  - AC-001 generate integration
  - AC-002 diff integration
  - AC-003 manual retail_domain acceptance
  - AC-004 warning observation
- EC:
  - EC-001 tracked/manual split
  - EC-002 unresolved warning acceptance
  - EC-003 dataclass / Protocol / exception / nested / ambiguous coverage
- 制約:
  - no manual env mutation
  - deterministic tracked assertions
  - CLI surface unchanged

## マイルストーン一覧
- M1:
  - 対象:
    - tracked generate / diff integration
  - exit:
    - `tests/app` が member-aware assertions を持つ
- M2:
  - 対象:
    - minimal coverage gaps fill
  - exit:
    - dataclass / Protocol / exception / nested / ambiguous / unresolved warning の tracked assertion が揃う
- M3:
  - 対象:
    - manual retail_domain acceptance
  - exit:
    - generate / diff manual evidence が report に残る

## 依存関係から導く実装順序
- 依存関係の正本:
  - `design.md` の `依存関係分析`
  - `design.md` の `Module Dependency Diagram`
  - `design.md` の `ディレクトリ / ファイル変更計画`
- sequencing rule:
  - upstream / prerequisite / lower-dependency slice から先に step を組む
  - downstream / dependent slice は前提が固まってから置く
- step ordering notes:
  - tracked tests を先に安定させ、manual env は最後の acceptance gate に置く
- step dependency summary:
  - S01:
    - depends on:
      - iss-00024
      - iss-00025
      - iss-00026
      - iss-00027
    - unblocks:
      - S02, S03
    - target files:
      - `tests/app/test_generate.py`
      - `tests/app/test_diff.py`

## ステップ一覧
- S01:
  - 観測可能な振る舞い:
    - generate / diff integration test が class body / typed relation を assertion できる
  - depends on:
    - iss-00024
    - iss-00025
    - iss-00026
    - iss-00027
  - unblocks:
    - S02, S03
  - target files:
    - `tests/app/test_generate.py`
    - `tests/app/test_diff.py`
  - closes:
    - AC-001, AC-002
  - review gate:
    - app integration tests pass
- S02:
  - 観測可能な振る舞い:
    - unresolved warning、dataclass、Protocol、exception、nested、ambiguous case の tracked assertion が揃う
  - depends on:
    - S01
  - unblocks:
    - S03
  - target files:
    - `tests/app/test_generate.py`
    - `tests/app/test_diff.py`
    - `tests/render/test_document.py`
  - closes:
    - AC-004, EC-002, EC-003
  - review gate:
    - coverage review pass
- S03:
  - 観測可能な振る舞い:
    - `retail_domain` manual env で generate / diff acceptance が完了する
  - depends on:
    - S02
  - unblocks:
    - final close
  - target files:
    - `spec-dock/active/issue/report.md`
  - closes:
    - AC-003, EC-001
  - review gate:
    - manual evidence recorded
- S90:
  - 観測可能な振る舞い:
    - epic acceptance evidence が report にまとまる
  - depends on:
    - S03
  - unblocks:
    - S99
  - target files:
    - `spec-dock/active/issue/report.md`
  - closes:
    - docs impact
  - review gate:
    - report completeness review
- S99:
  - 観測可能な振る舞い:
    - final validation と review が揃う
  - depends on:
    - S90
  - unblocks:
    - epic closure
  - target files:
    - `spec-dock/active/issue/report.md`
  - closes:
    - final exit contract
  - review gate:
    - SG/RG/QG pass

## 要件 ↔ ステップ対応
- AC-001 -> S01
- AC-002 -> S01
- AC-003 -> S03
- AC-004 -> S02, S03
- EC-001 -> S03
- EC-002 -> S02, S03
- EC-003 -> S02

## レビュー / QA ゲート方針
- RG1 implementation review:
  - timing:
    - S01-S03 green 後
  - scope:
    - CLI observable acceptance と manual evidence
- QG1 QA review:
  - timing:
    - RG1 pass 後
  - scope:
    - tracked assertions、manual env acceptance、warning coverage
- SG1 spec review:
  - timing:
    - 実装前
  - scope:
    - tracked/manual split、final acceptance definition

## 実行ルール（全ステップ共通）
- 実行 policy、approval cadence、completion contract は `workflow_issue.md` を正本にする。
- step / block / iteration の書き方は `phase_plan_issue.md` を正本にする。
- plan 本文には、この Issue 固有の順序、依存、検証、review / QA gate だけを書く。

## 実装ステップ

### S01 — tracked generate / diff integration
- observable behavior:
  - `tests/app` が member-aware `.puml` 要点を assertion できる
- design refs:
  - `design.md` の `tracked integration`
- depends on:
  - iss-00024-00027
- unblocks:
  - S02, S03
- target files:
  - `tests/app/test_generate.py`
  - `tests/app/test_diff.py`
- expected tests:
  - generate integration
  - diff integration
- report update:
  - tracked assertion coverage を残す
- notes:
  - full snapshot ではなく body / arrow / warning の要点 assertion を優先する
  - Pydantic quoted forward ref の tracked assertion を必須にする:
    - fixture:
      - `class CheckoutRequest(BaseModel): shipping_address: "AddressDto"; lines: list["CheckoutLineDto"]`
    - expected `.puml` evidence:
      - `CheckoutRequest` class body に `+ shipping_address: AddressDto` と `+ lines: list[CheckoutLineDto]` 相当の field line がある
      - `class "CheckoutRequest" as cNNN` / `class "AddressDto" as cNNN` / `class "CheckoutLineDto" as cNNN` の alias 宣言がある
      - 上記 alias 間に `-->` の association arrow がある
    - negative/warning companion:
      - unresolved quoted ref `GhostPaymentProviderContext` は warning として観測し、relation は追加しない
  - diff path の独立 assertion を必須にする:
    - base state:
      - `pkg/checkout.py` に `class CheckoutSnapshot: request_id: str`
      - commit して `base` tag を作る
    - working tree state:
      - 同 class に `order: "Order"` field と `def submit(self, order: "Order") -> "Receipt"` method を追加する
      - 同 file に `class Order` と `class Receipt` を追加する
    - expected diff `.puml` evidence:
      - `CheckoutSnapshot` の class body に `+ order: Order` と `+ submit(order: Order): Receipt` がある
      - `class "CheckoutSnapshot" as cNNN` / `class "Order" as cNNN` / `class "Receipt" as cNNN` の alias 宣言がある
      - 上記 alias 間に `-->` と `..>` の typed arrow がある
      - `changed_class_count` / `seed_file_count` が stdout summary で観測できる

#### TDD iterations（必要時）
- I1:
  - Red:
    - generate / diff の member-aware assertion を追加する
  - Green:
    - integration expectations を更新する
  - Refactor:
    - test helper を整理する

#### step gate
- review:
  - integration assertion review
- expected tests:
  - `uv run --with pytest pytest tests/app/test_generate.py tests/app/test_diff.py -q`
- report update:
  - tracked acceptance coverage を記録する

### S02 — coverage gaps for warnings and mixed fixture shapes
- observable behavior:
  - unresolved warning、dataclass、Protocol、exception、nested、ambiguous case の acceptance が tracked に入る
- design refs:
  - `design.md` の `acceptance observations`
- depends on:
  - S01
- unblocks:
  - S03
- target files:
  - `tests/app/test_generate.py`
  - `tests/app/test_diff.py`
  - `tests/render/test_document.py`
- expected tests:
  - warning acceptance assertion
  - dataclass field / method assertion
  - Protocol method assertion
  - exception inherits assertion
  - nested class body assertion
  - ambiguous reference warning assertion
  - mixed fixture acceptance assertion
  - Pydantic `BaseModel` quoted-forward-ref assertion
- report update:
  - residual risks を残す

### S03 — manual retail_domain acceptance
- observable behavior:
  - manual env で class body / method signature / field relation / inherits / warnings を確認できる
- design refs:
  - `design.md` の `manual acceptance`
- depends on:
  - S02
- unblocks:
  - final close
- target files:
  - `spec-dock/active/issue/report.md`
- expected tests:
  - manual env pre-clean check:
    - `git -C build/manual-tests/pyclassuml-manual-env status --short --branch`
    - expected: clean except branch header
  - manual `generate` run
  - manual `diff` run
  - manual Pydantic evidence check:
    - `retail_domain/api/schemas.py` の `CheckoutRequest(BaseModel)` が field body に現れること
    - `class "CheckoutRequest" as cNNN` / `class "AddressDto" as cNNN` / `class "CheckoutLineDto" as cNNN` の alias 宣言があること
    - 上記 alias 間に `-->` の association arrow があること
    - `ErrorEnvelope.provider_context: Optional["GhostPaymentProviderContext"]` が unresolved warning として残ること
  - manual dataclass / Protocol / exception / nested / ambiguous evidence check:
    - dataclass `Order` / `OrderLine` の field body と method signature が現れること
    - Protocol `OrderRepository` / `InventoryRepository` / `PaymentGateway` の method body が現れること
    - exception `InventoryOversoldError` / `PaymentMismatchError` が `DomainError` への inherits relation を持つこと
    - nested acceptance は tracked fixture で必須、manual env では存在する場合のみ観測結果を report に記録すること
    - ambiguous は source manual env の既存 file では強制しない。既存 `LegacyWebhookPayload.duplicate: "DuplicateName"` は same-module preference により resolved relation になるため、manual report には「ambiguous source ではない」ことを記録する。
    - manual ambiguous warning は disposable copy 側で `retail_domain/api/ambiguous_probe.py` を追加し、`class AmbiguousProbe(BaseModel): duplicate: "DuplicateName"` を置くことで観測する。
    - disposable copy には `retail_domain/api/ambiguous_probe.py::DuplicateName` を作らず、既存 `api/legacy_contracts.py::DuplicateName` と `domain/legacy_shadow.py::DuplicateName` の 2 候補にする。
    - `typed_relation_ambiguous` warning があり、どちらか一方へ勝手に relation を張らないこと
  - manual diff executable contract:
    - source manual env は変更しない
    - `build/manual-tests/pyclassuml-manual-env/tmp/iss-00028-diff-worktree/` に disposable copy を作る
    - disposable copy 内で `git init` / base commit / working-tree edit を行い、`diff` の working-tree path で member-aware output を観測する
    - deterministic edit scenario:
      - base commit は current `retail_domain` copy 全体
      - working-tree edit は `retail_domain/application/checkout.py` の `CheckoutService` にだけ加える
      - 追加 field: `last_order: Order | None = None`
      - 追加 method: `def preview_total(self, order: Order) -> Decimal: return order.total()`
    - expected diff `.puml` evidence:
      - `CheckoutService` class body に `+ last_order: Order | None` がある
      - `CheckoutService` class body に `+ preview_total(order: Order): Decimal` がある
      - `class "CheckoutService" as cNNN` / `class "Order" as cNNN` の alias 宣言がある
      - 上記 alias 間に `-->` の association arrow がある
      - `Decimal` が selected class として存在する場合のみ、`..>` uses arrow を観測結果に記録する
      - stdout summary に `seed_file_count` と `changed_class_count` がある
    - 実行後は disposable copy を削除してよい
    - source manual env の post-clean check で clean のまま戻ったことを確認する
  - output discipline:
    - `.puml` と command logs は `build/manual-tests/pyclassuml-manual-env/out/iss-00028/` 以下にのみ書く
    - source manual env に対する永続書き込みは `out/iss-00028/` と `tmp/iss-00028-diff-worktree/` の作成/削除だけに限定する
    - source manual env の `.gitignore` は `out/` と `tmp/` を ignore しているため、これらは post-clean check の汚れにならない
    - repo root 側の `git status --short` には manual env の生成物を出さない
- report update:
  - absolute command、観測結果、warning 内容、manual env pre/post cleanliness を記録する

### S90 — docs impact resolution / docs refresh
- 対象:
  - docs
- 対応:
  - report に tracked / manual acceptance をまとめる

### S99 — final diff review quality gate
- branch diff scope:
  - `iss-00028` acceptance coverage
- required validation:
  - `uv run --with pytest pytest tests/app/test_generate.py tests/app/test_diff.py tests/render/test_document.py -q`
  - manual `generate` / `diff` evidence
  - `git -C build/manual-tests/pyclassuml-manual-env status --short --branch` pre/post clean evidence
  - `./spec-dock/scripts/spec-dock sync --github`
  - `./spec-dock/scripts/spec-dock validate`
  - `git diff --check`
  - `rg --files | rg '[A-Z]'`
    - expected:
      - existing allowed paths only, such as root `AGENTS.md` and checked-in `README.md` files
      - no newly created uppercase path in this issue
- reviewer approvals:
  - spec-reviewer pass
  - code-reviewer pass
  - qa-reviewer pass
- report update:
  - final acceptance verdict を残す
  - `spec-dock sync --github` / `spec-dock validate` / targeted tests / manual evidence / review verdict の command と結果を残す

## 未確定事項
- なし:
  - manual env は final gate として固定する

## final exit contract
- AC/EC 達成:
  - tracked integration と manual env acceptance が揃う
- docs impact resolved:
  - report に command / observation / warning evidence が残る
- final diff approved:
  - SG / RG / QG pass
