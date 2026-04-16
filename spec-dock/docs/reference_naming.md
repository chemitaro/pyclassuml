# reference: naming（`--title` / `--slug` / branch / discussions）

このドキュメントは、spec-dock が扱う **命名**（title/slug、discussion docs のファイル名、checkout 後のブランチ名）をまとめた参照です。

関連:
- 入口: [README.md](README.md)
- GitHub 連携: [reference_github.md](reference_github.md)

---

## 1. 対象（どのコマンドに効くか）

### 1.1 `--title` / `--slug` の入力制約

- `new {initiative,epic,issue}`
- `import {initiative,epic,issue}`
- `new doc <type>`（`type = adr|disc|research|note`）

補足:
- `new doc <type>` は explicit basename / `doc_id` override（`--id` / `--seq` など）を提供しません。

### 1.2 ブランチ命名（checkout 後の正規化）

- `active set <target> --checkout`
  - デフォルト（`active set <target>`）は no-checkout のため、ブランチ操作は行いません

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
- `new doc <type>` の `--title` は、discussion markdown 本文に埋め込むためのタイトルです（node title 制約とは別系統）。

---

## 3. `--slug`（kebab-case 制約）

`new/import {initiative,epic,issue}` と `new doc <type>` の `--slug` は、**trim 後**に次を満たす必要があります。

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
- ルール（discussion docs）: `_slugify(title)` で候補を作り、最終的に kebab-case 制約で検証

---

## 4. discussion docs の命名と識別子（`new doc <type>`）

### 4.1 doc family と保存先

- discussion doc family は `adr|disc|research|note` です。
- original/source file は、対象 Initiative / Epic / Issue ノード配下の `discussions/` に作成されます。
- ADR も original は常に `discussions/` 配下です。mirror / sync があっても original location は変わりません。

### 4.2 basename contract

標準形:
- `<ts>-<kind>-<slug>.md`

same-second collision 形:
- `<ts>-<nn>-<kind>-<slug>.md`

各要素:
- `ts = yyyymmddthhmmssz`
  - UTC 固定
  - `t` / `z` は lowercase 固定
- `nn = 01..99`
  - 同一 `discussions/` directory 内で同じ秒を共有した discussion doc family collision を解消する suffix です
  - suffix が必要ないときは付けません
- `kind = adr|disc|research|note`
- `slug` は kebab-case です

例:
- `20260329t123456z-adr-token-rotation.md`
- `20260329t123456z-disc-api-options.md`
- `20260329t123456z-01-research-benchmark-summary.md`
- `20260329t123456z-02-note-kickoff-memo.md`

### 4.3 `doc_id` と filename stem の境界

`doc_id` は slugless identity です。

標準形の `doc_id`:
- `<ts>-<kind>`

collision 形の `doc_id`:
- `<ts>-<nn>-<kind>`

関係:
- filename stem = `<doc_id>-<slug>`
- つまり slug は filename の一部ですが、identity そのものではありません
- CLI / runtime が discussion doc の識別子を表示するときは、この slugless `doc_id` を使います

例:
- filename: `20260329t123456z-adr-token-rotation.md`
  - `doc_id`: `20260329t123456z-adr`
- filename: `20260329t123456z-01-disc-api-options.md`
  - `doc_id`: `20260329t123456z-01-disc`

### 4.4 legacy files と validation 境界

legacy sequential docs は grandfathered only です。

- 例: `001-adr-token-rotation.md`, `002-disc-api-options.md`
- 強制的 backward compatibility を維持するために legacy naming へ戻したり、新規 doc で legacy sequence basename を優先したりはしません
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
  - 例: `001_adr-token-rotation.md`, `adr_token_rotation.md`（discussion-doc intent の malformed legacy-like basename）

原則:
- unrelated file は ignore します
- malformed discussion filename candidate は fail-closed で reject します
- grandfathered なのは既存 legacy sequential docs だけであり、legacy contract 全体の forced compatibility を意味しません

---

## 5. `active set --checkout` のブランチ命名（日本語ブランチを避ける）

### 5.1 目的

`active set --checkout` では、ブランチ名を **ASCII かつ git 的に妥当**な形式へ寄せます。  
これにより、非ASCII名や不正ref名による運用トラブルを避けます。

### 5.2 対象

- `active set <target> --checkout` を明示した場合のみ
- target の node 種別（initiative / epic / issue）や GitHub 紐づき有無は問いません
- `--checkout` を付けない場合は **ブランチ操作しません**

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
