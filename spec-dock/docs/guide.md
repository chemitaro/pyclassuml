# 全体ガイド（guide）

spec-dock の docs レイヤ、概念、生成物を最短で把握するための入口です。
Agent の operational entrypoint / first-read spine は skill が所有します。docs は skill から到達する detail / reference surface として、field semantics、policy detail、hard cases、生成物の読み方を説明します。
scope 固有の詳細手順は `workflow_*.md`、曖昧さの明確化の bridge/reference は `workflow_clarification.md`、仕様書作成の phase promotion semantics は `workflow_spec_authoring.md`、shared な requirement / design の作法は `phase_*.md`、plan は `phase_plan.md` と `phase_plan_<scope>.md` の二段構成、コマンドや制約は `reference_*.md` を参照します。
runtime command の現行 contract は `./spec-dock/scripts/spec-dock ...` です。

## 文書の読み分け（docs）

- `workflow_*.md`: Initiative / Epic / Issue / ADR の scope 固有 workflow
- `workflow_clarification.md`: source-grounded な一問一答、質問 artifact、docs synthesis、ADR triage の workflow
- `workflow_spec_authoring.md`: Initiative / Epic / Issue 共通の requirement / design / plan 作成 workflow
- `phase_*.md`: shared phase playbook（共通の作り方）
- `phase_plan_<scope>.md`: scope 固有の plan authoring rule
- `reference_*.md`: GitHub / naming / deps / sync などの参照仕様
- Worktree: [reference_worktree.md](reference_worktree.md)
- `artifacts/`: raw capture、ヒアリング、調査、議論、ADR の作業面

phase playbook:
- [phase_requirement.md](phase_requirement.md)
- [phase_design.md](phase_design.md)
- [phase_plan.md](phase_plan.md)
- [phase_plan_initiative.md](phase_plan_initiative.md)
- [phase_plan_epic.md](phase_plan_epic.md)
- [phase_plan_issue.md](phase_plan_issue.md)

detail / reference 入口:
- Clarification bridge/reference: [workflow_clarification.md](workflow_clarification.md)
- Spec authoring semantics: [workflow_spec_authoring.md](workflow_spec_authoring.md)
- Initiative detail: [workflow_initiative.md](workflow_initiative.md)
- Epic detail: [workflow_epic.md](workflow_epic.md)
- Issue detail: [workflow_issue.md](workflow_issue.md)
- ADR detail: [workflow_adr.md](workflow_adr.md)
- ChatGPT authoring evidence lane: [workflow_chatgpt_authoring_pack.md](workflow_chatgpt_authoring_pack.md), [reference_authoring_pack_backend.md](reference_authoring_pack_backend.md), [authoring/chatgpt-pack.md](authoring/chatgpt-pack.md)

## 基本概念

- Initiative: 投資単位。なぜやるか、成功条件、スコープを持つ
- Epic: 設計の背骨。契約、移行、観測性、Issue 分割を持つ
- Issue: 実装の最小単位。active issue を起点に behavior-slice based execution contract で完了する
- ADR: 後続へ残る意思決定。initiative / epic / issue の任意 scope に紐づく
- artifact docs: 思考、知識、未確定情報を外部化する補助 artifact。文書そのものを正本へ昇格させず、必要な文脈だけを `adr` / `requirement.md` / `design.md` / `plan.md` へ反映する
- Workbench（experimental）: `spec-dock/.workbench/` または Initiative / Epic / Issue 直下の `.workbench/`。Workbench は任意です。optional、temporary、worktree-local、disposable、non-canonical な一時作業場であり、canonical docs、durable evidence、node metadata の置き場ではない

Workbench は exact path component `.workbench` を reserved boundary とし、default semantic discovery はその内部を探索・解釈しません。fresh root と future Initiative / Epic / Issue の shell に `.workbench/README.md` が生成されますが、existing scope には no-backfill です。Workbench は任意であり、不在でも workspace は valid です。`.workbench/README.md` は direct child の README-only tracking surface で、その他の Workbench entry は ignored payload として Git に ignore されます。Git ignore は security boundary ではありません。内容の保存、昇格、バックアップは自動化されず、scope や worktree の削除時には一緒に失われてよい前提です。永続化が必要な記録は `artifacts/` または canonical docs へ明示的に反映してください。`.workbench-notes` や `my.workbench` のような near-name は reserved boundary ではありません。

Root `spec-dock/.workbench/` は `yyyymmdd` などの粗い日付bucketへ置き、必要なfileだけを人間またはモデルが手動選択します。Root Workbench全体を移すcommandはありません。Initiative / Epic / Issue直下のWorkbenchは、`workbench copy --scope <full-id> --to <linked-worktree>`で同一repositoryのlinked worktreeに明示的かつ一度だけcopyできます。Copyはsource-winsでdestination-only entryを保持し、自動sync、copy-back、継続同期を行いません。Directoryをそのままcopyし、言語、拡張子、MIME、内容による対象fileの分類は行いません。

