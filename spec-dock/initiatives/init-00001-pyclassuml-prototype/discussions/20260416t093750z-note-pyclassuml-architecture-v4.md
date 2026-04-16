---
種別: note
ID: "20260416t093750z-note"
タイトル: "PyClassUML Architecture V4"
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-16"
親: ["init-00001"]
関連: []
---

# 20260416t093750z-note PyClassUML Architecture V4

## 目的
- `v3` を consultant レビューで磨き、実装分解に直接つながる設計案へ引き上げる。
- 特に `model` と `report` の責務膨張を防ぐため、diagnostics、strict escalation、issue slicing の契約を追加する。
- この版を、epic / issue 設計へ進む直前の最有力な discussion ベース設計として扱う。

## consultant review の要点
- 境界の方向性は正しい。増やすべきものは package ではなく contract である。
- 最大の設計リスクは `model` と `report` の dumping ground 化である。
- SpecDock 的には、filesystem tree よりも `seam-to-issue dependency map` を先に置いた方が patchwork 化を防げる。
- `generate` / `diff` の差は今のまま `targets` と `vcs` に閉じ込めるべきで、後段へ漏らしてはいけない。

## canonical dto contract
| dto | producer | consumer | minimum invariant |
| --- | --- | --- | --- |
| `CommandRequest` | `cli` | `config`, `app` | command type と raw option 値を保持する |
| `ExecutionContext` | `config` | 全 stage | 4 root が canonical path であり、包含関係が検証済みである |
| `AnalysisConfig` | `config` | `targets`, `analyze`, `render`, `report` | CLI override と config merge が済んでいる |
| `TargetSet` | `targets` | `parse`, `analyze` | seed が一意化され、`generate` / `diff` 差分はここまでで吸収済み |
| `ParsedModule` | `parse` | `analyze`, `frameworks` | import 実行なしの AST 由来情報のみを持つ |
| `DependencyGraph` | `analyze` | `frameworks`, `render`, `report` | scope/depth/package 境界を満たす |
| `DiagramModel` | `render` の手前 | `render`, `report` | deterministic な順序で要素が並ぶ |
| `CommandResult` | `report` | `cli` | summary、diagnostics、artifact 情報、exit policy を持つ |

## diagnostics ownership / strict escalation table
| topic | owner | normal mode | strict mode |
| --- | --- | --- | --- |
| import 解決失敗 | `parse` / `analyze` | warning として収集 | failure 候補 |
| re-export 解決失敗 | `analyze` | warning | failure 候補 |
| forward reference 解決失敗 | `analyze` / `frameworks` | warning | failure 候補 |
| wildcard import 解決不能 | `analyze` | warning | failure 候補 |
| SQLAlchemy / Pydantic 補強失敗 | `frameworks` | warning | failure 候補 |
| scope 外起点 | `targets` | `generate` は error, `diff` は除外 + warning | failure |
| 出力失敗 | `report` | error | error |
| 探索上限到達 | `analyze` | error | error |

- 実装原則:
  - diagnostics の収集は各 stage で行ってよい。
  - ただし strict 昇格判定は `report` に一元化し、各 stage に `if strict` を散らさない。
  - `cli` は diagnostics を表示するが、意味論の判定はしない。

## deterministic ordering contract
| artifact | ordering owner | rule |
| --- | --- | --- |
| target file list | `targets` | canonical path で昇順 |
| parsed module list | `parse` | `TargetSet` 順を保持しつつ canonical path で安定化 |
| class list | `analyze` | module id -> class name |
| relation list | `analyze` / `render` | source class -> relation kind -> target class |
| final PlantUML output | `render` | package/group/class/relation を固定順で出力 |

