from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from evohunter.ai import AIConfigurationError
from evohunter.core.evaluator import GEPEvaluator
from evohunter.core.evolution import evolve_weight_config
from evohunter.core.protocol import ValidationError
from evohunter.data_scraper import ScrapeError, scrape_source, scrape_sources
from evohunter.llm_parser import LLMParserError, parse_candidate_texts, parse_job_text
from evohunter.outreach import OutreachDraftError, draft_outreach
from evohunter.storage import (
    save_candidate_genes,
    save_feedback_events,
    save_job_gene,
    save_match_results,
    save_weight_config,
)
from evohunter.web import run_server


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "score":
            _run_score(args)
        elif args.command == "evolve":
            _run_evolve(args)
        elif args.command == "scrape":
            _run_scrape(args)
        elif args.command == "parse-job":
            _run_parse_job(args)
        elif args.command == "parse-candidates":
            _run_parse_candidates(args)
        elif args.command == "serve":
            _run_serve(args)
        elif args.command == "draft-outreach":
            _run_draft_outreach(args)
        elif args.command == "workflow":
            _run_workflow(args)
        elif args.command == "recruiter-assess":
            _run_recruiter_assess(args)
        elif args.command == "rag-index":
            _run_rag_index(args)
        elif args.command == "evaluate":
            _run_evaluate(args)
        else:
            parser.print_help(sys.stderr)
            return 1
    except FileNotFoundError as exc:
        print(f"File not found: {exc.filename}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON: {exc.msg}", file=sys.stderr)
        return 1
    except ValidationError as exc:
        print(f"Validation error: {exc}", file=sys.stderr)
        return 1
    except (AIConfigurationError, LLMParserError, OutreachDraftError, ScrapeError) as exc:
        print(f"Runtime error: {exc}", file=sys.stderr)
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evohunter")
    subparsers = parser.add_subparsers(dest="command", required=True)

    score_parser = subparsers.add_parser("score")
    score_parser.add_argument("--job", required=True)
    score_parser.add_argument("--candidates", required=True)
    score_parser.add_argument("--weights", required=True)
    score_parser.add_argument("--output", required=True)
    score_parser.add_argument("--db-path")

    evolve_parser = subparsers.add_parser("evolve")
    evolve_parser.add_argument("--weights", required=True)
    evolve_parser.add_argument("--feedback", required=True)
    evolve_parser.add_argument("--output", required=True)
    evolve_parser.add_argument("--db-path")
    evolve_parser.add_argument("--use-evolver-cycle", action="store_true")
    evolve_parser.add_argument("--publish", action="store_true")
    evolve_parser.add_argument("--fetch", action="store_true")
    evolve_parser.add_argument("--sender-id")

    scrape_parser = subparsers.add_parser("scrape")
    scrape_parser.add_argument("--source", action="append", required=True)
    scrape_parser.add_argument("--output", required=True)

    parse_job_parser = subparsers.add_parser("parse-job")
    parse_job_parser.add_argument("--input", required=True)
    parse_job_parser.add_argument("--output", required=True)

    parse_candidates_parser = subparsers.add_parser("parse-candidates")
    parse_candidates_parser.add_argument("--input", required=True)
    parse_candidates_parser.add_argument("--output", required=True)

    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)

    draft_parser = subparsers.add_parser("draft-outreach")
    draft_parser.add_argument("--job", required=True)
    draft_parser.add_argument("--candidate", required=True)
    draft_parser.add_argument("--match", required=True)
    draft_parser.add_argument("--output", required=True)

    workflow_parser = subparsers.add_parser("workflow")
    workflow_parser.add_argument("--id", default="full_headhunting")
    workflow_parser.add_argument("--inputs", required=True)
    workflow_parser.add_argument("--output", required=True)
    workflow_parser.add_argument("--db-path")

    recruiter_parser = subparsers.add_parser("recruiter-assess")
    recruiter_parser.add_argument("--job-gene", required=True)
    recruiter_parser.add_argument("--resume", required=True)
    recruiter_parser.add_argument("--language", default="zh")
    recruiter_parser.add_argument("--output", required=True)

    rag_index_parser = subparsers.add_parser("rag-index")
    rag_index_parser.add_argument("--company-name", required=True)
    rag_index_parser.add_argument("--industry", default="tech")
    rag_index_parser.add_argument("--description", default="")
    rag_index_parser.add_argument("--db-path", default=".evohunter/rag.db")
    rag_index_parser.add_argument("--output", required=True)

    evaluate_parser = subparsers.add_parser("evaluate")
    evaluate_parser.add_argument("--assessment", required=True)
    evaluate_parser.add_argument("--interview-qa", default="[]")
    evaluate_parser.add_argument("--background-check", default="{}")
    evaluate_parser.add_argument("--output", required=True)

    return parser


def _run_score(args: argparse.Namespace) -> None:
    job_gene = _read_json(args.job)
    candidates = _read_json(args.candidates)
    weight_config = _read_json(args.weights)
    candidate_list = candidates if isinstance(candidates, list) else [candidates]
    results = GEPEvaluator().rank_candidates(job_gene, candidate_list, weight_config)
    result_payloads = [result.to_dict() for result in results]
    output: dict[str, Any] | list[dict[str, Any]]
    if isinstance(candidates, list):
        output = result_payloads
    else:
        output = result_payloads[0]
    _write_json(args.output, output)
    if args.db_path:
        save_job_gene(args.db_path, job_gene)
        save_candidate_genes(args.db_path, candidate_list)
        save_weight_config(args.db_path, weight_config)
        save_match_results(args.db_path, result_payloads)


