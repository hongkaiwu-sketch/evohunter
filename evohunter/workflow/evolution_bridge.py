from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from evohunter.core.evolution import EvoMapEvolver
from evohunter.core.evolution.evolution import scan_feedback_patterns
from evohunter.core.protocol import (
    FeedbackEvent,
    WeightConfig,
    validate_feedback_event,
    validate_weight_config,
)
from evohunter.storage import (
    save_evolution_event,
    save_feedback_events,
    save_weight_config,
)


class EvolutionBridge:
    """Bridge between left brain (workflow) and right brain (evolver).

    Responsibilities:
    1. Extract feedback signals from workflow node outputs
    2. Convert to standard FeedbackEvent list
    3. Invoke right-brain EvoMapEvolver.run_cycle() or run_gene_cycle()
    4. Write evolved results back to storage

    This is the integration point where left-brain execution logs
    drive right-brain evolution.
    """

    def __init__(
        self,
        db_path: str | None = None,
        sender_id: str | None = None,
        publish_to_hub: bool = False,
        fetch_from_hub: bool = False,
    ) -> None:
        self._db_path = db_path
        self._sender_id = sender_id
        self._publish_to_hub = publish_to_hub
        self._fetch_from_hub = fetch_from_hub

    # ── Main entry: evolve after workflow execution ───────────────────

    def after_workflow(
        self,
        workflow_result: dict[str, Any],
        weight_config: dict[str, Any] | None = None,
        company_gene: Any | None = None,
        candidate_genes: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Run evolution after a workflow execution completes.

        Returns a dict with evolution results or an explanation if skipped.
        """
        # Step 1: Extract feedback signals from workflow results
        feedback_events = self._extract_feedback(workflow_result)

        # Step 2: Decide whether evolution is needed
        decision = self._should_evolve(workflow_result, feedback_events)
        if not decision["should_evolve"]:
            return decision

        # Step 3: Run evolution
        return self._run_evolution(
            feedback_events=feedback_events,
            weight_config=weight_config,
            company_gene=company_gene,
            candidate_genes=candidate_genes,
            workflow_result=workflow_result,
        )

    # ── Feedback extraction from workflow nodes ───────────────────────

    def _extract_feedback(
        self, workflow_result: dict[str, Any]
    ) -> list[FeedbackEvent]:
        """Scan workflow node outputs and convert to FeedbackEvents.

        Extraction rules by node:

        - resume_parsing: match_degree < 6 → signals a "quality_mismatch"
          (JD or resume parsing quality issues). missing_fields → signals
          "data_incomplete" which should drive scraper/parser improvements.

        - intelligent_outreach: delivery_status=False → "no_reply" signal.
          If a candidate reply is recorded → "reply_positive".

        - evaluation_report: final_recommendation is "weak_hire" or "no"
          → signals "interview_failed" or "skill_mismatch".

        - External feedback (context input): user-provided feedback_events
          in the workflow inputs are passed through directly.
        """
        events: list[FeedbackEvent] = []
        node_results = workflow_result.get("node_results", {})
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

        candidate_id = _find_candidate_id(node_results)
        job_id = _find_job_id(node_results)

        # ── Resume parsing signals ─────────────────────────────────
        assessment = node_results.get("resume_parsing", {})
        if isinstance(assessment, dict):
            match_degree = assessment.get("match_degree", 0)

            if match_degree <= 5:
                events.append(
                    _make_event(candidate_id, job_id, "interview_failed",
                                f"low_match_{match_degree}", now)
                )
            if assessment.get("missing_fields"):
                events.append(
                    _make_event(candidate_id, job_id, "no_reply",
                                "missing_info_" + "_".join(assessment["missing_fields"]), now)
                )

            # Salary mismatch signal
            deductions = assessment.get("main_deductions", [])
            for d in deductions:
                if "薪资" in str(d) or "salary" in str(d).lower():
                    events.append(
                        _make_event(candidate_id, job_id, "salary_mismatch", str(d)[:100], now)
                    )
                if "地点" in str(d) or "location" in str(d).lower():
                    events.append(
                        _make_event(candidate_id, job_id, "location_mismatch", str(d)[:100], now)
                    )

        # ── Outreach signals ──────────────────────────────────────
        outreach = node_results.get("intelligent_outreach", {})
        if isinstance(outreach, dict):
            if not outreach.get("delivery_status", True):
                events.append(
                    _make_event(candidate_id, job_id, "no_reply",
                                "delivery_failed", now)
                )
            thread = outreach.get("thread", {})
            if isinstance(thread, dict):
                status = thread.get("status", "")
                if status == "replied":
                    events.append(
                        _make_event(candidate_id, job_id, "reply_positive",
                                    "candidate_replied", now)
                    )
                elif status == "scheduled":
                    events.append(
                        _make_event(candidate_id, job_id, "interview_passed",
                                    "interview_scheduled", now)
                    )

        # ── Evaluation report signals ─────────────────────────────
        report = node_results.get("evaluation_report", {})
        if isinstance(report, dict):
            rec = report.get("final_recommendation", "")
            if rec == "no":
                events.append(
                    _make_event(candidate_id, job_id, "interview_failed",
                                "final_recommendation_no", now)
                )
            elif rec == "weak_hire":
                events.append(
                    _make_event(candidate_id, job_id, "interview_failed",
                                "final_recommendation_weak", now)
                )

        return events

    # ── Evolution decision ──────────────────────────────────────────

    def _should_evolve(
        self,
        workflow_result: dict[str, Any],
        feedback_events: list[FeedbackEvent],
    ) -> dict[str, Any]:
        """Decide whether to trigger evolution.

        Returns {"should_evolve": bool, "reason": str}.
        """
        if not feedback_events:
            return {
                "should_evolve": False,
                "reason": "no_feedback_events_extracted",
                "note": "workflow completed without actionable feedback signals",
            }

        # Check if we have enough signal
        scan = scan_feedback_patterns(feedback_events, None)
        severity = scan.get("pattern_severity", "low")

        if severity == "low" and len(feedback_events) < 2:
            return {
                "should_evolve": False,
                "reason": "insufficient_signal",
                "scan_report": scan,
                "note": "not enough feedback events to trigger meaningful evolution",
            }

        return {
            "should_evolve": True,
            "reason": f"pattern_severity={severity}",
            "scan_report": scan,
            "feedback_count": len(feedback_events),
        }

    # ── Evolution execution ─────────────────────────────────────────

    def _run_evolution(
        self,
        feedback_events: list[FeedbackEvent],
        weight_config: dict[str, Any] | None,
        company_gene: Any | None,
        candidate_genes: list[Any] | None,
        workflow_result: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute the right-brain evolution cycle."""
        # Build A2A client if configured
        a2a_client = None
        if self._sender_id:
            try:
                from evohunter.core.evolution.a2a import A2AClient
                a2a_client = A2AClient(sender_id=self._sender_id)
            except Exception:
                pass

        evolver = EvoMapEvolver(
            db_path=self._db_path,
            a2a_client=a2a_client,
            sender_id=self._sender_id,
        )

        events_dicts = [e.to_dict() for e in feedback_events]
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

        result: dict[str, Any] = {
            "feedback_events_extracted": len(feedback_events),
            "evolution_triggered_at": now,
        }

        # ── Weight evolution (legacy 5-stage cycle) ─────────────────
        if weight_config is not None:
            try:
                wc = validate_weight_config(weight_config)
                weight_result = evolver.run_cycle(
                    weight_config=wc,
                    feedback_events=events_dicts,
                    publish_to_hub=self._publish_to_hub,
                    fetch_from_hub=self._fetch_from_hub,
                )
                result["weight_evolution"] = weight_result

                if self._db_path:
                    try:
                        save_feedback_events(self._db_path, events_dicts)
                        save_weight_config(
                            self._db_path,
                            weight_result["weight_config"],
                            step="evolve_after_workflow",
                        )
                        if "evolution_event" in weight_result:
                            save_evolution_event(
                                self._db_path,
                                weight_result["evolution_event"],
                            )
                    except Exception:
                        pass
            except Exception as exc:
                result["weight_evolution_error"] = str(exc)

        # ── Gene preference evolution (company + candidate preferences) ──
        if company_gene is not None or candidate_genes:
            try:
                gene_result = evolver.run_gene_cycle(
                    company_gene=company_gene,
                    candidate_genes=candidate_genes or [],
                    feedback_events=events_dicts,
                    publish_to_hub=self._publish_to_hub,
                    fetch_from_hub=self._fetch_from_hub,
                )
                result["gene_evolution"] = gene_result
            except Exception as exc:
                result["gene_evolution_error"] = str(exc)

        return result


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_event(
    candidate_id: str,
    job_id: str,
    event_type: str,
    event_value: str,
    event_time: str,
) -> FeedbackEvent:
    return FeedbackEvent(
        candidate_id=candidate_id or "unknown",
        job_id=job_id or "unknown",
        event_type=event_type,
        event_value=event_value,
        event_time=event_time,
    )


def _find_candidate_id(node_results: dict[str, Any]) -> str:
    """Walk node results to find a candidate identifier."""
    # Check resume_parsing first
    assessment = node_results.get("resume_parsing", {})
    if isinstance(assessment, dict):
        cid = assessment.get("candidate_name", "")
        if cid:
            return cid
    # Check outreach thread
    outreach = node_results.get("intelligent_outreach", {})
    if isinstance(outreach, dict):
        thread = outreach.get("thread", {})
        if isinstance(thread, dict):
            cid = thread.get("candidate_id", "")
            if cid:
                return cid
    # Check evaluation report
    report = node_results.get("evaluation_report", {})
    if isinstance(report, dict):
        cid = report.get("candidate_hash", "")
        if cid:
            return cid
    return "unknown"


def _find_job_id(node_results: dict[str, Any]) -> str:
    """Walk node results to find a job identifier."""
    jd = node_results.get("jd_generation", {})
    if isinstance(jd, dict):
        job_gene = jd.get("job_gene", {})
        if isinstance(job_gene, dict):
            jid = job_gene.get("job_id", "")
            if jid:
                return jid
    report = node_results.get("evaluation_report", {})
    if isinstance(report, dict):
        jid = report.get("job_id", "")
        if jid:
            return jid
    return "unknown"