完成したChatGPTの単一Markdownは、`artifact import chatgpt-output --{initiative|epic|issue} <id> --file <workbench-file.md> --title "..."`でsourceを残したままbyte-identicalなblank Artifactへ保存できます。`chatgpt-output`はimport kindでありtyped Artifact tokenではないため、同名typeの予約はせず`new artifact`と共存します。read / import authorization は evidence-only であり、canonical adoption ではありません。Evidence Adoption Ledgerへ採否を記録し、採用した規範的内容だけをcanonical docsへ再記述してfresh reviewer gateを通してください。`update`は既存Workbenchを保持し、migration、normalize、delete、promotionしません。

`artifact import file --file <path>` は別の generic lane です。`--root`、`--initiative <id>`、`--epic <id>`、`--issue <id>` のいずれか一つを明示し、Workbench 内外を問わず一件の regular file を opaque generic Artifact として保存します。source は変更・削除しません。結果には source content、hash、byte count、repository 外 absolute path を出さず、repository 内 source は repo-relative、その他は basename のみを表示します。保存済みは `committed=true` で、通常は `publication_state=committed`、commit 後 warning が残る場合は `committed_with_warning` です。両方とも `retry_disposition=not_needed` であり、commit 前 failure は `not_committed` と `safe_after_remediation` です。generic Artifact は `canonical=false` の evidence-only content で、body は default lifecycle の authority / canonical input になりません。採用には Evidence Adoption Ledger と canonical docs または accepted ADR への明示反映、必要な fresh reviewer gate が必要です。generic filename と collision は [reference_naming.md](reference_naming.md) を参照してください。

explicit generic import の publication は platform safety boundary を持ちます。Linux では anonymous `O_TMPFILE` staging を使い、capability を確立できない場合は formal destination を作らず fail closed し、named-temp success fallback はありません。macOS では destination-side named stage を作り、検証済み staged descriptor から `fclonefileat` で no-replace publication を行います。commit 後 cleanup は identity/type を確認してからだけ行い、不確実性があれば unsafe unlink や retry guidance ではなく retain と warning になります。same-UID actor が final check と unlink の間に置換する事象は accepted exclusion のままであり、解消済みとは扱いません。

ordinary `uv run pytest` は default full-regression skip を適用する fast lane です。full-regression body は別の explicit lane であり、`uv run pytest --run-full-regression` を実行します。

親子関係:

```text
Initiative
└── Epic
    └── Issue
```

## 成果物文書カタログ（artifact docs catalog）

current catalog は `blank` / `adr` / `disc` / `research` / `interview` / `decision-candidate` / `pr-repair-batch` / issue-only `draft-requirement` / `draft-design` / `draft-plan` です。

| 種別（type） | ライフサイクル（lifecycle） | 既定 authority（authority default） | 使う場面 |
|---|---|---:|---|
| `blank` | 記録（capture） | `raw` | 型を先に決めない working evidence、未整理の発話、観察、思考、会話ログ、下書きを低摩擦に置く |
| `interview` | 聞き取り（elicitation） | `raw` | 人間から目的、制約、期待、判断基準、未決事項を引き出す |
| `research` | 調査（research） | `synthesized` | 検証可能な事実、仕様、実装、先例、外部制約を確認する |
| `disc` | 論点整理（framing） | `proposed` | 集まった情報から論点、評価軸、選択肢、合意点を整理する |
| `decision-candidate` | 判断候補（decision candidate） | `proposed` | 採用前の判断候補を canonical docs / ADR / report ledger へ反映できる形で整理する |
| `adr` | 判断（decision） | `accepted` | 長期的な判断、理由、影響、見直し条件を固定する |
| `pr-repair-batch` | 実行証跡（execution evidence） | `proposed` | レビュー修復 workflow の observation、concern inventory、repair queue、merge-prepared gate を記録する |

通常は doc type から authority を推定します。例外時だけ front matter の `authority` で override し、全 artifact で明示必須にはしません。`derived_from` / `reflected_to` は任意 metadata として、元になった discussion docs と反映先を追うために使えます。

`scratch` / `note` は新規作成 catalog から retired されています。軽量メモと raw capture の境界が曖昧で役割が重複するため、型を先に決めない記録先を `blank` に一本化します。既存 `scratch` / `note` artifact は grandfathered として壊さず、以後の raw capture は `blank` に置きます。

reflection rules（反映ルール）:
- `blank`: 事実確認が必要なら `research`、論点整理が必要なら `disc`、人間判断が必要なら `interview`、長期判断なら `adr` を新規作成する。
- `interview`: 回答は `requirement.md` / `design.md` / `plan.md` / `adr` の反映先を明示する。回答が新しい論点や調査を生む場合は `disc` / `research` へつなぐ。
- `research`: 調査結果が比較を必要とする場合は `disc`、長期判断を支える場合は `adr` へつなぐ。
- `disc`: 合意内容は authoritative docs へ反映する。長期的・横断的・不可逆寄りの判断は新しい `adr` を作成する。
- `decision-candidate`: 採用可否、根拠、反映先を整理し、accepted ADR または canonical docs / `report.md` Evidence Adoption Ledger へ昇格する。
- `adr`: 決定内容を `requirement.md` / `design.md` / `plan.md` へ織り込み、必要な follow-up を残す。

