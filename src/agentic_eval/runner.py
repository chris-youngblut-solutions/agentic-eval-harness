"""CLI: run one task, run the eval, or diff the last two runs.

agentic-eval run "What is 17 * 23?"            one task, live backend
agentic-eval eval --record                      full eval, live, record full transcripts
agentic-eval eval --backend replay              full eval from recorded transcripts
agentic-eval eval --backend replay --record     regenerate transcripts keyless (replay + re-record)
agentic-eval report                             diff the two most recent scorecards
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from agentic_eval import scoring
from agentic_eval.agent import LiveBackend, ModelBackend, ReplayBackend, run_task
from agentic_eval.cases import load_cases
from agentic_eval.domain import load_domain

DEFAULT_MODEL = "claude-opus-4-8"
DEFAULT_DOMAIN = "generic"


def _require_key() -> None:
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        sys.exit(
            "live backend needs ANTHROPIC_API_KEY (or ANTHROPIC_AUTH_TOKEN) in the "
            "environment; use --backend replay to score recorded transcripts"
        )


def cmd_run(args: argparse.Namespace) -> None:
    _require_key()
    domain = load_domain(args.domain)
    result = run_task(args.task, LiveBackend(model=args.model), domain)
    print(f"stop_reason: {result.stop_reason}  turns: {result.turns}")
    print(f"tools: {result.tools_called}")
    print(f"answer: {result.answer}")


def cmd_eval(args: argparse.Namespace) -> None:
    domain = load_domain(args.domain)
    cases = load_cases(domain.cases_path)
    run_id = time.strftime("%Y%m%d-%H%M%S") + f"-{domain.name}-{args.backend}"
    if args.backend == "live":
        _require_key()

    scores: list[scoring.CaseScore] = []
    for case in cases:
        transcript_path = domain.transcripts_dir / f"{case.id}.jsonl"
        backend: ModelBackend
        if args.backend == "live":
            backend = LiveBackend(model=args.model)
        else:
            if not transcript_path.exists():
                sys.exit(f"no transcript for {case.id}; run the live eval with --record first")
            backend = ReplayBackend(transcript_path)
        result = run_task(
            case.prompt,
            backend,
            domain,
            max_turns=case.max_turns,
            record_path=transcript_path if args.record else None,
        )
        case_score = scoring.score_case(case, result)
        scores.append(case_score)
        status = "PASS" if case_score.passed else f"{case_score.score:.1f}"
        print(f"  {case.id:<28} {status:>5}  ({result.stop_reason}, {result.turns} turns)")

    card = scoring.Scorecard(run_id=run_id, backend=args.backend, model=args.model, cases=scores)
    path = scoring.save_scorecard(card, domain.history_dir)
    print(f"\n{card.summary()}")
    for rollup in card.by_metric():
        if rollup.metric != "(untagged)":
            print(
                f"  {rollup.metric:<28} {rollup.passed}/{rollup.n} pass  "
                f"mean {rollup.mean_score:.2f}"
            )
    print(f"scorecard: {path}")
    if card.hard_gate_failures:
        sys.exit(f"HARD-GATE FAIL: {', '.join(card.hard_gate_failures)}")
    if args.min_pass is not None and card.passed < args.min_pass:
        sys.exit(f"FAIL: {card.passed} passed < required {args.min_pass}")


def cmd_report(args: argparse.Namespace) -> None:
    domain = load_domain(args.domain)
    history = scoring.load_history(domain.history_dir)
    if len(history) < 2:
        sys.exit(f"need at least two scorecards in {domain.history_dir} to diff")
    print(scoring.diff_report(history[-2], history[-1]))


def main() -> None:
    parser = argparse.ArgumentParser(prog="agentic-eval")
    sub = parser.add_subparsers(required=True)

    p_run = sub.add_parser("run", help="run the agent on one task (live)")
    p_run.add_argument("task")
    p_run.add_argument("--domain", default=DEFAULT_DOMAIN, help="domain pack to load")
    p_run.add_argument("--model", default=DEFAULT_MODEL)
    p_run.set_defaults(func=cmd_run)

    p_eval = sub.add_parser("eval", help="run the golden set and write a scorecard")
    p_eval.add_argument("--domain", default=DEFAULT_DOMAIN, help="domain pack to evaluate")
    p_eval.add_argument("--backend", choices=["live", "replay"], default="live")
    p_eval.add_argument("--model", default=DEFAULT_MODEL)
    p_eval.add_argument(
        "--record",
        action="store_true",
        help="record full transcripts (works with --backend replay to regenerate them keyless)",
    )
    p_eval.add_argument("--min-pass", type=int, default=None, help="exit nonzero below this")
    p_eval.set_defaults(func=cmd_eval)

    p_report = sub.add_parser("report", help="diff the two most recent scorecards")
    p_report.add_argument("--domain", default=DEFAULT_DOMAIN, help="domain pack to report on")
    p_report.set_defaults(func=cmd_report)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
