import pytest

from evohunter.core.evaluator import GEPEvaluator
from evohunter.core.protocol import CandidateGene, JobGene, WeightConfig


def make_job_gene():
    return JobGene.from_dict(
        {
            "job_id": "j_001",
            "job_title": "ai_agent_engineer",
            "required_skills": ["python", "llm", "playwright"],
            "preferred_skills": ["scrapy", "postgresql"],
            "min_years_of_experience": 3,
            "salary_range": "25k-40k",
            "location": "shanghai",
            "seniority_level": "mid",
        }
    )


def make_weight_config():
    return WeightConfig.from_dict({})


def make_candidate_gene(candidate_id, skills, years, salary, location, seniority="mid"):
    return CandidateGene.from_dict(
        {
            "candidate_id": candidate_id,
            "skill_vector": skills,
            "years_of_experience": years,
            "salary_expectation": salary,
            "location_preference": location,
            "recent_projects": ["agent_workflow"],
            "availability": "open",
            "seniority_level": seniority,
        }
    )


def test_complete_match_candidate_scores_highest():
    evaluator = GEPEvaluator()
    job_gene = make_job_gene()
    weight_config = make_weight_config()
    strong_candidate = make_candidate_gene(
        "c_001",
        ["python", "llm", "playwright", "scrapy"],
        4,
        "30k-35k",
        "shanghai",
    )
    weak_candidate = make_candidate_gene(
        "c_002",
        ["excel"],
        1,
        "50k-60k",
        "beijing",
        "junior",
    )

    strong_result = evaluator.score_candidate(job_gene, strong_candidate, weight_config)
    weak_result = evaluator.score_candidate(job_gene, weak_candidate, weight_config)

    assert strong_result.match_score > 0.85
    assert weak_result.match_score < strong_result.match_score
    assert weak_result.score_detail["skill_score"] < 0.5


def test_years_and_salary_mismatch_reduce_dimension_scores():
    evaluator = GEPEvaluator()
    result = evaluator.score_candidate(
        make_job_gene(),
        make_candidate_gene("c_003", ["python", "llm", "playwright"], 1, "50k-60k", "shanghai"),
        make_weight_config(),
    )

    assert result.score_detail["experience_score"] == pytest.approx(1 / 3)
    assert result.score_detail["salary_score"] == 0


def test_rank_candidates_orders_by_score_then_candidate_id():
    evaluator = GEPEvaluator()
    job_gene = make_job_gene()
    weight_config = make_weight_config()
    candidates = [
        make_candidate_gene("c_003", ["python"], 1, "50k-60k", "beijing", "junior"),
        make_candidate_gene("c_002", ["python", "llm", "playwright"], 4, "30k-35k", "shanghai"),
        make_candidate_gene("c_001", ["python", "llm", "playwright"], 4, "30k-35k", "shanghai"),
    ]

    results = evaluator.rank_candidates(job_gene, candidates, weight_config)

    assert [result.candidate_id for result in results] == ["c_001", "c_002", "c_003"]


def test_explanation_mentions_main_match_and_gap_points():
    evaluator = GEPEvaluator()
    result = evaluator.score_candidate(
        make_job_gene(),
        make_candidate_gene("c_004", ["python"], 2, "45k-55k", "beijing", "junior"),
        make_weight_config(),
    )

    assert "技能" in result.recommendation_reason
    assert "经验" in result.recommendation_reason
    assert "薪资" in result.recommendation_reason
    assert "地点" in result.recommendation_reason
    assert "职级" in result.recommendation_reason


def test_score_candidate_reports_confidence_and_risk_flags():
    evaluator = GEPEvaluator()
    result = evaluator.score_candidate(
        make_job_gene(),
        make_candidate_gene("c_005", ["python"], 1, "unknown", "beijing", "lead"),
        make_weight_config(),
    )
    payload = result.to_dict()

    assert payload["confidence_score"] < 0.9
    assert payload["risk_flags"] == [
        "skill_gap",
        "experience_gap",
        "salary_unknown",
        "location_mismatch",
        "seniority_gap",
    ]
