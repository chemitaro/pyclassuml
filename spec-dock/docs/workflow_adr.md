# アーキテクチャ判断ワークフロー（workflow: ADR）

ADR（Architecture Decision Record）は、意思決定を仕様（requirement/design/plan）から **切り離して**記録するための仕組みです。

対応 leaf skill:
- `.agents/skills/spec-dock-adr-facilitation/SKILL.md`

関連:
- 総合: [guide.md](guide.md)
- Initiative: [workflow_initiative.md](workflow_initiative.md)
- Epic: [workflow_epic.md](workflow_epic.md)
- Issue: [workflow_issue.md](workflow_issue.md)
- 命名と採番: [reference_naming.md](reference_naming.md)
- 依存関係: [reference_deps.md](reference_deps.md)

## 1. いつ ADR を起こすか

次のどれかに当てはまるなら、先に ADR を作ります:

- 方針が複数ありトレードオフがある
- “やり直しコストが高い” 変更（データ/契約/公開API）
- チーム合意が必要（合意無く進めると事故る）

## 2. 作る（叩き台を先に作る）

Issue/Epic/Initiative のいずれかに紐づけて作成します。

runtime command（scope を明示）:

```bash
# 課題スコープ（issue scope）
./spec-dock/scripts/spec-dock new artifact adr --issue <issue-id> --title "..."

# エピックスコープ（epic scope）
./spec-dock/scripts/spec-dock new artifact adr --epic <epic-id> --title "..."

# イニシアチブスコープ（initiative scope）
./spec-dock/scripts/spec-dock new artifact adr --initiative <initiative-id> --title "..."
```

生成先:
- scope ノード配下の `artifacts/`（例: `.../init-.../artifacts/` / `.../epic-.../artifacts/` / `.../iss-.../artifacts/`）
- ADR original は future `artifacts/` または legacy `discussions/` 配下にありえます。mirror / sync があっても original location は変わりません。
- ファイル名:
  - 標準: `<ts>-adr-<slug>.md`
  - same-second collision: `<ts>-<nn>-adr-<slug>.md`
- `ts = yyyymmddthhmmssz`（UTC, lowercase `t` / `z`）
- `nn = 01..99`
- `artifact_id` は slugless identity（`<ts>-adr` / `<ts>-<nn>-adr`）

補足:
- `new artifact` の詳細な naming contract は [reference_naming.md](reference_naming.md) を参照してください。
- legacy sequential ADR / discussion docs は grandfathered で、自動 rename しません。
- `rules.md` のような unrelated files は無視されますが、malformed artifact filename candidate は explicit validation error です。

方針:
- Decision は最初は **TBD** で良い（議論の叩き台として先に置く）
- Options を列挙し、Pros/Cons を書く

## 3. 決める（Decision → accepted）

レビュー/合意後に:
- Decision を確定し、必要ならステータスを `accepted` にする
- 影響がある仕様（design/plan）へリンクして反映する

## 3.5 依存変更を伴う ADR の運用

ADR で Issue 間依存の追加/削除を採用した場合は、次の command-first contract で反映します。

```bash
./spec-dock/scripts/spec-dock deps check <target>
./spec-dock/scripts/spec-dock deps add --from <issue-id> --to <issue-id>
./spec-dock/scripts/spec-dock deps remove --from <issue-id> --to <issue-id>
./spec-dock/scripts/spec-dock validate
./spec-dock/scripts/spec-dock sync
```

## 4. 品質ゲート（ADR）

- [ ] 問題（Context）が 1〜3 行で説明できる
- [ ] 選択肢（Options）が複数あり、それぞれ Pros/Cons がある
- [ ] Decision が明確（何を採り、何を捨てたか）
- [ ] 影響範囲（仕様/実装/移行/運用）が書かれている（必要なら）
