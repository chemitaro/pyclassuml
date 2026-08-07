---
種別: 実装計画書（Issue）
ID: "<ISS_ID>"
タイトル: "<ISS_TITLE>"
Issue Grade: "lite"
状態: "draft | approved | in-progress | completed"
作成者: "<YOUR_NAME>"
最終更新: "YYYY-MM-DD"
関連Requirement: ["requirement.md"]
関連Design: ["design.md"]
関連Report: ["report.md"]
親: ["<EPIC_ID>", "<INIT_ID>"]
---

# <ISS_ID> <ISS_TITLE> — Issue 実装計画書（Lite / チェックリスト実行（Checklist Execution））

この文書は、`lite` grade のIssueを安全に実行するための軽量な実装計画書である。

`lite` は、実装計画が不要であることを意味しない。
このIssueが軽量なチェックリストで完了可能である理由、変更範囲、検証項目、report証跡（report evidence）、等級引き上げ（grade escalation）条件を明示する。

---

## 0. 文書の位置づけ

### この文書が定義すること

- このIssueを `lite` として実行してよい理由
- 変更する対象
- 変更しない対象
- 実行する軽量チェックリスト
- 必要な検証方法
- report.md に残す証拠
- 完了条件
- `standard` 以上へ引き上げる条件

### この文書が定義しないこと

- 新しい要件
- 新しい設計判断
- 新しい実行時振る舞い（runtime behavior）
- public contract変更
- migration / compatibility strategy
- セキュリティ・プライバシー（security / privacy） design
- 詳細なTDD マイルストーン（Milestone）
- 詳細なRed-Green-Refactorサイクル

### 計画 Liteの前提（Lite Plan）

- 実行時振る舞い（runtime behavior）を変更しない
- public CLI / API / Event / Schema contractを変更しない
- ワークスペース scaffold構造を変更しない
- sync / validate / active / lifecycle挙動を変更しない
- `.meta.json`、`.assurance.json`、`.agent/*.json` の意味を変更しない
- migrationまたは既存ファイル変換を行わない
- セキュリティ・プライバシー（security / privacy） / secret / credentialに影響しない
- 切り戻し（rollback）が容易である
- 変更範囲が限定的である

---

## 1. 計画開始条件（Plan Readiness）

### 1.1 必須入力（Required Inputs）

| 作業成果物（Artifact） | 状態 | 確認事項 |
|---|---|---|
| `requirement.md` | 下書き / 承認済み（draft / approved） | 目的、受け入れ条件、軽量判定（Lite）材料がある |
| `design.md` | 下書き / 承認済み（draft / approved） | 証跡 Liteゲート（Lite Evidence Gate）、変更範囲、Stop条件がある |
| `report.md` | 存在 / 欠落（exists / missing） | 実行証拠の記録先がある |
| 親Epic / Initiative | 確認済み / N/A（reviewed / N/A） | 上位制約と矛盾しない |
| 関連docs / テンプレート（templates） | 確認済み / N/A（reviewed / N/A） | 変更対象が把握されている |

### 1.2 実行開始条件

- [ ] `requirement.md` に目的と受け入れ条件がある
- [ ] `design.md` で `lite` gradeが妥当と判断されている
- [ ] BlockingなOpen Questionがない
- [ ] 実行時振る舞い（runtime behavior）変更がない
- [ ] public contract変更がない
- [ ] migrationがない
- [ ] セキュリティ・プライバシー（security / privacy）影響がない
- [ ] 切り戻し（rollback）が容易である
- [ ] 変更対象と変更禁止対象が明確である
- [ ] report.md に証拠を記録できる

---

## 2. 実行 Lite戦略（Lite Execution Strategy）

このIssueでは、詳細なTDDサイクルではなく、軽量なチェックリスト実行を採用する。

```text
Lite 受け入れ範囲（Acceptance Envelope）
└── 変更チェックリスト（Change Checklist）
    ├── ベースライン確認（Baseline）
    ├── 最小変更
    ├── 軽量検証
    ├── 影響なし確認
    ├── 報告証跡（Report Evidence）記録
    └── 最終ゲート（Final Gate）
```

