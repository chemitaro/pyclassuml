---
種別: 要件定義書（Issue）
ID: "<ISS_ID>"
タイトル: "<ISS_TITLE>"
関連GitHub: ["<GITHUB_ISSUE_NUMBER_OR_URL>"]
状態: "draft | approved"
作成者: "<YOUR_NAME>"
最終更新: "YYYY-MM-DD"
親: ["<EPIC_ID>", "<INIT_ID>"]
---

# <ISS_ID> <ISS_TITLE> — Issue 要件定義

この文書は、Issueで実現すべき **観測可能な成果、制約、受け入れ条件、リスク信号** を定義する。

この文書では、実装方法、クラス設計、メソッド設計、TDDの実行順序を決定しない。
それらは `design.md` と `plan.md` で扱う。

---

## 0. 文書の位置づけ

### この文書が定義すること

- このIssueで何を実現するか
- なぜこのIssueが必要か
- 誰または何が影響を受けるか
- 完了後に外部から何を観測できるか
- 何を変更対象に含めるか
- 何を変更対象に含めないか
- どの受け入れ条件を満たす必要があるか
- どの失敗・例外・境界条件を考慮する必要があるか
- どのIssue gradeの設計書・実装計画書を使うべきかを判断する材料

### この文書が定義しないこと

- Aggregate、Entity、Value Objectの具体設計
- Application Service、Repository、Port、Adapterの具体設計
- API、Event、DB Migrationの詳細設計
- テストケースの実装順序
- Red-Green-Refactorの具体サイクル
- 変更ファイル一覧
- privateメソッドや内部ヘルパーの構造

---

## 1. 概要

### 1.1 目的

このIssueで達成したい目的を1〜3文で記述する。

- 目的:
  - ...

### 1.2 観測可能な成果

このIssueが完了したとき、利用者、外部システム、開発者、またはテストから何が観測できるかを記述する。

コード要素ではなく、振る舞い・状態・契約・出力・証拠として書く。

- 完了後に観測できること:
  - ...
- 完了後に観測できてはいけないこと:
  - ...

### 1.3 このIssueの種類

該当するものに印を付ける。

- [ ] 新規振る舞いの追加
- [ ] 既存振る舞いの変更
- [ ] 既存振る舞いの不具合修正
- [ ] 仕様・文書の明確化
- [ ] テンプレート変更
- [ ] CLI / script 挙動変更
- [ ] workflow / skill / agent導線の変更
- [ ] metadata / sync / validate / lifecycle の変更
- [ ] migration / compatibility を伴う変更
- [ ] セキュリティ・プライバシー（security / privacy） / authorization に関係する変更
- [ ] その他:
  - ...

---

## 2. 背景・現状

### 2.1 現在の状態

- 現在の挙動:
  - ...
- 現在の制約:
  - ...
- 現在の問題:
  - ...

### 2.2 問題が発生する状況

再現可能な場合は、手順と観測点を書く。

- 再現手順:
  1. ...
  2. ...
  3. ...

- 観測点:
  - UI:
    - ...
  - CLI:
    - ...
  - ファイル:
    - ...
  - GitHub:
    - ...
  - DB:
    - ...
  - ログ:
    - ...
  - テスト:
    - ...
  - その他:
    - ...

### 2.3 根拠・情報源

このIssueの根拠となる情報源を列挙する。

- 上位要件:
  - ...
- 上位設計:
  - ...
- 関連Issue:
  - ...
- 関連ADR:
  - ...
- 関連PR:
  - ...
- 関連コード:
  - ...
- 関連テンプレート:
  - ...
- 関連docs:
  - ...
- 作業成果物・議論（artifacts / discussions） / research:
  - ...
- その他:
  - ...

---

## 3. 親スコープと継承条件

このIssueが属する上位スコープを記述する。

### 3.1 親Initiative

- Initiative ID:
  - ...
- 関連するInitiative requirement IDs:
  - ...
- 関連するInitiative design IDs:
  - ...
- このIssueが継承する戦略的制約:
  - ...

### 3.2 親Epic

- Epic ID:
  - ...
- 関連するEpic requirement IDs:
  - ...
- 関連するEpic design IDs:
  - ...
- このIssueが継承するモデル・境界・契約:
  - ...

