# 判断配置ガイド（Decision Routing Authoring Guide）

このガイドは、authoring agent が execution handoff 前に発見事項の配置先を判断するための参照です。Workflow docs は入口ルールを持ち、この文書は再利用できる例と good / bad routing pattern を持ちます。Templates と skills は薄く保ち、生成 artifact へ例を複製せず、この文書へ link します。

Scope ownership、decision radius、authority flow の共通定義は [authoring/scope-layering.md](scope-layering.md) を authoritative reference とします。この文書は routing 例を補うものであり、責務表を複製しません。

## 配置ルール（Routing rule）

未来の作業を隠さずに判断を所有できる、最小の durable scope へ配置します。
Issue-local / Epic / Initiative のどれが owning scope か迷う場合は、先に [authoring/scope-layering.md](scope-layering.md) の ownership と authority flow を確認し、そのうえで下の routing rule を適用します。

| 発見種別（finding type） | 配置先（destination） | 使う条件（use when） | 引き渡し結果（handoff result） |
|---|---|---|---|
| 単一 Issue の実装判断（Issue-local implementation tradeoff） | 単一 Issue | 1つの implementation slice だけに影響し、可逆または issue-local な判断である。 | 記録先は Issue design / plan / report とし、Issue が executable のままなら継続する。 |
| 複数 Issue の設計背骨（Cross-issue design backbone） | 上位 Epic | 対象は Issue 分割、ownership boundary、dependency direction、shared component behavior、workflow policy へ複数 Issue にまたがって影響する。 | 実行前に Epic artifact を更新する、または Epic-scope follow-up を作成する。 |
| 複数 Epic の運用判断（Cross-epic operating decision） | 上位 Initiative | 複数 Epic、investment scope、success metric、product direction、operating model に影響する。 | その判断に依存する Epic / Issue decomposition 前に Initiative artifact を更新する、または Initiative-scope follow-up を作成する。 |
| 長期 architecture 判断（Long-lived architecture decision） | ADR | 1つの scope tree を超えて再利用され、独立して発見できる durable decision として残すべきである。 | 記録先として ADR candidate を作成または更新し、accepted outcome を影響 artifact から link する。 |
| 判断根拠不足（Missing source of truth） | 確認質問（Clarification） | 利用可能な source から scope、acceptance、non-scope、owner intent、priority を判断できない。 | 調査後は clarification へ戻して essential question を1つ聞く。 |

## 汎用例（Generic examples）

| 発見（finding） | 配置（route） | 理由（why） |
|---|---|---|
| 1つの Issue が公開挙動を保ったまま同等の helper 名を選ぶ。 | 単一 Issue | 判断は局所的で、分解や durable policy を変えない。 |
| 複数 Issue が安全に実装へ進む前に、同じ ownership boundary を固定する必要がある。 | 上位 Epic | 境界は cross-issue design backbone である。 |
| 提案された変更が複数 Epic の対象 team や product area を変える。 | 上位 Initiative | これは investment scope と operating model を変える判断である。 |
| 保存方式または integration style を、将来の unrelated work の default にしたい。 | ADR | 長期に残り、現在の tree 外からも発見できる必要がある。 |
| 表題上は実装を求めているが、source 間で必要な挙動が矛盾している。 | 確認質問（Clarification） | 実行すると agent が acceptance criteria を作り出す必要が出てしまう。 |

## 良いパターン（Good patterns）

- good: 可逆な local implementation choice は Issue に残し、promotion 不要の理由を report evidence に記録する。
- good: Cross-issue dependency direction は、それを前提に issue plan を書く前に Epic へ昇格する。
- good: Cross-epic success metric や responsibility boundary は、新しい Epic 分割の前に Initiative へ昇格する。
- good: 将来の Initiative が Issue report を読まずに見つけるべき判断は ADR にする。
- good: 欠けている判断を agent が特定できるが、source-grounded research から owner intent を推測できない場合は clarification を使う。

## 悪いパターン（Bad patterns）

- bad: Decision-only Issue に title と branch があるだけで execution-ready と扱う。
- bad: Cross-issue ownership decision を1つの Issue plan に隠し、sibling Issue が後から発見する状態にする。
- bad: 完了後 artifact に残る template へ reusable example や routing tutorial を入れる。
- bad: Future agent が依存する durable decision を `report.md` だけに保存する。
- bad: 既存 docs、code、ADR、discussions、workflow rules を確認する前に、広すぎる質問を user に投げる。

## 引き渡しチェック（Handoff checklist）

- Finding の配置先は Issue-local、Epic、Initiative、ADR、clarification のいずれか1つである。
- 選んだ配置先は、その判断を安全に所有できる最小 scope である。
- Execution handoff が、未記録の durable decision に依存していない。
- 例と instructional guidance は docs に置き、完了後の requirement / design / plan artifact には採用済みの scope-specific facts だけを残す。
