---
種別: 要件定義書（Epic）
ID: "epic-00002"
タイトル: "Foundation Contracts"
関連GitHub: ["#2"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
親: ["init-00001"]
---

# epic-00002 Foundation Contracts — 要件定義（WHAT / WHY）

## 目的（Initiative との紐づき）
- initiative goal / metric:
  - `generate` / `diff` の外部 CLI prototype を seam-first で実装可能にするため、M1 で前段契約を固定する。
  - 後続 epic が `execution_cwd` / `project_root` / `package_root` / `scope_root`、config merge、explicit / diff seed semantics を再解釈しなくてよい状態を作る。
- この epic が提供する能力:
  - `cli`, `model`, `config`, `targets`, `vcs` の 6 seams について、request bind、DTO invariant、context resolve、explicit target normalize、diff file collect、diff target normalize を authoritative に定義する。

## ユースケース
- happy path:
  - 利用者が `generate` を実行すると、CLI option が `CommandRequest` へ束縛され、4 roots と config merge が確定し、explicit target が `TargetSet` として後段へ渡せる。
  - 利用者が `diff --base <ref>` を実行すると、Git 差分から changed files が収集され、scope filtering 済みの `TargetSet` が後段へ渡せる。
- exception / operation scenario:
  - usage error、invalid config、invalid `--base <ref>`、containment violation、scope 外 diff 起点のみといった前段 failure が、後段の parse / analyze を呼ぶ前に観測できる。

## Epic requirements
- E-RQ-001:
  - `model.execution-contracts` は、initiative plan の issue baseline table に列挙した DTO 群の最小 field / invariant / handoff を固定する。
- E-RQ-002:
  - `config.context-resolve` は、`process_cwd` からの `execution_cwd` 解決、4 roots、config discovery / merge、`relative_path_base`、containment validation を固定する。
- E-RQ-003:
  - `cli.request-bind-and-exit-contract` は、usage error、`--cwd` を含む CLI option bind、`CommandResult.exit_code` の伝播を固定する。
- E-RQ-004:
  - `targets.explicit-target-normalize` は、file / glob / dir 起点、dedupe、`project_root` 相対 ignore、scope outside fail を固定する。
- E-RQ-005:
  - `vcs.diff-file-collect` と `targets.diff-target-normalize` は、`--base <ref>`、`working-tree | head`、untracked、scope outside exclusion、zero-target fail を固定する。
- E-RQ-006:
  - この epic で定義する diagnostics / counters は、後続の `parse` / `analyze` / `report` が summary と exit policy を組み立てられる粒度で carry される。

## Epic acceptance criteria
- E-AC-001:
  - Given:
    - 有効な `generate` または `diff` invocation がある。
  - When:
    - M1 seams の contract review を行う。
  - Then:
    - `CommandRequest`、`ExecutionContext`、`AnalysisConfig`、`TargetSet` の handoff と ownership が一意に説明でき、後続 epic が path semantics を再定義しない。
  - 観測点:
    - initiative `plan.md` の issue baseline table、epic / issue docs の相互整合、CLI transcript 想定例。
- E-AC-002:
  - Given:
    - `--cwd`、`--config`、`--project-root`、`--base <ref>`、`current_state`、`include_untracked` の組み合わせがある。
  - When:
    - front-stage contract を適用する。
  - Then:
    - `CLI > config > default`、config discovery 順序、`current_state=head` での untracked no-op warning、diff scope outside exclusion、zero-target fail が initiative canonical docs と一致する。
  - 観測点:
    - command transcript、config discovery scenario、failure taxonomy の照合。
- E-AC-003:
  - Given:
    - invalid config、invalid containment、invalid `--base <ref>`、usage error、scope 外 explicit target がある。
  - When:
    - 該当 seam の requirement / design をレビューする。
  - Then:
    - どの seam が fail-fast し、どの seam が recoverable diagnostics を downstream へ渡すかが曖昧でない。
  - 観測点:
    - issue requirement / design の edge case と failure ownership。

## スコープ
- MUST:
  - `iss-00006` から `iss-00011` までの 6 seams を対象にする。
  - `generate` と `diff` の差分を `targets` / `vcs` までに閉じる前段契約を固める。
  - `strict` / `warn` の外部契約を支えるための diagnostics origin / recoverability / failure_reason carry を前段で固定する。
- MUST NOT:
  - `parse` / `analyze` / `frameworks` / `render` / `report` の algorithm や acceptance をこの epic で肩代わりしない。
  - `.puml` artifact 書き出し、summary stream routing、changed class counting をこの epic の責務にしない。
- OUT OF SCOPE:
  - import graph 構築、class selection、framework enrich、PlantUML text 生成。
  - 複数 `package_root`、複数 `scope_root`、namespace package 完全対応。

## 境界
- Always:
  - CLI 相対 path の基準は `execution_cwd` とし、その resolve owner は `config` とする。
  - `generate` / `diff` の command-specific branching は `TargetSet` 生成までに閉じる。
  - `vcs` は Git 読み取りに専念し、scope filtering や explicit target semantics を持たない。
  - `targets` は seed normalization を担い、Git 読み取りや parse / analyze を担わない。
- Ask:
  - 4 roots の意味論を変更したい場合。
  - `diff` の zero-target fail や scope outside exclusion を warning/failure から変更したい場合。
  - `model` に追加 field を入れる理由が downstream handoff ではなく convenience に寄っている場合。
- Never:
  - `cli` で `execution_cwd` を解決しない。
  - `parse` / `analyze` 側で config discovery や target normalization を再実装しない。
  - `model` を dumping ground にしない。

## 非機能要件
- performance:
  - path resolve、config merge、target normalization、Git diff 読み取りは deterministic であり、同一入力では同一 seed / diagnostics 順序を返せること。
- reliability / consistency:
  - invalid config、containment violation、invalid `--base <ref>`、Git diff read failure は fail-fast とし、後段へ曖昧な state を渡さないこと。
- security:
  - 対象 repository と Git history は read-only に扱い、対象コード import 実行を前提にしないこと。
- operations:
  - origin seam が分かる diagnostics と、ignore 件数・scope outside exclusion 件数などの summary 素材を後続 `report` へ渡せること。

## 依存 / 影響範囲
- impacted components:
  - `cli`
  - `model`
  - `config`
  - `targets`
  - `vcs`
  - 後続 consumer として `parse`, `app`, `report`
- external dependency:
  - local filesystem
  - local Git repository metadata
- compatibility:
  - initiative `requirement.md`, `design.md`, `plan.md`
  - `20260416t113919z-note-pyclassuml-architecture-v5.md`
  - `20260417t152718z-note-pyclassuml-prototype-roadmap-bridge-v1.md`

## 未確定事項
- なし:
  - この epic で固定すべき contract と completion contract は initiative canonical docs で十分に定義済みであり、追加の open question は残さない。
