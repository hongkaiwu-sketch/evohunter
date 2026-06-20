from __future__ import annotations

import re
from typing import Any

from evohunter.core.protocol import (
    CandidateGene,
    JobGene,
    MatchResult,
    WeightConfig,
    validate_candidate_gene,
    validate_job_gene,
    validate_weight_config,
)


SENIORITY_ORDER = {
    "intern": 0,
    "junior": 1,
    "mid": 2,
    "middle": 2,
    "senior": 3,
    "lead": 4,
    "principal": 5,
}


REMOTE_LOCATIONS = {"remote", "open", "anywhere", "全国", "不限", "远程"}


class GEPEvaluator:
    def score_candidate(
        self,
        job_gene: dict[str, Any] | JobGene,
        candidate_gene: dict[str, Any] | CandidateGene,
        weight_config: dict[str, Any] | WeightConfig,
    ) -> MatchResult:
        job_gene = validate_job_gene(job_gene)
        candidate_gene = validate_candidate_gene(candidate_gene)
        weight_config = validate_weight_config(weight_config)

        score_detail = {
            "skill_score": self._score_skills(job_gene, candidate_gene),
            "experience_score": self._score_experience(job_gene, candidate_gene),
            "salary_score": self._score_salary(job_gene, candidate_gene),
            "location_score": self._score_location(job_gene, candidate_gene),
            "seniority_score": self._score_seniority(job_gene, candidate_gene),
        }
        match_score = sum(
            score_detail[field_name.replace("_weight", "_score")] * weight
            for field_name, weight in weight_config.weights().items()
        )
        return MatchResult(
            candidate_id=candidate_gene.candidate_id,
            job_id=job_gene.job_id,
            match_score=match_score,
            score_detail=score_detail,
            recommendation_reason=self.explain_match(job_gene, candidate_gene, score_detail),
            confidence_score=self._estimate_confidence(job_gene, candidate_gene),
            risk_flags=self._build_risk_flags(job_gene, candidate_gene, score_detail),
        )

    def rank_candidates(
        self,
        job_gene: dict[str, Any] | JobGene,
        candidate_genes: list[dict[str, Any] | CandidateGene],
        weight_config: dict[str, Any] | WeightConfig,
    ) -> list[MatchResult]:
        results = [
            self.score_candidate(job_gene, candidate_gene, weight_config)
            for candidate_gene in candidate_genes
        ]
        return sorted(results, key=lambda result: (-result.match_score, result.candidate_id))

    def explain_match(
        self,
        job_gene: JobGene,
        candidate_gene: CandidateGene,
        score_detail: dict[str, float],
    ) -> str:
        parts = [
            self._explain_score("技能", score_detail["skill_score"]),
            self._explain_score("经验", score_detail["experience_score"]),
            self._explain_score("薪资", score_detail["salary_score"]),
            self._explain_score("地点", score_detail["location_score"]),
            self._explain_score("职级", score_detail["seniority_score"]),
        ]
        return "，".join(parts) + "。"

    def _score_skills(self, job_gene: JobGene, candidate_gene: CandidateGene) -> float:
        candidate_skills = set(candidate_gene.skill_vector)
        required_score = self._overlap_score(job_gene.required_skills, candidate_skills)
        if not job_gene.preferred_skills:
            return required_score
        preferred_score = self._overlap_score(job_gene.preferred_skills, candidate_skills)
        return 0.8 * required_score + 0.2 * preferred_score

    def _score_experience(self, job_gene: JobGene, candidate_gene: CandidateGene) -> float:
        if job_gene.min_years_of_experience <= 0:
            return 1.0
        return max(0.0, min(candidate_gene.years_of_experience / job_gene.min_years_of_experience, 1.0))

    def _score_salary(self, job_gene: JobGene, candidate_gene: CandidateGene) -> float:
        job_range = self._parse_salary_range(job_gene.salary_range)
        candidate_range = self._parse_salary_range(candidate_gene.salary_expectation)
        if job_range is None or candidate_range is None:
            return 0.5
        job_low, job_high = job_range
        candidate_low, candidate_high = candidate_range
        if max(job_low, candidate_low) <= min(job_high, candidate_high):
            return 1.0
        return 0.0

    def _score_location(self, job_gene: JobGene, candidate_gene: CandidateGene) -> float:
        job_location = job_gene.location.strip().lower()
        candidate_location = candidate_gene.location_preference.strip().lower()
        if not job_location or not candidate_location:
            return 0.5
        if job_location == candidate_location:
            return 1.0
        if job_location in REMOTE_LOCATIONS or candidate_location in REMOTE_LOCATIONS:
            return 0.8
        return 0.0

    def _score_seniority(self, job_gene: JobGene, candidate_gene: CandidateGene) -> float:
        job_level = SENIORITY_ORDER.get(job_gene.seniority_level)
        candidate_level = SENIORITY_ORDER.get(candidate_gene.seniority_level)
        if candidate_level is None:
            candidate_level = self._infer_seniority_level(candidate_gene.years_of_experience)
        if job_level is None or candidate_level is None:
            return 0.5
        distance = abs(job_level - candidate_level)
        if distance == 0:
            return 1.0
        if distance == 1:
            return 0.7
        return 0.3

    def _estimate_confidence(self, job_gene: JobGene, candidate_gene: CandidateGene) -> float:
        values = [
            1.0 if job_gene.required_skills and candidate_gene.skill_vector else 0.5,
            1.0 if candidate_gene.years_of_experience >= 0 else 0.5,
            1.0
            if self._parse_salary_range(job_gene.salary_range)
            and self._parse_salary_range(candidate_gene.salary_expectation)
            else 0.4,
            1.0 if job_gene.location and candidate_gene.location_preference else 0.5,
            1.0
            if job_gene.seniority_level in SENIORITY_ORDER
            and candidate_gene.seniority_level in SENIORITY_ORDER
            else 0.75,
        ]
        return sum(values) / len(values)

    def _build_risk_flags(
        self,
        job_gene: JobGene,
        candidate_gene: CandidateGene,
        score_detail: dict[str, float],
    ) -> list[str]:
        risk_flags = []
        if score_detail["skill_score"] < 0.5:
            risk_flags.append("skill_gap")
        if score_detail["experience_score"] < 0.7:
            risk_flags.append("experience_gap")
        if self._parse_salary_range(job_gene.salary_range) is None or self._parse_salary_range(
            candidate_gene.salary_expectation
        ) is None:
            risk_flags.append("salary_unknown")
        elif score_detail["salary_score"] == 0:
            risk_flags.append("salary_mismatch")
        if score_detail["location_score"] == 0:
            risk_flags.append("location_mismatch")
        elif score_detail["location_score"] == 0.5:
            risk_flags.append("location_unknown")
        if score_detail["seniority_score"] < 0.5:
            risk_flags.append("seniority_gap")
        elif score_detail["seniority_score"] == 0.5:
            risk_flags.append("seniority_unknown")
        return risk_flags

    def _overlap_score(self, expected_skills: list[str], candidate_skills: set[str]) -> float:
        if not expected_skills:
            return 1.0
        return len(set(expected_skills) & candidate_skills) / len(set(expected_skills))

    def _parse_salary_range(self, value: str) -> tuple[float, float] | None:
        numbers = [float(match) for match in re.findall(r"\d+(?:\.\d+)?", value)]
        if not numbers:
            return None
        if len(numbers) == 1:
            return numbers[0], numbers[0]
        low, high = numbers[0], numbers[1]
        if low > high:
            low, high = high, low
        return low, high

    def _infer_seniority_level(self, years_of_experience: float) -> int:
        if years_of_experience < 3:
            return SENIORITY_ORDER["junior"]
        if years_of_experience < 6:
            return SENIORITY_ORDER["mid"]
        if years_of_experience < 10:
            return SENIORITY_ORDER["senior"]
        return SENIORITY_ORDER["lead"]

    def _explain_score(self, label: str, score: float) -> str:
        if score >= 0.85:
            return f"{label}匹配度高"
        if score >= 0.5:
            return f"{label}部分匹配"
        return f"{label}存在明显差距"