### 3.3 このIssueで再定義してはいけないもの

上位設計または既存仕様により、このIssueでは変更しないものを明示する。

- 変更しない境界:
  - ...
- 変更しない契約:
  - ...
- 変更しない責任分担:
  - ...
- 変更しないワークフロー:
  - ...
- 変更しない既存挙動:
  - ...

---

## 4. 関係者・開始条件・利用シナリオ（Actor / Trigger）

### 4.1 主な関係者（Actor）

このIssueの振る舞いに関与する人、外部システム、agent、CLI利用者、workflow上の役割を記述する。

| 関係者（Actor） | 役割 | このIssueとの関係 |
|---|---|---|
| ... | ... | ... |

### 4.2 開始条件（Trigger）

このIssueの対象となる振る舞いが何によって開始されるかを記述する。

- [ ] 人間の操作
- [ ] CLIコマンド
- [ ] GitHub Issue / PR 操作
- [ ] agent skill 実行
- [ ] script 実行
- [ ] template scaffold
- [ ] sync / validate / lifecycle 操作
- [ ] event / webhook / 外部入力
- [ ] その他:
  - ...

### 4.3 代表シナリオ

#### シナリオ SC-001:

- Actor:
  - ...
- 前提:
  - ...
- 操作 / 開始条件（Trigger）:
  - ...
- 期待される結果:
  - ...
- 観測点:
  - ...

#### シナリオ SC-002:

- Actor:
  - ...
- 前提:
  - ...
- 操作 / 開始条件（Trigger）:
  - ...
- 期待される結果:
  - ...
- 観測点:
  - ...

#### シナリオ SC-XXX:

- 必要に応じて `SC-003` 以降を連番で追加する。`XXX` は実IDへ置換するか削除する。

---

## 5. スコープ

### 5.1 対象範囲（In 対象範囲（Scope））

このIssueで必ず実現することを列挙する。

- ...
- ...

### 5.2 対象外（Out of 対象範囲（Scope））

このIssueでは実現しないことを列挙する。

- ...
- ...

### 5.3 変更しないもの（Unchanged / Must Not Change）

関連はあるが、このIssueで変更してはいけないものを列挙する。

- ...
- ...

### 5.4 判断が必要な境界

このIssueに含めるか、上位上位文書（Epic・Initiative・ADR）へ昇格すべきか判断が必要なものを列挙する。

| 項目 | 現時点の扱い | 昇格先候補 | 備考 |
|---|---|---|---|
| ... | 含める / 除外する / 不明（include / exclude / unknown） | 上位文書（Epic・Initiative・ADR） | ... |

---

## 6. 要求される振る舞い

このIssueで成立させたい振る舞いを、Given / When / Thenに近い形で記述する。

### 振る舞い BH-001:

- Given:
  - ...
- When:
  - ...
- Then:
  - ...
- And:
  - ...
- 観測点:
  - ...

### 振る舞い BH-002:

- Given:
  - ...
- When:
  - ...
- Then:
  - ...
- And:
  - ...
- 観測点:
  - ...

### 振る舞い BH-XXX:

- 必要に応じて `BH-003` 以降を連番で追加する。`XXX` は実IDへ置換するか削除する。

---

## 7. 受け入れ条件

各受け入れ条件にはIDを付与する。
後続の `design.md`、`plan.md`、`report.md` から参照できる粒度にする。

### 受け入れ条件 AC-001:

- 説明:
  - ...
- Actor / 開始条件（Trigger）:
  - ...
- 前提:
  - ...
- 操作:
  - ...
- 期待結果:
  - ...
- 観測点:
  - ...
- 関連する振る舞い:
  - `BH-...`
- 関連する制約:
  - `CON-...`

### 受け入れ条件 AC-002:

- 説明:
  - ...
- Actor / 開始条件（Trigger）:
  - ...
- 前提:
  - ...
- 操作:
  - ...
- 期待結果:
  - ...
- 観測点:
  - ...
- 関連する振る舞い:
  - `BH-...`
- 関連する制約:
  - `CON-...`

### 受け入れ条件 AC-XXX:

- 必要に応じて `AC-003` 以降を連番で追加する。`XXX` は実IDへ置換するか削除する。

---

