from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class RAGError(RuntimeError):
    pass


@dataclass(frozen=True)
class CompanyProfile:
    company_hash: str
    company_name_encrypted: str
    industry: str
    description: str
    culture_tags: list[str] = field(default_factory=list)
    values: list[str] = field(default_factory=list)
    typical_salary_ranges: dict[str, str] = field(default_factory=dict)
    remote_policy: str = "unknown"
    interview_process: str = ""
    previous_jd_hashes: list[str] = field(default_factory=list)
    embedding: list[float] | None = None
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CompanyProfile":
        if not isinstance(data, dict):
            raise RAGError("CompanyProfile data must be a dict")
        return cls(
            company_hash=_require_string(data, "company_hash"),
            company_name_encrypted=_require_string(data, "company_name_encrypted"),
            industry=_optional_string(data, "industry", "unknown"),
            description=_optional_string(data, "description", ""),
            culture_tags=_optional_list(data, "culture_tags"),
            values=_optional_list(data, "values"),
            typical_salary_ranges=data.get("typical_salary_ranges", {}),
            remote_policy=_optional_string(data, "remote_policy", "unknown"),
            interview_process=_optional_string(data, "interview_process", ""),
            previous_jd_hashes=_optional_list(data, "previous_jd_hashes"),
            embedding=data.get("embedding"),
            created_at=_optional_string(data, "created_at", ""),
            updated_at=_optional_string(data, "updated_at", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "type": "CompanyProfile",
            "company_hash": self.company_hash,
            "company_name_encrypted": self.company_name_encrypted,
            "industry": self.industry,
            "description": self.description,
            "culture_tags": list(self.culture_tags),
            "values": list(self.values),
            "typical_salary_ranges": dict(self.typical_salary_ranges),
            "remote_policy": self.remote_policy,
            "interview_process": self.interview_process,
            "previous_jd_hashes": list(self.previous_jd_hashes),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.embedding is not None:
            result["embedding"] = list(self.embedding)
        return result


@dataclass(frozen=True)
class JDTemplate:
    template_id: str
    role_category: str
    seniority_level: str
    industry: str
    required_skills_template: list[str] = field(default_factory=list)
    preferred_skills_template: list[str] = field(default_factory=list)
    experience_range: tuple[int, int] = (0, 0)
    salary_template: str = ""
    sections: list[str] = field(default_factory=list)
    embedding: list[float] | None = None
    success_rate: float = 0.0
    usage_count: int = 0
    content: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JDTemplate":
        if not isinstance(data, dict):
            raise RAGError("JDTemplate data must be a dict")
        exp_range = data.get("experience_range", [0, 0])
        if isinstance(exp_range, list) and len(exp_range) >= 2:
            exp_tuple = (int(exp_range[0]), int(exp_range[1]))
        elif isinstance(exp_range, tuple):
            exp_tuple = exp_range
        else:
            exp_tuple = (0, 0)
        return cls(
            template_id=_require_string(data, "template_id"),
            role_category=_require_string(data, "role_category"),
            seniority_level=_optional_string(data, "seniority_level", "mid"),
            industry=_optional_string(data, "industry", "tech"),
            required_skills_template=_optional_list(data, "required_skills_template"),
            preferred_skills_template=_optional_list(data, "preferred_skills_template"),
            experience_range=exp_tuple,
            salary_template=_optional_string(data, "salary_template", ""),
            sections=_optional_list(data, "sections"),
            embedding=data.get("embedding"),
            success_rate=float(data.get("success_rate", 0.0)),
            usage_count=int(data.get("usage_count", 0)),
            content=_optional_string(data, "content", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "type": "JDTemplate",
            "template_id": self.template_id,
            "role_category": self.role_category,
            "seniority_level": self.seniority_level,
            "industry": self.industry,
            "required_skills_template": list(self.required_skills_template),
            "preferred_skills_template": list(self.preferred_skills_template),
            "experience_range": list(self.experience_range),
            "salary_template": self.salary_template,
            "sections": list(self.sections),
            "success_rate": self.success_rate,
            "usage_count": self.usage_count,
            "content": self.content,
        }
        if self.embedding is not None:
            result["embedding"] = list(self.embedding)
        return result


@dataclass(frozen=True)
class CultureTag:
    tag_id: str
    name: str
    category: str  # "work_style" | "values" | "environment"
    description: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CultureTag":
        if not isinstance(data, dict):
            raise RAGError("CultureTag data must be a dict")
        return cls(
            tag_id=_require_string(data, "tag_id"),
            name=_require_string(data, "name"),
            category=_require_string(data, "category"),
            description=_optional_string(data, "description", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "CultureTag",
            "tag_id": self.tag_id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
        }


@dataclass(frozen=True)
class RAGContext:
    source_type: str  # "company_profile" | "jd_template" | "culture_tag"
    source_id: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "source_id": self.source_id,
            "content": self.content,
            "score": self.score,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class RAGResult:
    query: str
    contexts: list[RAGContext] = field(default_factory=list)
    total_found: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "contexts": [c.to_dict() for c in self.contexts],
            "total_found": self.total_found,
        }


def _require_string(data: dict[str, Any], field_name: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise RAGError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_string(data: dict[str, Any], field_name: str, default: str = "") -> str:
    value = data.get(field_name, default)
    if value is None:
        return default
    if not isinstance(value, str):
        return default
    return value.strip() or default


def _optional_list(data: dict[str, Any], field_name: str) -> list[str]:
    value = data.get(field_name, [])
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()]
