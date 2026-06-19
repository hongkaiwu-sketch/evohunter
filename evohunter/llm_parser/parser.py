from __future__ import annotations

import json
import re
from typing import Any

from evohunter.ai import DEFAULT_MODEL, complete_chat
from evohunter.core.protocol import ValidationError, validate_candidate_gene, validate_job_gene


class LLMParserError(RuntimeError):
    pass


def parse_job_text(
    text: str,
    client: Any | None = None,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    payload = _request_json(
        text=text,
        system_prompt=_job_system_prompt(),
        model=model,
        client=client,
    )
    if not isinstance(payload, dict):
        raise LLMParserError("job parser must return a JSON object")
    try:
        return validate_job_gene(_with_default_job_id(payload)).to_dict()
    except ValidationError as exc:
        raise LLMParserError(f"invalid job_gene: {exc}") from exc


def parse_candidate_text(
    text: str,
    client: Any | None = None,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    candidates = parse_candidate_texts(text=text, client=client, model=model)
    if len(candidates) != 1:
        raise LLMParserError("candidate parser must return exactly one candidate")
    return candidates[0]


def parse_candidate_texts(
    text: str,
    client: Any | None = None,
    model: str = DEFAULT_MODEL,
) -> list[dict[str, Any]]:
    payload = _request_json(
        text=text,
        system_prompt=_candidate_system_prompt(),
        model=model,
        client=client,
    )
    candidate_payloads = payload if isinstance(payload, list) else [payload]
    output: list[dict[str, Any]] = []
    try:
        for index, candidate_payload in enumerate(candidate_payloads, start=1):
            output.append(
                validate_candidate_gene(
                    _with_default_candidate_id(candidate_payload, index)
                ).to_dict()
            )
    except ValidationError as exc:
        raise LLMParserError(f"invalid candidate_gene: {exc}") from exc
    return output


def _request_json(
    text: str,
    system_prompt: str,
    model: str,
    client: Any | None,
) -> Any:
    if not text.strip():
        raise LLMParserError("input text is required")
    response = complete_chat(
        model=model,
        client=client,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text.strip()},
        ],
    )
    return _loads_json_response(response)


def _loads_json_response(response: str) -> Any:
    candidate = _strip_json_fence(response)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise LLMParserError("AI response must be valid JSON") from exc


def _strip_json_fence(response: str) -> str:
    text = response.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.S | re.I)
    if fence_match:
        return fence_match.group(1).strip()
    return text


def _with_default_job_id(payload: dict[str, Any]) -> dict[str, Any]:
    output = dict(payload)
    if not isinstance(output.get("job_id"), str) or not output["job_id"].strip():
        output["job_id"] = "j_001"
    return output


def _with_default_candidate_id(payload: Any, index: int) -> Any:
    if not isinstance(payload, dict):
        return payload
    output = dict(payload)
    if not isinstance(output.get("candidate_id"), str) or not output["candidate_id"].strip():
        output["candidate_id"] = f"c_{index:03d}"
    return output


def _job_system_prompt() -> str:
    return (
        "你是 EvoHunter 的 JD 解析器。只返回 JSON object，不要解释。"
        "字段必须使用 snake_case，并严格包含：job_id, job_title, required_skills, "
        "preferred_skills, min_years_of_experience, salary_range, location, seniority_level。"
    )


def _candidate_system_prompt() -> str:
    return (
        "你是 EvoHunter 的候选人解析器。只返回 JSON array，不要解释。"
        "每个对象字段必须使用 snake_case，并严格包含：candidate_id, skill_vector, "
        "years_of_experience, salary_expectation, location_preference, recent_projects, "
        "availability, seniority_level。"
    )
