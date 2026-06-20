from __future__ import annotations

from typing import Any

from evohunter.rag.embedding import EmbeddingProvider
from evohunter.rag.models import CompanyProfile, CultureTag, JDTemplate, RAGContext, RAGResult
from evohunter.rag.structured_store import StructuredKnowledgeStore
from evohunter.rag.vector_store import VectorStore


class KnowledgeBaseManager:
    """Hybrid RAG orchestrator: vector search + structured queries.

    Retrieval strategy:
    1. Structured query for exact match (company profile, tags, role)
    2. Vector search for semantic similarity (historical JDs)
    3. Merge and re-rank results
    4. Return sorted ``RAGResult``
    """

    def __init__(
        self,
        vector_store: VectorStore,
        structured_store: StructuredKnowledgeStore,
        embedder: EmbeddingProvider,
    ) -> None:
        self._vector = vector_store
        self._structured = structured_store
        self._embedder = embedder

    def retrieve_for_jd_generation(
        self,
        company_name: str,
        role_title: str,
        industry: str | None = None,
        top_k: int = 3,
    ) -> RAGResult:
        """Hybrid retrieval for JD generation context.

        1. Look up company profile from structured store
        2. Vector search on historical JDs with role_title
        3. Structured search for JD templates matching role_category
        4. Merge, deduplicate, rank by score
        """
        contexts: list[RAGContext] = []

        # Structured: company profile
        company_hash = _disguise_company_name(company_name)
        profile = self._structured.get_company_profile(company_hash)
        if profile is not None:
            contexts.append(
                RAGContext(
                    source_type="company_profile",
                    source_id=company_hash,
                    content=profile.description,
                    score=0.95,
                    metadata={
                        "culture_tags": profile.culture_tags,
                        "industry": profile.industry,
                        "remote_policy": profile.remote_policy,
                        "interview_process": profile.interview_process,
                    },
                )
            )

        # Vector: semantic search on JD templates
        query_text = role_title
        if industry:
            query_text = f"{industry} {role_title}"
        try:
            query_embedding = self._embedder.embed_text(query_text)
            vector_results = self._vector.search(query_embedding, top_k)
            for ext_id, score, meta in vector_results:
                if score > 0.3:  # minimum relevance threshold
                    contexts.append(
                        RAGContext(
                            source_type="jd_template",
                            source_id=ext_id,
                            content=meta.get("content", ""),
                            score=score,
                            metadata=meta,
                        )
                    )
        except Exception:
            pass  # vector search is optional

        # Structured: exact template match
        if role_title:
            normalized_role = _normalize_role_category(role_title)
            templates = self._structured.search_jd_templates(
                role_category=normalized_role,
            )
            for t in templates[:2]:
                contexts.append(
                    RAGContext(
                        source_type="jd_template",
                        source_id=t.template_id,
                        content=t.content or f"{t.role_category} - {t.seniority_level}",
                        score=0.70,
                        metadata={
                            "required_skills": t.required_skills_template,
                            "preferred_skills": t.preferred_skills_template,
                            "salary_template": t.salary_template,
                            "success_rate": t.success_rate,
                            "sections": t.sections,
                        },
                    )
                )

        # De-duplicate by content and sort by score
        seen = set()
        unique: list[RAGContext] = []
        for ctx in sorted(contexts, key=lambda c: c.score, reverse=True):
            key = (ctx.source_type, ctx.source_id)
            if key not in seen:
                seen.add(key)
                unique.append(ctx)

        return RAGResult(
            query=f"{company_name} {role_title}",
            contexts=unique,
            total_found=len(unique),
        )

    def retrieve_for_resume_parsing(
        self,
        resume_text: str,
        top_k: int = 3,
    ) -> RAGResult | None:
        """Optional: retrieve relevant context for recruiter agent enrichment."""
        if not resume_text.strip():
            return None

        try:
            query_embedding = self._embedder.embed_text(resume_text[:2000])
            results = self._vector.search(query_embedding, top_k)
        except Exception:
            return None

        contexts = [
            RAGContext(
                source_type="jd_template",
                source_id=ext_id,
                content=meta.get("content", ""),
                score=score,
                metadata=meta,
            )
            for ext_id, score, meta in results
            if score > 0.3
        ]

        return RAGResult(
            query=f"resume:{_resume_preview(resume_text)}",
            contexts=contexts,
            total_found=len(contexts),
        )

    # ── Indexing ────────────────────────────────────────────────────────

    def index_company(
        self,
        company_name: str,
        industry: str,
        description: str = "",
        culture_tags: list[str] | None = None,
        values: list[str] | None = None,
        typical_salary_ranges: dict[str, str] | None = None,
        remote_policy: str = "unknown",
        interview_process: str = "",
    ) -> CompanyProfile:
        """Index a company profile into both stores."""
        company_hash = _disguise_company_name(company_name)

        text_to_embed = f"{industry} {' '.join(culture_tags or [])} {description}"
        try:
            embedding = self._embedder.embed_text(text_to_embed)
        except Exception:
            embedding = None

        profile = CompanyProfile(
            company_hash=company_hash,
            company_name_encrypted=company_name,
            industry=industry,
            description=description,
            culture_tags=culture_tags or [],
            values=values or [],
            typical_salary_ranges=typical_salary_ranges or {},
            remote_policy=remote_policy,
            interview_process=interview_process,
            embedding=embedding,
        )

        # Store in structured
        self._structured.save_company_profile(profile)

        # Store in vector
        if embedding is not None:
            self._vector.add(
                company_hash,
                embedding,
                {
                    "type": "company",
                    "industry": industry,
                    "tags": ",".join(culture_tags or []),
                },
            )

        return profile

    def index_jd_template(
        self,
        role_category: str,
        seniority_level: str,
        industry: str,
        required_skills: list[str] | None = None,
        preferred_skills: list[str] | None = None,
        experience_range: tuple[int, int] = (0, 0),
        salary_template: str = "",
        sections: list[str] | None = None,
        content: str = "",
        success_rate: float = 0.0,
    ) -> JDTemplate:
        """Index a JD template into both stores."""
        import uuid

        template_id = f"jdt_{uuid.uuid4().hex[:12]}"
        text_to_embed = f"{role_category} {seniority_level} {industry} {' '.join(required_skills or [])} {content}"

        try:
            embedding = self._embedder.embed_text(text_to_embed)
        except Exception:
            embedding = None

        template = JDTemplate(
            template_id=template_id,
            role_category=role_category,
            seniority_level=seniority_level,
            industry=industry,
            required_skills_template=required_skills or [],
            preferred_skills_template=preferred_skills or [],
            experience_range=experience_range,
            salary_template=salary_template,
            sections=sections or [],
            embedding=embedding,
            success_rate=success_rate,
            usage_count=0,
            content=content,
        )

        # Store in structured
        self._structured.save_jd_template(template)

        # Store in vector
        if embedding is not None:
            self._vector.add(
                template_id,
                embedding,
                {
                    "type": "jd_template",
                    "role_category": role_category,
                    "seniority_level": seniority_level,
                    "content": content,
                },
            )

        return template

    def index_culture_tag(self, name: str, category: str, description: str = "") -> CultureTag:
        """Index a culture tag in structured store."""
        tag = CultureTag(
            tag_id=_tag_id(name),
            name=name,
            category=category,
            description=description,
        )
        self._structured.save_culture_tag(tag)
        return tag


