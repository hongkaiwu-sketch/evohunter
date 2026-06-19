from __future__ import annotations

from typing import Any

from evohunter.ai import build_evomap_api_key
from evohunter.core.evaluator import GEPEvaluator
from evohunter.core.evolution import evolve_weight_config
from evohunter.data_scraper import scrape_source
from evohunter.llm_parser import parse_candidate_texts, parse_job_text


class ApiError(RuntimeError):
    pass


def handle_api_request(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    if path == "/api/config":
        return {"has_api_key": _has_api_key()}
    if path == "/api/scrape":
        return {"text": scrape_source(_required_string(payload, "source"))}
    if path == "/api/parse-job":
        return {"job_gene": parse_job_text(_required_string(payload, "text"))}
    if path == "/api/parse-candidates":
        return {"candidate_genes": parse_candidate_texts(_required_string(payload, "text"))}
    if path == "/api/score":
        return {"match_results": _score(payload)}
    if path == "/api/evolve":
        return {"weight_config": _evolve(payload)}
    raise ApiError(f"unknown endpoint: {path}")


def _score(payload: dict[str, Any]) -> list[dict[str, Any]]:
    job_gene = _required_mapping(payload, "job_gene")
    candidate_genes = payload.get("candidate_genes")
    if not isinstance(candidate_genes, list):
        raise ApiError("candidate_genes must be a list")
    weight_config = payload.get("weight_config", {})
    if not isinstance(weight_config, dict):
        raise ApiError("weight_config must be a dict")
    results = GEPEvaluator().rank_candidates(job_gene, candidate_genes, weight_config)
    return [result.to_dict() for result in results]


def _evolve(payload: dict[str, Any]) -> dict[str, Any]:
    weight_config = payload.get("weight_config", {})
    feedback_events = payload.get("feedback_events", [])
    if not isinstance(weight_config, dict):
        raise ApiError("weight_config must be a dict")
    if not isinstance(feedback_events, list):
        raise ApiError("feedback_events must be a list")
    return evolve_weight_config(weight_config, feedback_events).to_dict()


def _required_string(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(f"{field_name} must be a non-empty string")
    return value.strip()


def _required_mapping(payload: dict[str, Any], field_name: str) -> dict[str, Any]:
    value = payload.get(field_name)
    if not isinstance(value, dict):
        raise ApiError(f"{field_name} must be a dict")
    return value


def _has_api_key() -> bool:
    try:
        build_evomap_api_key()
    except Exception:
        return False
    return True
