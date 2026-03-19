"""
ghoul/agent.py — Agent Core.

The main agentic loop:
  1. Receive a task.
  2. Generate Python code with Claude.
  3. Execute the code.
  4. Evaluate the output with Claude.
  5. (Optional) Run specialist sub-agents via the orchestrator for deeper
     feedback (debugging, optimisation, testing, architecture, security).
  6. Feed the evaluation (and specialist insights) back to Claude and request
     an improvement.
  7. Repeat indefinitely until the evaluator says the task is complete
     or the user interrupts.

No iteration limits. Maintains full conversation history.
"""

from __future__ import annotations

import anthropic

from ghoul.config import CFG
from ghoul.evaluator import evaluate
from ghoul.executor import execute_code
from ghoul.memory import Memory
from ghoul.orchestrator import Orchestrator


_SYSTEM = """\
You are Ghoul, an autonomous self-improving AI coding agent.
Your job is to write Python code that solves the given task.
Return ONLY the raw Python code — no markdown fences, no explanations.
The code must be complete and executable as-is.
"""


def _extract_code(text: str) -> str:
    """Strip optional markdown code fences from Claude's response."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop first line (```python or ```) and last line (```)
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        return "\n".join(inner)
    return text


def run(
    task: str,
    session_id: str | None = None,
    verbose: bool = True,
    orchestrate: bool = False,
    specialists: list[str] | None = None,
) -> Memory:
    """
    Run the agent loop on *task*.

    Parameters
    ----------
    task:        Natural language description of what to accomplish.
    session_id:  Optional ID to resume a previous session.
    verbose:     Print progress to stdout.
    orchestrate: If *True*, run specialist sub-agents after each evaluation
                 to gather deeper feedback before the next iteration.
    specialists: Optional list of specialist names to use when *orchestrate*
                 is True.  Defaults to all registered specialists.

    Returns
    -------
    The :class:`~ghoul.memory.Memory` object with the full history.
    """
    memory = Memory(session_id=session_id)
    client = anthropic.Anthropic(api_key=CFG["anthropic_api_key"])

    # Set up the orchestrator if requested
    orch: Orchestrator | None = None
    if orchestrate:
        orch = Orchestrator(specialist_names=specialists)
        if verbose:
            names = ", ".join(s.name for s in orch.specialists)
            print(f"[Ghoul] Orchestration enabled — specialists: {names}")

    # Conversation history kept in the Claude messages format
    messages: list[dict] = []

    # Seed with the task
    messages.append(
        {
            "role": "user",
            "content": (
                f"Task: {task}\n\n"
                "Write Python code to solve this task. "
                "Return ONLY the raw Python code."
            ),
        }
    )

    iteration = 0
    while True:
        iteration += 1
        if verbose:
            print(f"\n{'='*60}")
            print(f"[Ghoul] Iteration {iteration}")
            print(f"{'='*60}")

        # --- Generate code ---
        response = client.messages.create(
            model=CFG["model"],
            max_tokens=4096,
            system=_SYSTEM,
            messages=messages,
        )
        code_raw = response.content[0].text
        code = _extract_code(code_raw)

        if verbose:
            print(f"[Ghoul] Generated code ({len(code)} chars):\n{code}\n")

        # Add assistant turn to history
        messages.append({"role": "assistant", "content": code_raw})

        # --- Execute ---
        result = execute_code(code)
        if verbose:
            print(f"[Ghoul] Execution — rc={result['returncode']}, "
                  f"time={result['duration']}s")
            if result["stdout"]:
                print(f"  stdout: {result['stdout'][:500]}")
            if result["stderr"]:
                print(f"  stderr: {result['stderr'][:500]}")

        # --- Evaluate ---
        evaluation = evaluate(task, code, result)
        if verbose:
            print(f"[Ghoul] Evaluation — score={evaluation['score']}/100, "
                  f"complete={evaluation['complete']}")
            print(f"  Summary: {evaluation['summary']}")
            if evaluation.get("improvements"):
                print("  Improvements needed:")
                for imp in evaluation["improvements"]:
                    print(f"    - {imp}")

        # --- Persist ---
        memory.record_iteration(code, result, evaluation, task)

        # --- Check completion ---
        if evaluation.get("complete"):
            if verbose:
                print("\n[Ghoul] Task complete! 🎉")
            break

        # --- Optional: Run specialist orchestrator ---
        orchestration_result: dict | None = None
        if orch is not None:
            if verbose:
                print("\n[Ghoul] Running specialist sub-agents…")
            orchestration_result = orch.orchestrate(
                task, code, result, verbose=verbose
            )
            memory.record_orchestration(orchestration_result)

        # --- Build next user message with evaluation feedback ---
        feedback_parts = [
            "The previous code did not fully solve the task.",
            f"Evaluation score: {evaluation['score']}/100.",
            f"Summary: {evaluation['summary']}",
        ]
        if evaluation.get("improvements"):
            feedback_parts.append("Specific improvements needed:")
            for imp in evaluation["improvements"]:
                feedback_parts.append(f"  - {imp}")

        # Append specialist insights when available
        if orchestration_result is not None:
            synthesis = orchestration_result.get("synthesis", {})
            findings = synthesis.get("all_findings", [])
            if findings:
                feedback_parts.append(
                    f"\nSpecialist sub-agents (avg score "
                    f"{synthesis.get('avg_score', '?')}/100) found:"
                )
                for finding in findings:
                    feedback_parts.append(f"  • {finding}")

        feedback_parts.append(
            "\nPlease rewrite the code addressing all the issues above. "
            "Return ONLY the raw Python code."
        )
        if result["stderr"]:
            feedback_parts.append(f"\nThe execution produced this error:\n{result['stderr']}")

        messages.append({"role": "user", "content": "\n".join(feedback_parts)})

    return memory
