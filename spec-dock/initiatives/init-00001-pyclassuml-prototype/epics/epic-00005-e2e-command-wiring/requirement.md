---
種別: 要件定義書（Epic）
ID: "epic-00005"
タイトル: "E2E Command Wiring"
関連GitHub: ["#5"]
状態: "draft"
作成者: "iwasawayuuta"
最終更新: "2026-04-17"
親: ["init-00001"]
---

# epic-00005 E2E Command Wiring — 要件定義（WHAT / WHY）

## 目的（Initiative との紐づき）
- initiative goal / metric:
  - M1 と M2 で固定した front-stage / core-analysis / downstream output seams を、M3 で command として閉じる。
  - `app` を最後の stitcher に限定し、`generate` / `diff` の end-to-end 実行を成立させても `analyze` / `render` / `report` に orchestration logic が逆流しない状態を作る。
- この epic が提供する能力:
  - `app.generate-wiring` による `generate` の end-to-end orchestration。
  - `app.diff-wiring` による `diff` の end-to-end orchestration。
  - `generate` と `diff` の差を前段 seed / changed-file context 生成に閉じ、`parse -> analyze -> frameworks -> render -> report` の共通 pipeline を維持する。
  - usage error は `cli`、それ以外の summary / `CommandResult` 生成は `report`、という既存契約を end-to-end で破らない。

## ユースケース
- happy path:
  - 利用者が `generate` を実行したとき、explicit target から得た `TargetSet` を共通 pipeline に通し、`.puml` artifact、stdout summary、exit code を観測できる。
  - 利用者が `diff --base <ref>` を実行したとき、changed-file context と `TargetSet` を共通 pipeline に通し、`.puml` artifact、summary、exit code、current-state / untracked 切替の差を観測できる。
- exception / operation scenario:
  - invalid config、zero-target、diagram unbuildable、output write failure などの non-usage failure は、`app` が再分類せず `report` owner の summary / result として返せる。
  - `current_state=head` かつ `include_untracked=true` の no-op warning や diff scope exclusion は、前段で発生した diagnostics / counters をそのまま `report` へ運び、summary で観測できる。

## Epic requirements
- E-RQ-001:
  - `iss-00020-app-generate-wiring` は、`config.context-resolve`、`targets.explicit-target-normalize`、`parse`、`analyze`、`frameworks`、`render`、`report` を canonical order で接続し、`generate` を end-to-end で成立させる。
- E-RQ-002:
  - `iss-00021-app-diff-wiring` は、`config.context-resolve`、`vcs.diff-file-collect`、`targets.diff-target-normalize`、`parse`、`analyze`、`frameworks`、`render`、`report` を canonical order で接続し、`diff` を end-to-end で成立させる。
- E-RQ-003:
  - この epic は、`generate` と `diff` の差分を front-stage の `TargetSet` / changed-file context 準備までに閉じ、`TargetSet` 以降の pipeline に command-specific branching を持ち込まない。
- E-RQ-004:
  - `app` は stitcher / orchestrator に限定し、target normalization、graph 解析、framework enrich、diagram shaping、summary synthesis、exit policy 決定を再実装しない。
- E-RQ-005:
  - CLI usage error は `cli` owner に残し、それ以外の `RunSummary` / `CommandResult` 生成は `report` owner に固定する。
- E-RQ-006:
  - `TargetSet.observations`、`ChangedClassInventory`、upstream diagnostics を `app` が transport し、summary counter source と failure reason source を欠落させず `report` へ handoff する。

## Epic acceptance criteria
- E-AC-001:
  - Given:
    - initiative `plan.md` の `app.generate-wiring` / `app.diff-wiring` baseline row と、M1 / M2 の upstream seam 契約がある。
  - When:
    - epic / issue requirement と design をレビューする。
  - Then:
    - `app` の責務が invocation order と transport に限定され、`cli` / `report` / downstream seams との owner split が一意に説明できる。
  - 観測点:
    - epic design の seam contract table、issue design の invariant、initiative `design.md` / `plan.md` との整合。
- E-AC-002:
  - Given:
    - valid な `generate` invocation と explicit target fixture がある。
  - When:
    - `iss-00020` の contract を適用する。
  - Then:
    - `targets.explicit-target-normalize` 以降は共通 pipeline に通り、`.puml` artifact、stdout summary、exit code が `report` owner の結果として観測できる。
  - 観測点:
    - command transcript、filesystem observation、issue requirement / design の verification mapping。
