from __future__ import annotations

from typing import Any

from evohunter.ai import DEFAULT_MODEL, complete_chat
from evohunter.llm_parser import parse_job_text
from evohunter.rag.kb_manager import KnowledgeBaseManager
from evohunter.workflow.base import BaseWorkflowNode
from evohunter.workflow.models import WorkflowContext


class JDGenerationNode(BaseWorkflowNode):
    """Node ①: JD Generation & Calibration.

    Generates a structured JD using:
    1. RAG context (company profile, historical JD templates, culture tags)
    2. User-provided requirements
    3. LLM generation → validated via ``llm_parser.parse_job_text()``

    Without RAG (kb_manager=None), falls back to pure LLM generation.
    """

    def __init__(
        self,
        ai_client: Any | None = None,
        kb_manager: KnowledgeBaseManager | None = None,
        model: str = DEFAULT_MODEL,
        node_id: str = "jd_generation",
    ) -> None:
        super().__init__(node_id, {"model": model})
        self._ai = ai_client
        self._kb = kb_manager
        self._model = model

    def execute(self, context: WorkflowContext) -> dict[str, Any]:
        company = context.get_input("company_name", "")
        role = context.get_input("role_title", "")
        requirements = context.get_input("requirements", "")
        industry = context.get_input("industry", "")
        seniority = context.get_input("seniority_level", "")
        culture = context.get_input("culture_context", "")
        language = context.get_input("language", "zh")

        if not role.strip():
            return {"error": "role_title is required"}

        # Step 1: RAG retrieval
        rag_context = None
        if self._kb is not None:
            try:
                rag_context = self._kb.retrieve_for_jd_generation(
                    company_name=company or "unknown",
                    role_title=role,
                    industry=industry or None,
                )
            except Exception:
                pass  # RAG failure is non-fatal

        # Step 2: LLM generation
        jd_text = _generate_jd_text(
            client=self._ai,
            model=self._model,
            company=company,
            role=role,
            requirements=requirements,
            industry=industry,
            seniority=seniority,
            culture=culture,
            rag_context=rag_context,
            language=language,
        )

        # Step 3: Parse into JobGene (reuses existing parser)
        try:
            job_gene = parse_job_text(
                text=jd_text,
                client=self._ai,
                model=self._model,
            )
        except Exception:
            # If parser fails, return raw text
            job_gene = {
                "job_id": "j_auto",
                "job_title": role,
                "required_skills": [],
                "preferred_skills": [],
                "min_years_of_experience": 0,
                "salary_range": "unknown",
                "location": "unknown",
                "seniority_level": seniority or "unknown",
            }

        return {
            "job_gene": job_gene,
            "raw_jd_text": jd_text,
            "rag_contexts": rag_context.to_dict() if rag_context else {},
        }


def _generate_jd_text(
    client: Any,
    model: str,
    company: str,
    role: str,
    requirements: str,
    industry: str,
    seniority: str,
    culture: str,
    rag_context: Any,
    language: str,
) -> str:
    """Build the JD generation prompt and call the LLM."""
    # Assemble RAG context into prompt
    rag_block = ""
    if rag_context and rag_context.contexts:
        parts = []
        for ctx in rag_context.contexts:
            if ctx.source_type == "company_profile" and ctx.content:
                parts.append(f"公司背景：{ctx.content}")
                if ctx.metadata.get("culture_tags"):
                    parts.append(f"文化标签：{', '.join(ctx.metadata['culture_tags'])}")
                if ctx.metadata.get("interview_process"):
                    parts.append(f"面试流程：{ctx.metadata['interview_process']}")
            elif ctx.source_type == "jd_template":
                if ctx.metadata.get("required_skills"):
                    parts.append(f"参考技能要求：{', '.join(ctx.metadata['required_skills'])}")
                if ctx.metadata.get("salary_template"):
                    parts.append(f"参考薪资范围：{ctx.metadata['salary_template']}")
                if ctx.metadata.get("sections"):
                    parts.append(f"参考 JD 结构：{' → '.join(ctx.metadata['sections'])}")
        if parts:
            rag_block = "## 参考背景\n" + "\n".join(parts) + "\n\n"

    if language == "en":
        system = (
            "You are a senior technical recruiter. Generate a comprehensive, "
            "structured job description based on the provided information. "
            "Include: job title, required skills, preferred skills, minimum "
            "years of experience, salary range, location, seniority level, "
            "and a detailed role description section."
        )
        user = (
            f"{rag_block}"
            f"Company: {company}\n"
            f"Role: {role}\n"
            f"Industry: {industry}\n"
            f"Seniority: {seniority}\n"
            f"Requirements: {requirements}\n"
            f"Culture context: {culture}\n\n"
            f"Generate a complete JD in English."
        )
    else:
        system = (
            "你是一名资深技术猎头。请根据以下信息生成一份完整、结构化的职位描述（JD）。"
            "JD 应包含：职位名称、必备技能、加分技能、最低工作年限、薪资范围、"
            "工作地点、职级、岗位职责、任职要求。"
        )
        user = (
            f"{rag_block}"
            f"公司：{company}\n"
            f"岗位：{role}\n"
            f"行业：{industry}\n"
            f"职级：{seniority}\n"
            f"要求：{requirements}\n"
            f"文化背景：{culture}\n\n"
            f"请生成完整 JD。"
        )

    return complete_chat(
        model=model,
        client=client,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
