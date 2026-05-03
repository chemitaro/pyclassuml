---
種別: adr
ID: "20260416t121500z-adr"
タイトル: "Ratify architecture v5 as initiative seam contract source"
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-04-16"
親: ["init-00001"]
関連:
  - "20260416t113919z-note"
---

# 20260416t121500z-adr Ratify architecture v5 as initiative seam contract source

## 文脈
- repo root `AGENTS.md` では、長期に残す判断は ADR に置き、discussion は論点整理や比較に使う原則を採用している。
- 一方で init-00001 では、`20260416t113919z-note-pyclassuml-architecture-v5.md` が seam-level HOW、module contract、flow detail の実質的な正本になっている。
- このままでは、discussion note を正本として使う例外が暗黙になり、将来レビュー時の supersession rule と監査性が弱くなる。

## 決定
- init-00001 では、`20260416t113919z-note-pyclassuml-architecture-v5.md` を **seam-level detailed design の正本** として ratify する。
- `requirement.md` / `design.md` / `plan.md` / `v5` の役割分担は次で固定する。
  - `requirement.md`: WHAT / scope / constraints / acceptance
  - `design.md`: 採用アーキテクチャと whole-system guardrail
  - `plan.md`: 実装順序と epic / milestone 分解
  - `v5`: seam-level HOW、module / contract / flow 詳細
- supersession rule は次で固定する。
  - scope / constraints / acceptance の差分は `requirement.md` を優先する
  - whole-system guardrail の差分は `design.md` を優先する
  - epic grouping / milestone gate / readiness / issue baseline の差分は `plan.md` を優先する
  - seam-level HOW の差分は `v5` を優先する
- epic grouping / milestone gate / readiness 判定は `plan.md` が優先し、`v5` はそれを上書きしない。
- 今回の initiative に限って、discussion note である `v5` を詳細設計の正本として扱うことを ADR で明示し、governance 上の例外を意図的なものとして残す。

## 結果
- spec-review 時に、なぜ `v5` が authoritative なのかを ADR で説明できる。
- 後続の epic / issue authors は、詳細契約の参照先を一意に判断できる。
- 将来 `v5` を置き換える場合は、新しい discussion note か設計文書を作った上で、この ADR か後継 ADR を更新する。

## 非採用案
- `v5` の内容をすべて `design.md` へ移す
  - 却下理由:
    - initiative design の guardrail 要約と detailed seam contract が混ざり、SpecDock での段階分解に不向き
- root `AGENTS.md` を変更して discussion を常に正本として許可する
  - 却下理由:
    - repo 全体の運用原則を broad に変える必要はなく、initiative ローカルの例外として閉じた方が安全
