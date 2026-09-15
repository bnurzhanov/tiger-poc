"""Deterministic presence timing, geometry, and failure regressions."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from tiger_perception.contracts import RawDetection, RawInference
from tiger_perception.presence import PresencePolicy, PresenceRule

START = datetime(2026, 9, 15, tzinfo=UTC)
PALLET = RawDetection(0, "pallet", 0.9, {"xMin": 0.3, "yMin": 0.3, "xMax": 0.6, "yMax": 0.6})


def evidence(second: float, *, occupied: bool = True, succeeded: bool = True) -> RawInference:
    """Build normalized inference with controllable time and usability."""
    timestamp = (START + timedelta(seconds=second)).isoformat()
    return RawInference(str(second), "camera-a", int(second * 100), timestamp,
                        timestamp, "test-provider", "test-model",
                        [PALLET] if occupied else [], succeeded=succeeded)


@pytest.fixture
def rule() -> PresenceRule:
    """Create a fresh instance for each test."""
    return PresenceRule(source_id="camera-a", subject_id="position-a",
                        policy=PresencePolicy((0.2, 0.2, 0.8, 0.8)))


def observe(rule: PresenceRule, second: float, **kwargs: bool):
    """Observe evidence at its production time."""
    return rule.observe(evidence(second, **kwargs), now=START + timedelta(seconds=second))


@pytest.mark.parametrize("occupied,seconds", [(True, 2), (False, 3)])
def test_given_initial_evidence_when_window_completes_then_emit_once(rule, occupied, seconds):
    for second in range(seconds):
        assert observe(rule, second, occupied=occupied) is None

    event = observe(rule, seconds, occupied=occupied)

    assert event.value is occupied
    assert event.subject_id == "position-a"
    assert event.confidence == (0.9 if occupied else 0.0)
    assert observe(rule, seconds + 1, occupied=occupied) is None
    assert rule.availability == "current"


def test_given_flicker_when_evidence_restarts_then_delay_is_reset(rule):
    observe(rule, 0)
    observe(rule, 1, occupied=False)
    observe(rule, 2)

    assert observe(rule, 3) is None
    assert observe(rule, 4).value is True


@pytest.mark.parametrize("failure", ["failed", "stale", "missing", "duplicate"])
def test_given_outage_when_recovered_then_reconfirm_without_duplicate(rule, failure):
    for second in range(3):
        observe(rule, second)
    if failure == "failed":
        observe(rule, 3, succeeded=False, occupied=False)
    elif failure == "stale":
        rule.observe(evidence(3, occupied=False), now=START + timedelta(seconds=6))
    elif failure == "duplicate":
        observe(rule, 2, occupied=False)
    else:
        rule.expire(START + timedelta(seconds=5))

    assert rule.confirmed is True
    assert rule.availability == "unavailable"
    assert observe(rule, 7) is None
    assert rule.availability == "confirming"
    assert observe(rule, 8) is None
    assert observe(rule, 9) is None
    assert rule.availability == "current"


def test_given_gap_when_no_explicit_failure_then_pending_window_resets(rule):
    observe(rule, 0, occupied=False)
    observe(rule, 1, occupied=False)

    assert observe(rule, 4, occupied=False) is None
    assert observe(rule, 5, occupied=False) is None
    assert observe(rule, 6, occupied=False) is None
    assert observe(rule, 7, occupied=False).value is False


def test_given_occupied_when_empty_confirmed_then_one_transition(rule):
    events = [observe(rule, second, occupied=second < 3) for second in range(9)]

    assert [event.value for event in events if event] == [True, False]


@pytest.mark.parametrize("detection", [
    replace(PALLET, label="person"), replace(PALLET, confidence=0.1),
    replace(PALLET, bounding_box={"xMin": 0.8, "yMin": 0.8, "xMax": 1.0, "yMax": 1.0}),
])
def test_given_nonqualifying_detection_when_matching_then_not_present(detection):
    assert not PresencePolicy((0.2, 0.2, 0.8, 0.8)).matches(detection)


def test_given_invalid_geometry_when_observed_then_unavailable(rule):
    inference = replace(evidence(0), detections=[replace(PALLET, bounding_box={})])

    assert rule.observe(inference, now=START) is None
    assert rule.availability == "unavailable"


def test_given_wrong_source_when_observed_then_reject(rule):
    with pytest.raises(ValueError, match="source"):
        rule.observe(replace(evidence(0), source_id="camera-b"), now=START)