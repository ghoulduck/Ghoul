"""
ghoul/agent.py — Agent Core.

The main agentic loop:
  1. Receive a task.
  2. Generate Python code with Claude.
  3. Execute the code.
  4. Evaluate the output with Claude.
  5. Feed the evaluation back to Claude and request an improvement.
  6. Repeat indefinitely until the evaluator says the task is complete
     or the user interrupts.

No iteration limits. Maintains full conversation history.

Optionally integrates with the orchestrator to run specialist personas
for additional improvement at configurable intervals.
"""

import anthropic

from ghoul import strip_markdown_fences
from ghoul.config import CFG
from ghoul.evaluator import evaluate
from ghoul.executor import execute_code
from ghoul.memory import Memory


_SYSTEM = """\
You are Ghoul, an autonomous self-improving AI coding agent.
Your job is to write Python code that solves the given task.
Return ONLY the raw Python code — no markdown fences, no explanations.
The code must be complete and executable as-is.
"""


def _extract_code(text: str) -> str:
    """Strip optional markdown code fences from Claude's response."""
    return strip_markdown_fences(text)


def run(
    task: str,
    session_id: str | None = None,
    verbose: bool = True,
    use_orchestrator: bool = False,
    orchestrate_interval: int = 3,
) -> Memory:
    """
    Run the agent loop on *task*.

    Parameters
    ----------
    task:                  Natural language description of what to accomplish.
    session_id:            Optional ID to resume a previous session.
    verbose:               Print progress to stdout.
    use_orchestrator:      If True, run specialist personas via the orchestrator
                           every *orchestrate_interval* iterations to refine code.
    orchestrate_interval:  How often (in iterations) to invoke the orchestrator.

    Returns
    -------
    The :class:`~ghoul.memory.Memory` object with the full history.
    """
    memory = Memory(session_id=session_id)
    client = anthropic.Anthropic(api_key=CFG["anthropic_api_key"])

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

        # --- Orchestrator pass (optional) ---
        if use_orchestrator and iteration % orchestrate_interval == 0:
            try:
                from ghoul.orchestrator import orchestrate

                if verbose:
                    print(f"[Ghoul] Running orchestrator pass…")
                code = orchestrate(
                    code=code,
                    task=task,
                    verbose=verbose,
                )
                if verbose:
                    print(f"[Ghoul] Orchestrator refined code ({len(code)} chars)")
            except Exception as exc:
                if verbose:
                    print(f"[Ghoul] Orchestrator pass failed: {exc}")

        # --- Persist ---
        memory.record_iteration(code, result, evaluation, task)

        # --- Check completion ---
        if evaluation.get("complete"):
            if verbose:
                print("\n[Ghoul] Task complete! 🎉")
            break

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
        feedback_parts.append(
            "\nPlease rewrite the code addressing all the issues above. "
            "Return ONLY the raw Python code."
        )
        if result["stderr"]:
            feedback_parts.append(f"\nThe execution produced this error:\n{result['stderr']}")

        messages.append({"role": "user", "content": "\n".join(feedback_parts)})

    return memory
