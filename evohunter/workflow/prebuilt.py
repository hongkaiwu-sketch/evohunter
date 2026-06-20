from __future__ import annotations

from typing import Any

from evohunter.ai import DEFAULT_MODEL
from evohunter.core.evaluator import GEPEvaluator
from evohunter.mcp.tool_registry import MCPToolRegistry
from evohunter.rag.kb_manager import KnowledgeBaseManager
from evohunter.workflow.engine import WorkflowEngine
from evohunter.workflow.evolution_bridge import EvolutionBridge
from evohunter.workflow.models import WorkflowDefinition, WorkflowNode
from evohunter.workflow.nodes import (
    EvaluationReportNode,
    IntelligentOutreachNode,
    JDGenerationNode,
    RecruiterAssessmentNode,
)


def create_full_headhunting_workflow(
    ai_client: Any | None = None,
    mcp_registry: MCPToolRegistry | None = None,
    kb_manager: KnowledgeBaseManager | None = None,
    model: str = DEFAULT_MODEL,
) -> WorkflowEngine:
    """Factory: creates a complete 4-node headhunting workflow.

    DAG: jd_generation → resume_parsing → intelligent_outreach → evaluation_report

    Each node passes its results downstream through the WorkflowContext.
    The right-brain evolver can read node results + FeedbackEvents to drive evolution.
    """
    definition = WorkflowDefinition(
        workflow_id="full_headhunting",
        name="Full Headhunting Pipeline",
        version="1.0.0",
        nodes={
            "jd_generation": WorkflowNode(
                node_id="jd_generation",
                node_type="process",
                deps=[],
                config={"model": model},
            ),
            "resume_parsing": WorkflowNode(
                node_id="resume_parsing",
                node_type="process",
                deps=["jd_generation"],
                config={"model": model},
            ),
            "intelligent_outreach": WorkflowNode(
                node_id="intelligent_outreach",
                node_type="process",
                deps=["resume_parsing"],
                config={"model": model},
            ),
            "evaluation_report": WorkflowNode(
                node_id="evaluation_report",
                node_type="process",
                deps=["intelligent_outreach"],
                config={"model": model},
            ),
        },
        edges=[
            ("jd_generation", "resume_parsing"),
            ("resume_parsing", "intelligent_outreach"),
            ("intelligent_outreach", "evaluation_report"),
        ],
        entry_points=["jd_generation"],
    )

    engine = WorkflowEngine(definition)
    engine.register_node(JDGenerationNode(ai_client, kb_manager, model))
    engine.register_node(RecruiterAssessmentNode(ai_client, model))
    engine.register_node(IntelligentOutreachNode(mcp_registry, ai_client, model))
    engine.register_node(EvaluationReportNode(ai_client, model))
    return engine


def create_minimal_workflow(
    ai_client: Any | None = None,
    model: str = DEFAULT_MODEL,
) -> WorkflowEngine:
    """Minimal workflow: JD → resume assessment → report.

    No MCP or RAG required. Useful for quick evaluation.
    """
    definition = WorkflowDefinition(
        workflow_id="minimal_headhunting",
        name="Minimal Headhunting Pipeline",
        version="1.0.0",
        nodes={
            "jd_generation": WorkflowNode(
                node_id="jd_generation",
                node_type="process",
                deps=[],
                config={"model": model},
            ),
            "resume_parsing": WorkflowNode(
                node_id="resume_parsing",
                node_type="process",
                deps=["jd_generation"],
                config={"model": model},
            ),
            "evaluation_report": WorkflowNode(
                node_id="evaluation_report",
                node_type="process",
                deps=["resume_parsing"],
                config={"model": model},
            ),
        },
        edges=[
            ("jd_generation", "resume_parsing"),
            ("resume_parsing", "evaluation_report"),
        ],
        entry_points=["jd_generation"],
    )

    engine = WorkflowEngine(definition)
    engine.register_node(JDGenerationNode(ai_client, None, model))
    engine.register_node(RecruiterAssessmentNode(ai_client, model))
    engine.register_node(EvaluationReportNode(ai_client, model))
    return engine


def create_assessment_only_workflow(
    ai_client: Any | None = None,
    evaluator: GEPEvaluator | None = None,
    model: str = DEFAULT_MODEL,
) -> WorkflowEngine:
    """Assessment-only workflow: JD + resume → recruiter assessment.

    No outreach, no report. Just the core match + recommend logic.
    """
    definition = WorkflowDefinition(
        workflow_id="assessment_only",
        name="Assessment Only",
        version="1.0.0",
        nodes={
            "resume_parsing": WorkflowNode(
                node_id="resume_parsing",
                node_type="process",
                deps=[],
                config={"model": model},
            ),
        },
        edges=[],
        entry_points=["resume_parsing"],
    )

    engine = WorkflowEngine(definition)
    engine.register_node(RecruiterAssessmentNode(ai_client, model))
    return engine


# ── Convenience: workflow + evolution in one call ──────────────────────


def run_workflow_with_evolution(
    engine: WorkflowEngine,
    context: WorkflowContext,
    weight_config: dict[str, Any] | None = None,
    db_path: str | None = None,
    sender_id: str | None = None,
    publish_to_hub: bool = False,
    fetch_from_hub: bool = False,
) -> dict[str, Any]:
    """Execute workflow, then automatically run right-brain evolution.

    This is the integration point between left brain (workflow execution)
    and right brain (EvoMapEvolver evolution cycle).

    Process:
    1. Execute all workflow nodes via the engine
    2. EvolutionBridge scans node outputs for feedback signals
    3. If enough signal exists, runs EvoMapEvolver.run_cycle()
    4. Returns workflow result + evolution result together

    Returns:
        {
            "workflow": WorkflowResult.to_dict(),
            "evolution": {
                "should_evolve": bool,
                "reason": str,
                ... evolution results
            }
        }
    """
    # Step 1: Run left-brain workflow
    workflow_result = engine.execute(context)
    workflow_dict = workflow_result.to_dict()

    # Step 2: Bridge to right-brain evolution
    bridge = EvolutionBridge(
        db_path=db_path,
        sender_id=sender_id,
        publish_to_hub=publish_to_hub,
        fetch_from_hub=fetch_from_hub,
    )

    evolution_result = bridge.after_workflow(
        workflow_result=workflow_dict,
        weight_config=weight_config,
    )

    # Step 3: Persist workflow execution to storage
    if db_path:
        try:
            from evohunter.storage import save_workflow_execution
            save_workflow_execution(db_path, workflow_dict)
        except Exception:
            pass

    return {
        "workflow": workflow_dict,
        "evolution": evolution_result,
    }

