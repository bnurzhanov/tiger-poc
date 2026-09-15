"""Tests for ProcessEvent and Observation contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tiger_perception.contracts import ProcessEvent
from tiger_perception.sinks import SinkError, validate_process_event

FIXTURES = Path(__file__).parent / "fixtures"


def test_given_typed_process_event_when_serialized_then_round_trips() -> None:
    event = ProcessEvent(
        event_id="evt-001",
        source_id="cell-a-cam-01",
        subject_id="cell-a-pallet-pos-01",
        observation_type="PalletPresent",
        value=True,
        unit="boolean",
        confidence=0.92,
        captured_at="2026-09-15T12:00:00Z",
        produced_at="2026-09-15T12:00:01Z",
        published_at="2026-09-15T12:00:01Z",
        provider="local-yolo",
        model="yolo26n-pallet",
        source="rtsp",
        plant_name="Demo Plant 01",
        plant_id="demo-plant-01",
    )

    serialized = validate_process_event(event)
    restored = ProcessEvent.from_dict(serialized)

    assert restored == event
    assert serialized["plantName"] == "Demo Plant 01"
    assert serialized["plantId"] == "demo-plant-01"


def test_given_valid_fixture_when_validated_then_accepted() -> None:
    fixture = json.loads((FIXTURES / "process-event-valid.json").read_text(encoding="utf-8"))
    validated = validate_process_event(fixture)
    assert validated["eventId"] == "evt-valid-001"
    assert validated["value"] is True


def test_given_invalid_fixture_when_validated_then_raises() -> None:
    fixture = json.loads((FIXTURES / "process-event-invalid.json").read_text(encoding="utf-8"))
    with pytest.raises(SinkError):
        validate_process_event(fixture)
