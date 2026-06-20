from __future__ import annotations

from typing import Any

from evohunter.ai import build_evomap_api_key
from evohunter.core.evaluator import GEPEvaluator
from evohunter.core.evolution import (
    EvoMapEvolver,
    evolve_weight_config_with_summary,
)
from evohunter.data_scraper import scrape_source, scrape_sources
from evohunter.llm_parser import (
    parse_candidate_texts,
    parse_candidate_texts_with_metadata,
    parse_job_text,
    parse_job_text_with_metadata,
)
from evohunter.outreach import draft_outreach
from evohunter.storage import (
    load_evolution_events,
    load_workbench_history,
    load_overview,
    save_candidate_genes,
    save_evolution_event,
    save_feedback_events,
    save_job_gene,
    save_match_results,
    save_weight_config,
)


class ApiError(RuntimeError):
    pass


def handle_api_request(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    if path == "/api/config":
        return {"has_api_key": _has_api_key()}
    if path == "/api/overview":
        return _overview(payload)
    if path == "/api/history":
        return _history(payload)
    if path == "/api/scrape":
        return _scrape(payload)
    if path == "/api/parse-job":
        if payload.get("include_parser_metadata") is True:
            return parse_job_text_with_metadata(_required_string(payload, "text"))
        return {"job_gene": parse_job_text(_required_string(payload, "text"))}
    if path == "/api/parse-candidates":
        if payload.get("include_parser_metadata") is True:
            return parse_candidate_texts_with_metadata(_required_string(payload, "text"))
        return {"candidate_genes": parse_candidate_texts(_required_string(payload, "text"))}
    if path == "/api/score":
        return {"match_results": _score(payload)}
    if path == "/api/evolve":
        return _evolve(payload)
    if path == "/api/draft-outreach":
        return {"outreach_draft": _draft_outreach(payload)}
    # ── Workflow endpoints ─────────────────────────────────────────
    if path == "/api/workflow/execute":
        return _workflow_execute(payload)
    if path == "/api/workflow/list":
        return _workflow_list()
    # ── Recruiter assessment endpoint ──────────────────────────────
    if path == "/api/recruiter/assess":
        return _recruiter_assess(payload)
    # ── RAG endpoints ──────────────────────────────────────────────
    if path == "/api/rag/retrieve":
        return _rag_retrieve(payload)
    if path == "/api/rag/index-company":
        return _rag_index_company(payload)
    # ── MCP endpoints ──────────────────────────────────────────────
    if path == "/api/mcp/tools":
        return _mcp_tools()
    if path == "/api/mcp/execute":
        return _mcp_execute(payload)
    # ── Evaluation endpoint ────────────────────────────────────────
    if path == "/api/evaluation/generate":
        return _evaluation_generate(payload)
    raise ApiError(f"unknown endpoint: {path}")


def _overview(payload: dict[str, Any]) -> dict[str, Any]:
    db_path = _optional_string(payload, "db_path")
    if not db_path:
        return {
            "candidate_count": 0,
            "highest_match_score": 0,
            "current_generation": 0,
            "last_step": "none",
        }
    return load_overview(db_path)


def _history(payload: dict[str, Any]) -> dict[str, Any]:
    db_path = _optional_string(payload, "db_path")
    if not db_path:
        return {
            "score_trend": [],
            "candidate_history": {},
            "generation_comparison": [],
        }
    return load_workbench_history(db_path)


def _scrape(payload: dict[str, Any]) -> dict[str, Any]:
    if "sources" in payload:
        sources = payload["sources"]
        if not isinstance(sources, list):
            raise ApiError("sources must be a list")
        results = scrape_sources(sources)
        return {
            "results": results,
            "text": "\n\n".join(result["text"] for result in results if result["status"] == "success"),
        }
    return {"text": scrape_source(_required_string(payload, "source"))}


def _score(payload: dict[str, Any]) -> list[dict[str, Any]]:
    job_gene = _required_mapping(payload, "job_gene")
    candidate_genes = payload.get("candidate_genes")
    if not isinstance(candidate_genes, list):
        raise ApiError("candidate_genes must be a list")
    weight_config = payload.get("weight_config", {})
    if not isinstance(weight_config, dict):
        raise ApiError("weight_config must be a dict")
    results = GEPEvaluator().rank_candidates(job_gene, candidate_genes, weight_config)
    output = [result.to_dict() for result in results]
    db_path = _optional_string(payload, "db_path")
    if db_path:
        save_job_gene(db_path, job_gene)
        save_candidate_genes(db_path, candidate_genes)
        save_weight_config(db_path, weight_config)
        save_match_results(db_path, output)
    return output


def _evolve(payload: dict[str, Any]) -> dict[str, Any]:
    weight_config = payload.get("weight_config", {})
    feedback_events = payload.get("feedback_events", [])
    use_evolver_cycle = payload.get("use_evolver_cycle", False)
    publish_to_hub = payload.get("publish_to_hub", False)
    fetch_from_hub = payload.get("fetch_from_hub", False)
    sender_id = _optional_string(payload, "sender_id")

    if not isinstance(weight_config, dict):
        raise ApiError("weight_config must be a dict")
    if not isinstance(feedback_events, list):
        raise ApiError("feedback_events must be a list")

    db_path = _optional_string(payload, "db_path")

    if use_evolver_cycle:
        a2a_client = None
        if sender_id:
            try:
                from evohunter.core.evolution.a2a import A2AClient
                a2a_client = A2AClient(sender_id=sender_id)
            except Exception:
                pass  # A2A is optional

        evolver = EvoMapEvolver(
            db_path=db_path or None,
            a2a_client=a2a_client,
            sender_id=sender_id or None,
        )

        match_results = None
        if db_path:
            try:
                stored = load_workbench_history(db_path)
                match_results = stored.get("score_trend", [])
            except Exception:
                pass

        output = evolver.run_cycle(
            weight_config=weight_config,
            feedback_events=feedback_events,
            match_results=match_results,
            publish_to_hub=publish_to_hub,
            fetch_from_hub=fetch_from_hub,
        )
    else:
        output = evolve_weight_config_with_summary(weight_config, feedback_events)

    if db_path:
        save_feedback_events(db_path, feedback_events)
        save_weight_config(db_path, output["weight_config"], step="evolve")
        if use_evolver_cycle and "evolution_event" in output:
            try:
                save_evolution_event(db_path, output["evolution_event"])
            except Exception:
                pass

    return output


def _draft_outreach(payload: dict[str, Any]) -> dict[str, str]:
    return draft_outreach(
        _required_mapping(payload, "job_gene"),
        _required_mapping(payload, "candidate_gene"),
        _required_mapping(payload, "match_result"),
    )


def _required_string(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(f"{field_name} must be a non-empty string")
    return value.strip()


def _required_mapping(payload: dict[str, Any], field_name: str) -> dict[str, Any]:
    value = payload.get(field_name)
    if not isinstance(value, dict):
        raise ApiError(f"{field_name} must be a dict")
    return value


def _optional_string(payload: dict[str, Any], field_name: str) -> str:
    value = payload.get(field_name, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ApiError(f"{field_name} must be a string")
    return value.strip()


def _has_api_key() -> bool:
    try:
        build_evomap_api_key()
    except Exception:
        return False
    return True


# ── Workflow handlers ─────────────────────────────────────────────────


def _workflow_execute(payload: dict[str, Any]) -> dict[str, Any]:
    workflow_id = _optional_string(payload, "workflow_id")
    if not workflow_id:
        workflow_id = "full_headhunting"

    from evohunter.workflow import WorkflowContext
    from evohunter.workflow.prebuilt import (
        create_assessment_only_workflow,
        create_full_headhunting_workflow,
        create_minimal_workflow,
        run_workflow_with_evolution,
    )

    if workflow_id == "minimal_headhunting":
        engine = create_minimal_workflow()
    elif workflow_id == "assessment_only":
        engine = create_assessment_only_workflow()
    else:
        engine = create_full_headhunting_workflow()

    context = WorkflowContext(
        workflow_id=workflow_id,
        input_data=payload.get("inputs", {}),
    )
    # Inject JD gene if provided directly (bypasses JD generation node)
    jd_gene = payload.get("job_gene")
    if jd_gene:
        context.set_node_result("jd_generation", {"job_gene": jd_gene})

    db_path = _optional_string(payload, "db_path")
    weight_config = payload.get("weight_config")

    # Run workflow + evolution bridge
    result = run_workflow_with_evolution(
        engine=engine,
        context=context,
        weight_config=weight_config,
        db_path=db_path or None,
        sender_id=_optional_string(payload, "sender_id") or None,
        publish_to_hub=payload.get("publish_to_hub", False),
        fetch_from_hub=payload.get("fetch_from_hub", False),
    )
    return result


def _workflow_list() -> dict[str, Any]:
    from evohunter.workflow.prebuilt import (
        create_assessment_only_workflow,
        create_full_headhunting_workflow,
        create_minimal_workflow,
    )
    return {
        "workflows": [
            {"id": "full_headhunting", "name": "Full Headhunting Pipeline", "nodes": 4},
            {"id": "minimal_headhunting", "name": "Minimal Pipeline", "nodes": 3},
            {"id": "assessment_only", "name": "Assessment Only", "nodes": 1},
        ]
    }


# ── Recruiter assessment handler ─────────────────────────────────────


def _recruiter_assess(payload: dict[str, Any]) -> dict[str, Any]:
    from evohunter.ai import create_evomap_client
    from evohunter.workflow.nodes.resume_parsing import RecruiterAssessmentNode

    node = RecruiterAssessmentNode(ai_client=create_evomap_client())
    from evohunter.workflow import WorkflowContext

    context = WorkflowContext(
        workflow_id="inline_assessment",
        input_data={
            "resume_text": _required_string(payload, "resume_text"),
            "language": payload.get("language", "zh"),
            "user_notes": payload.get("user_notes", ""),
        },
    )
    # Inject JD result into context for the node to use
    jd_gene = payload.get("job_gene", {})
    if jd_gene:
        context.set_node_result("jd_generation", {"job_gene": jd_gene})
    else:
        context.set_node_result("jd_generation", {
            "job_gene": {
                "job_id": payload.get("job_id", "j_001"),
                "job_title": payload.get("job_title", "unknown"),
                "required_skills": payload.get("required_skills", []),
                "preferred_skills": payload.get("preferred_skills", []),
                "min_years_of_experience": payload.get("min_years_of_experience", 0),
                "salary_range": payload.get("salary_range", "unknown"),
                "location": payload.get("location", "unknown"),
                "seniority_level": payload.get("seniority_level", "unknown"),
            }
        })

    return node.execute(context)


# ── RAG handlers ──────────────────────────────────────────────────────


def _rag_retrieve(payload: dict[str, Any]) -> dict[str, Any]:
    from evohunter.rag import EmbeddingProvider, KnowledgeBaseManager, StructuredKnowledgeStore, VectorStore

    db_path = _required_string(payload, "db_path")
    embedder = EmbeddingProvider()
    vector = VectorStore(dimension=embedder.dimension)
    structured = StructuredKnowledgeStore(db_path)

    kb = KnowledgeBaseManager(vector, structured, embedder)
    result = kb.retrieve_for_jd_generation(
        company_name=_optional_string(payload, "company_name"),
        role_title=_required_string(payload, "role_title"),
    )
    return result.to_dict()


def _rag_index_company(payload: dict[str, Any]) -> dict[str, Any]:
    from evohunter.rag import EmbeddingProvider, KnowledgeBaseManager, StructuredKnowledgeStore, VectorStore

    db_path = _required_string(payload, "db_path")
    embedder = EmbeddingProvider()
    vector = VectorStore(dimension=embedder.dimension)
    structured = StructuredKnowledgeStore(db_path)

    kb = KnowledgeBaseManager(vector, structured, embedder)
    profile = kb.index_company(
        company_name=_required_string(payload, "company_name"),
        industry=_optional_string(payload, "industry"),
        description=_optional_string(payload, "description"),
        culture_tags=payload.get("culture_tags", []),
        values=payload.get("values", []),
        typical_salary_ranges=payload.get("typical_salary_ranges", {}),
        remote_policy=_optional_string(payload, "remote_policy"),
        interview_process=_optional_string(payload, "interview_process"),
    )
    return profile.to_dict()


# ── MCP handlers ──────────────────────────────────────────────────────


def _mcp_tools() -> dict[str, Any]:
    from evohunter.mcp import MCPToolRegistry
    from evohunter.mcp.tools import register_calendar_tools, register_email_tools, register_im_tools

    registry = MCPToolRegistry()
    register_email_tools(registry)
    register_im_tools(registry)
    register_calendar_tools(registry)

    return {"tools": [t.to_dict() for t in registry.list_tools()]}


def _mcp_execute(payload: dict[str, Any]) -> dict[str, Any]:
    from evohunter.mcp import MCPToolRegistry
    from evohunter.mcp.models import MCPToolCall

    registry = MCPToolRegistry()
    result = registry.execute_tool(
        MCPToolCall(
            tool_id=_required_string(payload, "tool_id"),
            parameters=payload.get("parameters", {}),
        )
    )
    return result.to_dict()


# ── Evaluation handler ────────────────────────────────────────────────


def _evaluation_generate(payload: dict[str, Any]) -> dict[str, Any]:
    from evohunter.workflow.nodes.evaluation_report import EvaluationReportNode
    from evohunter.workflow import WorkflowContext

    node = EvaluationReportNode()
    context = WorkflowContext(
        workflow_id="inline_evaluation",
        input_data={
            "interview_qa": payload.get("interview_qa", []),
            "background_check": payload.get("background_check", {}),
            "language": payload.get("language", "zh"),
        },
    )
    context.set_node_result("resume_parsing", payload.get("assessment", {}))
    context.set_node_result("intelligent_outreach", payload.get("outreach_result", {}))
    context.set_node_result("jd_generation", payload.get("jd_result", {}))

    return node.execute(context)
