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

# New gene types for bidirectional scoring — optional imports
try:
    from evohunter.core.genes import CandidateGene as NewCandidateGene
    from evohunter.core.genes import CompanyGene as NewCompanyGene
except ImportError:
    NewCandidateGene = None  # type: ignore[assignment]
    NewCompanyGene = None  # type: ignore[assignment]


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


def _extract_numbers(value: str) -> list[float]:
    numbers = [float(match) for match in re.findall(r"\d+(?:\.\d+)?", value)]
    if not numbers:
        return []
    return numbers


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

    # ── Bidirectional scoring (new gene types) ─────────────────────────

    def score_candidate_company_view(
        self,
        job_gene: dict[str, Any] | JobGene,
        candidate_gene: Any,  # old CandidateGene dict or new genes.CandidateGene
        weight_config: dict[str, Any] | WeightConfig | None = None,
    ) -> dict[str, Any]:
        """Company perspective: how well does this candidate fit the role?"""
        wc = weight_config if weight_config is not None else {}
        # Convert new-style CandidateGene to old-style dict for compatibility
        old_style = self._to_old_candidate_dict(candidate_gene)
        result = self.score_candidate(job_gene, old_style, wc)
        return {
            "match_score": result.match_score,
            "score_detail": result.score_detail,
            "recommendation_reason": result.recommendation_reason,
            "confidence_score": result.confidence_score,
            "risk_flags": result.risk_flags or [],
        }

    def score_company_candidate_view(
        self,
        company_gene: Any,  # NewCompanyGene
        candidate_gene: Any,  # NewCandidateGene
    ) -> dict[str, Any]:
        """Candidate perspective: how well does this company match what the candidate values?

        Matches the candidate's 5 preference dimensions against the company's profile.
        """
        cp = candidate_gene.preference_vector()  # compensation, remote, growth, stability, culture_fit

        # compensation: compare salary ranges
        salary_score = self._bidirectional_salary(
            company_gene.salary_range,
            candidate_gene.salary_expectation,
        )
        # remote: remote_policy vs values_remote
        remote_score = self._bidirectional_remote(
            company_gene.remote_policy,
            cp["remote"],
        )
        # growth: seniority + industry signals
        growth_score = self._bidirectional_growth(
            company_gene.industry,
            candidate_gene.seniority_level,
            cp["growth"],
        )
        # stability: industry/culture signals
        stability_score = self._bidirectional_stability(
            company_gene.industry,
            company_gene.culture_tags,
            cp["stability"],
        )
        # culture fit: culture_tags vs values_culture_fit
        culture_score = self._bidirectional_culture(
            company_gene.culture_tags,
            cp["culture_fit"],
        )

        score_detail = {
            "compensation_score": round(salary_score, 4),
            "remote_score": round(remote_score, 4),
            "growth_score": round(growth_score, 4),
            "stability_score": round(stability_score, 4),
            "culture_fit_score": round(culture_score, 4),
        }
        # use candidate's own preference weights for final score
        match_score = (
            cp["compensation"] * salary_score
            + cp["remote"] * remote_score
            + cp["growth"] * growth_score
            + cp["stability"] * stability_score
            + cp["culture_fit"] * culture_score
        )
        total_pref = sum(cp.values()) or 1.0
        match_score = match_score / total_pref

        return {
            "match_score": round(match_score, 4),
            "score_detail": score_detail,
            "recommendation_reason": self._explain_candidate_match(score_detail),
            "confidence_score": 0.8,  # default for preference-based scoring
            "risk_flags": self._build_candidate_risk_flags(score_detail),
        }

    def score_bidirectional(
        self,
        job_gene: dict[str, Any] | JobGene,
        candidate_gene: Any,  # NewCandidateGene
        weight_config: dict[str, Any] | WeightConfig | None = None,
        company_gene: Any | None = None,  # NewCompanyGene
    ) -> dict[str, Any]:
        """Combine company view and candidate view into a bidirectional match.

        A match is only good if BOTH sides are satisfied.
        """
        company_view = self.score_candidate_company_view(
            job_gene, candidate_gene, weight_config
        )

        if company_gene is not None and NewCandidateGene is not None:
            candidate_view = self.score_company_candidate_view(
                company_gene, candidate_gene
            )
            # harmonic mean — penalizes one-sided matches
            cs = company_view["match_score"]
            cv = candidate_view["match_score"]
            if cs + cv > 0:
                bidirectional_score = 2 * cs * cv / (cs + cv)
            else:
                bidirectional_score = 0.0
        else:
            candidate_view = {
                "match_score": 1.0,
                "score_detail": {},
                "recommendation_reason": "",
                "confidence_score": 0.5,
                "risk_flags": [],
            }
            bidirectional_score = company_view["match_score"]

        return {
            "bidirectional_score": round(bidirectional_score, 4),
            "company_view": company_view,
            "candidate_view": candidate_view,
        }

    def rank_candidates_bidirectional(
        self,
        job_gene: dict[str, Any] | JobGene,
        candidate_genes: list[Any],  # list of NewCandidateGene
        weight_config: dict[str, Any] | WeightConfig | None = None,
        company_gene: Any | None = None,  # NewCompanyGene
    ) -> list[dict[str, Any]]:
        """Rank candidates using bidirectional scoring."""
        results = []
        for cg in candidate_genes:
            result = self.score_bidirectional(
                job_gene, cg, weight_config, company_gene
            )
            result["candidate_id"] = (
                cg.candidate_hash
                if hasattr(cg, "candidate_hash")
                else cg.get("candidate_hash", cg.get("candidate_id", "unknown"))
            )
            results.append(result)
        return sorted(
            results,
            key=lambda r: (-r["bidirectional_score"], r["candidate_id"]),
        )

    # ── Bidirectional dimension scorers ───────────────────────────────

    @staticmethod
    def _to_old_candidate_dict(candidate_gene: Any) -> dict[str, Any]:
        """Convert new-style genes.CandidateGene to old-style protocol dict."""
        # Already a plain dict with old keys
        if isinstance(candidate_gene, dict):
            cid = candidate_gene.get("candidate_id", candidate_gene.get("candidate_hash", "unknown"))
            return {
                "candidate_id": cid,
                "skill_vector": candidate_gene.get("skill_vector", []),
                "years_of_experience": candidate_gene.get("years_of_experience", 0),
                "salary_expectation": candidate_gene.get("salary_expectation", ""),
                "location_preference": candidate_gene.get("location_preference", ""),
                "recent_projects": candidate_gene.get("recent_projects", []),
                "availability": candidate_gene.get("availability", "open"),
                "seniority_level": candidate_gene.get("seniority_level", "mid"),
            }
        # New-style genes.CandidateGene (dataclass)
        cid = getattr(candidate_gene, "candidate_hash", None) or getattr(candidate_gene, "candidate_id", "unknown")
        return {
            "candidate_id": str(cid),
            "skill_vector": list(getattr(candidate_gene, "skill_vector", [])),
            "years_of_experience": float(getattr(candidate_gene, "years_of_experience", 0)),
            "salary_expectation": str(getattr(candidate_gene, "salary_expectation", "")),
            "location_preference": str(getattr(candidate_gene, "location_preference", "")),
            "recent_projects": list(getattr(candidate_gene, "recent_projects", [])),
            "availability": str(getattr(candidate_gene, "availability", "open")),
            "seniority_level": str(getattr(candidate_gene, "seniority_level", "mid")),
        }

    @staticmethod
    def _bidirectional_salary(
        company_salary_range: str,
        candidate_salary_expectation: str,
    ) -> float:
        if not company_salary_range or not candidate_salary_expectation:
            return 0.5
        # reuse the existing parser logic (simplified inline)
        nums_c = _extract_numbers(company_salary_range)
        nums_p = _extract_numbers(candidate_salary_expectation)
        if not nums_c or not nums_p:
            return 0.5
        c_low, c_high = nums_c[0], nums_c[-1]
        p_low, p_high = nums_p[0], nums_p[-1]
        if max(c_low, p_low) <= min(c_high, p_high):
            return 1.0
        # partial: how close are they?
        gap = max(p_low - c_high, c_low - p_high, 0)
        avg_range = (c_high - c_low + p_high - p_low) / 2 or 1
        return max(0.0, 1.0 - gap / avg_range)

    @staticmethod
    def _bidirectional_remote(remote_policy: str, values_remote: float) -> float:
        policy_scores = {"full": 1.0, "hybrid": 0.7, "none": 0.1}
        policy_score = policy_scores.get(remote_policy.lower(), 0.5)
        # blend: how much the candidate cares × company offering
        return 0.5 * values_remote + 0.5 * policy_score

    @staticmethod
    def _bidirectional_growth(
        industry: str,
        seniority_level: str,
        values_growth: float,
    ) -> float:
        # tech companies and early-stage have higher growth signals
        growth_industries = {"tech", "ai", "startup", "internet"}
        industry_score = 0.8 if industry.lower() in growth_industries else 0.5
        # mid-level and below benefit most from growth opportunities
        seniority_order = {"intern": 0, "junior": 1, "mid": 2, "senior": 3, "lead": 4}
        level = seniority_order.get(seniority_level.lower(), 2)
        level_score = max(0.3, 1.0 - level * 0.15)
        return 0.4 * values_growth + 0.3 * industry_score + 0.3 * level_score

    @staticmethod
    def _bidirectional_stability(
        industry: str,
        culture_tags: list[str],
        values_stability: float,
    ) -> float:
        # established industries signal stability
        stable_industries = {"finance", "healthcare", "manufacturing", "government"}
        industry_score = 0.8 if industry.lower() in stable_industries else 0.5
        # culture tags that suggest stability
        stability_tags = {"established", "enterprise", "stable", "large-scale"}
        tag_score = 0.7 if any(t.lower() in stability_tags for t in culture_tags) else 0.5
        return 0.4 * values_stability + 0.3 * industry_score + 0.3 * tag_score

    @staticmethod
    def _bidirectional_culture(
        culture_tags: list[str],
        values_culture_fit: float,
    ) -> float:
        # richness of culture signals
        tag_richness = min(1.0, len(culture_tags) / 5.0)
        return 0.5 * values_culture_fit + 0.5 * tag_richness

    @staticmethod
    def _explain_candidate_match(score_detail: dict[str, float]) -> str:
        explanations = {
            "compensation_score": "薪资",
            "remote_score": "远程",
            "growth_score": "成长",
            "stability_score": "稳定性",
            "culture_fit_score": "文化契合",
        }
        parts = []
        for key, label in explanations.items():
            score = score_detail.get(key, 0.5)
            if score >= 0.85:
                parts.append(f"{label}匹配度高")
            elif score >= 0.5:
                parts.append(f"{label}部分匹配")
            else:
                parts.append(f"{label}存在差距")
        return "，".join(parts) + "。"

    @staticmethod
    def _build_candidate_risk_flags(score_detail: dict[str, float]) -> list[str]:
        flags = []
        for key in ("compensation_score", "remote_score", "growth_score",
                     "stability_score", "culture_fit_score"):
            if score_detail.get(key, 1.0) < 0.3:
                flags.append(f"{key.replace('_score', '')}_gap")
        return flags

    # ── Original private scorers ──────────────────────────────────────

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
