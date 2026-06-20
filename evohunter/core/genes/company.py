from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from evohunter.core.genes.base import (
    GeneBase,
    _optional_list,
    _optional_number,
    _optional_string,
    _require_mapping,
    _require_string,
)

# Label categories for dimension importance: 0 = unimportant, 1 = critical
# These are the mirror of WeightConfig but from the company's subjective view.
PREFERENCE_FIELDS = (
    "skill_importance",
    "experience_importance",
    "salary_importance",
    "location_importance",
    "seniority_importance",
)


@dataclass(frozen=True)
class CompanyGene(GeneBase):
    company_hash: str                          # sha256 hash of company name (anonymized ID)
    industry: str                               # tech / finance / healthcare / manufacturing
    skill_importance: float                     # 0..1, how much this company values skills
    experience_importance: float                # 0..1
    salary_importance: float                    # 0..1
    location_importance: float                   # 0..1
    seniority_importance: float                  # 0..1
    salary_range: str                           # "25k-40k", typical for this company
    location: str                                # "shanghai"
    remote_policy: str                           # "none" | "hybrid" | "full"
    culture_tags: list[str] = field(default_factory=list)   # "fast-paced", "flat", "startup"
    match_history_scores: list[dict[str, Any]] = field(default_factory=list)
    # ^ e.g. [{"pattern_hash": "abc", "result": "passed", "count": 3}]

    def preference_vector(self) -> dict[str, float]:
        return {
            "skill_importance": self.skill_importance,
            "experience_importance": self.experience_importance,
            "salary_importance": self.salary_importance,
            "location_importance": self.location_importance,
            "seniority_importance": self.seniority_importance,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CompanyGene":
        data = _require_mapping(data, "company_gene")
        raw = {
            f: _optional_number(data, f, 0.2)
            for f in PREFERENCE_FIELDS
        }
        total = sum(raw.values()) or 1.0
        return cls(
            company_hash=_require_string(data, "company_hash"),
            industry=_optional_string(data, "industry", "unknown"),
            skill_importance=raw["skill_importance"] / total,
            experience_importance=raw["experience_importance"] / total,
            salary_importance=raw["salary_importance"] / total,
            location_importance=raw["location_importance"] / total,
            seniority_importance=raw["seniority_importance"] / total,
            salary_range=_optional_string(data, "salary_range", ""),
            location=_optional_string(data, "location", ""),
            remote_policy=_optional_string(data, "remote_policy", "none"),
            culture_tags=_optional_list(data, "culture_tags"),
            match_history_scores=data.get("match_history_scores", []),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "CompanyGene",
            "company_hash": self.company_hash,
            "industry": self.industry,
            "skill_importance": round(self.skill_importance, 4),
            "experience_importance": round(self.experience_importance, 4),
            "salary_importance": round(self.salary_importance, 4),
            "location_importance": round(self.location_importance, 4),
            "seniority_importance": round(self.seniority_importance, 4),
            "salary_range": self.salary_range,
            "location": self.location,
            "remote_policy": self.remote_policy,
            "culture_tags": list(self.culture_tags),
            "match_history_scores": list(self.match_history_scores),
        }

    def anonymize(self) -> "CompanyGene":
        """Return a safe-for-sharing copy: keeps industry + preferences, drops location specificity."""
        return CompanyGene(
            company_hash=self.company_hash,
            industry=self.industry,
            skill_importance=self.skill_importance,
            experience_importance=self.experience_importance,
            salary_importance=self.salary_importance,
            location_importance=self.location_importance,
            seniority_importance=self.seniority_importance,
            salary_range="",           # drop: may identify company
            location="",               # drop: may identify company
            remote_policy=self.remote_policy,
            culture_tags=list(self.culture_tags),
            match_history_scores=list(self.match_history_scores),
        )
