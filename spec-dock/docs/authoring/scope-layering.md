# スコープ階層リファレンス（Scope Layering Reference）

この文書は、Initiative / Epic / Issue の責務境界、判断半径、authority flow を揃えるための狭い参照です。Lifecycle の開始、review gate、完了条件、実行手順は各 `workflow_*.md` が扱います。この文書はそれらを置き換えません。

## 基本方針

- 判断は、その判断を安全に所有できる最小の durable scope に置く。
- 上位 scope は下位 scope の実装手順を先取りせず、下位 scope は上位 scope の目的や責務境界を再定義しない。
- `artifacts/`、research、interview、delegated draft は evidence であり、canonical authority ではない。
- Canonical authority は、採用判断を経た `requirement.md`、`design.md`、`plan.md`、accepted ADR、または `report.md` の disposition 済み ledger に置く。
- 日本語ファーストで説明する。ただし path、command、code identifier、SpecDock 固有語、外部固有名詞は原文を保持する。

## スコープ別の責務

| スコープ（Scope） | 所有責務（Ownership） | 判断半径（Decision radius） | 正本成果物（Canonical artifact） |
|---|---|---|---|
| イニシアチブ（Initiative） | 複数 Epic にまたがる投資範囲、成功条件、運用方針、全体の責務境界を所有する。 | プロダクト / operating model / cross-epic policy に影響する判断。 | イニシアチブ（Initiative）の `requirement.md` / `design.md` / `plan.md`、必要な accepted ADR。 |
| エピック（Epic） | 複数 Issue を束ねる設計背骨、Issue 分割、依存方向、handoff boundary を所有する。 | 複数 Issue にまたがる architecture / workflow boundary / delivery slice に影響する判断。 | エピック（Epic）の `requirement.md` / `design.md` / `plan.md`、Epic-local report ledger。 |
| イシュー（Issue） | 1つの実装 slice の受け入れ条件、実装計画、観測 evidence、局所的 tradeoff を所有する。 | イシュー（Issue）内に閉じる behavior / docs update / test obligation / reversible implementation choice の判断。 | イシュー（Issue）の `requirement.md` / `design.md` / `plan.md` / `report.md`。 |

## 権限フロー（Authority flow）

1. 調査、interview、delegated draft、pre-start seed は evidence として作成する。
2. Evidence を採用する場合は、対象 scope の canonical artifact または `report.md` の Evidence Adoption Ledger / Decision Ledger に採否を記録する。
3. 採用済みの判断だけを downstream handoff に使う。
4. 下位 scope が上位 scope の未採用 evidence に依存している場合は、実行前に上位 scope へ戻して採用判断を行う。
5. Durable decision として他の scope tree からも発見されるべき判断は ADR に昇格する。

Raw artifact の path は証跡参照として有用ですが、path が存在するだけでは authority になりません。たとえば `artifacts/...draft-design...md` は採用元の候補であり、canonical `design.md` や ledger の採用判断なしに下流の前提にはできません。

## 証跡と正本権限の違い（Evidence / canonical authority）

- Evidence: research note、interview answer、delegated draft、manual inspection、test output、command output。
- Canonical authority: reviewer-pass または disposition 済みの `requirement.md`、`design.md`、`plan.md`、accepted ADR、`report.md` ledger。
- Evidence は事実や候補を運ぶ。Canonical authority は、採用された判断と次の作業者が依存してよい前提を運ぶ。
- Evidence を canonical artifact に反映したあとも、元 artifact は「採用済み証跡」であって正本にはならない。

## 日本語ファースト

Canonical docs、artifacts、ledger の本文、判断理由、説明文は日本語を優先します。正確性、検索性、外部契約を損なう場合は原文を保持します。

- 保持する: `src/spec_dock/assets/...`、`./spec-dock/scripts/spec-dock validate`、`Issue-local draft-design`、`Evidence Adoption Ledger`、API 名、class / function 名、外部サービス名。
- 日本語化する: 背景、目的、受け入れ条件、リスク、判断理由、handoff の説明。
- 避ける: path、command、identifier、固定語まで日本語化して、検索や実行を難しくすること。

## 設計語彙としての DDD / EDA

DDD / EDA は分析や設計の補助語彙として使ってよいが、SpecDock の標準アーキテクチャ、必須プロセス、必須分割単位ではありません。必要な場合だけ、対象 repo の実態と active docs に根拠を置いて使います。

## 禁止事項（Anti-rules）

- Initiative に Issue の実装手順を書かない。
- Epic に canonical Issue `design.md` / `plan.md` の本文を pre-start で作らない。必要な seed は Issue-local artifact として渡す。
- Issue で Initiative / Epic の目的、成功条件、責務境界を再定義しない。
- Workflow docs、phase docs、skills、templates にこの責務表全文を複製しない。必要な場所からこの文書へ薄く link する。
- `artifacts/`、research、interview、delegated draft を accepted authority として扱わない。
- `report.md` だけに将来も依存する durable decision を閉じ込めない。
- DDD / EDA を mandatory wording として書かない。
- 日本語ファーストを、identifier や command の翻訳強制として扱わない。
