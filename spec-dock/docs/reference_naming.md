# 命名参照（reference: naming / `--title` / `--slug` / branch / artifacts）

このドキュメントは、spec-dock が扱う **命名**（title/slug、artifact docs のファイル名、checkout 後のブランチ名）をまとめた参照です。

関連:
- 入口: [README.md](README.md)
- GitHub 連携: [reference_github.md](reference_github.md)

---

## 1. 対象（どのコマンドに効くか）

### 1.1 `--title` / `--slug` の入力制約

- `new {initiative,epic,issue}`
- `import {initiative,epic,issue}`
- `new artifact <type>`（current catalog: `blank` / `adr` / `disc` / `research` / `interview` / `decision-candidate` / `pr-repair-batch` / issue-only `draft-requirement` / `draft-design` / `draft-plan`）

補足:
- `new artifact <type>` は explicit basename / `artifact_id` override（`--id` / `--seq` など）を提供しません。
- 新規 artifact doc の filename / `artifact_id` / path は runtime が生成します。caller / agent は `new artifact <type>` の stdout で返る `path=...` を正本として本文更新に使います。

### 1.2 ブランチ命名（checkout 後の正規化）

- `issue start <target>`
- `issue start <target> -f`
- `active set <target> --checkout`
  - デフォルト（`active set <target>`）は no-checkout のため、ブランチ操作は行いません
  - `issue start` は issue node 専用です。initiative / epic / issue の target kind を問わないのは `active set <target> --checkout` のみです

---

## 2. `--title`（ASCII 制約）

`new/import {initiative,epic,issue}` の `--title` は、**trim 後**に次を満たす必要があります。

- 正規表現: `^[A-Za-z0-9]+(?: [A-Za-z0-9]+)*$`
- 意味: 「英数字トークンを **半角スペース 1 個**で区切った列」

許可:
- 英字（`A-Z` / `a-z`）
- 数字（`0-9`）
- 区切り（半角スペース 1 個）

不許可（例）:
- 日本語などの非 ASCII（例: `トークン追加`）
- 記号（例: `Add-Token`, `Fix: token`, `foo/bar`）
- 連続スペース / 全角スペース（例: `Add  Token`, `Add　Token`）

保存:
- 保存される title は **trim 後の文字列**です（先頭/末尾の空白は保存しません）。

目的:
- title から slug を決定的に生成できるようにし、パス/ブランチ名を安全に保つためです。

補足:
- `new artifact <type>` の `--title` は、artifact markdown 本文に埋め込むためのタイトルです（node title 制約とは別系統）。

---

## 3. `--slug`（kebab-case 制約）

`new/import {initiative,epic,issue}` と `new artifact <type>` の `--slug` は、**trim 後**に次を満たす必要があります。

- 正規表現: `^[a-z0-9]+(?:-[a-z0-9]+)*$`
- 意味: 「小文字英数字トークンを `-` で区切った列（kebab-case）」

許可（例）:
- `add-refresh-token`
- `jwt-auth`
- `oauth2`

不許可（例）:
- 大文字（例: `Add-token`）
- アンダースコア/スペース（例: `add_refresh_token`, `add refresh token`）
- 連続/前後のハイフン（例: `add--token`, `-add-token`, `add-token-`）

### 3.1 `--slug` を省略した場合（title → slug 合成）

`--slug` を省略した場合、slug は title から自動生成されます。

- ルール（node系）: `slug = lower(title).replace(" ", "-")`
- ルール（artifact docs）: `_slugify(title)` で候補を作り、最終的に kebab-case 制約で検証

---

## 4. 成果物文書の命名と識別子（artifact docs / `new artifact <type>`）

### 4.1 文書種別と保存先（doc family）

- new creation の artifact doc family は `blank` / `adr` / `disc` / `research` / `interview` / `decision-candidate` / `pr-repair-batch` / issue-only `draft-requirement` / `draft-design` / `draft-plan` です。
- `scratch` / `note` は retired です。既存 `scratch` / `note` artifact は grandfathered として validation 対象に残りますが、新規作成 catalog ではありません。
- original/source file は、対象 Initiative / Epic / Issue ノード配下の `artifacts/` に作成されます。
- ADR original は future `artifacts/` または legacy `discussions/` 配下にありえます。generated ADR mirror / sync 対象は `adr` のみで、`pr-repair-batch` や他の artifact type へ広げません。
- `draft-requirement` / `draft-design` / `draft-plan` は issue-only routing type です。Initiative / Epic scope では unsupported です。
- この節の basename 形式は validation / allocation contract の参照です。新規作成時に手で `<ts>-...` filename を組み立てず、`new artifact <type>` が返す generated path を使います。

