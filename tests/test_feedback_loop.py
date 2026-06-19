import pytest

from evohunter.core.evolution import (
    crossover_weight_configs,
    evolve_weight_config,
    mutate_weight_config,
    record_feedback,
)
from evohunter.core.protocol import FeedbackEvent, WeightConfig


def test_mutate_weight_config_changes_weights_and_preserves_total():
    weight_config = WeightConfig.from_dict({})

    mutated = mutate_weight_config(weight_config, mutation_rate=1.0, mutation_strength=0.05)

    assert mutated.generation == weight_config.generation + 1
    assert mutated.weights() != weight_config.weights()
    assert sum(mutated.weights().values()) == pytest.approx(1.0)
    assert all(0.05 <= value <= 0.70 for value in mutated.weights().values())


def test_crossover_weight_configs_mixes_parent_weights():
    parent_a = WeightConfig.from_dict(
        {
            "generation": 2,
            "skill_weight": 0.7,
            "experience_weight": 0.1,
            "salary_weight": 0.1,
            "location_weight": 0.05,
            "seniority_weight": 0.05,
        }
    )
    parent_b = WeightConfig.from_dict(
        {
            "generation": 4,
            "skill_weight": 0.1,
            "experience_weight": 0.4,
            "salary_weight": 0.2,
            "location_weight": 0.2,
            "seniority_weight": 0.1,
        }
    )

    child = crossover_weight_configs(parent_a, parent_b)

    assert child.generation == 5
    assert parent_b.skill_weight < child.skill_weight < parent_a.skill_weight
    assert parent_a.experience_weight < child.experience_weight < parent_b.experience_weight
    assert sum(child.weights().values()) == pytest.approx(1.0)


def test_evolve_weight_config_uses_positive_feedback_to_raise_skill_and_experience():
    weight_config = WeightConfig.from_dict({})
    feedback_events = [
        FeedbackEvent.from_dict(
            {
                "candidate_id": "c_001",
                "job_id": "j_001",
                "event_type": "reply_positive",
            }
        ),
        FeedbackEvent.from_dict(
            {
                "candidate_id": "c_002",
                "job_id": "j_001",
                "event_type": "interview_passed",
            }
        ),
    ]

    evolved = evolve_weight_config(weight_config, feedback_events)

    assert evolved.generation == 1
    assert evolved.skill_weight > weight_config.skill_weight
    assert evolved.experience_weight > weight_config.experience_weight
    assert sum(evolved.weights().values()) == pytest.approx(1.0)


def test_evolve_weight_config_uses_mismatch_feedback_to_raise_matching_dimension():
    weight_config = WeightConfig.from_dict({})
    feedback_events = [
        {"candidate_id": "c_001", "job_id": "j_001", "event_type": "salary_mismatch"},
        {"candidate_id": "c_002", "job_id": "j_001", "event_type": "location_mismatch"},
        {"candidate_id": "c_003", "job_id": "j_001", "event_type": "no_reply"},
    ]

    evolved = evolve_weight_config(weight_config, feedback_events)

    assert evolved.salary_weight > weight_config.salary_weight
    assert evolved.location_weight > weight_config.location_weight
    assert sum(evolved.weights().values()) == pytest.approx(1.0)


def test_record_feedback_returns_validated_feedback_event():
    feedback_event = record_feedback(
        {
            "candidate_id": "c_001",
            "job_id": "j_001",
            "event_type": "interview_failed",
        }
    )

    assert feedback_event.event_type == "interview_failed"
