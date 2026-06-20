import sqlite3

from evohunter.storage import (
    initialize_database,
    load_match_result_history,
    save_match_results,
)


def test_storage_initializes_sqlite_schema(tmp_path):
    db_path = tmp_path / "evohunter.db"

    initialize_database(str(db_path))

    with sqlite3.connect(db_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "select name from sqlite_master where type = 'table'"
            )
        }
    assert {
        "job_genes",
        "candidate_genes",
        "match_results",
        "feedback_events",
        "weight_configs",
    }.issubset(table_names)


def test_storage_saves_and_loads_match_result_history(tmp_path):
    db_path = tmp_path / "evohunter.db"
    match_results = [
        {
            "candidate_id": "c_001",
            "job_id": "j_001",
            "match_score": 0.92,
            "score_detail": {"skill_score": 1.0},
            "recommendation_reason": "技能匹配",
        },
        {
            "candidate_id": "c_002",
            "job_id": "j_001",
            "match_score": 0.41,
            "score_detail": {"skill_score": 0.2},
            "recommendation_reason": "技能不足",
        },
    ]

    save_match_results(str(db_path), match_results)
    history = load_match_result_history(str(db_path), "j_001")

    assert [item["candidate_id"] for item in history] == ["c_001", "c_002"]
    assert history[0]["match_score"] == 0.92