### 4.2 ベース名契約（basename contract）

標準形:
- typed artifact: `<ts>-<type>-<slug>.md`
- blank artifact: `<ts>-<slug>.md`

same-second collision 形:
- typed artifact: `<ts>-<nn>-<type>-<slug>.md`
- blank artifact: `<ts>-<nn>-<slug>.md`

各要素:
- `ts = yyyymmddthhmmssz`
  - UTC 固定
  - `t` / `z` は lowercase 固定
- `nn = 01..99`
  - 同一 `artifacts/` directory 内で同じ秒を共有した artifact doc family collision の safety fallback suffix です
  - runtime は同じ timestamp slot が使われている場合、短い wait / retry で次の timestamp slot を優先し、bounded wait で解消できないときだけ suffix を使います
- `type = adr|disc|research|interview|decision-candidate|pr-repair-batch|draft-requirement|draft-design|draft-plan`
- `blank` は filename token を使わず、front matter の `template: "blank"` で template identity を示します。
- grandfathered existing `scratch` / `note` filenames may also appear in validation.
- `slug` は kebab-case です

例:
- `20260329t123455z-kickoff-memo.md`
- `20260329t123456z-adr-token-rotation.md`
- `20260329t123456z-disc-api-options.md`
- `20260329t123456z-decision-candidate-token-options.md`
- `20260329t123456z-pr-repair-batch-review-fixes.md`
- `20260329t123456z-01-research-benchmark-summary.md`
- `20260329t123456z-02-interview-rollout-policy.md`
- `20260329t123457z-draft-plan-step-slicing.md`

### 4.3 `artifact_id` と filename stem の境界

`artifact_id` は slugless identity です。

標準形の `artifact_id`:
- typed artifact: `<ts>-<type>`
- blank artifact: `<ts>`

collision 形の `artifact_id`:
- typed artifact: `<ts>-<nn>-<type>`
- blank artifact: `<ts>-<nn>`

関係:
- filename stem = `<artifact_id>-<slug>`
- つまり slug は filename の一部ですが、identity そのものではありません
- CLI / runtime が artifact doc の識別子を表示するときは、この slugless `artifact_id` を使います

例:
- filename: `20260329t123456z-adr-token-rotation.md`
  - `artifact_id`: `20260329t123456z-adr`
- filename: `20260329t123456z-01-disc-api-options.md`
  - `artifact_id`: `20260329t123456z-01-disc`
- filename: `20260329t123456z-pr-repair-batch-review-fixes.md`
  - `artifact_id`: `20260329t123456z-pr-repair-batch`
- filename: `20260329t123455z-kickoff-memo.md`
  - `artifact_id`: `20260329t123455z`

### 4.4 旧形式ファイルと検証境界（legacy files / validation boundary）

legacy sequential docs は grandfathered only です。

- 例: `001-adr-token-rotation.md`, `002-disc-api-options.md`
- 既存 `001-note-kickoff-memo.md`、timestamp `*-note-*.md`、timestamp `*-scratch-*.md` も grandfathered artifact として扱います。
- 強制的 backward compatibility を維持するために legacy naming へ戻したり、新規 artifact で legacy sequence basename を優先したりはしません
- 既存 legacy file は自動 rename しません
- 新 contract で新規作成するときに legacy sequential basename を再利用しません
- malformed / mismatch basename を validation が自動 repair することもありません

validation / allocation の扱い:
- unrelated files は無視します
  - 例: `rules.md`, `README.md`, `notes.txt`
- ただし、timestamp intent / discussion-doc intent があるのに contract を満たさない basename は explicit error です
  - 例: `20260329T123456Z-adr-token-rotation.md`（`T` / `Z` が uppercase）
  - 例: `20260329t123456-adr-token-rotation.md`（末尾 `z` 欠落）
  - 例: `20260329t123456z_adr-token-rotation.md`（separator 不正）
  - 例: `001_adr-token-rotation.md`, `adr_token_rotation.md`（artifact intent の malformed legacy-like basename）

