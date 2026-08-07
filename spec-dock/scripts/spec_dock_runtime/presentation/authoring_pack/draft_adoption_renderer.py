from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spec_dock_runtime.domain.authoring_pack.draft_adoption_contract import DraftAdoptionResult


def render_draft_adoption_json(result: DraftAdoptionResult) -> str:
    return json.dumps(result.to_dict(), sort_keys=True)


def render_draft_adoption_text(result: DraftAdoptionResult) -> list[str]:
    return [
        f"spec-dock: authoring validate {result.validation_kind}",
        f"status={result.status}",
        f"authority={result.authority}",
        f"adoption_status={result.adoption_status}",
        f"bundle_generation_not_promotion={str(result.bundle_generation_not_promotion).lower()}",
        f"evidence_mode={result.evidence_mode}",
        f"review_status={result.review_status}",
        f"review_gate_passed={str(result.review_gate_passed).lower()}",
        f"issue_id={result.issue_id}",
        f"expected_profile={result.expected_profile}",
        f"observed_profile={result.observed_profile}",
        f"draft_count={result.draft_count}",
        f"valid_draft_count={result.valid_draft_count}",
        f"section_count={result.section_count}",
        f"valid_section_count={result.valid_section_count}",
        f"node_creation_performed={str(result.node_creation_performed).lower()}",
        f"canonical_written={str(result.canonical_written).lower()}",
        f"assurance_mutated={str(result.assurance_mutated).lower()}",
        f"reviewer_pass_claimed={str(result.reviewer_pass_claimed).lower()}",
        f"execution_ready={str(result.execution_ready).lower()}",
        f"pr_ready={str(result.pr_ready).lower()}",
        "comparison=" + ",".join(result.comparison),
        "findings=" + ",".join(result.findings),
    ]
