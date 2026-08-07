---
種別: research
ID: "20260804t090540z-research"
タイトル: "Diff Default Depth Core Contract Investigation"
状態: "draft | completed | archived"
作成者: "iwasawayuuta"
最終更新: "2026-08-04"
親: ["iss-00044"]
関連: []
authority: "synthesized"
derived_from: []
reflected_to: []
---

# 20260804t090540z-research Diff Default Depth Core Contract Investigation

## 位置づけ
- 用途: 外部仕様、実装事実、先例、制約、用語衝突、edge case など、検証可能な根拠を整理する。
- authority default: `synthesized`。通常は doc type から推定し、例外時だけ front matter の `authority` で override する。
- 調査結果が選択肢比較を必要とする場合は `disc`、長期判断を支える場合は `adr`、人間判断を必要とする場合は `interview` へつなぐ。
- 事実、推測、未検証事項、用語衝突、edge case、判断への含意を混ぜない。
- local context で解ける疑問は人間に聞かず、この artifact に source-grounding を残す。

## 調査目的 (必須)
- `diff` の未指定 `depth` を `1` に変更し、`generate` の既定挙動と CLI / config の明示値優先を壊さないための実装境界を確定する。
- スキル側が本体の挙動を誤って仮定しないよう、PyClassUML本体が提供する Git 比較方式と既知の制約を整理する。

## sources / 調査方法 (必須)
- 参照先:
  - `src/pyclassuml/cli/bind.py`
  - `src/pyclassuml/config/resolver.py`
  - `src/pyclassuml/model/contracts.py`
  - `src/pyclassuml/analyze/traversal.py`
  - `src/pyclassuml/vcs/diff_collect.py`
  - `tests/config/test_context_resolve.py`
  - `tests/analyze/test_traversal.py`
  - `README.md`
  - initiative research baseline `20260416t080346z-research-pyclassuml-requirements-baseline-v2.md`
- 検証手順:
  - `active show` と active docs の確認。
  - `rg` による `depth`、`current_state`、`base_ref` の実装・テスト検索。
  - CLI bind、config merge、traversal、Git diff collection のコード読解。
  - config resolver の既定値と優先順位をテストケースへ対応付ける。
- 実験条件:
  - 対象 checkout は commit `8bb20e9` 上の detached worktree。
  - 本調査時点では実装変更前であり、既存テストの全体結果は未実施。

## facts / 観測できた事実 (必須)
- CLI の共通 `--depth` は `CommandOptions.depth: int | None` として bind され、未指定時は `None` になる。
- `AnalysisConfig.depth` の `None` は traversal 側で深さ制限なしを意味する。ただし `DEFAULT_TRAVERSAL_MODULE_LIMIT = 1000` の安全上限がある。
- `config.resolver._merged_depth()` は現在、CLI `depth`、config の `depth`、未指定時の `None` を同じ merge として扱っている。
- `generate` と `diff` はどちらも `resolve_context()` の `AnalysisConfig` を `traverse_dependencies()` に渡すため、command-specific default は config seam に置くのが最小である。
- `--depth 0` は有効で、seed module 自身を残し、直接依存を探索しない契約が traversal tests にある。
- Git の比較基点は次の方式を既に持つ。
  - `--base <ref>` 指定時はその ref を検証して明示基点として使う。
  - `--base` 省略時は default branch 候補との merge-base を試し、current default branch または候補不在時は initial commit object を fallback にする。
  - `--current-state working-tree` は resolved base と作業ツリーを比較する。
  - `--current-state head` は resolved base と `HEAD` を比較する。
  - `working-tree` では `--include-untracked` が既定で有効、`head` では未追跡ファイルは差分に含まれず no-op warning になる。
- Git の差分収集は `git diff`、`git show`、`git rev-parse`、`git merge-base` などの読み取り操作だけで、checkout や対象コードの import は行わない。
- 任意の終点 commit `B` を指定する `A..B` CLI option は存在しない。`head` の図生成でも現在側ソースは作業ツリーから読むため、厳密な HEAD 内容の図には clean worktree が必要である。

