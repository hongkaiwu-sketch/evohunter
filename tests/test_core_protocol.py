import pytest

from evohunter.core.protocol import (
    CandidateGene,
    FeedbackEvent,
    JobGene,
    MatchResult,
    ValidationError,
    WeightConfig,
    normalize_skill_vector,
    validate_candidate_gene,
    validate_feedback_event,
    validate_job_gene,
    validate_weight_config,
)


def test_candidate_gene_round_trips_and_normalizes_skills():
    candidate_gene = CandidateGene.from_dict(
        {
            "candidate_id": "c_001",
            "skill_vector": [" Python ", "LLM", "python", "Scrapy"],
            "years_of_experience": 4,
            "salary_expectation": "30k-40k",
            "location_preference": "shanghai",
            "recent_projects": ["agent_workflow"],
            "availability": "open",
            "seniority_level": "mid",
        }
    )

    assert candidate_gene.skill_vector == ["python", "llm", "scrapy"]
    assert candidate_gene.to_dict()["candidate_id"] == "c_001"


def test_job_gene_missing_required_field_raises_validation_error():
    with pytest.raises(ValidationError, match="job_id"):
        JobGene.from_dict(
            {
                "job_title": "ai_agent_engineer",
                "required_skills": ["python"],
                "salary_range": "25k-40k",
                "location": "shanghai",
                "seniority_level": "mid",
            }
        )


def test_weight_config_normalizes_weight_sum():
    weight_config = WeightConfig.from_dict(
        {
            "generation": 2,
            "skill_weight": 4,
            "experience_weight": 2,
            "salary_weight": 1.5,
            "location_weight": 1.5,
            "seniority_weight": 1,
        }
    )

    assert weight_config.generation == 2
    assert sum(weight_config.weights().values()) == pytest.approx(1.0)
    assert weight_config.skill_weight == pytest.approx(0.4)


def test_unknown_feedback_type_raises_validation_error():
    with pytest.raises(ValidationError, match="event_type"):
        FeedbackEvent.from_dict(
            {
                "candidate_id": "c_001",
                "job_id": "j_001",
                "event_type": "reply",
                "event_time": "2026-06-19T17:30:00+08:00",
            }
        )


def test_validator_functions_accept_dicts_and_return_models():
    job_gene = validate_job_gene(
        {
            "job_id": "j_001",
            "job_title": "ai_agent_engineer",
            "required_skills": ["Python"],
            "preferred_skills": ["Scrapy"],
            "min_years_of_experience": 3,
            "salary_range": "25k-40k",
            "location": "Shanghai",
            "seniority_level": "mid",
        }
    )
    candidate_gene = validate_candidate_gene(
        {
            "candidate_id": "c_001",
            "skill_vector": ["python"],
            "years_of_experience": 4,
            "salary_expectation": "30k-40k",
            "location_preference": "shanghai",
        }
    )
    feedback_event = validate_feedback_event(
        {
            "candidate_id": "c_001",
            "job_id": "j_001",
            "event_type": "reply_positive",
        }
    )
    weight_config = validate_weight_config({})

    assert job_gene.required_skills == ["python"]
    assert candidate_gene.availability == "unknown"
    assert feedback_event.event_type == "reply_positive"
    assert weight_config.to_dict()["generation"] == 0


def test_normalize_skill_vector_rejects_non_list_values():
    with pytest.raises(ValidationError, match="skill_vector"):
        normalize_skill_vector("python")


def test_match_result_round_trips_to_dict():
    match_result = MatchResult.from_dict(
        {
            "candidate_id": "c_001",
            "job_id": "j_001",
            "match_score": 0.86,
            "score_detail": {"skill_score": 0.9},
            "recommendation_reason": "技能匹配度高。",
        }
    )

    assert match_result.to_dict()["match_score"] == 0.86
