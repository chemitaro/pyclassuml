# reference: hard cutover

Hard cutover は標準 Issue workflow ではなく、fallback 廃止、dual-read 廃止、checked-in data の手動境界修正、または canonical storage / mutation contract の切替を伴う issue だけが採用する optional pattern です。

通常の Issue は [workflow_issue.md](workflow_issue.md) の lifecycle / execution / reviewer / completion policy と、[authoring/issue-plan.md](authoring/issue-plan.md) の planned contract / observed evidence ledger 境界に従います。Hard cutover を採用する場合は、この reference の entry 条件と evidence keys を `plan.md` の planned contract に取り込み、実結果を `report.md` の observed evidence ledger に残します。

## entry conditions

- issue plan が hard cutover を含む場合、entry 条件は `docs 更新 + checked-in data manual fix + validate/sync evidence` の 3 点を必須にする。
- T3/T4 owner split は次に固定する:
  - T3 integration issue（例: `iss-00062`）が entry 条件充足と hard cutover judgment の primary owner
  - T4 closure issue（例: `iss-00063`）は T3 judgment を参照して final parity / close review を実施
- no fallback / no dual-read contract を崩す救済策は採用しない。Canonical storage / mutation contract の詳細は [reference_deps.md](reference_deps.md) を参照する。

## report evidence keys

Hard cutover evidence の fixed-key contract は issue-level `report.md` に残す。最低限、以下のキー群を使う:

- `cutover_entry.docs_update.paths`
- `cutover_entry.docs_update.pass`
- `cutover_entry.manual_fix.paths`
- `cutover_entry.manual_fix.pass`
- `cutover_entry.boundary_tests`
- `cutover_entry.validate.command`
- `cutover_entry.validate.exit_code`
- `cutover_entry.validate.pass`
- `cutover_entry.sync.command`
- `cutover_entry.sync.exit_code`
- `cutover_entry.sync.pass`
- `cutover_entry.targeted_regression_summary.scope`
- `cutover_entry.targeted_regression_summary.results`
- `cutover_entry.targeted_regression_summary.pass`
- `cutover_entry.entry_conditions_pass`
- `cutover_judgment.owner_issue_id`
- `cutover_judgment.owner_role`
- `cutover_judgment.verdict`
- `cutover_judgment.fixed_at`
- `cutover_judgment.follow_up_issue_id`
- `cutover_judgment.notes`