## 生成物と SSOT

- SSOT: `spec-dock/initiatives/**/.meta.json`
- issue dependency metadata の canonical storage は node 直下 `.meta.json` の top-level `depends_on` です
- 依存変更は `./spec-dock/scripts/spec-dock deps add/remove/check` の command-first mutation で行います
- legacy `deps.json` / `meta.json` は current storage や fallback read/write ではありません（no dual-read / manual migration）
- legacy hidden workspace `.spec-dock/` は current `spec-dock/` と非互換です。rename せず `spec-dock init` -> manual migration -> manual delete で扱います
- 主な生成物: `spec-dock/active/**`, `spec-dock/.agent/{active,index,tree}*.json`, `spec-dock/{tree,deps-issues,deps-raw}*.puml`, `spec-dock/dashboard.md`
- `spec-dock/adrs/` は generated ADR mirror です（`sync` で rebuild / gitignore 対象）
- GitHub は入口として連携できるが、仕様ツリーの正はローカル metadata

代表構造:

```text
spec-dock/
├── initiatives/
│   └── init-.../
│       ├── requirement.md
│       ├── design.md
│       ├── plan.md
│       ├── report.md
│       ├── artifacts/
│       └── epics/
│           └── epic-.../
│               ├── requirement.md
│               ├── design.md
│               ├── plan.md
│               └── issues/
│                   └── issue-.../
│                       ├── requirement.md
│                       ├── design.md
│                       ├── plan.md
│                       ├── report.md
│                       └── artifacts/
├── templates/
├── scripts/
├── docs/
├── active/
└── .agent/
```

## 最短 workflow

1. 既存ノードに収まるか確認し、必要なら `new` / `import` する
2. Issue 実行では `issue start <target>` で作業対象を固定し、対象ブランチへ checkout する
3. 仕様書作成は対応 planning skill を operational entrypoint にし、`workflow_spec_authoring.md` の phase promotion detail を参照する。未解決の曖昧さは `spec-dock-clarification` skill と `workflow_clarification.md` の bridge/reference で一問ずつ解消してから、対象 scope の `workflow_*.md`、requirement / design の shared playbook、`phase_plan.md` → `phase_plan_<scope>.md` の順で書く
4. ChatGPT / Oracle を使う場合は evidence lane として扱い、ZIP/tree/staged evidence や validation `pass` を canonical adoption、reviewer pass、execution-ready、PR-ready と混同しない
5. Initiative は Epic 分解、Epic は Issue 分割、Issue は agent-native / behavior-slice based execution contract を plan に落とす
6. reviewed Epic plan が final delivery Issue を明示している場合だけ、中間 Issue は relay-style に実装し、最後の delivery Issue で Epic 品質ゲートと mergeable PR をまとめる。それ以外は通常の PR Delivery / Merge Preparation Gate に従う
7. `validate` / `sync` で整合性と生成物を更新し、Issue lifecycle を閉じる場合は `issue finish` を使う

## 代表コマンド（runtime script）

```bash
./spec-dock/scripts/spec-dock issue start <github-issue-number>
./spec-dock/scripts/spec-dock issue start --id <issue-id>
./spec-dock/scripts/spec-dock issue finish
./spec-dock/scripts/spec-dock active set <id|#num|url>
./spec-dock/scripts/spec-dock deps check <target>
./spec-dock/scripts/spec-dock deps add --from <issue-id> --to <issue-id>
./spec-dock/scripts/spec-dock deps remove --from <issue-id> --to <issue-id>
./spec-dock/scripts/spec-dock worktree create [label]
./spec-dock/scripts/spec-dock worktree list --json
./spec-dock/scripts/spec-dock worktree show <target> --json
./spec-dock/scripts/spec-dock worktree remove <target> [--force] [--json]
./spec-dock/scripts/spec-dock artifact import file --root --file <path>
./spec-dock/scripts/spec-dock artifact import file --issue <issue-id> --file <path> [--json]
./spec-dock/scripts/spec-dock validate
./spec-dock/scripts/spec-dock sync
```

`active set` / `active set --checkout` は manual / recovery 用の low-level command です。通常の Issue 実行では `issue start` / `issue finish` を入口にします。


## 次に読む

- 実務導線: [README.md](README.md)
- 仕様書作成 workflow: [workflow_spec_authoring.md](workflow_spec_authoring.md)
- 明確化 workflow: [workflow_clarification.md](workflow_clarification.md)
- 作業対象別 workflow: [workflow_initiative.md](workflow_initiative.md), [workflow_epic.md](workflow_epic.md), [workflow_issue.md](workflow_issue.md)
- 参照仕様: [reference_github.md](reference_github.md), [reference_naming.md](reference_naming.md), [reference_deps.md](reference_deps.md), [reference_sync.md](reference_sync.md)
- ChatGPT authoring pack: [workflow_chatgpt_authoring_pack.md](workflow_chatgpt_authoring_pack.md)
