from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from evohunter.rag.models import CompanyProfile, CultureTag, JDTemplate


class StructuredKnowledgeStore:
    """SQLite-backed structured storage for RAG knowledge base.

    Tables (prefixed with ``rag_`` to avoid collisions with main store):
    - rag_company_profiles
    - rag_jd_templates
    - rag_culture_tags
    - rag_company_tags  (many-to-many)
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def initialize_tables(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                create table if not exists rag_company_profiles (
                  company_hash text primary key,
                  payload text not null,
                  created_at text not null default current_timestamp,
                  updated_at text not null default current_timestamp
                );
                create table if not exists rag_jd_templates (
                  template_id text primary key,
                  payload text not null,
                  created_at text not null default current_timestamp
                );
                create table if not exists rag_culture_tags (
                  tag_id text primary key,
                  name text not null unique,
                  category text not null,
                  description text not null default ''
                );
                create table if not exists rag_company_tags (
                  company_hash text not null,
                  tag_id text not null,
                  primary key (company_hash, tag_id)
                );
                """
            )

    # ── Company Profiles ────────────────────────────────────────────────

    def save_company_profile(self, profile: CompanyProfile) -> None:
        self.initialize_tables()
        payload = _dump(profile.to_dict())
        with self._connect() as conn:
            conn.execute(
                """
                insert into rag_company_profiles (company_hash, payload, updated_at)
                values (?, ?, current_timestamp)
                on conflict(company_hash) do update set
                  payload = excluded.payload,
                  updated_at = current_timestamp
                """,
                (profile.company_hash, payload),
            )
            # Sync culture tags
            for tag_name in profile.culture_tags:
                tag_id = _tag_id(tag_name)
                conn.execute(
                    """
                    insert or ignore into rag_culture_tags (tag_id, name, category, description)
                    values (?, ?, 'values', '')
                    """,
                    (tag_id, tag_name),
                )
                conn.execute(
                    """
                    insert or ignore into rag_company_tags (company_hash, tag_id)
                    values (?, ?)
                    """,
                    (profile.company_hash, tag_id),
                )

    def get_company_profile(self, company_hash: str) -> CompanyProfile | None:
        self.initialize_tables()
        with self._connect() as conn:
            row = conn.execute(
                "select payload from rag_company_profiles where company_hash = ?",
                (company_hash,),
            ).fetchone()
        if row is None:
            return None
        return CompanyProfile.from_dict(_load(row[0]))

    def search_company_by_tags(self, tags: list[str]) -> list[CompanyProfile]:
        self.initialize_tables()
        if not tags:
            return []
        tag_ids = [_tag_id(t) for t in tags]
        placeholders = ",".join(["?" for _ in tag_ids])
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                select distinct p.payload
                from rag_company_profiles p
                join rag_company_tags ct on p.company_hash = ct.company_hash
                where ct.tag_id in ({placeholders})
                limit 20
                """,
                tag_ids,
            ).fetchall()
        return [CompanyProfile.from_dict(_load(r[0])) for r in rows]

    def list_company_profiles(self) -> list[CompanyProfile]:
        self.initialize_tables()
        with self._connect() as conn:
            rows = conn.execute(
                "select payload from rag_company_profiles order by updated_at desc"
            ).fetchall()
        return [CompanyProfile.from_dict(_load(r[0])) for r in rows]

    # ── JD Templates ────────────────────────────────────────────────────

    def save_jd_template(self, template: JDTemplate) -> None:
        self.initialize_tables()
        payload = _dump(template.to_dict())
        with self._connect() as conn:
            conn.execute(
                """
                insert into rag_jd_templates (template_id, payload)
                values (?, ?)
                on conflict(template_id) do update set payload = excluded.payload
                """,
                (template.template_id, payload),
            )

    def search_jd_templates(
        self,
        role_category: str | None = None,
        seniority: str | None = None,
    ) -> list[JDTemplate]:
        self.initialize_tables()
        with self._connect() as conn:
            rows = conn.execute(
                "select payload from rag_jd_templates order by created_at desc"
            ).fetchall()

        results = [JDTemplate.from_dict(_load(r[0])) for r in rows]

        if role_category:
            results = [
                t
                for t in results
                if t.role_category.lower() == role_category.lower()
                or role_category.lower() in t.role_category.lower()
            ]
        if seniority:
            results = [
                t
                for t in results
                if t.seniority_level.lower() == seniority.lower()
            ]

        return results

    def list_jd_templates(self) -> list[JDTemplate]:
        self.initialize_tables()
        with self._connect() as conn:
            rows = conn.execute(
                "select payload from rag_jd_templates order by created_at desc"
            ).fetchall()
        return [JDTemplate.from_dict(_load(r[0])) for r in rows]

    # ── Culture Tags ────────────────────────────────────────────────────

    def save_culture_tag(self, tag: CultureTag) -> None:
        self.initialize_tables()
        with self._connect() as conn:
            conn.execute(
                """
                insert or replace into rag_culture_tags (tag_id, name, category, description)
                values (?, ?, ?, ?)
                """,
                (tag.tag_id, tag.name, tag.category, tag.description),
            )

    def get_all_tags(self) -> list[CultureTag]:
        self.initialize_tables()
        with self._connect() as conn:
            rows = conn.execute(
                "select tag_id, name, category, description from rag_culture_tags"
            ).fetchall()
        return [
            CultureTag(tag_id=r[0], name=r[1], category=r[2], description=r[3])
            for r in rows
        ]

    def search_tags(self, category: str | None = None) -> list[CultureTag]:
        self.initialize_tables()
        if category:
            with self._connect() as conn:
                rows = conn.execute(
                    "select tag_id, name, category, description from rag_culture_tags where category = ?",
                    (category,),
                ).fetchall()
        else:
            return self.get_all_tags()
        return [
            CultureTag(tag_id=r[0], name=r[1], category=r[2], description=r[3])
            for r in rows
        ]

    # ── Helpers ─────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        path = Path(self._db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn


def _tag_id(name: str) -> str:
    return f"tag_{name.lower().replace(' ', '_').replace('-', '_')}"


def _dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _load(raw: str) -> dict[str, Any]:
    return json.loads(raw)