基本方針:

- 変更範囲を最小にする
- 設計判断を増やさない
- 実行時振る舞い（runtime behavior）を変更しない
- public contractを変更しない
- migrationを行わない
- 既存ユーザー作成物を変更しない
- 検証は軽量でよいが、検証しない理由を曖昧にしない
- 実行結果は `report.md` に記録する
- 軽量前提（Lite）を破る兆候があれば停止し、gradeを引き上げる

---

## 3. 範囲と変更面（対象範囲（Scope） and Change Surface）

### 3.1 許可変更面（Allowed Change Surface）

| 種別 | パス・対象（Path / Target） | 許可する変更 | 関連設計メモ（Design Note） |
|---|---|---|---|
| 文書（docs） | ... | 文言修正 / 説明追加 / 整理 | `LDES-...` |
| テンプレート（template） | ... | 文言修正 / コメント追加 / セクション軽微修正 | `LDES-...` |
| スキル（skill） | ... | 説明文の軽微修正 | `LDES-...` |
| テスト（test） | ... | 既存テストの追加実行 / 軽微な検査 | `LDES-...` |
| その他（other） | ... | ... | `LDES-...` |

### 3.2 禁止変更（Forbidden Changes）

| 対象 | 禁止理由 | 必要になった場合の対応 |
|---|---|---|
| 実行時振る舞い（runtime behavior） | 範囲外（lite） | 等級 standard へ引き上げ |
| 公開 CLI 契約（public CLI contract） | 範囲外（lite） | 等級 strict へ引き上げ |
| テンプレート契約（template contract） | 範囲外（lite） | 等級 strict へ引き上げ |
| ワークスペース scaffold structure | 範囲外（lite） | 等級 strict へ引き上げ / critical |
| メタデータ意味論（metadata semantics） | 範囲外（lite） | 等級 strict へ引き上げ |
| 移行（migration） | 範囲外（lite） | 等級 strict へ引き上げ / critical |
| セキュリティ・プライバシー（security / privacy） | 範囲外（lite） | 等級 critical へ引き上げ |
| ユーザー作成物（user-authored artifacts） | 範囲外（lite） | 停止して再計画 |

### 3.3 提供側・利用側反映（Provider / Consumer）

| 対象 | 変更要否 | 対応 |
|---|---|---|
| `src/spec_dock/assets/...` | はい / いいえ / 不明（yes / no / unknown） | ... |
| ワークスペース（root `spec-dock/...`） | はい / いいえ / 不明（yes / no / unknown） | ... |

### 3.4 ロールバックの容易性（Rollback）

- rollback方法:
  - commit revert / file restore / N/A / other
- 切り戻し（rollback）困難な点:
  - なし / ...
- 切り戻し（rollback）困難な点がある場合の対応:
  - escalate / split issue / redesign

---

## 4. 受け入れ範囲（Acceptance Envelope）

### 4.1 受け入れ成果（Acceptance Outcomes）

| 成果識別子（Outcome ID） | 内容 | 関連AC | 関連設計メモ（Design Note） | 完了証拠 |
|---|---|---|---|---|
| OUT-001 | ... | `AC-...` | `LDES-...` | `EVD-...` |
| OUT-002 | ... | `AC-...` | `LDES-...` | `EVD-...` |

### 4.2 起きてはいけないこと（Must Not Happen）

| 識別子（ID） | 内容 | 確認方法 |
|---|---|---|
| MNH-001 | 実行時振る舞い（runtime behavior）が変わらない | 点検 / tests / N/A |
| MNH-002 | 公開契約（public contract）が変わらない | 点検 / grep / N/A（inspect / grep / N/A）（確認方法） |
| MNH-003 | 移行（migration）が発生しない | 点検（inspect） |
| MNH-004 | セキュリティ・プライバシー（security/privacy）影響がない | 点検（inspect） |
| MNH-005 | 変更対象外ファイルを触らない | 差分review（diff review） |

---

