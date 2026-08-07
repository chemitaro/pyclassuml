# テンプレート一覧（spec-dock/templates）

このディレクトリは、ローカルスクリプト `./spec-dock/scripts/spec-dock new ...` が
新規ノードを作成する際に参照するテンプレート群です。Templates provide thin scaffold and evidence slots only; workflow authority and detailed field semantics live in skills, docs, accepted ADRs, canonical artifacts, reviewer gates, and report ledgers.

- `initiative/` → `initiatives/init-xxxx-<slug>/`
- `epic/` → `.../epics/epic-xxxx-<slug>/`
- `issue/` → `.../issues/iss-xxxx-<slug>/`
- Initiative / Epic / Issue の責務境界と authority flow は `docs/authoring/scope-layering.md` を参照します。テンプレートは薄い scaffold に留め、scope 表や workflow 詳細は複製しません。
- legacy `discussions/{scratch,interview,research,disc,adr,pr-repair-batch}.md` → `<scope>/discussions/<ts>-<kind>-<slug>.md`
- `draft-requirement` / `draft-design` / `draft-plan` は safety-sensitive draft work です。Future `new artifact draft-*` は Issue scope only で、Initiative / Epic scope は unsupported のため write 前に no-write fail-closed します。Issue の `draft-design` / `draft-plan` は verified `.assurance.json` の `authorized_profile` に対応する `templates/issue-profiles/<profile>/design.md` / `plan.md` を source として render します。
- legacy discussion same-second collision 時は `<scope>/discussions/<ts>-<nn>-<kind>-<slug>.md`
- future `artifacts/{blank,research,interview,disc,decision-candidate,pr-repair-batch,adr}.md` → `<scope>/artifacts/<ts>-<type>-<slug>.md`
- future `blank` artifact は `<scope>/artifacts/<ts>-<slug>.md` を使い、filename に `blank` token を要求しません。template identity は front matter の `template: "blank"` で示します。
- future `new artifact draft-requirement` / `draft-design` / `draft-plan` は専用 `templates/artifacts/draft-*.md` を持ちません。Issue scope だけで `draft-requirement` は既存 issue requirement template contract を、`draft-design` / `draft-plan` は verified `.assurance.json` の `authorized_profile` に対応する `templates/issue-profiles/<profile>/design.md` / `plan.md` を source とします。Initiative / Epic scope の future `new artifact draft-*` は unsupported / no-write fail-closed です。