## inference / 推測 (必須)
- `diff` の既定を `1` にしても、`AnalysisConfig` や traversal の意味論を変更する必要はない。
- 実装は `_merged_depth()` に command default を渡し、`CLI > config > command default` の順序を明示するのが最小である。
- 新しい `[diff].depth` を追加すると既存の共通 `depth` 契約と設定 schema を二重化するため、今回の目的には不要である。
- 既存の Git 比較方式はスキルが直接実行する Git 操作を拡張するための API ではなく、本体が読み取り可能な比較方式の境界として文書化すべきである。
- 根拠は、depth merge の owner が `config` であり、Git ref の解決・差分収集の owner が `vcs` として既存設計に固定されていることである。

## unverified / 未検証事項 (必須)
- 新実装後の focused test、全体 test、SpecDock validate の結果は未検証である。
- README の Git 比較説明が、今回の本体契約と完全に一致しているかは docs 更新後に再確認する。
- 外部スキルの user-level 導入、GitHub fetch、任意 A→B clone は本Issueの対象外であり、本体側では検証しない。

## terminology conflicts / 用語衝突 (必須)
- `depth` と「無制限」:
  - CLI / config では `depth` 未指定を `None` で表す。
  - traversal では `None` は無制限だが、module limit 1000 は別の安全制約として存在する。
  - docs では「無制限」と「安全上限なし」を混同しない。
- `HEAD` 比較と「HEAD の図」:
  - `current_state=head` は Git changed-file collection と分類を HEAD 基準にする。
  - 解析・描画対象の現在側ファイルは作業ツリーから読むため、dirty worktree では exact HEAD diagram ではない。
- `base`:
  - `--base` は明示された Git ref。
  - no-base invocation では resolved base metadata が自動解決される。

## edge cases / 具体シナリオ (必須)
- CLI と config がどちらも `depth` を持つ:
  - CLI 値を採用し、`diff` の command default `1` は適用しない。
- config のみ `depth = 0` または `depth = 3`:
  - config 値を `generate` / `diff` の両方で採用する。
- CLI / config がどちらも `depth` を持たない:
  - `generate` は既存どおり `None`、`diff` は `1`。
- `--current-state head`、`--include-untracked`、`--base` の有無:
  - Git比較方式は既存どおりで、depth の解決結果には影響させない。
- 無効な CLI / config depth:
  - 既存の non-negative integer validation を維持し、別の fallback に置き換えない。

## implications / 判断への含意 (必須)
- requirement は command-specific default と優先順位を観測可能な acceptance criteria として固定する。
- design は `config.resolver` を唯一の変更実装点とし、CLI parser、model contract、traversal algorithm、VCS resolverを変更対象外にする。
- plan は config resolution tests を中心に、generate regression、CLI/config explicit override、docs impact、全体品質ゲートを固定する。
- README は `diff` の default depth と Git 比較の実行可能な組み合わせ、非対応の A→B 終点指定、HEAD の作業ツリー制約を明記する。

## リスク/制約 (任意)
- `diff` の既定深さ変更により、明示的に depth を指定していない既存利用者の図が小さくなる。ただし CLI / config で従来相当の `depth=None` を明示する設定キーは現行 schema にないため、無制限へ戻すには設定 schema の拡張が必要になる。この拡張は今回行わない。
- そのため README と skill 連携情報では、`diff` の depth default が `1` であることを明示し、深い探索は `--depth n` または config `depth = n` で指定するようにする。

## 反映先 (任意)
- `requirement.md`
- `design.md`
- `plan.md`
- `README.md`

## 参考（References） (任意)
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/discussions/20260416t080346z-research-pyclassuml-requirements-baseline-v2.md`
- `spec-dock/initiatives/init-00001-pyclassuml-prototype/epics/epic-00002-foundation-contracts/design.md`
