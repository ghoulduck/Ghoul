"""Tests for the Memory.record_orchestration method."""

import os

from ghoul.memory import Memory


class TestMemoryOrchestration:
    def test_record_orchestration(self, tmp_path, monkeypatch):
        # Point data dir to tmp
        monkeypatch.setitem(
            __import__("ghoul.config", fromlist=["CFG"]).CFG,
            "data_dir",
            tmp_path,
        )

        m = Memory(session_id="test_orch")
        assert m.summary()["orchestrations"] == 0

        mock_result = {
            "specialist_results": [
                {"specialist": "debugger", "findings": ["Bug"], "score": 80, "summary": "OK"},
            ],
            "synthesis": {
                "avg_score": 80,
                "all_findings": ["Bug"],
                "specialist_scores": {"debugger": 80},
                "summary": "One finding",
            },
        }
        m.record_orchestration(mock_result)
        assert m.summary()["orchestrations"] == 1

        # Second recording
        m.record_orchestration(mock_result)
        assert m.summary()["orchestrations"] == 2
