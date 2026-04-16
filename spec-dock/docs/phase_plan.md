# phase playbook: plan

Initiative / Epic / Issue に共通する plan の shared axiom です。
scope 固有の plan authoring rule は `phase_plan_<scope>.md` を参照してください。
workflow は `workflow_initiative.md` / `workflow_epic.md` が lifecycle / governance、`workflow_issue.md` が lifecycle / governance / execution policy の正本です。

関連:
- 全体像: [guide.md](guide.md)
- Scope workflow: [workflow_initiative.md](workflow_initiative.md), [workflow_epic.md](workflow_epic.md), [workflow_issue.md](workflow_issue.md)
- Scope plan playbook: [phase_plan_initiative.md](phase_plan_initiative.md), [phase_plan_epic.md](phase_plan_epic.md), [phase_plan_issue.md](phase_plan_issue.md)

## phase contract

- 位置: `調査分析 → requirement → design → plan → 実装/品質ゲート` の `plan`
- 責務: 確定した requirement / design を、実行可能な分解・順序・停止点・品質ゲートへ変換する
- 前提入力: reviewer 承認レベルの `requirement.md` / `design.md`、依存、ブロッカー、対象 scope の workflow / phase plan
- 固定すること:
  - target
  - decomposition
  - sequence
  - gate
  - dependency
  - exit
- 出力: reviewer が handoff できる `plan.md` と必要な `disc` / `research` / `adr`
- 非ゴール: requirement / design の再議論、設計不足の隠蔽、将来作業の過剰先読み

## shared terminology

- `shared minimum gate`: 全 scope に共通して満たす最小 gate
- `scope-specific readiness contract`: 次の実行単位へ handoff するために対象 scope が追加で満たす条件
- `final exit contract`: この plan が閉じたと判断する最終条件

## shared entry checklist

- `requirement.md` と `design.md` が reviewer 承認レベルにある
- この plan が扱う単位を明確にした
- 依存、ブロッカー、外部制約を露出した
- 分割案や順序案の比較が必要なら `disc` に逃がすと決めた
- 対象 scope の `phase_plan_<scope>.md` と `workflow_<scope>.md` を確認した

## shared review / handoff gate

- 順序の理由が説明できる
- 粒度が対象 scope に対して妥当である
- 依存とブロッカーが plan に露出している
- gate と exit が plan に反映されている
- `plan.md` と必要な `disc` / `research` / `adr` を束で渡せる
- reviewer が「この計画で次へ進める」と判断できる

## escape hatch

- 分割案 / 順序案 / gate 案の比較は `disc`
- 外部制約や運用条件は `research`
- 恒久化すべき運用方針は `adr`
