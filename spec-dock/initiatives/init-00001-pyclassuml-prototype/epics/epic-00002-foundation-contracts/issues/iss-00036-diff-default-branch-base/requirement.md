---
種別: 要件定義書（Issue）
ID: "iss-00036"
タイトル: "Diff Default Branch Base"
関連GitHub: ["#36"]
状態: "approved"
作成者: "iwasawayuuta"
最終更新: "2026-05-22"
親: ["epic-00002", "init-00001"]
---

# iss-00036 Diff Default Branch Base — 要件定義（WHAT / WHY）

## 目的
- `pyclassuml diff` を `--base` なしで実行できるようにし、利用者が「現在の作業ブランチで積み上げた変更範囲」をすぐに UML クラス図として確認できるようにする。
- 明示的な `--base <ref>` は既存互換のまま維持し、branch / tag / commit hash を指定した比較は従来どおり `<ref>` 自体を比較基点として扱う。
- upstream、base branch 設定、config 記述を必須にせず、基点を推定できない場合も可能な限り有用な diff を生成する。

## 背景・現状
- 現状の挙動:
  - `pyclassuml diff --base <ref>` は必須引数であり、`--base` を省略すると CLI usage error になる。
  - `diff` は Git 差分から対象ファイルを集め、`--current-state working-tree|head` に応じて現在側を比較する。
  - `--current-state working-tree` がデフォルトであり、未追跡ファイルは `--include-untracked` の既存仕様に従って扱われる。
- 現状の課題:
  - 利用者が日常的に見たいことが多い「このブランチで何が変わったか」を確認するだけでも、毎回 `--base <ref>` を考える必要がある。
  - Git の upstream は「ローカルブランチの追跡先」であり、作業ブランチの分岐元 branch とは限らない。たとえば `feature/foo` の upstream が `origin/feature/foo` の場合、upstream から branch-start を導くと利用者の意図とずれる。
  - upstream がないこと、または config に default base がないことを理由に `pyclassuml diff` を失敗させると、外部 CLI として利用者へ過度な設定負担を要求する。
  - Git は「この branch が作成された瞬間の commit」を永続的な first-class metadata として保持しないため、`--base` 未指定時の branch-start は厳密値ではなく、決定的な best effort 推定として扱う必要がある。
- 情報源:
  - `README.md` の既存 `diff --base <ref>` / `--current-state` 仕様。
  - `iss-00006-cli-request-bind-and-exit-contract` の CLI bind 契約。
  - `iss-00007-model-execution-contracts` の `CommandRequest` / `DiffOptions` 契約。
  - `iss-00010-vcs-diff-file-collect` の `--base <ref>` / `current_state` / `include_untracked` 契約。
  - 2026-05-21〜2026-05-22 の設計相談: `--base` を任意化し、未指定時は設定強制や upstream 必須化を避けてよしなに動かす方針。

## 対象ユーザー / 利用シナリオ
- 主な利用者:
  - Python プロジェクトの feature branch 上で、作業ブランチ全体の設計差分を UML クラス図で確認したい開発者。
  - PR 作成前、レビュー前、作業再開時に、現在ブランチで積み上げた変更範囲を俯瞰したい開発者。
- 代表シナリオ:
  - `pyclassuml diff` だけで、推定された branch-start base から現在の working tree までの差分図を生成する。
  - `pyclassuml diff --current-state head` で、推定された branch-start base から `HEAD` までの committed diff 図を生成する。
  - `pyclassuml diff --base origin/main` や `pyclassuml diff --base <commit>` で、明示した ref そのものを基点に従来互換の差分図を生成する。

## スコープ
- 必須:
  - `diff` の `--base` を任意にする。
  - `--base <ref>` 指定時の既存挙動と意味論を維持する。
  - CLI / model / VCS handoff では、明示 `--base <ref>` と no-base invocation を区別できるようにする。
  - no-base invocation は valid input として扱い、VCS diff collection 前または VCS diff collection 内で resolved base を確定してから既存 diff pipeline へ渡す。
  - `--base` 未指定時に、現在ブランチの開始点に近い基点を決定的な順序で best effort 解決する。
  - `--base` 未指定時に upstream や config default がなくても、それだけを理由に usage error / hard failure にしない。
  - best effort 解決で適切な候補が得られない場合は、repository の initial commit object を fallback base として差分収集を続行する。
  - 実際に使った resolved base と、その解決理由を `CommandResult.diagnostics` または同等の structured result でテスト可能にし、成功 / degraded success / failure summary の diagnostics 表示経路でも CLI 利用者が確認できるようにする。
  - `--current-state working-tree|head` と `--include-untracked|--no-include-untracked` の既存意味論を維持する。
