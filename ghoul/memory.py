"""
ghoul/memory.py — Memory & State Persistence.

Persists the agent's full history: all code generated, all evaluations,
all improvements, and collected training data references.
Uses JSON files stored in the configured data/ directory.
"""

import json
import time
from pathlib import Path
from typing import Any

from ghoul.config import CFG


class Memory:
    """Persists agent state across runs."""

    def __init__(self, session_id: str | None = None):
        self.data_dir: Path = CFG["data_dir"]
        self.session_id = session_id or f"session_{int(time.time())}"
        self._history_file = self.data_dir / f"{self.session_id}_history.json"
        self._metrics_file = self.data_dir / f"{self.session_id}_metrics.json"
        self._state: dict = self._load(self._history_file) or {
            "session_id": self.session_id,
            "created_at": time.time(),
            "iterations": [],
        }
        self._metrics: dict = self._load(self._metrics_file) or {
            "session_id": self.session_id,
            "scores": [],
            "iteration_count": 0,
            "improvement_rate": 0.0,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self, path: Path) -> dict | None:
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
        return None

    def _save(self, path: Path, data: dict) -> None:
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_iteration(
        self,
        code: str,
        execution_result: dict,
        evaluation: dict,
        task: str,
    ) -> None:
        """Record one full agent iteration."""
        record: dict[str, Any] = {
            "timestamp": time.time(),
            "task": task,
            "code": code,
            "execution_result": execution_result,
            "evaluation": evaluation,
        }
        self._state["iterations"].append(record)
        self._save(self._history_file, self._state)

        # Update metrics
        score = evaluation.get("score", 0)
        self._metrics["scores"].append(score)
        self._metrics["iteration_count"] += 1
        scores = self._metrics["scores"]
        if len(scores) >= 2:
            self._metrics["improvement_rate"] = (scores[-1] - scores[0]) / (len(scores) - 1)
        self._save(self._metrics_file, self._metrics)

    def record_improvement(self, module: str, old_code: str, new_code: str) -> None:
        """Record a self-improvement event."""
        record = {
            "timestamp": time.time(),
            "type": "self_improvement",
            "module": module,
            "old_code_length": len(old_code),
            "new_code_length": len(new_code),
        }
        self._state.setdefault("improvements", []).append(record)
        self._save(self._history_file, self._state)

    def record_data_collection(self, source: str, count: int, path: str) -> None:
        """Record a data collection event."""
        record = {
            "timestamp": time.time(),
            "source": source,
            "count": count,
            "path": path,
        }
        self._state.setdefault("data_collections", []).append(record)
        self._save(self._history_file, self._state)

    def record_orchestration(self, orchestration_result: dict) -> None:
        """Record an orchestration event (specialist sub-agent run)."""
        synthesis = orchestration_result.get("synthesis", {})
        specialist_names = [
            r.get("specialist", "unknown")
            for r in orchestration_result.get("specialist_results", [])
        ]
        record = {
            "timestamp": time.time(),
            "specialists": specialist_names,
            "avg_score": synthesis.get("avg_score", 0),
            "finding_count": len(synthesis.get("all_findings", [])),
            "summary": synthesis.get("summary", ""),
        }
        self._state.setdefault("orchestrations", []).append(record)
        self._save(self._history_file, self._state)

    def get_iterations(self) -> list:
        return self._state.get("iterations", [])

    def get_metrics(self) -> dict:
        return self._metrics

    def get_last_code(self) -> str | None:
        iters = self._state.get("iterations", [])
        if iters:
            return iters[-1].get("code")
        return None

    def get_last_score(self) -> float:
        scores = self._metrics.get("scores", [])
        return scores[-1] if scores else 0.0

    def summary(self) -> dict:
        """Return a human-readable summary dict."""
        m = self._metrics
        iters = self._state.get("iterations", [])
        return {
            "session_id": self.session_id,
            "iteration_count": m["iteration_count"],
            "last_score": self.get_last_score(),
            "improvement_rate": m["improvement_rate"],
            "improvements": len(self._state.get("improvements", [])),
            "data_collections": len(self._state.get("data_collections", [])),
            "orchestrations": len(self._state.get("orchestrations", [])),
            "history_file": str(self._history_file),
            "first_task": iters[0]["task"] if iters else None,
        }

    @classmethod
    def list_sessions(cls) -> list[str]:
        """List all session IDs found in the data directory."""
        data_dir = CFG["data_dir"]
        sessions = set()
        for f in data_dir.glob("*_history.json"):
            sid = f.name.replace("_history.json", "")
            sessions.add(sid)
        return sorted(sessions)
