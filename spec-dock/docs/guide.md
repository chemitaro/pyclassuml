# 全体ガイド（guide）

spec-dock の docs レイヤ、概念、生成物を最短で把握するための入口です。
scope 固有の手順は `workflow_*.md`、仕様書作成の phase promotion は `workflow_spec_authoring.md`、shared な requirement / design の作法は `phase_*.md`、plan は `phase_plan.md` と `phase_plan_<scope>.md` の二段構成、コマンドや制約は `reference_*.md` を正本とします。
runtime command の現行 contract は `./spec-dock/scripts/spec-dock ...` です。

## 文書の読み分け（docs）

- `workflow_*.md`: Initiative / Epic / Issue / ADR の scope 固有 workflow
- `workflow_spec_authoring.md`: Initiative / Epic / Issue 共通の requirement / design / plan 作成 workflow
- `phase_*.md`: shared phase playbook（共通の作り方）
- `phase_plan_<scope>.md`: scope 固有の plan authoring rule
- `reference_*.md`: GitHub / naming / deps / sync などの参照仕様
- Worktree: [reference_worktree.md](reference_worktree.md)
- `discussions/`: raw capture、ヒアリング、調査、議論、ADR の作業面

phase playbook:
- [phase_requirement.md](phase_requirement.md)
- [phase_design.md](phase_design.md)
- [phase_plan.md](phase_plan.md)
- [phase_plan_initiative.md](phase_plan_initiative.md)
- [phase_plan_epic.md](phase_plan_epic.md)
- [phase_plan_issue.md](phase_plan_issue.md)

入口:
- Spec authoring: [workflow_spec_authoring.md](workflow_spec_authoring.md)
- Initiative: [workflow_initiative.md](workflow_initiative.md)
- Epic: [workflow_epic.md](workflow_epic.md)
- Issue: [workflow_issue.md](workflow_issue.md)
- ADR: [workflow_adr.md](workflow_adr.md)

## 基本概念

- Initiative: 投資単位。なぜやるか、成功条件、スコープを持つ
- Epic: 設計の背骨。契約、移行、観測性、Issue 分割を持つ
- Issue: 実装の最小単位。active issue を起点に behavior-slice based execution contract で完了する
- ADR: 後続へ残る意思決定。initiative / epic / issue の任意 scope に紐づく
- discussion docs: 思考、知識、未確定情報を外部化する補助 artifact。文書そのものを正本へ昇格させず、必要な文脈だけを `adr` / `requirement.md` / `design.md` / `plan.md` へ反映する

親子関係:

```text
Initiative
└── Epic
    └── Issue
```

## 議論文書カタログ（discussion docs catalog）

current catalog は `scratch` / `interview` / `research` / `disc` / `adr` / `draft-requirement` / `draft-design` / `draft-plan` です。

| 種別（type） | ライフサイクル（lifecycle） | 既定 authority（authority default） | 使う場面 |
|---|---|---:|---|
| `scratch` | capture | `raw` | 未整理の発話、観察、思考、会話ログ、下書きを低摩擦に置く |
| `interview` | elicitation | `raw` | 人間から目的、制約、期待、判断基準、未決事項を引き出す |
| `research` | research | `synthesized` | 検証可能な事実、仕様、実装、先例、外部制約を確認する |
| `disc` | framing | `proposed` | 集まった情報から論点、評価軸、選択肢、合意点を整理する |
| `adr` | decision | `accepted` | 長期的な判断、理由、影響、見直し条件を固定する |

通常は doc type から authority を推定します。例外時だけ front matter の `authority` で override し、全 artifact で明示必須にはしません。`derived_from` / `reflected_to` は任意 metadata として、元になった discussion docs と反映先を追うために使えます。

`note` は新規作成 catalog から retired されています。軽量メモと raw capture の境界が曖昧で `scratch` と役割が重複するため、未整理の記録先を `scratch` に一本化します。これは raw capture type の重複を避け、選択時の認知的曖昧さを減らすためです。既存 `note` artifact は grandfathered として壊さず、以後の raw capture は `scratch` に置きます。

reflection rules（反映ルール）:
- `scratch`: 事実確認が必要なら `research`、論点整理が必要なら `disc`、人間判断が必要なら `interview`、長期判断なら `adr` を新規作成する。
- `interview`: 回答は `requirement.md` / `design.md` / `plan.md` / `adr` の反映先を明示する。回答が新しい論点や調査を生む場合は `disc` / `research` へつなぐ。
- `research`: 調査結果が比較を必要とする場合は `disc`、長期判断を支える場合は `adr` へつなぐ。
- `disc`: 合意内容は authoritative docs へ反映する。長期的・横断的・不可逆寄りの判断は新しい `adr` を作成する。
- `adr`: 決定内容を `requirement.md` / `design.md` / `plan.md` へ織り込み、必要な follow-up を残す。

## 生成物と SSOT

- SSOT: `spec-dock/initiatives/**/.meta.json`
- issue dependency metadata の canonical storage は node 直下 `.meta.json` の top-level `depends_on` です
- 依存変更は `./spec-dock/scripts/spec-dock deps add/remove/check` の command-first mutation で行います
- legacy `deps.json` / `meta.json` は current storage や fallback read/write ではありません（no dual-read / manual migration）
- legacy hidden workspace `.spec-dock/` は current `spec-dock/` と非互換です。rename せず `spec-dock init` -> manual migration -> manual delete で扱います
- 主な生成物: `spec-dock/active/**`, `spec-dock/.agent/{active,index,tree}*.json`, `spec-dock/{tree,deps-issues}*.puml`, `spec-dock/dashboard.md`
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
│       ├── discussions/
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
│                       └── discussions/
├── templates/
├── scripts/
├── docs/
├── active/
└── .agent/
```

## 最短 workflow

1. 既存ノードに収まるか確認し、必要なら `new` / `import` する
2. Issue 実行では `issue start <target>` で作業対象を固定し、対象ブランチへ checkout する
3. 仕様書作成は `workflow_spec_authoring.md` を正本にし、対象 scope の `workflow_*.md`、requirement / design の shared playbook、`phase_plan.md` → `phase_plan_<scope>.md` の順で書く
4. Initiative は Epic 分解、Epic は Issue 分割、Issue は agent-native / behavior-slice based execution contract を plan に落とす
5. `validate` / `sync` で整合性と生成物を更新し、Issue lifecycle を閉じる場合は `issue finish` を使う

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
./spec-dock/scripts/spec-dock validate
./spec-dock/scripts/spec-dock sync
```

`active set` / `active set --checkout` は manual / recovery 用の low-level command です。通常の Issue 実行では `issue start` / `issue finish` を入口にします。


## 次に読む

- 実務導線: [README.md](README.md)
- 仕様書作成 workflow: [workflow_spec_authoring.md](workflow_spec_authoring.md)
- 作業対象別 workflow: [workflow_initiative.md](workflow_initiative.md), [workflow_epic.md](workflow_epic.md), [workflow_issue.md](workflow_issue.md)
- 参照仕様: [reference_github.md](reference_github.md), [reference_naming.md](reference_naming.md), [reference_deps.md](reference_deps.md), [reference_sync.md](reference_sync.md)
