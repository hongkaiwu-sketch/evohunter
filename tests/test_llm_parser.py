import pytest

from evohunter.llm_parser import LLMParserError, parse_candidate_texts, parse_job_text
from evohunter.llm_parser import parse_candidate_texts_with_metadata, parse_job_text_with_metadata


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeCompletion:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def create(self, model, messages):
        self.calls.append({"model": model, "messages": messages})
        return FakeCompletion(self.content)


class FakeChat:
    def __init__(self, content):
        self.completions = FakeCompletions(content)


class FakeClient:
    def __init__(self, content):
        self.chat = FakeChat(content)


class SequenceFakeCompletions:
    def __init__(self, contents):
        self.contents = list(contents)
        self.calls = []

    def create(self, model, messages):
        self.calls.append({"model": model, "messages": messages})
        return FakeCompletion(self.contents.pop(0))


class SequenceFakeChat:
    def __init__(self, contents):
        self.completions = SequenceFakeCompletions(contents)


class SequenceFakeClient:
    def __init__(self, contents):
        self.chat = SequenceFakeChat(contents)


def test_parse_job_text_returns_valid_job_gene():
    client = FakeClient(
        """
        {
          "job_id": "j_001",
          "job_title": "ai_agent_engineer",
          "required_skills": ["Python", "LLM"],
          "preferred_skills": ["Playwright"],
          "min_years_of_experience": 3,
          "salary_range": "25k-40k",
          "location": "Shanghai",
          "seniority_level": "Mid"
        }
        """
    )

    output = parse_job_text("招聘 AI Agent 工程师", client=client)

    assert output["job_id"] == "j_001"
    assert output["required_skills"] == ["python", "llm"]
    assert output["location"] == "shanghai"
    assert client.chat.completions.calls[0]["model"] == "evomap-gemini-3.1-pro-preview"


def test_parse_candidate_texts_accepts_json_fence_and_returns_valid_candidates():
    client = FakeClient(
        """
        ```json
        [
          {
            "candidate_id": "c_001",
            "skill_vector": ["Python", "LLM", "python"],
            "years_of_experience": 4,
            "salary_expectation": "30k-35k",
            "location_preference": "Shanghai",
            "recent_projects": ["agent_workflow"],
            "availability": "open",
            "seniority_level": "mid"
          }
        ]
        ```
        """
    )

    output = parse_candidate_texts("Alice Zhang, Python LLM engineer", client=client)

    assert output == [
        {
            "candidate_id": "c_001",
            "skill_vector": ["python", "llm"],
            "years_of_experience": 4.0,
            "salary_expectation": "30k-35k",
            "location_preference": "shanghai",
            "recent_projects": ["agent_workflow"],
            "availability": "open",
            "seniority_level": "mid",
        }
    ]


def test_parse_job_text_raises_for_invalid_llm_json():
    client = FakeClient("not json")

    with pytest.raises(LLMParserError, match="valid JSON"):
        parse_job_text("招聘 AI Agent 工程师", client=client)


def test_parse_job_text_fills_default_job_id_when_llm_omits_it():
    client = FakeClient(
        """
        {
          "job_title": "ai_agent_engineer",
          "required_skills": ["Python", "LLM"],
          "preferred_skills": [],
          "min_years_of_experience": 3,
          "salary_range": "25k-40k",
          "location": "Shanghai",
          "seniority_level": "Mid"
        }
        """
    )

    output = parse_job_text("招聘 AI Agent 工程师", client=client)

    assert output["job_id"] == "j_001"


def test_parse_candidate_texts_fills_default_candidate_ids_when_llm_omits_them():
    client = FakeClient(
        """
        [
          {
            "skill_vector": ["Python"],
            "years_of_experience": 4,
            "salary_expectation": "30k-35k",
            "location_preference": "Shanghai",
            "recent_projects": [],
            "availability": "open",
            "seniority_level": "mid"
          }
        ]
        """
    )

    output = parse_candidate_texts("Alice Zhang, Python engineer", client=client)

    assert output[0]["candidate_id"] == "c_001"


def test_parse_job_text_with_metadata_retries_and_extracts_json_object():
    client = SequenceFakeClient(
        [
            "not json",
            """
            The parsed JSON is:
            {
              "job_title": "ai_agent_engineer",
              "required_skills": ["Python"],
              "preferred_skills": [],
              "min_years_of_experience": 3,
              "salary_range": "25k-40k",
              "location": "Shanghai",
              "seniority_level": "Mid"
            }
            """,
        ]
    )

    output = parse_job_text_with_metadata("招聘 AI Agent 工程师", client=client, max_attempts=2)

    assert output["job_gene"]["job_id"] == "j_001"
    assert output["job_gene"]["required_skills"] == ["python"]
    assert output["parser_metadata"]["attempt_count"] == 2
    assert "retry_after_invalid_json" in output["parser_metadata"]["repair_actions"]
    assert "extracted_json_object" in output["parser_metadata"]["repair_actions"]
    assert output["parser_metadata"]["confidence_score"] < 1


def test_parse_candidate_texts_with_metadata_fills_missing_fields():
    client = FakeClient(
        """
        [
          {
            "skill_vector": ["Python"],
            "years_of_experience": 4
          }
        ]
        """
    )

    output = parse_candidate_texts_with_metadata("Alice Zhang, Python engineer", client=client)

    assert output["candidate_genes"][0]["candidate_id"] == "c_001"
    assert output["candidate_genes"][0]["salary_expectation"] == "unknown"
    assert output["candidate_genes"][0]["location_preference"] == "unknown"
    assert output["candidate_genes"][0]["recent_projects"] == []
    assert "defaulted_candidate_fields" in output["parser_metadata"]["repair_actions"]
    assert output["parser_metadata"]["confidence_score"] < 0.8
