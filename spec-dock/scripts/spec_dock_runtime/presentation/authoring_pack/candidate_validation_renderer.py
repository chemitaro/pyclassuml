from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spec_dock_runtime.domain.authoring_pack.candidate_contract import CandidateValidationResult


def render_candidate_validation_json(result: CandidateValidationResult) -> str:
    return json.dumps(result.to_dict(), sort_keys=True)


def render_candidate_validation_text(result: CandidateValidationResult) -> list[str]:
    return [
        "spec-dock: authoring validate candidates",
        f"status={result.status}",
        f"authority={result.authority}",
        f"adoption_status={result.adoption_status}",
        f"bundle_generation_not_promotion={str(result.bundle_generation_not_promotion).lower()}",
        f"candidate_kind={result.candidate_kind}",
        f"candidate_count={result.candidate_count}",
        f"valid_candidate_count={result.valid_candidate_count}",
        f"review_status={result.review_status}",
        f"review_gate_passed={str(result.review_gate_passed).lower()}",
        f"approval_required={str(result.approval_required).lower()}",
        f"node_creation_performed={str(result.node_creation_performed).lower()}",
        f"canonical_written={str(result.canonical_written).lower()}",
        f"assurance_mutated={str(result.assurance_mutated).lower()}",
        f"reviewer_pass_claimed={str(result.reviewer_pass_claimed).lower()}",
        f"execution_ready={str(result.execution_ready).lower()}",
        f"pr_ready={str(result.pr_ready).lower()}",
        "findings=" + ",".join(result.findings),
    ]
