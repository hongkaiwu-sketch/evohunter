import pytest

from evohunter.outreach import OutreachDraftError, draft_outreach


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


def make_candidate_gene():
    return {
        "candidate_id": "c_001",
        "skill_vector": ["python", "llm", "playwright"],
        "years_of_experience": 4,
        "salary_expectation": "30k-35k",
        "location_preference": "shanghai",
        "recent_projects": ["agent_workflow"],
        "availability": "open",
        "seniority_level": "mid",
    }


def make_match_result():
    return {
        "candidate_id": "c_001",
        "job_id": "j_001",
        "match_score": 0.91,
        "score_detail": {"skill_score": 1.0},
        "recommendation_reason": "技能和地点匹配",
    }


class FakeClient:
    def __init__(self):
        self.sent = False

    class chat:
        class completions:
            @staticmethod
            def create(model, messages):
                return type(
                    "Completion",
                    (),
                    {
                        "choices": [
                            type(
                                "Choice",
                                (),
                                {
                                    "message": type(
                                        "Message",
                                        (),
                                        {
                                            "content": """
                                            {
                                              "candidate_id": "c_001",
                                              "job_id": "j_001",
                                              "subject": "AI Agent Engineer opportunity",
                                              "message_body": "Alice，你的 Python 和 LLM 背景很匹配这个岗位。",
                                              "rationale": "候选人与岗位技能和地点匹配。"
                                            }
                                            """
                                        },
                                    )()
                                },
                            )()
                        ]
                    },
                )()


def test_draft_outreach_returns_snake_case_fields():
    draft = draft_outreach(
        make_job_gene(),
        make_candidate_gene(),
        make_match_result(),
        client=FakeClient(),
    )

    assert set(draft) == {
        "candidate_id",
        "job_id",
        "subject",
        "message_body",
        "rationale",
    }
    assert draft["candidate_id"] == "c_001"
    assert draft["job_id"] == "j_001"
    assert "AI Agent" in draft["subject"]


def test_draft_outreach_rejects_missing_match_result():
    with pytest.raises(OutreachDraftError, match="match_result is required"):
        draft_outreach(make_job_gene(), make_candidate_gene(), None, client=FakeClient())


def test_draft_outreach_does_not_send_messages():
    fake_client = FakeClient()

    draft_outreach(make_job_gene(), make_candidate_gene(), make_match_result(), client=fake_client)

    assert fake_client.sent is False