- 禁止:
  - `--base <ref>` の意味を暗黙に merge-base / three-dot 比較へ変更しない。
  - upstream 設定、config 設定、特定 branch 名の存在を必須条件にしない。
  - 対象プロジェクトのファイル、Git history、branch 設定、upstream 設定を書き換えない。
  - 対象コードを import 実行しない。
- 対象外:
  - `pyclassuml diff --branch-base`、`--merge-base`、`--guess-upstream` などの追加 UI。
  - GitHub PR API やホスティングサービス API から base branch を取得する機能。
  - reflog / fork-point に依存した精密な分岐元推定。
  - design / plan の詳細化と実装ステップの確定。

## 境界
- 常に行う:
  - 明示 `--base <ref>` がある場合は、その ref を authoritative base として扱う。
  - no-base invocation は explicit base absence として保持し、空文字列や invalid ref と混同しない。
  - `--base` 未指定時は、Git から読み取れる情報だけで deterministic best effort の branch-start base 解決を行う。
  - 解決結果の commit hash または ref と resolution kind を観測可能にする。
  - base 解決と Git diff collection は read-only に行う。
- 判断が必要:
  - default branch 候補の具体的な優先順位。
  - fallback 時の diagnostic severity と文面。
  - resolved base 情報を stdout / stderr / report のどこにどの粒度で出すか。
- 行わない:
  - upstream がないことを理由に失敗させない。
  - 設定ファイルに default base を必須として要求しない。
  - `main` / `develop` などの候補が見つからないことだけで usage error にしない。
  - `--base` 明示時に branch-start 推定を混ぜない。

## 非交渉制約
- 外部 CLI として対象プロジェクトへ依存を追加しない。
- 対象ソースコードを書き換えない。
- Git 操作は読み取り専用に限定する。
- 同一 repository state / same inputs では、base 解決順序、resolved base、diagnostics 順序を決定的にする。
- invalid explicit `--base <ref>` は既存どおり invalid base 系 failure として扱い、initial commit fallback で握りつぶさない。
- no-base fallback は、利用者に設定を強制しないための degraded behavior であり、明示 `--base` の代替として silent に不正確さを隠さない。
- initial commit fallback は empty tree 比較を意味しない。既存 `git diff <base>` 形式の比較基点として repository の initial commit object を使う。

## 前提
- Git branch は commit を指す可変の名前であり、「branch 作成時点」や「branch の一番最初の commit」を常に復元できるとは限らない。
- この issue でいう「現在ブランチの開始点」は、厳密な Git metadata ではなく、現在 repository state から決定的に推定した diff 基点を指す。
- initial commit fallback は、branch-start が推定できない場合にも `pyclassuml diff` を useful に動かすための最終 fallback とする。
- initial commit fallback では、initial commit で導入された内容そのものは差分対象に含まれない。これは「最初の commit から現在までの差分」を見るという no-base fallback の意図に従う。
- default branch candidate や merge-base 推定は、明示 `--base` がない場合にだけ使う。

## 受け入れ条件
- AC-001:
  - アクター: 開発者
  - 前提: feature branch が default branch 候補から分岐しており、`--base` は指定されていない。
  - 操作: `pyclassuml diff` を実行する。
  - 期待結果: default branch 候補との merge-base が resolved base になり、その base から現在の working tree までの diff UML が生成される。
  - 観測点: resolved base と resolution kind が `CommandResult.diagnostics` または同等の structured result で検証でき、summary diagnostics 表示経路でも CLI 利用者が確認できる。
- AC-002:
  - アクター: 開発者
  - 前提: `--base origin/main`、`--base <tag>`、または `--base <commit>` が指定されている。
  - 操作: `pyclassuml diff --base <ref>` を実行する。
  - 期待結果: 既存どおり `<ref>` 自体を base として差分収集し、no-base 用の branch-start 解決は実行されない。
  - 観測点: 既存の invalid base / current-state / untracked 挙動が後方互換である。
- AC-003:
  - アクター: 開発者
  - 前提: upstream、config default、default branch 候補が利用できない repository state がある。
  - 操作: `pyclassuml diff` を実行する。
  - 期待結果: initial commit を fallback base として差分収集を続行し、fallback したことを示す diagnostic を出す。
  - 観測点: usage error ではなく、resolved base と `initial_commit_fallback` 相当の resolution kind を持つ diagnostic 付きの通常 pipeline 結果になる。
