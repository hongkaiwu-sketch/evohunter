from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from evohunter.core.evolution.evolution import (
    WEIGHT_FIELDS,
    crossover_weight_configs,
    mutate_weight_config,
    scan_feedback_patterns,
    select_target_dimensions,
    validate_candidate_weights,
)
from evohunter.core.protocol import (
    EvolutionEvent,
    FeedbackEvent,
    WeightConfig,
    generate_evolution_id,
    validate_feedback_event,
    validate_weight_config,
)

DEFAULT_NUM_CANDIDATES = 5


class EvoMapEvolver:
    """5-Stage evolution cycle orchestrator.

    1. Scan   — Analyze feedback patterns and historical scores
    2. Select — Choose target dimensions and mutation parameters
    3. Mutate — Generate candidate weight configs
    4. Validate — Score candidates against historical data
    5. Solidify — Pick the best config, record EvolutionEvent
    """

    def __init__(
        self,
        db_path: str | None = None,
        evaluator: Any | None = None,
        a2a_client: Any | None = None,
        sender_id: str | None = None,
    ) -> None:
        self._db_path = db_path
        self._evaluator = evaluator
        self._a2a_client = a2a_client
        self._sender_id = sender_id
        self._cycle_count = 0

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    def run_cycle(
        self,
        weight_config: dict[str, Any] | WeightConfig,
        feedback_events: list[dict[str, Any] | FeedbackEvent],
        match_results: list[dict[str, Any]] | None = None,
        job_gene: dict[str, Any] | None = None,
        candidate_genes: list[dict[str, Any]] | None = None,
        publish_to_hub: bool = False,
        fetch_from_hub: bool = False,
        num_candidates: int = DEFAULT_NUM_CANDIDATES,
    ) -> dict[str, Any]:
        self._cycle_count += 1

        current_wc = validate_weight_config(weight_config)
        events = [validate_feedback_event(e) for e in feedback_events]

        # Stage 1: Scan
        scan_report = scan_feedback_patterns(events, match_results)

        # Stage 2: Select (with optional strategy override from Evolution Control Center)
        selection = select_target_dimensions(scan_report, current_wc)
        self._apply_strategy_override(selection)

        # Stage 3: Mutate
        candidates = self._stage_mutate(
            current_wc, selection, num_candidates, fetch_from_hub
        )

        # Stage 4: Validate
        validation_reports = self._stage_validate(
            current_wc, candidates, match_results, job_gene, candidate_genes
        )

        # Stage 5: Solidify
        evolved_wc, solidify_info = self._stage_solidify(
            current_wc, candidates, validation_reports
        )

        # Build EvolutionEvent
        evolution_event = EvolutionEvent(
            evolution_id=generate_evolution_id(),
            cycle_number=self._cycle_count,
            intent="recruiting_weight_tuning",
            strategy=selection["strategy"],
            capsule_id=None,
            genes_used=[c.weights() for c in candidates[:3]],
            outcome={
                "weight_config": evolved_wc.to_dict(),
                "performance": solidify_info,
            },
            mutations_tried=num_candidates,
            total_cycles=self._cycle_count,
            created_at=datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.%f"
            )[:-3] + "Z",
        )

        # Build extended summary
        weight_changes = {
            f: round(evolved_wc.weights()[f] - current_wc.weights()[f], 4)
            for f in WEIGHT_FIELDS
        }
        change_magnitude = round(sum(abs(v) for v in weight_changes.values()), 4)

        summary = {
            "generation": evolved_wc.generation,
            "total_events": len(events),
            "event_counts": scan_report.get("event_counts", {}),
            "pattern_severity": scan_report.get("pattern_severity", "low"),
            "strategy": selection["strategy"],
            "target_dimensions": selection["target_dimensions"],
            "weight_changes": weight_changes,
            "change_magnitude": change_magnitude,
            "convergence_status": _classify_convergence_evolver(
                len(events), solidify_info
            ),
        }

        # Optional A2A publish
        if publish_to_hub and self._a2a_client:
            try:
                self._a2a_client.publish(
                    evolution_event.to_dict(), evolved_wc.to_dict()
                )
                summary["published_to_hub"] = True
            except Exception:
                summary["published_to_hub"] = False

        if fetch_from_hub and self._a2a_client:
            summary["fetched_from_hub"] = True

        return {
            "weight_config": evolved_wc.to_dict(),
            "evolution_summary": summary,
            "scan_report": scan_report,
            "selection_strategy": selection,
            "validation_report": validation_reports,
            "evolution_event": evolution_event.to_dict(),
        }

    def run_gene_cycle(
        self,
        company_gene: Any | None = None,
        candidate_genes: list[Any] | None = None,
        feedback_events: list[dict[str, Any]] | None = None,
        publish_to_hub: bool = False,
        fetch_from_hub: bool = False,
        num_mutations: int = 3,
    ) -> dict[str, Any]:
        """Run an evolution cycle on gene-level preferences.

        Evolves company and/or candidate preference vectors based on feedback,
        then optionally exchanges anonymized genes via A2A.
        """
        from evohunter.core.evolution.evolution import (
            mutate_company_preferences,
            mutate_candidate_preferences,
            crossover_candidate_preferences,
            crossover_company_preferences,
        )
        from evohunter.core.privacy import (
            anonymize_company_gene,
            anonymize_candidate_gene,
        )

        events = feedback_events or []
        result: dict[str, Any] = {
            "company_gene": None,
            "candidate_genes": [],
            "evolution_event": None,
        }

        # Evolve company preferences
        if company_gene is not None:
            mutated = []
            for _ in range(num_mutations):
                mutated.append(mutate_company_preferences(company_gene))
            # Select best via simple averaging (stability-preserving)
            avg_prefs = {
                k: round(sum(m[k] for m in mutated) / len(mutated), 4)
                for k in mutated[0]
            }
            result["company_gene"] = {
                "preference_vector": avg_prefs,
                "original_hash": getattr(company_gene, "company_hash", ""),
                "evolved": True,
            }

        # Evolve candidate preferences
        if candidate_genes:
            evolved_candidates = []
            for cg in candidate_genes:
                mutated = []
                for _ in range(max(num_mutations - 1, 1)):
                    mutated.append(mutate_candidate_preferences(cg))
                mutated.append(crossover_candidate_preferences(cg, cg))
                avg_prefs = {
                    k: round(sum(m[k] for m in mutated) / len(mutated), 4)
                    for k in mutated[0]
                }
                evolved_candidates.append({
                    "candidate_hash": getattr(cg, "candidate_hash", ""),
                    "preference_vector": avg_prefs,
                    "evolved": True,
                })
            result["candidate_genes"] = evolved_candidates

        # Build EvolutionEvent
        evolution_event = {
            "gene_cycle": True,
            "intent": "gene_preference_evolution",
            "company_evolved": company_gene is not None,
            "candidates_evolved": len(evolved_candidates) if candidate_genes else 0,
            "feedback_event_count": len(events),
        }

        # A2A exchange
        if publish_to_hub and self._a2a_client:
            try:
                pub_kwargs: dict[str, Any] = {}
                if company_gene is not None:
                    pub_kwargs["company_gene"] = anonymize_company_gene(
                        company_gene
                    ).to_dict()
                if candidate_genes:
                    pub_kwargs["candidate_gene"] = anonymize_candidate_gene(
                        candidate_genes[0]
                    ).to_dict()
                pub_kwargs["evolution_event"] = evolution_event
                self._a2a_client.publish_genes(**pub_kwargs)
                evolution_event["published_to_hub"] = True
            except Exception:
                evolution_event["published_to_hub"] = False

        if fetch_from_hub and self._a2a_client:
            try:
                fetched = self._a2a_client.fetch_genes(limit=3)
                result["fetched_genes"] = fetched
                evolution_event["fetched_from_hub"] = True
            except Exception:
                evolution_event["fetched_from_hub"] = False

        result["evolution_event"] = evolution_event
        return result

    # ── Strategy override ───────────────────────────────────────────

    def _apply_strategy_override(self, selection: dict[str, Any]) -> None:
        """Check storage for user-configured strategy and override selection params.

        Reads the ``evolution_strategy`` table populated by the Evolution
        Control Center UI. Overrides mutation_rate, mutation_strength,
        strategy, and filters target_dimensions.
        """
        if not self._db_path:
            return
        try:
            from evohunter.storage import load_evolution_strategy
            override = load_evolution_strategy(self._db_path)
            if override is None:
                return

            # Override strategy and mutation params
            strategy = override.get("strategy")
            if strategy == "conservative":
                selection["strategy"] = "conservative"
                selection["mutation_rate"] = 0.2
                selection["mutation_strength"] = 0.02
            elif strategy == "aggressive":
                selection["strategy"] = "aggressive"
                selection["mutation_rate"] = 0.6
                selection["mutation_strength"] = 0.06
            else:
                selection["strategy"] = "balanced"

            # Apply explicit overrides if set
            mr = override.get("mutation_rate")
            ms = override.get("mutation_strength")
            if mr is not None and mr > 0:
                selection["mutation_rate"] = float(mr)
            if ms is not None and ms > 0:
                selection["mutation_strength"] = float(ms)

            # Filter target dimensions
            target_dims = override.get("target_dimensions", [])
            if target_dims:
                selection["target_dimensions"] = [
                    d for d in selection.get("target_dimensions", [])
                    if d.replace("_weight", "") in target_dims
                ]

        except Exception:
            pass  # strategy override is best-effort, never blocks evolution

    # ── Internal stage methods ────────────────────────────────────────

    def _stage_mutate(
        self,
        current: WeightConfig,
        selection: dict[str, Any],
        num_candidates: int,
        fetch_from_hub: bool,
    ) -> list[WeightConfig]:
        candidates: list[WeightConfig] = []
        rate = selection["mutation_rate"]
        strength = selection["mutation_strength"]

        # Generate via mutation
        for _ in range(max(num_candidates - 1, 1)):
            candidates.append(mutate_weight_config(current, rate, strength))

        # Generate via self-crossover (structural anchor)
        candidates.append(crossover_weight_configs(current, current))

        # If fetch_from_hub, blend remote configs into mutation pool
        if fetch_from_hub and self._a2a_client:
            try:
                remote_configs = self._a2a_client.fetch(limit=3)
                for rc in remote_configs:
                    wc_data = rc.get("payload", {}).get("weight_config", {})
                    if wc_data:
                        remote_wc = validate_weight_config(wc_data)
                        candidates.append(
                            crossover_weight_configs(current, remote_wc)
                        )
            except Exception:
                pass  # network failure is non-fatal

        return candidates[: num_candidates + 2]  # cap

    def _stage_validate(
        self,
        original: WeightConfig,
        candidates: list[WeightConfig],
        match_results: list[dict[str, Any]] | None,
        job_gene: Any | None,
        candidate_genes: list[Any] | None,
    ) -> list[dict[str, Any]]:
        reports = []
        for candidate in candidates:
            report = validate_candidate_weights(
                candidate,
                original,
                match_results,
                self._evaluator,
                job_gene,
                candidate_genes,
            )
            report["config"] = candidate.to_dict()
            reports.append(report)

        # Sort: best improvement first
        reports.sort(
            key=lambda r: (
                r.get("score_impact", {}).get("score_delta", 0.0)
                if r.get("score_impact")
                else -r.get("weight_stability", 999.0)
            ),
            reverse=True,
        )
        return reports

    def _stage_solidify(
        self,
        original: WeightConfig,
        candidates: list[WeightConfig],
        validation_reports: list[dict[str, Any]],
    ) -> tuple[WeightConfig, dict[str, Any]]:
        improvements = [
            (i, r)
            for i, r in enumerate(validation_reports)
            if r.get("is_improvement", False)
        ]
        if improvements:
            best_idx, best_report = improvements[0]
            best_candidate = candidates[best_idx]
            info = {
                "selection_method": "best_validated",
                "best_validation": best_report,
                "candidate_rank": 0,
            }
        else:
            # No improvement — fall back to minimal mutation
            best_candidate = mutate_weight_config(original, 0.1, 0.01)
            info = {
                "selection_method": "fallback_mutation",
                "best_validation": {
                    "is_improvement": True,
                    "note": "fallback from no-improvement candidates",
                },
                "candidate_rank": -1,
            }
        return best_candidate, info


def _classify_convergence_evolver(
    total_events: int,
    solidify_info: dict[str, Any],
) -> str:
    if total_events == 0:
        return "no_feedback"
    validation = solidify_info.get("best_validation", {})
    stability = validation.get("weight_stability", 999.0)
    if stability < 0.01:
        return "stable"
    if stability < 0.03:
        return "converging"
    return "adjusting"
