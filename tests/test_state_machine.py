"""Run state machine transition rules."""

import pytest

from preflight.worker.state import ALLOWED_TRANSITIONS, InvalidTransition, assert_can_transition


def test_pending_can_progress_to_personas_ready() -> None:
    assert_can_transition("pending", "personas_ready")


def test_pending_can_fail() -> None:
    assert_can_transition("pending", "failed")


def test_pending_cannot_skip_to_completed() -> None:
    with pytest.raises(InvalidTransition):
        assert_can_transition("pending", "completed")


def test_completed_is_terminal() -> None:
    assert ALLOWED_TRANSITIONS["completed"] == set()


def test_failed_is_terminal() -> None:
    assert ALLOWED_TRANSITIONS["failed"] == set()


def test_full_happy_path() -> None:
    chain = [
        ("pending", "personas_ready"),
        ("personas_ready", "paraphrases_ready"),
        ("paraphrases_ready", "probing"),
        ("probing", "stats_running"),
        ("stats_running", "completed"),
    ]
    for current, target in chain:
        assert_can_transition(current, target)


def test_cannot_revert_state() -> None:
    with pytest.raises(InvalidTransition):
        assert_can_transition("probing", "personas_ready")