原則:
- unrelated file は ignore します
- malformed discussion filename candidate は fail-closed で reject します
- grandfathered なのは既存 legacy sequential docs だけであり、legacy contract 全体の forced compatibility を意味しません

### 4.5 `artifact import chatgpt-output` の命名境界

`artifact import chatgpt-output` は、approved Workbenchにある単一 `.md` fileのbytesをblank Artifact identityで保存します。`chatgpt-output`はimport kindであり、この節のtyped Artifact `type` tokenには追加しません。Blank Artifactのtitle/slugに`chatgpt-output`を使うことは予約・禁止せず、`new artifact`のcatalogとimport commandは独立して共存します。

Import先basenameはblank grammarと既存collision allocationを使い、slugだけに`chatgpt-output-` prefixを含めます。Source本文、encoding、改行、frontmatterは変更せず、source fileも削除しません。FilenameがArtifact規則へ適合することと、imported bodyがcanonical authorityを持つことは別です。

### 4.6 `artifact import file` の generic identity

`artifact import file --file <path>` は `--root`、`--initiative`、`--epic`、`--issue` の一つを destination として指定し、title / slug / type token を受け取りません。一件の explicit regular file の basename から runtime が generic identity を生成します。

- standard: `<ts>--<normalized-basename>`
- same-second collision: `<ts>-<nn>--<normalized-basename>`
- `ts` と `nn` は 4.2 と同じ UTC timestamp / `01..99` の shared slot contract を使います。typed、blank、generic は同じ `artifacts/` directory の slot を共有します。
- generic `artifact_id` は slugless artifact doc identity ではなく、保存先の generic filename 全体です。
- `normalized-basename` は source basename を基礎にし、path separator、NUL、control / format character、platform で unsafe な basename character を `_` に置換します。component byte limit を超える場合は extension chain をできるだけ保持して短縮します。caller は保存先名を手組みせず command result の `artifact_id` / `destination` を使います。

例:

- source `Report FINAL.PDF` → `20260730t010203z--Report FINAL.PDF`
- 同一 timestamp slot の collision → `20260730t010203z-01--Report FINAL.PDF`

generic identity は typed / blank Artifact grammar と別であり、拡張子、Markdown、本文 encoding、frontmatter を要求しません。`rules.md` は generic Artifact ではありません。generic filename が valid であることは、body が canonical authority、review 済み、または採用済みであることを意味しません。

---

## 5. `issue start` / `active set --checkout` のブランチ命名（日本語ブランチを避ける）

### 5.1 目的

`issue start` と `active set --checkout` では、ブランチ名を **ASCII かつ git 的に妥当**な形式へ寄せます。
これにより、非ASCII名や不正ref名による運用トラブルを避けます。

### 5.2 対象

- `issue start <target>` / `issue start <target> -f`
  - issue node のみを受け付けます
- `active set <target> --checkout` を明示した場合
  - target の node 種別（initiative / epic / issue）や GitHub 紐づき有無は問いません
- `active set` で `--checkout` を付けない場合は **ブランチ操作しません**

### 5.3 望ましいブランチ名（desired）

基本:
- desired = `<id>-<slug>`
  - 例: `iss-00123-add-refresh-token`

フォールバック:
- `<id>-<slug>` が次のいずれかに該当する場合、desired は `<id>` にフォールバックします
  - **非 ASCII**（`isascii()` 相当で判定）
  - `git check-ref-format --branch` を満たさない

### 5.4 既存ブランチがある場合（衝突）

desired ブランチが既に存在する場合:
- 既存ブランチを checkout して **再利用**します（上書き/削除/強制更新はしません）
- stderr に warning を出します（例: `spec-dock: (warn) branch already exists; reusing existing branch; content is not verified`）

desired ブランチが存在しない場合:
- `git checkout -b <desired>` で新規作成して checkout します

補足:
- `active` の解決は checkout 前に確定しており、checkout 後に node を再解決しません
- spec-dock は `git branch -D` / `git reset --hard` / `git checkout -B` / `git branch -M` 等の破壊的/強制操作は行いません

### 5.5 警告（stderr）の安定トークン

warning は stderr に `spec-dock: (warn)` プレフィクスで出力されます。  
運用/テストでは全文一致ではなく、このプレフィクスやキーフレーズ（例: `fallback to id`, `reusing existing branch`）の **包含**で検証するのが安全です。