## 5. 軽量クロージャ一覧（Lightweight クロージャ（Closure） Index）

| クロージャ識別子（Closure ID） | 要件識別子（Requirement ID） | 設計メモ識別子（Design Note ID） | 閉じる内容 | 検証レベル（Verification Level） | 報告証跡（Report Evidence） |
|---|---|---|---|---|---|
| LCLOS-001 | AC-001 | LDES-001 | ... | 文書 / 点検 / grep | `report.md#...` |
| LCLOS-002 | AC-002 | LDES-002 | ... | テンプレート / 手動 | `report.md#...` |
| LCLOS-003 | CON-001 | LDES-003 | ... | 点検（inspect） | `report.md#...` |

---

## 6. 変更チェックリスト（Change Checklist）

### 6.1 ベースライン確認（Baseline）

| 確認識別子（ID）Check ID） | 内容 | 方法 | 報告証跡（Report Evidence） |
|---|---|---|---|
| BASE-001 | 現在の対象ファイルを確認する | 点検（inspect） | `report.md#...` |
| BASE-002 | 変更前の表現・構造を確認する | 点検（inspect） / grep | `report.md#...` |
| BASE-003 | 軽量前提（Lite）を再確認する | チェックリスト（checklist） | `report.md#...` |

### 6.2 変更チェックリスト

| ステップID（Step ID） | 内容 | 対象 | 完了条件 | 報告証跡（Report Evidence） |
|---|---|---|---|---|
| LSTEP-001 | ... | ... | ... | `report.md#...` |
| LSTEP-002 | ... | ... | ... | `report.md#...` |
| LSTEP-003 | ... | ... | ... | `report.md#...` |

### 6.3 変更中に守ること

- [ ] 許可変更面（Allowed Change Surface）外を変更しない
- [ ] runtime logicを変更しない
- [ ] public contractを変更しない
- [ ] migrationを発生させない
- [ ] セキュリティ・プライバシー（security / privacy）に影響する内容を追加しない
- [ ] ユーザー作成物（user-authored artifact）を変更しない
- [ ] 判断が必要になったら作業を止める

---

## 7. 任意の軽量テスト・証跡（Optional Lightweight Test / Evidence）

LiteではTDDサイクルは原則不要だが、軽量テストまたは検査を必要に応じて計画する。

### 7.1 Red・Green の扱い（Red / Green）

- Red-Green-Refactor:
  - required / not-required / not-applicable
- 理由:
  - ...
- 代替証拠:
  - 文書点検（docs inspect） / grep / existing テスト / 手動（tests / 手動（manual）） review / other

### 7.2 既存テストの実行

| テスト識別子（ID）Test ID） | コマンド（Command） | 期待結果 | 報告証跡（Report Evidence） |
|---|---|---|---|
| T-001 | `...` | pass | `report.md#...` |

### 7.3 点検・検索・手動証跡（Inspect / Grep / Manual Evidence）

| 証跡ID（Evidence ID） | 対象 | 方法 | 期待結果 | 報告証跡（Report Evidence） |
|---|---|---|---|---|
| EVD-001 | ... | 点検（inspect） | ... | `report.md#...` |
| EVD-002 | ... | 検索（grep） | ... | `report.md#...` |
| EVD-003 | ... | 手動（manual） review | ... | `report.md#...` |

---

## 8. 検証 Lite段階（Lite 検証（Verification） Ladder）

| レベル（Level） | 名称 | 目的 | コマンド（Command） / Evidence |
|---|---|---|---|
| L1 | 差分点検（Diff Inspect） | 差分が意図どおりか確認 | `git diff` / 手動（manual） |
| L2 | 対象grep（Targeted Grep） | 旧表現・参照漏れ確認 | `grep ...` |
| L3 | 文書Markdown点検（Docs / Markdown Inspect） | 文書構造確認 | 手動（manual） / markdown確認（markdown check） |
| L4 | テンプレート点検（Template Inspect） | テンプレート内容確認 | 手動（manual） / 低コストなら生成（generate if cheap） |
| L5 | 既存テスト（Existing Tests） | 既存テストの軽量実行 | `...` |
| L6 | 最終 Lite ゲート（Final Lite Gate） | 完了条件確認 | チェックリスト（checklist） |

