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
