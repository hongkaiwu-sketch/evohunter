from __future__ import annotations

import random
from collections import Counter
from typing import Any

from evohunter.core.protocol import (
    FeedbackEvent,
    WeightConfig,
    validate_feedback_event,
    validate_weight_config,
)
from evohunter.core.protocol.models import WEIGHT_FIELDS


MIN_WEIGHT = 0.05
MAX_WEIGHT = 0.70


FEEDBACK_DELTAS = {
    "reply_positive": {
        "skill_weight": 0.03,
        "experience_weight": 0.02,
    },
    "interview_passed": {
        "skill_weight": 0.03,
        "experience_weight": 0.03,
        "seniority_weight": 0.02,
    },
    "interview_failed": {
        "skill_weight": -0.02,
        "experience_weight": 0.03,
        "seniority_weight": 0.03,
    },
    "salary_mismatch": {
        "salary_weight": 0.04,
    },
    "location_mismatch": {
        "location_weight": 0.04,
    },
    "no_reply": {
        "salary_weight": 0.015,
        "location_weight": 0.015,
    },
}


def record_feedback(feedback_event: dict[str, Any] | FeedbackEvent) -> FeedbackEvent:
    return validate_feedback_event(feedback_event)


def mutate_weight_config(
    weight_config: dict[str, Any] | WeightConfig,
    mutation_rate: float,
    mutation_strength: float,
) -> WeightConfig:
    weight_config = validate_weight_config(weight_config)
    weights = weight_config.weights()
    changed = False

    for field_name in WEIGHT_FIELDS:
        if random.random() <= mutation_rate:
            weights[field_name] += random.uniform(-mutation_strength, mutation_strength)
            changed = True

    if not changed and mutation_rate > 0 and mutation_strength > 0:
        weights["skill_weight"] += mutation_strength

    return _build_weight_config(weights, weight_config.generation + 1)


def crossover_weight_configs(
    parent_a: dict[str, Any] | WeightConfig,
    parent_b: dict[str, Any] | WeightConfig,
) -> WeightConfig:
    parent_a = validate_weight_config(parent_a)
    parent_b = validate_weight_config(parent_b)
    weights = {
        field_name: (parent_a.weights()[field_name] + parent_b.weights()[field_name]) / 2
        for field_name in WEIGHT_FIELDS
    }
    return _build_weight_config(weights, max(parent_a.generation, parent_b.generation) + 1)


def evolve_weight_config(
    weight_config: dict[str, Any] | WeightConfig,
    feedback_events: list[dict[str, Any] | FeedbackEvent] | dict[str, Any] | FeedbackEvent,
) -> WeightConfig:
    weight_config = validate_weight_config(weight_config)
    events = _normalize_feedback_events(feedback_events)
    return _apply_feedback_deltas(weight_config, events)


def evolve_weight_config_with_summary(
    weight_config: dict[str, Any] | WeightConfig,
    feedback_events: list[dict[str, Any] | FeedbackEvent] | dict[str, Any] | FeedbackEvent,
) -> dict[str, Any]:
    weight_config = validate_weight_config(weight_config)
    events = _normalize_feedback_events(feedback_events)
    evolved = _apply_feedback_deltas(weight_config, events)
    return {
        "weight_config": evolved.to_dict(),
        "evolution_summary": _build_evolution_summary(weight_config, evolved, events),
    }


# ── Gene-level evolution adapters ─────────────────────────────────────


def mutate_company_preferences(
    company_gene: dict[str, Any] | Any,
    mutation_rate: float = 0.3,
    mutation_strength: float = 0.04,
) -> dict[str, float]:
    """Mutate a company's preference vector.  Accepts a CompanyGene instance or dict."""
    prefs = _extract_prefs(company_gene, "company")
    changed = False
    for field in prefs:
        if random.random() <= mutation_rate:
            prefs[field] += random.uniform(-mutation_strength, mutation_strength)
            changed = True
    if not changed and mutation_rate > 0 and mutation_strength > 0:
        keys = list(prefs.keys())
        prefs[keys[0]] += mutation_strength
    return _normalize_prefs(prefs)


def crossover_company_preferences(
    company_a: dict[str, Any] | Any,
    company_b: dict[str, Any] | Any,
) -> dict[str, float]:
    """Crossover two companies' preference vectors."""
    prefs_a = _extract_prefs(company_a, "company")
    prefs_b = _extract_prefs(company_b, "company")
    return _normalize_prefs({
        f: (prefs_a[f] + prefs_b[f]) / 2 for f in prefs_a
    })


def mutate_candidate_preferences(
    candidate_gene: dict[str, Any] | Any,
    mutation_rate: float = 0.3,
    mutation_strength: float = 0.04,
) -> dict[str, float]:
    """Mutate a candidate's preference vector."""
    prefs = _extract_prefs(candidate_gene, "candidate")
    changed = False
    for field in prefs:
        if random.random() <= mutation_rate:
            prefs[field] += random.uniform(-mutation_strength, mutation_strength)
            changed = True
    if not changed and mutation_rate > 0 and mutation_strength > 0:
        keys = list(prefs.keys())
        prefs[keys[0]] += mutation_strength
    return _normalize_prefs(prefs)