---

## 9. 文書・テンプレート・スキル影響（Docs / Template / Skill 影響（Impact））

| 対象 | 影響 | 必要な対応 | 報告証跡（Report Evidence） |
|---|---|---|---|
| 文書（docs） | はい / いいえ / 不明（yes / no / unknown） | ... | `report.md#...` |
| テンプレート（templates） | はい / いいえ / 不明（yes / no / unknown） | ... | `report.md#...` |
| スキル群（skills） | はい / いいえ / 不明（yes / no / unknown） | ... | `report.md#...` |
| ワークフロー文書（workflow docs） | はい / いいえ / 不明（yes / no / unknown） | ... | `report.md#...` |
| 提供資産（provider assets） | はい / いいえ / 不明（yes / no / unknown） | ... | `report.md#...` |
| 検証workspace（dogfooding workspace） | はい / いいえ / 不明（yes / no / unknown） | ... | `report.md#...` |

Consistency Check:

- [ ] 用語が既存docsと矛盾しない
- [ ] templateとdocsが矛盾しない
- [ ] skill導線とtemplateが矛盾しない
- [ ] 古い名称や古い手順が残っていない
- [ ] provider assetとconsumer workspaceの反映要否を判断した

---

## 10. 報告証跡対応（報告証跡（Report Evidence） Mapping）

### 10.1 証跡記録先（Evidence Destinations）

| 証跡ID（Evidence ID） | 対象 | 報告節（Report Section） | 記録内容 |
|---|---|---|---|
| EVD-001 | 基準（baseline） / current state | `report.md#...` | 変更前の対象確認 |
| EVD-002 | 差分点検（diff inspect） | `report.md#...` | 変更差分 |
| EVD-003 | 検索 / 参照確認（grep / reference check） | `report.md#...` | 旧表現・参照漏れ確認 |
| EVD-004 | 文書・テンプレート（docs / template） 点検（inspect） | `report.md#...` | 整合性確認 |
| EVD-005 | 既存テスト（existing tests） | `report.md#...` | 必要な場合のテスト結果 |
| EVD-006 | 最終lite gate（final lite gate） | `report.md#...` | 完了判定 |

### 10.2 Report記録ルール

- 実施したcheckの結果はreport.mdに記録する
- 実施しなかったcheckは理由をreport.mdに記録する
- 軽量前提（Lite）を破る発見があればreport.mdに記録し、gradeを引き上げる
- plan.mdは観測実績の正本にしない

---

## 11. 停止・引き上げルール（Stop / Escalation Rules）

### 即時停止条件（Immediate Stop Conditions）

- [ ] 実行時振る舞い（runtime behavior）変更が必要になった
- [ ] public CLI / API / Event / Schema contract変更が必要になった
- [ ] テンプレート契約（template contract）変更が必要になった
- [ ] sync / validate / active / lifecycleに影響すると分かった
- [ ] `.meta.json`、`.assurance.json`、`.agent/*.json` の意味変更が必要になった
- [ ] migrationまたは既存ファイル変換が必要になった
- [ ] セキュリティ・プライバシー（security / privacy） / secret / credentialに影響すると分かった
- [ ] 既存テストの期待値変更が必要になった
- [ ] 要件の期待値を変更したくなった
- [ ] 許可変更面（Allowed Change Surface）外の変更が必要になった
- [ ] ユーザー作成物（user-authored artifact）に触る必要が出た
- [ ] rollbackが容易ではないと分かった

### 停止後の対応（Stop）

| 状況 | 対応 |
|---|---|
| 小さなruntime変更が必要 | 等級 standard へ引き上げ |
| 公開契約（public contract）変更が必要 | 等級 strict へ引き上げ |
| 移行（migration）が必要 | 等級 strict へ引き上げ / critical |
| セキュリティ・プライバシー（security / privacy）影響 | 等級 critical へ引き上げ |
| 要件が曖昧 | 要件文書（requirement.md）へ戻す |
| 設計判断が必要 | 設計書（design.md）を更新し、等級standard以上へ |
| 対象範囲外変更（対象範囲（Scope））が必要 | 後続issue（後続（follow-up） issue）へ分割 |

