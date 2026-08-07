---
種別: 計画書（Epic）
ID: "epic-00002"
タイトル: "Foundation Contracts"
関連GitHub: ["#2"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-08-05"
依存: ["requirement.md", "design.md"]
親: ["init-00001"]
---

# epic-00002 Foundation Contracts — 計画（Issues / Order）

## この計画で閉じる E-RQ / E-AC
- E-RQ:
  - `E-RQ-001` から `E-RQ-006` までを、6 issue の seam owner 単位で閉じる。
- E-AC:
  - `E-AC-001` から `E-AC-003` を、issue docs と canonical verification scenario の整合で満たす。

## Issue 分割方針
- slicing principle:
  - `1 issue = 1 seam` を守り、front-stage の owner を曖昧にしない。
  - `generate` / `diff` の共通部分は `model` / `config` に寄せ、差分は `targets.explicit` と `vcs + targets.diff` に閉じる。
- exceptions:
  - `vcs.diff-file-collect` と `targets.diff-target-normalize` は同じ `diff` front-stage だが、Git 読み取りと scope filtering を分けるため別 issue にする。

## 承認済みの範囲外補正 Issue
- `iss-00044-diff-default-depth` は、`diff` のdefault depthをCLI/configのresolverで補正するための、M1計画外のcorrective issueとする。
- `iss-00045-diff-implicit-base-safety` は、`iss-00036-diff-default-branch-base` で導入したimplicit base解決を、実運用で確認された巨大履歴走査から保護するための、M1計画外のcorrective issueとする。
- 承認根拠はsource task delegation `019fcba8-ca5e-71d2-a6a7-ddec18085eff` と最新のユーザー指示である。
- 各corrective issueのclosure ownerは、それぞれのcanonical `requirement.md` / `design.md` / `plan.md` / `report.md` とする。
- これらのIssueは既存M1の6 Issue closureに含めず、E-RQおよびM1 closureの定義を変更しない。

## Issue 一覧（順序 / tranche 付き）
1. `iss-00007-model-execution-contracts`
   - 目的:
     - shared DTO と invariant を固定し、以後の issue が ad-hoc handoff を作らないようにする。
   - deliverable:
     - `CommandRequest` から `CommandResult` までの最小 contract 定義。
   - tranche:
     - `M1-a`
   - closes:
     - `E-RQ-001`
   - depends on:
     - なし
2. `iss-00008-config-context-resolve`
   - 目的:
     - 4 roots、config discovery / merge、`relative_path_base`、containment fail-fast を固定する。
   - deliverable:
     - `ExecutionContext` / `AnalysisConfig` の authoritative handoff。
   - tranche:
     - `M1-a`
   - closes:
     - `E-RQ-002`
   - depends on:
     - `iss-00007-model-execution-contracts`
3. `iss-00006-cli-request-bind-and-exit-contract`
   - 目的:
     - usage error、CLI option bind、exit code propagation を固定する。
   - deliverable:
     - `CommandRequest(process_cwd, cli_options)` と `CommandResult.exit_code` 伝播の契約。
   - tranche:
     - `M1-b`
   - closes:
     - `E-RQ-003`
   - depends on:
     - `iss-00007-model-execution-contracts`
4. `iss-00009-targets-explicit-target-normalize`
   - 目的:
     - file / glob / dir 起点の `TargetSet` 正規化を固定する。
   - deliverable:
     - explicit target の dedupe、ignore、scope outside fail。
   - tranche:
     - `M1-b`
   - closes:
     - `E-RQ-004`
   - depends on:
     - `iss-00008-config-context-resolve`
5. `iss-00010-vcs-diff-file-collect`
  - 目的:
    - `--base <ref>`、`working-tree | head`、untracked、VCS failure を固定する。
  - deliverable:
    - `targets.diff-target-normalize` へ渡す seam-local `ChangedFileCollection` 契約。
   - tranche:
     - `M1-b`
   - closes:
     - `E-RQ-005`
   - depends on:
     - `iss-00007-model-execution-contracts`
     - `iss-00008-config-context-resolve`
6. `iss-00011-targets-diff-target-normalize`
  - 目的:
    - diff seed の scope filtering、exclusion diagnostics、zero-target fail を固定する。
  - deliverable:
    - command-neutral な diff `TargetSet(seed_files, observations)` と exclusion / failure handoff。
   - tranche:
     - `M1-c`
   - closes:
     - `E-RQ-005`
     - `E-RQ-006`
   - depends on:
     - `iss-00008-config-context-resolve`
     - `iss-00010-vcs-diff-file-collect`

## dependency rationale
- `iss-00007` を先頭に置くのは、DTO 名・必須 field・nullability が曖昧なまま各 seam の requirement / design を進めないため。
- `iss-00008` を early に固定するのは、`targets` と `vcs` の path semantics が `config` owner に依存するため。
- `iss-00006` は `model` 依存だが `config` の resolve owner を侵食しないので、`M1-b` で並行に固められる。
- `iss-00010` は計画上 `model` と並行検討しやすいが、completion は `config` の project_root / diff default 契約を前提にする。
- `iss-00011` は `config + vcs` の合流点なので最後に置き、後続 `parse` が 1 つの `TargetSet` 契約だけを見ればよい状態にする。

## what gets fixed in M1
- `CommandRequest`, `ExecutionContext`, `AnalysisConfig`, `TargetObservations`, `TargetSet`, `Diagnostic`, `RunSummary`, `CommandResult` の前段 handoff。
- `process_cwd -> execution_cwd`、config discovery / merge、`relative_path_base=config|cwd`、config-file-dir fallback project_root。
- explicit target の file / glob / dir normalize、default ignore と user ignore、scope outside fail。
- `diff` の `--base <ref>`、`working-tree | head`、untracked、seam-local `ChangedFileCollection`、scope outside exclusion、zero-target fail。
- usage error と exit propagation の boundary。

## 統合チェックポイント
- G1 decomposition review:
  - 6 issue の owner / upstream / observable behavior が initiative `plan.md` の issue baseline table と一致している。
- G2 integration readiness:
  - `generate` と `diff` の前段がともに `TargetSet` へ収束し、`parse` 以降が command-specific branching を必要としない。
- G3 rollout/docs impact:
  - issue docs が initiative canonical docs を重複上書きせず、epic 粒度で dependency rationale を補完している。
- G9 final epic spec review:
  - M1 exit seams と quality gates が、後続 epic が依存できる粒度で固定されている。

## 品質ゲート
- test:
  - 6 issues すべてに command transcript または contract review ベースの canonical verification が定義されている。
- observability:
  - origin seam、warning / exclusion count、failure reason 候補の carry が明文化されている。
- migration:
  - front-stage が後段 algorithm や output policy に踏み込んでいない。
- docs:
  - initiative `requirement.md` / `design.md` / `plan.md` / v5 と contradiction がない。

## ロールアウト / docs impact
- rollout order:
  - `M1-a` で shared contract と context resolve を固める。
  - `M1-b` で CLI / explicit target / VCS diff collection を固める。
  - `M1-c` で diff target normalize を閉じ、M1 完了とする。
- contract / docs refresh:
  - issue `plan.md` は execution 直前に issue 単位で具体化する。
  - issue `report.md` は execution / verification 後の判断記録として更新する。

## Issue readiness contract
- Issue に要求する最低条件:
  - upstream / downstream が initiative `plan.md` と一致する。
  - handoff する DTO または seam-local collection が明示されている。
  - verification strategy が fixture 依存か transcript 依存か判別できる。
  - non-goal が明示され、後続 epic の責務を侵食しない。

## final exit contract
- E-AC closure:
  - `E-AC-001` から `E-AC-003` が issue docs の acceptance / edge cases / failure ownership で閉じている。
- integration / rollout complete:
  - M1 seams が `parse.module-parse-and-index` と `app.*-wiring` の前提として利用可能である。
- docs impact resolved:
  - epic / issue docs が initiative canonical docs の補助正本として読める状態であり、placeholder を残さない。

## 依存 / ブロッカー
- D-001:
  - issue `plan.md` は execution 直前まで詳細化しないため、本書が sequencing と quality gate の epic-level planning source になる。
- D-002:
  - `strict` / `warn` の最終 exit policy 自体は `report.artifact-summary-exit-policy` owner であり、本 epic では escalation 素材の handoff までに留める。

## 未確定事項
- なし:
  - ordering、dependency rationale、M1 exit の定義は initiative canonical docs から十分に確定できる。
