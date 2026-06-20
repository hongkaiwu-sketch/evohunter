from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from evohunter.ai import DEFAULT_MODEL, complete_chat
from evohunter.workflow.base import BaseWorkflowNode
from evohunter.workflow.models import WorkflowContext


@dataclass(frozen=True)
class EvaluationReport:
    report_id: str
    candidate_hash: str
    job_id: str
    final_recommendation: str  # "strong_hire" | "hire" | "weak_hire" | "no"
    resume_summary: str
    match_assessment: dict[str, Any] = field(default_factory=dict)
    interview_qa: list[dict[str, Any]] = field(default_factory=list)
    background_check: dict[str, Any] = field(default_factory=dict)
    overall_risk: str = "low"  # "low" | "medium" | "high"
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "candidate_hash": self.candidate_hash,
            "job_id": self.job_id,
            "final_recommendation": self.final_recommendation,
            "resume_summary": self.resume_summary,
            "match_assessment": dict(self.match_assessment),
            "interview_qa": list(self.interview_qa),
            "background_check": dict(self.background_check),
            "overall_risk": self.overall_risk,
            "created_at": self.created_at,
        }


class EvaluationReportNode(BaseWorkflowNode):
    """Node ④: Evaluation Report Generation.

    Synthesizes:
    - Resume assessment from Node ②
    - Interview Q&A (from context input)
    - Background check info (from context input)
    - Outreach/interview history from Node ③

    Outputs a structured hiring recommendation report.
    """

    def __init__(
        self,
        ai_client: Any | None = None,
        model: str = DEFAULT_MODEL,
        node_id: str = "evaluation_report",
    ) -> None:
        super().__init__(node_id, {"model": model})
        self._ai = ai_client
        self._model = model

    def execute(self, context: WorkflowContext) -> dict[str, Any]:
        assessment = context.get_node_result("resume_parsing") or {}
        outreach = context.get_node_result("intelligent_outreach") or {}
        jd_result = context.get_node_result("jd_generation") or {}
        interview_qa = context.get_input("interview_qa", [])
        background_check = context.get_input("background_check", {})
        language = context.get_input("language", "zh")

        # Determine recommendation via rules
        recommendation = self._determine_recommendation(
            assessment=assessment,
            interview_qa=interview_qa,
            background_check=background_check,
        )
        risk = self._assess_risk(assessment, background_check)

        # Generate summary via LLM
        resume_summary = assessment.get("background_summary", "")
        if not resume_summary:
            try:
                resume_summary = _generate_report_summary(
                    client=self._ai,
                    model=self._model,
                    assessment=assessment,
                    interview_qa=interview_qa,
                    background_check=background_check,
                    recommendation=recommendation,
                    language=language,
                )
            except Exception:
                resume_summary = assessment.get("conclusion", "")

        report = EvaluationReport(
            report_id=f"rpt_{uuid.uuid4().hex[:12]}",
            candidate_hash=assessment.get("candidate_name", "unknown"),
            job_id=jd_result.get("job_gene", {}).get("job_id", "unknown"),
            final_recommendation=recommendation,
            resume_summary=resume_summary,
            match_assessment=assessment,
            interview_qa=interview_qa,
            background_check=background_check,
            overall_risk=risk,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        return report.to_dict()

    def _determine_recommendation(
        self,
        assessment: dict[str, Any],
        interview_qa: list[dict[str, Any]],
        background_check: dict[str, Any],
    ) -> str:
        match_degree = assessment.get("match_degree", 0)

        # Interview score
        interview_scores = [
            qa.get("score", 0)
            for qa in interview_qa
            if isinstance(qa, dict) and qa.get("score")
        ]
        avg_interview = (
            sum(interview_scores) / len(interview_scores)
            if interview_scores
            else 5
        )

        # Background check
        red_flags = background_check.get("red_flags", [])
        bg_ok = len(red_flags) == 0

        if match_degree >= 8 and avg_interview >= 7 and bg_ok:
            return "strong_hire"
        if match_degree >= 6 and avg_interview >= 5 and bg_ok:
            return "hire"
        if match_degree >= 4:
            return "weak_hire"
        return "no"

    def _assess_risk(
        self,
        assessment: dict[str, Any],
        background_check: dict[str, Any],
    ) -> str:
        risks = 0
        if assessment.get("match_degree", 10) < 6:
            risks += 1
        if background_check.get("red_flags"):
            risks += len(background_check["red_flags"])
        if assessment.get("missing_fields"):
            risks += 1

        if risks >= 3:
            return "high"
        if risks >= 1:
            return "medium"
        return "low"


def _generate_report_summary(
    client: Any,
    model: str,
    assessment: dict[str, Any],
    interview_qa: list[dict[str, Any]],
    background_check: dict[str, Any],
    recommendation: str,
    language: str,
) -> str:
    """Generate a comprehensive evaluation summary via LLM."""

    rec_labels = {
        "strong_hire": "强烈建议录用" if language == "zh" else "Strong Hire",
        "hire": "建议录用" if language == "zh" else "Hire",
        "weak_hire": "可考虑录用" if language == "zh" else "Weak Hire",
        "no": "不建议录用" if language == "zh" else "Not Recommended",
    }

    if language == "zh":
        system = (
            "你是一名资深技术猎头顾问。请根据候选人评估数据、面试反馈和背调信息，"
            "生成一份简洁的候选人综合评估总结（200字以内）。"
            "只陈述可核验的事实，不虚构不夸张。"
        )
    else:
        system = (
            "You are a senior technical recruiter. Generate a concise candidate "
            "evaluation summary (within 150 words) based on assessment data, "
            "interview feedback, and background check. Factual only, no fluff."
        )

    assessment_json = {
        "match_degree": assessment.get("match_degree", 0),
        "match_points": assessment.get("main_match_points", []),
        "deductions": assessment.get("main_deductions", []),
        "tech_tags": assessment.get("tech_tags", []),
    }

    user = (
        f"## Assessment\n{assessment_json}\n\n"
        f"## Interview Q&A\n{interview_qa}\n\n"
        f"## Background Check\n{background_check}\n\n"
        f"## Recommendation: {rec_labels.get(recommendation, recommendation)}\n\n"
        f"Please generate the evaluation summary."
    )

    return complete_chat(
        model=model,
        client=client,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": str(user)},
        ],
    )
