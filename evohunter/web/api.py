from __future__ import annotations

from typing import Any

from evohunter.ai import build_evomap_api_key
from evohunter.core.evaluator import GEPEvaluator
from evohunter.core.evolution import evolve_weight_config
from evohunter.data_scraper import scrape_source, scrape_sources
from evohunter.llm_parser import parse_candidate_texts, parse_job_text
from evohunter.outreach import draft_outreach
from evohunter.storage import (
    load_overview,
    save_candidate_genes,
    save_feedback_events,
    save_job_gene,
    save_match_results,
    save_weight_config,
)


class ApiError(RuntimeError):
    pass


def handle_api_request(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    if path == "/api/config":
        return {"has_api_key": _has_api_key()}
    if path == "/api/overview":
        return _overview(payload)
    if path == "/api/scrape":
        return _scrape(payload)
    if path == "/api/parse-job":
        return {"job_gene": parse_job_text(_required_string(payload, "text"))}
    if path == "/api/parse-candidates":
        return {"candidate_genes": parse_candidate_texts(_required_string(payload, "text"))}
    if path == "/api/score":
        return {"match_results": _score(payload)}
    if path == "/api/evolve":
        return {"weight_config": _evolve(payload)}
    if path == "/api/draft-outreach":
        return {"outreach_draft": _draft_outreach(payload)}
    raise ApiError(f"unknown endpoint: {path}")


def _overview(payload: dict[str, Any]) -> dict[str, Any]:
    db_path = _optional_string(payload, "db_path")
    if not db_path:
        return {
            "candidate_count": 0,
            "highest_match_score": 0,
            "current_generation": 0,
            "last_step": "none",
        }
    return load_overview(db_path)


def _scrape(payload: dict[str, Any]) -> dict[str, Any]:
    if "sources" in payload:
        sources = payload["sources"]
        if not isinstance(sources, list):
            raise ApiError("sources must be a list")
        results = scrape_sources(sources)
        return {
            "results": results,
            "text": "\n\n".join(result["text"] for result in results if result["status"] == "success"),
        }
    return {"text": scrape_source(_required_string(payload, "source"))}


def _score(payload: dict[str, Any]) -> list[dict[str, Any]]:
    job_gene = _required_mapping(payload, "job_gene")
    candidate_genes = payload.get("candidate_genes")
    if not isinstance(candidate_genes, list):
        raise ApiError("candidate_genes must be a list")
    weight_config = payload.get("weight_config", {})
    if not isinstance(weight_config, dict):
        raise ApiError("weight_config must be a dict")
    results = GEPEvaluator().rank_candidates(job_gene, candidate_genes, weight_config)
    output = [result.to_dict() for result in results]
    db_path = _optional_string(payload, "db_path")
    if db_path:
        save_job_gene(db_path, job_gene)
        save_candidate_genes(db_path, candidate_genes)
        save_weight_config(db_path, weight_config)
        save_match_results(db_path, output)
    return output


def _evolve(payload: dict[str, Any]) -> dict[str, Any]:
    weight_config = payload.get("weight_config", {})
    feedback_events = payload.get("feedback_events", [])
    if not isinstance(weight_config, dict):
        raise ApiError("weight_config must be a dict")
    if not isinstance(feedback_events, list):
        raise ApiError("feedback_events must be a list")
    output = evolve_weight_config(weight_config, feedback_events).to_dict()
    db_path = _optional_string(payload, "db_path")
    if db_path:
        save_feedback_events(db_path, feedback_events)
        save_weight_config(db_path, output, step="evolve")
    return output


def _draft_outreach(payload: dict[str, Any]) -> dict[str, str]:
    return draft_outreach(
        _required_mapping(payload, "job_gene"),
        _required_mapping(payload, "candidate_gene"),
        _required_mapping(payload, "match_result"),
    )


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


def _optional_string(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ApiError(f"{field_name} must be a string")
    return value.strip()


def _has_api_key() -> bool:
    try:
        build_evomap_api_key()
    except Exception:
        return False
    return True
