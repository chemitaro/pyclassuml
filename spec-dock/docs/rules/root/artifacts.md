# ルートの成果物ルール（root / artifacts/rules.md）

`artifact import file --root --file <path>` は、一件の明示 regular file を
root の `spec-dock/artifacts/` へ generic Artifact として保存する経路です。
Workbench は入力要件ではありません。source は変更・削除せず、imported bytes
は opaque evidence として扱います。

- generic Artifact は canonical specification、review 済み内容、承認済み内容、
  または採用済み判断ではありません。保存結果の `canonical=false` はこの境界を
  表します。採用する主張だけを canonical docs または accepted ADR へ明示的に
  反映し、必要な reviewer gate を通してください。
- source が repository 内で安全に識別できるときだけ result は repo-relative
  source を表示します。それ以外は basename だけを表示します。source bytes、
  hash、byte count、repository 外の絶対 path は generic result に出しません。
- success は `committed=true` です。通常は
  `publication_state=committed`、commit 後に許可された durability / cleanup
  warning が残る場合は `committed_with_warning` になります。どちらも
  `retry_disposition=not_needed` です。commit 前 failure は
  `not_committed` と `safe_after_remediation` で返ります。
- filename、timestamp slot、collision と normalized basename の契約は
  [reference_naming.md](../../reference_naming.md) を参照してください。

root Artifact storage を初期化すると、`spec-dock/artifacts/rules.md` はこの
provider-managed rules source への relative symlink になります。この
`rules.md` は入口だけであり、本文の正本を node ごとに複製しません。
