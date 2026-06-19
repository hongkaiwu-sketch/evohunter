from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ValidationError(ValueError):
    pass


FEEDBACK_EVENT_TYPES = {
    "reply_positive",
    "interview_passed",
    "interview_failed",
    "salary_mismatch",
    "location_mismatch",
    "no_reply",
}


WEIGHT_FIELDS = (
    "skill_weight",
    "experience_weight",
    "salary_weight",
    "location_weight",
    "seniority_weight",
)


DEFAULT_WEIGHTS = {
    "skill_weight": 0.4,
    "experience_weight": 0.2,
    "salary_weight": 0.15,
    "location_weight": 0.15,
    "seniority_weight": 0.1,
}


def normalize_skill_vector(skill_vector: Any) -> list[str]:
    if not isinstance(skill_vector, list):
        raise ValidationError("skill_vector must be a list")

    normalized = []
    seen = set()
    for skill in skill_vector:
        if not isinstance(skill, str):
            raise ValidationError("skill_vector items must be strings")
        value = skill.strip().lower()
        if value and value not in seen:
            normalized.append(value)
            seen.add(value)
    return normalized


def _require_mapping(data: Any, name: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValidationError(f"{name} must be a dict")
    return data


def _require_field(data: dict[str, Any], field_name: str) -> Any:
    if field_name not in data:
        raise ValidationError(f"{field_name} is required")
    return data[field_name]


def _require_string(data: dict[str, Any], field_name: str) -> str:
    value = _require_field(data, field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field_name} must be a non-empty string")
    return value.strip()


def _optional_string(data: dict[str, Any], field_name: str, default: str) -> str:
    value = data.get(field_name, default)
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string")
    return value.strip() or default


def _number(data: dict[str, Any], field_name: str, default: float | None = None) -> float:
    if field_name not in data:
        if default is None:
            raise ValidationError(f"{field_name} is required")
        return default
    value = data[field_name]
    if isinstance(value, bool):
        raise ValidationError(f"{field_name} must be a number")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field_name} must be a number") from exc


def _string_list(data: dict[str, Any], field_name: str, default: list[str] | None = None) -> list[str]:
    if field_name not in data:
        return list(default or [])
    return normalize_skill_vector(data[field_name])


def _project_list(data: dict[str, Any], field_name: str) -> list[str]:
    value = data.get(field_name, [])
    if not isinstance(value, list):
        raise ValidationError(f"{field_name} must be a list")
    result = []
    for item in value:
        if not isinstance(item, str):
            raise ValidationError(f"{field_name} items must be strings")
        text = item.strip()
        if text:
            result.append(text)
    return result


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    for field_name, value in weights.items():
        if value < 0:
            raise ValidationError(f"{field_name} must be non-negative")
    total = sum(weights.values())
    if total <= 0:
        raise ValidationError("weight total must be greater than 0")
    return {field_name: value / total for field_name, value in weights.items()}


