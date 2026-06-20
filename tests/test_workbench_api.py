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


def test_workbench_overview_updates_after_scoring(tmp_path):
    db_path = tmp_path / "workbench.db"
    handle_api_request(
        "/api/score",
        {
            "db_path": str(db_path),
            "job_gene": make_job_gene(),
            "candidate_genes": [
                make_candidate_gene("c_002", ["excel"], 1, "beijing"),
                make_candidate_gene("c_001", ["python", "llm", "playwright"], 4),
            ],
            "weight_config": {"generation": 3},
        },
    )

    overview = handle_api_request("/api/overview", {"db_path": str(db_path)})

    assert overview["candidate_count"] == 2
    assert overview["highest_match_score"] > 0
    assert overview["current_generation"] == 3
    assert overview["last_step"] == "score"


def test_web_api_can_use_optional_db_path(tmp_path):
    db_path = tmp_path / "api.db"

    output = handle_api_request(
        "/api/score",
        {
            "db_path": str(db_path),
            "job_gene": make_job_gene(),
            "candidate_genes": [make_candidate_gene("c_001", ["python", "llm"], 4)],
            "weight_config": {},
        },
    )

    assert output["match_results"][0]["candidate_id"] == "c_001"
    history = handle_api_request("/api/overview", {"db_path": str(db_path)})
    assert history["candidate_count"] == 1


def test_handle_draft_outreach_uses_outreach_module(monkeypatch):
    def fake_draft_outreach(job_gene, candidate_gene, match_result):
        assert job_gene["job_id"] == "j_001"
        assert candidate_gene["candidate_id"] == "c_001"
        assert match_result["candidate_id"] == "c_001"
        return {
            "candidate_id": "c_001",
            "job_id": "j_001",
            "subject": "AI Agent Engineer opportunity",
            "message_body": "你的经验很匹配。",
            "rationale": "技能和岗位匹配。",
        }

    monkeypatch.setattr(api, "draft_outreach", fake_draft_outreach)

    output = handle_api_request(
        "/api/draft-outreach",
        {
            "job_gene": make_job_gene(),
            "candidate_gene": make_candidate_gene("c_001", ["python", "llm"], 4),
            "match_result": {
                "candidate_id": "c_001",
                "job_id": "j_001",
                "match_score": 0.9,
                "score_detail": {"skill_score": 1.0},
                "recommendation_reason": "技能匹配",
            },
        },
    )

    assert output["outreach_draft"]["message_body"] == "你的经验很匹配。"


def test_handle_scrape_accepts_batch_sources(tmp_path):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("Alice", encoding="utf-8")
    second.write_text("Bob", encoding="utf-8")

    output = handle_api_request(
        "/api/scrape",
        {"sources": [str(first), str(second)]},
    )

    assert [result["text"] for result in output["results"]] == ["Alice", "Bob"]
    assert output["text"] == "Alice\n\nBob"


def test_handle_api_request_rejects_unknown_path():
    with pytest.raises(ApiError, match="unknown endpoint"):
        handle_api_request("/api/missing", {})
