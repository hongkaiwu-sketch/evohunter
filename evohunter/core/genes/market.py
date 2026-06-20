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
class MarketGene(GeneBase):
    """Market-layer knowledge — shared across all EvoHunter instances.

    Contains no company or candidate PII. Each instance contributes data
    and benefits from others' contributions.
    """
    gene_id: str                                # unique ID for this market gene entry
    # ── skill relations ──
    skill_aliases: dict[str, list[str]] = field(default_factory=dict)
    # ^ {"django": ["django framework", "Django"], "k8s": ["kubernetes", "K8S"]}
    skill_categories: dict[str, str] = field(default_factory=dict)
    # ^ {"django": "web", "k8s": "cloud-native", "pytorch": "ml"}

    # ── market salary data ──
    salary_ranges: dict[str, dict[str, str]] = field(default_factory=dict)
    # ^ {"shanghai+ai_engineer+mid": {"low": "25k", "median": "32k", "high": "45k"}}

    # ── role baselines ──
    role_baselines: dict[str, dict[str, float]] = field(default_factory=dict)
    # ^ {"ai_engineer": {"skill_weight": 0.45, "experience_weight": 0.15, ...}}

    # ── parse strategies ──
    parse_strategies: dict[str, str] = field(default_factory=dict)
    # ^ {"zh_resume": "prompt template for Chinese CV", "linkedin": "prompt for LinkedIn"}

    # ── anonymous match patterns ──
    match_patterns: list[dict[str, Any]] = field(default_factory=list)
    # ^ [
    #     {"pattern_hash": "abc", "dimensions": {"skill": 0.9, "exp": 4},
    #      "result": "interview_passed", "confidence": 0.85, "count": 12},
    #   ]

    # ── source metadata ──
    contributor_count: int = 1
    last_updated: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MarketGene":
        data = _require_mapping(data, "market_gene")
        return cls(
            gene_id=_require_string(data, "gene_id"),
            skill_aliases={
                str(k): [str(vv) for vv in v]
                for k, v in data.get("skill_aliases", {}).items()
            },
            skill_categories={
                str(k): str(v)
                for k, v in data.get("skill_categories", {}).items()
            },
            salary_ranges={
                str(k): {str(kk): str(vv) for kk, vv in v.items()}
                for k, v in data.get("salary_ranges", {}).items()
            },
            role_baselines={
                str(k): {str(kk): float(vv) for kk, vv in v.items()}
                for k, v in data.get("role_baselines", {}).items()
            },
            parse_strategies={
                str(k): str(v)
                for k, v in data.get("parse_strategies", {}).items()
            },
            match_patterns=data.get("match_patterns", []),
            contributor_count=int(_optional_number(data, "contributor_count", 1)),
            last_updated=_optional_string(data, "last_updated", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "MarketGene",
            "gene_id": self.gene_id,
            "skill_aliases": {
                k: list(v) for k, v in self.skill_aliases.items()
            },
            "skill_categories": dict(self.skill_categories),
            "salary_ranges": {
                k: dict(v) for k, v in self.salary_ranges.items()
            },
            "role_baselines": {
                k: dict(v) for k, v in self.role_baselines.items()
            },
            "parse_strategies": dict(self.parse_strategies),
            "match_patterns": list(self.match_patterns),
            "contributor_count": self.contributor_count,
            "last_updated": self.last_updated,
        }

    def anonymize(self) -> "MarketGene":
        """MarketGene is already anonymous — returns self."""
        return self

    def merge(self, other: "MarketGene") -> "MarketGene":
        """Merge another MarketGene into this one (union semantics)."""
        merged_aliases = dict(self.skill_aliases)
        for k, v in other.skill_aliases.items():
            existing = set(merged_aliases.get(k, []))
            merged_aliases[k] = list(existing | set(v))

        merged_categories = dict(self.skill_categories)
        merged_categories.update(other.skill_categories)

        merged_salary = dict(self.salary_ranges)
        merged_salary.update(other.salary_ranges)

        merged_baselines = dict(self.role_baselines)
        merged_baselines.update(other.role_baselines)

        merged_strategies = dict(self.parse_strategies)
        merged_strategies.update(other.parse_strategies)

        seen_hashes = {p.get("pattern_hash") for p in self.match_patterns}
        merged_patterns = list(self.match_patterns)
        for p in other.match_patterns:
            if p.get("pattern_hash") not in seen_hashes:
                merged_patterns.append(p)
                seen_hashes.add(p.get("pattern_hash"))

        return MarketGene(
            gene_id=self.gene_id,
            skill_aliases=merged_aliases,
            skill_categories=merged_categories,
            salary_ranges=merged_salary,
            role_baselines=merged_baselines,
            parse_strategies=merged_strategies,
            match_patterns=merged_patterns,
            contributor_count=self.contributor_count + other.contributor_count,
            last_updated=max(self.last_updated, other.last_updated),
        )
