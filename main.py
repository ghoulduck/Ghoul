#!/usr/bin/env python3
"""
main.py — Ghoul CLI entry point.

Subcommands:
  run <task>            — Run the agent on a task.
  improve [module ...]  — Have the agent improve its own code.
  orchestrate [module]  — Orchestrate specialist personas to improve code.
  collect <topic>       — Collect training data on a topic.
  fine-tune <data_path> — Run the fine-tuning pipeline.
  status                — Show agent history and metrics.
"""

import argparse
import json
import sys


def cmd_run(args: argparse.Namespace) -> None:
    from ghoul.agent import run

    task = " ".join(args.task)
    memory = run(task=task, session_id=args.session_id, verbose=not args.quiet)
    summary = memory.summary()
    print("\n[Ghoul] Session complete.")
    print(json.dumps(summary, indent=2, default=str))


def cmd_improve(args: argparse.Namespace) -> None:
    from ghoul.improver import improve_all, improve_module
    from ghoul.memory import Memory

    memory = Memory(session_id=args.session_id)

    if args.modules:
        for module in args.modules:
            improve_module(
                module,
                instructions=args.instructions,
                memory=memory,
                verbose=True,
                use_specialists=args.specialists,
            )
    else:
        improve_all(
            instructions=args.instructions,
            memory=memory,
            verbose=True,
            use_specialists=args.specialists,
        )


def cmd_orchestrate(args: argparse.Namespace) -> None:
    from ghoul.memory import Memory
    from ghoul.orchestrator import orchestrate_module

    memory = Memory(session_id=args.session_id)

    modules = args.modules or [
        "agent", "executor", "evaluator", "data_collector",
        "fine_tuner", "memory", "improver", "config",
    ]

    specialist_ids = args.specialists.split(",") if args.specialists else None

    for module in modules:
        try:
            orchestrate_module(
                module,
                specialist_ids=specialist_ids,
                extra_instructions=args.instructions,
                memory=memory,
                verbose=True,
            )
        except Exception as exc:
            print(f"[Orchestrator] Failed on {module}: {exc}")


def cmd_collect(args: argparse.Namespace) -> None:
    from ghoul.data_collector import collect
    from ghoul.memory import Memory

    memory = Memory(session_id=args.session_id)
    urls = args.urls or []
    out_path = collect(
        topic=args.topic,
        urls=urls,
        github_query=args.github_query,
        synthetic_count=args.synthetic_count,
        memory=memory,
    )
    print(f"\n[Ghoul] Training data saved to: {out_path}")


def cmd_finetune(args: argparse.Namespace) -> None:
    from pathlib import Path

    from ghoul.fine_tuner import run_pipeline

    job_info = run_pipeline(
        data_path=Path(args.data_path),
        target=args.target,
        model=args.model,
    )
    print("\n[Ghoul] Fine-tuning job submitted:")
    print(json.dumps(job_info, indent=2, default=str))


def cmd_status(args: argparse.Namespace) -> None:
    from ghoul.memory import Memory

    sessions = Memory.list_sessions()
    if not sessions:
        print("[Ghoul] No sessions found.")
        return

    if args.session_id:
        sessions = [s for s in sessions if s == args.session_id]

    for sid in sessions:
        m = Memory(session_id=sid)
        print(json.dumps(m.summary(), indent=2, default=str))
        print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ghoul",
        description="Ghoul — a self-improving AI agent powered by Anthropic Claude.",
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Resume or reference a specific session by ID.",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # run
    p_run = sub.add_parser("run", help="Run the agent on a task.")
    p_run.add_argument("task", nargs="+", help="The task/goal for the agent.")
    p_run.add_argument("--quiet", action="store_true", help="Suppress verbose output.")

    # improve
    p_improve = sub.add_parser(
        "improve", help="Have the agent improve its own source code."
    )
    p_improve.add_argument(
        "modules",
        nargs="*",
        help="Module names to improve (e.g. executor evaluator). "
        "Defaults to all modules.",
    )
    p_improve.add_argument(
        "--instructions",
        default=None,
        help="Specific improvement instructions to pass to Claude.",
    )
    p_improve.add_argument(
        "--specialists",
        action="store_true",
        default=False,
        help="Also run specialist personas for additional insights.",
    )

    # orchestrate
    p_orch = sub.add_parser(
        "orchestrate",
        help="Orchestrate specialist personas to improve Ghoul modules.",
    )
    p_orch.add_argument(
        "modules",
        nargs="*",
        help="Module names to orchestrate (default: all modules).",
    )
    p_orch.add_argument(
        "--specialists",
        default=None,
        help="Comma-separated specialist IDs to use (default: all).",
    )
    p_orch.add_argument(
        "--instructions",
        default=None,
        help="Extra instructions for every specialist.",
    )

    # collect
    p_collect = sub.add_parser("collect", help="Collect training data on a topic.")
    p_collect.add_argument("topic", help="Topic to collect data on.")
    p_collect.add_argument(
        "--urls", nargs="*", default=[], help="URLs to scrape."
    )
    p_collect.add_argument(
        "--github-query", default=None, help="GitHub search query override."
    )
    p_collect.add_argument(
        "--synthetic-count",
        type=int,
        default=10,
        help="Number of synthetic examples to generate (default: 10).",
    )

    # fine-tune
    p_ft = sub.add_parser("fine-tune", help="Run the fine-tuning pipeline.")
    p_ft.add_argument("data_path", help="Path to the JSONL training data file.")
    p_ft.add_argument(
        "--target",
        choices=["anthropic", "huggingface"],
        default="anthropic",
        help="Fine-tuning target (default: anthropic).",
    )
    p_ft.add_argument("--model", default=None, help="Base model name override.")

    # status
    sub.add_parser("status", help="Show agent history and metrics.")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "run": cmd_run,
        "improve": cmd_improve,
        "orchestrate": cmd_orchestrate,
        "collect": cmd_collect,
        "fine-tune": cmd_finetune,
        "status": cmd_status,
    }

    fn = dispatch.get(args.command)
    if fn is None:
        parser.print_help()
        sys.exit(1)

    fn(args)


if __name__ == "__main__":
    main()
