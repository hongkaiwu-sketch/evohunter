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
    return parse_job_text_with_metadata(text=text, client=client, model=model)["job_gene"]


def parse_job_text_with_metadata(
    text: str,
    client: Any | None = None,
    model: str = DEFAULT_MODEL,
    max_attempts: int = 2,
) -> dict[str, Any]:
    payload, metadata = _request_json(
        text=text,
        system_prompt=_job_system_prompt(),
        model=model,
        client=client,
        max_attempts=max_attempts,
    )
    if not isinstance(payload, dict):
        raise LLMParserError("job parser must return a JSON object")
    payload = _with_default_job_fields(payload, metadata)
    try:
        return {
            "job_gene": validate_job_gene(payload).to_dict(),
            "parser_metadata": _finalize_metadata(metadata),
        }
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
    return parse_candidate_texts_with_metadata(text=text, client=client, model=model)[
        "candidate_genes"
    ]


def parse_candidate_texts_with_metadata(
    text: str,
    client: Any | None = None,
    model: str = DEFAULT_MODEL,
    max_attempts: int = 2,
) -> dict[str, Any]:
    payload, metadata = _request_json(
        text=text,
        system_prompt=_candidate_system_prompt(),
        model=model,
        client=client,
        max_attempts=max_attempts,
    )
    candidate_payloads = payload if isinstance(payload, list) else [payload]
    output: list[dict[str, Any]] = []
    try:
        for index, candidate_payload in enumerate(candidate_payloads, start=1):
            output.append(
                validate_candidate_gene(
                    _with_default_candidate_fields(candidate_payload, index, metadata)
                ).to_dict()
            )
    except ValidationError as exc:
        raise LLMParserError(f"invalid candidate_gene: {exc}") from exc
    return {"candidate_genes": output, "parser_metadata": _finalize_metadata(metadata)}


def _request_json(
    text: str,
    system_prompt: str,
    model: str,
    client: Any | None,
    max_attempts: int,
) -> tuple[Any, dict[str, Any]]:
    if not text.strip():
        raise LLMParserError("input text is required")
    if max_attempts <= 0:
        raise LLMParserError("max_attempts must be greater than 0")

    metadata: dict[str, Any] = {
        "attempt_count": 0,
        "repair_actions": [],
        "defaulted_fields": [],
    }
    last_error: LLMParserError | None = None
    for attempt_index in range(max_attempts):
        metadata["attempt_count"] = attempt_index + 1
        response = complete_chat(
            model=model,
            client=client,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text.strip()},
            ],
        )
        try:
            return _loads_json_response(response, metadata), metadata
        except LLMParserError as exc:
            last_error = exc
            if attempt_index < max_attempts - 1:
                metadata["repair_actions"].append("retry_after_invalid_json")

    raise LLMParserError("AI response must be valid JSON") from last_error


def _loads_json_response(response: str, metadata: dict[str, Any] | None = None) -> Any:
    candidate = _strip_json_fence(response)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        repaired = re.sub(r",\s*([}\]])", r"\1", candidate)
        if repaired != candidate:
            try:
                if metadata is not None:
                    metadata["repair_actions"].append("removed_trailing_commas")
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass
        extracted = _extract_json_payload(candidate, metadata)
        if extracted is not None:
            return extracted
        raise LLMParserError("AI response must be valid JSON") from exc


def _strip_json_fence(response: str) -> str:
    text = response.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.S | re.I)
    if fence_match:
        return fence_match.group(1).strip()
    return text


def _extract_json_payload(response: str, metadata: dict[str, Any] | None) -> Any | None:
    decoder = json.JSONDecoder()
    for index, character in enumerate(response):
        if character not in "{[":
            continue
        try:
            payload, _ = decoder.raw_decode(response[index:])
        except json.JSONDecodeError:
            continue
        if metadata is not None:
            action = "extracted_json_object" if character == "{" else "extracted_json_array"
            metadata["repair_actions"].append(action)
        return payload
    return None


def _with_default_job_fields(payload: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    output = dict(payload)
    defaults = {
        "job_id": "j_001",
        "job_title": "unknown_role",
        "required_skills": [],
        "preferred_skills": [],
        "min_years_of_experience": 0,
        "salary_range": "unknown",
        "location": "unknown",
        "seniority_level": "unknown",
    }
    defaulted_fields = []
    for field_name, default_value in defaults.items():
        if _needs_default(output.get(field_name)):
            output[field_name] = default_value
            defaulted_fields.append(field_name)
    if defaulted_fields:
        metadata["repair_actions"].append("defaulted_job_fields")
        metadata["defaulted_fields"].extend(defaulted_fields)
    return output


def _with_default_candidate_fields(payload: Any, index: int, metadata: dict[str, Any]) -> Any:
    if not isinstance(payload, dict):
        return payload
    output = dict(payload)
    defaults = {
        "candidate_id": f"c_{index:03d}",
        "skill_vector": [],
        "years_of_experience": 0,
        "salary_expectation": "unknown",
        "location_preference": "unknown",
        "recent_projects": [],
        "availability": "unknown",
        "seniority_level": "unknown",
    }
    defaulted_fields = []
    for field_name, default_value in defaults.items():
        if _needs_default(output.get(field_name)):
            output[field_name] = default_value
            defaulted_fields.append(f"candidate_{index}.{field_name}")
    if defaulted_fields:
        metadata["repair_actions"].append("defaulted_candidate_fields")
        metadata["defaulted_fields"].extend(defaulted_fields)
    return output


def _needs_default(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def _finalize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    repair_actions = list(dict.fromkeys(metadata["repair_actions"]))
    defaulted_fields = list(dict.fromkeys(metadata["defaulted_fields"]))
    penalty = 0.1 * max(metadata["attempt_count"] - 1, 0)
    penalty += 0.1 * sum(
        1
        for action in repair_actions
        if action in {"extracted_json_object", "extracted_json_array", "removed_trailing_commas"}
    )
    penalty += 0.08 * len(defaulted_fields)
    return {
        "attempt_count": metadata["attempt_count"],
        "repair_actions": repair_actions,
        "defaulted_fields": defaulted_fields,
        "confidence_score": round(max(0.2, 1.0 - penalty), 4),
    }


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