---

## 12. 最終 Lite ゲート（Final Lite Gate）

### 12.1 必須最終確認（Required Final Checks）

| Check | コマンド（Command） / Evidence | 期待結果（Expected） | 報告先（Report Destination） |
|---|---|---|---|
| Requirement closure | 点検（inspect） closure index | all lite closures closed | `report.md#...` |
| Design note compliance | 点検（inspect） LDES IDs | 違反なし | `report.md#...` |
| 差分review（Diff review） | `git diff` / 手動（manual） | only allowed changes | `report.md#...` |
| 実行時影響確認（Runtime impact check） | 点検 / tests / N/A | no 実行時変更（runtime change） | `report.md#...` |
| Contract impact check | 点検（inspect） | 公開 contract 変更なし | `report.md#...` |
| Migration check | 点検（inspect） | migration なし | `report.md#...` |
| Security/privacy check | 点検（inspect） | no impact | `report.md#...` |
| Docs/template consistency | 点検（inspect） / grep | consistent | `report.md#...` |
| Existing tests if needed | `...` | pass / N/A | `report.md#...` |

### 12.2 最終終了契約（Final Exit Contract）

- [ ] すべてのLite クロージャ識別子（Closure ID）が完了している
- [ ] すべての変更チェックリスト（Change Checklist）項目が完了している
- [ ] 許可変更面（Allowed Change Surface）外の変更がない
- [ ] 禁止変更（Forbidden Changes）に触れていない
- [ ] 実行時振る舞い（runtime behavior）変更がない
- [ ] public contract変更がない
- [ ] migrationがない
- [ ] セキュリティ・プライバシー（security / privacy）影響がない
- [ ] 切り戻し（rollback）が容易である
- [ ] 文書・テンプレート（docs / template） / skill整合性を確認した
- [ ] 必要な軽量検証を実施した
- [ ] report.mdに証拠を記録した
- [ ] `standard` 以上へ引き上げる条件に該当していない
- [ ] 後続（follow-up）が必要な場合、明示されている

---

## 13. フォローアップ候補（Follow-up Candidates）

| 識別子（ID） | 内容 | 理由 | 推奨先 |
|---|---|---|---|
| FU-001 | ... | ... | Issue / Epic / ADR |
| FU-002 | ... | ... | Issue / Epic / ADR |

---

## 14. 計画 Lite承認チェックリスト（Lite Plan Approval Checklist）

### 入力整合性

- [ ] requirement.mdのAC / CONがLite クロージャ（Closure） Indexへ対応している
- [ ] design.mdの固定軽量設計メモ（Fixed Lightweight Design Notes）がPlanに反映されている
- [ ] design.mdの停止・引き上げ条件（Stop / Escalation Triggers）がPlanに反映されている
- [ ] 上位Epic / Initiativeの制約と矛盾しない

### 計画 Lite品質

- [ ] 変更チェックリスト（Change Checklist）が具体的である
- [ ] 許可変更面（Allowed Change Surface）が明確である
- [ ] 禁止変更（Forbidden Changes）が明確である
- [ ] 検証方法が軽量だが十分である
- [ ] report.mdへの証拠記録先がある
- [ ] TDD不要または限定的でよい理由が明確である

### 妥当性 Lite

- [ ] 実行時振る舞い（runtime behavior）変更がない
- [ ] public contract変更がない
- [ ] migrationがない
- [ ] セキュリティ・プライバシー（security / privacy）影響がない
- [ ] 切り戻し（rollback）が容易である
- [ ] 軽量前提（Lite）を破る既知リスクがない

---

## 15. 変更履歴

| 日付（Date） | 変更（Change） | 理由（Reason） | 作成者（Author） |
|---|---|---|---|
| YYYY-MM-DD | 初稿（Initial draft） | ... | ... |
