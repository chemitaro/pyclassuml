# イニシアチブワークフロー（workflow: initiative）

Initiative は投資単位です。
この workflow は、Initiative 固有の再利用判定、作成、Epic 分解、品質ゲートを正本として扱います。
この workflow の品質ゲートは scope 固有の additive gate であり、`phase_*.md` の shared minimum gate 通過を前提とします。

対応 leaf skill:
- `.agents/skills/spec-dock-initiative-planning/SKILL.md`

関連:
- 総合: [guide.md](guide.md)
- 仕様書作成: [workflow_spec_authoring.md](workflow_spec_authoring.md)
- Epic: [workflow_epic.md](workflow_epic.md)
- GitHub 連携: [reference_github.md](reference_github.md)
- 共通 phase playbook: [phase_requirement.md](phase_requirement.md), [phase_design.md](phase_design.md), [phase_plan.md](phase_plan.md)
- Initiative plan playbook: [phase_plan_initiative.md](phase_plan_initiative.md)
- Decision routing: [authoring/decision-routing.md](authoring/decision-routing.md)
- Scope layering: [authoring/scope-layering.md](authoring/scope-layering.md)
- ChatGPT authoring evidence lane: [workflow_chatgpt_authoring_pack.md](workflow_chatgpt_authoring_pack.md)

## 再利用判定

- まず既存 initiative の `requirement.md` / `design.md` / `plan.md` / `discussions/` と current active を確認する
- 目的、成功条件、スコープ、責任主体が既存 initiative に自然に収まるなら、新規作成せず既存 initiative を更新する
- 投資判断の単位や success metrics が崩れる場合だけ `new` / `import` を使う
- 新規作成した理由や既存 initiative を使わない理由は、作成後の対象 initiative 配下の最初の `disc` に残す

## 作成

```bash
./spec-dock/scripts/spec-dock new initiative --title "..."
./spec-dock/scripts/spec-dock new initiative --github-issue <n> --title "..."
./spec-dock/scripts/spec-dock new initiative --create-github-issue --title "..."

./spec-dock/scripts/spec-dock import initiative <num|#num|url> --title "..."
```

- naming 制約と GitHub 振る舞いは [reference_naming.md](reference_naming.md), [reference_github.md](reference_github.md) を参照する
- Initiative 配下の Epic 作成は runtime command `./spec-dock/scripts/spec-dock new epic --initiative <initiative-id> --title "..."` を使う。生成される `epics/rules.md` は `spec-dock/docs/rules/initiative/epics.md` への入口で、作成ルールの正本は後者にある
- Issue 間依存の追加/削除/確認は `./spec-dock/scripts/spec-dock deps add/remove/check` を使い、反映は `./spec-dock/scripts/spec-dock validate` と `./spec-dock/scripts/spec-dock sync` で確認する

## 記述

- `requirement.md`: 投資理由、成功条件、スコープ
- `design.md`: 方針、境界、依存、リスク
- `plan.md`: Epic 分解、順序、ブロッカー。shared axiom は `phase_plan.md`、Initiative 固有の書き方は `phase_plan_initiative.md`
- Initiative は複数 Epic にまたがる product / architecture / operating model / investment decision を所有する。Epic 分解、success metric、責任主体、長期方針を変える判断は Initiative requirement / design / plan に反映してから Epic へ落とす。単一 Epic の設計 backbone に閉じる場合は Epic へ、単一 Issue の軽量 tradeoff に閉じる場合は Issue-local に戻す。責務境界と authority flow の共通参照は [authoring/scope-layering.md](authoring/scope-layering.md)、routing 例は [authoring/decision-routing.md](authoring/decision-routing.md) を参照する
- ChatGPT / Oracle は非自明な Initiative planning の ChatGPT-first primary route として、Initiative design / plan と Epic candidate の evidence producer に使う。candidate validation は node creation approval ではないため、Epic node 作成前に人間の明示的承認を通し、採用判断を `report.md` に残す。`local-context` は明示的な lower-authority evidence として扱う
- `spec-dock-initiative-planning-manual` は human-approved emergency backup であり、hard / unrecoverable ChatGPT route failure と recovery attempts、explicit approval、fresh reviewer gate の evidence がある場合だけ使う
- Requirement / design / plan の phase promotion は `workflow_spec_authoring.md` を正本にし、各 artifact ごとに fresh `spec-reviewer` の `review_status: pass` まで次 phase へ進めない
- `artifacts/`: `new artifact <type> --initiative <initiative-id> --title "..."` で、この initiative の `artifacts/` 配下に timestamp-prefixed original を作成する。current catalog は `blank` / `adr` / `disc` / `research` / `interview` / `decision-candidate` / `pr-repair-batch`。`draft-requirement` / `draft-design` / `draft-plan` は Issue-only artifact として扱う。runtime が filename / path を生成し、caller は stdout の `path=...` を正本として扱う。標準形は `<ts>-<kind>-<slug>.md`、same-second collision fallback は `<ts>-<nn>-<kind>-<slug>.md`。既存 `discussions/` 配下の artifact は legacy/grandfathered として保持する。詳細 contract は [reference_naming.md](reference_naming.md) を参照する
- `note` は新規作成 catalog から retired。既存 `note` artifact は grandfathered として壊さない。
- shared な書き方は `phase_*.md`、lifecycle / governance と Initiative 固有の分解判断はこの workflow を正本とする

## 品質ゲート

- requirement:
  - 背景 / 目的が 1〜3 行で言える
  - 成功条件が観測可能
  - スコープと非スコープが明確
  - 新規 initiative が必要な理由を最初の `disc` で追える
- design:
  - 依存関係が列挙されている
  - リスクと軽減策がある
- plan:
  - Epic への分解方針がある
  - 大まかな順序とブロッカーが見える
- authoring:
  - requirement / design / plan の各 promotion gate が `Spec Authoring Gate` として `report.md` に記録されている
  - scope / success metric / Epic 分解に影響する未確認事項が残っていない
  - plan gate pass 後に Epic 分解へ進む

## 仕上げ

```bash
./spec-dock/scripts/spec-dock validate
./spec-dock/scripts/spec-dock sync
```
