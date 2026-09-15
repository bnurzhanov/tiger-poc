from __future__ import annotations

import json
from pathlib import Path

import pytest
from tiger_perception.contracts import (
    Frame,
    Observation,
    ProcessEvent,
    RawDetection,
    RawInference,
)
from tiger_perception.sinks import SinkError, validate_process_event

FIXTURES = Path(__file__).parent / "fixtures"


def test_given_typed_process_event_when_serialized_then_wire_fields_round_trip() -> None:
    # Arrange
    event = ProcessEvent(
        event_id="evt-typed-001",
        source_id="camera-01",
        subject_id="station-7",
        observation_type="state",
        value="running",
        unit="status",
        confidence=0.99,
        captured_at="2026-09-15T10:00:00Z",
        produced_at="2026-09-15T10:00:01Z",
        published_at="2026-09-15T10:00:02Z",
        provider="local-replay",
        model="demo-model",
        source="replay",
    )

    # Act
    serialized = validate_process_event(event)
    restored = ProcessEvent.from_dict(serialized)

    # Assert
    assert restored == event


def test_given_valid_fixture_when_validated_then_event_is_accepted() -> None:
    # Arrange
    fixture = json.loads(
        (FIXTURES / "process-event-valid.json").read_text(encoding="utf-8")
    )

    # Act
    validated = validate_process_event(fixture)

    # Assert
    assert validated["eventId"] == "evt-valid-001"


def test_given_invalid_fixture_when_validated_then_event_is_rejected() -> None:
    # Arrange
    fixture = json.loads(
        (FIXTURES / "process-event-invalid.json").read_text(encoding="utf-8")
    )

    # Act and assert
    with pytest.raises(SinkError):
        validate_process_event(fixture)


def test_given_unresolved_observation_when_created_then_resolution_is_explicit() -> None:
    # Arrange and act
    observation = Observation(
        observation_id="obs-001",
        source_id="thermal-01",
        observation_type="temperature",
        value=72.5,
        confidence=0.8,
        captured_at="2026-09-15T10:00:00Z",
        produced_at="2026-09-15T10:00:01Z",
        provider="thermal-sensor",
        model="sensor-firmware-1",
    )

    # Assert
    assert observation.subject_id is None
    assert observation.subject_resolution == "unresolved"


def test_given_raw_inference_when_created_then_raw_detections_are_preserved() -> None:
    # Arrange
    detection = RawDetection(
        class_id=1,
        label="pallet",
        confidence=0.91,
        bounding_box={"xMin": 1.0, "yMin": 2.0, "xMax": 3.0, "yMax": 4.0},
    )

    # Act
    inference = RawInference(
        inference_id="inf-001",
        source_id="camera-01",
        sequence=42,
        captured_at="2026-09-15T10:00:00Z",
        produced_at="2026-09-15T10:00:01Z",
        provider="yolo",
        model="demo-model",
        detections=[detection],
    )

    # Assert
    assert inference.detections == [detection]


def test_given_frame_when_created_then_source_sequence_and_capture_time_are_available() -> None:
    # Arrange and act
    frame = Frame(
        source_id="camera-01",
        sequence=42,
        captured_at="2026-09-15T10:00:00Z",
        payload=b"frame",
    )

    # Assert
    assert (frame.source_id, frame.sequence, frame.captured_at) == (
        "camera-01",
        42,
        "2026-09-15T10:00:00Z",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("capturedAt", "2026-09-15T10:00:00"),
        ("producedAt", "not-a-timestamp"),
        ("publishedAt", "2026-09-15"),
    ],
)
def test_given_invalid_timestamp_when_validated_then_event_is_rejected(
    field: str, value: str
) -> None:
    # Arrange
    event = json.loads(
        (FIXTURES / "process-event-valid.json").read_text(encoding="utf-8")
    )
    event[field] = value

    # Act and assert
    with pytest.raises(SinkError, match=field):
        validate_process_event(event)


@pytest.mark.parametrize("confidence", [-0.1, 1.1, True, float("nan")])
def test_given_invalid_confidence_when_validated_then_event_is_rejected(
    confidence: object,
) -> None:
    # Arrange
    event = json.loads(
        (FIXTURES / "process-event-valid.json").read_text(encoding="utf-8")
    )
    event["confidence"] = confidence

    # Act and assert
    with pytest.raises(SinkError, match="confidence"):
        validate_process_event(event)


def test_given_object_value_when_validated_then_event_is_rejected() -> None:
    # Arrange
    event = json.loads(
        (FIXTURES / "process-event-valid.json").read_text(encoding="utf-8")
    )
    event["value"] = {"count": 2}

    # Act and assert
    with pytest.raises(SinkError, match="value"):
        validate_process_event(event)
