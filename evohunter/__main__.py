from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from evohunter.core.evaluator import GEPEvaluator
from evohunter.core.evolution import evolve_weight_config
from evohunter.core.protocol import ValidationError


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "score":
            _run_score(args)
        elif args.command == "evolve":
            _run_evolve(args)
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


def _read_json(path: str) -> Any:
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


def _write_json(path: str, payload: Any) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())