def crossover_candidate_preferences(
    candidate_a: dict[str, Any] | Any,
    candidate_b: dict[str, Any] | Any,
) -> dict[str, float]:
    """Crossover two candidates' preference vectors."""
    prefs_a = _extract_prefs(candidate_a, "candidate")
    prefs_b = _extract_prefs(candidate_b, "candidate")
    return _normalize_prefs({
        f: (prefs_a[f] + prefs_b[f]) / 2 for f in prefs_a
    })


def _extract_prefs(gene: Any, kind: str) -> dict[str, float]:
    """Extract preference vector from a gene object or dict."""
    if isinstance(gene, dict):
        if kind == "company":
            return {
                f: float(gene.get(f, 0.2))
                for f in ("skill_importance", "experience_importance",
                           "salary_importance", "location_importance", "seniority_importance")
            }
        else:
            return {
                f: float(gene.get(f, 0.5))
                for f in ("values_compensation", "values_remote",
                           "values_growth", "values_stability", "values_culture_fit")
            }
    # Dataclass instance
    if hasattr(gene, "preference_vector"):
        prefs = gene.preference_vector()
        if prefs:
            return {k: float(v) for k, v in prefs.items()}
    # Fallback: try common field names
    if kind == "company":
        return {
            f: float(getattr(gene, f, 0.2))
            for f in ("skill_importance", "experience_importance",
                       "salary_importance", "location_importance", "seniority_importance")
        }
    return {
        f: float(getattr(gene, f, 0.5))
        for f in ("values_compensation", "values_remote",
                   "values_growth", "values_stability", "values_culture_fit")
    }


def _normalize_prefs(prefs: dict[str, float]) -> dict[str, float]:
    """Clamp to [0.0, 1.0] and normalize to sum 1.0."""
    clamped = {k: min(max(v, 0.0), 1.0) for k, v in prefs.items()}
    total = sum(clamped.values()) or 1.0
    return {k: round(v / total, 4) for k, v in clamped.items()}


# ── 5-Stage Evolver helpers ──────────────────────────────────────────


