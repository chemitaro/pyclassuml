---
種別: research
ID: "20260526t070111z-research"
タイトル: "Self Dependency Suppression Analysis"
状態: "completed"
作成者: "iwasawayuuta"
最終更新: "2026-05-26"
親: ["iss-00042"]
関連: ["iss-00040"]
authority: "synthesized"
derived_from: ["user-analysis-session", "deep-consultant-analysis"]
reflected_to: ["../requirement.md"]
---

# 20260526t070111z-research Self Dependency Suppression Analysis

## 調査目的

`iss-00040` で導入した direct dependency rendering の実プロダクト適用後に観測された self dependency ノイズについて、技術的対策の有無、望ましい対策範囲、複雑性を整理する。

## 調査方法

- 実プロダクト `taikyohiyou_project-issue-1716` の `class-diagram-diff-from-issue-start.puml` を確認した。
- `DispatchOrigin ..> DispatchOrigin` が出力されていることを確認した。
- 対象コードでは `DispatchOrigin.from_header(...) -> DispatchOrigin` のような自己型参照があり、同一 class への dependency 候補になりうることを確認した。
- deep-consultant 2 名に、UML 意味論と pyclassuml 実装複雑性の観点で分析を依頼した。

## 調査結果

- method body 内の一時的なクラス利用を `dependency` / PlantUML `..>` として描画する方針は、一般的な UML class diagram として妥当である。
- `A ..> A` の self dependency は UML として絶対に不可能ではないが、実務上の class diagram では新しい設計情報をほぼ与えず、読者にとってノイズになりやすい。
- self dependency の原因を parse 層で個別に分類して潰すより、最終的な relation 正規化層で `source == target` の `dependency` を除外する方がシンプルで壊れにくい。
- type-only dependency と runtime direct dependency の区別は技術的に可能だが、Python の `TYPE_CHECKING`、forward reference、string annotation、generic、cast、isinstance、factory call などを正確に分類し始めると解析仕様が重くなる。
- 現時点では type-only / runtime の分離を実装せず、必要性が実例で強まった時点で label / stereotype による軽い表示を検討するのが妥当である。

## 対策案比較

| 案 | 想定層 | 複雑度 | 壊れやすさ | 既存挙動への影響 | 評価 |
|---|---|---:|---:|---|---|
| self dependency を relation 正規化で除外 | analyze / selection | 低 | 低 | `A ..> A` だけ消える | 推奨 |
| self dependency を render 直前で除外 | render | 低 | 低 | 表示だけ消えるが analysis observations とずれる可能性 | 次点 |
| classmethod return など原因別に parse で抑制 | parse | 中 | 中-高 | 原因ごとの仕様が増える | 非推奨 |
| CLI option `--include-self-dependencies` を追加 | cli / config / analyze | 中 | 中 | UI と仕様が増える | 今は不要 |
| type-only / runtime を label で区別 | model / analyze / render | 中 | 中 | 出力表現とテストが広がる | 将来検討 |
| dependency 種別を細分化 | parse / model / analyze / render | 高 | 高 | 表現と解釈が複雑化 | 避ける |

## 判断への含意

- `iss-00042` の MVP は self dependency suppression のみに絞る。
- 実装候補は `src/pyclassuml/analyze/selection.py` の relation 正規化付近。
- 受け入れ条件は、self dependency が消え、異なる class 間の `dependency` が維持されることを中心にする。
- type-only / runtime dependency の分離はこの issue の対象外にする。

## 推測 / 未検証事項

- 推測:
  - `DispatchOrigin ..> DispatchOrigin` は classmethod return annotation または self type reference 由来である可能性が高い。
- 未検証:
  - pyclassuml の現行 test fixture に self dependency regression が既にあるかは未確認。
  - `generate` / `diff` の最小 app-level fixture は実装計画時に確定する。

## リスク / 制約

- self dependency を常に抑制すると、自己 factory や self-recursive design を dependency として見たい利用者には情報が減る。
- ただし pyclassuml の現目的では、class diagram の可読性を優先し self dependency を抑制する方が有益と判断する。
