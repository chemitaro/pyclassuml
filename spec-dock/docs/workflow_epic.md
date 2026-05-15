# workflow: epic

Epic は設計の背骨です。
この workflow は、Epic 固有の再利用判定、作成、Issue 分割、品質ゲートを正本として扱います。
この workflow の品質ゲートは scope 固有の additive gate であり、`phase_*.md` の shared minimum gate 通過を前提とします。

対応 leaf skill:
- `.agents/skills/spec-dock-epic-planning/SKILL.md`

関連:
- 総合: [guide.md](guide.md)
- 仕様書作成: [workflow_spec_authoring.md](workflow_spec_authoring.md)
- Initiative: [workflow_initiative.md](workflow_initiative.md)
- Issue: [workflow_issue.md](workflow_issue.md)
- GitHub 連携: [reference_github.md](reference_github.md)
- 共通 phase playbook: [phase_requirement.md](phase_requirement.md), [phase_design.md](phase_design.md), [phase_plan.md](phase_plan.md)
- Epic plan playbook: [phase_plan_epic.md](phase_plan_epic.md)

## 再利用判定

- まず親 initiative 配下の既存 epic の `requirement.md` / `design.md` / `plan.md` / `discussions/` を確認する
- 契約、移行、観測性、Done 定義が既存 epic に収まるなら、新規作成せず既存 epic を更新する
- 設計の背骨や rollout 順が崩れる場合だけ `new` / `import` を使う
- 新規作成した理由や既存 epic に収めない理由は、作成後の対象 epic 配下の最初の `disc` に残す

## 作成

```bash
./spec-dock/scripts/spec-dock new epic --initiative <initiative-id> --title "..."
./spec-dock/scripts/spec-dock new epic --initiative <initiative-id> --github-issue <n> --title "..."
./spec-dock/scripts/spec-dock new epic --initiative <initiative-id> --create-github-issue --title "..."

./spec-dock/scripts/spec-dock import epic <num|#num|url> --title "..." [--initiative <initiative-id>]
```

- `import epic` で `--initiative` を省略した場合は current active から親 initiative を解決する
- naming 制約と GitHub 振る舞いは [reference_naming.md](reference_naming.md), [reference_github.md](reference_github.md) を参照する
- Epic 配下の Issue 作成は runtime command `./spec-dock/scripts/spec-dock new issue --epic <epic-id> --title "..."` を使う。生成される `issues/rules.md` は `spec-dock/docs/rules/epic/issues.md` への入口で、作成ルールの正本は後者にある。GitHub linkage は [reference_github.md](reference_github.md) を参照する
- Issue 間依存の追加/削除/確認は `./spec-dock/scripts/spec-dock deps add/remove/check` を使い、反映は `./spec-dock/scripts/spec-dock validate` と `./spec-dock/scripts/spec-dock sync` で確認する

## 記述

- `requirement.md`: 期待する価値、受け入れ条件、非機能、スコープ
- `design.md`: 契約、移行、観測性、リスク
- `plan.md`: Issue 分割、依存順、品質ゲート。shared axiom は `phase_plan.md`、Epic 固有の書き方は `phase_plan_epic.md`
- Requirement / design / plan の phase promotion は `workflow_spec_authoring.md` を正本にし、各 artifact ごとに fresh `spec-reviewer` の `review_status: pass` まで次 phase へ進めない
- `discussions/`: `new doc {adr|disc|research|note} --epic <epic-id> --title "..."` で、この epic の `discussions/` 配下に timestamp-prefixed original を作成する。標準形は `<ts>-<kind>-<slug>.md`、same-second collision は `<ts>-<nn>-<kind>-<slug>.md`。詳細 contract は [reference_naming.md](reference_naming.md) を参照する
- shared な書き方は `phase_*.md`、lifecycle / governance と Epic 固有の分割判断はこの workflow を正本とする

## 品質ゲート

- requirement:
  - Done 条件が観測可能
  - スコープと非スコープが明確
  - 新規 epic が必要な理由を最初の `disc` で追える
- design:
  - 契約が明記されている
  - 移行 / 互換 / ロールバックが整理されている
  - 観測性の方針がある
- plan:
  - Issue へ分割できている
  - 依存順が現実的
- authoring:
  - requirement / design / plan の各 promotion gate が `Spec Authoring Gate` として `report.md` に記録されている
  - scope / acceptance criteria / Issue 分割に影響する未確認事項が残っていない
  - plan gate pass 後に Issue 分割へ進む

## 仕上げ

```bash
./spec-dock/scripts/spec-dock validate
./spec-dock/scripts/spec-dock sync
```
