"""Tests for FabricEventstreamSink and dry-run/mock functionality."""

from __future__ import annotations

import json
from pathlib import Path

from tiger_perception.contracts import ProcessEvent
from tiger_perception.sinks import FabricEventstreamSink


def test_given_dry_run_sink_when_published_then_event_is_logged_and_persisted(tmp_path: Path) -> None:
    trace_file = tmp_path / "fabric-trace.jsonl"
    sink = FabricEventstreamSink(dry_run=True, fallback_jsonl_path=trace_file)

    event = ProcessEvent(
        event_id="evt-fabric-001",
        source_id="cell-a-cam-01",
        subject_id="cell-a-pallet-pos-01",
        observation_type="PalletPresent",
        value=True,
        unit="boolean",
        confidence=0.95,
        captured_at="2026-09-15T12:00:00Z",
        produced_at="2026-09-15T12:00:01Z",
        published_at="2026-09-15T12:00:01Z",
        provider="local-yolo",
        model="yolo26n-pallet",
        source="rtsp",
        plant_name="Demo Plant 01",
        plant_id="demo-plant-01",
    )

    success = sink.publish(event)
    assert success is True
    assert trace_file.exists()

    lines = trace_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["eventId"] == "evt-fabric-001"
    assert record["value"] is True
