from __future__ import annotations

import json
import re
from typing import Any

from evohunter.ai import DEFAULT_MODEL, complete_chat
from evohunter.core.protocol import (
    CandidateGene,
    JobGene,
    MatchResult,
    ValidationError,
    validate_candidate_gene,
    validate_job_gene,
)


class OutreachDraftError(RuntimeError):
    pass


def draft_outreach(
    job_gene: dict[str, Any] | JobGene,
    candidate_gene: dict[str, Any] | CandidateGene,
    match_result: dict[str, Any] | MatchResult | None,
    client: Any | None = None,
    model: str = DEFAULT_MODEL,
) -> dict[str, str]:
    if match_result is None:
        raise OutreachDraftError("match_result is required")
    try:
        job = validate_job_gene(job_gene)
        candidate = validate_candidate_gene(candidate_gene)
        match = match_result if isinstance(match_result, MatchResult) else MatchResult.from_dict(match_result)
    except ValidationError as exc:
        raise OutreachDraftError(str(exc)) from exc

    if match.candidate_id != candidate.candidate_id:
        raise OutreachDraftError("match_result candidate_id must match candidate_gene")
    if match.job_id != job.job_id:
        raise OutreachDraftError("match_result job_id must match job_gene")

    response = complete_chat(
        model=model,
        client=client,
        messages=[
            {"role": "system", "content": _system_prompt()},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "job_gene": job.to_dict(),
                        "candidate_gene": candidate.to_dict(),
                        "match_result": match.to_dict(),
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    )
    payload = _loads_json_response(response)
    return _validate_draft(payload, job.job_id, candidate.candidate_id)


def _system_prompt() -> str:
    return (
        "你是 EvoHunter 的候选人触达草稿生成器。只返回 JSON object，不要解释。"
        "字段必须使用 snake_case，并严格包含：candidate_id, job_id, subject, "
        "message_body, rationale。只生成草稿，不要发送消息。"
    )


def _loads_json_response(response: str) -> Any:
    candidate = _strip_json_fence(response)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise OutreachDraftError("AI response must be valid JSON") from exc


def _strip_json_fence(response: str) -> str:
    text = response.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.S | re.I)
    if fence_match:
        return fence_match.group(1).strip()
    return text


def _validate_draft(payload: Any, job_id: str, candidate_id: str) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise OutreachDraftError("outreach draft must be a JSON object")
    required_fields = ("candidate_id", "job_id", "subject", "message_body", "rationale")
    output: dict[str, str] = {}
    for field_name in required_fields:
        value = payload.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise OutreachDraftError(f"{field_name} must be a non-empty string")
        output[field_name] = value.strip()
    if output["candidate_id"] != candidate_id:
        raise OutreachDraftError("candidate_id must match candidate_gene")
    if output["job_id"] != job_id:
        raise OutreachDraftError("job_id must match job_gene")
    return output
