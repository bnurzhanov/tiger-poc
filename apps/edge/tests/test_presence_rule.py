"""Tests for the RegionPresenceRule confirmation logic, transition suppression, and state handling."""

from __future__ import annotations

from tiger_perception.presence import (
    PresenceRuleConfig,
    RawDetection,
    RegionConfig,
    RegionPresenceRule,
)


def create_test_rule(occupied_frames: int = 3, empty_frames: int = 3) -> RegionPresenceRule:
    region = RegionConfig(x_min=0.2, y_min=0.2, x_max=0.8, y_max=0.8)
    config = PresenceRuleConfig(
        source_id="cam-01",
        subject_id="pallet-pos-01",
        region=region,
        target_class="pallet",
        confidence_threshold=0.5,
        occupied_confirmation_frames=occupied_frames,
        empty_confirmation_frames=empty_frames,
    )
    return RegionPresenceRule(config)


def test_given_qualifying_detections_when_threshold_reached_then_emits_occupied_event() -> None:
    rule = create_test_rule(occupied_frames=2)
    detection = RawDetection(
        class_id=0,
        label="pallet",
        confidence=0.88,
        bounding_box={"x_min": 0.3, "y_min": 0.3, "x_max": 0.7, "y_max": 0.7},
    )

    # Frame 1: Not confirmed yet
    evt1 = rule.process_frame_detections([detection], "2026-09-15T12:00:00Z")
    assert evt1 is None
    assert rule.confirmed_present is None

    # Frame 2: Threshold 2 met -> confirmed occupied
    evt2 = rule.process_frame_detections([detection], "2026-09-15T12:00:01Z")
    assert evt2 is not None
    assert evt2.value is True
    assert rule.confirmed_present is True

    # Frame 3: Consecutive occupied frames do NOT re-emit (transition suppression)
    evt3 = rule.process_frame_detections([detection], "2026-09-15T12:00:02Z")
    assert evt3 is None


def test_given_occupied_state_when_empty_frames_reach_threshold_then_emits_empty_event() -> None:
    rule = create_test_rule(occupied_frames=1, empty_frames=2)
    detection = RawDetection(
        class_id=0,
        label="pallet",
        confidence=0.9,
        bounding_box={"x_min": 0.3, "y_min": 0.3, "x_max": 0.7, "y_max": 0.7},
    )

    # Frame 1: Occupied
    evt_occ = rule.process_frame_detections([detection], "2026-09-15T12:00:00Z")
    assert evt_occ is not None and evt_occ.value is True

    # Frame 2: Empty frame 1
    evt_empty1 = rule.process_frame_detections([], "2026-09-15T12:00:01Z")
    assert evt_empty1 is None
    assert rule.confirmed_present is True

    # Frame 3: Empty frame 2 -> confirmed empty transition
    evt_empty2 = rule.process_frame_detections([], "2026-09-15T12:00:02Z")
    assert evt_empty2 is not None
    assert evt_empty2.value is False
    assert rule.confirmed_present is False


def test_given_unusable_frame_then_pending_counts_reset_without_emitting_empty() -> None:
    rule = create_test_rule(occupied_frames=2)
    detection = RawDetection(
        class_id=0,
        label="pallet",
        confidence=0.85,
        bounding_box={"x_min": 0.3, "y_min": 0.3, "x_max": 0.7, "y_max": 0.7},
    )

    # Frame 1: Partial occupied count
    rule.process_frame_detections([detection], "2026-09-15T12:00:00Z")
    assert rule.consecutive_occupied_count == 1

    # Frame 2: Unusable frame (e.g. camera drop)
    evt_bad = rule.process_frame_detections([], "2026-09-15T12:00:01Z", is_usable=False)
    assert evt_bad is None
    assert rule.consecutive_occupied_count == 0
    assert rule.is_available is False
