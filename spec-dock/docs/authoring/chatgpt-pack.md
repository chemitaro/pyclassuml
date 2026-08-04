# プロンプトパックとZIP証跡のリファレンス（ChatGPT prompt pack / ZIP / staged evidence）

この文書は ChatGPT output と authoring pack の生成物を、SpecDock の evidence として安全に扱うための reference です。

## 生成物の関係

```text
preflight evidence
  -> prompt pack
  -> backend invocation
  -> output received
  -> preservation checkpoint
     -> standalone / inline import evidence
     -> ZIP / tree pack review -> staged evidence -> candidate / draft validation
     -> unavailable exception
  -> EAL adoption decision
  -> canonical rewrite
  -> fresh reviewer gate
```

どの段階でも、ChatGPT output は正本ではありません。
review / stage / validate の `pass` は、その command が担当する構造や安全性の確認結果です。
ChatGPT-first planning route は非自明な Initiative / Epic / Issue planning の正規 evidence-production route ですが、canonical adoption、fresh reviewer pass、execution-ready、PR-ready、merge-ready は各 planning / execution workflow が所有します。manual planning skill は hard / unrecoverable ChatGPT route failure と human-approved emergency backup evidence がある場合だけ使います。

## 証跡レーンと保存チェックポイント（Evidence lane / preservation checkpoint）

ChatGPT evidence は次の三laneを混同せず扱います。

1. External preserved evidence: standalone Markdownまたは完全に受信したinline answerをWorkbenchからArtifactへ保存した原文evidence。
2. Delegated draft evidence: delegated authoring roleがtask-local authorizationの下で作成するdraft。既存のfrontmatter、provenance、diff guard、authority restrictionに従う。
3. ZIP/tree staged evidence: existing authoring packのreview、quarantine、stage、validationを経た複数file evidence。

Main orchestratorはoutput受領後、adoptionやcanonical rewriteより先にsemantic completenessとoutput formを確認し、次の一分岐だけを選びます。未分類の間はpreservation statusを付けず、import、EAL disposition、canonical rewriteをblockします。

| 分類 | メインオーケストレーターの操作（Main orchestrator action） | 保存状態 / 証跡（preservation status / evidence） | 禁止 |
|---|---|---|---|
| 完成standalone Markdown | 作業台のsource（Workbench source）を`artifact import chatgpt-output`で明示importし、receiptを検証する | `imported_byte_exact`。同一性境界はWorkbench sourceからimported Artifactまで | 委任draft用frontmatterの追加（delegated frontmatter addition）、source削除、automatic import |
| 完全に受信したinline answer | 受信回答本文（Answer body）の開始・終了を確認し、文字の追加・削除・整形なしでWorkbench `.md`へcaptureして明示importする | `captured_received_text`。同一性境界は受信textからimported Artifactまで | プロンプト / wrapper metadataを含むraw transcript全体のdurable import、provider-original bytes claim |
| 本当に不完全または取得不能なinline output | 理由（Reason）、判断者（decision owner）、nonblocking根拠、next action / revisit conditionを記録する | `skipped_inline_unavailable`。Source/destination path、hash、byte countは記録しない | 完全なsource（Complete source）の保存失敗、receipt欠落、eligibility failureをunavailableへ再分類 |
| 圧縮包またはツリー（ZIP / tree） | 既存packのreview、quarantine、stage、validation laneへrouteする | 既存のreview/stage証跡（existing review/stage evidence） | 単一file importへの変換（single-file import conversion）、ZIP safety contractの緩和 |

Fileの存在、拡張子、size、encodingだけでsemantic completenessを自動判定しません。Main orchestratorが内容を確認するかcomplete sourceを取得してから分類します。

### 取り込み結果（Import result）

- `committed=true`、`import_kind=chatgpt-output`、`storage_identity=blank`、final repo-relative path、SHA-256、byte countが揃う場合は保存済みとする。
- `committed=true`でwarningがある場合も保存済みである。Warningを記録し、自動retryや重複importを行わない。
- `committed=false`、receipt欠落、eligibility failure、またはsemantic completeness未分類はblockである。Complete sourceを`skipped_inline_unavailable`へ読み替えない。
- Import途中で失敗してもWorkbench sourceを削除しない。
- Standalone importのMVP対象は単一`.md` fileであり、source bytes、encoding、改行、frontmatterを変更しない。Directory、bundle、PDF、image、ZIPはこのcommandへ自動変換しない。
- 言語、拡張子、MIME、内容からcopy/import可否を決めるclassifierは持たない。ただしpublic command contractとしてsourceは`.md`に限定する。
- `chatgpt-output`はimport kindであってtyped Artifact tokenではない。Blank naming/collision grammarで保存し、template-based `new artifact`のcatalogや命名を予約・置換しない。

### 本文を含まないEAL（Content-free EAL）

保存成功recordは標準EAL field（ID、source、source role、claim、target artifact / section、rationale、evidence strength / path、adopter、reviewer、blocking、next action）に加え、output form、preservation status、capture boundary、`import_kind=chatgpt-output`、`storage_identity=blank`、repo-relative source/destination、SHA-256、byte count、committed/warning、adoption statusを記録します。本文、secret-like value、absolute host pathは記録しません。

