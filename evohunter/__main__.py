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
from evohunter.data_scraper import ScrapeError, scrape_source
from evohunter.llm_parser import LLMParserError, parse_candidate_texts, parse_job_text
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
    except (AIConfigurationError, LLMParserError, ScrapeError) as exc:
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

    evolve_parser = subparsers.add_parser("evolve")
    evolve_parser.add_argument("--weights", required=True)
    evolve_parser.add_argument("--feedback", required=True)
    evolve_parser.add_argument("--output", required=True)

    scrape_parser = subparsers.add_parser("scrape")
    scrape_parser.add_argument("--source", required=True)
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

    return parser


def _run_score(args: argparse.Namespace) -> None:
    job_gene = _read_json(args.job)
    candidates = _read_json(args.candidates)
    weight_config = _read_json(args.weights)
    candidate_list = candidates if isinstance(candidates, list) else [candidates]
    results = GEPEvaluator().rank_candidates(job_gene, candidate_list, weight_config)
    output: dict[str, Any] | list[dict[str, Any]]
    if isinstance(candidates, list):
        output = [result.to_dict() for result in results]
    else:
        output = results[0].to_dict()
    _write_json(args.output, output)


def _run_evolve(args: argparse.Namespace) -> None:
    weight_config = _read_json(args.weights)
    feedback_events = _read_json(args.feedback)
    evolved = evolve_weight_config(weight_config, feedback_events)
    _write_json(args.output, evolved.to_dict())


def _run_scrape(args: argparse.Namespace) -> None:
    _write_text(args.output, scrape_source(args.source))


def _run_parse_job(args: argparse.Namespace) -> None:
    _write_json(args.output, parse_job_text(_read_text(args.input)))


def _run_parse_candidates(args: argparse.Namespace) -> None:
    _write_json(args.output, parse_candidate_texts(_read_text(args.input)))


def _run_serve(args: argparse.Namespace) -> None:
    run_server(host=args.host, port=args.port)


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
