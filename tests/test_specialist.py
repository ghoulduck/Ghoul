"""Tests for ghoul.specialist — Specialist sub-agent personas."""

import pytest

from ghoul.specialist import (
    SPECIALISTS,
    Specialist,
    get_specialist,
    list_specialists,
)


class TestSpecialistRegistry:
    def test_list_specialists_returns_sorted_names(self):
        names = list_specialists()
        assert names == sorted(names)
        assert len(names) >= 5

    def test_all_predefined_specialists_exist(self):
        expected = {"debugger", "optimizer", "tester", "architect", "security_reviewer"}
        assert expected.issubset(set(SPECIALISTS.keys()))

    def test_get_specialist_valid(self):
        s = get_specialist("debugger")
        assert isinstance(s, Specialist)
        assert s.name == "debugger"

    def test_get_specialist_invalid_raises(self):
        with pytest.raises(KeyError, match="Unknown specialist"):
            get_specialist("nonexistent_agent")

    def test_specialist_has_required_fields(self):
        for name, s in SPECIALISTS.items():
            assert s.name == name
            assert s.description
            assert s.system_prompt
            assert isinstance(s.focus_areas, list)