def scan_feedback_patterns(
    feedback_events: list[FeedbackEvent],
    match_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    event_counts: dict[str, int] = {}
    dimension_impact: dict[str, float] = {field: 0.0 for field in WEIGHT_FIELDS}

    for event in feedback_events:
        event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1
        deltas = FEEDBACK_DELTAS.get(event.event_type, {})
        for field_name, delta in deltas.items():
            dimension_impact[field_name] = dimension_impact.get(field_name, 0.0) + delta

    total_delta_magnitude = sum(abs(v) for v in dimension_impact.values())

    if len(event_counts) >= 3 and total_delta_magnitude > 0.15:
        pattern_severity = "high"
    elif len(event_counts) >= 2 or total_delta_magnitude > 0.08:
        pattern_severity = "medium"
    else:
        pattern_severity = "low"

    sorted_by_impact = sorted(
        dimension_impact.items(), key=lambda kv: abs(kv[1]), reverse=True
    )
    suggested_focus = [
        field for field, _ in sorted_by_impact[:3] if abs(dimension_impact[field]) > 0.01
    ]

    result: dict[str, Any] = {
        "event_counts": event_counts,
        "dimension_impact": dimension_impact,
        "total_delta_magnitude": round(total_delta_magnitude, 4),
        "pattern_severity": pattern_severity,
        "suggested_focus": suggested_focus,
    }

    if match_results:
        dimension_scores: dict[str, list[float]] = {
            field: [] for field in WEIGHT_FIELDS
        }
        score_field_map = {
            field: field.replace("_weight", "_score") for field in WEIGHT_FIELDS
        }
        for mr in match_results:
            sd = mr.get("score_detail", {})
            for weight_field, score_field in score_field_map.items():
                if score_field in sd:
                    dimension_scores[weight_field].append(float(sd[score_field]))

        score_trend_analysis = {}
        for field, scores in dimension_scores.items():
            if scores:
                avg = sum(scores) / len(scores)
                score_trend_analysis[field] = {
                    "average_score": round(avg, 4),
                    "count": len(scores),
                    "below_threshold": avg < 0.5,
                }
        result["score_trend_analysis"] = score_trend_analysis

    return result


def select_target_dimensions(
    scan_report: dict[str, Any],
    weight_config: WeightConfig,
) -> dict[str, Any]:
    severity = scan_report.get("pattern_severity", "low")
    suggested_focus = scan_report.get("suggested_focus", [])
    total_magnitude = scan_report.get("total_delta_magnitude", 0.0)

    if severity == "high":
        strategy = "aggressive"
        mutation_rate = 0.6
        mutation_strength = 0.06
    elif severity == "medium":
        strategy = "balanced"
        mutation_rate = 0.4
        mutation_strength = 0.04
    else:
        strategy = "conservative"
        mutation_rate = 0.2
        mutation_strength = 0.02

    return {
        "target_dimensions": suggested_focus,
        "mutation_rate": mutation_rate,
        "mutation_strength": mutation_strength,
        "strategy": strategy,
    }


def validate_candidate_weights(
    candidate: WeightConfig,
    original: WeightConfig,
    match_results: list[dict[str, Any]] | None = None,
    evaluator: Any | None = None,
    job_gene: dict[str, Any] | None = None,
    candidate_genes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    stability = sum(
        abs(candidate.weights()[f] - original.weights()[f])
        for f in WEIGHT_FIELDS
    )

    result: dict[str, Any] = {
        "weight_stability": round(stability, 4),
    }

    if evaluator and job_gene and candidate_genes and match_results:
        old_scores = [mr.get("match_score", 0) for mr in match_results]
        new_scores: list[float] = []
        for cg in candidate_genes:
            mr = evaluator.score_candidate(job_gene, cg, candidate)
            new_scores.append(mr.match_score)

        old_avg = sum(old_scores) / len(old_scores) if old_scores else 0.0
        new_avg = sum(new_scores) / len(new_scores) if new_scores else 0.0
        score_delta = new_avg - old_avg

        result["score_impact"] = {
            "old_average": round(old_avg, 4),
            "new_average": round(new_avg, 4),
            "score_delta": round(score_delta, 4),
        }
        result["is_improvement"] = score_delta >= -0.01
        result["validation_confidence"] = "high" if stability < 0.3 else "medium"
    else:
        all_in_bounds = all(
            MIN_WEIGHT <= candidate.weights()[f] <= MAX_WEIGHT
            for f in WEIGHT_FIELDS
        )
        result["is_improvement"] = all_in_bounds and stability < 0.5
        result["validation_confidence"] = "low"

    return result


# ── Internal helpers ─────────────────────────────────────────────────


def _apply_feedback_deltas(weight_config: WeightConfig, events: list[FeedbackEvent]) -> WeightConfig:
    weights = weight_config.weights()
    for event in events:
        for field_name, delta in FEEDBACK_DELTAS[event.event_type].items():
            weights[field_name] += delta

    return _build_weight_config(weights, weight_config.generation + 1)


def _normalize_feedback_events(
    feedback_events: list[dict[str, Any] | FeedbackEvent] | dict[str, Any] | FeedbackEvent,
) -> list[FeedbackEvent]:
    if isinstance(feedback_events, list):
        return [record_feedback(feedback_event) for feedback_event in feedback_events]
    return [record_feedback(feedback_events)]


def _build_weight_config(weights: dict[str, float], generation: int) -> WeightConfig:
    bounded_weights = _normalize_with_bounds(weights)
    return WeightConfig.from_dict({"generation": generation, **bounded_weights})


def _build_evolution_summary(
    original: WeightConfig,
    evolved: WeightConfig,
    events: list[FeedbackEvent],
) -> dict[str, Any]:
    weight_changes = {
        field_name: round(evolved.weights()[field_name] - original.weights()[field_name], 4)
        for field_name in WEIGHT_FIELDS
    }
    change_magnitude = round(sum(abs(value) for value in weight_changes.values()), 4)
    return {
        "generation": evolved.generation,
        "total_events": len(events),
        "event_counts": dict(Counter(event.event_type for event in events)),
        "weight_changes": weight_changes,
        "change_magnitude": change_magnitude,
        "convergence_status": _classify_convergence(len(events), change_magnitude),
    }


def _classify_convergence(total_events: int, change_magnitude: float) -> str:
    if total_events == 0:
        return "no_feedback"
    if change_magnitude < 0.01:
        return "stable"
    if change_magnitude < 0.03:
        return "converging"
    return "adjusting"


def _normalize_with_bounds(weights: dict[str, float]) -> dict[str, float]:
    bounded = {
        field_name: min(max(float(weights[field_name]), MIN_WEIGHT), MAX_WEIGHT)
        for field_name in WEIGHT_FIELDS
    }

    for _ in range(10):
        total = sum(bounded.values())
        normalized = {field_name: value / total for field_name, value in bounded.items()}
        fixed = {}
        variable = {}
        for field_name, value in normalized.items():
            if value < MIN_WEIGHT:
                fixed[field_name] = MIN_WEIGHT
            elif value > MAX_WEIGHT:
                fixed[field_name] = MAX_WEIGHT
            else:
                variable[field_name] = value

        if not fixed:
            return normalized

        remaining = 1.0 - sum(fixed.values())
        if not variable:
            share = remaining / len(WEIGHT_FIELDS)
            return {field_name: share for field_name in WEIGHT_FIELDS}

        variable_total = sum(variable.values())
        bounded = {
            **fixed,
            **{
                field_name: value / variable_total * remaining
                for field_name, value in variable.items()
            },
        }

    total = sum(bounded.values())
    return {field_name: value / total for field_name, value in bounded.items()}
