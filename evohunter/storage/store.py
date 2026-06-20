from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from evohunter.core.protocol import (
    FeedbackEvent,
    MatchResult,
    WeightConfig,
    validate_candidate_gene,
    validate_job_gene,
)


def initialize_database(db_path: str) -> None:
    with _connect(db_path) as connection:
        connection.executescript(
            """
            create table if not exists job_genes (
              job_id text primary key,
              payload text not null,
              updated_at text not null default current_timestamp
            );
            create table if not exists candidate_genes (
              candidate_id text primary key,
              payload text not null,
              updated_at text not null default current_timestamp
            );
            create table if not exists match_results (
              id integer primary key autoincrement,
              job_id text not null,
              candidate_id text not null,
              match_score real not null,
              payload text not null,
              created_at text not null default current_timestamp
            );
            create table if not exists feedback_events (
              id integer primary key autoincrement,
              job_id text not null,
              candidate_id text not null,
              event_type text not null,
              payload text not null,
              created_at text not null default current_timestamp
            );
            create table if not exists weight_configs (
              id integer primary key autoincrement,
              generation integer not null,
              payload text not null,
              created_at text not null default current_timestamp
            );
            create table if not exists workflow_events (
              id integer primary key autoincrement,
              step text not null,
              created_at text not null default current_timestamp
            );
            """
        )


def save_job_gene(db_path: str, job_gene: dict[str, Any]) -> None:
    payload = validate_job_gene(job_gene).to_dict()
    initialize_database(db_path)
    with _connect(db_path) as connection:
        connection.execute(
            """
            insert into job_genes (job_id, payload, updated_at)
            values (?, ?, current_timestamp)
            on conflict(job_id) do update set
              payload = excluded.payload,
              updated_at = current_timestamp
            """,
            (payload["job_id"], _dump(payload)),
        )


def save_candidate_genes(db_path: str, candidate_genes: list[dict[str, Any]]) -> None:
    initialize_database(db_path)
    with _connect(db_path) as connection:
        for candidate_gene in candidate_genes:
            payload = validate_candidate_gene(candidate_gene).to_dict()
            connection.execute(
                """
                insert into candidate_genes (candidate_id, payload, updated_at)
                values (?, ?, current_timestamp)
                on conflict(candidate_id) do update set
                  payload = excluded.payload,
                  updated_at = current_timestamp
                """,
                (payload["candidate_id"], _dump(payload)),
            )


def save_match_results(db_path: str, match_results: list[dict[str, Any]]) -> None:
    initialize_database(db_path)
    with _connect(db_path) as connection:
        for match_result in match_results:
            payload = MatchResult.from_dict(match_result).to_dict()
            connection.execute(
                """
                insert into match_results (job_id, candidate_id, match_score, payload)
                values (?, ?, ?, ?)
                """,
                (
                    payload["job_id"],
                    payload["candidate_id"],
                    payload["match_score"],
                    _dump(payload),
                ),
            )
        _record_workflow_step(connection, "score")


def save_feedback_events(db_path: str, feedback_events: list[dict[str, Any]]) -> None:
    initialize_database(db_path)
    with _connect(db_path) as connection:
        for feedback_event in feedback_events:
            payload = FeedbackEvent.from_dict(feedback_event).to_dict()
            connection.execute(
                """
                insert into feedback_events (job_id, candidate_id, event_type, payload)
                values (?, ?, ?, ?)
                """,
                (
                    payload["job_id"],
                    payload["candidate_id"],
                    payload["event_type"],
                    _dump(payload),
                ),
            )


def save_weight_config(db_path: str, weight_config: dict[str, Any], step: str | None = None) -> None:
    payload = WeightConfig.from_dict(weight_config).to_dict()
    initialize_database(db_path)
    with _connect(db_path) as connection:
        connection.execute(
            """
            insert into weight_configs (generation, payload)
            values (?, ?)
            """,
            (payload["generation"], _dump(payload)),
        )
        if step:
            _record_workflow_step(connection, step)


def load_match_result_history(db_path: str, job_id: str) -> list[dict[str, Any]]:
    initialize_database(db_path)
    with _connect(db_path) as connection:
        rows = connection.execute(
            """
            select payload
            from match_results
            where job_id = ?
            order by id asc
            """,
            (job_id,),
        ).fetchall()
    return [_load(row["payload"]) for row in rows]


def load_overview(db_path: str) -> dict[str, Any]:
    initialize_database(db_path)
    with _connect(db_path) as connection:
        candidate_count = connection.execute(
            "select count(distinct candidate_id) from match_results"
        ).fetchone()[0]
        highest_match_score = connection.execute(
            "select max(match_score) from match_results"
        ).fetchone()[0]
        generation_row = connection.execute(
            "select generation from weight_configs order by id desc limit 1"
        ).fetchone()
        last_step_row = connection.execute(
            "select step from workflow_events order by id desc limit 1"
        ).fetchone()
    return {
        "candidate_count": int(candidate_count or 0),
        "highest_match_score": round(float(highest_match_score or 0), 4),
        "current_generation": int(generation_row[0]) if generation_row else 0,
        "last_step": last_step_row[0] if last_step_row else "none",
    }


def _connect(db_path: str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def _record_workflow_step(connection: sqlite3.Connection, step: str) -> None:
    connection.execute("insert into workflow_events (step) values (?)", (step,))


def _dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _load(payload: str) -> dict[str, Any]:
    return json.loads(payload)
