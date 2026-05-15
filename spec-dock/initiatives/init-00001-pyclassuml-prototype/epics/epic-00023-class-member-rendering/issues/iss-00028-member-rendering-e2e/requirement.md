---
種別: 要件定義書（Issue）
ID: "iss-00028"
タイトル: "Member Rendering E2E"
関連GitHub: ["#28"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-05-04"
親: ["epic-00023", "init-00001"]
---

# iss-00028 Member Rendering E2E — 要件定義（WHAT / WHY）

## 目的
- epic-00023 の outcome を CLI generate / diff と manual environment で end-to-end に検証し、member-aware output が実利用に耐えることを示す。
- `build/manual-tests/pyclassuml-manual-env/retail_domain` を使い、Pydantic `BaseModel`、dataclass、Protocol、exception、ambiguous / unresolved refs を manual acceptance に含める。
- nested class は tracked integration fixture で必須 acceptance とし、manual env では既存 `retail_domain` に存在する場合だけ追加観測として report に残す。

## 背景・現状
- 現状の挙動:
  - seam-level tests はあるが、class body と typed relation をまとめて CLI / manual fixture で確認する acceptance contract はない。
  - manual environment は存在するが、member rendering 観測点として明文化されていない。
- 現状の課題:
  - 個別 unit が通っても、複雑 fixture で diagram readability が満たされる保証がない。
  - `retail_domain` の Pydantic schema、service / protocol / exception の混在ケースを最終確認していない。
- 再現手順:
  1. `build/manual-tests/pyclassuml-manual-env/retail_domain` 配下を確認する。
  2. current docs に member rendering acceptance がないことを確認する。
- 情報源:
  - `build/manual-tests/pyclassuml-manual-env/retail_domain`
  - `tests/app/test_generate.py`
  - `tests/app/test_diff.py`
  - `tests/render/test_document.py`

## 対象ユーザー / 利用シナリオ（必要時）
- 主な利用者:
  - CLI 利用者、QA reviewer
- 代表シナリオ:
  - `generate` で retail domain を図示し、class body / relation semantics / warnings を確認する。
  - `diff` で member-aware output の差分観測を確認する。

## スコープ
- MUST:
  - tracked integration test で class body / typed relation / warnings を検証する。
  - `build/manual-tests/pyclassuml-manual-env/retail_domain` を使った manual acceptance を実施する。
  - Pydantic `BaseModel`, dataclass, Protocol, exception, ambiguous / unresolved refs を manual acceptance に含める。
  - nested class は tracked integration acceptance に含める。
  - final acceptance では `.puml` に class body、method signatures、field relations、inherits relation、warnings が観測できることを要求する。
- MUST NOT:
  - manual environment を Git 管理下の fixture として書き換えない。
  - tracked tests のために過大な fixture repo を追加しない。
- OUT OF SCOPE:
  - diagram aesthetic tuning
  - benchmark / performance profiling
  - docs 以外の運用フロー改変

## 境界
- Always:
  - tracked tests には最小再現を入れ、manual env は acceptance environment として使い分ける。
  - generate / diff の command surface は既存のまま使う。
- Ask:
  - manual env に permanent fixture file を追加したい場合。
  - acceptance を screenshot まで要求する場合。
- Never:
  - manual env を source of truth として repo に取り込まない。
  - CLI 実行結果を手修正で合わせない。

## 非交渉制約
- non-invasive / AST-only / deterministic を acceptance でも維持する。
- manual env は Git 管理外環境として扱う。

## 前提
- iss-00024 から iss-00027 までが完了している。
- manual environment `build/manual-tests/pyclassuml-manual-env` が利用可能である。

## 受け入れ条件
- AC-001:
  - Actor:
    - CLI 利用者
  - Given:
    - minimal tracked fixture がある。
  - When:
    - `generate` integration test を実行する。
  - Then:
    - class body、typed arrows、warnings を含む `.puml` が assertion できる。
  - 観測点:
    - `tests/app/test_generate.py`
- AC-002:
  - Actor:
    - CLI 利用者
  - Given:
    - diff fixture がある。
  - When:
    - `diff` integration test を実行する。
  - Then:
    - member-aware output が diff path でも観測できる。
  - 観測点:
    - `tests/app/test_diff.py`
- AC-003:
  - Actor:
    - QA reviewer
  - Given:
    - `build/manual-tests/pyclassuml-manual-env/retail_domain` がある。
  - When:
    - manual `generate` / `diff` を実行する。
  - Then:
    - manual `generate` で `domain`, `api`, `application`, `infra` をまたぐ class body / relation / warnings が観測できる。
    - manual `diff` で disposable copy の changed class body、selection-outside / unresolved warning、stdout summary が観測できる。
    - diff path の relation arrow は tracked diff integration test で観測できる。
  - 観測点:
    - manual output `.puml`
- AC-004:
  - Actor:
    - QA reviewer
  - Given:
    - unresolved / ambiguous reference を含む fixture がある。
  - When:
    - integration / manual acceptance を行う。
  - Then:
    - unresolved / ambiguous warning は CLI stdout summary の diagnostics で確認できる。
    - `.puml` は warning source の class body context を補助的に確認する。
    - failure handoff はこの issue では必須にしない。warning-only success を acceptance とする。
  - 観測点:
    - tracked tests、manual output、CLI stderr / stdout summary

## 例外・エッジケース
- EC-001:
  - 条件:
    - manual env は Git 管理外である。
  - 期待:
    - tracked tests には最小再現だけを持ち込み、manual env 依存を強制しない。
  - 観測点:
    - plan / report evidence
- EC-002:
  - 条件:
    - unresolved Pydantic forward ref がある。
  - 期待:
    - warning を観測しつつ diagram 生成は継続する。
  - 観測点:
    - `retail_domain/api/schemas.py`
- EC-003:
  - 条件:
    - Protocol / exception / nested class が混在する。
  - 期待:
    - member body と inherits relation が崩れない。
  - 観測点:
    - manual env + tracked minimal fixture

## 入力→出力例（必要時）
- EX-001:
  - Input:
    - `retail_domain/api/schemas.py`
  - Output:
    - Pydantic field body と unresolved warning を含む `.puml`
- EX-002:
  - Input:
    - `retail_domain/application/checkout.py`
  - Output:
    - method signature と `uses` relation を含む `.puml`

## 用語（ドメイン語彙）
- TERM-001:
  - manual environment:
    - `build/manual-tests/pyclassuml-manual-env` 以下の Git 管理外 acceptance sandbox
- TERM-002:
  - tracked minimal fixture:
    - `tests/*` 内に置く最小再現入力

## 未確定事項
- なし:
  - final acceptance は `retail_domain` を使う方針で固定する。
