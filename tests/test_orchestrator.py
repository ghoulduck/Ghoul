"""Tests for ghoul.orchestrator — Specialist orchestrator."""

from ghoul.orchestrator import Orchestrator


class TestOrchestratorInit:
    def test_default_all_specialists(self):
        o = Orchestrator()
        names = [s.name for s in o.specialists]
        assert "debugger" in names
        assert "optimizer" in names
        assert len(names) >= 5

    def test_selective_specialists(self):
        o = Orchestrator(specialist_names=["debugger", "tester"])
        names = [s.name for s in o.specialists]
        assert names == ["debugger", "tester"]


class TestSynthesise:
    def test_empty_results(self):
        synth = Orchestrator.synthesise([])
        assert synth["avg_score"] == 0
        assert synth["all_findings"] == []

    def test_single_result(self):
        results = [
            {
                "specialist": "debugger",
                "findings": ["Bug A"],
                "score": 80,
                "summary": "Found a bug",
            }
        ]
        synth = Orchestrator.synthesise(results)
        assert synth["avg_score"] == 80
        assert synth["all_findings"] == ["Bug A"]
        assert synth["specialist_scores"] == {"debugger": 80}

    def test_multiple_results_deduplicates_findings(self):
        results = [
            {
                "specialist": "debugger",
                "findings": ["Bug A", "Bug B"],
                "score": 70,
                "summary": "Bugs found",
            },
            {
                "specialist": "optimizer",
                "findings": ["Bug A", "Perf issue"],
                "score": 90,
                "summary": "Perf issue",
            },
        ]
        synth = Orchestrator.synthesise(results)
        assert synth["avg_score"] == 80
        # "Bug A" appears in both but should only be listed once
        assert synth["all_findings"].count("Bug A") == 1
        assert "Bug B" in synth["all_findings"]
        assert "Perf issue" in synth["all_findings"]

    def test_avg_score_rounds(self):
        results = [
            {"specialist": "a", "findings": [], "score": 33, "summary": ""},
            {"specialist": "b", "findings": [], "score": 34, "summary": ""},
        ]
        synth = Orchestrator.synthesise(results)
        # (33 + 34) / 2 = 33.5 → rounds to 34
        assert synth["avg_score"] == 34
