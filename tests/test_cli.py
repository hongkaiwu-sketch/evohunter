import json
import subprocess
import sys


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "evohunter", *args],
        text=True,
        capture_output=True,
        check=False,
    )


def test_score_command_writes_ranked_match_results(tmp_path):
    job_path = tmp_path / "job_gene.json"
    candidates_path = tmp_path / "candidate_genes.json"
    weights_path = tmp_path / "weight_config.json"
    output_path = tmp_path / "match_results.json"
    write_json(
        job_path,
        {
            "job_id": "j_001",
            "job_title": "ai_agent_engineer",
            "required_skills": ["python", "llm", "playwright"],
            "preferred_skills": ["scrapy"],
            "min_years_of_experience": 3,
            "salary_range": "25k-40k",
            "location": "shanghai",
            "seniority_level": "mid",
        },
    )
    write_json(
        candidates_path,
        [
            {
                "candidate_id": "c_002",
                "skill_vector": ["excel"],
                "years_of_experience": 1,
                "salary_expectation": "50k-60k",
                "location_preference": "beijing",
                "seniority_level": "junior",
            },
            {
                "candidate_id": "c_001",
                "skill_vector": ["python", "llm", "playwright"],
                "years_of_experience": 4,
                "salary_expectation": "30k-35k",
                "location_preference": "shanghai",
                "seniority_level": "mid",
            },
        ],
    )
    write_json(weights_path, {})

    result = run_cli(
        "score",
        "--job",
        str(job_path),
        "--candidates",
        str(candidates_path),
        "--weights",
        str(weights_path),
        "--output",
        str(output_path),
    )

    assert result.returncode == 0
    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert [item["candidate_id"] for item in output] == ["c_001", "c_002"]
    assert output[0]["score_detail"]["seniority_score"] == 1.0


def test_evolve_command_writes_updated_weight_config(tmp_path):
    weights_path = tmp_path / "weight_config.json"
    feedback_path = tmp_path / "feedback_events.json"
    output_path = tmp_path / "weight_config.evolved.json"
    write_json(weights_path, {})
    write_json(
        feedback_path,
        [
            {"candidate_id": "c_001", "job_id": "j_001", "event_type": "reply_positive"},
            {"candidate_id": "c_002", "job_id": "j_001", "event_type": "interview_passed"},
        ],
    )

    result = run_cli(
        "evolve",
        "--weights",
        str(weights_path),
        "--feedback",
        str(feedback_path),
        "--output",
        str(output_path),
    )

    assert result.returncode == 0
    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert output["generation"] == 1
    assert output["skill_weight"] > 0.4


def test_score_command_returns_nonzero_for_missing_file(tmp_path):
    result = run_cli(
        "score",
        "--job",
        str(tmp_path / "missing.json"),
        "--candidates",
        str(tmp_path / "candidate_genes.json"),
        "--weights",
        str(tmp_path / "weight_config.json"),
        "--output",
        str(tmp_path / "match_results.json"),
    )

    assert result.returncode != 0
    assert "File not found" in result.stderr


def test_score_command_returns_nonzero_for_invalid_json(tmp_path):
    job_path = tmp_path / "job_gene.json"
    candidates_path = tmp_path / "candidate_genes.json"
    weights_path = tmp_path / "weight_config.json"
    job_path.write_text("{bad json", encoding="utf-8")
    write_json(candidates_path, [])
    write_json(weights_path, {})

    result = run_cli(
        "score",
        "--job",
        str(job_path),
        "--candidates",
        str(candidates_path),
        "--weights",
        str(weights_path),
        "--output",
        str(tmp_path / "match_results.json"),
    )

    assert result.returncode != 0
    assert "Invalid JSON" in result.stderr


def test_scrape_command_writes_cleaned_text(tmp_path):
    source_path = tmp_path / "profile.html"
    output_path = tmp_path / "scraped_text.txt"
    source_path.write_text("<h1>Alice Zhang</h1><script>x()</script><p>Python</p>", encoding="utf-8")

    result = run_cli(
        "scrape",
        "--source",
        str(source_path),
        "--output",
        str(output_path),
    )

    assert result.returncode == 0
    assert output_path.read_text(encoding="utf-8") == "Alice Zhang\nPython\n"


def test_parse_job_command_writes_job_gene(tmp_path, monkeypatch):
    import evohunter.__main__ as cli

    input_path = tmp_path / "jd.txt"
    output_path = tmp_path / "job_gene.json"
    input_path.write_text("招聘 AI Agent 工程师", encoding="utf-8")

    def fake_parse_job_text(text):
        assert text == "招聘 AI Agent 工程师"
        return {
            "job_id": "j_001",
            "job_title": "ai_agent_engineer",
            "required_skills": ["python"],
            "preferred_skills": [],
            "min_years_of_experience": 3,
            "salary_range": "25k-40k",
            "location": "shanghai",
            "seniority_level": "mid",
        }

    monkeypatch.setattr(cli, "parse_job_text", fake_parse_job_text)

    result = cli.main(["parse-job", "--input", str(input_path), "--output", str(output_path)])

    assert result == 0
    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert output["job_id"] == "j_001"


def test_parse_candidates_command_writes_candidate_genes(tmp_path, monkeypatch):
    import evohunter.__main__ as cli

    input_path = tmp_path / "candidates.txt"
    output_path = tmp_path / "candidate_genes.json"
    input_path.write_text("Alice Zhang, Python engineer", encoding="utf-8")

    def fake_parse_candidate_texts(text):
        assert text == "Alice Zhang, Python engineer"
        return [
            {
                "candidate_id": "c_001",
                "skill_vector": ["python"],
                "years_of_experience": 4,
                "salary_expectation": "30k-35k",
                "location_preference": "shanghai",
                "recent_projects": ["agent_workflow"],
                "availability": "open",
                "seniority_level": "mid",
            }
        ]

    monkeypatch.setattr(cli, "parse_candidate_texts", fake_parse_candidate_texts)

    result = cli.main(["parse-candidates", "--input", str(input_path), "--output", str(output_path)])

    assert result == 0
    output = json.loads(output_path.read_text(encoding="utf-8"))
    assert output[0]["candidate_id"] == "c_001"


def test_serve_command_help_lists_web_options():
    result = run_cli("serve", "--help")

    assert result.returncode == 0
    assert "--host" in result.stdout
    assert "--port" in result.stdout
