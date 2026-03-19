"""
ghoul/evaluator.py — Self-Evaluator.

Sends the generated code, execution output, errors, and the original task
to Claude and asks it to score / evaluate the result.

Returns a structured evaluation:
    score           (int 0-100)
    complete        (bool)
    summary         (str)
    improvements    (list[str])
"""

import json

import anthropic

from ghoul.config import CFG


_EVAL_SYSTEM = """\
You are a strict code quality evaluator. You will be given:
1. A task description.
2. The Python code that was generated to solve the task.
3. The execution output (stdout, stderr, return code).

Your job is to evaluate how well the code solves the task and return a JSON
object with EXACTLY these fields:
{
  "score": <integer 0-100>,
  "complete": <true|false>,
  "summary": "<one-sentence assessment>",
  "improvements": ["<suggestion 1>", "<suggestion 2>", ...]
}

Return ONLY valid JSON — no markdown fences, no extra text.
"""


def evaluate(task: str, code: str, execution_result: dict) -> dict:
    """
    Ask Claude to evaluate whether *code* solved *task*.

    Parameters
    ----------
    task:             The original task/goal string.
    code:             The Python code that was executed.
    execution_result: Dict with keys stdout, stderr, returncode, duration.

    Returns
    -------
    dict with keys: score, complete, summary, improvements
    """
    client = anthropic.Anthropic(api_key=CFG["anthropic_api_key"])

    user_msg = f"""Task:
{task}

Generated code:
```python
{code}
```

Execution result:
- Return code: {execution_result.get('returncode')}
- Duration: {execution_result.get('duration')}s
- stdout:
{execution_result.get('stdout', '(empty)')}
- stderr:
{execution_result.get('stderr', '(empty)')}

Evaluate and return the JSON object as instructed."""

    message = client.messages.create(
        model=CFG["model"],
        max_tokens=1024,
        system=_EVAL_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = message.content[0].text.strip()

    # Strip accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        evaluation = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback if Claude returns malformed JSON
        evaluation = {
            "score": 0,
            "complete": False,
            "summary": "Evaluator could not parse Claude's response.",
            "improvements": [raw],
        }

    return evaluation