- AC-004:
  - アクター: 開発者
  - 前提: `--current-state head` が指定されており、`--base` は指定されていない。
  - 操作: `pyclassuml diff --current-state head` を実行する。
  - 期待結果: resolved base から `HEAD` までの tracked diff を収集し、working tree only の変更や untracked は既存仕様どおり含めない。
  - 観測点: `head_untracked_noop` 等の既存 diagnostics と矛盾しない。
- AC-005:
  - アクター: 開発者
  - 前提: 明示 `--base missing-ref` が指定されている。
  - 操作: `pyclassuml diff --base missing-ref` を実行する。
  - 期待結果: 既存どおり invalid base failure になり、initial commit fallback は使われない。
  - 観測点: explicit base の誤りが silent に別 base へ置き換わらない。

## 例外・エッジケース
- EC-001:
  - 条件: repository に commit がない。
  - 期待: diff base を解決できないため、Git diff / base resolution failure として fail-fast する。
  - 観測点: Python parse / analyze pipeline を呼ばない。
- EC-002:
  - 条件: default branch 候補が存在するが、現在 `HEAD` との merge-base が取れない。
  - 期待: 次候補へ進み、全候補が失敗したら initial commit fallback を使う。
  - 観測点: 最終的な resolved base と resolution kind が確認できる。
- EC-003:
  - 条件: `--base` 未指定かつ current branch が default branch 自身である。
  - 期待: initial commit object を fallback base として使い、その commit から現在状態までの diff として動作する。
  - 観測点: upstream 未設定でも usage error にしない。
- EC-004:
  - 条件: no-base 実行時に untracked Python file が存在する。
  - 期待: `--current-state working-tree` かつ `include_untracked=true` の既存仕様どおり、diff seed に含める。
  - 観測点: no-base 解決が untracked の既存扱いを変えない。
- EC-005:
  - 条件: no-base 実行時に changed files が scope 外にしか存在しない。
  - 期待: base 解決後、既存 `targets.diff-target-normalize` の scope outside exclusion / zero-target 仕様に従う。
  - 観測点: base 解決 issue が scope filtering を肩代わりしない。

## 入力→出力例
- EX-001:
  - 入力: `pyclassuml diff`
  - 出力: `resolved_base=<sha>`, `base_resolution=default_branch_merge_base` 等を伴う diff UML。
- EX-002:
  - 入力: `pyclassuml diff --base origin/main`
  - 出力: `origin/main` を explicit base とする従来互換 diff UML。
- EX-003:
  - 入力: `pyclassuml diff --current-state head`
  - 出力: no-base resolved base から `HEAD` までの committed diff UML。
- EX-004:
  - 入力: default branch 候補がない repository で `pyclassuml diff`
  - 出力: `resolved_base=<initial-commit-sha>`, `base_resolution=initial_commit_fallback` 等を伴う diff UML。比較基点は empty tree ではなく initial commit object。

## 用語
- TERM-001: explicit base
  - `--base <ref>` で利用者が明示した Git revision。指定時は既存どおり `<ref>` 自体を比較基点にする。
- TERM-002: no-base diff
  - `--base` を指定しない `pyclassuml diff` invocation。
- TERM-003: resolved base
  - `diff` が実際に Git 差分の起点として使う commit / ref。
- TERM-004: branch-start base
  - no-base diff で、現在ブランチの開始点に近いものとして best effort で解決した resolved base。
- TERM-005: default branch candidate
  - no-base diff の branch-start 推定に使う、default branch / base branch の候補。具体的な候補順は design で確定する。
- TERM-006: initial commit fallback
  - branch-start base を推定できない場合に、repository の initial commit object を resolved base として使う最終 fallback。empty tree 比較ではない。
- TERM-007: upstream
  - Git が保持するローカルブランチの追跡先。今回の branch-start base の必須条件ではなく、分岐元 branch と同一とは限らない。

## 未確定事項
- Q-001:
  - 質問: default branch candidate の正確な優先順位をどうするか。
  - 推奨案: design 作成時に、`origin/HEAD` など Git が示す default branch 情報を優先し、その後に代表的な branch 名を固定順序で試す。
  - 影響範囲: base 解決の決定性、CI / local の再現性、diagnostic 文面。
- Q-002:
  - 質問: resolved base と resolution kind を既存 summary diagnostics だけで表示するか、追加の report field / counter も持たせるか。
  - 推奨案: design 作成時に既存 report / diagnostics の責務境界を確認し、少なくとも `CommandResult.diagnostics` と summary diagnostics 表示で観測できるようにする。
  - 影響範囲: CLI transcript、README、report tests。
