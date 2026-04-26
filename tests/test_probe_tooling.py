"""Probe-response tool schema generation per question type."""

from __future__ import annotations

from preflight.schemas.survey import Question
from preflight.worker.jobs.probe_response import _answer_tool_for, _format_question


def test_likert5_schema_is_int_1_to_5() -> None:
    q = Question(id="Q", type="likert_5", text="?")
    tool = _answer_tool_for(q)
    schema = tool["input_schema"]["properties"]["response_value"]
    assert schema == {"type": "integer", "minimum": 1, "maximum": 5}


def test_nps_schema_is_0_to_10() -> None:
    q = Question(id="Q", type="nps", text="?")
    tool = _answer_tool_for(q)
    schema = tool["input_schema"]["properties"]["response_value"]
    assert schema["minimum"] == 0
    assert schema["maximum"] == 10


def test_single_choice_schema_uses_option_count() -> None:
    q = Question(id="Q", type="single_choice", text="?", options=["A", "B", "C"])
    tool = _answer_tool_for(q)
    schema = tool["input_schema"]["properties"]["response_value"]
    assert schema == {"type": "integer", "minimum": 0, "maximum": 2}


def test_multi_choice_schema_is_array() -> None:
    q = Question(id="Q", type="multi_choice", text="?", options=["A", "B", "C", "D"])
    tool = _answer_tool_for(q)
    schema = tool["input_schema"]["properties"]["response_value"]
    assert schema["type"] == "array"
    assert schema["items"]["maximum"] == 3


def test_format_question_appends_likert_scale_hint() -> None:
    q = Question(id="Q", type="likert_5", text="How satisfied?")
    formatted = _format_question(q, "How satisfied are you?")
    assert "1" in formatted and "5" in formatted


def test_format_question_lists_options_for_choice() -> None:
    q = Question(id="Q", type="single_choice", text="?", options=["Apple", "Banana"])
    formatted = _format_question(q, "Which fruit?")
    assert "0. Apple" in formatted
    assert "1. Banana" in formatted