注意:
- legacy discussion docs were historically created by `new doc <type>` and remain preservation evidence.
- legacy discussion catalog は `scratch` / `interview` / `research` / `disc` / `adr` / `pr-repair-batch` / `draft-requirement` / `draft-design` / `draft-plan` です。新規 working artifacts は future `new artifact` catalog を使います。
- future `new artifact` catalog は `blank` / `research` / `interview` / `disc` / `decision-candidate` / `pr-repair-batch` / `adr` / `draft-requirement` / `draft-design` / `draft-plan` です。
- `scratch` は legacy-only であり、future artifact catalog には追加しません。raw / untyped capture は future `blank` artifact を使います。
- `interview` は docs-aware clarification workflow の正式質問シートです。重要判断は一問一答で扱い、回答前に unanswered artifact を作成し、回答後に同じ artifact へ回答、採用判断、反映先を追記します。既存の複数質問 interview artifact は grandfathered で、自動分割や rename はしません。
- `research` は source-grounded read、事実、推測、未検証事項、判断への含意を分離します。`disc` は複数質問や research の synthesis、reflection proposal、ADR candidate triage を扱います。採否の最終証跡は canonical docs / ADR / `report.md` へ昇格して記録します。
- `report.md` は initiative / epic / issue の canonical observed evidence ledger であり、legacy `new doc report` として作成する discussion catalog には含めません。
- Issue scope の legacy `draft-requirement` / `draft-design` / `draft-plan` は existing `discussions/` 配置と draft filename で grandfathered draft artifact として扱います。canonical docs remain main-orchestrator-only; canonical docs direct-write success path はありません。
- Future `new artifact` では Issue scope の `draft-requirement` / `draft-design` / `draft-plan` も `artifacts/` 配置になりますが、content source は上記の existing issue requirement / issue-profile design / issue-profile plan template reuse です。
- Future `artifacts/` は working evidence surface です。既存 `discussions/` docs は preservation / legacy surface として削除、移動、rename しません。
- Future ADR originals may live under `artifacts/` or legacy `discussions/`; accepted ADR mirror collection must collect both without moving originals.
- `note` は retired です。既存 `note` artifact は grandfathered として壊さず、legacy `new doc` surface の historical raw capture は `scratch` です。future `new artifact` surface の raw / untyped capture は `blank` を使います。
- discussion docs の filename contract は timestamp-prefix です（標準: `<ts>-<kind>-<slug>.md` / same-second collision: `<ts>-<nn>-<kind>-<slug>.md`）。
- `ts = yyyymmddthhmmssz`（UTC, lowercase `t` / `z`）、`nn = 01..99` です。
- `doc_id` は slugless identity（`<ts>-<kind>` / `<ts>-<nn>-<kind>`）で、filename stem は `<doc_id>-<slug>` です。
- `discussions/` 配下の allocation は valid timestamp-contract files を対象にし、unrelated files / navigation files は無視されます。
- legacy sequential discussion docs（`<nnn>-<kind>-<slug>.md`）は grandfathered artifact として許容されますが、自動 rename や basename 再利用はしません。
- ただし discussion-doc intent を持つ malformed basename は explicit failure です。
- same-second collision suffix が `99` まで埋まった場合は失敗します。follow-up issue で archive または contract 拡張を判断してください。
- 生成後のファイルは自由に編集して構いません（テンプレは starting scaffold であり、placeholder は completion evidence ではありません）。
- authority は通常 doc type から推定します。例外時だけ front matter の `authority` で override し、全 artifact に明示必須化しません。
- discussion docs は作業面です。必要な文脈だけを新しい `adr`、または `requirement.md` / `design.md` / `plan.md` へ反映します。
- 命名規則は **全て小文字**（macOS のケース非区別FS対策）。
- `new/import {initiative,epic,issue}` の `--slug` は kebab-case（小文字英数字 + `-`）です。`--slug` 省略時は `--title` から合成されます（詳細は `spec-dock/docs/reference_naming.md`）。
- 各ノードの子スコープ配下には canonical guidance への `rules.md` symlink が含まれます。`rules.md` は入口/ナビゲーション用です。
- 作成/運用ルールの詳細参照先は `spec-dock/docs/rules/**` です。runtime command はサポートされた実行経路です。
- Workbench は任意です。optional、temporary、worktree-local、disposable、non-canonical な作業領域です。`.workbench/README.md` は direct child の README-only tracking surface で、その他の Workbench entry は ignored payload として Git に ignore されます。fresh root と future Initiative / Epic / Issue の shell にはこの Workbench README が生成されますが、existing scope には no-backfill です。Workbench は任意であり、不在でも workspace は valid です。新規ノードの node-root `README.md` は生成されません。

更新:
- 導入済み repo の managed files/docs/templates/scripts/skills は repo root から `./spec-dock/scripts/spec-dock update [path]` で更新します。
- `path` 省略時の target は current directory です。別 repo を更新する場合は `./spec-dock/scripts/spec-dock update /path/to/project` のように明示します。
- runtime update は installer update の wrapper です。内部では固定 upstream `git+https://github.com/chemitaro/spec-dock` に対して `uvx --no-cache --from git+https://github.com/chemitaro/spec-dock spec-dock update <target>` を実行します。
- runtime update は `init --force` ではなく、自動 migration tool でもありません。legacy / incompatible workspace は手動 normalize または rebuild が必要な場合があります。
