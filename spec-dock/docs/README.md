# 文書入口（spec-dock docs）

このディレクトリは `spec-dock init/update` により導入先リポジトリへ配置されます。  
まず `guide.md` で全体像を掴み、曖昧さの明確化は `workflow_clarification.md`、仕様書作成は `workflow_spec_authoring.md`、scope 固有の lifecycle / governance は対象 scope の `workflow_*.md` を入口にしてください。
plan だけは `phase_plan.md` の shared axiom と `phase_plan_<scope>.md` の scope-specific playbook を合わせて参照します。
runtime command の現行 contract は `./spec-dock/scripts/spec-dock ...` です。

## エージェント起点

`spec-dock init/update` は次の skill を導入します。

- Hub: `.agents/skills/spec-driven-tdd-workflow/SKILL.md`
- Clarification: `.agents/skills/spec-dock-clarification/SKILL.md`
- Initiative: `.agents/skills/spec-dock-initiative-planning/SKILL.md`
- Epic: `.agents/skills/spec-dock-epic-planning/SKILL.md`
- Issue planning: `.agents/skills/spec-dock-issue-planning/SKILL.md`
- Issue execution: `.agents/skills/spec-dock-issue-execution/SKILL.md`
- ADR: `.agents/skills/spec-dock-adr-facilitation/SKILL.md`

## 読み順

1. [guide.md](guide.md)
2. 対象 scope の workflow
   - [workflow_spec_authoring.md](workflow_spec_authoring.md)
   - [workflow_clarification.md](workflow_clarification.md)
   - [workflow_initiative.md](workflow_initiative.md)
   - [workflow_epic.md](workflow_epic.md)
   - [workflow_issue.md](workflow_issue.md)
   - [workflow_adr.md](workflow_adr.md)
3. phase の shared playbook
   - [phase_requirement.md](phase_requirement.md)
   - [phase_design.md](phase_design.md)
   - [phase_plan.md](phase_plan.md)
4. scope 固有の plan playbook
   - [phase_plan_initiative.md](phase_plan_initiative.md)
   - [phase_plan_epic.md](phase_plan_epic.md)
   - [phase_plan_issue.md](phase_plan_issue.md)
5. reference レイヤ
   - [reference_github.md](reference_github.md)
   - [reference_naming.md](reference_naming.md)
   - [reference_deps.md](reference_deps.md)
   - [reference_sync.md](reference_sync.md)

## 最短コマンド

```bash
./spec-dock/scripts/spec-dock new initiative --title "..."
./spec-dock/scripts/spec-dock new epic --initiative <initiative-id> --title "..."
./spec-dock/scripts/spec-dock new issue --epic <epic-id> --title "..."
./spec-dock/scripts/spec-dock new issue --create-github-issue --epic <epic-id> --title "..."

./spec-dock/scripts/spec-dock import epic <num-or-canonical-url> --title "..." [--initiative <id>] [--allow-foreign-url]
./spec-dock/scripts/spec-dock import issue <num-or-canonical-url> --title "..." [--epic <id>] [--allow-foreign-url]

./spec-dock/scripts/spec-dock issue start <github-issue-number>
./spec-dock/scripts/spec-dock issue start --id <issue-id>
./spec-dock/scripts/spec-dock issue finish

./spec-dock/scripts/spec-dock active set <id|#num|url>
./spec-dock/scripts/spec-dock active set --id <node-id>
./spec-dock/scripts/spec-dock active set --github-issue <n>
./spec-dock/scripts/spec-dock active set <id|#num|url> --checkout
./spec-dock/scripts/spec-dock active show

./spec-dock/scripts/spec-dock deps check <target>
./spec-dock/scripts/spec-dock deps add --from <issue-id> --to <issue-id>
./spec-dock/scripts/spec-dock deps remove --from <issue-id> --to <issue-id>
./spec-dock/scripts/spec-dock validate
./spec-dock/scripts/spec-dock sync

# 管理対象 files/docs/templates/scripts/skills の更新（refresh）
./spec-dock/scripts/spec-dock update
./spec-dock/scripts/spec-dock update /path/to/project
```

## 高頻度ルール

- Initiative / Epic は `new` / `import` の前に既存ノード再利用を確認する
- Requirement / design / plan 作成は `workflow_spec_authoring.md` の phase promotion gate を正本にし、fresh `spec-reviewer` の `review_status: pass` まで次 phase へ進めない
- 仕様書作成前後の曖昧さ、用語衝突、責務境界、正式質問は `workflow_clarification.md` を正本にし、`spec-dock-clarification` skill を入口にして一問ずつ扱う
- plan は shared `phase_plan.md` の後に対象 scope の `phase_plan_<scope>.md` を読む
- `new initiative` / `new epic` / `new issue` はデフォルトで GitHub Issue を作る。node create/import で local-only create へ自動フォールバックしない
- `new issue --create-github-issue` は default create の explicit alias
- `--no-github` / `--allow-foreign-url` は compatibility flag として残るが、current contract mismatch を auto-migrate せず reject/fail-fast しうる
- `import` は読み取り確認のみで、GitHub を更新しない。canonical URL は current repo と照合し、cross-repo node import は reject される
- Issue 実行の通常入口は `issue start <target>`、終了導線は `issue finish`。`active set` / `active set --checkout` は manual / recovery 用の low-level command として使う
- `active set` / `deps check` は `<target>` の後方互換を維持しつつ、`--id` / `--github-issue` の explicit form も使える
- 依存関係の追加/削除/確認は metadata の直編集ではなく `./spec-dock/scripts/spec-dock deps add/remove/check` を使い、変更後は `./spec-dock/scripts/spec-dock validate` と `./spec-dock/scripts/spec-dock sync` で GitHub live state を含めて整合を確認する。GitHub を呼ばない確認が必要な場合だけ `--no-github` を指定する
- legacy sequential discussion docs は grandfathered only。新規作成で sequence reuse / auto-rename / auto-repair はしない
- `./spec-dock/scripts/spec-dock update [path]` は repo-local self-update path で、target 省略時は current directory を更新する。明示 path を渡すとその managed repo を更新する
- runtime update は installer update の wrapper であり、固定 upstream `git+https://github.com/chemitaro/spec-dock` を `uvx --no-cache --from git+https://github.com/chemitaro/spec-dock spec-dock update <target>` として実行する。arbitrary source / cache / `--force` option は公開しない
- update は managed files/docs/templates/scripts/skills の更新であり、`init --force` でも old workspace の in-place migration ツールでもない。current contract mismatch は手動 normalize / rebuild が必要な場合がある
- Issue plan は agent-native / behavior-slice based execution contract を持つが、cadence policy の正本は `workflow_issue.md`
- naming 制約、GitHub 副作用、deps / sync の詳細は `reference_*.md` を参照する
