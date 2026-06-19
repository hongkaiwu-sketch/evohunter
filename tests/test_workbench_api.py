import pytest

from evohunter.web import api
from evohunter.web.api import ApiError, handle_api_request


def make_job_gene():
    return {
        "job_id": "j_001",
        "job_title": "ai_agent_engineer",
        "required_skills": ["python", "llm"],
        "preferred_skills": ["playwright"],
        "min_years_of_experience": 3,
        "salary_range": "25k-40k",
        "location": "shanghai",
        "seniority_level": "mid",
    }


def make_candidate_gene(candidate_id, skills, years, location="shanghai"):
    return {
        "candidate_id": candidate_id,
        "skill_vector": skills,
        "years_of_experience": years,
        "salary_expectation": "30k-35k",
        "location_preference": location,
        "recent_projects": ["agent_workflow"],
        "availability": "open",
        "seniority_level": "mid",
    }


def test_handle_scrape_returns_cleaned_text(tmp_path):
    source = tmp_path / "candidate.html"
    source.write_text("<h1>Alice</h1><script>x()</script><p>Python</p>", encoding="utf-8")

    output = handle_api_request("/api/scrape", {"source": str(source)})

    assert output == {"text": "Alice\nPython"}


def test_handle_parse_job_uses_llm_parser(monkeypatch):
    monkeypatch.setattr(api, "parse_job_text", lambda text: {"job_id": "j_001", "job_title": text})

    output = handle_api_request("/api/parse-job", {"text": "ai_agent_engineer"})

    assert output == {"job_gene": {"job_id": "j_001", "job_title": "ai_agent_engineer"}}


def test_handle_score_returns_ranked_match_results():
    output = handle_api_request(
        "/api/score",
        {
            "job_gene": make_job_gene(),
            "candidate_genes": [
                make_candidate_gene("c_002", ["excel"], 1, "beijing"),
                make_candidate_gene("c_001", ["python", "llm", "playwright"], 4),
            ],
            "weight_config": {},
        },
    )

    assert [item["candidate_id"] for item in output["match_results"]] == ["c_001", "c_002"]


def test_handle_api_request_rejects_unknown_path():
    with pytest.raises(ApiError, match="unknown endpoint"):
        handle_api_request("/api/missing", {})
