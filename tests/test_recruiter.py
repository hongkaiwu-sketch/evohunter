import pytest

from evohunter.workflow import WorkflowContext
from evohunter.workflow.nodes.resume_parsing import (
    RecruiterAssessment,
    RecruiterAssessmentNode,
    _conclusion_label,
    _parse_assessment_response,
)


def test_recruiter_assessment_model():
    assessment = RecruiterAssessment(
        candidate_name="Alice Zhang",
        match_degree=7,
        hard_match_score=5.0,
        hr_bonus_score=2.0,
        main_match_points=["Python/LangChain 经验吻合", "上海匹配"],
        main_deductions=["期望薪资略高于预算"],
        conclusion="可推荐",
        background_summary="4年AI工程师，擅长LLM应用开发",
        reasons_for_recommendation=[
            "具备扎实的LLM应用开发经验，主导过企业级RAG系统构建",
            "有完整的Agent工作流设计经验",
        ],
        tech_tags=["Python", "LangChain", "Kubernetes", "Go", "PostgreSQL"],
        current_salary="35k/月",
        current_level="高级工程师",
        reason_for_leaving="寻求更有挑战的技术方向",
        recommendation_text="完整推荐词...",
        requires_human_input=False,
        missing_fields=[],
    )

    d = assessment.to_dict()
    assert d["candidate_name"] == "Alice Zhang"
    assert d["match_degree"] == 7
    assert "recommendation_text" in d
    assert len(d["tech_tags"]) == 5


def test_conclusion_label_zh():
    assert _conclusion_label(4, "zh") == "不合格"
    assert _conclusion_label(6, "zh") == "可尝试"
    assert _conclusion_label(7, "zh") == "可推荐"
    assert _conclusion_label(9, "zh") == "强匹配"


def test_conclusion_label_en():
    assert _conclusion_label(4, "en") == "Not qualified"
    assert _conclusion_label(6, "en") == "Worth trying"
    assert _conclusion_label(7, "en") == "Recommendable"
    assert _conclusion_label(9, "en") == "Strong match"


def test_parse_assessment_response_valid_json():
    raw = '{"candidate_name": "Alice", "match_degree": 8}'
    result = _parse_assessment_response(raw)
    assert result["candidate_name"] == "Alice"
    assert result["match_degree"] == 8


def test_parse_assessment_response_with_fence():
    raw = '```json\n{"candidate_name": "Bob", "match_degree": 6}\n```'
    result = _parse_assessment_response(raw)
    assert result["candidate_name"] == "Bob"
    assert result["match_degree"] == 6


def test_parse_assessment_response_embedded():
    raw = 'Here is the assessment:\n{"candidate_name": "Charlie", "match_degree": 7}\n\nHope this helps.'
    result = _parse_assessment_response(raw)
    assert result["candidate_name"] == "Charlie"


def test_parse_assessment_response_invalid():
    result = _parse_assessment_response("Not JSON at all")
    assert result == {}


def test_apply_rules_high_score_missing_info():
    """Score >= 7 but missing salary/leaving reason → requires_human_input."""
    node = RecruiterAssessmentNode()
    data = {
        "candidate_name": "Test",
        "match_degree": 8,
        "hard_match_score": 6.0,
        "hr_bonus_score": 2.0,
        "current_salary": "",
        "current_level": "Senior",
        "reason_for_leaving": "",
        "background_summary": "Test background",
    }
    assessment = node._apply_rules(data, "zh")
    assert assessment.match_degree == 8
    assert assessment.requires_human_input is True
    assert "当前薪资 / 职级" in assessment.missing_fields


def test_apply_rules_low_score():
    """Score < 7 → requires_human_input, no recommendation text."""
    node = RecruiterAssessmentNode()
    data = {
        "candidate_name": "Test",
        "match_degree": 5,
        "current_salary": "30k",
        "current_level": "Mid",
        "reason_for_leaving": "Growth",
    }
    assessment = node._apply_rules(data, "zh")
    assert assessment.match_degree == 5
    assert assessment.requires_human_input is True
    assert assessment.recommendation_text is None


def test_apply_rules_perfect_score():
    """Score >= 7, all info present → auto generate recommendation."""
    node = RecruiterAssessmentNode()
    data = {
        "candidate_name": "Alice",
        "match_degree": 8,
        "hard_match_score": 6.0,
        "hr_bonus_score": 2.0,
        "current_salary": "35k/月",
        "current_level": "高级工程师",
        "reason_for_leaving": "寻求成长机会",
        "background_summary": "背景概述...",
        "reasons_for_recommendation": ["理由1", "理由2", "理由3"],
        "tech_tags": ["Python", "LLM"],
        "recommendation_text": "完整推荐词...",
    }
    assessment = node._apply_rules(data, "zh")
    assert assessment.match_degree == 8
    assert assessment.requires_human_input is False
    assert assessment.recommendation_text is not None


def test_apply_rules_en():
    node = RecruiterAssessmentNode()
    data = {
        "candidate_name": "Test",
        "match_degree": 6,
        "current_salary": "",
        "current_level": "",
        "reason_for_leaving": "",
    }
    assessment = node._apply_rules(data, "en")
    assert "current_salary" in assessment.missing_fields
    assert "reason_for_leaving" in assessment.missing_fields


def test_node_execute_no_jd():
    """Resume parsing without JD → returns error."""
    node = RecruiterAssessmentNode()
    context = WorkflowContext(
        workflow_id="test",
        input_data={"resume_text": "Resume content..."},
    )
    context.set_node_result("jd_generation", {})
    result = node.execute(context)
    assert result.get("error") == "no_jd" or result.get("match_degree", 0) == 0


def test_node_execute_no_resume():
    """Resume parsing without resume → returns error."""
    node = RecruiterAssessmentNode()
    context = WorkflowContext(workflow_id="test", input_data={})
    context.set_node_result("jd_generation", {"job_gene": {"job_id": "j_001"}})
    result = node.execute(context)
    assert result.get("error") == "no_resume"
