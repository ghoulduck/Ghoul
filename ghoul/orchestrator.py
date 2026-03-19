"""
ghoul/orchestrator.py — Specialist Orchestrator.

Runs multiple specialist sub-agents against a task + code + execution result,
collects their feedback, and synthesises a unified recommendation that the
main agent loop can consume.

Supports concurrent execution via ``concurrent.futures``.
"""

from __future__ import annotations

import concurrent.futures
from typing import Any

from ghoul.specialist import (
    SPECIALISTS,
    Specialist,
    get_specialist,
    list_specialists,
)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class Orchestrator:
    """Manages a set of specialist sub-agents and synthesises their feedback."""

    def __init__(self, specialist_names: list[str] | None = None):
        """
        Parameters
        ----------
        specialist_names:
            Names of the specialists to use.  Defaults to **all** registered
            specialists if *None*.
        """
        if specialist_names is None:
            specialist_names = list_specialists()
        self.specialists: list[Specialist] = [
            get_specialist(n) for n in specialist_names
        ]

    # ------------------------------------------------------------------
    # Run specialists
    # ------------------------------------------------------------------

    def run_specialists(
        self,
        task: str,
        code: str,
        execution_result: dict,
        *,
        parallel: bool = True,
    ) -> list[dict]:
        """
        Run every configured specialist against the given context.

        Parameters
        ----------
        task:             Task description.
        code:             Python code to review.
        execution_result: Execution result dict.
        parallel:         If *True* (default), run specialists concurrently.

        Returns
        -------
        List of specialist result dicts (one per specialist).
        """
        if parallel:
            return self._run_parallel(task, code, execution_result)
        return self._run_sequential(task, code, execution_result)

    def _run_sequential(
        self, task: str, code: str, execution_result: dict
    ) -> list[dict]:
        results: list[dict] = []
        for specialist in self.specialists:
            try:
                result = specialist.analyse(task, code, execution_result)
                results.append(result)
            except Exception as exc:
                results.append(
                    {
                        "specialist": specialist.name,
                        "findings": [f"Error: {exc}"],
                        "score": 0,
                        "summary": f"Specialist '{specialist.name}' failed.",
                    }
                )
        return results

    def _run_parallel(
        self, task: str, code: str, execution_result: dict
    ) -> list[dict]:
        results: list[dict] = []
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(self.specialists)
        ) as pool:
            futures = {
                pool.submit(s.analyse, task, code, execution_result): s
                for s in self.specialists
            }
            for future in concurrent.futures.as_completed(futures):
                specialist = futures[future]
                try:
                    results.append(future.result())
                except Exception as exc:
                    results.append(
                        {
                            "specialist": specialist.name,
                            "findings": [f"Error: {exc}"],
                            "score": 0,
                            "summary": f"Specialist '{specialist.name}' failed.",
                        }
                    )
        return results

    # ------------------------------------------------------------------
    # Synthesise
    # ------------------------------------------------------------------

    @staticmethod
    def synthesise(specialist_results: list[dict]) -> dict:
        """
        Merge specialist results into a single unified recommendation.

        Returns
        -------
        dict with keys:
            avg_score         — average specialist score
            all_findings      — deduplicated list of all findings
            specialist_scores — dict mapping specialist name → score
            summary           — combined summary string
        """
        if not specialist_results:
            return {
                "avg_score": 0,
                "all_findings": [],
                "specialist_scores": {},
                "summary": "No specialist feedback available.",
            }

        scores: dict[str, int] = {}
        all_findings: list[str] = []
        summaries: list[str] = []

        for res in specialist_results:
            name = res.get("specialist", "unknown")
            scores[name] = res.get("score", 0)
            for finding in res.get("findings", []):
                if finding not in all_findings:
                    all_findings.append(finding)
            if res.get("summary"):
                summaries.append(f"[{name}] {res['summary']}")

        avg_score = round(sum(scores.values()) / len(scores)) if scores else 0

        return {
            "avg_score": avg_score,
            "all_findings": all_findings,
            "specialist_scores": scores,
            "summary": " | ".join(summaries) if summaries else "No summaries.",
        }

    # ------------------------------------------------------------------
    # Convenience: run + synthesise
    # ------------------------------------------------------------------

    def orchestrate(
        self,
        task: str,
        code: str,
        execution_result: dict,
        *,
        parallel: bool = True,
        verbose: bool = False,
    ) -> dict[str, Any]:
        """
        Run all specialists then synthesise.

        Returns
        -------
        dict with:
            specialist_results — list of individual specialist dicts
            synthesis          — the unified synthesis dict
        """
        if verbose:
            names = ", ".join(s.name for s in self.specialists)
            print(f"[Orchestrator] Running specialists: {names}")

        results = self.run_specialists(
            task, code, execution_result, parallel=parallel
        )

        if verbose:
            for r in results:
                print(
                    f"  [{r.get('specialist')}] score={r.get('score', '?')} "
                    f"— {r.get('summary', '')}"
                )

        synthesis = self.synthesise(results)

        if verbose:
            print(
                f"[Orchestrator] Synthesis — avg_score={synthesis['avg_score']}, "
                f"findings={len(synthesis['all_findings'])}"
            )

        return {
            "specialist_results": results,
            "synthesis": synthesis,
        }
