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


@dataclass(frozen=True)
class CandidateGene(GeneBase):
    """Enhanced candidate gene with both skill profile and personal preferences.

    This merges the old ``CandidateGene`` skill vector with a new preference
    model that captures what the candidate values in a job offer.
    """
    candidate_hash: str                         # sha256 hash of name+contact (anonymized ID)
    skill_vector: list[str]                     # normalized skill names
    years_of_experience: float
    salary_expectation: str                     # "30k-35k"
    location_preference: str                    # "shanghai"
    recent_projects: list[str]
    availability: str                           # "open" | "interviewing" | "closed"
    seniority_level: str                        # "junior" | "mid" | "senior" | "lead"
    # ── preference dimensions (0..1) ──
    values_compensation: float                  # how much salary matters to them
    values_remote: float                        # how much remote work matters
    values_growth: float                        # how much career growth matters
    values_stability: float                     # how much job stability matters
    values_culture_fit: float                   # how much team culture matters
    level_match_strictness: float               # 0=flexible, 1=strict about level match
    # ── history across agents ──
    match_history_results: list[dict[str, Any]] = field(default_factory=list)
    # ^ [{"company_hash": "abc", "result": "interview_passed", "score": 0.92}, ...]

    def preference_vector(self) -> dict[str, float]:
        return {
            "compensation": self.values_compensation,
            "remote": self.values_remote,
            "growth": self.values_growth,
            "stability": self.values_stability,
            "culture_fit": self.values_culture_fit,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CandidateGene":
        data = _require_mapping(data, "candidate_gene")
        return cls(
            candidate_hash=_require_string(data, "candidate_hash"),
            skill_vector=_optional_list(data, "skill_vector"),
            years_of_experience=_optional_number(data, "years_of_experience", 0),
            salary_expectation=_require_string(data, "salary_expectation"),
            location_preference=_optional_string(data, "location_preference", ""),
            recent_projects=_optional_list(data, "recent_projects"),
            availability=_optional_string(data, "availability", "unknown"),
            seniority_level=_optional_string(data, "seniority_level", "unknown"),
            values_compensation=_optional_number(data, "values_compensation", 0.5),
            values_remote=_optional_number(data, "values_remote", 0.5),
            values_growth=_optional_number(data, "values_growth", 0.5),
            values_stability=_optional_number(data, "values_stability", 0.5),
            values_culture_fit=_optional_number(data, "values_culture_fit", 0.5),
            level_match_strictness=_optional_number(data, "level_match_strictness", 0.5),
            match_history_results=data.get("match_history_results", []),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "CandidateGene",
            "candidate_hash": self.candidate_hash,
            "skill_vector": list(self.skill_vector),
            "years_of_experience": self.years_of_experience,
            "salary_expectation": self.salary_expectation,
            "location_preference": self.location_preference,
            "recent_projects": list(self.recent_projects),
            "availability": self.availability,
            "seniority_level": self.seniority_level,
            "values_compensation": round(self.values_compensation, 4),
            "values_remote": round(self.values_remote, 4),
            "values_growth": round(self.values_growth, 4),
            "values_stability": round(self.values_stability, 4),
            "values_culture_fit": round(self.values_culture_fit, 4),
            "level_match_strictness": round(self.level_match_strictness, 4),
            "match_history_results": list(self.match_history_results),
        }

    def anonymize(self) -> "CandidateGene":
        """Return a safe-for-sharing copy without personally identifiable data."""
        return CandidateGene(
            candidate_hash=self.candidate_hash,
            skill_vector=list(self.skill_vector),
            years_of_experience=self.years_of_experience,
            salary_expectation="",            # drop: may identify individual
            location_preference="",           # drop
            recent_projects=[],               # drop: may contain identifying info
            availability=self.availability,
            seniority_level=self.seniority_level,
            values_compensation=self.values_compensation,
            values_remote=self.values_remote,
            values_growth=self.values_growth,
            values_stability=self.values_stability,
            values_culture_fit=self.values_culture_fit,
            level_match_strictness=self.level_match_strictness,
            match_history_results=list(self.match_history_results),
        )
