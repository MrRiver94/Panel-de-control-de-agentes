"""Syntax-level contract notes; run after installing backend requirements."""

from app.main import ActivityIn, ControlUpdate


def test_controls_accept_policy_and_budget() -> None:
    control = ControlUpdate(token_budget=4000, reasoning_effort="high")
    assert control.token_budget == 4000


def test_activity_counts_reasoning_tokens() -> None:
    activity = ActivityIn(agent_id="nexus", kind="plan", message="planning", reasoning_tokens=25)
    assert activity.reasoning_tokens == 25