# ── Internal helpers ────────────────────────────────────────────────────


def _disguise_company_name(name: str) -> str:
    """Create a deterministic anonymized company hash."""
    import hashlib
    return hashlib.sha256(name.strip().lower().encode()).hexdigest()[:16]


def _tag_id(name: str) -> str:
    return f"tag_{name.lower().replace(' ', '_').replace('-', '_')}"


def _normalize_role_category(role_title: str) -> str:
    """Normalize role title to a simplified category."""
    title = role_title.lower().strip()
    # Common role categories
    mappings = {
        "ai": "ai_engineer",
        "ml": "ai_engineer",
        "machine learning": "ai_engineer",
        "deep learning": "ai_engineer",
        "frontend": "frontend",
        "front-end": "frontend",
        "backend": "backend",
        "back-end": "backend",
        "fullstack": "fullstack",
        "full-stack": "fullstack",
        "devops": "devops",
        "sre": "devops",
        "data engineer": "data_engineer",
        "data scientist": "data_scientist",
        "product manager": "product_manager",
        "pm": "product_manager",
    }
    for pattern, category in mappings.items():
        if pattern in title:
            return category
    return title.replace(" ", "_")


def _resume_preview(text: str, max_len: int = 80) -> str:
    preview = text.replace("\n", " ").strip()
    return preview[:max_len] + ("..." if len(preview) > max_len else "")