## 8. 例外・エッジケース

正常系だけでなく、拒否、未対応、重複、競合、不正入力、部分失敗などを記述する。

### 例外・エッジケース EC-001:

- 条件:
  - ...
- 期待される扱い:
  - ...
- 状態変更:
  - あり / なし / unknown
- 観測点:
  - ...
- 関連する受け入れ条件:
  - `AC-...`

### 例外・エッジケース EC-002:

- 条件:
  - ...
- 期待される扱い:
  - ...
- 状態変更:
  - あり / なし / unknown
- 観測点:
  - ...
- 関連する受け入れ条件:
  - `AC-...`

---

## 9. 入力・出力・契約の例

該当する場合のみ記述する。
ここでは正確なAPI / Event / Schema設計を固定しすぎない。
公開契約になる場合、詳細は `design.md` で定義する。

### 例 EX-001: 入力例

```text
...
```

### 例 EX-002: 出力例

```text
...
```

### 例 EX-003: エラー例

```text
...
```

### 契約上の注意

- 公開APIに影響する:
  - はい / いいえ / 不明（yes / no / unknown）
- CLI contractに影響する:
  - はい / いいえ / 不明（yes / no / unknown）
- Template contractに影響する:
  - はい / いいえ / 不明（yes / no / unknown）
- Metadata / generated index に影響する:
  - はい / いいえ / 不明（yes / no / unknown）
- Event / message contract に影響する:
  - はい / いいえ / 不明（yes / no / unknown）

---

## 10. 非機能要求・品質要求

このIssueに固有の品質要求のみ記述する。
システム全体の一般原則は上位文書を参照する。

### 10.1 互換性

- 後方互換性が必要:
  - はい / いいえ / 不明（yes / no / unknown）
- 既存workspaceへの影響:
  - ...
- 既存Issue / Epic / Initiativeへの影響:
  - ...
- 既存CLI利用者への影響:
  - ...
- 既存テンプレート利用者への影響:
  - ...

### 10.2 移行性

- 移行（migration）が必要:
  - はい / いいえ / 不明（yes / no / unknown）
- 移行対象:
  - ...
- 既存データ / 既存ファイルへの影響:
  - ...
- 旧形式との共存が必要:
  - はい / いいえ / 不明（yes / no / unknown）

### 10.3 可観測性

- 追加・変更すべきログ:
  - ...
- 追加・変更すべき検証出力:
  - ...
- 追加・変更すべきreport証跡（report evidence）:
  - ...
- 追加・変更すべきdiagnostic:
  - ...

### 10.4 性能・スケール

- 実行時間への影響:
  - ...
- 大量ファイル / 大量Issueでの影響:
  - ...
- GitHub API / 外部I/Oへの影響:
  - ...

### 10.5 セキュリティ・プライバシー

- 認証・認可への影響:
  - はい / いいえ / 不明（yes / no / unknown）
- secret / token / credentialsへの影響:
  - はい / いいえ / 不明（yes / no / unknown）
- 個人情報・機微情報への影響:
  - はい / いいえ / 不明（yes / no / unknown）
- ログやreportに出してはいけない情報:
  - ...

---

## 11. 制約

### 制約 CON-001:

- 種別:
  - business / domain / architecture / compatibility / security / operation / other
- 内容:
  - ...
- 根拠:
  - ...
- 変更可能性:
  - fixed / negotiable / unknown

### 制約 CON-002:

- 種別:
  - business / domain / architecture / compatibility / security / operation / other
- 内容:
  - ...
- 根拠:
  - ...
- 変更可能性:
  - fixed / negotiable / unknown

---

## 12. 依存関係

### 12.1 前提となるIssue / PR / 作業

| 種別 | 識別子・リンク（ID / Link） | 必要な理由 | 状態 |
|---|---|---|---|
| 課題（Issue） | ... | ... | ... |
| PR | ... | ... | ... |
| ADR（意思決定記録） | ... | ... | ... |
| 文書（Docs） | ... | ... | ... |

### 12.2 後続作業

このIssueが完了した後に必要になる可能性がある作業を記述する。

| 種別 | 内容 | 理由 | 必須 / 任意 |
|---|---|---|---|
| ... | ... | ... | ... |

### 12.3 ブロッカー