- E-AC-003:
  - Given:
    - valid な `diff` invocation と `working-tree|head`、`include_untracked=true|false` の fixture がある。
  - When:
    - `iss-00021` の contract を適用する。
  - Then:
    - current-state / untracked の差は front-stage seed / warning 差としてだけ現れ、`parse` 以降の pipeline は `generate` と同一 order で維持される。
  - 観測点:
    - diff transcript review、warning / counter review、issue design の flow。
- E-AC-004:
  - Given:
    - usage error、zero-target failure、invalid `--base <ref>`、output write failure の scenario がある。
  - When:
    - epic contract を review する。
  - Then:
    - usage error は `cli`、それ以外の summary / result は `report` という producer split が崩れていない。
  - 観測点:
    - `iss-00006`、`iss-00019`、`iss-00020`、`iss-00021` の requirement / design cross-check。

## スコープ
- MUST:
  - `iss-00020` と `iss-00021` の 2 seams を対象にする。
  - `generate` / `diff` の end-to-end sequencing、transport する DTO / observations、owner split を固定する。
  - `TargetSet.observations` と `ChangedClassInventory` を `report` へ到達させる transport path を明示する。
- MUST NOT:
  - `cli` の usage error contract を `app` へ移さない。
  - `report` の summary / exit policy contract を `app` へ移さない。
  - `parse` / `analyze` / `frameworks` / `render` / `report` の issue `plan.md` や `report.md` をこの turn で編集しない。
- OUT OF SCOPE:
  - new command 追加。
  - progress bar や console 装飾。
  - pipeline 並列化、retry、cache。

## 境界
- Always:
  - `app` は command-local branching を front-stage に閉じ、後段では command-neutral な shared DTO だけを扱う。
  - `generate` は empty changed-file context を analyze に渡し、changed class 数 `0` の authoritative inventory も downstream common contract に乗せる。
  - `diff` は actual changed-file context を前段で準備し、`ChangedClassInventory` の authoritative producer は引き続き `analyze` とする。
  - `TargetSet` と `TargetObservations` の SoR は `targets`、`ChangedClassInventory` の SoR は `analyze`、`CommandResult` の SoR は `report`、usage error result の SoR は `cli` とする。
- Ask:
  - `TargetSet` 以降に `generate` / `diff` 専用分岐を追加したい場合。
  - `app` に summary 文面や failure taxonomy を持たせたい場合。
  - changed-file context を `analyze` 以外で authoritative に持ちたい場合。
- Never:
  - `app` で graph / relation / framework / render / report logic を再実装しない。
  - `cli` usage error を `report` へ流さない。
  - `report` が受け取る observations / diagnostics / inventory を `app` で欠落させない。

## 非機能要件
- performance:
  - 同一 request、同一 upstream outputs、同一 Git 基準では、stage invocation order と downstream user-visible result が決定的であること。
- reliability / consistency:
  - `generate` / `diff` の違いが post-`TargetSet` pipeline に漏れず、summary counter source が欠落しないこと。
  - usage error と non-usage failure の producer split が曖昧でないこと。
- security:
  - `app` 自身は target repository への read/write を持たず、upstream seams の read-only / AST-only 契約を破らないこと。
- operations:
  - command transcript review だけで stage order、artifact path、summary stream、exit owner を追跡できること。

## 依存 / 影響範囲
- impacted components:
  - `app`
  - `cli`
  - `report`
  - `targets`
  - `vcs`
  - `parse`
  - `analyze`
  - `frameworks`
  - `render`
- external dependency:
  - stdout / stderr
  - filesystem artifact write
  - git diff read
- compatibility:
  - initiative `requirement.md`, `design.md`, `plan.md`
  - `20260416t113919z-note-pyclassuml-architecture-v5.md`
  - `20260417t152718z-note-pyclassuml-prototype-roadmap-bridge-v1.md`
  - `epic-00002-foundation-contracts`
  - `epic-00003-core-analysis`
  - `epic-00004-framework-render-report`

## 未確定事項
- なし:
  - M3 で固定すべき owner split、common pipeline、transport path は initiative canonical docs と upstream epics から十分に導出できる。
