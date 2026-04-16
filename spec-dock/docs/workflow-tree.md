# Workflow: Initiative → Epic → Issue（ツリー運用）

このドキュメントは、`Initiative → Epic → Issue` を **複数ネスト・複数同時**に扱うためのワークフローです。  
目的は「巨大Issue化」「Why/What/How/Do の混線」「承認前に実装が走る」を防ぎ、Codex CLI（コーディングエージェント）と人間が同じ前提で運用できる状態を作ることです。

関連:
- 総合導線: `guide.md`
- GitHub連携の挙動: `reference_github.md`
- 状態集計（tree/index）: `reference_sync.md`
- Issue実装ワークフロー: `workflow_issue.md`
- ADR運用: `workflow_adr.md`

---

## 0. レイヤーの責務（混ぜない）

- Initiative: **Why / Outcome**（目的・成功指標・制約・投資範囲）
- Epic: **What / System-level How**（E2E要件・契約/API/データ/移行/観測性・Issue分割）
- Issue: **Do / Code-level How**（この差分で完了させること・詳細設計・テストで証明・実装ログ）

---

## 1. ノード作成（新規ツリーを起こす）

### 1.1 基本（デフォルト: GitHub Issue を自動作成）

```bash
./spec-dock/scripts/spec-dock new initiative --title "..."
./spec-dock/scripts/spec-dock new epic --initiative 123 --title "..."
./spec-dock/scripts/spec-dock new issue --epic 124 --title "..."
```

- `new {initiative,epic,issue}` はデフォルトで `gh` を呼びます（詳細: `reference_github.md`）。
- 親IDは `123` のような省略形、`init-00123` / `epic-00124` のような完全形を受け付けます。

### 1.2 既存 GitHub Issue へリンクする（新規作成しない）

```bash
./spec-dock/scripts/spec-dock new initiative --github-issue 123 --title "..."
./spec-dock/scripts/spec-dock new epic --initiative 123 --github-issue 124 --title "..."
./spec-dock/scripts/spec-dock new issue --epic 124 --github-issue 125 --title "..."
```

- `initiative / epic / issue` の local-only create はサポートされません。
- `--no-github` は compatibility option として残っていますが、contract error で reject されます。

---

## 2. Initiative を固める（Outcome とガードレールを固定）

対象ファイル（Initiative配下）:
- `requirement.md`（Outcome / 成功指標 / スコープ境界 / DoR）
- `design.md`（Guardrails: 互換性・移行方針・観測性・品質ゲート）
- `plan.md`（Roadmap: Epic分解/順序/計測/ロールアウト）
- `report.md`（進捗/決定/結果）
- `adrs/`（initiative全体に効く意思決定）

運用:
- `状態: draft` の間は **議論・詰め・TBD解消の期間**。推測で埋めない。
- Initiativeの `状態: approved` は、ユーザー/レビュアーの **明示的承認** でのみ付ける。
- 詳細確認は `guide.md` を入口に対象 workflow / phase を参照する。

---

## 3. Epic を設計の背骨として作る（Issue分割が破綻しない状態）

対象ファイル（Epic配下）:
- `requirement.md`（E-RQ / E-AC / NFR / 境界）
- `design.md`（契約/API/イベント/データ/移行/観測性/テスト戦略の背骨）
- `plan.md`（Issue分割/順序/品質ゲート/ロールアウト）
- `report.md`（進捗/決定/統合結果）
- `adrs/`（epicに閉じる意思決定）

ポイント:
- Epicは「Issue一覧」ではなく、**Issueが増えても壊れない“背骨”**（契約/移行/観測性/品質ゲート）を持つ。
- Issue分割は `plan.md` に集約し、順序・依存・品質ゲートを明文化する。

---

## 4. Issue を“単独完結”の作業単位として作る（ただし親に従う）

Issueは単独で「要件→設計→計画→実装→報告」まで完結する作業単位です。  
一方で、親（Initiative/Epic）のガードレール・契約・E2E受入（E-AC/NFR）に従います。

推奨:
- 重複を避け、背景/KPIの再掲はせず **親へリンク**する。
- 親の前提や制約を破る必要が出たら、先に ADR を起こす（`workflow_adr.md`）。

詳細: `workflow_issue.md`

---

## 5. 複数同時運用（可視化と集中の両立）

### 5.1 状態の可視化（sync）

```bash
./spec-dock/scripts/spec-dock sync
./spec-dock/scripts/spec-dock sync --github
```

- `spec-dock/.agent/tree.json`（人間向けのネスト表示）
- `spec-dock/.agent/index.json`（エージェント向けのフラット索引）
- `spec-dock/adrs/`（generated ADR mirror。`sync` で rebuild / gitignore 対象）

詳細: `reference_sync.md`

### 5.2 いま作業する対象の固定（active）

```bash
./spec-dock/scripts/spec-dock active show
./spec-dock/scripts/spec-dock active set 123          # GitHub issue number（checkout + active + sync）
./spec-dock/scripts/spec-dock active set iss-00123     # node id（issue）
./spec-dock/scripts/spec-dock active set epic-00123    # node id（epic）
./spec-dock/scripts/spec-dock active set init-00123    # node id（initiative）
./spec-dock/scripts/spec-dock active clear
```

- `active` は生成物（gitignore）で、**「いま触る対象」の入口**だけを提供する。
- エージェントは `spec-dock/active/context-pack.md` を入口にする。
- GitHub Issue に紐づくノード（`github.issue_number` があるノード）を `active set` した場合、`active set` は checkout も行う。
- active が未設定のレイヤーは placeholder（`spec-dock/system/active-none/**`）へ向く。
  - placeholder は編集対象外（best-effortで read-only）

### 5.3 構造チェック（validate）

```bash
./spec-dock/scripts/spec-dock validate
```

---

## 5.4 依存変更（Issue 間）

```bash
./spec-dock/scripts/spec-dock deps check <target> --github
./spec-dock/scripts/spec-dock deps add --from <issue-id> --to <issue-id>
./spec-dock/scripts/spec-dock deps remove --from <issue-id> --to <issue-id>
./spec-dock/scripts/spec-dock validate
./spec-dock/scripts/spec-dock sync --github
```

- Issue 依存の canonical storage は node metadata の top-level `depends_on` です（詳細は `reference_deps.md`）。
- metadata の手編集を current/fallback 運用にせず、command-first で更新してください。

## 6. 典型的な落とし穴（防止策）

- GitHub を使えない環境で `new` が失敗 → `gh` と current repo の GitHub linkage を整えるか、既存 current-repo Issue に `--github-issue <n>` でリンクする（`reference_github.md`）
- `approved` を“進捗”として使ってしまう → **承認用途のみ**（進捗は report/sync）
- 上位（Initiative/Epic）と下位（Issue）の矛盾が放置される → 差分が出たら上位へフィードバック + ADR
- “とりあえず実装”が始まる → requirement/design/plan の承認ゲートを必ず通す（`guide.md` を入口に確認）