- ...
- ...

---

## 13. 等級（Grade）判定材料

このセクションは、どのIssue gradeの `design.md` / `plan.md` テンプレートを使うかを判断するための材料である。

内部profile名は `lite / standard / strict / critical` を使用する。

### 13.1 推奨 Issue 等級（Issue Grade）

現時点の推奨を一つ選ぶ。

- [ ] `lite`
- [ ] `standard`
- [ ] `strict`
- [ ] `critical`
- [ ] 未判断

### 13.2 推奨理由

- 推奨grade:
  - ...
- 理由:
  - ...
- gradeを上げる可能性がある条件:
  - ...
- gradeを下げられる条件:
  - ...

### 13.3 リスク事実（Risk Facts）

値は `true / false / unknown` のいずれかで記述する。
`unknown` が残る場合、原則として軽量gradeへ寄せない。

| リスク事実（Risk Fact） | 値（Value） | 理由（Reason） |
|---|---|---|
| `docs_only_change` | 不明（unknown） | ... |
| `explicit_lite_opt_in` | 偽（false） | ... |
| `lite_evidence_gate_passed` | 偽（false） | ... |
| `runtime_behavior_change` | 不明（unknown） | ... |
| `public_contract_change` | 不明（unknown） | ... |
| `migration_or_persistence_change` | 不明（unknown） | ... |
| `rollback_difficulty_high` | 不明（unknown） | ... |
| `security_or_privacy_sensitive` | 不明（unknown） | ... |

### 13.4 等級引き上げ条件（Grade Escalation Triggers）

#### `strict` 以上を検討する条件

- [ ] 公開CLI挙動を変更する
- [ ] 公開API / Event / Schema / generated metadata を変更する
- [ ] テンプレート契約（template contract） を変更する
- [ ] ワークスペース scaffold結果を変更する
- [ ] sync / validate / active / lifecycle 挙動を変更する
- [ ] migrationまたは既存ファイル変換が必要
- [ ] 既存workspaceとの互換性が必要
- [ ] rollbackが難しい
- [ ] 複数Issue / 複数Epicに影響する
- [ ] agent skill / workflow policy を変更する
- [ ] その他:
  - ...

#### `critical` を検討する条件

- [ ] セキュリティ・プライバシー（security / privacy） / secret / credential に関係する
- [ ] 破壊的変更またはデータ損失リスクがある
- [ ] GitHub上の状態変更を伴う
- [ ] 既存workspace layoutを移行する
- [ ] 大量ファイルの自動更新を伴う
- [ ] 手動確認なしで進めると危険
- [ ] rollback不能またはforward-only migrationになる
- [ ] その他:
  - ...

#### `lite` を検討できる条件

すべて満たす場合のみ `lite` を検討できる。

- [ ] 文書のみ（docs-only） または非runtime変更である
- [ ] 公開contractを変更しない
- [ ] migration / persistence変更がない
- [ ] 切り戻し（rollback）が容易である
- [ ] セキュリティ・プライバシー（security / privacy） に影響しない
- [ ] 実行時挙動を変更しない
- [ ] liteを明示的に選ぶ理由がある
- [ ] lite evidence gateを満たせる

---

## 14. 設計への引き渡し

このセクションは `design.md` を作成するための入力である。
ここでは設計を決定しすぎず、設計で検討すべき論点を整理する。

### 14.1 設計で必ず扱うべき論点

- ...
- ...

### 14.2 責任所有者が未確定のもの

| 論点 | 候補 | 未確定理由 |
|---|---|---|
| ... | ... | ... |

### 14.3 境界が未確定のもの

| 境界 | 候補 | 未確定理由 |
|---|---|---|
| ... | ... | ... |

### 14.4 契約影響が未確定のもの

| 契約 | 影響の可能性 | 未確定理由 |
|---|---|---|
| ... | ... | ... |

### 14.5 上位へ昇格すべき可能性がある判断

| 判断 | 昇格先候補 | 理由 |
|---|---|---|
| ... | 上位文書（Epic・Initiative・ADR） | ... |

---

## 15. 実装計画への引き渡し

このセクションは `plan.md` を作成するための入力である。
ここでは実装順序を固定せず、計画で分解すべき成果・検証対象を整理する。