def _run_evolve(args: argparse.Namespace) -> None:
    weight_config = _read_json(args.weights)
    feedback_events = _read_json(args.feedback)
    evolution_result = None

    if args.use_evolver_cycle:
        from evohunter.core.evolution.a2a import A2AClient
        from evohunter.core.evolution.evolver import EvoMapEvolver

        a2a_client = None
        if args.sender_id:
            try:
                a2a_client = A2AClient(sender_id=args.sender_id)
            except Exception:
                pass

        evolver = EvoMapEvolver(
            db_path=args.db_path,
            a2a_client=a2a_client,
            sender_id=args.sender_id,
        )
        evolution_result = evolver.run_cycle(
            weight_config=weight_config,
            feedback_events=feedback_events,
            publish_to_hub=args.publish,
            fetch_from_hub=args.fetch,
        )
        evolved = evolution_result["weight_config"]
    else:
        from evohunter.core.evolution import evolve_weight_config as _evolve_func
        evolved = _evolve_func(weight_config, feedback_events).to_dict()

    _write_json(args.output, evolved)
    if args.db_path:
        save_feedback_events(args.db_path, feedback_events)
        save_weight_config(args.db_path, evolved, step="evolve")
        if evolution_result is not None and "evolution_event" in evolution_result:
            try:
                from evohunter.storage import save_evolution_event
                save_evolution_event(args.db_path, evolution_result["evolution_event"])
            except Exception:
                pass


def _run_scrape(args: argparse.Namespace) -> None:
    if len(args.source) == 1:
        _write_text(args.output, scrape_source(args.source[0]))
        return
    _write_json(args.output, scrape_sources(args.source))


def _run_parse_job(args: argparse.Namespace) -> None:
    _write_json(args.output, parse_job_text(_read_text(args.input)))


def _run_parse_candidates(args: argparse.Namespace) -> None:
    _write_json(args.output, parse_candidate_texts(_read_text(args.input)))


def _run_serve(args: argparse.Namespace) -> None:
    run_server(host=args.host, port=args.port)


def _run_draft_outreach(args: argparse.Namespace) -> None:
    _write_json(
        args.output,
        draft_outreach(
            _read_json(args.job),
            _read_json(args.candidate),
            _read_json(args.match),
        ),
    )


def _run_workflow(args: argparse.Namespace) -> None:
    from evohunter.workflow import WorkflowContext
    from evohunter.workflow.prebuilt import (
        create_assessment_only_workflow,
        create_full_headhunting_workflow,
        create_minimal_workflow,
        run_workflow_with_evolution,
    )

    inputs = _read_json(args.inputs)
    if args.id == "minimal_headhunting":
        engine = create_minimal_workflow()
    elif args.id == "assessment_only":
        engine = create_assessment_only_workflow()
    else:
        engine = create_full_headhunting_workflow()

    context = WorkflowContext(workflow_id=args.id, input_data=inputs)
    result = run_workflow_with_evolution(
        engine=engine,
        context=context,
        db_path=args.db_path or None,
    )
    _write_json(args.output, result)


def _run_recruiter_assess(args: argparse.Namespace) -> None:
    from evohunter.workflow.nodes.resume_parsing import RecruiterAssessmentNode
    from evohunter.workflow import WorkflowContext

    job_gene = _read_json(args.job_gene)
    resume_text = _read_text(args.resume)

    node = RecruiterAssessmentNode()
    context = WorkflowContext(
        workflow_id="cli_assessment",
        input_data={
            "resume_text": resume_text,
            "language": args.language,
        },
    )
    context.set_node_result("jd_generation", {"job_gene": job_gene})
    result = node.execute(context)
    _write_json(args.output, result)


def _run_rag_index(args: argparse.Namespace) -> None:
    from evohunter.rag import EmbeddingProvider, KnowledgeBaseManager, StructuredKnowledgeStore, VectorStore

    embedder = EmbeddingProvider()
    vector = VectorStore(dimension=embedder.dimension)
    structured = StructuredKnowledgeStore(args.db_path)
    kb = KnowledgeBaseManager(vector, structured, embedder)

    profile = kb.index_company(
        company_name=args.company_name,
        industry=args.industry,
        description=args.description,
    )
    _write_json(args.output, profile.to_dict())


def _run_evaluate(args: argparse.Namespace) -> None:
    from evohunter.workflow.nodes.evaluation_report import EvaluationReportNode
    from evohunter.workflow import WorkflowContext

    assessment = _read_json(args.assessment)
    interview_qa = _read_json(args.interview_qa)
    background_check = _read_json(args.background_check)

    node = EvaluationReportNode()
    context = WorkflowContext(
        workflow_id="cli_evaluation",
        input_data={
            "interview_qa": interview_qa if isinstance(interview_qa, list) else [],
            "background_check": background_check if isinstance(background_check, dict) else {},
        },
    )
    context.set_node_result("resume_parsing", assessment)
    context.set_node_result("intelligent_outreach", {})
    context.set_node_result("jd_generation", {})
    result = node.execute(context)
    _write_json(args.output, result)


def _read_json(path: str) -> Any:
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def _read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _write_json(path: str, payload: Any) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")


def _write_text(path: str, payload: str) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(f"{payload}\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