Preservation statusとadoption statusは別fieldです。保存成功後のadoption statusは`adopted`、`partially_adopted`、`rejected`、`deferred`のいずれかをexact tokenで記録し、evidenceを保存したこと自体をcanonical採用とみなしません。Imported bodyはevidence-onlyであり、import commandやshared/planning skillはEAL、canonical docs、ADR、assurance stateを変更せず、reviewer pass、readiness、finish、PR deliveryを自己主張しません。

## プロンプトパックの役割（Prompt pack）

prompt pack は、ChatGPT に渡すタスク、期待出力、source manifest、branch / commit 情報、evidence mode、出力 ZIP のディレクトリ構成をまとめたものです。

prompt pack には次を含めます。

- scope: initiative / epic / issue / selected-skeleton
- target node id
- upstream requirement / design / plan
- relevant ADR / artifact summary
- supported output tree
- explicit forbidden authority claims
- expected ZIP manifest
- evidence mode
- failure handling expectation: wait / retry / recover before any manual route

## GitHub 同期 receipt と pack binding

`github-synced` の preflight receipt を保存する場合は、SpecDock entrypoint を direct argv で実行し、既存かつ repository 外の directory を `--output-dir` に指定します。shell wrapper、redirect、pipe、`tee`、heredoc、command substitution、inline environment assignment は使いません。

```text
./spec-dock/scripts/spec-dock authoring preflight github-sync --output-dir <existing-external-directory>
```

receipt は stdout format と独立した JSON で、file 名は `github-sync-preflight.receipt.json` に固定されます。安全な出力先なら blocked result も保存されます。fetch の nonzero は追加権限が必要であることの証跡ではなく、`require_escalated` や sandbox / permission mode の変更理由にはなりません。限定 retry は SpecDock が同じ実行形で行うため、agent-owned raw `git fetch` に置き換えません。blocked result の `blockers`、bounded diagnostics、`remediation` に従って原因を修正し、`local-context` や default branch へ暗黙に切り替えません。

`authoring pack prepare --preflight <receipt>` は、versioned receipt の kind、schema、digest、pass / fetch / snapshot semantics を検証し、receipt digest、snapshot identity、`observed_at` を prompt pack provenance に binding します。これは preflight 観測時点の integrity と provenance の契約です。pack prepare は current repository / remote を再取得・再検証せず、`current_repository_revalidated` は false のままです。receipt publication 後や backend invocation 直前までの freshness を保証するものではありません。

legacy unversioned receipt は既存 contract を満たす範囲で読み取れますが、new receipt digest、snapshot binding、current freshness を推測しません。receipt / pack validation は evidence-lane の検査であり、canonical adoption、reviewer pass、execution-ready、PR-ready、merge-ready を付与しません。

## 出力 ZIP / tree の扱い（ZIP / tree output）

ZIP / tree output は長文の複数ファイルをまとめて受け取るための transport です。
そのまま canonical docs にコピーするものではありません。

安全な取り扱い:

- path traversal を拒否する。
- unsafe symlink を拒否する。
- manifest にない unexpected file を警告または拒否する。
- canonical docs、`.assurance.json`、runtime state、GitHub state を直接変更しない。
- output metadata に `authority: evidence_only` を持たせる。

ZIP/treeは上記preservation checkpointの独立branchです。Standalone/inline用のsingle-file importへ流さず、この安全laneを維持します。

## 配置済み証跡の扱い（staged evidence）

`authoring pack stage` は、review 済み output を evidence として配置する工程です。
staged evidence は採用候補であり、canonical artifact ではありません。

staged evidence から canonical docs へ反映する場合:

1. main orchestrator が採用する claim と捨てる claim を決める。
2. `report.md` の Evidence Adoption Ledger に記録する。
3. canonical docs に main orchestrator が再記述する。
4. fresh reviewer gate を通す。

Option 3+ の Epic output では、Epic docs と配下 Issue の draft requirement / draft design / draft plan を ZIP/tree でまとめて受け取れます。この場合でも Issue draft は handoff-ready evidence であり、各 Issue の canonical docs は Issue planning が current state と prior Issues を確認して正式化します。

## 候補検証（Candidate validation）

`authoring validate initiative-epic-candidates` と `authoring validate epic-issue-candidates` は、候補 list の構造、source hash、approval 前提を確認します。
candidate validation pass は、人間の node creation approval ではありません。

Epic / Issue node creation の前には、人間が候補を確認して承認します。

## ドラフト採用検証（Draft adoption validation）

`authoring validate issue-draft-adoption` と `authoring validate selected-skeleton-fill` は、既に作成された Issue node の draft adoption input を検査します。

これらの validation pass は、次のどれでもありません。

- canonical adoption completed
- reviewer pass
- execution-ready
- Issue finish

Issue planning skill は validation 結果を evidence として読み、正式 requirement / design / plan を作り、fresh `spec-reviewer` pass を通します。

## ローカル文脈証跡（Local-context evidence）

`local-context` で作った pack は lower-authority evidence です。
GitHub sync が未確認であること、どの local context を渡したか、採用判断の制約を `report.md` に残します。