### 15.1 計画で分解すべき成果

- ...
- ...

### 15.2 検証が必要な観測点

- テスト:
  - ...
- CLI実行:
  - ...
- ファイル生成:
  - ...
- 文書・テンプレート（docs / template）:
  - ...
- sync / validate:
  - ...
- GitHub連携:
  - ...
- 手動確認:
  - ...

### 15.3 TDDが必要な振る舞い候補

振る舞い変更がある場合のみ記述する。

| 候補識別子（ID） | 振る舞い | 関連AC | 備考 |
|---|---|---|---|
| B-CAND-001 | ... | `AC-...` | ... |
| B-CAND-XXX | 必要に応じて連番で追加する。`XXX` は実IDへ置換するか削除する。 | `AC-...` | ... |

### 15.4 TDD不要または限定的でよい理由

文書のみ（docs-only）やtemplate-onlyなど、TDDを限定してよい場合に記述する。

- ...
- ...

---

## 16. 文書・作業成果物（docs / artifacts）影響

### 16.1 更新が必要な正本文書（正本（canonical） docs）

| パス（Path） | 更新理由 | 必須 / 任意 |
|---|---|---|
| ... | ... | ... |

### 16.2 更新が必要なテンプレート（templates）

| パス（Path） | 更新理由 | 必須 / 任意 |
|---|---|---|
| ... | ... | ... |

### 16.3 更新が必要なスキル・ワークフロー（skills / workflow）

| パス（Path） | 更新理由 | 必須 / 任意 |
|---|---|---|
| ... | ... | ... |

### 16.4 参照すべき作業成果物・議論（artifacts / discussions）

| パス（Path） | 用途 | 正本（canonical）へ昇格する必要 |
|---|---|---|
| ... | ... | はい / いいえ / 不明（yes / no / unknown） |

---

## 17. 用語

このIssueで使う用語を定義する。
上位文書に定義済みの場合は参照する。

| 識別子（ID） | 用語 | 定義 | 備考 |
|---|---|---|---|
| TERM-001 | ... | ... | ... |
| TERM-XXX | 必要に応じて連番で追加する。`XXX` は実IDへ置換するか削除する。 | ... | ... |

---

## 18. 未確定事項

未確定事項は、実装計画で吸収しない。
要件、設計、計画のどの段階で解決すべきかを明示する。

### 未確定事項 Q-001:

- 質問:
  - ...
- 選択肢:
  - A:
    - ...
  - B:
    - ...
- 推奨案:
  - ...
- 影響範囲:
  - requirement / design / plan / implementation / test / release
- 解決期限:
  - before design / before plan / before implementation / can defer
- 解決者:
  - ...

### 未確定事項 Q-002:

- 質問:
  - ...
- 選択肢:
  - A:
    - ...
  - B:
    - ...
- 推奨案:
  - ...
- 影響範囲:
  - requirement / design / plan / implementation / test / release
- 解決期限:
  - before design / before plan / before implementation / can defer
- 解決者:
  - ...

---

## 19. 要件承認チェック

`approved` にする前に確認する。

- [ ] 目的が1〜3文で明確に説明されている
- [ ] 観測可能な成果が書かれている
- [ ] 対象範囲（In 対象範囲（Scope）） / 対象外（Out of 対象範囲（Scope）） / Unchanged が区別されている
- [ ] 受け入れ条件にIDが付いている
- [ ] 主要な例外・エッジケースが記載されている
- [ ] 上位Initiative / Epicとの関係が記載されている
- [ ] 変更してはいけない上位制約が明示されている
- [ ] grade判定材料が記載されている
- [ ] `unknown` のrisk factが残っている場合、その理由が書かれている
- [ ] 設計で扱うべき論点が整理されている
- [ ] 実装計画で分解すべき成果が整理されている
- [ ] 未確定事項の解決段階が明示されている
- [ ] Issue内で決めるべきでない判断が上位へ昇格されている
- [ ] 要件定義書に実装手順やTDDサイクルを書き込んでいない

---

## 20. 変更履歴

| 日付（Date） | 変更（Change） | 理由（Reason） | 作成者（Author） |
|---|---|---|---|
| YYYY-MM-DD | 初稿（Initial draft） | ... | ... |