## seam-to-issue dependency map
| seam | upstream dependency | observable behavior | verification focus |
| --- | --- | --- | --- |
| `model.execution-contracts` | none | core dto が定義される | type / invariant review |
| `config.context-resolve` | `model.execution-contracts` | 4 root と config merge が一元化される | path semantics |
| `targets.explicit-target-normalize` | `config.context-resolve` | file/glob/dir が TargetSet 化される | dedupe / scope fail |
| `vcs.diff-file-collect` | `model.execution-contracts` | base ref との差分ファイルが取得できる | git read-only |
| `targets.diff-target-normalize` | `config.context-resolve`, `vcs.diff-file-collect` | diff seed が TargetSet 化される | scope pre-filter / zero-target fail |
| `parse.module-parse-and-index` | `targets.*` | AST 由来の parsed module 群が作られる | import 実行禁止 |
| `analyze.traversal` | `parse.module-parse-and-index` | 到達 graph が構築される | depth / package / scope |
| `analyze.relationship-extract` | `analyze.traversal` | UML 関係候補が抽出される | relation correctness |
| `frameworks.sqlalchemy-enrich` | `analyze.relationship-extract` | SQLAlchemy 補強が追加される | best-effort isolation |
| `frameworks.pydantic-enrich` | `analyze.relationship-extract` | Pydantic 補強が追加される | best-effort isolation |
| `render.uml-document` | `analyze.*`, `frameworks.*` | deterministic な PlantUML text が得られる | output stability |
| `report.artifact-summary-exit-policy` | `render.uml-document` | `.puml`、summary、exit policy が得られる | write + strict/warn |
| `app.generate-wiring` | foundation + core seams | generate end-to-end が動く | e2e generate |
| `app.diff-wiring` | foundation + core seams + `vcs` | diff end-to-end が動く | e2e diff |

## issue slicing guidance
- 1 issue = 1 seam を原則にする。
- 1 issue は 1 つの observable behavior を持つ。
- cross-layer change は `app.generate-wiring` / `app.diff-wiring` か、明示的な contract stitching のときだけ許可する。
- `model` と `report` は便利だからといって横断的に機能を吸い込ませない。

## いま固定してよいこと
- top-level boundary 11 個
- layer を dependency rule として扱うこと
- `generate` / `diff` 差分は `targets` + `vcs` まで
- side-effect ownership
- stage contract と deterministic ordering の責任箇所

## いま固定しない方がよいこと
- `model` の physical split
- 各 package 配下の file split
- framework registry の一般化
- renderer 複数化
- cache / parallelism
- diagnostics code の完全一覧

## 現時点の結論
- `v4` 時点の推奨案は、`pipeline-oriented modular monolith` を保ちつつ、issue 分解に必要な contract を揃えた設計である。
- ここまで来ると、次に必要なのは大きな設計変更ではなく、epic / issue へ安全に切り出すための planning である。
- 以後の `v5` 以降は、実際に epic / issue 分解を始めたあと、必要なときだけ局所契約を追加するのがよい。

## 参考
- [architecture v1](</Users/iwasawayuuta/workspace/tools/pyclassuml/spec-dock/initiatives/init-00001-pyclassuml-prototype/discussions/20260416t093206z-note-pyclassuml-architecture-v1.md>)
- [architecture v2](</Users/iwasawayuuta/workspace/tools/pyclassuml/spec-dock/initiatives/init-00001-pyclassuml-prototype/discussions/20260416t093206z-02-note-pyclassuml-architecture-v2.md>)
- [architecture v3](</Users/iwasawayuuta/workspace/tools/pyclassuml/spec-dock/initiatives/init-00001-pyclassuml-prototype/discussions/20260416t093206z-01-note-pyclassuml-architecture-v3.md>)
- [requirements baseline v2](</Users/iwasawayuuta/workspace/tools/pyclassuml/spec-dock/initiatives/init-00001-pyclassuml-prototype/discussions/20260416t080346z-research-pyclassuml-requirements-baseline-v2.md>)
- [architecture proposal seed](</Users/iwasawayuuta/workspace/tools/pyclassuml/spec-dock/initiatives/init-00001-pyclassuml-prototype/discussions/20260416t084338z-disc-pyclassuml-architecture-proposal.md>)
