import pytest

from evohunter.core.evolution import (
    crossover_weight_configs,
    evolve_weight_config_with_summary,
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


def test_evolve_weight_config_with_summary_reports_event_counts_and_convergence():
    weight_config = WeightConfig.from_dict({})
    output = evolve_weight_config_with_summary(
        weight_config,
        [
            {"candidate_id": "c_001", "job_id": "j_001", "event_type": "salary_mismatch"},
            {"candidate_id": "c_002", "job_id": "j_001", "event_type": "salary_mismatch"},
            {"candidate_id": "c_003", "job_id": "j_001", "event_type": "location_mismatch"},
        ],
    )

    assert output["weight_config"]["generation"] == 1
    assert output["evolution_summary"]["total_events"] == 3
    assert output["evolution_summary"]["event_counts"] == {
        "salary_mismatch": 2,
        "location_mismatch": 1,
    }
    assert output["evolution_summary"]["weight_changes"]["salary_weight"] > 0
    assert output["evolution_summary"]["change_magnitude"] > 0
    assert output["evolution_summary"]["convergence_status"] == "adjusting"


# ── 5-Stage Evolver tests ────────────────────────────────────────────

def test_scan_feedback_patterns_returns_event_counts():
    from evohunter.core.evolution import scan_feedback_patterns
    events = [
        FeedbackEvent.from_dict({"candidate_id": "c_001", "job_id": "j_001", "event_type": "salary_mismatch"}),
        FeedbackEvent.from_dict({"candidate_id": "c_002", "job_id": "j_001", "event_type": "salary_mismatch"}),
        FeedbackEvent.from_dict({"candidate_id": "c_003", "job_id": "j_001", "event_type": "location_mismatch"}),
    ]
    report = scan_feedback_patterns(events)
    assert report["event_counts"] == {"salary_mismatch": 2, "location_mismatch": 1}
    assert report["pattern_severity"] in ("low", "medium", "high")
    assert "suggested_focus" in report


def test_scan_feedback_patterns_detects_severity():
    from evohunter.core.evolution import scan_feedback_patterns
    events = [
        FeedbackEvent.from_dict({"candidate_id": f"c_{i:03d}", "job_id": "j_001", "event_type": t})
        for i, t in enumerate(["reply_positive", "interview_passed", "salary_mismatch", "location_mismatch", "no_reply"])
    ]
    report = scan_feedback_patterns(events)
    assert report["pattern_severity"] == "high"


def test_select_target_dimensions_returns_strategy():
    from evohunter.core.evolution import select_target_dimensions
    scan_report = {
        "event_counts": {"salary_mismatch": 2},
        "dimension_impact": {"salary_weight": 0.08},
        "total_delta_magnitude": 0.08,
        "pattern_severity": "medium",
        "suggested_focus": ["salary_weight"],
    }
    strategy = select_target_dimensions(scan_report, WeightConfig.from_dict({}))
    assert strategy["strategy"] == "balanced"
    assert 0 < strategy["mutation_rate"] <= 1
    assert strategy["mutation_strength"] > 0
    assert "salary_weight" in strategy["target_dimensions"]


def test_validate_candidate_weights_checks_stability():
    from evohunter.core.evolution import validate_candidate_weights
    original = WeightConfig.from_dict({})
    candidate = WeightConfig.from_dict({
        "skill_weight": 0.5, "experience_weight": 0.2,
        "salary_weight": 0.15, "location_weight": 0.1, "seniority_weight": 0.05,
    })
    report = validate_candidate_weights(candidate, original)
    assert "weight_stability" in report
    assert "is_improvement" in report
    assert report["validation_confidence"] == "low"


def test_evomap_evolver_run_cycle_returns_full_output():
    from evohunter.core.evolution.evolver import EvoMapEvolver
    evolver = EvoMapEvolver()
    result = evolver.run_cycle(
        weight_config={},
        feedback_events=[
            {"candidate_id": "c_001", "job_id": "j_001", "event_type": "salary_mismatch"},
        ],
    )
    assert "weight_config" in result
    assert "evolution_summary" in result
    assert "scan_report" in result
    assert "selection_strategy" in result
    assert "validation_report" in result
    assert "evolution_event" in result
    assert result["evolution_summary"]["total_events"] == 1
    assert result["evolution_event"]["intent"] == "recruiting_weight_tuning"


def test_evolve_backward_compatible_without_cycle_flag():
    from evohunter.core.evolution import evolve_weight_config
    wc = WeightConfig.from_dict({})
    result = evolve_weight_config(wc, [
        {"candidate_id": "c_001", "job_id": "j_001", "event_type": "reply_positive"},
    ])
    assert result.generation == 1
    assert result.skill_weight > wc.skill_weight
    assert sum(result.weights().values()) == pytest.approx(1.0)