@dataclass(frozen=True)
class JobGene:
    job_id: str
    job_title: str
    required_skills: list[str]
    preferred_skills: list[str]
    min_years_of_experience: float
    salary_range: str
    location: str
    seniority_level: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobGene":
        data = _require_mapping(data, "job_gene")
        return cls(
            job_id=_require_string(data, "job_id"),
            job_title=_require_string(data, "job_title"),
            required_skills=_string_list(data, "required_skills"),
            preferred_skills=_string_list(data, "preferred_skills", []),
            min_years_of_experience=_number(data, "min_years_of_experience", 0),
            salary_range=_require_string(data, "salary_range"),
            location=_require_string(data, "location").lower(),
            seniority_level=_require_string(data, "seniority_level").lower(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "job_title": self.job_title,
            "required_skills": list(self.required_skills),
            "preferred_skills": list(self.preferred_skills),
            "min_years_of_experience": self.min_years_of_experience,
            "salary_range": self.salary_range,
            "location": self.location,
            "seniority_level": self.seniority_level,
        }


@dataclass(frozen=True)
class CandidateGene:
    candidate_id: str
    skill_vector: list[str]
    years_of_experience: float
    salary_expectation: str
    location_preference: str
    recent_projects: list[str]
    availability: str
    seniority_level: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CandidateGene":
        data = _require_mapping(data, "candidate_gene")
        return cls(
            candidate_id=_require_string(data, "candidate_id"),
            skill_vector=_string_list(data, "skill_vector"),
            years_of_experience=_number(data, "years_of_experience", 0),
            salary_expectation=_require_string(data, "salary_expectation"),
            location_preference=_require_string(data, "location_preference").lower(),
            recent_projects=_project_list(data, "recent_projects"),
            availability=_optional_string(data, "availability", "unknown").lower(),
            seniority_level=_optional_string(data, "seniority_level", "unknown").lower(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "skill_vector": list(self.skill_vector),
            "years_of_experience": self.years_of_experience,
            "salary_expectation": self.salary_expectation,
            "location_preference": self.location_preference,
            "recent_projects": list(self.recent_projects),
            "availability": self.availability,
            "seniority_level": self.seniority_level,
        }


@dataclass(frozen=True)
class WeightConfig:
    generation: int
    skill_weight: float
    experience_weight: float
    salary_weight: float
    location_weight: float
    seniority_weight: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WeightConfig":
        data = _require_mapping(data, "weight_config")
        generation = data.get("generation", 0)
        if isinstance(generation, bool):
            raise ValidationError("generation must be a non-negative integer")
        try:
            generation = int(generation)
        except (TypeError, ValueError) as exc:
            raise ValidationError("generation must be a non-negative integer") from exc
        if generation < 0:
            raise ValidationError("generation must be a non-negative integer")

        raw_weights = {
            field_name: _number(data, field_name, DEFAULT_WEIGHTS[field_name])
            for field_name in WEIGHT_FIELDS
        }
        weights = _normalize_weights(raw_weights)
        return cls(generation=generation, **weights)

    def weights(self) -> dict[str, float]:
        return {
            "skill_weight": self.skill_weight,
            "experience_weight": self.experience_weight,
            "salary_weight": self.salary_weight,
            "location_weight": self.location_weight,
            "seniority_weight": self.seniority_weight,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "generation": self.generation,
            **self.weights(),
        }


@dataclass(frozen=True)
class FeedbackEvent:
    candidate_id: str
    job_id: str
    event_type: str
    event_value: str
    event_time: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeedbackEvent":
        data = _require_mapping(data, "feedback_event")
        event_type = _require_string(data, "event_type")
        if event_type not in FEEDBACK_EVENT_TYPES:
            raise ValidationError(f"event_type must be one of {sorted(FEEDBACK_EVENT_TYPES)}")
        return cls(
            candidate_id=_require_string(data, "candidate_id"),
            job_id=_require_string(data, "job_id"),
            event_type=event_type,
            event_value=_optional_string(data, "event_value", ""),
            event_time=_optional_string(data, "event_time", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "job_id": self.job_id,
            "event_type": self.event_type,
            "event_value": self.event_value,
            "event_time": self.event_time,
        }


@dataclass(frozen=True)
class MatchResult:
    candidate_id: str
    job_id: str
    match_score: float
    score_detail: dict[str, float]
    recommendation_reason: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MatchResult":
        data = _require_mapping(data, "match_result")
        score_detail = _require_field(data, "score_detail")
        if not isinstance(score_detail, dict):
            raise ValidationError("score_detail must be a dict")
        return cls(
            candidate_id=_require_string(data, "candidate_id"),
            job_id=_require_string(data, "job_id"),
            match_score=_number(data, "match_score"),
            score_detail={key: float(value) for key, value in score_detail.items()},
            recommendation_reason=_require_string(data, "recommendation_reason"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "job_id": self.job_id,
            "match_score": round(self.match_score, 4),
            "score_detail": {
                field_name: round(value, 4)
                for field_name, value in self.score_detail.items()
            },
            "recommendation_reason": self.recommendation_reason,
        }


def validate_job_gene(job_gene: dict[str, Any] | JobGene) -> JobGene:
    if isinstance(job_gene, JobGene):
        return job_gene
    return JobGene.from_dict(job_gene)


def validate_candidate_gene(candidate_gene: dict[str, Any] | CandidateGene) -> CandidateGene:
    if isinstance(candidate_gene, CandidateGene):
        return candidate_gene
    return CandidateGene.from_dict(candidate_gene)


def validate_feedback_event(feedback_event: dict[str, Any] | FeedbackEvent) -> FeedbackEvent:
    if isinstance(feedback_event, FeedbackEvent):
        return feedback_event
    return FeedbackEvent.from_dict(feedback_event)


def validate_weight_config(weight_config: dict[str, Any] | WeightConfig) -> WeightConfig:
    if isinstance(weight_config, WeightConfig):
        return weight_config
    return WeightConfig.from_dict(weight_config)
